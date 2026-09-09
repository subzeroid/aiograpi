"""Explicitly enabled, single-attempt CAA checks on ten fresh test accounts.

Run with AIOGRAPI_RUN_CAA_LIVE=1 and TEST_ACCOUNTS_URL configured. A private
AIOGRAPI_CAA_ACCOUNTS_FILE may instead supply ten freshly assigned records.
Do not reuse these records for a second run. Credentials and responses are never
included in pytest failures; successful settings are saved only in the private
AIOGRAPI_CAA_LIVE_DIR (or pytest's temporary directory).
"""

import asyncio
import copy
import json
import logging
import os
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
import pytest

from aiograpi import Client

fresh_login_only = pytest.mark.skipif(
    os.getenv("AIOGRAPI_RUN_CAA_LIVE") != "1", reason="fresh CAA logins require explicit opt-in"
)


class ProbeStopped(BaseException):
    """Leave library fallback/retry handlers immediately."""


@pytest.fixture(scope="module")
def fresh_accounts():
    try:
        if path := os.getenv("AIOGRAPI_CAA_ACCOUNTS_FILE"):
            accounts = json.loads(Path(path).read_text())
        else:
            parts = urlsplit(os.environ["TEST_ACCOUNTS_URL"])
            query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "count"]
            source = urlunsplit(
                (parts.scheme, parts.netloc, parts.path, urlencode([*query, ("count", "10")]), parts.fragment)
            )
            response = httpx.get(source, timeout=40)
            response.raise_for_status()
            accounts = response.json()
        assert isinstance(accounts, list) and len(accounts) == 10
        assert len({account["username"].casefold() for account in accounts}) == 10
        assert all(
            all(account.get(key) for key in ("username", "password", "user_id", "proxy", "client_settings"))
            for account in accounts
        )
    except Exception as exc:
        pytest.fail(f"Fresh-account setup failed ({type(exc).__name__})", pytrace=False)
    return accounts


@pytest.fixture(scope="module")
def private_results(tmp_path_factory):
    path = os.getenv("AIOGRAPI_CAA_LIVE_DIR")
    root = Path(path) if path else tmp_path_factory.mktemp("caa-live")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    root.chmod(0o700)
    return root


def write_private(path, data):
    with path.open("w") as stream:
        path.chmod(0o600)
        json.dump(data, stream, indent=2)


@fresh_login_only
@pytest.mark.parametrize("index", range(10), ids=[f"account-{n:02d}" for n in range(1, 11)])
def test_caa_login_with_private_curl(fresh_accounts, private_results, index):
    asyncio.run(_caa_probe(fresh_accounts, private_results, index))


async def _caa_probe(fresh_accounts, private_results, index):
    account = fresh_accounts[index]
    result_dir = private_results / f"account-{index + 1:02d}"
    result_dir.mkdir(mode=0o700, exist_ok=True)
    marker = result_dir / "started.json"
    try:
        with marker.open("x") as stream:
            marker.chmod(0o600)
            json.dump({"max_password_submissions": 1}, stream)
    except FileExistsError:
        pytest.fail(
            "This account probe was already started; use fresh records and a new results directory", pytrace=False
        )

    report = {"password_submissions": 0, "responses": [], "session_validated": False}
    started = time.monotonic()
    previous_logging = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    client = None
    try:
        settings = copy.deepcopy(account["client_settings"])
        settings.pop("totp_seed", None)
        settings.update(session_retry_total=0, public_request_retries_count=1, private_transport="curl")
        client = Client(settings=settings, proxy=account["proxy"])
        client.username, client.password = account["username"], account["password"]
        if not client.bloks_versioning_id:
            pytest.skip("Assigned profile has no known CAA Bloks hash")

        async def stop(*args, **kwargs):
            raise ProbeStopped("Manual account verification required")

        client.challenge_code_handler = stop
        client.change_password_handler = stop
        client.handle_exception = lambda _client, exc: (_ for _ in ()).throw(exc)
        for session in (client.private, client.public, client.graphql):
            original_request = session.request

            async def request(method, url, _request=original_request, **kwargs):
                target = urlsplit(str(url))
                if target.hostname not in {"i.instagram.com", "b.i.instagram.com", "www.instagram.com"}:
                    raise ProbeStopped("Unexpected destination")
                if any(route in target.path for route in ("/challenge/", "/auth_platform/", "/accounts/login/")):
                    raise ProbeStopped("Unexpected login or verification route")
                if len(report["responses"]) >= 25 or time.monotonic() - started > 180:
                    raise ProbeStopped("Probe request or time budget reached")
                if "caa.login.async.send_login_request" in target.path:
                    if report["password_submissions"]:
                        raise ProbeStopped("Duplicate password submission blocked")
                    report["password_submissions"] += 1
                kwargs.update(timeout=httpx.Timeout(25, connect=10), follow_redirects=False)
                response = await _request(method, url, **kwargs)
                report["responses"].append(response.status_code)
                if response.status_code == 429 or 300 <= response.status_code < 400:
                    raise ProbeStopped("HTTP 429 or unexpected redirect; stopped")
                return response

            session.request = request

        client._clear_session_state(
            clear_authorization_data=True,
            clear_authorization_header=True,
            clear_private_cookies=True,
            clear_public_cookies=True,
            clear_last_login=True,
        )
        assert not client.user_id
        assert await client.bloks_caa_login_prepare(username=client.username)
        response = await client.bloks_caa_login_send_request(
            client.password, username=client.username, auto_prepare=False
        )
        if not client.bloks_apply_login_response(response):
            if client.bloks_extract_two_step_verification_context(response) or client.bloks_caa_login_needs_two_step(
                response
            ):
                report["verification_required"] = True
                pytest.skip("CAA reached account verification; session success was not established")
            pytest.fail("CAA did not return a session", pytrace=False)
        report["session_validated"] = str((await client.account_info()).pk) == str(account["user_id"])
        assert report["session_validated"]
        assert report["password_submissions"] == 1
        write_private(result_dir / "settings.private.json", client.get_settings())
    except ProbeStopped as exc:
        report["stop_reason"] = str(exc)
        pytest.fail(str(exc), pytrace=False)
    except Exception as exc:
        report["exception"] = type(exc).__name__
        pytest.fail(f"CAA probe failed ({type(exc).__name__})", pytrace=False)
    finally:
        if client:
            for session in (client.private, client.public, client.graphql):
                await session._close()
        logging.disable(previous_logging)
        report["elapsed_seconds"] = round(time.monotonic() - started, 2)
        write_private(result_dir / "result.sanitized.json", report)


@pytest.mark.skipif(
    os.getenv("AIOGRAPI_RUN_PRIVATE_CURL_LIVE") != "1", reason="saved-session live reads require explicit opt-in"
)
def test_saved_session_private_curl():
    """Two read-only calls with original proxy; no login or recovery requests."""

    async def probe():
        previous_logging = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        client = None
        try:
            account = json.loads(Path(os.environ["AIOGRAPI_PRIVATE_ACCOUNT_FILE"]).read_text())
            settings = json.loads(Path(os.environ["AIOGRAPI_PRIVATE_SETTINGS_FILE"]).read_text())
            settings["private_transport"] = "curl"
            client = Client(settings=settings, proxy=account["proxy"], request_timeout=0)
            client.handle_exception = lambda _client, exc: (_ for _ in ()).throw(exc)
            original = client.private.request
            seen = []

            async def guarded(method, url, **kwargs):
                target = urlsplit(str(url))
                allowed = {"/api/v1/accounts/current_user/", f"/api/v1/users/{account['user_id']}/info/"}
                if (
                    method.lower() != "get"
                    or target.hostname != "i.instagram.com"
                    or target.path not in allowed
                    or len(seen) >= 2
                ):
                    raise ProbeStopped("Unexpected request or retry blocked")
                seen.append(target.path)
                kwargs.update(timeout=httpx.Timeout(25, connect=10), follow_redirects=False)
                response = await original(method, url, **kwargs)
                if destination := os.getenv("AIOGRAPI_PRIVATE_RESULTS_DIR"):
                    directory = Path(destination)
                    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
                    write_private(
                        directory / f"{len(seen)}.response.private.json",
                        {
                            "status": response.status_code,
                            "http_version": response.http_version,
                            "body": response.text,
                        },
                    )
                if response.status_code != 200 or response.http_version != "HTTP/2":
                    raise ProbeStopped(
                        f"Expected HTTP 200 over HTTP/2; got {response.status_code} over {response.http_version}"
                    )
                return response

            client.private.request = guarded

            async def stop(*args, **kwargs):
                raise ProbeStopped("Unexpected public request blocked")

            client.public.request = client.graphql.request = stop
            assert str((await client.account_info()).pk) == str(account["user_id"])
            assert str((await client.user_info_v1(account["user_id"])).pk) == str(account["user_id"])
            assert len(seen) == 2
            if destination := os.getenv("AIOGRAPI_PRIVATE_SETTINGS_OUTPUT"):
                write_private(Path(destination), client.get_settings())
        except ProbeStopped as exc:
            pytest.fail(str(exc), pytrace=False)
        except Exception as exc:
            pytest.fail(f"Saved-session probe failed ({type(exc).__name__})", pytrace=False)
        finally:
            if client:
                for session in (client.private, client.public, client.graphql):
                    await session._close()
            logging.disable(previous_logging)

    asyncio.run(probe())

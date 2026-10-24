# protects: Async login diagnostics retain response order without exporting account material.
# fails_when: Observation changes login outcomes, leaks payloads, or leaves callbacks/sessions modified.
# why_new: Existing async login tests do not exercise a standalone sanitized observer or its CLI lifecycle.
import asyncio
import base64
import functools
import importlib.util
import io
import json
import logging
import stat
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
import requests
from Cryptodome.PublicKey import RSA
from urllib3.response import HTTPResponse

from aiograpi import Client
from aiograpi.transports import CurlH2Transport
from tests.regression.test_utls_transport import native as native
from tests.regression.test_utls_transport import reply

SCRIPT = Path(__file__).resolve().parents[2] / "examples" / "diagnose_login.py"
LOGIN = "https://i.instagram.com/api/v1/accounts/login/"
CAA = "https://b.i.instagram.com/api/v1/bloks/async_action/com.bloks.www.bloks.caa.login.async.send_login_request/"
SECRET = "DO_NOT_SHARE_test_secret_12345"
CURL_REQUEST = CurlH2Transport.handle_async_request


def test_standalone_async_diagnostic_is_available_without_other_example_helpers():
    assert SCRIPT.exists(), "The standalone async login diagnostic script is missing"


def async_test(function):
    @functools.wraps(function)
    def run(*args, **kwargs):
        return asyncio.run(function(*args, **kwargs))

    return run


@pytest.fixture(autouse=True)
def deny_unexpected_network(monkeypatch):
    async def deny(*args, **kwargs):
        raise AssertionError("Unexpected network attempt in offline diagnostic test")

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", deny)
    monkeypatch.setattr(CurlH2Transport, "handle_async_request", deny)


@pytest.fixture
def diagnostic():
    assert SCRIPT.exists(), "The standalone async login diagnostic script is missing"
    spec = importlib.util.spec_from_file_location("async_login_diagnostic", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def clients():
    opened = []

    def make(**kwargs):
        client = Client(**kwargs)
        client.request_timeout = 0
        client.small_delay = AsyncMock()
        opened.append(client)
        return client

    yield make

    async def close():
        for client in opened:
            for session in (client.private, client.public, client.graphql):
                await type(session)._close(session)

    asyncio.run(close())


def response(request, status, body, content_type="application/json"):
    return httpx.Response(status, request=request, content=body, headers={"Content-Type": content_type})


def install_transport(client, handler):
    # Use the real AsyncClient request path and the SDK's session wrappers.
    client.private._client._transport = httpx.MockTransport(handler)
    client.private._client._mounts = {}
    configure_login(client)


def configure_login(client):
    client.caa_aac = '{"aaccs":"synthetic-context"}'
    client.bloks_caa_login_prepare = AsyncMock(return_value=True)
    client.pre_login_flow = AsyncMock(return_value=True)
    client.password_encrypt = AsyncMock(return_value="#PWD_INSTAGRAM:4:1:synthetic")
    client.login_flow = AsyncMock(return_value=True)


@pytest.mark.parametrize("route", ["direct", "redirect", "redirect-failure"])
def test_cli_public_curl_fetches_real_password_keys_through_requests_timeout_boundary(
    diagnostic, clients, monkeypatch, tmp_path, route
):
    public_calls, private_calls = [], []
    publickey = base64.b64encode(RSA.generate(1024).public_key().export_key(format="DER")).decode()

    class OfflineConnection:
        def urlopen(self, method, url, **kwargs):
            public_calls.append((method, url, kwargs["timeout"]))
            if route != "direct" and len(public_calls) == 1:
                return HTTPResponse(
                    status=302,
                    body=io.BytesIO(SECRET.encode()),
                    preload_content=False,
                    headers={"location": "https://i.instagram.com/api/v1/qe/sync/?private=" + SECRET},
                )
            if route == "redirect-failure":
                raise requests.exceptions.ConnectionError(SECRET)
            return HTTPResponse(
                status=200,
                body=io.BytesIO(b"{}"),
                preload_content=False,
                headers={
                    "content-type": "application/json",
                    "ig-set-password-encryption-key-id": "1",
                    "ig-set-password-encryption-pub-key": publickey,
                },
            )

    class OfflineAdapter(requests.adapters.HTTPAdapter):
        def __init__(self, *, impersonate_browser_type):
            super().__init__()

        def get_connection_with_tls_context(self, *args, **kwargs):
            return OfflineConnection()

    # Keep the optional package boundary offline while retaining Requests'
    # real send/timeout conversion and CurlSession's real async request path.
    monkeypatch.setitem(sys.modules, "curl_adapter", SimpleNamespace(CurlCffiAdapter=OfflineAdapter))
    client = clients(private_transport="requests", public_transport="curl")

    async def send(request):
        private_calls.append(str(request.url))
        return response(request, 400, b'{"status":"fail","error_type":"bad_password"}')

    install_transport(client, send)
    del client.password_encrypt  # Exercise password_publickeys and RSA encryption.
    monkeypatch.setattr(diagnostic, "Client", Mock(return_value=client))
    monkeypatch.setenv("IG_USERNAME", "synthetic-user")
    monkeypatch.setenv("IG_PASSWORD", SECRET)
    monkeypatch.delenv("IG_PROXY", raising=False)
    settings, output = tmp_path / "settings.json", tmp_path / "report.json"
    settings.write_text('{"public_transport":"curl"}')
    assert diagnostic.main(["--settings", str(settings), "--report", str(output)]) == 1
    report = json.loads(output.read_text())
    assert report["exception"]["type"] == ("ConnectError" if route == "redirect-failure" else "BadPassword")
    assert len(public_calls) == (1 if route == "direct" else 2)
    assert public_calls[0][0:2] == ("GET", "/api/v1/qe/sync/")
    assert public_calls[0][2].connect_timeout == 10
    assert public_calls[0][2].read_timeout == 30
    assert private_calls == ([] if route == "redirect-failure" else [CAA])
    assert [item["http_status"] for item in report["responses"]] == {
        "direct": [200, 400],
        "redirect": [302, 200, 400],
        "redirect-failure": [302],
    }[route]
    assert report["responses"][0]["endpoint"] == "qe/sync"
    assert client.public._client.hooks["response"] == []
    assert SECRET not in output.read_text()


@pytest.mark.parametrize("transport_failure", [False, True])
@async_test
async def test_actual_httpx_redirects_are_ordered_once_even_before_transport_failure(
    diagnostic, clients, transport_failure
):
    final = "https://b.i.instagram.com/api/v1/oauth_token.fetch/?private=" + SECRET
    expected_calls = [CAA, LOGIN + "?private=" + SECRET, final]

    async def run(observe):
        client = clients(private_transport="requests")
        calls, original_hooks_seen = [], []

        async def send(request):
            calls.append(str(request.url))
            if len(calls) < 3:
                return httpx.Response(
                    302 if len(calls) == 1 else 307,
                    request=request,
                    content=SECRET.encode(),
                    headers={"location": expected_calls[len(calls)], "content-type": "text/plain"},
                )
            if transport_failure:
                raise httpx.ConnectError(SECRET, request=request)
            return response(request, 400, b'{"status":"fail","error_type":"bad_password"}')

        install_transport(client, send)

        async def existing_hook(raw):
            original_hooks_seen.append(raw.status_code)

        hooks = client.private._client.event_hooks["response"]
        hooks.append(existing_hook)
        if observe:
            report = await diagnostic.diagnose(client, "synthetic-user", SECRET)
            error = report["exception"]["type"]
        else:
            with diagnostic.quiet_library():
                try:
                    await client.login("synthetic-user", SECRET)
                except Exception as exc:
                    error = type(exc).__name__
            report = None
        assert calls == expected_calls
        assert client.private._client.event_hooks["response"] is hooks
        assert hooks == [existing_hook]
        return error, calls, original_hooks_seen, report

    plain = await run(False)
    observed = await run(True)
    assert observed[:3] == plain[:3]
    report = observed[3]
    assert [item["http_status"] for item in report["responses"]] == (
        [302, 307] if transport_failure else [302, 307, 400]
    )
    assert report["caa_attempts"][0]["response_end"] == len(report["responses"])
    assert SECRET not in json.dumps(report)


@async_test
async def test_response_body_read_failure_keeps_original_error_and_restores_httpx_hooks(diagnostic, clients):
    client = clients(private_transport="requests")
    original_error = httpx.ReadError(SECRET)
    caught = []

    class FailingBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"first"
            raise original_error

    async def send(request):
        return httpx.Response(200, request=request, stream=FailingBody())

    install_transport(client, send)

    async def login(*args, **kwargs):
        try:
            await client.private.get(CAA)
        except Exception as exc:
            caught.append(exc)
            raise

    client.login = login
    hooks = client.private._client.event_hooks["response"]
    report = await diagnostic.diagnose(client, "synthetic-user", SECRET)
    assert caught == [original_error]
    assert report["exception"]["type"] == "ReadError"
    assert report["responses"] == [{"inspection_error": True}]
    assert client.private._client.event_hooks["response"] is hooks
    assert hooks == []
    assert SECRET not in json.dumps(report)


def test_sync_cli_boundary_converts_cancellation_to_quiet_failure_and_saved_report(
    diagnostic, clients, monkeypatch, tmp_path, capsys
):
    client = clients(private_transport="requests")
    client.login = AsyncMock(side_effect=asyncio.CancelledError(SECRET))
    closed = []
    for name in ("private", "public", "graphql"):

        async def close(name=name):
            closed.append(name)

        monkeypatch.setattr(getattr(client, name), "_close", close)
    monkeypatch.setattr(diagnostic, "Client", Mock(return_value=client))
    monkeypatch.setenv("IG_USERNAME", "synthetic-user")
    monkeypatch.setenv("IG_PASSWORD", SECRET)
    monkeypatch.delenv("IG_PROXY", raising=False)
    output = tmp_path / "report.json"
    assert diagnostic.main(["--settings", str(tmp_path / "settings.json"), "--report", str(output)]) == 1
    assert closed == ["private", "public", "graphql"]
    report = json.loads(output.read_text())
    assert report["exception"]["type"] == "CancelledError"
    assert report["settings_saved"] is True
    streams = capsys.readouterr()
    assert SECRET not in output.read_text() + streams.out + streams.err


def test_script_entrypoint_cancellation_has_no_traceback_or_private_message(tmp_path):
    code = """
import asyncio,importlib.util,sys
spec=importlib.util.spec_from_file_location('standalone_diagnostic',sys.argv[1])
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
async def cancelled(argv=None):
    raise asyncio.CancelledError(sys.argv[2])
module.async_main=cancelled
raise SystemExit(module.main([]))
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(SCRIPT), SECRET], capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert SECRET not in result.stdout + result.stderr


@async_test
async def test_actual_curl_session_and_transport_reach_async_native_boundary_once(diagnostic, clients, monkeypatch):
    client = clients()
    configure_login(client)
    transport = client.private._client._transport
    transport._client = SimpleNamespace(
        request=AsyncMock(
            return_value=SimpleNamespace(
                status_code=400,
                content=json.dumps({"status": "fail", "error_type": "bad_password", "message": SECRET}).encode(),
                headers=httpx.Headers({"content-type": "application/json"}),
                http_version=transport._http2,
            )
        ),
        close=AsyncMock(),
    )
    monkeypatch.setattr(CurlH2Transport, "handle_async_request", CURL_REQUEST)
    report = await diagnostic.diagnose(client, "synthetic-user", SECRET)
    assert report["exception"]["type"] == "BadPassword"
    assert report["responses"][0]["endpoint"] == "caa/send_login_request"
    assert report["responses"][0]["http_status"] == 400
    transport._client.request.assert_awaited_once()
    assert SECRET not in json.dumps(report)


def test_cli_real_async_utls_transport_uses_uniform_deadline_without_exporting_path(
    diagnostic, clients, native, monkeypatch, tmp_path
):
    client = clients(private_transport="utls", utls_library_path=SECRET)
    configure_login(client)
    native.replies.append(
        reply(status=400, body=json.dumps({"status": "fail", "error_type": "bad_password", "message": SECRET}).encode())
    )
    monkeypatch.setattr(diagnostic, "Client", Mock(return_value=client))
    monkeypatch.setenv("IG_USERNAME", "synthetic-user")
    monkeypatch.setenv("IG_PASSWORD", SECRET)
    monkeypatch.delenv("IG_PROXY", raising=False)
    settings, output = tmp_path / "settings.json", tmp_path / "report.json"
    settings.write_text('{"private_transport":"utls"}')
    assert diagnostic.main(["--settings", str(settings), "--report", str(output), "--utls-library-path", SECRET]) == 1
    assert len(native.payloads) == 1
    assert native.payloads[0]["timeoutMilliseconds"] <= 30000
    assert native.payloads[0]["timeoutMilliseconds"] > 29000
    assert native.payloads[0]["requestMethod"] == "POST"
    assert "destroy" in native.events
    report = json.loads(output.read_text())
    assert report["exception"]["type"] == "BadPassword"
    assert report["responses"][0]["http_status"] == 400
    assert SECRET not in output.read_text()


@pytest.mark.parametrize("transport", ["requests", "curl"])
@pytest.mark.parametrize(
    "error_type,exception_type", [("bad_password", "BadPassword"), ("needs_upgrade", "ClientNeedsUpgradeError")]
)
@async_test
async def test_actual_async_login_records_error_without_session_hook_support(
    diagnostic, clients, transport, error_type, exception_type
):
    client = clients(private_transport=transport)
    calls = []

    async def send(request):
        calls.append(str(request.url))
        return response(
            request, 400, json.dumps({"status": "fail", "error_type": error_type, "message": SECRET}).encode()
        )

    install_transport(client, send)
    original_request = client.private.request
    report = await diagnostic.diagnose(client, "synthetic-user", SECRET)
    assert calls == [CAA]
    assert report["exception"]["type"] == exception_type
    assert report["responses"][0]["json"]["error_type"] == error_type
    assert report["caa_attempts"] == [{"outcome": "error", "response_start": 0, "response_end": 1}]
    assert "request" not in vars(client.private)
    assert client.private.request == original_request
    assert SECRET not in json.dumps(report)


@async_test
async def test_caa_legacy_caa_captures_each_outcome_before_fallback_overwrites_state(diagnostic, clients):
    client = clients(private_transport="requests")
    calls = []

    async def send(request):
        calls.append(str(request.url))
        assert calls == [CAA, LOGIN, CAA][: len(calls)]
        body = (
            {"status": "fail", "error_type": "needs_upgrade", "message": SECRET}
            if str(request.url) == LOGIN
            else {"status": "ok", "markers": ["CAA_LOGIN_FALLBACK:" + SECRET], "private": SECRET}
        )
        return response(request, 400 if str(request.url) == LOGIN else 200, json.dumps(body).encode())

    install_transport(client, send)
    report = await diagnostic.diagnose(client, "synthetic-user", SECRET, verification_code="123456")
    assert calls == [CAA, LOGIN, CAA]
    assert report["exception"]["error_type"] == "needs_upgrade"
    # aiograpi restores the original legacy error after an unsuccessful fallback.
    assert report["last_json"]["status"] == "fail"
    assert report["responses"][-1]["json"]["status"] == "ok"
    assert [item["endpoint"] for item in report["responses"]] == [
        "caa/send_login_request",
        "accounts/login",
        "caa/send_login_request",
    ]
    assert [(a["response_start"], a["response_end"]) for a in report["caa_attempts"]] == [(0, 1), (2, 3)]
    for attempt in report["caa_attempts"]:
        assert attempt["logged_in"] is False
        assert attempt["fallback_marker_present"] is True
        assert attempt["two_factor_context_present"] is False
    assert SECRET not in json.dumps(report)


@pytest.mark.parametrize("session_material", [False, True])
@pytest.mark.parametrize("inspection_failure", [False, True])
@async_test
async def test_actual_two_factor_http200_preserves_plain_login_outcome(
    diagnostic, clients, monkeypatch, session_material, inspection_failure
):
    if inspection_failure:
        monkeypatch.setattr(
            diagnostic.BLOKS_PARSER, "bloks_extract_login_response", Mock(side_effect=ValueError(SECRET))
        )
    verify = "https://i.instagram.com/api/v1/bloks/async_action/com.bloks.www.two_step_verification.verify_code.async/"
    expected = [
        CAA,
        "https://i.instagram.com/api/v1/bloks/apps/com.bloks.www.two_step_verification.entrypoint/",
        "https://i.instagram.com/api/v1/bloks/apps/com.bloks.www.two_step_verification.method_picker/",
        "https://i.instagram.com/api/v1/bloks/async_action/com.bloks.www.two_step_verification.method_picker.navigation.async/",
        verify,
    ]

    async def run(observe):
        client = clients(private_transport="requests")
        calls = []

        async def send(request):
            calls.append(str(request.url))
            assert calls == expected[: len(calls)]
            body = (
                {"status": "ok", "two_step_verification_context": SECRET}
                if str(request.url) == CAA
                else (
                    embedded_bloks(session=session_material, user=True)
                    if str(request.url) == verify
                    else {"status": "ok"}
                )
            )
            return response(request, 200, json.dumps(body).encode())

        install_transport(client, send)
        if observe:
            report = await diagnostic.diagnose(client, "synthetic-user", SECRET, verification_code="123456")
            outcome, error = report["outcome"], report.get("exception", {}).get("type")
        else:
            with diagnostic.quiet_library():
                try:
                    outcome = (
                        "success"
                        if await client.login("synthetic-user", SECRET, verification_code="123456")
                        else "false_return"
                    )
                    error = None
                except Exception as exc:
                    outcome, error = "error", type(exc).__name__
            report = None
        assert calls == expected
        return outcome, error, calls, report

    baseline = await run(False)
    observed = await run(True)
    assert observed[:3] == baseline[:3]
    report = observed[3]
    assert report["outcome"] == ("success" if session_material else "error")
    assert report.get("exception", {}).get("type") == (None if session_material else "TwoFactorRequired")
    assert len(report["responses"]) == 5
    assert report["responses"][-1]["bloks"]["sessionid_cookie_present"] is (session_material and not inspection_failure)
    assert SECRET not in json.dumps(report)


@pytest.mark.parametrize("failure", [RuntimeError(SECRET), asyncio.CancelledError(), SystemExit(SECRET)])
@async_test
async def test_restores_exact_instance_overrides_callbacks_and_logging_on_failure(diagnostic, clients, failure):
    client = clients(private_transport="requests")
    original = AsyncMock(side_effect=failure)
    client.bloks_caa_login = original
    handler, challenge, change = Mock(), Mock(), Mock()
    client.handle_exception, client.challenge_code_handler, client.change_password_handler = handler, challenge, change
    request_override = client.private.request
    client.private.request = request_override
    previous_logging = logging.root.manager.disable
    settings_before = json.dumps(client.settings, sort_keys=True)
    if isinstance(failure, (asyncio.CancelledError, SystemExit)):
        with pytest.raises(type(failure)) as caught:
            await diagnostic.diagnose(client, "synthetic-user", SECRET)
        assert caught.value is failure
    else:
        report = await diagnostic.diagnose(client, "synthetic-user", SECRET)
        assert report["exception"]["type"] == "RuntimeError"
        assert SECRET not in json.dumps(report)
    assert client.bloks_caa_login is original
    assert client.private.request is request_override
    assert "request" not in vars(client.public)
    assert client.handle_exception is handler
    assert client.challenge_code_handler is challenge
    assert client.change_password_handler is change
    assert client.private._client.event_hooks["response"] == []
    assert client.public._client.event_hooks["response"] == []
    assert logging.root.manager.disable == previous_logging
    assert json.dumps(client.settings, sort_keys=True) == settings_before
    assert not client.private._client.is_closed
    original.assert_awaited_once_with(verification_code="")


@async_test
async def test_cancelled_task_restores_observer_and_preserves_caller_sessions(diagnostic, clients):
    client = clients(private_transport="requests")
    entered = asyncio.Event()

    async def wait(*args, **kwargs):
        entered.set()
        await asyncio.Event().wait()

    original = client.bloks_caa_login = wait
    before = {
        key: vars(client).get(key) for key in ("handle_exception", "challenge_code_handler", "change_password_handler")
    }
    task = asyncio.create_task(diagnostic.diagnose(client, "synthetic-user", SECRET))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert client.bloks_caa_login is original
    for key, value in before.items():
        assert vars(client).get(key) is value
    assert "request" not in vars(client.private)
    assert "request" not in vars(client.public)
    assert not client.private._client.is_closed
    assert client.private._client.event_hooks["response"] == []
    assert client.public._client.event_hooks["response"] == []


@async_test
async def test_manual_callbacks_stop_automatic_input_and_restore_class_resolution(diagnostic, clients):
    client = clients(private_transport="requests")
    original = {
        key: getattr(client, key) for key in ("challenge_code_handler", "change_password_handler", "handle_exception")
    }

    async def login(*args, **kwargs):
        client.challenge_code_handler("synthetic-user", "email")

    client.login = login
    report = await diagnostic.diagnose(client, "synthetic-user", SECRET)
    assert report["exception"]["type"] == "ChallengeRequired"
    for key, value in original.items():
        assert key not in vars(client)
        assert getattr(client, key) == value


@async_test
async def test_observation_failure_never_changes_returned_response_or_caa_object(diagnostic, clients, monkeypatch):
    client = clients(private_transport="requests")
    raw = response(httpx.Request("GET", "https://www.instagram.com/"), 200, b"{}")
    outcome = {"logged_in": True, "result": {}, "reason": ""}
    request = AsyncMock(return_value=raw)
    client.public.request = request
    client.bloks_caa_login = AsyncMock(return_value=outcome)

    async def login(*args, **kwargs):
        assert await client.public.get("https://www.instagram.com/") is raw
        assert await client.bloks_caa_login() is outcome
        return True

    client.login = login
    monkeypatch.setattr(diagnostic, "summarize_response", Mock(side_effect=ValueError(SECRET)))
    monkeypatch.setattr(diagnostic, "summarize_caa_outcome", Mock(side_effect=ValueError(SECRET)))
    report = await diagnostic.diagnose(client, "synthetic-user", SECRET)
    assert report["outcome"] == "success"
    assert report["responses"] == [{"inspection_error": True}]
    assert report["caa_attempts"] == [
        {"outcome": "returned", "response_start": 1, "response_end": 1, "inspection_error": True}
    ]
    assert client.public.request is request
    assert SECRET not in json.dumps(report)


@async_test
async def test_library_output_and_untrusted_request_metadata_are_never_exported(diagnostic, clients, capsys, caplog):
    client = clients(private_transport="requests")

    async def send(request):
        print(SECRET)
        logging.getLogger("aiograpi").error(SECRET)
        return httpx.Response(
            400,
            json={"status": "fail", "error_type": "bad_password", "message": SECRET, "password": SECRET},
            headers={
                "Set-Cookie": "sessionid=" + SECRET,
                "Authorization": SECRET,
                "Server": SECRET,
                "Proxy-Status": SECRET,
            },
            request=request,
        )

    install_transport(client, send)
    report = await diagnostic.diagnose(client, SECRET, SECRET, verification_code=SECRET)
    streams = capsys.readouterr()
    assert SECRET not in json.dumps(report) + streams.out + streams.err + caplog.text


@pytest.mark.parametrize("timeout", [None, 2])
@pytest.mark.parametrize("native", [False, True])
@async_test
async def test_bound_requests_uses_supported_timeout_and_restores_original(diagnostic, timeout, native):
    class Session:
        request = AsyncMock(return_value=object())

    session = Session()
    original = session.request
    with diagnostic.bound_requests(session, total_timeout=30 if native else None):
        await session.request("POST", "https://fixture.invalid/", timeout=timeout)
        bound = original.call_args.kwargs["timeout"]
        if timeout is not None:
            assert bound == timeout
        elif native:
            assert bound == 30
        else:
            assert isinstance(bound, httpx.Timeout)
            assert bound.connect == 10 and bound.read == 30
    assert "request" not in vars(session)
    assert session.request is original


@pytest.mark.parametrize("retry_settings", [{}, {"session_retry_total": 4, "public_request_retries_count": 2}])
def test_cli_saves_failure_settings_atomically_and_closes_every_owned_session(
    diagnostic, clients, monkeypatch, tmp_path, capsys, retry_settings
):
    client = clients(private_transport="requests")

    async def send(request):
        return response(
            request, 400, json.dumps({"status": "fail", "error_type": "bad_password", "message": SECRET}).encode()
        )

    install_transport(client, send)
    client.private.set_cookies({"private-cookie": SECRET})
    settings, output = tmp_path / "settings.json", tmp_path / "report.json"
    settings.write_text(json.dumps(retry_settings))
    output.write_text("replace-existing")
    settings.chmod(0o644)
    output.chmod(0o644)
    factory = Mock(return_value=client)
    monkeypatch.setattr(diagnostic, "Client", factory)
    monkeypatch.setenv("IG_USERNAME", "synthetic-user")
    monkeypatch.setenv("IG_PASSWORD", SECRET)
    monkeypatch.delenv("IG_PROXY", raising=False)
    closes = []
    for name in ("private", "public", "graphql"):
        session = getattr(client, name)
        original = session._close

        async def close(original=original, name=name):
            print(SECRET)
            closes.append(name)
            await original()

        monkeypatch.setattr(session, "_close", close)
    assert diagnostic.main(["--settings", str(settings), "--report", str(output)]) == 1
    report = json.loads(output.read_text())
    assert report["exception"]["type"] == "BadPassword"
    assert report["settings_saved"] is True
    assert sorted(closes) == ["graphql", "private", "public"]
    assert "request" not in vars(client.private)
    assert stat.S_IMODE(settings.stat().st_mode) == stat.S_IMODE(output.stat().st_mode) == 0o600
    assert SECRET in settings.read_text()
    for key in ("session_retry_total", "public_request_retries_count"):
        assert json.loads(settings.read_text()).get(key) == retry_settings.get(key)
    assert factory.call_args.kwargs["settings"]["session_retry_total"] == 0
    assert factory.call_args.kwargs["settings"]["public_request_retries_count"] == 1
    streams = capsys.readouterr()
    assert SECRET not in output.read_text() + streams.out + streams.err


def test_cli_utls_configuration_stays_private_and_deadline_is_numeric(diagnostic, clients, monkeypatch, tmp_path):
    client = clients(private_transport="requests")
    client.private_transport = "utls"
    requests = []

    async def request(*args, **kwargs):
        requests.append(kwargs["timeout"])
        return response(httpx.Request("POST", CAA), 200, b"{}")

    client.private.request = request

    async def login(*args, **kwargs):
        await client.private.post(CAA)
        raise RuntimeError(SECRET)

    client.login = login
    factory = Mock(return_value=client)
    monkeypatch.setattr(diagnostic, "Client", factory)
    monkeypatch.setenv("IG_USERNAME", "synthetic-user")
    monkeypatch.setenv("IG_PASSWORD", SECRET)
    monkeypatch.delenv("IG_PROXY", raising=False)
    settings, output, native = tmp_path / "settings.json", tmp_path / "report.json", tmp_path / SECRET
    settings.write_text('{"private_transport":"utls"}')
    assert (
        diagnostic.main(["--settings", str(settings), "--report", str(output), "--utls-library-path", str(native)]) == 1
    )
    assert requests == [30]
    assert factory.call_args.kwargs["utls_library_path"] == native
    assert "utls_library_path" not in json.loads(settings.read_text())
    assert json.loads(output.read_text())["environment"]["total_timeout_seconds"] == 30
    assert SECRET not in output.read_text()


@pytest.mark.parametrize("transport", ["requests", "curl"])
def test_cli_real_session_applies_reported_connect_and_read_timeout_budgets(
    diagnostic, clients, monkeypatch, tmp_path, transport
):
    client = clients(private_transport=transport)
    budgets = []

    async def send(request):
        budgets.append(request.extensions["timeout"])
        return response(request, 400, b'{"error_type":"bad_password","status":"fail"}')

    install_transport(client, send)
    monkeypatch.setattr(diagnostic, "Client", Mock(return_value=client))
    monkeypatch.setenv("IG_USERNAME", "synthetic-user")
    monkeypatch.setenv("IG_PASSWORD", SECRET)
    monkeypatch.delenv("IG_PROXY", raising=False)
    output = tmp_path / "report.json"
    assert diagnostic.main(["--settings", str(tmp_path / "settings.json"), "--report", str(output)]) == 1
    assert len(budgets) == 1
    assert budgets[0]["connect"] == 10
    assert budgets[0]["read"] == 30
    assert json.loads(output.read_text())["environment"]["connect_timeout_seconds"] == 10


@pytest.mark.parametrize("alias", ["direct", "symlink", "hardlink"])
def test_cli_rejects_settings_report_aliases_before_any_write(diagnostic, monkeypatch, tmp_path, alias):
    settings, output = tmp_path / "settings.json", tmp_path / "report.json"
    settings.write_text(SECRET)
    if alias == "direct":
        output = settings
    elif alias == "symlink":
        output.symlink_to(settings)
    else:
        output.hardlink_to(settings)
    factory = Mock()
    monkeypatch.setattr(diagnostic, "Client", factory)
    with pytest.raises(SystemExit) as caught:
        diagnostic.main(["--settings", str(settings), "--report", str(output)])
    assert caught.value.code == 2
    assert settings.read_text() == SECRET
    factory.assert_not_called()


def test_atomic_write_failure_preserves_original_and_removes_tempfile(diagnostic, monkeypatch, tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(SECRET)
    original = settings.read_bytes()
    monkeypatch.setattr(Path, "replace", Mock(side_effect=OSError(SECRET)))
    with pytest.raises(OSError):
        diagnostic.write_private_json(settings, {"changed": True})
    assert settings.read_bytes() == original
    assert list(tmp_path.iterdir()) == [settings]


def test_cli_invalid_destination_and_setup_failure_do_not_submit_credentials(diagnostic, monkeypatch, tmp_path, capsys):
    settings = tmp_path / "settings.json"
    settings.write_text('{"uuids":{"uuid":"keep-existing"}}')
    original = settings.read_bytes()
    factory = Mock(side_effect=ValueError(SECRET))
    monkeypatch.setattr(diagnostic, "Client", factory)
    assert diagnostic.main(["--settings", str(settings), "--report", str(tmp_path / "missing" / "report.json")]) == 1
    assert settings.read_bytes() == original
    factory.assert_not_called()
    monkeypatch.setenv("IG_USERNAME", "synthetic-user")
    monkeypatch.setenv("IG_PASSWORD", SECRET)
    monkeypatch.delenv("IG_PROXY", raising=False)
    output = tmp_path / "report.json"
    assert diagnostic.main(["--settings", str(settings), "--report", str(output)]) == 1
    assert json.loads(output.read_text())["outcome"] == "setup_error"
    assert SECRET not in output.read_text() + str(capsys.readouterr())


@async_test
async def test_partial_observer_setup_restores_all_previous_overrides(diagnostic, clients):
    client = clients(private_transport="requests")
    original_caa = client.bloks_caa_login
    original_private = client.private.request
    original_public = client.public

    class NoOverride:
        __slots__ = ()

        async def request(self, *args, **kwargs):
            raise AssertionError("Setup must fail before requests")

    client.public = NoOverride()
    login = client.login = AsyncMock()
    try:
        with pytest.raises((AttributeError, TypeError)):
            await diagnostic.diagnose(client, "synthetic-user", SECRET)
    finally:
        client.public = original_public
    login.assert_not_awaited()
    assert client.bloks_caa_login == original_caa
    assert client.private.request == original_private
    assert "request" not in vars(client.private)
    assert "handle_exception" not in vars(client)


@pytest.mark.parametrize("mode", ["success", "post-construction-setup-error", "close-error"])
def test_cli_closes_all_owned_sessions_on_success_and_setup_errors(diagnostic, clients, monkeypatch, tmp_path, mode):
    client = clients(private_transport="requests")
    client.login = AsyncMock(return_value=True)
    closed = []
    for name in ("private", "public", "graphql"):

        async def close(name=name):
            closed.append(name)
            if mode == "close-error" and name == "private":
                raise RuntimeError(SECRET)

        monkeypatch.setattr(getattr(client, name), "_close", close)
    monkeypatch.setattr(diagnostic, "Client", Mock(return_value=client))
    monkeypatch.setenv("IG_USERNAME", "synthetic-user")
    monkeypatch.setenv("IG_PASSWORD", SECRET)
    monkeypatch.delenv("IG_PROXY", raising=False)
    if mode == "post-construction-setup-error":
        monkeypatch.setattr(diagnostic, "bound_requests", Mock(side_effect=ValueError(SECRET)))
    output = tmp_path / "report.json"
    result = diagnostic.main(["--settings", str(tmp_path / "settings.json"), "--report", str(output)])
    assert result == (0 if mode == "success" else 1)
    assert closed == ["private", "public", "graphql"]
    report = json.loads(output.read_text())
    if mode == "post-construction-setup-error":
        client.login.assert_not_awaited()
        assert report["exception"]["type"] == "ValueError"
    if mode == "close-error":
        assert report["session_close_errors"] == [{"session": "private", "type": "RuntimeError"}]
    assert SECRET not in output.read_text()


@async_test
async def test_cli_task_cancellation_saves_settings_report_and_closes_sessions(
    diagnostic, clients, monkeypatch, tmp_path
):
    client = clients(private_transport="requests")
    entered = asyncio.Event()
    closed = []

    async def login(*args, **kwargs):
        entered.set()
        await asyncio.Event().wait()

    client.login = login
    for name in ("private", "public", "graphql"):

        async def close(name=name):
            closed.append(name)

        monkeypatch.setattr(getattr(client, name), "_close", close)
    monkeypatch.setattr(diagnostic, "Client", Mock(return_value=client))
    monkeypatch.setenv("IG_USERNAME", "synthetic-user")
    monkeypatch.setenv("IG_PASSWORD", SECRET)
    monkeypatch.delenv("IG_PROXY", raising=False)
    settings, output = tmp_path / "settings.json", tmp_path / "report.json"
    task = asyncio.create_task(diagnostic.async_main(["--settings", str(settings), "--report", str(output)]))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert closed == ["private", "public", "graphql"]
    report = json.loads(output.read_text())
    assert report["exception"]["type"] == "CancelledError"
    assert report["settings_saved"] is True
    assert SECRET not in output.read_text()
    assert "request" not in vars(client.private)


@async_test
async def test_cancellation_during_cli_close_drains_all_owned_sessions_before_propagating(
    diagnostic, clients, monkeypatch, tmp_path
):
    client = clients(private_transport="requests")
    client.login = AsyncMock(return_value=True)
    entered, release = asyncio.Event(), asyncio.Event()
    closed = []

    async def private_close():
        entered.set()
        await release.wait()
        closed.append("private")

    monkeypatch.setattr(client.private, "_close", private_close)
    for name in ("public", "graphql"):

        async def close(name=name):
            closed.append(name)

        monkeypatch.setattr(getattr(client, name), "_close", close)
    monkeypatch.setattr(diagnostic, "Client", Mock(return_value=client))
    monkeypatch.setenv("IG_USERNAME", "synthetic-user")
    monkeypatch.setenv("IG_PASSWORD", SECRET)
    monkeypatch.delenv("IG_PROXY", raising=False)
    output = tmp_path / "report.json"
    task = asyncio.create_task(
        diagnostic.async_main(["--settings", str(tmp_path / "settings.json"), "--report", str(output)])
    )
    await entered.wait()
    task.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert closed == ["private", "public", "graphql"]
    assert json.loads(output.read_text())["settings_saved"] is True


# protects: A false login result is reported without changing caller callbacks, hooks or session ownership.
# fails_when: False becomes success or an exception, login repeats, or observer state remains installed.
# why_new: The new standalone observer has success/error controls but no false-result control; this is not an SDK regression.
# seam: none
@async_test
async def test_false_login_result_preserves_outcome_and_restores_caller_state(diagnostic, clients):
    client = clients(private_transport="requests")
    login = client.login = AsyncMock(return_value=False)
    previous = {
        name: vars(client).get(name)
        for name in ("handle_exception", "challenge_code_handler", "change_password_handler", "bloks_caa_login")
    }
    request_overrides = {name: vars(getattr(client, name)).get("request") for name in ("private", "public")}
    hooks = {name: getattr(client, name)._client.event_hooks["response"] for name in ("private", "public")}
    logging_before = logging.root.manager.disable

    report = await diagnostic.diagnose(client, "synthetic-user", SECRET)

    assert report["outcome"] == "false_return"
    assert "exception" not in report
    assert report["responses"] == report["caa_attempts"] == []
    login.assert_awaited_once_with("synthetic-user", SECRET, relogin=False, verification_code="")
    for name, value in previous.items():
        assert vars(client).get(name) is value
    for name in ("private", "public"):
        session = getattr(client, name)
        assert vars(session).get("request") is request_overrides[name]
        assert session._client.event_hooks["response"] is hooks[name]
        assert hooks[name] == []
        assert not session._client.is_closed
    assert logging.root.manager.disable == logging_before
    assert SECRET not in json.dumps(report)


# protects: Invalid settings and empty credentials stop before constructing a client or submitting credentials.
# fails_when: Malformed/non-object settings or an empty username/password reach the client factory or leak error text.
# why_new: Existing new-example setup controls cover bad destinations and constructor errors, not invalid input values.
# seam: none
@pytest.mark.parametrize(
    "invalid_input", ["malformed-settings", "non-object-settings", "empty-username", "empty-password"]
)
def test_cli_invalid_settings_or_empty_credentials_stop_before_submission(
    diagnostic, monkeypatch, tmp_path, capsys, invalid_input
):
    settings, output = tmp_path / "settings.json", tmp_path / "report.json"
    settings.write_text(
        {"malformed-settings": "{" + SECRET, "non-object-settings": json.dumps([SECRET])}.get(invalid_input, "{}")
    )
    factory = Mock(side_effect=AssertionError("Invalid setup must not construct a client"))
    monkeypatch.setattr(diagnostic, "Client", factory)
    monkeypatch.setenv("IG_USERNAME", "synthetic-user")
    monkeypatch.setenv("IG_PASSWORD", SECRET)
    monkeypatch.delenv("IG_PROXY", raising=False)
    monkeypatch.setattr("builtins.input", Mock(return_value=""))
    monkeypatch.setattr(diagnostic.getpass, "getpass", Mock(return_value=""))
    if invalid_input == "empty-username":
        monkeypatch.delenv("IG_USERNAME")
    elif invalid_input == "empty-password":
        monkeypatch.delenv("IG_PASSWORD")

    assert diagnostic.main(["--settings", str(settings), "--report", str(output)]) == 1

    factory.assert_not_called()
    report = json.loads(output.read_text())
    assert report["outcome"] == "setup_error"
    assert report["exception"]["type"] == ("JSONDecodeError" if invalid_input == "malformed-settings" else "ValueError")
    assert report["responses"] == []
    streams = capsys.readouterr()
    assert SECRET not in output.read_text() + streams.out + streams.err


# protects: CLI proxy/TOTP prompts and relogin selection reach one awaited login while private values stay out of output.
# fails_when: Flags or environment proxy values are ignored, prompted without selection, repeated, or exported.
# why_new: Existing new-example CLI controls use credential env values and omit interactive proxy/TOTP/relogin forwarding.
# seam: none
@pytest.mark.parametrize("private_flags", [False, True])
def test_cli_privately_forwards_proxy_totp_and_relogin_options(
    diagnostic, clients, monkeypatch, tmp_path, capsys, private_flags
):
    client = clients(private_transport="requests")
    login = client.login = AsyncMock(return_value=True)
    factory = Mock(return_value=client)
    proxy = "http://synthetic-user:" + SECRET + "@fixture.invalid:3128"
    code = SECRET + "-synthetic-code"
    prompts = Mock(side_effect=lambda prompt: {"Proxy URL: ": proxy, "Current 2FA code: ": code}[prompt])
    monkeypatch.setattr(diagnostic, "Client", factory)
    monkeypatch.setattr(diagnostic.getpass, "getpass", prompts)
    monkeypatch.setenv("IG_USERNAME", "synthetic-user")
    monkeypatch.setenv("IG_PASSWORD", SECRET)
    monkeypatch.setenv("IG_PROXY", "http://environment:" + SECRET + "@fixture.invalid:8080")
    output = tmp_path / "report.json"
    args = ["--settings", str(tmp_path / "settings.json"), "--report", str(output)]
    if private_flags:
        args.extend(["--proxy", "--two-factor", "--relogin"])

    assert diagnostic.main(args) == 0

    assert factory.call_args.kwargs["proxy"] == (
        proxy if private_flags else "http://environment:" + SECRET + "@fixture.invalid:8080"
    )
    login.assert_awaited_once_with(
        "synthetic-user", SECRET, relogin=private_flags, verification_code=code if private_flags else ""
    )
    assert [call.args[0] for call in prompts.call_args_list] == (
        ["Proxy URL: ", "Current 2FA code: "] if private_flags else []
    )
    report = json.loads(output.read_text())
    assert report["environment"]["proxy_configured"] is True
    assert report["environment"]["two_factor_code_supplied"] is private_flags
    assert report["environment"]["relogin"] is private_flags
    streams = capsys.readouterr()
    assert SECRET not in output.read_text() + streams.out + streams.err


# protects: Final settings read/write failures report a fixed error, return failure and still close every owned session.
# fails_when: A persistence error returns success, leaks its message, prevents cleanup/report, or replaces prior settings.
# why_new: Existing new-example storage controls exercise atomic writes alone, not failure during CLI final persistence.
# seam: none
@pytest.mark.parametrize("save_failure", ["get-settings", "replace-settings"])
def test_cli_final_settings_failure_is_sanitized_and_preserves_cleanup(
    diagnostic, clients, monkeypatch, tmp_path, capsys, save_failure
):
    client = clients(private_transport="requests")
    login = client.login = AsyncMock(return_value=True)
    settings, output = tmp_path / "settings.json", tmp_path / "report.json"
    initial_settings = {"uuids": {"uuid": "synthetic-saved-device"}}
    settings.write_text(json.dumps(initial_settings))
    saved_before_failure = []
    original_replace = Path.replace

    def replace(source, target):
        if Path(target) == settings and login.await_count:
            saved_before_failure.append(settings.read_bytes())
            raise OSError(SECRET)
        return original_replace(source, target)

    if save_failure == "get-settings":
        monkeypatch.setattr(client, "get_settings", Mock(side_effect=ValueError(SECRET)))
    else:
        monkeypatch.setattr(Path, "replace", replace)
    closed = []
    for name in ("private", "public", "graphql"):

        async def close(name=name):
            print(SECRET)
            closed.append(name)

        monkeypatch.setattr(getattr(client, name), "_close", close)
    monkeypatch.setattr(diagnostic, "Client", Mock(return_value=client))
    monkeypatch.setenv("IG_USERNAME", "synthetic-user")
    monkeypatch.setenv("IG_PASSWORD", SECRET)
    monkeypatch.delenv("IG_PROXY", raising=False)

    assert diagnostic.main(["--settings", str(settings), "--report", str(output)]) == 1

    login.assert_awaited_once()
    assert closed == ["private", "public", "graphql"]
    report = json.loads(output.read_text())
    assert report["outcome"] == "success"
    assert report["settings_saved"] is False
    assert report["settings_save_error"] == ("ValueError" if save_failure == "get-settings" else "OSError")
    assert json.loads(settings.read_text()) == initial_settings
    if saved_before_failure:
        assert settings.read_bytes() == saved_before_failure[0]
    assert sorted(path.name for path in tmp_path.iterdir()) == ["report.json", "settings.json"]
    streams = capsys.readouterr()
    assert SECRET not in output.read_text() + streams.out + streams.err


# protects: A failed final report replacement exits safely after cleanup and preserves the preceding report bytes.
# fails_when: Final write failure returns success, exports private exception text, skips closes or loses the prior report.
# why_new: Existing new-example destination controls stop before login and do not cover the final report write boundary.
# seam: none
def test_cli_final_report_failure_preserves_prior_report_and_safe_exit(
    diagnostic, clients, monkeypatch, tmp_path, capsys
):
    client = clients(private_transport="requests")
    login = client.login = AsyncMock(return_value=True)
    settings, output = tmp_path / "settings.json", tmp_path / "report.json"
    output.write_text('{"existing":"report"}')
    preceding_report = []
    original_replace = Path.replace

    def replace(source, target):
        if Path(target) == output and login.await_count:
            preceding_report.append(output.read_bytes())
            raise OSError(SECRET)
        return original_replace(source, target)

    monkeypatch.setattr(Path, "replace", replace)
    closed = []
    for name in ("private", "public", "graphql"):

        async def close(name=name):
            closed.append(name)

        monkeypatch.setattr(getattr(client, name), "_close", close)
    monkeypatch.setattr(diagnostic, "Client", Mock(return_value=client))
    monkeypatch.setenv("IG_USERNAME", "synthetic-user")
    monkeypatch.setenv("IG_PASSWORD", SECRET)
    monkeypatch.delenv("IG_PROXY", raising=False)

    assert diagnostic.main(["--settings", str(settings), "--report", str(output)]) == 1

    login.assert_awaited_once()
    assert closed == ["private", "public", "graphql"]
    assert len(preceding_report) == 1
    assert output.read_bytes() == preceding_report[0]
    assert json.loads(output.read_text())["outcome"] == "setup_error"
    assert settings.exists()
    assert sorted(path.name for path in tmp_path.iterdir()) == ["report.json", "settings.json"]
    streams = capsys.readouterr()
    assert "Could not write the report (OSError)." in streams.out
    assert SECRET not in output.read_text() + streams.out + streams.err


def test_response_summary_never_copies_untrusted_strings(diagnostic):
    req = httpx.Request("POST", f"https://i.instagram.com/api/v1/challenge/{SECRET}/?token={SECRET}")
    payload = {
        "message": SECRET,
        "status": SECRET,
        "error_type": SECRET,
        "step_name": SECRET,
        "bloks_action": SECRET,
        "challenge": {"native_flow": SECRET, "api_path": f"/challenge/{SECRET}/", "challenge_context": SECRET},
        "authorization_data": {"sessionid": SECRET},
    }
    raw = response(req, 400, json.dumps(payload).encode(), SECRET)
    raw.headers["Set-Cookie"] = f"sessionid={SECRET}"
    raw.headers["Location"] = f"https://instagram.com/{SECRET}"
    summary = diagnostic.summarize_response(raw)

    assert SECRET not in json.dumps(summary)
    assert summary["endpoint"] == "challenge"
    assert summary["json"]["challenge_api_path"] == "/challenge/<redacted>"
    assert summary["json"]["error_type"] == "other"
    assert summary["content_type"] == "other"
    assert "Set-Cookie" not in summary


@pytest.mark.parametrize(
    "message",
    [
        "Your version of Instagram is out of date.",
        "Your version of Instagram is out of date. Please upgrade your app to log in to Instagram.",
    ],
)
def test_outdated_app_response_keeps_signal_without_copying_message(diagnostic, message):
    request = httpx.Request("POST", LOGIN)
    raw = response(
        request,
        400,
        json.dumps({"message": message + SECRET, "error_type": "needs_upgrade", "status": "fail"}).encode(),
    )

    summary = diagnostic.summarize_response(raw)

    assert summary["endpoint"] == "accounts/login"
    assert summary["json"]["error_type"] == "needs_upgrade"
    assert summary["json"]["message_category"] == "app_out_of_date"
    assert SECRET not in json.dumps(summary)


def test_native_challenge_fields_remain_useful(diagnostic):
    summary = diagnostic.summarize_json(
        {
            "message": "challenge_required",
            "status": "fail",
            "challenge": {"native_flow": True, "api_path": f"/api/v1/challenge/{SECRET}/"},
        }
    )
    assert summary["message_category"] == "challenge_required"
    assert summary["challenge_native_flow"] is True
    assert summary["challenge_api_path"] == "/api/v1/challenge/<redacted>"
    assert SECRET not in json.dumps(summary)


@pytest.mark.parametrize(
    "reason",
    [
        "CAA preflight did not return account access and attestation data",
        "missing entrypoint context_data",
        "missing code_entry context_data",
        "missing code_entry_async context_data",
    ],
)
def test_caa_reason_categories_are_preserved(diagnostic, reason):
    result = diagnostic.summarize_caa_outcome(Client(), {"logged_in": False, "reason": reason, "result": {}})
    assert result["reason"] == reason


def test_caa_summary_withholds_contexts_unknown_reasons_and_marker_suffixes(diagnostic):
    client = Client()
    body = {
        "logged_in": False,
        "two_step_verification_context": SECRET,
        "reason": SECRET,
        "result": {"markers": ["CAA_LOGIN_FALLBACK:" + SECRET], "token": SECRET},
    }
    before = json.dumps(body, sort_keys=True)
    summary = diagnostic.summarize_caa_outcome(client, body)
    assert summary["two_factor_context_present"] is True
    assert summary["reason"] == "other"
    assert summary["fallback_marker_present"] is True
    assert SECRET not in json.dumps(summary)
    assert json.dumps(body, sort_keys=True) == before


@pytest.mark.parametrize("has_context", [False, True])
def test_caa_summary_distinguishes_profile_reference_from_parsed_context(diagnostic, has_context):
    app = "com.bloks.www.ap.two_step_verification.entrypoint_async"
    action = json.dumps(app)
    if has_context:
        action += f' (f4i (dkc "context_data") (dkc "{SECRET}"))'
    body = {"logged_in": False, "result": {"layout": {"bloks_payload": {"action": action}}}}
    summary = diagnostic.summarize_caa_outcome(Client(), body)
    assert summary["profile_code_reference_present"] is True
    assert summary["profile_code_context_parsed"] is has_context
    assert SECRET not in json.dumps(summary)


STAGE_APPS = [
    ("com.bloks.www.bloks.caa.login.process_client_data_and_redirect", "caa/process_client_data_and_redirect"),
    ("com.bloks.www.caa.login.oauth.token.fetch.async", "caa/oauth_token_fetch"),
    ("com.bloks.www.bloks.caa.login.async.send_login_request", "caa/send_login_request"),
    ("com.bloks.www.two_step_verification.entrypoint", "two_step/entrypoint"),
    ("com.bloks.www.two_step_verification.method_picker", "two_step/method_picker"),
    ("com.bloks.www.two_step_verification.method_picker.navigation.async", "two_step/select_method"),
    ("com.bloks.www.two_factor_login.enter_totp_code", "two_step/enter_totp_code"),
    ("com.bloks.www.two_factor_login.enter_backup_code", "two_step/enter_backup_code"),
    ("com.bloks.www.two_step_verification.verify_code.async", "two_step/verify_code"),
    ("com.bloks.www.two_step_verification.has_been_allowed.async", "two_step/has_been_allowed"),
    ("com.bloks.www.caa.notif_status.async", "caa/notif_status"),
    ("com.bloks.www.ap.two_step_verification.entrypoint_async", "profile_code/entrypoint"),
    ("com.bloks.www.ap.two_step_verification.code_entry", "profile_code/code_entry"),
    ("com.bloks.www.ap.two_step_verification.code_entry_async", "profile_code/code_entry_async"),
]


@pytest.mark.parametrize(("app", "label"), STAGE_APPS, ids=[label for _, label in STAGE_APPS])
def test_exact_new_endpoint_stages(diagnostic, app, label):
    assert diagnostic.endpoint_label(f"/api/v1/bloks/async_action/{app}/") == label
    assert diagnostic.endpoint_label(f"/api/v1/bloks/apps/{app}/") == label
    for unknown in (app + SECRET, app + ".unknown", SECRET + app):
        assert diagnostic.endpoint_label(f"/api/v1/bloks/async_action/{unknown}/") == "bloks"


def test_attestation_and_legacy_endpoint_categories(diagnostic):
    assert diagnostic.endpoint_label("/api/v1/attestation/create_android_keystore/") == (
        "attestation/create_android_keystore"
    )
    assert diagnostic.endpoint_label("/api/v1/attestation/" + SECRET) == "attestation"
    for suffix, category in (
        ("process_client_data/", "caa/process_client_data"),
        ("oauth_token.fetch/", "caa/oauth_token_fetch"),
        ("send_login_request/", "caa/send_login_request"),
        ("accounts/current_user/", "accounts/current_user"),
    ):
        assert diagnostic.endpoint_label("/api/v1/" + suffix) == category


@pytest.mark.parametrize("friendly_name_kind", ["exact", "missing", "unknown", "suffix", "prefix"])
def test_usdid_registration_uses_only_exact_friendly_name(diagnostic, friendly_name_kind):
    friendly_name = {
        "exact": "IGUSDIDRegistrationMutation",
        "missing": None,
        "unknown": SECRET,
        "suffix": "IGUSDIDRegistrationMutation" + SECRET,
        "prefix": SECRET + "IGUSDIDRegistrationMutation",
    }[friendly_name_kind]
    headers = {"x-fb-friendly-name": friendly_name} if friendly_name is not None else {}
    request = httpx.Request("POST", "https://b.i.instagram.com/graphql_www", headers=headers, content=SECRET)
    raw = response(request, 200, b"{}")
    summary = diagnostic.summarize_response(raw)
    assert summary["endpoint"] == ("usdid/registration" if friendly_name_kind == "exact" else "other")
    assert SECRET not in json.dumps(summary)


@pytest.mark.parametrize(
    ("server", "proxy_status", "server_category", "proxy_category"),
    [
        ("proxygen-bolt", "http_request_error", "proxygen-bolt", "http_request_error"),
        ("proxygen-bolt", 'proxy; error=http_request_error; details="private"', "proxygen-bolt", "http_request_error"),
        ("proxygen-bolt", 'proxy; error="http_request_error"', "proxygen-bolt", "http_request_error"),
        (None, None, None, None),
        (SECRET, SECRET, "other", "other"),
        ("proxygen-bolt" + SECRET, "http_request_error" + SECRET, "other", "other"),
        (SECRET, 'proxy; details="error=http_request_error"', "other", "other"),
        (SECRET, 'proxy; details="private; error=http_request_error;"', "other", "other"),
        (SECRET, "proxy; error=http_request_error" + SECRET, "other", "other"),
    ],
    ids=[
        "bare",
        "parameter",
        "quoted",
        "absent",
        "unknown",
        "hostile-suffix",
        "details",
        "quoted-details",
        "hostile-error",
    ],
)
def test_response_metadata_is_allowlisted(diagnostic, server, proxy_status, server_category, proxy_category):
    request = httpx.Request("POST", CAA)
    raw = response(request, 429, b"", "text/plain")
    if server is not None:
        raw.headers["Server"] = server
    if proxy_status is not None:
        raw.headers["Proxy-Status"] = proxy_status
    raw.headers["Retry-After"] = SECRET
    summary = diagnostic.summarize_response(raw)
    assert summary["server_category"] == server_category
    assert summary["proxy_error_category"] == proxy_category
    assert summary["retry_after_present"] is True
    assert SECRET not in json.dumps(summary)
    del raw.headers["Retry-After"]
    assert diagnostic.summarize_response(raw)["retry_after_present"] is False


def embedded_bloks(*, session=False, authorization=False, user=False):
    embedded = {
        "login_response": json.dumps({"logged_in_user": {"pk": "123", "username": SECRET}} if user else {}),
        "headers": json.dumps({"IG-Set-Authorization": SECRET} if authorization else {}),
        "cookies": f"Set-Cookie: sessionid={SECRET}; Path=/" if session else "Set-Cookie: sessionid=; Path=/",
        "private": SECRET,
    }
    return {"status": "ok", "layout": {"bloks_payload": {"action": f"(bk.action {json.dumps(json.dumps(embedded))})"}}}


@pytest.mark.parametrize("kind", ["empty", "fallback", "reference", "malformed", "decoded-empty", "session"])
def test_bloks_summary_distinguishes_references_and_current_session_material(diagnostic, kind):
    body = {
        "empty": {},
        "fallback": {"markers": ["CAA_LOGIN_FALLBACK:" + SECRET]},
        "reference": {"layout": {"bloks_payload": {"action": "login_response " + SECRET}}},
        "malformed": {"layout": {"bloks_payload": {"action": '"{invalid login_response ' + SECRET}}},
        "decoded-empty": embedded_bloks(),
        "session": embedded_bloks(session=True, authorization=True, user=True),
    }[kind]
    before = json.dumps(body, sort_keys=True)
    request = httpx.Request("POST", CAA)
    raw = response(request, 200, json.dumps(body).encode())
    summary = diagnostic.summarize_response(raw)
    bloks = summary["bloks"]
    assert bloks["login_response_reference_present"] is (kind in {"reference", "malformed", "decoded-empty", "session"})
    assert bloks["login_response_decoded"] is (kind in {"decoded-empty", "session"})
    assert bloks["logged_in_user_present"] is (kind == "session")
    assert bloks["authorization_present"] is (kind == "session")
    assert bloks["sessionid_cookie_present"] is (kind == "session")
    assert bloks["fallback_reference_present"] is (kind == "fallback")
    assert bloks["inspection_error"] is False
    assert SECRET not in json.dumps(summary)
    assert json.dumps(body, sort_keys=True) == before


def test_bloks_referenced_apps_are_exact_and_closed(diagnostic):
    app = "com.bloks.www.two_step_verification.entrypoint"
    payload = {
        "layout": {"bloks_payload": {"action": f"{json.dumps(app)} {json.dumps(app + SECRET)}"}},
        "private": SECRET,
    }
    request = httpx.Request("POST", CAA)
    summary = diagnostic.summarize_response(response(request, 200, json.dumps(payload).encode()))
    assert summary["bloks"]["referenced_apps"] == [app]
    assert SECRET not in json.dumps(summary)
    payload["layout"]["bloks_payload"]["action"] = json.dumps(app + SECRET)
    summary = diagnostic.summarize_response(response(request, 200, json.dumps(payload).encode()))
    assert summary["bloks"]["referenced_apps"] == []


@pytest.mark.parametrize("kind", ["success", "redirect", "continuation", "error", "ocl-error", "hostile"])
def test_bloks_marker_references_are_narrow_and_not_outcomes(diagnostic, kind):
    app = "com.bloks.www.two_step_verification.method_picker"
    body = {
        "success": {"layout": {"bloks_payload": {"action": json.dumps("login_success") + SECRET}}},
        "redirect": {"layout": {"bloks_payload": {"action": json.dumps("two_fac_redirect") + SECRET}}},
        "continuation": {"layout": {"bloks_payload": {"action": json.dumps(app) + SECRET}}},
        "error": {"error_type": "bad_password", "message": SECRET},
        "ocl-error": {"markers": ["CAA_LOGIN_OCL_ERROR:" + SECRET]},
        "hostile": {"layout": {"bloks_payload": {"action": json.dumps("login_success" + SECRET)}}},
    }[kind]
    raw = response(httpx.Request("POST", CAA), 200, json.dumps(body).encode())
    bloks = diagnostic.summarize_response(raw)["bloks"]
    assert bloks["login_success_reference_present"] is (kind in {"success", "redirect"})
    assert bloks["continuation_reference_present"] is (kind == "continuation")
    assert bloks["error_reference_present"] is (kind in {"error", "ocl-error"})
    assert bloks["login_response_decoded"] is False
    assert bloks["sessionid_cookie_present"] is False
    assert SECRET not in json.dumps(bloks)


@pytest.mark.parametrize(
    "label",
    ["Incorrect password", "Incorrect Password", "Can't find account", "CAN'T FIND ACCOUNT", "Can\u2019t find account"],
)
@pytest.mark.parametrize("location", ["value", "action", "escaped-action"])
def test_bloks_error_dialog_references_are_private_and_not_login_outcomes(diagnostic, label, location):
    payload = {"data": [label, SECRET]}
    if location != "value":
        literal = json.dumps(label, ensure_ascii=location == "escaped-action")
        payload = {"action": f"(dialog {literal} {json.dumps(SECRET)})"}
    body = {"status": "ok", "layout": {"bloks_payload": payload}}
    before = json.dumps(body, sort_keys=True)
    raw = response(httpx.Request("POST", CAA), 200, json.dumps(body).encode())

    summary = diagnostic.summarize_response(raw)

    assert summary["bloks"]["error_reference_present"] is True
    assert summary["json"]["status"] == "ok"
    assert summary["json"]["error_type"] is None
    assert summary["json"]["message_category"] is None
    assert summary["bloks"]["login_response_decoded"] is False
    assert summary["bloks"]["sessionid_cookie_present"] is False
    assert summary["bloks"]["inspection_error"] is False
    assert SECRET not in json.dumps(summary)
    assert label not in json.dumps(summary, ensure_ascii=False)
    assert json.dumps(body, sort_keys=True) == before


@pytest.mark.parametrize(
    "label",
    ["Incorrect password" + SECRET, "Can't find account" + SECRET, "Reset password", "Account settings"],
)
def test_bloks_error_dialog_labels_require_an_exact_literal(diagnostic, label):
    body = {"layout": {"bloks_payload": {"action": f"(dialog {json.dumps(label)})", "data": [label]}}}
    raw = response(httpx.Request("POST", CAA), 200, json.dumps(body).encode())

    summary = diagnostic.summarize_response(raw)

    assert summary["bloks"]["error_reference_present"] is False
    assert SECRET not in json.dumps(summary)


@pytest.mark.parametrize(
    "label",
    ["Incorrect password", "Incorrect Password", "Can't find account", "CAN'T FIND ACCOUNT", "Can\u2019t find account"],
)
def test_bloks_error_dialog_reference_does_not_override_session_material(diagnostic, label):
    body = embedded_bloks(session=True, authorization=True, user=True)
    body["dialog_label"] = label
    raw = response(httpx.Request("POST", CAA), 200, json.dumps(body).encode())

    summary = diagnostic.summarize_response(raw)

    assert summary["bloks"]["error_reference_present"] is True
    assert summary["bloks"]["login_response_decoded"] is True
    assert summary["bloks"]["logged_in_user_present"] is True
    assert summary["bloks"]["authorization_present"] is True
    assert summary["bloks"]["sessionid_cookie_present"] is True
    assert SECRET not in json.dumps(summary)


def test_bloks_extraction_failure_uses_fixed_schema_without_session_changes(diagnostic, monkeypatch):
    body = embedded_bloks(session=True, authorization=True, user=True)
    raw = response(httpx.Request("POST", CAA), 200, json.dumps(body).encode())
    before = raw.content
    monkeypatch.setattr(diagnostic.BLOKS_PARSER, "bloks_extract_login_response", Mock(side_effect=ValueError(SECRET)))
    bloks = diagnostic.summarize_response(raw)["bloks"]
    assert set(bloks) == {
        "referenced_apps",
        "fallback_reference_present",
        "login_success_reference_present",
        "continuation_reference_present",
        "error_reference_present",
        "login_response_reference_present",
        "two_step_context_parsed",
        "profile_code_context_parsed",
        "login_response_decoded",
        "logged_in_user_present",
        "authorization_present",
        "sessionid_cookie_present",
        "inspection_error",
    }
    assert bloks["inspection_error"] is True
    assert bloks["login_response_decoded"] is False
    assert raw.content == before
    assert SECRET not in json.dumps(bloks)


@pytest.mark.parametrize(
    "kind", ["two-step-json", "two-step-action", "profile-action", "reference-only", "hostile-app"]
)
def test_current_response_context_booleans_withhold_values(diagnostic, kind):
    app = "com.bloks.www.two_step_verification.entrypoint"
    profile = "com.bloks.www.ap.two_step_verification.code_entry"
    body = {
        "two-step-json": {"two_step_verification_context": SECRET},
        "two-step-action": {
            "layout": {
                "bloks_payload": {
                    "action": (f'{json.dumps(app)} (f4i (dkc "two_step_verification_context") (dkc "{SECRET}"))')
                }
            }
        },
        "profile-action": {
            "layout": {
                "bloks_payload": {"action": (f'{json.dumps(profile)} (f4i (dkc "context_data") (dkc "{SECRET}"))')}
            }
        },
        "reference-only": {"layout": {"bloks_payload": {"action": json.dumps(profile)}}},
        "hostile-app": {
            "layout": {
                "bloks_payload": {
                    "action": (f'{json.dumps(profile + SECRET)} (f4i (dkc "context_data") (dkc "{SECRET}"))')
                }
            }
        },
    }[kind]
    before = json.dumps(body, sort_keys=True)
    raw = response(httpx.Request("POST", CAA), 200, json.dumps(body).encode())
    bloks = diagnostic.summarize_response(raw)["bloks"]
    assert bloks["two_step_context_parsed"] is (kind in {"two-step-json", "two-step-action"})
    assert bloks["profile_code_context_parsed"] is (kind == "profile-action")
    assert bloks["inspection_error"] is False
    assert json.dumps(body, sort_keys=True) == before
    assert SECRET not in json.dumps(bloks)


@pytest.mark.parametrize("error_type", [None, [], {}], ids=["null", "list", "dict"])
def test_non_string_error_metadata_does_not_hide_decoded_payload(diagnostic, error_type):
    body = embedded_bloks(session=True)
    body["error_type"] = error_type
    raw = response(httpx.Request("POST", CAA), 200, json.dumps(body).encode())
    summary = diagnostic.summarize_response(raw)
    assert summary["bloks"]["sessionid_cookie_present"] is True
    assert summary["bloks"]["inspection_error"] is False
    assert SECRET not in json.dumps(summary)

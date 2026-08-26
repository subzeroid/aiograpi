import asyncio
import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "research_login_matrix.py"
SPEC = importlib.util.spec_from_file_location("research_login_matrix", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
login_matrix = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = login_matrix
SPEC.loader.exec_module(login_matrix)


def test_build_accounts_url_preserves_query_and_sets_count():
    assert login_matrix.build_accounts_url("https://pool.test/accounts?kind=live", 3) == (
        "https://pool.test/accounts?kind=live&count=3"
    )
    assert login_matrix.build_accounts_url("https://pool.test/accounts?count=99", 2) == (
        "https://pool.test/accounts?count=2"
    )


def test_device_only_settings_drops_authentication_state():
    assert login_matrix.device_only_settings(
        {
            "uuids": {"phone_id": "phone"},
            "device_settings": {"model": "Pixel"},
            "sessionid": "secret",
            "authorization_data": {"sessionid": "secret"},
            "totp_seed": "secret",
        }
    ) == {
        "uuids": {"phone_id": "phone"},
        "device_settings": {"model": "Pixel"},
    }


def test_build_jobs_uses_separate_accounts_and_alternates_order():
    accounts = [{"username": f"u{index}", "password": "p"} for index in range(4)]

    jobs = login_matrix.build_jobs(accounts, ("stable", "fresh"), "separate", 2)

    assert [(job.trial, job.account_index, job.mode) for job in jobs] == [
        (0, 0, "stable"),
        (0, 1, "fresh"),
        (1, 2, "fresh"),
        (1, 3, "stable"),
    ]


def test_build_jobs_crossover_reuses_one_account_per_trial():
    accounts = [{"username": f"u{index}", "password": "p"} for index in range(2)]

    jobs = login_matrix.build_jobs(accounts, ("stable", "fresh"), "crossover", 2)

    assert [(job.trial, job.account_index, job.mode) for job in jobs] == [
        (0, 0, "stable"),
        (0, 0, "fresh"),
        (1, 1, "fresh"),
        (1, 1, "stable"),
    ]


def test_build_jobs_rejects_incomplete_account_pool_without_echoing_records():
    with pytest.raises(ValueError, match="need 2 accounts; endpoint returned 1") as exc_info:
        login_matrix.build_jobs(
            [{"username": "private-name", "password": "secret"}], ("stable", "fresh"), "separate", 1
        )

    assert "private-name" not in str(exc_info.value)
    assert "secret" not in str(exc_info.value)


def test_profile_digest_is_stable_only_within_one_run():
    first = login_matrix.digest_profile_value(b"run-key", "device-id")

    assert first == login_matrix.digest_profile_value(b"run-key", "device-id")
    assert first != login_matrix.digest_profile_value(b"other-key", "device-id")
    assert "device-id" not in first
    assert len(first) == 16


@pytest.mark.parametrize(
    "argv",
    [
        ["--count", "0"],
        ["--count", "-1"],
        ["--login-timeout", "0"],
        ["--cooldown", "9.99"],
        ["--mode", "both", "--count", "6"],
        ["--mode", "stable", "--count", "11"],
    ],
)
def test_parse_args_rejects_unsafe_bounds(argv):
    with pytest.raises(SystemExit):
        login_matrix.parse_args(argv)


def test_parse_args_accepts_at_most_ten_attempts():
    both = login_matrix.parse_args(["--mode", "both", "--count", "5"])
    single = login_matrix.parse_args(["--mode", "stable", "--count", "10"])

    assert both.attempts == 10
    assert single.attempts == 10
    assert both.cooldown == 30.0


def test_require_opt_in_needs_gate_and_account_pool_url():
    with pytest.raises(RuntimeError, match="IG_RUN_LOGIN_MATRIX=1"):
        login_matrix.require_opt_in({"TEST_ACCOUNTS_URL": "https://pool.test/accounts"})
    with pytest.raises(RuntimeError, match="TEST_ACCOUNTS_URL"):
        login_matrix.require_opt_in({"IG_RUN_LOGIN_MATRIX": "1"})

    assert (
        login_matrix.require_opt_in(
            {
                "IG_RUN_LOGIN_MATRIX": "1",
                "TEST_ACCOUNTS_URL": "https://pool.test/accounts",
            }
        )
        == "https://pool.test/accounts"
    )


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return json.dumps(self.payload).encode()


class FakeOpener:
    def __init__(self, payload):
        self.payload = payload
        self.request = None
        self.kwargs = None

    def __call__(self, request, **kwargs):
        self.request = request
        self.kwargs = kwargs
        return FakeResponse(self.payload)


def test_fetch_accounts_uses_verified_tls_and_validates_records():
    opener = FakeOpener(
        {
            "accounts": [
                {"username": "first", "password": "secret"},
                {"username": "second", "password": "secret"},
            ]
        }
    )

    accounts = login_matrix.fetch_accounts("https://pool.test/accounts?kind=live", 2, opener=opener)

    assert len(accounts) == 2
    assert opener.request.full_url == "https://pool.test/accounts?kind=live&count=2"
    assert opener.request.headers["User-agent"] == "aiograpi-login-matrix"
    assert opener.kwargs == {"timeout": 30}


@pytest.mark.parametrize(
    "payload",
    [
        {"unexpected": []},
        {"accounts": "not-a-list"},
        {"accounts": [{}]},
        {"accounts": [{"username": "only"}]},
    ],
)
def test_fetch_accounts_rejects_invalid_shapes_without_echoing_payload(payload):
    with pytest.raises(ValueError, match="account pool") as exc_info:
        login_matrix.fetch_accounts("https://pool.test/accounts", 1, opener=FakeOpener(payload))

    assert "only" not in str(exc_info.value)
    assert "not-a-list" not in str(exc_info.value)


class FakeSession:
    def __init__(self):
        self.entered = 0
        self.exited = 0

    async def __aenter__(self):
        self.entered += 1
        return self

    async def __aexit__(self, *_args):
        self.exited += 1


class FakeClient:
    instances = []
    behavior = "success"

    def __init__(self, settings=None, proxy=None):
        self.settings_argument = settings
        self.proxy_argument = proxy
        self.uuid = "uuid-before"
        self.android_device_id = "android-before"
        self.user_agent = "agent-before"
        self.public = FakeSession()
        self.private = FakeSession()
        self.graphql = FakeSession()
        self.login_call = None
        self.totp_seed = None
        type(self).instances.append(self)

    def totp_generate_code(self, seed):
        self.totp_seed = seed
        return "123456"

    async def login(self, username, password, **kwargs):
        self.login_call = (username, password, kwargs)
        if self.behavior == "failure":
            raise RuntimeError("private failure details")
        if self.behavior == "timeout":
            await asyncio.sleep(60)
        self.uuid = "uuid-after"
        return True


def run_attempt(account, *, mode="stable", behavior="success", timeout=1.0):
    FakeClient.instances.clear()
    FakeClient.behavior = behavior
    return asyncio.run(
        login_matrix.attempt(
            login_matrix.Job(trial=2, account_index=0, mode=mode),
            account,
            run_id="public-run-id",
            digest_key=b"private-run-key",
            pairing="separate",
            login_timeout=timeout,
            client_factory=FakeClient,
        )
    )


def test_attempt_reuses_only_device_settings_and_sanitizes_success_record():
    account = {
        "username": "private-user",
        "password": "private-password",
        "proxy": "http://private-proxy.test",
        "client_settings": {
            "uuids": {"phone_id": "private-phone"},
            "sessionid": "private-session",
            "totp_seed": "private-totp",
        },
    }

    result = run_attempt(account)

    client = FakeClient.instances[0]
    assert client.settings_argument == {"uuids": {"phone_id": "private-phone"}}
    assert client.proxy_argument == "http://private-proxy.test"
    assert client.totp_seed == "private-totp"
    assert client.login_call == ("private-user", "private-password", {"verification_code": "123456"})
    assert result["status"] == "ok"
    assert result["run_id"] == "public-run-id"
    assert result["trial"] == 2
    assert result["mode"] == "stable"
    assert result["pairing"] == "separate"
    assert result["proxy_used"] is True
    assert result["profile_before"] != result["profile_after"]
    serialized = json.dumps(result)
    for private_value in (
        "private-user",
        "private-password",
        "private-proxy",
        "private-phone",
        "private-session",
        "private-totp",
        "123456",
    ):
        assert private_value not in serialized


def test_attempt_records_only_exception_type_and_closes_all_sessions():
    result = run_attempt(
        {"username": "private-user", "password": "private-password"},
        behavior="failure",
    )

    client = FakeClient.instances[0]
    assert result["status"] == "error"
    assert result["error_type"] == "RuntimeError"
    assert "private failure details" not in json.dumps(result)
    assert all(
        session.entered == 1 and session.exited == 1 for session in (client.public, client.private, client.graphql)
    )


def test_attempt_bounds_login_time_and_closes_all_sessions():
    result = run_attempt(
        {"username": "private-user", "password": "private-password"},
        behavior="timeout",
        timeout=0.001,
    )

    client = FakeClient.instances[0]
    assert result["status"] == "error"
    assert result["error_type"] == "TimeoutError"
    assert all(session.exited == 1 for session in (client.public, client.private, client.graphql))

import asyncio
import importlib.util
import json
import stat
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


@pytest.mark.parametrize("url", ["http://pool.test/accounts", "pool.test/accounts", "https:///accounts"])
def test_build_accounts_url_requires_https(url):
    with pytest.raises(ValueError, match="HTTPS"):
        login_matrix.build_accounts_url(url, 1)


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
        ["--login-timeout", "nan"],
        ["--login-timeout", "inf"],
        ["--cooldown", "9.99"],
        ["--cooldown", "nan"],
        ["--cooldown", "inf"],
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

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeGetter:
    def __init__(self, payload):
        self.payload = payload
        self.request = None
        self.kwargs = None

    def __call__(self, url, **kwargs):
        self.request = url
        self.kwargs = kwargs
        return FakeResponse(self.payload)


def test_fetch_accounts_uses_verified_tls_and_validates_records():
    getter = FakeGetter(
        {
            "accounts": [
                {"username": "first", "password": "secret"},
                {"username": "second", "password": "secret"},
            ]
        }
    )

    accounts = login_matrix.fetch_accounts("https://pool.test/accounts?kind=live", 2, getter=getter)

    assert len(accounts) == 2
    assert getter.request == "https://pool.test/accounts?kind=live&count=2"
    assert getter.kwargs == {
        "headers": {"User-Agent": "aiograpi-login-matrix"},
        "timeout": 30,
        "follow_redirects": False,
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"unexpected": []},
        {"accounts": "not-a-list"},
        {"accounts": [{}]},
        {"accounts": [{"username": "only"}]},
        {"accounts": [{"username": 123, "password": "secret"}]},
        {"accounts": [{"username": "user", "password": "secret", "client_settings": "invalid"}]},
        {"accounts": [{"username": "user", "password": "secret", "proxy": {"url": "private"}}]},
    ],
)
def test_fetch_accounts_rejects_invalid_shapes_without_echoing_payload(payload):
    with pytest.raises(ValueError, match="account pool") as exc_info:
        login_matrix.fetch_accounts("https://pool.test/accounts", 1, getter=FakeGetter(payload))

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
        if self.behavior == "totp_failure":
            raise ValueError("private TOTP failure details")
        return "123456"

    async def login(self, username, password, **kwargs):
        self.login_call = (username, password, kwargs)
        if self.behavior == "failure":
            raise RuntimeError("private failure details")
        if self.behavior == "timeout":
            await asyncio.sleep(60)
        if self.behavior == "false":
            return False
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


def test_attempt_does_not_record_false_login_result_as_success():
    result = run_attempt(
        {"username": "private-user", "password": "private-password"},
        behavior="false",
    )

    assert result["status"] == "error"
    assert result["error_type"] == "LoginReturnedFalse"


def test_attempt_sanitizes_totp_failure_and_closes_all_sessions():
    result = run_attempt(
        {
            "username": "private-user",
            "password": "private-password",
            "totp_seed": "private-totp",
        },
        behavior="totp_failure",
    )

    client = FakeClient.instances[0]
    assert result["status"] == "error"
    assert result["error_type"] == "ValueError"
    assert "private TOTP failure details" not in json.dumps(result)
    assert all(session.exited == 1 for session in (client.public, client.private, client.graphql))


def test_secure_output_creates_owner_only_file_and_appends_jsonl(tmp_path):
    output_path = tmp_path / "matrix.jsonl"

    with login_matrix.secure_output(output_path) as output:
        output.write('{"attempt": 0}\n')
    with login_matrix.secure_output(output_path) as output:
        output.write('{"attempt": 1}\n')

    assert stat.S_IMODE(output_path.stat().st_mode) == 0o600
    assert output_path.read_text().splitlines() == ['{"attempt": 0}', '{"attempt": 1}']


def test_secure_output_rejects_symlinks(tmp_path):
    target = tmp_path / "target.jsonl"
    target.write_text("")
    output_path = tmp_path / "matrix.jsonl"
    output_path.symlink_to(target)

    with pytest.raises(PermissionError, match="symlink"):
        with login_matrix.secure_output(output_path):
            pass


def test_secure_output_rejects_existing_shared_permissions(tmp_path):
    output_path = tmp_path / "matrix.jsonl"
    output_path.write_text("")
    output_path.chmod(0o640)

    with pytest.raises(PermissionError, match="owner-only"):
        with login_matrix.secure_output(output_path):
            pass


def test_async_main_runs_sequential_matrix_and_flushes_before_cooldown(tmp_path, monkeypatch):
    output_path = tmp_path / "matrix.jsonl"
    calls = []
    flush_sizes = []

    def fake_fetch(url, count):
        calls.append(("fetch", url, count))
        return [{"username": f"user-{index}", "password": "secret"} for index in range(count)]

    async def fake_attempt(job, account, **kwargs):
        calls.append(("attempt", job.trial, job.account_index, job.mode, account["username"]))
        assert kwargs["pairing"] == "separate"
        assert kwargs["login_timeout"] == 12.0
        assert isinstance(kwargs["digest_key"], bytes)
        assert kwargs["run_id"]
        return {"status": "ok", "trial": job.trial, "mode": job.mode}

    async def fake_sleep(seconds):
        calls.append(("sleep", seconds))
        flush_sizes.append(len(output_path.read_text().splitlines()))

    async def fake_to_thread(function, *args):
        calls.append(("thread", function.__name__))
        return function(*args)

    monkeypatch.setattr(login_matrix, "fetch_accounts", fake_fetch)
    monkeypatch.setattr(login_matrix, "attempt", fake_attempt)
    monkeypatch.setattr(login_matrix.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(login_matrix.asyncio, "to_thread", fake_to_thread)

    result = asyncio.run(
        login_matrix.async_main(
            [
                "--mode",
                "both",
                "--count",
                "2",
                "--cooldown",
                "10",
                "--login-timeout",
                "12",
                "--output",
                str(output_path),
            ],
            {
                "IG_RUN_LOGIN_MATRIX": "1",
                "TEST_ACCOUNTS_URL": "https://pool.test/accounts?kind=live",
            },
        )
    )

    assert result == 0
    assert calls[:2] == [
        ("thread", "fake_fetch"),
        ("fetch", "https://pool.test/accounts?kind=live", 4),
    ]
    assert [call[1:] for call in calls if call[0] == "attempt"] == [
        (0, 0, "stable", "user-0"),
        (0, 1, "fresh", "user-1"),
        (1, 2, "fresh", "user-2"),
        (1, 3, "stable", "user-3"),
    ]
    assert [call for call in calls if call[0] == "sleep"] == [("sleep", 10.0)] * 3
    assert flush_sizes == [1, 2, 3]
    records = [json.loads(line) for line in output_path.read_text().splitlines()]
    assert [record["attempt"] for record in records] == [0, 1, 2, 3]


def test_async_main_crossover_fetches_one_account_per_trial(tmp_path, monkeypatch):
    requested = []

    def fake_fetch(_url, count):
        requested.append(count)
        return [{"username": f"user-{index}", "password": "secret"} for index in range(count)]

    async def fake_attempt(job, _account, **_kwargs):
        return {"status": "ok", "trial": job.trial, "mode": job.mode}

    async def fake_sleep(_seconds):
        return None

    monkeypatch.setattr(login_matrix, "fetch_accounts", fake_fetch)
    monkeypatch.setattr(login_matrix, "attempt", fake_attempt)
    monkeypatch.setattr(login_matrix.asyncio, "sleep", fake_sleep)

    result = asyncio.run(
        login_matrix.async_main(
            ["--pairing", "crossover", "--count", "2", "--cooldown", "10", "--output", str(tmp_path / "out")],
            {"IG_RUN_LOGIN_MATRIX": "1", "TEST_ACCOUNTS_URL": "https://pool.test/accounts"},
        )
    )

    assert result == 0
    assert requested == [2]


def test_main_reports_configuration_error_without_traceback():
    with pytest.raises(SystemExit, match="IG_RUN_LOGIN_MATRIX=1"):
        login_matrix.main([], {})

"""The live smoke reports outcomes without exposing account or response data."""

import json
import logging
import os
import subprocess
import sys
import types
import urllib.error
import urllib.request
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.regression.test_live_smoke import _FakeLiveClient, _load_live_smoke_module

SENSITIVE_VALUES = {
    name: f"smoke-sentinel-{name}"
    for name in ("username", "password", "user_id", "sessionid", "proxy", "totp_seed", "url", "response")
}
SENSITIVE_TEXT = " ".join(SENSITIVE_VALUES.values())
REPO_ROOT = Path(__file__).resolve().parents[2]


def noisy_dependency():
    print(SENSITIVE_TEXT)
    print(SENSITIVE_TEXT, file=sys.stderr)
    os.write(1, SENSITIVE_TEXT.encode())
    os.write(2, SENSITIVE_TEXT.encode())
    sys.__stdout__.write(SENSITIVE_TEXT)
    sys.__stderr__.write(SENSITIVE_TEXT)
    for name in ("aiograpi", "private_request", "public_request", "graphql_request", "httpx"):
        logging.getLogger(name).warning(SENSITIVE_TEXT)


class SensitiveHttpError(RuntimeError):
    def __init__(self, status=429):
        super().__init__(SENSITIVE_TEXT)
        self.response = types.SimpleNamespace(status_code=status)


class SensitiveClient(_FakeLiveClient):
    username = SENSITIVE_VALUES["username"]
    password = SENSITIVE_VALUES["password"]
    user_id = SENSITIVE_VALUES["user_id"]
    sessionid = SENSITIVE_VALUES["sessionid"]
    proxy = SENSITIVE_VALUES["proxy"]

    def __init__(self, mode="success"):
        self.mode = mode
        self.restored = False

    def set_settings(self, settings):
        pass

    def set_proxy(self, proxy):
        self.proxy = proxy

    def totp_generate_code(self, seed):
        return "000000"

    def load_settings(self, path):
        self.restored = True
        return super().load_settings(path)

    async def login(self, username, password, **kwargs):
        noisy_dependency()
        if self.mode == "login_error" or (self.mode == "required_error" and self.restored):
            raise SensitiveHttpError()
        return await super().login(username, password)

    async def login_by_sessionid(self, sessionid):
        if self.mode == "required_error":
            raise SensitiveHttpError()
        return await super().login_by_sessionid(sessionid)

    async def user_info_by_username_gql(self, username):
        noisy_dependency()
        return types.SimpleNamespace(username="instagram", pk="25025320")

    async def user_info_by_username_v1(self, username):
        return types.SimpleNamespace(username=self.username, pk=self.user_id)

    async def user_info_by_username(self, username):
        return await self.user_info_by_username_v1(username)

    async def user_info(self, user_id):
        return await self.user_info_by_username_v1(self.username)

    async def username_from_user_id(self, user_id):
        return self.username

    async def hashtag_info_v1(self, name):
        return types.SimpleNamespace(name=SENSITIVE_VALUES["response"])

    async def user_medias(self, user_id, amount=0):
        if self.mode == "required_error":
            raise SensitiveHttpError()
        return await super().user_medias(user_id, amount)

    async def music_search_v2(self, query):
        noisy_dependency()
        raise SensitiveHttpError(503)


def install_cli_fakes(mode):
    import aiograpi

    aiograpi.Client = lambda *args, **kwargs: SensitiveClient(mode)

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return json.dumps([SENSITIVE_VALUES]).encode()

    def fake_urlopen(*args, **kwargs):
        noisy_dependency()
        if mode == "allocation_error":
            raise urllib.error.HTTPError(SENSITIVE_VALUES["url"], 503, SENSITIVE_TEXT, {}, None)
        return FakeResponse()

    urllib.request.urlopen = fake_urlopen


@pytest.mark.parametrize("mode", ["success", "allocation_error", "login_error", "required_error"])
def test_actual_smoke_cli_never_prints_sensitive_data(mode):
    script = """
import logging
import runpy
import sys
from tests.regression.test_live_smoke_output import install_cli_fakes

logging.basicConfig(level=logging.DEBUG)
install_cli_fakes(sys.argv[1])
runpy.run_path("tests/live/smoke.py", run_name="__main__")
"""
    env = dict(os.environ, TEST_ACCOUNTS_URL="https://example.test/" + SENSITIVE_VALUES["url"])
    result = subprocess.run(
        [sys.executable, "-c", script, mode],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    output = result.stdout + result.stderr
    for value in SENSITIVE_VALUES.values():
        assert value not in output
    assert "Traceback" not in output
    assert result.stderr == ""
    assert result.returncode == (0 if mode == "success" else 1), output
    if mode == "allocation_error":
        assert "account_allocation FAIL: HTTPError HTTP 503" in output
    else:
        assert "pool: 1 accs" in output
    if mode in ("success", "required_error"):
        assert "LOGIN_OK acc1" in output
        assert "opt music_search_v2: SensitiveHttpError HTTP 503" in output
    if mode == "success":
        assert "ALL REQUIRED PASS" in output
        assert "REQ user_medias: len=3" in output
        assert "REQ user_medias_paginated: len=2 cursor=False" in output
    else:
        assert "ALL REQUIRED PASS" not in output
    if mode == "login_error":
        assert "acc1: SensitiveHttpError HTTP 429" in output
    if mode == "required_error":
        for name in ("saved_session_login", "sessionid_login", "user_medias"):
            assert f"REQ {name} FAIL: SensitiveHttpError HTTP 429" in output


@pytest.mark.parametrize("mode", ["success", "allocation_error", "unexpected_error"])
def test_smoke_restores_logging_after_success_or_unexpected_failure(mode, capsys):
    import asyncio

    smoke = _load_live_smoke_module()

    async def fake_fetch(url):
        noisy_dependency()
        if mode == "allocation_error":
            raise SensitiveHttpError()
        return [SENSITIVE_VALUES]

    previous_level = logging.root.manager.disable
    logging.disable(logging.WARNING)
    try:
        with (
            patch.dict(os.environ, {"TEST_ACCOUNTS_URL": SENSITIVE_VALUES["url"]}),
            patch.object(smoke, "_fetch_accounts", side_effect=fake_fetch),
            patch.object(smoke, "Client", side_effect=lambda *args, **kwargs: SensitiveClient()),
            patch.object(smoke, "_login_first_usable", side_effect=SensitiveHttpError())
            if mode == "unexpected_error"
            else nullcontext(),
        ):
            status = asyncio.run(smoke.main())
        assert status == (0 if mode == "success" else 1)
        assert logging.root.manager.disable == logging.WARNING
    finally:
        logging.disable(previous_level)
    captured = capsys.readouterr()
    for value in SENSITIVE_VALUES.values():
        assert value not in captured.out + captured.err
    assert captured.err == ""
    if mode == "unexpected_error":
        assert "FAILED smoke: SensitiveHttpError HTTP 429" in captured.out


@pytest.mark.parametrize("status", [100, 429, 599])
def test_error_summary_keeps_only_valid_integer_http_status(status):
    smoke = _load_live_smoke_module()

    assert smoke._error_summary(SensitiveHttpError(status)) == f"SensitiveHttpError HTTP {status}"


@pytest.mark.parametrize("status", [True, False, "429", SENSITIVE_TEXT, 99, 600, None])
def test_error_summary_ignores_non_http_status_values(status):
    smoke = _load_live_smoke_module()

    assert smoke._error_summary(SensitiveHttpError(status)) == "SensitiveHttpError"


def test_error_summary_uses_numeric_code_if_response_status_is_unavailable():
    smoke = _load_live_smoke_module()
    error = SensitiveHttpError()
    error.response = None
    error.code = 503

    assert smoke._error_summary(error) == "SensitiveHttpError HTTP 503"


@pytest.mark.parametrize("fail", [False, True])
def test_output_context_restores_descriptors_and_closes_duplicates(fail, capfd):
    smoke = _load_live_smoke_module()
    stdout, stderr = sys.stdout, sys.stderr
    original_fds = {fd: (os.fstat(fd).st_dev, os.fstat(fd).st_ino) for fd in (1, 2)}
    duplicates = []
    real_dup = os.dup

    def track_dup(fd):
        duplicate = real_dup(fd)
        duplicates.append(duplicate)
        return duplicate

    with patch.object(smoke.os, "dup", side_effect=track_dup):
        try:
            with smoke._quiet_output() as report:
                noisy_dependency()
                report("SAFE_REPORT")
                if fail:
                    raise RuntimeError("synthetic failure")
        except RuntimeError:
            assert fail

    assert sys.stdout is stdout
    assert sys.stderr is stderr
    assert {fd: (os.fstat(fd).st_dev, os.fstat(fd).st_ino) for fd in (1, 2)} == original_fds
    assert duplicates
    for fd in duplicates:
        with pytest.raises(OSError):
            os.fstat(fd)
    sys.__stdout__.flush()
    sys.__stderr__.flush()
    os.write(1, b"STDOUT_RESTORED")
    os.write(2, b"STDERR_RESTORED")
    captured = capfd.readouterr()
    assert "SAFE_REPORT" in captured.out
    assert "STDOUT_RESTORED" in captured.out
    assert "STDERR_RESTORED" in captured.err
    for value in SENSITIVE_VALUES.values():
        assert value not in captured.out + captured.err


def test_missing_configuration_keeps_local_skip_behavior():
    env = os.environ.copy()
    env.pop("TEST_ACCOUNTS_URL", None)
    result = subprocess.run(
        [sys.executable, "tests/live/smoke.py"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "SKIP: TEST_ACCOUNTS_URL not set"
    assert result.stderr == ""

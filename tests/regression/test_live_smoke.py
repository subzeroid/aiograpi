import importlib.util
import io
import os
import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlsplit


def _load_live_smoke_module():
    smoke_path = Path(__file__).resolve().parents[1] / "live" / "smoke.py"
    spec = importlib.util.spec_from_file_location("aiograpi_live_smoke", smoke_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeLiveClient:
    user_id = "1"
    sessionid = "1%3Asession"
    proxy = None

    async def login_by_sessionid(self, sessionid):
        self.sessionid = sessionid
        return True

    async def account_info(self):
        return types.SimpleNamespace(pk=self.user_id)

    async def get_timeline_feed(self, reason="cold_start_fetch"):
        return {"reason": reason}

    async def user_info_by_username_gql(self, username):
        raise RuntimeError("429 Too Many Requests")

    async def user_info_by_username_v1(self, username):
        return types.SimpleNamespace(username=username, pk="25025320")

    async def user_info_by_username_v2_gql(self, username):
        raise AssertionError("public web GraphQL helper must not be a required check")

    async def user_short_gql(self, user_id):
        raise AssertionError("public web GraphQL helper must not be a required check")

    async def user_info_by_username(self, username):
        return types.SimpleNamespace(username=username, pk="25025320")

    async def user_info(self, user_id):
        return types.SimpleNamespace(username="instagram", pk=str(user_id))

    async def username_from_user_id(self, user_id):
        return "instagram"

    async def hashtag_info_v1(self, name):
        return types.SimpleNamespace(name=name)

    async def clip_info_for_creation(self):
        return {"clips": True}

    async def direct_search(self, query):
        return [types.SimpleNamespace(username=query)]

    async def user_medias_v1(self, user_id, amount=0):
        return [types.SimpleNamespace(pk=str(i)) for i in range(amount)]

    async def user_medias_gql(self, user_id, amount=0):
        raise AssertionError("public web GraphQL helper must not be a required check")

    async def user_medias(self, user_id, amount=0):
        return [types.SimpleNamespace(pk=str(i)) for i in range(amount)]

    async def user_medias_paginated(self, user_id, amount=0):
        return [types.SimpleNamespace(pk=str(i)) for i in range(amount)], None

    async def user_followers(self, user_id, amount=0, use_cache=True):
        return [types.SimpleNamespace(pk=str(i)) for i in range(amount)]

    async def user_followers_v1(self, user_id, amount=0, use_cache=True):
        return [
            types.SimpleNamespace(
                pk=str(i),
                is_verified=False,
                latest_reel_media=1710000000 + i,
                has_anonymous_profile_picture=False,
            )
            for i in range(amount)
        ]

    async def user_following(self, user_id, amount=0, use_cache=True):
        return [types.SimpleNamespace(pk=str(i)) for i in range(amount)]

    async def user_stories(self, user_id, amount=0):
        return [types.SimpleNamespace(pk=str(i)) for i in range(amount)]

    async def highlight_info(self, highlight_id):
        return types.SimpleNamespace(pk=str(highlight_id))


class _LoginClient:
    user_id = "1"

    def __init__(self, delay=0):
        self.delay = delay
        self.proxy = None

    def set_settings(self, settings):
        self.settings = settings

    def set_proxy(self, proxy):
        self.proxy = proxy

    def totp_generate_code(self, seed):
        return "123456"

    async def login(self, **kwargs):
        if self.delay:
            import asyncio

            await asyncio.sleep(self.delay)
        return True


class LiveSmokeRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_accounts_overrides_existing_default_count(self):
        smoke = _load_live_smoke_module()
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return b"[]"

        def fake_urlopen(req, context=None):
            captured["url"] = req.full_url
            return FakeResponse()

        with patch.object(smoke.urllib.request, "urlopen", side_effect=fake_urlopen):
            await smoke._fetch_accounts("https://example.test/accounts?count=1&token=abc")

        query = parse_qs(urlsplit(captured["url"]).query)
        self.assertEqual(query["count"], ["10"])
        self.assertEqual(query["token"], ["abc"])

    def test_direct_script_execution_imports_checkout_package(self):
        repo_root = Path(__file__).resolve().parents[2]
        smoke_path = repo_root / "tests" / "live" / "smoke.py"
        script = f"""
import os
import runpy
import sys

repo_root = {str(repo_root)!r}
smoke_path = {str(smoke_path)!r}
sys.path = [str({str(smoke_path.parent)!r})] + [
    path for path in sys.path if path not in ("", repo_root)
]
os.environ.pop("TEST_ACCOUNTS_URL", None)
module_globals = runpy.run_path(smoke_path, run_name="aiograpi_live_smoke_test")
print(module_globals["Client"].__module__)
print(sys.modules["aiograpi"].__file__)
"""
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=repo_root,
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )

        self.assertIn(str(repo_root / "aiograpi"), result.stdout)

    async def test_anonymous_public_lookup_throttle_does_not_fail_smoke(self):
        smoke = _load_live_smoke_module()
        fake_logged_client = _FakeLiveClient()

        with patch.dict(os.environ, {"TEST_ACCOUNTS_URL": "https://example.test/accounts"}):
            with patch.object(smoke, "Client", side_effect=lambda *args, **kwargs: _FakeLiveClient()):
                with patch.object(smoke, "_fetch_accounts", AsyncMock(return_value=[{"username": "example"}])):
                    with patch.object(smoke, "_login_first_usable", AsyncMock(return_value=fake_logged_client)):
                        status = await smoke.main()

        self.assertEqual(status, 0)

    async def test_login_first_usable_tries_next_account_after_login_timeout(self):
        smoke = _load_live_smoke_module()
        slow_client = _LoginClient(delay=1)
        fast_client = _LoginClient()
        accounts = [
            {
                "username": "slow",
                "password": "password",
                "client_settings": {},
                "proxy": "",
                "user_id": "1",
            },
            {
                "username": "fast",
                "password": "password",
                "client_settings": {},
                "proxy": "",
                "user_id": "2",
            },
        ]

        with patch.dict(os.environ, {"AIOGRAPI_TEST_LOGIN_TIMEOUT": "0.01"}):
            with patch.object(smoke, "Client", side_effect=[slow_client, fast_client]):
                import asyncio

                result = await asyncio.wait_for(smoke._login_first_usable(accounts), timeout=0.2)

        self.assertIs(result, fast_client)

    async def test_required_smoke_uses_private_first_high_level_paths(self):
        smoke = _load_live_smoke_module()
        fake_logged_client = _FakeLiveClient()

        with patch.dict(os.environ, {"TEST_ACCOUNTS_URL": "https://example.test/accounts"}):
            with patch.object(smoke, "Client", side_effect=lambda *args, **kwargs: _FakeLiveClient()):
                with patch.object(smoke, "_fetch_accounts", AsyncMock(return_value=[{"username": "example"}])):
                    with patch.object(smoke, "_login_first_usable", AsyncMock(return_value=fake_logged_client)):
                        with patch("sys.stdout", new=io.StringIO()) as output:
                            status = await smoke.main()

        self.assertEqual(status, 0, output.getvalue())
        smoke_output = output.getvalue()
        for required_name in [
            "user_info_by_username",
            "user_info",
            "username_from_user_id",
            "user_medias",
            "user_medias_paginated",
            "user_followers_extended_fields",
            "user_following",
            "user_stories",
        ]:
            self.assertIn(f"REQ {required_name}:", smoke_output)
        for public_name in [
            "private_v2_gql",
            "user_short_gql",
            "user_medias_gql",
        ]:
            self.assertNotIn(f"REQ {public_name}:", smoke_output)
        self.assertNotIn("AttributeError", smoke_output)

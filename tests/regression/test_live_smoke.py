import importlib.util
import os
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
        return types.SimpleNamespace(username=username, pk="25025320")

    async def user_short_gql(self, user_id):
        return types.SimpleNamespace(username="instagram", pk=str(user_id))

    async def hashtag_info_v1(self, name):
        return types.SimpleNamespace(name=name)

    async def user_medias_v1(self, user_id, amount=0):
        return [types.SimpleNamespace(pk=str(i)) for i in range(amount)]

    async def user_medias_gql(self, user_id, amount=0):
        return [types.SimpleNamespace(pk=str(i)) for i in range(amount)]

    async def user_followers(self, user_id, amount=0):
        return [types.SimpleNamespace(pk=str(i)) for i in range(amount)]

    async def highlight_info(self, highlight_id):
        return types.SimpleNamespace(pk=str(highlight_id))

    def __getattr__(self, name):
        async def _method(*args, **kwargs):
            return types.SimpleNamespace(name=name)

        return _method


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

    async def test_anonymous_public_lookup_throttle_does_not_fail_smoke(self):
        smoke = _load_live_smoke_module()
        fake_logged_client = _FakeLiveClient()

        with patch.dict(os.environ, {"TEST_ACCOUNTS_URL": "https://example.test/accounts"}):
            with patch.object(smoke, "Client", return_value=_FakeLiveClient()):
                with patch.object(smoke, "_fetch_accounts", AsyncMock(return_value=[{"username": "example"}])):
                    with patch.object(smoke, "_login_first_usable", AsyncMock(return_value=fake_logged_client)):
                        status = await smoke.main()

        self.assertEqual(status, 0)

import os
import unittest

from aiograpi import Client
from tests.live.smoke import _fetch_accounts


class ClientAccountLiveTestCase(unittest.IsolatedAsyncioTestCase):
    async def live_client(self):
        accounts_url = os.getenv("TEST_ACCOUNTS_URL")
        if not accounts_url:
            self.skipTest("TEST_ACCOUNTS_URL is required for account live tests")
        accounts = await _fetch_accounts(accounts_url, count=20)
        for account in accounts:
            try:
                settings = dict(account.get("client_settings") or account.get("settings") or {})
                settings.pop("totp_seed", None)
                client = Client(settings=settings, proxy=account.get("proxy"), override_app_version=True)
                client._user_id = account.get("user_id")
                await client.account_info()
                return client
            except Exception:
                continue
        self.skipTest("No usable saved-session account returned")

    @unittest.skipUnless(
        os.getenv("IG_RUN_AI_INFO_LIVE"),
        "set IG_RUN_AI_INFO_LIVE=1 to run the account mutation test",
    )
    async def test_account_set_ai_info_live(self):
        client = await self.live_client()
        try:
            enabled = await client.account_set_ai_info(True)
            self.assertIsNotNone(enabled)
        finally:
            disabled = await client.account_set_ai_info(False)
            self.assertIsNotNone(disabled)

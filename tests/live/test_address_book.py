import os
import unittest

from aiograpi import Client
from tests.live.smoke import _fetch_accounts


class ClientAddressBookLiveTestCase(unittest.IsolatedAsyncioTestCase):
    async def live_client(self):
        test_accounts_url = os.getenv("TEST_ACCOUNTS_URL")
        if not test_accounts_url:
            self.skipTest("TEST_ACCOUNTS_URL is required for address book live tests")
        accounts = await _fetch_accounts(test_accounts_url, count=80)
        last_exc = None
        for acc in accounts:
            try:
                cl = Client()
                settings = dict(acc.get("client_settings") or acc.get("settings") or {})
                settings.pop("totp_seed", None)
                cl.set_settings(settings)
                if acc.get("proxy"):
                    cl.set_proxy(acc["proxy"])
                cl._user_id = acc.get("user_id")
                await cl.account_info()
                return cl
            except Exception as exc:
                last_exc = exc
        self.skipTest(f"No usable saved-session account returned: {last_exc}")

    async def test_address_book_link_returns_suggestions_payload_live(self):
        cl = await self.live_client()
        self.addAsyncCleanup(cl.address_book_unlink)
        contacts = [
            {
                "phone_numbers": [{"phone_number": "+15555550123"}],
                "email_addresses": [],
                "first_name": "Test",
                "last_name": "Contact",
            }
        ]

        result = await cl.address_book_link(contacts)

        self.assertEqual(result.get("status"), "ok")

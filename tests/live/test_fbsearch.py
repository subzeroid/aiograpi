import os
import unittest

from aiograpi.types import UserShort
from tests.live.smoke import _fetch_accounts, _login_first_usable

INSTAGRAM_USER_ID = "25025320"


class ClientFbSearchLiveTestCase(unittest.IsolatedAsyncioTestCase):
    async def live_client(self):
        test_accounts_url = os.getenv("TEST_ACCOUNTS_URL")
        if not test_accounts_url:
            self.skipTest("TEST_ACCOUNTS_URL is required for fbsearch live tests")
        accounts = await _fetch_accounts(test_accounts_url, count=20)
        cl = await _login_first_usable(accounts)
        if cl is None:
            self.skipTest("Could not login with any test account")
        return cl

    async def test_fbsearch_suggested_profiles_returns_user_short_live(self):
        cl = await self.live_client()

        users = await cl.fbsearch_suggested_profiles(INSTAGRAM_USER_ID)

        if not users:
            self.skipTest("Instagram returned no suggested profiles")
        self.assertIsInstance(users[0], UserShort)
        self.assertIsInstance(users[0].stories, list)

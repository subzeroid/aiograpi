import os
import unittest

from aiograpi import Client
from aiograpi.types import Media, UserShort
from tests.live.smoke import _fetch_accounts

INSTAGRAM_USER_ID = "25025320"


class ClientFbSearchLiveTestCase(unittest.IsolatedAsyncioTestCase):
    async def live_client(self):
        test_accounts_url = os.getenv("TEST_ACCOUNTS_URL")
        if not test_accounts_url:
            self.skipTest("TEST_ACCOUNTS_URL is required for fbsearch live tests")
        accounts = await _fetch_accounts(test_accounts_url, count=20)
        last_error = None
        for account in accounts:
            try:
                cl = Client(settings=dict(account["client_settings"]), proxy=os.getenv("IG_PROXY") or account["proxy"])
                cl._user_id = account.get("user_id")
                await cl.fbsearch_topsearch_v2("instagram")
                return cl
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {str(exc)[:120]}"
        self.skipTest(f"Could not build a usable fbsearch test client: {last_error}")

    async def test_fbsearch_suggested_profiles_returns_user_short_live(self):
        cl = await self.live_client()

        users = await cl.fbsearch_suggested_profiles(INSTAGRAM_USER_ID)

        if not users:
            self.skipTest("Instagram returned no suggested profiles")
        self.assertIsInstance(users[0], UserShort)
        self.assertIsInstance(users[0].stories, list)

    async def test_media_search_returns_media_live(self):
        cl = await self.live_client()

        medias = await cl.media_search("space", amount=3)

        if not medias:
            self.skipTest("Instagram returned no media search results")
        self.assertLessEqual(len(medias), 3)
        self.assertIsInstance(medias[0], Media)
        self.assertTrue(medias[0].pk)
        self.assertTrue(medias[0].code)

import os
import unittest

from aiograpi.exceptions import TrackNotFound
from tests.live.smoke import _fetch_accounts, _login_first_usable


class ClientTrackLiveTestCase(unittest.IsolatedAsyncioTestCase):
    async def live_client(self):
        test_accounts_url = os.getenv("TEST_ACCOUNTS_URL")
        if not test_accounts_url:
            self.skipTest("TEST_ACCOUNTS_URL is required for track live tests")
        accounts = await _fetch_accounts(test_accounts_url, count=20)
        cl = await _login_first_usable(accounts)
        if cl is None:
            self.skipTest("Could not login with any test account")
        return cl

    async def test_music_bookmarked_live(self):
        cl = await self.live_client()

        result = await cl.music_bookmarked()

        self.assertEqual(result.get("status"), "ok")
        self.assertIsInstance(result.get("items"), list)

    async def test_track_info_by_canonical_id_missing_live(self):
        cl = await self.live_client()

        with self.assertRaises(TrackNotFound) as cm:
            await cl.track_info_by_canonical_id("0")

        self.assertEqual(cm.exception.music_canonical_id, "0")

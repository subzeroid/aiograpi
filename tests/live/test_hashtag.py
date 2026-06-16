import os
import unittest

from aiograpi import Client
from aiograpi.types import Media
from tests.live.smoke import _fetch_accounts


class ClientHashtagLiveTestCase(unittest.IsolatedAsyncioTestCase):
    async def live_client(self):
        test_accounts_url = os.getenv("TEST_ACCOUNTS_URL")
        if not test_accounts_url:
            self.skipTest("TEST_ACCOUNTS_URL is required for hashtag live tests")
        accounts = await _fetch_accounts(test_accounts_url, count=20)
        last_error = None
        for account in accounts:
            try:
                cl = Client(settings=dict(account["client_settings"]), proxy=os.getenv("IG_PROXY") or account["proxy"])
                cl._user_id = account.get("user_id")
                await cl.hashtag_info("instagram")
                return cl
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {str(exc)[:120]}"
        self.skipTest(f"Could not build a usable hashtag test client: {last_error}")

    async def test_hashtag_medias_paginated_recent_live(self):
        cl = await self.live_client()

        medias, max_id = await cl.hashtag_medias_paginated("instagram", amount=12, tab_key="recent")
        self.assertGreater(len(medias), 0)
        self.assertLessEqual(len(medias), 12)
        self.assertIsInstance(medias[0], Media)
        if not max_id:
            self.skipTest("instagram hashtag did not return next cursor")

        next_medias, next_max_id = await cl.hashtag_medias_paginated(
            "instagram",
            amount=12,
            tab_key="recent",
            end_cursor=max_id,
        )

        self.assertGreater(len(next_medias), 0)
        self.assertNotEqual(max_id, next_max_id)
        self.assertTrue({media.pk for media in medias}.isdisjoint({media.pk for media in next_medias}))

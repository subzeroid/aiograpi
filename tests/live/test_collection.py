import os
import unittest

from aiograpi.types import Media
from tests.live.smoke import _fetch_accounts, _login_first_usable


class ClientCollectionLiveTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        test_accounts_url = os.getenv("TEST_ACCOUNTS_URL")
        if not test_accounts_url:
            self.skipTest("TEST_ACCOUNTS_URL is required for collection live tests")
        accounts = await _fetch_accounts(test_accounts_url, count=20)
        self.cl = await _login_first_usable(accounts)
        if self.cl is None:
            self.skipTest("Could not login with any test account")

    async def test_collection_medias_by_name_pagination_live(self):
        user_id = await self.cl.user_id_from_username("instagram")
        media = (await self.cl.user_medias(user_id, amount=1))[0]
        self.assertTrue(await self.cl.media_save(media.id))
        try:
            collection = next((item for item in await self.cl.collections() if item.media_count), None)
            self.assertIsNotNone(collection)

            medias = await self.cl.collection_medias_by_name(collection.name, amount=1)
            self.assertEqual(len(medias), 1)
            self.assertIsInstance(medias[0], Media)
            self.assertEqual(
                await self.cl.collection_medias_by_name(
                    collection.name,
                    amount=1,
                    last_media_pk=medias[0].pk,
                ),
                [],
            )
        finally:
            await self.cl.media_unsave(media.id)

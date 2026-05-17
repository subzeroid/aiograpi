import unittest
from unittest.mock import AsyncMock

from aiograpi import Client


class HashtagRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_hashtag_medias_recent_strips_leading_hash_and_warns(self):
        client = Client()
        client.hashtag_medias_recent_a1 = AsyncMock(return_value=["media"])

        with self.assertWarnsRegex(UserWarning, "leading '#'"):
            medias = await client.hashtag_medias_recent("#pizza", amount=1)

        self.assertEqual(medias, ["media"])
        client.hashtag_medias_recent_a1.assert_awaited_once_with("pizza", 1)

    async def test_hashtag_name_cannot_be_empty_after_normalization(self):
        client = Client()
        client.hashtag_medias_recent_a1 = AsyncMock(side_effect=AssertionError("network call should not be attempted"))

        with self.assertRaisesRegex(ValueError, "Hashtag name cannot be empty"):
            await client.hashtag_medias_recent("#")

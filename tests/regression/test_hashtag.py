import unittest
from unittest.mock import AsyncMock

from aiograpi import Client
from aiograpi.types import Hashtag


class HashtagRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_hashtag_info_a1_uses_private_endpoint_without_public_web_request(self):
        client = Client()
        hashtag = Hashtag(id="1", name="pizza")
        client.public_a1_request = AsyncMock(side_effect=AssertionError("public web should not be called"))
        client.hashtag_info_v1 = AsyncMock(return_value=hashtag)

        result = await client.hashtag_info_a1("pizza")

        self.assertEqual(result, hashtag)
        client.public_a1_request.assert_not_called()
        client.hashtag_info_v1.assert_awaited_once_with("pizza")

    async def test_hashtag_medias_a1_chunk_uses_private_endpoint_without_public_web_request(self):
        client = Client()
        client.public_a1_request = AsyncMock(side_effect=AssertionError("public web should not be called"))
        client.hashtag_medias_v1_chunk = AsyncMock(return_value=(["media"], "cursor"))

        medias, cursor = await client.hashtag_medias_a1_chunk("pizza", max_amount=2, tab_key="recent")

        self.assertEqual(medias, ["media"])
        self.assertEqual(cursor, "cursor")
        client.public_a1_request.assert_not_called()
        client.hashtag_medias_v1_chunk.assert_awaited_once_with("pizza", 2, "recent", None)

    async def test_hashtag_medias_a1_uses_full_private_fallback_when_chunk_is_short(self):
        client = Client()
        client.hashtag_medias_a1_chunk = AsyncMock(return_value=(["media"], "cursor"))
        client.hashtag_medias_v1 = AsyncMock(return_value=["media", "media2"])

        medias = await client.hashtag_medias_a1("pizza", amount=2, tab_key="recent")

        self.assertEqual(medias, ["media", "media2"])
        client.hashtag_medias_v1.assert_awaited_once_with("pizza", 2, "recent")

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

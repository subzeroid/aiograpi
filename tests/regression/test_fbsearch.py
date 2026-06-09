import unittest
from unittest.mock import AsyncMock

from aiograpi import Client


class FbSearchRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    def _build_client(self):
        client = Client()
        client.__dict__["timezone_offset"] = 10800
        return client

    async def test_search_hashtags_accepts_numeric_private_id(self):
        client = self._build_client()
        client.private_request = AsyncMock(
            return_value={
                "results": [
                    {
                        "id": 17843915557058484,
                        "name": "restaurant",
                        "media_count": 65043150,
                        "profile_pic_url": None,
                    }
                ]
            }
        )

        hashtags = await client.search_hashtags("restaurant")

        self.assertEqual(hashtags[0].id, "17843915557058484")
        self.assertEqual(hashtags[0].name, "restaurant")
        self.assertEqual(hashtags[0].media_count, 65043150)

import unittest
from unittest.mock import AsyncMock

from aiograpi import Client
from aiograpi.exceptions import MediaError


class InsightsRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    def build_client(self):
        client = Client()
        client._user_id = "1"
        return client

    async def test_insights_media_returns_available_payload(self):
        client = self.build_client()
        payload = {
            "data": {
                "instagram_post_by_igid": {
                    "id": "18000000000000000",
                    "instagram_media_id": "123",
                    "inline_insights_node": {
                        "state": "AVAILABLE",
                        "metrics": {
                            "like_count": {"value": 1},
                        },
                    },
                    "like_count": 1,
                    "save_count": 0,
                },
            },
        }
        client.private_request = AsyncMock(return_value=payload)

        result = await client.insights_media("123")

        self.assertEqual(result["instagram_media_id"], "123")
        self.assertEqual(result["inline_insights_node"]["state"], "AVAILABLE")

    async def test_insights_media_raises_media_error_when_inline_insights_missing(self):
        client = self.build_client()
        client.last_json = {}
        payload = {
            "data": {
                "instagram_post_by_igid": {
                    "id": "18000000000000000",
                    "instagram_media_id": "123",
                    "inline_insights_node": None,
                    "like_count": None,
                    "save_count": None,
                },
            },
        }
        client.private_request = AsyncMock(return_value=payload)

        with self.assertRaises(MediaError) as cm:
            await client.insights_media("123")

        self.assertEqual(cm.exception.media_pk, "123")
        self.assertIn("inline insights", cm.exception.message)

    async def test_insights_media_raises_media_error_when_post_missing(self):
        client = self.build_client()
        client.last_json = {}
        client.private_request = AsyncMock(return_value={"data": {"instagram_post_by_igid": None}})

        with self.assertRaises(MediaError) as cm:
            await client.insights_media("123")

        self.assertEqual(cm.exception.media_pk, "123")
        self.assertIn("insight data", cm.exception.message)

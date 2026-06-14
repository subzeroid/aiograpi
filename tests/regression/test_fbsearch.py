import unittest
from unittest.mock import AsyncMock

from aiograpi import Client
from aiograpi.types import UserShort


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

    async def test_fbsearch_suggested_profiles_extracts_user_short_without_stories(self):
        client = self._build_client()
        client.private_request = AsyncMock(
            return_value={
                "users": [
                    {
                        "pk": "123",
                        "username": "alice",
                        "full_name": "Alice",
                        "profile_pic_url": "https://example.com/alice.jpg",
                        "is_private": False,
                        "has_anonymous_profile_picture": False,
                    }
                ]
            }
        )

        users = await client.fbsearch_suggested_profiles("999")

        client.private_request.assert_awaited_once_with(
            "fbsearch/accounts_recs/",
            params={
                "target_user_id": "999",
                "include_friendship_status": "true",
            },
        )
        self.assertIsInstance(users[0], UserShort)
        self.assertEqual(users[0].pk, "123")
        self.assertEqual(users[0].stories, [])

import unittest
from unittest.mock import AsyncMock

from aiograpi import Client
from aiograpi.exceptions import ClientNotFoundError, UserNotFound


class StoryMixinRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_user_stories_uses_private_first_when_authorized(self):
        client = Client()
        client.authorization_data = {"sessionid": "sessionid-value", "ds_user_id": "1"}
        client.user_stories_v1 = AsyncMock(return_value=["private"])
        client.user_stories_gql = AsyncMock(
            side_effect=AssertionError("authorized stories lookup should use private first")
        )

        stories = await client.user_stories("123", amount=1)

        self.assertEqual(stories, ["private"])
        client.user_stories_v1.assert_awaited_once_with("123", 1)
        client.user_stories_gql.assert_not_awaited()

    async def test_user_stories_public_promotes_not_found_to_user_not_found(self):
        client = Client()
        client.last_json = {"status": "fail"}
        client.user_stories_gql = AsyncMock(side_effect=ClientNotFoundError("not found"))

        with self.assertRaises(UserNotFound):
            await client._user_stories_public("123", amount=1)

    async def test_user_stories_public_returns_empty_for_missing_reel(self):
        client = Client()
        client.user_stories_gql = AsyncMock(side_effect=IndexError("missing"))

        stories = await client._user_stories_public("123", amount=1)

        self.assertEqual(stories, [])

    async def test_users_stories_gql_populates_user_short_stories(self):
        client = Client()
        story_payload = {
            "id": "1234567890",
            "owner": {
                "id": "123",
                "username": "alice",
                "full_name": "Alice",
                "profile_pic_url": "https://example.com/alice.jpg",
                "is_private": False,
            },
            "display_url": "https://example.com/story.jpg",
            "taken_at_timestamp": 1_700_000_000,
            "is_video": False,
            "tappable_objects": [],
            "edge_media_to_sponsor_user": {"edges": []},
        }

        client.public_graphql_request = AsyncMock(
            return_value={"reels_media": [{"owner": story_payload["owner"], "items": [story_payload]}]}
        )

        users = await client.users_stories_gql(["123"])

        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].pk, "123")
        self.assertEqual(len(users[0].stories), 1)
        self.assertEqual(users[0].stories[0].id, "1234567890_123")

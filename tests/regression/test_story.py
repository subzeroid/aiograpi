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

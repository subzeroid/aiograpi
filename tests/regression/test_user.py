import unittest
from unittest.mock import AsyncMock, Mock

from aiograpi import Client
from aiograpi.exceptions import ClientError


class UserMixinRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_username_from_user_id_fallback_awaits_user_info(self):
        client = Client()
        client.username_from_user_id_gql = AsyncMock(side_effect=ClientError("graphql failed"))
        client.user_info_v1 = AsyncMock(return_value=Mock(username="fallback_user"))

        username = await client.username_from_user_id(123)

        self.assertEqual(username, "fallback_user")
        client.username_from_user_id_gql.assert_awaited_once_with("123")
        client.user_info_v1.assert_awaited_once_with("123")

    async def test_user_short_gql_uses_web_profile_doc_id_without_legacy_query_hash(self):
        client = Client()
        web_user = {
            "id": "25025320",
            "username": "instagram",
            "full_name": "Instagram",
            "is_private": False,
            "profile_pic_url": "https://example.com/pic.jpg",
        }
        client.public_graphql_request = AsyncMock(side_effect=AssertionError("legacy query_hash should not be used"))
        client.user_web_profile_info_gql = AsyncMock(return_value=web_user)

        user = await client.user_short_gql("25025320")

        self.assertEqual(user.username, "instagram")
        client.user_web_profile_info_gql.assert_awaited_once_with("25025320")
        client.public_graphql_request.assert_not_called()

    async def test_user_web_profile_info_gql_uses_public_doc_id_endpoint(self):
        client = Client()
        web_user = {
            "id": "25025320",
            "username": "instagram",
            "full_name": "Instagram",
            "is_private": False,
            "profile_pic_url": "https://example.com/pic.jpg",
        }
        client.inject_sessionid_to_public = Mock(return_value=True)
        client.public_request = AsyncMock(side_effect=AssertionError("legacy /api/graphql endpoint should not be used"))
        client.public_doc_id_graphql_request = AsyncMock(return_value={"user": web_user})

        user = await client.user_web_profile_info_gql("25025320")

        self.assertEqual(user["username"], "instagram")
        client.public_request.assert_not_called()
        client.public_doc_id_graphql_request.assert_awaited_once()
        args, kwargs = client.public_doc_id_graphql_request.call_args
        self.assertEqual(args[0], "26762473490008061")
        self.assertEqual(args[1]["id"], "25025320")
        self.assertEqual(args[1]["render_surface"], "PROFILE")
        self.assertEqual(kwargs["referer"], "https://www.instagram.com/25025320/")

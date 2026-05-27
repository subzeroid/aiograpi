import json
import unittest
from unittest.mock import AsyncMock, Mock

from aiograpi import Client
from aiograpi.exceptions import ClientError, ClientGraphqlError
from aiograpi.mixins.user import UserMixin


class UserMixinRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    def _build_private_client(self):
        client = Client()
        client._user_id = "1"
        client.uuid = "uuid"
        client.with_action_data = lambda data: data
        return client

    def _build_action_client(self):
        client = Client()
        client._user_id = "1"
        client.uuid = "uuid"
        client.android_device_id = "android-device"
        return client

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

    async def test_user_info_by_username_gql_normalizes_username(self):
        class DummyClient(UserMixin):
            response_body = None

            def __init__(self):
                self.public_request_calls = []

            async def public_request(self, url, headers=None, **kwargs):
                self.public_request_calls.append({"url": url, "headers": headers, "kwargs": kwargs})
                return json.dumps(self.response_body)

        client = DummyClient()
        client.response_body = {
            "data": {
                "user": {
                    "id": "123",
                    "username": "example",
                    "full_name": "Example",
                    "is_private": False,
                    "is_verified": False,
                    "profile_pic_url": "https://example.com/pic.jpg",
                    "profile_pic_url_hd": None,
                    "edge_owner_to_timeline_media": {"count": 0},
                    "edge_followed_by": {"count": 0},
                    "edge_follow": {"count": 0},
                    "is_business_account": False,
                    "business_email": None,
                    "business_phone_number": None,
                    "biography": "",
                    "bio_links": [],
                    "external_url": None,
                    "business_category_name": None,
                    "category_name": None,
                    "fbid": "123",
                    "pinned_channels_info": {"pinned_channels_list": []},
                }
            }
        }

        user = await client.user_info_by_username_gql(" @Example ")

        self.assertEqual(user.username, "example")
        self.assertIn("web_profile_info/?username=example", client.public_request_calls[0]["url"])

    async def test_user_info_by_username_v1_normalizes_username(self):
        client = Client()
        client.private_request = AsyncMock(
            return_value={
                "user": {
                    "pk": "123",
                    "username": "example",
                    "full_name": "Example",
                    "is_private": False,
                    "is_verified": False,
                    "profile_pic_url": "https://example.com/pic.jpg",
                    "media_count": 0,
                    "follower_count": 0,
                    "following_count": 0,
                    "is_business": False,
                }
            }
        )

        user = await client.user_info_by_username_v1(" @Example ")

        self.assertEqual(user.username, "example")
        client.private_request.assert_awaited_once_with("users/example/usernameinfo/")

    async def test_user_info_by_username_v2_gql_normalizes_search_query(self):
        client = Client()
        client._inject_sessionid_for_v2_gql = Mock()
        client.public_doc_id_graphql_request = AsyncMock(
            return_value={"xdt_api__v1__fbsearch__non_profiled_serp": {"users": [{"username": "example", "pk": "123"}]}}
        )
        client.user_info_v2_gql = AsyncMock(return_value="user")

        result = await client.user_info_by_username_v2_gql(" @Example ")

        self.assertEqual(result, "user")
        client.public_doc_id_graphql_request.assert_awaited_once_with(
            "26347858941511777", {"hasQuery": True, "query": "example"}
        )

    async def test_user_stream_by_username_v1_normalizes_endpoint(self):
        client = Client()
        client.private_request = AsyncMock(return_value={"stream_rows": []})

        await client.user_stream_by_username_v1(" @Example ")

        client.private_request.assert_awaited_once()
        self.assertEqual(client.private_request.call_args.args[0], "users/example/usernameinfo_stream/")

    async def test_user_web_profile_info_v1_normalizes_username_param(self):
        client = Client()
        client.private_request = AsyncMock(return_value={"data": {"pk": "9", "username": "example"}})

        user = await client.user_web_profile_info_v1(" @Example ")

        client.private_request.assert_awaited_once_with("users/web_profile_info/", params={"username": "example"})
        self.assertEqual(user, {"pk": "9", "username": "example"})

    async def test_user_followers_v1_chunk_sends_order(self):
        client = Client()
        client.uuid = "rank-token"
        client.private_request = AsyncMock(return_value={"users": [], "next_max_id": None})

        await client.user_followers_v1_chunk("123", max_amount=2, order="date_followed_latest")

        client.private_request.assert_awaited_once()
        self.assertEqual(client.private_request.call_args.kwargs["params"]["order"], "date_followed_latest")

    async def test_user_followers_private_gql_chunk_extracts_followers_payload(self):
        client = Client()
        client.uuid = "rank-token"
        client.private_graphql_followers_list = AsyncMock(
            return_value={
                "data": {
                    "xdt_api__v1__friendships__followers": {
                        "users": [
                            {
                                "pk": "42",
                                "username": "follower",
                                "full_name": "Follower",
                                "profile_pic_url": None,
                            }
                        ],
                        "next_max_id": "next",
                    }
                }
            }
        )

        users, next_max_id = await client.user_followers_private_gql_chunk(
            "123",
            max_amount=1,
            order="date_followed_latest",
        )

        self.assertEqual(next_max_id, "next")
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].pk, "42")
        client.private_graphql_followers_list.assert_awaited_once_with(
            "123",
            "rank-token",
            max_id=None,
            order="date_followed_latest",
            priority="u=3, i",
        )

    async def test_user_followers_private_gql_raises_on_missing_payload(self):
        client = Client()
        client.uuid = "rank-token"
        client.private_graphql_followers_list = AsyncMock(return_value={"data": {}})

        with self.assertRaises(ClientGraphqlError):
            await client.user_followers_private_gql_chunk("123")

    async def test_user_follow_requests_chunk_fetches_pending_users(self):
        client = self._build_private_client()
        client.private_request = AsyncMock(
            return_value={
                "users": [
                    {
                        "pk": "42",
                        "username": "pending",
                        "full_name": "Pending User",
                        "profile_pic_url": None,
                    }
                ],
                "next_max_id": "next",
            }
        )

        users, next_max_id = await client.user_follow_requests_chunk(max_amount=1)

        self.assertEqual(next_max_id, "next")
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].pk, "42")
        client.private_request.assert_awaited_once_with("friendships/pending/", params={"count": 1})

    async def test_user_follow_requests_chunk_sends_non_empty_max_id(self):
        client = self._build_private_client()
        client.private_request = AsyncMock(return_value={"users": [], "next_max_id": None})

        await client.user_follow_requests_chunk(max_amount=20, max_id="cursor")

        client.private_request.assert_awaited_once_with(
            "friendships/pending/",
            params={"count": 20, "max_id": "cursor"},
        )

    async def test_user_follow_request_approve_posts_action_data_and_returns_status(self):
        client = self._build_private_client()
        client.private_request = AsyncMock(return_value={"friendship_status": {"followed_by": True}})

        result = await client.user_follow_request_approve("42")

        self.assertTrue(result)
        endpoint, data = client.private_request.call_args.args
        self.assertEqual(endpoint, "friendships/approve/42/")
        self.assertEqual(data["user_id"], "42")

    async def test_user_follow_request_decline_posts_action_data_and_returns_status(self):
        client = self._build_private_client()
        client.private_request = AsyncMock(return_value={"friendship_status": {"followed_by": False}})

        result = await client.user_follow_request_decline("42")

        self.assertTrue(result)
        endpoint, data = client.private_request.call_args.args
        self.assertEqual(endpoint, "friendships/ignore/42/")
        self.assertEqual(data["user_id"], "42")

    async def test_user_follow_requests_approve_batches_results(self):
        client = self._build_private_client()
        client.user_follow_request_approve = AsyncMock(side_effect=[True, False])

        result = await client.user_follow_requests_approve(["1", "2"])

        self.assertEqual(result, {"1": True, "2": False})
        client.user_follow_request_approve.assert_has_awaits([unittest.mock.call("1"), unittest.mock.call("2")])

    async def test_user_follow_requests_decline_batches_results(self):
        client = self._build_private_client()
        client.user_follow_request_decline = AsyncMock(side_effect=[False, True])

        result = await client.user_follow_requests_decline(["1", "2"])

        self.assertEqual(result, {"1": False, "2": True})
        client.user_follow_request_decline.assert_has_awaits([unittest.mock.call("1"), unittest.mock.call("2")])

    async def test_user_follow_posts_current_action_context(self):
        client = self._build_action_client()
        client.private_request = AsyncMock(return_value={"friendship_status": {"following": True}})

        self.assertTrue(await client.user_follow("42"))

        endpoint, data = client.private_request.call_args.args
        self.assertEqual(endpoint, "friendships/create/42/")
        self.assertEqual(data["user_id"], "42")
        self.assertEqual(data["_uid"], "1")
        self.assertEqual(data["device_id"], "android-device")
        self.assertEqual(data["radio_type"], "wifi-none")
        self.assertEqual(data["include_follow_friction_check"], "1")
        self.assertEqual(data["container_module"], "profile")

    async def test_user_unfollow_posts_current_action_context(self):
        client = self._build_action_client()
        client.private_request = AsyncMock(return_value={"friendship_status": {"following": False}})

        self.assertTrue(await client.user_unfollow("42"))

        endpoint, data = client.private_request.call_args.args
        self.assertEqual(endpoint, "friendships/destroy/42/")
        self.assertEqual(data["user_id"], "42")
        self.assertEqual(data["_uid"], "1")
        self.assertEqual(data["device_id"], "android-device")
        self.assertEqual(data["radio_type"], "wifi-none")
        self.assertEqual(data["container_module"], "profile")

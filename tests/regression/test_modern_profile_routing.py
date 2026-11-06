import unittest
from unittest.mock import AsyncMock, Mock

from aiograpi import Client
from aiograpi.exceptions import ClientError, ClientThrottledError, UserNotFound
from aiograpi.mixins.user import USER_INFO_BY_USERNAME_V2_DOC_ID, USER_INFO_V2_DOC_ID

PROFILE = {
    "id": "123",
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


class ModernPublicProfileRoutingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = Client()
        self.client._users_cache = {}
        self.client._usernames_cache = {}
        self.client._inject_sessionid_for_v2_gql = Mock()
        self.client.user_info_by_username_gql = AsyncMock(side_effect=AssertionError("legacy profile request"))
        self.client.username_from_user_id_gql = AsyncMock(side_effect=AssertionError("unneeded username lookup"))
        self.client.user_info_v1 = AsyncMock(side_effect=ClientError("private unavailable"))
        self.client.user_info_by_username_v1 = AsyncMock(side_effect=ClientError("private unavailable"))
        self.calls = []

        async def query(doc_id, variables):
            self.calls.append((doc_id, variables))
            if doc_id == USER_INFO_BY_USERNAME_V2_DOC_ID:
                return {"xdt_api__v1__fbsearch__non_profiled_serp": {"users": [{"username": "example", "pk": "123"}]}}
            assert doc_id == USER_INFO_V2_DOC_ID
            return {"user": dict(PROFILE)}

        self.client.public_doc_id_graphql_request = query

    async def asyncTearDown(self):
        for session in (self.client.private, self.client.public, self.client.graphql):
            await type(session)._close(session)

    async def test_standard_username_lookup_uses_modern_search_and_profile_then_cache(self):
        user = await self.client.user_info_by_username(" @Example ")
        cached = await self.client.user_info_by_username("example")
        self.assertEqual((user.pk, cached.username), ("123", "example"))
        self.assertEqual([x[0] for x in self.calls], [USER_INFO_BY_USERNAME_V2_DOC_ID, USER_INFO_V2_DOC_ID])
        self.assertEqual(self.calls[0][1], {"hasQuery": True, "query": "example"})
        self.assertEqual(self.calls[1][1]["id"], "123")
        self.assertEqual(self.client._usernames_cache, {"example": "123"})

    async def test_gql_id_lookup_fetches_profile_directly(self):
        user = await self.client.user_info_gql(123)
        self.assertEqual(user.pk, "123")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][0], USER_INFO_V2_DOC_ID)
        self.assertEqual(self.calls[0][1]["id"], "123")

    async def test_authorized_username_lookup_keeps_private_priority(self):
        self.client.authorization_data = {"ds_user_id": "1"}
        from aiograpi.extractors import extract_user_v1

        self.client.user_info_by_username_v1 = AsyncMock(return_value=extract_user_v1(dict(PROFILE, pk="123")))
        user = await self.client.user_info_by_username("example")
        self.assertEqual(user.pk, "123")
        self.assertEqual(self.calls, [])

    async def test_authorized_username_fallback_uses_modern(self):
        self.client.authorization_data = {"ds_user_id": "1"}
        self.client.user_info_by_username_v1 = AsyncMock(side_effect=ClientError("private unavailable"))
        user = await self.client.user_info_by_username("example")
        self.assertEqual(user.pk, "123")
        self.assertEqual([x[0] for x in self.calls], [USER_INFO_BY_USERNAME_V2_DOC_ID, USER_INFO_V2_DOC_ID])

    async def test_authorized_id_fallback_uses_modern(self):
        self.client.authorization_data = {"ds_user_id": "1"}
        self.client.user_info_v1 = AsyncMock(side_effect=ClientError("private unavailable"))
        user = await self.client.user_info("123")
        self.assertEqual(user.pk, "123")
        self.assertEqual([x[0] for x in self.calls], [USER_INFO_V2_DOC_ID])

    async def test_throttled_modern_lookup_does_not_dispatch_legacy(self):
        error = ClientThrottledError("restricted")
        self.client.public_doc_id_graphql_request = AsyncMock(side_effect=error)
        with self.assertRaises(ClientThrottledError) as caught:
            await self.client._user_info_by_username_public("example")
        self.assertIs(caught.exception, error)
        self.client.public_doc_id_graphql_request.assert_awaited_once()
        self.client.user_info_by_username_gql.assert_not_awaited()

    async def test_username_search_requires_exact_match(self):
        self.client.public_doc_id_graphql_request = AsyncMock(
            return_value={
                "xdt_api__v1__fbsearch__non_profiled_serp": {"users": [{"username": "example_other", "pk": "456"}]}
            }
        )
        with self.assertRaises(UserNotFound):
            await self.client._user_info_by_username_public("example")
        self.client.public_doc_id_graphql_request.assert_awaited_once()
        self.client.user_info_by_username_gql.assert_not_awaited()

    async def test_standard_id_lookup_caches_and_returns_independent_copies(self):
        user = await self.client.user_info("123")
        user.full_name = "Edited"
        cached = await self.client.user_info("123")
        self.assertEqual(cached.full_name, "Example")
        self.assertEqual([x[0] for x in self.calls], [USER_INFO_V2_DOC_ID])

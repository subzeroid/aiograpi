import unittest
from unittest.mock import AsyncMock

from aiograpi import Client
from aiograpi.exceptions import ClientGraphqlError


class RelatedProfileSessionTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = Client()

    async def asyncTearDown(self):
        await self.client.public._close()

    def response(self):
        return {
            "status": "ok",
            "data": {
                "user": {
                    "edge_chaining": {
                        "edges": [
                            {
                                "node": {
                                    "id": "2",
                                    "username": "example",
                                    "is_private": False,
                                    "profile_pic_url": "https://example.com/avatar.jpg",
                                }
                            }
                        ]
                    }
                }
            },
        }

    async def check_related_cookie(self, expected):
        def request(*args, **kwargs):
            self.assertEqual(self.client.public.cookies_dict().get("sessionid"), expected)
            return self.response()

        self.client.public_request = AsyncMock(side_effect=request)
        users = await self.client.user_related_profiles_gql("2")
        self.assertEqual([user.username for user in users], ["example"])
        self.client.public_request.assert_awaited_once()

    async def test_first_related_lookup_uses_saved_authorization(self):
        self.client.authorization_data = {"ds_user_id": "1", "sessionid": "saved-session"}
        self.assertIsNone(self.client.public.cookies_dict().get("sessionid"))
        await self.check_related_cookie("saved-session")

    async def test_private_cookie_replaces_stale_public_session(self):
        self.client.private.set_cookies({"sessionid": "current-session"})
        self.client.public.set_cookies({"sessionid": "stale-session"})
        await self.check_related_cookie("current-session")

    async def test_without_private_session_preserves_existing_public_cookie(self):
        self.client.public.set_cookies({"sessionid": "public-session"})
        await self.check_related_cookie("public-session")

    async def test_anonymous_related_lookup_remains_available(self):
        await self.check_related_cookie(None)

    async def test_related_error_is_not_retried_or_replaced(self):
        error = ClientGraphqlError("unavailable")
        self.client.public_request = AsyncMock(side_effect=error)
        with self.assertRaises(ClientGraphqlError) as raised:
            await self.client.user_related_profiles_gql("2")
        self.assertIs(raised.exception, error)
        self.client.public_request.assert_awaited_once()

    async def test_generic_legacy_graphql_remains_anonymous(self):
        self.client.authorization_data = {"ds_user_id": "1", "sessionid": "saved-session"}
        self.client.public_request = AsyncMock(return_value=self.response())
        await self.client.public_graphql_request({"id": "2"}, query_hash="query-placeholder")
        self.assertIsNone(self.client.public.cookies_dict().get("sessionid"))

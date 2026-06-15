import os
import unittest

from aiograpi import Client
from aiograpi import types as ig_types
from aiograpi.extractors import extract_user_short
from tests.live.smoke import _fetch_accounts


async def _client_from_reusable_test_account(account):
    settings = dict(account.get("client_settings") or account.get("settings") or {})
    settings.pop("totp_seed", None)
    client = Client(
        settings=settings,
        proxy=os.getenv("IG_PROXY") or account.get("proxy"),
        override_app_version=True,
    )
    client._user_id = account.get("user_id")
    await client.account_info()
    return client


async def _fresh_reusable_user_clients(test_accounts_url, count=20):
    clients = []
    seen_user_ids = set()
    accounts = await _fetch_accounts(test_accounts_url, count=count)
    for account in accounts:
        try:
            client = await _client_from_reusable_test_account(account)
        except Exception:
            continue
        if client.user_id in seen_user_ids:
            continue
        seen_user_ids.add(client.user_id)
        clients.append(client)
        if len(clients) >= 2:
            return clients
    return clients


class ClientUserFollowActionLiveTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.test_accounts_url = os.getenv("TEST_ACCOUNTS_URL")
        if not self.test_accounts_url:
            self.skipTest("TEST_ACCOUNTS_URL is required for user follow live tests")

    async def test_user_follow_returns_false_for_existing_follow_live(self):
        clients = await _fresh_reusable_user_clients(self.test_accounts_url)
        if len(clients) < 2:
            self.skipTest("At least two reusable TEST_ACCOUNTS_URL sessions are required")

        requester, target = clients[:2]
        target_id = str(target.user_id)
        try:
            try:
                await requester.user_unfollow(target_id)
            except Exception:
                pass

            self.assertTrue(await requester.user_follow(target_id))
            relationship = await requester.user_friendship_v1(target_id)
            self.assertTrue(relationship.following or relationship.outgoing_request)
            self.assertFalse(await requester.user_follow(target_id))
        finally:
            try:
                await requester.user_unfollow(target_id)
            except Exception:
                pass


class ClientPrivateGraphQLV2UserFieldsLiveTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.test_accounts_url = os.getenv("TEST_ACCOUNTS_URL")
        if not self.test_accounts_url:
            self.skipTest("TEST_ACCOUNTS_URL is required for private GraphQL v2 user field live tests")

    async def test_user_followers_private_gql_preserves_v2_user_fields(self):
        clients = await _fresh_reusable_user_clients(self.test_accounts_url, count=10)
        if not clients:
            self.skipTest("At least one reusable TEST_ACCOUNTS_URL session is required")
        cl = clients[0]
        user_id = await cl.user_id_from_username("instagram")
        result = await cl.private_graphql_followers_list(user_id, cl.rank_token, order="date_followed_latest")
        data = result.get("data") or {}
        followers = next(
            (value for key, value in data.items() if "xdt_api__v1__friendships__followers" in key),
            {},
        )
        raw_user = next((user for user in followers.get("users", []) if user.get("friendship_status")), None)
        if raw_user is None:
            self.skipTest("private GraphQL followers payload did not include friendship_status")

        rich_user = extract_user_short(dict(raw_user))

        self.assertIsNotNone(rich_user.latest_reel_media)
        self.assertIsInstance(rich_user.account_badges, list)
        self.assertIsInstance(rich_user.friendship_status, ig_types.RelationshipShort)
        for field in ("profile_pic_id", "fbid_v2", "interop_messaging_user_fbid", "strong_id__"):
            raw_value = raw_user.get(field)
            if raw_value is not None:
                self.assertEqual(getattr(rich_user, field), str(raw_value))

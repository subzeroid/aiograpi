import os
import unittest

from aiograpi import Client
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

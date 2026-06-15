import asyncio
import os
import unittest
from pathlib import Path

from aiograpi import Client
from aiograpi.types import StoryPoll
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


async def _fresh_reusable_story_clients(test_accounts_url, count=10):
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


async def _story_payload_for_viewer(client, user_id, story, attempts=12, delay=5):
    last_item_ids = []
    for attempt in range(attempts):
        if attempt:
            await asyncio.sleep(delay)
        result = await client.private_request(f"feed/user/{user_id}/story/")
        items = (result.get("reel") or {}).get("items") or []
        last_item_ids = [item.get("id") for item in items[:5]]
        for item in items:
            if str(item.get("id")) == str(story.id) or str(item.get("pk")) == str(story.pk):
                return item
    raise RuntimeError(f"Story payload was not visible after {attempts} attempts: {last_item_ids}")


def _first_poll_sticker(item):
    story_polls = item.get("story_polls") or []
    if not story_polls:
        raise RuntimeError("Story payload did not include story_polls")
    return story_polls[0].get("poll_sticker") or story_polls[0]


class ClientStoryPollVoteLiveTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.test_accounts_url = os.getenv("TEST_ACCOUNTS_URL")
        if not self.test_accounts_url:
            self.skipTest("TEST_ACCOUNTS_URL is required for story poll vote live tests")

    async def test_story_poll_vote_live(self):
        timeout = int(os.getenv("AIOGRAPI_STORY_POLL_VOTE_LIVE_TIMEOUT", "240"))
        await asyncio.wait_for(self._test_story_poll_vote_live(), timeout=timeout)

    async def _test_story_poll_vote_live(self):
        clients = await _fresh_reusable_story_clients(self.test_accounts_url)
        if len(clients) < 2:
            self.skipTest("At least two reusable TEST_ACCOUNTS_URL sessions are required")

        author, voter = clients[:2]
        story = None
        try:
            story = await author.photo_upload_to_story(
                Path("examples/background.png"),
                "Story poll vote live test",
                polls=[
                    StoryPoll(
                        x=0.5,
                        y=0.5,
                        width=0.7,
                        height=0.3,
                        question="Poll vote live?",
                        options=["Yes", "No"],
                    )
                ],
            )
            author_item = await _story_payload_for_viewer(author, author.user_id, story)
            author_poll = _first_poll_sticker(author_item)
            poll_id = author_poll.get("poll_id") or author_poll.get("id")
            voter_before = _first_poll_sticker(await _story_payload_for_viewer(voter, author.user_id, story))

            voted = await voter.story_poll_vote(story.id, poll_id, 0)
            voter_after = _first_poll_sticker(await _story_payload_for_viewer(voter, author.user_id, story))

            self.assertTrue(story.id)
            self.assertTrue(poll_id)
            self.assertTrue(voted)
            self.assertIsNone(voter_before.get("viewer_vote"))
            self.assertEqual(voter_after.get("viewer_vote"), 0)
            self.assertGreaterEqual((voter_after.get("tallies") or [])[0]["count"], 1)
        finally:
            if story:
                self.assertTrue(await author.story_delete(story.id))


async def _story_likers_until_contains(client, story_pk, expected_user_id, attempts=12, delay=5):
    last_liker_ids = []
    for attempt in range(attempts):
        if attempt:
            await asyncio.sleep(delay)
        likers = await client.story_likers(story_pk, amount=20)
        last_liker_ids = [str(liker.pk) for liker in likers]
        if str(expected_user_id) in last_liker_ids:
            return likers
    raise RuntimeError(f"Story likers did not include {expected_user_id} after {attempts} attempts: {last_liker_ids}")


class ClientStoryLikersLiveTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.test_accounts_url = os.getenv("TEST_ACCOUNTS_URL")
        if not self.test_accounts_url:
            self.skipTest("TEST_ACCOUNTS_URL is required for story likers live tests")

    async def test_story_likers_live(self):
        timeout = int(os.getenv("AIOGRAPI_STORY_LIKERS_LIVE_TIMEOUT", "240"))
        await asyncio.wait_for(self._test_story_likers_live(), timeout=timeout)

    async def _test_story_likers_live(self):
        clients = await _fresh_reusable_story_clients(self.test_accounts_url)
        if len(clients) < 2:
            self.skipTest("At least two reusable TEST_ACCOUNTS_URL sessions are required")

        author, liker = clients[:2]
        story = None
        try:
            story = await author.photo_upload_to_story(Path("examples/background.png"), "Story likers live test")
            await _story_payload_for_viewer(liker, author.user_id, story)
            liked = await liker.story_like(story.id)
            likers = await _story_likers_until_contains(author, story.pk, liker.user_id)

            self.assertTrue(story.id)
            self.assertTrue(liked)
            self.assertIn(str(liker.user_id), [str(user.pk) for user in likers])
        finally:
            if story:
                self.assertTrue(await author.story_delete(story.id))

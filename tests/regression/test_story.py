import unittest
from unittest.mock import AsyncMock

from aiograpi import Client
from aiograpi.exceptions import ClientNotFoundError, UserNotFound
from aiograpi.extractors import extract_story_v1


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

    async def test_extract_story_v1_reads_poll_stickers(self):
        story = extract_story_v1(
            {
                "pk": "1",
                "id": "1_2",
                "code": "abc",
                "taken_at": 1710000000,
                "media_type": 1,
                "image_versions2": {
                    "candidates": [
                        {
                            "url": "https://example.com/thumbnail.jpg",
                            "width": 720,
                            "height": 1280,
                        }
                    ]
                },
                "user": {
                    "pk": "2",
                    "username": "example",
                    "profile_pic_url": "https://example.com/profile.jpg",
                },
                "story_polls": [
                    {
                        "x": 0.5,
                        "y": 0.5,
                        "z": 0,
                        "width": 0.7,
                        "height": 0.3,
                        "rotation": 0.0,
                        "poll_sticker": {
                            "poll_id": "17895695668004550",
                            "question": "Pick one",
                            "viewer_can_vote": True,
                            "finished": False,
                            "tallies": [
                                {"text": "Yes", "count": 1},
                                {"text": "No", "count": 0},
                            ],
                        },
                    }
                ],
            }
        )

        self.assertEqual(len(story.polls), 1)
        self.assertEqual(story.polls[0].id, "17895695668004550")
        self.assertEqual(story.polls[0].question, "Pick one")
        self.assertEqual(story.polls[0].options, ["Yes", "No"])
        self.assertTrue(story.polls[0].viewer_can_vote)

    async def test_story_poll_vote_posts_vote_to_poll_endpoint(self):
        client = Client()
        client.authorization_data = {"sessionid": "sessionid-value", "ds_user_id": "1"}
        client.private_request = AsyncMock(return_value={"status": "ok"})

        result = await client.story_poll_vote("1234567890_1", "17895695668004550", 1)

        self.assertTrue(result)
        client.private_request.assert_awaited_once()
        endpoint, data = client.private_request.call_args.args
        self.assertEqual(endpoint, "media/1234567890_1/17895695668004550/story_poll_vote/")
        self.assertEqual(data["_uid"], "1")
        self.assertEqual(data["vote"], "1")
        self.assertEqual(data["radio_type"], "wifi-none")

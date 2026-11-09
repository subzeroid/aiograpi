import json
import unittest
from copy import deepcopy
from unittest.mock import AsyncMock, patch

from aiograpi import Client
from aiograpi.exceptions import ClientGraphqlError, ClientNotFoundError, UserNotFound
from aiograpi.extractors import extract_story_v1, extract_story_web
from aiograpi.mixins.graphql import GraphQLRequestMixin
from aiograpi.utils.ids import InstagramIdCodec


def web_story_payload():
    return {
        "pk": 314159265358979,
        "id": "314159265358979_271828182845904",
        "code": "web-story-code",
        "taken_at": 1700000000,
        "media_type": 2,
        "user": {
            "pk": 271828182845904,
            "username": "web-story-user",
            "profile_pic_url": "https://example.com/profile.jpg",
        },
        "video_versions": [
            {"type": 101, "url": "https://example.com/first.mp4"},
            {"type": 102, "url": "https://example.com/second.mp4"},
        ],
        "image_versions2": {
            "candidates": [
                {
                    "url": "https://example.com/thumb.jpg",
                    "width": 720,
                    "height": 1280,
                }
            ]
        },
        "story_locations": None,
        "story_hashtags": None,
        "story_cta": None,
        "sponsor_tags": None,
        "story_feed_media": None,
        "story_link_stickers": None,
    }


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
        client.public_graphql_request = AsyncMock(side_effect=AssertionError("legacy query must not be used"))
        client._fb_dtsg = "token"
        body = {
            "data": {
                "xdt_api__v1__feed__reels_media": {
                    "reels_media": [{"items": [web_story_payload(), web_story_payload()]}]
                }
            }
        }
        client.graphql_request = AsyncMock(return_value=body)

        users = await client.users_stories_gql(["271828182845904"], amount=1)

        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].pk, "271828182845904")
        self.assertEqual(len(users[0].stories), 1)
        self.assertEqual(users[0].stories[0].pk, "314159265358979")
        client.graphql_request.assert_awaited_once_with(
            data={
                "variables": json.dumps(
                    {
                        "reel_ids_arr": ["271828182845904"],
                        "__relay_internal__pv__PolarisCommunityNoteStoriesLabelEnabledrelayprovider": True,
                    }
                ),
                "doc_id": "29184890191114309",
                "fb_dtsg": "token",
                "fb_api_caller_class": "RelayModern",
                "fb_api_req_friendly_name": "PolarisStoriesV3ReelPageStandaloneQuery",
                "server_timestamps": "true",
            }
        )

    async def test_users_stories_gql_validates_modern_response_and_preserves_errors(self):
        client = Client()
        client.public_graphql_request = AsyncMock(side_effect=AssertionError("legacy query must not be used"))
        client._fb_dtsg = "token"
        empty = {"data": {"xdt_api__v1__feed__reels_media": {"reels_media": [{"items": []}]}}}
        client.graphql_request = AsyncMock(return_value=empty)
        self.assertEqual(await client.users_stories_gql(["123"]), [])

        bodies = [
            {},
            {"data": {}},
            {"data": {"xdt_api__v1__feed__reels_media": None}},
            {"data": {"xdt_api__v1__feed__reels_media": {"reels_media": None}}},
            {"data": {"xdt_api__v1__feed__reels_media": {"reels_media": [{}]}}},
        ]
        for body in bodies:
            with self.subTest(body=body):
                client.graphql_request = AsyncMock(return_value=body)
                with self.assertRaises(ClientGraphqlError):
                    await client.users_stories_gql(["123"])

        error = ClientGraphqlError("request failed")
        client.graphql_request = AsyncMock(side_effect=error)
        with self.assertRaises(ClientGraphqlError) as caught:
            await client.users_stories_gql(["123"])
        self.assertIs(caught.exception, error)

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

    async def test_extract_story_v1_normalizes_sponsor_tag_friendship_status(self):
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
                "sponsor_tags": [
                    {
                        "sponsor": {
                            "pk": "3",
                            "username": "sponsor",
                            "profile_pic_url": "https://example.com/sponsor.jpg",
                            "friendship_status": {"following": False},
                        }
                    }
                ],
            }
        )

        self.assertEqual(story.sponsor_tags[0].pk, "3")
        self.assertEqual(story.sponsor_tags[0].friendship_status.user_id, "3")
        self.assertFalse(story.sponsor_tags[0].friendship_status.following)
        self.assertFalse(story.sponsor_tags[0].friendship_status.incoming_request)

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

    async def test_story_likers_chunk_filters_liked_viewers_and_deduplicates_users(self):
        client = Client()
        client.private_request = AsyncMock(
            side_effect=[
                {
                    "viewers": [
                        {
                            "has_liked": True,
                            "user": {
                                "pk": "10",
                                "username": "liked_1",
                                "profile_pic_url": "https://example.com/liked_1.jpg",
                            },
                        },
                        {
                            "has_liked": False,
                            "user": {
                                "pk": "20",
                                "username": "viewer_only",
                                "profile_pic_url": "https://example.com/viewer_only.jpg",
                            },
                        },
                    ],
                    "next_max_id": "page-2",
                },
                {
                    "viewers": [
                        {
                            "has_liked": True,
                            "user": {
                                "pk": "10",
                                "username": "liked_1_duplicate",
                                "profile_pic_url": "https://example.com/liked_1_duplicate.jpg",
                            },
                        },
                        {
                            "has_liked": True,
                            "user": {
                                "pk": "30",
                                "username": "liked_2",
                                "profile_pic_url": "https://example.com/liked_2.jpg",
                            },
                        },
                    ],
                },
            ]
        )

        likers, max_id = await client.story_likers_chunk("1234567890_1")

        self.assertEqual([liker.pk for liker in likers], ["10", "30"])
        self.assertEqual([liker.username for liker in likers], ["liked_1", "liked_2"])
        self.assertIsNone(max_id)
        self.assertEqual(client.private_request.call_args_list[0].args[0], "media/1234567890/list_reel_media_viewer/")
        self.assertIn("supported_capabilities_new", client.private_request.call_args_list[0].kwargs["params"])
        self.assertEqual(client.private_request.call_args_list[1].kwargs["params"]["max_id"], "page-2")

    async def test_story_likers_limits_amount(self):
        client = Client()
        client.private_request = AsyncMock(
            return_value={
                "viewers": [
                    {
                        "has_liked": True,
                        "user": {
                            "pk": "10",
                            "username": "liked_1",
                            "profile_pic_url": "https://example.com/liked_1.jpg",
                        },
                    },
                    {
                        "has_liked": True,
                        "user": {
                            "pk": "20",
                            "username": "liked_2",
                            "profile_pic_url": "https://example.com/liked_2.jpg",
                        },
                    },
                ],
            }
        )

        likers = await client.story_likers("1234567890_1", amount=1)

        self.assertEqual([liker.pk for liker in likers], ["10"])

    async def test_story_likers_handles_viewer_payload_without_viewers(self):
        client = Client()
        client.private_request = AsyncMock(return_value={"status": "ok", "user_count": 0, "total_viewer_count": 0})

        likers = await client.story_likers("1234567890_1")

        self.assertEqual(likers, [])

    async def test_story_like_marks_story_seen_before_liking(self):
        client = Client()
        client.authorization_data = {"sessionid": "sessionid-value", "ds_user_id": "1"}
        client.story_seen = AsyncMock(return_value=True)
        client.private_request = AsyncMock(return_value={"status": "ok"})

        result = await client.story_like("1234567890_1")

        self.assertTrue(result)
        client.story_seen.assert_awaited_once_with(["1234567890"])
        client.private_request.assert_awaited_once()
        self.assertEqual(client.private_request.call_args.args[0], "story_interactions/send_story_like")

    async def test_story_like_can_skip_mark_seen(self):
        client = Client()
        client.authorization_data = {"sessionid": "sessionid-value", "ds_user_id": "1"}
        client.story_seen = AsyncMock(return_value=True)
        client.private_request = AsyncMock(return_value={"status": "ok"})

        result = await client.story_like("1234567890_1", mark_seen=False)

        self.assertTrue(result)
        client.story_seen.assert_not_awaited()

    async def test_story_unlike_does_not_mark_story_seen(self):
        client = Client()
        client.authorization_data = {"sessionid": "sessionid-value", "ds_user_id": "1"}
        client.story_seen = AsyncMock(return_value=True)
        client.private_request = AsyncMock(return_value={"status": "ok"})

        result = await client.story_unlike("1234567890_1")

        self.assertTrue(result)
        client.story_seen.assert_not_awaited()
        self.assertEqual(client.private_request.call_args.args[0], "story_interactions/unsend_story_like")

    async def test_extract_story_web_normalizes_capture_shape(self):
        payload = web_story_payload()
        original = deepcopy(payload)

        story = extract_story_web(payload)

        self.assertEqual(payload, original)
        self.assertEqual(story.pk, str(payload["pk"]))
        self.assertEqual(story.id, payload["id"])
        self.assertEqual(int(story.taken_at.timestamp()), payload["taken_at"])
        self.assertEqual(story.media_type, payload["media_type"])
        self.assertEqual(story.user.pk, str(payload["user"]["pk"]))
        self.assertEqual(str(story.video_url), "https://example.com/first.mp4")
        self.assertEqual(str(story.thumbnail_url), "https://example.com/thumb.jpg")
        for field in ("locations", "hashtags", "links", "sponsor_tags", "medias", "stickers"):
            self.assertEqual(getattr(story, field), [])

    async def test_extract_story_web_normalizes_feed_media(self):
        payload = web_story_payload()
        media_pk = payload["pk"]
        payload["story_feed_media"] = [
            {
                "id": f"{media_pk}_1",
                "media_code": InstagramIdCodec.encode(media_pk),
                "product_type": "feed",
                "x": 0.1,
                "y": 0.2,
                "width": 0.3,
                "height": 0.4,
                "rotation": 0,
            },
            {
                "media_id": "123",
                "product_type": "feed",
                "x": 0.1,
                "y": 0.2,
                "width": 0.3,
                "height": 0.4,
                "rotation": 0,
            },
        ]

        story = extract_story_web(payload)

        self.assertEqual([media.media_pk for media in story.medias], [media_pk, 123])

    async def test_extract_story_web_requires_identifiers(self):
        for kind in ("story", "user"):
            payload = web_story_payload()
            if kind == "story":
                payload.pop("pk")
            else:
                payload["user"].pop("pk")
                payload["user"].pop("id", None)
            with self.subTest(kind=kind):
                with self.assertRaises(KeyError):
                    extract_story_web(payload)

    async def test_graphql_fetch_fb_dtsg_uses_instagram_homepage(self):
        client = Client()
        response = AsyncMock()
        response.content = b'<html><script id="__eqmc">{"f":"synthetic-dtsg"}</script></html>'
        with (
            patch.object(client, "inject_sessionid_to_public") as inject,
            patch.object(client.graphql, "get", new=AsyncMock(return_value=response)) as get,
        ):
            self.assertEqual(await GraphQLRequestMixin.fetch_fb_dtsg(client), "synthetic-dtsg")
        get.assert_awaited_once_with("https://www.instagram.com/")
        inject.assert_called_once_with()

    async def test_user_stories_web_uses_modern_query_and_typed_response(self):
        client = Client()
        client._fb_dtsg = "token"
        body = {
            "data": {
                "xdt_api__v1__feed__reels_media": {
                    "reels_media": [{"items": [web_story_payload(), web_story_payload()]}]
                }
            }
        }
        client.graphql_request = AsyncMock(return_value=body)

        stories = await client.user_stories_web("271828182845904", amount=1)

        self.assertEqual(len(stories), 1)
        self.assertEqual(stories[0].pk, "314159265358979")
        client.graphql_request.assert_awaited_once_with(
            data={
                "variables": json.dumps(
                    {
                        "reel_ids_arr": ["271828182845904"],
                        "__relay_internal__pv__PolarisCommunityNoteStoriesLabelEnabledrelayprovider": True,
                    }
                ),
                "doc_id": "29184890191114309",
                "fb_dtsg": "token",
                "fb_api_caller_class": "RelayModern",
                "fb_api_req_friendly_name": "PolarisStoriesV3ReelPageStandaloneQuery",
                "server_timestamps": "true",
            }
        )

    async def test_user_stories_web_empty_and_malformed_roots(self):
        client = Client()
        client._fb_dtsg = "token"
        empty = {"data": {"xdt_api__v1__feed__reels_media": {"reels_media": []}}}
        client.graphql_request = AsyncMock(return_value=empty)
        self.assertEqual(await client.user_stories_web("271828182845904"), [])

        bodies = [
            {"data": {}},
            {"data": {"xdt_api__v1__feed__reels_media": None}},
            {"data": {"xdt_api__v1__feed__reels_media": {"reels_media": None}}},
            {"data": {"xdt_api__v1__feed__reels_media": {"reels_media": [{}]}}},
        ]
        for body in bodies:
            with self.subTest(body=body):
                client.graphql_request = AsyncMock(return_value=body)
                with self.assertRaises(ClientGraphqlError):
                    await client.user_stories_web("271828182845904")

    async def test_extract_story_web_skips_empty_dimensionless_urls(self):
        payload = web_story_payload()
        payload["video_versions"][0]["url"] = ""

        story = extract_story_web(payload)

        self.assertEqual(str(story.video_url), "https://example.com/second.mp4")

    async def test_extract_story_web_keeps_dimensioned_video_selection(self):
        payload = web_story_payload()
        payload["video_versions"] = [
            {"url": "https://example.com/small.mp4", "width": 320, "height": 480},
            {"url": "https://example.com/large.mp4", "width": 720, "height": 1280},
        ]

        story = extract_story_web(payload)

        self.assertEqual(str(story.video_url), "https://example.com/large.mp4")

    async def test_user_stories_web_preserves_request_errors_and_empty_items(self):
        client = Client()
        client._fb_dtsg = "token"
        error = ClientGraphqlError("request failed")
        client.graphql_request = AsyncMock(side_effect=error)
        with self.assertRaises(ClientGraphqlError) as caught:
            await client.user_stories_web("271828182845904")
        self.assertIs(caught.exception, error)

        empty = {"data": {"xdt_api__v1__feed__reels_media": {"reels_media": [{"items": []}]}}}
        client.graphql_request = AsyncMock(return_value=empty)
        self.assertEqual(await client.user_stories_web("271828182845904"), [])

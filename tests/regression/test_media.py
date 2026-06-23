import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock

from aiograpi import Client
from aiograpi.extractors import extract_media_gql, extract_media_v1
from aiograpi.types import StoryMedia, UserShort


class MediaClipsMetadataRegressionTestCase(unittest.TestCase):
    def _media_payload(self):
        return {
            "pk": "1",
            "id": "1_2",
            "code": "abc",
            "taken_at": 1710000000,
            "media_type": 2,
            "product_type": "clips",
            "usertags": None,
            "carousel_media": None,
            "user": {
                "pk": "2",
                "username": "example",
                "profile_pic_url": "https://example.com/profile.jpg",
            },
            "image_versions2": {
                "candidates": [{"url": "https://example.com/x.jpg", "width": 100, "height": 100}],
            },
        }

    def _clips_metadata_payload(self, **overrides):
        payload = {
            "clips_creation_entry_point": "clips",
            "achievements_info": {"num_earned_achievements": None, "show_achievements": False},
            "additional_audio_info": {
                "additional_audio_username": None,
                "audio_reattribution_info": {"should_allow_restore": False},
            },
            "audio_ranking_info": {"best_audio_cluster_id": ""},
            "audio_type": "original_sounds",
            "branded_content_tag_info": {"can_add_tag": True},
            "content_appreciation_info": {"enabled": False},
            "music_canonical_id": "",
        }
        payload.update(overrides)
        return payload

    def test_extract_media_v1_does_not_default_missing_clips_shared_to_fb_to_false(self):
        payload = self._media_payload()
        payload["clips_metadata"] = self._clips_metadata_payload()

        media = extract_media_v1(payload)

        self.assertIsNone(media.clips_metadata.is_shared_to_fb)
        self.assertIsNone(media.model_dump()["clips_metadata"]["is_shared_to_fb"])

    def test_extract_media_v1_preserves_clips_shared_to_fb_when_present(self):
        for value in (False, True):
            with self.subTest(value=value):
                payload = self._media_payload()
                payload["clips_metadata"] = self._clips_metadata_payload(is_shared_to_fb=value)

                media = extract_media_v1(payload)

                self.assertIs(media.clips_metadata.is_shared_to_fb, value)
                self.assertIs(media.model_dump()["clips_metadata"]["is_shared_to_fb"], value)

    def test_extract_media_v1_normalizes_video_counts(self):
        payload = self._media_payload()
        payload.update(
            {
                "video_view_count": 1234,
                "video_play_count": 5678,
            }
        )

        media = extract_media_v1(payload)

        self.assertEqual(media.view_count, 1234)
        self.assertEqual(media.play_count, 5678)

    def test_extract_media_v1_normalizes_sponsor_tag_friendship_status(self):
        payload = self._media_payload()
        payload["sponsor_tags"] = [
            {
                "sponsor": {
                    "pk": "3",
                    "username": "sponsor",
                    "profile_pic_url": "https://example.com/sponsor.jpg",
                    "friendship_status": {"following": False},
                }
            }
        ]

        media = extract_media_v1(payload)

        self.assertEqual(media.sponsor_tags[0].pk, "3")
        self.assertEqual(media.sponsor_tags[0].friendship_status.user_id, "3")
        self.assertFalse(media.sponsor_tags[0].friendship_status.following)
        self.assertFalse(media.sponsor_tags[0].friendship_status.incoming_request)

    def test_extract_media_v1_preserves_coauthor_producers(self):
        payload = self._media_payload()
        payload["coauthor_producers"] = [
            {
                "id": "100",
                "username": "collab_user",
                "full_name": "Collab User",
                "profile_pic_url": "https://example.com/collab.jpg",
                "is_private": False,
                "is_verified": True,
            }
        ]

        media = extract_media_v1(payload)

        self.assertEqual(len(media.coauthor_producers), 1)
        coauthor = media.coauthor_producers[0]
        self.assertIsInstance(coauthor, UserShort)
        self.assertEqual(coauthor.pk, "100")
        self.assertEqual(coauthor.username, "collab_user")
        self.assertTrue(coauthor.is_verified)

    def test_extract_media_v1_preserves_extended_media_fields(self):
        payload = self._media_payload()
        payload.update(
            {
                "caption_is_edited": True,
                "dimensions": {"height": 1916, "width": 1080},
                "has_audio": True,
                "like_and_view_counts_disabled": True,
                "viewer_can_reshare": True,
                "viewer_has_saved": True,
                "is_paid_partnership": True,
                "is_affiliate": True,
                "dash_info": {
                    "is_dash_eligible": False,
                    "video_dash_manifest": None,
                    "number_of_qualities": 0,
                },
                "clips_music_attribution_info": {
                    "artist_name": "example",
                    "song_name": "Original audio",
                    "uses_original_audio": True,
                    "should_mute_audio": False,
                    "should_mute_audio_reason": "",
                    "audio_id": "1192260532058807",
                },
            }
        )

        media = extract_media_v1(payload)

        self.assertTrue(media.caption_is_edited)
        self.assertEqual(media.dimensions.height, 1916)
        self.assertEqual(media.dimensions.width, 1080)
        self.assertTrue(media.has_audio)
        self.assertTrue(media.like_and_view_counts_disabled)
        self.assertTrue(media.viewer_can_reshare)
        self.assertTrue(media.viewer_has_saved)
        self.assertTrue(media.is_paid_partnership)
        self.assertTrue(media.is_affiliate)
        self.assertFalse(media.dash_info.is_dash_eligible)
        self.assertEqual(media.dash_info.number_of_qualities, 0)
        self.assertEqual(media.clips_music_attribution_info.artist_name, "example")
        self.assertTrue(media.clips_music_attribution_info.uses_original_audio)

    def test_extract_media_gql_normalizes_video_counts(self):
        payload = {
            "__typename": "GraphVideo",
            "id": "1",
            "shortcode": "abc",
            "taken_at_timestamp": 1710000000,
            "owner": {
                "id": "2",
                "username": "example",
                "profile_pic_url": "https://example.com/profile.jpg",
            },
            "display_resources": [],
            "edge_media_to_comment": {"count": 0},
            "edge_media_preview_like": {"count": 0},
            "edge_media_to_caption": {"edges": []},
            "edge_media_to_tagged_user": {"edges": []},
            "edge_sidecar_to_children": {"edges": []},
            "edge_media_to_sponsor_user": {"edges": []},
            "video_view_count": 1234,
            "video_play_count": 5678,
        }

        media = extract_media_gql(payload)

        self.assertEqual(media.view_count, 1234)
        self.assertEqual(media.play_count, 5678)

    def test_extract_media_gql_preserves_extended_media_fields(self):
        payload = {
            "__typename": "GraphVideo",
            "id": "1",
            "shortcode": "abc",
            "taken_at_timestamp": 1710000000,
            "owner": {
                "id": "2",
                "username": "example",
                "profile_pic_url": "https://example.com/profile.jpg",
            },
            "display_resources": [],
            "edge_media_to_comment": {"count": 0},
            "edge_media_preview_like": {"count": 0},
            "edge_media_to_caption": {"edges": []},
            "edge_media_to_tagged_user": {"edges": []},
            "edge_sidecar_to_children": {"edges": []},
            "edge_media_to_sponsor_user": {"edges": []},
            "caption_is_edited": True,
            "dimensions": {"height": 1916, "width": 1080},
            "has_audio": True,
            "like_and_view_counts_disabled": True,
            "viewer_can_reshare": True,
            "viewer_has_saved": True,
            "is_paid_partnership": True,
            "is_affiliate": True,
            "dash_info": {
                "is_dash_eligible": False,
                "video_dash_manifest": None,
                "number_of_qualities": 0,
            },
            "clips_music_attribution_info": {
                "artist_name": "example",
                "song_name": "Original audio",
                "uses_original_audio": True,
                "should_mute_audio": False,
                "should_mute_audio_reason": "",
                "audio_id": "1192260532058807",
            },
        }

        media = extract_media_gql(payload)

        self.assertTrue(media.caption_is_edited)
        self.assertEqual(media.dimensions.height, 1916)
        self.assertEqual(media.dimensions.width, 1080)
        self.assertTrue(media.has_audio)
        self.assertTrue(media.like_and_view_counts_disabled)
        self.assertTrue(media.viewer_can_reshare)
        self.assertTrue(media.viewer_has_saved)
        self.assertTrue(media.is_paid_partnership)
        self.assertTrue(media.is_affiliate)
        self.assertFalse(media.dash_info.is_dash_eligible)
        self.assertEqual(media.dash_info.number_of_qualities, 0)
        self.assertEqual(media.clips_music_attribution_info.artist_name, "example")
        self.assertTrue(media.clips_music_attribution_info.uses_original_audio)

    def test_extract_media_gql_preserves_inline_comment_preview(self):
        def comment_node(comment_id, text, user_id, username):
            return {
                "id": comment_id,
                "text": text,
                "created_at": 1710000000,
                "did_report_as_spam": False,
                "owner": {
                    "id": user_id,
                    "username": username,
                    "profile_pic_url": f"https://example.com/{username}.jpg",
                    "is_verified": False,
                },
                "viewer_has_liked": False,
                "edge_liked_by": {"count": 2},
                "is_restricted_pending": False,
                "edge_threaded_comments": {"count": 0, "page_info": {"has_next_page": False}, "edges": []},
            }

        parent = comment_node("c1", "parent", "10", "parent_user")
        reply = comment_node("r1", "reply", "11", "reply_user")
        parent["edge_threaded_comments"] = {
            "count": 1,
            "page_info": {"has_next_page": False, "end_cursor": None},
            "edges": [{"node": reply}],
        }
        hoisted = comment_node("h1", "hoisted", "12", "hoisted_user")
        payload = {
            "__typename": "GraphImage",
            "id": "1",
            "shortcode": "abc",
            "taken_at_timestamp": 1710000000,
            "owner": {
                "id": "2",
                "username": "example",
                "profile_pic_url": "https://example.com/profile.jpg",
            },
            "display_resources": [],
            "edge_media_to_comment": {"count": 1},
            "edge_media_preview_like": {"count": 0},
            "edge_media_to_caption": {"edges": []},
            "edge_media_to_tagged_user": {"edges": []},
            "edge_sidecar_to_children": {"edges": []},
            "edge_media_to_sponsor_user": {"edges": []},
            "edge_media_to_parent_comment": {
                "count": 1,
                "page_info": {"has_next_page": True, "end_cursor": "cursor"},
                "edges": [{"node": parent}],
            },
            "edge_media_to_hoisted_comment": {"edges": [{"node": hoisted}]},
        }

        media = extract_media_gql(payload)

        self.assertEqual(media.comments_preview.count, 1)
        self.assertTrue(media.comments_preview.has_next_page)
        self.assertEqual(media.comments_preview.end_cursor, "cursor")
        comment = media.comments_preview.comments[0]
        self.assertEqual(comment.pk, "c1")
        self.assertEqual(comment.text, "parent")
        self.assertEqual(comment.user.pk, "10")
        self.assertEqual(comment.user.username, "parent_user")
        self.assertEqual(comment.like_count, 2)
        self.assertFalse(comment.has_liked)
        self.assertFalse(comment.is_restricted_pending)
        self.assertEqual(comment.replies_count, 1)
        self.assertEqual(comment.replies[0].pk, "r1")
        self.assertEqual(comment.replies[0].replied_to_comment_id, "c1")
        self.assertEqual(media.hoisted_comments[0].pk, "h1")
        self.assertEqual(media.hoisted_comments[0].text, "hoisted")


class MediaActionPayloadRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    def _build_logged_in_client(self):
        client = Client()
        client._user_id = "1"
        client.uuid = "uuid"
        client.android_device_id = "android-device"
        return client

    async def test_media_like_preserves_full_media_id_and_posts_current_action_context(self):
        client = self._build_logged_in_client()
        client.private_request = AsyncMock(return_value={"status": "ok"})

        self.assertTrue(await client.media_like("123_456"))

        endpoint, data = client.private_request.call_args.args
        self.assertEqual(endpoint, "media/123_456/like/")
        self.assertEqual(data["media_id"], "123_456")
        self.assertEqual(data["_uid"], "1")
        self.assertEqual(data["device_id"], "android-device")
        self.assertEqual(data["radio_type"], "wifi-none")
        self.assertEqual(data["delivery_class"], "organic")
        self.assertEqual(data["tap_source"], "button")
        self.assertEqual(data["is_2m_enabled"], "false")
        self.assertEqual(data["is_from_swipe"], "false")
        self.assertEqual(data["floating_context_items"], "[]")
        self.assertEqual(data["media_pct_watched"], "0")
        self.assertEqual(data["container_module"], "feed_timeline")
        self.assertIn(data["feed_position"], {str(i) for i in range(7)})

    async def test_media_note_create_posts_current_v2_payload(self):
        client = self._build_logged_in_client()
        expected = {
            "id": "17881913307564398",
            "media_id": "3884795301060104481",
            "text": "seen this",
            "status": "ok",
        }
        client.private_request = AsyncMock(return_value=expected)

        result = await client.media_note_create(
            "3884795301060104481_52448022913",
            text="seen this",
            extra_data={"ranking_info_token": "rank-token"},
        )

        self.assertEqual(result, expected)
        client.private_request.assert_awaited_once_with(
            "media/create_note/v2/",
            data={
                "inventory_source": "recommended_clips_chaining_model",
                "media_client_position": "0",
                "media_id": "3884795301060104481_52448022913",
                "note_style": "13",
                "carousel_index": "-1",
                "text": "seen this",
                "_uuid": "uuid",
                "audience": "7",
                "event_source": "ufi",
                "container_module": "clips_viewer_clips_tab",
                "ranking_info_token": "rank-token",
            },
            with_signature=False,
        )

    async def test_media_note_delete_posts_current_v2_payload(self):
        client = self._build_logged_in_client()
        client.private_request = AsyncMock(return_value={"status": "ok"})

        result = await client.media_note_delete("17881913307564398", extra_data={"ranking_info_token": "rank-token"})

        self.assertTrue(result)
        client.private_request.assert_awaited_once_with(
            "media/delete_note/",
            data={
                "inventory_source": "recommended_clips_chaining_model",
                "carousel_index": "-1",
                "_uuid": "uuid",
                "event_source": "ufi",
                "container_module": "clips_viewer_clips_tab",
                "note_id": "17881913307564398",
                "ranking_info_token": "rank-token",
            },
            with_signature=False,
        )

    async def test_media_share_to_story_uses_existing_media_as_story_sticker(self):
        client = self._build_logged_in_client()
        background = Path("background.jpg")
        story = object()
        client.photo_upload_to_story = AsyncMock(return_value=story)

        result = await client.media_share_to_story(
            "123_456",
            background=background,
            caption="caption",
            x=0.4,
            y=0.45,
            width=0.7,
            height=0.55,
        )

        self.assertIs(result, story)
        client.photo_upload_to_story.assert_awaited_once()
        args, kwargs = client.photo_upload_to_story.call_args
        self.assertEqual(args[:2], (background, "caption"))
        self.assertEqual(len(kwargs["medias"]), 1)
        media_sticker = kwargs["medias"][0]
        self.assertIsInstance(media_sticker, StoryMedia)
        self.assertEqual(media_sticker.media_pk, 123)
        self.assertEqual(media_sticker.user_id, 456)
        self.assertEqual(media_sticker.x, 0.4)
        self.assertEqual(media_sticker.y, 0.45)
        self.assertEqual(media_sticker.width, 0.7)
        self.assertEqual(media_sticker.height, 0.55)

    async def test_media_info_uses_private_first_when_authorized(self):
        client = self._build_logged_in_client()
        client.authorization_data = {"sessionid": "sessionid-value", "ds_user_id": "1"}
        client._medias_cache = {}
        private_media = Mock(pk="123")
        client.media_info_v1 = AsyncMock(return_value=private_media)
        client.media_info_gql = AsyncMock(
            side_effect=AssertionError("authorized media lookup should use private first")
        )

        media = await client.media_info("123", use_cache=False)

        self.assertEqual(media.pk, "123")
        client.media_info_v1.assert_awaited_once_with("123")
        client.media_info_gql.assert_not_awaited()

    async def test_user_medias_uses_private_first_when_authorized(self):
        client = self._build_logged_in_client()
        client.authorization_data = {"sessionid": "sessionid-value", "ds_user_id": "1"}
        client.user_medias_v1 = AsyncMock(return_value=["private"])
        client.user_medias_gql = AsyncMock(
            side_effect=AssertionError("authorized user media lookup should use private first")
        )

        medias = await client.user_medias("123", amount=1)

        self.assertEqual(medias, ["private"])
        client.user_medias_v1.assert_awaited_once_with(123, 1)
        client.user_medias_gql.assert_not_awaited()

    async def test_user_medias_paginated_uses_private_first_when_authorized(self):
        client = self._build_logged_in_client()
        client.authorization_data = {"sessionid": "sessionid-value", "ds_user_id": "1"}
        client.user_medias_paginated_v1 = AsyncMock(return_value=(["private"], "next"))
        client.user_medias_paginated_gql = AsyncMock(
            side_effect=AssertionError("authorized paginated user media lookup should use private first")
        )

        medias, cursor = await client.user_medias_paginated("123", amount=1, end_cursor="")

        self.assertEqual(medias, ["private"])
        self.assertEqual(cursor, "next")
        client.user_medias_paginated_v1.assert_awaited_once_with("123", 1, end_cursor="")
        client.user_medias_paginated_gql.assert_not_awaited()

    async def test_iter_user_medias_streams_paginated_pages_and_respects_amount(self):
        client = self._build_logged_in_client()
        medias = [Mock(pk=str(i)) for i in range(1, 5)]
        client.user_medias_paginated = AsyncMock(side_effect=[(medias[:2], "cursor-1"), (medias[2:], "cursor-2")])

        result = []
        async for media in client.iter_user_medias("456", amount=3, page_size=2):
            result.append(media)

        self.assertEqual([media.pk for media in result], ["1", "2", "3"])
        client.user_medias_paginated.assert_has_awaits(
            [
                unittest.mock.call("456", amount=2, end_cursor=""),
                unittest.mock.call("456", amount=1, end_cursor="cursor-1"),
            ]
        )
        self.assertEqual(client.user_medias_paginated.await_count, 2)

    async def test_usertag_medias_uses_private_first_when_authorized(self):
        client = self._build_logged_in_client()
        client.authorization_data = {"sessionid": "sessionid-value", "ds_user_id": "1"}
        client.usertag_medias_v1 = AsyncMock(return_value=["private"])
        client.usertag_medias_gql = AsyncMock(
            side_effect=AssertionError("authorized usertag media lookup should use private first")
        )

        medias = await client.usertag_medias("123", amount=1)

        self.assertEqual(medias, ["private"])
        client.usertag_medias_v1.assert_awaited_once_with(123, 1)
        client.usertag_medias_gql.assert_not_awaited()

    async def test_usertag_medias_paginated_uses_private_first_when_authorized(self):
        client = self._build_logged_in_client()
        client.authorization_data = {"sessionid": "sessionid-value", "ds_user_id": "1"}
        client.usertag_medias_paginated_v1 = AsyncMock(return_value=(["private"], "next"))
        client.usertag_medias_paginated_gql = AsyncMock(
            side_effect=AssertionError("authorized paginated usertag media lookup should use private first")
        )

        medias, cursor = await client.usertag_medias_paginated("123", amount=1, end_cursor="")

        self.assertEqual(medias, ["private"])
        self.assertEqual(cursor, "next")
        client.usertag_medias_paginated_v1.assert_awaited_once_with(123, 1, end_cursor="")
        client.usertag_medias_paginated_gql.assert_not_awaited()

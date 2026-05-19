import unittest
from unittest.mock import AsyncMock

from aiograpi import Client


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

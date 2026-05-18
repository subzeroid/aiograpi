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

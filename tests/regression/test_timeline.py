import json
import unittest
from unittest.mock import AsyncMock

from aiograpi import Client


class TimelineRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_friends_reels_uses_social_discover_endpoint(self):
        client = Client()
        client.private_request = AsyncMock(
            return_value={
                "items": [],
                "paging_info": {"more_available": False},
            }
        )

        result = await client.friends_reels(amount=1)

        assert result == []
        client.private_request.assert_awaited_once_with(
            "clips/discover/social/",
            data=" ",
            params={"max_id": ""},
        )

    async def test_get_timeline_feed_sends_seen_posts_when_paginating(self):
        client = Client()
        client.private_request = AsyncMock(
            side_effect=[
                {
                    "feed_items": [
                        {"media_or_ad": {"id": "111_1"}},
                        {"media_or_ad": {"pk": "222", "user": {"pk": "1"}}},
                    ],
                    "next_max_id": "next-page",
                },
                {"feed_items": []},
            ]
        )

        await client.get_timeline_feed("cold_start_fetch")
        await client.get_timeline_feed("pull_to_refresh", max_id="next-page")

        first_data = json.loads(client.private_request.call_args_list[0].args[1])
        second_data = json.loads(client.private_request.call_args_list[1].args[1])
        self.assertEqual(first_data["feed_view_info"], "[]")
        self.assertNotIn("seen_posts", first_data)
        self.assertEqual(second_data["reason"], "pagination")
        self.assertEqual(second_data["max_id"], "next-page")
        self.assertEqual(second_data["seen_posts"], "111_1,222_1")
        feed_view_info = json.loads(second_data["feed_view_info"])
        self.assertEqual([item["media_id"] for item in feed_view_info], ["111_1", "222_1"])

    async def test_get_timeline_feed_sends_current_app_request_metadata(self):
        client = Client()
        client.private_request = AsyncMock(return_value={"feed_items": []})

        with unittest.mock.patch("aiograpi.mixins.auth.time.time", return_value=1778379170.083):
            await client.get_timeline_feed("cold_start_fetch")

        data = json.loads(client.private_request.call_args.args[1])
        self.assertEqual(data["app_start_time"], "1778379170083")
        self.assertEqual(data["client_recorded_request_time_ms"], "1778379170083")
        self.assertEqual(data["client_seen_store_media_list"], "")
        self.assertEqual(data["client_view_state_media_list"], "[]")
        self.assertEqual(data["device_timezone_name"], "GMT")
        self.assertEqual(data["feed_reshare_info"], "")
        self.assertEqual(data["include_attribution_ui_data"], "true")
        self.assertEqual(data["push_disabled"], "true")
        self.assertEqual(data["request_build_time"], "1778379170083")
        session_level_signals = json.loads(data["session_level_signals"])
        self.assertEqual(session_level_signals["app_entry"], "normal")
        self.assertEqual(session_level_signals["video_play_count"], 0)

    async def test_get_timeline_feed_sends_current_app_pagination_metadata(self):
        client = Client()
        client.private_request = AsyncMock(
            side_effect=[
                {"feed_items": [{"media_or_ad": {"id": "111_1"}}], "next_max_id": "next-page"},
                {"feed_items": []},
            ]
        )

        await client.get_timeline_feed("cold_start_fetch")
        await client.get_timeline_feed(max_id="next-page")

        data = json.loads(client.private_request.call_args_list[1].args[1])
        self.assertEqual(data["organic_realtime_information"], "[]")
        self.assertEqual(data["pagination_source"], "feed_recs")
        self.assertEqual(data["triggered_by_visible_spinner"], "false")

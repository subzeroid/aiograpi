import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from aiograpi import Client


class TrackMixinRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_music_trending_posts_product_payload(self):
        client = Client()
        client.uuid = "uuid-1"
        client.private_request = AsyncMock(return_value={"items": [], "status": "ok"})

        result = await client.music_trending(product="feed_post")

        self.assertEqual(result, {"items": [], "status": "ok"})
        client.private_request.assert_awaited_once_with(
            "music/trending/",
            data={"product": "feed_post", "_uuid": "uuid-1"},
            with_signature=False,
        )

    async def test_music_top_trends_posts_page_size(self):
        client = Client()
        client.uuid = "uuid-1"
        client.private_request = AsyncMock(return_value={"items": [], "status": "ok"})

        result = await client.music_top_trends(page_size=15)

        self.assertEqual(result, {"items": [], "status": "ok"})
        client.private_request.assert_awaited_once_with(
            "music/top_trends/",
            data={"product": "music_in_feed", "_uuid": "uuid-1", "page_size": "15"},
            with_signature=False,
        )

    async def test_music_search_v2_posts_current_search_payload(self):
        client = Client()
        client.uuid = "uuid-1"
        client.generate_uuid = Mock(side_effect=["search-session", "browse-session"])
        client.private_request = AsyncMock(return_value={"items": [], "status": "ok"})

        result = await client.music_search_v2("drake")

        self.assertEqual(result, {"items": [], "status": "ok"})
        client.private_request.assert_awaited_once_with(
            "music/search_v2/",
            data={
                "from_typeahead": "false",
                "search_session_id": "search-session",
                "product": "music_in_feed",
                "q": "drake",
                "_uuid": "uuid-1",
                "browse_session_id": "browse-session",
            },
            with_signature=False,
        )

    async def test_music_keyword_search_uses_query_params(self):
        client = Client()
        client.generate_uuid = Mock(return_value="browse-session")
        client.private_request = AsyncMock(return_value={"keywords": [], "status": "ok"})

        result = await client.music_keyword_search("drake")

        self.assertEqual(result, {"keywords": [], "status": "ok"})
        client.private_request.assert_awaited_once_with(
            "music/keyword_search/",
            params={
                "num_keywords": "3",
                "search_session_id": "",
                "product": "music_in_feed",
                "q": "drake",
                "browse_session_id": "browse-session",
            },
        )

    async def test_music_bookmark_posts_original_audio_id(self):
        client = Client()
        client.uuid = "uuid-1"
        client.private_request = AsyncMock(return_value={"success": True, "status": "ok"})

        result = await client.music_bookmark("1171063161088391")

        self.assertTrue(result)
        client.private_request.assert_awaited_once_with(
            "music/bookmark_music/",
            data={
                "original_audio_id": "1171063161088391",
                "_uuid": "uuid-1",
                "surface_requested_from": "audio_aggregation_page",
            },
            with_signature=False,
        )

    async def test_music_clips_audio_browser_posts_browse_session(self):
        client = Client()
        client.uuid = "uuid-1"
        client.generate_uuid = Mock(return_value="browse-session")
        client.private_request = AsyncMock(return_value={"items": [], "status": "ok"})

        result = await client.music_clips_audio_browser()

        self.assertEqual(result, {"items": [], "status": "ok"})
        client.private_request.assert_awaited_once_with(
            "music/clips_audio_browser/",
            data={
                "product": "story_camera_clips_v2",
                "_uuid": "uuid-1",
                "browse_session_id": "browse-session",
            },
            with_signature=False,
        )

    async def test_music_verify_original_audio_title_returns_valid_flag(self):
        client = Client()
        client.uuid = "uuid-1"
        client.private_request = AsyncMock(return_value={"is_valid": True, "status": "ok"})

        result = await client.music_verify_original_audio_title("Original Audio")

        self.assertTrue(result)
        client.private_request.assert_awaited_once_with(
            "music/verify_original_audio_title/",
            data={"original_audio_name": "Original Audio", "_uuid": "uuid-1"},
            with_signature=False,
        )

    async def test_track_download_by_url_uses_httpx_request(self):
        client = Client()
        client.request_timeout = 7
        response = Mock()
        response.read.return_value = b"track-bytes"

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("aiograpi.mixins.track.httpx_ext.request", new=AsyncMock(return_value=response)) as request:
                path = await client.track_download_by_url(
                    "https://example.com/audio/test-track.mp3",
                    folder=Path(temp_dir),
                )
                self.assertEqual(path.read_bytes(), b"track-bytes")

        request.assert_awaited_once_with("GET", "https://example.com/audio/test-track.mp3", timeout=7)
        response.raise_for_status.assert_called_once_with()
        self.assertEqual(path.name, "test-track.mp3")

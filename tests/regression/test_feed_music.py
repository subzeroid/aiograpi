import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from aiograpi import Client


def _build_client():
    client = Client()
    client.settings = {}
    client._user_id = "1"
    client.uuid = "uuid"
    client.android_device_id = "device"
    client.client_session_id = "client-session"
    client.timezone_offset = 0
    client.set_device({})
    client.with_default_data = lambda data: data
    return client


class FeedMusicRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_music_in_feed_audio_browser_requests_feed_music_product(self):
        client = _build_client()
        expected = {"status": "ok", "alacorn_session_id": "alacorn-1"}
        client.private_request = AsyncMock(return_value=expected)

        result = await client.music_in_feed_audio_browser(browse_session_id="browse-1")

        assert result == expected
        client.private_request.assert_awaited_once_with(
            "music/music_in_feed_audio_browser/",
            data={
                "product": "music_in_feed",
                "_uuid": "uuid",
                "browse_session_id": "browse-1",
            },
            with_signature=False,
        )

    async def test_photo_upload_with_music_adds_music_params_without_mutating_extra_data(self):
        client = _build_client()
        track = types.SimpleNamespace(
            id="track-id",
            audio_asset_id="asset-id",
            audio_cluster_id="cluster-id",
            highlight_start_times_in_ms=[58000],
            title="Memories",
            display_artist="Justin Lee",
        )
        extra_data = {"share_to_facebook": 1}
        client.photo_upload = AsyncMock(return_value="uploaded")

        result = await client.photo_upload_with_music(
            Path("photo.jpg"),
            "caption",
            track,
            extra_data=extra_data,
            alacorn_session_id="alacorn-1",
        )

        assert result == "uploaded"
        assert extra_data == {"share_to_facebook": 1}
        upload_extra = client.photo_upload.call_args.kwargs["extra_data"]
        assert upload_extra["share_to_facebook"] == 1
        assert upload_extra["music_params"] == {
            "audio_asset_id": "asset-id",
            "audio_cluster_id": "cluster-id",
            "audio_asset_start_time_in_ms": 58000,
            "derived_content_start_time_in_ms": 0,
            "overlap_duration_in_ms": 30000,
            "browse_session_id": None,
            "product": "music_in_feed",
            "song_name": "Memories",
            "artist_name": "Justin Lee",
            "alacorn_session_id": "alacorn-1",
            "audio_apply_source": 0,
        }

    async def test_album_upload_with_music_adds_music_params_without_mutating_extra_data(self):
        client = _build_client()
        track = {
            "id": "track-id",
            "audio_cluster_id": "cluster-id",
            "highlight_start_times_in_ms": [12000],
            "title": "Album song",
            "display_artist": "Album artist",
        }
        extra_data = {"disable_comments": 1}
        client.album_upload = AsyncMock(return_value="uploaded")

        result = await client.album_upload_with_music(
            [Path("one.jpg"), Path("two.jpg")],
            "caption",
            track,
            extra_data=extra_data,
            alacorn_session_id="alacorn-1",
            browse_session_id="browse-1",
            overlap_duration=15000,
        )

        assert result == "uploaded"
        assert extra_data == {"disable_comments": 1}
        upload_extra = client.album_upload.call_args.kwargs["extra_data"]
        assert upload_extra["disable_comments"] == 1
        assert upload_extra["music_params"]["audio_asset_id"] == "track-id"
        assert upload_extra["music_params"]["audio_cluster_id"] == "cluster-id"
        assert upload_extra["music_params"]["audio_asset_start_time_in_ms"] == 12000
        assert upload_extra["music_params"]["overlap_duration_in_ms"] == 15000
        assert upload_extra["music_params"]["browse_session_id"] == "browse-1"
        assert upload_extra["music_params"]["product"] == "music_in_feed"
        assert upload_extra["music_params"]["song_name"] == "Album song"
        assert upload_extra["music_params"]["artist_name"] == "Album artist"
        assert upload_extra["music_params"]["alacorn_session_id"] == "alacorn-1"

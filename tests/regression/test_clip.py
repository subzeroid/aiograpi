import json
import unittest
from pathlib import Path
from unittest import mock
from unittest.mock import AsyncMock, Mock

from aiograpi import Client


def _build_client():
    client = Client()
    client.settings = {}
    client._user_id = "1"
    client.uuid = "uuid"
    client.android_device_id = "device"
    client.client_session_id = "client-session"
    client.timezone_offset = 0
    client.last_json = {}
    client.last_response = None
    client.set_device({})
    client.with_default_data = lambda data: data
    client.request_log = lambda response: None
    client.expose = AsyncMock()
    return client


def _build_media_payload():
    return {
        "pk": "1",
        "id": "1_1",
        "code": "abc",
        "taken_at": 1710000000,
        "media_type": 2,
        "caption": {"text": "caption"},
        "user": {
            "pk": "1",
            "username": "example",
            "profile_pic_url": "https://example.com/profile.jpg",
        },
        "like_count": 0,
        "video_versions": [
            {
                "url": "https://example.com/video.mp4",
                "width": 720,
                "height": 1280,
            }
        ],
        "image_versions2": {
            "candidates": [
                {
                    "url": "https://example.com/thumbnail.jpg",
                    "width": 720,
                    "height": 1280,
                }
            ]
        },
    }


class ClipPinRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_clip_pin_uses_reels_grid_payload(self):
        client = Client()
        client.private_request = AsyncMock(return_value={"status": "ok"})

        result = await client.clip_pin("3894040329476845448")

        assert result is True
        client.private_request.assert_awaited_once_with(
            "users/pin_timeline_media/",
            data={"post_id": "3894040329476845448", "profile_grid": "clips"},
        )

    async def test_clip_unpin_uses_reels_grid_payload(self):
        client = Client()
        client.private_request = AsyncMock(return_value={"status": "ok"})

        result = await client.clip_unpin("3894040329476845448")

        assert result is True
        client.private_request.assert_awaited_once_with(
            "users/unpin_timeline_media/",
            data={"post_id": "3894040329476845448", "profile_grid": "clips"},
        )

    async def test_clip_pin_revert_unpins_reels_grid(self):
        client = Client()
        client.private_request = AsyncMock(return_value={"status": "ok"})

        result = await client.clip_pin("3894040329476845448", revert=True)

        assert result is True
        client.private_request.assert_awaited_once_with(
            "users/unpin_timeline_media/",
            data={"post_id": "3894040329476845448", "profile_grid": "clips"},
        )


class ClipUploadRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_clip_share_to_fb_config_requests_reel_facebook_config(self):
        client = _build_client()
        expected = {"status": "ok", "eligible": True}
        client.private_request = AsyncMock(return_value=expected)

        result = await client.clip_share_to_fb_config()

        client.private_request.assert_awaited_once()
        endpoint = client.private_request.call_args.args[0]
        params = client.private_request.call_args.kwargs["params"]
        assert endpoint == "clips/user/share_to_fb_config/"
        device_status = json.loads(params["device_status"])
        assert device_status["chip_vendor"] == "others"
        assert device_status["hw_av1_dec"] is False
        assert result == expected

    async def test_clip_info_for_creation_requests_reel_creation_config(self):
        client = _build_client()
        expected = {"status": "ok", "trial_config": {"is_enabled": True}}
        client.private_request = AsyncMock(return_value=expected)

        result = await client.clip_info_for_creation()

        assert result == expected
        client.private_request.assert_awaited_once_with("clips/clips_info_for_creation/")

    async def test_clip_trial_eligible_reads_creation_trial_config(self):
        client = _build_client()
        client.clip_info_for_creation = AsyncMock(return_value={"trial_config": {"is_enabled": True}})

        assert await client.clip_trial_eligible() is True
        client.clip_info_for_creation.assert_awaited_once_with()

    async def test_clip_trial_eligible_returns_false_when_creation_trial_config_is_missing(self):
        client = _build_client()
        client.clip_info_for_creation = AsyncMock(return_value={"status": "ok"})

        assert await client.clip_trial_eligible() is False

    async def test_clip_upload_uses_current_reel_rupload_flow(self):
        client = _build_client()
        client.last_json = {"media": _build_media_payload()}
        ok_response = Mock(status_code=200)
        client.private.get = AsyncMock(return_value=ok_response)
        client.private.post = AsyncMock(side_effect=[ok_response, ok_response])
        client.clip_configure = AsyncMock(return_value={"status": "ok", "media": _build_media_payload()})

        with mock.patch(
            "aiograpi.mixins.clip.analyze_video",
            return_value=(Path("/tmp/thumb.jpg"), 720, 1280, 6.023),
        ):
            with mock.patch("time.time", return_value=1778346423.0):
                with mock.patch("builtins.open", mock.mock_open(read_data=b"video-bytes")):
                    with mock.patch("aiograpi.mixins.clip.asyncio.sleep", new=AsyncMock()):
                        await client.clip_upload(Path("example.mp4"), "caption")

        post_calls = client.private.post.call_args_list
        assert len(post_calls) == 2
        upload_settings_call, video_upload_call = post_calls
        assert upload_settings_call.args[0].startswith("https://i.instagram.com/upload_settings/")
        settings_headers = upload_settings_call.kwargs["headers"]
        assert settings_headers["Content-Type"] == "application/json"
        assert settings_headers["X-Entity-Name"] == "upload_settings"
        assert settings_headers["X-Entity-Type"] == "application/json"
        assert settings_headers["Offset"] == "0"
        assert settings_headers["Content-Length"] == settings_headers["X-Entity-Length"]
        settings_payload = json.loads(upload_settings_call.kwargs["data"])
        assert settings_payload["composer_session_id"] == upload_settings_call.args[0].rsplit("/", 1)[-1]
        settings_properties = settings_payload["upload_setting_properties"]
        assert settings_properties["context"]["source_type"] == "clips"
        assert settings_properties["context"]["target_id"] == 1
        assert settings_properties["video"]["video_width"] == 720
        assert settings_properties["video"]["video_height"] == 1280
        assert settings_properties["video"]["video_original_file_size"] == 11
        assert settings_payload["preview_spec"]["video_dur_ms"] == 6023

        upload_url = video_upload_call.args[0]
        upload_name = upload_url.rsplit("/", 1)[-1]
        assert client.private.get.call_args.args[0].endswith(upload_name)
        assert upload_name.endswith("-0-11-1778346423000-1778346423000")

        headers = video_upload_call.kwargs["headers"]
        assert headers["Content-Type"] == "application/octet-stream"
        assert headers["X-Entity-Type"] == "video/mp4"
        assert headers["X-Entity-Length"] == "11"
        assert headers["X-Entity-Name"] == upload_name
        assert headers["Offset"] == "0"
        assert headers["Segment-Start-Offset"] == "0"
        assert headers["Segment-Type"] == "3"

        rupload_params = json.loads(headers["X-Instagram-Rupload-Params"])
        assert rupload_params["share_type"] == "reels"
        assert rupload_params["is_optimistic_upload"] == "true"
        assert rupload_params["content_tags"] == "use_default_cover"
        assert rupload_params["xsharing_user_ids"] == "[]"
        assert rupload_params["upload_media_duration_ms"] == "6023"
        assert rupload_params["session_id"] == rupload_params["upload_id"]

    async def test_clip_upload_trial_adds_trial_params_without_mutating_extra_data(self):
        client = _build_client()
        client.last_json = {"media": _build_media_payload()}
        ok_response = Mock(status_code=200)
        client.private.get = AsyncMock(return_value=ok_response)
        client.private.post = AsyncMock(side_effect=[ok_response, ok_response])
        client.clip_configure = AsyncMock(return_value={"status": "ok", "media": _build_media_payload()})
        extra_data = {"share_to_facebook": 1}

        with mock.patch(
            "aiograpi.mixins.clip.analyze_video",
            return_value=(Path("/tmp/thumb.jpg"), 720, 1280, 6.023),
        ):
            with mock.patch("builtins.open", mock.mock_open(read_data=b"video-bytes")):
                with mock.patch("aiograpi.mixins.clip.asyncio.sleep", new=AsyncMock()):
                    await client.clip_upload(
                        Path("example.mp4"),
                        "caption",
                        trial=True,
                        trial_graduation_strategy="manual",
                        extra_data=extra_data,
                    )

        assert extra_data == {"share_to_facebook": 1}
        assert client.clip_configure.call_args.args[8] == "0"
        configure_extra = client.clip_configure.call_args.kwargs["extra_data"]
        assert configure_extra["share_to_facebook"] == 1
        assert configure_extra["trial_params"] == {"graduation_strategy": "manual"}

    async def test_clip_upload_trial_preserves_explicit_trial_params(self):
        client = _build_client()
        client.last_json = {"media": _build_media_payload()}
        ok_response = Mock(status_code=200)
        client.private.get = AsyncMock(return_value=ok_response)
        client.private.post = AsyncMock(side_effect=[ok_response, ok_response])
        client.clip_configure = AsyncMock(return_value={"status": "ok", "media": _build_media_payload()})
        extra_data = {
            "trial_params": {
                "graduation_strategy": "ss_performance",
                "custom_field": "1",
            },
        }

        with mock.patch(
            "aiograpi.mixins.clip.analyze_video",
            return_value=(Path("/tmp/thumb.jpg"), 720, 1280, 6.023),
        ):
            with mock.patch("builtins.open", mock.mock_open(read_data=b"video-bytes")):
                with mock.patch("aiograpi.mixins.clip.asyncio.sleep", new=AsyncMock()):
                    await client.clip_upload(
                        Path("example.mp4"),
                        "caption",
                        trial=True,
                        extra_data=extra_data,
                    )

        assert client.clip_configure.call_args.args[8] == "0"
        configure_extra = client.clip_configure.call_args.kwargs["extra_data"]
        assert configure_extra["trial_params"] == {
            "graduation_strategy": "ss_performance",
            "custom_field": "1",
        }

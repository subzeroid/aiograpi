import json
import unittest
from pathlib import Path
from unittest import mock
from unittest.mock import AsyncMock, Mock

from aiograpi import Client
from aiograpi.exceptions import ClientError, ClipNotUpload


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
    async def test_clip_upload_error_includes_stage_status_and_body(self):
        client = _build_client()
        response = Mock(status_code=500, text='{"message":"upload failed","status":"fail"}')
        response.json.return_value = {"message": "upload failed", "status": "fail"}

        with self.assertRaises(ClipNotUpload) as ctx:
            client._raise_clip_upload_error(response, "upload_settings")

        error = ctx.exception
        self.assertIs(error.response, response)
        self.assertEqual(error.stage, "upload_settings")
        self.assertEqual(error.status_code, 500)
        self.assertEqual(error.error_response, {"message": "upload failed", "status": "fail"})
        self.assertEqual(error.response_text, '{"message":"upload failed","status":"fail"}')
        self.assertIn("Clip upload failed during upload_settings", str(error))
        self.assertEqual(client.last_response, response)
        self.assertEqual(client.last_json, {"message": "upload failed", "status": "fail"})

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

    async def test_clip_share_to_fb_unified_config_requests_android_cxp_query(self):
        client = _build_client()
        expected = {"status": "ok", "data": {"xcxp_unified_crossposting_configs_root": {}}}
        client.private_graphql_query_request = AsyncMock(return_value=expected)

        result = await client.clip_share_to_fb_unified_config()

        client.private_graphql_query_request.assert_awaited_once()
        kwargs = client.private_graphql_query_request.call_args.kwargs
        assert kwargs["friendly_name"] == "CrosspostingUnifiedConfigsQuery"
        assert kwargs["root_field_name"] == "xcxp_unified_crossposting_configs_root"
        assert kwargs["client_doc_id"] == "216179630714134719310007237117"
        assert kwargs["priority"] == "u=3, i"
        assert kwargs["extra_headers"] == {"X-FB-RMD": "state=URL_ELIGIBLE"}
        assert kwargs["variables"] == {
            "configs_request": {
                "source_app": "IG",
                "crosspost_app_surface_list": [
                    {
                        "source_surface": "STORY",
                        "destination_app": "FB",
                        "destination_surface": "STORY",
                    },
                    {
                        "source_surface": "FEED",
                        "destination_app": "FB",
                        "destination_surface": "FEED",
                    },
                    {
                        "source_surface": "REELS",
                        "destination_app": "FB",
                        "destination_surface": "REELS",
                    },
                ],
            }
        }
        assert result == expected

    async def test_clip_share_to_fb_destination_normalizes_current_reel_destination_fields(self):
        client = _build_client()

        result = await client.clip_share_to_fb_destination(
            config={
                "enabled": True,
                "is_account_linked": True,
                "share_to_fb_destination_id": "fb-destination-id",
                "share_to_fb_destination_type": "page",
                "share_to_fb_destination_audience_type": "PUBLIC",
                "reels_cross_app_share_fb_validation_check_bypass": True,
                "status": "ok",
            }
        )

        assert result == {
            "destination_id": "fb-destination-id",
            "destination_type": "PAGE",
            "destination_audience_type": "PUBLIC",
            "validation_check_bypass": True,
        }

    async def test_clip_share_to_fb_destination_rejects_unavailable_config_without_destination(self):
        client = _build_client()

        with self.assertRaises(ClientError) as ctx:
            await client.clip_share_to_fb_destination(
                config={
                    "share_to_fb_unavailable": True,
                    "status": "ok",
                }
            )

        assert "unavailable" in str(ctx.exception)

    async def test_clip_share_to_fb_destination_does_not_use_account_id_as_destination(self):
        client = _build_client()

        with self.assertRaises(ClientError) as ctx:
            await client.clip_share_to_fb_destination(
                config={
                    "enabled": True,
                    "is_account_linked": True,
                    "account_id": "account-center-or-linking-id",
                    "posting_type": "USER",
                    "status": "ok",
                }
            )

        assert "no destination" in str(ctx.exception)

    async def test_clip_share_to_fb_destination_falls_back_to_unified_reels_fb_destination(self):
        client = _build_client()
        unified_config = {
            "data": {
                "1$xcxp_unified_crossposting_configs_root(configs_request:$configs_request)": {
                    "configs": [
                        {
                            "source_surface": "FEED",
                            "destination_app": "FB",
                            "destination_surface": "FEED",
                            "destination": {
                                "destination_id": "feed-destination-id",
                                "destination_type": "USER",
                            },
                        },
                        {
                            "source_surface": "REELS",
                            "destination_app": "FB",
                            "destination_surface": "REELS",
                            "destination": {
                                "destination_id": "reels-destination-id",
                                "destination_type": "page",
                                "destination_audience_type": "PUBLIC",
                            },
                            "cross_app_share_fb_validation_check_bypass": True,
                        },
                    ]
                }
            },
            "status": "ok",
        }
        client.clip_share_to_fb_config = AsyncMock(return_value={"share_to_fb_unavailable": True, "status": "ok"})
        client.clip_share_to_fb_unified_config = AsyncMock(return_value=unified_config)

        result = await client.clip_share_to_fb_destination()

        client.clip_share_to_fb_config.assert_awaited_once()
        client.clip_share_to_fb_unified_config.assert_awaited_once()
        assert result == {
            "destination_id": "reels-destination-id",
            "destination_type": "PAGE",
            "destination_audience_type": "PUBLIC",
            "validation_check_bypass": True,
        }

    async def test_clip_share_to_fb_unified_destination_ignores_generic_account_center_ids(self):
        client = _build_client()

        with self.assertRaises(ClientError) as ctx:
            await client.clip_share_to_fb_unified_destination(
                config={
                    "data": {
                        "xcxp_unified_crossposting_configs_root": {
                            "configs": [
                                {
                                    "source_surface": "REELS",
                                    "destination_app": "FB",
                                    "destination_surface": "REELS",
                                    "account_id": "account-center-id",
                                    "fbid": "facebook-linking-id",
                                    "posting_type": "USER",
                                }
                            ]
                        }
                    },
                    "status": "ok",
                }
            )

        assert "no confirmed Reel Facebook destination" in str(ctx.exception)

    async def test_clip_share_to_fb_extra_data_builds_current_reel_crosspost_payload(self):
        client = _build_client()
        config = {
            "enabled": True,
            "is_account_linked": True,
            "reels_share_to_facebook": True,
            "reels_destination_id": "fb-destination-id",
            "posting_type": "USER",
            "reels_cross_app_share_type": "CROSSPOST",
            "reels_cross_app_share_fb_validation_check_bypass": True,
            "status": "ok",
        }

        result = await client.clip_share_to_fb_extra_data(config=config, attempt_id="attempt-id")

        assert result == {
            "share_to_facebook": "1",
            "is_reel_shared_to_fb": True,
            "share_to_facebook_reels": True,
            "share_to_fb_destination_id": "fb-destination-id",
            "share_to_fb_destination_type": "USER",
            "cross_app_share_fb_validation_check_bypass": True,
            "xpost_surface": "IG_REELS_COMPOSER",
            "no_token_crosspost": "1",
            "attempt_id": "attempt-id",
        }

    async def test_clip_share_to_fb_extra_data_allows_explicit_destination_when_preflight_is_unavailable(self):
        client = _build_client()

        result = await client.clip_share_to_fb_extra_data(
            config={
                "share_to_fb_unavailable": True,
                "status": "ok",
            },
            destination_id="fb-destination-id",
            destination_type="USER",
            attempt_id="attempt-id",
        )

        assert result["share_to_fb_destination_id"] == "fb-destination-id"
        assert result["share_to_fb_destination_type"] == "USER"
        assert result["attempt_id"] == "attempt-id"

    async def test_clip_share_to_fb_extra_data_allows_config_destination_when_preflight_is_unavailable(self):
        client = _build_client()

        result = await client.clip_share_to_fb_extra_data(
            config={
                "share_to_fb_unavailable": True,
                "reels_destination_id": "fb-destination-id",
                "posting_type": "PAGE",
                "status": "ok",
            },
            attempt_id="attempt-id",
        )

        assert result["share_to_fb_destination_id"] == "fb-destination-id"
        assert result["share_to_fb_destination_type"] == "PAGE"

    async def test_clip_share_to_fb_extra_data_does_not_use_cross_app_share_type_as_destination_type(self):
        client = _build_client()

        with self.assertRaises(ClientError) as ctx:
            await client.clip_share_to_fb_extra_data(
                config={
                    "enabled": True,
                    "is_account_linked": True,
                    "reels_destination_id": "fb-destination-id",
                    "reels_cross_app_share_type": "CROSSPOST",
                    "status": "ok",
                }
            )

        assert "destination type" in str(ctx.exception)

    async def test_clip_share_to_fb_extra_data_raises_without_destination(self):
        client = _build_client()

        with self.assertRaises(ClientError) as ctx:
            await client.clip_share_to_fb_extra_data(
                config={
                    "enabled": True,
                    "default_share_to_fb_enabled": False,
                    "status": "ok",
                }
            )

        assert "Facebook Reel sharing configuration has no destination" in str(ctx.exception)

    async def test_clip_info_for_creation_requests_reel_creation_config(self):
        client = _build_client()
        expected = {"status": "ok", "trial_config": {"is_enabled": True}}
        client.private_request = AsyncMock(return_value=expected)

        result = await client.clip_info_for_creation()

        assert result == expected
        client.private_request.assert_awaited_once()
        assert client.private_request.call_args.args[0] == "clips/clips_info_for_creation/"
        device_status = json.loads(client.private_request.call_args.kwargs["params"]["device_status"])
        assert device_status["chip_vendor"] == "others"
        assert device_status["hw_av1_dec"] is False

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

    async def test_clip_upload_share_to_facebook_adds_crosspost_params_before_upload(self):
        client = _build_client()
        client.last_json = {"media": _build_media_payload()}
        ok_response = Mock(status_code=200)
        client.private.get = AsyncMock(return_value=ok_response)
        client.private.post = AsyncMock(side_effect=[ok_response, ok_response])
        client.clip_configure = AsyncMock(return_value={"status": "ok", "media": _build_media_payload()})
        extra_data = {"disable_comments": "1"}
        fb_extra = {
            "share_to_facebook": "1",
            "is_reel_shared_to_fb": True,
            "share_to_facebook_reels": True,
            "share_to_fb_destination_id": "fb-destination-id",
            "share_to_fb_destination_type": "USER",
            "cross_app_share_fb_validation_check_bypass": False,
            "xpost_surface": "IG_REELS_COMPOSER",
            "no_token_crosspost": "1",
            "attempt_id": "attempt-id",
        }
        client.clip_share_to_fb_extra_data = AsyncMock(return_value=fb_extra)

        with mock.patch(
            "aiograpi.mixins.clip.analyze_video",
            return_value=(Path("/tmp/thumb.jpg"), 720, 1280, 6.023),
        ):
            with mock.patch("builtins.open", mock.mock_open(read_data=b"video-bytes")):
                with mock.patch("aiograpi.mixins.clip.asyncio.sleep", new=AsyncMock()):
                    await client.clip_upload(
                        Path("example.mp4"),
                        "caption",
                        share_to_facebook=True,
                        fb_destination_id="fb-destination-id",
                        fb_destination_type="USER",
                        extra_data=extra_data,
                    )

        client.clip_share_to_fb_extra_data.assert_awaited_once_with(
            destination_id="fb-destination-id",
            destination_type="USER",
            destination_audience_type=None,
            xpost_surface="IG_REELS_COMPOSER",
            validation_check_bypass=None,
        )
        assert extra_data == {"disable_comments": "1"}
        configure_extra = client.clip_configure.call_args.kwargs["extra_data"]
        assert configure_extra["disable_comments"] == "1"
        assert configure_extra["share_to_fb_destination_id"] == "fb-destination-id"
        assert configure_extra["share_to_fb_destination_type"] == "USER"
        assert configure_extra["share_to_facebook_reels"] is True
        assert configure_extra["xpost_surface"] == "IG_REELS_COMPOSER"

    async def test_clip_music_extra_data_builds_reels_music_payload_from_dict(self):
        client = _build_client()
        track = {
            "id": "track-id",
            "audio_cluster_id": "cluster-id",
            "highlight_start_times_in_ms": [40500],
            "title": "Runaway",
            "display_artist": "AURORA",
            "music_canonical_id": "canonical-id",
        }

        result = client.clip_music_extra_data(track, overlap_duration=34000)

        assert result["clips_audio_metadata"] == {
            "original": {"volume_level": 1.0},
            "song": {
                "volume_level": 1.0,
                "is_saved": "0",
                "artist_name": "AURORA",
                "audio_asset_id": "track-id",
                "audio_cluster_id": "cluster-id",
                "track_name": "Runaway",
                "is_picked_precapture": "1",
                "music_canonical_id": "canonical-id",
            },
        }
        assert result["music_params"] == {
            "audio_asset_id": "track-id",
            "audio_cluster_id": "cluster-id",
            "audio_asset_start_time_in_ms": 40500,
            "derived_content_start_time_in_ms": 0,
            "overlap_duration_in_ms": 34000,
            "product": "story_camera_clips_v2",
            "song_name": "Runaway",
            "artist_name": "AURORA",
            "alacorn_session_id": "null",
            "music_canonical_id": "canonical-id",
        }

    async def test_clip_upload_with_music_adds_reels_music_metadata_without_mutating_extra_data(self):
        client = _build_client()
        extra_data = {"disable_comments": 1}
        track = {
            "id": "track-id",
            "audio_cluster_id": "cluster-id",
            "highlight_start_times_in_ms": [1500],
            "title": "Track title",
            "display_artist": "Artist",
        }
        client.clip_upload = AsyncMock(return_value="uploaded")

        result = await client.clip_upload_with_music(
            Path("clip.mp4"),
            "caption",
            track,
            extra_data=extra_data,
            overlap_duration=2500,
        )

        assert result == "uploaded"
        assert extra_data == {"disable_comments": 1}
        client.clip_upload.assert_awaited_once()
        assert client.clip_upload.call_args.args[:2] == (Path("clip.mp4"), "caption")
        upload_extra = client.clip_upload.call_args.kwargs["extra_data"]
        assert upload_extra["disable_comments"] == 1
        assert upload_extra["music_params"]["audio_asset_id"] == "track-id"
        assert upload_extra["music_params"]["audio_cluster_id"] == "cluster-id"
        assert upload_extra["music_params"]["audio_asset_start_time_in_ms"] == 1500
        assert upload_extra["music_params"]["overlap_duration_in_ms"] == 2500
        assert "clips_audio_metadata" in upload_extra

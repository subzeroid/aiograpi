import json
import tempfile
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

from aiograpi import Client
from aiograpi.types import Media, UserShort


class UploadRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    def build_client(self):
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
        client.expose = AsyncMock(return_value=None)
        return client

    def build_media(self, media_type=1):
        return Media(
            pk="1",
            id="1_1",
            code="abc",
            taken_at=datetime.now(timezone.utc),
            media_type=media_type,
            user=UserShort(pk="1", username="example", profile_pic_url="https://example.com/profile.jpg"),
            like_count=0,
            caption_text="caption",
            usertags=[],
            sponsor_tags=[],
            video_url="https://example.com/video.mp4" if media_type == 2 else None,
            thumbnail_url="https://example.com/photo.jpg",
        )

    async def test_photo_upload_sends_scheduled_publish_metadata(self):
        client = self.build_client()
        schedule_at = 1779808917
        client.photo_rupload = AsyncMock(return_value=("1", 720, 720))
        client.photo_configure = AsyncMock(return_value={"status": "ok"})
        client._extract_configured_media_or_recent = AsyncMock(return_value=self.build_media(media_type=1))

        media = await client.photo_upload(Path("example.jpg"), "caption", schedule_at=schedule_at)

        self.assertIsInstance(media, Media)
        extra_data = client.photo_configure.call_args.kwargs["extra_data"]
        self.assertEqual(extra_data["publish_mode"], "scheduled")
        self.assertEqual(json.loads(extra_data["content_scheduling_metadata"]), {"scheduled_publish_time": schedule_at})

    async def test_photo_upload_accepts_datetime_schedule_at(self):
        client = self.build_client()
        schedule_at = datetime.fromtimestamp(1779808917, tz=timezone.utc)
        client.photo_rupload = AsyncMock(return_value=("1", 720, 720))
        client.photo_configure = AsyncMock(return_value={"status": "ok"})
        client._extract_configured_media_or_recent = AsyncMock(return_value=self.build_media(media_type=1))

        await client.photo_upload(Path("example.jpg"), "caption", schedule_at=schedule_at)

        extra_data = client.photo_configure.call_args.kwargs["extra_data"]
        self.assertEqual(json.loads(extra_data["content_scheduling_metadata"]), {"scheduled_publish_time": 1779808917})

    async def test_video_upload_sends_scheduled_publish_metadata(self):
        client = self.build_client()
        schedule_at = 1779808917
        client.video_rupload = AsyncMock(return_value=("1", 720, 1280, 5, Path("/tmp/thumb.jpg")))
        client.video_configure = AsyncMock(return_value={"status": "ok"})
        client._extract_configured_media_or_raise = lambda configured, *args, **kwargs: self.build_media(media_type=2)

        media = await client.video_upload(Path("example.mp4"), "caption", schedule_at=schedule_at)

        self.assertIsInstance(media, Media)
        extra_data = client.video_configure.call_args.kwargs["extra_data"]
        self.assertEqual(extra_data["publish_mode"], "scheduled")
        self.assertEqual(json.loads(extra_data["content_scheduling_metadata"]), {"scheduled_publish_time": schedule_at})

    async def test_album_upload_sends_scheduled_publish_metadata(self):
        client = self.build_client()
        schedule_at = 1779808917
        client.photo_rupload = AsyncMock(return_value=("1", 720, 720))
        client.album_configure = AsyncMock(return_value={"status": "ok"})
        client._extract_configured_media_or_raise = lambda configured, *args, **kwargs: self.build_media(media_type=8)

        media = await client.album_upload([Path("one.jpg")], "caption", schedule_at=schedule_at, configure_timeout=0)

        self.assertIsInstance(media, Media)
        extra_data = client.album_configure.call_args.kwargs["extra_data"]
        self.assertEqual(extra_data["publish_mode"], "scheduled")
        self.assertEqual(json.loads(extra_data["content_scheduling_metadata"]), {"scheduled_publish_time": schedule_at})

    async def test_album_upload_with_music_forwards_schedule_at_without_mutating_extra_data(self):
        client = self.build_client()
        track = {
            "id": "track-id",
            "audio_cluster_id": "cluster-id",
            "highlight_start_times_in_ms": [12000],
            "title": "Album song",
            "display_artist": "Album artist",
        }
        extra_data = {"disable_comments": 1}
        schedule_at = datetime.fromtimestamp(1779808917, tz=timezone.utc)
        client.album_upload = AsyncMock(return_value="uploaded")

        result = await client.album_upload_with_music(
            [Path("one.jpg"), Path("two.jpg")],
            "caption",
            track,
            extra_data=extra_data,
            alacorn_session_id="alacorn-1",
            schedule_at=schedule_at,
        )

        self.assertEqual(result, "uploaded")
        self.assertEqual(extra_data, {"disable_comments": 1})
        self.assertEqual(client.album_upload.call_args.kwargs["schedule_at"], schedule_at)

    async def test_photo_upload_adds_coauthor_user_ids_without_mutating_extra_data(self):
        client = self.build_client()
        extra_data = {"disable_comments": 1}
        client.photo_rupload = AsyncMock(return_value=("1", 720, 720))
        client.photo_configure = AsyncMock(return_value={"status": "ok"})
        client._extract_configured_media_or_recent = AsyncMock(return_value=self.build_media(media_type=1))

        with unittest.mock.patch("asyncio.sleep", new=AsyncMock()):
            media = await client.photo_upload(
                Path("example.jpg"),
                "caption",
                extra_data=extra_data,
                coauthor_user_ids=[123, "456"],
            )

        self.assertIsInstance(media, Media)
        self.assertEqual(extra_data, {"disable_comments": 1})
        configure_extra = client.photo_configure.call_args.kwargs["extra_data"]
        self.assertEqual(configure_extra["disable_comments"], 1)
        self.assertEqual(configure_extra["invite_coauthor_user_ids"], ["123", "456"])

    async def test_video_upload_adds_coauthor_user_ids(self):
        client = self.build_client()
        client.video_rupload = AsyncMock(return_value=("1", 720, 1280, 5, Path("/tmp/thumb.jpg")))
        client.video_configure = AsyncMock(return_value={"status": "ok"})
        client._extract_configured_media_or_raise = lambda configured, *args, **kwargs: self.build_media(media_type=2)

        with unittest.mock.patch("asyncio.sleep", new=AsyncMock()):
            media = await client.video_upload(
                Path("example.mp4"),
                "caption",
                coauthor_user_ids=["123", "456"],
            )

        self.assertIsInstance(media, Media)
        self.assertEqual(
            client.video_configure.call_args.kwargs["extra_data"]["invite_coauthor_user_ids"], ["123", "456"]
        )

    async def test_album_upload_adds_coauthor_user_ids(self):
        client = self.build_client()
        client.photo_rupload = AsyncMock(return_value=("1", 720, 720))
        client.album_configure = AsyncMock(return_value={"status": "ok"})
        client._extract_configured_media_or_raise = lambda configured, *args, **kwargs: self.build_media(media_type=8)

        media = await client.album_upload(
            [Path("one.jpg")],
            "caption",
            configure_timeout=0,
            coauthor_user_ids=["123", "456"],
        )

        self.assertIsInstance(media, Media)
        self.assertEqual(
            client.album_configure.call_args.kwargs["extra_data"]["invite_coauthor_user_ids"], ["123", "456"]
        )

    async def test_clip_interest_topics_requests_reel_topic_catalog(self):
        client = self.build_client()
        expected = {
            "sub_interests": [
                {"name": "Technology", "fit_id": 607271032992452},
            ],
            "status": "ok",
        }
        client.private_request = AsyncMock(return_value=expected)

        result = await client.clip_interest_topics()

        client.private_request.assert_awaited_once_with(
            "interest_nux/list_all/",
            params={"caller": "INTEREST_NUX"},
            with_signature=False,
        )
        self.assertEqual(result, expected["sub_interests"])

    async def test_photo_rupload_sends_private_auth_headers(self):
        client = self.build_client()
        client.authorization_data = {
            "ds_user_id": "1",
            "sessionid": "1:session",
            "should_use_header_over_cookies": True,
        }
        response = unittest.mock.Mock(status_code=200)
        opened = unittest.mock.Mock()
        opened.__enter__ = unittest.mock.Mock(return_value=unittest.mock.Mock(size=(720, 720)))
        opened.__exit__ = unittest.mock.Mock(return_value=False)

        with unittest.mock.patch("aiograpi.mixins.photo.prepare_image", return_value=(b"photo-bytes", (720, 720))):
            with unittest.mock.patch("aiograpi.mixins.photo.Image.open", return_value=opened):
                with unittest.mock.patch("random.randint", return_value=1234567890):
                    client.private.post = AsyncMock(return_value=response)
                    upload_id, width, height = await client.photo_rupload(Path("image.jpg"), upload_id="upload-id")

        self.assertEqual((upload_id, width, height), ("upload-id", 720, 720))
        headers = client.private.post.call_args.kwargs["headers"]
        self.assertEqual(headers["Authorization"], client.authorization)
        self.assertEqual(headers["IG-U-DS-USER-ID"], "1")
        self.assertEqual(headers["X-Entity-Length"], "11")
        self.assertEqual(headers["X-Entity-Name"], "upload-id_0_1234567890")

    async def test_clip_upload_uses_current_reels_rupload_shape(self):
        client = self.build_client()
        client.last_json = {"media": {"pk": "1", "id": "1_1", "code": "abc", "media_type": 2}}
        client.authorization_data = {
            "ds_user_id": "1",
            "sessionid": "1:session",
            "should_use_header_over_cookies": True,
        }
        ok_response = unittest.mock.Mock(status_code=200)
        client.private.get = AsyncMock(return_value=ok_response)
        client.private.post = AsyncMock(side_effect=[ok_response, ok_response])
        client.clip_configure = AsyncMock(return_value={"status": "ok"})
        client._extract_configured_media_or_raise = lambda configured, *args, **kwargs: self.build_media(media_type=2)

        with unittest.mock.patch(
            "aiograpi.mixins.clip.analyze_video",
            return_value=(Path("/tmp/thumb.jpg"), 720, 1280, 6.023),
        ):
            with unittest.mock.patch("builtins.open", unittest.mock.mock_open(read_data=b"video-bytes")):
                with unittest.mock.patch("asyncio.sleep", new=AsyncMock()):
                    media = await client.clip_upload(Path("example.mp4"), "caption")

        self.assertIsInstance(media, Media)
        upload_settings_call = client.private.post.call_args_list[0]
        self.assertRegex(
            upload_settings_call.args[0],
            r"https://i\.instagram\.com/upload_settings/[0-9a-f-]{36}$",
        )
        settings_headers = upload_settings_call.kwargs["headers"]
        self.assertEqual(settings_headers["Authorization"], client.authorization)
        self.assertEqual(settings_headers["IG-U-DS-USER-ID"], "1")
        self.assertEqual(settings_headers["Content-Type"], "application/json")
        self.assertEqual(settings_headers["X-Entity-Name"], "upload_settings")
        self.assertEqual(settings_headers["X-Entity-Type"], "application/json")
        self.assertIn("X_FB_VIDEO_WATERFALL_ID", settings_headers)
        upload_settings = json.loads(upload_settings_call.kwargs["data"])
        upload_props = upload_settings["upload_setting_properties"]
        self.assertEqual(upload_props["context"]["source_type"], "clips")
        self.assertEqual(upload_props["context"]["target_id"], 1)
        self.assertEqual(upload_props["video"]["video_original_file_size"], 11)
        self.assertEqual(upload_props["video"]["video_duration_milliseconds"], 6023)

        init_headers = client.private.get.call_args.kwargs["headers"]
        self.assertEqual(init_headers["Authorization"], client.authorization)
        self.assertEqual(init_headers["IG-U-DS-USER-ID"], "1")
        self.assertEqual(init_headers["X-Entity-Type"], "video/mp4")
        rupload_params = json.loads(init_headers["X-Instagram-Rupload-Params"])
        self.assertEqual(rupload_params["share_type"], "reels")
        self.assertEqual(rupload_params["is_clips_video"], "1")
        self.assertEqual(rupload_params["upload_media_duration_ms"], "6023")
        self.assertEqual(rupload_params["upload_media_height"], "1280")
        self.assertEqual(rupload_params["upload_media_width"], "720")

        video_upload_call = client.private.post.call_args_list[1]
        upload_name = init_headers["X_FB_VIDEO_WATERFALL_ID"].rsplit("_", 2)[0]
        self.assertIn("/rupload_igvideo/", client.private.get.call_args.args[0])
        self.assertTrue(video_upload_call.args[0].startswith("https://i.instagram.com/rupload_igvideo/"))
        headers = video_upload_call.kwargs["headers"]
        self.assertEqual(headers["Authorization"], client.authorization)
        self.assertEqual(headers["IG-U-DS-USER-ID"], "1")
        self.assertEqual(headers["Content-Type"], "application/octet-stream")
        self.assertEqual(headers["X-Entity-Type"], "video/mp4")
        self.assertEqual(headers["X-Entity-Length"], "11")
        self.assertEqual(headers["Content-Length"], "11")
        self.assertEqual(headers["Offset"], "0")
        self.assertTrue(headers["X-Entity-Name"])
        self.assertIn("X-Instagram-Rupload-Params", headers)
        self.assertTrue(upload_name)

    async def test_clip_upload_topics_adds_interest_topics_without_mutating_extra_data(self):
        client = self.build_client()
        ok_response = unittest.mock.Mock(status_code=200)
        client.private.get = AsyncMock(return_value=ok_response)
        client.private.post = AsyncMock(side_effect=[ok_response, ok_response])
        client.clip_configure = AsyncMock(return_value={"status": "ok"})
        client._extract_configured_media_or_raise = lambda configured, *args, **kwargs: self.build_media(media_type=2)
        extra_data = {"disable_comments": "1"}

        with unittest.mock.patch(
            "aiograpi.mixins.clip.analyze_video",
            return_value=(Path("/tmp/thumb.jpg"), 720, 1280, 6.023),
        ):
            with unittest.mock.patch("builtins.open", unittest.mock.mock_open(read_data=b"video-bytes")):
                with unittest.mock.patch("asyncio.sleep", new=AsyncMock()):
                    await client.clip_upload(
                        Path("example.mp4"),
                        "caption",
                        topics=[123, "456"],
                        extra_data=extra_data,
                    )

        self.assertEqual(extra_data, {"disable_comments": "1"})
        configure_extra = client.clip_configure.call_args.kwargs["extra_data"]
        self.assertEqual(configure_extra["disable_comments"], "1")
        self.assertEqual(configure_extra["interest_topics"], ["123", "456"])

    async def test_coauthor_user_ids_rejects_conflicting_extra_data_key(self):
        client = self.build_client()

        with self.assertRaises(ValueError) as ctx:
            await client.photo_upload(
                Path("example.jpg"),
                "caption",
                extra_data={"invite_coauthor_user_ids": ["789"]},
                coauthor_user_ids=["123"],
            )

        self.assertIn("coauthor_user_ids", str(ctx.exception))
        self.assertIn("invite_coauthor_user_ids", str(ctx.exception))

    async def test_story_music_extra_data_builds_story_music_payload_from_dict(self):
        client = self.build_client()
        track = {
            "id": "track-id",
            "audio_asset_id": "asset-id",
            "audio_cluster_id": "cluster-id",
            "highlight_start_times_in_ms": [40500],
            "title": "Runaway",
            "display_artist": "AURORA",
            "music_canonical_id": "canonical-id",
        }
        extra_data = {
            "share_to_facebook": "1",
            "edits": {"crop_zoom": 1.0},
        }

        result = client.story_music_extra_data(
            track,
            extra_data=extra_data,
            overlap_duration=34000,
            audio_overlay_uuid="overlay-id",
        )

        self.assertEqual(extra_data, {"share_to_facebook": "1", "edits": {"crop_zoom": 1.0}})
        self.assertEqual(result["share_to_facebook"], "1")
        self.assertEqual(result["edits"]["crop_zoom"], 1.0)
        self.assertEqual(json.loads(result["music_burnin_params"]), {"asset_fbid": "asset-id", "offset_ms": 40500})
        self.assertEqual(result["music_params"]["audio_asset_id"], "asset-id")
        self.assertEqual(result["music_params"]["audio_cluster_id"], "cluster-id")
        self.assertEqual(result["music_params"]["audio_asset_start_time_in_ms"], 40500)
        self.assertEqual(result["music_params"]["overlap_duration_in_ms"], 34000)
        self.assertEqual(result["music_params"]["product"], "story_camera_music_overlay_post_capture")
        self.assertEqual(result["music_params"]["music_canonical_id"], "canonical-id")
        self.assertEqual(
            result["edits"]["media_audio_overlay_info"]["media_audio_overlays"][0]["audio_overlay_uuid"], "overlay-id"
        )

    async def test_video_upload_to_story_with_music_muxes_track_and_uploads_story(self):
        client = self.build_client()
        extra_data = {"share_to_facebook": "1"}
        track = {
            "id": "track-id",
            "audio_cluster_id": "cluster-id",
            "highlight_start_times_in_ms": [1500],
            "title": "Story song",
            "display_artist": "Story artist",
            "uri": "https://example.com/track.m4a",
        }
        audio_segments = []
        video_paths_seen = []

        class FakeAudioClip:
            def __init__(self, path):
                self.path = path

            def subclipped(self, start, end):
                audio_segments.append((start, end))
                return self

            def close(self):
                return None

        class FakeVideoClip:
            def __init__(self, path):
                self.path = path
                self.duration = 2.5

            def with_audio(self, audio_clip):
                self.audio_clip = audio_clip
                return self

            def write_videofile(self, path):
                Path(path).write_bytes(b"video")

            def close(self):
                return None

        fake_mp = types.ModuleType("moviepy")
        fake_mp.VideoFileClip = FakeVideoClip
        fake_mp.AudioFileClip = FakeAudioClip

        def upload_side_effect(path, caption="", **kwargs):
            video_paths_seen.append(Path(path))
            self.assertTrue(Path(path).exists())
            return "uploaded"

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "track.m4a"
            audio_path.write_bytes(b"audio")
            with unittest.mock.patch.dict("sys.modules", {"moviepy": fake_mp}):
                client.track_download_by_url = AsyncMock(return_value=audio_path)
                client.video_upload_to_story = AsyncMock(side_effect=upload_side_effect)
                result = await client.video_upload_to_story_with_music(
                    Path("input.mp4"),
                    "caption",
                    track,
                    extra_data=extra_data,
                )

        self.assertEqual(result, "uploaded")
        self.assertEqual(extra_data, {"share_to_facebook": "1"})
        client.track_download_by_url.assert_awaited_once()
        self.assertEqual(client.track_download_by_url.call_args.args[0], "https://example.com/track.m4a")
        self.assertEqual(audio_segments, [(1.5, 4.0)])
        self.assertEqual(len(video_paths_seen), 1)
        client.video_upload_to_story.assert_awaited_once()
        self.assertEqual(client.video_upload_to_story.call_args.args[:2], (video_paths_seen[0], "caption"))
        upload_extra = client.video_upload_to_story.call_args.kwargs["extra_data"]
        self.assertEqual(upload_extra["share_to_facebook"], "1")
        self.assertEqual(upload_extra["music_params"]["audio_asset_start_time_in_ms"], 1500)
        self.assertEqual(upload_extra["music_params"]["overlap_duration_in_ms"], 2500)

    async def test_photo_upload_to_story_with_music_renders_photo_story_video(self):
        client = self.build_client()
        track = {
            "id": "track-id",
            "audio_cluster_id": "cluster-id",
            "highlight_start_times_in_ms": [0],
            "title": "Photo song",
            "display_artist": "Photo artist",
            "progressive_download_url": "https://example.com/track.m4a",
        }
        audio_segments = []
        image_durations = []
        image_clips = []

        class FakeAudioClip:
            def __init__(self, path):
                self.path = path

            def subclipped(self, start, end):
                audio_segments.append((start, end))
                return self

            def close(self):
                return None

        class FakeImageClip:
            def __init__(self, path):
                self.path = path
                self.duration = None
                self.fps = None
                image_clips.append(self)

            def with_duration(self, duration):
                self.duration = duration
                image_durations.append(duration)
                return self

            def with_audio(self, audio_clip):
                self.audio_clip = audio_clip
                return self

            def write_videofile(self, path):
                Path(path).write_bytes(b"video")

            def close(self):
                return None

        fake_mp = types.ModuleType("moviepy")
        fake_mp.ImageClip = FakeImageClip
        fake_mp.AudioFileClip = FakeAudioClip

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "track.m4a"
            audio_path.write_bytes(b"audio")
            with unittest.mock.patch.dict("sys.modules", {"moviepy": fake_mp}):
                client.track_download_by_url = AsyncMock(return_value=audio_path)
                client.video_upload_to_story = AsyncMock(return_value="uploaded")
                result = await client.photo_upload_to_story_with_music(
                    Path("story.jpg"),
                    "caption",
                    track,
                    duration=7,
                )

        self.assertEqual(result, "uploaded")
        self.assertEqual(image_durations, [7])
        self.assertEqual(audio_segments, [(0.0, 7.0)])
        self.assertEqual(image_clips[0].fps, 30)
        self.assertEqual(
            client.video_upload_to_story.call_args.kwargs["extra_data"]["music_params"]["overlap_duration_in_ms"], 7000
        )
        client.video_upload_to_story.assert_awaited_once()
        self.assertEqual(client.video_upload_to_story.call_args.args[1], "caption")

    def _assert_crop_thumbnail_closes_images(self, module):
        class FakeImage:
            def __init__(self, size=(1780, 1000)):
                self.size = size
                self.closed = False
                self.saved = False
                self.crop_box = None
                self.crop_result = None

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                self.close()

            def crop(self, box):
                self.crop_box = box
                return self.crop_result

            def save(self, fp):
                self.saved = True

            def close(self):
                self.closed = True

        source_image = FakeImage()
        cropped_image = FakeImage()
        source_image.crop_result = cropped_image

        with unittest.mock.patch.object(module.Image, "open", return_value=source_image) as image_open:
            with unittest.mock.patch("builtins.open", unittest.mock.mock_open()) as output_open:
                result = module.crop_thumbnail(Path("thumb.jpg"))

        self.assertTrue(result)
        image_open.assert_called_once_with("thumb.jpg")
        output_open.assert_called_once_with(Path("thumb.jpg"), "wb")
        expected_box = (609.1011235955056, 0, 1170.8988764044943, 1000)
        for actual, expected in zip(source_image.crop_box, expected_box):
            self.assertAlmostEqual(actual, expected)
        self.assertTrue(source_image.closed)
        self.assertTrue(cropped_image.saved)
        self.assertTrue(cropped_image.closed)

    def test_clip_crop_thumbnail_closes_source_and_cropped_images(self):
        import aiograpi.mixins.clip as clip_mixin

        self._assert_crop_thumbnail_closes_images(clip_mixin)

    def test_igtv_crop_thumbnail_closes_source_and_cropped_images(self):
        import aiograpi.mixins.igtv as igtv_mixin

        self._assert_crop_thumbnail_closes_images(igtv_mixin)

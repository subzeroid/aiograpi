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

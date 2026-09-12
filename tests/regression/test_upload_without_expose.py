import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from aiograpi.exceptions import ClientNotFoundError
from aiograpi.types import Media, Story
from tests.regression import test_upload as upload_fixtures

UPLOAD_CASES = {
    "photo_upload": ("media/configure/", 1, Media),
    "photo_upload_to_story": ("media/configure_to_story/", 1, Story),
    "album_upload": ("media/configure_sidecar/", 8, Media),
    "video_upload": ("media/configure/?video=1", 2, Media),
    "video_upload_to_story": ("media/configure_to_story/?video=1", 2, Story),
    "clip_upload": ("media/configure_to_clips/?video=1", 2, Media),
    "igtv_upload": ("media/configure_to_igtv/?video=1", 2, Media),
}


class UploadWithoutExposeRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fixtures = upload_fixtures.UploadRegressionTestCase()
        self.client = self.fixtures.build_client()
        del self.client.expose  # Exercise the real expose API if an upload calls it.
        self.client.user_medias_v1 = AsyncMock(return_value=[])
        self.client.user_stories = AsyncMock(return_value=[])
        self.client.photo_rupload = AsyncMock(return_value=("1", 720, 1280))
        self.client.video_rupload = AsyncMock(return_value=("1", 720, 1280, 5, Path("thumbnail.jpg")))
        self.requests = []
        sleep = patch("asyncio.sleep", new=AsyncMock())
        sleep.start()
        self.addCleanup(sleep.stop)

    async def upload(self, method_name, configure_error=None):
        configure_endpoint, media_type, result_type = UPLOAD_CASES[method_name]
        payload = self.fixtures.build_media_payload(media_type=media_type)
        payload["product_type"] = "story" if result_type is Story else "feed"
        if method_name == "clip_upload":
            payload["product_type"] = "clips"
        if method_name == "igtv_upload":
            payload["product_type"] = "igtv"
            payload["title"] = "Video title"
        if method_name == "album_upload":
            payload["carousel_media"] = [self.fixtures.build_media_payload(media_type=1)]

        async def private_request(endpoint, *args, **kwargs):
            self.requests.append(endpoint)
            if endpoint == "qe/expose/":
                self.client.last_json = {"status": "fail", "message": "Not found"}
                raise ClientNotFoundError("qe/expose/ returned 404", response=Mock(status_code=404))
            self.assertEqual(endpoint, configure_endpoint)
            if configure_error is not None:
                self.client.last_json = {"status": "fail", "message": "Configure failed"}
                raise configure_error
            self.client.last_json = {"status": "ok", "media": payload}
            return self.client.last_json

        self.client.private_request = AsyncMock(side_effect=private_request)
        path = Path("example.jpg" if media_type in (1, 8) else "example.mp4")
        if method_name == "album_upload":
            return await self.client.album_upload([path], "caption", configure_timeout=0)
        if method_name in ("clip_upload", "igtv_upload"):
            response = Mock(status_code=200)
            self.client.private.get = AsyncMock(return_value=response)
            self.client.private.post = AsyncMock(return_value=response)
            module_name = method_name.split("_", 1)[0]
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "example.mp4"
                path.write_bytes(b"video-bytes")
                with patch(
                    f"aiograpi.mixins.{module_name}.analyze_video",
                    return_value=(Path("thumbnail.jpg"), 720, 1280, 5),
                ):
                    if method_name == "igtv_upload":
                        return await self.client.igtv_upload(path, "Video title", "caption", configure_timeout=0)
                    return await self.client.clip_upload(path, "caption", configure_timeout=0)
        return await getattr(self.client, method_name)(path, "caption")

    async def assert_upload_returns_configured_result(self, method_name):
        configure_endpoint, media_type, result_type = UPLOAD_CASES[method_name]

        result = await self.upload(method_name)

        self.assertIsInstance(result, result_type)
        self.assertEqual(result.pk, "1")
        self.assertEqual(result.id, "1_1")
        self.assertEqual(result.media_type, media_type)
        self.assertEqual(result.user.username, "example")
        if result_type is Media:
            self.assertEqual(result.caption_text, "caption")
        else:
            self.assertEqual(result.product_type, "story")
        if media_type == 2:
            self.assertEqual(str(result.video_url), "https://example.com/video.mp4")
        if method_name == "album_upload":
            self.assertEqual(len(result.resources), 1)
            self.assertEqual(result.resources[0].pk, "1")
        if method_name == "igtv_upload":
            self.assertEqual(result.title, "Video title")
        self.assertEqual(self.requests, [configure_endpoint])

    async def assert_upload_propagates_configure_error(self, method_name):
        error = ClientNotFoundError("Configure endpoint returned 404", response=Mock(status_code=404))

        with self.assertRaises(ClientNotFoundError) as caught:
            await self.upload(method_name, configure_error=error)

        self.assertIs(caught.exception, error)
        self.assertEqual(self.requests, [UPLOAD_CASES[method_name][0]])

    async def test_photo_upload_returns_media_without_expose(self):
        await self.assert_upload_returns_configured_result("photo_upload")

    async def test_photo_story_upload_returns_story_without_expose(self):
        await self.assert_upload_returns_configured_result("photo_upload_to_story")

    async def test_album_upload_returns_media_without_expose(self):
        await self.assert_upload_returns_configured_result("album_upload")

    async def test_video_upload_returns_media_without_expose(self):
        await self.assert_upload_returns_configured_result("video_upload")

    async def test_video_story_upload_returns_story_without_expose(self):
        await self.assert_upload_returns_configured_result("video_upload_to_story")

    async def test_clip_upload_returns_media_without_expose(self):
        await self.assert_upload_returns_configured_result("clip_upload")

    async def test_igtv_upload_returns_media_without_expose(self):
        await self.assert_upload_returns_configured_result("igtv_upload")

    async def test_photo_upload_propagates_configure_error(self):
        await self.assert_upload_propagates_configure_error("photo_upload")

    async def test_photo_story_upload_propagates_configure_error(self):
        await self.assert_upload_propagates_configure_error("photo_upload_to_story")

    async def test_album_upload_propagates_configure_error(self):
        await self.assert_upload_propagates_configure_error("album_upload")

    async def test_video_upload_propagates_configure_error(self):
        await self.assert_upload_propagates_configure_error("video_upload")

    async def test_video_story_upload_propagates_configure_error(self):
        await self.assert_upload_propagates_configure_error("video_upload_to_story")

    async def test_clip_upload_propagates_configure_error(self):
        await self.assert_upload_propagates_configure_error("clip_upload")

    async def test_igtv_upload_propagates_configure_error(self):
        await self.assert_upload_propagates_configure_error("igtv_upload")

    async def test_explicit_expose_still_requests_experiment_endpoint(self):
        response = {"status": "ok"}
        self.client.private_request = AsyncMock(return_value=response)

        result = await self.client.expose()

        self.assertIs(result, response)
        self.client.private_request.assert_awaited_once_with(
            "qe/expose/",
            {"id": self.client.uuid, "experiment": "ig_android_profile_contextual_feed"},
        )

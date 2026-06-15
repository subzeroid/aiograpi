import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

from aiograpi import Client
from aiograpi.exceptions import ClientForbiddenError
from aiograpi.types import Media, UserShort


class DownloadRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    def _photo_media(self, media_pk="2936202982639873318", thumbnail_url="https://example.com/photo.jpg"):
        return Media(
            pk=media_pk,
            id=f"{media_pk}_50838397751",
            code="Ci_fQ5YsS0m",
            taken_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            media_type=1,
            user=UserShort(
                pk="50838397751",
                username="example",
                profile_pic_url="https://example.com/profile.jpg",
            ),
            like_count=0,
            caption_text="",
            usertags=[],
            sponsor_tags=[],
            thumbnail_url=thumbnail_url,
        )

    def _video_media(self, media_pk="3903542582802212941"):
        return Media(
            pk=media_pk,
            id=f"{media_pk}_50838397751",
            code="DYsK0wViWhN",
            taken_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            media_type=2,
            user=UserShort(
                pk="50838397751",
                username="example",
                profile_pic_url="https://example.com/profile.jpg",
            ),
            like_count=0,
            caption_text="",
            usertags=[],
            sponsor_tags=[],
            video_url="https://example.com/video.mp4",
        )

    async def test_video_download_uses_private_media_info_lookup(self):
        client = Client()
        media = self._video_media()
        expected = Path("/tmp/example.mp4")
        client.media_info = AsyncMock(side_effect=AssertionError("public-first media_info"))
        client.media_info_v1 = AsyncMock(return_value=media)
        client.video_download_by_url = AsyncMock(return_value=expected)

        result = await client.video_download(media.pk, folder="/tmp", overwrite=False)

        client.media_info.assert_not_called()
        client.media_info_v1.assert_awaited_once_with(media.pk)
        client.video_download_by_url.assert_awaited_once_with(
            media.video_url,
            f"example_{media.pk}",
            "/tmp",
            overwrite=False,
        )
        self.assertEqual(result, expected)

    async def test_photo_download_prefers_public_gql_media_info_lookup(self):
        client = Client()
        media_pk = "2936202982639873318"
        public_media = self._photo_media(media_pk, "https://example.com/public-1440.jpg")
        private_media = self._photo_media(media_pk, "https://example.com/private-1080.jpg")
        expected = Path("/tmp/example.jpg")
        client.media_info_gql = AsyncMock(return_value=public_media)
        client.media_info = AsyncMock(return_value=private_media)
        client.photo_download_by_url = AsyncMock(return_value=expected)

        result = await client.photo_download(media_pk, folder="/tmp", overwrite=False)

        client.media_info_gql.assert_awaited_once_with(media_pk)
        client.media_info.assert_not_called()
        client.photo_download_by_url.assert_awaited_once_with(
            str(public_media.thumbnail_url),
            f"example_{media_pk}",
            "/tmp",
            overwrite=False,
        )
        self.assertEqual(result, expected)

    async def test_photo_download_falls_back_to_media_info_when_public_gql_is_gated(self):
        client = Client()
        media_pk = "2936202982639873318"
        private_media = self._photo_media(media_pk, "https://example.com/private-1080.jpg")
        expected = Path("/tmp/example.jpg")
        client.media_info_gql = AsyncMock(side_effect=ClientForbiddenError("gated"))
        client.media_info = AsyncMock(return_value=private_media)
        client.photo_download_by_url = AsyncMock(return_value=expected)

        result = await client.photo_download(media_pk, folder="/tmp", overwrite=False)

        client.media_info_gql.assert_awaited_once_with(media_pk)
        client.media_info.assert_awaited_once_with(media_pk)
        client.photo_download_by_url.assert_awaited_once_with(
            str(private_media.thumbnail_url),
            f"example_{media_pk}",
            "/tmp",
            overwrite=False,
        )
        self.assertEqual(result, expected)

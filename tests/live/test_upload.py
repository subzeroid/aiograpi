import asyncio
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from aiograpi import Client
from aiograpi.exceptions import PhotoConfigureError, PhotoNotUpload
from aiograpi.types import Media
from tests.live.auth_helpers import login_with_timeout
from tests.live.smoke import _fetch_accounts


async def _client_from_test_account(account):
    client = Client()
    settings = dict(account.get("client_settings") or account.get("settings") or {})
    totp_seed = settings.pop("totp_seed", None) or account.get("totp_seed")
    client.set_settings(settings)
    if account.get("proxy"):
        client.set_proxy(account["proxy"])
    login_kwargs = {
        "username": account["username"],
        "password": account["password"],
        "relogin": True,
    }
    if totp_seed:
        login_kwargs["verification_code"] = client.totp_generate_code(totp_seed)
    await login_with_timeout(client, **login_kwargs)
    client._user_id = account.get("user_id")
    return client


class ClientUploadCoauthorLiveTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.test_accounts_url = os.getenv("TEST_ACCOUNTS_URL")
        if not self.test_accounts_url:
            self.skipTest("TEST_ACCOUNTS_URL is required for coauthor upload live tests")

    def copy_media_fixture(self, source):
        source = Path(source)
        with tempfile.NamedTemporaryFile(delete=False, suffix=source.suffix) as tmp:
            path = Path(tmp.name)
        shutil.copyfile(source, path)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        return path

    async def uploaded_media_payload(self, client, media, attempts=5, delay=3):
        last_error = None
        for attempt in range(attempts):
            if attempt:
                await asyncio.sleep(delay)
            try:
                result = await client.private_request(f"media/{media.pk}/info/")
                items = result.get("items") or []
                self.assertTrue(items, "media info did not return items")
                return items[0]
            except Exception as exc:
                last_error = exc
        self.fail(f"Uploaded media {media.id} was not accessible after {attempts} media_info attempts: {last_error}")

    async def assertUploadedMediaAccessible(self, client, media, media_type=None, product_type=None, caption_text=None):
        self.assertIsInstance(media, Media)
        payload = await self.uploaded_media_payload(client, media)
        self.assertEqual(str(payload.get("pk")), str(media.pk))
        self.assertEqual(str(payload.get("id")), str(media.id))
        if media_type is not None:
            self.assertEqual(payload.get("media_type"), media_type)
        if product_type is not None:
            self.assertEqual(payload.get("product_type"), product_type)
        if caption_text is not None:
            self.assertEqual((payload.get("caption") or {}).get("text", ""), caption_text)
        return payload

    def make_clip_mp4(self):
        try:
            import imageio_ffmpeg
        except ImportError:
            self.skipTest("imageio_ffmpeg is required to generate a Reel fixture")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
            path = Path(tmp.name)
        self.addCleanup(lambda: path.unlink(missing_ok=True))

        try:
            subprocess.run(
                [
                    imageio_ffmpeg.get_ffmpeg_exe(),
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "color=c=black:s=720x1280:r=30:d=4",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=440:duration=4",
                    "-shortest",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "64k",
                    str(path),
                ],
                check=True,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            self.skipTest(f"Could not generate Reel fixture: {exc}")
        return path

    def make_cover_fixture(self, color):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is required to generate a cover fixture")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            path = Path(tmp.name)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        Image.new("RGB", (720, 1280), color).save(path, quality=95)
        return path

    async def test_photo_upload_with_coauthor_user_ids(self):
        path = self.copy_media_fixture("examples/kanada.jpg")
        self.assertIsInstance(path, Path)
        accounts = await _fetch_accounts(self.test_accounts_url, count=50)
        coauthor_user_ids = [str(account.get("user_id")) for account in accounts if account.get("user_id")]
        if len(coauthor_user_ids) < 2:
            self.skipTest("At least two TEST_ACCOUNTS_URL accounts with user_id are required")

        login_failures = {}
        upload_failures = {}
        for account in accounts:
            try:
                uploader = await _client_from_test_account(account)
            except Exception as exc:
                login_failures[exc.__class__.__name__] = login_failures.get(exc.__class__.__name__, 0) + 1
                continue

            uploader_id = str(uploader.user_id or (await uploader.account_info()).pk)
            coauthor_user_id = next((user_id for user_id in coauthor_user_ids if user_id != uploader_id), None)
            if not coauthor_user_id:
                continue

            media = None
            try:
                caption_text = f"Test caption for coauthor photo {int(time.time())}"
                media = await uploader.photo_upload(path, caption_text, coauthor_user_ids=[coauthor_user_id])
                self.assertIsInstance(media, Media)
                self.assertEqual(media.caption_text, caption_text)
                await self.assertUploadedMediaAccessible(uploader, media, media_type=1, caption_text=caption_text)
                return
            except PhotoConfigureError:
                raise
            except PhotoNotUpload as exc:
                upload_failures[exc.__class__.__name__] = upload_failures.get(exc.__class__.__name__, 0) + 1
                continue
            finally:
                if media:
                    self.assertTrue(await uploader.media_delete(media.id))

        self.skipTest(
            "No upload-capable test account was available "
            f"(login_failures={login_failures}, upload_failures={upload_failures})"
        )

    async def test_clip_upload_with_topics(self):
        path = self.make_clip_mp4()
        thumbnail = self.make_cover_fixture((20, 20, 20))
        self.assertIsInstance(path, Path)
        accounts = await _fetch_accounts(self.test_accounts_url, count=5)
        login_failures = {}
        uploader = None
        for account in accounts:
            try:
                uploader = await _client_from_test_account(account)
                break
            except Exception as exc:
                login_failures[exc.__class__.__name__] = login_failures.get(exc.__class__.__name__, 0) + 1
        if uploader is None:
            self.skipTest(f"No usable test account was available (login_failures={login_failures})")

        topics = await uploader.clip_interest_topics()
        if not topics:
            self.skipTest("Instagram did not return Reel topics")
        topic = next((item for item in topics if item.get("name") == "Technology"), topics[0])
        topic_id = str(topic["fit_id"])
        media = None
        try:
            caption_text = f"Upload clip with topic {int(time.time())}"
            media = await uploader.clip_upload(path, caption_text, thumbnail=thumbnail, topics=[topic_id])
            self.assertIsInstance(media, Media)
            self.assertEqual(media.caption_text, caption_text)
            payload = await self.assertUploadedMediaAccessible(
                uploader,
                media,
                media_type=2,
                product_type="clips",
                caption_text=caption_text,
            )
            self.assertTrue(payload.get("video_versions"))
        finally:
            if media:
                self.assertTrue(await uploader.media_delete(media.id))

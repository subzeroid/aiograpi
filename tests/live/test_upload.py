import asyncio
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from aiograpi import Client
from aiograpi.exceptions import CrosspostingDestinationError, PhotoConfigureError, PhotoNotUpload
from aiograpi.types import Media, UserShort, Usertag
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


async def _client_with_destination(accounts, destination_method, *, initial_client=None):
    """Find a login-capable account that also exposes the requested destination."""
    failures = {}

    async def resolve(client):
        try:
            destination = await getattr(client, destination_method)()
            if not destination:
                raise CrosspostingDestinationError("destination resolver returned no destination")
            return client, destination
        except CrosspostingDestinationError as exc:
            name = exc.__class__.__name__
            failures[name] = failures.get(name, 0) + 1
            return None

    if initial_client is not None:
        resolved = await resolve(initial_client)
        if resolved is not None:
            return resolved

    for account in accounts:
        try:
            client = await _client_from_test_account(account)
        except Exception as exc:
            name = exc.__class__.__name__
            failures[name] = failures.get(name, 0) + 1
            continue
        resolved = await resolve(client)
        if resolved is not None:
            return resolved

    raise CrosspostingDestinationError(
        f"No usable test account exposed {destination_method} (failure_types={failures})"
    )


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

    async def assertPhotoUsertagsAccessible(self, client, media, expected_usertags, attempts=8, delay=5):
        last_tags = []
        for attempt in range(attempts):
            if attempt:
                await asyncio.sleep(delay)
            info = await client.media_info_v1(media.pk)
            last_tags = info.usertags
            if len(last_tags) < len(expected_usertags):
                continue
            for actual_tag, expected_tag in zip(last_tags, expected_usertags):
                if (
                    str(actual_tag.user.pk) != str(expected_tag.user.pk)
                    or actual_tag.x != expected_tag.x
                    or actual_tag.y != expected_tag.y
                ):
                    break
            else:
                return info
        self.fail(f"Photo usertags were not visible after {attempts} media_info_v1 attempts: {last_tags}")

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

    async def test_photo_upload_with_usertags_visible_after_media_info(self):
        path = self.copy_media_fixture("examples/kanada.jpg")
        self.assertIsInstance(path, Path)
        accounts = await _fetch_accounts(self.test_accounts_url, count=50)

        login_failures = {}
        upload_failures = {}
        for account in accounts:
            try:
                uploader = await _client_from_test_account(account)
            except Exception as exc:
                login_failures[exc.__class__.__name__] = login_failures.get(exc.__class__.__name__, 0) + 1
                continue

            media = None
            try:
                instagram = await uploader.user_info_by_username_v1("instagram")
                usertag = Usertag(
                    user=UserShort(
                        pk=instagram.pk,
                        username=instagram.username,
                        full_name=instagram.full_name,
                        profile_pic_url=instagram.profile_pic_url,
                        is_private=instagram.is_private,
                    ),
                    x=0.5,
                    y=0.5,
                )
                caption_text = f"Test caption for photo usertags {int(time.time())}"
                media = await uploader.photo_upload(path, caption_text, usertags=[usertag])
                self.assertIsInstance(media, Media)
                self.assertEqual(media.caption_text, caption_text)
                info = await self.assertPhotoUsertagsAccessible(uploader, media, [usertag])
                self.assertEqual(info.caption_text, caption_text)
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

    async def test_clip_upload_show_preview_in_feed_false_live(self):
        path = self.make_clip_mp4()
        thumbnail = self.make_cover_fixture((30, 30, 30))
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

        media = None
        try:
            caption_text = f"Upload clip hidden preview {int(time.time())}"
            media = await uploader.clip_upload(
                path,
                caption_text,
                thumbnail=thumbnail,
                show_preview_in_feed=False,
            )
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


class ClientFacebookReelCrosspostLiveTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        test_accounts_url = os.getenv("TEST_ACCOUNTS_URL")
        if not test_accounts_url:
            self.skipTest("TEST_ACCOUNTS_URL is required for Reel Facebook crosspost live tests")
        accounts = await _fetch_accounts(test_accounts_url, count=20)
        login_failures = {}
        for index, account in enumerate(accounts):
            try:
                self.cl = await _client_from_test_account(account)
                self.remaining_accounts = accounts[index + 1 :]
                return
            except Exception as exc:
                login_failures[exc.__class__.__name__] = login_failures.get(exc.__class__.__name__, 0) + 1
        self.skipTest(f"No usable test account was available (login_failures={login_failures})")

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

    async def uploaded_media_payload(self, media, attempts=5, delay=3):
        last_error = None
        for attempt in range(attempts):
            if attempt:
                await asyncio.sleep(delay)
            try:
                result = await self.cl.private_request(f"media/{media.pk}/info/")
                items = result.get("items") or []
                self.assertTrue(items, "media info did not return items")
                return items[0]
            except Exception as exc:
                last_error = exc
        self.fail(f"Uploaded media {media.id} was not accessible after {attempts} attempts: {last_error}")

    async def assert_uploaded_media_accessible(
        self,
        media,
        *,
        media_type=None,
        product_type=None,
        caption_text=None,
    ):
        self.assertIsInstance(media, Media)
        payload = await self.uploaded_media_payload(media)
        self.assertEqual(str(payload.get("pk")), str(media.pk))
        self.assertEqual(str(payload.get("id")), str(media.id))
        if media_type is not None:
            self.assertEqual(payload.get("media_type"), media_type)
        if product_type is not None:
            self.assertEqual(payload.get("product_type"), product_type)
        if caption_text is not None:
            self.assertEqual((payload.get("caption") or {}).get("text", ""), caption_text)
        return payload

    async def test_clip_share_to_fb_unified_config_live(self):
        config = await self.cl.clip_share_to_fb_unified_config()

        self.assertEqual(config.get("status"), "ok")
        data = config.get("data")
        self.assertIsInstance(data, dict)
        roots = [value for key, value in data.items() if "xcxp_unified_crossposting_configs_root" in str(key)]
        self.assertTrue(roots, "Android unified config response omitted its root field")
        self.assertIsInstance(
            roots[0],
            dict,
            "Android unified config returned a null Facebook cross-posting root",
        )

    async def test_clip_upload_share_to_facebook_live(self):
        try:
            self.cl, destination = await _client_with_destination(
                self.remaining_accounts,
                "clip_share_to_fb_destination",
                initial_client=self.cl,
            )
        except CrosspostingDestinationError as exc:
            self.skipTest(f"No confirmed Facebook Reel destination available: {exc}")

        config = await self.cl.clip_share_to_fb_config()
        self.assertEqual(config.get("status"), "ok")
        extra_data = await self.cl.clip_share_to_fb_extra_data()
        self.assertEqual(extra_data["share_to_facebook"], "1")
        self.assertTrue(extra_data["share_to_facebook_reels"])
        self.assertTrue(extra_data["is_reel_shared_to_fb"])
        self.assertTrue(extra_data["share_to_fb_destination_id"])
        self.assertIn(extra_data["share_to_fb_destination_type"], {"USER", "PAGE"})
        self.assertEqual(extra_data["cross_app_share_type"], "2")
        self.assertEqual(extra_data["xpost_surface"], "IG_REELS_COMPOSER")
        self.assertEqual(extra_data["no_token_crosspost"], "1")
        self.assertTrue(extra_data["attempt_id"])
        self.assertTrue(destination["destination_id"])
        self.assertIn(destination["destination_type"], {"USER", "PAGE"})
        if destination.get("destination_audience_type"):
            self.assertIsInstance(destination["destination_audience_type"], str)

        path = self.make_clip_mp4()
        media = None
        try:
            caption_text = f"Facebook Reel crosspost live test {int(time.time())}"
            media = await self.cl.clip_upload(
                path,
                caption_text,
                share_to_facebook=True,
                fb_destination_id=destination["destination_id"],
                fb_destination_type=destination["destination_type"],
            )
            payload = await self.assert_uploaded_media_accessible(
                media,
                media_type=2,
                product_type="clips",
                caption_text=caption_text,
            )
            for attempt in range(8):
                clips_metadata = payload.get("clips_metadata") or {}
                crosspost = {str(item).upper() for item in payload.get("crosspost") or []}
                if clips_metadata.get("is_shared_to_fb") or payload.get("has_shared_to_fb") or "FB" in crosspost:
                    break
                if attempt < 7:
                    await asyncio.sleep(5)
                    payload = await self.uploaded_media_payload(media)
            self.assertTrue(
                (payload.get("clips_metadata") or {}).get("is_shared_to_fb")
                or payload.get("has_shared_to_fb")
                or "FB" in {str(item).upper() for item in payload.get("crosspost") or []},
                "Instagram did not confirm Facebook Reel cross-posting",
            )
        finally:
            if media:
                self.assertTrue(await self.cl.media_delete(media.id))


class ClientFeedCrosspostLiveTestCase(unittest.IsolatedAsyncioTestCase):
    photo_path = Path("examples/kanada.jpg")

    async def asyncSetUp(self):
        self.test_accounts_url = os.getenv("TEST_ACCOUNTS_URL")
        if not self.test_accounts_url:
            self.skipTest("TEST_ACCOUNTS_URL is required for feed crosspost live tests")
        accounts = await _fetch_accounts(self.test_accounts_url, count=20)
        login_failures = {}
        for index, account in enumerate(accounts):
            try:
                self.cl = await _client_from_test_account(account)
                self.remaining_accounts = accounts[index + 1 :]
                return
            except Exception as exc:
                login_failures[exc.__class__.__name__] = login_failures.get(exc.__class__.__name__, 0) + 1
        self.skipTest(f"No usable test account was available (login_failures={login_failures})")

    async def uploaded_media_payload(self, media, attempts=5, delay=3):
        last_error = None
        for attempt in range(attempts):
            if attempt:
                await asyncio.sleep(delay)
            try:
                result = await self.cl.private_request(f"media/{media.pk}/info/")
                items = result.get("items") or []
                self.assertTrue(items, "media info did not return items")
                return items[0]
            except Exception as exc:
                last_error = exc
        self.fail(f"Uploaded media {media.id} was not accessible after {attempts} attempts: {last_error}")

    async def test_media_share_to_fb_unified_config_live(self):
        config = await self.cl.media_share_to_fb_unified_config()

        self.assertEqual(config.get("status"), "ok")
        data = config.get("data")
        self.assertIsInstance(data, dict)
        roots = [value for key, value in data.items() if "xcxp_unified_crossposting_configs_root" in str(key)]
        self.assertTrue(roots, "Android unified config response omitted its root field")
        self.assertIsInstance(
            roots[0],
            dict,
            "Android unified config returned a null Facebook cross-posting root",
        )

    async def test_media_share_to_fb_connected_services_config_live(self):
        config = await self.cl.media_share_to_fb_connected_services_config()

        self.assertEqual(config.get("status"), "ok")
        data = config.get("data")
        self.assertIsInstance(data, dict)
        roots = [value for key, value in data.items() if "fx_service_cache" in str(key)]
        self.assertTrue(roots, "Android connected-services response omitted its root field")
        self.assertIsInstance(roots[0], dict)

    async def test_media_share_to_threads_config_live(self):
        config = await self.cl.media_share_to_threads_config()

        data = config.get("data")
        self.assertIsInstance(data, dict)
        roots = [value for key, value in data.items() if "xcxp_fetch_linked_threads_profile" in str(key)]
        self.assertTrue(roots, "Android linked-Threads response omitted its root field")

    async def test_photo_upload_share_to_facebook_live(self):
        try:
            self.cl, destination = await _client_with_destination(
                self.remaining_accounts,
                "media_share_to_fb_destination",
                initial_client=self.cl,
            )
        except CrosspostingDestinationError as exc:
            self.skipTest(f"No confirmed Facebook Feed destination available: {exc}")

        self.assertTrue(destination["destination_id"])
        self.assertIn(destination["destination_type"], {"USER", "PAGE"})

        media = None
        try:
            caption = f"Facebook Feed crosspost live test {int(time.time())}"
            media = await self.cl.photo_upload(
                self.photo_path,
                caption,
                share_to_facebook=True,
                fb_destination_id=destination["destination_id"],
                fb_destination_type=destination["destination_type"],
            )
            payload = await self.uploaded_media_payload(media)
            self.assertEqual((payload.get("caption") or {}).get("text", ""), caption)
            self.assertTrue(
                "FB" in {str(item).upper() for item in media.crosspost} or bool(media.has_shared_to_fb),
                "Instagram configure response did not confirm Facebook cross-posting",
            )
        finally:
            if media:
                self.assertTrue(await self.cl.media_delete(media.id))

    async def test_photo_upload_share_to_threads_live(self):
        try:
            self.cl, destination = await _client_with_destination(
                self.remaining_accounts,
                "media_share_to_threads_destination",
                initial_client=self.cl,
            )
        except CrosspostingDestinationError as exc:
            self.skipTest(f"No linked Threads profile available: {exc}")

        self.assertTrue(destination["destination_id"])

        media = None
        try:
            caption = f"Threads crosspost live test {int(time.time())}"
            media = await self.cl.photo_upload(
                self.photo_path,
                caption,
                share_to_threads=True,
                threads_destination_id=destination["destination_id"],
            )
            payload = await self.uploaded_media_payload(media)
            self.assertEqual((payload.get("caption") or {}).get("text", ""), caption)
            self.assertTrue(
                {"THREADS", "BARCELONA"} & {str(item).upper() for item in media.crosspost},
                "Instagram configure response did not confirm Threads cross-posting",
            )
        finally:
            if media:
                self.assertTrue(await self.cl.media_delete(media.id))

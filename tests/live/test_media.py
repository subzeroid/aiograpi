import asyncio
import logging
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from PIL import Image

from aiograpi.exceptions import (
    ClientBadRequestError,
    ClientForbiddenError,
    ClientLoginRequired,
    ClientNotFoundError,
    ClientThrottledError,
    ClientUnauthorizedError,
)
from aiograpi.types import Media
from tests import legacy as _legacy
from tests.live.smoke import _fetch_accounts, _login_first_usable

logger = logging.getLogger("aiograpi.tests")

PUBLIC_MEDIA_FETCH_ERRORS = (
    ClientBadRequestError,
    ClientForbiddenError,
    ClientLoginRequired,
    ClientNotFoundError,
    ClientThrottledError,
    ClientUnauthorizedError,
)


class ClientPinnedMediaLiveTestCase(_legacy.ClientPrivateTestCase):
    def make_photo_png(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            path = Path(tmp.name)
        Image.new("RGB", (640, 800), (37, 99, 235)).save(path)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        return path

    async def expected_pinned_media_pks(self, client):
        user_id = str(client.user_id)
        nav_chain = "MainFeedFragment:feed_timeline:12:main_home::,UserDetailFragment:profile:13:button::"
        response = await client.private_request(
            f"feed/user/{user_id}/",
            params={
                "exclude_comment": "true",
                "only_fetch_first_carousel_media": "false",
            },
            headers={"X-IG-Nav-Chain": nav_chain},
        )
        return [
            str(item["pk"])
            for item in response.get("items") or []
            if user_id in map(str, item.get("timeline_pinned_user_ids") or ())
        ]

    async def test_user_pinned_medias_upload_pin_readback_unpin_delete_live(self):
        client = self.cl
        photo_path = self.make_photo_png()
        media = None
        pinned = False

        try:
            media = await client.photo_upload(
                photo_path,
                f"aiograpi pinned media live {int(time.time())}",
            )
            self.assertIsInstance(media, Media)
            self.assertTrue(await client.media_pin(media.pk))
            pinned = True

            expected_pks = []
            actual_pks = []
            for _ in range(8):
                expected_pks = await self.expected_pinned_media_pks(client)
                actual_pks = [str(item.pk) for item in await client.user_pinned_medias(client.user_id)]
                if str(media.pk) in expected_pks and actual_pks == expected_pks:
                    break
                await asyncio.sleep(3)

            self.assertIn(str(media.pk), expected_pks)
            self.assertEqual(actual_pks, expected_pks)

            self.assertTrue(await client.media_unpin(media.pk))
            pinned = False
            for _ in range(8):
                actual_pks = [str(item.pk) for item in await client.user_pinned_medias(client.user_id)]
                if str(media.pk) not in actual_pks:
                    break
                await asyncio.sleep(3)
            self.assertNotIn(str(media.pk), actual_pks)
        finally:
            if media is not None:
                if pinned:
                    try:
                        await client.media_unpin(media.pk)
                    except Exception as exc:
                        logger.warning("Pinned media unpin cleanup failed: %s", exc)
                try:
                    await client.media_delete(media.id)
                except Exception as exc:
                    logger.warning("Pinned media delete cleanup failed: %s", exc)


class ClientMediaCountAliasLiveTestCase(unittest.IsolatedAsyncioTestCase):
    async def live_media(self, code):
        test_accounts_url = os.getenv("TEST_ACCOUNTS_URL")
        if not test_accounts_url:
            self.skipTest("TEST_ACCOUNTS_URL is required for media count alias live tests")
        accounts = await _fetch_accounts(test_accounts_url, count=20)
        last_error = None
        for account in accounts:
            cl = await _login_first_usable([account])
            if cl is None:
                continue
            media_pk = cl.media_pk_from_code(code)
            captured_payload = {}
            original_doc_id_request = cl.public_doc_id_graphql_request

            async def capture_doc_id_payload(*args, **kwargs):
                result = await original_doc_id_request(*args, **kwargs)
                payload = result.get("xdt_shortcode_media") or result.get("shortcode_media")
                if payload:
                    captured_payload.update(payload)
                return result

            try:
                with (
                    patch.object(
                        cl,
                        "public_graphql_request",
                        AsyncMock(side_effect=ClientForbiddenError("force doc_id media fallback")),
                    ),
                    patch.object(cl, "public_doc_id_graphql_request", AsyncMock(side_effect=capture_doc_id_payload)),
                ):
                    media = await cl.media_info_gql(media_pk)
            except PUBLIC_MEDIA_FETCH_ERRORS as exc:
                last_error = f"{type(exc).__name__}: {str(exc)[:120]}"
                continue
            if captured_payload:
                return media, captured_payload
            last_error = "public doc_id media payload was empty"
        self.skipTest(f"Could not fetch public doc_id media payload from test accounts: {last_error}")

    async def test_media_info_gql_normalizes_live_video_count_aliases(self):
        code = "C_BM2yAN4Rm"
        media, payload = await self.live_media(code)
        self.assertIn(payload.get("__typename"), {"GraphVideo", "XDTGraphVideo"})
        self.assertIn("video_view_count", payload)
        self.assertIn("video_play_count", payload)
        self.assertEqual(media.view_count, payload["video_view_count"])
        self.assertEqual(media.play_count, payload["video_play_count"])

    async def test_media_info_gql_normalizes_live_xdt_sidecar_children(self):
        code = "Cu59OMFPQde"
        media, payload = await self.live_media(code)

        self.assertIn(payload.get("__typename"), {"GraphSidecar", "XDTGraphSidecar"})
        self.assertEqual(media.media_type, 8)
        self.assertGreaterEqual(len(media.resources), 1)
        self.assertTrue(all(resource.media_type in {1, 2} for resource in media.resources))


class ClientClipMashupInfoLiveTestCase(unittest.IsolatedAsyncioTestCase):
    async def live_client(self):
        test_accounts_url = os.getenv("TEST_ACCOUNTS_URL")
        if not test_accounts_url:
            self.skipTest("TEST_ACCOUNTS_URL is required for clip live tests")
        accounts = await _fetch_accounts(test_accounts_url, count=20)
        cl = await _login_first_usable(accounts)
        if cl is None:
            self.skipTest("Could not login with any test account")
        cl.request_timeout = 0
        return cl

    async def test_clip_mashup_info_live(self):
        cl = await self.live_client()
        media_pk = cl.media_pk_from_code("C_BM2yAN4Rm")

        result = await cl.clip_mashup_info(media_pk)

        self.assertEqual(result.get("status"), "ok")
        mashup_info = result.get("mashup_info")
        self.assertIsInstance(mashup_info, dict)
        self.assertIn("is_reuse_allowed", mashup_info)
        self.assertIn("mashups_allowed", mashup_info)

    async def test_clip_seen_live(self):
        cl = await self.live_client()
        try:
            medias = await cl.user_clips_v1("25025320", amount=3)
        except Exception as exc:
            self.skipTest(f"Could not fetch public Instagram clips: {type(exc).__name__}: {str(exc)[:120]}")
        if not medias:
            self.skipTest("Public Instagram clips feed returned no media")

        self.assertTrue(await cl.clip_seen([medias[0].id]))

import os
import unittest
from unittest.mock import AsyncMock, patch

from aiograpi.exceptions import (
    ClientBadRequestError,
    ClientForbiddenError,
    ClientLoginRequired,
    ClientNotFoundError,
    ClientThrottledError,
    ClientUnauthorizedError,
)
from tests.live.smoke import _fetch_accounts, _login_first_usable

PUBLIC_MEDIA_FETCH_ERRORS = (
    ClientBadRequestError,
    ClientForbiddenError,
    ClientLoginRequired,
    ClientNotFoundError,
    ClientThrottledError,
    ClientUnauthorizedError,
)


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

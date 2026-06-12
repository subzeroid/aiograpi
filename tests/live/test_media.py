import os
import unittest

from aiograpi.exceptions import (
    ClientBadRequestError,
    ClientForbiddenError,
    ClientLoginRequired,
    ClientNotFoundError,
    ClientThrottledError,
    ClientUnauthorizedError,
)
from aiograpi.extractors import extract_media_gql
from aiograpi.mixins.media import MEDIA_INFO_DOC_ID
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
    async def live_media_payload(self, code):
        test_accounts_url = os.getenv("TEST_ACCOUNTS_URL")
        if not test_accounts_url:
            self.skipTest("TEST_ACCOUNTS_URL is required for media count alias live tests")
        accounts = await _fetch_accounts(test_accounts_url, count=20)
        last_error = None
        for account in accounts:
            cl = await _login_first_usable([account])
            if cl is None:
                continue
            try:
                result = await cl.public_doc_id_graphql_request(
                    MEDIA_INFO_DOC_ID,
                    {"shortcode": code},
                    referer=f"https://www.instagram.com/p/{code}/",
                )
            except PUBLIC_MEDIA_FETCH_ERRORS as exc:
                last_error = f"{type(exc).__name__}: {str(exc)[:120]}"
                continue
            payload = result.get("xdt_shortcode_media") or result.get("shortcode_media")
            if payload:
                return payload
            last_error = f"public doc_id media payload was empty: {result}"
        self.skipTest(f"Could not fetch public doc_id media payload from test accounts: {last_error}")

    async def test_extract_media_gql_normalizes_live_video_count_aliases(self):
        code = "C_BM2yAN4Rm"
        payload = await self.live_media_payload(code)
        self.assertIn(payload.get("__typename"), {"GraphVideo", "XDTGraphVideo"})
        self.assertIn("video_view_count", payload)
        self.assertIn("video_play_count", payload)

        media = extract_media_gql(payload)

        self.assertEqual(media.view_count, payload["video_view_count"])
        self.assertEqual(media.play_count, payload["video_play_count"])

import os
import unittest

from aiograpi.extractors import extract_media_gql
from aiograpi.mixins.media import MEDIA_INFO_DOC_ID
from tests.live.smoke import _fetch_accounts, _login_first_usable


class ClientMediaCountAliasLiveTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        test_accounts_url = os.getenv("TEST_ACCOUNTS_URL")
        if not test_accounts_url:
            self.skipTest("TEST_ACCOUNTS_URL is required for media count alias live tests")
        accounts = await _fetch_accounts(test_accounts_url, count=20)
        self.cl = await _login_first_usable(accounts)
        if self.cl is None:
            self.skipTest("No usable fresh account returned")

    async def test_extract_media_gql_normalizes_live_video_count_aliases(self):
        code = "C_BM2yAN4Rm"
        result = await self.cl.public_doc_id_graphql_request(
            MEDIA_INFO_DOC_ID,
            {"shortcode": code},
            referer=f"https://www.instagram.com/p/{code}/",
        )
        payload = result.get("xdt_shortcode_media") or result.get("shortcode_media")
        self.assertTrue(payload, f"public doc_id media payload was empty: {result}")
        self.assertIn(payload.get("__typename"), {"GraphVideo", "XDTGraphVideo"})
        self.assertIn("video_view_count", payload)
        self.assertIn("video_play_count", payload)

        media = extract_media_gql(payload)

        self.assertEqual(media.view_count, payload["video_view_count"])
        self.assertEqual(media.play_count, payload["video_play_count"])

import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from PIL import Image

from aiograpi import Client
from aiograpi.exceptions import ClientError
from tests.live.smoke import _fetch_accounts


class ClientPhotoDownloadLiveTestCase(unittest.IsolatedAsyncioTestCase):
    async def photo_clients(self, errors):
        try:
            import curl_adapter  # noqa: F401
        except ImportError:
            pass
        else:
            yield (
                "anonymous/curl",
                Client(
                    public_transport="curl",
                    request_timeout=1,
                    public_request_retries_count=1,
                ),
            )

        yield (
            "anonymous/requests",
            Client(
                public_transport="requests",
                request_timeout=1,
                public_request_retries_count=1,
            ),
        )

        test_accounts_url = os.getenv("TEST_ACCOUNTS_URL")
        if not test_accounts_url:
            return

        try:
            accounts = await _fetch_accounts(test_accounts_url, count=3)
        except Exception as exc:
            errors.append(f"saved-session/fetch: {exc.__class__.__name__}")
            return

        for idx, account in enumerate(accounts[:3], start=1):
            settings = dict(account.get("client_settings") or account.get("settings") or {})
            settings.pop("totp_seed", None)
            yield (
                f"saved-session/{idx}",
                Client(
                    settings=settings,
                    proxy=os.getenv("IG_PROXY") or account.get("proxy"),
                    override_app_version=True,
                    request_timeout=1,
                    public_request_retries_count=1,
                ),
            )

    async def test_photo_download_public_highest_resolution_live(self):
        media_pk = Client().media_pk_from_code("Ci_fQ5YsS0m")
        errors = []
        async for label, cl in self.photo_clients(errors):
            try:
                media = await cl.media_info_gql(media_pk)
                self.assertEqual(media.media_type, 1)
                self.assertTrue(media.thumbnail_url)
                cl.request_timeout = 20
                with tempfile.TemporaryDirectory() as tmpdir:
                    with (
                        patch.object(cl, "media_info_gql", AsyncMock(return_value=media)) as media_info_gql,
                        patch.object(
                            cl,
                            "media_info",
                            AsyncMock(side_effect=AssertionError("media_info fallback used")),
                        ),
                    ):
                        path = await cl.photo_download(media_pk, folder=tmpdir)
                    media_info_gql.assert_awaited_once_with(media_pk)
                    with Image.open(path) as image:
                        width, height = image.size
            except ClientError as exc:
                errors.append(f"{label}: {exc.__class__.__name__}")
                continue
            break
        else:
            self.skipTest("Instagram public media info endpoint is gated: " + "; ".join(errors))

        self.assertGreaterEqual(width, 1080)
        self.assertGreaterEqual(height, 1080)

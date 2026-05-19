import unittest
from unittest.mock import AsyncMock

from aiograpi import Client
from aiograpi.utils.serialization import dumps


class BloksRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    def build_client(self):
        client = Client()
        client.uuid = "uuid-1"
        client.bloks_versioning_id = "bloks-version"
        return client

    async def test_bloks_async_action_posts_unsigned_bloks_payload(self):
        client = self.build_client()
        params = {"server_params": {"flow": "example_flow"}}
        expected = {"status": "ok"}
        client.private_request = AsyncMock(return_value=expected)

        result = await client.bloks_async_action("com.example.action", params)

        self.assertEqual(result, expected)
        client.private_request.assert_awaited_once_with(
            "bloks/async_action/com.example.action/",
            data={
                "params": dumps(params),
                "_uuid": "uuid-1",
                "bk_client_context": dumps({"bloks_version": "bloks-version", "styles_id": "instagram"}),
                "bloks_versioning_id": "bloks-version",
            },
            with_signature=False,
        )

    async def test_bloks_fxcal_link_reels_share_uses_current_flow_payload(self):
        client = self.build_client()
        expected = {"status": "ok"}
        client.bloks_async_action = AsyncMock(return_value=expected)

        result = await client.bloks_fxcal_link_reels_share(cds_client_value=2)

        self.assertEqual(result, expected)
        client.bloks_async_action.assert_awaited_once_with(
            "com.bloks.www.fxcal.link.async",
            {
                "server_params": {
                    "flow": "ig_fb_reels_composer_rowshare",
                    "logging_event": "linking_flow_initiated",
                    "cds_client_value": 2,
                    "opaque_verified_native_auth_data": None,
                    "native_auth_data": [],
                    "account_type": 0,
                }
            },
            bloks_versioning_id="",
        )

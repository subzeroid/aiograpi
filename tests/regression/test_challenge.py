import unittest
from unittest.mock import AsyncMock

from aiograpi import Client
from aiograpi.exceptions import ChallengeRequired


class ChallengeRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_native_flow_opaque_challenge_fails_fast_before_legacy_resolve(self):
        client = Client()
        last_json = {
            "message": "challenge_required",
            "challenge": {
                "api_path": "/challenge/opaque-user/opaque-nonce/",
                "native_flow": True,
                "challenge_context": "opaque-context",
            },
            "status": "fail",
        }
        client._send_private_request = AsyncMock()
        client.challenge_resolve_simple = AsyncMock(return_value=True)

        with self.assertRaises(ChallengeRequired) as cm:
            await client.challenge_resolve(last_json)

        self.assertIn("native challenge flow", str(cm.exception))
        client._send_private_request.assert_not_called()
        client.challenge_resolve_simple.assert_not_called()

    async def test_challenge_resolve_normalizes_prefixed_api_challenge_path(self):
        client = Client()
        client.uuid = "uuid-1"
        client.android_device_id = "android-1"
        client._send_private_request = AsyncMock()
        client.challenge_resolve_simple = AsyncMock(return_value=True)
        last_json = {
            "message": "challenge_required",
            "challenge": {"api_path": "/api/challenge/12345/nonce-code/"},
            "status": "fail",
        }

        result = await client.challenge_resolve(last_json)

        self.assertTrue(result)
        self.assertEqual(client._send_private_request.call_args.args[0], "challenge/12345/nonce-code/")
        client.challenge_resolve_simple.assert_awaited_once_with("/challenge/12345/nonce-code/")

    async def test_challenge_resolve_normalizes_prefixed_api_v1_challenge_path(self):
        client = Client()
        client.uuid = "uuid-1"
        client.android_device_id = "android-1"
        client._send_private_request = AsyncMock()
        client.challenge_resolve_simple = AsyncMock(return_value=True)
        last_json = {
            "message": "challenge_required",
            "challenge": {"api_path": "/api/v1/challenge/12345/nonce-code/"},
            "status": "fail",
        }

        result = await client.challenge_resolve(last_json)

        self.assertTrue(result)
        self.assertEqual(client._send_private_request.call_args.args[0], "challenge/12345/nonce-code/")
        client.challenge_resolve_simple.assert_awaited_once_with("/challenge/12345/nonce-code/")

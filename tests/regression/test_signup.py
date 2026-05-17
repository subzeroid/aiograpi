import unittest
from unittest.mock import AsyncMock, Mock

from aiograpi import Client
from aiograpi.exceptions import ClientError


class SignupHelperRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_challenge_api_rejects_external_api_path(self):
        client = Client()
        client.uuid = "uuid"
        client.android_device_id = "android-id"
        client.private.get = AsyncMock()

        for api_path in ("@attacker.example/steal", "//attacker.example/steal"):
            with self.subTest(api_path=api_path):
                with self.assertRaises(ClientError):
                    await client.challenge_api(
                        {
                            "api_path": api_path,
                            "challenge_context": "{}",
                        }
                    )

        client.private.get.assert_not_awaited()

    async def test_challenge_captcha_rejects_external_api_path_before_solver(self):
        client = Client()
        client.captcha_resolve = AsyncMock(side_effect=AssertionError("solver should not be called"))
        client.private.post = AsyncMock()

        with self.assertRaises(ClientError):
            await client.challenge_captcha(
                {
                    "api_path": "@attacker.example/steal",
                    "fields": {"sitekey": "site-key"},
                    "challengeType": "RecaptchaChallengeForm",
                }
            )

        client.captcha_resolve.assert_not_awaited()
        client.private.post.assert_not_awaited()

    async def test_challenge_submit_phone_number_rejects_external_forward_path(self):
        client = Client()
        client.private.post = AsyncMock(return_value=Mock(json=Mock(return_value={"status": "ok"})))

        with self.assertRaises(ClientError):
            await client.challenge_submit_phone_number(
                {
                    "navigation": {"forward": "@attacker.example/steal"},
                    "challenge_context": "{}",
                },
                "+15551234567",
            )

        client.private.post.assert_not_awaited()

    async def test_challenge_verify_sms_captcha_rejects_external_forward_path(self):
        client = Client()
        client.private.post = AsyncMock(return_value=Mock(json=Mock(return_value={"status": "ok"})))

        with self.assertRaises(ClientError):
            await client.challenge_verify_sms_captcha(
                {
                    "navigation": {"forward": "@attacker.example/steal"},
                    "challenge_context": "{}",
                },
                "123456",
            )

        client.private.post.assert_not_awaited()

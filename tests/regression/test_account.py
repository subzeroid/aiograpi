import unittest
from unittest.mock import AsyncMock

from aiograpi import Client


class AccountRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_send_password_reset_posts_recovery_payload(self):
        client = Client()
        client.public_request = AsyncMock(return_value={"status": "ok"})

        result = await client.send_password_reset("user@example.com")

        self.assertEqual(result, {"status": "ok"})
        client.public_request.assert_awaited_once()
        args, kwargs = client.public_request.call_args
        self.assertEqual(args, ("https://www.instagram.com/accounts/account_recovery_send_ajax/",))
        self.assertEqual(
            kwargs["data"],
            {
                "email_or_username": "user@example.com",
                "recaptcha_challenge_field": "",
            },
        )
        self.assertEqual(kwargs["headers"]["x-requested-with"], "XMLHttpRequest")
        self.assertIn("x-csrftoken", kwargs["headers"])
        self.assertTrue(kwargs["return_json"])
        self.assertFalse(kwargs["update_headers"])

    async def test_send_password_reset_accepts_recaptcha_challenge_field(self):
        client = Client()
        client.public_request = AsyncMock(return_value={"status": "ok"})

        await client.send_password_reset("user@example.com", recaptcha_challenge_field="challenge")

        self.assertEqual(client.public_request.call_args.kwargs["data"]["recaptcha_challenge_field"], "challenge")

    async def test_reset_password_delegates_to_send_password_reset(self):
        client = Client()
        client.send_password_reset = AsyncMock(return_value={"status": "ok"})

        result = await client.reset_password("username")

        self.assertEqual(result, {"status": "ok"})
        client.send_password_reset.assert_awaited_once_with("username")

    async def test_confirm_email_posts_verify_email_code_payload(self):
        client = Client()
        client.phone_id = "phone-id"
        client.authorization_data = {"ds_user_id": "123"}
        client.uuid = "uuid"
        client.android_device_id = "android-id"
        client.private_request = AsyncMock(return_value={"status": "ok"})

        result = await client.confirm_email("addr@example.com", "123456")

        self.assertEqual(result, {"status": "ok"})
        client.private_request.assert_awaited_once_with(
            "accounts/verify_email_code/",
            {
                "_uuid": "uuid",
                "device_id": "android-id",
                "phone_id": "phone-id",
                "_uid": "123",
                "guid": "uuid",
                "email": "addr@example.com",
                "code": "123456",
            },
        )

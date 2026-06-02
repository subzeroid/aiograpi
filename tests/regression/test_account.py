import unittest
from unittest.mock import AsyncMock, Mock

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

    async def test_account_convert_to_professional_posts_conversion_payload(self):
        client = Client()
        account = object()
        client.with_default_data = Mock(side_effect=lambda data: {"default": "yes", **data})
        client.private_request = AsyncMock(return_value={"status": "ok"})
        client.account_info = AsyncMock(return_value=account)

        result = await client.account_convert_to_professional(
            to_account_type=3,
            category_id=2347428775505624,
            should_show_category=True,
            should_show_public_contacts=False,
            entry_point="setting",
            extra_data={"custom": "value"},
        )

        self.assertIs(result, account)
        client.private_request.assert_awaited_once_with(
            "business/account/convert_account/",
            data={
                "default": "yes",
                "entry_point": "setting",
                "creator_destination_migration": "false",
                "to_account_type": "3",
                "category_id": "2347428775505624",
                "should_show_category": "1",
                "should_show_public_contacts": "0",
                "custom": "value",
            },
        )
        client.account_info.assert_awaited_once_with()

    async def test_account_convert_to_business_uses_business_account_type(self):
        client = Client()
        client.account_convert_to_professional = AsyncMock(return_value="account")

        result = await client.account_convert_to_business(category_id="123", should_show_public_contacts=True)

        self.assertEqual(result, "account")
        client.account_convert_to_professional.assert_awaited_once_with(
            to_account_type=2,
            category_id="123",
            should_show_category=True,
            should_show_public_contacts=True,
        )

    async def test_account_convert_to_creator_uses_creator_account_type(self):
        client = Client()
        client.account_convert_to_professional = AsyncMock(return_value="account")

        result = await client.account_convert_to_creator(category_id="456", should_show_category=False)

        self.assertEqual(result, "account")
        client.account_convert_to_professional.assert_awaited_once_with(
            to_account_type=3,
            category_id="456",
            should_show_category=False,
            should_show_public_contacts=False,
        )

    async def test_account_convert_to_professional_rejects_personal_account_type(self):
        client = Client()

        with self.assertRaises(ValueError):
            await client.account_convert_to_professional(to_account_type=1)

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

    async def test_confirm_phone_number_posts_verify_sms_code_payload(self):
        client = Client()
        client.phone_id = "phone-id"
        client.authorization_data = {"ds_user_id": "123"}
        client.uuid = "uuid"
        client.android_device_id = "android-id"
        client.private_request = AsyncMock(return_value={"status": "ok"})

        result = await client.confirm_phone_number("+15555550100", "123456", has_sms_consent=True)

        self.assertEqual(result, {"status": "ok"})
        client.private_request.assert_awaited_once_with(
            "accounts/verify_sms_code/",
            {
                "_uuid": "uuid",
                "device_id": "android-id",
                "phone_id": "phone-id",
                "_uid": "123",
                "guid": "uuid",
                "phone_number": "+15555550100",
                "verification_code": "123456",
                "has_sms_consent": "true",
            },
        )

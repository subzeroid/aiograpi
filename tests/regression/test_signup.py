import unittest
from unittest.mock import AsyncMock, Mock

from aiograpi import Client
from aiograpi.exceptions import ChallengeRequired, ClientError, FeedbackRequired, SignupSpamError
from aiograpi.mixins.challenge import ChallengeChoice


class SignupHelperRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_signup_requires_email_or_phone_number(self):
        client = Client()

        with self.assertRaises(ClientError) as ctx:
            await client.signup("example", "password", email="", phone_number="")

        self.assertIn("email or phone_number", str(ctx.exception))

    async def test_signup_with_phone_number_uses_sms_flow(self):
        client = Client()
        client.wait_seconds = 0
        client.get_signup_config = AsyncMock(return_value={})
        client.check_email = AsyncMock()
        client.check_phone_number = AsyncMock(return_value={"status": "ok"})
        client.send_signup_sms_code = AsyncMock(return_value={"status": "ok"})
        client.challenge_code_handler = AsyncMock(return_value="123456")
        client.accounts_create = AsyncMock(return_value={"created_user": {"pk": "1", "username": "example"}})
        client.parse_authorization = Mock(return_value={})
        client.last_response = Mock(headers={"ig-set-authorization": ""})

        with unittest.mock.patch("aiograpi.mixins.signup.extract_user_short", return_value="created-user"):
            result = await client.signup(
                username="example",
                password="password",
                email="",
                phone_number="+15551234567",
                full_name="Example User",
                year=2000,
                month=5,
                day=12,
            )

        self.assertEqual(result, "created-user")
        client.check_email.assert_not_awaited()
        client.check_phone_number.assert_awaited_once_with("+15551234567")
        client.send_signup_sms_code.assert_awaited_once_with("+15551234567")
        client.challenge_code_handler.assert_awaited_once_with("example", ChallengeChoice.SMS)
        client.accounts_create.assert_awaited_once_with(
            username="example",
            password="password",
            full_name="Example User",
            year=2000,
            month=5,
            day=12,
            phone_number="+15551234567",
            phone_code="123456",
        )

    async def test_accounts_create_primary_signup_omits_secondary_account_flag(self):
        client = Client()
        client.phone_id = "phone-id"
        client.uuid = "uuid"
        client.android_device_id = "android-id"
        client.adid = "adid"
        client.waterfall_id = "waterfall-id"
        client.password_encrypt = AsyncMock(return_value="enc-password")
        client.private_request = AsyncMock(return_value={"created_user": {"pk": "1"}})

        result = await client.accounts_create(
            username="example",
            password="password",
            email="addr@example.com",
            email_code="signup-code",
            full_name="Example User",
            year=2000,
            month=5,
            day=12,
        )

        self.assertEqual(result, {"created_user": {"pk": "1"}})
        data = client.private_request.call_args.args[1]
        self.assertNotIn("is_secondary_account_creation", data)
        self.assertEqual(data["username"], "example")
        self.assertEqual(data["force_sign_up_code"], "signup-code")
        client.private_request.assert_awaited_once()

    async def test_accounts_create_phone_signup_uses_validated_endpoint(self):
        client = Client()
        client.phone_id = "phone-id"
        client.uuid = "uuid"
        client.android_device_id = "android-id"
        client.adid = "adid"
        client.waterfall_id = "waterfall-id"
        client.password_encrypt = AsyncMock(return_value="enc-password")
        client.private_request = AsyncMock(return_value={"created_user": {"pk": "1"}})

        result = await client.accounts_create(
            username="example",
            password="password",
            phone_number="+15551234567",
            phone_code="123456",
            full_name="Example User",
            year=2000,
            month=5,
            day=12,
        )

        self.assertEqual(result, {"created_user": {"pk": "1"}})
        endpoint, data = client.private_request.call_args.args
        self.assertEqual(endpoint, "accounts/create_validated/")
        self.assertNotIn("is_secondary_account_creation", data)
        self.assertNotIn("email", data)
        self.assertEqual(data["username"], "example")
        self.assertEqual(data["phone_number"], "+15551234567")
        self.assertEqual(data["verification_code"], "123456")
        self.assertEqual(data["force_sign_up_code"], "")
        self.assertEqual(data["has_sms_consent"], "true")
        client.private_request.assert_awaited_once()

    async def test_accounts_create_requires_email_or_phone_number(self):
        client = Client()
        client.private_request = AsyncMock()

        with self.assertRaises(ClientError) as ctx:
            await client.accounts_create(username="example", password="password")

        self.assertIn("email or phone_number", str(ctx.exception))
        client.private_request.assert_not_awaited()

    async def test_accounts_create_spam_feedback_raises_signup_specific_error(self):
        client = Client()
        client.phone_id = "phone-id"
        client.uuid = "uuid"
        client.android_device_id = "android-id"
        client.adid = "adid"
        client.waterfall_id = "waterfall-id"
        client.password_encrypt = AsyncMock(return_value="enc-password")
        client.private_request = AsyncMock(
            side_effect=FeedbackRequired(
                message="feedback_required: Try Again Later",
                feedback_message="We limit how often you can do certain things on Instagram.",
                spam=True,
            )
        )

        with self.assertRaises(SignupSpamError) as ctx:
            await client.accounts_create(
                username="example",
                password="password",
                email="addr@example.com",
                email_code="signup-code",
            )

        self.assertIn("legacy signup flow", str(ctx.exception))
        self.assertTrue(ctx.exception.spam)
        self.assertEqual(ctx.exception.feedback_message, "We limit how often you can do certain things on Instagram.")

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

    async def test_challenge_flow_submits_phone_number_then_sms_code(self):
        client = Client()
        start = {"api_path": "/challenge/start", "challenge_context": "{}"}
        submit_phone_step = {
            "challengeType": "SubmitPhoneNumberForm",
            "navigation": {"forward": "/challenge/phone"},
            "challenge_context": "{}",
        }
        verify_sms_step = {
            "challengeType": "VerifySMSCodeFormForSMSCaptcha",
            "navigation": {"forward": "/challenge/sms"},
            "challenge_context": "{}",
        }
        client.challenge_api = AsyncMock(return_value=submit_phone_step)
        client.challenge_submit_phone_number = AsyncMock(return_value=verify_sms_step)
        client.challenge_verify_sms_captcha = AsyncMock(return_value={"status": "ok"})
        client.challenge_code_handler = AsyncMock(return_value="123456")

        result = await client.challenge_flow(
            start,
            phone_number="+15551234567",
            username="example",
            wait_seconds=0,
        )

        self.assertTrue(result)
        client.challenge_submit_phone_number.assert_awaited_once_with(submit_phone_step, "+15551234567")
        client.challenge_code_handler.assert_awaited_once()
        self.assertEqual(client.challenge_code_handler.call_args.args[0], "example")
        self.assertEqual(client.challenge_code_handler.call_args.args[1], ChallengeChoice.SMS)
        client.challenge_verify_sms_captcha.assert_awaited_once_with(verify_sms_step, "123456")

    async def test_challenge_flow_requires_phone_number_for_sms_challenge(self):
        client = Client()
        start = {"api_path": "/challenge/start", "challenge_context": "{}"}
        submit_phone_step = {
            "challengeType": "SubmitPhoneNumberForm",
            "navigation": {"forward": "/challenge/phone"},
            "challenge_context": "{}",
        }
        client.challenge_api = AsyncMock(return_value=submit_phone_step)

        with self.assertRaises(ClientError) as ctx:
            await client.challenge_flow(start, username="example", wait_seconds=0)

        self.assertIn("phone_number is required", str(ctx.exception))

    async def test_challenge_flow_requires_sms_code(self):
        client = Client()
        start = {"api_path": "/challenge/start", "challenge_context": "{}"}
        verify_sms_step = {
            "challengeType": "VerifySMSCodeFormForSMSCaptcha",
            "navigation": {"forward": "/challenge/sms"},
            "challenge_context": "{}",
        }
        client.challenge_api = AsyncMock(return_value=verify_sms_step)
        client.challenge_code_handler = AsyncMock(return_value=False)

        with self.assertRaises(ChallengeRequired) as ctx:
            await client.challenge_flow(
                start,
                phone_number="+15551234567",
                username="example",
                wait_seconds=0,
                attempts=1,
            )

        self.assertIn("SMS code required", str(ctx.exception))

    async def test_signup_passes_phone_number_to_challenge_flow(self):
        client = Client()
        client.wait_seconds = 0
        challenge = {"api_path": "/challenge/start", "challenge_context": "{}"}
        client.get_signup_config = AsyncMock(return_value={})
        client.check_email = AsyncMock(return_value={"valid": True, "available": True})
        client.send_verify_email = AsyncMock(return_value={"email_sent": True})
        client.challenge_code_handler = AsyncMock(return_value="654321")
        client.check_confirmation_code = AsyncMock(return_value={"signup_code": "signup-code"})
        client.check_phone_number = AsyncMock(return_value={"status": "ok"})
        client.send_signup_sms_code = AsyncMock(return_value={"status": "ok"})
        client.accounts_create = AsyncMock(
            side_effect=[
                {"message": "challenge_required", "challenge": challenge},
                {"created_user": {"pk": "1", "username": "example"}},
            ]
        )
        client.challenge_flow = AsyncMock(return_value=True)
        client.parse_authorization = Mock(return_value={})
        client.last_response = Mock(headers={"ig-set-authorization": ""})

        with unittest.mock.patch("aiograpi.mixins.signup.extract_user_short", return_value="created-user"):
            result = await client.signup(
                "example",
                "password",
                "example@example.com",
                "+15551234567",
            )

        self.assertEqual(result, "created-user")
        client.check_phone_number.assert_not_awaited()
        client.send_signup_sms_code.assert_not_awaited()
        client.challenge_flow.assert_awaited_once_with(
            challenge,
            phone_number="+15551234567",
            username="example",
        )

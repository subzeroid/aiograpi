import importlib.util
import json
import os
import subprocess
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock

from aiograpi import Client
from aiograpi.exceptions import ChallengeRequired, ClientError, FeedbackRequired, SignupSpamError
from aiograpi.mixins.challenge import ChallengeChoice
from aiograpi.types import UserShort
from aiograpi.utils.serialization import dumps


def _load_live_signup_module():
    signup_path = Path(__file__).resolve().parents[1] / "live" / "test_signup_live.py"
    spec = importlib.util.spec_from_file_location("aiograpi_live_signup", signup_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LIVE_SIGNUP_MODULE = _load_live_signup_module()
SignUpTestCase = LIVE_SIGNUP_MODULE.SignUpTestCase


class SignupHelperRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    def caa_response(
        self,
        reg_info='{"contactpoint":"addr@example.com"}',
        reg_context="ctx-1",
        email_token="email-token-1",
        registration_response=None,
    ):
        escaped_reg_info = reg_info.replace('"', '\\"')
        chunks = [
            (
                '(f4i (dkc "reg_info" "reg_context" "email_token") '
                f'(dkc "{escaped_reg_info}" "{reg_context}" "{email_token}"))'
            )
        ]
        if registration_response:
            response_json = json.dumps(
                {"registration_response": json.dumps(registration_response, separators=(",", ":"))}
            )
            chunks.append(f"(dsh (fom 1 1 {json.dumps(response_json)}))")
        return {
            "layout": {
                "bloks_payload": {
                    "ft": {"state": " ".join(chunks)},
                }
            },
            "status": "ok",
        }

    async def test_caa_extract_state_reads_bloks_dkc_maps_and_registration_response(self):
        client = Client()
        registration_response = {
            "account_created": True,
            "created_user": {
                "pk": "123",
                "username": "example",
                "full_name": "Example User",
                "profile_pic_url": "https://example.com/avatar.jpg",
            },
        }

        state = client._caa_extract_state(self.caa_response(registration_response=registration_response))

        self.assertEqual(state["reg_context"], "ctx-1")
        self.assertEqual(state["email_token"], "email-token-1")
        self.assertEqual(state["reg_info"], '{"contactpoint":"addr@example.com"}')
        self.assertEqual(state["registration_response"], registration_response)

    async def test_caa_extract_state_reads_graphql_bloks_bundle_action(self):
        client = Client()
        response = {
            "data": {
                "1$bloks_action(bk_context:$bk_context,params:$params)": {
                    "action": {
                        "action_bundle": {
                            "bloks_bundle_action": json.dumps(
                                self.caa_response(reg_context="ctx-from-graphql", email_token="token-from-graphql"),
                                separators=(",", ":"),
                            )
                        }
                    }
                }
            }
        }

        state = client._caa_extract_state(response)

        self.assertEqual(state["reg_context"], "ctx-from-graphql")
        self.assertEqual(state["email_token"], "token-from-graphql")

    async def test_signup_caa_email_runs_modern_email_flow(self):
        client = Client()
        client.uuid = "uuid-1"
        client.phone_id = "family-device-id"
        client.android_device_id = "android-id"
        client.mid = "machine-id"
        client.bloks_versioning_id = "bloks-version"
        client.waterfall_id = "waterfall-id"
        client.wait_seconds = 0
        client.challenge_code_handler = AsyncMock(return_value="123456")
        registration_response = {
            "account_created": True,
            "created_user": {
                "pk": "123",
                "username": "example",
                "full_name": "Example User",
                "profile_pic_url": "https://example.com/avatar.jpg",
            },
        }
        graphql_responses = [
            self.caa_response(reg_context=f"ctx-gql-{index}", email_token=f"email-token-{index}") for index in range(8)
        ]
        graphql_responses.append(self.caa_response(registration_response=registration_response))
        async_responses = [
            self.caa_response(reg_context=f"ctx-async-{index}", email_token=f"email-token-async-{index}")
            for index in range(4)
        ]
        client.caa_reg_graphql = AsyncMock(side_effect=graphql_responses)
        client.caa_reg_async_action = AsyncMock(side_effect=async_responses)

        user = await client.signup_caa_email(
            username="example",
            password="password",
            email="addr@example.com",
            full_name="Example User",
            year=1995,
            month=6,
            day=9,
        )

        self.assertIsInstance(user, UserShort)
        self.assertEqual(user.pk, "123")
        self.assertEqual(user.username, "example")
        self.assertEqual(user.full_name, "Example User")
        self.assertEqual(
            [call.args[0] for call in client.caa_reg_graphql.call_args_list],
            [
                "com.bloks.www.bloks.caa.reg.aymh_create_account_button.async",
                "com.bloks.www.bloks.caa.reg.async.contactpoint_prefill.async",
                "com.bloks.www.bloks.caa.reg.contactpoint_phone",
                "com.bloks.www.bloks.caa.reg.contactpoint_email",
                "com.bloks.www.bloks.caa.reg.confirmation.async",
                "com.bloks.www.bloks.caa.reg.password.async",
                "com.bloks.www.bloks.caa.reg.birthday.async",
                "com.bloks.www.bloks.caa.reg.username.async",
                "com.bloks.www.bloks.caa.reg.create.account.async",
            ],
        )
        self.assertEqual(
            [call.args[0] for call in client.caa_reg_async_action.call_args_list],
            [
                "com.bloks.www.bloks.caa.reg.async.expose_ntm_experiment.async",
                "com.bloks.www.bloks.caa.reg.async.contactpoint_email_new.async",
                "com.bloks.www.bloks.caa.reg.send_confirmation_email.async",
                "com.bloks.www.bloks.caa.reg.name_vtwo.async",
            ],
        )
        client.challenge_code_handler.assert_awaited_once_with("example", ChallengeChoice.EMAIL)
        password_call = client.caa_reg_graphql.call_args_list[5]
        self.assertRegex(
            password_call.kwargs["client_input_params"]["encrypted_password"],
            r"^#PWD_INSTAGRAM:0:\d+:password$",
        )
        self.assertEqual(password_call.kwargs["client_input_params"]["spi_action"], 1)
        self.assertEqual(
            password_call.kwargs["server_params"]["flow_modifier"],
            dumps({"flow_name": "new_to_family_ig_default", "flow_type": "ntf"}),
        )
        birthday_call = client.caa_reg_graphql.call_args_list[6]
        self.assertEqual(birthday_call.kwargs["client_input_params"]["birthday_or_current_date_string"], "09-06-1995")
        username_call = client.caa_reg_graphql.call_args_list[7]
        self.assertEqual(username_call.kwargs["server_params"]["action"], 1)
        self.assertEqual(username_call.kwargs["server_params"]["post_tos"], 0)
        email_new_call = client.caa_reg_async_action.call_args_list[1]
        self.assertIsNone(email_new_call.kwargs["server_params"]["reg_context"])
        self.assertEqual(email_new_call.kwargs["client_input_params"]["email_prefilled"], 0)
        self.assertEqual(email_new_call.kwargs["client_input_params"]["prefetch_version"], 11)
        self.assertEqual(email_new_call.kwargs["server_params"]["cp_funnel"], 0)
        self.assertEqual(email_new_call.kwargs["server_params"]["prefetch_on_field"], 1)

    async def test_signup_caa_email_reports_bloks_rejection_message(self):
        client = Client()
        client.uuid = "uuid-1"
        client.phone_id = "family-device-id"
        client.android_device_id = "android-id"
        client.mid = "machine-id"
        client.bloks_versioning_id = "bloks-version"
        client.waterfall_id = "waterfall-id"
        client.wait_seconds = 0
        client.challenge_code_handler = AsyncMock(return_value="123456")
        rejection_text = "We're sorry, but something went wrong. Please try again."
        graphql_responses = [
            self.caa_response(reg_context=f"ctx-gql-{index}", email_token=f"email-token-{index}") for index in range(8)
        ]
        graphql_responses.append(
            {
                "data": {
                    "1$bloks_action(bk_context:$bk_context,params:$params)": {
                        "action": {
                            "action_bundle": {
                                "bloks_bundle_action": json.dumps(
                                    {"layout": {"bloks_payload": {"data": [{"data": {"initial": rejection_text}}]}}}
                                )
                            }
                        }
                    }
                }
            }
        )
        async_responses = [
            self.caa_response(reg_context=f"ctx-async-{index}", email_token=f"email-token-async-{index}")
            for index in range(4)
        ]
        client.caa_reg_graphql = AsyncMock(side_effect=graphql_responses)
        client.caa_reg_async_action = AsyncMock(side_effect=async_responses)

        with self.assertRaisesRegex(
            ClientError,
            "CAA signup was rejected by Instagram: "
            r"We're sorry, but something went wrong\. Please try again\.",
        ):
            await client.signup_caa_email(
                username="example",
                password="password",
                email="addr@example.com",
                full_name="Example User",
                year=1995,
                month=6,
                day=9,
            )

    async def test_caa_reg_async_action_allows_prelogin_bloks_request(self):
        client = Client()
        client.uuid = "uuid-1"
        client.phone_id = "family-device-id"
        client.android_device_id = "android-id"
        client.mid = "machine-id"
        client.waterfall_id = "waterfall-id"
        client.bloks_async_action = AsyncMock(return_value={"status": "ok"})
        state = client._caa_initial_state(email="addr@example.com")

        result = await client.caa_reg_async_action("com.example.action", state=state)

        self.assertEqual(result, {"status": "ok"})
        client.bloks_async_action.assert_awaited_once()
        self.assertEqual(client.bloks_async_action.call_args.args[0], "com.example.action")
        self.assertEqual(client.bloks_async_action.call_args.kwargs["domain"], "b.i.instagram.com")
        self.assertTrue(client.bloks_async_action.call_args.kwargs["login"])

    async def test_signup_requires_email_or_phone_number(self):
        client = Client()

        with self.assertRaises(ClientError) as ctx:
            await client.signup("example", "password", email="", phone_number="")

        self.assertIn("email or phone_number", str(ctx.exception))

    async def test_legacy_signup_helpers_allow_sessionless_private_requests(self):
        client = Client()
        client.uuid = "uuid"
        client.phone_id = "phone-id"
        client.android_device_id = "android-id"
        client.waterfall_id = "waterfall-id"
        client.private_request = AsyncMock(return_value={"status": "ok"})
        client.password_encrypt = AsyncMock(return_value="enc-password")

        await client.get_signup_config()
        await client.check_username("example")
        await client.check_email("addr@example.com")
        await client.check_phone_number("+15551234567")
        await client.send_signup_sms_code("+15551234567")
        await client.send_verify_email("addr@example.com")
        await client.check_confirmation_code("addr@example.com", "123456")
        await client.check_age_eligibility(2000, 5, 12)
        await client.accounts_create(
            username="example",
            password="password",
            email="addr@example.com",
            email_code="signup-code",
        )

        self.assertEqual(client.private_request.await_count, 9)
        for call in client.private_request.call_args_list:
            with self.subTest(endpoint=call.args[0]):
                self.assertTrue(call.kwargs.get("login"))

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
            with unittest.mock.patch("builtins.print") as print_mock:
                with self.assertWarnsRegex(RuntimeWarning, "legacy account-create flow"):
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
        print_mock.assert_not_called()
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

    async def test_signup_warns_about_legacy_flow(self):
        client = Client()
        client.wait_seconds = 0
        client.get_signup_config = AsyncMock(return_value={})
        client.check_phone_number = AsyncMock(return_value={"status": "ok"})
        client.send_signup_sms_code = AsyncMock(return_value={"status": "ok"})
        client.challenge_code_handler = AsyncMock(return_value="123456")
        client.accounts_create = AsyncMock(return_value={"created_user": {"pk": "1", "username": "example"}})
        client.parse_authorization = Mock(return_value={})
        client.last_response = Mock(headers={"ig-set-authorization": ""})

        with unittest.mock.patch("aiograpi.mixins.signup.extract_user_short", return_value="created-user"):
            with self.assertWarnsRegex(RuntimeWarning, "legacy account-create flow"):
                result = await client.signup(
                    username="example",
                    password="password",
                    email="",
                    phone_number="+15551234567",
                )

        self.assertEqual(result, "created-user")

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

    async def test_challenge_code_or_raised_does_not_print_code_value(self):
        client = Client()
        client.username = "example"
        client.last_json = {}
        client.challenge_code_handler = AsyncMock(return_value="123456")

        with unittest.mock.patch("builtins.print") as print_mock:
            result = await client.challenge_code_or_raised(ChallengeChoice.EMAIL, wait_seconds=0, attempts=1)

        self.assertEqual(result, "123456")
        print_mock.assert_not_called()

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
            with self.assertWarnsRegex(RuntimeWarning, "legacy account-create flow"):
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


class SignupLiveHelperRegressionTestCase(unittest.TestCase):
    def test_get_signup_email_address_command_receives_username_context(self):
        case = SignUpTestCase("test_email_signup_live")
        completed = subprocess.CompletedProcess(args="email-command", returncode=0, stdout="fresh@example.test\n")

        with unittest.mock.patch.dict(os.environ, {"IG_SIGNUP_EMAIL_COMMAND": "email-command"}, clear=True):
            with unittest.mock.patch.object(LIVE_SIGNUP_MODULE.subprocess, "run", return_value=completed) as run:
                email = case._get_signup_email_address("freshuser")

        self.assertEqual(email, "fresh@example.test")
        self.assertEqual(run.call_args.kwargs["env"]["IG_SIGNUP_USERNAME"], "freshuser")

    def test_signup_code_command_receives_signup_context(self):
        case = SignUpTestCase("test_email_signup_live")
        completed = subprocess.CompletedProcess(args="code-command", returncode=0, stdout="123456\n")

        with unittest.mock.patch.dict(os.environ, {"IG_SIGNUP_EMAIL_CODE_COMMAND": "code-command"}, clear=True):
            with unittest.mock.patch.object(LIVE_SIGNUP_MODULE.subprocess, "run", return_value=completed) as run:
                code = case.signup_code_handler(
                    "IG_SIGNUP_EMAIL_CODE",
                    "IG_SIGNUP_EMAIL_CODE_COMMAND",
                    {
                        "IG_SIGNUP_USERNAME": "freshuser",
                        "IG_SIGNUP_EMAIL": "fresh@example.test",
                    },
                )

        self.assertEqual(code, "123456")
        self.assertEqual(run.call_args.kwargs["env"]["IG_SIGNUP_USERNAME"], "freshuser")
        self.assertEqual(run.call_args.kwargs["env"]["IG_SIGNUP_EMAIL"], "fresh@example.test")

    def test_get_signup_email_address_skips_without_static_email_or_command(self):
        case = SignUpTestCase("test_email_signup_live")

        with unittest.mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(unittest.SkipTest):
                case._get_signup_email_address("freshuser")

    def test_signup_phone_number_prefers_signup_specific_env(self):
        case = SignUpTestCase("test_phone_signup_live")

        with unittest.mock.patch.dict(
            os.environ,
            {
                "IG_PHONE_NUMBER": "+15550000000",
                "IG_SIGNUP_PHONE_NUMBER": "+15551234567",
            },
            clear=True,
        ):
            phone_number = case.signup_phone_number()

        self.assertEqual(phone_number, "+15551234567")

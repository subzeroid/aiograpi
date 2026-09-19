import asyncio
import unittest
from unittest.mock import AsyncMock, Mock

from pydantic import ValidationError

from aiograpi import Client
from aiograpi.exceptions import (
    AccountSuspended,
    BadPassword,
    ChallengeError,
    ClientNotFoundError,
    LoginRequired,
    PleaseWaitFewMinutes,
    PrivateError,
    RateLimitError,
    TwoFactorRequired,
    UnknownError,
)
from aiograpi.types import UserShort


class AuthRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_login_validates_existing_session_before_returning(self):
        client = Client()
        client.authorization_data = {"ds_user_id": "123"}
        client.account_info = AsyncMock(return_value=object())
        client.pre_login_flow = AsyncMock()
        client.private_request = AsyncMock()

        result = await client.login("example", "password")

        self.assertTrue(result)
        client.account_info.assert_awaited_once_with()
        client.pre_login_flow.assert_not_awaited()
        client.private_request.assert_not_awaited()

    async def test_login_legacy_refreshes_session_rejected_during_validation(self):
        client = Client()
        client.authorization_data = {"ds_user_id": "123", "sessionid": "stale"}
        client.private.set_cookies({"sessionid": "stale"})
        client.public.set_cookies({"sessionid": "public-stale"})
        client.private.headers["Authorization"] = "Bearer stale"
        client.account_info = AsyncMock(side_effect=LoginRequired())
        client.last_response = Mock(headers={"ig-set-authorization": "Bearer fresh"})
        client.parse_authorization = Mock(return_value={"ds_user_id": "123", "sessionid": "fresh"})
        client.pre_login_flow = AsyncMock(return_value=True)
        client.password_encrypt = AsyncMock(return_value="enc-password")
        client.private_request = AsyncMock(return_value=True)
        client.login_flow = AsyncMock()

        result = await client.login_legacy("example", "password")

        self.assertTrue(result)
        client.account_info.assert_awaited_once_with()
        client.pre_login_flow.assert_awaited_once_with()
        self.assertEqual(client.private_request.await_args.args[0], "accounts/login/")
        self.assertNotIn("Authorization", client.private.headers)
        self.assertEqual(client.private.cookies_dict(), {})
        self.assertEqual(client.public.cookies_dict(), {})
        self.assertEqual(client.authorization_data["sessionid"], "fresh")
        self.assertEqual(client.relogin_attempt, 0)

    async def test_login_does_not_mask_other_session_validation_errors(self):
        client = Client()
        client.authorization_data = {"ds_user_id": "123"}
        client.account_info = AsyncMock(side_effect=PleaseWaitFewMinutes())
        client.pre_login_flow = AsyncMock()
        client.private_request = AsyncMock()

        with self.assertRaises(PleaseWaitFewMinutes):
            await client.login("example", "password")

        client.pre_login_flow.assert_not_awaited()
        client.private_request.assert_not_awaited()

    async def test_login_by_sessionid_falls_back_to_private_stream_before_public(self):
        client = Client()
        sessionid = "1234567890123456789012345678901%3Atoken"
        client.user_info_v1 = AsyncMock(side_effect=PrivateError("boom"))
        client.user_stream_by_id_flat = AsyncMock(return_value={"pk": "1234567890123456789", "username": "example"})
        client.user_short_gql = AsyncMock(
            side_effect=AssertionError("sessionid login should use private fallback first")
        )

        result = await client.login_by_sessionid(sessionid)

        self.assertTrue(result)
        client.user_info_v1.assert_awaited_once_with(1234567890123456789012345678901)
        client.user_stream_by_id_flat.assert_awaited_once_with("1234567890123456789012345678901")
        client.user_short_gql.assert_not_awaited()
        self.assertEqual(client.username, "example")
        self.assertEqual(client.authorization_data["sessionid"], sessionid)
        self.assertEqual(client.cookie_dict["ds_user_id"], "1234567890123456789")

    async def test_login_by_sessionid_falls_back_to_public_after_private_stream_failure(self):
        client = Client()
        sessionid = "1234567890123456789012345678901%3Atoken"
        client.user_info_v1 = AsyncMock(side_effect=PrivateError("boom"))
        client.user_stream_by_id_flat = AsyncMock(side_effect=PrivateError("stream failed"))
        client.user_short_gql = AsyncMock(return_value=UserShort(pk="1234567890123456789", username="example"))

        result = await client.login_by_sessionid(sessionid)

        self.assertTrue(result)
        client.user_info_v1.assert_awaited_once_with(1234567890123456789012345678901)
        client.user_stream_by_id_flat.assert_awaited_once_with("1234567890123456789012345678901")
        client.user_short_gql.assert_awaited_once_with(1234567890123456789012345678901)
        self.assertEqual(client.username, "example")

    async def test_login_by_sessionid_falls_back_to_private_stream_on_validation_error(self):
        client = Client()
        sessionid = "1234567890123456789012345678901%3Atoken"
        client.user_info_v1 = AsyncMock(side_effect=ValidationError.from_exception_data("User", []))
        client.user_stream_by_id_flat = AsyncMock(return_value={"pk_id": "1234567890123456789", "username": "example"})
        client.user_short_gql = AsyncMock(
            side_effect=AssertionError("sessionid login should use private fallback first")
        )

        result = await client.login_by_sessionid(sessionid)

        self.assertTrue(result)
        client.user_info_v1.assert_awaited_once_with(1234567890123456789012345678901)
        client.user_stream_by_id_flat.assert_awaited_once_with("1234567890123456789012345678901")
        client.user_short_gql.assert_not_awaited()
        self.assertEqual(client.username, "example")

    async def test_login_legacy_bad_password_without_context_tries_current_caa_flow(self):
        client = Client()
        client.username = "example"
        client.password = "password"
        client.authorization_data = {}
        client.last_json = {"message": "The password you entered is incorrect.", "error_type": "bad_password"}
        client.pre_login_flow = AsyncMock(return_value=True)
        client.password_encrypt = AsyncMock(return_value="enc-password")
        client.login_flow = AsyncMock()
        client.private_request = AsyncMock(side_effect=BadPassword("Bad Password", response=Mock(status_code=400)))
        client.bloks_caa_login = AsyncMock(return_value={"logged_in": True})

        result = await client.login_legacy(verification_code="654321")

        self.assertTrue(result)
        client.bloks_caa_login.assert_awaited_once_with(verification_code="654321")
        client.login_flow.assert_awaited_once_with()

    async def test_login_legacy_bad_password_recovery_response_tries_current_caa_flow_without_code(self):
        client = Client()
        client.username = "example"
        client.password = "password"
        client.authorization_data = {}
        client.last_json = {
            "message": "Get back into your account",
            "error_title": "Forgotten password?",
            "error_type": "bad_password",
        }
        client.pre_login_flow = AsyncMock(return_value=True)
        client.password_encrypt = AsyncMock(return_value="enc-password")
        client.login_flow = AsyncMock()
        client.private_request = AsyncMock(side_effect=BadPassword("Bad Password", response=Mock(status_code=400)))
        client.bloks_caa_login = AsyncMock(return_value={"logged_in": True})

        result = await client.login_legacy()

        self.assertTrue(result)
        client.bloks_caa_login.assert_awaited_once_with(verification_code="")
        client.login_flow.assert_awaited_once_with()

    async def test_login_legacy_with_eight_digit_backup_code_selects_backup_code_bloks_challenge(self):
        client = Client()
        client.username = "example"
        client.password = "password"
        client.authorization_data = {}
        client.last_json = {
            "two_step_verification_context": "context-1",
            "sms_two_factor_on": False,
            "totp_two_factor_on": True,
        }
        client.pre_login_flow = AsyncMock(return_value=True)
        client.password_encrypt = AsyncMock(return_value="enc-password")
        client.login_flow = AsyncMock()
        client.private_request = AsyncMock(side_effect=BadPassword("Bad Password", response=Mock(status_code=400)))
        client.bloks_two_step_verification_entrypoint = AsyncMock(return_value={"status": "ok"})
        client.bloks_two_step_verification_method_picker = AsyncMock(return_value={"status": "ok"})
        client.bloks_two_step_verification_select_method = AsyncMock(return_value={"status": "ok"})
        client.bloks_two_step_verification_enter_backup_code = AsyncMock(return_value={"status": "ok"})
        client.bloks_two_step_verification_verify_code = AsyncMock(return_value={"layout": {}})
        client.bloks_apply_login_response = Mock(return_value=True)

        result = await client.login_legacy(verification_code="1234 5678")

        self.assertTrue(result)
        client.bloks_two_step_verification_select_method.assert_awaited_once_with(
            "context-1",
            selected_method="backup_codes",
        )
        client.bloks_two_step_verification_enter_backup_code.assert_awaited_once_with("context-1")
        client.bloks_two_step_verification_verify_code.assert_awaited_once_with(
            "context-1",
            "12345678",
            challenge="backup_codes",
        )
        client.login_flow.assert_awaited_once_with()

    async def test_login_legacy_two_factor_backup_code_with_context_uses_bloks_without_legacy_two_factor_request(self):
        client = Client()
        client.username = "example"
        client.password = "password"
        client.authorization_data = {}
        client.uuid = "uuid-1"
        client.phone_id = "phone-1"
        client.android_device_id = "android-1"
        client._token = "csrftoken"
        client.last_json = {
            "two_factor_info": {
                "two_factor_identifier": "two-factor-id",
                "two_step_verification_context": "context-1",
                "totp_two_factor_on": True,
                "sms_two_factor_on": False,
            }
        }
        client.pre_login_flow = AsyncMock(return_value=True)
        client.password_encrypt = AsyncMock(return_value="enc-password")
        client.login_flow = AsyncMock()
        client.private_request = AsyncMock(side_effect=[TwoFactorRequired("Two-factor authentication required")])
        client.bloks_two_step_verification_entrypoint = AsyncMock(return_value={"status": "ok"})
        client.bloks_two_step_verification_method_picker = AsyncMock(return_value={"status": "ok"})
        client.bloks_two_step_verification_select_method = AsyncMock(return_value={"status": "ok"})
        client.bloks_two_step_verification_enter_backup_code = AsyncMock(return_value={"status": "ok"})
        client.bloks_two_step_verification_verify_code = AsyncMock(return_value={"layout": {}})
        client.bloks_apply_login_response = Mock(return_value=True)

        result = await client.login_legacy(verification_code="1234 5678")

        self.assertTrue(result)
        self.assertEqual(client.private_request.await_count, 1)
        client.bloks_two_step_verification_select_method.assert_awaited_once_with(
            "context-1",
            selected_method="backup_codes",
        )
        client.bloks_two_step_verification_enter_backup_code.assert_awaited_once_with("context-1")
        client.bloks_two_step_verification_verify_code.assert_awaited_once_with(
            "context-1",
            "12345678",
            challenge="backup_codes",
        )
        client.login_flow.assert_awaited_once_with()

    async def test_login_legacy_bad_password_without_context_preserves_original_error_when_caa_has_no_session(self):
        client = Client()
        client.username = "example"
        client.password = "password"
        client.authorization_data = {}
        legacy_json = {"message": "The password you entered is incorrect.", "error_type": "bad_password"}
        legacy_response = Mock(status_code=400)
        client.last_json = legacy_json
        client.last_response = legacy_response
        client.pre_login_flow = AsyncMock(return_value=True)
        client.password_encrypt = AsyncMock(return_value="enc-password")
        original = BadPassword("Bad Password", response=legacy_response)
        client.private_request = AsyncMock(side_effect=original)

        async def caa_without_session(**kwargs):
            client.last_json = {"status": "ok", "step": "caa"}
            client.last_response = Mock(status_code=200)
            return {"logged_in": False, "two_step_verification_context": "", "reason": "no session"}

        client.bloks_caa_login = AsyncMock(side_effect=caa_without_session)

        with self.assertRaises(BadPassword) as raised:
            await client.login_legacy(verification_code="654321")

        self.assertIs(raised.exception, original)
        client.bloks_caa_login.assert_awaited_once_with(verification_code="654321")
        self.assertEqual(client.last_json, legacy_json)
        self.assertIs(client.last_response, legacy_response)

    async def test_login_legacy_bad_password_without_context_preserves_original_error_when_caa_is_unavailable(self):
        client = Client()
        client.username = "example"
        client.password = "password"
        client.authorization_data = {}
        legacy_json = {"message": "Bad Password", "error_type": "bad_password"}
        legacy_response = Mock(status_code=400)
        client.last_json = legacy_json
        client.last_response = legacy_response
        client.pre_login_flow = AsyncMock(return_value=True)
        client.password_encrypt = AsyncMock(return_value="enc-password")
        original = BadPassword("Bad Password", response=legacy_response)
        client.private_request = AsyncMock(side_effect=original)
        caa_response = Mock(status_code=404)
        caa_error = ClientNotFoundError(
            "Payload returned is null",
            response=caa_response,
            error_type="field_exception",
            status="fail",
        )

        async def unavailable_caa(**kwargs):
            client.last_json = {"status": "fail", "error_type": "field_exception"}
            client.last_response = caa_response
            raise caa_error

        client.bloks_caa_login = AsyncMock(side_effect=unavailable_caa)

        with self.assertRaises(BadPassword) as raised:
            await client.login_legacy(verification_code="654321")

        self.assertIs(raised.exception, original)
        client.bloks_caa_login.assert_awaited_once_with(verification_code="654321")
        self.assertEqual(client.last_json, legacy_json)
        self.assertIs(client.last_response, legacy_response)

    async def test_login_legacy_bad_password_without_bloks_hash_preserves_original_error(self):
        client = Client()
        client.username = "example"
        client.password = "password"
        client.authorization_data = {}
        client.bloks_versioning_id = None
        client.last_json = {"message": "Bad Password", "error_type": "bad_password"}
        client.pre_login_flow = AsyncMock(return_value=True)
        client.password_encrypt = AsyncMock(return_value="enc-password")
        client.private_request = AsyncMock(side_effect=BadPassword("Bad Password", response=Mock(status_code=400)))
        client.bloks_caa_login = AsyncMock(side_effect=AssertionError("Bloks hash is required"))

        with self.assertRaises(BadPassword):
            await client.login_legacy(verification_code="654321")

        client.bloks_caa_login.assert_not_awaited()

    async def test_caa_profile_code_error_is_not_replaced_with_legacy_bad_password(self):
        client = Client()
        original = BadPassword("Bad Password", response=Mock(status_code=400))
        rejection = ChallengeError("CAA profile-code submission failed")
        client.bloks_caa_login = AsyncMock(side_effect=rejection)

        with self.assertRaises(ChallengeError) as raised:
            await client._try_caa_login(original, verification_code="654321")

        self.assertIs(raised.exception, rejection)

    async def test_login_legacy_caa_rate_limit_error_is_not_replaced_and_retains_caa_state(self):
        client = Client()
        client.username = "example"
        client.password = "password"
        client.authorization_data = {}
        client.last_json = {"message": "Bad Password", "error_type": "bad_password"}
        client.last_response = Mock(status_code=400)
        client.pre_login_flow = AsyncMock(return_value=True)
        client.password_encrypt = AsyncMock(return_value="enc-password")
        client.private_request = AsyncMock(side_effect=BadPassword("Bad Password", response=client.last_response))
        caa_json = {"status": "fail", "error_type": "rate_limit_error"}
        caa_response = Mock(status_code=429)
        rejection = RateLimitError("CAA login is rate limited", response=caa_response)

        async def rate_limited_caa(**kwargs):
            client.last_json = caa_json
            client.last_response = caa_response
            raise rejection

        client.bloks_caa_login = AsyncMock(side_effect=rate_limited_caa)

        with self.assertRaises(RateLimitError) as raised:
            await client.login_legacy(verification_code="654321")

        self.assertIs(raised.exception, rejection)
        self.assertEqual(client.last_json, caa_json)
        self.assertIs(client.last_response, caa_response)

    async def test_caa_account_suspension_is_not_replaced_with_legacy_bad_password(self):
        client = Client()
        original = BadPassword("Bad Password", response=Mock(status_code=400))
        rejection = AccountSuspended("CAA account suspension")
        client.bloks_caa_login = AsyncMock(side_effect=rejection)

        with self.assertRaises(AccountSuspended) as raised:
            await client._try_caa_login(original, verification_code="654321")

        self.assertIs(raised.exception, rejection)

    async def test_caa_legacy_two_step_context_requires_a_verification_code(self):
        client = Client()
        original = BadPassword("Bad Password", response=Mock(status_code=400))
        client.bloks_caa_login = AsyncMock(
            return_value={"logged_in": False, "two_step_verification_context": "legacy-context"}
        )

        with self.assertRaises(TwoFactorRequired) as raised:
            await client._try_caa_login(original)

        self.assertIn("provide verification_code", str(raised.exception))

    async def test_caa_legacy_two_step_context_delegates_supplied_code(self):
        client = Client()
        original = BadPassword("Bad Password", response=Mock(status_code=400))
        client.bloks_caa_login = AsyncMock(
            return_value={"logged_in": False, "two_step_verification_context": "legacy-context"}
        )
        client._login_with_bloks_two_factor = AsyncMock(return_value=True)

        result = await client._try_caa_login(original, verification_code="654321")

        self.assertTrue(result)
        client._login_with_bloks_two_factor.assert_awaited_once_with(
            "654321",
            {"two_step_verification_context": "legacy-context"},
            original,
        )


class LegacyNeedsUpgradeAuthRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = Client()
        self.client.username = "example"
        self.client.password = "password"
        self.client.authorization_data = {}
        self.legacy_json = {
            "message": "Your version of Instagram is out of date.",
            "error_type": "needs_upgrade",
        }
        self.legacy_response = Mock(status_code=400)
        self.original = UnknownError(
            self.legacy_json["message"], error_type="needs_upgrade", response=self.legacy_response
        )
        self.client.last_json = self.legacy_json
        self.client.last_response = self.legacy_response
        self.client.pre_login_flow = AsyncMock(return_value=True)
        self.client.password_encrypt = AsyncMock(return_value="enc-password")
        self.client.private_request = AsyncMock(side_effect=self.original)
        self.client.login_flow = AsyncMock()
        self.client.bloks_caa_login = AsyncMock(return_value={"logged_in": True})

    async def test_needs_upgrade_tries_caa_and_completes_login(self):
        self.client.last_login = None
        self.client.relogin_attempt = 1

        result = await self.client.login_legacy(verification_code="654321")

        self.assertTrue(result)
        self.client.bloks_caa_login.assert_awaited_once_with(verification_code="654321")
        self.client.login_flow.assert_awaited_once_with()
        self.assertIsInstance(self.client.last_login, float)
        self.assertEqual(self.client.relogin_attempt, 0)
        self.assertEqual(self.client.private_request.await_count, 1)

    async def test_needs_upgrade_normalizes_error_type(self):
        self.original.error_type = "  NeEdS_UpGrAdE\t"

        result = await self.client.login_legacy()

        self.assertTrue(result)
        self.client.bloks_caa_login.assert_awaited_once_with(verification_code="")
        self.client.login_flow.assert_awaited_once_with()

    async def test_needs_upgrade_preserves_legacy_error_when_caa_has_no_session(self):
        async def caa_without_session(**kwargs):
            self.client.last_json = {"status": "ok", "step": "caa"}
            self.client.last_response = Mock(status_code=200)
            return {"logged_in": False, "two_step_verification_context": "", "reason": "no session"}

        self.client.bloks_caa_login.side_effect = caa_without_session

        with self.assertRaises(UnknownError) as raised:
            await self.client.login_legacy(verification_code="654321")

        self.assertIs(raised.exception, self.original)
        self.assertIs(raised.exception.response, self.legacy_response)
        self.client.bloks_caa_login.assert_awaited_once_with(verification_code="654321")
        self.assertEqual(self.client.last_json, self.legacy_json)
        self.assertIs(self.client.last_response, self.legacy_response)
        self.client.login_flow.assert_not_awaited()
        self.assertEqual(self.client.private_request.await_count, 1)

    async def test_unrelated_unknown_error_does_not_try_caa(self):
        for context in ({}, {"error_type": None}, {"error_type": "temporary_error"}):
            with self.subTest(context=context):
                original = UnknownError("Login failed", response=self.legacy_response, **context)
                self.client.private_request.side_effect = original

                with self.assertRaises(UnknownError) as raised:
                    await self.client.login_legacy(verification_code="654321")

                self.assertIs(raised.exception, original)
                self.client.bloks_caa_login.assert_not_awaited()
                self.client.login_flow.assert_not_awaited()

    async def test_needs_upgrade_caa_typed_failures_propagate(self):
        for error_class in (ChallengeError, TwoFactorRequired, RateLimitError, AccountSuspended):
            with self.subTest(error_class=error_class):
                caa_json = {"status": "fail", "step": "caa"}
                caa_response = Mock(status_code=400)
                rejection = error_class("CAA login failed", response=caa_response)

                async def rejected_caa(**kwargs):
                    self.client.last_json = caa_json
                    self.client.last_response = caa_response
                    raise rejection

                self.client.bloks_caa_login.side_effect = rejected_caa

                with self.assertRaises(error_class) as raised:
                    await self.client.login_legacy(verification_code="654321")

                self.assertIs(raised.exception, rejection)
                self.assertEqual(self.client.last_json, caa_json)
                self.assertIs(self.client.last_response, caa_response)
                self.client.login_flow.assert_not_awaited()

    async def test_needs_upgrade_caa_cancellation_propagates(self):
        cancellation = asyncio.CancelledError()
        self.client.bloks_caa_login.side_effect = cancellation

        with self.assertRaises(asyncio.CancelledError) as raised:
            await self.client.login_legacy()

        self.assertIs(raised.exception, cancellation)
        self.client.bloks_caa_login.assert_awaited_once_with(verification_code="")
        self.client.login_flow.assert_not_awaited()
        self.assertEqual(self.client.private_request.await_count, 1)

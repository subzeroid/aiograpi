import asyncio
import inspect
import unittest
from copy import deepcopy
from unittest.mock import AsyncMock, Mock, patch

from aiograpi import Client, config
from aiograpi.exceptions import (
    BadCredentials,
    BadPassword,
    ChallengeError,
    ClientError,
    ClientNotFoundError,
    LoginRequired,
    PleaseWaitFewMinutes,
    ReloginAttemptExceeded,
    TwoFactorRequired,
    UnknownError,
)


class LoginDefaultRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = Client(private_transport="requests")
        self.client.pre_login_flow = AsyncMock(side_effect=AssertionError("Unexpected legacy preflight"))
        self.client.password_encrypt = AsyncMock(side_effect=AssertionError("Unexpected legacy encryption"))
        self.client.private_request = AsyncMock(side_effect=AssertionError("Unexpected legacy request"))
        self.client.login_flow = AsyncMock()
        self.client.bloks_caa_login = AsyncMock(side_effect=self.caa_success)

    def caa_success(self, **kwargs):
        self.client.authorization_data = {"ds_user_id": "123", "sessionid": "fresh"}
        return self.caa_outcome(logged_in=True)

    def caa_outcome(self, **updates):
        outcome = {
            "logged_in": False,
            "two_step_verification_context": "",
            "result": {},
            "two_step": {},
            "reason": "CAA login did not return a session",
        }
        outcome.update(updates)
        return outcome

    def legacy_success(self):
        self.client.pre_login_flow = AsyncMock(return_value=True)
        self.client.password_encrypt = AsyncMock(return_value="encrypted")
        self.client.private_request = AsyncMock(return_value=True)
        self.client.last_response = Mock(headers={"ig-set-authorization": "Bearer fresh"})
        self.client.parse_authorization = Mock(return_value={"ds_user_id": "123", "sessionid": "fresh"})
        self.client.bloks_caa_login = AsyncMock(side_effect=AssertionError("Unexpected CAA fallback"))

    def saved_session(self):
        self.client.authorization_data = {"ds_user_id": "123", "sessionid": "stale"}
        self.client.private.set_cookies({"sessionid": "stale"})
        self.client.public.set_cookies({"sessionid": "public-stale"})
        self.client.private.headers["Authorization"] = "Bearer stale"

    def assert_session_cleared(self):
        self.assertNotIn("Authorization", self.client.private.headers)
        self.assertEqual(self.client.private.cookies_dict(), {})
        self.assertEqual(self.client.public.cookies_dict(), {})

    async def test_login_uses_caa_directly_and_finalizes_success(self):
        self.client.relogin_attempt = 1
        with patch("aiograpi.mixins.auth.time.time", return_value=1234567890.0):
            result = await self.client.login(" example ", "password", False, "654321")

        self.assertTrue(result)
        self.assertEqual(self.client.username, "example")
        self.assertEqual(self.client.password, "password")
        self.assertEqual(self.client.authorization_data["sessionid"], "fresh")
        self.client.bloks_caa_login.assert_awaited_once_with(verification_code="654321")
        self.client.pre_login_flow.assert_not_awaited()
        self.client.password_encrypt.assert_not_awaited()
        self.client.private_request.assert_not_awaited()
        self.client.login_flow.assert_awaited_once_with()
        self.assertEqual(self.client.last_login, 1234567890.0)
        self.assertEqual(self.client.relogin_attempt, 0)

    async def test_login_uses_stored_credentials(self):
        self.client.username = " example "
        self.client.password = "password"

        self.assertTrue(await self.client.login())

        self.assertEqual(self.client.username, "example")
        self.client.bloks_caa_login.assert_awaited_once_with(verification_code="")

    async def test_login_and_legacy_keep_the_same_call_signature(self):
        self.assertTrue(hasattr(Client, "login_legacy"))
        self.assertEqual(inspect.signature(Client.login), inspect.signature(Client.login_legacy))

    async def test_both_entrypoints_require_credentials_before_network_calls(self):
        self.assertTrue(hasattr(Client, "login_legacy"))
        for entrypoint in ("login", "login_legacy"):
            with self.subTest(entrypoint=entrypoint):
                with self.assertRaises(BadCredentials):
                    await getattr(self.client, entrypoint)()
        self.client.bloks_caa_login.assert_not_awaited()
        self.client.pre_login_flow.assert_not_awaited()

    async def test_legacy_login_keeps_accounts_endpoint_and_preflight(self):
        self.assertTrue(hasattr(Client, "login_legacy"))
        self.legacy_success()

        self.assertTrue(await self.client.login_legacy(" example ", "password", False, "654321"))

        self.client.pre_login_flow.assert_awaited_once_with()
        self.client.password_encrypt.assert_awaited_once_with("password")
        self.client.private_request.assert_awaited_once()
        self.assertEqual(self.client.private_request.await_args.args[0], "accounts/login/")
        self.assertEqual(self.client.private_request.await_args.args[1]["username"], "example")
        self.client.bloks_caa_login.assert_not_awaited()
        self.client.login_flow.assert_awaited_once_with()

    async def test_both_entrypoints_validate_saved_sessions_without_submitting_credentials(self):
        self.assertTrue(hasattr(Client, "login_legacy"))
        self.saved_session()
        self.client.account_info = AsyncMock(return_value=object())
        self.client.last_login = 123.0
        for entrypoint in ("login", "login_legacy"):
            with self.subTest(entrypoint=entrypoint):
                self.assertTrue(await getattr(self.client, entrypoint)("example", "password"))
        self.assertEqual(self.client.account_info.await_count, 2)
        self.client.bloks_caa_login.assert_not_awaited()
        self.client.pre_login_flow.assert_not_awaited()
        self.client.login_flow.assert_not_awaited()
        self.assertEqual(self.client.last_login, 123.0)

    async def test_expired_session_is_cleared_and_refreshed_with_caa(self):
        self.saved_session()
        self.client.account_info = AsyncMock(side_effect=LoginRequired())

        self.assertTrue(await self.client.login("example", "password", verification_code="654321"))

        self.client.account_info.assert_awaited_once_with()
        self.client.bloks_caa_login.assert_awaited_once_with(verification_code="654321")
        self.assert_session_cleared()
        self.assertEqual(self.client.authorization_data["sessionid"], "fresh")
        self.assertEqual(self.client.relogin_attempt, 0)

    async def test_expired_legacy_session_stays_on_legacy_entrypoint(self):
        self.assertTrue(hasattr(Client, "login_legacy"))
        self.saved_session()
        self.legacy_success()
        self.client.account_info = AsyncMock(side_effect=LoginRequired())

        self.assertTrue(await self.client.login_legacy("example", "password", verification_code="654321"))

        self.client.account_info.assert_awaited_once_with()
        self.client.pre_login_flow.assert_awaited_once_with()
        self.assertEqual(self.client.private_request.await_args.args[0], "accounts/login/")
        self.client.bloks_caa_login.assert_not_awaited()
        self.assert_session_cleared()
        self.assertEqual(self.client.authorization_data["sessionid"], "fresh")

    async def test_relogin_clears_session_without_validation(self):
        self.saved_session()
        self.client.account_info = AsyncMock(side_effect=AssertionError("Unexpected session validation"))

        self.assertTrue(await self.client.login("example", "password", relogin=True))

        self.assert_session_cleared()
        self.client.account_info.assert_not_awaited()
        self.client.bloks_caa_login.assert_awaited_once_with(verification_code="")
        self.assertEqual(self.client.relogin_attempt, 0)

    async def test_failed_relogin_attempts_are_bounded_for_both_entrypoints(self):
        self.assertTrue(hasattr(Client, "login_legacy"))
        for entrypoint in ("login", "login_legacy"):
            with self.subTest(entrypoint=entrypoint):
                self.client.relogin_attempt = 0
                self.client.pre_login_flow = AsyncMock(return_value=True)
                self.client.password_encrypt = AsyncMock(return_value="encrypted")
                self.client.private_request = AsyncMock(side_effect=PleaseWaitFewMinutes("rate limit"))
                self.client.bloks_caa_login = AsyncMock(side_effect=PleaseWaitFewMinutes("rate limit"))
                for attempt in (1, 2):
                    self.saved_session()
                    with self.assertRaises(PleaseWaitFewMinutes):
                        await getattr(self.client, entrypoint)("example", "password", relogin=True)
                    self.assertEqual(self.client.relogin_attempt, attempt)
                    self.assert_session_cleared()
                    self.assertEqual(self.client.authorization_data, {})
                self.saved_session()
                with self.assertRaises(ReloginAttemptExceeded):
                    await getattr(self.client, entrypoint)(relogin=True)
                self.assert_session_cleared()
                self.assertEqual(self.client.authorization_data, {})
                request = self.client.bloks_caa_login if entrypoint == "login" else self.client.private_request
                self.assertEqual(request.call_count, 2)

    async def test_default_propagates_native_caa_errors_without_retry_or_finalization(self):
        for exception_type in (
            BadPassword,
            ClientNotFoundError,
            UnknownError,
            ChallengeError,
            TwoFactorRequired,
            LoginRequired,
            PleaseWaitFewMinutes,
            ClientError,
        ):
            with self.subTest(exception_type=exception_type):
                error = exception_type("native CAA failure")
                self.client.bloks_caa_login = AsyncMock(side_effect=error)
                with self.assertRaises(exception_type) as caught:
                    await self.client.login("example", "password", verification_code="654321")
                self.assertIs(caught.exception, error)
                self.client.bloks_caa_login.assert_awaited_once_with(verification_code="654321")
        self.client.pre_login_flow.assert_not_awaited()
        self.client.private_request.assert_not_awaited()
        self.client.login_flow.assert_not_awaited()
        self.assertIsNone(self.client.last_login)

    async def test_session_validation_failure_is_not_retried_as_login(self):
        self.saved_session()
        error = PleaseWaitFewMinutes("validation rate limit")
        self.client.account_info = AsyncMock(side_effect=error)

        with self.assertRaises(PleaseWaitFewMinutes) as caught:
            await self.client.login("example", "password")

        self.assertIs(caught.exception, error)
        self.client.bloks_caa_login.assert_not_awaited()
        self.assertEqual(self.client.authorization_data["sessionid"], "stale")

    async def test_caa_outcome_without_session_raises_its_reason(self):
        self.client.bloks_caa_login = AsyncMock(return_value=self.caa_outcome(reason="CAA preflight was incomplete"))

        with self.assertRaisesRegex(ClientError, "CAA preflight was incomplete"):
            await self.client.login("example", "password")

        self.client.bloks_caa_login.assert_awaited_once_with(verification_code="")
        self.client.login_flow.assert_not_awaited()
        self.client.pre_login_flow.assert_not_awaited()

    async def test_caa_outcome_without_reason_has_clear_error(self):
        self.client.bloks_caa_login = AsyncMock(return_value=self.caa_outcome(reason=""))

        with self.assertRaisesRegex(ClientError, "CAA login did not return a session"):
            await self.client.login("example", "password")

    async def test_caa_two_factor_context_requires_a_code(self):
        self.client.bloks_caa_login = AsyncMock(
            return_value=self.caa_outcome(two_step_verification_context="context-1")
        )

        with self.assertRaisesRegex(TwoFactorRequired, "verification_code"):
            await self.client.login("example", "password", verification_code=" ")

        self.client.bloks_caa_login.assert_awaited_once_with(verification_code=" ")
        self.client.login_flow.assert_not_awaited()
        self.client.private_request.assert_not_awaited()

    async def test_caa_context_selects_totp_sms_and_normalized_backup_codes(self):
        for code, challenge, flags, expected_code in (
            ("654321", "totp", {"totp_two_factor_on": True}, "654321"),
            ("654321", "sms", {"sms_two_factor_on": True}, "654321"),
            ("1234 5678", "backup_codes", {"totp_two_factor_on": True}, "12345678"),
        ):
            with self.subTest(challenge=challenge):
                self.client.bloks_caa_login = AsyncMock(
                    return_value=self.caa_outcome(
                        two_step_verification_context="context-1",
                        result={"two_factor_info": flags},
                    )
                )
                self.client.bloks_two_step_verification_entrypoint = AsyncMock(return_value={"status": "ok"})
                self.client.bloks_two_step_verification_method_picker = AsyncMock(return_value={"status": "ok"})
                self.client.bloks_two_step_verification_select_method = AsyncMock(return_value={"status": "ok"})
                self.client.bloks_two_step_verification_enter_backup_code = AsyncMock(return_value={"status": "ok"})
                self.client.bloks_two_step_verification_verify_code = AsyncMock(return_value={"layout": {}})
                self.client.bloks_apply_login_response = Mock(return_value=True)

                self.assertTrue(await self.client.login("example", "password", verification_code=code))

                self.client.bloks_caa_login.assert_awaited_once_with(verification_code=code)
                self.client.bloks_two_step_verification_entrypoint.assert_awaited_once_with("context-1")
                self.client.bloks_two_step_verification_select_method.assert_awaited_once_with(
                    "context-1", selected_method=challenge
                )
                self.client.bloks_two_step_verification_verify_code.assert_awaited_once_with(
                    "context-1", expected_code, challenge=challenge
                )
                self.client.bloks_apply_login_response.assert_called_once_with({"layout": {}})
                if challenge == "backup_codes":
                    self.client.bloks_two_step_verification_enter_backup_code.assert_awaited_once_with("context-1")
                else:
                    self.client.bloks_two_step_verification_enter_backup_code.assert_not_awaited()
        self.assertEqual(self.client.login_flow.await_count, 3)
        self.client.private_request.assert_not_awaited()

    async def test_context_verification_error_is_not_retried(self):
        self.client.bloks_caa_login = AsyncMock(
            return_value=self.caa_outcome(two_step_verification_context="context-1")
        )
        error = TwoFactorRequired("Incorrect verification code")
        self.client.bloks_two_step_verification_entrypoint = AsyncMock(side_effect=error)

        with self.assertRaises(TwoFactorRequired) as caught:
            await self.client.login("example", "password", verification_code="654321")

        self.assertIs(caught.exception, error)
        self.client.bloks_caa_login.assert_awaited_once_with(verification_code="654321")
        self.client.login_flow.assert_not_awaited()

    async def test_completed_caa_verification_does_not_submit_code_again(self):
        self.client.bloks_caa_login = AsyncMock(
            return_value=self.caa_outcome(logged_in=True, two_step={"logged_in": True})
        )
        self.client.bloks_two_step_verification_entrypoint = AsyncMock(
            side_effect=AssertionError("Unexpected repeated two-factor verification")
        )

        self.assertTrue(await self.client.login("example", "password", verification_code="654321"))

        self.client.bloks_caa_login.assert_awaited_once_with(verification_code="654321")
        self.client.bloks_two_step_verification_entrypoint.assert_not_awaited()
        self.client.login_flow.assert_awaited_once_with()

    async def test_caa_cancellation_propagates_without_retry_or_finalization(self):
        self.client.bloks_caa_login = AsyncMock(side_effect=asyncio.CancelledError())

        with self.assertRaises(asyncio.CancelledError):
            await self.client.login("example", "password")

        self.client.bloks_caa_login.assert_awaited_once_with(verification_code="")
        self.client.pre_login_flow.assert_not_awaited()
        self.client.private_request.assert_not_awaited()
        self.client.login_flow.assert_not_awaited()

    def old_app_settings(self):
        settings = deepcopy(self.client.get_settings())
        settings["device_settings"].update({"app_version": "410.0.0.0.1", "version_code": "123456789"})
        settings["device_settings"].pop("bloks_versioning_id", None)
        return settings

    async def test_missing_saved_app_hash_stops_caa_before_preflight(self):
        settings = self.old_app_settings()
        original_settings = deepcopy(settings)
        for mode in ("fresh", "relogin", "expired"):
            with self.subTest(mode=mode):
                self.client = Client(settings=settings, private_transport="requests")
                self.assertIsNone(self.client.bloks_versioning_id)
                self.client.bloks_caa_login = AsyncMock(wraps=self.client.bloks_caa_login)
                self.client.bloks_caa_login_prepare = AsyncMock(side_effect=AssertionError("Unexpected CAA preflight"))
                self.client.pre_login_flow = AsyncMock(side_effect=AssertionError("Unexpected legacy preflight"))
                self.client.login_legacy = AsyncMock(side_effect=AssertionError("Unexpected legacy fallback"))
                self.client.private_request = AsyncMock(side_effect=AssertionError("Unexpected private request"))
                if mode != "fresh":
                    self.saved_session()
                if mode == "expired":
                    self.client.account_info = AsyncMock(side_effect=LoginRequired())

                with self.assertRaisesRegex(ClientError, "CAA login requires bloks_versioning_id") as caught:
                    await self.client.login("example", "password", relogin=mode == "relogin")

                self.assertIs(type(caught.exception), ClientError)
                self.assertIn("override_app_version=True", str(caught.exception))
                self.assertIn("matching Bloks hash", str(caught.exception))
                self.client.bloks_caa_login.assert_not_awaited()
                self.client.bloks_caa_login_prepare.assert_not_awaited()
                self.client.pre_login_flow.assert_not_awaited()
                self.client.login_legacy.assert_not_awaited()
                self.client.private_request.assert_not_awaited()
                self.assertEqual(self.client.device_settings, settings["device_settings"])
                self.assertEqual(self.client.get_settings()["uuids"], settings["uuids"])
                self.assertEqual(settings, original_settings)
                if mode != "fresh":
                    self.assert_session_cleared()
                    self.assertEqual(self.client.authorization_data, {})

    async def test_saved_session_without_app_hash_can_still_be_reused(self):
        self.client = Client(settings=self.old_app_settings(), private_transport="requests")
        self.assertIsNone(self.client.bloks_versioning_id)
        self.saved_session()
        self.client.account_info = AsyncMock(return_value=object())
        self.client.bloks_caa_login = AsyncMock(side_effect=AssertionError("Unexpected CAA login"))
        self.client.pre_login_flow = AsyncMock(side_effect=AssertionError("Unexpected legacy preflight"))

        self.assertTrue(await self.client.login("example", "password"))

        self.client.account_info.assert_awaited_once_with()
        self.client.bloks_caa_login.assert_not_awaited()
        self.client.pre_login_flow.assert_not_awaited()
        self.assertEqual(self.client.authorization_data["sessionid"], "stale")
        self.assertIsNone(self.client.bloks_versioning_id)

    async def test_app_override_restores_caa_profile_and_preserves_device_uuids_and_proxy(self):
        settings = self.old_app_settings()
        original_settings = deepcopy(settings)
        proxy = "http://127.0.0.1:4321"
        self.client = Client(settings=settings, proxy=proxy, override_app_version=True, private_transport="requests")
        self.client.bloks_caa_login = AsyncMock(side_effect=self.caa_success)
        self.client.login_flow = AsyncMock()
        self.client.pre_login_flow = AsyncMock(side_effect=AssertionError("Unexpected legacy preflight"))
        self.client.private_request = AsyncMock(side_effect=AssertionError("Unexpected private request"))

        self.assertTrue(await self.client.login("example", "password"))

        supported_profile = config.APP_SETTINGS[config.DEFAULT_APP_VERSION]
        for key in ("app_version", "version_code", "bloks_versioning_id"):
            self.assertEqual(self.client.device_settings[key], supported_profile[key])
        self.assertEqual(self.client.bloks_versioning_id, supported_profile["bloks_versioning_id"])
        for key, value in settings["device_settings"].items():
            if key not in {"app_version", "version_code", "bloks_versioning_id"}:
                self.assertEqual(self.client.device_settings[key], value)
        self.assertEqual(self.client.get_settings()["uuids"], settings["uuids"])
        self.assertEqual(self.client.proxy, proxy)
        self.assertEqual(self.client.private.proxy, proxy)
        self.assertEqual(self.client.public.proxy, proxy)
        self.assertEqual(settings, original_settings)
        self.client.bloks_caa_login.assert_awaited_once_with(verification_code="")
        self.client.login_flow.assert_awaited_once_with()

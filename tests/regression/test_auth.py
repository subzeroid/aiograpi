import unittest
from unittest.mock import AsyncMock, Mock

from pydantic import ValidationError

from aiograpi import Client
from aiograpi.exceptions import BadPassword, PrivateError, TwoFactorRequired
from aiograpi.types import UserShort


class AuthRegressionTestCase(unittest.IsolatedAsyncioTestCase):
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

    async def test_login_bad_password_without_context_tries_caa_bloks_context_when_code_provided(self):
        client = Client()
        client.username = "example"
        client.password = "password"
        client.authorization_data = {}
        client.last_json = {"message": "The password you entered is incorrect.", "error_type": "bad_password"}
        client.pre_login_flow = AsyncMock(return_value=True)
        client.password_encrypt = AsyncMock(return_value="enc-password")
        client.login_flow = AsyncMock()
        client.private_request = AsyncMock(side_effect=BadPassword("Bad Password", response=Mock(status_code=400)))
        caa_result = {"layout": {"bloks_payload": {"action": "action-with-context"}}}
        client.bloks_caa_login_send_request = AsyncMock(return_value=caa_result)
        client.bloks_extract_two_step_verification_context = Mock(return_value="context-1")
        client.bloks_two_step_verification_entrypoint = AsyncMock(return_value={"status": "ok"})
        client.bloks_two_step_verification_method_picker = AsyncMock(return_value={"status": "ok"})
        client.bloks_two_step_verification_select_method = AsyncMock(return_value={"status": "ok"})
        client.bloks_two_step_verification_verify_code = AsyncMock(return_value={"layout": {}})
        client.bloks_apply_login_response = Mock(return_value=True)

        result = await client.login(verification_code="654321")

        self.assertTrue(result)
        client.bloks_caa_login_send_request.assert_awaited_once_with("password", login_attempt_count=1)
        client.bloks_extract_two_step_verification_context.assert_called_once_with(caa_result)
        client.bloks_two_step_verification_select_method.assert_awaited_once_with("context-1", selected_method="totp")
        client.bloks_two_step_verification_verify_code.assert_awaited_once_with(
            "context-1",
            "654321",
            challenge="totp",
        )
        client.login_flow.assert_awaited_once_with()

    async def test_login_with_eight_digit_backup_code_selects_backup_code_bloks_challenge(self):
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

        result = await client.login(verification_code="1234 5678")

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

    async def test_login_two_factor_backup_code_with_context_uses_bloks_without_legacy_two_factor_request(self):
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

        result = await client.login(verification_code="1234 5678")

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

    async def test_login_bad_password_without_context_raises_clear_error_when_caa_has_no_context(self):
        client = Client()
        client.username = "example"
        client.password = "password"
        client.authorization_data = {}
        client.last_json = {"message": "The password you entered is incorrect.", "error_type": "bad_password"}
        client.pre_login_flow = AsyncMock(return_value=True)
        client.password_encrypt = AsyncMock(return_value="enc-password")
        client.private_request = AsyncMock(side_effect=BadPassword("Bad Password", response=Mock(status_code=400)))
        client.bloks_caa_login_send_request = AsyncMock(return_value={"layout": {"bloks_payload": {"action": ""}}})
        client.bloks_extract_two_step_verification_context = Mock(return_value="")
        client.bloks_two_step_verification_verify_code = AsyncMock()

        with self.assertRaises(TwoFactorRequired) as cm:
            await client.login(verification_code="654321")

        self.assertIn("CAA response did not include two_step_verification_context", str(cm.exception))
        client.bloks_caa_login_send_request.assert_awaited_once_with("password", login_attempt_count=1)
        client.bloks_two_step_verification_verify_code.assert_not_awaited()

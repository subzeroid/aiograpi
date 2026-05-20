import unittest
from unittest.mock import AsyncMock, Mock

from aiograpi import Client
from aiograpi.exceptions import BadPassword, TwoFactorRequired


class AuthRegressionTestCase(unittest.IsolatedAsyncioTestCase):
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

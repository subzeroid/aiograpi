import base64
import unittest
from unittest.mock import AsyncMock, patch

from aiograpi import Client
from aiograpi.exceptions import ChallengeRequired
from aiograpi.utils.serialization import dumps


class BloksRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    def build_client(self):
        client = Client()
        client.uuid = "uuid-1"
        client.bloks_versioning_id = "bloks-version"
        return client

    async def test_challenge_resolve_simple_bloks_redirect_step_raises_clear_manual_error(self):
        client = self.build_client()
        client.username = "example"
        client.last_json = {
            "message": "challenge_required",
            "status": "ok",
            "step_name": "STEP_NAME",
            "flow_render_type": 3,
            "bloks_action": "com.bloks.www.ig.challenge.redirect.async",
            "challenge_context": "opaque-context",
            "challenge_type_enum_str": "SUSPICIOUS_LOGIN",
        }

        with self.assertRaises(ChallengeRequired) as cm:
            await client.challenge_resolve_simple("challenge/test/")

        self.assertIn("Bloks redirect checkpoint", str(cm.exception))
        self.assertIn("official Instagram app", str(cm.exception))
        self.assertEqual(cm.exception.step_name, "STEP_NAME")
        self.assertEqual(cm.exception.bloks_action, "com.bloks.www.ig.challenge.redirect.async")

    async def test_bloks_async_action_posts_unsigned_bloks_payload(self):
        client = self.build_client()
        params = {"server_params": {"flow": "example_flow"}}
        expected = {"status": "ok"}
        client.private_request = AsyncMock(return_value=expected)

        result = await client.bloks_async_action("com.example.action", params)

        self.assertEqual(result, expected)
        client.private_request.assert_awaited_once_with(
            "bloks/async_action/com.example.action/",
            data={
                "params": dumps(params),
                "_uuid": "uuid-1",
                "bk_client_context": dumps({"bloks_version": "bloks-version", "styles_id": "instagram"}),
                "bloks_versioning_id": "bloks-version",
            },
            with_signature=False,
        )

    async def test_bloks_app_posts_unsigned_bloks_payload(self):
        client = self.build_client()
        params = {"server_params": {"flow": "example_flow"}}
        expected = {"status": "ok"}
        client.private_request = AsyncMock(return_value=expected)

        result = await client.bloks_app("com.example.app", params)

        self.assertEqual(result, expected)
        client.private_request.assert_awaited_once_with(
            "bloks/apps/com.example.app/",
            data={
                "params": dumps(params),
                "_uuid": "uuid-1",
                "bk_client_context": dumps({"bloks_version": "bloks-version", "styles_id": "instagram"}),
                "bloks_versioning_id": "bloks-version",
            },
            with_signature=False,
        )

    async def test_bloks_challenge_take_challenge_posts_unsigned_direct_payload(self):
        client = self.build_client()
        challenge_context = "Af4sGj7RsOARkOpaqueContext"
        expected = {"status": "ok"}
        client.private_request = AsyncMock(return_value=expected)

        result = await client.bloks_challenge_take_challenge(
            challenge_context=challenge_context,
            choice=0,
            extra_data={"is_bloks_web": False},
        )

        self.assertEqual(result, expected)
        client.private_request.assert_awaited_once_with(
            "bloks/apps/com.instagram.challenge.navigation.take_challenge/",
            data={
                "_uuid": "uuid-1",
                "has_follow_up_screens": "0",
                "bk_client_context": dumps({"bloks_version": "bloks-version", "styles_id": "instagram"}),
                "bloks_versioning_id": "bloks-version",
                "challenge_context": challenge_context,
                "choice": "0",
                "is_bloks_web": False,
            },
            with_signature=False,
        )

    async def test_bloks_change_password_preserves_opaque_challenge_context(self):
        client = self.build_client()
        challenge_context = "Af4sGj7RsOARkOpaqueContext"
        client.password_encrypt = AsyncMock(return_value="#PWD_INSTAGRAM:4:1:encrypted")
        client.private_request = AsyncMock(return_value={"status": "ok"})

        result = await client.bloks_change_password("new-password", challenge_context)

        self.assertTrue(result)
        client.private_request.assert_awaited_once_with(
            "bloks/apps/com.instagram.challenge.navigation.take_challenge/",
            data={
                "_uuid": "uuid-1",
                "has_follow_up_screens": "0",
                "bk_client_context": dumps({"bloks_version": "bloks-version", "styles_id": "instagram"}),
                "bloks_versioning_id": "bloks-version",
                "challenge_context": challenge_context,
                "enc_new_password1": "#PWD_INSTAGRAM:4:1:encrypted",
                "enc_new_password2": "#PWD_INSTAGRAM:4:1:encrypted",
            },
            with_signature=False,
        )

    async def test_bloks_fxcal_link_reels_share_uses_current_flow_payload(self):
        client = self.build_client()
        expected = {"status": "ok"}
        client.bloks_async_action = AsyncMock(return_value=expected)

        result = await client.bloks_fxcal_link_reels_share(cds_client_value=2)

        self.assertEqual(result, expected)
        client.bloks_async_action.assert_awaited_once_with(
            "com.bloks.www.fxcal.link.async",
            {
                "server_params": {
                    "flow": "ig_fb_reels_composer_rowshare",
                    "logging_event": "linking_flow_initiated",
                    "cds_client_value": 2,
                    "opaque_verified_native_auth_data": None,
                    "native_auth_data": [],
                    "account_type": 0,
                }
            },
            bloks_versioning_id="",
        )

    async def test_bloks_two_step_verification_entrypoint_uses_current_payload(self):
        client = self.build_client()
        client.android_device_id = "android-1"
        client.phone_id = "family-device-1"
        client.mid = "machine-1"
        expected = {"status": "ok"}
        client.bloks_app = AsyncMock(return_value=expected)

        result = await client.bloks_two_step_verification_entrypoint(
            "context-1",
            screen_id="screen-1",
            should_fallback_to_sms=True,
        )

        self.assertEqual(result, expected)
        client.bloks_app.assert_awaited_once_with(
            "com.bloks.www.two_step_verification.entrypoint",
            {
                "client_input_params": {
                    "device_id": "android-1",
                    "is_whatsapp_installed": 0,
                    "machine_id": "machine-1",
                },
                "server_params": {
                    "should_fallback_to_sms": 1,
                    "family_device_id": "family-device-1",
                    "device_id": "android-1",
                    "INTERNAL_INFRA_screen_id": "screen-1",
                    "two_step_verification_context": "context-1",
                    "flow_source": "two_factor_login",
                },
            },
            bloks_versioning_id="",
        )

    async def test_bloks_two_step_verification_method_picker_uses_current_payload(self):
        client = self.build_client()
        client.android_device_id = "android-1"
        expected = {"status": "ok"}
        client.bloks_app = AsyncMock(return_value=expected)

        result = await client.bloks_two_step_verification_method_picker("context-1")

        self.assertEqual(result, expected)
        client.bloks_app.assert_awaited_once_with(
            "com.bloks.www.two_step_verification.method_picker",
            {
                "client_input_params": {"is_whatsapp_installed": 0},
                "server_params": {
                    "should_fallback_to_sms": 0,
                    "device_id": "android-1",
                    "two_step_verification_context": "context-1",
                    "flow_source": "two_factor_login",
                },
            },
            bloks_versioning_id="",
        )

    async def test_bloks_two_step_verification_select_method_uses_current_payload(self):
        client = self.build_client()
        client.android_device_id = "android-1"
        expected = {"status": "ok"}
        client.bloks_async_action = AsyncMock(return_value=expected)

        result = await client.bloks_two_step_verification_select_method(
            "context-1",
            selected_method="sms",
            latency_qpl_marker_id=36707139,
            latency_qpl_instance_id=123,
        )

        self.assertEqual(result, expected)
        client.bloks_async_action.assert_awaited_once_with(
            "com.bloks.www.two_step_verification.method_picker.navigation.async",
            {
                "client_input_params": {
                    "selected_method": "sms",
                    "cloud_trust_token": None,
                    "network_bssid": None,
                },
                "server_params": {
                    "should_fallback_to_sms": 0,
                    "INTERNAL__latency_qpl_marker_id": 36707139,
                    "device_id": "android-1",
                    "spectra_reg_login_data": None,
                    "INTERNAL__latency_qpl_instance_id": 123,
                    "two_step_verification_context": "context-1",
                    "flow_source": "two_factor_login",
                },
            },
            bloks_versioning_id="",
        )

    async def test_bloks_two_step_verification_verify_code_uses_current_payload(self):
        client = self.build_client()
        client.android_device_id = "android-1"
        client.phone_id = "family-device-1"
        client.mid = "machine-1"
        expected = {"status": "ok"}
        client.bloks_async_action = AsyncMock(return_value=expected)

        result = await client.bloks_two_step_verification_verify_code(
            "context-1",
            "123456",
            challenge="sms",
            should_trust_device=False,
        )

        self.assertEqual(result, expected)
        client.bloks_async_action.assert_awaited_once_with(
            "com.bloks.www.two_step_verification.verify_code.async",
            {
                "client_input_params": {
                    "auth_secure_device_id": "",
                    "block_store_machine_id": "",
                    "code": "123456",
                    "should_trust_device": 0,
                    "family_device_id": "family-device-1",
                    "device_id": "android-1",
                    "cloud_trust_token": None,
                    "network_bssid": None,
                    "machine_id": "machine-1",
                },
                "server_params": {
                    "should_fallback_to_sms": 0,
                    "device_id": "android-1",
                    "spectra_reg_login_data": None,
                    "challenge": "sms",
                    "two_step_verification_context": "context-1",
                    "flow_source": "two_factor_login",
                },
            },
            bloks_versioning_id="",
        )

    async def test_bloks_two_step_verification_enter_backup_code_uses_current_payload(self):
        client = self.build_client()
        client.android_device_id = "android-1"
        expected = {"status": "ok"}
        client.bloks_app = AsyncMock(return_value=expected)

        result = await client.bloks_two_step_verification_enter_backup_code(
            "context-1",
            screen_id="screen-1",
        )

        self.assertEqual(result, expected)
        client.bloks_app.assert_awaited_once_with(
            "com.bloks.www.two_factor_login.enter_backup_code",
            {
                "server_params": {
                    "device_id": "android-1",
                    "INTERNAL_INFRA_screen_id": "screen-1",
                    "two_step_verification_context": "context-1",
                    "flow_source": "two_factor_login",
                },
            },
            bloks_versioning_id="",
        )

    async def test_bloks_caa_login_send_request_uses_current_payload(self):
        client = self.build_client()
        client.username = "example"
        client.android_device_id = "android-1"
        client.phone_id = "family-device-1"
        client.uuid = "uuid-1"
        client.mid = "machine-1"
        client.password_encrypt = AsyncMock(return_value="#PWD_INSTAGRAM:4:1:encrypted")
        expected = {"status": "ok"}

        with patch.object(client, "bloks_async_action", new=AsyncMock(return_value=expected)) as bloks_async_action:
            result = await client.bloks_caa_login_send_request("password", login_attempt_count=1)

        self.assertEqual(result, expected)
        bloks_async_action.assert_awaited_once()
        action, params = bloks_async_action.call_args.args[:2]
        self.assertEqual(action, "com.bloks.www.bloks.caa.login.async.send_login_request")
        self.assertEqual(params["client_input_params"]["contact_point"], "example")
        self.assertEqual(params["client_input_params"]["password"], "#PWD_INSTAGRAM:4:1:encrypted")
        self.assertEqual(params["client_input_params"]["device_id"], "android-1")
        self.assertEqual(params["client_input_params"]["family_device_id"], "family-device-1")
        self.assertEqual(params["client_input_params"]["machine_id"], "machine-1")
        self.assertEqual(params["client_input_params"]["login_attempt_count"], 1)
        self.assertEqual(params["client_input_params"]["try_num"], 1)
        self.assertEqual(params["server_params"]["login_credential_type"], "none")
        self.assertEqual(params["server_params"]["credential_type"], "password")
        self.assertEqual(params["server_params"]["family_device_id"], "family-device-1")
        self.assertEqual(params["server_params"]["device_id"], "android-1")
        self.assertIn("waterfall_id", params["server_params"])

    async def test_bloks_extract_two_step_verification_context_from_caa_action(self):
        client = self.build_client()
        result = {
            "layout": {
                "bloks_payload": {
                    "action": (
                        '(... "com.bloks.www.two_step_verification.entrypoint" '
                        '(dkc "server_params" "client_input_params") '
                        '(dkc (f4i (dkc "two_step_verification_context" "flow_source" '
                        '"device_id" "should_fallback_to_sms" "family_device_id" '
                        '"INTERNAL_INFRA_screen_id") '
                        '(dkc "context-1" "two_factor_login" "android-1" 0 '
                        '"family-device-1" "screen-1"))))'
                    )
                }
            }
        }

        self.assertEqual(client.bloks_extract_two_step_verification_context(result), "context-1")

    async def test_bloks_extract_login_response_parses_embedded_action_payload(self):
        client = self.build_client()
        login_payload = {
            "login_response": dumps(
                {
                    "logged_in_user": {"pk": 123, "username": "example"},
                    "trusted_device_nonce": "nonce-1",
                    "credential_type": "password",
                }
            ),
            "headers": dumps({"IG-Set-Authorization": "Bearer IGT:2:encoded"}),
            "cookies": (
                "Set-Cookie: csrftoken=token-1; Domain=.instagram.com; Path=/; Secure\r\n"
                "Set-Cookie: ds_user_id=123; Domain=.instagram.com; Path=/; Secure\r\n"
                "Set-Cookie: sessionid=123%3Aabc; Domain=.instagram.com; Path=/; Secure"
            ),
            "exact_profile_identified": "1",
        }
        result = {
            "layout": {
                "bloks_payload": {
                    "action": f"BK.action({dumps('ignored')}, {dumps(dumps(login_payload))})",
                }
            }
        }

        parsed = client.bloks_extract_login_response(result)

        self.assertEqual(parsed["login_response"]["logged_in_user"]["username"], "example")
        self.assertEqual(parsed["headers"]["IG-Set-Authorization"], "Bearer IGT:2:encoded")
        self.assertEqual(parsed["cookies"]["sessionid"], "123%3Aabc")
        self.assertEqual(parsed["raw_cookies"], login_payload["cookies"])
        self.assertEqual(parsed["raw"]["exact_profile_identified"], "1")

    async def test_bloks_apply_login_response_updates_client_session(self):
        client = self.build_client()
        authorization_data = {
            "ds_user_id": "123",
            "sessionid": "123%3Aabc",
            "should_use_header_over_cookies": True,
        }
        authorization = "Bearer IGT:2:" + base64.b64encode(dumps(authorization_data).encode()).decode()

        result = client.bloks_apply_login_response(
            {
                "headers": {
                    "IG-Set-Authorization": authorization,
                    "ig-set-ig-u-rur": "RUR,123,1:token",
                    "x-ig-set-www-claim": "hmac.claim",
                },
                "cookies": {
                    "csrftoken": "token-1",
                    "ds_user_id": "123",
                    "sessionid": "123%3Aabc",
                },
            }
        )

        self.assertTrue(result)
        self.assertEqual(client.authorization_data, authorization_data)
        self.assertEqual(client.private.cookies_dict().get("csrftoken"), "token-1")
        self.assertEqual(client.private.cookies_dict().get("ds_user_id"), "123")
        self.assertEqual(client.private.cookies_dict().get("sessionid"), "123%3Aabc")
        self.assertEqual(client.public.cookies_dict().get("sessionid"), "123%3Aabc")
        self.assertEqual(client.private.headers["Authorization"], client.authorization)
        self.assertEqual(client.ig_u_rur, "RUR,123,1:token")
        self.assertEqual(client.ig_www_claim, "hmac.claim")

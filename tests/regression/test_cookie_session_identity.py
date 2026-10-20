# protects: Cookie-only private sessions retain identity across restore and warmup failures.
# fails_when: Login ignores private ds_user_id cookies or starts fresh credentials instead of validation.
# why_new: Existing session tests supply authorization_data and miss the accepted cookie-only shape.
# seam: none; real Client, cookie jars, Bloks application, login and settings round-trips are used.
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from aiograpi import Client
from aiograpi.exceptions import ChallengeRequired, LoginRequired

COOKIES = {"sessionid": "synthetic-issued-session", "ds_user_id": "123"}


class CookieSessionIdentityTestCase(unittest.IsolatedAsyncioTestCase):
    def build_client(self, settings=None):
        client = Client(settings=settings)
        client.username = "synthetic-user"
        client.password = "synthetic-password"
        client.private_request = AsyncMock(side_effect=AssertionError("Unexpected HTTP request"))
        client.public_request = AsyncMock(side_effect=AssertionError("Unexpected public HTTP request"))
        for session in (client.private, client.public, client.graphql):
            self.addAsyncCleanup(session._close)
        return client

    async def test_cookie_only_identity_validates_existing_session_for_both_login_methods(self):
        for source in ("settings", "bloks"):
            for method in ("login", "login_legacy"):
                with self.subTest(source=source, method=method):
                    client = self.build_client({"cookies": COOKIES} if source == "settings" else None)
                    if source == "bloks":
                        self.assertTrue(client.bloks_apply_login_response({"headers": {}, "cookies": COOKIES}))
                    client.account_info = AsyncMock(return_value=object())
                    client.bloks_caa_login = AsyncMock(side_effect=AssertionError("Fresh credentials must not be sent"))
                    client.pre_login_flow = AsyncMock(side_effect=AssertionError("Pre-login must not run"))

                    self.assertEqual(client.user_id, 123)
                    self.assertIsInstance(client.user_id, int)
                    self.assertEqual(client.sessionid, COOKIES["sessionid"])
                    self.assertTrue(await getattr(client, method)())

                    client.account_info.assert_awaited_once_with()
                    client.bloks_caa_login.assert_not_awaited()
                    client.pre_login_flow.assert_not_awaited()
                    client.private_request.assert_not_awaited()
                    client.public_request.assert_not_awaited()

    async def test_cookie_fallback_preserves_existing_identity_priorities_and_reset(self):
        client = self.build_client()
        client.public.set_cookies({"ds_user_id": "999"})
        self.assertIsNone(client.user_id)
        client.private.set_cookies({"ds_user_id": "not-an-integer"})
        with self.assertRaises(ValueError):
            _ = client.user_id
        client.private.set_cookies(COOKIES)
        self.assertEqual(client.user_id, 123)
        client.authorization_data = {"sessionid": "synthetic-header-session"}
        self.assertEqual(client.user_id, 123)
        client.authorization_data = {"ds_user_id": "456"}
        self.assertEqual(client.user_id, 456)
        client._user_id = "789"
        self.assertEqual(client.user_id, 789)
        del client._user_id
        client._clear_session_state(clear_authorization_data=True, clear_private_cookies=True)
        self.assertIsNone(client.user_id)
        self.assertIsNone(client.sessionid)

    async def test_cookie_session_survives_warmup_challenge_and_settings_roundtrip(self):
        for stage in ("reels", "timeline"):
            with self.subTest(stage=stage):
                client = self.build_client()
                challenge = ChallengeRequired("Synthetic warmup challenge")

                async def issued_session(**kwargs):
                    self.assertTrue(client.bloks_apply_login_response({"headers": {}, "cookies": COOKIES}))
                    return {"logged_in": True}

                client.bloks_caa_login = AsyncMock(side_effect=issued_session)
                client.get_reels_tray_feed = AsyncMock(
                    side_effect=challenge if stage == "reels" else None, return_value={"status": "ok"}
                )
                client.get_timeline_feed = AsyncMock(
                    side_effect=challenge if stage == "timeline" else None, return_value={"status": "ok"}
                )
                with self.assertRaises(ChallengeRequired) as raised:
                    await client.login(relogin=True)
                self.assertIs(raised.exception, challenge)
                self.assertEqual(client.user_id, 123)
                self.assertEqual(client.get_settings()["cookies"], COOKIES)
                self.assertEqual(client.authorization_data, {})
                self.assertNotIn("Authorization", client.private.headers)

                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "session.json"
                    client.dump_settings(path)
                    restored = self.build_client(json.loads(path.read_text()))
                restored.account_info = AsyncMock(return_value=object())
                restored.bloks_caa_login = AsyncMock(side_effect=AssertionError("Fresh login must not run"))
                self.assertEqual(restored.user_id, 123)
                self.assertEqual(restored.sessionid, COOKIES["sessionid"])
                self.assertTrue(await restored.login())
                restored.account_info.assert_awaited_once_with()
                restored.bloks_caa_login.assert_not_awaited()

    async def test_rejected_cookie_session_is_cleared_before_a_fresh_login(self):
        client = self.build_client({"cookies": COOKIES})
        client.account_info = AsyncMock(side_effect=LoginRequired("Synthetic expired session"))

        async def issued_session(**kwargs):
            self.assertIsNone(client.user_id)
            self.assertNotIn("sessionid", client.cookie_dict)
            self.assertTrue(
                client.bloks_apply_login_response(
                    {"headers": {}, "cookies": {"sessionid": "synthetic-replacement", "ds_user_id": "456"}}
                )
            )
            return {"logged_in": True}

        client.bloks_caa_login = AsyncMock(side_effect=issued_session)
        client.login_flow = AsyncMock(return_value=True)
        self.assertTrue(await client.login())
        client.account_info.assert_awaited_once_with()
        client.bloks_caa_login.assert_awaited_once_with(verification_code="")
        self.assertEqual(client.user_id, 456)
        self.assertEqual(client.sessionid, "synthetic-replacement")

    async def test_existing_cookie_validation_challenge_is_not_masked_or_retried(self):
        client = self.build_client({"cookies": COOKIES})
        challenge = ChallengeRequired("Synthetic existing-session challenge")
        client.account_info = AsyncMock(side_effect=challenge)
        client.bloks_caa_login = AsyncMock(side_effect=AssertionError("Fresh login must not run"))
        with self.assertRaises(ChallengeRequired) as raised:
            await client.login()
        self.assertIs(raised.exception, challenge)
        self.assertEqual(client.user_id, 123)
        client.account_info.assert_awaited_once_with()
        client.bloks_caa_login.assert_not_awaited()

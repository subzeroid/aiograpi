import base64
import json
import unittest
from unittest.mock import AsyncMock, Mock, patch
from urllib.parse import parse_qsl

import httpx
from Cryptodome.PublicKey import RSA

from aiograpi import Client
from aiograpi.exceptions import ClientError, ConnectProxyError

URL = "https://i.instagram.com/api/v1/launcher/sync/"


class PasswordKeyRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        key = RSA.generate(2048).public_key().export_key()
        cls.key_headers = {
            "ig-set-password-encryption-key-id": "123",
            "ig-set-password-encryption-pub-key": base64.b64encode(key).decode(),
        }

    def client(self):
        client = Client(request_timeout=0)
        client.last_response_ts = 0
        client.small_delay = AsyncMock()
        client.public.get = AsyncMock(side_effect=AssertionError("Key retrieval must use the private launcher"))
        for session in (client.private, client.public, client.graphql):
            self.addAsyncCleanup(type(session)._close, session)
        return client

    def response(self, status=200, *, headers=True, body=b'{"status":"ok"}'):
        return httpx.Response(
            status,
            request=httpx.Request("POST", URL),
            headers=self.key_headers if headers else {},
            content=body,
        )

    async def test_launcher_payload_authorization_and_encrypted_password(self):
        client = self.client()
        client.authorization_data = {"ds_user_id": "123", "sessionid": "test-session"}
        authorization = client.authorization
        client.private.post = AsyncMock(return_value=self.response())
        encrypted = await client.password_encrypt("test")
        client.private.post.assert_awaited_once()
        args = client.private.post.call_args
        self.assertEqual(args.args[0], URL)
        self.assertEqual(args.kwargs["headers"]["Authorization"], authorization)
        signed = dict(parse_qsl(args.kwargs["data"]))["signed_body"]
        self.assertEqual(json.loads(signed.split(".", 1)[1]), {"id": client.uuid, "server_config_retrieval": "1"})
        self.assertEqual(client.private_requests_count, 1)
        parts = encrypted.split(":")
        self.assertEqual(parts[:2], ["#PWD_INSTAGRAM", "4"])
        self.assertEqual(len(parts[3]), 392)
        client.public.get.assert_not_awaited()

    async def test_error_status_headers_are_used_without_retry(self):
        for status in (400, 404, 408, 500):
            with self.subTest(status=status):
                client = self.client()
                client.private.post = AsyncMock(side_effect=[self.response(status), httpx.ConnectError("offline")])
                with patch("aiograpi.mixins.private.asyncio.sleep", new_callable=AsyncMock) as sleep:
                    result = await client.password_publickeys()
                self.assertEqual(result, (123, self.key_headers["ig-set-password-encryption-pub-key"]))
                client.private.post.assert_awaited_once()
                sleep.assert_not_awaited()

    async def test_challenge_headers_do_not_run_resolver_or_custom_handler(self):
        for custom_handler in (False, True):
            with self.subTest(custom_handler=custom_handler):
                client = self.client()
                client.challenge_resolve = AsyncMock()
                handler = AsyncMock()
                if custom_handler:
                    client.handle_exception = handler
                response = self.response(400, body=b'{"status":"fail","message":"challenge_required"}')
                client.private.post = AsyncMock(side_effect=[response, httpx.ConnectError("offline")])
                result = await client.password_publickeys()
                self.assertEqual(result, (123, self.key_headers["ig-set-password-encryption-pub-key"]))
                client.private.post.assert_awaited_once()
                client.challenge_resolve.assert_not_awaited()
                handler.assert_not_awaited()

    async def test_key_headers_do_not_require_parsing_any_response_body(self):
        for status in (200, 400):
            for body in (b"[]", b"null", b'{"message":null}', b'{"error_type":"two_factor_required"}', b"not JSON"):
                with self.subTest(status=status, body=body):
                    client = self.client()
                    response = self.response(status, body=body)
                    response.json = Mock(side_effect=AssertionError("Header-only lookup must not parse JSON"))
                    client.private.post = AsyncMock(return_value=response)
                    result = await client.password_publickeys()
                    self.assertEqual(result, (123, self.key_headers["ig-set-password-encryption-pub-key"]))
                    response.json.assert_not_called()

    async def test_missing_keys_preserve_response_status_and_original_http_error(self):
        for status in (200, 400, 408):
            for body in (b"[]", b"null", b'{"error_type":"two_factor_required"}', b"not JSON"):
                with self.subTest(status=status, body=body):
                    client = self.client()
                    response = self.response(status, headers=False, body=body)
                    client.private.post = AsyncMock(side_effect=[response, httpx.ConnectError("offline")])
                    with patch("aiograpi.mixins.private.asyncio.sleep", new_callable=AsyncMock) as sleep:
                        with self.assertRaisesRegex(ClientError, "password encryption key") as caught:
                            await client.password_publickeys()
                    self.assertIs(caught.exception.response, response)
                    self.assertEqual(caught.exception.code, status)
                    if status >= 400:
                        self.assertIsInstance(caught.exception.__cause__, httpx.HTTPStatusError)
                        self.assertIs(caught.exception.__cause__.response, response)
                    client.private.post.assert_awaited_once()
                    sleep.assert_not_awaited()

    async def test_connection_failure_cannot_reuse_a_stale_key_response(self):
        client = self.client()
        client.last_response = self.response()
        client.private.post = AsyncMock(side_effect=httpx.ConnectError("offline"))
        with self.assertRaisesRegex(ClientError, "password encryption key") as caught:
            await client.password_publickeys()
        self.assertIsNone(client.last_response)
        self.assertIsInstance(caught.exception.__cause__, ConnectProxyError)
        client.private.post.assert_awaited_once()

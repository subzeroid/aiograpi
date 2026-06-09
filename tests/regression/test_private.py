import json
import unittest
from unittest.mock import AsyncMock, Mock

from aiograpi import Client, httpx_ext
from aiograpi.exceptions import DirectMessageRequestsDisabled


class PrivateRequestRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    def _build_client(self):
        client = Client()
        client.last_response_ts = 0
        client.request_timeout = 0
        client.read_timeout = 0
        client.request_log = Mock()
        return client

    def _response(self, payload, status_code=200):
        response = Mock()
        response.status_code = status_code
        response.content = json.dumps(payload).encode()
        response.headers = {}
        response.url = "https://i.instagram.com/api/v1/direct_v2/threads/broadcast/text/"
        response.text = response.content.decode("utf-8")
        response.json.return_value = payload
        response.raise_for_status.return_value = None
        if status_code >= 400:
            response.raise_for_status.side_effect = httpx_ext.HTTPStatusError(
                f"{status_code} response",
                request=Mock(),
                response=response,
            )
        return response

    async def test_send_private_request_promotes_direct_message_requests_disabled_http_error(self):
        client = self._build_client()
        payload = {
            "message": "You can't message this account unless they follow you.",
            "status": "fail",
        }
        client.private.post = AsyncMock(return_value=self._response(payload, status_code=400))

        with self.assertRaises(DirectMessageRequestsDisabled) as cm:
            await client._send_private_request(
                "direct_v2/threads/broadcast/text/",
                data={"text": "hi"},
                with_signature=False,
            )

        self.assertEqual(cm.exception.message, payload["message"])
        self.assertEqual(cm.exception.status, "fail")

    async def test_private_request_retries_remote_protocol_error_once(self):
        client = self._build_client()
        client._user_id = "123"
        response = self._response({"status": "ok"})
        client.private.post = AsyncMock(
            side_effect=[
                httpx_ext.RemoteProtocolError(
                    "peer closed connection without sending complete message body (received 207264 bytes, expected 375848)"
                ),
                response,
            ]
        )

        with unittest.mock.patch("aiograpi.mixins.private.asyncio.sleep", new_callable=AsyncMock) as sleep:
            result = await client.private_request("test/", data={"_uuid": client.uuid}, with_signature=False)

        self.assertEqual(result, {"status": "ok"})
        self.assertEqual(client.private.post.await_count, 2)
        self.assertEqual(sleep.await_args_list.count(unittest.mock.call(2)), 1)

    async def test_send_private_request_promotes_direct_message_requests_disabled_status_fail(self):
        client = self._build_client()
        payload = {
            "message": "This account can't receive your message because they don't allow new message requests from everyone.",
            "status": "fail",
        }
        client.private.post = AsyncMock(return_value=self._response(payload))

        with self.assertRaises(DirectMessageRequestsDisabled) as cm:
            await client._send_private_request(
                "direct_v2/threads/broadcast/text/",
                data={"text": "hi"},
                with_signature=False,
            )

        self.assertEqual(cm.exception.message, payload["message"])
        self.assertEqual(cm.exception.status, "fail")

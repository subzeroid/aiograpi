import json
import unittest
from unittest.mock import AsyncMock, Mock

from aiograpi import Client, httpx_ext
from aiograpi.exceptions import (
    AccountContactPointRequired,
    AccountEditError,
    ClientNotFoundError,
    DirectMessageRequestsDisabled,
)


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

    async def test_send_private_request_promotes_account_edit_contact_point_required_http_error(self):
        client = self._build_client()
        payload = {
            "message": {"errors": ["You need an email or confirmed phone number."]},
            "status": "fail",
        }
        client.private.post = AsyncMock(return_value=self._response(payload, status_code=400))

        with self.assertRaises(AccountContactPointRequired) as cm:
            await client._send_private_request(
                "accounts/edit_profile/",
                data={"external_url": ""},
                with_signature=False,
            )

        self.assertEqual(cm.exception.message, payload["message"])
        self.assertEqual(cm.exception.status, "fail")

    async def test_send_private_request_promotes_account_edit_contact_point_required_status_fail(self):
        client = self._build_client()
        payload = {
            "message": {"errors": ["You need an email or confirmed phone number."]},
            "status": "fail",
        }
        client.private.post = AsyncMock(return_value=self._response(payload))

        with self.assertRaises(AccountContactPointRequired) as cm:
            await client._send_private_request(
                "accounts/edit_profile/",
                data={"external_url": ""},
                with_signature=False,
            )

        self.assertEqual(cm.exception.message, payload["message"])
        self.assertEqual(cm.exception.status, "fail")

    async def test_send_private_request_promotes_account_edit_unknown_server_error(self):
        client = self._build_client()
        payload = {
            "message": "Unknown Server Error.",
            "status": "fail",
        }
        client.private.post = AsyncMock(return_value=self._response(payload, status_code=400))

        with self.assertRaises(AccountEditError) as cm:
            await client._send_private_request(
                "accounts/edit_profile/",
                data={"external_url": ""},
                with_signature=False,
            )

        self.assertEqual(cm.exception.message, payload["message"])
        self.assertEqual(cm.exception.status, "fail")

    async def test_send_private_request_ignores_non_json_body_on_http_error(self):
        client = self._build_client()
        response = self._response({}, status_code=404)
        response.content = b"<html>not found</html>"
        response.text = response.content.decode("utf-8")
        response.json.side_effect = ValueError("bad json")
        client.private.get = AsyncMock(return_value=response)

        with self.assertRaises(ClientNotFoundError):
            await client._send_private_request("users/999/info/")

        self.assertEqual(client.last_json, {})

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

    async def test_send_private_request_passes_non_persistent_headers_per_request(self):
        client = self._build_client()
        response = self._response({"status": "ok"})
        client.private.post = AsyncMock(return_value=response)

        result = await client._send_private_request(
            "bloks/async_action/com.example.action/",
            data={"params": "{}"},
            with_signature=False,
            headers={"X-FB-Friendly-Name": "IgApi: bloks/async_action/com.example.action/"},
            domain="b.i.instagram.com",
        )

        self.assertEqual(result, {"status": "ok"})
        self.assertEqual(
            client.private.post.call_args.args[0],
            "https://b.i.instagram.com/api/v1/bloks/async_action/com.example.action/",
        )
        sent_headers = client.private.post.call_args.kwargs["headers"]
        self.assertEqual(sent_headers["Host"], "b.i.instagram.com")
        self.assertEqual(sent_headers["X-FB-Friendly-Name"], "IgApi: bloks/async_action/com.example.action/")
        self.assertNotIn("X-FB-Friendly-Name", client.private.headers)
        self.assertNotEqual(client.private.headers.get("Host"), "b.i.instagram.com")


class PrivateGraphQLRequestRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    def _build_client(self):
        client = Client()
        client.last_response_ts = 0
        client.request_timeout = 0
        client.read_timeout = 0
        client.request_log = Mock()
        return client

    async def test_private_graphql_www_request_posts_to_app_graphql_www_endpoint(self):
        client = self._build_client()
        variables = {"params": {"app_id": "com.example.app"}}
        response = Mock()
        response.url = "https://b.i.instagram.com/graphql_www"
        response.json.return_value = {"data": {"ok": True}}
        response.raise_for_status.return_value = None
        client.private.post = AsyncMock(return_value=response)

        result = await client.private_graphql_www_request(
            "IGBloksAppRootQuery-com.example.app",
            variables,
            client_doc_id="doc-id",
        )

        self.assertEqual(result, {"data": {"ok": True}})
        self.assertEqual(client.private.post.call_args.args, ("https://b.i.instagram.com/graphql_www",))
        data = client.private.post.call_args.kwargs["data"]
        self.assertEqual(data["purpose"], "fetch")
        self.assertEqual(data["fb_api_req_friendly_name"], "IGBloksAppRootQuery-com.example.app")
        self.assertEqual(data["client_doc_id"], "doc-id")
        self.assertEqual(json.loads(data["variables"]), variables)
        headers = client.private.post.call_args.kwargs["headers"]
        self.assertEqual(headers["X-FB-Friendly-Name"], "IGBloksAppRootQuery-com.example.app")
        self.assertEqual(headers["X-Client-Doc-Id"], "doc-id")
        self.assertEqual(headers["Host"], "b.i.instagram.com")
        client.request_log.assert_called_once_with(response)

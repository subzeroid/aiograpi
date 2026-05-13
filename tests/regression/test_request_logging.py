import unittest
from unittest.mock import AsyncMock, Mock

import orjson

from aiograpi import Client
from aiograpi.exceptions import ClientJSONDecodeError


def _json_decode_error():
    return orjson.JSONDecodeError("unexpected character", "<html>", 0)


def _html_response(body: str):
    response = Mock()
    response.status_code = 200
    response.url = "https://www.instagram.com/api/test/"
    response.text = body
    response.raise_for_status.return_value = None
    response.json.side_effect = _json_decode_error()
    return response


class RequestLoggingRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_public_json_decode_error_log_truncates_response_body(self):
        client = Client()
        client.last_response_ts = 0
        client.public_request_logger = Mock()
        long_body = "<html>" + ("A" * 5000) + "</html>"
        response = _html_response(long_body)
        client.public.get = AsyncMock(return_value=response)

        with self.assertRaises(ClientJSONDecodeError):
            await client._send_public_request("https://www.instagram.com/api/test/", return_json=True)

        logged_body = client.public_request_logger.error.call_args.args[3]
        self.assertLessEqual(len(logged_body), 600)
        self.assertTrue(logged_body.startswith("<html>"))
        self.assertIn("truncated", logged_body)
        self.assertNotEqual(logged_body, long_body)

    async def test_private_graphql_request_accepts_incremental_json_lines(self):
        client = Client()
        response = Mock()
        response.url = "https://i.instagram.com/graphql/query"
        response.text = (
            '{"data":{"timeline":{"items":[{"media":{"id":"1"}}]}},"status":"ok"}\n'
            '{"path":["timeline","items",0,"media"],"data":{"code":"abc"}}\n'
        )
        response.json.side_effect = _json_decode_error()
        response.raise_for_status.return_value = None
        client.private.post = AsyncMock(return_value=response)
        client.request_log = Mock()

        result = await client.private_graphql_request(
            {
                "fb_api_req_friendly_name": "ExampleQuery",
                "variables": "{}",
            }
        )

        self.assertEqual(result["data"]["timeline"]["items"][0]["media"]["id"], "1")
        self.assertEqual(result["data"]["timeline"]["items"][0]["media"]["code"], "abc")

    async def test_graphql_json_decode_error_log_truncates_response_body(self):
        client = Client()
        client.last_response_ts = 0
        client.request_logger = Mock()
        long_body = "<html>" + ("A" * 5000) + "</html>"
        response = _html_response(long_body)
        client.graphql.get = AsyncMock(return_value=response)

        with self.assertRaises(ClientJSONDecodeError):
            await client._send_graphql_request(return_json=True)

        logged_body = client.request_logger.error.call_args.args[3]
        self.assertLessEqual(len(logged_body), 600)
        self.assertTrue(logged_body.startswith("<html>"))
        self.assertIn("truncated", logged_body)
        self.assertNotEqual(logged_body, long_body)

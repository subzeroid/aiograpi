import sys
from importlib.metadata import requires
from unittest import IsolatedAsyncioTestCase, TestCase, mock

import orjson
import requests
from packaging.requirements import Requirement

from aiograpi import Client
from aiograpi.exceptions import ClientJSONDecodeError, ClientLoginRequired
from aiograpi.httpx_ext import CurlResponse


def curl_response(content, path="/graphql/query/"):
    response = requests.Response()
    response.status_code = 200
    response.url = f"https://www.instagram.com{path}"
    response._content = content
    return CurlResponse(response)


class CurlResponseRegressionTestCase(TestCase):
    def test_json_decodes_valid_utf8_content(self):
        response = curl_response('{"data":{"title":"café","ok":true}}'.encode())

        self.assertEqual(response.json(), {"data": {"title": "café", "ok": True}})

    def test_json_raises_the_same_decode_error_as_httpx(self):
        response = curl_response(b"<html>Unexpected response</html>")

        with self.assertRaises(orjson.JSONDecodeError):
            response.json()


class CurlResponsePublicRequestRegressionTestCase(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = Client()
        self.client.last_response_ts = 0
        for session in (self.client.public, self.client.private, self.client.graphql):
            self.addAsyncCleanup(session._client.aclose)

    async def test_invalid_json_keeps_the_response_on_typed_public_error(self):
        response = curl_response(b"<html>Unexpected response</html>")
        self.client.public.get = mock.AsyncMock(return_value=response)

        with self.assertRaises(ClientJSONDecodeError) as cm:
            await self.client.public_request(response.url, return_json=True, retries_count=1)

        self.assertIs(cm.exception.response, response)
        self.assertEqual(cm.exception.response.status_code, 200)

    async def test_login_redirect_html_raises_login_required(self):
        response = curl_response(b"<html>Login</html>", path="/accounts/login/")
        self.client.public.get = mock.AsyncMock(return_value=response)

        with self.assertRaises(ClientLoginRequired) as cm:
            await self.client.public_request(self.client.GRAPHQL_PUBLIC_API_URL, return_json=True)

        self.assertIs(cm.exception.response, response)
        self.client.public.get.assert_awaited_once()

    async def test_challenge_redirect_html_raises_login_required(self):
        response = curl_response(b"<html>Challenge</html>", path="/challenge/")
        self.client.public.get = mock.AsyncMock(return_value=response)

        with self.assertRaises(ClientLoginRequired) as cm:
            await self.client.public_request(self.client.GRAPHQL_PUBLIC_API_URL, return_json=True)

        self.assertIs(cm.exception.response, response)
        self.client.public.get.assert_awaited_once()


class PublicTransportRegressionTestCase(TestCase):
    def test_default_public_transport_does_not_require_curl_adapter(self):
        self.assertEqual(Client().public_transport, "requests")

    def test_public_user_agent_override_is_preserved(self):
        client = Client(public_user_agent="custom-public-agent")

        self.assertEqual(client.public.headers["User-Agent"], "custom-public-agent")

    def test_curl_adapter_is_optional_extra(self):
        requirements = [Requirement(value) for value in requires("aiograpi")]
        adapters = [requirement for requirement in requirements if requirement.name == "curl-adapter"]

        self.assertEqual(len(adapters), 1)
        adapter = adapters[0]
        self.assertIsNotNone(adapter.marker)
        self.assertFalse(adapter.marker.evaluate({"extra": ""}))
        self.assertTrue(adapter.marker.evaluate({"extra": "curl"}))
        self.assertNotIn("1.2.2", adapter.specifier)
        self.assertIn("1.2.3", adapter.specifier)
        self.assertIn("1.2.4", adapter.specifier)

    def test_curl_public_transport_uses_optional_adapter(self):
        adapter = mock.Mock()
        adapter_cls = mock.Mock(return_value=adapter)

        with mock.patch.dict(
            sys.modules,
            {
                "curl_adapter": mock.Mock(CurlCffiAdapter=adapter_cls),
            },
        ):
            client = Client(public_transport="curl", public_transport_impersonate="chrome136")

        self.assertEqual(client.public_transport, "curl")
        self.assertEqual(client.public_transport_impersonate, "chrome136")
        adapter_cls.assert_any_call(impersonate_browser_type="chrome136")
        self.assertIs(client.public._client.adapters["https://"], adapter)
        self.assertIs(client.public._client.adapters["http://"], adapter)

    def test_curl_public_transport_missing_extra_has_clear_error(self):
        with mock.patch.dict(sys.modules, {"curl_adapter": None}):
            with self.assertRaisesRegex(RuntimeError, r"pip install aiograpi\[curl\]"):
                Client(public_transport="curl")

    def test_public_transport_settings_roundtrip(self):
        adapter_cls = mock.Mock(return_value=mock.Mock())

        with mock.patch.dict(
            sys.modules,
            {
                "curl_adapter": mock.Mock(CurlCffiAdapter=adapter_cls),
            },
        ):
            client = Client(public_transport="curl", public_transport_impersonate="chrome136")
            settings = client.get_settings()

            self.assertEqual(settings["public_transport"], "curl")
            self.assertEqual(settings["public_transport_impersonate"], "chrome136")

            restored = Client(settings=settings)

        self.assertEqual(restored.public_transport, "curl")
        self.assertEqual(restored.public_transport_impersonate, "chrome136")

    def test_invalid_public_transport_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "public_transport must be 'requests' or 'curl'"):
            Client(public_transport="invalid")

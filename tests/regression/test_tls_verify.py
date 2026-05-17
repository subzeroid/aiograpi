import unittest
from unittest import mock
from unittest.mock import AsyncMock

import certifi

from aiograpi import Client


class _FakeResponse:
    status_code = 200
    text = ""

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def _assert_client_tls_verify(test_case, client, expected):
    test_case.assertEqual(client.tls_verify, expected)
    test_case.assertEqual(client.public.verify, expected)
    test_case.assertEqual(client.private.verify, expected)
    test_case.assertEqual(client.graphql.verify, expected)


class ClientTLSVerifyRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    def test_default_client_tls_verify_is_enabled(self):
        _assert_client_tls_verify(self, Client(), True)

    def test_client_tls_verify_can_be_disabled_for_debugging_proxy(self):
        _assert_client_tls_verify(self, Client(tls_verify=False), False)

    def test_client_tls_verify_accepts_ca_bundle_path_and_roundtrips_settings(self):
        ca_bundle = certifi.where()
        client = Client(tls_verify=ca_bundle)

        settings = client.get_settings()
        self.assertEqual(settings["tls_verify"], ca_bundle)

        restored = Client(settings=settings)
        _assert_client_tls_verify(self, restored, ca_bundle)

    def test_set_tls_verify_updates_existing_sessions(self):
        client = Client()

        self.assertTrue(client.set_tls_verify(False))
        _assert_client_tls_verify(self, client, False)

    async def test_direct_rupload_requests_use_client_tls_verify(self):
        client = Client(tls_verify=False)

        with mock.patch(
            "aiograpi.mixins.direct.httpx_ext.request",
            new_callable=AsyncMock,
        ) as request:
            request.side_effect = [_FakeResponse({"offset": 0}), _FakeResponse({"media_id": 123})]

            media_id = await client._video_rupload(b"video-bytes", "entity-name", "waterfall-id")

        self.assertEqual(media_id, 123)
        self.assertEqual(request.await_count, 2)
        for call in request.await_args_list:
            self.assertIs(call.kwargs["verify"], False)

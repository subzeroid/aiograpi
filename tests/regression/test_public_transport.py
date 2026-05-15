import sys
from pathlib import Path
from unittest import TestCase, mock

from aiograpi import Client


class PublicTransportRegressionTestCase(TestCase):
    def test_default_public_transport_does_not_require_curl_adapter(self):
        self.assertEqual(Client().public_transport, "requests")

    def test_public_user_agent_override_is_preserved(self):
        client = Client(public_user_agent="custom-public-agent")

        self.assertEqual(client.public.headers["User-Agent"], "custom-public-agent")

    def test_curl_adapter_is_optional_extra(self):
        pyproject = Path("pyproject.toml").read_text()
        required_dependencies = pyproject.split("[project.optional-dependencies]", 1)[0]
        optional_dependencies = pyproject.split("[project.optional-dependencies]", 1)[1]

        self.assertNotIn("curl-adapter", required_dependencies)
        self.assertIn("curl = [", optional_dependencies)
        self.assertIn('"curl-adapter>=1.2.1"', optional_dependencies)

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

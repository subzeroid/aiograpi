import asyncio
import gzip
import sys
from http.cookiejar import Cookie
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from aiograpi import Client


def test_explicit_requests_transport_does_not_require_curl(monkeypatch):
    monkeypatch.setitem(sys.modules, "curl_cffi", None)
    client = Client(private_transport="requests")
    assert client.private_transport == "requests"


def test_invalid_private_transport_is_rejected():
    with pytest.raises(ValueError, match="private_transport"):
        Client(private_transport="invalid")


@pytest.mark.parametrize("kwargs", [{}, {"private_transport": "curl"}])
def test_missing_private_curl_dependency_has_install_hint(monkeypatch, kwargs):
    monkeypatch.setitem(sys.modules, "curl_cffi", None)
    with pytest.raises(RuntimeError, match=r"requires curl_cffi>=0.15.0"):
        Client(**kwargs)


@pytest.mark.parametrize("version", ["libcurl/8.9.1", "unknown"])
def test_private_curl_requires_h2_only_capable_libcurl(monkeypatch, version):
    curl = pytest.importorskip("curl_cffi")
    monkeypatch.setattr(curl, "__curl_version__", version)
    with pytest.raises(RuntimeError, match="libcurl >= 8.10.0"):
        Client(private_transport="curl")


def test_private_transport_settings_restore_and_old_settings_preserve_selection():
    pytest.importorskip("curl_cffi")
    client = Client(private_transport="curl")
    assert client.get_settings()["private_transport"] == "curl"
    restored = Client(settings=client.get_settings())
    assert restored.private_transport == "curl"
    legacy = client.get_settings()
    legacy.pop("private_transport")
    assert Client(settings=legacy, private_transport="curl").private_transport == "curl"
    assert Client(settings={"private_transport": "requests"}, private_transport="curl").private_transport == "requests"


def test_switch_preserves_scoped_cookies_headers_proxy_and_device():
    pytest.importorskip("curl_cffi")
    client = Client(private_transport="requests", proxy="http://127.0.0.1:3128")
    cookie = Cookie(
        0,
        "sessionid",
        "synthetic",
        None,
        False,
        ".instagram.com",
        True,
        True,
        "/api",
        True,
        True,
        None,
        True,
        None,
        None,
        {},
    )
    client.private.cookies.set_cookie(cookie)
    client.private.headers["Authorization"] = "Bearer synthetic"
    client.private.headers["X-Custom"] = "preserve"
    uuid = client.uuid
    public, graphql = client.public, client.graphql
    client.set_retry_config(private_transport="curl")
    assert client.private_transport == "curl"
    assert client.private.headers["Authorization"] == "Bearer synthetic"
    assert client.private.headers["X-Custom"] == "preserve"
    assert client.private.proxy == "http://127.0.0.1:3128"
    assert client.private.verify is True
    assert [(c.name, c.domain, c.path, c.secure) for c in client.private.cookies] == [
        ("sessionid", ".instagram.com", "/api", True)
    ]
    assert client.uuid == uuid and client.public is public and client.graphql is graphql
    client.set_retry_config(private_transport="requests")
    assert next(iter(client.private.cookies)).value == "synthetic"


def test_saved_curl_cookies_survive_initial_tls_configuration():
    pytest.importorskip("curl_cffi")
    client = Client(settings={"private_transport": "curl", "cookies": {"sessionid": "synthetic"}})
    assert client.private.cookies_dict()["sessionid"] == "synthetic"


def test_native_async_transport_preserves_request_and_decodes_once():
    pytest.importorskip("curl_cffi")

    async def scenario():
        from curl_cffi import CurlHttpVersion
        from curl_cffi.requests.headers import Headers

        from aiograpi.transports import CurlH2Transport

        transport = CurlH2Transport(proxy="http://127.0.0.1:3128", verify=False)
        upstream = SimpleNamespace(
            status_code=200,
            content=gzip.compress(b'{"status":"ok"}'),
            headers=Headers({"content-encoding": "gzip"}),
            http_version=CurlHttpVersion.V2_0,
        )
        transport.client.request = AsyncMock(return_value=upstream)
        async with httpx.AsyncClient(transport=transport, trust_env=False) as client:
            response = await client.post(
                "https://i.instagram.com/api/v1/test/?encoded=%2F",
                content=b"exact\x00bytes",
                headers={"X-Mobile": "preserved"},
                timeout=7,
            )
            assert response.json() == {"status": "ok"}
            assert response.http_version == "HTTP/2"
            args, kwargs = transport.client.request.call_args
            assert args[:2] == ("POST", "https://i.instagram.com/api/v1/test/?encoded=%2F")
            assert kwargs["data"] == b"exact\x00bytes"
            assert kwargs["proxies"] == {"all": "http://127.0.0.1:3128"}
            assert kwargs["verify"] is False
            assert kwargs["allow_redirects"] is False
            assert kwargs["discard_cookies"] is True
            assert kwargs["default_headers"] is False
            assert kwargs["accept_encoding"] is None
            assert kwargs["quote"] is False
            assert (b"X-Mobile", b"preserved") in kwargs["headers"]
            assert transport.client.retry.count == 0

    asyncio.run(scenario())


def test_native_transport_rejects_https_http1_without_retry():
    pytest.importorskip("curl_cffi")

    async def scenario():
        from curl_cffi import CurlHttpVersion
        from curl_cffi.requests.headers import Headers

        from aiograpi.transports import CurlH2Transport

        transport = CurlH2Transport()
        transport.client.request = AsyncMock(
            return_value=SimpleNamespace(
                status_code=200, content=b"{}", headers=Headers(), http_version=CurlHttpVersion.V1_1
            )
        )
        async with httpx.AsyncClient(transport=transport, trust_env=False) as client:
            with pytest.raises(httpx.ConnectError, match="HTTP/2"):
                await client.post("https://i.instagram.com/api/v1/test/", content=b"synthetic")
            assert transport.client.request.await_count == 1

    asyncio.run(scenario())


def test_partial_transfer_does_not_trigger_private_login_retry():
    pytest.importorskip("curl_cffi")

    async def scenario():
        from curl_cffi.requests.exceptions import IncompleteRead

        from aiograpi.exceptions import ConnectProxyError

        client = Client(private_transport="curl", request_timeout=0)
        transport = client.private._client._transport
        transport.client.request = AsyncMock(side_effect=IncompleteRead("private credential must not leak"))
        try:
            with pytest.raises(ConnectProxyError) as exc:
                await client.private_request("accounts/login/", data={"synthetic": "value"}, login=True)
            assert transport.client.request.await_count == 1
            assert "private credential must not leak" not in str(exc.value)
        finally:
            await client.private._close()

    asyncio.run(scenario())


def test_switch_closes_retired_async_client_on_explicit_close():
    pytest.importorskip("curl_cffi")

    async def scenario():
        client = Client(private_transport="requests")
        old = client.private._client
        client.set_retry_config(private_transport="curl")
        await client.private._close()
        assert old.is_closed
        assert client.private._client.is_closed

    asyncio.run(scenario())


def test_failed_transport_switch_keeps_working_session(monkeypatch):
    client = Client(private_transport="requests")
    original = client.private
    original.headers["X-Custom"] = "preserved"
    monkeypatch.setitem(sys.modules, "curl_cffi", None)
    with pytest.raises(RuntimeError, match="requires curl_cffi"):
        client.set_retry_config(private_transport="curl")
    assert client.private is original
    assert client.get_settings()["private_transport"] == "requests"
    assert client.private.headers["X-Custom"] == "preserved"

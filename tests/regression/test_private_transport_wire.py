"""Native async curl transport over real loopback TLS and HTTP/2."""

import asyncio
import base64
from contextlib import asynccontextmanager

import httpx
import pytest

pytest.importorskip("curl_cffi")
pytest.importorskip("h2")
pytest.importorskip("cryptography")

from curl_cffi import CurlHttpVersion

from aiograpi import Client
from aiograpi.exceptions import ClientThrottledError
from tests.http2_server import LAB_JSON, Handler, LoopbackServer


@pytest.fixture
def lab(tmp_path, monkeypatch):
    for name in ("http_proxy", "https_proxy", "all_proxy", "no_proxy", "requests_ca_bundle", "curl_ca_bundle"):
        monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv(name.upper(), raising=False)
    server = LoopbackServer(tmp_path).start()
    try:
        yield server
    finally:
        server.close()


def url(lab, path="/lab/ok"):
    return f"https://localhost:{lab.port}{path}"


@asynccontextmanager
async def client_for(lab, **kwargs):
    client = Client(private_transport="curl", tls_verify=str(lab.ca_path), request_timeout=0, **kwargs)
    try:
        yield client
    finally:
        for session in (client.private, client.public, client.graphql):
            await session._close()


def test_actual_h2_only_clienthello_and_connection_reuse(lab):
    async def scenario():
        async with client_for(lab) as client:
            first = await client.private.get(url(lab), timeout=2)
            second = await client.private.get(url(lab), timeout=2)
            assert first.content == second.content == LAB_JSON
            assert first.http_version == second.http_version == "HTTP/2"
        assert [r["alpn_offers"] for r in lab.records] == [["h2"], ["h2"]]
        assert [r["connection_id"] for r in lab.records] == [1, 1]
        assert [r["stream_id"] for r in lab.records] == [1, 3]

    asyncio.run(scenario())


def test_mixed_alpn_control_negotiates_h2_but_offers_http1(lab):
    async def scenario():
        async with client_for(lab) as client:
            client.private._client._transport.client.http_version = CurlHttpVersion.V2_0
            response = await client.private.get(url(lab), timeout=2)
            assert response.http_version == "HTTP/2"
            assert lab.records[0]["alpn_offers"] == ["h2", "http/1.1"]

    asyncio.run(scenario())


@pytest.mark.parametrize("body", [b"signed_body=SIGNATURE.%7B%22x%22%3A1%7D", b"binary\x00body"])
def test_prepared_body_and_mobile_headers_are_preserved(lab, body):
    async def scenario():
        async with client_for(lab) as client:
            await client.private.post(
                url(lab, "/lab/form?encoded=%2F%2B"),
                content=body,
                headers={"X-IG-App-ID": "synthetic", "X-Empty": ""},
                timeout=2,
            )
            observed = lab.records[0]
            headers = dict(observed["headers"])
            assert base64.b64decode(observed["body_base64"]) == body
            assert headers[":path"] == "/lab/form?encoded=%2F%2B"
            assert headers["x-ig-app-id"] == "synthetic"
            assert headers["x-empty"] == ""
            assert headers["user-agent"] == client.user_agent

    asyncio.run(scenario())


def test_head_and_gzip_keep_connection_usable(lab):
    async def scenario():
        async with client_for(lab) as client:
            response = await client.private.request("HEAD", url(lab), timeout=2)
            assert response.content == b"" and int(response.headers["Content-Length"]) > 0
            assert (await client.private.get(url(lab), timeout=2)).content == LAB_JSON
            assert [r["connection_id"] for r in lab.records] == [1, 1]

    asyncio.run(scenario())


def test_httpx_owns_duplicate_cookies_and_cookie_clear(lab):
    async def scenario():
        async with client_for(lab) as client:
            response = await client.private.get(url(lab), timeout=2)
            assert len(response.headers.get_list("set-cookie")) == 2
            await client.private.get(url(lab), timeout=2)
            assert set(dict(lab.records[-1]["headers"])["cookie"].split("; ")) == {
                "first_cookie=one",
                "second_cookie=two",
            }
            client.private.cookies.clear()
            await client.private.get(url(lab), timeout=2)
            assert "cookie" not in dict(lab.records[-1]["headers"])

    asyncio.run(scenario())


def test_private_429_preserves_response_without_retry(lab):
    async def scenario():
        async with client_for(lab) as client:
            with pytest.raises(ClientThrottledError) as exc:
                await client.private_request(
                    "lab/rate-limit", data={"synthetic_password": "test"}, domain=f"localhost:{lab.port}", login=True
                )
            assert exc.value.response.status_code == 429
            assert exc.value.response.headers["retry-after"] == "7"
            assert len(lab.records) == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("path", ["/lab/drop", "/lab/partial"])
def test_dropped_or_partial_response_does_not_resubmit_post(lab, path):
    async def scenario():
        async with client_for(lab) as client:
            with pytest.raises(httpx.ConnectError):
                await client.private.post(url(lab, path), content=b"synthetic_password=test", timeout=2)
            assert len(lab.records) == 1

    asyncio.run(scenario())


def test_native_async_timeout_and_cancellation(lab):
    async def scenario():
        async with client_for(lab) as client:
            with pytest.raises(httpx.ConnectError):
                await client.private.get(url(lab, "/lab/slow"), timeout=0.03)
            task = asyncio.create_task(client.private.get(url(lab, "/lab/slow"), timeout=2))
            for _ in range(100):
                await asyncio.sleep(0.005)
                if len(lab.records) == 2:
                    break
            assert len(lab.records) == 2 and not task.done(), "network I/O must not block the event loop"
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert len(lab.records) == 2
            assert (await client.private.get(url(lab), timeout=2)).status_code == 200
            assert len(lab.records) == 3

    asyncio.run(scenario())


def test_unsupported_timeout_rejected_before_network_and_none_is_unlimited(lab):
    async def scenario():
        async with client_for(lab) as client:
            with pytest.raises(ValueError, match="numeric"):
                await client.private.get(url(lab), timeout=httpx.Timeout(1, connect=None))
            assert lab.records == []
            assert (await client.private.get(url(lab), timeout=None)).status_code == 200

    asyncio.run(scenario())


def test_proxy_change_honored_even_with_no_proxy_environment(lab, monkeypatch):
    async def scenario():
        async with client_for(lab) as client:
            await client.private.get(url(lab), timeout=2)
            client.set_proxy("http://127.0.0.1:1")
            monkeypatch.setenv("NO_PROXY", "*")
            with pytest.raises(httpx.ConnectError):
                await client.private.get(url(lab), timeout=0.2)
            assert len(lab.records) == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("variable", ["REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"])
def test_tls_verification_is_explicit_and_ignores_environment(lab, monkeypatch, variable):
    async def scenario():
        monkeypatch.setenv(variable, str(lab.ca_path))
        async with client_for(lab) as client:
            client.set_tls_verify(True)
            with pytest.raises(httpx.ConnectError):
                await client.private.get(url(lab), timeout=2)
            assert not lab.records
            client.set_tls_verify(False)
            assert (await client.private.get(url(lab), timeout=2)).status_code == 200
            client.set_tls_verify(True)
            with pytest.raises(httpx.ConnectError):
                await client.private.get(url(lab), timeout=2)
            assert len(lab.records) == 1

    asyncio.run(scenario())


def test_httpx_redirect_preserves_method_body_and_strips_cross_origin_auth(lab, tmp_path, monkeypatch):
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    other = LoopbackServer(other_dir).start()
    # Both servers use different CAs; this test concerns redirect semantics only.
    original = Handler.response

    def redirect(path):
        if path == "/lab/redirect":
            return 307, [("location", url(other, "/lab/final"))], b""
        return original(path)

    monkeypatch.setattr(Handler, "response", staticmethod(redirect))

    async def scenario():
        async with client_for(lab) as client:
            client.set_tls_verify(False)
            response = await client.private.post(
                url(lab, "/lab/redirect"),
                content=b"synthetic",
                headers={"Authorization": "Bearer synthetic"},
                timeout=2,
            )
            assert len(response.history) == 1 and response.status_code == 200
            assert dict(lab.records[0]["headers"])["authorization"] == "Bearer synthetic"
            headers = dict(other.records[0]["headers"])
            assert "authorization" not in headers and headers[":method"] == "POST"
            assert base64.b64decode(other.records[0]["body_base64"]) == b"synthetic"

    try:
        asyncio.run(scenario())
    finally:
        other.close()


def test_connect_proxy_reuses_tunnel_without_forwarding_proxy_auth(lab, monkeypatch):
    from tests.http2_server import LoopbackProxy

    async def scenario(proxy):
        monkeypatch.setenv("NO_PROXY", "*")
        credentials = ":".join(("synthetic", "password"))
        async with client_for(lab, proxy=f"http://{credentials}@127.0.0.1:{proxy.port}") as client:
            assert (await client.private.get(url(lab), timeout=2)).status_code == 200
            assert (await client.private.get(url(lab), timeout=2)).status_code == 200
            assert len(proxy.records) == 1
            assert proxy.records[0]["Proxy-Authorization"].startswith("Basic ")
            assert [r["connection_id"] for r in lab.records] == [1, 1]
            assert all("proxy-authorization" not in dict(r["headers"]) for r in lab.records)

    with LoopbackProxy(lab) as proxy:
        asyncio.run(scenario(proxy))


@pytest.mark.parametrize("change", ["tls", "proxy", "transport"])
def test_configuration_change_preserves_cookies_and_closes_opened_client(lab, change):
    async def scenario():
        async with client_for(lab) as client:
            await client.private.get(url(lab), timeout=2)
            old = client.private._client
            if change == "tls":
                client.set_tls_verify(str(lab.ca_path))
            elif change == "proxy":
                client.set_proxy(None)
            else:
                client.set_retry_config(private_transport="requests")
                client.set_retry_config(private_transport="curl")
            assert not old.is_closed
            await client.private.get(url(lab), timeout=2)
            assert old.is_closed
            assert set(dict(lab.records[-1]["headers"])["cookie"].split("; ")) == {
                "first_cookie=one",
                "second_cookie=two",
            }

    asyncio.run(scenario())

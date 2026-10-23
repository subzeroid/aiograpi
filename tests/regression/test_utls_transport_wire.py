# protects: Actual async native TLS/H2 settings, prepared bodies, cookies and proxy routes.
# fails_when: Protocol bytes, response decoding or native proxy policy violate the contract.
# why_new: Synthetic worker fixtures cannot establish native wire behavior.
# seam: none
"""Exercise the pinned native transport on loopback, without Instagram traffic."""

import asyncio
import base64
import os
import socket
import ssl
from contextlib import ExitStack, asynccontextmanager
from functools import wraps
from io import BytesIO

import httpx
import pytest

pytest.importorskip("h2")
pytest.importorskip("cryptography")
from h2.events import RemoteSettingsChanged, WindowUpdated

from aiograpi import Client
from aiograpi.exceptions import ClientThrottledError, ConnectProxyError
from tests import http2_server
from tests.http2_server import LAB_HOST, LAB_JSON, LoopbackProxy, LoopbackServer
from tests.socks5_proxy import LoopbackSocksProxy


@pytest.fixture
def library_path():
    path = os.environ.get("AIOGRAPI_UTLS_TEST_LIBRARY")
    if not path:
        pytest.skip("Install the native library and set AIOGRAPI_UTLS_TEST_LIBRARY to run wire tests")
    return path


@pytest.fixture
def lab(tmp_path):
    server = LoopbackServer(tmp_path).start()
    server.server.tls.minimum_version = ssl.TLSVersion.TLSv1_3
    server.server.tls.maximum_version = ssl.TLSVersion.TLSv1_3
    try:
        yield server
    finally:
        server.close()


@pytest.fixture
def client(library_path):

    @asynccontextmanager
    async def factory(**changes):
        options = dict(private_transport="utls", utls_library_path=library_path, tls_verify=False, request_timeout=0)
        # Client lifetime stays inside the same asyncio.run invocation.
        instance = Client(**(options | changes))
        try:
            yield instance
        finally:
            await close(instance)

    return factory


async def close(client):
    for session in (client.private, client.public, client.graphql):
        await session._close()


def async_test(function):
    """Run each complete client lifetime in one loop without pytest-asyncio."""

    @wraps(function)
    def run(*args, **kwargs):
        return asyncio.run(function(*args, **kwargs))

    return run


class FileBody(httpx.AsyncByteStream):
    def __init__(self, content):
        self.file = BytesIO(content)

    async def __aiter__(self):
        while chunk := self.file.read(3):
            yield chunk


def url(lab, path="/lab/ok"):
    return f"https://{LAB_HOST}:{lab.port}{path}"


@async_test
async def test_actual_clienthello_and_http2_profile(client, lab, monkeypatch):
    async with client() as client:
        hellos, settings, windows = ([], [], [])
        original_hello = http2_server.peek_client_hello
        original_receive = http2_server.H2Connection.receive_data

        def capture_hello(sock):
            header = sock.recv(5, socket.MSG_PEEK | socket.MSG_WAITALL)
            record = sock.recv(5 + int.from_bytes(header[3:5], "big"), socket.MSG_PEEK | socket.MSG_WAITALL)
            hello = record[9:]
            offset = 35 + hello[34]
            size = int.from_bytes(hello[offset : offset + 2], "big")
            ciphers = hello[offset + 2 : offset + 2 + size]
            offset += 2 + size
            offset += 1 + hello[offset]
            offset += 2
            extensions = {}
            while offset < len(hello):
                kind = int.from_bytes(hello[offset : offset + 2], "big")
                size = int.from_bytes(hello[offset + 2 : offset + 4], "big")
                extensions[kind] = hello[offset + 4 : offset + 4 + size]
                offset += 4 + size

            def pairs(value):
                return [int.from_bytes(value[i : i + 2], "big") for i in range(0, len(value), 2)]

            hellos.append((pairs(hello[:2]), pairs(ciphers), extensions))
            return original_hello(sock)

        def capture_settings(connection, data):
            events = original_receive(connection, data)
            for event in events:
                if isinstance(event, RemoteSettingsChanged):
                    settings.append([(int(key), value.new_value) for key, value in event.changed_settings.items()])
                if isinstance(event, WindowUpdated) and event.stream_id == 0:
                    windows.append(event.delta)
            return events

        monkeypatch.setattr(http2_server, "peek_client_hello", capture_hello)
        monkeypatch.setattr(http2_server.H2Connection, "receive_data", capture_settings)
        assert (await client.private.get(url(lab), timeout=2)).content == LAB_JSON
        assert (await client.private.get(url(lab), timeout=2)).content == LAB_JSON
        # Executor scheduling consumes the total budget. A changed integer
        # native timeout can legitimately rebuild a pool; validate every hello.
        assert len(lab.records) == 2
        assert len(hellos) == lab.server.connection_count
        for version, ciphers, extensions in hellos:
            assert version == [771] and ciphers == [4865]
            assert list(extensions) == [0, 43, 10, 51, 13, 16, 45]
            assert extensions[43] == b"\x02\x03\x04"
            assert extensions[10] == b"\x00\x04\x00\x1d\x00\x17"
            assert extensions[13] == b"\x00\x06\x04\x03\x05\x03\x08\x04"
            assert extensions[51][:6] == b"\x00$\x00\x1d\x00 "
        assert settings == [[(1, 65536), (2, 0), (3, 1000), (4, 6291456), (6, 262144)]] * len(hellos)
        assert windows == [15663105] * len(hellos)
        for record in lab.records:
            assert record["alpn_offers"] == ["h2"] and record["negotiated"] == "h2"
            assert record["tls_version"] == "TLSv1.3"
            assert record["supported_versions"] == [772] and record["supported_groups"] == [29, 23]
            assert [name for name, _ in record["headers"] if name.startswith(":")] == [
                ":method",
                ":authority",
                ":scheme",
                ":path",
            ]


@pytest.mark.parametrize(
    "body", ["signed_body=SIGNATURE.%7B%22x%22%3A1%7D", b"binary\x00body", FileBody(b"file\x00body")]
)
@async_test
async def test_exact_prepared_body_query_and_headers(client, lab, body):
    async with client() as client:
        expected = (
            body.file.getvalue() if isinstance(body, FileBody) else body.encode() if isinstance(body, str) else body
        )
        response = await client.private.post(
            url(lab, "/lab/form?encoded=%2F%2B"),
            content=body,
            headers={"X-IG-App-ID": "fixture", "X-Empty": ""},
            timeout=2,
        )
        assert response.content == LAB_JSON
        observed = lab.records[0]
        assert base64.b64decode(observed["body_base64"]) == expected
        headers = dict(observed["headers"])
        assert headers[":path"] == "/lab/form?encoded=%2F%2B"
        assert headers["x-ig-app-id"] == "fixture" and headers["x-empty"] == ""
        assert headers["user-agent"] == client.user_agent


@async_test
async def test_native_decodes_gzip_once_and_httpx_owns_duplicate_cookies(client, lab):
    async with client() as client:
        async with client.private._client.stream(
            "GET",
            url(lab),
            headers={key: value for key, value in client.private.headers.items() if value is not None},
            timeout=2,
        ) as response:
            assert await response.aread() == LAB_JSON
            assert response.headers.get_list("set-cookie") == [
                "first_cookie=one; Path=/; Secure",
                "second_cookie=two; Path=/; Secure",
            ]
            assert "content-encoding" not in response.headers and "content-length" not in response.headers
        response = await client.private.get(url(lab), timeout=2)
        assert b"".join([chunk async for chunk in response.aiter_bytes(3)]) == LAB_JSON
        assert set(dict(lab.records[-1]["headers"])["cookie"].split("; ")) == {"first_cookie=one", "second_cookie=two"}
        client.private.cookies.clear()
        await client.private.get(url(lab), timeout=2)
        assert "cookie" not in dict(lab.records[-1]["headers"])


@async_test
async def test_head_returns_metadata_without_reading_a_gzip_body(client, lab):
    async with client() as client:
        response = await client.private.request("HEAD", url(lab), timeout=2)
        assert response.status_code == 200 and response.content == b""
        assert int(response.headers["Content-Length"]) > 0
        assert (await client.private.get(url(lab), timeout=2)).content == LAB_JSON


@async_test
async def test_private_request_classifies_429_and_stream_failure_without_repeating_post(client, lab):
    async with client() as client:
        with pytest.raises(ClientThrottledError):
            await client.private_request(
                "lab/rate-limit", data={"synthetic_password": "test"}, login=True, domain=f"{LAB_HOST}:{lab.port}"
            )
        with pytest.raises(ConnectProxyError):
            await client.private_request(
                "lab/partial", data={"synthetic_password": "test"}, login=True, domain=f"{LAB_HOST}:{lab.port}"
            )
        assert len(lab.records) == 2


@async_test
async def test_transport_returns_429_and_does_not_repeat_dropped_post(client, lab):
    async with client() as client:
        response = await client.private.post(url(lab, "/lab/rate-limit"), content=b"synthetic-password", timeout=2)
        assert response.status_code == 429 and response.content == b"" and (response.headers["Retry-After"] == "7")
        with pytest.raises(httpx.ConnectError):
            await client.private.post(url(lab, "/lab/drop"), content=b"synthetic-password", timeout=2)
        assert len(lab.records) == 2


@async_test
async def test_per_request_deadline_and_verification_do_not_leak_through_pool(client, lab):
    async with client() as client:
        assert (await client.private.get(url(lab), timeout=2)).status_code == 200
        with pytest.raises(httpx.TimeoutException):
            await client.private.get(url(lab, "/lab/slow"), timeout=0.05)
        client.set_tls_verify(True)
        with pytest.raises(httpx.ConnectError):
            await client.private.get(url(lab), timeout=2)
        assert len(lab.records) == 2
        client.set_tls_verify(False)
        assert (await client.private.get(url(lab), timeout=2)).status_code == 200


@pytest.mark.parametrize("scheme", ["http", "socks5h"])
@async_test
async def test_proxy_routes_change_without_losing_cookies_or_resending_body(client, lab, scheme, monkeypatch):
    async with client() as client:
        monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
        monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:1")
        assert (await client.private.get(url(lab), timeout=2)).status_code == 200
        with ExitStack() as stack:
            proxy = stack.enter_context((LoopbackProxy if scheme == "http" else LoopbackSocksProxy)(lab))
            public, graphql = client.public._client, client.graphql._client
            client.private.proxy = f"{scheme}://synthetic:password@127.0.0.1:{proxy.port}"
            assert client.public._client is public and client.graphql._client is graphql
            assert (await client.private.post(url(lab), content=b"synthetic-body", timeout=2)).content == LAB_JSON
            assert (await client.private.get(url(lab), timeout=2)).content == LAB_JSON
            assert len(lab.records) == 3
            assert lab.records[0]["connection_id"] == 1
            assert all(record["connection_id"] > 1 for record in lab.records[1:])
            assert len(proxy.records) == len({record["connection_id"] for record in lab.records[1:]})
            assert base64.b64decode(lab.records[1]["body_base64"]) == b"synthetic-body"
            assert "first_cookie=one" in dict(lab.records[1]["headers"])["cookie"]
            assert "proxy-authorization" not in dict(lab.records[1]["headers"])
            if scheme == "socks5h":
                assert all(
                    record == {"hostname": "localhost", "port": lab.port, "authenticated": True}
                    for record in proxy.records
                )


# Value: protects=HTTPX redirect body/auth policy with uTLS;
# fails_when=native redirect or header mapping bypasses policy;
# why_new=existing actual redirect case selects curl; seam=none
@async_test
async def test_httpx_redirect_preserves_post_body_and_strips_cross_origin_authorization(
    client, lab, tmp_path, monkeypatch
):
    other_directory = tmp_path / "redirected-origin"
    other_directory.mkdir()
    other = LoopbackServer(other_directory).start()
    other.server.tls.minimum_version = ssl.TLSVersion.TLSv1_3
    other.server.tls.maximum_version = ssl.TLSVersion.TLSv1_3
    original = http2_server.Handler.response

    def redirect(path):
        if path == "/lab/redirect":
            return 307, [("location", url(other, "/lab/final"))], b""
        return original(path)

    monkeypatch.setattr(http2_server.Handler, "response", staticmethod(redirect))
    try:
        async with client() as instance:
            response = await instance.private.post(
                url(lab, "/lab/redirect"),
                content=b"synthetic-redirect\x00body",
                headers={"Authorization": "Bearer synthetic"},
                timeout=2,
            )
            assert response.status_code == 200 and response.content == LAB_JSON
            assert [hop.status_code for hop in response.history] == [307]
            assert len(lab.records) == len(other.records) == 1
            first_headers = dict(lab.records[0]["headers"])
            redirected_headers = dict(other.records[0]["headers"])
            assert first_headers["authorization"] == "Bearer synthetic"
            assert "authorization" not in redirected_headers
            assert first_headers[":method"] == redirected_headers[":method"] == "POST"
            assert first_headers[":path"] == "/lab/redirect" and redirected_headers[":path"] == "/lab/final"
            assert all(
                base64.b64decode(record["body_base64"]) == b"synthetic-redirect\x00body"
                for record in (lab.records[0], other.records[0])
            )
    finally:
        other.close()

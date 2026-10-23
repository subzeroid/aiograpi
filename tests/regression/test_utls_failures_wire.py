# protects: Native async faults never downgrade HTTP or replay POSTs; failed sessions are destroyed.
# fails_when: No-ALPN, refused-stream, GOAWAY or partial responses transmit again or leak a pool.
# why_new: Successful H2 requests miss protocol fault and first-failure cleanup cases.
# seam: none
"""Verify native protocol failures against local TLS peers with synthetic bodies."""

import asyncio
import ctypes
import socketserver
import threading
import time

import httpx
import pytest

pytest.importorskip("h2")
pytest.importorskip("cryptography")
from h2.config import H2Configuration
from h2.connection import H2Connection
from h2.events import DataReceived, RequestReceived, StreamEnded

from tests import http2_server
from tests.regression.test_utls_transport_wire import async_test, url
from tests.regression.test_utls_transport_wire import client as client
from tests.regression.test_utls_transport_wire import lab as lab
from tests.regression.test_utls_transport_wire import library_path as library_path


@pytest.mark.parametrize("peer_alpn", [[], ["http/1.1"]], ids=["no-alpn", "http1-only"])
@async_test
async def test_peer_without_h2_receives_no_http_headers_or_body(client, lab, monkeypatch, peer_alpn):
    async with client() as client:
        lab.server.tls.set_alpn_protocols(peer_alpn)
        finished = threading.Event()

        class NoALPNPeer(socketserver.BaseRequestHandler):
            def handle(self):
                self.request.settimeout(2)
                with self.server.tls.wrap_socket(self.request, server_side=True) as conn:
                    observed = {"alpn": conn.selected_alpn_protocol(), "tls": conn.version(), "http": b""}
                    try:
                        while chunk := conn.recv(65535):
                            observed["http"] += chunk
                            if b"synthetic-password" in observed["http"]:
                                conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")
                                break
                    finally:
                        self.server.records.append(observed)
                        finished.set()

        monkeypatch.setattr(lab.server, "RequestHandlerClass", NoALPNPeer)
        with pytest.raises(httpx.ConnectError):
            await client.private.post(url(lab), content=b"synthetic-password", timeout=2)
        assert finished.wait(1)
        assert len(lab.records) == 1
        assert lab.records[0]["tls"] == "TLSv1.3" and lab.records[0]["alpn"] is None
        assert lab.records[0]["http"] == b"", "The native client wrote HTTP before rejecting missing h2 ALPN"


@pytest.mark.parametrize("signal", ["refused_stream", "goaway"])
@async_test
async def test_native_protocol_error_does_not_replay_buffered_post(client, lab, monkeypatch, signal):
    async with client() as client:

        class RejectFirstStream(socketserver.BaseRequestHandler):
            def handle(self):
                self.request.settimeout(2)
                with self.server.tls.wrap_socket(self.request, server_side=True) as conn:
                    h2 = H2Connection(config=H2Configuration(client_side=False, header_encoding="utf-8"))
                    h2.initiate_connection()
                    conn.sendall(h2.data_to_send())
                    pending = {}
                    first = False
                    try:
                        while data := conn.recv(65535):
                            for event in h2.receive_data(data):
                                if isinstance(event, RequestReceived):
                                    pending[event.stream_id] = bytearray()
                                elif isinstance(event, DataReceived):
                                    pending[event.stream_id].extend(event.data)
                                    h2.acknowledge_received_data(event.flow_controlled_length, event.stream_id)
                                elif isinstance(event, StreamEnded):
                                    with self.server.lock:
                                        self.server.records.append(bytes(pending.pop(event.stream_id)))
                                        first = len(self.server.records) == 1
                                    if first:
                                        if signal == "goaway":
                                            h2.close_connection(error_code=0, last_stream_id=0)
                                        else:
                                            h2.reset_stream(event.stream_id, error_code=7)
                                    else:
                                        h2.send_headers(event.stream_id, [(":status", "200")], end_stream=True)
                            conn.sendall(h2.data_to_send())
                            if first and signal == "goaway":
                                return
                    except OSError:
                        return

        monkeypatch.setattr(lab.server, "RequestHandlerClass", RejectFirstStream)
        with pytest.raises(httpx.ConnectError):
            await client.private.post(url(lab), content=b"synthetic-password", timeout=2)
        assert lab.records == [b"synthetic-password"], "Native HTTP/2 replay repeated a buffered POST"


@async_test
async def test_first_native_body_read_error_is_removed_from_session_cache_on_close(client, lab):
    async with client() as client:
        adapter = client.private._client._transport
        with pytest.raises(httpx.ConnectError):
            await client.private.post(url(lab, "/lab/partial"), content=b"synthetic-password", timeout=2)
        assert len(lab.records) == 1
        await adapter.aclose()
        operation = adapter.client.library.getCookiesFromSession
        operation.argtypes = [ctypes.c_char_p]
        operation.restype = ctypes.c_void_p
        result = adapter.client._call(
            "getCookiesFromSession", {"sessionId": adapter.client.session_id, "url": url(lab)}
        )
        assert result.get("status") == 0 and "no client found" in result.get("body", "").lower()


@async_test
async def test_out_of_range_native_http_status_is_removed_from_session_cache_on_close(client, lab, monkeypatch):
    async with client() as client:
        monkeypatch.setattr(
            http2_server.Handler, "response", staticmethod(lambda path: (600, [], b"synthetic-response"))
        )
        adapter = client.private._client._transport
        with pytest.raises(httpx.ConnectError, match="invalid HTTP status"):
            await client.private.get(url(lab), timeout=2)
        assert len(lab.records) == 1
        await adapter.aclose()
        operation = adapter.client.library.getCookiesFromSession
        operation.argtypes = [ctypes.c_char_p]
        operation.restype = ctypes.c_void_p
        result = adapter.client._call(
            "getCookiesFromSession", {"sessionId": adapter.client.session_id, "url": url(lab)}
        )
        assert result.get("status") == 0 and "no client found" in result.get("body", "").lower()


@async_test
async def test_prepared_host_override_reaches_http2_authority(client, lab):
    async with client() as client:
        response = await client.private.get(url(lab), headers={"Host": "override.invalid"}, timeout=2)
        assert response.status_code == 200
        assert dict(lab.records[0]["headers"])[":authority"] == "override.invalid"


@pytest.mark.parametrize("scheme", ["socks5h", "http", "https"])
@async_test
async def test_stalled_proxy_handshake_respects_request_deadline(client, lab, scheme):
    async with client() as client:
        entered = threading.Event()
        release = threading.Event()

        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                self.request.settimeout(1)
                self.request.recv(1024)
                entered.set()
                release.wait(0.8)

        class Server(socketserver.ThreadingMixIn, socketserver.TCPServer):
            daemon_threads = True
            block_on_close = False

        proxy = Server(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=proxy.serve_forever, daemon=True)
        thread.start()
        try:
            client.private.proxy = f"{scheme}://127.0.0.1:{proxy.server_address[1]}"
            started = time.monotonic()
            with pytest.raises(httpx.TimeoutException):
                await client.private.post(url(lab), content=b"synthetic-password", timeout=0.1)
            assert entered.is_set()
            # gstack-timing-ok: a stalled loopback proxy must honor the native total deadline.
            assert time.monotonic() - started < 0.5
            assert not lab.records
        finally:
            release.set()
            proxy.shutdown()
            proxy.server_close()
            thread.join(2)


@async_test
async def test_stalled_tls_reconnect_respects_total_deadline(client, lab, monkeypatch):
    async with client() as client:
        original = http2_server.Handler
        entered = threading.Event()
        release = threading.Event()
        stall = threading.Event()
        accepted = []

        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                accepted.append(1)
                if not stall.is_set():
                    return original(self.request, self.client_address, self.server)
                self.request.settimeout(1)
                self.request.recv(65535)
                entered.set()
                release.wait(0.8)

        monkeypatch.setattr(lab.server, "RequestHandlerClass", Handler)
        assert (await client.private.get(url(lab), timeout=0.15)).status_code == 200
        with pytest.raises(httpx.ConnectError):
            await client.private.get(url(lab, "/lab/drop"), timeout=0.15)
        # Both requests above must reach HTTP even if the integer remaining
        # budget rebuilds the native pool. Stall only the next TLS connection.
        stall.set()
        accepted_before = len(accepted)
        await asyncio.sleep(0.03)
        try:
            started = time.monotonic()
            with pytest.raises(httpx.TimeoutException):
                await client.private.post(url(lab), content=b"synthetic-password", timeout=0.15)
            assert entered.is_set()
            # gstack-timing-ok: a stalled loopback TLS reconnect must consume the same deadline.
            assert time.monotonic() - started < 0.5
            assert len(lab.records) == 2
            assert len(accepted) == accepted_before + 1
        finally:
            release.set()

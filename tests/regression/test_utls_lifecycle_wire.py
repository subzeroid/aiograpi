# protects: A cancelled real native request owns its result until completion and async close drains it.
# fails_when: Cancellation releases admission early, an expired queued POST transmits, or close destroys an active pool.
# why_new: A synthetic C ABI cannot prove ownership during a delayed native TLS/H2 response.
# seam: none
"""Bound async cancellation and close with a real delayed loopback response."""

import asyncio
import base64
import ctypes
import threading
import time

import httpx
import pytest

pytest.importorskip("h2")
pytest.importorskip("cryptography")

from tests import http2_server
from tests.http2_server import LAB_JSON
from tests.regression.test_utls_transport_wire import async_test, url
from tests.regression.test_utls_transport_wire import client as client
from tests.regression.test_utls_transport_wire import lab as lab
from tests.regression.test_utls_transport_wire import library_path as library_path


async def wait_entered(event):
    deadline = time.monotonic() + 1
    while not event.is_set():
        # gstack-timing-ok: bounded polling diagnoses a peer that never receives the request.
        assert time.monotonic() < deadline, "native request never reached the delayed peer"
        await asyncio.sleep(0.005)


@pytest.mark.parametrize("cancel_close", [False, True])
@async_test
async def test_running_native_cancellation_keeps_admission_and_close_drains(client, lab, monkeypatch, cancel_close):
    entered, release = threading.Event(), threading.Event()
    original = http2_server.Handler.response

    def held_response(path):
        if path == "/lab/held":
            entered.set()
            assert release.wait(2), "test failed to release the bounded native response"
        return original(path)

    monkeypatch.setattr(http2_server.Handler, "response", staticmethod(held_response))
    async with client() as client:
        transport = client.private._client._transport
        native = transport.client
        session_id = native.session_id
        request = asyncio.create_task(
            client.private.post(url(lab, "/lab/held"), content=b"synthetic-running", timeout=2)
        )
        closing = None
        try:
            await wait_entered(entered)
            # The peer is blocked in a native request while this loop continues.
            await asyncio.sleep(0)
            assert len(lab.records) == 1
            assert base64.b64decode(lab.records[0]["body_base64"]) == b"synthetic-running"
            request.cancel()
            with pytest.raises(asyncio.CancelledError):
                await request
            assert len(transport._workers) == 1
            worker = next(iter(transport._workers))
            assert not worker.done() and not native.closed

            started = time.monotonic()
            with pytest.raises(httpx.TimeoutException):
                await client.private.post(url(lab, "/lab/queued"), content=b"synthetic-expired", timeout=0.05)
            # gstack-timing-ok: the forced deadline must expire while the first native request is held.
            assert time.monotonic() - started < 0.4
            assert len(lab.records) == 1
            assert transport._workers == {worker} and not worker.done()

            closing = asyncio.create_task(client.private._close())
            await asyncio.sleep(0.02)
            assert not closing.done() and not worker.done() and not native.closed
            assert len(lab.records) == 1
            if cancel_close:
                closing.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await closing
                # Cancelling the close waiter must leave the native drain owned.
                assert transport._closing is not None and not transport._closing.done()
                assert not worker.done() and not native.closed
                closing = asyncio.create_task(client.private._close())
                await asyncio.sleep(0)
                assert not closing.done()

            release.set()
            await asyncio.wait_for(closing, 1)
            assert worker.done() and worker.result()[0] == 200 and worker.result()[2] == LAB_JSON
            assert not transport._workers and native.closed and not native.created
            assert len(lab.records) == 1, "An expired queued POST reached the peer after admission was released"
            assert lab.server.connection_count == 1
            operation = native.library.getCookiesFromSession
            operation.argtypes = [ctypes.c_char_p]
            operation.restype = ctypes.c_void_p
            result = native._call("getCookiesFromSession", {"sessionId": session_id, "url": url(lab)})
            assert result.get("status") == 0 and "no client found" in result.get("body", "").lower()
        finally:
            release.set()
            await asyncio.gather(request, *([closing] if closing is not None else []), return_exceptions=True)

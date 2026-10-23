# protects: Async uTLS owns native results through cancellation, deadlines and close without replaying POSTs.
# fails_when: Native work blocks the event loop, queued work transmits late, or close races result release.
# why_new: Curl's native async I/O does not exercise a synchronous C ABI running in a worker.
import asyncio
import base64
import ctypes
import gc
import importlib
import importlib.util
import json
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest


def reply(status=200, body=b'{"status":"ok"}', **changes):
    return {
        "id": "fixture-result",
        "status": status,
        "usedProtocol": "HTTP/2.0",
        "headers": {"Content-Type": ["application/json"]},
        "body": "data:application/json;base64," + base64.b64encode(body).decode(),
        **changes,
    }


@pytest.fixture
def native(monkeypatch):
    assert importlib.util.find_spec("aiograpi.utls") is not None, "async uTLS transport is missing"
    module = importlib.import_module("aiograpi.utls")
    state = SimpleNamespace(replies=[], payloads=[], buffers=[], events=[], before=lambda: None)

    def output(value):
        buffer = ctypes.create_string_buffer(json.dumps(value).encode())
        state.buffers.append(buffer)
        return ctypes.addressof(buffer)

    def request(data):
        state.payloads.append(json.loads(data))
        state.events.append("request")
        state.before()
        return output(state.replies.pop(0) if state.replies else reply())

    def destroy(data):
        state.events.append("destroy")
        return output({"id": "fixture-destroy", "success": True})

    def free(identifier):
        state.events.append(identifier.decode())

    state.library = Mock(request=Mock(side_effect=request), destroySession=Mock(side_effect=destroy), freeMemory=free)
    monkeypatch.setattr(module, "load_library", lambda path: state.library)
    state.transport = lambda **kw: module.UtlsH2Transport(library_path="fixture-native", **kw)
    return state


def test_prepared_body_duplicate_cookies_and_decompressed_response(native):
    async def scenario():
        native.replies.extend(
            [
                reply(
                    headers={
                        "Content-Encoding": ["gzip"],
                        "Content-Length": ["100"],
                        "Set-Cookie": ["a=alpha; Path=/; Secure", "b=beta; Path=/; Secure"],
                    }
                ),
                reply(status=429, body=b"", headers={"Retry-After": ["7"]}),
            ]
        )
        async with httpx.AsyncClient(transport=native.transport(), trust_env=False) as client:
            first = await client.get("https://fixture.invalid/first", timeout=2)
            assert first.json() == {"status": "ok"}
            assert first.http_version == "HTTP/2"
            assert "Content-Encoding" not in first.headers and "Content-Length" not in first.headers
            assert first.headers.get_list("Set-Cookie") == ["a=alpha; Path=/; Secure", "b=beta; Path=/; Secure"]
            second = await client.post(
                "https://fixture.invalid/second?escaped=%2F", content=b"binary\x00body", timeout=2
            )
            assert second.status_code == 429 and second.content == b"" and second.headers["Retry-After"] == "7"
        assert len(native.payloads) == 2
        payload = native.payloads[1]
        assert payload["requestUrl"].endswith("?escaped=%2F")
        assert base64.b64decode(payload["requestBody"]) == b"binary\x00body"
        assert set(next(v for k, v in payload["headers"].items() if k.lower() == "cookie").split("; ")) == {
            "a=alpha",
            "b=beta",
        }
        assert payload["withoutCookieJar"] is True and payload["followRedirects"] is False
        assert native.events.count("fixture-result") == 2 and native.events[-2:] == ["destroy", "fixture-destroy"]

    asyncio.run(scenario())


@pytest.mark.parametrize("status,method", [(200, "HEAD"), (304, "GET")])
def test_representation_metadata_survives_head_and_304(native, status, method):
    async def scenario():
        native.replies.append(
            reply(status=status, body=b"", headers={"Content-Encoding": ["gzip"], "Content-Length": ["100"]})
        )
        async with httpx.AsyncClient(transport=native.transport(), trust_env=False) as client:
            response = await client.request(method, "https://fixture.invalid/", timeout=2)
            assert response.headers["content-length"] == "100" and response.headers["content-encoding"] == "gzip"

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "detail,error",
    [
        ("failed to do request: x509: certificate signed by unknown authority secret-fixture", httpx.ConnectError),
        ("failed to do request: context deadline exceeded secret-fixture", httpx.ConnectTimeout),
        ("failed to do request: unexpected EOF secret-fixture", httpx.ConnectError),
        ("unexpected EOF secret-fixture", httpx.ConnectError),
        ("gzip: invalid header secret-fixture", httpx.ConnectError),
        ("failed to build client out of request input: invalid configuration secret-fixture", httpx.ConnectError),
    ],
)
def test_native_errors_are_sanitized_and_constructed_sessions_are_destroyed(native, detail, error):
    async def scenario():
        native.replies.append({"id": "fixture-result", "status": 0, "body": detail})
        async with httpx.AsyncClient(transport=native.transport(), trust_env=False) as client:
            with pytest.raises(error) as caught:
                await client.post("https://fixture.invalid/", content=b"synthetic-password", timeout=2)
            assert "secret-fixture" not in str(caught.value)
            assert caught.value.request.method == "POST"
        assert len(native.payloads) == 1 and native.events.count("fixture-result") == 1
        assert native.library.destroySession.call_count == int(not detail.startswith("failed to build client"))

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "changes", [{"usedProtocol": "HTTP/1.1"}, {"status": 600}, {"status": None}, {"headers": []}, {"body": "malformed"}]
)
def test_malformed_native_response_releases_memory_and_destroys_session(native, changes):
    async def scenario():
        native.replies.append({**reply(), **changes})
        async with httpx.AsyncClient(transport=native.transport(), trust_env=False) as client:
            with pytest.raises(httpx.ConnectError):
                await client.post("https://fixture.invalid/", content=b"synthetic", timeout=2)
        assert len(native.payloads) == 1 and native.events.count("fixture-result") == 1
        native.library.destroySession.assert_called_once()

    asyncio.run(scenario())


async def wait_started(event):
    for _ in range(200):
        if event.is_set():
            return
        await asyncio.sleep(0.005)
    pytest.fail("native worker did not start")


def test_running_cancellation_keeps_worker_owned_until_memory_release_and_close(native):
    async def scenario():
        started, release = threading.Event(), threading.Event()

        def block():
            started.set()
            assert release.wait(2)

        native.before = block
        transport = native.transport()
        client = httpx.AsyncClient(transport=transport, trust_env=False)
        task = asyncio.create_task(client.post("https://fixture.invalid/", content=b"synthetic", timeout=1))
        try:
            await wait_started(started)
            # This awaited tick while native I/O is blocked proves loop responsiveness.
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            closing = asyncio.create_task(client.aclose())
            await asyncio.sleep(0.02)
            assert not closing.done() and "destroy" not in native.events
            closing.cancel()
            with pytest.raises(asyncio.CancelledError):
                await closing
            release.set()
            # Repeated close joins the same drain, even if HTTPX already marked itself closed.
            await transport.aclose()
            assert native.events == ["request", "fixture-result", "destroy", "fixture-destroy"]
            assert len(native.payloads) == 1
        finally:
            release.set()
            await transport.aclose()

    asyncio.run(scenario())


@pytest.mark.parametrize("cancel", [True, False])
def test_queued_cancellation_or_deadline_never_transmits(native, cancel):
    async def scenario():
        started, release = threading.Event(), threading.Event()

        def block():
            started.set()
            assert release.wait(2)

        native.before = block
        async with httpx.AsyncClient(transport=native.transport(), trust_env=False) as client:
            first = asyncio.create_task(client.post("https://fixture.invalid/first", timeout=1))
            try:
                await wait_started(started)
                second = asyncio.create_task(client.post("https://fixture.invalid/second", timeout=0.03))
                if cancel:
                    await asyncio.sleep(0.005)
                    second.cancel()
                with pytest.raises(asyncio.CancelledError if cancel else httpx.ConnectTimeout):
                    await second
                assert len(native.payloads) == 1
            finally:
                release.set()
                await first
            assert len(native.payloads) == 1

    asyncio.run(scenario())


def test_concurrent_admission_and_executor_wait_consume_same_native_budget(native):
    async def scenario():
        started, release = threading.Event(), threading.Event()

        def block():
            started.set()
            assert release.wait(2)

        native.before = block
        async with httpx.AsyncClient(transport=native.transport(), trust_env=False) as client:
            first = asyncio.create_task(client.get("https://fixture.invalid/first", timeout=1))
            await wait_started(started)
            second = asyncio.create_task(client.get("https://fixture.invalid/second", timeout=0.3))
            await asyncio.sleep(0.08)
            release.set()
            await asyncio.gather(first, second)
        assert len(native.payloads) == 2
        assert 1 <= native.payloads[1]["timeoutMilliseconds"] < 260

    asyncio.run(scenario())


@pytest.mark.parametrize("cancel", [False, True])
def test_executor_queue_timeout_or_cancellation_prevents_late_native_transmission(native, cancel):
    from concurrent.futures import ThreadPoolExecutor

    async def scenario():
        release, started = threading.Event(), threading.Event()
        loop = asyncio.get_running_loop()
        loop.set_default_executor(ThreadPoolExecutor(max_workers=1))
        transport = native.transport()

        def occupy():
            started.set()
            assert release.wait(2)

        occupied = loop.run_in_executor(getattr(transport, "_executor", None), occupy)
        await wait_started(started)
        client = httpx.AsyncClient(transport=transport, trust_env=False)
        try:
            request = asyncio.create_task(client.post("https://fixture.invalid/", timeout=1 if cancel else 0.03))
            if cancel:
                await asyncio.sleep(0.01)
                request.cancel()
            with pytest.raises(asyncio.CancelledError if cancel else httpx.ConnectTimeout):
                await request
            assert native.payloads == []
        finally:
            release.set()
            await occupied
            await client.aclose()
        assert native.payloads == [] and native.library.destroySession.call_count == 0

    asyncio.run(scenario())


def test_unrelated_default_executor_work_cannot_hold_native_request_or_close(native):
    from concurrent.futures import ThreadPoolExecutor

    async def scenario():
        release, started = threading.Event(), threading.Event()
        loop = asyncio.get_running_loop()
        loop.set_default_executor(ThreadPoolExecutor(max_workers=1))

        def occupy():
            started.set()
            assert release.wait(2)

        occupied = asyncio.create_task(asyncio.to_thread(occupy))
        await wait_started(started)
        transport = native.transport()
        client = httpx.AsyncClient(transport=transport, trust_env=False)
        try:
            response = await client.get("https://fixture.invalid/", timeout=0.1)
            assert response.status_code == 200
            await asyncio.wait_for(client.aclose(), 0.2)
            assert not release.is_set() and not occupied.done()
        finally:
            release.set()
            await occupied
            await transport.aclose()

    asyncio.run(scenario())


def test_async_body_preparation_consumes_total_deadline(native):
    class SlowBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            await asyncio.sleep(0.08)
            yield b"synthetic"

    async def scenario():
        async with httpx.AsyncClient(transport=native.transport(), trust_env=False) as client:
            with pytest.raises(httpx.ConnectTimeout):
                await client.post("https://fixture.invalid/", content=SlowBody(), timeout=0.02)
        assert native.payloads == []

    asyncio.run(scenario())


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("nan"), httpx.Timeout(1, read=2)])
def test_unsupported_deadline_rejected_before_transmission(native, timeout):
    async def scenario():
        async with httpx.AsyncClient(transport=native.transport(), trust_env=False) as client:
            with pytest.raises(ValueError, match="timeout"):
                await client.post("https://fixture.invalid/", timeout=timeout)
        assert native.payloads == []

    asyncio.run(scenario())


def test_https_and_boolean_verification_are_required(native):
    async def scenario():
        with pytest.raises(ValueError, match="CA"):
            native.transport(verify="custom.pem")
        async with httpx.AsyncClient(transport=native.transport(), trust_env=False) as client:
            with pytest.raises(ValueError, match="HTTPS"):
                await client.post("http://fixture.invalid/")
        assert native.payloads == []

    asyncio.run(scenario())


def test_cancellation_when_admission_completes_never_suppresses_cancel_on_python310(native):
    async def scenario():
        transport = native.transport()
        await transport._admission.acquire()
        request = httpx.Request("POST", "https://fixture.invalid/", content=b"synthetic")
        request.extensions["timeout"] = httpx.Timeout(1).as_dict()
        task = asyncio.create_task(transport.handle_async_request(request))
        try:
            for _ in range(200):
                if transport._admission._waiters:
                    break
                await asyncio.sleep(0)
            assert transport._admission._waiters
            transport._admission.release()
            # Wake the acquire, then cancel its parent before it resumes. This
            # reproduces wait_for's cancellation suppression on Python 3.10.
            asyncio.get_running_loop().call_soon(task.cancel)
            with pytest.raises(asyncio.CancelledError):
                await task
            assert native.payloads == [] and not transport._admission.locked()
            assert (await transport.handle_async_request(request)).status_code == 200
        finally:
            await transport.aclose()

    asyncio.run(scenario())


def test_cancellation_at_future_failure_consumes_background_exception(native):
    async def scenario():
        loop = asyncio.get_running_loop()
        errors = []
        loop.set_exception_handler(lambda loop, context: errors.append(context))
        future = loop.create_future()
        transport = native.transport()
        task = asyncio.create_task(transport._until(future, time.monotonic() + 1))
        await asyncio.sleep(0)
        future.set_exception(httpx.ConnectError("synthetic native failure"))
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        del task, future
        gc.collect()
        await asyncio.sleep(0)
        assert errors == []
        await transport.aclose()

    asyncio.run(scenario())


# Value: protects=None/default timeout is finite 30s; fails_when=fallback becomes unlimited or changes;
# why_new=existing timeout table tests rejection only; seam=none
@pytest.mark.parametrize("timeout_metadata", [None, httpx.Timeout(None).as_dict()])
def test_missing_or_none_timeout_has_a_finite_30_second_native_budget(native, timeout_metadata):
    async def scenario():
        transport = native.transport()
        request = httpx.Request("POST", "https://fixture.invalid/", content=b"synthetic")
        if timeout_metadata is not None:
            request.extensions["timeout"] = timeout_metadata
        try:
            started = time.monotonic()
            response = await transport.handle_async_request(request)
            elapsed_milliseconds = (time.monotonic() - started) * 1000
            assert response.status_code == 200 and len(native.payloads) == 1
            # gstack-timing-ok: the fallback must be finite 30s minus actual preparation time.
            assert 30_000 - elapsed_milliseconds <= native.payloads[0]["timeoutMilliseconds"] <= 30_000
        finally:
            await transport.aclose()

    asyncio.run(scenario())


# Value: protects=session-lock wait consumes deadline and cancellation;
# fails_when=lock winner transmits expired/cancelled work;
# why_new=admission avoids lock contention in existing cases; seam=none
@pytest.mark.parametrize("outcome", ["deadline", "cancelled", "remaining_budget"])
def test_native_session_lock_wait_never_restarts_budget_or_ignores_cancellation(native, outcome):
    async def scenario():
        transport = native.transport()
        entered, cancelled = threading.Event(), threading.Event()
        value = {"timeoutMilliseconds": 1000, "proxyUrl": "", "insecureSkipVerify": False}
        deadline = time.monotonic() + (0.03 if outcome == "deadline" else 0.3)
        transport.client.lock.acquire()

        def request():
            entered.set()
            return transport.client.request(value, deadline=deadline, cancelled=cancelled)

        worker = asyncio.create_task(asyncio.to_thread(request))
        try:
            await wait_started(entered)
            assert native.payloads == []
            if outcome == "deadline":
                with pytest.raises(httpx.ConnectTimeout, match="waiting for the session"):
                    await worker
            else:
                if outcome == "cancelled":
                    cancelled.set()
                else:
                    # gstack-timing-ok: hold the real session lock to consume its original total budget.
                    await asyncio.sleep(0.08)
                transport.client.lock.release()
                if outcome == "cancelled":
                    with pytest.raises(httpx.ConnectError, match="cancelled before transmission"):
                        await worker
                else:
                    assert (await worker)[0] == 200
                    assert len(native.payloads) == 1
                    assert 1 <= native.payloads[0]["timeoutMilliseconds"] < 260
            if outcome != "remaining_budget":
                assert native.payloads == []
        finally:
            if transport.client.lock.locked():
                transport.client.lock.release()
            await asyncio.gather(worker, return_exceptions=True)
            await transport.aclose()

    asyncio.run(scenario())


# Value: protects=closed transport never admits another request;
# fails_when=queued/new caller transmits after close begins;
# why_new=existing close cases have no surviving queued caller; seam=none
def test_close_rejects_new_and_already_waiting_requests_without_transmission(native):
    async def scenario():
        started, release = threading.Event(), threading.Event()

        def block():
            started.set()
            assert release.wait(2)

        native.before = block
        transport = native.transport()

        def request(path):
            prepared = httpx.Request("POST", f"https://fixture.invalid/{path}", content=b"synthetic")
            prepared.extensions["timeout"] = httpx.Timeout(1).as_dict()
            return transport.handle_async_request(prepared)

        first = asyncio.create_task(request("running"))
        queued = closing = None
        try:
            await wait_started(started)
            queued = asyncio.create_task(request("queued"))
            for _ in range(200):
                if transport._admission._waiters:
                    break
                await asyncio.sleep(0)
            assert transport._admission._waiters
            closing = asyncio.create_task(transport.aclose())
            for _ in range(200):
                if transport._closed:
                    break
                await asyncio.sleep(0)
            assert transport._closed and not closing.done()
            with pytest.raises(httpx.ConnectError, match="transport is closed"):
                await request("after-close")
            assert len(native.payloads) == 1
            release.set()
            assert (await first).status_code == 200
            with pytest.raises(httpx.ConnectError, match="transport is closed"):
                await queued
            await closing
            assert len(native.payloads) == 1
            assert native.events == ["request", "fixture-result", "destroy", "fixture-destroy"]
            assert not transport._admission.locked()
        finally:
            release.set()
            await asyncio.gather(
                first, *[task for task in (queued, closing) if task is not None], return_exceptions=True
            )
            await transport.aclose()

    asyncio.run(scenario())


@pytest.mark.parametrize("failure", ["allocation", "task_creation"])
def test_predispatch_failure_preserves_the_next_request_and_closes_rejected_coroutines(native, monkeypatch, failure):
    async def scenario():
        transport = native.transport()
        rejected = []
        create_task = asyncio.create_task

        def reject_worker(coroutine, *args, **kwargs):
            if coroutine.cr_code.co_name == "_request":
                rejected.append(coroutine)
                raise RuntimeError("synthetic task creation failure")
            return create_task(coroutine, *args, **kwargs)

        try:
            async with httpx.AsyncClient(transport=transport, trust_env=False) as client:
                with monkeypatch.context() as failing:
                    if failure == "allocation":
                        failing.setattr(
                            base64, "b64encode", Mock(side_effect=MemoryError("synthetic allocation failure"))
                        )
                    else:
                        failing.setattr(asyncio, "create_task", reject_worker)
                    with pytest.raises(httpx.ConnectError, match="uTLS private transport failed"):
                        await client.post("https://fixture.invalid/failed", content=b"body", timeout=1)
                assert native.payloads == []
                response = await client.post("https://fixture.invalid/recovered", content=b"body", timeout=0.1)
                assert response.status_code == 200
                assert len(native.payloads) == 1
                assert native.payloads[0]["requestUrl"].endswith("/recovered")
                assert not transport._admission.locked() and not transport._workers
                if failure == "task_creation":
                    assert len(rejected) == 1 and rejected[0].cr_frame is None
            assert native.events == ["request", "fixture-result", "destroy", "fixture-destroy"]
        finally:
            for coroutine in rejected:
                coroutine.close()
            await transport.aclose()

    asyncio.run(scenario())

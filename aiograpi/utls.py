"""Optional strict uTLS with a buffered HTTPX async boundary and no replay.

The pinned native C API is synchronous. One worker per transport owns native
results through cancellation; close drains workers before destroying the pool.
"""

import asyncio
import base64
import ctypes
import json
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from uuid import uuid4

import httpx

from aiograpi.utls_native import load_library

# Accepted in CAA experiments with Android app profile 449.0.0.52.84. This is
# not claimed to be a capture of the official Android client's fingerprint:
# https://github.com/subzeroid/instagrapi/issues/2852#issuecomment-6071774879
_PROFILE = {
    "ja3String": "771,4865,0-43-10-51-13-16-45,29-23,",
    "supportedVersions": ["1.3"],
    "supportedSignatureAlgorithms": ["ECDSAWithP256AndSHA256", "ECDSAWithP384AndSHA384", "PSSWithSHA256"],
    "keyShareCurves": ["X25519"],
    "alpnProtocols": ["h2"],
    "certCompressionAlgos": [],
    "h2Settings": {
        "HEADER_TABLE_SIZE": 65536,
        "ENABLE_PUSH": 0,
        "MAX_CONCURRENT_STREAMS": 1000,
        "INITIAL_WINDOW_SIZE": 6291456,
        "MAX_HEADER_LIST_SIZE": 262144,
    },
    "h2SettingsOrder": [
        "HEADER_TABLE_SIZE",
        "ENABLE_PUSH",
        "MAX_CONCURRENT_STREAMS",
        "INITIAL_WINDOW_SIZE",
        "MAX_HEADER_LIST_SIZE",
    ],
    "pseudoHeaderOrder": [":method", ":authority", ":scheme", ":path"],
    "connectionFlow": 15663105,
}


class _NativeClient:
    def __init__(self, library_path):
        self.library = load_library(library_path)
        self.session_id = str(uuid4())
        self.created = False
        self.closed = False
        self.policy = None
        self.lock = threading.Lock()

    def _call(self, operation, value):
        data = value if isinstance(value, bytes) else json.dumps(value).encode()
        pointer = getattr(self.library, operation)(data)
        if not pointer:
            raise httpx.ConnectError("uTLS native transport returned no response")
        result = None
        try:
            result = json.loads(ctypes.string_at(pointer))
            if not isinstance(result, dict) or not isinstance(result.get("id"), str):
                raise ValueError("invalid response")
            return result
        except (UnicodeDecodeError, ValueError):
            raise httpx.ConnectError("uTLS native transport returned malformed JSON") from None
        finally:
            if isinstance(result, dict) and isinstance(result.get("id"), str):
                self.library.freeMemory(result["id"].encode())

    def request(self, value, *, deadline=None, cancelled=None):
        if deadline is None:
            deadline = time.monotonic() + value["timeoutMilliseconds"] / 1000
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not self.lock.acquire(timeout=remaining):
            raise httpx.ConnectTimeout("uTLS private transport deadline expired while waiting for the session")
        try:
            if self.closed:
                raise httpx.ConnectError("uTLS native session is closed")

            def budget():
                if cancelled is not None and cancelled.is_set():
                    raise httpx.ConnectError("uTLS private request cancelled before transmission")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise httpx.ConnectTimeout("uTLS private transport deadline expired before transmission")
                return max(1, math.ceil(remaining * 1000))

            budget()
            # Encode the potentially large body/profile before fixing the
            # native timeout. Cancellation during encoding must not send later.
            payload = {**value, "customTlsClient": _PROFILE}
            payload.pop("timeoutMilliseconds", None)
            payload.pop("sessionId", None)
            encoded = json.dumps(payload).encode()
            milliseconds = budget()
            policy = (value["proxyUrl"], milliseconds, value["insecureSkipVerify"])
            # The native C API caches client configuration by sessionId. Rebuild
            # before changing TLS, deadline or route; cookies stay in HTTPX.
            if self.policy is not None and self.policy != policy:
                self._close_session()
                self.session_id = str(uuid4())
                milliseconds = budget()
                policy = (value["proxyUrl"], milliseconds, value["insecureSkipVerify"])
            self.policy = policy
            tail = json.dumps({"sessionId": self.session_id, "timeoutMilliseconds": milliseconds}).encode()
            data = encoded[:-1] + b", " + tail[1:]
            budget()  # Recheck after the final buffer copy, immediately before C.
            result = self._call("request", data)
            status = result.get("status")
            if status == 0:
                detail = str(result.get("body", "")).lower()
                # CreateClient errors can leave a nil cache entry in v1.16.0;
                # destroying it panics. All other error results follow successful
                # construction, including unprefixed BuildResponse/body errors.
                construction_errors = (
                    "failed to build client out of request input:",
                    "cannot build client out of client identifier and custom tls client information.",
                    "cannot build client with both defined timeout in seconds and timeout in milliseconds.",
                )
                if not detail.startswith(construction_errors):
                    self.created = True
                error = httpx.ConnectError
                if "certificate" in detail or "x509:" in detail or "tls:" in detail:
                    error = httpx.ConnectError
                elif "timeout" in detail or "deadline exceeded" in detail:
                    error = httpx.ConnectTimeout
                raise error("uTLS private transport failed")
            self.created = True
            if not isinstance(status, int) or not 100 <= status <= 599:
                raise httpx.ConnectError("uTLS native transport returned an invalid HTTP status")
            if result.get("usedProtocol") != "HTTP/2.0":
                raise httpx.ConnectError("uTLS private transport did not negotiate HTTP/2")
            headers, encoded = result.get("headers"), result.get("body")
            if (
                not isinstance(headers, dict)
                or not all(
                    isinstance(name, str) and isinstance(values, list) and all(isinstance(item, str) for item in values)
                    for name, values in headers.items()
                )
                or not isinstance(encoded, str)
                or ";base64," not in encoded
            ):
                raise httpx.ConnectError("uTLS native transport returned an invalid HTTP response")
            try:
                body = base64.b64decode(encoded.split(";base64,", 1)[1], validate=True)
            except ValueError:
                raise httpx.ConnectError("uTLS native transport returned an invalid response body") from None
            return status, headers, body
        finally:
            self.lock.release()

    def close(self):
        with self.lock:
            if not self.closed:
                self.closed = True
                self._close_session()

    def _close_session(self):
        if self.created:
            self._call("destroySession", {"sessionId": self.session_id})
            self.created = False


class UtlsH2Transport(httpx.AsyncBaseTransport):
    """HTTPX owns cookies/redirects; native workers own buffered I/O and results.

    Cancellation stops awaiting a running C call, not the call itself. The
    request's total deadline bounds native work; aclose drains it. Waiting for
    admission, the executor and request-body buffering consume that same budget.
    """

    def __init__(self, proxy=None, verify=True, library_path=None):
        if verify is not True and verify is not False:
            raise ValueError("utls supports system CA validation; custom CA files and directories are not supported")
        self.client = _NativeClient(library_path)
        # A lazy single-worker pool prevents unrelated default-executor work
        # from holding this transport's native request and shutdown indefinitely.
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="aiograpi-utls")
        self._proxy = proxy or ""
        self._verify = verify
        self._admission = asyncio.Lock()
        self._workers = set()
        self._closed = False
        self._closing = None

    @staticmethod
    def _seconds(request):
        values = list(request.extensions.get("timeout", {}).values())
        if not values or all(value is None for value in values):
            return 30
        if (
            any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in values)
            or any(not math.isfinite(value) or value <= 0 for value in values)
            or len(set(values)) != 1
        ):
            raise ValueError("utls timeout must be a positive finite uniform total deadline")
        return values[0]

    @staticmethod
    async def _until(awaitable, deadline):
        # asyncio.wait_for can suppress cancellation when its inner future just
        # completed on Python 3.10. wait keeps cancellation authoritative even
        # at that boundary. Shielded native tasks remain owned by the transport.
        task = asyncio.ensure_future(awaitable)
        try:
            done, _ = await asyncio.wait({task}, timeout=max(0, deadline - time.monotonic()))
            if not done:
                raise asyncio.TimeoutError
            return task.result()
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            elif not task.cancelled():
                task.exception()

    async def _acquire(self, deadline):
        task = asyncio.create_task(self._admission.acquire())
        try:
            await self._until(task, deadline)
        except BaseException:
            # If cancellation and acquisition complete together, this caller
            # owns the lock even though it never reached the native worker.
            if task.done() and not task.cancelled() and task.exception() is None and task.result():
                self._admission.release()
            raise

    def _completed(self, task):
        self._workers.discard(task)
        if not task.cancelled():
            task.exception()  # Retrieve failures even after the caller cancelled.

    async def _request(self, value, deadline, cancelled):
        try:
            call = partial(self.client.request, value, deadline=deadline, cancelled=cancelled)
            return await asyncio.get_running_loop().run_in_executor(self._executor, call)
        finally:
            self._admission.release()

    async def handle_async_request(self, request):
        if request.url.scheme != "https":
            raise ValueError("utls private transport supports HTTPS only")
        seconds = self._seconds(request)
        deadline = time.monotonic() + seconds
        if self._closed:
            raise httpx.ConnectError("uTLS private transport is closed", request=request)
        cancelled = threading.Event()
        owns_admission = False
        try:
            body = await self._until(request.aread(), deadline)
            await self._acquire(deadline)
            owns_admission = True
            if self._closed:
                raise httpx.ConnectError("uTLS private transport is closed", request=request)
            value = {
                "requestMethod": request.method,
                "requestUrl": str(request.url),
                "requestHostOverride": request.headers.get("Host"),
                "headers": dict(request.headers),
                "headerOrder": list(request.headers),
                "requestBody": base64.b64encode(body).decode(),
                "isByteRequest": True,
                "isByteResponse": True,
                "withoutCookieJar": True,
                "requestCookies": [],
                "followRedirects": False,
                "forceHttp1": False,
                "disableHttp3": True,
                "withProtocolRacing": False,
                "withRandomTLSExtensionOrder": False,
                "insecureSkipVerify": not self._verify,
                "timeoutMilliseconds": max(1, math.ceil(seconds * 1000)),
                "proxyUrl": self._proxy,
                "withDebug": False,
                "catchPanics": True,
                "transportOptions": {"disableCompression": True},
            }
            worker = self._request(value, deadline, cancelled)
            try:
                task = asyncio.create_task(worker)
            except BaseException:
                worker.close()
                raise
            owns_admission = False  # The worker now releases admission in its finally block.
            self._workers.add(task)
            task.add_done_callback(self._completed)
            status, headers, content = await self._until(asyncio.shield(task), deadline)
        except asyncio.TimeoutError:
            cancelled.set()
            raise httpx.ConnectTimeout("uTLS private transport total deadline expired", request=request) from None
        except asyncio.CancelledError:
            cancelled.set()
            raise
        except httpx.TransportError as exc:
            exc.request = request
            raise
        except Exception:
            # Never expose provider/native detail or map partial reads into the
            # legacy RemoteProtocolError -> incomplete-read retry path.
            raise httpx.ConnectError("uTLS private transport failed", request=request) from None
        finally:
            if owns_admission:
                self._admission.release()
        excluded = set() if request.method == "HEAD" or status == 304 else {"content-encoding", "content-length"}
        pairs = [(name, value) for name, values in headers.items() for value in values if name.lower() not in excluded]
        return httpx.Response(
            status,
            headers=pairs,
            stream=httpx.ByteStream(content),
            extensions={"http_version": b"HTTP/2"},
        )

    async def _drain(self):
        async def finish(future):
            while True:
                try:
                    return await asyncio.shield(future)
                except asyncio.CancelledError:
                    # Shutdown may cancel the retained task itself, not just
                    # its waiter. Native cleanup still owns the finite work.
                    if future.cancelled():
                        raise

        try:
            if self._workers:
                await finish(asyncio.gather(*self._workers, return_exceptions=True))
            await finish(asyncio.get_running_loop().run_in_executor(self._executor, self.client.close))
        finally:
            self._executor.shutdown(wait=False)

    async def aclose(self):
        self._closed = True
        if self._closing is None or self._closing.cancelled():
            self._closing = asyncio.create_task(self._drain())
            self._closing.add_done_callback(lambda task: task.exception() if not task.cancelled() else None)
        await asyncio.shield(self._closing)

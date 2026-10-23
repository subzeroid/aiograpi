# Optional uTLS private transport

Select `private_transport="utls"` to use the pinned TLS 1.3 and HTTP/2 profile introduced in instagrapi 3.1.0. The default remains `curl`; public web and GraphQL transports keep their independent configuration. Importing aiograpi or using either existing private transport does not download, compile or load uTLS.

## Explicit installation

Install Go 1.27.2 or newer and a C compiler, then run this command in the same Python installation and user account that will run aiograpi:

```bash
python -m aiograpi.utls_native ./native
```

The command downloads fixed-size, checksum-pinned tls-client and fhttp source archives, verifies and applies the bundled patches, runs native construction and HTTP/2 peer checks, and builds a shared library. It prints the path of the digest-named deployment file. Compilation is explicit; `Client` never runs the installer.

Build inputs and licenses are included in wheels and source distributions. The loader supports macOS, Linux and Windows on its supported architectures; Android/Termux is rejected. Native loopback CI runs on Linux, with additional local macOS verification. Other platform builds are not established by those checks.

The installer records the build in a private source-fingerprinted cache under `$XDG_CACHE_HOME/aiograpi/utls-native` or `~/.cache/aiograpi/utls-native`. On Unix, cache directories and files must be owned by the current user with modes 0700 and 0600, respectively. Newly created cache ancestors are private even with a group-writable umask; existing unsafe ancestors are rejected before compilation. The deployment file must match that registered build; adjacent manifests do not authorize a binary. The loader checks the checksum and ABI and loads the protected cache copy. Keep the cache available to the running user. Rebuild after changing Python/native build inputs; moving the deployment file alone to another user or machine does not register it there.

Use `--rebuild` to compile again with the current Go/C toolchain. A failed rebuild retains the previous registered build and deployment path.

## Selecting the transport

```python
from aiograpi import Client

cl = Client(
    private_transport="utls",
    utls_library_path="/path/printed/by/the/installer",
)
cl.load_settings("session.json")
cl.set_retry_config(private_transport="utls")
try:
    await cl.login(USERNAME, PASSWORD)
    cl.dump_settings("session.json")
finally:
    await cl.private._close()
    await cl.public._close()
    await cl.graphql._close()
```

The explicit saved `private_transport` overrides the constructor, so the example selects uTLS again after loading older settings. The library path is deployment configuration and is never included in account settings; supply it again when restoring a saved uTLS session. Changing transport, proxy or TLS configuration retains scoped cookies, headers and the device identity. Change configuration between requests; construction and configuration verify local library files synchronously. Replaced clients are drained on the next awaited request or session close. A terminal retired-client close error is reported to that caller and removed from the pending list; a cancelled close remains joinable.

## Async deadlines and cancellation

HTTPX prepares headers, bodies, cookies and redirects. Each uTLS transport owns one lazily started worker for the synchronous native boundary and its cleanup, so unrelated work in asyncio's default executor cannot block its shutdown. One native request is admitted per transport; other requests wait asynchronously. Response bodies are buffered and decompressed by the native library; HTTPX receives duplicate response headers and does not decompress the body again. HEAD and 304 representation metadata is retained.

A numeric request timeout is one positive, finite total deadline for each transport invocation. Reading the prepared body, admission, executor waiting, native session-lock waiting, proxy setup, TLS and response reading all consume it. HTTPX preparation before transport entry and draining a replaced client happen outside that deadline; each HTTPX redirect receives its own transport budget. Configure routes between completed requests and close sessions explicitly to avoid pending native cleanup delaying a subsequent request. HTTPX connect/read/write/pool values must be equal; mixed values are rejected before transmission. `timeout=None` selects a 30-second total deadline for uTLS rather than unlimited work. Direct private session requests default to 45 seconds; high-level private API calls use the client's `read_timeout`, which defaults to 25 seconds.

Cancelling a queued request prevents its later transmission, including cancellation during Python request serialization before the C call. Cancelling a request whose native call has already started stops awaiting it; the native call continues with a finite native timeout computed from the remaining request budget. The await deadline does not forcibly interrupt C preparation, I/O or cleanup. The transport retains ownership of the worker and releases its native result memory when it completes. Await session close during application shutdown: close drains outstanding workers before destroying their native sessions, and a cancelled close can be awaited again.

The native client caches its timeout as session configuration. A change in the remaining millisecond budget, proxy or verification policy rebuilds that native session, so consecutive requests are not guaranteed to reuse the same TLS connection.

## Protocol and error behavior

uTLS supports HTTPS with system CA verification (`tls_verify=True`) or explicit verification disabling (`False`). Custom CA paths and client certificates are unsupported. It uses the explicitly configured proxy and ignores environment proxy overrides for requests. Ordinary HTTP CONNECT, HTTPS CONNECT and SOCKS5 proxies retain the native engine's routing behavior. SOCKS4 dialers lack context cancellation and are rejected by the strict native patch.

The profile offers TLS 1.3 with `h2` only. The native patches reject missing HTTP/2 ALPN before writing HTTP, validate peer SETTINGS and disabled server push, and disable native replay after errors including refused streams and GOAWAY. There is no HTTP/1 fallback, alternate transport attempt or protocol racing. Native connection, timeout and partial-response failures map to HTTPX connection errors and the existing `ConnectProxyError` at the private API layer, avoiding the legacy incomplete-read retry path. HTTP status handling stays separate, including `ClientThrottledError` for HTTP 429.

A connection error does not establish whether the server received or committed a request. The transport and default private error handling do not automatically repeat these failed POSTs. An application retry or a configured `handle_exception` callback that returns normally can still cause resubmission through the existing private request logic; that behavior is outside the transport's no-replay guarantee.

The fixed profile is a tested transport candidate, not a claim to reproduce every official Android fingerprint. Local TLS/HTTP2 tests establish protocol, cancellation and cleanup behavior; they do not establish fresh Instagram login success, resolve `not_eligible_for_chaining`, or guarantee recovery from rate limits or account verification.

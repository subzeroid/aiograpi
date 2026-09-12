"""Optional asynchronous transports for private mobile API requests."""

import os
import re

import httpx


class CurlH2Transport(httpx.AsyncBaseTransport):
    """Buffered native-async curl transport with h2-only HTTPS ALPN.

    HTTPX owns request preparation, redirects, cookies and decompression.
    Curl owns the persistent connections and does not retry requests.
    """

    def __init__(self, proxy=None, verify=True):
        try:
            import curl_cffi
            from curl_cffi import CurlHttpVersion, CurlOpt, ffi
            from curl_cffi import requests as curl_requests
        except ImportError as exc:
            raise RuntimeError(
                "curl private transport requires curl_cffi>=0.15.0; reinstall aiograpi with its dependencies"
            ) from exc

        version = re.search(r"libcurl/(\d+)\.(\d+)\.(\d+)", curl_cffi.__curl_version__)
        if not version or tuple(map(int, version.groups())) < (8, 10, 0):
            raise RuntimeError("curl private transport requires libcurl >= 8.10.0 for h2-only ALPN")
        self._curl_requests = curl_requests
        self._http_version = CurlHttpVersion.V2_PRIOR_KNOWLEDGE
        self._http2 = CurlHttpVersion.V2_0
        self._proxy = proxy
        self._verify = verify
        self._client = None
        self._closed = False
        self._curl_options = {
            CurlOpt.HTTP_CONTENT_DECODING: 0,
            CurlOpt.NOPROXY: "",
            # Some proxy paths reject the default classical-only ClientHello.
            # Keep classical groups available for peers without hybrid support.
            CurlOpt.SSL_EC_CURVES: "X25519MLKEM768:X25519:P-256:P-384",
        }
        if isinstance(verify, str) and os.path.isdir(verify):
            self._curl_options.update({CurlOpt.CAPATH: verify, CurlOpt.CAINFO: ffi.NULL})
            self._verify = True

    @property
    def client(self):
        if self._closed:
            raise RuntimeError("curl private transport is closed")
        if self._client is None:
            self._client = self._curl_requests.AsyncSession(
                trust_env=False,
                default_headers=False,
                discard_cookies=True,
                http_version=self._http_version,
                curl_options=self._curl_options,
            )
            # curl_cffi reads CA environment variables even with trust_env=False.
            self._client.verify = True
        return self._client

    @staticmethod
    def _timeout(request):
        budgets = request.extensions.get("timeout", {})
        connect, read = budgets.get("connect"), budgets.get("read")
        if connect is None and read is None:
            return None
        if not all(isinstance(value, (int, float)) for value in (connect, read)):
            raise ValueError("curl connect/read timeouts must both be numeric or both None")
        return connect, read

    async def handle_async_request(self, request):
        timeout = self._timeout(request)
        body = await request.aread()
        try:
            upstream = await self.client.request(
                request.method,
                str(request.url),
                data=body,
                headers=list(request.headers.raw),
                proxies={"all": self._proxy or ""},
                timeout=timeout,
                verify=self._verify,
                allow_redirects=False,
                default_headers=False,
                accept_encoding=None,
                discard_cookies=True,
                quote=False,
            )
        except self._curl_requests.exceptions.RequestException as exc:
            # In particular, partial transfers must not reach the legacy
            # incomplete-read retry and resubmit a credential-bearing POST.
            raise httpx.ConnectError(f"curl private transport failed ({type(exc).__name__})", request=request) from exc

        if request.url.scheme == "https" and upstream.http_version != self._http2:
            raise httpx.ConnectError("curl private transport did not negotiate HTTP/2", request=request)
        return httpx.Response(
            upstream.status_code,
            headers=upstream.headers.multi_items(),
            stream=httpx.ByteStream(upstream.content),
            extensions={"http_version": b"HTTP/2" if upstream.http_version == self._http2 else b"HTTP/1.1"},
        )

    async def aclose(self):
        if not self._closed:
            self._closed = True
            if self._client is not None:
                await self._client.close()

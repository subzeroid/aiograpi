import httpx
import orjson
import zstandard as zstd
from httpx import (
    CloseError,
    ConnectError,
    ConnectTimeout,
    CookieConflict,
    DecodingError,
    HTTPError,
    HTTPStatusError,
    InvalidURL,
    LocalProtocolError,
    NetworkError,
    PoolTimeout,
    ProtocolError,
    ProxyError,
    ReadError,
    ReadTimeout,
    RemoteProtocolError,
    RequestError,
    TimeoutException,
    TooManyRedirects,
    TransportError,
    UnsupportedProtocol,
    WriteError,
    WriteTimeout,
)
from httpx._client import ClientState
from httpx._decoders import SUPPORTED_DECODERS, ContentDecoder

httpx.Response.json = lambda self: orjson.loads(self.content)


class ZstdDecoder(ContentDecoder):
    def __init__(self) -> None:
        self.decompressor = zstd.ZstdDecompressor().decompressobj()

    def decode(self, data: bytes) -> bytes:
        # TODO: optimization
        if not data:
            return b""
        data_parts = [self.decompressor.decompress(data)]
        while self.decompressor.eof and self.decompressor.unused_data:
            unused_data = self.decompressor.unused_data
            self.decompressor = zstd.ZstdDecompressor().decompressobj()
            data_parts.append(self.decompressor.decompress(unused_data))
        return b"".join(data_parts)

    def flush(self) -> bytes:
        ret = self.decompressor.flush()
        if not self.decompressor.eof:
            raise DecodingError("Zstandard data is incomplete")
        return ret


SUPPORTED_DECODERS["zstd"] = ZstdDecoder

DEFAULT_TIMEOUT = 45


async def request(method, url, proxies=None, **kwargs):
    if "timeout" not in kwargs:
        kwargs["timeout"] = DEFAULT_TIMEOUT
    async with httpx.AsyncClient(
        proxies=proxies, verify=False, follow_redirects=True
    ) as client:
        return await client.request(method, url, **kwargs)


class Session:
    def __init__(self):
        self.headers = {}
        self.verify = False
        self._client = None
        self._proxies = None

    @property
    def cookies(self):
        return self._client.cookies.jar

    def cookies_dict(self):
        return {c.name: c.value for c in self._client.cookies.jar}

    def set_cookies(self, d):
        for k, v in d.items():
            self._client.cookies.set(k, v)

    @property
    def proxies(self):
        return self._proxies

    @proxies.setter
    def proxies(self, p):
        self._proxies = p
        self._set_client()

    def _set_client(self):
        self._client = httpx.AsyncClient(
            proxies=self._proxies, verify=self.verify, follow_redirects=True
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args, **kwargs):
        await self._close()

    async def _close(self):
        if self._client and self._client._state is ClientState.OPENED:
            await self._client.__aexit__()

    async def request(self, *args, headers=None, proxies=None, **kwargs):
        if "timeout" not in kwargs:
            kwargs["timeout"] = DEFAULT_TIMEOUT
        if self._client._state is ClientState.UNOPENED:
            await self._client.__aenter__()
        headers = self.headers | (headers or {})
        headers = {k: v for k, v in headers.items() if v is not None}
        kwargs = {k: v for k, v in kwargs.items() if v}
        return await self._client.request(*args, headers=headers, **kwargs)

    async def get(self, *args, **kwargs):
        return await self.request("get", *args, **kwargs)

    async def post(self, *args, **kwargs):
        return await self.request("post", *args, **kwargs)


__all__ = [
    "HTTPError",
    "RequestError",
    "TransportError",
    "TimeoutException",
    "ConnectTimeout",
    "ReadTimeout",
    "WriteTimeout",
    "PoolTimeout",
    "NetworkError",
    "ConnectError",
    "ReadError",
    "WriteError",
    "CloseError",
    "ProtocolError",
    "LocalProtocolError",
    "RemoteProtocolError",
    "ProxyError",
    "UnsupportedProtocol",
    "DecodingError",
    "TooManyRedirects",
    "HTTPStatusError",
    "InvalidURL",
    "CookieConflict",
    "ZstdDecoder",
    "request",
    "Session",
]

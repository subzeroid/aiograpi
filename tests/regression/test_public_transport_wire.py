"""Exercise the optional public adapter with real loopback response bodies."""

import asyncio
import gzip
import threading
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from aiograpi import Client

BODY = '{"status":"ok","title":"café"}'.encode()
PAYLOAD = {"status": "ok", "title": "café"}


@pytest.fixture(scope="module")
def public_server():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = BODY
            encoding = self.path.removeprefix("/")
            if encoding == "gzip":
                body = gzip.compress(body)
            elif encoding == "deflate":
                body = zlib.compress(body)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            if encoding != "plain":
                self.send_header("Content-Encoding", encoding)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}"
        finally:
            server.shutdown()
            thread.join(timeout=5)


@pytest.fixture
def curl_adapter():
    # Default installations must remain usable without the optional extra.
    return pytest.importorskip("curl_adapter")


@pytest.mark.parametrize("encoding", ["plain", "gzip", "deflate"])
@pytest.mark.parametrize("stream", [False, True], ids=["buffered", "streamed"])
def test_public_curl_reads_response_body(curl_adapter, public_server, encoding, stream):
    async def check():
        client = Client(public_transport="curl")
        client.public._client.trust_env = False
        async with client.public, client.private, client.graphql:
            assert isinstance(client.public._client.get_adapter("http://"), curl_adapter.CurlCffiAdapter)
            response = await client.public.get(f"{public_server}/{encoding}", stream=stream, timeout=5)
            try:
                assert response.status_code == 200
                if stream:
                    assert not response._content_consumed
                    body = await asyncio.to_thread(lambda: b"".join(response.iter_content(chunk_size=7)))
                    assert body == BODY
                else:
                    assert response.content == BODY
                    assert response.json() == PAYLOAD
            finally:
                response.close()

    asyncio.run(check())


@pytest.mark.parametrize("encoding", ["plain", "gzip", "deflate"])
def test_public_curl_request_decodes_json(curl_adapter, public_server, encoding):
    async def check():
        client = Client(public_transport="curl")
        client.public._client.trust_env = False
        async with client.public, client.private, client.graphql:
            payload = await client.public_request(f"{public_server}/{encoding}", return_json=True, retries_count=1)
            assert payload == PAYLOAD

    asyncio.run(check())

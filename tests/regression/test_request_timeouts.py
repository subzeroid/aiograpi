import asyncio
from unittest import mock

import httpx
import pytest

from aiograpi import Client


@pytest.fixture(params=[{}, {"request_timeout": 0}, {"request_timeout": 7}], ids=["default", "zero", "custom"])
def client(request):
    return Client(**request.param)


@pytest.fixture(params=[None, 30], ids=["default-read-timeout", "custom-read-timeout"])
def read_timeout(client, request):
    if request.param is not None:
        client.read_timeout = request.param
    return 25 if request.param is None else request.param


def test_share_link_resolution_uses_read_timeout(client, read_timeout):
    url = "https://www.instagram.com/share/p/example/"
    response = httpx.Response(
        302,
        headers={"Location": "https://www.instagram.com/p/B1LbfVPlwIA/"},
        request=httpx.Request("GET", url),
    )

    with mock.patch("aiograpi.mixins.media.httpx_ext.request", new_callable=mock.AsyncMock) as request:
        request.return_value = response
        media_pk = asyncio.run(client.media_pk_from_url(url))

    assert media_pk == "2110901750722920960"
    request.assert_awaited_once_with(
        "GET",
        url,
        proxy=client.public.proxy,
        timeout=read_timeout,
        follow_redirects=False,
    )


def test_track_download_uses_read_timeout(client, read_timeout, tmp_path):
    url = "https://example.com/audio.m4a"
    content = b"downloaded audio bytes"
    response = httpx.Response(200, content=content, request=httpx.Request("GET", url))

    with mock.patch("aiograpi.mixins.track.httpx_ext.request", new_callable=mock.AsyncMock) as request:
        request.return_value = response
        path = asyncio.run(client.track_download_by_url(url, filename="track", folder=tmp_path))

    assert path == tmp_path / "track.m4a"
    assert path.read_bytes() == content
    request.assert_awaited_once_with("GET", url, timeout=read_timeout)


@pytest.mark.parametrize("surface", ["public", "private"])
def test_read_timeout_preserves_request_pacing(client, surface):
    client.read_timeout = 30
    client.last_response_ts = 0
    url = "https://www.instagram.com/api/test/"
    response = httpx.Response(200, json={"status": "ok"}, request=httpx.Request("GET", url))

    with (
        mock.patch.object(getattr(client, surface), "get", new_callable=mock.AsyncMock) as get,
        mock.patch(f"aiograpi.mixins.{surface}.asyncio.sleep", new_callable=mock.AsyncMock) as sleep,
    ):
        get.return_value = response
        if surface == "public":
            result = asyncio.run(client._send_public_request(url, return_json=True))
        else:
            result = asyncio.run(client._send_private_request("test/"))

    assert result == {"status": "ok"}
    if surface == "public":
        sleep.assert_not_awaited()
    else:
        sleep.assert_awaited_once_with(client.request_timeout)


@pytest.mark.parametrize("request_timeout", [0, 7])
def test_settings_preserve_request_pacing(request_timeout):
    client = Client(settings={"request_timeout": request_timeout})
    client.read_timeout = 30

    assert client.request_timeout == request_timeout
    assert client.get_settings()["request_timeout"] == request_timeout

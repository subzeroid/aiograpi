import asyncio

import pytest

from aiograpi import Client
from aiograpi.httpx_ext import CurlPrivateSession


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({}, "curl"),
        ({"settings": {"locale": "en_US"}}, "curl"),
        ({"private_transport": "requests"}, "requests"),
        ({"settings": {"locale": "en_US"}, "private_transport": "requests"}, "requests"),
        ({"settings": {"private_transport": "requests"}, "private_transport": "curl"}, "requests"),
        ({"settings": {"private_transport": "curl"}, "private_transport": "requests"}, "curl"),
    ],
)
def test_private_transport_default_and_saved_precedence(kwargs, expected):
    client = Client(**kwargs)
    try:
        assert client.private_transport == expected
        assert (isinstance(client.private, CurlPrivateSession)) is (expected == "curl")
        assert client.get_settings()["private_transport"] == expected
        assert client.public_transport == "requests"
    finally:

        async def close():
            for session in (client.private, client.public, client.graphql):
                await session._close()

        asyncio.run(close())

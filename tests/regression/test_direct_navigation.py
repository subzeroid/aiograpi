import json
import socket
from copy import deepcopy
from types import SimpleNamespace
from typing import get_args
from urllib.parse import parse_qs

import pytest

from aiograpi import Client
from aiograpi.exceptions import ClientError
from aiograpi.mixins.direct import SEND_ATTRIBUTE

SETTINGS = {"authorization_data": {"ds_user_id": "123", "sessionid": "synthetic-session"}}
LEGACY_CHAIN = (
    "1qT:feed_timeline:1,1qT:feed_timeline:2,1qT:feed_timeline:3,"
    "7Az:direct_inbox:4,7Az:direct_inbox:5,5rG:direct_thread:7"
)
PROFILE_CHAIN = (
    "UserDetailFragment:profile:1:search_result:10:::10,DirectThreadFragment:direct_thread:2:message_button:11:::11"
)
INBOX_CHAIN = (
    "DirectInboxFragment:direct_inbox:1:main_direct:20:::20,DirectThreadFragment:direct_thread:2:inbox:21:::21"
)
PAYLOAD = {"status": "ok", "payload": {"item_id": "1", "timestamp": 1761953663000000, "user_id": "123"}}


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Network prohibited in Direct serialization tests")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)
    import curl_cffi
    import curl_cffi.aio

    monkeypatch.setattr(curl_cffi.Curl, "perform", blocked)
    monkeypatch.setattr(curl_cffi.aio.AsyncCurl, "add_handle", blocked)


def form(request):
    body = request.content
    return parse_qs(body.decode() if isinstance(body, bytes) else body, keep_blank_values=True)


import asyncio
from contextlib import asynccontextmanager

import httpx


class Recorder:
    def __init__(self, gate=None):
        self.records = []
        self.fail_next = False
        self.gate = gate

    async def respond(self, request):
        self.records.append(request)
        if self.gate is not None:
            if len(self.records) == 2:
                self.gate.set()
            await self.gate.wait()
        failure = self.fail_next
        self.fail_next = False
        return httpx.Response(
            400 if failure else 200, json={"status": "fail", "message": "synthetic failure"} if failure else PAYLOAD
        )


@asynccontextmanager
async def recording(gate=None):
    client = Client(settings=deepcopy(SETTINGS), private_transport="requests", request_timeout=0)
    recorder = Recorder(gate)
    await client.private._client.aclose()
    client.private._client = httpx.AsyncClient(transport=httpx.MockTransport(recorder.respond), trust_env=False)
    try:
        yield client, recorder
    finally:
        for session in (client.private, client.public, client.graphql):
            await session._close()
            await session._client.aclose()


@pytest.mark.parametrize("text, endpoint", [("hello", "text"), ("see https://example.com/a", "link")])
@pytest.mark.parametrize("attribution", ["message_button", "inbox_search", "inbox"])
def test_default_chain_matches_actual_header_and_preserves_payload(text, endpoint, attribution):
    async def scenario():
        async with recording() as (client, recorder):
            result = await client.direct_send(text, user_ids=[456], send_attribute=attribution)
            assert result.id == "1"
            request = recorder.records[0]
            data = form(request)
            assert str(request.url).endswith("/broadcast/" + endpoint + "/")
            assert request.headers["X-IG-Nav-Chain"] == data["nav_chain"][0] == LEGACY_CHAIN
            assert data["send_attribution"] == [attribution]
            assert json.loads(data["recipient_users"][0]) == [[456]]
            assert data["client_context"] == data["mutation_token"] == data["offline_threading_id"]
            assert "signed_body" not in data
            assert attribution in get_args(SEND_ATTRIBUTE)
            if endpoint == "link":
                assert data["link_text"] == [text]
                assert json.loads(data["link_urls"][0]) == ["https://example.com/a"]
            else:
                assert data["text"] == [text]

    asyncio.run(scenario())


def test_custom_chains_are_request_local_and_do_not_leak():
    async def scenario():
        async with recording() as (client, recorder):
            original = client.base_headers["X-IG-Nav-Chain"]
            for chain, attribution in [(PROFILE_CHAIN, "message_button"), (INBOX_CHAIN, "inbox")]:
                await client.direct_send("hello", thread_ids=[456], send_attribute=attribution, nav_chain=chain)
            await client.private_request("test/")
            assert [form(req)["nav_chain"][0] for req in recorder.records[:2]] == [PROFILE_CHAIN, INBOX_CHAIN]
            assert [req.headers["X-IG-Nav-Chain"] for req in recorder.records] == [PROFILE_CHAIN, INBOX_CHAIN, original]
            assert client.base_headers["X-IG-Nav-Chain"] == client.private.headers["X-IG-Nav-Chain"] == original

    asyncio.run(scenario())


def test_positional_reply_and_link_keep_fields_with_custom_chain():
    async def scenario():
        async with recording() as (client, recorder):
            reply = SimpleNamespace(id="88", client_context="reply-context")
            await client.direct_send(
                "https://example.com/reply", [], [456], "message_button", reply, nav_chain=PROFILE_CHAIN
            )
            request = recorder.records[0]
            data = form(request)
            assert str(request.url).endswith("/broadcast/link/")
            assert data["nav_chain"] == [PROFILE_CHAIN]
            assert request.headers["X-IG-Nav-Chain"] == PROFILE_CHAIN
            assert data["replied_to_item_id"] == ["88"]
            assert data["replied_to_client_context"] == ["reply-context"]
            assert data["replied_to_action_source"] == ["swipe"]
            assert json.loads(data["thread_ids"][0]) == [456]
            assert "recipient_users" not in data

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "chain",
    [
        "",
        " ",
        " leading",
        "x\rInjected: yes",
        "x\nInjected: yes",
        "x\x00",
        "x\t",
        "x\x7f",
        "trailing ",
        "x\x85",
        "x\xa0",
        "xé",
        "x\u2014",
        123,
        False,
        [],
    ],
)
def test_invalid_chain_is_rejected_before_dispatch(chain):
    async def scenario():
        async with recording() as (client, recorder):
            with pytest.raises(ValueError, match="nav_chain"):
                await client.direct_send("hello", thread_ids=[456], nav_chain=chain)
            assert recorder.records == []

    asyncio.run(scenario())


def test_failed_send_does_not_leak_chain_to_next_request():
    async def scenario():
        async with recording() as (client, recorder):
            original = client.base_headers["X-IG-Nav-Chain"]
            recorder.fail_next = True
            with pytest.raises(ClientError):
                await client.direct_send("hello", thread_ids=[456], nav_chain=PROFILE_CHAIN)
            await client.private_request("test/")
            assert len(recorder.records) == 2
            assert recorder.records[0].headers["X-IG-Nav-Chain"] == PROFILE_CHAIN
            assert recorder.records[1].headers["X-IG-Nav-Chain"] == original
            assert client.private.headers["X-IG-Nav-Chain"] == original

    asyncio.run(scenario())


def test_overlapping_sends_keep_their_own_navigation_headers():
    async def scenario():
        async with recording(gate=asyncio.Event()) as (client, recorder):
            original = client.base_headers["X-IG-Nav-Chain"]
            await asyncio.wait_for(
                asyncio.gather(
                    client.direct_send("one", thread_ids=[456], nav_chain=PROFILE_CHAIN),
                    client.direct_send("two", thread_ids=[789], send_attribute="inbox", nav_chain=INBOX_CHAIN),
                ),
                timeout=2,
            )
            assert len(recorder.records) == 2
            for request in recorder.records:
                data = form(request)
                expected = PROFILE_CHAIN if data["text"] == ["one"] else INBOX_CHAIN
                assert request.headers["X-IG-Nav-Chain"] == data["nav_chain"][0] == expected
            assert client.private.headers["X-IG-Nav-Chain"] == original

    asyncio.run(scenario())

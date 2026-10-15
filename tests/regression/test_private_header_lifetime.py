import asyncio
import base64
import json
import socket
from contextlib import asynccontextmanager
from copy import deepcopy
from itertools import count
from types import SimpleNamespace

import httpx
import pytest

from aiograpi import Client
from aiograpi.mixins import private

PIGEON = "X-Pigeon-Session-Id"
RAWTIME = "X-Pigeon-Rawclienttime"
SALT = "X-IG-SALT-IDS"
ACCOUNT_SETTINGS = {"authorization_data": {"ds_user_id": "123", "sessionid": "synthetic-session"}}


def _authorization_header(auth_data: dict) -> str:
    payload = base64.b64encode(json.dumps(auth_data).encode()).decode()
    return f"Bearer IGT:2:{payload}"


async def _client_with_responder(settings, respond):
    client = Client(settings=settings, private_transport="requests", request_timeout=0)
    await client.private._client.aclose()
    client.private._client = httpx.AsyncClient(transport=httpx.MockTransport(respond), trust_env=False)
    return client


async def _close_client(client):
    for session in (client.private, client.public, client.graphql):
        await session._close()
        await session._client.aclose()


@pytest.fixture(autouse=True)
def header_clock(monkeypatch):
    def forbid_network(*args, **kwargs):
        raise AssertionError("Network access is forbidden in header lifetime tests")

    monkeypatch.setattr(socket.socket, "connect", forbid_network)
    clock = count(1700000000, 2)
    monkeypatch.setattr(private, "time", SimpleNamespace(time=lambda: next(clock)))


async def record_requests(client, records):
    def respond(request):
        records.append(request)
        return httpx.Response(200, json={"status": "ok"})

    await client.private._client.aclose()
    client.private._client = httpx.AsyncClient(transport=httpx.MockTransport(respond), trust_env=False)


@asynccontextmanager
async def recording_client(settings=None, records=None):
    records = [] if records is None else records
    client = Client(settings=settings, private_transport="requests", request_timeout=0)
    await record_requests(client, records)
    try:
        yield client, records
    finally:
        for session in (client.private, client.public, client.graphql):
            await session._close()
            await session._client.aclose()


def test_successive_get_and_post_reuse_pigeon_id():
    async def scenario():
        async with recording_client() as (client, records):
            await client.private_request("test/", login=True)
            await client.private_request("test/", data={"synthetic": "value"}, login=True)

            assert [request.method for request in records] == ["GET", "POST"]
            same_pigeon = records[0].headers[PIGEON] == records[1].headers[PIGEON]
            assert same_pigeon, "A Client must reuse its runtime Pigeon ID"

    asyncio.run(scenario())


def test_rawclienttime_is_fresh_for_each_request():
    async def scenario():
        async with recording_client() as (client, records):
            await client.private_request("test/", login=True)
            await client.private_request("test/", data={"synthetic": "value"}, login=True)

            newer_timestamp = float(records[1].headers[RAWTIME]) > float(records[0].headers[RAWTIME])
            assert newer_timestamp

    asyncio.run(scenario())


def test_new_and_restored_clients_have_distinct_runtime_ids():
    async def scenario():
        async with recording_client(deepcopy(ACCOUNT_SETTINGS)) as (original, records):
            saved = original.get_settings()
            await original.private_request("test/")
            async with recording_client(saved, records) as (restored, _):
                await restored.private_request("test/")
                assert restored.get_settings()["uuids"] == saved["uuids"]
                assert restored.authorization_data == original.authorization_data
            async with recording_client(records=records) as (independent, _):
                await independent.private_request("test/", login=True)

            distinct_ids = len({request.headers[PIGEON] for request in records})
            assert distinct_ids == 3
            pigeon_persisted = any("pigeon" in key.lower() for key in saved)
            assert not pigeon_persisted

    asyncio.run(scenario())


def test_reapplying_settings_preserves_runtime_id():
    async def scenario():
        async with recording_client(deepcopy(ACCOUNT_SETTINGS)) as (client, records):
            await client.private_request("test/")
            client.set_settings(client.get_settings())
            await record_requests(client, records)
            await client.private_request("test/")

            same_pigeon = records[0].headers[PIGEON] == records[1].headers[PIGEON]
            assert same_pigeon, "Settings reapplication must preserve the runtime Pigeon ID"

    asyncio.run(scenario())


def test_authorization_cleanup_preserves_runtime_id():
    async def scenario():
        async with recording_client(deepcopy(ACCOUNT_SETTINGS)) as (client, records):
            await client.private_request("test/")
            client._clear_session_state(
                clear_private_cookies=True, clear_authorization_data=True, clear_authorization_header=True
            )
            await client.private_request("test/", login=True)

            assert "Authorization" in records[0].headers
            assert "Authorization" not in records[1].headers
            assert records[1].headers["IG-INTENDED-USER-ID"] == "0"
            same_pigeon = records[0].headers[PIGEON] == records[1].headers[PIGEON]
            assert same_pigeon, "Authorization cleanup must preserve the runtime Pigeon ID"

    asyncio.run(scenario())


def test_private_request_applies_rotated_authorization_and_reuses_it():
    async def scenario():
        rotated = {"ds_user_id": "999", "sessionid": "rotated-session"}
        outgoing_auth = []

        def respond(request):
            outgoing_auth.append(request.headers.get("Authorization"))
            return httpx.Response(
                200,
                json={"status": "ok"},
                headers={"ig-set-authorization": _authorization_header(rotated)},
            )

        client = await _client_with_responder(deepcopy(ACCOUNT_SETTINGS), respond)
        try:
            await client.private_request("test/", login=True)
            # rotation is merged into the live session
            assert client.authorization_data["ds_user_id"] == "999"
            assert client.authorization_data["sessionid"] == "rotated-session"
            # persisted settings carry the rotation
            assert client.get_settings()["authorization_data"] == rotated
            # the next outgoing request uses the rotated token
            await client.private_request("test/", login=True)
            sent = json.loads(base64.b64decode(outgoing_auth[-1].rsplit(":", 1)[-1]))
            assert sent["sessionid"] == "rotated-session"
        finally:
            await _close_client(client)

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "header_value",
    [
        None,  # absent
        "",  # empty
        "Bearer IGT:2:!!!not-base64!!!",  # malformed base64
        "Bearer IGT:2:" + base64.b64encode(b"not-json").decode(),  # malformed JSON
        "Bearer IGT:2:" + base64.b64encode(b'["a", "b"]').decode(),  # non-mapping: list
        "Bearer IGT:2:"
        + base64.b64encode(b'[["k", "v"], ["k2", "v2"]]').decode(),  # non-mapping: list of key/value pairs
        "Bearer IGT:2:" + base64.b64encode(b'"just-a-string"').decode(),  # non-mapping: string
        "Bearer IGT:2:" + base64.b64encode(b"null").decode(),  # non-mapping: null
    ],
)
def test_private_request_ignores_invalid_authorization_header(header_value):
    async def scenario():
        def respond(request):
            headers = {"ig-set-authorization": header_value} if header_value is not None else {}
            return httpx.Response(200, json={"status": "ok"}, headers=headers)

        client = await _client_with_responder(deepcopy(ACCOUNT_SETTINGS), respond)
        try:
            await client.private_request("test/", login=True)
            assert client.authorization_data == ACCOUNT_SETTINGS["authorization_data"]
        finally:
            await _close_client(client)

    asyncio.run(scenario())


def test_upload_header_helper_uses_the_same_runtime_id():
    async def scenario():
        async with recording_client(deepcopy(ACCOUNT_SETTINGS)) as (client, records):
            await client.private_request("test/")
            await client.private.post(
                "https://i.instagram.com/rupload_igphoto/synthetic",
                data=b"synthetic",
                headers=client.private_headers({"X-Entity-Type": "image/jpeg"}),
            )
            await client.private_request("test/")

            assert records[1].headers["X-Entity-Type"] == "image/jpeg"
            assert "Authorization" in records[1].headers
            same_pigeon = len({request.headers[PIGEON] for request in records}) == 1
            assert same_pigeon, "Uploads and private API requests must share the runtime Pigeon ID"
            newer_timestamp = float(records[1].headers[RAWTIME]) > float(records[0].headers[RAWTIME])
            assert newer_timestamp

    asyncio.run(scenario())


def test_default_headers_omit_salt_ids():
    async def scenario():
        async with recording_client() as (client, records):
            await client.private_request("test/", login=True)
            await client.private_request("test/", data={"synthetic": "value"}, login=True)

            salt_omitted = all(SALT not in request.headers for request in records)
            assert salt_omitted, "Ordinary requests must not fabricate diagnostic flow IDs"
            assert SALT not in client.private_headers()
            assert SALT not in client.private.headers

    asyncio.run(scenario())


def test_explicit_request_overrides_do_not_leak():
    async def scenario():
        async with recording_client() as (client, records):
            await client.private_request("test/", login=True)
            await client.private_request(
                "test/", data={"synthetic": "value"}, headers={PIGEON: "caller-pigeon", SALT: "11,12"}, login=True
            )
            await client.private_request("test/", login=True)

            assert records[1].headers[PIGEON] == "caller-pigeon"
            assert records[1].headers[SALT] == "11,12"
            same_pigeon = records[0].headers[PIGEON] == records[2].headers[PIGEON]
            assert same_pigeon, "A request override must not replace the runtime Pigeon ID"
            assert SALT not in records[2].headers
            assert SALT not in client.private.headers

    asyncio.run(scenario())


def test_persistent_caller_salt_survives_requests_and_temporary_override():
    async def scenario():
        async with recording_client() as (client, records):
            client.private.headers[SALT] = "11,12"
            await client.private_request("test/", login=True)
            await client.private_request("test/", data={"synthetic": "value"}, headers={SALT: "21"}, login=True)
            await client.private_request("test/", login=True)

            caller_salt_preserved = [request.headers.get(SALT) for request in records] == ["11,12", "21", "11,12"]
            assert caller_salt_preserved, "Base headers must preserve caller-supplied persistent SALT"
            assert client.private.headers[SALT] == "11,12"

    asyncio.run(scenario())


def test_transport_switches_preserve_runtime_id():
    pytest.importorskip("curl_cffi")

    async def scenario():
        async with recording_client() as (client, records):
            await client.private_request("test/", login=True)
            for transport in ("curl", "requests"):
                client.set_retry_config(private_transport=transport)
                await record_requests(client, records)
                await client.private_request("test/", login=True)

            same_pigeon = len({request.headers[PIGEON] for request in records}) == 1
            assert same_pigeon, "Transport selection must preserve the runtime Pigeon ID"

    asyncio.run(scenario())

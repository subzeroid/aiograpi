# protects: Optional uTLS session changes retain account identity and never persist deployment paths.
# fails_when: Saved settings silently select another transport, drop cookies, leak clients or replay a POST.
# why_new: Existing curl session tests have no verified native library or worker lifetime.
import asyncio
import threading
from unittest.mock import Mock

import httpx
import pytest

from aiograpi import Client
from aiograpi.exceptions import ConnectProxyError
from tests.regression.test_utls_transport import native as native
from tests.regression.test_utls_transport import wait_started


async def close(client):
    for session in (client.private, client.public, client.graphql):
        await session._close()


def test_explicit_selection_and_restore_exclude_deployment_path(native):
    async def scenario():
        client = Client(private_transport="utls", utls_library_path="fixture-native")
        try:
            assert client.private_transport == "utls"
            assert client.private.library_path == "fixture-native"
            client.private.set_cookies({"sessionid": "synthetic"})
            transport = client.private._client._transport
            settings = client.get_settings()
            assert settings["private_transport"] == "utls"
            assert "utls_library_path" not in settings
            client.set_settings(settings)
            client.set_retry_config(private_transport="utls")
            assert client.private._client._transport is transport
            assert client.private.cookies_dict()["sessionid"] == "synthetic"
            restored = Client(settings=settings, utls_library_path="fixture-native")
            try:
                assert (
                    restored.private_transport == "utls" and restored.private.cookies_dict()["sessionid"] == "synthetic"
                )
            finally:
                await close(restored)
        finally:
            await close(client)

    asyncio.run(scenario())


def test_switch_and_route_replacement_preserve_identity_and_drain_retired_clients(native):
    async def scenario():
        client = Client(private_transport="requests", utls_library_path="fixture-native", proxy="http://127.0.0.1:3128")
        try:
            client.private._client.cookies.set("sessionid", "synthetic", domain=".instagram.com", path="/api")
            client.private.headers["X-Custom"] = "preserved"
            original = client.private._client
            device, public, graphql = client.uuid, client.public, client.graphql
            client.set_retry_config(private_transport="utls")
            assert original in client.private._retired_clients
            assert client.private.proxy == "http://127.0.0.1:3128"
            assert client.private.headers["X-Custom"] == "preserved"
            assert [(c.name, c.domain, c.path) for c in client.private.cookies] == [
                ("sessionid", ".instagram.com", "/api")
            ]
            assert client.uuid == device and client.public is public and client.graphql is graphql
            await client.private.get("https://i.instagram.com/api/fixture", timeout=1)
            assert original.is_closed and not client.private._retired_clients
            assert native.payloads[-1]["proxyUrl"] == "http://127.0.0.1:3128"
            previous = client.private._client
            client.set_proxy("http://127.0.0.1:3129")
            assert previous in client.private._retired_clients
            client.set_tls_verify(False)
            await client.private.get("https://i.instagram.com/api/fixture", timeout=1)
            assert previous.is_closed
            assert native.payloads[-1]["proxyUrl"] == "http://127.0.0.1:3129"
            assert native.payloads[-1]["insecureSkipVerify"] is True
            client.set_retry_config(private_transport="curl")
            assert client.private_transport == "curl" and client.private.cookies_dict()["sessionid"] == "synthetic"
        finally:
            await close(client)

    asyncio.run(scenario())


@pytest.mark.parametrize("detail", ["unexpected EOF secret-fixture", "context deadline exceeded secret-fixture"])
def test_private_request_native_failure_never_enters_incomplete_read_retry(native, detail):
    async def scenario():
        client = Client(private_transport="utls", utls_library_path="fixture-native", request_timeout=0)
        native.replies.append({"id": "fixture-result", "status": 0, "body": detail})
        try:
            with pytest.raises(ConnectProxyError) as caught:
                await client.private_request("accounts/login/", data={"synthetic": "value"}, login=True)
            assert len(native.payloads) == 1
            assert "secret-fixture" not in str(caught.value)
        finally:
            await close(client)

    asyncio.run(scenario())


def test_failed_selection_keeps_existing_client(native, monkeypatch):
    async def scenario():
        client = Client(private_transport="requests")
        old = client.private
        loader = Mock(side_effect=RuntimeError("verified library required"))
        monkeypatch.setattr("aiograpi.utls.load_library", loader)
        try:
            with pytest.raises(RuntimeError, match="verified"):
                client.set_retry_config(private_transport="utls")
            assert client.private is old and client.private_transport == "requests"
            assert not old._client.is_closed
        finally:
            await close(client)

    asyncio.run(scenario())


def test_default_and_legacy_selection_never_load_utls(native, monkeypatch):
    async def scenario():
        loader = Mock(side_effect=AssertionError("uTLS must remain optional"))
        monkeypatch.setattr("aiograpi.utls.load_library", loader)
        for options, expected in (({}, "curl"), ({"private_transport": "requests"}, "requests")):
            client = Client(**options)
            assert client.private_transport == expected
            await close(client)
        loader.assert_not_called()

    asyncio.run(scenario())


def test_cancelled_retired_client_close_remains_joinable_after_transport_change(native):
    async def scenario():
        started, release = threading.Event(), threading.Event()

        def block():
            started.set()
            assert release.wait(2)

        native.before = block
        client = Client(private_transport="utls", utls_library_path="fixture-native")
        old = client.private._client
        first = asyncio.create_task(client.private.get("https://fixture.invalid/", timeout=1))
        try:
            await wait_started(started)
            first.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first
            client.set_retry_config(private_transport="requests")
            closing = asyncio.create_task(client.private._close())
            await asyncio.sleep(0.02)
            closing.cancel()
            with pytest.raises(asyncio.CancelledError):
                await closing
            assert old in client.private._retired_clients
            finishing = asyncio.create_task(client.private._close())
            await asyncio.sleep(0.02)
            assert not finishing.done() and "destroy" not in native.events
            release.set()
            await finishing
            assert old not in client.private._retired_clients and "destroy" in native.events
        finally:
            release.set()
            await close(client)

    asyncio.run(scenario())


def test_concurrent_requests_after_between_request_proxy_rebuild(native):
    async def scenario():
        client = Client(private_transport="utls", utls_library_path="fixture-native")
        try:
            client.set_proxy("http://127.0.0.1:3128")
            results = await asyncio.gather(
                client.private.get("https://fixture.invalid/first", timeout=1),
                client.private.get("https://fixture.invalid/second", timeout=1),
                return_exceptions=True,
            )
            assert not any(isinstance(result, Exception) for result in results)
        finally:
            await close(client)

    asyncio.run(scenario())


def test_failed_tls_rebuild_then_identical_retry_enables_verification(native, monkeypatch):
    async def scenario():
        client = Client(private_transport="utls", utls_library_path="fixture-native", tls_verify=False)
        original_loader = __import__("aiograpi.utls", fromlist=["load_library"]).load_library
        try:
            monkeypatch.setattr("aiograpi.utls.load_library", Mock(side_effect=RuntimeError("fixture load failure")))
            with pytest.raises(RuntimeError, match="fixture load failure"):
                client.set_tls_verify(True)
            monkeypatch.setattr("aiograpi.utls.load_library", original_loader)
            client.set_tls_verify(True)
            await client.private.get("https://fixture.invalid/", timeout=1)
            assert native.payloads[-1]["insecureSkipVerify"] is False
        finally:
            await close(client)

    asyncio.run(scenario())


def test_rejected_utls_ca_configuration_leaves_all_sessions_and_settings_unchanged(native):
    import certifi

    async def scenario():
        client = Client(private_transport="utls", utls_library_path="fixture-native")
        sessions = (client.public, client.private, client.graphql)
        old = [session._client for session in sessions]
        for session in sessions:
            session.set_cookies({"synthetic_cookie": "preserved"})
        saved = client.get_settings()
        try:
            with pytest.raises(ValueError, match="CA"):
                client.set_tls_verify(certifi.where())
            assert client.tls_verify is True and client.get_settings() == saved
            assert [session._client for session in sessions] == old
            assert all(session.verify is True for session in sessions)
            assert all(session.cookies_dict()["synthetic_cookie"] == "preserved" for session in sessions)
        finally:
            await close(client)

    asyncio.run(scenario())


def test_terminal_retired_close_error_is_reported_once_without_poisoning_new_session(native):
    async def scenario():
        client = Client(private_transport="utls", utls_library_path="fixture-native")
        old = client.private._client
        old._transport.client.close = Mock(side_effect=RuntimeError("synthetic close failure"))
        client.private.proxy = "http://127.0.0.1:3128"
        try:
            with pytest.raises(RuntimeError, match="synthetic close failure"):
                await client.private.get("https://fixture.invalid/", timeout=1)
            assert old not in client.private._retired_clients
            assert native.payloads == []
            assert (await client.private.get("https://fixture.invalid/", timeout=1)).status_code == 200
            assert len(native.payloads) == 1
        finally:
            if old in client.private._retired_clients:
                client.private._retired_clients.remove(old)
            await close(client)

    asyncio.run(scenario())


def test_rejected_proxy_rebuild_keeps_all_sessions_on_the_previous_route(native, monkeypatch):
    async def scenario():
        client = Client(private_transport="utls", utls_library_path="fixture-native", proxy="http://127.0.0.1:3128")
        sessions = (client.private, client.public, client.graphql)
        previous = [session._client for session in sessions]
        try:
            monkeypatch.setattr("aiograpi.utls.load_library", Mock(side_effect=RuntimeError("synthetic cache failure")))
            with pytest.raises(RuntimeError, match="synthetic cache failure"):
                client.set_proxy("http://127.0.0.1:3129")
            assert [session._client for session in sessions] == previous
            assert all(session.proxy == "http://127.0.0.1:3128" for session in sessions)
            assert client.proxy == "http://127.0.0.1:3128"
            await client.private.get("https://fixture.invalid/", timeout=1)
            assert native.payloads[-1]["proxyUrl"] == "http://127.0.0.1:3128"
        finally:
            await close(client)

    asyncio.run(scenario())


@pytest.mark.parametrize("started_drain", [False, True])
def test_direct_drain_task_cancellation_cannot_abandon_native_cleanup(native, started_drain):
    async def scenario():
        started, release = threading.Event(), threading.Event()

        def block():
            started.set()
            assert release.wait(2)

        native.before = block
        client = Client(private_transport="utls", utls_library_path="fixture-native")
        old = client.private._client
        request = asyncio.create_task(client.private.get("https://fixture.invalid/", timeout=1))
        closing = None
        try:
            await wait_started(started)
            request.cancel()
            with pytest.raises(asyncio.CancelledError):
                await request
            client.private.proxy = "http://127.0.0.1:3128"
            closing = asyncio.create_task(old.aclose())
            while old._transport._closing is None:
                await asyncio.sleep(0)
            if started_drain:
                await asyncio.sleep(0)
            old._transport._closing.cancel()
            await asyncio.sleep(0)
            release.set()
            await asyncio.gather(closing, return_exceptions=True)
            assert (await client.private.get("https://fixture.invalid/", timeout=1)).status_code == 200
            assert old not in client.private._retired_clients
            assert native.events.count("destroy") == 1
        finally:
            release.set()
            if closing is not None:
                await asyncio.gather(closing, return_exceptions=True)
            await close(client)

    asyncio.run(scenario())

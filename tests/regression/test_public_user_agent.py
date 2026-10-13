import io
import itertools
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import httpx
import requests
from requests.adapters import HTTPAdapter

from aiograpi import Client
from aiograpi.mixins import public as public_mixin

LEGACY_GRAPHQL_UA = "Instagram 273.0.0.16.70 (iPhone15,2; iOS 17_5_1; en_US; en-US; scale=3.00; 1290x2796; 470085518)"
PROFILE = {
    "pk": "123",
    "username": "example",
    "full_name": "Example",
    "is_private": False,
    "is_verified": False,
    "profile_pic_url": "https://example.test/pic.jpg",
    "media_count": 1,
    "follower_count": 2,
    "following_count": 3,
    "is_business": False,
}
LSD_HTML = '<script>["LSD",[],{"token":"lsd-token"}]</script>'


class PublicUserAgentTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.clients = []
        ticks = itertools.count(10, 2)
        patcher = mock.patch.object(
            public_mixin, "time", SimpleNamespace(time=lambda: next(ticks), sleep=lambda _: None)
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    async def build_client(self, payloads=None, client_class=Client, **kwargs):
        client = client_class(request_timeout=0, **kwargs)
        self.clients.append(client)
        for session in (client.private, client.graphql):
            if session._client is not None:
                self.addAsyncCleanup(session._client.aclose)
        await self.bind_recording(client, payloads)
        return client

    async def bind_recording(self, client, payloads=None):
        client._recorded = []
        queue = list(payloads or [])

        async def respond(request):
            client._recorded.append({"method": request.method, "agents": request.headers.get_list("user-agent")})
            payload = queue.pop(0) if queue else {"status": "ok", "data": {"user": PROFILE, "ok": True}}
            if isinstance(payload, str):
                return httpx.Response(200, text=payload, request=request)
            return httpx.Response(200, json=payload, request=request)

        if isinstance(client.public._client, requests.Session):

            class RecordingAdapter(HTTPAdapter):
                def send(self, request, **kwargs):
                    client._recorded.append({"method": request.method, "agents": [request.headers["User-Agent"]]})
                    payload = queue.pop(0) if queue else {"status": "ok", "data": {"user": PROFILE, "ok": True}}
                    body = payload.encode() if isinstance(payload, str) else json.dumps(payload).encode()
                    response = requests.Response()
                    response.status_code = 200
                    response._content = body
                    response.raw = io.BytesIO(body)
                    response.url = request.url
                    response.request = request
                    return response

            client.public._client.mount("https://", RecordingAdapter())
            self.addCleanup(client.public._client.close)
            client.last_response_ts = 0
            return
        if client.public._client is not None:
            await client.public._client.aclose()
        client.public._client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        self.addAsyncCleanup(client.public._client.aclose)
        client.last_response_ts = 0

    async def test_defaults_keep_the_existing_route_profiles(self):
        client = await self.build_client()
        web_ua = client.public_user_agent
        private_ua = client.user_agent
        await client.public_request("https://www.instagram.com/", return_json=True)
        await client.public_doc_id_graphql_request("1", {})
        self.assertEqual(client._recorded[0]["agents"], [web_ua])
        self.assertEqual(client._recorded[1]["agents"], [LEGACY_GRAPHQL_UA])
        self.assertEqual(client.public.headers["User-Agent"], web_ua)
        self.assertEqual(client.user_agent, private_ua)

    async def test_constructor_graphql_agent_reaches_a_high_level_profile_helper(self):
        client = await self.build_client(
            public_user_agent="fixture-web-agent", public_graphql_user_agent="fixture-graphql-agent"
        )
        profile = await client.user_info_v2_gql("123")
        self.assertEqual(profile.username, "example")
        self.assertEqual(client._recorded[-1]["agents"], ["fixture-graphql-agent"])
        self.assertEqual(client.public.headers["User-Agent"], "fixture-web-agent")

    async def test_changing_graphql_agent_reaches_username_search_and_profile(self):
        client = await self.build_client(
            payloads=[
                {
                    "data": {
                        "xdt_api__v1__fbsearch__non_profiled_serp": {"users": [{"pk": "123", "username": "example"}]}
                    }
                },
                {"data": {"user": PROFILE}},
            ]
        )
        client.public_graphql_user_agent = "fixture-next-graphql-agent"
        profile = await client.user_info_by_username_v2_gql("example")
        self.assertEqual(profile.pk, "123")
        self.assertEqual([r["agents"] for r in client._recorded], [["fixture-next-graphql-agent"]] * 2)

    async def test_none_graphql_agent_shares_the_web_agent(self):
        client = await self.build_client(public_user_agent="fixture-shared-agent", public_graphql_user_agent=None)
        await client.public_request("https://www.instagram.com/", return_json=True)
        await client.public_graphql_request({}, query_hash="fixture-query")
        await client.public_doc_id_graphql_request("1", {})
        self.assertEqual([r["agents"] for r in client._recorded], [["fixture-shared-agent"]] * 3)

    async def test_lsd_preparation_and_post_keep_the_web_agent(self):
        client = await self.build_client(
            payloads=[LSD_HTML, {"data": {"ok": True}}],
            public_user_agent="fixture-web-agent",
            public_graphql_user_agent="fixture-graphql-agent",
        )
        result = await client.public_doc_id_graphql_request("1", {}, include_lsd=True)
        self.assertEqual(result, {"ok": True})
        self.assertEqual([r["method"] for r in client._recorded], ["GET", "POST"])
        self.assertEqual([r["agents"] for r in client._recorded], [["fixture-web-agent"]] * 2)

    async def test_request_agent_override_is_case_insensitive_and_does_not_persist(self):
        client = await self.build_client(public_user_agent="fixture-web-agent")
        for key in ["User-Agent", "user-agent", "USER-AGENT"]:
            with self.subTest(key=key):
                await client.public_doc_id_graphql_request("1", {}, headers={key: "fixture-request-agent"})
                self.assertEqual(client._recorded[-1]["agents"], ["fixture-request-agent"])
                self.assertEqual(client.public.headers["User-Agent"], "fixture-web-agent")
        await client.public_doc_id_graphql_request("1", {})
        self.assertEqual(client._recorded[-1]["agents"], [LEGACY_GRAPHQL_UA])

    async def test_agents_are_independent_between_clients(self):
        first = await self.build_client(public_graphql_user_agent="fixture-first-agent")
        second = await self.build_client()
        await first.public_doc_id_graphql_request("1", {})
        await second.public_doc_id_graphql_request("1", {})
        self.assertEqual(first._recorded[-1]["agents"], ["fixture-first-agent"])
        self.assertEqual(second._recorded[-1]["agents"], [LEGACY_GRAPHQL_UA])

    async def test_subclass_graphql_default_is_preserved(self):
        class CustomClient(Client):
            public_graphql_user_agent = "fixture-subclass-agent"

        client = await self.build_client(client_class=CustomClient)
        await client.public_doc_id_graphql_request("1", {})
        self.assertEqual(client._recorded[-1]["agents"], ["fixture-subclass-agent"])

    async def test_custom_agents_survive_settings_roundtrip(self):
        original = await self.build_client(
            public_user_agent="fixture-web-agent", public_graphql_user_agent="fixture-graphql-agent"
        )
        settings = json.loads(json.dumps(original.get_settings()))
        self.assertEqual(settings.get("public_user_agent"), "fixture-web-agent")
        self.assertEqual(settings.get("public_graphql_user_agent"), "fixture-graphql-agent")
        restored = await self.build_client(settings=settings)
        await restored.public_request("https://www.instagram.com/", return_json=True)
        await restored.public_doc_id_graphql_request("1", {})
        self.assertEqual([r["agents"] for r in restored._recorded], [["fixture-web-agent"], ["fixture-graphql-agent"]])

    async def test_saved_agents_take_precedence_over_constructor_agents(self):
        settings = {
            "public_transport": "requests",
            "public_user_agent": "fixture-saved-web",
            "public_graphql_user_agent": "fixture-saved-graphql",
        }
        client = await self.build_client(
            settings=settings,
            public_user_agent="fixture-constructor-web",
            public_graphql_user_agent="fixture-constructor-graphql",
        )
        await client.public_doc_id_graphql_request("1", {})
        self.assertEqual(client.public.headers["User-Agent"], "fixture-saved-web")
        self.assertEqual(client._recorded[-1]["agents"], ["fixture-saved-graphql"])

    async def test_explicit_constructor_agent_is_kept_with_legacy_settings(self):
        client = await self.build_client(
            settings={"public_transport": "requests"}, public_user_agent="fixture-explicit-web"
        )
        await client.public_request("https://www.instagram.com/", return_json=True)
        self.assertEqual(client._recorded[-1]["agents"], ["fixture-explicit-web"])

    async def test_legacy_settings_keep_the_selected_transport_default(self):
        # This settings test records prepared requests without requiring the optional curl adapter.
        class Adapter(HTTPAdapter):
            def __init__(self, *, impersonate_browser_type):
                super().__init__()

        with mock.patch.dict("sys.modules", {"curl_adapter": SimpleNamespace(CurlCffiAdapter=Adapter)}):
            for transport in ["requests", "curl"]:
                with self.subTest(transport=transport):
                    client = await self.build_client(settings={"public_transport": transport})
                    self.assertEqual(
                        client.public_user_agent, client._default_public_user_agent(transport, "chrome136")
                    )
                    self.assertEqual(client.public.headers["User-Agent"], client.public_user_agent)
                    await client.public_doc_id_graphql_request("1", {})
                    self.assertEqual(client._recorded[-1]["agents"], [LEGACY_GRAPHQL_UA])

    async def test_setter_shares_agent_and_updates_saved_settings(self):
        client = await self.build_client()
        private_ua = client.user_agent
        self.assertTrue(client.set_public_user_agent("fixture-shared-agent"))
        await client.public_doc_id_graphql_request("1", {})
        self.assertEqual(client._recorded[-1]["agents"], ["fixture-shared-agent"])
        self.assertIsNone(client.public_graphql_user_agent)
        self.assertEqual(client.public.headers["User-Agent"], "fixture-shared-agent")
        self.assertEqual(client.settings["public_user_agent"], "fixture-shared-agent")
        self.assertIsNone(client.settings["public_graphql_user_agent"])
        self.assertEqual(client.user_agent, private_ua)

    async def test_setter_supports_independent_agents_and_file_roundtrip(self):
        client = await self.build_client()
        client.set_public_user_agent("fixture-web-agent", "fixture-graphql-agent")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            client.dump_settings(path)
            restored = await self.build_client()
            restored.load_settings(path)
            await self.bind_recording(restored)
            await restored.public_doc_id_graphql_request("1", {})
        self.assertEqual(restored.public.headers["User-Agent"], "fixture-web-agent")
        self.assertEqual(restored._recorded[-1]["agents"], ["fixture-graphql-agent"])

    async def test_shared_none_survives_roundtrip_and_follows_later_web_changes(self):
        client = await self.build_client(public_user_agent="fixture-web-agent", public_graphql_user_agent=None)
        restored = await self.build_client(settings=client.get_settings())
        self.assertIsNone(restored.public_graphql_user_agent)
        restored.set_public_user_agent("fixture-next-web-agent")
        await restored.public_doc_id_graphql_request("1", {})
        self.assertEqual(restored._recorded[-1]["agents"], ["fixture-next-web-agent"])

    async def test_transport_selection_updates_the_saved_web_profile(self):
        client = await self.build_client(public_user_agent="fixture-custom-web", public_graphql_user_agent=None)
        client.set_retry_config(public_transport="requests")
        await self.bind_recording(client)
        expected = client._default_public_user_agent("requests", "chrome136")
        await client.public_doc_id_graphql_request("1", {})
        self.assertEqual(client._recorded[-1]["agents"], [expected])
        self.assertEqual(client.settings["public_user_agent"], expected)
        self.assertIsNone(client.settings["public_graphql_user_agent"])
        client.init()
        await self.bind_recording(client)
        self.assertEqual(client.public.headers["User-Agent"], expected)

    async def test_transport_selection_preserves_an_independent_graphql_profile(self):
        client = await self.build_client(public_graphql_user_agent="fixture-graphql-agent")
        client.set_retry_config(public_transport="requests")
        await self.bind_recording(client)
        await client.public_doc_id_graphql_request("1", {})
        self.assertEqual(client._recorded[-1]["agents"], ["fixture-graphql-agent"])
        self.assertEqual(client.get_settings()["public_graphql_user_agent"], "fixture-graphql-agent")

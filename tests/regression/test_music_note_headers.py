"""Regression coverage for music Note routing headers; no live requests."""

import inspect
import json
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock

from aiograpi import Client
from aiograpi.exceptions import ClientGraphqlError
from aiograpi.mixins.note import NoteAudience

FIXTURE = Path(__file__).with_name("fixtures") / "music_note_headers.json"


class MusicNoteContractTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = Client(private_transport="requests")
        self.client.request_timeout = 0
        self.client.authorization_data = {"ds_user_id": "123"}
        self.client.request_log = Mock()
        self.fixture = json.loads(FIXTURE.read_text())
        self.post = AsyncMock(return_value=self.response(self.fixture["response"]))
        self.client.private.post = self.post

    @staticmethod
    def response(body):
        response = Mock(status_code=200, url="https://i.instagram.com/graphql/query")
        response.json.return_value = body
        response.text = json.dumps(body)
        response.content = response.text.encode()
        response.headers = {"Content-Type": "application/json"}
        return response

    async def asyncTearDown(self):
        for name in ("private", "public", "graphql"):
            session = getattr(self.client, name)
            close = (
                getattr(session, "_close", None) or getattr(session, "aclose", None) or getattr(session, "close", None)
            )
            if close:
                result = close()
                if inspect.isawaitable(result):
                    await result

    async def create(self, **overrides):
        arguments = dict(
            track={
                "audio_asset_id": "1349366503352513",
                "audio_cluster_id": "2081445788764469",
                "highlight_start_times_in_ms": [61000],
            },
            browse_session_id="browse-test",
            alacorn_session_id="alacorn-test",
        )
        arguments.update(overrides)
        return await self.client.create_music_note(**arguments)

    async def test_required_headers_preserve_existing_operation_and_payload(self):
        note = await self.create()
        self.assertEqual(self.post.call_count, 1)
        args, kwargs = self.post.call_args
        self.assertEqual(args[0], "https://i.instagram.com/graphql/query")
        form = kwargs["data"]
        self.assertEqual(form["client_doc_id"], "3510400299951610199199089856")
        self.assertEqual(form["fb_api_req_friendly_name"], "CreateInboxTrayItemRequest")
        self.assertEqual(form["locale"], self.client.locale)
        self.assertNotIn("purpose", form)
        self.assertEqual(json.loads(form["variables"]), self.fixture["variables"])
        headers = kwargs["headers"]
        self.assertEqual(headers["X-Root-Field-Name"], "xdt_create_inbox_tray_item")
        self.assertEqual(headers["X-GraphQL-Client-Library"], "pando")
        self.assertEqual(note.id, "42")
        self.assertEqual(note.note_style, 1)

    async def test_metadata_does_not_leak_on_success_or_null(self):
        before = dict(self.client.private.headers)
        await self.create()
        self.assertEqual(dict(self.client.private.headers), before)
        self.post.return_value = self.response({"data": {"xdt_create_inbox_tray_item": None}, "status": "ok"})
        with self.assertRaises(ClientGraphqlError):
            await self.create()
        self.assertEqual(dict(self.client.private.headers), before)
        self.assertEqual(self.post.call_count, 2)

    async def test_null_or_unsuccessful_result_never_retries_mutation(self):
        for payload in [None, {"success": False}, {"success": True, "inbox_tray_item": {}}]:
            with self.subTest(payload=payload):
                self.post.reset_mock()
                self.post.return_value = self.response(
                    {"data": {"xdt_create_inbox_tray_item": payload}, "status": "ok"}
                )
                with self.assertRaises(ClientGraphqlError):
                    await self.create()
                self.assertEqual(self.post.call_count, 1)

    async def test_graphql_error_never_retries_mutation(self):
        self.post.return_value = self.response({"errors": [{"message": "mutation failed"}]})
        with self.assertRaises(ClientGraphqlError):
            await self.create()
        self.assertEqual(self.post.call_count, 1)

    async def test_preserves_explicit_audience_text_and_clip(self):
        await self.create(audience=NoteAudience.CLOSE_FRIENDS, text="test", start_time=2500, duration=10000)
        variables = json.loads(self.post.call_args.kwargs["data"]["variables"])
        self.assertEqual(variables["request"]["audience"], 1)
        params = variables["request"]["additional_params"]["note_create_params"]
        self.assertEqual(params["text"], "test")
        music = params["note_create_info"]["music_note_create_info"]
        self.assertEqual((music["start_time"], music["duration"]), (2500, 10000))

    async def test_fetches_missing_session_once_and_generates_browse_id(self):
        self.client.notes_music_browser = AsyncMock(return_value={"alacorn_session_id": "catalog-session"})
        self.client.generate_uuid = Mock(return_value="generated-browse")
        await self.create(alacorn_session_id=None, browse_session_id=None)
        self.assertEqual(self.client.notes_music_browser.call_count, 1)
        variables = json.loads(self.post.call_args.kwargs["data"]["variables"])
        music = variables["request"]["additional_params"]["note_create_params"]["note_create_info"][
            "music_note_create_info"
        ]
        self.assertEqual(music["browse_session_id"], "generated-browse")
        self.assertEqual(music["alacorn_session_id"], "catalog-session")
        self.assertEqual(self.post.call_count, 1)

    async def test_missing_catalog_session_prevents_mutation(self):
        self.client.notes_music_browser = AsyncMock(return_value={})
        with self.assertRaisesRegex(AssertionError, "alacorn_session_id"):
            await self.create(alacorn_session_id=None)
        self.post.assert_not_called()

    async def test_followup_graphql_does_not_inherit_music_note_headers(self):
        await self.create()
        self.post.reset_mock()
        self.post.return_value = self.response({"data": {}})
        await self.client.private_graphql_request({"fb_api_req_friendly_name": "OtherQuery"})
        headers = self.post.call_args.kwargs["headers"]
        self.assertNotIn("X-Root-Field-Name", headers)
        self.assertNotIn("X-GraphQL-Client-Library", headers)
        self.assertEqual(headers["X-FB-Friendly-Name"], "OtherQuery")

    async def test_custom_graphql_headers_are_request_scoped_on_error(self):
        before = dict(self.client.private.headers)
        custom = {"X-Client-Doc-Id": "custom-id"}
        self.post.return_value = self.response({"errors": [{"message": "rejected"}]})
        with self.assertRaises(ClientGraphqlError):
            await self.client.private_graphql_request({"fb_api_req_friendly_name": "CustomQuery"}, headers=custom)
        self.assertEqual(self.post.call_args.kwargs["headers"]["X-Client-Doc-Id"], "custom-id")
        self.assertEqual(dict(self.client.private.headers), before)
        self.assertEqual(custom, {"X-Client-Doc-Id": "custom-id"})
        self.assertEqual(self.post.call_count, 1)

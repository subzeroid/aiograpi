import json
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from aiograpi import Client
from aiograpi.types import Note, UserShort


class NoteMixinRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_get_note_helpers_by_user(self):
        client = Client()
        notes = [
            Note(
                id="1",
                text="hello",
                user_id="10",
                user=UserShort(pk="10", username="example"),
                audience=0,
                created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                expires_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
                is_emoji_only=False,
                has_translation=False,
                note_style=0,
            )
        ]

        note = client.get_note_by_user(notes, "Example")

        assert note is not None
        assert note.id == "1"
        assert client.get_note_text_by_user(notes, "example") == "hello"
        assert client.get_note_by_user(notes, "missing") is None
        assert client.get_note_text_by_user(notes, "missing") is None

    async def test_notes_music_browser_requests_notes_music_product(self):
        client = Client()
        client.uuid = "uuid-1"
        expected = {
            "status": "ok",
            "alacorn_session_id": "alacorn-1",
            "items": [],
        }
        client.private_request = AsyncMock(return_value=expected)

        result = await client.notes_music_browser()

        client.private_request.assert_awaited_once_with(
            "music/notes_audio_browser/",
            data={"product": "music_notes", "_uuid": "uuid-1"},
            with_signature=False,
        )
        assert result == expected

    async def test_create_music_note_uses_create_inbox_tray_item_graphql_payload(self):
        client = Client()
        client.uuid = "uuid-1"
        client._user_id = "123"
        track = {
            "id": "818914077374464",
            "audio_asset_id": "818914077374464",
            "audio_cluster_id": "745666024934797",
            "highlight_start_times_in_ms": [66000],
        }
        graphql_response = {
            "data": {
                "mutation": {
                    "success": True,
                    "inbox_tray_item": {
                        "note_dict": {
                            "note_id": "18072502430410984",
                            "text": "Now playing",
                            "author_id": "123",
                            "audience": 1,
                            "note_style": 1,
                            "is_emoji_only": False,
                            "has_translation": False,
                            "1lcreated_at": 1710000000,
                            "1lexpires_at": 1710086400,
                            "author": {
                                "pk": "123",
                                "username": "example",
                                "full_name": "",
                            },
                        }
                    },
                }
            }
        }
        client.private_graphql_request = AsyncMock(return_value=graphql_response)

        note = await client.create_music_note(
            track=track,
            text="Now playing",
            audience=1,
            start_time=66000,
            duration=30000,
            browse_session_id="browse-1",
            alacorn_session_id="alacorn-1",
        )

        client.private_graphql_request.assert_awaited_once()
        data = client.private_graphql_request.call_args.args[0]
        assert data["client_doc_id"] == "3510400299951610199199089856"
        assert data["fb_api_req_friendly_name"] == "CreateInboxTrayItemRequest"
        variables = json.loads(data["variables"])
        request = variables["request"]
        assert request["inbox_tray_item_type"] == "note"
        assert request["audience"] == 1
        note_params = request["additional_params"]["note_create_params"]
        assert note_params["text"] == "Now playing"
        assert note_params["note_style"] == 1
        music_info = note_params["note_create_info"]["music_note_create_info"]
        assert music_info["audio_asset_id"] == "818914077374464"
        assert music_info["audio_cluster_id"] == "745666024934797"
        assert music_info["start_time"] == 66000
        assert music_info["duration"] == 30000
        assert music_info["browse_session_id"] == "browse-1"
        assert music_info["alacorn_session_id"] == "alacorn-1"
        assert music_info["selected_lyrics"] is None
        assert music_info["is_reshare_eligible"] is False
        assert note.id == "18072502430410984"
        assert note.text == "Now playing"
        assert note.audience == 1
        assert note.note_style == 1

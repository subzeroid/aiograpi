import json
import unittest
from unittest.mock import AsyncMock

from aiograpi import Client


def _build_client():
    client = Client()
    client.settings = {}
    client._user_id = "1"
    client.uuid = "uuid-1"
    client.android_device_id = "android-device"
    client.last_json = {}
    client.with_default_data = lambda data: data
    return client


class DirectMixinRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_direct_thread_update_title_posts_unsigned_title(self):
        client = _build_client()
        client.private_request = AsyncMock(return_value={"status": "ok"})

        result = await client.direct_thread_update_title(123, "Updated title")

        assert result is True
        client.private_request.assert_awaited_once_with(
            "direct_v2/threads/123/update_title/",
            data={"_uuid": "uuid-1", "title": "Updated title"},
            with_signature=False,
        )

    async def test_direct_send_reaction_posts_reaction_payload(self):
        client = _build_client()
        client.private_request = AsyncMock(return_value={"status": "ok"})
        client.generate_mutation_token = lambda: "mutation-token"

        result = await client.direct_send_reaction(
            123,
            456,
            emoji="😂",
            client_context="original-client-context",
            action_source="reaction_sheet",
        )

        assert result is True
        client.private_request.assert_awaited_once_with(
            "direct_v2/threads/broadcast/reaction/",
            data=unittest.mock.ANY,
            with_signature=False,
        )
        data = client.private_request.call_args.kwargs["data"]
        assert json.loads(data["thread_ids"]) == ["123"]
        assert data["_uuid"] == "uuid-1"
        assert data["device_id"] == "android-device"
        assert data["client_context"] == "mutation-token"
        assert data["offline_threading_id"] == "mutation-token"
        assert data["mutation_token"] == "mutation-token"
        assert data["action"] == "send_item"
        assert data["item_type"] == "reaction"
        assert data["reaction_type"] == "like"
        assert data["reaction_status"] == "created"
        assert data["node_type"] == "item"
        assert data["item_id"] == "456"
        assert data["emoji"] == "😂"
        assert data["reaction_action_source"] == "reaction_sheet"
        assert data["original_message_client_context"] == "original-client-context"

    async def test_direct_message_unlike_posts_deleted_reaction(self):
        client = _build_client()
        client.private_request = AsyncMock(return_value={"status": "ok"})
        client.generate_mutation_token = lambda: "mutation-token"

        result = await client.direct_message_unlike(123, 456, client_context="original-client-context")

        assert result is True
        data = client.private_request.call_args.kwargs["data"]
        assert data["reaction_status"] == "deleted"
        assert data["emoji"] == "❤"
        assert data["reaction_type"] == "like"
        assert data["original_message_client_context"] == "original-client-context"

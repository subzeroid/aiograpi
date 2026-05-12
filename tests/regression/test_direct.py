import json
import unittest
from unittest.mock import AsyncMock

from aiograpi import Client
from aiograpi.exceptions import DirectMessageNotFound
from aiograpi.types import DirectMessage, DirectThread


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

    async def test_direct_message_returns_matching_message_by_id(self):
        client = _build_client()
        first = DirectMessage(id="111", user_id="1", timestamp=1)
        expected = DirectMessage(id="222", user_id="1", timestamp=2)
        client.direct_messages = AsyncMock(return_value=[first, expected])

        result = await client.direct_message(123, "222", amount=50)

        assert result is expected
        client.direct_messages.assert_awaited_once_with(123, 50)

    async def test_direct_message_raises_when_message_is_missing(self):
        client = _build_client()
        message = DirectMessage(id="111", user_id="1", timestamp=1)
        client.direct_messages = AsyncMock(return_value=[message])

        with self.assertRaises(DirectMessageNotFound) as ctx:
            await client.direct_message(123, 222, amount=1)

        assert "222" in str(ctx.exception)

    async def test_direct_message_unsend_delegates_to_delete_endpoint(self):
        client = _build_client()
        client.direct_message_delete = AsyncMock(return_value=True)

        result = await client.direct_message_unsend(123, 456)

        assert result is True
        client.direct_message_delete.assert_awaited_once_with(123, 456)

    async def test_direct_requests_uses_pending_inbox(self):
        client = _build_client()
        expected = [unittest.mock.Mock(spec=DirectThread)]
        client.direct_pending_inbox = AsyncMock(return_value=expected)

        result = await client.direct_requests(amount=7)

        assert result is expected
        client.direct_pending_inbox.assert_awaited_once_with(7)

    async def test_direct_request_approve_delegates_to_pending_approve(self):
        client = _build_client()
        client.direct_pending_approve = AsyncMock(return_value=True)

        result = await client.direct_request_approve(123)

        assert result is True
        client.direct_pending_approve.assert_awaited_once_with(123)

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

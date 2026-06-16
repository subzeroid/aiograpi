import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from unittest.mock import AsyncMock, Mock

from aiograpi import Client
from aiograpi.exceptions import DirectMessageNotFound, DirectThreadNotFound
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


def _direct_payload():
    return {
        "payload": {
            "item_id": "1",
            "timestamp": 1761953663000000,
            "user_id": "1",
        },
        "status": "ok",
    }


def _temp_file(suffix, data):
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.write(data)
    tmp.close()
    return Path(tmp.name)


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

    async def test_direct_thread_add_users_posts_unsigned_user_ids(self):
        client = _build_client()
        client.private_request = AsyncMock(return_value={"status": "ok"})

        result = await client.direct_thread_add_users(123, [42, "43"])

        assert result is True
        client.private_request.assert_awaited_once_with(
            "direct_v2/threads/123/add_user/",
            data={"_uuid": "uuid-1", "user_ids": '["42","43"]'},
            with_signature=False,
        )

    async def test_direct_thread_create_posts_group_payload(self):
        client = _build_client()
        client.generate_mutation_token = lambda: "mutation-token"
        client.private_request = AsyncMock(return_value={"thread_id": "3402823668417103"})

        result = await client.direct_thread_create([42, "43"], title="Group title")

        assert result == "3402823668417103"
        client.private_request.assert_awaited_once_with(
            "direct_v2/create_group_thread/",
            data={
                "_uuid": "uuid-1",
                "_uid": "1",
                "client_context": "mutation-token",
                "is_partnership_folder": "false",
                "recipient_users": "[42,43]",
                "thread_title": "Group title",
            },
        )

    async def test_direct_thread_create_accepts_nested_thread_id_response(self):
        client = _build_client()
        client.generate_mutation_token = lambda: "mutation-token"
        client.private_request = AsyncMock(return_value={"thread": {"thread_id": "3402823668417104"}})

        result = await client.direct_thread_create([42, 43])

        assert result == "3402823668417104"

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

    async def test_direct_threads_chunk_sends_current_inbox_query_params(self):
        client = _build_client()
        client.private_request = AsyncMock(return_value={"inbox": {"threads": []}})

        threads, cursor = await client.direct_threads_chunk()

        assert threads == []
        assert cursor is None
        params = client.private_request.call_args.kwargs["params"]
        assert params["eb_device_id"] == "0"
        self.assertRegex(params["igd_request_log_tracking_id"], r"^[0-9a-f-]{36}$")
        assert params["fetch_reason"] == "initial_snapshot"
        assert params["include_old_mrs"] == "false"
        assert params["no_pending_badge"] == "true"
        assert params["push_disabled"] == "true"

    async def test_direct_threads_chunk_uses_configured_push_state(self):
        client = _build_client()
        client.set_push_disabled(False)
        client.private_request = AsyncMock(return_value={"inbox": {"threads": []}})

        await client.direct_threads_chunk()

        params = client.private_request.call_args.kwargs["params"]
        assert params["push_disabled"] == "false"
        assert client.get_settings()["push_disabled"] is False

    async def test_direct_threads_chunk_rejects_unsupported_selected_filter(self):
        client = _build_client()

        with self.assertRaises(ValueError) as ctx:
            await client.direct_threads_chunk(selected_filter="archived")

        assert "selected_filter" in str(ctx.exception)
        assert "flagged" in str(ctx.exception)
        assert "unread" in str(ctx.exception)

    async def test_direct_search_sends_current_ranked_recipient_limits(self):
        client = _build_client()
        client.private_request = AsyncMock(return_value={"ranked_recipients": []})

        result = await client.direct_search("alice")

        assert result == []
        params = client.private_request.call_args.kwargs["params"]
        assert params["max_ai_bot_results"] == "0"
        assert params["max_ibc_results"] == "20"

    async def test_direct_message_search_hides_locked_threads(self):
        client = _build_client()
        client.private_request = AsyncMock(return_value={"status": "ok", "message_search_results": {}})

        result = await client.direct_message_search("alice")

        assert result == []
        params = client.private_request.call_args.kwargs["params"]
        assert params["hide_locked_threads"] == '{"message_content":"false"}'

    async def test_direct_media_sends_current_thread_media_query_params(self):
        client = _build_client()
        client.private_request = AsyncMock(return_value={"items": [], "more_available": False})

        result = await client.direct_media(123)

        assert result == []
        params = client.private_request.call_args.kwargs["params"]
        assert params["eb_device_id"] == "0"
        self.assertRegex(params["igd_request_log_tracking_id"], r"^[0-9a-f-]{36}$")
        assert params["media_type"] == "media_shares"

    async def test_direct_pending_requests_preview_uses_current_preview_endpoint(self):
        client = _build_client()
        response = {
            "pending_requests_total": 1,
            "unread_pending_requests": 1,
            "status": "ok",
        }
        client.private_request = AsyncMock(return_value=response)

        result = await client.direct_pending_requests_preview()

        assert result == response
        client.private_request.assert_awaited_once_with(
            "direct_v2/async_get_pending_requests_preview/",
            params={"pending_inbox_filters": "[]"},
        )

    async def test_direct_has_interop_upgraded_returns_boolean_state(self):
        client = _build_client()
        client.private_request = AsyncMock(return_value={"has_interop_upgraded": False, "status": "ok"})

        result = await client.direct_has_interop_upgraded()

        assert result is False
        client.private_request.assert_awaited_once_with("direct_v2/has_interop_upgraded/")

    async def test_direct_search_gen_ai_bots_returns_user_results(self):
        client = _build_client()
        client.private_request = AsyncMock(
            return_value={
                "user_search_results": [
                    {
                        "pk": 64528677628,
                        "username": "meta_ai",
                        "full_name": "Meta AI",
                        "profile_pic_url": "https://example.com/meta.jpg",
                    }
                ],
                "status": "ok",
            }
        )

        result = await client.direct_search_gen_ai_bots(amount=5)

        assert len(result) == 1
        assert result[0].username == "meta_ai"
        client.private_request.assert_awaited_once_with(
            "direct_v2/search_gen_ai_bots/",
            params={"num_ai_bots": "5"},
        )

    async def test_direct_channels_uses_authenticated_user_by_default(self):
        client = _build_client()
        client.private_request = AsyncMock(return_value={"all_channels_list": [{"thread_id": "123"}], "status": "ok"})

        result = await client.direct_channels()

        assert result == [{"thread_id": "123"}]
        client.private_request.assert_awaited_once_with(
            "direct_v2/get_all_channels/",
            params={"user_id": "1", "thread_subtypes": "[29]"},
        )

    async def test_direct_set_e2ee_eligibility_posts_unsigned_value(self):
        client = _build_client()
        client.private_request = AsyncMock(return_value={"status": "ok"})

        result = await client.direct_set_e2ee_eligibility(4)

        assert result is True
        client.private_request.assert_awaited_once_with(
            "direct_v2/set_e2ee_eligibility/",
            data={"_uuid": "uuid-1", "e2ee_eligibility": "4"},
            with_signature=False,
        )

    async def test_direct_request_approve_delegates_to_pending_approve(self):
        client = _build_client()
        client.direct_pending_approve = AsyncMock(return_value=True)

        result = await client.direct_request_approve(123)

        assert result is True
        client.direct_pending_approve.assert_awaited_once_with(123)

    async def test_direct_send_accepts_scalar_user_id(self):
        client = _build_client()
        client.private_request = AsyncMock(return_value=_direct_payload())
        client.generate_mutation_token = lambda: "mutation-token"

        await client.direct_send("hello", user_ids="42")

        data = client.private_request.call_args.kwargs["data"]
        assert json.loads(data["recipient_users"]) == [[42]]

    async def test_direct_send_accepts_scalar_thread_id(self):
        client = _build_client()
        client.private_request = AsyncMock(return_value=_direct_payload())
        client.generate_mutation_token = lambda: "mutation-token"

        await client.direct_send("hello", thread_ids="340282366841710300949128149448121770626")

        data = client.private_request.call_args.kwargs["data"]
        assert json.loads(data["thread_ids"]) == [340282366841710300949128149448121770626]

    async def test_direct_media_share_accepts_scalar_user_id(self):
        client = _build_client()
        client.private_request = AsyncMock(return_value=_direct_payload())
        client.generate_mutation_token = lambda: "mutation-token"
        client.media_id = AsyncMock(return_value="123_1")

        await client.direct_media_share("123", user_ids=42)

        data = client.private_request.call_args.kwargs["data"]
        assert json.loads(data["recipient_users"]) == [[42]]

    async def test_direct_media_share_posts_thread_ids(self):
        client = _build_client()
        client.private_request = AsyncMock(return_value=_direct_payload())
        client.generate_mutation_token = lambda: "mutation-token"
        client.media_id = AsyncMock(return_value="123_1")

        await client.direct_media_share("123", thread_ids=[340282366841710300949128149448121770626])

        client.private_request.assert_awaited_once_with(
            "direct_v2/threads/broadcast/media_share/",
            params={"media_type": "photo"},
            data=mock.ANY,
            with_signature=False,
        )
        data = client.private_request.call_args.kwargs["data"]
        assert "recipient_users" not in data
        assert json.loads(data["thread_ids"]) == [340282366841710300949128149448121770626]
        assert data["client_context"] == "mutation-token"
        assert data["media_id"] == "123_1"

    async def test_direct_media_share_rejects_user_ids_and_thread_ids_together(self):
        client = _build_client()
        client.generate_mutation_token = lambda: "mutation-token"
        client.media_id = AsyncMock(return_value="123_1")

        with self.assertRaises(AssertionError):
            await client.direct_media_share("123", user_ids=[42], thread_ids=[123])

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

    async def test_direct_send_video_uploads_and_broadcasts_raven_attachment_for_thread_ids(self):
        client = _build_client()
        path = _temp_file(".mp4", b"video-bytes")
        expected = Mock(spec=DirectMessage)

        try:
            with (
                mock.patch("aiograpi.mixins.direct.time.time", return_value=1234.567),
                mock.patch("aiograpi.mixins.direct.secrets.token_hex", return_value="a" * 32),
                mock.patch("aiograpi.mixins.direct.random.randint", return_value=111111111111),
                mock.patch.object(client, "_direct_video_metadata", return_value=(720, 1280, 1.5)),
                mock.patch.object(client, "_video_rupload", return_value=987654321) as rupload,
                mock.patch.object(client, "generate_mutation_token", return_value="mutation-token"),
                mock.patch("aiograpi.mixins.direct.extract_direct_message", return_value=expected),
            ):
                client.private_request = AsyncMock(return_value=_direct_payload())
                result = await client.direct_send_video(path, thread_ids=[123])
        finally:
            path.unlink(missing_ok=True)

        assert result is expected
        rupload.assert_called_once_with(
            b"video-bytes",
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-0-11-1234567-1234567",
            "111111111111_AAAAAAAAAAAA_Mixed_0",
        )
        client.private_request.assert_awaited_once_with(
            "direct_v2/threads/broadcast/raven_attachment/?video=1",
            data=mock.ANY,
            with_signature=True,
        )
        data = client.private_request.call_args.kwargs["data"]
        assert json.loads(data["thread_ids"]) == ["123"]
        assert data["recipient_users"] == "[]"
        assert data["attachment_fbid"] == "987654321"
        assert data["video_result"] == "987654321"
        assert data["client_context"] == "mutation-token"
        assert data["mutation_token"] == "mutation-token"

    async def test_direct_send_video_resolves_existing_thread_from_last_json(self):
        client = _build_client()
        path = _temp_file(".mp4", b"video-bytes")
        thread_id = "340282366841710300949128149448121770626"

        async def thread_lookup(user_ids):
            client.last_json = {"thread": {"thread_v2_id": thread_id}}
            return {"users": []}

        try:
            with (
                mock.patch.object(client, "direct_thread_by_participants", side_effect=thread_lookup) as lookup,
                mock.patch.object(client, "_direct_video_metadata", return_value=(720, 1280, 1.5)),
                mock.patch.object(client, "_video_rupload", return_value=123),
                mock.patch.object(client, "generate_mutation_token", return_value="mutation-token"),
            ):
                client.private_request = AsyncMock(return_value=_direct_payload())
                await client.direct_send_video(path, user_ids=[42])
        finally:
            path.unlink(missing_ok=True)

        lookup.assert_awaited_once_with([42])
        data = client.private_request.call_args.kwargs["data"]
        assert json.loads(data["thread_ids"]) == [thread_id]

    async def test_direct_send_voice_uploads_and_broadcasts_for_thread_ids(self):
        client = _build_client()
        path = _temp_file(".m4a", b"voice-bytes")
        expected = Mock(spec=DirectMessage)

        try:
            with (
                mock.patch("aiograpi.mixins.direct.time.time", return_value=1234.567),
                mock.patch("aiograpi.mixins.direct.random.randint", return_value=-99),
                mock.patch.object(client, "_voice_rupload", return_value=987654321) as rupload,
                mock.patch.object(client, "generate_mutation_token", return_value="mutation-token"),
                mock.patch("aiograpi.mixins.direct.extract_direct_message", return_value=expected),
            ):
                client.private_request = AsyncMock(return_value=_direct_payload())
                result = await client.direct_send_voice(path, thread_ids=[123], waveform=[0.1, 0.2])
        finally:
            path.unlink(missing_ok=True)

        assert result is expected
        rupload.assert_called_once_with(b"voice-bytes", "1234567", -99)
        client.private_request.assert_awaited_once_with(
            "direct_v2/threads/broadcast/voice_attachment/",
            data=mock.ANY,
            with_signature=False,
        )
        data = client.private_request.call_args.kwargs["data"]
        assert json.loads(data["thread_ids"]) == [123]
        assert data["attachment_fbid"] == "987654321"
        assert data["client_context"] == "mutation-token"
        assert data["mutation_token"] == "mutation-token"
        assert data["offline_threading_id"] == "mutation-token"
        assert data["upload_id"] == "1234567"
        assert json.loads(data["waveform"]) == [0.1, 0.2]
        assert data["waveform_sampling_frequency_hz"] == "10"

    async def test_direct_send_voice_resolves_existing_thread_from_last_json(self):
        client = _build_client()
        path = _temp_file(".m4a", b"voice-bytes")
        thread_id = "340282366841710300949128149448121770626"

        async def thread_lookup(user_ids):
            client.last_json = {"thread": {"thread_v2_id": thread_id}}
            return {"users": []}

        try:
            with (
                mock.patch.object(client, "direct_thread_by_participants", side_effect=thread_lookup) as lookup,
                mock.patch.object(client, "_voice_rupload", return_value=123),
                mock.patch.object(client, "generate_mutation_token", return_value="mutation-token"),
            ):
                client.private_request = AsyncMock(return_value=_direct_payload())
                await client.direct_send_voice(path, user_ids=[42], waveform=[0.3])
        finally:
            path.unlink(missing_ok=True)

        lookup.assert_awaited_once_with([42])
        data = client.private_request.call_args.kwargs["data"]
        assert json.loads(data["thread_ids"]) == [int(thread_id)]
        assert data["attachment_fbid"] == "123"
        assert json.loads(data["waveform"]) == [0.3]

    async def test_direct_send_voice_raises_when_existing_thread_is_missing(self):
        client = _build_client()
        path = _temp_file(".m4a", b"voice-bytes")

        try:
            client.direct_thread_by_participants = AsyncMock(return_value={})
            client._voice_rupload = Mock()
            with self.assertRaises(DirectThreadNotFound):
                await client.direct_send_voice(path, user_ids=[42])
        finally:
            path.unlink(missing_ok=True)

        client.direct_thread_by_participants.assert_awaited_once_with([42])
        client._voice_rupload.assert_not_called()

    async def test_messenger_rupload_headers_merges_common_optional_and_extra_headers(self):
        client = _build_client()
        client._user_id = "123"
        client.authorization_data = {"ds_user_id": "123", "sessionid": "raw-session"}
        client.private.headers["Authorization"] = "Bearer token"
        client.private.headers["IG-U-RUR"] = "rur-token"
        client.private.headers["X-MID"] = "mid-token"

        headers = client._messenger_rupload_headers({"audio_type": "FILE_ATTACHMENT"})

        assert headers["authorization"] == "Bearer token"
        assert headers["ig-intended-user-id"] == "123"
        assert headers["ig-u-ds-user-id"] == "123"
        assert headers["accept-encoding"] == "gzip"
        assert headers["accept-language"] == "en-US"
        assert headers["priority"] == "u=6, i"
        assert headers["user-agent"] == client.user_agent
        assert headers["audio_type"] == "FILE_ATTACHMENT"
        assert headers["ig-u-rur"] == "rur-token"
        assert headers["x-mid"] == "mid-token"

    async def test_video_rupload_delegates_base_headers_to_helper(self):
        client = _build_client()

        class FakeResponse:
            status_code = 200
            text = "{}"

            def __init__(self, payload):
                self.payload = payload

            def json(self):
                return self.payload

        with (
            mock.patch.object(
                client, "_messenger_rupload_headers", return_value={"authorization": "Bearer token"}
            ) as headers,
            mock.patch(
                "aiograpi.mixins.direct.httpx_ext.request",
                new=AsyncMock(side_effect=[FakeResponse({"offset": 0}), FakeResponse({"media_id": 987654321})]),
            ),
        ):
            media_id = await client._video_rupload(b"video-bytes", "entity-name", "waterfall-id")

        assert media_id == 987654321
        headers.assert_called_once_with(
            {
                "video_type": "FILE_ATTACHMENT",
                "segment-start-offset": "0",
                "segment-type": "3",
                "ephemeral_media_view_mode": "2",
                "ig_raven_metadata": "{}",
                "x_fb_video_waterfall_id": "waterfall-id",
            }
        )

    async def test_voice_rupload_delegates_base_headers_to_helper(self):
        client = _build_client()

        class FakeResponse:
            status_code = 200
            text = "{}"

            def __init__(self, payload):
                self.payload = payload

            def json(self):
                return self.payload

        with (
            mock.patch.object(
                client, "_messenger_rupload_headers", return_value={"authorization": "Bearer token"}
            ) as headers,
            mock.patch(
                "aiograpi.mixins.direct.httpx_ext.request",
                new=AsyncMock(side_effect=[FakeResponse({"offset": 0}), FakeResponse({"media_id": 987654321})]),
            ),
        ):
            media_id = await client._voice_rupload(b"voice-bytes", "1234567", -99)

        assert media_id == 987654321
        headers.assert_called_once_with({"audio_type": "FILE_ATTACHMENT"})

import json
import unittest
import zlib
from unittest import mock
from unittest.mock import AsyncMock

from aiograpi import Client
from aiograpi.realtime import RealtimeClient
from aiograpi.realtime.mqttot import (
    MQTToTConnection,
    MQTToTTopics,
    SocketMQTToTTransport,
    decode_packet,
    read_thrift_object,
    write_connect_packet,
    write_pingreq_packet,
    write_publish_packet,
)


def _build_logged_in_client():
    client = Client()
    client.authorization_data = {"ds_user_id": "12345", "sessionid": "12345:session"}
    client.phone_id = "phone-id-12345678901234567890"
    client.uuid = "uuid-1"
    client.user_agent = "Instagram 428.0.0.47.67 Android"
    client.app_version = "428.0.0.47.67"
    client.capabilities = "3brTvw=="
    client.locale = "en_US"
    return client


class MQTToTPacketRegressionTestCase(unittest.TestCase):
    def test_mqttot_connect_packet_uses_custom_protocol_and_zipped_thrift_payload(self):
        connection = MQTToTConnection(
            client_identifier="phone-id-123456789",
            client_info={
                "userId": 12345,
                "userAgent": "Instagram 428",
                "clientCapabilities": 183,
                "endpointCapabilities": 0,
                "publishFormat": 1,
                "deviceId": "phone-id-12345678901234567890",
                "isInitiallyForeground": True,
                "subscribeTopics": [88, 135, 149, 150, 133, 146],
                "clientType": "cookie_auth",
                "appId": 567067343352427,
                "clientStack": 3,
            },
            password="sessionid=12345:session",
            app_specific_info={
                "app_version": "428.0.0.47.67",
                "platform": "android",
                "ig_mqtt_route": "django",
            },
        )

        packet = write_connect_packet(connection, keep_alive=20)

        decoded = decode_packet(packet)
        self.assertEqual(packet[0], 0x10)
        self.assertEqual(decoded.packet_type, "connect")
        self.assertEqual(decoded.protocol_name, "MQTToT")
        self.assertEqual(decoded.protocol_level, 3)
        self.assertEqual(decoded.connect_flags, 0xC2)
        self.assertEqual(decoded.keep_alive, 20)

        thrift_payload = zlib.decompress(decoded.payload)
        thrift = read_thrift_object(thrift_payload, MQTToTConnection.thrift_descriptors())
        self.assertEqual(thrift["clientIdentifier"], "phone-id-123456789")
        self.assertEqual(thrift["password"], "sessionid=12345:session")
        self.assertEqual(thrift["clientInfo"]["clientType"], "cookie_auth")
        self.assertEqual(thrift["clientInfo"]["subscribeTopics"], [88, 135, 149, 150, 133, 146])
        self.assertEqual(thrift["appSpecificInfo"]["ig_mqtt_route"], "django")

    def test_publish_packet_round_trips_topic_and_zipped_payload(self):
        payload = zlib.compress(json.dumps({"sub": ["1/graphqlsubscriptions/test/{}"]}).encode())

        packet = write_publish_packet(MQTToTTopics.REALTIME_SUB, payload, qos=1, packet_id=7)

        decoded = decode_packet(packet)
        self.assertEqual(decoded.packet_type, "publish")
        self.assertEqual(decoded.topic, MQTToTTopics.REALTIME_SUB)
        self.assertEqual(decoded.qos, 1)
        self.assertEqual(decoded.packet_id, 7)
        self.assertEqual(json.loads(zlib.decompress(decoded.payload)), {"sub": ["1/graphqlsubscriptions/test/{}"]})

    def test_ping_response_packet_decodes_as_pingresp(self):
        decoded = decode_packet(b"\xd0\x00")

        self.assertEqual(decoded.packet_type, "pingresp")
        self.assertEqual(decoded.payload, b"")


class RealtimeClientRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    def test_realtime_client_builds_cookie_auth_connection_from_instagram_session(self):
        client = _build_logged_in_client()
        realtime = RealtimeClient(client)

        connection = realtime.build_connection()

        self.assertEqual(connection.client_identifier, "phone-id-12345678901")
        self.assertEqual(connection.password, "sessionid=12345:session")
        self.assertEqual(connection.client_info["userId"], 12345)
        self.assertEqual(connection.client_info["clientType"], "cookie_auth")
        self.assertEqual(connection.client_info["appId"], 567067343352427)
        self.assertEqual(connection.client_info["subscribeTopics"], [88, 135, 149, 150, 133, 146])
        self.assertEqual(connection.app_specific_info["app_version"], "428.0.0.47.67")
        self.assertEqual(connection.app_specific_info["platform"], "android")

    def test_realtime_client_default_transport_uses_client_proxy(self):
        client = _build_logged_in_client()
        client.proxy = "socks5://127.0.0.1:8888"

        realtime = RealtimeClient(client)

        self.assertIsInstance(realtime.transport, SocketMQTToTTransport)
        self.assertEqual(realtime.transport.proxy, "socks5://127.0.0.1:8888")

    async def test_client_exposes_stateful_realtime_helpers(self):
        client = _build_logged_in_client()
        transport = mock.Mock()
        await client.realtime_connect(transport=transport)

        self.assertIsInstance(client.realtime, RealtimeClient)
        transport.connect.assert_called_once()

        await client.realtime_disconnect()
        transport.disconnect.assert_called_once()

    async def test_realtime_client_ping_sends_keepalive_and_reads_pingresp(self):
        client = _build_logged_in_client()
        transport = mock.Mock()
        transport.recv_packet.return_value = b"\xd0\x00"
        realtime = RealtimeClient(client, transport=transport)
        realtime.connected = True

        self.assertTrue(await realtime.ping())

        transport.send.assert_called_once_with(write_pingreq_packet())
        transport.recv_packet.assert_called_once()

    async def test_client_exposes_stateful_realtime_ping_helper(self):
        client = _build_logged_in_client()
        transport = mock.Mock()
        transport.recv_packet.return_value = b"\xd0\x00"
        await client.realtime_connect(transport=transport)

        self.assertTrue(await client.realtime_ping())

    async def test_realtime_client_iris_subscribe_publishes_inbox_sync_state(self):
        client = _build_logged_in_client()
        realtime = RealtimeClient(client, transport=mock.Mock())

        with mock.patch.object(realtime, "publish_json", new=AsyncMock()) as publish_json:
            await realtime.iris_subscribe(seq_id=123, snapshot_at_ms=456)

        publish_json.assert_awaited_once_with(
            MQTToTTopics.IRIS_SUB,
            {
                "seq_id": 123,
                "snapshot_at_ms": 456,
                "snapshot_app_version": "428.0.0.47.67",
            },
        )

    async def test_realtime_client_direct_subscribe_fetches_inbox_and_subscribes_to_iris(self):
        client = _build_logged_in_client()
        client.last_json = {"seq_id": 123, "snapshot_at_ms": 456}
        client.direct_threads = AsyncMock(return_value=[])
        realtime = RealtimeClient(client, transport=mock.Mock())

        with mock.patch.object(realtime, "iris_subscribe", new=AsyncMock()) as iris_subscribe:
            state = await realtime.direct_subscribe()

        client.direct_threads.assert_awaited_once_with(amount=1)
        iris_subscribe.assert_awaited_once_with(seq_id=123, snapshot_at_ms=456)
        self.assertEqual(state, {"seq_id": 123, "snapshot_at_ms": 456})

    async def test_realtime_client_direct_send_text_publishes_mqtt_direct_command(self):
        client = _build_logged_in_client()
        transport = mock.Mock()
        realtime = RealtimeClient(client, transport=transport)

        state = await realtime.direct_send_text("thread-1", "hello", client_context="ctx-1")

        packet = decode_packet(transport.send.call_args.args[0])
        payload = json.loads(zlib.decompress(packet.payload))
        self.assertEqual(packet.topic, MQTToTTopics.SEND_MESSAGE)
        self.assertEqual(
            payload,
            {
                "action": "send_item",
                "thread_id": "thread-1",
                "client_context": "ctx-1",
                "item_type": "text",
                "text": "hello",
            },
        )
        self.assertEqual(state, {"thread_id": "thread-1", "client_context": "ctx-1", "action": "send_item"})

    async def test_realtime_client_direct_send_reaction_publishes_mqtt_direct_command(self):
        client = _build_logged_in_client()
        transport = mock.Mock()
        realtime = RealtimeClient(client, transport=transport)

        await realtime.direct_send_reaction("thread-1", "item-1", emoji="*", client_context="ctx-1")

        packet = decode_packet(transport.send.call_args.args[0])
        payload = json.loads(zlib.decompress(packet.payload))
        self.assertEqual(packet.topic, MQTToTTopics.SEND_MESSAGE)
        self.assertEqual(
            payload,
            {
                "action": "send_item",
                "thread_id": "thread-1",
                "client_context": "ctx-1",
                "item_type": "reaction",
                "item_id": "item-1",
                "node_type": "item",
                "reaction_type": "like",
                "reaction_status": "created",
                "target_item_type": "text",
                "emoji": "*",
            },
        )

    async def test_realtime_client_direct_indicate_activity_publishes_typing_command(self):
        client = _build_logged_in_client()
        transport = mock.Mock()
        realtime = RealtimeClient(client, transport=transport)

        await realtime.direct_indicate_activity("thread-1", is_active=False, client_context="ctx-1")

        packet = decode_packet(transport.send.call_args.args[0])
        payload = json.loads(zlib.decompress(packet.payload))
        self.assertEqual(packet.topic, MQTToTTopics.SEND_MESSAGE)
        self.assertEqual(
            payload,
            {
                "action": "indicate_activity",
                "thread_id": "thread-1",
                "client_context": "ctx-1",
                "activity_status": "0",
            },
        )

    async def test_realtime_client_direct_mark_seen_publishes_seen_command(self):
        client = _build_logged_in_client()
        transport = mock.Mock()
        realtime = RealtimeClient(client, transport=transport)

        await realtime.direct_mark_seen("thread-1", "item-1")

        packet = decode_packet(transport.send.call_args.args[0])
        payload = json.loads(zlib.decompress(packet.payload))
        self.assertEqual(packet.topic, MQTToTTopics.SEND_MESSAGE)
        self.assertEqual(
            payload,
            {
                "action": "mark_seen",
                "thread_id": "thread-1",
                "item_id": "item-1",
            },
        )

    def test_message_sync_delta_new_message_without_patch_data_is_still_emitted(self):
        client = _build_logged_in_client()
        realtime = RealtimeClient(client, transport=mock.Mock())
        messages = []
        realtime.on("message", messages.append)

        realtime.dispatch_message_sync(
            [
                {
                    "event": "patch",
                    "data": [],
                    "message_type": 1,
                    "seq_id": 22,
                    "mutation_token": "token-1",
                    "client_context": "ctx-1",
                    "realtime": True,
                    "delta_type": "deltaNewMessage",
                }
            ]
        )

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["message"]["delta_type"], "deltaNewMessage")
        self.assertEqual(messages[0]["message"]["client_context"], "ctx-1")

    async def test_realtime_client_send_foreground_state_publishes_thrift_state(self):
        client = _build_logged_in_client()
        transport = mock.Mock()
        realtime = RealtimeClient(client, transport=transport)

        await realtime.send_foreground_state(keep_alive_timeout=60, subscribe_topics=["146"], request_id=99)

        packet = decode_packet(transport.send.call_args.args[0])
        payload = zlib.decompress(packet.payload)
        self.assertEqual(packet.topic, MQTToTTopics.FOREGROUND_STATE)
        self.assertEqual(payload[0], 0)
        state = read_thrift_object(payload[1:], realtime.foreground_state_descriptors())
        self.assertEqual(state["keepAliveTimeout"], 60)
        self.assertEqual(state["subscribeTopics"], ["146"])
        self.assertEqual(state["requestId"], 99)

    def test_realtime_client_dispatches_send_message_response_event(self):
        client = _build_logged_in_client()
        realtime = RealtimeClient(client, transport=mock.Mock())
        handler = mock.Mock()
        realtime.on("send_response", handler)
        payload = {"status": "ok", "client_context": "ctx-1"}

        realtime.dispatch_packet(MQTToTTopics.SEND_MESSAGE_RESPONSE, zlib.compress(json.dumps(payload).encode()))

        handler.assert_called_once_with(payload)

    def test_message_sync_dispatch_emits_direct_message_wrapper(self):
        client = _build_logged_in_client()
        realtime = RealtimeClient(client, transport=mock.Mock())
        handler = mock.Mock()
        realtime.on("message", handler)
        payload = [
            {
                "event": "patch",
                "seq_id": 123,
                "data": [
                    {
                        "op": "add",
                        "path": "/direct_v2/threads/987/items/item-1",
                        "value": json.dumps({"item_id": "item-1", "text": "hello", "user_id": "55"}),
                    }
                ],
            }
        ]

        realtime.dispatch_packet(MQTToTTopics.MESSAGE_SYNC, zlib.compress(json.dumps(payload).encode()))

        handler.assert_called_once()
        message = handler.call_args.args[0]["message"]
        self.assertEqual(message["thread_id"], "987")
        self.assertEqual(message["path"], "/direct_v2/threads/987/items/item-1")
        self.assertEqual(message["op"], "add")
        self.assertEqual(message["text"], "hello")
        self.assertEqual(message["user_id"], "55")

    def test_realtime_sub_dispatch_emits_direct_typing_seen_and_presence_events(self):
        client = _build_logged_in_client()
        realtime = RealtimeClient(client, transport=mock.Mock())
        direct_handler = mock.Mock()
        typing_handler = mock.Mock()
        seen_handler = mock.Mock()
        presence_handler = mock.Mock()
        realtime.on("direct", direct_handler)
        realtime.on("typing", typing_handler)
        realtime.on("seen", seen_handler)
        realtime.on("presence", presence_handler)
        direct_payload = {
            "message": json.dumps(
                {
                    "data": [
                        {
                            "path": "/direct_v2/threads/987/activity_indicator_id",
                            "value": json.dumps({"activity_status": "1", "sender_id": "55"}),
                        },
                        {
                            "path": "/direct_v2/threads/987/seen_state",
                            "value": json.dumps({"item_id": "item-1", "user_id": "55"}),
                        },
                        {
                            "path": "/direct_v2/threads/987/presence",
                            "value": json.dumps({"is_active": True, "user_id": "55"}),
                        },
                    ]
                }
            )
        }

        realtime.dispatch_packet(MQTToTTopics.REALTIME_SUB, zlib.compress(json.dumps(direct_payload).encode()))

        self.assertEqual(direct_handler.call_count, 3)
        typing_handler.assert_called_once()
        seen_handler.assert_called_once()
        presence_handler.assert_called_once()
        self.assertEqual(typing_handler.call_args.args[0]["thread_id"], "987")
        self.assertEqual(seen_handler.call_args.args[0]["thread_id"], "987")
        self.assertTrue(presence_handler.call_args.args[0]["value"]["is_active"])

    async def test_realtime_connect_preserves_handlers_registered_before_connect(self):
        client = _build_logged_in_client()
        transport = mock.Mock()
        handler = mock.Mock()

        client.realtime_on("receive", handler)
        await client.realtime_connect(transport=transport)
        client.realtime.emit("receive", {"topic": "146", "payload": {"ok": True}})

        handler.assert_called_once_with({"topic": "146", "payload": {"ok": True}})

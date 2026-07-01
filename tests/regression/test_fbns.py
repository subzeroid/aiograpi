import json
import unittest
import zlib
from unittest import mock
from unittest.mock import AsyncMock

from aiograpi import Client
from aiograpi.realtime import FbnsClient, FbnsDeviceAuth
from aiograpi.realtime.fbns import FBNS_HOST, FBNS_SUBSCRIBE_TOPICS, FBNSTopics
from aiograpi.realtime.mqttot import MQTToTConnection, decode_packet, read_thrift_object, write_publish_packet


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


def _packet(packet_type: int, body: bytes) -> bytes:
    remaining = bytearray()
    value = len(body)
    while True:
        byte = value % 128
        value //= 128
        if value:
            byte |= 0x80
        remaining.append(byte)
        if not value:
            break
    return bytes([packet_type << 4]) + bytes(remaining) + body


def _connack(payload: dict) -> bytes:
    return _packet(2, b"\x00\x00" + json.dumps(payload, separators=(",", ":")).encode())


def _publish(topic: str, payload: dict, packet_id: int = 7) -> bytes:
    return write_publish_packet(topic, json.dumps(payload, separators=(",", ":")).encode(), packet_id=packet_id)


def _suback(packet_id: int = 2) -> bytes:
    return _packet(9, packet_id.to_bytes(2, "big") + b"\x01")


class FbnsClientRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    def test_fbns_device_auth_reads_connack_payload_and_updates_settings(self):
        client = _build_logged_in_client()
        auth = FbnsDeviceAuth.from_client(client)

        auth.read(
            {
                "ck": 123456,
                "cs": "connection-secret",
                "di": "fbns-device-id",
                "ds": "fbns-device-secret",
                "sr": "odn",
                "rc": "ATN",
            }
        )
        auth.save(client)

        self.assertEqual(auth.user_id, 123456)
        self.assertEqual(auth.password, "connection-secret")
        self.assertEqual(auth.device_id, "fbns-device-id")
        self.assertEqual(auth.device_secret, "fbns-device-secret")
        self.assertEqual(client.settings["fbns_auth"]["device_id"], "fbns-device-id")
        self.assertEqual(client.settings["fbns_auth"]["user_id"], 123456)

    def test_fbns_device_auth_reads_length_prefixed_connack_payload(self):
        auth = FbnsDeviceAuth()
        payload = json.dumps({"ck": 123456, "cs": "secret"}, separators=(",", ":")).encode()

        auth.read(len(payload).to_bytes(2, "big") + payload)

        self.assertEqual(auth.user_id, 123456)
        self.assertEqual(auth.password, "secret")

    def test_fbns_initial_device_auth_connection_uses_zero_fbns_user_id(self):
        client = _build_logged_in_client()
        fbns = FbnsClient(client)

        connection = fbns.build_connection()

        self.assertEqual(connection.client_info["userId"], 0)

    def test_fbns_client_builds_device_auth_connection(self):
        client = _build_logged_in_client()
        auth = FbnsDeviceAuth(
            client_id="phone-id-12345678901",
            user_id=12345,
            password="connection-secret",
            device_id="fbns-device-id",
            device_secret="fbns-device-secret",
        )
        fbns = FbnsClient(client, auth=auth)

        connection = fbns.build_connection()

        self.assertEqual(connection.client_identifier, "phone-id-12345678901")
        self.assertEqual(connection.password, "connection-secret")
        self.assertEqual(connection.client_info["userId"], 12345)
        self.assertEqual(connection.client_info["clientType"], "device_auth")
        self.assertEqual(connection.client_info["endpointCapabilities"], 128)
        self.assertEqual(connection.client_info["subscribeTopics"], FBNS_SUBSCRIBE_TOPICS)
        self.assertEqual(connection.client_info["deviceId"], "fbns-device-id")
        self.assertEqual(connection.client_info["deviceSecret"], "fbns-device-secret")
        self.assertEqual(connection.client_info["fbnsDeviceId"], "fbns-device-id")

        decoded = decode_packet(fbns.connect_packet())
        self.assertEqual(decoded.keep_alive, 60)
        thrift = read_thrift_object(zlib.decompress(decoded.payload), MQTToTConnection.thrift_descriptors())
        self.assertEqual(thrift["clientInfo"]["clientType"], "device_auth")
        self.assertEqual(thrift["clientInfo"]["subscribeTopics"], FBNS_SUBSCRIBE_TOPICS)

    async def test_fbns_register_token_publishes_registration_request_and_reads_token(self):
        client = _build_logged_in_client()
        transport = mock.Mock()
        transport.recv_packet.return_value = _publish(FBNSTopics.REG_RESPONSE, {"token": "fbns-token-1"})
        fbns = FbnsClient(client, transport=transport)

        token = await fbns.register_token()

        sent = decode_packet(transport.send.call_args_list[0].args[0])
        self.assertEqual(token, "fbns-token-1")
        self.assertEqual(sent.topic, FBNSTopics.REG_REQUEST)
        self.assertEqual(
            json.loads(zlib.decompress(sent.payload)),
            {
                "pkg_name": "com.instagram.android",
                "appid": 567310203415052,
            },
        )

    async def test_fbns_connect_reads_device_auth_and_registers_push_token(self):
        client = _build_logged_in_client()
        client.private_request = AsyncMock(return_value={"status": "ok"})
        transport = mock.Mock()
        transport.recv_packet.side_effect = [
            _connack(
                {
                    "ck": 123456,
                    "cs": "connection-secret",
                    "di": "fbns-device-id",
                    "ds": "fbns-device-secret",
                }
            ),
            _suback(),
            _publish(FBNSTopics.REG_RESPONSE, {"token": "fbns-token-1"}),
        ]
        registered = []
        fbns = FbnsClient(client, transport=transport)
        fbns.on("registered", registered.append)

        await fbns.connect()

        self.assertTrue(fbns.connected)
        self.assertEqual(fbns.auth.password, "connection-secret")
        self.assertEqual(client.settings["fbns_auth"]["device_secret"], "fbns-device-secret")
        client.private_request.assert_awaited_once()
        endpoint, data = client.private_request.call_args.args[:2]
        self.assertEqual(endpoint, "push/register/")
        self.assertEqual(data["device_type"], "android_mqtt")
        self.assertIs(data["is_main_push_channel"], True)
        self.assertEqual(data["device_sub_type"], 2)
        self.assertEqual(data["device_token"], "fbns-token-1")
        self.assertEqual(data["users"], "12345")
        self.assertEqual(client.private_request.call_args.kwargs, {"with_signature": False})
        self.assertEqual(registered, [{"token": "fbns-token-1", "response": {"status": "ok"}}])

    async def test_fbns_connect_subscribes_to_message_topic_before_waiting_for_registration_response(self):
        client = _build_logged_in_client()
        client.private_request = AsyncMock(return_value={"status": "ok"})
        transport = mock.Mock()
        transport.recv_packet.side_effect = [_connack({}), _suback(), _publish(FBNSTopics.REG_RESPONSE, {"token": "x"})]
        fbns = FbnsClient(client, transport=transport)

        await fbns.connect()

        subscribe_packet = transport.send.call_args_list[1].args[0]
        self.assertEqual(subscribe_packet[0], 0x82)
        self.assertIn(b"\x00\x0276", subscribe_packet)

    def test_fbns_dispatches_push_notification_payloads(self):
        client = _build_logged_in_client()
        fbns = FbnsClient(client, transport=mock.Mock())
        push_events = []
        direct_push_events = []
        received_events = []
        fbns.on("push", push_events.append)
        fbns.on("direct_v2_message", direct_push_events.append)
        fbns.on("receive", received_events.append)

        payload = fbns.dispatch_packet(
            FBNSTopics.MESSAGE,
            json.dumps(
                {
                    "fbpushnotif": json.dumps(
                        {
                            "collapse_key": "direct_v2_message",
                            "message": "hello",
                            "ig": "payload",
                        },
                        separators=(",", ":"),
                    )
                },
                separators=(",", ":"),
            ).encode(),
        )

        self.assertEqual(payload["collapse_key"], "direct_v2_message")
        self.assertEqual(push_events, [payload])
        self.assertEqual(direct_push_events, [payload])
        self.assertEqual(received_events, [{"topic": FBNSTopics.MESSAGE, "payload": payload}])

    async def test_client_exposes_stateful_fbns_helpers(self):
        client = _build_logged_in_client()
        transport = mock.Mock()
        transport.recv_packet.side_effect = [
            _connack({}),
            _suback(),
            _publish(FBNSTopics.REG_RESPONSE, {"token": "fbns-token-1"}),
        ]
        client.private_request = AsyncMock(return_value={"status": "ok"})

        fbns = await client.fbns_connect(transport=transport)

        self.assertIsInstance(fbns, FbnsClient)
        self.assertIs(fbns.transport, transport)
        self.assertTrue(fbns.transport.connect.called)

        await client.fbns_disconnect()
        transport.disconnect.assert_called_once()

    async def test_fbns_read_once_marks_client_disconnected_when_socket_closes(self):
        client = _build_logged_in_client()
        transport = mock.Mock()
        transport.recv_packet.side_effect = ConnectionError("Socket closed while reading MQTT packet")
        fbns = FbnsClient(client, transport=transport)
        fbns.connected = True

        with self.assertRaises(ConnectionError):
            await fbns.read_once()

        self.assertFalse(fbns.connected)

    async def test_fbns_read_once_keeps_client_connected_on_socket_timeout(self):
        client = _build_logged_in_client()
        transport = mock.Mock()
        transport.recv_packet.side_effect = TimeoutError("timed out")
        fbns = FbnsClient(client, transport=transport)
        fbns.connected = True

        with self.assertRaises(TimeoutError):
            await fbns.read_once()

        self.assertTrue(fbns.connected)

    async def test_fbns_disconnect_clears_client_state_after_broken_socket(self):
        client = _build_logged_in_client()
        transport = mock.Mock()
        transport.send.side_effect = ConnectionError("Socket is already closed")
        fbns = FbnsClient(client, transport=transport)
        fbns.connected = True
        client.fbns = fbns

        await client.fbns_disconnect()

        transport.disconnect.assert_called_once()
        self.assertFalse(fbns.connected)
        self.assertIsNone(client.fbns)

    def test_fbns_default_transport_uses_mqtt_mini_and_client_proxy(self):
        client = _build_logged_in_client()
        client.proxy = "socks5://127.0.0.1:8888"

        fbns = FbnsClient(client)

        self.assertEqual(fbns.transport.host, FBNS_HOST)
        self.assertEqual(fbns.transport.proxy, "socks5://127.0.0.1:8888")

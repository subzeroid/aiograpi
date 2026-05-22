import json
import unittest
import zlib
from unittest.mock import AsyncMock, Mock

from aiograpi import Client
from aiograpi.realtime import RealtimeClient
from aiograpi.realtime.mqttot import (
    MQTToTConnection,
    MQTToTTopics,
    decode_packet,
    read_thrift_object,
    write_connect_packet,
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


def test_mqttot_connect_packet_uses_custom_protocol_and_zipped_thrift_payload():
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

    assert packet[0] == 0x10
    decoded = decode_packet(packet)
    assert decoded.packet_type == "connect"
    assert decoded.protocol_name == "MQTToT"
    assert decoded.protocol_level == 3
    assert decoded.connect_flags == 0xC2
    assert decoded.keep_alive == 20

    thrift_payload = zlib.decompress(decoded.payload)
    thrift = read_thrift_object(thrift_payload, MQTToTConnection.thrift_descriptors())
    assert thrift["clientIdentifier"] == "phone-id-123456789"
    assert thrift["password"] == "sessionid=12345:session"
    assert thrift["clientInfo"]["clientType"] == "cookie_auth"
    assert thrift["clientInfo"]["subscribeTopics"] == [88, 135, 149, 150, 133, 146]
    assert thrift["appSpecificInfo"]["ig_mqtt_route"] == "django"


def test_publish_packet_round_trips_topic_and_zipped_payload():
    payload = zlib.compress(json.dumps({"sub": ["1/graphqlsubscriptions/test/{}"]}).encode())

    packet = write_publish_packet(MQTToTTopics.REALTIME_SUB, payload, qos=1, packet_id=7)

    decoded = decode_packet(packet)
    assert decoded.packet_type == "publish"
    assert decoded.topic == MQTToTTopics.REALTIME_SUB
    assert decoded.qos == 1
    assert decoded.packet_id == 7
    assert json.loads(zlib.decompress(decoded.payload)) == {"sub": ["1/graphqlsubscriptions/test/{}"]}


def test_realtime_client_builds_cookie_auth_connection_from_instagram_session():
    client = _build_logged_in_client()
    realtime = RealtimeClient(client)

    connection = realtime.build_connection()

    assert connection.client_identifier == "phone-id-12345678901"
    assert connection.password == "sessionid=12345:session"
    assert connection.client_info["userId"] == 12345
    assert connection.client_info["clientType"] == "cookie_auth"
    assert connection.client_info["appId"] == 567067343352427
    assert connection.client_info["subscribeTopics"] == [88, 135, 149, 150, 133, 146]
    assert connection.app_specific_info["app_version"] == "428.0.0.47.67"
    assert connection.app_specific_info["platform"] == "android"


class RealtimeMixinRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_client_exposes_stateful_realtime_helpers(self):
        client = _build_logged_in_client()
        transport = AsyncMock()
        await client.realtime_connect(transport=transport)

        assert isinstance(client.realtime, RealtimeClient)
        transport.connect.assert_awaited_once()

        await client.realtime_disconnect()
        transport.disconnect.assert_awaited_once()

    async def test_realtime_connect_preserves_handlers_registered_before_connect(self):
        client = _build_logged_in_client()
        transport = AsyncMock()
        handler = Mock()

        client.realtime_on("receive", handler)
        await client.realtime_connect(transport=transport)
        await client.realtime.emit("receive", {"topic": "146", "payload": {"ok": True}})

        handler.assert_called_once_with({"topic": "146", "payload": {"ok": True}})

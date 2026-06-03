import asyncio
import os
import time

from aiograpi.realtime.client import REALTIME_HOST
from aiograpi.realtime.mqttot import SocketMQTToTTransport
from aiograpi.types import DirectMessage
from tests import legacy as _legacy


class RealtimeLiveHelpers:
    def realtime_proxy(self, client):
        return os.getenv("IG_REALTIME_PROXY") or client.proxy

    async def fresh_account_excluding(self, exclude_user_ids):
        data = await self.fetch_test_accounts(count=5 + len(exclude_user_ids))
        last_exc = None
        for acc in data[:5]:
            if str(acc.get("user_id")) in {str(user_id) for user_id in exclude_user_ids}:
                continue
            try:
                return await self.client_from_test_account(acc)
            except Exception as exc:
                last_exc = exc
                continue
        raise last_exc or RuntimeError("No usable second fresh account returned")

    def payload_contains(self, payload, expected):
        if isinstance(payload, dict):
            return any(self.payload_contains(value, expected) for value in payload.values())
        if isinstance(payload, (list, tuple)):
            return any(self.payload_contains(value, expected) for value in payload)
        return str(expected) in str(payload)

    def payload_contains_message(self, payload, text, sender_id):
        return self.payload_contains(payload, text) and self.payload_contains(payload, sender_id)

    def payload_is_new_direct_message_sync(self, payload):
        if isinstance(payload, dict):
            message = payload.get("message")
            if isinstance(message, dict) and message.get("delta_type") == "deltaNewMessage":
                return True
            if payload.get("delta_type") == "deltaNewMessage":
                return True
            return any(self.payload_is_new_direct_message_sync(value) for value in payload.values())
        if isinstance(payload, (list, tuple)):
            return any(self.payload_is_new_direct_message_sync(value) for value in payload)
        return False

    async def direct_message_visible(self, client, thread_id, text, sender_id):
        try:
            messages = await client.direct_messages(thread_id, amount=10)
        except Exception:
            messages = []
        for message in messages:
            if message.text == text and str(message.user_id) == str(sender_id):
                return message
        try:
            request_threads = await client.direct_requests(amount=10)
        except Exception:
            request_threads = []
        for thread in request_threads:
            if str(thread.id) != str(thread_id):
                continue
            for message in thread.messages:
                if message.text == text and str(message.user_id) == str(sender_id):
                    return message
        return None


class ClientRealtimeLiveTestCase(RealtimeLiveHelpers, _legacy.ClientPrivateTestCase):
    async def test_realtime_connect_and_ping_live(self):
        transport = SocketMQTToTTransport(REALTIME_HOST, timeout=30, proxy=self.realtime_proxy(self.cl))

        try:
            realtime = await self.cl.realtime_connect(transport=transport)

            self.assertTrue(realtime.connected)
            self.assertTrue(await self.cl.realtime_ping())
        finally:
            await self.cl.realtime_disconnect()

    async def test_realtime_receives_direct_message_sync_live(self):
        receiver = self.cl
        try:
            sender = await self.fresh_account_excluding({receiver.user_id})
        except RuntimeError as exc:
            self.skipTest(str(exc))

        received_payloads = []
        message = None
        transport = SocketMQTToTTransport(REALTIME_HOST, timeout=30, proxy=self.realtime_proxy(receiver))
        text = f"aiograpi realtime live {int(time.time())}"

        receiver.realtime_on("message", received_payloads.append)
        try:
            realtime = await receiver.realtime_connect(transport=transport)
            self.assertTrue(await receiver.realtime_ping())
            try:
                await realtime.direct_subscribe()
            except RuntimeError as exc:
                self.skipTest(str(exc))

            message = await sender.direct_send(text, user_ids=[receiver.user_id])
            self.assertIsInstance(message, DirectMessage)

            deadline = time.time() + 45
            sync_seen = False
            while time.time() < deadline:
                try:
                    await receiver.realtime_read_once()
                except TimeoutError:
                    continue
                for payload in received_payloads:
                    sync_seen = sync_seen or self.payload_is_new_direct_message_sync(payload)
                    if self.payload_contains_message(payload, text, sender.user_id):
                        return
                if sync_seen:
                    visible = await self.direct_message_visible(receiver, message.thread_id, text, sender.user_id)
                    if visible:
                        self.assertEqual(visible.text, text)
                        return

            self.fail("Realtime MQTT did not deliver a Direct message sync payload for the visible Direct message")
        finally:
            await receiver.realtime_disconnect()
            if message:
                try:
                    await sender.direct_message_unsend(message.thread_id, message.id)
                except Exception:
                    pass
                try:
                    await sender.direct_thread_hide(message.thread_id)
                except Exception:
                    pass
                try:
                    await receiver.direct_thread_hide(message.thread_id)
                except Exception:
                    pass

    async def test_realtime_direct_send_text_live(self):
        sender = self.cl
        try:
            receiver = await self.fresh_account_excluding({sender.user_id})
        except RuntimeError as exc:
            self.skipTest(str(exc))

        setup_message = None
        mqtt_message = None
        thread_id = None
        transport = SocketMQTToTTransport(REALTIME_HOST, timeout=30, proxy=self.realtime_proxy(sender))
        setup_text = f"aiograpi realtime setup {int(time.time())}"
        text = f"aiograpi mqtt send live {int(time.time())}"

        try:
            setup_message = await sender.direct_send(setup_text, user_ids=[receiver.user_id])
            self.assertIsInstance(setup_message, DirectMessage)
            thread_id = setup_message.thread_id

            realtime = await sender.realtime_connect(transport=transport)
            self.assertTrue(realtime.connected)
            self.assertTrue(await sender.realtime_ping())

            command = await realtime.direct_send_text(thread_id, text)

            deadline = time.time() + 45
            while time.time() < deadline:
                try:
                    await sender.realtime_read_once()
                except TimeoutError:
                    pass
                mqtt_message = await self.direct_message_visible(receiver, thread_id, text, sender.user_id)
                if mqtt_message:
                    self.assertEqual(command["thread_id"], str(thread_id))
                    self.assertEqual(mqtt_message.text, text)
                    return
                await asyncio.sleep(2)

            self.fail("Realtime MQTT direct_send_text did not create a visible Direct message")
        finally:
            await sender.realtime_disconnect()
            for message in (mqtt_message, setup_message):
                if not message or not thread_id:
                    continue
                try:
                    await sender.direct_message_unsend(thread_id, message.id)
                except Exception:
                    pass
            if thread_id:
                try:
                    await sender.direct_thread_hide(thread_id)
                except Exception:
                    pass
                try:
                    await receiver.direct_thread_hide(thread_id)
                except Exception:
                    pass

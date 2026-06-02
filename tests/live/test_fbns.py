import os
import time

from aiograpi.realtime.fbns import FBNS_HOST
from aiograpi.realtime.mqttot import SocketMQTToTTransport
from aiograpi.types import DirectMessage
from tests import legacy as _legacy
from tests.live.test_realtime import RealtimeLiveHelpers


class ClientFbnsLiveTestCase(RealtimeLiveHelpers, _legacy.ClientPrivateTestCase):
    def payload_contains_push(self, payload, text, sender_id):
        return self.payload_contains(payload, text) and self.payload_contains(payload, sender_id)

    async def test_fbns_connect_register_and_ping_live(self):
        registered = []
        auth_events = []
        transport = SocketMQTToTTransport(FBNS_HOST, timeout=30, proxy=self.realtime_proxy(self.cl))

        self.cl.set_push_disabled(False)
        self.cl.fbns_on("auth", auth_events.append)
        self.cl.fbns_on("registered", registered.append)

        try:
            fbns = await self.cl.fbns_connect(transport=transport)

            self.assertTrue(fbns.connected)
            self.assertTrue(auth_events)
            self.assertTrue(fbns.auth.password)
            self.assertTrue(fbns.auth.device_id)
            self.assertTrue(registered)
            self.assertTrue(registered[0]["token"])
            self.assertTrue(await self.cl.fbns_ping())
        finally:
            await self.cl.fbns_disconnect()

    async def test_fbns_receives_direct_push_live(self):
        if os.getenv("IG_RUN_FBNS_PUSH_LIVE") != "1":
            self.skipTest("IG_RUN_FBNS_PUSH_LIVE=1 is required for the nondeterministic FBNS Direct push test")
        receiver = self.cl
        try:
            sender = await self.fresh_account_excluding({receiver.user_id})
        except RuntimeError as exc:
            self.skipTest(str(exc))

        registered = []
        pushes = []
        received = []
        message = None
        transport = SocketMQTToTTransport(FBNS_HOST, timeout=30, proxy=self.realtime_proxy(receiver))
        text = f"aiograpi fbns push live {int(time.time())}"

        receiver.set_push_disabled(False)
        receiver.fbns_on("registered", registered.append)
        receiver.fbns_on("push", pushes.append)
        receiver.fbns_on("receive", received.append)

        try:
            fbns = await receiver.fbns_connect(transport=transport)
            self.assertTrue(fbns.connected)
            self.assertTrue(registered)
            self.assertTrue(await receiver.fbns_ping())

            message = await sender.direct_send(text, user_ids=[receiver.user_id])
            self.assertIsInstance(message, DirectMessage)

            deadline = time.time() + 60
            while time.time() < deadline:
                try:
                    await receiver.fbns_read_once()
                except TimeoutError:
                    continue
                for payload in pushes:
                    if self.payload_contains_push(payload, text, sender.user_id):
                        return

            self.fail(
                "FBNS did not deliver a Direct push payload for the live Direct message "
                f"(received={len(received)}, pushes={len(pushes)})"
            )
        finally:
            await receiver.fbns_disconnect()
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

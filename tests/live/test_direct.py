import asyncio
import logging
import time

from aiograpi.exceptions import DirectMessageNotFound
from aiograpi.types import DirectMessage
from tests import legacy as _legacy
from tests.live.test_realtime import RealtimeLiveHelpers

logger = logging.getLogger("aiograpi.tests")


class ClientDirectLiveTestCase(RealtimeLiveHelpers, _legacy.ClientPrivateTestCase):
    async def test_direct_messages_chunk_paginates_thread_history_live(self):
        sender = self.cl
        try:
            first_recipient = await self.fresh_account_excluding({sender.user_id})
            second_recipient = await self.fresh_account_excluding({sender.user_id, first_recipient.user_id})
        except RuntimeError as exc:
            self.skipTest(str(exc))

        thread_id = None
        sent_messages = []
        title = f"aiograpi-pagination-{int(time.time())}"
        text_prefix = f"aiograpi pagination live {int(time.time())}"

        try:
            thread_id = await sender.direct_thread_create(
                [int(first_recipient.user_id), int(second_recipient.user_id)],
                title=title,
            )
            self.assertTrue(thread_id)

            for index in range(3):
                message = await sender.direct_answer(thread_id, f"{text_prefix} {index}")
                self.assertIsInstance(message, DirectMessage)
                self.assertTrue(message.id)
                sent_messages.append(message)
                await asyncio.sleep(1)

            first_page = []
            cursor = None
            deadline = time.time() + 30
            while time.time() < deadline:
                first_page, cursor = await sender.direct_messages_chunk(thread_id, amount=1)
                if first_page:
                    break
                await asyncio.sleep(2)

            self.assertEqual(len(first_page), 1)
            self.assertIsInstance(first_page[0], DirectMessage)
            if not cursor:
                self.skipTest("Instagram did not return oldest_cursor for the live thread")

            second_page, next_cursor = await sender.direct_messages_chunk(thread_id, amount=1, cursor=cursor)
            self.assertEqual(len(second_page), 1)
            self.assertIsInstance(second_page[0], DirectMessage)
            self.assertNotEqual(first_page[0].id, second_page[0].id)
            self.assertTrue(next_cursor is None or isinstance(next_cursor, str))
        finally:
            if thread_id:
                for message in reversed(sent_messages):
                    try:
                        await sender.direct_message_unsend(thread_id, message.id)
                    except Exception as exc:
                        logger.warning("Direct pagination message cleanup failed: %s", exc)
                for client in (sender, first_recipient, second_recipient):
                    try:
                        await client.direct_thread_hide(thread_id)
                    except Exception as exc:
                        logger.warning("Direct pagination thread cleanup failed: %s", exc)

    async def test_direct_media_share_to_group_thread_live(self):
        sender = self.cl
        try:
            first_recipient = await self.fresh_account_excluding({sender.user_id})
            second_recipient = await self.fresh_account_excluding({sender.user_id, first_recipient.user_id})
        except RuntimeError as exc:
            self.skipTest(str(exc))

        thread_id = None
        dm = None
        title = f"aiograpi-media-share-{int(time.time())}"

        try:
            thread_id = await sender.direct_thread_create(
                [int(first_recipient.user_id), int(second_recipient.user_id)],
                title=title,
            )
            self.assertTrue(thread_id)

            instagram_pk = await self.user_id_from_username("instagram")
            medias = await sender.user_medias(instagram_pk, amount=12)
            media = next((item for item in medias if item.id and item.media_type == 1), None)
            if media is None:
                self.skipTest("No photo media available for Direct media-share live test")

            dm = await sender.direct_media_share(
                media.id,
                thread_ids=[thread_id],
                media_type="photo",
            )
            self.assertIsInstance(dm, DirectMessage)
            self.assertTrue(dm.id)
            self.assertEqual(str(dm.thread_id), str(thread_id))

            shared = None
            for _ in range(8):
                try:
                    shared = await sender.direct_message(thread_id, dm.id, amount=10)
                except DirectMessageNotFound:
                    await asyncio.sleep(2)
                    continue
                if shared.media_share or shared.xma_share or shared.raw_xma:
                    break
                await asyncio.sleep(2)

            self.assertIsNotNone(shared)
            self.assertTrue(shared.media_share or shared.xma_share or shared.raw_xma)
        finally:
            if thread_id:
                if dm and dm.id:
                    try:
                        await sender.direct_message_unsend(thread_id, dm.id)
                    except Exception as exc:
                        logger.warning("Direct media share unsend cleanup failed: %s", exc)
                for client in (sender, first_recipient, second_recipient):
                    try:
                        await client.direct_thread_hide(thread_id)
                    except Exception as exc:
                        logger.warning("Direct media share thread cleanup failed: %s", exc)

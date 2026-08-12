import asyncio
import logging
import tempfile
import time
from contextlib import asynccontextmanager
from pathlib import Path

from PIL import Image

from aiograpi.exceptions import DirectMessageNotFound
from aiograpi.types import DirectMessage
from tests import legacy as _legacy
from tests.live.test_realtime import RealtimeLiveHelpers

logger = logging.getLogger("aiograpi.tests")


class ClientDirectLiveTestCase(RealtimeLiveHelpers, _legacy.ClientPrivateTestCase):
    def make_photo_png(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            path = Path(tmp.name)
        Image.new("RGBA", (64, 48), (37, 99, 235, 128)).save(path)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        return path

    @asynccontextmanager
    async def direct_pagination_thread(self, sender, test_name):
        try:
            first_recipient = await self.fresh_account_excluding({sender.user_id})
            second_recipient = await self.fresh_account_excluding({sender.user_id, first_recipient.user_id})
        except RuntimeError as exc:
            self.skipTest(str(exc))

        thread_id = None
        sent_messages = []
        title = f"aiograpi-{test_name}-{int(time.time())}"
        text_prefix = f"aiograpi {test_name} live {int(time.time())}"

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
            yield thread_id

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

    async def test_direct_messages_chunk_paginates_thread_history_live(self):
        sender = self.cl
        async with self.direct_pagination_thread(sender, "chunk-pagination") as thread_id:
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

    async def test_direct_messages_auto_paginates_thread_history_live(self):
        sender = self.cl
        async with self.direct_pagination_thread(sender, "messages-pagination") as thread_id:
            original_direct_messages_chunk = sender.direct_messages_chunk
            requested_cursors = []

            async def one_message_chunk(thread_id, amount=20, cursor=None):
                requested_cursors.append(cursor)
                return await original_direct_messages_chunk(thread_id, amount=1, cursor=cursor)

            sender.direct_messages_chunk = one_message_chunk
            messages = []
            try:
                deadline = time.time() + 30
                while time.time() < deadline:
                    requested_cursors.clear()
                    messages = await sender.direct_messages(thread_id, amount=2)
                    if len(messages) == 2:
                        break
                    await asyncio.sleep(2)
            finally:
                sender.direct_messages_chunk = original_direct_messages_chunk

            if len(messages) < 2 and len(requested_cursors) < 2:
                self.skipTest("Instagram did not return oldest_cursor for the live thread")

            self.assertEqual(len(messages), 2)
            self.assertTrue(all(isinstance(message, DirectMessage) for message in messages))
            self.assertEqual(len({message.id for message in messages}), 2)
            self.assertGreaterEqual(len(requested_cursors), 2)
            self.assertIsNone(requested_cursors[0])
            self.assertIsInstance(requested_cursors[1], str)

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

    async def test_direct_send_photo_with_thread_and_user_ids_live(self):
        sender = self.cl
        try:
            recipient = await self.fresh_account_excluding({sender.user_id})
        except RuntimeError as exc:
            self.skipTest(str(exc))

        photo_path = self.make_photo_png()
        sent_messages = []
        thread_id = None
        recipient_follow_added = False

        try:
            relationship = await recipient.user_friendship_v1(sender.user_id)
            if not relationship or not relationship.following:
                followed = await recipient.user_follow(sender.user_id)
                if not followed:
                    self.skipTest("Recipient could not follow sender before Direct delivery test")
                recipient_follow_added = True
                relationship = await recipient.user_friendship_v1(sender.user_id)
                if relationship and relationship.outgoing_request:
                    approved = await sender.user_follow_request_approve(recipient.user_id)
                    if not approved:
                        self.skipTest("Sender could not approve recipient follow request")

                for _ in range(6):
                    relationship = await recipient.user_friendship_v1(sender.user_id)
                    if relationship and relationship.following:
                        break
                    await asyncio.sleep(2)
                if not relationship or not relationship.following:
                    self.skipTest("Recipient follow was not active before Direct delivery test")

            seed_message = await sender.direct_send(
                f"aiograpi direct photo live warm {int(time.time())}",
                user_ids=[recipient.user_id],
            )
            self.assertIsInstance(seed_message, DirectMessage)
            sent_messages.append((sender, seed_message))

            thread_id = seed_message.thread_id
            if not thread_id:
                thread = await sender.direct_thread_by_participants([recipient.user_id])
                thread_id = thread.get("thread_v2_id") or thread.get("thread_id")
            self.assertTrue(thread_id)

            reply_message = await recipient.direct_answer(
                thread_id,
                f"aiograpi direct photo live reply {int(time.time())}",
            )
            self.assertIsInstance(reply_message, DirectMessage)
            sent_messages.append((recipient, reply_message))

            thread_photo = await sender.direct_send_photo(photo_path, thread_ids=[thread_id])
            self.assertIsInstance(thread_photo, DirectMessage)
            self.assertTrue(thread_photo.id)
            sent_messages.append((sender, thread_photo))

            user_photo = await sender.direct_send_photo(photo_path, user_ids=[recipient.user_id])
            self.assertIsInstance(user_photo, DirectMessage)
            self.assertTrue(user_photo.id)
            sent_messages.append((sender, user_photo))

            for sent_photo in (thread_photo, user_photo):
                received_photo = None
                for _ in range(8):
                    try:
                        received_photo = await recipient.direct_message(thread_id, sent_photo.id, amount=20)
                    except DirectMessageNotFound:
                        await asyncio.sleep(2)
                        continue
                    if received_photo.item_type == "media" and received_photo.media:
                        break
                    await asyncio.sleep(2)

                self.assertIsNotNone(received_photo)
                self.assertEqual(received_photo.item_type, "media")
                self.assertIsNotNone(received_photo.media)
        finally:
            if thread_id:
                for client, message in reversed(sent_messages):
                    try:
                        await client.direct_message_unsend(thread_id, message.id)
                    except Exception as exc:
                        logger.warning("Direct photo message cleanup failed: %s", exc)
                for client in (sender, recipient):
                    try:
                        await client.direct_thread_hide(thread_id)
                    except Exception as exc:
                        logger.warning("Direct photo thread cleanup failed: %s", exc)
            if recipient_follow_added:
                try:
                    await recipient.user_unfollow(sender.user_id)
                except Exception as exc:
                    logger.warning("Direct photo follow cleanup failed: %s", exc)

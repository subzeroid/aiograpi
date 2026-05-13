import unittest
from unittest.mock import AsyncMock

from aiograpi import Client
from aiograpi.types import Comment


class CommentRepliesRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    def _reply_payload(self, pk, text="reply", replied_to_comment_id="100"):
        return {
            "pk": str(pk),
            "text": text,
            "user": {"pk": "1", "username": "example", "full_name": "Example"},
            "created_at_utc": 1_700_000_000,
            "content_type": "comment",
            "status": "Active",
            "replied_to_comment_id": str(replied_to_comment_id),
            "has_liked_comment": False,
            "comment_like_count": 0,
        }

    async def test_media_comments_chunk_fetches_private_comments_page(self):
        client = Client()
        client.private_request = AsyncMock(
            return_value={
                "comments": [self._reply_payload("101", "first")],
                "next_min_id": "cursor-2",
                "has_more_headload_comments": False,
                "status": "ok",
            }
        )

        comments, cursor = await client.media_comments_chunk("123_456", max_amount=10, min_id="cursor-1")

        client.private_request.assert_awaited_once_with("media/123_456/comments/", {"min_id": "cursor-1"})
        assert [comment.pk for comment in comments] == ["101"]
        assert cursor == "cursor-2"

    async def test_media_comment_replies_fetches_inline_child_comments(self):
        client = Client()
        client.private_request = AsyncMock(
            return_value={
                "child_comments": [
                    self._reply_payload("101", "first"),
                    self._reply_payload("102", "second"),
                ],
                "has_more_head_child_comments": False,
                "status": "ok",
            }
        )

        replies = await client.media_comment_replies("123_456", "100")

        client.private_request.assert_awaited_once_with("media/123_456/comments/100/inline_child_comments/", None)
        assert [reply.pk for reply in replies] == ["101", "102"]
        assert all(isinstance(reply, Comment) for reply in replies)
        assert replies[0].replied_to_comment_id == "100"

    async def test_media_comment_replies_chunk_returns_child_cursor(self):
        client = Client()
        client.private_request = AsyncMock(
            return_value={
                "child_comments": [self._reply_payload("101")],
                "next_min_child_cursor": "cursor-2",
                "has_more_head_child_comments": True,
                "status": "ok",
            }
        )

        replies, cursor = await client.media_comment_replies_chunk("123_456", "100", max_amount=10, min_id="cursor-1")

        client.private_request.assert_awaited_once_with(
            "media/123_456/comments/100/inline_child_comments/",
            {"min_id": "cursor-1"},
        )
        assert [reply.pk for reply in replies] == ["101"]
        assert cursor == "cursor-2"

    async def test_media_comment_replies_paginates_until_amount(self):
        client = Client()
        client.private_request = AsyncMock(
            side_effect=[
                {
                    "child_comments": [self._reply_payload("101")],
                    "next_min_child_cursor": "cursor-2",
                    "has_more_head_child_comments": True,
                    "status": "ok",
                },
                {
                    "child_comments": [self._reply_payload("102")],
                    "has_more_head_child_comments": False,
                    "status": "ok",
                },
            ]
        )

        replies = await client.media_comment_replies("123_456", "100", amount=2)

        assert client.private_request.await_args_list[0].args == (
            "media/123_456/comments/100/inline_child_comments/",
            None,
        )
        assert client.private_request.await_args_list[1].args == (
            "media/123_456/comments/100/inline_child_comments/",
            {"min_id": "cursor-2"},
        )
        assert [reply.pk for reply in replies] == ["101", "102"]

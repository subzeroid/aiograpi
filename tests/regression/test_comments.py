import unittest
from unittest.mock import AsyncMock, Mock

from aiograpi import Client
from aiograpi.exceptions import ClientLoginRequired
from aiograpi.extractors import extract_comment, extract_comment_gql
from aiograpi.types import Comment


class CommentRepliesRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    def _build_logged_in_client(self):
        client = Client()
        client.authorization_data = {"ds_user_id": "1"}
        client.android_device_id = "android-device"
        return client

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

    def _graphql_comment_payload(self):
        return {
            "pk": "101",
            "user": {
                "id": "1",
                "pk": "1",
                "username": "example",
                "is_verified": True,
            },
            "child_comment_count": 2,
            "parent_comment_id": None,
            "has_liked_comment": False,
            "text": "hello",
            "created_at": 1_700_000_000,
            "comment_like_count": 7,
            "__typename": "XDTCommentDict",
        }

    async def test_media_comments_normalizes_xdt_graphql_comment(self):
        client = Client()
        client.media_comments_gql = AsyncMock(return_value=[self._graphql_comment_payload()])
        client.media_comments_v1 = AsyncMock()

        comments = await client.media_comments("123_456", amount=1)

        self.assertEqual(len(comments), 1)
        comment = comments[0]
        self.assertIsInstance(comment, Comment)
        self.assertEqual(comment.pk, "101")
        self.assertEqual(comment.user.pk, "1")
        self.assertEqual(int(comment.created_at_utc.timestamp()), 1_700_000_000)
        self.assertEqual(comment.content_type, "comment")
        self.assertEqual(comment.status, "Active")
        self.assertIs(comment.has_liked, False)
        self.assertEqual(comment.like_count, 7)
        self.assertEqual(comment.child_comment_count, 2)
        self.assertIsNone(comment.replied_to_comment_id)
        client.media_comments_v1.assert_not_awaited()

    def test_extract_comment_preserves_optional_child_comment_count(self):
        with_count = self._reply_payload("201")
        with_count["child_comment_count"] = 0

        self.assertEqual(extract_comment(with_count).child_comment_count, 0)
        self.assertIsNone(extract_comment(self._reply_payload("202")).child_comment_count)

    async def test_media_comments_falls_back_when_graphql_comment_has_no_pk(self):
        client = Client()
        malformed_comment = self._graphql_comment_payload()
        malformed_comment.pop("pk")
        private_comment = extract_comment(self._reply_payload("203"))
        client.media_comments_gql = AsyncMock(return_value=[malformed_comment])
        client.media_comments_v1 = AsyncMock(return_value=[private_comment])
        client.logger = Mock()

        comments = await client.media_comments("123_456", amount=1)

        self.assertEqual(comments, [private_comment])
        client.media_comments_v1.assert_awaited_once_with("123_456", 1)

    async def test_media_comments_normalizes_graphql_user_with_null_id_and_valid_pk(self):
        client = Client()
        malformed_comment = self._graphql_comment_payload()
        malformed_comment["user"] = {
            "id": None,
            "pk": "1",
            "username": "sensitive-user",
            "profile_pic_url": "https://sensitive.example/avatar.jpg",
        }
        client.media_comments_gql = AsyncMock(return_value=[malformed_comment])
        client.media_comments_v1 = AsyncMock()
        client.logger = Mock()

        comments = await client.media_comments("123_456", amount=1)

        self.assertIsInstance(comments[0], Comment)
        self.assertEqual(comments[0].user.pk, "1")
        client.media_comments_v1.assert_not_awaited()
        client.logger.exception.assert_not_called()

    async def test_media_comments_does_not_log_graphql_user_payload_without_pk(self):
        client = Client()
        malformed_comment = self._graphql_comment_payload()
        malformed_comment["user"] = {
            "username": "sensitive-user",
            "profile_pic_url": "https://sensitive.example/avatar.jpg",
        }
        private_comment = extract_comment(self._reply_payload("204"))
        client.media_comments_gql = AsyncMock(return_value=[malformed_comment])
        client.media_comments_v1 = AsyncMock(return_value=[private_comment])
        client.logger = Mock()

        comments = await client.media_comments("123_456", amount=1)

        self.assertEqual(comments, [private_comment])
        logged_error = str(client.logger.exception.call_args.args[0])
        self.assertNotIn("sensitive-user", logged_error)
        self.assertNotIn("sensitive.example", logged_error)

    async def test_media_comments_does_not_log_graphql_validation_input(self):
        client = Client()
        malformed_comment = self._graphql_comment_payload()
        malformed_comment["user"]["profile_pic_url"] = "sensitive-token-not-a-url"
        private_comment = extract_comment(self._reply_payload("205"))
        client.media_comments_gql = AsyncMock(return_value=[malformed_comment])
        client.media_comments_v1 = AsyncMock(return_value=[private_comment])
        client.logger = Mock()

        comments = await client.media_comments("123_456", amount=1)

        self.assertEqual(comments, [private_comment])
        logged_error = str(client.logger.exception.call_args.args[0])
        self.assertNotIn("sensitive-token-not-a-url", logged_error)

    async def test_media_comments_normalizes_graphql_comment_after_login_retry(self):
        client = Client()
        payload = self._graphql_comment_payload()
        client.media_comments_gql = AsyncMock(side_effect=[ClientLoginRequired("login"), [payload]])
        client.inject_sessionid_to_public = Mock(return_value=True)
        client.media_comments_v1 = AsyncMock()

        comments = await client.media_comments("123_456", amount=1)

        self.assertEqual(client.media_comments_gql.await_count, 2)
        self.assertEqual(client.media_comments_gql.await_args_list[0].args, ("123_456", 1))
        self.assertEqual(client.media_comments_gql.await_args_list[1].args, ("123_456", 1))
        client.inject_sessionid_to_public.assert_called_once_with()
        self.assertIsInstance(comments[0], Comment)
        self.assertEqual(comments[0].child_comment_count, 2)
        client.media_comments_v1.assert_not_awaited()

    async def test_media_comments_falls_back_when_public_session_injection_is_unavailable(self):
        client = Client()
        private_comment = extract_comment(self._reply_payload("206"))
        client.media_comments_gql = AsyncMock(side_effect=ClientLoginRequired("login"))
        client.inject_sessionid_to_public = Mock(return_value=False)
        client.media_comments_v1 = AsyncMock(return_value=[private_comment])

        comments = await client.media_comments("123_456", amount=1)

        self.assertEqual(comments, [private_comment])
        client.media_comments_gql.assert_awaited_once_with("123_456", 1)
        client.inject_sessionid_to_public.assert_called_once_with()
        client.media_comments_v1.assert_awaited_once_with("123_456", 1)

    def test_extract_comment_gql_normalizes_legacy_aliases(self):
        comment = extract_comment_gql(
            {
                "id": "301",
                "owner": {"id": "7", "username": "legacy"},
                "text": "legacy",
                "created_at": 1_700_000_000,
                "viewer_has_liked": False,
                "edge_liked_by": {"count": 0},
                "parent_comment_id": 42,
            }
        )

        self.assertEqual(comment.pk, "301")
        self.assertEqual(comment.user.pk, "7")
        self.assertIs(comment.has_liked, False)
        self.assertEqual(comment.like_count, 0)
        self.assertEqual(comment.replied_to_comment_id, "42")
        self.assertEqual(comment.content_type, "comment")
        self.assertEqual(comment.status, "Active")

    def test_extract_comment_gql_preserves_canonical_fields(self):
        comment = extract_comment_gql(
            {
                "pk": "302",
                "user": {"id": "8", "username": "canonical"},
                "text": "canonical",
                "created_at_utc": 1_700_000_001,
                "created_at": 1_700_000_000,
                "has_liked": False,
                "has_liked_comment": True,
                "viewer_has_liked": True,
                "like_count": 0,
                "comment_like_count": 9,
                "edge_liked_by": {"count": 8},
                "replied_to_comment_id": "41",
                "parent_comment_id": 42,
                "content_type": "canonical-comment",
                "status": "Canonical",
            }
        )

        self.assertEqual(int(comment.created_at_utc.timestamp()), 1_700_000_001)
        self.assertIs(comment.has_liked, False)
        self.assertEqual(comment.like_count, 0)
        self.assertEqual(comment.replied_to_comment_id, "41")
        self.assertEqual(comment.content_type, "canonical-comment")
        self.assertEqual(comment.status, "Canonical")

    async def test_media_comment_posts_current_action_context(self):
        client = self._build_logged_in_client()
        expected_comment = self._reply_payload("101", text="hello")
        client.private_request = AsyncMock(return_value={"comment": expected_comment})

        comment = await client.media_comment("123_456", "hello", replied_to_comment_id=100)

        self.assertIsInstance(comment, Comment)
        endpoint, data = client.private_request.await_args.args
        self.assertEqual(endpoint, "media/123_456/comment/")
        self.assertEqual(data["media_id"], "123_456")
        self.assertEqual(data["_uid"], "1")
        self.assertEqual(data["_uuid"], client.uuid)
        self.assertEqual(data["device_id"], "android-device")
        self.assertEqual(data["radio_type"], "wifi-none")
        self.assertEqual(data["delivery_class"], "organic")
        self.assertEqual(data["tap_source"], "button")
        self.assertEqual(data["is_2m_enabled"], "false")
        self.assertEqual(data["is_carousel_bumped_post"], "false")
        self.assertEqual(data["is_from_swipe"], "false")
        self.assertEqual(data["floating_context_items"], "[]")
        self.assertEqual(data["media_pct_watched"], "0")
        self.assertEqual(data["container_module"], "feed_timeline")
        self.assertIn(data["feed_position"], {str(i) for i in range(7)})
        self.assertEqual(data["comment_text"], "hello")
        self.assertEqual(data["replied_to_comment_id"], 100)
        self.assertIn("user_breadcrumb", data)
        self.assertIn("idempotence_token", data)
        self.assertEqual(data["comment_creation_key"], data["idempotence_token"])
        self.assertEqual(data["include_e2ee_mentioned_user_list"], "true")
        self.assertEqual(data["include_media_code"], "true")

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

    async def test_media_comments_gql_chunk_posts_public_doc_id_query(self):
        client = Client()
        client.public_doc_id_graphql_request = AsyncMock(
            return_value={
                "xdt_media_comments": {
                    "edges": [{"node": {"pk": "101", "text": "hello"}}],
                    "page_info": {"has_next_page": True, "end_cursor": "cursor-2"},
                }
            }
        )

        comments, cursor = await client.media_comments_gql_chunk("3441088131388376166", end_cursor="cursor-1")

        self.assertEqual(comments, [{"pk": "101", "text": "hello"}])
        self.assertEqual(cursor, "cursor-2")
        client.public_doc_id_graphql_request.assert_awaited_once_with(
            "6974885689225067",
            {
                "after": "cursor-1",
                "before": None,
                "first": 50,
                "last": None,
                "media_id": "3441088131388376166",
                "sort_order": "popular",
            },
            referer="https://www.instagram.com/p/C_BM2yAN4Rm/",
        )

    async def test_media_comments_gql_aggregates_raw_comment_nodes(self):
        client = Client()
        first = {"pk": "101", "text": "first"}
        second = {"pk": "102", "text": "second"}
        client.media_comments_gql_chunk = AsyncMock(side_effect=[([first], "cursor-1"), ([second], "")])

        comments = await client.media_comments_gql("3441088131388376166", amount=0)

        self.assertEqual(comments, [first, second])
        self.assertTrue(all(isinstance(comment, dict) for comment in comments))
        self.assertEqual(client.media_comments_gql_chunk.await_count, 2)

    async def test_media_comments_public_gql_uses_shortcode_without_manual_graphql_params(self):
        client = Client()
        client.media_comments_gql = AsyncMock(return_value=[{"pk": "101"}])

        comments = await client.media_comments_public_gql("C_BM2yAN4Rm", amount=12, max_requests=2)

        self.assertEqual(comments, [{"pk": "101"}])
        client.media_comments_gql.assert_awaited_once_with("3441088131388376166", amount=12, max_requests=2)

    async def test_comment_pin_posts_to_slash_terminated_endpoint(self):
        client = self._build_logged_in_client()
        client.private_request = AsyncMock(return_value={"status": "ok"})

        result = await client.comment_pin("123_456", 789)

        self.assertTrue(result)
        endpoint, data = client.private_request.await_args.args
        self.assertEqual(endpoint, "media/123_456/pin_comment/789/")
        self.assertEqual(data["_uid"], client.user_id)
        self.assertEqual(data["_uuid"], client.uuid)

    async def test_comment_unpin_posts_to_slash_terminated_endpoint(self):
        client = self._build_logged_in_client()
        client.private_request = AsyncMock(return_value={"status": "ok"})

        result = await client.comment_unpin("123_456", 789)

        self.assertTrue(result)
        endpoint, data = client.private_request.await_args.args
        self.assertEqual(endpoint, "media/123_456/unpin_comment/789/")
        self.assertEqual(data["_uid"], client.user_id)
        self.assertEqual(data["_uuid"], client.uuid)

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

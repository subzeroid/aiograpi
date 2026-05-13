import unittest
from unittest.mock import AsyncMock

import orjson

from aiograpi import Client
from aiograpi.exceptions import ClientError, ClientForbiddenError


class UsertagMediasPaginationRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    def _media_v1_payload(self, pk="1"):
        return {
            "pk": pk,
            "id": f"{pk}_2",
            "code": "abc",
            "taken_at": 1710000000,
            "media_type": 1,
            "user": {
                "pk": "2",
                "username": "example",
                "profile_pic_url": "https://example.com/profile.jpg",
            },
            "image_versions2": {"candidates": [{"url": "https://example.com/x.jpg", "width": 100, "height": 100}]},
        }

    def _media_gql_payload(self, pk="1"):
        return {
            "__typename": "GraphImage",
            "id": pk,
            "shortcode": "abc",
            "taken_at_timestamp": 1710000000,
            "owner": {
                "id": "2",
                "username": "example",
                "profile_pic_url": "https://example.com/profile.jpg",
            },
            "display_resources": [{"src": "https://example.com/x.jpg", "config_width": 100, "config_height": 100}],
            "edge_media_to_comment": {"count": 0},
            "edge_media_preview_like": {"count": 0},
            "edge_media_to_caption": {"edges": []},
            "edge_media_to_tagged_user": {"edges": []},
        }

    async def test_usertag_medias_paginated_gql_returns_page_and_cursor(self):
        client = Client()
        payload = self._media_gql_payload()
        client.public_graphql_request = AsyncMock(
            return_value={
                "user": {
                    "edge_user_to_photos_of_you": {
                        "page_info": {"end_cursor": "next-page"},
                        "edges": [{"node": payload}],
                    }
                }
            }
        )

        medias, end_cursor = await client.usertag_medias_paginated_gql("123", amount=1, end_cursor="cursor-1")

        client.public_graphql_request.assert_awaited_once_with(
            {"id": 123, "first": 1, "after": "cursor-1"},
            query_hash="be13233562af2d229b008d2976b998b5",
        )
        assert end_cursor == "next-page"
        assert [media.pk for media in medias] == ["1"]

    async def test_usertag_medias_paginated_v1_returns_page_and_cursor(self):
        client = Client()
        payload = self._media_v1_payload()
        client.private_request = AsyncMock(return_value={"items": [payload], "next_max_id": "next-page"})

        medias, end_cursor = await client.usertag_medias_paginated_v1("123", amount=1, end_cursor="cursor-1")

        client.private_request.assert_awaited_once_with("usertags/123/feed/", params={"max_id": "cursor-1"})
        assert end_cursor == "next-page"
        assert [media.pk for media in medias] == ["1"]

    async def test_usertag_medias_paginated_falls_back_to_v1(self):
        client = Client()
        client.usertag_medias_paginated_gql = AsyncMock(side_effect=ClientError("public unavailable"))
        client.usertag_medias_paginated_v1 = AsyncMock(return_value=(["m1"], "next-page"))

        medias, end_cursor = await client.usertag_medias_paginated("123", amount=5, end_cursor="cursor-1")

        client.usertag_medias_paginated_gql.assert_awaited_once_with(123, 5, end_cursor="cursor-1")
        client.usertag_medias_paginated_v1.assert_awaited_once_with(123, 5, end_cursor="cursor-1")
        assert medias == ["m1"]
        assert end_cursor == "next-page"


class LocationPaginationRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_location_medias_v1_chunk_stops_when_next_max_id_is_missing(self):
        client = Client()
        client.uuid = "uuid"
        client.client_session_id = "session"
        client.private_request = AsyncMock(
            return_value={
                "next_page": 335,
                "next_media_ids": [],
                "next_max_id": None,
                "sections": [],
            }
        )

        medias, next_max_id = await client.location_medias_v1_chunk(123, tab_key="recent")

        assert medias == []
        assert next_max_id is None


class UserMediasGraphQLRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    def _xdt_media_payload(self):
        return {
            "id": "1",
            "code": "abc",
            "1ltaken_at": 1710000000,
            "media_type": 1,
            "usertags": None,
            "carousel_media": None,
            "user": {
                "pk": "2",
                "username": "example",
                "profile_pic_url": "https://example.com/profile.jpg",
            },
            "image_versions2": {
                "candidates": [{"url": "https://example.com/x.jpg", "width": 100, "height": 100}],
                "scrubber_spritesheet_info_candidates": {"default": {"video_length": 15.4}},
            },
        }

    async def test_user_medias_chunk_gql_uses_app_timeline_doc_id(self):
        client = Client()
        response = {
            "data": {
                "xdt_api__v1__profile_timeline": {
                    "profile_grid_items": [{"media": self._xdt_media_payload()}],
                    "more_available": True,
                    "next_max_id": "next-page",
                }
            }
        }
        client.private_graphql_request = AsyncMock(return_value=response)
        client.public_graphql_request = AsyncMock(side_effect=AssertionError("legacy query_hash should not be used"))

        medias, end_cursor = await client.user_medias_chunk_gql("123", amount=1, end_cursor="cursor-1")

        client.private_graphql_request.assert_awaited_once()
        client.public_graphql_request.assert_not_called()
        data = client.private_graphql_request.call_args.args[0]
        variables = orjson.loads(data["variables"])
        self.assertEqual(data["fb_api_req_friendly_name"], "IGProfileTimelineQuery")
        self.assertEqual(data["client_doc_id"], "56030350814417327502004290437")
        self.assertEqual(variables["user_id"], "123")
        self.assertEqual(variables["count"], 1)
        self.assertEqual(variables["max_id"], "cursor-1")
        self.assertEqual(end_cursor, "next-page")
        self.assertEqual([media.pk for media in medias], ["1"])
        self.assertEqual(medias[0].id, "1_2")

    async def test_user_medias_paginated_aliases_chunk_gql(self):
        client = Client()
        client.user_medias_chunk_gql = AsyncMock(return_value=(["media"], "next-page"))

        medias, end_cursor = await client.user_medias_paginated_gql("123", amount=7, sleep=1, end_cursor="cursor-1")

        assert medias == ["media"]
        assert end_cursor == "next-page"
        client.user_medias_chunk_gql.assert_awaited_once_with("123", sleep=1, end_cursor="cursor-1", amount=7)

    async def test_user_medias_paginated_v1_sends_count_and_cursor(self):
        client = Client()
        payload = UsertagMediasPaginationRegressionTestCase()._media_v1_payload()
        client.private_request = AsyncMock(return_value={"items": [payload], "next_max_id": "next-page"})

        medias, end_cursor = await client.user_medias_paginated_v1("123", amount=5, end_cursor="cursor-1")

        client.private_request.assert_awaited_once()
        assert client.private_request.call_args.args[0] == "feed/user/123/"
        params = client.private_request.call_args.kwargs["params"]
        assert params["max_id"] == "cursor-1"
        assert params["count"] == 5
        assert end_cursor == "next-page"
        assert [media.pk for media in medias] == ["1"]

    async def test_user_medias_paginated_falls_back_to_v1_for_v1_cursor(self):
        client = Client()
        client.user_medias_paginated_gql = AsyncMock(side_effect=AssertionError("gql should not be used"))
        client.user_medias_paginated_v1 = AsyncMock(return_value=(["media"], "next-page"))

        medias, end_cursor = await client.user_medias_paginated("123", amount=5, end_cursor="v1_cursor")

        assert medias == ["media"]
        assert end_cursor == "next-page"
        client.user_medias_paginated_gql.assert_not_called()
        client.user_medias_paginated_v1.assert_awaited_once_with("123", 5, end_cursor="v1_cursor")

    async def test_user_videos_paginated_v1_sends_count_and_cursor(self):
        client = Client()
        payload = UsertagMediasPaginationRegressionTestCase()._media_v1_payload()
        client.private_request = AsyncMock(return_value={"items": [payload], "next_max_id": "next-page"})

        medias, end_cursor = await client.user_videos_paginated_v1("123", amount=6, end_cursor="cursor-1")

        client.private_request.assert_awaited_once_with(
            "igtv/channel/",
            params={"id": "uservideo_123", "count": 6, "max_id": "cursor-1"},
        )
        assert end_cursor == "next-page"
        assert [media.pk for media in medias] == ["1"]

    async def test_user_clips_paginated_v1_sends_page_size_and_cursor(self):
        client = Client()
        payload = UsertagMediasPaginationRegressionTestCase()._media_v1_payload()
        client.private_request = AsyncMock(
            return_value={"items": [{"media": payload}], "paging_info": {"max_id": "next-page"}}
        )

        medias, end_cursor = await client.user_clips_paginated_v1("123", amount=8, end_cursor="cursor-1")

        client.private_request.assert_awaited_once_with(
            "clips/user/",
            data={
                "target_user_id": 123,
                "max_id": "cursor-1",
                "page_size": 8,
                "include_feed_video": "true",
            },
        )
        assert end_cursor == "next-page"
        assert [media.pk for media in medias] == ["1"]


class MediaInfoGraphQLRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    def _media_gql_payload(self):
        return {
            "__typename": "GraphImage",
            "id": "1",
            "shortcode": "abc",
            "taken_at_timestamp": 1710000000,
            "owner": {
                "id": "2",
                "username": "example",
                "profile_pic_url": "https://example.com/profile.jpg",
            },
            "display_resources": [{"src": "https://example.com/x.jpg", "config_width": 100, "config_height": 100}],
            "edge_media_to_comment": {"count": 0},
            "edge_media_preview_like": {"count": 0},
            "edge_media_to_caption": {"edges": []},
            "edge_media_to_tagged_user": {"edges": []},
            "location": None,
        }

    async def test_media_info_gql_falls_back_to_doc_id_endpoint(self):
        client = Client()
        client.public_graphql_request = AsyncMock(side_effect=ClientForbiddenError("blocked"))
        client.public_doc_id_graphql_request = AsyncMock(
            return_value={"xdt_shortcode_media": self._media_gql_payload()}
        )
        client.media_info_a1 = AsyncMock(side_effect=AssertionError("a1 should not be used when doc_id works"))

        media = await client.media_info_gql("1")

        client.public_doc_id_graphql_request.assert_awaited_once_with(
            "8845758582119845",
            {"shortcode": "B"},
            referer="https://www.instagram.com/p/B/",
        )
        assert media.pk == "1"


class MediaLikersGraphQLRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_media_likers_gql_chunk_posts_doc_id_query(self):
        client = Client()
        client._fb_dtsg = "token"
        client.graphql_request = AsyncMock(
            return_value={
                "data": {"xdt_api__v1__likes__media_id__likers": {"users": [{"id": "1", "username": "alice"}]}}
            }
        )

        users = await client.media_likers_gql_chunk("123")

        assert users == [{"id": "1", "username": "alice"}]
        data = client.graphql_request.await_args.kwargs["data"]
        assert data["doc_id"] == "24452425501069647"
        assert '"id":"123"' in data["variables"]

    async def test_media_likers_gql_truncates_chunk_without_cursor_unpack(self):
        client = Client()
        client.media_likers_gql_chunk = AsyncMock(
            return_value=[
                {"id": "1", "username": "alice"},
                {"id": "2", "username": "bob"},
            ]
        )

        users = await client.media_likers_gql("123", amount=1)

        assert users == [{"id": "1", "username": "alice"}]
        client.media_likers_gql_chunk.assert_awaited_once_with("123")

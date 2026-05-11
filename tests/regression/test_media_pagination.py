import unittest
from unittest.mock import AsyncMock

from aiograpi import Client
from aiograpi.exceptions import ClientError


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

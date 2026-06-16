import unittest
from unittest.mock import AsyncMock

from aiograpi import Client
from aiograpi.types import Media, UserShort


class FbSearchRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    def _build_client(self):
        client = Client()
        client.__dict__["timezone_offset"] = 10800
        return client

    async def test_search_hashtags_accepts_numeric_private_id(self):
        client = self._build_client()
        client.private_request = AsyncMock(
            return_value={
                "results": [
                    {
                        "id": 17843915557058484,
                        "name": "restaurant",
                        "media_count": 65043150,
                        "profile_pic_url": None,
                    }
                ]
            }
        )

        hashtags = await client.search_hashtags("restaurant")

        self.assertEqual(hashtags[0].id, "17843915557058484")
        self.assertEqual(hashtags[0].name, "restaurant")
        self.assertEqual(hashtags[0].media_count, 65043150)

    async def test_fbsearch_suggested_profiles_extracts_user_short_without_stories(self):
        client = self._build_client()
        client.private_request = AsyncMock(
            return_value={
                "users": [
                    {
                        "pk": "123",
                        "username": "alice",
                        "full_name": "Alice",
                        "profile_pic_url": "https://example.com/alice.jpg",
                        "is_private": False,
                        "has_anonymous_profile_picture": False,
                    }
                ]
            }
        )

        users = await client.fbsearch_suggested_profiles("999")

        client.private_request.assert_awaited_once_with(
            "fbsearch/accounts_recs/",
            params={
                "target_user_id": "999",
                "include_friendship_status": "true",
            },
        )
        self.assertIsInstance(users[0], UserShort)
        self.assertEqual(users[0].pk, "123")
        self.assertEqual(users[0].stories, [])

    async def test_media_search_extracts_media_grid_and_paginates(self):
        client = self._build_client()

        def media(pk):
            return {
                "pk": pk,
                "id": f"{pk}_2",
                "code": f"code-{pk}",
                "taken_at": 1710000000,
                "media_type": 1,
                "user": {
                    "pk": "2",
                    "username": "example",
                    "profile_pic_url": "https://example.com/profile.jpg",
                },
                "image_versions2": {
                    "candidates": [
                        {
                            "url": f"https://example.com/{pk}.jpg",
                            "width": 100,
                            "height": 100,
                        }
                    ]
                },
                "caption": {"text": "space"},
            }

        client.fbsearch_topsearch_v2 = AsyncMock(
            side_effect=[
                {
                    "media_grid": {
                        "sections": [
                            {
                                "layout_content": {
                                    "fill_items": [
                                        {"media": media("1")},
                                        {"media": media("2")},
                                    ]
                                }
                            }
                        ],
                        "has_more": True,
                        "next_max_id": "next-page",
                        "reels_max_id": "next-reels",
                        "rank_token": "next-rank",
                    }
                },
                {
                    "media_grid": {
                        "sections": [
                            {
                                "layout_content": {
                                    "fill_items": [
                                        {"media": media("3")},
                                    ]
                                }
                            }
                        ],
                        "has_more": False,
                    }
                },
            ]
        )

        medias = await client.media_search("space", amount=3)

        self.assertEqual([media.pk for media in medias], ["1", "2", "3"])
        self.assertTrue(all(isinstance(media, Media) for media in medias))
        self.assertEqual(client.fbsearch_topsearch_v2.call_args_list[0].kwargs, {})
        self.assertEqual(
            client.fbsearch_topsearch_v2.call_args_list[1].kwargs,
            {
                "next_max_id": "next-page",
                "reels_max_id": "next-reels",
                "rank_token": "next-rank",
            },
        )

    async def test_media_search_stops_at_amount_without_next_page(self):
        client = self._build_client()

        def media(pk):
            return {
                "pk": pk,
                "id": f"{pk}_2",
                "code": f"code-{pk}",
                "taken_at": 1710000000,
                "media_type": 1,
                "user": {
                    "pk": "2",
                    "username": "example",
                    "profile_pic_url": "https://example.com/profile.jpg",
                },
                "image_versions2": {
                    "candidates": [
                        {
                            "url": f"https://example.com/{pk}.jpg",
                            "width": 100,
                            "height": 100,
                        }
                    ]
                },
                "caption": {"text": "space"},
            }

        client.fbsearch_topsearch_v2 = AsyncMock(
            return_value={
                "media_grid": {
                    "sections": [
                        {
                            "layout_content": {
                                "fill_items": [
                                    {"media": media("1")},
                                    {"media": media("2")},
                                ]
                            }
                        }
                    ],
                    "has_more": True,
                    "next_max_id": "next-page",
                }
            }
        )

        medias = await client.media_search("space", amount=1)

        self.assertEqual([media.pk for media in medias], ["1"])
        client.fbsearch_topsearch_v2.assert_awaited_once_with("space")

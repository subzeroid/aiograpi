import unittest
from unittest import mock
from unittest.mock import AsyncMock

from aiograpi import Client
from aiograpi.exceptions import ClientError, PrivateError
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

    def _media_payload(self, pk):
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

    async def test_media_search_raises_when_media_grid_is_missing(self):
        for payload in ({"status": "ok"}, {"status": "ok", "media_grid": None}):
            with self.subTest(payload=payload):
                client = self._build_client()
                fake_response = mock.Mock(status_code=200)
                client.last_response = fake_response
                with mock.patch.object(client, "fbsearch_topsearch_v2", return_value=payload) as topsearch:
                    with self.assertRaises(PrivateError) as caught:
                        await client.media_search("secret-query")

                self.assertIsInstance(caught.exception, ClientError)
                self.assertIs(caught.exception.response, fake_response)
                self.assertEqual(caught.exception.code, 200)
                self.assertNotIn("secret-query", str(caught.exception))
                topsearch.assert_called_once_with("secret-query")

    async def test_media_search_raises_when_paginated_page_misses_media_grid(self):
        client = self._build_client()
        with mock.patch.object(
            client,
            "fbsearch_topsearch_v2",
            side_effect=[
                {
                    "media_grid": {
                        "sections": [{"layout_content": {"fill_items": [{"media": self._media_payload("1")}]}}],
                        "has_more": True,
                        "next_max_id": "page-2",
                    }
                },
                {"status": "ok"},
            ],
        ) as topsearch:
            with self.assertRaises(PrivateError):
                await client.media_search("space", amount=5)

        self.assertEqual(topsearch.call_count, 2)
        self.assertEqual(topsearch.call_args_list[1].kwargs, {"next_max_id": "page-2"})

    async def test_media_search_raises_on_malformed_response_or_grid(self):
        malformed_payloads = [
            None,
            [],
            {"status": "ok", "media_grid": []},
            {"status": "ok", "media_grid": "invalid"},
            {"status": "ok", "media_grid": {"sections": "invalid"}},
            {"status": "ok", "media_grid": {"sections": 123}},
            {"status": "ok", "media_grid": {"sections": {}}},
        ]
        for payload in malformed_payloads:
            with self.subTest(payload=payload):
                client = self._build_client()
                with mock.patch.object(client, "fbsearch_topsearch_v2", return_value=payload):
                    with self.assertRaises(PrivateError):
                        await client.media_search("space")

    async def test_media_search_returns_empty_list_for_valid_empty_media_grid(self):
        empty_payloads = [
            {"status": "ok", "media_grid": {"sections": [], "has_more": False}},
            {"status": "ok", "media_grid": {}},
            {"status": "ok", "media_grid": {"sections": None, "has_more": False}},
        ]
        for payload in empty_payloads:
            with self.subTest(payload=payload):
                client = self._build_client()
                with mock.patch.object(client, "fbsearch_topsearch_v2", return_value=payload) as topsearch:
                    medias = await client.media_search("space")

                self.assertEqual(medias, [])
                topsearch.assert_called_once_with("space")

    async def test_media_search_extracts_all_grid_section_shapes_without_pagination_metadata(self):
        client = self._build_client()
        payload = {
            "media_grid": {
                "sections": [
                    {
                        "layout_content": {
                            "one_by_two_item": {
                                "media": self._media_payload("1"),
                                "clips": {"items": [{"media": self._media_payload("2")}]},
                            },
                            "fill_items": [{"media": self._media_payload("3")}],
                            "medias": [{"media": self._media_payload("4")}],
                        }
                    }
                ]
            }
        }
        with mock.patch.object(client, "fbsearch_topsearch_v2", return_value=payload) as topsearch:
            medias = await client.media_search("space", amount=10)

        self.assertEqual([media.pk for media in medias], ["1", "2", "3", "4"])
        self.assertTrue(all(isinstance(media, Media) for media in medias))
        topsearch.assert_called_once_with("space")

    async def test_media_search_skips_malformed_nodes_and_sections(self):
        client = self._build_client()
        client.logger = mock.Mock()
        payload = {
            "media_grid": {
                "sections": [
                    "invalid-section",
                    {"layout_content": "invalid-layout"},
                    {
                        "layout_content": {
                            "fill_items": [
                                "invalid-item",
                                {"media": {"pk": "broken"}},
                                {"media": self._media_payload("10")},
                            ]
                        }
                    },
                ],
                "has_more": False,
            }
        }
        with mock.patch.object(client, "fbsearch_topsearch_v2", return_value=payload):
            medias = await client.media_search("space", amount=5)

        self.assertEqual([media.pk for media in medias], ["10"])
        client.logger.warning.assert_called_once()

    async def test_media_search_stops_on_repeated_cursor_and_missing_next_cursor(self):
        client = self._build_client()
        with mock.patch.object(
            client,
            "fbsearch_topsearch_v2",
            side_effect=[
                {
                    "media_grid": {
                        "sections": [{"layout_content": {"fill_items": [{"media": self._media_payload("1")}]}}],
                        "has_more": True,
                        "next_max_id": "cursor-1",
                    }
                },
                {
                    "media_grid": {
                        "sections": [{"layout_content": {"fill_items": [{"media": self._media_payload("2")}]}}],
                        "has_more": True,
                        "next_max_id": "cursor-1",
                    }
                },
                AssertionError("repeated cursor should not trigger another request"),
            ],
        ) as topsearch:
            medias = await client.media_search("space", amount=0)

        self.assertEqual([media.pk for media in medias], ["1", "2"])
        self.assertEqual(topsearch.call_count, 2)

        with mock.patch.object(
            client,
            "fbsearch_topsearch_v2",
            side_effect=[
                {
                    "media_grid": {
                        "sections": [{"layout_content": {"fill_items": [{"media": self._media_payload("3")}]}}],
                        "has_more": True,
                        "next_max_id": "",
                    }
                },
                AssertionError("empty cursor should not trigger another request"),
            ],
        ) as topsearch_empty_cursor:
            medias = await client.media_search("space", amount=0)

        self.assertEqual([media.pk for media in medias], ["3"])
        self.assertEqual(topsearch_empty_cursor.call_count, 1)

    async def test_media_search_stops_a_multi_cursor_cycle(self):
        client = self._build_client()
        pages = [
            {"media_grid": {"sections": [], "has_more": True, "next_max_id": cursor}} for cursor in ("a", "b", "a")
        ]
        pages.append(AssertionError("cursor cycle must stop"))
        with mock.patch.object(client, "fbsearch_topsearch_v2", side_effect=pages) as search:
            self.assertEqual(await client.media_search("space", amount=0), [])
        self.assertEqual(search.call_count, 3)

    async def test_media_search_allows_reels_cursor_progress(self):
        client = self._build_client()
        pages = [
            {"media_grid": {"sections": [], "has_more": True, "next_max_id": "same", "reels_max_id": reels}}
            for reels in ("one", "two")
        ]
        pages.append({"media_grid": {"sections": [], "has_more": False}})
        with mock.patch.object(client, "fbsearch_topsearch_v2", side_effect=pages) as search:
            self.assertEqual(await client.media_search("space", amount=0), [])
        self.assertEqual(search.call_count, 3)
        self.assertEqual(search.call_args_list[2].kwargs, {"next_max_id": "same", "reels_max_id": "two"})

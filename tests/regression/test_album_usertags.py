import json
import unittest
from unittest.mock import AsyncMock

from aiograpi import Client
from aiograpi.extractors import extract_media_v1
from aiograpi.types import UserShort, Usertag


def _build_client():
    client = Client()
    client.settings = {}
    client._user_id = "1"
    client.uuid = "uuid"
    client.android_device_id = "device"
    client.client_session_id = "client-session"
    client.timezone_offset = 0
    client.last_json = {}
    client.last_response = None
    client.set_device({})
    client.with_default_data = lambda data: data
    return client


def _media_payload():
    return {
        "pk": "1",
        "id": "1_1",
        "code": "abc",
        "taken_at": 1710000000,
        "media_type": 8,
        "caption": {"text": "caption"},
        "user": {
            "pk": "1",
            "username": "example",
            "profile_pic_url": "https://example.com/profile.jpg",
        },
        "like_count": 0,
        "carousel_media": [
            {
                "pk": "10",
                "id": "10_2",
                "media_type": 1,
                "image_versions2": {
                    "candidates": [{"url": "https://example.com/one.jpg", "width": 100, "height": 100}],
                },
                "usertags": {
                    "in": [
                        {
                            "user": {
                                "pk": "100",
                                "username": "first",
                                "profile_pic_url": "https://example.com/first.jpg",
                            },
                            "position": [0.25, 0.75],
                        }
                    ]
                },
            },
            {
                "pk": "20",
                "id": "20_2",
                "media_type": 1,
                "image_versions2": {
                    "candidates": [{"url": "https://example.com/two.jpg", "width": 100, "height": 100}],
                },
                "usertags": {
                    "in": [
                        {
                            "user": {
                                "pk": "200",
                                "username": "second",
                                "profile_pic_url": "https://example.com/second.jpg",
                            },
                            "position": [0.5, 0.5],
                        }
                    ]
                },
            },
        ],
    }


class AlbumUsertagsRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_album_configure_assigns_nested_usertags_by_carousel_index(self):
        client = _build_client()
        first_user = UserShort(pk="10", username="first")
        second_user = UserShort(pk="20", username="second")
        children = [{"upload_id": "1"}, {"upload_id": "2"}]
        client.private_request = AsyncMock(return_value={"status": "ok"})

        await client.album_configure(
            children,
            "caption",
            usertags=[
                [Usertag(user=first_user, x=0.25, y=0.75)],
                [Usertag(user=second_user, x=0.5, y=0.5)],
            ],
        )

        metadata = client.private_request.call_args.args[1]["children_metadata"]
        first_tags = json.loads(metadata[0]["usertags"])
        second_tags = json.loads(metadata[1]["usertags"])
        self.assertEqual(first_tags, {"in": [{"user_id": "10", "position": [0.25, 0.75]}]})
        self.assertEqual(second_tags, {"in": [{"user_id": "20", "position": [0.5, 0.5]}]})

    async def test_album_configure_keeps_flat_usertags_on_first_carousel_item(self):
        client = _build_client()
        user = UserShort(pk="10", username="first")
        children = [{"upload_id": "1"}, {"upload_id": "2"}]
        client.private_request = AsyncMock(return_value={"status": "ok"})

        await client.album_configure(children, "caption", usertags=[Usertag(user=user, x=0.25, y=0.75)])

        metadata = client.private_request.call_args.args[1]["children_metadata"]
        first_tags = json.loads(metadata[0]["usertags"])
        self.assertEqual(first_tags, {"in": [{"user_id": "10", "position": [0.25, 0.75]}]})
        self.assertNotIn("usertags", metadata[1])

    async def test_extract_media_v1_preserves_album_resource_usertags(self):
        media = extract_media_v1(_media_payload())

        self.assertEqual(media.resources[0].usertags[0].user.pk, "100")
        self.assertEqual(media.resources[0].usertags[0].x, 0.25)
        self.assertEqual(media.resources[1].usertags[0].user.pk, "200")
        self.assertEqual(media.resources[1].usertags[0].y, 0.5)

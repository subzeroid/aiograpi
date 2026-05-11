import json
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from aiograpi import Client
from aiograpi.types import Location, StoryLocation


def _build_client():
    client = Client()
    client.settings = {}
    client._user_id = "1"
    client.uuid = "uuid"
    client.android_device_id = "device"
    client.client_session_id = "client-session"
    client.timezone_offset = 0
    client.set_device({})
    client.with_default_data = lambda data: data
    return client


def _build_location():
    return Location(
        pk=213597007,
        name="Palace Square",
        address="Palace Square, Saint Petersburg",
        lat=59.939166,
        lng=30.315833,
        external_id=107617247320879,
        external_id_source="facebook_places",
    )


def _assert_story_location_model(data):
    assert data["story_sticker_ids"] == "location_sticker"
    tap_models = json.loads(data["tap_models"])
    assert len(tap_models) == 1
    location_model = tap_models[0]
    assert location_model["type"] == "location"
    assert location_model["is_sticker"] is True
    assert location_model["tap_state"] == 0
    assert location_model["tap_state_str_id"] == "location_sticker_vibrant"
    assert "location" not in location_model
    assert location_model["location_id"] == "107617247320879"


class StoryConfigureRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_photo_story_location_uses_external_location_id_tap_model(self):
        client = _build_client()
        location = _build_location()
        client.location_complete = AsyncMock(return_value=location)
        client.private_request = AsyncMock(return_value={"status": "ok"})

        await client.photo_configure_to_story(
            upload_id="1",
            width=720,
            height=1280,
            caption="",
            locations=[
                StoryLocation(
                    location=location,
                    x=0.2,
                    y=0.3,
                    width=0.4,
                    height=0.1,
                )
            ],
        )

        endpoint, data = client.private_request.call_args.args
        assert endpoint == "media/configure_to_story/"
        _assert_story_location_model(data)

    async def test_video_story_location_uses_external_location_id_tap_model(self):
        client = _build_client()
        location = _build_location()
        client.location_complete = AsyncMock(return_value=location)
        client.private_request = AsyncMock(return_value={"status": "ok"})
        client.photo_rupload = AsyncMock(return_value=("1", 720, 1280))

        await client.video_configure_to_story(
            upload_id="1",
            width=720,
            height=1280,
            duration=3,
            thumbnail=Path("thumbnail.jpg"),
            caption="",
            locations=[
                StoryLocation(
                    location=location,
                    x=0.2,
                    y=0.3,
                    width=0.4,
                    height=0.1,
                )
            ],
        )

        endpoint, data = client.private_request.call_args.args
        assert endpoint == "media/configure_to_story/?video=1"
        _assert_story_location_model(data)

import json
from copy import deepcopy
from unittest import IsolatedAsyncioTestCase, mock

import httpx
import pytest
from pydantic import ValidationError

from aiograpi import Client
from aiograpi.extractors import extract_media_v1


def media_payload(pk="1"):
    return {
        "pk": pk,
        "id": f"{pk}_2",
        "code": "example",
        "taken_at": 1,
        "media_type": 1,
        "user": {"pk": "2", "username": "example", "profile_pic_url": "https://example.com/avatar.jpg"},
    }


def test_extract_media_v1_normalizes_null_crosspost_without_mutating_payload():
    payload = media_payload()
    payload["crosspost"] = None
    original = deepcopy(payload)

    media = extract_media_v1(payload)

    assert media.crosspost == []
    assert media.model_dump()["crosspost"] == []
    assert payload == original


@pytest.mark.parametrize("destinations", [[], ["FB", "IG", "THREADS"]])
def test_extract_media_v1_preserves_crosspost_destinations(destinations):
    payload = media_payload()
    payload["crosspost"] = destinations

    media = extract_media_v1(payload)

    assert media.crosspost == destinations
    assert payload["crosspost"] == destinations


def test_extract_media_v1_still_rejects_invalid_crosspost():
    payload = media_payload()
    payload["crosspost"] = False

    with pytest.raises(ValidationError) as error:
        extract_media_v1(payload)

    assert error.value.errors()[0]["loc"] == ("crosspost",)


def incremental_timeline_body():
    timeline = {
        "profile_grid_items": [{"media": media_payload(str(index + 1))} for index in range(3)],
        "more_available": True,
        "next_max_id": "next-page",
    }
    chunks = [{"data": {"xdt_api__v1__profile_timeline": timeline}, "status": "ok"}]
    for index in (2, 0, 1):
        chunks.append(
            {
                "path": ["xdt_api__v1__profile_timeline", "profile_grid_items", index, "media"],
                "data": {"crosspost": None},
            }
        )
    return "\n".join(json.dumps(chunk) for chunk in chunks).encode()


class MediaCrosspostTimelineRegressionTestCase(IsolatedAsyncioTestCase):
    async def test_user_medias_gql_accepts_null_crosspost_in_incremental_timeline(self):
        client = Client()
        for session in (client.public, client.private, client.graphql):
            self.addAsyncCleanup(session._client.aclose)
        response = httpx.Response(
            200,
            request=httpx.Request("POST", "https://i.instagram.com/graphql/query"),
            content=incremental_timeline_body(),
        )
        client.private.post = mock.AsyncMock(return_value=response)
        client.request_log = mock.Mock()
        client.public_graphql_request = mock.AsyncMock(side_effect=AssertionError("unexpected fallback"))

        medias = await client.user_medias_gql("2", amount=3, sleep=1)

        self.assertEqual([media.pk for media in medias], ["1", "2", "3"])
        self.assertEqual([media.crosspost for media in medias], [[], [], []])
        client.private.post.assert_awaited_once()
        client.public_graphql_request.assert_not_called()

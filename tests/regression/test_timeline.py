import unittest
from unittest.mock import AsyncMock

from aiograpi import Client


class TimelineRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_friends_reels_uses_social_discover_endpoint(self):
        client = Client()
        client.private_request = AsyncMock(
            return_value={
                "items": [],
                "paging_info": {"more_available": False},
            }
        )

        result = await client.friends_reels(amount=1)

        assert result == []
        client.private_request.assert_awaited_once_with(
            "clips/discover/social/",
            data=" ",
            params={"max_id": ""},
        )

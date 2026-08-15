import unittest
from unittest.mock import AsyncMock, Mock, patch

from aiograpi.exceptions import ClientBadRequestError, ClientError
from tests.live import test_upload


class _DestinationClient:
    def __init__(self, destination=None):
        self.destination = destination

    async def clip_share_to_fb_destination(self):
        if self.destination is None:
            raise ClientError("not linked")
        return self.destination


class _BrokenDestinationClient:
    async def clip_share_to_fb_destination(self):
        raise RuntimeError("parser bug")


class _BadRequestDestinationClient:
    async def clip_share_to_fb_destination(self):
        raise ClientBadRequestError("HTTP 400")


class _ServerErrorDestinationClient:
    async def clip_share_to_fb_destination(self):
        raise ClientError("HTTP 500", response=Mock(status_code=500))


class LiveUploadAccountSelectionRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_linked_destination_selection_continues_after_usable_unlinked_account(self):
        unlinked = _DestinationClient()
        linked_destination = {"destination_id": "123", "destination_type": "USER"}
        linked = _DestinationClient(linked_destination)
        accounts = [{"username": "linked"}]

        with patch.object(
            test_upload,
            "_client_from_test_account",
            new=AsyncMock(return_value=linked),
        ) as login:
            client, destination = await test_upload._client_with_destination(
                accounts,
                "clip_share_to_fb_destination",
                initial_client=unlinked,
            )

        self.assertIs(client, linked)
        self.assertEqual(destination, linked_destination)
        login.assert_awaited_once_with(accounts[0])

    async def test_linked_destination_selection_does_not_hide_unexpected_errors(self):
        with self.assertRaisesRegex(RuntimeError, "parser bug"):
            await test_upload._client_with_destination(
                [],
                "clip_share_to_fb_destination",
                initial_client=_BrokenDestinationClient(),
            )

    async def test_linked_destination_selection_does_not_hide_request_errors(self):
        with self.assertRaisesRegex(ClientBadRequestError, "HTTP 400"):
            await test_upload._client_with_destination(
                [],
                "clip_share_to_fb_destination",
                initial_client=_BadRequestDestinationClient(),
            )

    async def test_linked_destination_selection_does_not_hide_response_backed_base_errors(self):
        with self.assertRaisesRegex(ClientError, "HTTP 500"):
            await test_upload._client_with_destination(
                [],
                "clip_share_to_fb_destination",
                initial_client=_ServerErrorDestinationClient(),
            )

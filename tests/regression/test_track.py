import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from aiograpi import Client


class TrackMixinRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_track_download_by_url_uses_httpx_request(self):
        client = Client()
        client.request_timeout = 7
        response = Mock()
        response.read.return_value = b"track-bytes"

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("aiograpi.mixins.track.httpx_ext.request", new=AsyncMock(return_value=response)) as request:
                path = await client.track_download_by_url(
                    "https://example.com/audio/test-track.mp3",
                    folder=Path(temp_dir),
                )
                self.assertEqual(path.read_bytes(), b"track-bytes")

        request.assert_awaited_once_with("GET", "https://example.com/audio/test-track.mp3", timeout=7)
        response.raise_for_status.assert_called_once_with()
        self.assertEqual(path.name, "test-track.mp3")

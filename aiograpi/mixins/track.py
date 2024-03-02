from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse

from aiograpi import reqwests
from aiograpi.exceptions import ClientError, TrackNotFound


class TrackMixin:
    async def track_download_by_url(
        self, url: str, filename: str = "", folder: Path = ""
    ) -> Path:
        """
        Download track by URL

        Parameters
        ----------
        url: str
            URL for a track
        filename: str, optional
            Filename for the track
        folder: Path, optional
            Directory in which you want to download the track, default
            is "" and will download the files to working directory

        Returns
        -------
        Path
            Path for the file downloaded
        """
        fname = urlparse(url).path.rsplit("/", 1)[1].strip()
        if not fname:
            raise Exception("The URL must contain the path to the file (m4a or mp3).")
        filename = "%s.%s" % (filename, fname.rsplit(".", 1)[1]) if filename else fname
        path = Path(folder) / filename
        response = await reqwests.get(url, timeout=self.request_timeout)
        response.raise_for_status()
        with open(path, "wb") as f:
            f.write(response.read())
        return path.resolve()

    async def _track_request(self, data: Dict[str, Any]) -> Dict:
        try:
            result = await self.private_request("clips/music/", data)
        except ClientError as e:
            if not self.last_json:
                kw = {
                    k: v
                    for k, v in data.items()
                    if k in {"music_canonical_id", "original_sound_audio_asset_id"}
                }
                raise TrackNotFound(**kw)
            raise e
        return result

    async def track_info_by_canonical_id(self, music_canonical_id: str) -> Dict:
        """
        Get Track by music_canonical_id

        Parameters
        ----------
        music_canonical_id: str
            Unique identifier of the track

        Returns
        -------
        Dict
            Raw insta response json
        """
        data = {
            "tab_type": "clips",
            "referrer_media_id": "",
            "_uuid": self.uuid,
            "music_canonical_id": str(music_canonical_id),
        }
        return await self._track_request(data)

    async def track_info_by_id(self, track_id: str, max_id: str = "") -> Dict:
        """
        Get Track by id

        Parameters
        ----------
        track_id: str
            Unique identifier of the track

        Returns
        -------
        Dict
            Raw insta response json
        """
        data = {
            "audio_cluster_id": track_id,
            "original_sound_audio_asset_id": track_id,
        }
        if max_id:
            data["max_id"] = max_id
        return await self._track_request(data)

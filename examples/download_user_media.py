from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from _common import env_int, make_client


async def download_media(username: str, amount: int, folder: Path) -> list[Path]:
    cl = await make_client()
    folder.mkdir(parents=True, exist_ok=True)

    user_id = await cl.user_id_from_username(username)
    downloaded: list[Path] = []
    for media in await cl.user_medias(user_id, amount=amount):
        if media.media_type == 1:
            downloaded.append(await cl.photo_download(media.pk, folder=folder))
        elif media.media_type == 2:
            downloaded.append(await cl.video_download(media.pk, folder=folder))
        elif media.media_type == 8:
            downloaded.extend(await cl.album_download(media.pk, folder=folder))
    return downloaded


async def main() -> None:
    parser = argparse.ArgumentParser(description="Download recent media for an Instagram username.")
    parser.add_argument("username")
    parser.add_argument("--amount", type=int, default=env_int("IG_AMOUNT", 10))
    parser.add_argument("--folder", type=Path, default=Path("downloads"))
    args = parser.parse_args()

    for path in await download_media(args.username, args.amount, args.folder):
        print(path)


if __name__ == "__main__":
    asyncio.run(main())

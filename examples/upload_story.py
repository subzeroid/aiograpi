from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from _common import env, make_client

from aiograpi.types import StoryLink


async def upload_story(
    kind: str,
    path: Path,
    caption: str,
    thumbnail: Path | None = None,
    link: str | None = None,
    resize_mode: str = "fill",
):
    cl = await make_client()
    links = [StoryLink(webUri=link)] if link else []

    if kind == "photo":
        return await cl.photo_upload_to_story(path, caption=caption, links=links, resize_mode=resize_mode)
    if kind == "video":
        return await cl.video_upload_to_story(
            path,
            caption=caption,
            thumbnail=thumbnail,
            links=links,
            resize_mode=resize_mode,
        )

    raise ValueError(f"Unsupported story kind: {kind}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Upload a photo or video story.")
    parser.add_argument("kind", choices=["photo", "video"])
    parser.add_argument("path", type=Path)
    parser.add_argument("--caption", default=env("IG_CAPTION", ""))
    parser.add_argument("--thumbnail", type=Path, default=None)
    parser.add_argument("--link", default=env("IG_STORY_LINK"))
    parser.add_argument("--resize-mode", choices=["fill", "fit"], default="fill")
    args = parser.parse_args()

    story = await upload_story(args.kind, args.path, args.caption, args.thumbnail, args.link, args.resize_mode)
    print(f"Uploaded story {story.pk}")


if __name__ == "__main__":
    asyncio.run(main())

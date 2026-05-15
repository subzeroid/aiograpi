from __future__ import annotations

import argparse
import asyncio

from _common import env, make_client, parse_ids


async def send_direct(text: str, user_ids: list[int], thread_ids: list[int]):
    if bool(user_ids) == bool(thread_ids):
        raise SystemExit("Pass exactly one of --user-ids or --thread-ids.")

    cl = await make_client()
    return await cl.direct_send(text, user_ids=user_ids, thread_ids=thread_ids)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Send a Direct text message.")
    parser.add_argument("--text", default=env("IG_DIRECT_TEXT", "Hello from aiograpi"))
    parser.add_argument("--user-ids", default=env("IG_DIRECT_USER_IDS"))
    parser.add_argument("--thread-ids", default=env("IG_DIRECT_THREAD_IDS"))
    args = parser.parse_args()

    message = await send_direct(
        args.text,
        user_ids=parse_ids(args.user_ids),
        thread_ids=parse_ids(args.thread_ids),
    )
    print(f"Sent direct message {message.id}")


if __name__ == "__main__":
    asyncio.run(main())

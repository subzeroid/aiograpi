from __future__ import annotations

import argparse
import asyncio
import json

from _common import env_int, make_client


async def receive_direct_messages(limit: int = 1):
    cl = await make_client()
    received = []

    def handle_message(payload):
        received.append(payload)
        print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))

    cl.realtime_on("message", handle_message)
    rt = await cl.realtime_connect()
    await rt.direct_subscribe()

    try:
        while limit <= 0 or len(received) < limit:
            await cl.realtime_read_once()
    finally:
        await cl.realtime_disconnect()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Receive Direct message sync payloads over Realtime MQTT.")
    parser.add_argument(
        "--limit",
        type=int,
        default=env_int("IG_REALTIME_DIRECT_LIMIT", 1),
        help="Number of message payloads to print. Use 0 to run until interrupted.",
    )
    args = parser.parse_args()

    await receive_direct_messages(limit=args.limit)


if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import os


class FreshAccountLoginTimeout(RuntimeError):
    pass


def live_login_timeout_seconds():
    value = os.getenv("AIOGRAPI_TEST_LOGIN_TIMEOUT", os.getenv("INSTAGRAPI_TEST_LOGIN_TIMEOUT", "30"))
    try:
        return float(value)
    except ValueError:
        return 30.0


async def login_with_timeout(client, **login_kwargs):
    seconds = live_login_timeout_seconds()
    if seconds <= 0:
        return await client.login(**login_kwargs)
    try:
        return await asyncio.wait_for(client.login(**login_kwargs), timeout=seconds)
    except asyncio.TimeoutError as exc:
        raise FreshAccountLoginTimeout(f"Fresh account login timed out after {seconds:g}s") from exc

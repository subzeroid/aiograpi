# aiograpi Examples

These scripts are small runnable starting points for common `aiograpi` tasks.
They keep credentials out of source code and use environment variables so they can be copied into applications without
hard-coded secrets.

## Setup

Install the package and export credentials:

```bash
python -m pip install -U aiograpi

export IG_USERNAME="your_username"
export IG_PASSWORD="your_password"
export IG_SESSION_FILE="./ig_settings.json"
```

Optional settings:

```bash
export IG_PROXY="http://user:pass@host:port"
export IG_PUBLIC_TRANSPORT="curl"
export IG_PUBLIC_TRANSPORT_IMPERSONATE="chrome136"
```

`IG_SESSION_FILE` is reused between runs. Keep that file private; it contains session data.

## Scripts

| Script | Purpose |
| --- | --- |
| [`_common.py`](_common.py) | Shared async login, proxy, session, and environment helpers used by the examples. |
| [`diagnose_login.py`](diagnose_login.py) | Standalone async login diagnostic with a shareable sanitized report. |
| [`public_lookup.py`](public_lookup.py) | Public profile lookup with optional `public_transport="curl"`. |
| [`download_user_media.py`](download_user_media.py) | Login, list recent media for a username, and download photos/videos/albums. |
| [`upload_media.py`](upload_media.py) | Upload a feed photo, feed video, Reel, or Trial Reel. |
| [`upload_story.py`](upload_story.py) | Upload a photo or video story, optionally with a link sticker. |
| [`direct_message.py`](direct_message.py) | Send a Direct text message to user IDs or thread IDs. |
| [`realtime_direct.py`](realtime_direct.py) | Receive Direct message sync payloads over Realtime MQTT. |

## Login diagnostics

Download [`diagnose_login.py`](diagnose_login.py) and run it with the same Python environment and aiograpi version as the failing script. It is standalone and does not need [`_common.py`](_common.py):

```bash
python diagnose_login.py --settings session.json --report login-diagnostic.json
python diagnose_login.py --settings session.json --report login-diagnostic.json --relogin --proxy --two-factor
```

From a repository checkout, use `python examples/diagnose_login.py` instead. Credentials come from `IG_USERNAME` and `IG_PASSWORD` or interactive input; `--proxy` and `--two-factor` prompt privately for the existing proxy and a current verification code. `IG_PROXY` is used when `--proxy` is absent. Keep the account's existing settings and proxy. `--relogin` requests password login even when a saved session is authorized. For saved `private_transport="utls"` settings, supply `--utls-library-path` for the already verified local native build; the path stays private.

The CLI calls high-level `login()` once, disables transport retries, sets bounded timeouts, and stops automatic code and password callbacks. That login can perform its normal CAA, verification, saved-session validation and legacy fallback requests. Private uTLS uses a 30-second total request deadline; HTTPX/curl use a 10-second connect budget and a 30-second read budget. Settings are updated even after failure, retaining saved retry preferences. Settings and reports are replaced atomically with mode 0600. The CLI closes its owned sessions, including after cancellation.

Review `login-diagnostic.json` before sharing it. Keep `session.json` private: it contains session credentials. The report retains response order, fixed error categories, and CAA outcomes captured before fallback replaces state. Bloks markers and dialog labels indicate references. Their presence and HTTP 200 responses do not establish an executed callback, accepted verification code, valid credentials, or a usable session.

For an application using the repository example, await `diagnose()` from a dedicated client/process:

```python
import asyncio
import os

from aiograpi import Client
from examples.diagnose_login import diagnose


async def main():
    client = Client()
    async with client.private, client.public, client.graphql:
        report = await diagnose(client, os.environ["IG_USERNAME"], os.environ["IG_PASSWORD"])
    print(report["outcome"])


asyncio.run(main())
```

The reusable helper restores its temporary request methods, exception handler and challenge callbacks after errors or cancellation. Cancellation propagates to the caller. The caller owns session cleanup and settings persistence. Output and library logging are suppressed process-wide while observing the attempt; avoid concurrent work in that process.

## Public lookup

```bash
python examples/public_lookup.py instagram
IG_PUBLIC_TRANSPORT=curl python examples/public_lookup.py instagram
```

## Download media

```bash
python examples/download_user_media.py instagram --amount 5 --folder ./downloads
```

## Upload media

```bash
python examples/upload_media.py photo ./photo.jpg --caption "Hello from aiograpi"
python examples/upload_media.py video ./video.mp4 --thumbnail ./thumb.jpg --caption "Feed video"
python examples/upload_media.py reel ./reel.mp4 --thumbnail ./thumb.jpg --caption "Reel"
python examples/upload_media.py trial-reel ./reel.mp4 --thumbnail ./thumb.jpg --caption "Trial Reel"
```

For Android/Pydroid environments, pass `--thumbnail` for videos and Reels or configure executable `ffmpeg`.

## Upload story

```bash
python examples/upload_story.py photo ./story.jpg --caption "Story"
python examples/upload_story.py video ./story.mp4 --thumbnail ./thumb.jpg --link https://github.com/subzeroid/aiograpi
```

Story assets should usually be 9:16, for example 720x1280.

## Direct message

```bash
python examples/direct_message.py --user-ids 123456789 --text "Hello"
python examples/direct_message.py --thread-ids 340282366841710301949128122292511813703 --text "Hello thread"
```

Use exactly one target type: `--user-ids` or `--thread-ids`.

## Realtime Direct MQTT

```bash
python examples/realtime_direct.py --limit 1
IG_REALTIME_DIRECT_LIMIT=0 python examples/realtime_direct.py
```

The script logs in, subscribes to Direct message sync over Realtime MQTT, and prints received payloads as JSON.

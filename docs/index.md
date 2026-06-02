# aiograpi

### We recommend using our services:

* [LamaTok](https://lamatok.com/p/X0HatoxX) for TikTok API 🔥
* [HikerAPI](https://hikerapi.com/p/KhMxYMSn) for Instagram API ⚡⚡⚡
* [DataLikers](https://datalikers.com/p/XPhrh0Y3) for Instagram Datasets 🚀

[![Package](https://github.com/subzeroid/aiograpi/actions/workflows/python-package.yml/badge.svg?branch=main)](https://github.com/subzeroid/aiograpi/actions/workflows/python-package.yml)
[![PyPI](https://img.shields.io/pypi/v/aiograpi)][pypi]
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/aiograpi)][pypi]

Asynchronous Instagram Private API wrapper without selenium. Use the most recent version of the API from Instagram, which was obtained using [reverse-engineering with Charles Proxy](https://github.com/subzeroid/instagrapi/discussions/1182) and [Proxyman](https://proxyman.io/).

Support **Python >= 3.10**

Video uploads can use a built-in MP4 metadata parser when you provide `thumbnail=...`. Automatic thumbnail generation, `StoryBuilder`, and video/audio composition still need the optional video dependencies, MoviePy `2.2.1`, and executable `ffmpeg`:

```bash
pip install "aiograpi[video]"
pip install --no-deps "moviepy==2.2.1"
```

MoviePy `2.2.1` currently declares `Pillow<12`, but aiograpi keeps `Pillow>=12.2.0` for security fixes; the `--no-deps` install keeps the safe Pillow version. If your project imports MoviePy directly, migrate any MoviePy `1.x` code from `moviepy.editor`, `set_*`, `resize`, and `subclip` APIs to the MoviePy `2.x` API before upgrading.

Android users should see [Pydroid and ffmpeg](usage-guide/pydroid.md) and [Termux](usage-guide/termux.md).

For any other languages (e.g. C++, C#, F#, D, [Golang](https://github.com/subzeroid/instagrapi-rest/tree/main/golang), Erlang, Elixir, Nim, Haskell, Lisp, Closure, Julia, R, Java, Kotlin, Scala, OCaml, JavaScript, Crystal, Ruby, Rust, [Swift](https://github.com/subzeroid/instagrapi-rest/tree/main/swift), Objective-C, Visual Basic, .NET, Pascal, Perl, Lua, PHP and others), I suggest using [instagrapi-rest](https://github.com/subzeroid/instagrapi-rest)

[Support Chat in Telegram](https://t.me/aiograpi_support)
![](https://gist.githubusercontent.com/m8rge/4c2b36369c9f936c02ee883ca8ec89f1/raw/c03fd44ee2b63d7a2a195ff44e9bb071e87b4a40/telegram-single-path-24px.svg) and [GitHub Discussions](https://github.com/subzeroid/aiograpi/discussions)

## Features

1. Performs [Public API](https://subzeroid.github.io/aiograpi/latest/usage-guide/fundamentals/) (web, anonymous) or [Private API](https://subzeroid.github.io/aiograpi/latest/usage-guide/fundamentals/) (mobile app, authorized) requests depending on the situation (to avoid Instagram limits)
2. [Login](https://subzeroid.github.io/aiograpi/latest/usage-guide/interactions/) by username and password, including 2FA, 8-digit backup codes, [Bloks 2FA](usage-guide/totp.md#bloks-two-factor-flow) fallback/helpers, and by sessionid
3. [Challenge Resolver](https://subzeroid.github.io/aiograpi/latest/usage-guide/challenge_resolver/) have Email and SMS handlers
4. Support [upload](https://subzeroid.github.io/aiograpi/latest/usage-guide/media/) a Photo, Video, IGTV, Reels, Albums, Stories and Trial Reels
5. Support work with [User](https://subzeroid.github.io/aiograpi/latest/usage-guide/user/), [Media](https://subzeroid.github.io/aiograpi/latest/usage-guide/media/), [Comment](https://subzeroid.github.io/aiograpi/latest/usage-guide/comment/), [Insights](https://subzeroid.github.io/aiograpi/latest/usage-guide/insight/), [Collections](https://subzeroid.github.io/aiograpi/latest/usage-guide/collection/), [Location](https://subzeroid.github.io/aiograpi/latest/usage-guide/location/) (Place), [Hashtag](https://subzeroid.github.io/aiograpi/latest/usage-guide/hashtag/) and [Direct Message](https://subzeroid.github.io/aiograpi/latest/usage-guide/direct/) objects
6. [Like](https://subzeroid.github.io/aiograpi/latest/usage-guide/media/), [Follow](https://subzeroid.github.io/aiograpi/latest/usage-guide/user/), [Edit account](https://subzeroid.github.io/aiograpi/latest/usage-guide/account/) (Bio) and much more else
7. [Insights](https://subzeroid.github.io/aiograpi/latest/usage-guide/insight/) by account, posts and stories
8. [Build stories](https://subzeroid.github.io/aiograpi/latest/usage-guide/story/) with custom background, font animation, link sticker and mention users
9. [Realtime MQTT](usage-guide/realtime.md) for Direct message sync, lightweight Direct MQTT actions, and FBNS push notifications
10. Account registration helpers and opt-in captcha handler hooks

## Example

### Realtime MQTT and Direct

`aiograpi 1.1.0` adds experimental async Realtime MQTT/MQTToT helpers. They can receive Direct message sync payloads,
publish lightweight Direct actions over MQTT, and subscribe to FBNS push notifications.

```python
from aiograpi import Client

cl = Client()
await cl.login(USERNAME, PASSWORD)


def handle_message(payload):
    print(payload)


cl.realtime_on("message", handle_message)
rt = await cl.realtime_connect()
await rt.direct_subscribe()

await rt.direct_send_text(thread_id, "Hello from MQTT")

while True:
    await cl.realtime_read_once()
```

See the [Realtime MQTT guide](usage-guide/realtime.md) for Direct sync, MQTT Direct actions, and FBNS push examples.

### Basic Usage

``` python
from aiograpi import Client

cl = Client()
await cl.login(ACCOUNT_USERNAME, ACCOUNT_PASSWORD)

user_id = await cl.user_id_from_username("example")
medias = await cl.user_medias(user_id, 20)
```

#### The full example

``` python
from aiograpi import Client
from aiograpi.types import StoryMention, StoryMedia, StoryLink, StoryHashtag

cl = Client()
await cl.login(USERNAME, PASSWORD, verification_code="<2FA CODE HERE>")

media_pk = await cl.media_pk_from_url('https://www.instagram.com/p/CGgDsi7JQdS/')
media_path = await cl.video_download(media_pk)
example = await cl.user_info_by_username('example')
hashtag = await cl.hashtag_info('dhbastards')

await cl.video_upload_to_story(
    media_path,
    "Credits @example",
    mentions=[StoryMention(user=example, x=0.49892962, y=0.703125, width=0.8333333333333334, height=0.125)],
    links=[StoryLink(webUri='https://github.com/subzeroid/aiograpi')],
    hashtags=[StoryHashtag(hashtag=hashtag, x=0.23, y=0.32, width=0.5, height=0.22)],
    medias=[StoryMedia(media_pk=media_pk, x=0.5, y=0.5, width=0.6, height=0.8)]
)
```

### Requests

* `Public` or `Graphql` (anonymous request via web api) methods have a suffix `_gql`
* `Private` (authorized request via mobile api) methods have `_v1` suffix

The first request to fetch media/user is `public` (anonymous), if instagram raise exception, then use `private` (authorized). Example (pseudo-code):

``` python
async def media_info(media_pk):
    try:
        return await self.media_info_gql(media_pk)
    except ClientError as e:
        # Restricted Video: This video is not available in your country.
        # Or media from private account
        return await self.media_info_v1(media_pk)
```

## Detailed Documentation

To learn more about the various ways `aiograpi` can be used, read the [Usage Guide](usage-guide/fundamentals.md) page.

* [Getting Started](getting-started.md)
* [Runnable Examples](usage-guide/examples.md)
* [Usage Guide](usage-guide/fundamentals.md)
* [Interactions](usage-guide/interactions.md)
  * [`Media`](usage-guide/media.md) - Publication (also called post): Photo, Video, Album, IGTV and Reels
  * [`Resource`](usage-guide/media.md) - Part of Media (for albums)
  * [`MediaOembed`](usage-guide/media.md) - Short version of Media
  * [`Account`](usage-guide/account.md) - Full private info for your account (e.g. email, phone_number)
  * [`TOTP`](usage-guide/totp.md) - 2FA TOTP helpers, code generation, and Bloks verification fallback/helpers
  * [`User`](usage-guide/user.md) - Full public user data
  * [`UserShort`](usage-guide/user.md) - Short public user data (used in Usertag, Comment, Media, Direct Message)
  * [`Usertag`](usage-guide/user.md) - Tag user in Media (coordinates + UserShort)
  * [`Location`](usage-guide/location.md) - GEO location (GEO coordinates, name, address)
  * [`Hashtag`](usage-guide/hashtag.md) - Hashtag object (id, name, picture)
  * [`Collection`](usage-guide/collection.md) - Collection of medias (name, picture and list of medias)
  * [`Comment`](usage-guide/comment.md) - Comments to Media
  * [`Highlight`](usage-guide/highlight.md) - Highlights
  * [`Notes`](usage-guide/notes.md) - Notes
  * [`Realtime MQTT`](usage-guide/realtime.md) - Direct sync, lightweight Direct MQTT actions, and FBNS push callbacks
  * [`Pydroid and ffmpeg`](usage-guide/pydroid.md) - Android/Pydroid video upload setup
  * [`Termux`](usage-guide/termux.md) - Termux install notes and optional video helpers
  * [`Public Transport`](usage-guide/public-transport.md) - Optional curl transport for public web requests
  * [`Story`](usage-guide/story.md) - Story
  * [`StoryLink`](usage-guide/story.md) - Link (Swipe up)
  * [`StoryLocation`](usage-guide/story.md) - Tag Location in Story (as sticker)
  * [`StoryMention`](usage-guide/story.md) - Mention users in Story (user, coordinates and dimensions)
  * [`StoryHashtag`](usage-guide/story.md) - Hashtag for story (as sticker)
  * [`StorySticker`](usage-guide/story.md) - Tag sticker to story (for example from giphy)
  * [`StoryBuild`](usage-guide/story.md) - [StoryBuilder](https://github.com/subzeroid/aiograpi/blob/main/aiograpi/story.py) return path to photo/video and mention co-ordinates
  * [`DirectThread`](usage-guide/direct.md) - Thread (topic) with messages in Direct Message
  * [`DirectMessage`](usage-guide/direct.md) - Message in Direct Message
  * [`Insight`](usage-guide/insight.md) - Insights for a post
  * [`Track`](usage-guide/track.md) - Music track (for Reels/Clips)
* [Best Practices](usage-guide/best-practices.md)
* [Development Guide](development-guide.md)
* [Handle Exceptions](usage-guide/handle_exception.md)
* [Challenge Resolver](usage-guide/challenge_resolver.md)
* [Exceptions](exceptions.md)

[ci]: https://github.com/subzeroid/aiograpi/actions
[pypi]: https://pypi.org/project/aiograpi/

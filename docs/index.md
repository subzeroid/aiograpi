# aiograpi

### We recommend using our services:

* [LamaTok](https://lamatok.com/p/X0HatoxX) for TikTok API 🔥
* [HikerAPI](https://hikerapi.com/p/KhMxYMSn) for Instagram API ⚡⚡⚡
* [DataLikers](https://datalikers.com/p/XPhrh0Y3) for Instagram Datasets 🚀

[![Package](https://github.com/subzeroid/aiograpi/actions/workflows/python-package.yml/badge.svg?branch=main)](https://github.com/subzeroid/aiograpi/actions/workflows/python-package.yml)
[![PyPI](https://img.shields.io/pypi/v/aiograpi)][pypi]
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/aiograpi)][pypi]

Asynchronous Instagram Private API wrapper 2024. Use the most recent version of the API from Instagram, which was obtained using [reverse-engineering with Charles Proxy](https://github.com/subzeroid/instagrapi/discussions/1182) and [Proxyman](https://proxyman.io/).

Support **Python >= 3.10**

For any other languages (e.g. C++, C#, F#, D, [Golang](https://github.com/subzeroid/instagrapi-rest/tree/main/golang), Erlang, Elixir, Nim, Haskell, Lisp, Closure, Julia, R, Java, Kotlin, Scala, OCaml, JavaScript, Crystal, Ruby, Rust, [Swift](https://github.com/subzeroid/instagrapi-rest/tree/main/swift), Objective-C, Visual Basic, .NET, Pascal, Perl, Lua, PHP and others), I suggest using [instagrapi-rest](https://github.com/subzeroid/instagrapi-rest)

[Support Chat in Telegram](https://t.me/aiograpi)
![](https://gist.githubusercontent.com/m8rge/4c2b36369c9f936c02ee883ca8ec89f1/raw/c03fd44ee2b63d7a2a195ff44e9bb071e87b4a40/telegram-single-path-24px.svg) and [GitHub Discussions](https://github.com/subzeroid/aiograpi/discussions)

## Features

1. Performs [Public API](https://subzeroid.github.io/aiograpi/usage-guide/fundamentals.html) (web, anonymous) or [Private API](https://subzeroid.github.io/aiograpi/usage-guide/fundamentals.html) (mobile app, authorized) requests depending on the situation (to avoid Instagram limits)
2. [Login](https://subzeroid.github.io/aiograpi/usage-guide/interactions.html) by username and password, including 2FA and by sessionid
3. [Challenge Resolver](https://subzeroid.github.io/aiograpi/usage-guide/challenge_resolver.html) have Email and SMS handlers
4. Support [upload](https://subzeroid.github.io/aiograpi/usage-guide/media.html) a Photo, Video, IGTV, Reels, Albums and Stories
5. Support work with [User](https://subzeroid.github.io/aiograpi/usage-guide/user.html), [Media](https://subzeroid.github.io/aiograpi/usage-guide/media.html), [Comment](https://subzeroid.github.io/aiograpi/usage-guide/comment.html), [Insights](https://subzeroid.github.io/aiograpi/usage-guide/insight.html), [Collections](https://subzeroid.github.io/aiograpi/usage-guide/collection.html), [Location](https://subzeroid.github.io/aiograpi/usage-guide/location.html) (Place), [Hashtag](https://subzeroid.github.io/aiograpi/usage-guide/hashtag.html) and [Direct Message](https://subzeroid.github.io/aiograpi/usage-guide/direct.html) objects
6. [Like](https://subzeroid.github.io/aiograpi/usage-guide/media.html), [Follow](https://subzeroid.github.io/aiograpi/usage-guide/user.html), [Edit account](https://subzeroid.github.io/aiograpi/usage-guide/account.html) (Bio) and much more else
7. [Insights](https://subzeroid.github.io/aiograpi/usage-guide/insight.html) by account, posts and stories
8. [Build stories](https://subzeroid.github.io/aiograpi/usage-guide/story.html) with custom background, font animation, swipe up link and mention users
9. In the next release, account registration and captcha passing will appear

## Example

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
* [Usage Guide](usage-guide/fundamentals.md)
* [Interactions](usage-guide/interactions.md)
  * [`Media`](usage-guide/media.md) - Publication (also called post): Photo, Video, Album, IGTV and Reels
  * [`Resource`](usage-guide/media.md) - Part of Media (for albums)
  * [`MediaOembed`](usage-guide/media.md) - Short version of Media
  * [`Account`](usage-guide/account.md) - Full private info for your account (e.g. email, phone_number)
  * [`TOTP`](usage-guide/totp.md) - 2FA TOTP helpers (generate seed, enable/disable TOTP, generate code as Google Authenticator)
  * [`User`](usage-guide/user.md) - Full public user data
  * [`UserShort`](usage-guide/user.md) - Short public user data (used in Usertag, Comment, Media, Direct Message)
  * [`Usertag`](usage-guide/user.md) - Tag user in Media (coordinates + UserShort)
  * [`Location`](usage-guide/location.md) - GEO location (GEO coordinates, name, address)
  * [`Hashtag`](usage-guide/hashtag.md) - Hashtag object (id, name, picture)
  * [`Collection`](usage-guide/collection.md) - Collection of medias (name, picture and list of medias)
  * [`Comment`](usage-guide/comment.md) - Comments to Media
  * [`Highlight`](usage-guide/highlight.md) - Highlights
  * ['Notes'](usage-guide/notes.md) - Notes
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

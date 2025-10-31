# aiograpi - Asynchronous Instagram API for Python

If you want to work with aiograpi (business interests), we strongly advise you to prefer [HikerAPI](https://hikerapi.com/p/KhMxYMSn) project.
However, you won't need to spend weeks or even months setting it up.
The best service available today is [HikerAPI](https://hikerapi.com/p/KhMxYMSn), which handles 4–5 million daily requests, provides support around-the-clock, and offers partners a special rate.
In many instances, our clients tried to save money and preferred aiograpi, but in our experience, they ultimately returned to [HikerAPI](https://hikerapi.com/p/KhMxYMSn) after spending much more time and money.
It will be difficult to find good accounts, good proxies, or resolve challenges, and IG will ban your accounts.

The aiograpi more suits for testing or research than a working business!

### We recommend using our services:

* [LamaTok](https://lamatok.com/p/X0HatoxX) for TikTok API 🔥
* [HikerAPI](https://hikerapi.com/p/KhMxYMSn) for Instagram API ⚡⚡⚡
* [DataLikers](https://datalikers.com/p/XPhrh0Y3) for Instagram Datasets 🚀

[![Package](https://github.com/subzeroid/aiograpi/actions/workflows/python-package.yml/badge.svg?branch=main&1)](https://github.com/subzeroid/aiograpi/actions/workflows/python-package.yml)
[![PyPI](https://img.shields.io/pypi/v/aiograpi)](https://pypi.org/project/aiograpi/)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/aiograpi)
![Checked with mypy](https://img.shields.io/badge/mypy-checked-blue)


Features:

* Getting public data of user, posts, stories, highlights, followers and following users
* Getting public email and phone number, if the user specified them in his business profile
* Getting public data of post, story, album, Reels, IGTV data and the ability to download content
* Getting public data of hashtag and location data, as well as a list of posts for them
* Getting public data of all comments on a post and a list of users who liked it
* Management of proxy servers, mobile devices and challenge resolver
* Login by username and password, sessionid and support 2FA
* Managing messages and threads for Direct and attach files
* Download and upload a Photo, Video, IGTV, Reels, Albums and Stories
* Work with Users, Posts, Comments, Insights, Collections, Location and Hashtag
* Insights by account, posts and stories
* Like, following, commenting, editing account (Bio) and much more else

-----

Asynchronous Instagram Private API wrapper without selenium. Use the most recent version of the API from Instagram, which was obtained using reverse-engineering with Charles Proxy and [Proxyman](https://proxyman.io/).

Support **Python >= 3.10**

For any other languages (e.g. C++, C#, F#, D, [Golang](https://github.com/subzeroid/instagrapi-rest/tree/main/golang), Erlang, Elixir, Nim, Haskell, Lisp, Closure, Julia, R, Java, Kotlin, Scala, OCaml, JavaScript, Crystal, Ruby, Rust, [Swift](https://github.com/subzeroid/instagrapi-rest/tree/main/swift), Objective-C, Visual Basic, .NET, Pascal, Perl, Lua, PHP and others), I suggest using [instagrapi-rest](https://github.com/subzeroid/instagrapi-rest)

[Support Chat in Telegram](https://t.me/instagrapi)
![](https://gist.githubusercontent.com/m8rge/4c2b36369c9f936c02ee883ca8ec89f1/raw/c03fd44ee2b63d7a2a195ff44e9bb071e87b4a40/telegram-single-path-24px.svg) and [GitHub Discussions](https://github.com/subzeroid/aiograpi/discussions)


## Features

1. Performs [Web API](https://subzeroid.github.io/aiograpi/usage-guide/fundamentals.html) or [Mobile API](https://subzeroid.github.io/aiograpi/usage-guide/fundamentals.html) requests depending on the situation (to avoid Instagram limits)
2. [Login](https://subzeroid.github.io/aiograpi/usage-guide/interactions.html) by username and password, including 2FA and by sessionid (and uses Authorization header instead Cookies)
3. [Challenge Resolver](https://subzeroid.github.io/aiograpi/usage-guide/challenge_resolver.html) have Email and SMS handlers
4. Support [upload](https://subzeroid.github.io/aiograpi/usage-guide/media.html) a Photo, Video, IGTV, Reels, Albums and Stories
5. Support work with [User](https://subzeroid.github.io/aiograpi/usage-guide/user.html), [Media](https://subzeroid.github.io/aiograpi/usage-guide/media.html), [Comment](https://subzeroid.github.io/aiograpi/usage-guide/comment.html), [Insights](https://subzeroid.github.io/aiograpi/usage-guide/insight.html), [Collections](https://subzeroid.github.io/aiograpi/usage-guide/collection.html), [Location](https://subzeroid.github.io/aiograpi/usage-guide/location.html) (Place), [Hashtag](https://subzeroid.github.io/aiograpi/usage-guide/hashtag.html) and [Direct Message](https://subzeroid.github.io/aiograpi/usage-guide/direct.html) objects
6. [Like](https://subzeroid.github.io/aiograpi/usage-guide/media.html), [Follow](https://subzeroid.github.io/aiograpi/usage-guide/user.html), [Edit account](https://subzeroid.github.io/aiograpi/usage-guide/account.html) (Bio) and much more else
7. [Insights](https://subzeroid.github.io/aiograpi/usage-guide/insight.html) by account, posts and stories
8. [Build stories](https://subzeroid.github.io/aiograpi/usage-guide/story.html) with custom background, font animation, link sticker and mention users
9. Account [registration](https://github.com/subzeroid/aiograpi/blob/main/aiograpi/mixins/signup.py) and captcha passing will appear

### Installation

```
pip install aiograpi
```

### Basic Usage

``` python
from aiograpi import Client

cl = Client()
await cl.login(ACCOUNT_USERNAME, ACCOUNT_PASSWORD)

user_id = await cl.user_id_from_username(ACCOUNT_USERNAME)
medias = await cl.user_medias(user_id, 20)
```

<details>
    <summary>Additional example</summary>

```python
from aiograpi import Client
from aiograpi.types import StoryMention, StoryMedia, StoryLink, StoryHashtag

cl = Client()
await cl.login(USERNAME, PASSWORD, verification_code="<2FA CODE HERE>")

media_pk = await cl.media_pk_from_url('https://www.instagram.com/p/CGgDsi7JQdS/')
media_path = await cl.video_download(media_pk)
subzeroid = await cl.user_info_by_username('subzeroid')
hashtag = await cl.hashtag_info('dhbastards')

await cl.video_upload_to_story(
    media_path,
    "Credits @subzeroid",
    mentions=[StoryMention(user=subzeroid, x=0.49892962, y=0.703125, width=0.8333333333333334, height=0.125)],
    links=[StoryLink(webUri='https://github.com/subzeroid/aiograpi')],
    hashtags=[StoryHashtag(hashtag=hashtag, x=0.23, y=0.32, width=0.5, height=0.22)],
    medias=[StoryMedia(media_pk=media_pk, x=0.5, y=0.5, width=0.6, height=0.8)]
)
```
</details>

## Documentation

* [Index](https://subzeroid.github.io/aiograpi/)
* [Getting Started](https://subzeroid.github.io/aiograpi/getting-started.html)
* [Usage Guide](https://subzeroid.github.io/aiograpi/usage-guide/fundamentals.html)
* [Interactions](https://subzeroid.github.io/aiograpi/usage-guide/interactions.html)
  * [`Media`](https://subzeroid.github.io/aiograpi/usage-guide/media.html) - Publication (also called post): Photo, Video, Album, IGTV and Reels
  * [`Resource`](https://subzeroid.github.io/aiograpi/usage-guide/media.html) - Part of Media (for albums)
  * [`MediaOembed`](https://subzeroid.github.io/aiograpi/usage-guide/media.html) - Short version of Media
  * [`Account`](https://subzeroid.github.io/aiograpi/usage-guide/account.html) - Full private info for your account (e.g. email, phone_number)
  * [`TOTP`](https://subzeroid.github.io/aiograpi/usage-guide/totp.html) - 2FA TOTP helpers (generate seed, enable/disable TOTP, generate code as Google Authenticator)
  * [`User`](https://subzeroid.github.io/aiograpi/usage-guide/user.html) - Full public user data
  * [`UserShort`](https://subzeroid.github.io/aiograpi/usage-guide/user.html) - Short public user data (used in Usertag, Comment, Media, Direct Message)
  * [`Usertag`](https://subzeroid.github.io/aiograpi/usage-guide/user.html) - Tag user in Media (coordinates + UserShort)
  * [`Location`](https://subzeroid.github.io/aiograpi/usage-guide/location.html) - GEO location (GEO coordinates, name, address)
  * [`Hashtag`](https://subzeroid.github.io/aiograpi/usage-guide/hashtag.html) - Hashtag object (id, name, picture)
  * [`Collection`](https://subzeroid.github.io/aiograpi/usage-guide/collection.html) - Collection of medias (name, picture and list of medias)
  * [`Comment`](https://subzeroid.github.io/aiograpi/usage-guide/comment.html) - Comments to Media
  * [`Highlight`](https://subzeroid.github.io/aiograpi/usage-guide/highlight.html) - Highlights
  * [`Notes`](https://subzeroid.github.io/aiograpi/usage-guide/notes.html) - Notes
  * [`Story`](https://subzeroid.github.io/aiograpi/usage-guide/story.html) - Story
  * [`StoryLink`](https://subzeroid.github.io/aiograpi/usage-guide/story.html) - Link Sticker
  * [`StoryLocation`](https://subzeroid.github.io/aiograpi/usage-guide/story.html) - Tag Location in Story (as sticker)
  * [`StoryMention`](https://subzeroid.github.io/aiograpi/usage-guide/story.html) - Mention users in Story (user, coordinates and dimensions)
  * [`StoryHashtag`](https://subzeroid.github.io/aiograpi/usage-guide/story.html) - Hashtag for story (as sticker)
  * [`StorySticker`](https://subzeroid.github.io/aiograpi/usage-guide/story.html) - Tag sticker to story (for example from giphy)
  * [`StoryBuild`](https://subzeroid.github.io/aiograpi/usage-guide/story.html) - [StoryBuilder](/aiograpi/story.py) return path to photo/video and mention co-ordinates
  * [`DirectThread`](https://subzeroid.github.io/aiograpi/usage-guide/direct.html) - Thread (topic) with messages in Direct Message
  * [`DirectMessage`](https://subzeroid.github.io/aiograpi/usage-guide/direct.html) - Message in Direct Message
  * [`Insight`](https://subzeroid.github.io/aiograpi/usage-guide/insight.html) - Insights for a post
  * [`Track`](https://subzeroid.github.io/aiograpi/usage-guide/track.html) - Music track (for Reels/Clips)
* [Best Practices](https://subzeroid.github.io/aiograpi/usage-guide/best-practices.html)
* [Development Guide](https://subzeroid.github.io/aiograpi/development-guide.html)
* [Handle Exceptions](https://subzeroid.github.io/aiograpi/usage-guide/handle_exception.html)
* [Challenge Resolver](https://subzeroid.github.io/aiograpi/usage-guide/challenge_resolver.html)
* [Exceptions](https://subzeroid.github.io/aiograpi/exceptions.html)

## Contributing

[![List of contributors](https://opencollective.com/aiograpi/contributors.svg?width=890&button=0)](https://github.com/subzeroid/aiograpi/graphs/contributors)

To release, you need to call the following commands:

    python setup.py sdist
    twine upload dist/*

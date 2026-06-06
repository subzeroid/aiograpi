# aiograpi - Asynchronous Instagram API for Python

> ⚠️ **Telegram support group moved to https://t.me/aiograpi_support** — the previous `@instagrapi` group has been restricted by Meta and is no longer maintained.

If you want to work with aiograpi (business interests), we strongly advise you to prefer [HikerAPI](https://hikerapi.com/p/KhMxYMSn) project.
However, you won't need to spend weeks or even months setting it up.
The best service available today is [HikerAPI](https://hikerapi.com/p/KhMxYMSn), which handles 4–5 million daily requests, provides support around-the-clock, and offers partners a special rate.
In many instances, our clients tried to save money and preferred aiograpi, but in our experience, they ultimately returned to [HikerAPI](https://hikerapi.com/p/KhMxYMSn) after spending much more time and money.
It will be difficult to find good accounts, good proxies, or resolve challenges, and IG will ban your accounts.

The aiograpi more suits for testing or research than a working business!

Video uploads can use a built-in MP4 metadata parser when you provide `thumbnail=...`. Automatic thumbnail generation, `StoryBuilder`, and video/audio composition still need the optional video dependencies, MoviePy `2.2.1`, and executable `ffmpeg`:

```bash
pip install "aiograpi[video]"
pip install --no-deps "moviepy==2.2.1"
```

MoviePy `2.2.1` currently declares `Pillow<12`, but aiograpi keeps `Pillow>=12.2.0` for security fixes; the `--no-deps` install keeps the safe Pillow version. If your project imports MoviePy directly, migrate any MoviePy `1.x` code from `moviepy.editor`, `set_*`, `resize`, and `subclip` APIs to the MoviePy `2.x` API before upgrading.

Android users should see [Pydroid and ffmpeg](docs/usage-guide/pydroid.md) and [Termux](docs/usage-guide/termux.md).

### We recommend using our services:

* [LamaTok](https://lamatok.com/p/X0HatoxX) for TikTok API 🔥
* [HikerAPI](https://hikerapi.com/p/KhMxYMSn) for Instagram API ⚡⚡⚡
* [DataLikers](https://datalikers.com/p/XPhrh0Y3) for Instagram Datasets 🚀

[![PyPI](https://img.shields.io/pypi/v/aiograpi)](https://pypi.org/project/aiograpi/)
[![Python](https://img.shields.io/pypi/pyversions/aiograpi)](https://pypi.org/project/aiograpi/)
[![License](https://img.shields.io/pypi/l/aiograpi)](LICENSE)
[![Package](https://github.com/subzeroid/aiograpi/actions/workflows/python-package.yml/badge.svg)](https://github.com/subzeroid/aiograpi/actions/workflows/python-package.yml)
[![Docs](https://img.shields.io/badge/docs-gh--pages-blue)](https://subzeroid.github.io/aiograpi/latest/)
[![SemVer](https://img.shields.io/badge/semver-1.2.0-blue)](https://semver.org/spec/v2.0.0.html)


Features:

* Getting public data of user, posts, stories, highlights, followers and following users
* Getting public email and phone number, if the user specified them in his business profile
* Getting public data of post, story, album, Reels, IGTV data and the ability to download content
* Getting public data of hashtag and location data, as well as a list of posts for them
* Getting public data of all comments on a post and a list of users who liked it
* Management of proxy servers, mobile devices and challenge resolver
* Login by username and password, sessionid, 2FA, 8-digit backup codes, and Bloks 2FA fallback/helpers
* Managing messages, reactions and threads for Direct and attach files
* Experimental Realtime MQTT/MQTToT for Direct message sync, lightweight Direct actions, and FBNS push callbacks
* Download and upload a Photo, Video, IGTV, Reels, Albums, Stories and Trial Reels
* Work with Users, Posts, Comments, Insights, Collections, Location and Hashtag
* Insights by account, posts and stories
* Like, following, commenting, editing account (Bio) and much more else

-----

Asynchronous Instagram Private API wrapper without selenium. Use the most recent version of the API from Instagram, which was obtained using reverse-engineering with Charles Proxy and [Proxyman](https://proxyman.io/).

Support **Python >= 3.10**

For any other languages (e.g. C++, C#, F#, D, [Golang](https://github.com/subzeroid/instagrapi-rest/tree/main/golang), Erlang, Elixir, Nim, Haskell, Lisp, Closure, Julia, R, Java, Kotlin, Scala, OCaml, JavaScript, Crystal, Ruby, Rust, [Swift](https://github.com/subzeroid/instagrapi-rest/tree/main/swift), Objective-C, Visual Basic, .NET, Pascal, Perl, Lua, PHP and others), I suggest using [instagrapi-rest](https://github.com/subzeroid/instagrapi-rest)

Support chat in Telegram: https://t.me/aiograpi_support
![](https://gist.githubusercontent.com/m8rge/4c2b36369c9f936c02ee883ca8ec89f1/raw/c03fd44ee2b63d7a2a195ff44e9bb071e87b4a40/telegram-single-path-24px.svg) and [GitHub Discussions](https://github.com/subzeroid/aiograpi/discussions)


## Features

1. Performs [Web API](https://subzeroid.github.io/aiograpi/latest/usage-guide/fundamentals/) or [Mobile API](https://subzeroid.github.io/aiograpi/latest/usage-guide/fundamentals/) requests depending on the situation (to avoid Instagram limits)
2. [Login](https://subzeroid.github.io/aiograpi/latest/usage-guide/interactions/) by username and password, including 2FA, 8-digit backup codes, [Bloks 2FA](https://subzeroid.github.io/aiograpi/latest/usage-guide/totp/#bloks-two-factor-flow) fallback/helpers, and by sessionid (and uses Authorization header instead Cookies)
3. [Challenge Resolver](https://subzeroid.github.io/aiograpi/latest/usage-guide/challenge_resolver/) have Email and SMS handlers
4. Support [upload](https://subzeroid.github.io/aiograpi/latest/usage-guide/media/) a Photo, Video, IGTV, Reels, Albums and Stories
5. Support work with [User](https://subzeroid.github.io/aiograpi/latest/usage-guide/user/), [Media](https://subzeroid.github.io/aiograpi/latest/usage-guide/media/), [Comment](https://subzeroid.github.io/aiograpi/latest/usage-guide/comment/), [Insights](https://subzeroid.github.io/aiograpi/latest/usage-guide/insight/), [Collections](https://subzeroid.github.io/aiograpi/latest/usage-guide/collection/), [Location](https://subzeroid.github.io/aiograpi/latest/usage-guide/location/) (Place), [Hashtag](https://subzeroid.github.io/aiograpi/latest/usage-guide/hashtag/) and [Direct Message](https://subzeroid.github.io/aiograpi/latest/usage-guide/direct/) objects
6. [Like](https://subzeroid.github.io/aiograpi/latest/usage-guide/media/), [Follow](https://subzeroid.github.io/aiograpi/latest/usage-guide/user/), [Edit account](https://subzeroid.github.io/aiograpi/latest/usage-guide/account/) (Bio) and much more else
7. [Insights](https://subzeroid.github.io/aiograpi/latest/usage-guide/insight/) by account, posts and stories
8. [Build stories](https://subzeroid.github.io/aiograpi/latest/usage-guide/story/) with custom background, font animation, link sticker and mention users
9. [Realtime MQTT](https://subzeroid.github.io/aiograpi/latest/usage-guide/realtime/) for Direct message sync, lightweight Direct MQTT actions, and FBNS push notifications
10. Account [registration](https://github.com/subzeroid/aiograpi/blob/main/aiograpi/mixins/signup.py) and captcha passing will appear

### Versioning policy

Starting with `1.0.0`, aiograpi follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
for the Python library API surface. Instagram's private API still rotates
`doc_id`s, deprecates endpoints, and changes response shapes without notice, so
`1.0.0` is not a promise that every Instagram-side flow will stay stable forever.

What you can rely on instead:

- **Breaking library API changes use major releases** when they are under our control.
- **Instagram-driven endpoint removals are flagged in the [CHANGELOG](https://github.com/subzeroid/aiograpi/blob/main/CHANGELOG.md)** with migration notes.
- **Deprecated methods stay around for ≥2 minor releases** with
  `DeprecationWarning` before removal — you'll get loud warnings, not
  surprise `AttributeError`s.
- **Live CI smoke** runs on every push: `tests/live/smoke.py` against a
  real account through a real proxy. If we ship something that breaks
  the basic happy path, CI catches it.
- **Migration Guide** at [docs/migration.md](https://subzeroid.github.io/aiograpi/latest/migration/) — breaking changes are documented with before/after examples.

### What's new in 1.0.0 and recent releases

- **1.2.0 upstream sync** — synced with `instagrapi 2.8.13`, adding Direct media share to existing threads, clearer Direct message request privacy errors, private-first high-level user/media/story lookups, sessionid username recovery via private stream, and clearer Bloks redirect challenge handling.
- **1.1.0 MQTT/FBNS sync** — synced with `instagrapi 2.8.2`, adding experimental async Realtime MQTT/MQTToT,
  Direct message sync, lightweight Direct MQTT actions, FBNS push token registration/callbacks, phone confirmation,
  followed hashtag helpers, feed-media share-to-story, opaque Bloks challenge context handling, and clearer Reel upload
  failure details.
- **1.0.0 SemVer baseline** — synced with `instagrapi 2.7.0`, removed the dead public `?__a=1`
  API surface, kept `media_info_gql()` GraphQL-only, and moved high-level hashtag/location helpers
  to authenticated private/mobile flows.
- **Sync with instagrapi 2.6.x** — current Android app profile defaults,
  `override_app_version` constructor support, Trial Reels, current Reel rupload flow, Reel pin/unpin,
  Reel Facebook cross-post payload helpers,
  feed photo/carousel music, music Notes, archive readers, tagged media pagination,
  Direct reactions, thread title updates, message request helpers, single-message lookup, and Direct unsend.
- **Android/Pydroid/Termux-friendly video uploads** — when you pass `thumbnail=...`, aiograpi can read
  MP4 dimensions/duration without importing MoviePy/ffmpeg. The optional `video` dependencies plus
  MoviePy `2.2.1` cover automatic thumbnails, StoryBuilder, `prepare_video()`, and audio/video composition.
- **Modern dev tooling** — `uv.lock`, Ruff formatting/checks, updated test pins, and an
  upstream sync tracking workflow.
- **Sync with instagrapi 2.4.4** — every mixin and infrastructure module ported, plus three new mixins:
  [`ExploreMixin`](https://subzeroid.github.io/aiograpi/latest/usage-guide/explore/),
  [`FundraiserMixin`](https://subzeroid.github.io/aiograpi/latest/usage-guide/fundraiser/), and opt-in
  [`CaptchaHandlerMixin`](https://subzeroid.github.io/aiograpi/latest/usage-guide/captcha/).
- **doc_id GraphQL primitive** — `Client.public_doc_id_graphql_request(doc_id, variables)` and
  `Client.private_graphql_query_request(...)` for the new `i.instagram.com/graphql/query` surface
  IG migrated to. New high-level methods: `user_info_v2_gql`, `user_info_by_username_v2_gql`,
  `private_graphql_followers_list` / `following_list` / `clips_profile` / `inbox_tray_for_user`,
  `private_graphql_memories_pog` / `realtime_region_hint` / `top_audio_trends_eligible_categories`,
  plus `fbsearch_keyword_typeahead` / `fbsearch_typeahead_stream` / `fbsearch_item`,
  `feed_user_stream_item`, `media_comment_infos`. All live-verified.
- **Pure helpers go sync** (breaking from 0.0.x): `media_pk_from_code`, `media_code_from_pk`,
  `media_pk`, `share_info`, `share_code_from_url`, `share_info_by_url`, `highlight_pk_from_url`,
  `handle_challenge_result`, `challenge_resolve_new_password_form` no longer require `await`.
  See [Migration Guide](https://subzeroid.github.io/aiograpi/latest/migration/) for the full list.
- **CI publish-on-tag** with PyPI trusted publishing — push a version tag, GitHub Actions builds,
  publishes, and creates a release.

Full per-release notes: [CHANGELOG.md](https://github.com/subzeroid/aiograpi/blob/main/CHANGELOG.md).
Migrating from `0.0.x`?
See the [Migration Guide](https://subzeroid.github.io/aiograpi/latest/migration/).

### Installation

```
pip install aiograpi
```

Optional public web TLS impersonation support is available as an extra:

```bash
pip install "aiograpi[curl]"
```

Use it only for public web endpoints that are sensitive to browser TLS fingerprints:

```python
cl = Client(public_transport="curl", public_transport_impersonate="chrome136")
```

See the [public transport guide](docs/usage-guide/public-transport.md) for live comparison results and caveats.

TLS certificate verification is enabled by default. For a trusted debugging MITM proxy, prefer `Client(tls_verify="/path/to/proxy-ca.pem")`; use `Client(tls_verify=False)` only for temporary local debugging because it allows session interception.

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

See the [Realtime MQTT guide](docs/usage-guide/realtime.md) for Direct sync, MQTT Direct actions, and FBNS push examples.

### Basic Usage

``` python
from aiograpi import Client

cl = Client()
await cl.login(ACCOUNT_USERNAME, ACCOUNT_PASSWORD)

user_id = await cl.user_id_from_username(ACCOUNT_USERNAME)
medias = await cl.user_medias(user_id, 20)
```

### Runnable Examples

Practical async scripts live in [examples/README.md](examples/README.md). They cover session login, public lookups, media
downloads, feed uploads, Reels and Trial Reels, story uploads, Direct messages, proxies, and optional curl-backed public
transport.

### Session Persistence

Logging in fresh on every run is the fastest way to get your account flagged.
Persist the session and reuse it:

``` python
from aiograpi import Client

cl = Client()
await cl.login(USERNAME, PASSWORD)
cl.dump_settings("session.json")

# reload later without entering credentials again
cl = Client()
cl.load_settings("session.json")
await cl.login(USERNAME, PASSWORD)
```

If you want explicit control over the loaded session object:

```python
from aiograpi import Client

cl = Client()
cl.set_settings(cl.load_settings("session.json"))
await cl.login(USERNAME, PASSWORD)
```

### Login by sessionid

```python
from aiograpi import Client

cl = Client()
await cl.login_by_sessionid("<your_sessionid>")
```

`login_by_sessionid()` is a lightweight compatibility path. For long-lived automation prefer the regular `login()` → `dump_settings()` → `load_settings()` / `set_settings()` flow.

If a browser/web `sessionid` returns `login_required` or logs the browser out, Instagram rejected that session for the private mobile API. Use a stable password login once, save settings with `dump_settings()`, and reuse those settings instead of repeatedly importing browser cookies.

### Typical Tasks

#### List and download another user's posts

```python
target_id = await cl.user_id_from_username("target_user")
posts = await cl.user_medias(target_id, amount=10)
for media in posts:
    await cl.photo_download(media.pk)
```

#### Search a location by name

```python
places = await cl.location_search("Times Square")
print(places[0].name, places[0].pk)
```

#### Followers via the new private GraphQL surface

```python
import uuid

data = await cl.private_graphql_followers_list(
    user_id="25025320",
    rank_token=str(uuid.uuid4()),
    order="date_followed_latest",
)
# Raw GraphQL envelope: {"data": {...}, "status": "ok", ...}
```

See [Private GraphQL & doc_id](https://subzeroid.github.io/aiograpi/latest/usage-guide/private-graphql/)
for the full new-mobile-API surface (followers, clips, search, inbox).

<details>
    <summary>Additional example (story upload with mentions / hashtags / media)</summary>

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

* [Index](https://subzeroid.github.io/aiograpi/latest/)
* [Getting Started](https://subzeroid.github.io/aiograpi/latest/getting-started/)
* [Migration Guide](https://subzeroid.github.io/aiograpi/latest/migration/) — for users coming from `0.0.x`
* [Runnable Examples](https://subzeroid.github.io/aiograpi/latest/usage-guide/examples/)
* [Usage Guide](https://subzeroid.github.io/aiograpi/latest/usage-guide/fundamentals/)
* [Interactions](https://subzeroid.github.io/aiograpi/latest/usage-guide/interactions/)
  * [`Media`](https://subzeroid.github.io/aiograpi/latest/usage-guide/media/) - Publication (also called post): Photo, Video, Album, IGTV and Reels
  * [`Resource`](https://subzeroid.github.io/aiograpi/latest/usage-guide/media/) - Part of Media (for albums)
  * [`MediaOembed`](https://subzeroid.github.io/aiograpi/latest/usage-guide/media/) - Short version of Media
  * [`Account`](https://subzeroid.github.io/aiograpi/latest/usage-guide/account/) - Full private info for your account (e.g. email, phone_number)
  * [`TOTP`](https://subzeroid.github.io/aiograpi/latest/usage-guide/totp/) - 2FA TOTP helpers, code generation, and Bloks verification fallback/helpers
  * [`User`](https://subzeroid.github.io/aiograpi/latest/usage-guide/user/) - Full public user data
  * [`UserShort`](https://subzeroid.github.io/aiograpi/latest/usage-guide/user/) - Short public user data (used in Usertag, Comment, Media, Direct Message)
  * [`Usertag`](https://subzeroid.github.io/aiograpi/latest/usage-guide/user/) - Tag user in Media (coordinates + UserShort)
  * [`Location`](https://subzeroid.github.io/aiograpi/latest/usage-guide/location/) - GEO location (GEO coordinates, name, address)
  * [`Hashtag`](https://subzeroid.github.io/aiograpi/latest/usage-guide/hashtag/) - Hashtag object (id, name, picture)
  * [`Collection`](https://subzeroid.github.io/aiograpi/latest/usage-guide/collection/) - Collection of medias (name, picture and list of medias)
  * [`Comment`](https://subzeroid.github.io/aiograpi/latest/usage-guide/comment/) - Comments to Media
  * [`Highlight`](https://subzeroid.github.io/aiograpi/latest/usage-guide/highlight/) - Highlights
  * [`Notes`](https://subzeroid.github.io/aiograpi/latest/usage-guide/notes/) - Notes
  * [`Story`](https://subzeroid.github.io/aiograpi/latest/usage-guide/story/) - Story
  * [`StoryLink`](https://subzeroid.github.io/aiograpi/latest/usage-guide/story/) - Link Sticker
  * [`StoryLocation`](https://subzeroid.github.io/aiograpi/latest/usage-guide/story/) - Tag Location in Story (as sticker)
  * [`StoryMention`](https://subzeroid.github.io/aiograpi/latest/usage-guide/story/) - Mention users in Story (user, coordinates and dimensions)
  * [`StoryHashtag`](https://subzeroid.github.io/aiograpi/latest/usage-guide/story/) - Hashtag for story (as sticker)
  * [`StorySticker`](https://subzeroid.github.io/aiograpi/latest/usage-guide/story/) - Tag sticker to story (for example from giphy)
  * [`StoryBuild`](https://subzeroid.github.io/aiograpi/latest/usage-guide/story/) - [StoryBuilder](/aiograpi/story.py) return path to photo/video and mention co-ordinates
  * [`DirectThread`](https://subzeroid.github.io/aiograpi/latest/usage-guide/direct/) - Thread (topic) with messages in Direct Message
  * [`DirectMessage`](https://subzeroid.github.io/aiograpi/latest/usage-guide/direct/) - Message in Direct Message
  * [`Insight`](https://subzeroid.github.io/aiograpi/latest/usage-guide/insight/) - Insights for a post
  * [`Track`](https://subzeroid.github.io/aiograpi/latest/usage-guide/track/) - Music track (for Reels/Clips)
* [Captcha](https://subzeroid.github.io/aiograpi/latest/usage-guide/captcha/) - Opt-in handler interface for solver integrations
* [Explore](https://subzeroid.github.io/aiograpi/latest/usage-guide/explore/) - Explore page methods
* [Fundraiser](https://subzeroid.github.io/aiograpi/latest/usage-guide/fundraiser/) - Fundraiser info
* [Best Practices](https://subzeroid.github.io/aiograpi/latest/usage-guide/best-practices/)
* [Pydroid and ffmpeg](https://subzeroid.github.io/aiograpi/latest/usage-guide/pydroid/) - Android/Pydroid video upload notes
* [Termux](https://subzeroid.github.io/aiograpi/dev/usage-guide/termux/) - Termux install notes and optional video helpers
* [Development Guide](https://subzeroid.github.io/aiograpi/latest/development-guide/)
* [Handle Exceptions](https://subzeroid.github.io/aiograpi/latest/usage-guide/handle_exception/)
* [Challenge Resolver](https://subzeroid.github.io/aiograpi/latest/usage-guide/challenge_resolver/)
* [Exceptions](https://subzeroid.github.io/aiograpi/latest/exceptions/)

## Contributing

[![List of contributors](https://contrib.rocks/image?repo=subzeroid/aiograpi)](https://github.com/subzeroid/aiograpi/graphs/contributors)

### Releasing

Releases are automated via the `publish.yml` GitHub Actions workflow with PyPI
[trusted publishing](https://docs.pypi.org/trusted-publishers/). To cut a new release:

1. Bump `version =` in `pyproject.toml`.
2. Add a section to `CHANGELOG.md`.
3. Commit and push to `main`.
4. Tag: `git tag -a 0.x.y -m "Release 0.x.y" && git push origin 0.x.y`.

The workflow then builds sdist + wheel, verifies the tag matches `pyproject.toml`,
publishes to PyPI, and creates the GitHub release with both artefacts attached
— no API tokens needed.

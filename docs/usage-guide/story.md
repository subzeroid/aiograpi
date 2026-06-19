# Story

| Method                                                                 | Return          | Description
| ---------------------------------------------------------------------- | --------------- | ----------------------------------
| user_stories(user_id: str, amount: int = None)                         | List[Story]     | Get list of stories by user_id
| story_info(story_pk: int, use_cache: bool = True)                      | Story           | Return story info
| story_delete(story_pk: int)                                            | bool            | Delete story
| story_seen(story_pks: List[int], skipped_story_pks: List[int])         | bool            | Mark a story as seen
| story_pk_from_url(url: str)                                            | int             | Get Story (media) PK from URL
| story_download(story_pk: int, filename: str = "", folder: Path = "")   | Path            | Download story media by media_type
| story_download_by_url(url: str, filename: str = "", folder: Path = "") | Path            | Download story media using URL to file (mp4 or jpg)
| story_viewers(story_pk: int, amount: int = 20)                         | List[UserShort] | List of story viewers (via Private API)
| story_likers(story_pk: int, amount: int = 0)                           | List[UserShort] | List of story likers (via Private API)
| story_like(story_id: str, revert: bool = False, mark_seen: bool = True) | bool            | Like a story
| story_unlike(story_id: str)                                            | bool            | Unlike a story
| story_poll_vote(story_id: str, poll_id: str, vote: int)                | bool            | Vote in a story poll sticker
| archive_story_days(amount: int = 0, include_memories: bool = True)      | List[StoryArchiveDay] | Get story archive day shells
| archive_stories(amount: int = 0)                                       | List[Story]     | Get archived stories

Example:

``` python
>>> await cl.story_download(await cl.story_pk_from_url('https://www.instagram.com/stories/example/2581281926631793076/'))
PosixPath('/app/189361307_229642088942817_9180243596650100310_n.mp4')

>>> s = await cl.story_info(2581281926631793076)

>>> await cl.story_download_by_url(s.video_url)  # url to mp4 file
PosixPath('/app/189361307_229642088942817_9180243596650100310_n.mp4')

>>> await cl.story_download_by_url(s.thumbnail_url)  # URL to jpg file
PosixPath('/app/191260083_2908005872746895_8988438451809588865_n.jpg')

>>> days = await cl.archive_story_days(amount=5)
>>> stories = await cl.archive_stories(amount=10)
```

## Upload Stories

Upload medias to your stories.

The story file should be at 9:16 resolution (e.g. 720x1280).
If you have a different resolution, then you need to prepare a file or use the StoryBuilder, which is written about below.

Common arguments:

* `path` - Path to media file
* `caption` - Caption for story (now use to fetch mentions)
* `thumbnail` - Thumbnail instead capture from source file
* `mentions` - Tag profiles in story
* `locations` - Add locations to story
* `links` - "Swipe Up" links (now use first)
* `hashtags` - Add hashtags to story
* `stickers` - Add stickers to story
* `resize_mode` - Story media sizing mode. Exposed as `StoryResizeMode = Literal["fill", "fit"]`; `"fill"` keeps the current crop/fill behavior, `"fit"` renders the full source media on a Story canvas without cropping

| Method                               | Return   | Description
| ------------------------------------ | -------- | -------------
| photo_upload_to_story(path: Path, caption: str = "", upload_id: str = "", mentions: List[StoryMention] = [], locations: List[StoryLocation] = [], links: List[StoryLink] = [], hashtags: List[StoryHashtag] = [], stickers: List[StorySticker] = [], medias: List[StoryMedia] = [], polls: List[StoryPoll] = [], extra_data: Dict[str, str] = {}, resize_mode: StoryResizeMode = "fill")  | Story  | Upload photo to story
| video_upload_to_story(path: Path, caption: str = "", thumbnail: Path = None, mentions: List[StoryMention] = [], locations: List[StoryLocation] = [], links: List[StoryLink] = [], hashtags: List[StoryHashtag] = [], stickers: List[StorySticker] = [], medias: List[StoryMedia] = [], polls: List[StoryPoll] = [], extra_data: Dict[str, str] = {}, resize_mode: StoryResizeMode = "fill") | Story  | Upload video to story
| photo_upload_to_story_with_music(path: Path, caption: str, track: Track or dict, thumbnail: Path = None, duration: float = 15.0, extra_data: Dict = {}) | Story | Upload photo to story as a short video with the selected music track muxed into it
| video_upload_to_story_with_music(path: Path, caption: str, track: Track or dict, thumbnail: Path = None, extra_data: Dict = {}) | Story | Upload video to story with the selected music track muxed into it
| story_music_extra_data(track: Track or dict, extra_data: Dict = {}) | dict | Build Story music configure fields for manual story upload `extra_data`
| media_share_to_story(media_id: str, background: Path = None, caption: str = "") | Story | Share an existing feed media as a story sticker |

In `extra_data`, you can pass additional story settings, for example:

| Method            | Type   | Description
| ----------------- | ------ | ------------------
| audience          | String | [Publish story for close friends](https://github.com/subzeroid/instagrapi/issues/1210) `{"audience": "besties"}`

Story music helpers require the optional video dependencies, MoviePy `2.2.1`, and executable ffmpeg because they render
a local MP4 before upload. They add Story music metadata and bake the selected track into the uploaded media; they do not
expose Instagram's native interactive lyrics/music sticker UI.

Sizing notes:

* For story uploads, use a 9:16 asset, pass `resize_mode="fit"` to keep the full source media visible on a Story canvas, or build one manually with `StoryBuilder`.
* `resize_mode="fill"` is the default and keeps the existing crop/fill behavior.

Examples:

``` python
from aiograpi import Client
from aiograpi.types import StoryMention, StoryMedia, StoryLink, StoryHashtag, StoryPoll

cl = Client()
await cl.login(USERNAME, PASSWORD)

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
    medias=[StoryMedia(media_pk=media_pk, x=0.5, y=0.5, width=0.6, height=0.8)],
)
```

Upload a story poll:

```python
story = await cl.photo_upload_to_story(
    "/app/image.jpg",
    "Poll",
    polls=[StoryPoll(x=0.5, y=0.5, width=0.7, height=0.3, question="Pick one", options=["Yes", "No"])],
)
```

Share a feed media to story:

```python
await cl.media_share_to_story(
    "3613500067578544892_25025320",
    caption="Shared from feed",
)
```

## Build Story to Upload

If you want to format your story correctly (correct resolution, user mentions, etc) use StoryBuilder. StoryBuilder renders media with MoviePy and ffmpeg, so install the optional video dependencies first:

```bash
pip install "aiograpi[video]"
pip install --no-deps "moviepy==2.2.1"
```

MoviePy `2.2.1` currently declares `Pillow<12`, but aiograpi keeps `Pillow>=12.2.0` for security fixes; the `--no-deps` install keeps the safe Pillow version. Older MoviePy `1.x` imports such as `moviepy.editor` and clip methods such as `set_duration`, `set_position`, `resize`, and `subclip` are not supported by aiograpi's video helpers.

| Method                                                | Return     | Description                              |
| ----------------------------------------------------- | ---------- | ---------------------------------------- |
| StoryBuilder.build_clip(clip: moviepy.Clip, max_duration: int = 0) | StoryBuild | Build CompositeVideoClip with background and mentioned users. Return MP4 file and mentions with coordinates |
| StoryBuilder.video(max_duration: int = 0)            | StoryBuild | Call build_clip(VideoClip, max_duration) |
| StoryBuilder.video_fit(max_duration: int = 0)        | StoryBuild | Build a 720x1280 Story video canvas that fits the full source video without cropping |
| StoryBuilder.photo(max_duration: int = 0)            | StoryBuild | Call build_clip(ImageClip, max_duration) |

Example:

``` python
from aiograpi.types import StoryMention, StoryMedia, StoryLink
from aiograpi.story import StoryBuilder

media_pk = await cl.media_pk_from_url('https://www.instagram.com/p/CGgDsi7JQdS/')
media_path = await cl.video_download(media_pk)
example = await cl.user_info_by_username('example')

buildout = StoryBuilder(
    media_path,
    'Credits @example',
    [StoryMention(user=example)],
    Path('/path/to/background_720x1280.jpg')
).video(15)  # seconds

await cl.video_upload_to_story(
    buildout.path,
    "Credits @example",
    mentions=buildout.mentions,
    links=[StoryLink(webUri='https://github.com/subzeroid/aiograpi')],
    medias=[StoryMedia(media_pk=media_pk)]
)
```

Result:

![](https://raw.githubusercontent.com/example/aiograpi/main/examples/dhb.gif)

Photo upload:

``` python
await cl.photo_upload_to_story('/app/image.jpg')
```

Upload photo as video:

``` python
buildout = StoryBuilder('/app/image.jpg').photo()
await cl.video_upload_to_story(buildout.path)
```

Upload photo or video without cropping:

``` python
await cl.photo_upload_to_story(Path("/app/landscape.jpg"), resize_mode="fit")
await cl.video_upload_to_story(Path("/app/landscape.mp4"), resize_mode="fit")
```

Like & unlike story:

```python
pk = await cl.story_pk_from_url("https://instagram.com/stories/purely.anand/2884886531427631361/")
info = (await cl.story_info(pk)).dict()

await cl.story_like(info['id']) # To like story
await cl.story_unlike(info['id']) # To unlike story

# another way to unlike story
await cl.story_like(info['id'], revert=True)
```

Vote in story poll:

```python
story = await cl.story_info(STORY_ID)
poll = story.polls[0]
await cl.story_poll_vote(story.id, poll.id, 0)
```

More stories here [https://www.instagram.com/wrclive/](https://www.instagram.com/wrclive/)

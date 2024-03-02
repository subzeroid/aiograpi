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
| story_like(story_id: str, revert: bool = False)                        | bool            | Like a story
| story_unlike(story_id: str)                                            | bool            | Unlike a story

Example:

``` python
>>> await cl.story_download(await cl.story_pk_from_url('https://www.instagram.com/stories/example/2581281926631793076/'))
PosixPath('/app/189361307_229642088942817_9180243596650100310_n.mp4')

>>> s = await cl.story_info(2581281926631793076)

>>> await cl.story_download_by_url(s.video_url)  # url to mp4 file
PosixPath('/app/189361307_229642088942817_9180243596650100310_n.mp4')

>>> await cl.story_download_by_url(s.thumbnail_url)  # URL to jpg file
PosixPath('/app/191260083_2908005872746895_8988438451809588865_n.jpg')
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

| Method                               | Return   | Description
| ------------------------------------ | -------- | -------------
| photo_upload_to_story(path: Path, caption: str, upload_id: str, mentions: List[Usertag], locations: List[StoryLocation], links: List[StoryLink], hashtags: List[StoryHashtag], stickers: List[StorySticker], extra_data: Dict[str, str] = {})  | Story  | Upload photo (Support JPG files)
| video_upload_to_story(path: Path, caption: str, thumbnail: Path, mentions: List[Usertag], locations: List[StoryLocation], links: List[StoryLink], hashtags: List[StoryHashtag], stickers: List[StorySticker], extra_data: Dict[str, str] = {}) | Story  | Upload video (Support MP4 files)

In `extra_data`, you can pass additional story settings, for example:

| Method            | Type   | Description
| ----------------- | ------ | ------------------
| audience          | String | [Publish story for close friends](https://github.com/subzeroid/instagrapi/issues/1210) `{"audience": "besties"}`


Examples:

``` python
from aiograpi import Client
from aiograpi.types import StoryMention, StoryMedia, StoryLink, StoryHashtag

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

## Build Story to Upload

If you want to format your story correctly (correct resolution, user mentions, etc) use StoryBuilder:

| Method                                                | Return     | Description                              |
| ----------------------------------------------------- | ---------- | ---------------------------------------- |
| StoryBuilder.build_clip(clip: moviepy.Clip, max_duration: int = 0) | StoryBuild | Build CompositeVideoClip with background and mentioned users. Return MP4 file and mentions with coordinates |
| StoryBuilder.video(max_duration: int = 0)            | StoryBuild | Call build_clip(VideoClip, max_duration) |
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

Like & unlike story:

```python
pk = await cl.story_pk_from_url("https://instagram.com/stories/purely.anand/2884886531427631361/")
info = (await cl.story_info(pk)).dict()

await cl.story_like(info['id']) # To like story
await cl.story_unlike(info['id']) # To unlike story

# another way to unlike story
await cl.story_like(info['id'], revert=True)
```

More stories here [https://www.instagram.com/wrclive/](https://www.instagram.com/wrclive/)

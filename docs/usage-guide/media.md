# Media

Viewing, downloading, uploading and editing publications

In terms of Instagram, this is called Media, usually users call it publications or posts

### Basic terms:

* `media_id` - String ID `"{media_id}_{user_id}"`, e.g. `"2277033926878261772_1903424587"`
* `media_pk` - Integer ID (real media id), e.g. `2277033926878261772`
* `code` - Short code (slug for media), e.g. `BjNLpA1AhXM` from `"https://www.instagram.com/p/BjNLpA1AhXM/"`
* `url` - URL to media publication, e.g. `"https://www.instagram.com/p/BjNLpA1AhXM/"`

### Media types:

* `Photo` - When media_type=1
* `Video` - When media_type=2 and product_type=feed
* `IGTV`  - When media_type=2 and product_type=igtv
* `Reel`  - When media_type=2 and product_type=clips
* `Album` - When media_type=8

## Viewing and editing publication

| Method                                                          | Return             | Description
| --------------------------------------------------------------- | ------------------ | --------------------------------------------
| media_id(media_pk: int)                                         | str                | Return media_id by media_pk (e.g. 2277033926878261772 -> 2277033926878261772_1903424587)
| media_pk(media_id: str)                                         | int                | Return media_pk by media_id (e.g. 2277033926878261772_1903424587 -> 2277033926878261772)
| media_pk_from_code(code: str)                                   | int                | Return media_pk
| media_pk_from_url(url: str)                                     | int                | Return media_pk
| user_medias(user_id: str, amount: int = 20)                     | List\[Media]       | Get list of medias by user_id
| user_medias_chunk(user_id: str, end_cursor: str = "")           | Tuple\[List\[Media], str] | Get one page of medias by user_id
| user_medias_paginated(user_id: str, amount: int = 0, end_cursor: str = "") | Tuple\[List\[Media], str] | Get one page of medias by user_id; compatibility alias for `instagrapi`
| user_clips(user_id: str, amount: int = 50)                      | List\[Media]       | Get list of clips (reels) by user_id
| usertag_medias(user_id: str, amount: int = 20)                  | List\[Media]       | Get medias where a user is tagged
| media_info(media_pk: int)                                       | Media              | Return media info
| media_delete(media_pk: int)                                     | bool               | Delete media
| media_edit(media_pk: int, caption: str, title: str, usertags: List[Usertag], location: Location) | dict | Change caption for media
| media_user(media_pk: int)                                       | User | Get user info for media
| media_oembed(url: str)                                          | MediaOembed        | Return short media info by media URL
| media_like(media_id: str)                                       | bool               | Like media
| media_unlike(media_id: str)                                     | bool               | Unlike media
| media_note_create(media_id: str, text: str = "", audience: int = 7, note_style: int = 13, extra_data: Optional[Dict] = None) | dict | Create a note attached to a media item
| media_note_delete(note_id: str, extra_data: Optional[Dict] = None) | bool | Delete a note attached to a media item
| media_share_to_story(media_id: str, background: Path = None, caption: str = "", extra_data: Optional[Dict] = None) | Story | Share an existing feed media as a story sticker
| media_seen(media_ids: List[str], skipped_media_ids: List[str])  | bool               | Mark a media as seen
| media_likers(media_id: str)                                     | List\[UserShort]   | Return list of users who liked this post (due to Instagram limitations, this may not return a complete list)
| media_archive(media_id: str)                                    | bool               | Archive a media
| media_unarchive(media_id: str)                                  | bool               | Unarchive a media
| archive_medias(amount: int = 0)                                 | List\[Media]       | Get your archived feed posts
| media_pin(media_id: str)                                        | bool               | Pin a media to user profile
| media_unpin(media_id: str)                                      | bool               | Unpin a media to user profile
| clip_mashup_info(media_pk: str)                                 | dict               | Fetch Reel remix/reuse availability metadata
| clip_seen(media_ids: List[str], blend_media_ids: List[str] = None) | bool            | Mark Reels/Clips as seen through the Clips seen-state endpoint
| clip_pin(media_pk: str)                                         | bool               | Pin a Reel to the Reels tab/profile Reels grid
| clip_unpin(media_pk: str)                                       | bool               | Unpin a Reel from the Reels tab/profile Reels grid

Media notes are separate from Direct inbox Notes. Use `media_note_create()` and `media_note_delete()` for the note surface attached to a post or Reel; use the [Notes guide](notes.md) for Direct inbox Notes.

Use `clip_seen()` for Reels/Clips. `media_seen()` keeps the older story/reel-tray seen payload. Instagram still decides whether a seen-state event is counted in view analytics.

`media_share_to_story()` uploads a story background and attaches the feed media as a story sticker. Pass a 9:16
background image, or omit `background` to generate a temporary black 720x1280 image.

Low level methods:

| Method                                                          | Return       | Description
| --------------------------------------------------------------- | ------------ | --------------------------------------------
| media_info_gql(media_pk: int)                                   | Media        | Get Media from PK by Public Graphql API
| media_info_v1(media_pk: int)                                    | Media        | Get Media from PK by Private Mobile API
| user_medias_gql(user_id: str, amount: int = 50, sleep: int = 2) | List\[Media] | Get a user's media by Public Graphql API
| user_medias_chunk_gql(user_id: str, sleep: int = 2, end_cursor=None) | Tuple\[List\[Media], str] | Get a page of user's media by Public Graphql API
| user_medias_paginated_gql(user_id: str, amount: int = 0, sleep: int = 2, end_cursor=None) | Tuple\[List\[Media], str] | Get one GraphQL page of user's media; compatibility alias for `instagrapi`
| user_medias_v1(user_id: str, amount: int = 18)                  | List\[Media] | Get a user's media by Private Mobile API
| user_medias_chunk_v1(user_id: str, end_cursor: str = "") | Tuple\[List\[Media], str] | Get a page of user's media by Private Mobile API
| user_medias_paginated_v1(user_id: str, amount: int = 33, end_cursor: str = "") | Tuple\[List\[Media], str] | Get one private API page of user's media; compatibility alias for `instagrapi`
| user_clips_v1(user_id: str, amount: int = 50)                  | List\[Media] | Get a user's clip by Private Mobile API
| user_clips_chunk_v1(user_id: str, end_cursor: str = "") | Tuple\[List\[Media], str] | Get a page of user's clip by Private Mobile API
| user_clips_paginated_v1(user_id: str, amount: int = 50, end_cursor: str = "") | Tuple\[List\[Media], str] | Get one private API page of user's clips; compatibility alias for `instagrapi`
| user_videos_v1(user_id: str, amount: int = 50)                  | List\[Media] | Get a user's video by Private Mobile API
| user_videos_chunk_v1(user_id: int, end_cursor: str = "") | Tuple\[List\[Media], str] | Get a page of user's video by Private Mobile API
| user_videos_paginated_v1(user_id: str, amount: int = 50, end_cursor: str = "") | Tuple\[List\[Media], str] | Get one private API page of user's videos; compatibility alias for `instagrapi`
| usertag_medias_gql(user_id: str, amount: int = 20)              | List\[Media] | Get medias where a user is tagged by Public Graphql API
| usertag_medias_v1(user_id: str, amount: int = 20)               | List\[Media] | Get medias where a user is tagged by Private Mobile API
| usertag_medias_paginated(user_id: str, amount: int = 20, end_cursor: str = "") | Tuple\[List\[Media], str] | Get tagged medias with pagination cursor

### Example:

``` python
>>> from aiograpi import Client
>>> cl = Client()
>>> await cl.login(USERNAME, PASSWORD)

>>> await cl.media_pk_from_code("B-fKL9qpeab")
2278584739065882267

>>> await cl.media_pk_from_code("B8jnuB2HAbyc0q001y3F9CHRSoqEljK_dgkJjo0")
2243811726252050162

>>> await cl.media_pk_from_url("https://www.instagram.com/p/BjNLpA1AhXM/")
1787135824035452364

>>> (await cl.media_info(1787135824035452364)).dict()
{'pk': 1787135824035452364,
 'id': '1787135824035452364_1903424587',
 'code': 'BjNLpA1AhXM',
 'taken_at': datetime.datetime(2018, 5, 25, 15, 46, 53, tzinfo=datetime.timezone.utc),
 'media_type': 8,
 'product_type': '',
 'thumbnail_url': None,
 'location': {'pk': 260916528,
  'name': 'Foros, Crimea',
  'address': '',
  'lng': 33.7878,
  'lat': 44.3914,
  'external_id': 181364832764479,
  'external_id_source': 'facebook_places'},
 'user': {'pk': 1903424587,
  'username': 'example',
  'full_name': 'Example Example',
  'profile_pic_url': HttpUrl('https://scontent-hel3-1.cdninstagram.com/v/t51.2885-19/s150x150/123884060_...&oe=5FD7600E')},
 'comment_count': 0,
 'like_count': 48,
 'caption_text': '@mind__flowers в Форосе под дождём, 24 мая 2018 #downhill #skateboarding #downhillskateboarding #crimea #foros',
 'usertags': [],
 'video_url': None,
 'view_count': 0,
 'video_duration': 0.0,
 'title': '',
 'resources': [{'pk': 1787135361353462176,
   'video_url': HttpUrl('https://scontent-hel3-1.cdninstagram.com/v/t50.2886-16/33464086_3755...0e2362', scheme='https', ...),
   'thumbnail_url': HttpUrl('https://scontent-hel3-1.cdninstagram.com/v/t51.2885-15/e35/3220311...AE7332', scheme='https', ...),
   'media_type': 2},
  {'pk': 1787135762219834098,
   'video_url': HttpUrl('https://scontent-hel3-1.cdninstagram.com/v/t50.2886-16/32895...61320_n.mp4', scheme='https', ...),
   'thumbnail_url': HttpUrl('https://scontent-hel3-1.cdninstagram.com/v/t51.2885-15/e35/3373413....8480_n.jpg', scheme='https', ...),
   'media_type': 2},
  {'pk': 1787133803186894424,
   'video_url': None,
   'thumbnail_url': HttpUrl('https://scontent-hel3-1.cdninstagram.com/v/t51.2885-15/e35/324307712_n.jpg...', scheme='https', ...),
   'media_type': 1}]}

>>> (await cl.media_oembed("https://www.instagram.com/p/B3mr1-OlWMG/")).dict()
{'version': '1.0',
 'title': 'В гостях у ДК @delai_krasivo_kaifui',
 'author_name': 'example',
 'author_url': 'https://www.instagram.com/example',
 'author_id': 1903424587,
 'media_id': '2154602296692269830_1903424587',
 'provider_name': 'Instagram',
 'provider_url': 'https://www.instagram.com',
 'type': 'rich',
 'width': 658,
 'height': None,
 'html': '<blockquote>...',
 'thumbnail_url': 'https://instagram.frix7-1.fna.fbcdn.net/v...0655800983_n.jpg',
 'thumbnail_width': 640,
 'thumbnail_height': 480,
 'can_view': True}


>>> await cl.media_archive('2155832952940083788_1903424587')
True

>>> await cl.media_unarchive('2155832952940083788_1903424587')
True

>>> (await cl.user_medias_gql(1903424587, amount=1))[0].dict()
{'pk': 2592252466151482347,
 'id': '2592252466151482347_1903424587',
 'code': 'CP5h-I1FuPr',
 'taken_at': datetime.datetime(2021, 6, 9, 12, 9, 56, tzinfo=datetime.timezone.utc),
 'media_type': 8,
 'product_type': '',
 'thumbnail_url': None,
 'location': None,
 'user': {'pk': 1903424587,
  'username': 'example',
  'full_name': '',
  'profile_pic_url': None,
  'profile_pic_url_hd': None,
  'stories': []},
 'comment_count': 5,
 'like_count': 63,
 'has_liked': None,
 'caption_text': 'Любимые подвески ♥️ @daewon1song @tensortrucks',
 'usertags': [{'user': {'pk': 53860445,
    'username': 'tensortrucks',
    'full_name': '',
    'profile_pic_url': None,
    'profile_pic_url_hd': None,
    'stories': []},
   'x': 0.3146666667,
   'y': 0.368159204}],
 'video_url': None,
 'view_count': 0,
 'video_duration': 0.0,
 'title': '',
 'resources': [{'pk': 2592252463089480898,
   'video_url': None,
   'thumbnail_url': HttpUrl('https://instagram.fhel5-1.fna.fbcdn.net/v/t51.2885-15/e35/s1080x1080/198404255_317668533141074_749682826672118306_n.jpg?_nc_ht=instagram.fhel5-1.fna.fbcdn.net&_nc_cat=102&_nc_ohc=f8FR-bZNbp8AX-A6YQ4&edm=APU89FABAAAA&ccb=7-4&oh=864bb145a4fa7e523f5cc22f9ac5d015&oe=61145E4F&_nc_sid=86f79a', scheme='https', host='instagram.fhel5-1.fna.fbcdn.net', tld='net', host_type='domain', path='/v/t51.2885-15/e35/s1080x1080/198404255_317668533141074_749682826672118306_n.jpg', query='_nc_ht=instagram.fhel5-1.fna.fbcdn.net&_nc_cat=102&_nc_ohc=f8FR-bZNbp8AX-A6YQ4&edm=APU89FABAAAA&ccb=7-4&oh=864bb145a4fa7e523f5cc22f9ac5d015&oe=61145E4F&_nc_sid=86f79a'),
   'media_type': 1},
  {'pk': 2592252463081081550,
   'video_url': None,
   'thumbnail_url': HttpUrl('https://instagram.fhel5-1.fna.fbcdn.net/v/t51.2885-15/e35/s1080x1080/198228498_303261361473979_3031095263106513772_n.jpg?_nc_ht=instagram.fhel5-1.fna.fbcdn.net&_nc_cat=107&_nc_ohc=C9SeKrAO6poAX-nXhCG&edm=APU89FABAAAA&ccb=7-4&oh=6aab825e12fef746449be22c322762a1&oe=61132FB0&_nc_sid=86f79a', scheme='https', host='instagram.fhel5-1.fna.fbcdn.net', tld='net', host_type='domain', path='/v/t51.2885-15/e35/s1080x1080/198228498_303261361473979_3031095263106513772_n.jpg', query='_nc_ht=instagram.fhel5-1.fna.fbcdn.net&_nc_cat=107&_nc_ohc=C9SeKrAO6poAX-nXhCG&edm=APU89FABAAAA&ccb=7-4&oh=6aab825e12fef746449be22c322762a1&oe=61132FB0&_nc_sid=86f79a'),
   'media_type': 1},
  {'pk': 2592252463056089912,
   'video_url': None,
   'thumbnail_url': HttpUrl('https://instagram.fhel5-1.fna.fbcdn.net/v/t51.2885-15/e35/s1080x1080/199142152_323583732599636_4553823395468898634_n.jpg?_nc_ht=instagram.fhel5-1.fna.fbcdn.net&_nc_cat=108&_nc_ohc=_feIkorChpsAX_wzTff&edm=APU89FABAAAA&ccb=7-4&oh=a22a2f5b30772fbbb02db92b9394e981&oe=61147D59&_nc_sid=86f79a', scheme='https', host='instagram.fhel5-1.fna.fbcdn.net', tld='net', host_type='domain', path='/v/t51.2885-15/e35/s1080x1080/199142152_323583732599636_4553823395468898634_n.jpg', query='_nc_ht=instagram.fhel5-1.fna.fbcdn.net&_nc_cat=108&_nc_ohc=_feIkorChpsAX_wzTff&edm=APU89FABAAAA&ccb=7-4&oh=a22a2f5b30772fbbb02db92b9394e981&oe=61147D59&_nc_sid=86f79a'),
   'media_type': 1}]}

# Use paginated interface to resume fetch from stored cursor

>>> end_cursor = None
... for page in range(3):
...     medias, end_cursor = client.user_medias_chunk_v1(1903424587, 5, end_cursor=end_cursor)
...     print([ m.taken_at.date().isoformat() for m in medias ])
...

['2021-06-09', '2019-10-16', '2019-10-14', '2019-06-13', '2019-06-06']
['2019-06-05', '2019-03-23', '2019-03-23', '2018-11-15', '2018-10-16']
['2018-10-16', '2018-10-11', '2018-10-09', '2018-10-09', '2018-08-02']

```

## Download media

| Method                                                       | Return  | Description                                                         |
| ------------------------------------------------------------ | ------- | ------------------------------------------------------------------- |
| photo_download(media_pk: int, folder: Path)                  | Path    | Download photo (path to photo with best resolution)                  |
| photo_download_by_url(url: str, filename: str, folder: Path) | Path    | Download photo by URL (path to photo with best resolution)           |
| video_download(media_pk: int, folder: Path)                  | Path    | Download video (path to video with best resolution)                  |
| video_download_by_url(url: str, filename: str, folder: Path) | Path    | Download Video by URL (path to video with best resolution)           |
| album_download(media_pk: int, folder: Path)                  | Path    | Download Album (multiple paths to photo/video with best resolutions) |
| album_download_by_urls(urls: List[str], folder: Path)        | Path    | Download Album by URLs (multiple paths to photo/video)              |
| igtv_download(media_pk: int, folder: Path)                   | Path    | Download IGTV (path to video with best resolution)                   |
| igtv_download_by_url(url: str, filename: str, folder: Path)  | Path    | Download IGTV by URL (path to video with best resolution)            |
| clip_download(media_pk: int, folder: Path)                   | Path    | Download Reels Clip (path to video with best resolution)             |
| clip_download_by_url(url: str, filename: str, folder: Path)  | Path    | Download Reels Clip by URL (path to video with best resolution)      |

`photo_download()` resolves photo metadata through the public/web media-info path first so it can use the largest
display resource Instagram exposes for the post, then falls back to private/mobile metadata when the public web
endpoint is gated. It does not rewrite CDN URLs manually.

### Example:

``` python

>>> from aiograpi import Client
>>> cl = Client()
>>> await cl.login(USERNAME, PASSWORD)

>>> await cl.media_pk_from_url("https://www.instagram.com/p/BqNQJleFoSJ/")
1913256444155036809

>>> video_url = (await cl.media_info(1913256444155036809)).video_url
>>> await cl.video_download_by_url(video_url, folder='/tmp')
PosixPath('/tmp/45588546_367538213983456_6830188946193737023_n.mp4')

```

If Instagram returns a `Content-Length` header and the downloaded file is shorter, download helpers remove the partial file and raise `ClientIncompleteReadError`.

``` python

>>> await cl.media_pk_from_url("http://www.instagram.com/p/BjNLpA1AhXM/")
1787135824035452364

>>> await cl.album_download(1787135824035452364)
[PosixPath('/app/example_1787135361353462176.mp4'),
 PosixPath('/app/example_1787135762219834098.mp4'),
 PosixPath('/app/example_1787133803186894424.jpg')]

```

## Upload media

Upload medias to your feed. Common arguments:

* `path` - Path to source file
* `caption`  - Text for you post
* `usertags` - List[Usertag] of mention users (see `Usertag` in [types.py](https://github.com/subzeroid/aiograpi/blob/main/aiograpi/types.py)); album uploads also accept `List[List[Usertag]]` for per-slide tags
* `location` - Location (e.g. `Location(name='Test', lat=42.0, lng=42.0)`)
* `schedule_at` - Unix timestamp in seconds or `datetime` for scheduled publishing on eligible professional accounts

| Method                                                                                                                                 | Return  | Description
| -------------------------------------------------------------------------------------------------------------------------------------- | ------- | ------------------
| photo_upload(path: Path, caption: str, upload_id: str, usertags: List[Usertag], location: Location, extra_data: Dict = {}, schedule_at: int \| datetime = None, coauthor_user_ids: List[int \| str] = None)             | Media   | Upload photo (Support JPG files)
| photo_upload_with_music(path: Path, caption: str, track: Track, extra_data: Dict = {}, schedule_at: int \| datetime = None) | Media | Upload feed photo with music metadata
| video_upload(path: Path, caption: str, thumbnail: Path, usertags: List[Usertag], location: Location, extra_data: Dict = {}, schedule_at: int \| datetime = None, coauthor_user_ids: List[int \| str] = None)            | Media   | Upload video (Support MP4 files)
| album_upload(paths: List[Path], caption: str, usertags: List[Usertag] or List[List[Usertag]], location: Location, extra_data: Dict = {}, schedule_at: int \| datetime = None, coauthor_user_ids: List[int \| str] = None) | Media   | Upload Album (Support JPG/MP4 files)
| album_upload_with_music(paths: List[Path], caption: str, track: Track, usertags: List[Usertag] or List[List[Usertag]], extra_data: Dict = {}, schedule_at: int \| datetime = None) | Media | Upload feed album/carousel with music metadata
| igtv_upload(path: Path, title: str, caption: str, thumbnail: Path, usertags: List[Usertag], location: Location, extra_data: Dict = {}) | Media   | Upload IGTV (Support MP4 files)
| clip_upload(path: Path, caption: str, thumbnail: Path, usertags: List[Usertag], location: Location, extra_data: Dict = {}, trial: bool = False, share_to_facebook: bool = False, topics: List[int \| str] = None) | Media | Upload Reels Clip (Support MP4 files), optionally as a Trial Reel, cross-posted to Facebook, or published with Reel topic `fit_id` values
| clip_music_extra_data(track: Track or dict, extra_data: Dict = {}) | dict | Build Reels music configure fields for manual `clip_upload(..., extra_data=...)`
| clip_upload_with_music(path: Path, caption: str, track: Track or dict, thumbnail: Path = None, extra_data: Dict = {}) | Media | Upload a Reel with music metadata without local audio muxing
| clip_upload_as_reel_with_music(path: Path, caption: str, track: Track, extra_data: Dict = {}) | Media | Upload a Reel after locally muxing the track into the video with MoviePy
| clip_info_for_creation()                                      | Dict    | Get Reel creation preflight configuration for the current user
| clip_interest_topics()                                        | List[dict] | Get Reel topic catalog items with `name` and `fit_id` values for `clip_upload(..., topics=...)`
| clip_trial_eligible()                                         | bool    | Check whether Reel creation preflight reports Trial Reels enabled
| clip_share_to_fb_config()                                      | Dict    | Get Reel Facebook sharing configuration for the current user
| clip_share_to_fb_unified_config() | Dict | Get the Android cross-posting unified config used by the Reel composer
| clip_share_to_fb_unified_destination(config: Dict = None) | dict | Resolve confirmed Reel Facebook destination fields from the unified cross-posting config
| clip_share_to_fb_destination(config: Dict = None, destination_id: str = None, destination_type: str = None) | dict | Resolve confirmed Reel Facebook destination fields without treating Account Center linking ids as publish destinations
| clip_share_to_fb_extra_data(config: Dict = None, destination_id: str = None, destination_type: str = None) | Dict | Build modern Reel Facebook cross-post configure fields for manual `extra_data`

For video uploads in Android environments, pass `thumbnail=...` to avoid automatic thumbnail generation, or install the optional video dependencies, MoviePy `2.2.1`, and executable ffmpeg. See [Pydroid and ffmpeg](pydroid.md) and [Termux](termux.md).

Scheduled publishing is available only where the Instagram app enables scheduled content, typically professional
creator/business accounts. `schedule_at` works for feed photo, feed video, and album/carousel uploads. Reels, IGTV,
Story, Direct, and cutout sticker upload helpers do not use this scheduled publishing flow.

Trial Reels use the same upload method:

``` python
media = await cl.clip_upload(
    Path("reel.mp4"),
    "Trying a new format",
    thumbnail=Path("reel-thumb.jpg"),
    trial=True,
)
```

Reel topics use Instagram's interest topic `fit_id` values. Call `clip_interest_topics()` to get the current catalog, then pass selected ids with `clip_upload(..., topics=[topic["fit_id"]])`; aiograpi sends them as the Android `interest_topics` configure field.

``` python
topics = await cl.clip_interest_topics()
technology_topic = next(topic for topic in topics if topic["name"] == "Technology")
media = await cl.clip_upload(
    Path("reel.mp4"),
    "Reel with a topic",
    topics=[technology_topic["fit_id"]],
)
```

Facebook Reel sharing requires a Facebook account/page linked in the Instagram app. Modern Android app builds no longer use only `{"share_to_facebook": 1}` for Reels; they also send destination and cross-posting fields such as `share_to_fb_destination_id`, `share_to_fb_destination_type`, `no_token_crosspost`, and `attempt_id`.

`clip_share_to_fb_config()` calls the lightweight Reel sharing preflight endpoint. On recent app versions this response contains availability flags, not the full Account Center destination state, and some linked accounts can still return `share_to_fb_unavailable=True` even when the Instagram app can cross-post manually. When `clip_upload(..., share_to_facebook=True)` has no manual destination override, aiograpi now falls back to Android's `CrosspostingUnifiedConfigsQuery` via `clip_share_to_fb_unified_config()` and uses `clip_share_to_fb_unified_destination()` only if that response contains confirmed Reel-to-Facebook destination fields. Use `clip_share_to_fb_destination()` when a config or captured app response already contains confirmed destination fields; it normalizes `destination_id`, `destination_type`, optional audience, and validation bypass values. For accounts where the app can cross-post manually but automatic discovery still has no destination, pass `fb_destination_id` and `fb_destination_type="USER"` or `"PAGE"` to `clip_upload(...)`, or build `extra_data` manually with `clip_share_to_fb_extra_data(...)`. If neither the preflight/unified config data nor the caller provides a destination, aiograpi raises `ClientError` before uploading video bytes. The Reel cross-post `attempt_id` is generated automatically; only pass it to `clip_share_to_fb_extra_data(...)` when replaying or testing a specific low-level payload.
`bloks_fxcal_link_reels_share()` exposes the raw Account Center Bloks link action seen on the Reel composer surface, but it starts an app linking flow and does not replace the interactive Facebook linking step in Instagram. Treat Account Center Bloks `fbid`, auth, and linking values as linking context, not as `fb_destination_id`; only use them as a Reel publish destination after verifying that the final Reel configure request sends the same value as `share_to_fb_destination_id`. See [subzeroid/instagrapi#2556](https://github.com/subzeroid/instagrapi/issues/2556) for tracking automatic destination discovery.

``` python
media = await cl.clip_upload(
    Path("reel.mp4"),
    "Cross-posting this Reel to Facebook",
    thumbnail=Path("reel-thumb.jpg"),
    share_to_facebook=True,
)

media = await cl.clip_upload(
    Path("reel.mp4"),
    "Cross-posting with explicit Facebook destination",
    thumbnail=Path("reel-thumb.jpg"),
    share_to_facebook=True,
    fb_destination_id="FACEBOOK_DESTINATION_ID",
    fb_destination_type="USER",
)

fb_extra = await cl.clip_share_to_fb_extra_data(
    destination_id="FACEBOOK_DESTINATION_ID",
    destination_type="USER",
)
media = await cl.clip_upload(
    Path("reel.mp4"),
    "Cross-posting with explicit Facebook destination",
    thumbnail=Path("reel-thumb.jpg"),
    extra_data=fb_extra,
)
```

Feed music helpers attach Instagram music metadata to photo and carousel posts:

``` python
browser = await cl.music_in_feed_audio_browser()
track = browser["items"][0]["track"]
media = await cl.photo_upload_with_music(
    Path("photo.jpg"),
    "caption",
    track,
    alacorn_session_id=browser["alacorn_session_id"],
)
```

In `extra_data`, you can pass additional media settings, for example:

| Method                        | Type   | Description
| ----------------------------- | ------ | ------------------
| custom_accessibility_caption  | String | [Set alternative text](https://github.com/subzeroid/instagrapi/issues/351) `{"custom_accessibility_caption": "ALT TEXT HERE"}`
| like_and_view_counts_disabled | Int    | [Disable like and view counts](https://github.com/subzeroid/instagrapi/issues/382) `{"like_and_view_counts_disabled": 1}`
| disable_comments              | Int    | Disable comments `{"disable_comments": 1}`
| invite_coauthor_user_ids      | List   | Low-level coauthor invite field. Prefer `coauthor_user_ids=[...]` on `photo_upload`, `video_upload`, or `album_upload`

Accepted Instagram Collabs/coauthor users from private media payloads are available as `media.coauthor_producers`. This is separate from upload-time `coauthor_user_ids`, which only sends collaborator invitations.

Extended media metadata from Instagram payloads is available on `Media` when returned by the source API, including caption edit state, dimensions, audio presence, hidden count state, viewer save/reshare state, paid partnership/affiliate flags, DASH video info, clips music attribution, and inline comment previews.

Extended `Media` metadata fields:

| Field | Type | Notes |
| --- | --- | --- |
| `comments_preview` | `MediaCommentsPreview` or `None` | Inline public/web comment preview when Instagram includes `edge_media_to_parent_comment` or preview comment edges. Use full comments helpers for complete pagination. |
| `hoisted_comments` | `List[MediaInlineComment]` | Comments Instagram hoists separately from the regular preview list. Usually empty. |
| `comments_preview.count` | `int` | Total count reported for the inline preview edge. |
| `comments_preview.has_next_page` | `bool` | Whether the inline preview edge has more comments after `end_cursor`. |
| `comments_preview.end_cursor` | `str` or `None` | Cursor reported by the inline preview edge. |
| `comments_preview.comments` | `List[MediaInlineComment]` | Inline parent comments already present in the media payload. |
| `MediaInlineComment.pk` | `str` | Comment id. |
| `MediaInlineComment.text` | `str` | Comment text. |
| `MediaInlineComment.user` | `UserShort` | Comment author. |
| `MediaInlineComment.created_at_utc` | `datetime` | Comment creation time. |
| `MediaInlineComment.has_liked` | `bool` or `None` | Current viewer like state when Instagram sends it. |
| `MediaInlineComment.like_count` | `int` or `None` | Inline like count from the comment edge. |
| `MediaInlineComment.replied_to_comment_id` | `str` or `None` | Parent comment id for inline replies. |
| `MediaInlineComment.did_report_as_spam` | `bool` or `None` | Viewer report state when Instagram sends it. |
| `MediaInlineComment.is_restricted_pending` | `bool` or `None` | Restricted/pending state when Instagram sends it. |
| `MediaInlineComment.replies_count` | `int` | Number of threaded replies reported inline. |
| `MediaInlineComment.replies` | `List[MediaInlineComment]` | Inline threaded replies already present in the media payload. |

### Example:

``` python
>>> from aiograpi import Client

>>> cl = Client()
>>> await cl.login(USERNAME, PASSWORD)

>>> media = await cl.photo_upload(
    "/app/image.jpg",
    "Test caption for photo with #hashtags and mention users such @example",
    extra_data={
        "custom_accessibility_caption": "alt text example",
        "like_and_view_counts_disabled": 1,
        "disable_comments": 1,
    }
)

>>> media.dict()
{'pk': 2573347427873726764,
 'id': '2573347427873726764_1903424587',
 'code': 'CO2Xdn6FCEs',
 'taken_at': datetime.datetime(2021, 5, 14, 10, 9, tzinfo=datetime.timezone.utc),
 'media_type': 1,
 'product_type': 'feed',
 'thumbnail_url': HttpUrl('https://instagram.fhel5-1.fna.fbcdn.net/v/t51.2885-15/e35/185486538_463522984736407_6315244509641560230_n.jpg?se=8&tp=1&_nc_ht=instagram.fhel5-1.fna.fbcdn.net&_nc_cat=107&_nc_ohc=6tBMsh9HlmMAX9zI_jc&edm=ACqnv0EBAAAA&ccb=7-4&oh=2b46f1e9fbd2416eb7d08b398e0f639e&oe=60C30437&_nc_sid=9ec724&ig_cache_key=MjU3MzM0NzQyNzg3MzcyNjc2NA%3D%3D.2-ccb7-4', scheme='https', host='instagram.fhel5-1.fna.fbcdn.net', tld='net', host_type='domain', path='/v/t51.2885-15/e35/185486538_463522984736407_6315244509641560230_n.jpg', query='se=8&tp=1&_nc_ht=instagram.fhel5-1.fna.fbcdn.net&_nc_cat=107&_nc_ohc=6tBMsh9HlmMAX9zI_jc&edm=ACqnv0EBAAAA&ccb=7-4&oh=2b46f1e9fbd2416eb7d08b398e0f639e&oe=60C30437&_nc_sid=9ec724&ig_cache_key=MjU3MzM0NzQyNzg3MzcyNjc2NA%3D%3D.2-ccb7-4'),
 'location': None,
 'user': {'pk': 1903424587,
  'username': 'example',
  'full_name': 'Example Example',
  'profile_pic_url': HttpUrl('https://instagram.fhel5-1.fna.fbcdn.net/v/t51.2885-19/s150x150/156689363_269505058076642_6448820957073669709_n.jpg?tp=1&_nc_ht=instagram.fhel5-1.fna.fbcdn.net&_nc_ohc=EtzrL0pAdg8AX-Xq8yS&edm=ACqnv0EBAAAA&ccb=7-4&oh=e2fd6a9d362f8587ea8123f23b248f1b&oe=60C2CB91&_nc_sid=9ec724', scheme='https', host='instagram.fhel5-1.fna.fbcdn.net', tld='net', host_type='domain', path='/v/t51.2885-19/s150x150/156689363_269505058076642_6448820957073669709_n.jpg', query='tp=1&_nc_ht=instagram.fhel5-1.fna.fbcdn.net&_nc_ohc=EtzrL0pAdg8AX-Xq8yS&edm=ACqnv0EBAAAA&ccb=7-4&oh=e2fd6a9d362f8587ea8123f23b248f1b&oe=60C2CB91&_nc_sid=9ec724'),
  'stories': []},
 'comment_count': 0,
 'like_count': 0,
 'has_liked': None,
 'caption_text': 'Test caption for photo with #hashtags and mention users such @example',
 'usertags': [],
 'video_url': None,
 'view_count': 0,
 'video_duration': 0.0,
 'title': '',
 'resources': []}
```

Now let's mention users (Usertag) and location:

``` python
>>> from aiograpi import Client
>>> from aiograpi.types import Usertag, Location

>>> cl = Client()
>>> await cl.login(USERNAME, PASSWORD)

>>> example = await cl.user_info_by_username('example')
>>> media = await cl.photo_upload(
    "/app/image.jpg",
    "Test caption for photo with #hashtags and mention users such @example",
    usertags=[Usertag(user=example, x=0.5, y=0.5)],
    location=Location(name='Russia, Saint-Petersburg', lat=59.96, lng=30.29)
)

>>> other = await cl.user_info_by_username('other')
>>> album = await cl.album_upload(
    ["/app/image.jpg", "/app/image2.jpg"],
    "Album with per-slide tags",
    usertags=[
        [Usertag(user=example, x=0.5, y=0.5)],
        [Usertag(user=other, x=0.25, y=0.75)],
    ],
)

>>> media.dict()
{'pk': 2573355619819242434,
 'id': '2573355619819242434_1903424587',
 'code': 'CO2ZU1QFMPC',
 'taken_at': datetime.datetime(2021, 5, 14, 10, 25, 16, tzinfo=datetime.timezone.utc),
 'media_type': 1,
 'product_type': 'feed',
 'thumbnail_url': HttpUrl('https://instagram.fhel5-1.fna.fbcdn.net/v/t51.2885-15/e35/185426950_474602463640866_4228057388625412955_n.jpg?se=8&tp=1&_nc_ht=instagram.fhel5-1.fna.fbcdn.net&_nc_cat=106&_nc_ohc=7NrVvAEG7f4AX_XPaOK&edm=ACqnv0EBAAAA&ccb=7-4&oh=bd2c90c2dcb693184e07c2777e09bb0b&oe=60C4E326&_nc_sid=9ec724&ig_cache_key=MjU3MzM1NTYxOTgxOTI0MjQzNA%3D%3D.2-ccb7-4', scheme='https', host='instagram.fhel5-1.fna.fbcdn.net', tld='net', host_type='domain', path='/v/t51.2885-15/e35/185426950_474602463640866_4228057388625412955_n.jpg', query='se=8&tp=1&_nc_ht=instagram.fhel5-1.fna.fbcdn.net&_nc_cat=106&_nc_ohc=7NrVvAEG7f4AX_XPaOK&edm=ACqnv0EBAAAA&ccb=7-4&oh=bd2c90c2dcb693184e07c2777e09bb0b&oe=60C4E326&_nc_sid=9ec724&ig_cache_key=MjU3MzM1NTYxOTgxOTI0MjQzNA%3D%3D.2-ccb7-4'),
 'location': {'pk': 107617247320879,
  'name': 'Russia, Saint-Petersburg',
  'address': 'Russia, Saint-Petersburg',
  'lng': 30.30605,
  'lat': 59.93318,
  'external_id': 107617247320879,
  'external_id_source': 'facebook_places'},
 'user': {'pk': 1903424587,
  'username': 'example',
  'full_name': 'Example Example',
  'profile_pic_url': HttpUrl('https://instagram.fhel5-1.fna.fbcdn.net/v/t51.2885-19/s150x150/156689363_269505058076642_6448820957073669709_n.jpg?tp=1&_nc_ht=instagram.fhel5-1.fna.fbcdn.net&_nc_ohc=EtzrL0pAdg8AX-Xq8yS&edm=ACqnv0EBAAAA&ccb=7-4&oh=e2fd6a9d362f8587ea8123f23b248f1b&oe=60C2CB91&_nc_sid=9ec724', scheme='https', host='instagram.fhel5-1.fna.fbcdn.net', tld='net', host_type='domain', path='/v/t51.2885-19/s150x150/156689363_269505058076642_6448820957073669709_n.jpg', query='tp=1&_nc_ht=instagram.fhel5-1.fna.fbcdn.net&_nc_ohc=EtzrL0pAdg8AX-Xq8yS&edm=ACqnv0EBAAAA&ccb=7-4&oh=e2fd6a9d362f8587ea8123f23b248f1b&oe=60C2CB91&_nc_sid=9ec724'),
  'stories': []},
 'comment_count': 0,
 'like_count': 0,
 'has_liked': None,
 'caption_text': 'Test caption for photo with #hashtags and mention users such @example',
 'usertags': [{'user': {'pk': 1903424587,
    'username': 'example',
    'full_name': 'Example Example',
    'profile_pic_url': HttpUrl('https://instagram.fhel5-1.fna.fbcdn.net/v/t51.2885-19/s150x150/156689363_269505058076642_6448820957073669709_n.jpg?tp=1&_nc_ht=instagram.fhel5-1.fna.fbcdn.net&_nc_ohc=EtzrL0pAdg8AX-Xq8yS&edm=ACqnv0EBAAAA&ccb=7-4&oh=e2fd6a9d362f8587ea8123f23b248f1b&oe=60C2CB91&_nc_sid=9ec724', scheme='https', host='instagram.fhel5-1.fna.fbcdn.net', tld='net', host_type='domain', path='/v/t51.2885-19/s150x150/156689363_269505058076642_6448820957073669709_n.jpg', query='tp=1&_nc_ht=instagram.fhel5-1.fna.fbcdn.net&_nc_ohc=EtzrL0pAdg8AX-Xq8yS&edm=ACqnv0EBAAAA&ccb=7-4&oh=e2fd6a9d362f8587ea8123f23b248f1b&oe=60C2CB91&_nc_sid=9ec724'),
    'stories': []},
   'x': 0.5,
   'y': 0.5}],
 'video_url': None,
 'view_count': 0,
 'video_duration': 0.0,
 'title': '',
 'resources': []}
```

For `album_upload`, nested `usertags` are matched by index with `paths`: `usertags[0]` applies to `paths[0]`, `usertags[1]` applies to `paths[1]`, and so on. A flat `List[Usertag]` is still accepted for backward compatibility and tags only the first carousel item.

When reading an album, the same index rule applies to resources: tags for the first carousel item are in `media.resources[0].usertags`, tags for the second item are in `media.resources[1].usertags`, etc.

Reels:

Timeline helpers:

```python
>>> first_page = await cl.get_timeline_feed("cold_start_fetch")
>>> second_page = await cl.get_timeline_feed(max_id=first_page["next_max_id"])
>>> await cl.reels(amount=10)
>>> await cl.explore_reels(amount=10)
>>> await cl.friends_reels(amount=10)
```

`get_timeline_feed()` remembers media ids from the previous response and sends `seen_posts` plus minimal `feed_view_info` when `max_id` is used. For stateless pagination, pass `seen_posts=...` and `feed_view_info=...` explicitly.

```python
>>> clips = await cl.user_clips_v1(25025320, amount=2)
>>> clips[0].dict()

{'pk': '3052048407587698594',
 'id': '3052048407587698594_25025320',
 'code': 'CpbDdszj7ei',
 'taken_at': datetime.datetime(2023, 3, 5, 21, 50, 4, tzinfo=datetime.timezone.utc),
 'media_type': 2,
 'product_type': 'clips',
 'thumbnail_url': HttpUrl('https://scontent-den4-1.cdninstagram.com/v/t51.2885-15/333966975_152901010970043_8971338145148712917_n.jpg?stp=dst-jpg_e15_p150x150&_nc_ht=scontent-den4-1.cdninstagram.com&_nc_cat=1&_nc_ohc=rRuJ7u4YrqEAX-UEMFq&edm=ACHbZRIBAAAA&ccb=7-5&ig_cache_key=MzA1MjA0ODQwNzU4NzY5ODU5NA%3D%3D.2-ccb7-5&oh=00_AfC_tNEWVjJLM5RQYUiQJFHQZSmvnDtAcpzs42DRSYt1pQ&oe=6409C451&_nc_sid=4a9e64', scheme='https', host='scontent-den4-1.cdninstagram.com', tld='com', host_type='domain', port='443', path='/v/t51.2885-15/333966975_152901010970043_8971338145148712917_n.jpg', query='stp=dst-jpg_e15_p150x150&_nc_ht=scontent-den4-1.cdninstagram.com&_nc_cat=1&_nc_ohc=rRuJ7u4YrqEAX-UEMFq&edm=ACHbZRIBAAAA&ccb=7-5&ig_cache_key=MzA1MjA0ODQwNzU4NzY5ODU5NA%3D%3D.2-ccb7-5&oh=00_AfC_tNEWVjJLM5RQYUiQJFHQZSmvnDtAcpzs42DRSYt1pQ&oe=6409C451&_nc_sid=4a9e64'),
 'location': {'pk': 213011753,
  'name': 'Sydney, Australia',
  'phone': '',
  'website': '',
  'category': '',
  'hours': {},
  'address': '',
  'city': '',
  'zip': None,
  'lng': 151.20797,
  'lat': -33.86751,
  'external_id': 110884905606108,
  'external_id_source': 'facebook_places'},
....
}
```

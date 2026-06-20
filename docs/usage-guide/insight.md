# Insights

Get statistics by medias. Common arguments:

* `post_type` - Media type: "ALL", "CAROUSEL_V2", "IMAGE", "SHOPPING", "VIDEO".
* `time_frame` - Time frame for media publishing date: "ONE_WEEK", "ONE_MONTH", "THREE_MONTHS", "SIX_MONTHS", "ONE_YEAR", "TWO_YEARS".
* `data_ordering` - Data ordering in instagram response: "REACH_COUNT", "LIKE_COUNT", "FOLLOW", "SHARE_COUNT", "BIO_LINK_CLICK", "COMMENT_COUNT", "IMPRESSION_COUNT", "PROFILE_VIEW", "VIDEO_VIEW_COUNT", "SAVE_COUNT".

These arguments are exposed as `POST_TYPE`, `TIME_FRAME`, and `DATA_ORDERING` Literal aliases.

| Method                                                                                             | Return             | Description
| -------------------------------------------------------------------------------------------------- | ------------------ | -------------------------------
| insights_media_feed_all(post_type: POST_TYPE = "ALL", time_frame: TIME_FRAME = "TWO_YEARS", data_ordering: DATA_ORDERING = "REACH_COUNT", count: int = 0, sleep: int = 2) | List[Dict] | Return medias with insights
| insights_account()                                                                                 | Dict               | Get statistics by your account
| insights_media(media_pk: int)                                                                      | Dict               | Get statistics by your media


Example:

``` python
from aiograpi import Client

cl = Client()
await cl.login(USERNAME, PASSWORD)

await cl.insights_media_feed_all("VIDEO", "ONE_WEEK", "LIKE_COUNT", 42)
await cl.insights_account()

media_pk = await cl.media_pk_from_url('https://www.instagram.com/p/CP5h-I1FuPr/')
await cl.insights_media(media_pk)
```

Notes:

* These methods require an authenticated business/professional account. Personal accounts can raise `UserError`.
* `insights_media()` raises `MediaError` when Instagram does not return insight data for the requested media.
* If Instagram returns media metadata without `inline_insights_node`, `insights_media()` raises `MediaError` instead of returning partial counts with null insight metrics.

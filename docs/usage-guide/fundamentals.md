# Usage Guide

This section provides detailed descriptions of all the ways `aiograpi` can be used. If you are new to `aiograpi`, the
[Getting Started](../getting-started.md) page provides a gradual introduction of the basic functionality with examples.

## Public vs Private Requests

* Many `_gql` methods use public web GraphQL, while `user_medias*_gql()` first uses the private app timeline and falls back to public GraphQL on `ClientError`. Legacy `?__a=1` helpers were removed because that public web response is no longer reliable.
* `Private` (authorized request via mobile api) methods have `_v1` suffix

With private authorization or a saved session, `media_info()` and `user_info()` try the private mobile API first and fall back to public web lookup. Without it, they try public web lookup first, then the private API if that lookup fails. Cached results can avoid a new request.

## Detailed Sections

* [Index](../index.md)
* [Getting Started](../getting-started.md)
* [Interactions](interactions.md)
  * [`Media`](media.md) - Publication (also called post): Photo, Video, Album, IGTV and Reels
  * [`Resource`](media.md) - Part of Media (for albums)
  * [`MediaOembed`](media.md) - Short version of Media
  * [`Account`](account.md) - Full private info for your account (e.g. email, phone_number)
  * [`User`](user.md) - Full public user data
  * [`UserShort`](user.md) - Short public user data (used in Usertag, Comment, Media, Direct Message)
  * [`Usertag`](user.md) - Tag user in Media (coordinates + UserShort)
  * [`Location`](location.md) - GEO location (GEO coordinates, name, address)
  * [`Hashtag`](hashtag.md) - Hashtag object (id, name, picture)
  * [`Collection`](collection.md) - Collection of medias (name, picture and list of medias)
  * [`Comment`](comment.md) - Comments to Media
  * [`Highlight`](highlight.md) - Highlights
  * [`Story`](story.md) - Story
  * [`StoryLink`](story.md) - Link (Swipe up)
  * [`StoryLocation`](story.md) - Tag Location in Story (as sticker)
  * [`StoryMention`](story.md) - Mention users in Story (user, coordinates and dimensions)
  * [`StoryHashtag`](story.md) - Hashtag for story (as sticker)
  * [`StorySticker`](story.md) - Tag sticker to story (for example from giphy)
  * [`StoryBuild`](story.md) - [StoryBuilder](https://github.com/subzeroid/aiograpi/blob/main/aiograpi/story.py) return path to photo/video and mention co-ordinates
  * [`DirectThread`](direct.md) - Thread (topic) with messages in Direct Message
  * [`DirectMessage`](direct.md) - Message in Direct Message
  * [`Insight`](insight.md) - Insights for a post
  * [`Track`](track.md) - Music track (for Reels/Clips)
* [Best Practices](best-practices.md)
* [Development Guide](../development-guide.md)
* [Handle Exceptions](handle_exception.md)
* [Exceptions](../exceptions.md)

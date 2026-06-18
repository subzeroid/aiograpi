# Types

`aiograpi.types` contains the public Pydantic models returned by high-level client methods and accepted by upload/story helpers.

Import models directly when you need structured input objects:

```python
from aiograpi.types import Location, Media, StoryMention, UserShort, Usertag
```

## How To Read Fields

Required fields have no default value. `Optional[...]` fields may be absent from Instagram responses or returned as `null`. Fields with raw `dict` or `list` types intentionally preserve Instagram data whose shape is not stable enough for a dedicated public model yet.

## Common Models

| Model | Common source | Notes |
| --- | --- | --- |
| `Account` | `account_info()` | Private account profile for the authenticated user, including email/phone fields when Instagram returns them. |
| `User` | `user_info(...)`, `user_info_by_username(...)` | Full public profile fields such as counts, biography, public contacts, business category, location, and messaging ids. |
| `UserShort` | user lists, tags, comments, direct threads | Compact user profile used inside many other models. Preserves newer v2 fields such as `fbid_v2`, `profile_pic_id`, `account_badges`, and `friendship_status`. |
| `Media` | `media_info(...)`, feeds, timelines, hashtag media | Main post/Reel/album object. Includes caption/count flags, resources, usertags, coauthors, DASH info, music attribution, and inline comment previews when returned. |
| `Resource` | `Media.resources` | Album child media with thumbnail/video URLs and nested usertags. |
| `Comment` | comment helpers | Public comment model with author, text, like state/count, and reply target. |
| `DirectThread` | direct thread helpers | Direct conversation shell with participants, messages, mute/pin/group state, and activity metadata. |
| `DirectMessage` | direct message helpers | Individual direct item with text, media shares, visual media, links, reactions, replies, and seen state. |
| `Story` | story/reel helpers | Story media object with stickers, mentions, hashtags, links, locations, sponsor tags, and video metadata. |
| `Location` | location helpers and upload metadata | Place metadata used by media and story publishing flows. |
| `Hashtag` | hashtag helpers | Hashtag identity, media count, and profile picture. |
| `Track` | music/Reels helpers | Music track metadata and audio URLs when available. |
| `Note` | notes helpers | Direct Notes payload with author, audience, timestamps, and style flags. |

## Account And User Models

::: aiograpi.types.Account

::: aiograpi.types.User

::: aiograpi.types.UserShort

::: aiograpi.types.RelationshipShort

::: aiograpi.types.Relationship

::: aiograpi.types.Viewer

::: aiograpi.types.Usertag

::: aiograpi.types.About

::: aiograpi.types.BioLink

::: aiograpi.types.Broadcast

::: aiograpi.types.AddressBookPhone

::: aiograpi.types.AddressBookEmail

::: aiograpi.types.AddressBookContact

## Media Models

::: aiograpi.types.Media

::: aiograpi.types.Resource

::: aiograpi.types.MediaOembed

::: aiograpi.types.MediaXma

::: aiograpi.types.MediaDimensions

::: aiograpi.types.MediaDashInfo

::: aiograpi.types.MediaInlineComment

::: aiograpi.types.MediaCommentsPreview

::: aiograpi.types.SharedMediaImageCandidate

::: aiograpi.types.SharedMediaImageVersions

::: aiograpi.types.AdditionalCandidates

::: aiograpi.types.ScrubberSpritesheetInfo

::: aiograpi.types.ScrubberSpritesheetInfoCandidates

::: aiograpi.types.Collection

::: aiograpi.types.Comment

::: aiograpi.types.Location

::: aiograpi.types.Hashtag

::: aiograpi.types.Guide

::: aiograpi.types.Highlight

::: aiograpi.types.Share

## Reels And Music Models

::: aiograpi.types.ClipsMetadata

::: aiograpi.types.ClipsAchievementsInfo

::: aiograpi.types.AudioReattributionInfo

::: aiograpi.types.ClipsAdditionalAudioInfo

::: aiograpi.types.ClipsAudioRankingInfo

::: aiograpi.types.ClipsBrandedContentTagInfo

::: aiograpi.types.ClipsContentAppreciationInfo

::: aiograpi.types.ClipsMashupInfo

::: aiograpi.types.ClipsConsumptionInfo

::: aiograpi.types.ClipsFbDownstreamUseXpostMetadata

::: aiograpi.types.ClipsIgArtist

::: aiograpi.types.ClipsOriginalSoundInfo

::: aiograpi.types.ClipsReusableTextColor

::: aiograpi.types.ClipsReusableTextInfo

::: aiograpi.types.ClipsMusicAttributionInfo

::: aiograpi.types.Track

## Story Models

::: aiograpi.types.Story

::: aiograpi.types.StoryMention

::: aiograpi.types.StoryMedia

::: aiograpi.types.StoryHashtag

::: aiograpi.types.StoryLocation

::: aiograpi.types.StoryStickerLink

::: aiograpi.types.StorySticker

::: aiograpi.types.StoryPoll

::: aiograpi.types.StoryBuild

::: aiograpi.types.StoryLink

::: aiograpi.types.StoryArchiveDay

## Direct Models

::: aiograpi.types.DirectThread

::: aiograpi.types.DirectShortThread

::: aiograpi.types.DirectMessage

::: aiograpi.types.DirectResponse

::: aiograpi.types.DirectMedia

::: aiograpi.types.ReplyMessage

::: aiograpi.types.MessageReaction

::: aiograpi.types.MessageReactions

::: aiograpi.types.MessageLink

::: aiograpi.types.LinkContext

::: aiograpi.types.LastSeenInfo

::: aiograpi.types.DisappearingMessagesSeenState

::: aiograpi.types.FallbackUrl

::: aiograpi.types.DirectMessageImageCandidate

::: aiograpi.types.DirectMessageImageVersions

::: aiograpi.types.VideoVersion

::: aiograpi.types.FriendshipStatus

::: aiograpi.types.VisualMedia

::: aiograpi.types.VisualMediaContent

::: aiograpi.types.VisualMediaUser

::: aiograpi.types.ExpiringMediaActionSummary

## Notes

::: aiograpi.types.Note

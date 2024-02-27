from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, FilePath, ValidationError, validator  # ConfigDict


def validate_external_url(cls, v):
    if v is None or (v.startswith("http") and "://" in v) or isinstance(v, str):
        return v
    raise ValidationError("external_url must been URL or string")


# class TypesBaseModel(BaseModel):
#     model_config = ConfigDict(
#         coerce_numbers_to_str=True
#     )


class Resource(BaseModel):
    pk: str
    video_url: Optional[str] = None  # for Video and IGTV
    thumbnail_url: str
    media_type: int
    image_versions: List[dict] = []
    video_versions: List[dict] = []


class User(BaseModel):
    pk: str
    username: str
    full_name: Optional[str] = None
    is_private: Optional[bool] = None
    profile_pic_url: str
    profile_pic_url_hd: Optional[str] = None
    is_verified: Optional[bool] = None
    media_count: Optional[int] = None
    follower_count: Optional[int] = None
    following_count: Optional[int] = None
    biography: Optional[str] = ""
    external_url: Optional[str] = None
    account_type: Optional[int] = None
    is_business: Optional[bool] = None

    public_email: Optional[str] = None
    contact_phone_number: Optional[str] = None
    public_phone_country_code: Optional[str] = None
    public_phone_number: Optional[str] = None
    business_contact_method: Optional[str] = None
    business_category_name: Optional[str] = None
    category_name: Optional[str] = None
    category: Optional[str] = None

    address_street: Optional[str] = None
    city_id: Optional[str] = None
    city_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    zip: Optional[str] = None
    instagram_location_id: Optional[str] = None
    interop_messaging_user_fbid: Optional[str] = None

    _external_url = validator("external_url", allow_reuse=True)(validate_external_url)


class About(BaseModel):
    username: Optional[str] = ""
    is_verified: Optional[bool] = False
    country: Optional[str] = ""
    date: Optional[str] = ""
    former_usernames: Optional[str] = ""


class Account(BaseModel):
    pk: str
    username: str
    full_name: str
    is_private: bool
    profile_pic_url: str
    is_verified: bool
    biography: Optional[str] = ""
    external_url: Optional[str] = None
    is_business: bool
    birthday: Optional[str] = None
    phone_number: Optional[str] = None
    gender: Optional[int] = None
    email: Optional[str] = None

    _external_url = validator("external_url", allow_reuse=True)(validate_external_url)


class UserShort(BaseModel):
    pk: str
    username: Optional[str] = None
    full_name: Optional[str] = ""
    profile_pic_url: Optional[str] = None
    profile_pic_url_hd: Optional[str] = None
    is_private: Optional[bool] = None
    is_verified: Optional[bool] = None


class Usertag(BaseModel):
    user: UserShort
    x: float
    y: float


class Location(BaseModel):
    pk: Optional[int] = None
    name: str
    phone: Optional[str] = ""
    website: Optional[str] = ""
    category: Optional[str] = ""
    hours: Optional[dict] = {}  # opening hours
    address: Optional[str] = ""
    city: Optional[str] = ""
    zip: Optional[str] = ""
    lng: Optional[float] = None
    lat: Optional[float] = None
    external_id: Optional[str] = None
    external_id_source: Optional[str] = None
    # address_json: Optional[dict] = {}
    # profile_pic_url: Optional[str] = None
    # directory: Optional[dict] = {}


class Media(BaseModel):
    pk: str
    id: str
    code: str
    taken_at: datetime
    taken_at_ts: int
    media_type: int
    product_type: Optional[str] = ""  # igtv or feed
    thumbnail_url: Optional[str] = None
    location: Optional[Location] = None
    user: UserShort
    comment_count: Optional[int] = 0
    comments_disabled: Optional[bool] = False
    like_count: int
    play_count: Optional[int] = None
    has_liked: Optional[bool] = None
    caption_text: str
    accessibility_caption: Optional[str] = None
    usertags: List[Usertag]
    sponsor_tags: Optional[List[UserShort]] = []
    video_url: Optional[str] = None  # for Video and IGTV
    view_count: Optional[int] = 0  # for Video and IGTV
    video_duration: Optional[float] = 0.0  # for Video and IGTV
    title: Optional[str] = ""
    resources: List[Resource] = []
    image_versions: List[dict] = []
    video_versions: List[dict] = []
    clips_metadata: dict = {}
    video_dash_manifest: Optional[str] = ""
    like_and_view_counts_disabled: Optional[bool] = None
    coauthor_producers: Optional[list] = []
    is_paid_partnership: Optional[bool] = None


class MediaOembed(BaseModel):
    title: str
    author_name: str
    author_url: str
    author_id: str
    media_id: str
    provider_name: str
    provider_url: str
    type: str
    width: Optional[int] = None
    height: Optional[int] = None
    html: str
    thumbnail_url: str
    thumbnail_width: int
    thumbnail_height: int
    can_view: Optional[bool] = None


class Collection(BaseModel):
    id: str
    name: str
    type: str
    media_count: int


class Comment(BaseModel):
    pk: str
    text: str
    user: UserShort
    created_at_utc: datetime
    content_type: str
    status: str
    has_liked: Optional[bool] = None
    like_count: Optional[int] = None


class Hashtag(BaseModel):
    id: Optional[str] = None
    name: str
    media_count: Optional[int] = None
    allow_following: Optional[bool] = None
    profile_pic_url: Optional[str] = None


class StoryMention(BaseModel):
    user: UserShort
    x: Optional[float] = None
    y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None


class StoryMedia(BaseModel):
    # Instagram does not return the feed_media object when requesting story,
    # so you will have to make an additional request to get media and this is overhead:
    # media: Media
    x: float = 0.5
    y: float = 0.4997396
    z: float = 0
    width: float = 0.8
    height: float = 0.60572916
    rotation: float = 0.0
    is_pinned: Optional[bool] = None
    is_hidden: Optional[bool] = None
    is_sticker: Optional[bool] = None
    is_fb_sticker: Optional[bool] = None
    media_pk: str
    user_id: Optional[str] = None
    product_type: Optional[str] = None
    media_code: Optional[str] = None


class StoryHashtag(BaseModel):
    hashtag: Hashtag
    x: Optional[float] = None
    y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None


class StoryLocation(BaseModel):
    location: Location
    x: Optional[float] = None
    y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None


class StoryStickerLink(BaseModel):
    url: Optional[str] = None
    link_title: Optional[str] = None
    link_type: Optional[str] = None
    display_url: Optional[str] = None


class StorySticker(BaseModel):
    id: Optional[str] = None
    type: Optional[str] = "gif"
    x: float
    y: float
    z: Optional[int] = 1000005
    width: float
    height: float
    rotation: Optional[float] = 0.0
    story_link: Optional[StoryStickerLink] = None
    extra: Optional[dict] = {}


class StoryBuild(BaseModel):
    mentions: List[StoryMention]
    path: FilePath
    paths: List[FilePath] = []
    stickers: List[StorySticker] = []


class StoryLink(BaseModel):
    webUri: str
    x: float = 0.5126011
    y: float = 0.5168225
    z: float = 0.0
    width: float = 0.50998676
    height: float = 0.25875
    rotation: float = 0.0


class Story(BaseModel):
    pk: str
    id: str
    code: str
    taken_at: datetime
    media_type: Optional[int] = None
    product_type: Optional[str] = ""
    thumbnail_url: Optional[str] = None
    user: UserShort
    video_url: Optional[str] = None  # for Video and IGTV
    video_duration: Optional[float] = 0.0  # for Video and IGTV
    sponsor_tags: Optional[List[UserShort]] = []
    mentions: List[StoryMention]
    links: List[StoryLink]
    hashtags: List[StoryHashtag]
    locations: List[StoryLocation]
    stickers: List[StorySticker]
    medias: List[StoryMedia] = []


class Guide(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    description: str
    cover_media: Media
    feedback_item: Optional[dict] = None


class DirectMedia(BaseModel):
    id: str
    media_type: int
    user: Optional[UserShort]
    thumbnail_url: Optional[str] = None
    video_url: Optional[str] = None


class DirectMessage(BaseModel):
    id: str  # e.g. 28597946203914980615241927545176064
    user_id: Optional[str] = None
    thread_id: Optional[str]  # e.g. 340282366841710300949128531777654287254
    timestamp: datetime
    item_type: Optional[str] = None
    is_shh_mode: Optional[bool] = None
    reactions: Optional[dict] = None
    text: Optional[str] = None
    link: Optional[dict] = None
    media: Optional[DirectMedia] = None
    media_share: Optional[Media] = None
    reel_share: Optional[dict] = None
    story_share: Optional[dict] = None
    felix_share: Optional[dict] = None
    clip: Optional[Media]
    placeholder: Optional[dict] = None


class DirectResponse(BaseModel):
    unseen_count: Optional[int] = None
    unseen_count_ts: Optional[int] = None
    status: Optional[str] = None


class DirectShortThread(BaseModel):
    id: str
    users: List[UserShort]
    named: bool
    thread_title: str
    pending: bool
    thread_type: str
    viewer_id: str
    is_group: bool


class DirectThread(BaseModel):
    pk: str  # thread_v2_id, e.g. 17898572618026348
    id: str  # thread_id, e.g. 340282366841510300949128268610842297468
    messages: List[DirectMessage]
    users: List[UserShort]
    inviter: Optional[UserShort]
    left_users: List[UserShort] = []
    admin_user_ids: list
    last_activity_at: datetime
    muted: bool
    is_pin: Optional[bool] = None
    named: bool
    canonical: bool
    pending: bool
    archived: bool
    thread_type: str
    thread_title: str
    folder: int
    vc_muted: bool
    is_group: bool
    mentions_muted: bool
    approval_required_for_new_members: bool
    input_mode: int
    business_thread_folder: int
    read_state: int
    is_close_friend_thread: bool
    assigned_admin_id: str
    shh_mode_enabled: bool
    last_seen_at: dict

    def is_seen(self, user_id: str):
        """Have I seen this thread?
        :param user_id: You account user_id
        """
        user_id = str(user_id)
        own_timestamp = int(self.last_seen_at[user_id]["timestamp"])
        timestamps = [
            (int(v["timestamp"]) - own_timestamp) > 0
            for k, v in self.last_seen_at.items()
            if k != user_id
        ]
        return not any(timestamps)


class Relationship(BaseModel):
    blocking: bool
    followed_by: bool
    following: bool
    incoming_request: bool
    is_bestie: bool
    is_blocking_reel: bool
    is_muting_reel: bool
    is_private: bool
    is_restricted: bool
    muting: bool
    outgoing_request: bool
    status: str


class Highlight(BaseModel):
    pk: str  # 17895485401104052
    id: str  # highlight:17895485401104052
    latest_reel_media: int
    cover_media: dict
    user: UserShort
    title: str
    created_at: datetime
    is_pinned_highlight: bool
    media_count: int
    media_ids: List[int] = []
    items: List[Story] = []


class Share(BaseModel):
    pk: str
    type: str


class Track(BaseModel):
    id: str
    title: str
    subtitle: str
    display_artist: str
    audio_cluster_id: str
    artist_id: Optional[str] = None
    cover_artwork_uri: str
    cover_artwork_thumbnail_uri: str
    progressive_download_url: Optional[str] = None
    fast_start_progressive_download_url: Optional[str] = None
    reactive_audio_download_url: Optional[str] = None
    highlight_start_times_in_ms: List[int]
    is_explicit: bool
    dash_manifest: str
    has_lyrics: bool
    audio_asset_id: str
    duration_in_ms: int
    dark_message: Optional[str] = None
    allows_saving: bool
    territory_validity_periods: Optional[dict] = None

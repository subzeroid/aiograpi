import datetime
import logging

import orjson

from .types import (
    About,
    Account,
    Collection,
    Comment,
    DirectMedia,
    DirectMessage,
    DirectResponse,
    DirectShortThread,
    DirectThread,
    Guide,
    Hashtag,
    Highlight,
    Location,
    Media,
    MediaOembed,
    MediaXma,
    ReplyMessage,
    Resource,
    Story,
    StoryLink,
    StoryMedia,
    StoryMention,
    Track,
    User,
    UserShort,
    Usertag,
)
from .utils import InstagramIdCodec, json_value

# from copy import deepcopy


MEDIA_TYPES_GQL = {"GraphImage": 1, "GraphVideo": 2, "GraphSidecar": 8, "StoryVideo": 2}

logger = logging.getLogger(__name__)


def extract_media_v1(media):
    """Extract media from Private API"""
    # media = deepcopy(data)
    if versions := media.get("video_versions", []):
        # Select Best Quality by Resolutiuon
        media["video_url"] = sorted(versions, key=lambda o: o["height"] * o["width"])[
            -1
        ]["url"]
    # if media.get("is_reel_media"):
    #    media["media_type"] = 2
    #    media["product_type"] = "clips"
    if media.get("media_type") == 2 and not media.get("product_type"):
        media["product_type"] = "feed"
    if "image_versions2" in media:
        media["image_versions"] = media["image_versions2"]["candidates"]
        media["thumbnail_url"] = sorted(
            media["image_versions"],
            key=lambda o: o["height"] * o["width"],
        )[-1]["url"]
    if media.get("media_type") == 8:
        # remove thumbnail_url and video_url for albums
        # see resources
        media.pop("thumbnail_url", "")
        media.pop("video_url", "")
    location = media.get("location")
    media["location"] = location and extract_location(location)
    media["user"] = extract_user_short(media.get("user"))
    media["usertags"] = sorted(
        [
            extract_usertag(usertag)
            for usertag in media.get("usertags", {}).get("in", [])
        ],
        key=lambda tag: tag.user.pk,
    )
    media["like_count"] = media.get("like_count", 0)
    media["has_liked"] = media.get("has_liked", False)
    media["taken_at_ts"] = media.get("taken_at")
    media["sponsor_tags"] = [tag["sponsor"] for tag in media.get("sponsor_tags", [])]
    media["play_count"] = media.get("play_count", 0)
    media["pk"] = str(media["pk"])
    for tag in media["sponsor_tags"]:
        tag["pk"] = str(tag["pk"])
    return Media(
        caption_text=(media.get("caption") or {}).get("text", ""),
        resources=[
            extract_resource_v1(edge) for edge in media.get("carousel_media", [])
        ],
        **media,
    )


def extract_media_v1_xma(media):
    """Extract media from Private API"""
    # media = deepcopy(data)
    # media["media_type"] = 10
    media["video_url"] = media.get("target_url", "")
    media["title"] = media.get("title_text", "")
    media["preview_url"] = media.get("preview_url", "")
    media["preview_url_mime_type"] = media.get("preview_url_mime_type", "")
    media["header_icon_url"] = media.get("header_icon_url", "")
    media["header_icon_width"] = media.get("header_icon_width", 0)
    media["header_icon_height"] = media.get("header_icon_height", 0)
    media["header_title_text"] = media.get("header_title_text", "")
    media["preview_media_fbid"] = media.get("preview_media_fbid", "")

    return MediaXma(
        **media,
    )


def extract_media_gql(media):
    """Extract media from GraphQL"""
    # media = deepcopy(data)
    user = extract_user_short(media["owner"])
    # if "full_name" in user:
    #     user = extract_user_short(user)
    # else:
    #     user["pk"] = user.pop("id")
    try:
        media["media_type"] = MEDIA_TYPES_GQL[media["__typename"]]
    except KeyError:
        media["media_type"] = 0
    if media.get("media_type") == 2 and not media.get("product_type"):
        media["product_type"] = "feed"
    if "thumbnail_src" in media:
        media["thumbnail_url"] = media["thumbnail_src"]
    else:
        media["thumbnail_url"] = sorted(
            # display_resources - user feed, thumbnail_resources - hashtag feed
            media.get("display_resources", media.get("thumbnail_resources")),
            key=lambda o: o["config_width"] * o["config_height"],
        )[-1]["src"]
    if media.get("media_type") == 8:
        # remove thumbnail_url and video_url for albums
        # see resources
        media.pop("thumbnail_url", "")
        media.pop("video_url", "")
    location = media.pop("location", None)
    media_id = media.get("id")
    media["pk"] = media_id
    media["id"] = f"{media_id}_{user.pk}"
    media["image_versions"] = media["display_resources"]
    taken_at = media.get("taken_at_timestamp")
    return Media(
        code=media.get("shortcode"),
        taken_at=taken_at,
        taken_at_ts=taken_at,
        location=extract_location(location) if location else None,
        user=user,
        view_count=media.get("video_view_count", 0),
        comment_count=json_value(media, "edge_media_to_comment", "count"),
        like_count=json_value(media, "edge_media_preview_like", "count"),
        caption_text=json_value(
            media, "edge_media_to_caption", "edges", 0, "node", "text", default=""
        ),
        usertags=sorted(
            [
                extract_usertag(usertag["node"])
                for usertag in media.get("edge_media_to_tagged_user", {}).get(
                    "edges", []
                )
            ],
            key=lambda tag: tag.user.pk,
        ),
        resources=[
            extract_resource_gql(edge["node"])
            for edge in media.get("edge_sidecar_to_children", {}).get("edges", [])
        ],
        sponsor_tags=[
            extract_user_short(edge["node"]["sponsor"])
            for edge in media.get("edge_media_to_sponsor_user", {}).get("edges", [])
        ],
        **media,
    )


def extract_resource_v1(data):
    if versions := data.get("video_versions", []):
        data["video_url"] = sorted(versions, key=lambda o: o["height"] * o["width"])[
            -1
        ]["url"]
    data["pk"] = str(data["pk"])
    data["image_versions"] = data["image_versions2"]["candidates"]
    data["thumbnail_url"] = sorted(
        data["image_versions"],
        key=lambda o: o["height"] * o["width"],
    )[-1]["url"]
    return Resource(**data)


def extract_resource_gql(data):
    data["media_type"] = MEDIA_TYPES_GQL[data["__typename"]]
    data["image_versions"] = data["display_resources"]
    return Resource(pk=data["id"], thumbnail_url=data["display_url"], **data)


def extract_usertag(data):
    """Extract user tag"""
    x, y = data.get("position", [data.get("x"), data.get("y")])
    return Usertag(user=extract_user_short(data["user"]), x=x, y=y)


def extract_user_short(data):
    """Extract User Short info"""
    data["pk"] = str(data.get("id", data.get("pk", None)))
    assert data["pk"], f'User without pk "{data}"'
    return UserShort(**data)


def extract_user_gql(data):
    """For Public GraphQL API"""
    return User(
        pk=data["id"],
        media_count=data["edge_owner_to_timeline_media"]["count"],
        follower_count=data["edge_followed_by"]["count"],
        following_count=data["edge_follow"]["count"],
        is_business=data["is_business_account"],
        public_email=data["business_email"],
        contact_phone_number=data["business_phone_number"],
        **data,
    )


def extract_user_v1(data):
    """For Private API"""
    data["external_url"] = data.get("external_url") or None
    versions = data.get("hd_profile_pic_versions")
    pic_hd = versions[-1] if versions else data.get("hd_profile_pic_url_info", {})
    data["profile_pic_url_hd"] = pic_hd.get("url")
    data["pk"] = str(data["pk"])
    data["city_id"] = None
    if cid := data.get("city_id"):
        data["city_id"] = str(cid)
    if "interop_messaging_user_fbid" in data:
        data["interop_messaging_user_fbid"] = str(data["interop_messaging_user_fbid"])
    return User(**data)


def _extract_about_lispy(c, data):
    params = {}
    try:
        params["country"] = c.split('"')[1]
    except IndexError:
        logger.warn("Problem with about. data - %r", data)
    try:
        s = str(data).split("space_evenly")[1].split("stretch")
        try:
            params["username"] = s[1].split("center")[1].split(": '")[1].split("',")[0]
        except IndexError:
            pass
        try:
            params["date"] = s[4].split("&")[1].split("'")[2]
        except IndexError:
            pass
    except IndexError:
        pass
    return About(**params)


def extract_about_v1(data):
    c = json_value(data, "layout", "bloks_payload", "data", 0, "data")
    params = {}
    if c:
        if "initial_lispy" in c:
            # old version
            return _extract_about_lispy(c["initial_lispy"], data)
        params["country"] = c["initial"]
    date_finded = False
    dumps = orjson.dumps(data).decode()
    params["is_verified"] = '"Verified"' in dumps
    ddata = orjson.dumps(data).decode().split('")":')
    for i, v in enumerate(ddata):
        if '"bold"}' in v:
            params["username"] = v.strip().split(",")[0][1:-1]
        if date_finded:
            params["date"] = v.strip().split(",")[0][1:-1]
        if "Former usernames" in v:
            params["former_usernames"] = ddata[i + 2].strip().split(",")[0][1:-1]
        date_finded = '"Date joined"' in v
    return About(**params)


def extract_location(data):
    """Extract location info"""
    if not data:
        return None
    data["pk"] = data.get("id", data.get("pk", data.get("location_id", None)))
    data["external_id"] = str(data.get("external_id", data.get("facebook_places_id")))
    data["external_id_source"] = data.get(
        "external_id_source", data.get("external_source")
    )
    data["address"] = data.get("address", data.get("location_address"))
    data["city"] = data.get("city", data.get("location_city"))
    data["zip"] = data.get("zip", data.get("location_zip"))
    address_json = data.get("address_json", "{}")
    if isinstance(address_json, str):
        address = orjson.loads(address_json)
        if isinstance(address, dict) and address:
            data["address"] = address.get("street_address")
            data["city"] = address.get("city_name")
            data["zip"] = address.get("zip_code")
    return Location(**data)


def extract_comment(data):
    """Extract comment"""
    data["has_liked"] = data.get("has_liked_comment")
    data["like_count"] = data.get("comment_like_count")
    data["user"]["pk"] = str(data["user"]["pk"])
    return Comment(**data)


def extract_collection(data):
    """Extract collection for authorized account
    Example:
    {'collection_id': '17851406186124602',
    'collection_name': 'Repost',
    'collection_type': 'MEDIA',
    'collection_media_count': 1,
    'cover_media': {...}
    """
    data = {key.replace("collection_", ""): val for key, val in data.items()}
    # data['pk'] = data.get('id')
    return Collection(**data)


def extract_media_oembed(data):
    """Return short version of Media"""
    data["author_id"] = str(data["author_id"])
    return MediaOembed(**data)


def extract_direct_thread(data):
    data["pk"] = data.get("thread_v2_id")
    data["id"] = data.get("thread_id")
    data["messages"] = []
    for item in data["items"]:
        item["thread_id"] = data["id"]
        data["messages"].append(extract_direct_message(item))
    data["users"] = [extract_user_short(u) for u in data["users"]]
    if "inviter" in data:
        data["inviter"] = extract_user_short(data["inviter"])
    data["left_users"] = data.get("left_users", [])

    data["last_activity_at"] = datetime.datetime.fromtimestamp(data["last_activity_at"] / 1_000_000)

    return DirectThread(**data)


def extract_direct_short_thread(data):
    data["users"] = [extract_user_short(u) for u in data["users"]]
    data["id"] = data.get("thread_id")
    return DirectShortThread(**data)


def extract_direct_response(data):
    return DirectResponse(**data)


def extract_reply_message(data):
    data["id"] = data.get("item_id")
    if "media_share" in data:
        ms = data["media_share"]
        if not ms.get("code"):
            ms["code"] = InstagramIdCodec.encode(ms["id"])
        data["media_share"] = extract_media_v1(ms)
    if "media" in data:
        data["media"] = extract_direct_media(data["media"])
    clip = data.get("clip", {})
    if clip:
        if "clip" in clip:
            # Instagram ¯\_(ツ)_/¯
            clip = clip.get("clip")
        data["clip"] = extract_media_v1(clip)

    data["timestamp"] = datetime.datetime.fromtimestamp(data["timestamp"] / 1_000_000)
    data["user_id"] = str(data["user_id"])

    return ReplyMessage(**data)


def extract_direct_message(data):
    data["id"] = data.get("item_id")
    if "replied_to_message" in data:
        data["reply"] = extract_reply_message(data["replied_to_message"])
    if "media_share" in data:
        ms = data["media_share"]
        if not ms.get("code"):
            ms["code"] = InstagramIdCodec.encode(ms["id"])
        data["media_share"] = extract_media_v1(ms)
    if "media" in data:
        data["media"] = extract_direct_media(data["media"])
    if "voice_media" in data:
        if "media" in data["voice_media"]:
            data["media"] = extract_direct_media(data["voice_media"]["media"])
    clip = data.get("clip", {})
    if clip:
        if "clip" in clip:
            # Instagram ¯\_(ツ)_/¯
            clip = clip.get("clip")
        data["clip"] = extract_media_v1(clip)
    xma_media_share = data.get("xma_media_share", {})
    if xma_media_share:
        data["xma_share"] = extract_media_v1_xma(xma_media_share[0])

    data["timestamp"] = datetime.datetime.fromtimestamp(data["timestamp"] / 1_000_000)
    data["user_id"] = str(data.get("user_id", ""))

    return DirectMessage(**data)


def extract_direct_media(media):
    # media = deepcopy(data)
    if versions := media.get("video_versions", []):
        # Select Best Quality by Resolutiuon
        media["video_url"] = sorted(versions, key=lambda o: o["height"] * o["width"])[
            -1
        ]["url"]
    if "image_versions2" in media:
        media["thumbnail_url"] = sorted(
            media["image_versions2"]["candidates"],
            key=lambda o: o["height"] * o["width"],
        )[-1]["url"]
    if "user" in media:
        media["user"] = extract_user_short(media.get("user"))
    return DirectMedia(**media)


def extract_account(data):
    data["pk"] = str(data["pk"])
    data["external_url"] = data.get("external_url") or None
    return Account(**data)


def extract_hashtag_gql(data):
    data["media_count"] = data.get("edge_hashtag_to_media", {}).get("count")
    data["profile_pic_url"] = data.get("profile_pic_url") or None
    return Hashtag(**data)


def extract_hashtag_v1(data):
    if hashtag_id := data.get("id"):
        data["id"] = str(hashtag_id)
    data["allow_following"] = data.get("allow_following") == 1
    data["profile_pic_url"] = data.get("profile_pic_url") or None
    return Hashtag(**data)


def extract_story_v1(story):
    """Extract story from Private API"""
    # story = deepcopy(data)
    if versions := story.get("video_versions", []):
        # Select Best Quality by Resolutiuon
        story["video_url"] = sorted(versions, key=lambda o: o["height"] * o["width"])[
            -1
        ]["url"]
    # if story.get("is_reel_media"):
    #    story["media_type"] = 2
    #    story["product_type"] = "clips"
    if story.get("media_type") == 2 and not story.get("product_type"):
        story["product_type"] = "story"
    if "image_versions2" in story:
        story["thumbnail_url"] = sorted(
            story["image_versions2"]["candidates"],
            key=lambda o: o["height"] * o["width"],
        )[-1]["url"]
    story["user"]["pk"] = str(story["user"]["pk"])
    mentions = []
    for mention in story.get("reel_mentions", []):
        mention["user"]["pk"] = str(mention["user"]["pk"])
        mentions.append(StoryMention(**mention))
    story["mentions"] = mentions
    story["pk"] = str(story["pk"])
    story["locations"] = story.pop("story_locations", [])
    story["hashtags"] = story.pop("story_hashtags", [])
    for sht in story["hashtags"]:
        sht["hashtag"] = extract_hashtag_v1(sht["hashtag"])
    story["stickers"] = story.pop("story_link_stickers", [])
    feed_medias = []
    story_feed_medias = story.pop("story_feed_media", [])
    for feed_media in story_feed_medias:
        feed_media["media_pk"] = str(feed_media["media_id"])
        feed_medias.append(StoryMedia(**feed_media))
    story["medias"] = feed_medias
    story["links"] = []
    for cta in story.get("story_cta", []):
        for link in cta.get("links", []):
            story["links"].append(StoryLink(**link))
    story["user"] = extract_user_short(story.get("user"))
    tags = []
    for tag in story.get("sponsor_tags", []):
        sponsor = tag["sponsor"]
        sponsor["pk"] = str(sponsor["pk"])
        tags.append(sponsor)
    story["sponsor_tags"] = tags
    return Story(**story)


def extract_story_gql(story):
    """Extract story from Public API"""
    # story = deepcopy(data)
    if "video_resources" in story:
        # Select Best Quality by Resolutiuon
        story["video_url"] = sorted(
            story["video_resources"],
            key=lambda o: o["config_height"] * o["config_width"],
        )[-1]["src"]
    story["product_type"] = "story"
    story["thumbnail_url"] = story.get("display_url")
    story["mentions"] = []
    story["medias"] = []
    for item in story.get("tappable_objects", []):
        if item["__typename"] == "GraphTappableMention":
            item["id"] = 1
            item["user"] = extract_user_short(item)
            story["mentions"].append(StoryMention(**item))
        if item["__typename"] == "GraphTappableFeedMedia":
            media = item.get("media")
            if media:
                item["media_pk"] = int(media["id"])
                item["media_code"] = media["shortcode"]
            story["medias"].append(StoryMedia(**item))
    story["locations"] = []
    story["hashtags"] = []
    story["stickers"] = []
    story["links"] = []
    story_cta_url = story.get("story_cta_url", [])
    if story_cta_url:
        story["links"] = [StoryLink(**{"webUri": story_cta_url})]
    story["user"] = extract_user_short(story.get("owner"))
    story["pk"] = int(story["id"])
    story["id"] = f"{story['id']}_{story['owner']['id']}"
    story["code"] = InstagramIdCodec.encode(story["pk"])
    story["taken_at"] = story["taken_at_ts"] = story["taken_at_timestamp"]
    story["media_type"] = 2 if story["is_video"] else 1
    return Story(**story)


def extract_highlight_v1(highlight):
    # highlight = deepcopy(data)
    highlight["pk"] = highlight["id"].split(":")[1]
    highlight["items"] = [extract_story_v1(item) for item in highlight.get("items", [])]
    highlight["user"]["pk"] = str(highlight["user"]["pk"])
    return Highlight(**highlight)


def extract_guide_v1(data):
    item = data.get("summary") or {}
    if media := item.get("cover_media"):
        item["cover_media"] = extract_media_v1(media)
    return Guide(**item)


def extract_track(data):
    return Track(**data)

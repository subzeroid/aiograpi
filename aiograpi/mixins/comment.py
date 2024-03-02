import random
from typing import List, Optional, Tuple

from aiograpi.exceptions import (  # CommentsDisabled,
    ClientError,
    ClientLoginRequired,
    ClientNotFoundError,
    CommentNotFound,
    MediaNotFound,
    PreLoginRequired,
    PrivateError,
)
from aiograpi.extractors import extract_comment
from aiograpi.mixins.graphql import GQL_STUFF
from aiograpi.types import Comment
from aiograpi.utils import dumps, generate_jazoest


class CommentMixin:
    """
    Helpers for managing comments on a Media
    """

    async def media_comments_threaded_gql_chunk(
        self, media_pk: str, comment_pk: str, end_cursor: str = ""
    ) -> Tuple[List[dict], str]:
        """
        Get threaded comments on a media

        Parameters
        ----------
        comment_pk: str
            Unique identifier of a Comment
        end_cursor: str
            Cursor

        Returns
        -------
        Tuple[List[dict], str]
            A list of objects of Comment
        """
        doc_id = "7171917939589632"
        comments = []

        # variables = {"comment_id": comment_pk, "first": 50}
        # if end_cursor:
        #     variables["after"] = end_cursor
        # data = await self.public_graphql_request(
        #     variables, query_hash="1ee91c32fc020d44158a3192eda98247"
        # )
        # comment = data.get("comment")
        # if not comment:
        #     raise CommentNotFound(**data)
        # edge_threaded_comments = comment.get("edge_threaded_comments", {})
        # for edge in edge_threaded_comments.get("edges", []):
        #     comments.append(edge["node"])
        # page_info = edge_threaded_comments["page_info"]
        # end_cursor = page_info["end_cursor"] if page_info["has_next_page"] else None

        media_pk = str(await self.media_pk(media_pk))
        variables = {
            "after": end_cursor or None,
            "before": None,
            "first": 50,
            "last": None,
            "media_id": media_pk,
            "parent_comment_id": str(comment_pk),
            "is_chronological": None,
        }
        data = {
            "variables": dumps(variables),
            "doc_id": doc_id,
            "fb_dtsg": await self.fb_dtsg,
            # OPTIONAL (may have random values):
            "jazoest": generate_jazoest(self.phone_id),
            **GQL_STUFF,
        }
        resp = await self.graphql_request(data=data)
        if data := resp["data"]:
            key = None
            for key in data.keys():
                if "comments" in key:
                    break
            item = data[key]
            edges = item.get("edges", [])
            if not edges:
                raise CommentNotFound(**data)
            for edge in edges:
                comments.append(edge["node"])
            page_info = item.get("page_info", {})
            end_cursor = (
                page_info.get("end_cursor") if page_info.get("has_next_page") else None
            )
            return comments, end_cursor
        return [], ""

    async def media_comments_threaded_gql(
        self, media_pk: str, comment_pk: str, amount: int = 0
    ) -> List[dict]:
        """
        Get threaded comments on a media

        Parameters
        ----------
        comment_pk: str
            Unique identifier of a Comment
        amount: int, optional
            Maximum number of media to return, default is 0 - Inf

        Returns
        -------
        List[dict]
            A list of objects of Comment
        """
        end_cursor = ""
        comments = []
        while True:
            items, end_cursor = await self.media_comments_threaded_gql_chunk(
                media_pk, comment_pk, end_cursor=end_cursor
            )
            comments.extend(items)
            if not end_cursor or len(items) == 0:
                break
            if amount and len(comments) >= amount:
                break
        if amount:
            comments = comments[:amount]
        return comments

    async def media_comments_gql_chunk(
        self, media_pk: str, end_cursor: str = ""
    ) -> Tuple[List[dict], str]:
        """
        Get comments on a media

        Parameters
        ----------
        media_pk: str
            Unique identifier of a Media
        end_cursor: str
            Cursor

        Returns
        -------
        Tuple[List[dict], str]
            A list of objects of Comment
        """
        media_pk = str(await self.media_pk(media_pk))
        comments = []

        # shortcode = await self.media_code_from_pk(media_pk)
        # variables = {
        #     "shortcode": shortcode,
        #     "child_comment_count": 50,
        #     "fetch_comment_count": 50,
        #     "parent_comment_count": 50,
        #     "has_threaded_comments": True,
        # }
        # query_hash = "477b65a610463740ccdb83135b2014db"
        # if end_cursor:
        #     variables = {"shortcode": shortcode, "first": 50, "after": end_cursor}
        #     query_hash = "bc3296d1ce80a24b1b6e40b1e72903f5"
        # data = await self.public_graphql_request(variables, query_hash=query_hash)
        # shortcode_media = data.get("shortcode_media")
        # if not shortcode_media:
        #     raise MediaNotFound(media_pk=media_pk, **data)
        # if shortcode_media.get("comments_disabled"):
        #     raise CommentsDisabled(media_pk=media_pk, **data)
        # edge_media_to_parent_comment = shortcode_media.get(
        #     "edge_media_to_parent_comment", {}
        # )
        # for edge in edge_media_to_parent_comment.get("edges", []):
        #     comments.append(edge["node"])
        # page_info = edge_media_to_parent_comment.get("page_info", {})
        # end_cursor = (
        #     page_info.get("end_cursor") if page_info.get("has_next_page") else None
        # )

        doc_id = "6974885689225067"
        variables = {
            "after": end_cursor or None,
            "before": None,
            "first": 50,
            "last": None,
            "media_id": media_pk,
            "sort_order": "popular",
        }
        data = {
            "variables": dumps(variables),
            "doc_id": doc_id,
            "fb_dtsg": await self.fb_dtsg,
            # OPTIONAL (may have random values):
            "jazoest": generate_jazoest(self.phone_id),
            **GQL_STUFF,
        }
        resp = await self.graphql_request(data=data)
        if data := resp["data"]:
            key = None
            for key in data.keys():
                if "comments" in key:
                    break
            item = data[key]
            for edge in item.get("edges", []):
                comments.append(edge["node"])
            page_info = item.get("page_info", {})
            end_cursor = (
                page_info.get("end_cursor") if page_info.get("has_next_page") else None
            )
            return comments, end_cursor
        return [], ""

    async def media_comments_gql(
        self, media_pk: str, amount: int = 50, max_requests: int = 0
    ) -> List[dict]:
        """
        Get comments on a media

        Parameters
        ----------
        media_id: str
            Unique identifier of a Media
        amount: int, optional
            Maximum number of media to return, default is 0 - Inf

        Returns
        -------
        List[dict]
            A list of objects of Comment
        """
        media_pk = await self.media_pk(media_pk)
        end_cursor = ""
        comments = []
        i = 0
        while True:
            i += 1
            if max_requests and i > max_requests:
                break
            items, end_cursor = await self.media_comments_gql_chunk(
                media_pk, end_cursor=end_cursor
            )
            comments.extend(items)
            if not end_cursor or len(items) == 0:
                break
            if amount and len(comments) >= amount:
                break
        if amount:
            comments = comments[:amount]
        return comments

    async def media_stream_comments_v1_chunk(
        self, media_id: str, min_id: str = "", max_id: str = ""
    ) -> Tuple[List[Comment], str, str]:
        """
        Get comments on a media

        Parameters
        ----------
        media_id: str
            Unique identifier of a Media

        Returns
        -------
        List[Comment]
            A list of objects of Comment
        """
        params = {
            "can_support_threading": "true",
            "inventory_source": "explore_story",
            "analytics_module": "comments_v2_feed_timeline",
            "is_carousel_bumped_post": "false",
            "feed_position": "1",
        }
        if min_id:
            params["min_id"] = min_id
        if max_id:
            params["max_id"] = max_id
        result = await self.private_request(
            f"media/{media_id}/stream_comments/",
            params=params,
        )
        # if result.get("has_more_comments"):
        #     params = {"max_id": max_id}
        # else:  # has_more_headload_comments
        #     params = {"min_id": min_id}
        comments = []
        rows = result.get("stream_rows") or [result]
        for row in rows:
            for comment in row["comments"]:
                comments.append(extract_comment(comment))
        min_id = result.get("next_min_id") or result.get("min_id", "")
        max_id = result.get("next_max_id") or result.get("max_id", "")
        return comments, min_id, max_id

    async def media_comments_v1_chunk(
        self, media_id: str, min_id: str = "", max_id: str = ""
    ) -> Tuple[List[Comment], str, str]:
        """
        Get comments on a media

        Parameters
        ----------
        media_id: str
            Unique identifier of a Media

        Returns
        -------
        List[Comment]
            A list of objects of Comment
        """
        params = {"can_support_threading": "true", "permalink_enabled": "false"}
        if min_id:
            params["min_id"] = min_id
        if max_id:
            params["max_id"] = max_id
        result = await self.private_request(
            f"media/{media_id}/comments/", params=params
        )
        # if result.get("has_more_comments"):
        #     params = {"max_id": max_id}
        # else:  # has_more_headload_comments
        #     params = {"min_id": min_id}
        comments = []
        for comment in result.get("comments", []):
            comments.append(extract_comment(comment))
        min_id = result.get("next_min_id") or result.get("min_id", "")
        max_id = result.get("next_max_id") or result.get("max_id", "")
        return comments, min_id, max_id

    async def media_comments_v1(self, media_id: str, amount: int = 20) -> List[Comment]:
        """
        Get comments on a media

        Parameters
        ----------
        media_id: str
            Unique identifier of a Media
        amount: int, optional
            Maximum number of media to return, default is 0 - Inf

        Returns
        -------
        List[Comment]
            A list of objects of Comment
        """
        comments = []
        min_id, max_id = None, None
        try:
            while True:
                items, min_id, max_id = await self.media_comments_v1_chunk(
                    media_id, min_id, max_id
                )
                comments.extend(items)
                if len(items) == 0:
                    break
                if amount and len(comments) > amount:
                    break
        except ClientNotFoundError as e:
            raise MediaNotFound(e, media_id=media_id, **self.last_json)
        except ClientError as e:
            if "Media not found" in str(e):
                raise MediaNotFound(e, media_id=media_id, **self.last_json)
            raise e
        if amount:
            comments = comments[:amount]
        return comments

    async def media_comments(self, media_id: str, amount: int = 20) -> List[Comment]:
        try:
            try:
                comments = await self.media_comments_gql(media_id, amount)
            except ClientLoginRequired as e:
                if not self.inject_sessionid_to_public():
                    raise e
                comments = await self.media_comments_gql(media_id, amount)  # retry
        except PrivateError as e:
            raise e
        except Exception as e:
            if not isinstance(e, ClientError):
                self.logger.exception(e)  # Register unknown error
            # Restricted Video: This video is not available in your country.
            # Or private account
            comments = await self.media_comments_v1(media_id, amount)
        return comments

    async def media_comment(
        self, media_id: str, text: str, replied_to_comment_id: Optional[int] = None
    ) -> Comment:
        """
        Post a comment on a media

        Parameters
        ----------
        media_id: str
            Unique identifier of a Media
        text: str
            String to be posted on the media

        Returns
        -------
        Comment
            An object of Comment type
        """
        if not self.user_id:
            raise PreLoginRequired
        data = {
            "delivery_class": "organic",
            "feed_position": "0",
            "container_module": "self_comments_v2_feed_contextual_self_profile",
            "user_breadcrumb": self.gen_user_breadcrumb(len(text)),
            "idempotence_token": self.generate_uuid(),
            "comment_text": text,
        }
        if replied_to_comment_id:
            data["replied_to_comment_id"] = int(replied_to_comment_id)
        result = await self.private_request(
            f"media/{media_id}/comment/",
            self.with_action_data(data),
        )
        return extract_comment(result["comment"])

    async def comment_like(self, comment_pk: int, revert: bool = False) -> bool:
        """
        Like a comment on a media

        Parameters
        ----------
        comment_pk: int
            Unique identifier of a Comment
        revert: bool, optional
            If liked, whether or not to unlike. Default is False

        Returns
        -------
        bool
            A boolean value
        """
        if not self.user_id:
            raise PreLoginRequired
        comment_pk = int(comment_pk)
        data = {
            "is_carousel_bumped_post": "false",
            "container_module": "feed_contextual_self_profile",
            "feed_position": str(random.randint(0, 6)),
        }
        name = "unlike" if revert else "like"
        result = await self.private_request(
            f"media/{comment_pk}/comment_{name}/", self.with_action_data(data)
        )
        return result["status"] == "ok"

    async def comment_unlike(self, comment_pk: int) -> bool:
        """
        Unlike a comment on a media

        Parameters
        ----------
        comment_pk: int
            Unique identifier of a Comment

        Returns
        -------
        bool
            A boolean value
        """
        return await self.comment_like(comment_pk, revert=True)

    async def comment_bulk_delete(self, media_id: str, comment_pks: List[int]) -> bool:
        """
        Delete a comment on a media

        Parameters
        ----------
        media_id: str
            Unique identifier of a Media
        comment_pks: List[int]
            List of unique identifier of a Comment

        Returns
        -------
        bool
            A boolean value
        """
        media_id = await self.media_id(media_id)
        data = {
            "comment_ids_to_delete": ",".join([str(pk) for pk in comment_pks]),
            "container_module": "self_comments_v2_newsfeed_you",
        }
        result = await self.private_request(
            f"media/{media_id}/comment/bulk_delete/", self.with_action_data(data)
        )
        return result["status"] == "ok"

    async def comment_likers_gql_chunk(
        self, comment_pk: str, end_cursor: str = ""
    ) -> Tuple[List[dict], str]:
        """
        Get likers of comment

        Parameters
        ----------
        comment_pk: str
            Unique identifier of a Media
        end_cursor: str
            Cursor

        Returns
        -------
        Tuple[List[dict], str]
            A list of objects of Users
        """
        comment_pk = str(comment_pk)
        self.inject_sessionid_to_public()
        likers = []
        variables = {
            "comment_id": str(comment_pk),
            "first": 50,
        }
        query_hash = "5f0b1f6281e72053cbc07909c8d154ae"
        if end_cursor:
            variables["after"] = end_cursor
        data = await self.public_graphql_request(variables, query_hash=query_hash)
        comment = data.get("comment") or {}
        edge_liked_by = comment.get("edge_liked_by") or {}
        for edge in edge_liked_by.get("edges") or []:
            likers.append(edge["node"])
        end_cursor = ""
        if "page_info" in edge_liked_by:
            page_info = edge_liked_by["page_info"]
            end_cursor = page_info["end_cursor"] if page_info["has_next_page"] else None
        return likers, end_cursor

    async def comment_likers_gql(self, comment_pk: str, amount: int = 0) -> List[dict]:
        """
        Get likers of comment

        Parameters
        ----------
        comment_pk: str
            Unique identifier of a Media
        end_cursor: str
            Cursor

        Returns
        -------
        List[dict]
            A list of objects of Users
        """
        comment_pk = str(comment_pk)
        end_cursor = ""
        likers = []
        while True:
            items, end_cursor = await self.comment_likers_gql_chunk(
                comment_pk, end_cursor=end_cursor
            )
            likers.extend(items)
            if not end_cursor or len(items) == 0:
                break
            if amount and len(likers) >= amount:
                break
        if amount:
            likers = likers[:amount]
        return likers

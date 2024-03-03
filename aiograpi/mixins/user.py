import logging
from typing import Dict, List, Tuple

from orjson import JSONDecodeError

from aiograpi.exceptions import (
    ClientError,
    ClientJSONDecodeError,
    ClientLoginRequired,
    ClientNotFoundError,
    ClientStatusFail,
    IsRegulatedC18Error,
    PreLoginRequired,
    PrivateError,
    UserNotFound,
)
from aiograpi.extractors import (
    extract_about_v1,
    extract_guide_v1,
    extract_user_gql,
    extract_user_short,
    extract_user_v1,
)
from aiograpi.types import (
    About,
    Guide,
    Relationship,
    RelationshipShort,
    User,
    UserShort,
)
from aiograpi.utils import dumps, json_value

logger = logging.getLogger(__name__)


class UserMixin:
    async def user_id_from_username(self, username: str) -> str:
        """
        Get full media id

        Parameters
        ----------
        username: str
            Username for an Instagram account

        Returns
        -------
        str
            User PK

        Example
        -------
        'example' -> 1903424587
        """
        username = str(username).lower()
        user = await self.user_info_by_username(username)
        return str(user.pk)

    async def user_short_gql(self, user_id: str) -> UserShort:
        """
        Get full media id

        Parameters
        ----------
        user_id: str
            User ID

        Returns
        -------
        UserShort
            An object of UserShort type
        """
        variables = {
            "user_id": str(user_id),
            "include_reel": True,
        }
        data = await self.public_graphql_request(
            variables, query_hash="ad99dd9d3646cc3c0dda65debcd266a7"
        )
        if not data["user"]:
            raise UserNotFound(user_id=user_id, **data)
        user = extract_user_short(data["user"]["reel"]["user"])
        return user

    async def username_from_user_id_gql(self, user_id: str) -> str:
        """
        Get username from user id

        Parameters
        ----------
        user_id: str
            User ID

        Returns
        -------
        str
            User name

        Example
        -------
        1903424587 -> 'example'
        """
        return (await self.user_short_gql(user_id)).username

    async def username_from_user_id(self, user_id: str) -> str:
        """
        Get username from user id

        Parameters
        ----------
        user_id: str
            User ID

        Returns
        -------
        str
            User name

        Example
        -------
        1903424587 -> 'example'
        """
        user_id = str(user_id)
        try:
            username = await self.username_from_user_id_gql(user_id)
        except ClientError:
            username = await self.user_info_v1(user_id).username
        return username

    async def user_info_by_username_a1(self, username: str) -> dict:
        """
        Get user object from user name

        Parameters
        ----------
        username: str
            User name of an instagram account

        Returns
        -------
        dict
        """
        username = str(username).lower()
        return await self.public_a1_request(f"/{username}/", full=True)

    async def user_info_by_username_gql(self, username: str) -> User:
        """
        Get user object from user name

        Parameters
        ----------
        username: str
            User name of an instagram account

        Returns
        -------
        User
            An object of User type
        """
        username = str(username).lower()
        resp = await self.public_a1_request(f"/{username}/")
        return extract_user_gql(resp["user"])

    async def user_info_by_username_v1(self, username: str) -> User:
        """
        Get user object from user name

        Parameters
        ----------
        username: str
            User name of an instagram account

        Returns
        -------
        User
            An object of User type
        """
        username = str(username).lower()
        try:
            result = await self.private_request(f"users/{username}/usernameinfo/")
        except ClientNotFoundError as e:
            raise UserNotFound(e, username=username, **self.last_json)
        except ClientError as e:
            if "User not found" in str(e):
                raise UserNotFound(e, username=username, **self.last_json)
            if isinstance(e, ClientStatusFail):
                raise IsRegulatedC18Error(username=username, **self.last_json)
            raise e
        if user := result.get("user"):
            return extract_user_v1(user)
        raise UserNotFound("User not found", username=username, **self.last_json)

    async def user_info_by_username(self, username: str) -> User:
        """
        Get user object from username

        Parameters
        ----------
        username: str
            User name of an instagram account

        Returns
        -------
        User
            An object of User type
        """
        username = str(username).lower()
        try:
            try:
                user = await self.user_info_by_username_gql(username)
            except ClientLoginRequired as e:
                if not self.inject_sessionid_to_public():
                    raise e
                user = await self.user_info_by_username_gql(username)  # retry
        except PrivateError as e:
            raise e
        except Exception as e:
            if not isinstance(e, ClientError):
                self.logger.exception(e)  # Register unknown error
            user = await self.user_info_by_username_v1(username)
        return await self.user_info(user.pk)

    async def user_info_gql(self, user_id: str) -> User:
        """
        Get user object from user id

        Parameters
        ----------
        user_id: str
            User id of an instagram account

        Returns
        -------
        User
            An object of User type
        """
        user_id = str(user_id)
        try:
            # GraphQL haven't method to receive user by id
            return await self.user_info_by_username_gql(
                await self.username_from_user_id_gql(user_id)
            )
        except JSONDecodeError as e:
            raise ClientJSONDecodeError(e, user_id=user_id)

    async def user_info_v1(self, user_id: str) -> User:
        """
        Get user object from user id

        Parameters
        ----------
        user_id: str
            User id of an instagram account

        Returns
        -------
        User
            An object of User type
        """
        user_id = str(user_id)
        try:
            result = await self.private_request(f"users/{user_id}/info/")
        except ClientNotFoundError as e:
            raise UserNotFound(e, user_id=user_id, **self.last_json)
        except ClientError as e:
            if "User not found" in str(e):
                raise UserNotFound(e, user_id=user_id, **self.last_json)
            raise e
        if user := result.get("user"):
            return extract_user_v1(user)
        raise UserNotFound("User not found", user_id=user_id, **self.last_json)

    async def user_about_v1(self, user_id: str) -> About:
        """
        Get about info from user id

        Parameters
        ----------
        user_id: str
            User id of an instagram account

        Returns
        -------
        About
            An object of About type
        """
        user_id = str(user_id)
        bk = dumps(
            {"bloks_version": self.bloks_versioning_id, "styles_id": "instagram"}
        )
        data = {
            "referer_type": "ProfileMore",
            "target_user_id": user_id,
            "bk_client_context": bk,
            "bloks_versioning_id": self.bloks_versioning_id,
        }
        try:
            await self.bloks_action(
                "com.instagram.interactions.about_this_account", data
            )
        except ClientNotFoundError as e:
            raise UserNotFound(e, user_id=user_id, **self.last_json)
        except ClientError as e:
            if "User not found" in str(e):
                raise UserNotFound(e, user_id=user_id, **self.last_json)
            raise e
        return extract_about_v1(self.last_json)

    async def user_info(self, user_id: str) -> User:
        """
        Get user object from user id

        Parameters
        ----------
        user_id: str
            User id of an instagram account

        Returns
        -------
        User
            An object of User type
        """
        user_id = str(user_id)
        try:
            try:
                user = await self.user_info_gql(user_id)
            except ClientLoginRequired as e:
                if not self.inject_sessionid_to_public():
                    raise e
                user = await self.user_info_gql(user_id)  # retry
        except PrivateError as e:
            raise e
        except Exception as e:
            if not isinstance(e, ClientError):
                self.logger.exception(e)
            user = await self.user_info_v1(user_id)
        return user

    async def new_feed_exist(self) -> bool:
        """
        Returns bool
        -------
        Check if new feed exist
        -------
        True if new feed exist ,
        After Login or load Settings always return False
        """
        results = await self.private_request("feed/new_feed_posts_exist/")
        return results.get("new_feed_posts_exist", False)

    async def user_friendships_v1(self, user_ids: List[str]) -> List[RelationshipShort]:
        """
        Get user friendship status

        Parameters
        ----------
        user_ids: List[str]
            List of user ID of an instagram account

        Returns
        -------
        List[RelationshipShort]
           List of RelationshipShorts with requested user_ids
        """
        user_ids_str = ",".join(user_ids)
        result = await self.private_request(
            "friendships/show_many/",
            data={"user_ids": user_ids_str, "_uuid": self.uuid},
            with_signature=False,
        )
        assert result.get("status", "") == "ok"

        relationships = []
        for user_id, status in result.get("friendship_statuses", {}).items():
            relationships.append(RelationshipShort(user_id=user_id, **status))

        return relationships

    async def user_friendship_v1(self, user_id: str) -> Relationship:
        """
        Get user friendship status

        Parameters
        ----------
        user_id: str
            User id of an instagram account

        Returns
        -------
        Relationship
            An object of Relationship type
        """

        try:
            result = await self.private_request(f"friendships/show/{user_id}/")
            assert result.get("status", "") == "ok"

            return Relationship(user_id=user_id, **result)
        except ClientError as e:
            self.logger.exception(e)
            return None

    async def search_users_v1(self, query: str, count: int) -> List[UserShort]:
        """
        Search users by a query (Private Mobile API)
        Parameters
        ----------
        query: str
            Query to search
        count: int
            The count of search results
        Returns
        -------
        List[UserShort]
            List of users
        """
        results = await self.private_request(
            "users/search/", params={"query": query, "count": count}
        )
        users = results.get("users", [])
        return [extract_user_short(user) for user in users]

    async def search_users(self, query: str, count: int = 50) -> List[UserShort]:
        """
        Search users by a query
        Parameters
        ----------
        query: str
            Query string to search
        count: int
            The count of search results
        Returns
        -------
        List[UserShort]
            List of User short object
        """
        return await self.search_users_v1(query, count)

    async def search_followers_v1(self, user_id: str, query: str) -> List[UserShort]:
        """
        Search users by followers (Private Mobile API)

        Parameters
        ----------
        user_id: str
            User id of an instagram account
        query: str
            Query to search

        Returns
        -------
        List[UserShort]
            List of users
        """
        results = await self.private_request(
            f"friendships/{user_id}/followers/",
            params={
                "search_surface": "follow_list_page",
                "query": query,
                "enable_groups": "true",
            },
        )
        users = results.get("users", [])
        return [extract_user_short(user) for user in users]

    async def search_followers(self, user_id: str, query: str) -> List[UserShort]:
        """
        Search by followers

        Parameters
        ----------
        user_id: str
            User id of an instagram account
        query: str
            Query string

        Returns
        -------
        List[UserShort]
            List of User short object
        """
        return await self.search_followers_v1(user_id, query)

    async def search_following_v1(self, user_id: str, query: str) -> List[UserShort]:
        """
        Search following users (Private Mobile API)

        Parameters
        ----------
        user_id: str
            User id of an instagram account
        query: str
            Query to search

        Returns
        -------
        List[UserShort]
            List of users
        """
        results = await self.private_request(
            f"friendships/{user_id}/following/",
            params={
                "includes_hashtags": "false",
                "search_surface": "follow_list_page",
                "query": query,
                "enable_groups": "true",
            },
        )
        users = results.get("users", [])
        return [extract_user_short(user) for user in users]

    async def search_following(self, user_id: str, query: str) -> List[UserShort]:
        """
        Search by following

        Parameters
        ----------
        user_id: str
            User id of an instagram account
        query: str
            Query string

        Returns
        -------
        List[UserShort]
            List of User short object
        """
        return await self.search_following_v1(user_id, query)

    async def user_following_gql_chunk(
        self, user_id: str, end_cursor: str = None
    ) -> Tuple[List[UserShort], str]:
        """
        Get user's following information by Public Graphql API and end_cursor

        Parameters
        ----------
        user_id: str
            User id of an instagram account
        end_cursor: str, optional
            The cursor from which it is worth continuing
            to receive the list of following

        Returns
        -------
        Tuple[List[UserShort], str]
            List of objects of User type with cursor
        """
        self.inject_sessionid_to_public()
        users = []
        user_id = str(user_id)
        variables = {
            "id": user_id,
            "include_reel": True,
            "fetch_mutual": False,
            "first": 50,
        }
        if end_cursor:
            variables["after"] = end_cursor
        data = await self.public_graphql_request(
            variables, query_hash="c56ee0ae1f89cdbd1c89e2bc6b8f3d18"
        )
        if not data["user"] and not users:
            if end_cursor:
                logger.warn("Strange UserNotFound. Request: %r", variables)
            raise UserNotFound(user_id=user_id, **data)
        page = json_value(data, "user", "edge_follow")
        page_info = json_value(page, "page_info", default={})
        edges = json_value(page, "edges", default=[])
        for edge in edges:
            users.append(extract_user_short(edge["node"]))
        end_cursor = page_info.get("end_cursor")
        return users, end_cursor

    async def user_following_gql(
        self, user_id: str, amount: int = 0
    ) -> List[UserShort]:
        """
        Get user's following information by Public Graphql API

        Parameters
        ----------
        user_id: str
            User id of an instagram account
        amount: int, optional
            Maximum number of media to return, default is 0 - Inf

        Returns
        -------
        List[UserShort]
            List of objects of User type
        """
        end_cursor = ""
        users = []
        while True:
            items, end_cursor = await self.user_following_gql_chunk(
                str(user_id), end_cursor=end_cursor
            )
            users.extend(items)
            if not end_cursor or len(items) == 0:
                break
            if amount and len(users) >= amount:
                break
        if amount:
            users = users[:amount]
        return users

    async def user_following_v1(self, user_id: str, amount: int = 0) -> List[UserShort]:
        """
        Get user's following users information by Private Mobile API

        Parameters
        ----------
        user_id: str
            User id of an instagram account
        amount: int, optional
            Maximum number of media to return, default is 0

        Returns
        -------
        List[UserShort]
            List of objects of User type
        """
        unique_set = set()
        max_id = ""
        users = []
        while True:
            items, max_id = await self.user_following_v1_chunk(
                str(user_id), max_id=max_id
            )
            for user in items:
                if user.pk in unique_set:
                    continue
                unique_set.add(user.pk)
                users.append(user)
            if not max_id or len(items) == 0:
                break
            if amount and len(users) >= amount:
                break
        if amount:
            users = users[:amount]
        return users

    async def user_following_v1_chunk(
        self, user_id: str, max_id: str = ""
    ) -> Tuple[List[UserShort], str]:
        """
        Get user's following users information by Private Mobile API and max_id (cursor)

        Parameters
        ----------
        user_id: str
            User id of an instagram account
        max_id: str, optional
            Max ID, default value is empty String

        Returns
        -------
        Tuple[List[UserShort], str]
            Tuple of List of users and max_id
        """
        # if max_amount and max_amount > 100:
        #     max_amount = 100
        unique_set = set()
        users = []

        result = await self.private_request(
            f"friendships/{user_id}/following/",
            params={
                "max_id": max_id,
                # "count": max_amount,
                "rank_token": self.rank_token,
                "search_surface": "follow_list_page",
                # "includes_hashtags": "true",
                "enable_groups": "true",
                "query": "",
            },
        )
        max_id = result.get("next_max_id") or result.get("max_id")
        for user in result.get("users") or []:
            user = extract_user_short(user)
            if user.pk in unique_set:
                continue
            unique_set.add(user.pk)
            users.append(user)
        return users, max_id

    async def user_following(
        self, user_id: str, amount: int = 0
    ) -> Dict[str, UserShort]:
        """
        Get user's followers information

        Parameters
        ----------
        user_id: str
            User id of an instagram account
        amount: int, optional
            Maximum number of media to return, default is 0

        Returns
        -------
        Dict[str, UserShort]
            Dict of user_id and User object
        """
        user_id = str(user_id)
        following = await self.user_following_v1(user_id, amount)
        if amount and len(following) > amount:
            following = following[:amount]
        return following

    async def user_followers_gql_chunk(
        self, user_id: str, end_cursor: str = None
    ) -> Tuple[List[UserShort], str]:
        """
        Get user's followers information by Public Graphql API and end_cursor

        Parameters
        ----------
        user_id: str
            User id of an instagram account
        end_cursor: str, optional
            The cursor from which it is worth continuing
            to receive the list of followers

        Returns
        -------
        Tuple[List[UserShort], str]
            List of objects of User type with cursor
        """
        self.inject_sessionid_to_public()
        users = []
        user_id = str(user_id)
        variables = {
            "id": user_id,
            "include_reel": True,
            "fetch_mutual": False,
            "first": 50,
        }
        if end_cursor:
            variables["after"] = end_cursor
        data = await self.public_graphql_request(
            variables, query_hash="5aefa9893005572d237da5068082d8d5"
        )
        if not data["user"] and not users:
            if end_cursor:
                logger.warn("Strange UserNotFound. Request: %r", variables)
            raise UserNotFound(user_id=user_id, **data)
        page_info = json_value(
            data, "user", "edge_followed_by", "page_info", default={}
        )
        edges = json_value(data, "user", "edge_followed_by", "edges", default=[])
        for edge in edges:
            users.append(extract_user_short(edge["node"]))
        end_cursor = page_info.get("end_cursor")
        return users, end_cursor

    async def user_followers_gql(
        self, user_id: str, amount: int = 0
    ) -> List[UserShort]:
        """
        Get user's followers information by Public Graphql API

        Parameters
        ----------
        user_id: str
            User id of an instagram account
        amount: int, optional
            Maximum number of media to return, default is 0 - Inf

        Returns
        -------
        List[UserShort]
            List of objects of User type
        """
        end_cursor = ""
        users = []
        while True:
            items, end_cursor = await self.user_followers_gql_chunk(
                str(user_id), end_cursor=end_cursor
            )
            users.extend(items)
            if not end_cursor or len(items) == 0:
                break
            if amount and len(users) >= amount:
                break
        if amount:
            users = users[:amount]
        return users

    async def user_followers_v1_chunk(
        self, user_id: str, max_id: str = ""
    ) -> Tuple[List[UserShort], str]:
        """
        Get user's followers information by Private Mobile API and max_id (cursor)

        Parameters
        ----------
        user_id: str
            User id of an instagram account
        max_id: str, optional
            Max ID, default value is empty String

        Returns
        -------
        Tuple[List[UserShort], str]
            Tuple of List of users and max_id
        """
        # if max_amount and max_amount > 100:
        #     max_amount = 100
        unique_set = set()
        users = []
        result = await self.private_request(
            f"friendships/{user_id}/followers/",
            params={
                "max_id": max_id,
                # "count": max_amount,
                "rank_token": self.rank_token,
                "search_surface": "follow_list_page",
                "query": "",
                "enable_groups": "true",
            },
        )
        for user in result.get("users") or []:
            user = extract_user_short(user)
            if user.pk in unique_set:
                continue
            unique_set.add(user.pk)
            users.append(user)
        max_id = result.get("next_max_id") or result.get("max_id")
        return users, max_id

    async def user_followers_v1(self, user_id: str, amount: int = 0) -> List[UserShort]:
        """
        Get user's followers information by Private Mobile API

        Parameters
        ----------
        user_id: str
            User id of an instagram account
        amount: int, optional
            Maximum number of media to return, default is 0 - Inf

        Returns
        -------
        List[UserShort]
            List of objects of User type
        """
        unique_set = set()
        max_id = ""
        users = []
        while True:
            items, max_id = await self.user_followers_v1_chunk(
                str(user_id), max_id=max_id
            )
            for user in items:
                if user.pk in unique_set:
                    continue
                unique_set.add(user.pk)
                users.append(user)
            if not max_id or len(items) == 0:
                break
            if amount and len(users) >= amount:
                break
        if amount:
            users = users[:amount]
        return users

    async def user_followers(
        self, user_id: str, amount: int = 0
    ) -> Dict[str, UserShort]:
        """
        Get user's followers

        Parameters
        ----------
        user_id: str
            User id of an instagram account
        amount: int, optional
            Maximum number of media to return, default is 0 - Inf

        Returns
        -------
        Dict[str, UserShort]
            Dict of user_id and User object
        """
        user_id = str(user_id)
        users = []
        try:
            users = await self.user_followers_gql(user_id, amount)
        except PrivateError as e:
            raise e
        except Exception as e:
            if not isinstance(e, ClientError):
                self.logger.exception(e)
            users = await self.user_followers_v1(user_id, amount)
        if amount and len(users) > amount:
            users = users[:amount]
        return users

    async def user_follow(self, user_id: str) -> bool:
        """
        Follow a user

        Parameters
        ----------
        user_id: str

        Returns
        -------
        bool
            A boolean value
        """
        if not self.user_id:
            raise PreLoginRequired
        user_id = str(user_id)
        if user_id in self._users_following.get(self.user_id, []):
            self.logger.debug("User %s already followed", user_id)
            return False
        data = self.with_action_data({"user_id": user_id})
        result = await self.private_request(f"friendships/create/{user_id}/", data)
        if self.user_id in self._users_following:
            self._users_following.pop(self.user_id)  # reset
        return result["friendship_status"]["following"] is True

    async def user_unfollow(self, user_id: str) -> bool:
        """
        Unfollow a user

        Parameters
        ----------
        user_id: str

        Returns
        -------
        bool
            A boolean value
        """
        if not self.user_id:
            raise PreLoginRequired
        user_id = str(user_id)
        data = self.with_action_data({"user_id": user_id})
        result = await self.private_request(f"friendships/destroy/{user_id}/", data)
        if self.user_id in self._users_following:
            self._users_following[self.user_id].pop(user_id, None)
        return result["friendship_status"]["following"] is False

    async def user_remove_follower(self, user_id: str) -> bool:
        """
        Remove a follower

        Parameters
        ----------
        user_id: str

        Returns
        -------
        bool
            A boolean value
        """
        if not self.user_id:
            raise PreLoginRequired
        user_id = str(user_id)
        data = self.with_action_data({"user_id": str(user_id)})
        result = await self.private_request(
            f"friendships/remove_follower/{user_id}/", data
        )
        if self.user_id in self._users_followers:
            self._users_followers[self.user_id].pop(user_id, None)
        return result["friendship_status"]["followed_by"] is False

    async def mute_posts_from_follow(self, user_id: str, revert: bool = False) -> bool:
        """
        Mute posts from following user

        Parameters
        ----------
        user_id: str
            Unique identifier of a User
        revert: bool, optional
            Unmute when True

        Returns
        -------
        bool
            A boolean value
        """
        user_id = str(user_id)
        name = "unmute" if revert else "mute"
        result = await self.private_request(
            f"friendships/{name}_posts_or_story_from_follow/",
            {
                # "media_id": media_pk,  # when feed_timeline
                "target_posts_author_id": str(user_id),
                "container_module": "media_mute_sheet",  # or "feed_timeline"
            },
        )
        return result["status"] == "ok"

    async def unmute_posts_from_follow(self, user_id: str) -> bool:
        """
        Unmute posts from following user

        Parameters
        ----------
        user_id: str
            Unique identifier of a User

        Returns
        -------
        bool
            A boolean value
        """
        return await self.mute_posts_from_follow(user_id, True)

    async def mute_stories_from_follow(
        self, user_id: str, revert: bool = False
    ) -> bool:
        """
        Mute stories from following user

        Parameters
        ----------
        user_id: str
            Unique identifier of a User
        revert: bool, optional
            Unmute when True

        Returns
        -------
        bool
            A boolean value
        """
        user_id = str(user_id)
        name = "unmute" if revert else "mute"
        result = await self.private_request(
            f"friendships/{name}_posts_or_story_from_follow/",
            {
                # "media_id": media_pk,  # when feed_timeline
                "target_reel_author_id": str(user_id),
                "container_module": "media_mute_sheet",  # or "feed_timeline"
            },
        )
        return result["status"] == "ok"

    async def unmute_stories_from_follow(self, user_id: str) -> bool:
        """
        Unmute stories from following user

        Parameters
        ----------
        user_id: str
            Unique identifier of a User

        Returns
        -------
        bool
            A boolean value
        """
        return await self.mute_stories_from_follow(user_id, True)

    async def enable_posts_notifications(
        self, user_id: str, disable: bool = False
    ) -> bool:
        """
        Enable post notifications of a user

        Parameters
        ----------
        user_id: str
            Unique identifier of a User
        disable: bool, optional
            Unfavorite when True

        Returns
        -------
        bool
            A boolean value
        """
        if not self.user_id:
            raise PreLoginRequired
        user_id = str(user_id)
        data = self.with_action_data({"user_id": user_id, "_uid": self.user_id})
        name = "unfavorite" if disable else "favorite"
        result = await self.private_request(f"friendships/{name}/{user_id}/", data)
        return result["status"] == "ok"

    async def disable_posts_notifications(self, user_id: str) -> bool:
        """
        Disable post notifications of a user

        Parameters
        ----------
        user_id: str
            Unique identifier of a User
        Returns
        -------
        bool
            A boolean value
        """
        return await self.enable_posts_notifications(user_id, True)

    async def enable_videos_notifications(
        self, user_id: str, revert: bool = False
    ) -> bool:
        """
        Enable videos notifications of a user

        Parameters
        ----------
        user_id: str
            Unique identifier of a User
        revert: bool, optional
            Unfavorite when True

        Returns
        -------
        bool
        A boolean value
        """
        if not self.user_id:
            raise PreLoginRequired
        user_id = str(user_id)
        data = self.with_action_data({"user_id": user_id, "_uid": self.user_id})
        name = "unfavorite" if revert else "favorite"
        result = await self.private_request(
            f"friendships/{name}_for_igtv/{user_id}/", data
        )
        return result["status"] == "ok"

    async def disable_videos_notifications(self, user_id: str) -> bool:
        """
        Disable videos notifications of a user

        Parameters
        ----------
        user_id: str
            Unique identifier of a User
        Returns
        -------
        bool
            A boolean value
        """
        return await self.enable_videos_notifications(user_id, True)

    async def enable_reels_notifications(
        self, user_id: str, revert: bool = False
    ) -> bool:
        """
        Enable reels notifications of a user

        Parameters
        ----------
        user_id: str
            Unique identifier of a User
        revert: bool, optional
            Unfavorite when True

        Returns
        -------
        bool
        A boolean value
        """
        if not self.user_id:
            raise PreLoginRequired
        user_id = str(user_id)
        data = self.with_action_data({"user_id": user_id, "_uid": self.user_id})
        name = "unfavorite" if revert else "favorite"
        result = await self.private_request(
            f"friendships/{name}_for_clips/{user_id}/", data
        )
        return result["status"] == "ok"

    async def disable_reels_notifications(self, user_id: str) -> bool:
        """
        Disable reels notifications of a user

        Parameters
        ----------
        user_id: str
            Unique identifier of a User
        Returns
        -------
        bool
            A boolean value
        """
        return await self.enable_reels_notifications(user_id, True)

    async def enable_stories_notifications(
        self, user_id: str, revert: bool = False
    ) -> bool:
        """
        Enable stories notifications of a user

        Parameters
        ----------
        user_id: str
            Unique identifier of a User
        revert: bool, optional
            Unfavorite when True

        Returns
        -------
        bool
        A boolean value
        """
        if not self.user_id:
            raise PreLoginRequired
        user_id = str(user_id)
        data = self.with_action_data({"user_id": user_id, "_uid": self.user_id})
        name = "unfavorite" if revert else "favorite"
        result = await self.private_request(
            f"friendships/{name}_for_stories/{user_id}/", data
        )
        return result["status"] == "ok"

    async def disable_stories_notifications(self, user_id: str) -> bool:
        """
        Disable stories notifications of a user

        Parameters
        ----------
        user_id: str
            Unique identifier of a User
        Returns
        -------
        bool
            A boolean value
        """
        return await self.enable_stories_notifications(user_id, True)

    async def user_guides_v1(self, user_id: int) -> List[Guide]:
        """
        Get guides by user_id

        Parameters
        ----------
        user_id: int

        Returns
        -------
        List[Guide]
            List of objects of Guide
        """
        user_id = int(user_id)
        result = await self.private_request(f"guides/user/{user_id}/")
        return [extract_guide_v1(item) for item in (result.get("guides") or [])]

    async def user_stream_by_username_v1(self, username: str) -> dict:
        """
        Get stream object from user name

        Parameters
        ----------
        username: str
            User name of an instagram account

        Returns
        -------
        Dict
            An object of user stream (user info)
        """
        username = str(username).lower()
        data = {
            "is_prefetch": False,
            "entry_point": "profile",
            "from_module": "feed_timeline",
        }
        try:
            result = await self.private_request(
                f"users/{username}/usernameinfo_stream/", data=data
            )
        except ClientNotFoundError as e:
            raise UserNotFound(e, username=username, **self.last_json)
        except ClientError as e:
            raise UserNotFound(e, username=username, **self.last_json)
        return result

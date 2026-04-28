import json
import logging
from typing import Dict, List, Tuple

from orjson import JSONDecodeError

from aiograpi.exceptions import (
    ClientError,
    ClientGraphqlError,
    ClientJSONDecodeError,
    ClientLoginRequired,
    ClientNotFoundError,
    ClientStatusFail,
    InvalidTargetUser,
    IsRegulatedC18Error,
    PreLoginRequired,
    PrivateError,
    UnknownError,
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
from aiograpi.utils import dumps, generate_jazoest, json_value

MAX_USER_COUNT = 200
INFO_FROM_MODULES = ("self_profile", "feed_timeline", "reel_feed_timeline")
GRAPHQL_WEB_API_URL = "https://www.instagram.com/api/graphql"
GQL_STUFF = {
    "av": "17841464591314721",
    "__d": "www",
    "__user": "0",
    "__a": "1",
    "__req": "q",
    "__hs": "19768.HYP:instagram_web_pkg.2.1..0.1",
    "dpr": "2",
    "__ccg": "UNKNOWN",
    "__rev": "1011444902",
    "__s": "x82a1q:agr3gd:4nh4nl",
    "__hsi": "7335888108907652597",
    "__dyn": (
        "7xeUjG1mxu1syUbFp40NonwgU7SbzEdF8aUco2qwJxS0k24o0B-"
        "q1ew65xO0FE2awt81s8hwGwQwoEcE7O2l0Fwqo31w9O7U2cxe0E"
        "UjwGzEaE7622362W2K0zK5o4q3y1Sx-0iS2Sq2-azqwt8dUaob8"
        "2cwMwrUdUbGwmk0KU6O1FwlE6PhA6bxy4VUKUnAwHw"
    ),
    "__csr": (
        "g9cj5kxfs8lifTitQDqhdhalmDEAJaKBRJFdkAGHBkPy9HgCA-A"
        "rtucm5bCBBGpyAoz-mLJpXJufKWGQ9hHhAhnKECuFUZ3Q8Jkmmp"
        "eWyGAzkEj_CjyoZUgK-E8bwYzaxy00ktMGx20XU3gw4KAo3MChU"
        "jw3N80poolwiA1d7G2yu2ucxi1nwEw16OE1JsS043Etw63wkSEgg1Mu00yiU"
    ),
    "__comet_req": "7",
    "lsd": "6b2800R9u4biJOYjcdXFEI",
    "__spin_r": "1011444902",
    "__spin_b": "trunk",
    "__spin_t": "1708019550",
    "fb_api_caller_class": "RelayModern",
    "fb_api_req_friendly_name": "PolarisProfilePageContentQuery",
    "server_timestamps": "true",
}

logger = logging.getLogger(__name__)

try:
    from typing import Literal

    INFO_FROM_MODULE = Literal[INFO_FROM_MODULES]
except Exception:
    INFO_FROM_MODULE = str


class UserMixin:
    """
    Helpers to manage user
    """

    _users_following = {}  # user_pk -> dict(user_pk -> "short user object")
    _users_followers = {}  # user_pk -> dict(user_pk -> "short user object")

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
        try:
            data = await self.public_graphql_request(
                variables, query_hash="ad99dd9d3646cc3c0dda65debcd266a7"
            )
            if not data["user"]:
                raise UserNotFound(user_id=user_id, **data)
            user = extract_user_short(data["user"]["reel"]["user"])
        except ClientGraphqlError:
            user = extract_user_short(await self.user_web_profile_info_gql(user_id))
        return user

    async def user_web_profile_info_gql(self, user_id: str) -> dict:
        user_id = str(user_id)
        if not self.inject_sessionid_to_public():
            raise ClientLoginRequired("Session is required for web profile GraphQL")
        doc_id = "26762473490008061"
        variables = {
            "enable_integrity_filters": True,
            "id": user_id,
            "render_surface": "PROFILE",
            "__relay_internal__pv__PolarisCannesGuardianExperienceEnabledrelayprovider": True,
            "__relay_internal__pv__PolarisCASB976ProfileEnabledrelayprovider": False,
            "__relay_internal__pv__PolarisRepostsConsumptionEnabledrelayprovider": False,
        }
        headers = {
            "Origin": "https://www.instagram.com",
            "Authority": "www.instagram.com",
            "Sec-Fetch-Site": "same-origin",
            "X-FB-Friendly-Name": "PolarisProfilePageContentQuery",
        }
        body = await self.public_request(
            GRAPHQL_WEB_API_URL,
            data={
                "variables": dumps(variables),
                "doc_id": doc_id,
                "fb_dtsg": await self.fb_dtsg,
                "jazoest": generate_jazoest(self.phone_id),
                **GQL_STUFF,
            },
            headers=headers,
            update_headers=False,
            return_json=True,
        )
        if errs := body.get("errors"):
            if "data" not in body:
                summary = errs[0].get("summary")
                description = errs[0].get("description")
                raise ClientGraphqlError(
                    "GraphQL user profile fallback failed. Summary: '{}'. Description: '{}'".format(
                        summary, description
                    )
                )
        data = body.get("data")
        if not data or not data.get("user"):
            raise UserNotFound(user_id=user_id, **body)
        return data["user"]

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
        temporary_public_headers = {
            "Host": "www.instagram.com",
            "X-Requested-With": "XMLHttpRequest",
            "Sec-Ch-Prefers-Color-Scheme": "dark",
            "Sec-Ch-Ua-Platform": '"Linux"',
            "X-Ig-App-Id": "936619743392459",
            "Sec-Ch-Ua-Model": '""',
            "Sec-Ch-Ua-Mobile": "?0",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.6261.112 Safari/537.36"
            ),
            "Accept": "*/*",
            "X-Asbd-Id": "129477",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": "https://www.instagram.com/",
            "Accept-Language": "en-US,en;q=0.9",
            "Priority": "u=1, i",
        }
        return extract_user_gql(
            json.loads(
                await self.public_request(
                    f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}",
                    headers=temporary_public_headers,
                )
            )["data"]["user"]
        )

    def _inject_sessionid_for_v2_gql(self) -> None:
        """The new doc_id endpoints require logged-in cookies. Bridge the
        private session's sessionid into the public session so
        public_doc_id_graphql_request carries it."""
        try:
            self.inject_sessionid_to_public()
        except Exception:  # nosec B110 - anonymous caller; IG will 403 if auth needed
            pass

    async def user_info_v2_gql(self, user_id: str) -> User:
        """
        Get user object via the new PolarisProfilePageContentQuery doc_id.

        IG migrated logged-in profile fetches off ``api/v1/users/web_profile_info/``
        to a doc_id-based GraphQL endpoint. This method posts to that endpoint
        and normalizes the response into the same legacy shape that
        :func:`extract_user_v1` understands.

        Use this when ``user_info_by_username_gql`` starts returning
        unauthorized / empty for logged-in callers.

        Parameters
        ----------
        user_id: str
            Numeric user id ("pk").

        Returns
        -------
        User
            An object of User type.
        """
        variables = {
            "id": str(user_id),
            "render_surface": "PROFILE",
            # Relay provider flags carried over from PolarisProfilePageContentQuery.
            "__relay_internal__pv__PolarisCannesGuardianExperienceEnabledrelayprovider": True,
            "__relay_internal__pv__PolarisCASB976ProfileEnabledrelayprovider": False,
            "__relay_internal__pv__PolarisRepostsConsumptionEnabledrelayprovider": False,
        }
        self._inject_sessionid_for_v2_gql()
        data = await self.public_doc_id_graphql_request("25980296051578533", variables)
        user_data = (data or {}).get("user")
        if user_data is None:
            raise UserNotFound("User not found", user_id=user_id)
        return extract_user_v1(self._normalize_polaris_profile(user_data))

    async def user_info_by_username_v2_gql(self, username: str) -> User:
        """
        Get user object via the new doc_id-based GraphQL endpoints.

        Two-step: first resolve username → user_id via the FB search query
        (doc_id 26347858941511777), then fetch the profile via
        :meth:`user_info_v2_gql`. Provides a logged-in-friendly alternative
        to :meth:`user_info_by_username_gql` (which uses the increasingly
        flaky ``api/v1/users/web_profile_info/`` endpoint).

        Parameters
        ----------
        username: str
            User name of an instagram account.

        Returns
        -------
        User
            An object of User type.
        """
        username = str(username).lower()
        self._inject_sessionid_for_v2_gql()
        data = await self.public_doc_id_graphql_request(
            "26347858941511777", {"hasQuery": True, "query": username}
        )
        # Defend against `{"xdt_api__v1__fbsearch__non_profiled_serp": null}` —
        # `.get(key, {})` returns the default ONLY when key is absent;
        # if the key is present with value `None`, the chained `.get` would
        # crash with AttributeError. Promote None → {} explicitly.
        users = (
            (data or {}).get("xdt_api__v1__fbsearch__non_profiled_serp") or {}
        ).get("users") or []
        for user in users:
            if (user.get("username") or "").lower() == username:
                return await self.user_info_v2_gql(user.get("pk") or user.get("id"))
        raise UserNotFound("User not found", username=username)

    @staticmethod
    def _normalize_polaris_profile(user_data: dict) -> dict:
        """Map PolarisProfilePageContentQuery fields onto the legacy v1 shape
        understood by :func:`extract_user_v1`."""
        normalized = dict(user_data)
        if "pk" not in normalized and "id" in normalized:
            normalized["pk"] = normalized["id"]
        if "is_business" not in normalized and "is_business_account" in normalized:
            normalized["is_business"] = normalized["is_business_account"]
        if "category" not in normalized and "category_name" in normalized:
            normalized["category"] = normalized["category_name"]
        # PolarisProfilePageContentQuery puts viewer-relationship flags
        # under friendship_status; aiograpi User doesn't track them, but
        # flatten anyway in case future fields land.
        friendship = normalized.get("friendship_status") or {}
        normalized.setdefault("followed_by_viewer", friendship.get("following", False))
        normalized.setdefault("follows_viewer", friendship.get("followed_by", False))
        return normalized

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

    async def user_info_v1(
        self,
        user_id: str,
        from_module: INFO_FROM_MODULE = "self_profile",
        is_app_start: bool = False,
    ) -> User:
        """
        Get user object from user id

        Parameters
        ----------
        user_id: str
            User id of an instagram account
        from_module: str
            Which module triggered request: self_profile, feed_timeline,
            reel_feed_timeline. Default: self_profile
        is_app_start: bool
            Boolean value specifying if profile is being retrieved on app launch

        Returns
        -------
        User
            An object of User type
        """
        user_id = str(user_id)
        try:
            params = {
                "is_prefetch": "false",
                "entry_point": "self_profile",
                "from_module": from_module,
                "is_app_start": is_app_start,
            }
            assert (
                from_module in INFO_FROM_MODULES
            ), f'Unsupported send_attribute="{from_module}" {INFO_FROM_MODULES}'
            if from_module != "self_profile":
                params["entry_point"] = "profile"

            result = await self.private_request(f"users/{user_id}/info/", params=params)
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
            params = {
                "is_external_deeplink_profile_view": "false",
            }
            result = await self.private_request(
                f"friendships/show/{user_id}/", params=params
            )
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
        self, user_id: str, max_amount: int = 0, end_cursor: str = None
    ) -> Tuple[List[UserShort], str]:
        """
        Get user's following information by Public Graphql API and end_cursor

        Parameters
        ----------
        user_id: str
            User id of an instagram account
        max_amount: int, optional
            Maximum number of users to return, default is 0 - Inf
        end_cursor: str, optional
            The cursor from which it is worth continuing
            to receive the list of following

        Returns
        -------
        Tuple[List[UserShort], str]
            List of objects of User type with cursor
        """
        users = []
        variables = {
            "id": user_id,
            "include_reel": True,
            "fetch_mutual": False,
            "first": 24,
        }
        self.inject_sessionid_to_public()
        while True:
            if end_cursor:
                variables["after"] = end_cursor
            data = await self.public_graphql_request(
                variables, query_hash="58712303d941c6855d4e888c5f0cd22f"
            )
            if not data["user"] and not users:
                raise UserNotFound(user_id=user_id, **data)
            page_info = json_value(data, "user", "edge_follow", "page_info", default={})
            edges = json_value(data, "user", "edge_follow", "edges", default=[])
            for edge in edges:
                users.append(extract_user_short(edge["node"]))
            end_cursor = page_info.get("end_cursor")
            if not page_info.get("has_next_page") or not end_cursor:
                break
            if max_amount and len(users) >= max_amount:
                break
        return users, end_cursor

    async def user_following_gql(
        self, user_id: str, amount: int = 0
    ) -> List[UserShort]:
        """
        Get user's following users information by Public Graphql API

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
        users, _ = await self.user_following_gql_chunk(str(user_id), amount)
        if amount:
            users = users[:amount]
        return users

    async def user_following_v1_chunk(
        self, user_id: str, max_amount: int = 0, max_id: str = ""
    ) -> Tuple[List[UserShort], str]:
        """
        Get user's following users information by Private Mobile API and max_id (cursor)

        Parameters
        ----------
        user_id: str
            User id of an instagram account
        max_amount: int, optional
            Maximum number of users to return, default is 0 - Inf
        max_id: str, optional
            Max ID, default value is empty String

        Returns
        -------
        Tuple[List[UserShort], str]
            Tuple of List of users and max_id
        """
        unique_set = set()
        users = []
        while True:
            params = {
                "count": max_amount or MAX_USER_COUNT,
                "rank_token": self.rank_token,
                "search_surface": "follow_list_page",
                "query": "",
                "enable_groups": "true",
            }
            if max_id:
                params["max_id"] = max_id
            result = await self.private_request(
                f"friendships/{user_id}/following/",
                params=params,
            )
            for user in result["users"]:
                user = extract_user_short(user)
                if user.pk in unique_set:
                    continue
                unique_set.add(user.pk)
                users.append(user)
            max_id = result.get("next_max_id")
            if not max_id or (max_amount and len(users) >= max_amount):
                break
        return users, max_id

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
        users, _ = await self.user_following_v1_chunk(str(user_id), amount)
        if amount:
            users = users[:amount]
        return users

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
        self, user_id: str, max_amount: int = 0, end_cursor: str = None
    ) -> Tuple[List[UserShort], str]:
        """
        Get user's followers information by Public Graphql API and end_cursor

        Parameters
        ----------
        user_id: str
            User id of an instagram account
        max_amount: int, optional
            Maximum number of users to return, default is 0 - Inf
        end_cursor: str, optional
            The cursor from which it is worth continuing
            to receive the list of followers

        Returns
        -------
        Tuple[List[UserShort], str]
            List of objects of User type with cursor
        """
        user_id = str(user_id)
        users = []
        variables = {
            "id": user_id,
            "include_reel": True,
            "fetch_mutual": False,
            "first": 12,
        }
        self.inject_sessionid_to_public()
        while True:
            if end_cursor:
                variables["after"] = end_cursor
            data = await self.public_graphql_request(
                variables, query_hash="37479f2b8209594dde7facb0d904896a"
            )
            if not data["user"] and not users:
                raise UserNotFound(user_id=user_id, **data)
            page_info = json_value(
                data, "user", "edge_followed_by", "page_info", default={}
            )
            edges = json_value(data, "user", "edge_followed_by", "edges", default=[])
            for edge in edges:
                users.append(extract_user_short(edge["node"]))
            end_cursor = page_info.get("end_cursor")
            if not page_info.get("has_next_page") or not end_cursor:
                break
            if max_amount and len(users) >= max_amount:
                break
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
        users, _ = await self.user_followers_gql_chunk(str(user_id), amount)
        if amount:
            users = users[:amount]
        return users

    async def user_followers_v1_chunk(
        self, user_id: str, max_amount: int = 0, max_id: str = ""
    ) -> Tuple[List[UserShort], str]:
        """
        Get user's followers information by Private Mobile API and max_id (cursor)

        Parameters
        ----------
        user_id: str
            User id of an instagram account
        max_amount: int, optional
            Maximum number of users to return, default is 0 - Inf
        max_id: str, optional
            Max ID, default value is empty String

        Returns
        -------
        Tuple[List[UserShort], str]
            Tuple of List of users and max_id
        """
        unique_set = set()
        users = []
        while True:
            params = {
                "count": max_amount or MAX_USER_COUNT,
                "rank_token": self.rank_token,
                "search_surface": "follow_list_page",
                "query": "",
                "enable_groups": "true",
            }
            if max_id:
                params["max_id"] = max_id
            result = await self.private_request(
                f"friendships/{user_id}/followers/",
                params=params,
            )
            for user in result["users"]:
                user = extract_user_short(user)
                if user.pk in unique_set:
                    continue
                unique_set.add(user.pk)
                users.append(user)
            max_id = result.get("next_max_id")
            if not max_id or (max_amount and len(users) >= max_amount):
                break
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
        users, _ = await self.user_followers_v1_chunk(str(user_id), amount)
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

    async def user_block(self, user_id: str, surface: str = "profile") -> bool:
        """
        Block a User

        Parameters
        ----------
        user_id: str
            User ID of an Instagram account
        surface: str, (optional)
            Surface of block (deafult "profile", also can be "direct_thread_info")

        Returns
        -------
        bool
            A boolean value
        """
        data = {
            "surface": surface,
            "is_auto_block_enabled": "false",
            "user_id": user_id,
            "_uid": self.user_id,
            "_uuid": self.uuid,
        }
        if surface == "direct_thread_info":
            data["client_request_id"] = self.request_id

        result = await self.private_request(f"friendships/block/{user_id}/", data)
        assert result.get("status", "") == "ok"

        return result.get("friendship_status", {}).get("blocking") is True

    async def user_unblock(self, user_id: str, surface: str = "profile") -> bool:
        """
        Unlock a User

        Parameters
        ----------
        user_id: str
            User ID of an Instagram account
        surface: str, (optional)
            Surface of block (deafult "profile", also can be "direct_thread_info")

        Returns
        -------
        bool
            A boolean value
        """
        data = {
            "container_module": surface,
            "user_id": user_id,
            "_uid": self.user_id,
            "_uuid": self.uuid,
        }
        if surface == "direct_thread_info":
            data["client_request_id"] = self.request_id

        result = await self.private_request(f"friendships/unblock/{user_id}/", data)
        assert result.get("status", "") == "ok"

        return result.get("friendship_status", {}).get("blocking") is False

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

    async def close_friend_add(self, user_id: str):
        """
        Add to Close Friends List

        Parameters
        ----------
        user_id: str
            Unique identifier of a User
        Returns
        -------
        bool
            A boolean value
        """
        assert self.user_id, "Login required"
        user_id = str(user_id)
        data = {
            "block_on_empty_thread_creation": "false",
            "module": "CLOSE_FRIENDS_V2_SEARCH",
            "source": "audience_manager",
            "_uid": self.user_id,
            "_uuid": self.uuid,
            "remove": [],
            "add": [user_id],
        }
        result = await self.private_request("friendships/set_besties/", data)
        return json_value(result, "friendship_statuses", user_id, "is_bestie")

    async def close_friend_remove(self, user_id: str):
        """
        Remove from Close Friends List

        Parameters
        ----------
        user_id: str
            Unique identifier of a User
        Returns
        -------
        bool
            A boolean value
        """
        assert self.user_id, "Login required"
        user_id = str(user_id)
        data = {
            "block_on_empty_thread_creation": "false",
            "module": "CLOSE_FRIENDS_V2_SEARCH",
            "source": "audience_manager",
            "_uid": self.user_id,
            "_uuid": self.uuid,
            "remove": [user_id],
            "add": [],
        }
        result = await self.private_request("friendships/set_besties/", data)
        return json_value(result, "friendship_statuses", user_id, "is_bestie") is False

    async def creator_info(
        self, user_id: str, entry_point: str = "direct_thread"
    ) -> Tuple[UserShort, Dict]:
        """
        Retrieves Creator's information

        Parameters
        ----------
        user_id: str
            Unique identifier of a User
        entry_point: str, optional
            Entry point for retrieving, default - direct_thread
            When passing self_profile, own user_id must be provided

        Returns
        -------
        Tuple[UserShort, Dict]
            Retrieved User and his Creator's Info
        """
        assert self.user_id, "Login required"
        params = {
            "entry_point": entry_point,
            "surface_type": "android",
            "user_id": user_id,
        }

        result = await self.private_request("creator/creator_info/", params=params)
        assert result.get("status", "") == "ok"

        creator_info = result.get("user", {}).pop("creator_info", {})
        user = extract_user_short(result.get("user", {}))
        return (user, creator_info)

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

    async def feed_user_stream_item(
        self,
        item_id: str,
        is_pull_to_refresh: bool = False,
    ) -> dict:
        """
        Fetch the streamed feed for a user (profile grid stream).

        ``POST /feed/user_stream/{item_id}/`` — returns the per-user feed
        delivered as a streaming response. ``item_id`` is typically the
        target user pk. Sends the standard ``_uuid`` payload IG expects on
        POST endpoints.

        Parameters
        ----------
        item_id: str
            Target user pk (or other stream resource id).
        is_pull_to_refresh: bool, default False
            Set to True to mimic a pull-to-refresh fetch (sends
            ``is_pull_to_refresh="true"``).

        Returns
        -------
        dict
            Parsed JSON response. Streaming envelopes are aggregated by
            ``private_request`` into a ``stream_rows`` key when needed.
        """
        data = {
            "_uuid": self.uuid,
        }
        if is_pull_to_refresh:
            data["is_pull_to_refresh"] = "true"
        return await self.private_request(f"feed/user_stream/{item_id}/", data=data)

    async def private_graphql_followers_list(
        self,
        user_id: str,
        rank_token: str,
        client_doc_id: str = "28479704798344003308647327139",
        max_id: int = None,
        priority: str = None,
        exclude_field_is_favorite: bool = None,
        exclude_unused_fields: bool = None,
    ) -> dict:
        """
        Private-side ``FollowersList`` GraphQL query.

        Newer mobile-app surface that returns the followers list via
        ``i.instagram.com/graphql/query`` (root field
        ``xdt_api__v1__friendships__followers``). Prefer the higher-level
        ``user_followers_v1`` / ``user_followers_gql`` helpers when you
        just need a list of users — this is the raw doc-id wrapper.

        Parameters
        ----------
        user_id: str
            Target user pk.
        rank_token: str
            UUID-style rank token IG generates per follow-list session.
        client_doc_id: str, optional
            Numeric doc id of the registered query.
        max_id: int, optional
            Cursor for pagination.
        priority: str, optional
            ``Priority`` header value, e.g. ``"u=3, i"``.
        exclude_field_is_favorite, exclude_unused_fields: bool, optional
            Forwarded to the ``variables`` payload.

        Returns
        -------
        dict
            Raw GraphQL response.
        """
        request_data = {
            "rank_token": rank_token,
            "enableGroups": True,
        }
        variables = {
            "include_unseen_count": False,
            "query": "",
            "include_biography": False,
            "user_id": str(user_id),
            "request_data": request_data,
            "search_surface": "follow_list_page",
        }
        if exclude_field_is_favorite is not None:
            variables["exclude_field_is_favorite"] = exclude_field_is_favorite
        if max_id is not None:
            variables["max_id"] = max_id
        if exclude_unused_fields is not None:
            variables["exclude_unused_fields"] = exclude_unused_fields
        return await self.private_graphql_query_request(
            friendly_name="FollowersList",
            root_field_name="xdt_api__v1__friendships__followers",
            variables=variables,
            client_doc_id=client_doc_id,
            priority=priority,
        )

    async def private_graphql_following_list(
        self,
        user_id: str,
        rank_token: str,
        client_doc_id: str = "16104639289023609826830352479",
        max_id: int = None,
        priority: str = None,
        exclude_field_is_favorite: bool = None,
        exclude_unused_fields: bool = None,
    ) -> dict:
        """
        Private-side ``FollowingList`` GraphQL query.

        Mirror of ``private_graphql_followers_list`` for the following
        edge — root field ``xdt_api__v1__friendships__following``.
        """
        request_data = {
            "search_surface": "follow_list_page",
            "rank_token": rank_token,
            "includes_hashtags": True,
        }
        variables = {
            "include_unseen_count": False,
            "enable_groups": True,
            "user_id": str(user_id),
            "request_data": request_data,
            "include_biography": False,
            "query": "",
        }
        if exclude_field_is_favorite is not None:
            variables["exclude_field_is_favorite"] = exclude_field_is_favorite
        if max_id is not None:
            variables["max_id"] = max_id
        if exclude_unused_fields is not None:
            variables["exclude_unused_fields"] = exclude_unused_fields
        return await self.private_graphql_query_request(
            friendly_name="FollowingList",
            root_field_name="xdt_api__v1__friendships__following",
            variables=variables,
            client_doc_id=client_doc_id,
            priority=priority,
        )

    async def private_graphql_clips_profile(
        self,
        target_user_id: str,
        client_doc_id: str = "209049231614685382737238866578",
        priority: str = None,
        initial_stream_count: int = 6,
        page_size: int = 12,
        no_of_medias_in_each_chunk: int = 6,
    ) -> dict:
        """
        Private-side ``ClipsProfileQuery`` GraphQL query.

        Returns the profile-grid Reels stream for ``target_user_id`` via
        ``i.instagram.com/graphql/query`` (root field
        ``xdt_user_clips_graphql``). For a parsed list of media use
        ``user_clips_v1`` instead — this is the raw doc-id wrapper.

        Parameters
        ----------
        target_user_id: str
            Target user pk.
        client_doc_id: str, optional
            Numeric doc id of the registered query.
        priority: str, optional
        initial_stream_count: int, default 6
        page_size: int, default 12
        no_of_medias_in_each_chunk: int, default 6

        Returns
        -------
        dict
            Raw GraphQL response (often a streamed envelope).
        """
        inner_data = {
            "target_user_id": str(target_user_id),
            # IG returns a multi-document NDJSON envelope when these are
            # True; turn them off so the response is a single JSON we can
            # parse with response.json(). Set them back to True if you
            # want raw streamed media chunks (you'll need to parse it
            # yourself from the raw .text).
            "should_stream_response": False,
            "sort_by_views": False,
            "max_id": None,
            "include_feed_video": True,
            "audience": None,
        }
        if page_size:
            inner_data["page_size"] = page_size
        if no_of_medias_in_each_chunk:
            inner_data["no_of_medias_in_each_chunk"] = no_of_medias_in_each_chunk
        variables = {
            "use_stream": False,
            "use_defer": False,
            "enable_video_versions_in_light_media": True,
            "exclude_caption_user_field": False,
            "enable_thumbnails_in_light_media": False,
            "enable_audience_in_light_media": False,
            "enable_clips_metadata_in_light_media": False,
            "exclude_main_user_field": False,
            "enable_likers_in_full_media": False,
            "data": inner_data,
            "stream_use_customized_batch": False,
        }
        if initial_stream_count:
            variables["initial_stream_count"] = initial_stream_count
        return await self.private_graphql_query_request(
            friendly_name="ClipsProfileQuery",
            root_field_name="xdt_user_clips_graphql",
            variables=variables,
            client_doc_id=client_doc_id,
            priority=priority,
        )

    async def private_graphql_inbox_tray_for_user(
        self,
        user_id: str,
        client_doc_id: str = "2035639076042015234490020607",
        priority: str = None,
    ) -> dict:
        """
        Private-side ``InboxTrayRequestForUserQuery`` GraphQL query.

        Returns the per-user direct-inbox tray digest (root field
        ``xdt_get_inbox_tray_items``).

        Parameters
        ----------
        user_id: str
            Target user pk.
        client_doc_id: str, optional
        priority: str, optional
        """
        variables = {
            "user_id": str(user_id),
            "should_fetch_content_note_stack_video_info": False,
        }
        return await self.private_graphql_query_request(
            friendly_name="InboxTrayRequestForUserQuery",
            root_field_name="xdt_get_inbox_tray_items",
            variables=variables,
            client_doc_id=client_doc_id,
            priority=priority,
        )

    async def chaining(self, user_id: str) -> dict:
        """Get suggested users for a target user_id.

        Hits Instagram's private ``discover/chaining/`` endpoint — the
        same surface the official app uses to render the "Suggested
        for you" carousel under a profile. Returns the raw payload so
        the caller can decide what shape it wants (typically passed
        straight into :meth:`fetch_suggestion_details` for the
        expanded form).

        Parameters
        ----------
        user_id: str
            Target user pk.

        Raises
        ------
        InvalidTargetUser
            Instagram refused chaining for this target ("Not eligible
            for chaining."). Common on locked-down / private accounts
            and recently-flagged users.
        """
        params = {
            "module": "profile",
            "target_id": str(user_id),
            "profile_chaining_check": "false",
            "eligible_for_threads_cta": "false",
        }
        try:
            return await self.private_request("discover/chaining/", params=params)
        except UnknownError as e:
            if str(e) == "Not eligible for chaining.":
                raise InvalidTargetUser("Not eligible for chaining.") from e
            raise

    async def fetch_suggestion_details(self, user_id: str, chained_ids: str) -> dict:
        """Fetch expanded details for chained suggestion ids.

        Companion to :meth:`chaining`. Pass a comma-separated list of
        user pks (typically the ``pk`` field of every entry in
        ``chaining()['users']``) and Instagram returns the same users
        with social-context fields filled in (mutual followers,
        verification, friendship state, etc.).

        Parameters
        ----------
        user_id: str
            Target user pk that produced the chained ids.
        chained_ids: str
            Comma-separated list of suggested user pks.
        """
        params = {
            "target_id": str(user_id),
            "chained_ids": chained_ids,
            "include_social_context": "1",
        }
        return await self.private_request(
            "discover/fetch_suggestion_details/",
            params=params,
        )

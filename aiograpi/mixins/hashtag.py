import base64
from typing import List, Tuple

import orjson

from aiograpi.exceptions import (
    ClientError,
    ClientUnauthorizedError,
    HashtagNotFound,
    PreLoginRequired,
    WrongCursorError,
)
from aiograpi.extractors import (
    extract_hashtag_gql,
    extract_hashtag_v1,
    extract_media_v1,
)
from aiograpi.types import Hashtag, Media
from aiograpi.utils import dumps


class HashtagMixin:
    """
    Helpers for managing Hashtag
    """

    async def hashtag_info_a1(self, name: str, max_id: str = None) -> Hashtag:
        """
        Get information about a hashtag by Public Web API

        Parameters
        ----------
        name: str
            Name of the hashtag

        max_id: str
            Max ID, default value is None

        Returns
        -------
        Hashtag
            An object of Hashtag
        """
        params = {"max_id": max_id} if max_id else None
        try:
            data = await self.public_a1_request(f"/explore/tags/{name}/", params=params)
        except ClientUnauthorizedError:
            self.inject_sessionid_to_public()
            data = await self.public_a1_request(f"/explore/tags/{name}/", params=params)
        if not data.get("hashtag"):
            raise HashtagNotFound(name=name, **data)
        return extract_hashtag_gql(data["hashtag"])

    async def hashtag_info_gql(
        self, name: str, amount: int = 12, end_cursor: str = None
    ) -> Hashtag:
        """
        Get information about a hashtag by Public Graphql API

        Parameters
        ----------
        name: str
            Name of the hashtag

        amount: int, optional
            Maximum number of media to return, default is 12

        end_cursor: str, optional
            End Cursor, default value is None

        Returns
        -------
        Hashtag
            An object of Hashtag
        """
        variables = {"tag_name": name, "show_ranked": False, "first": int(amount)}
        if end_cursor:
            variables["after"] = end_cursor
        data = await self.public_graphql_request(
            variables, query_hash="f92f56d47dc7a55b606908374b43a314"
        )
        if not data.get("hashtag"):
            raise HashtagNotFound(name=name, **data)
        return extract_hashtag_gql(data["hashtag"])

    async def hashtag_info_v1(self, name: str) -> Hashtag:
        """
        Get information about a hashtag by Private Mobile API

        Parameters
        ----------
        name: str
            Name of the hashtag

        Returns
        -------
        Hashtag
            An object of Hashtag
        """
        result = await self.private_request(f"tags/{name}/info/")
        return extract_hashtag_v1(result)

    async def hashtag_info(self, name: str) -> Hashtag:
        """
        Get information about a hashtag

        Parameters
        ----------
        name: str
            Name of the hashtag

        Returns
        -------
        Hashtag
            An object of Hashtag
        """
        try:
            hashtag = await self.hashtag_info_a1(name)
        except Exception:
            # Users do not understand the output of such information and create bug reports
            # such this - https://github.com/subzeroid/instagrapi/issues/364
            # if not isinstance(e, ClientError):
            #     self.logger.exception(e)
            hashtag = await self.hashtag_info_v1(name)
        return hashtag

    async def hashtag_related_hashtags(self, name: str) -> List[Hashtag]:
        """
        Get related hashtags from a hashtag

        Parameters
        ----------
        name: str
            Name of the hashtag

        Returns
        -------
        List[Hashtag]
            List of objects of Hashtag
        """
        data = await self.public_a1_request(f"/explore/tags/{name}/")
        if not data.get("hashtag"):
            raise HashtagNotFound(name=name, **data)
        return [
            extract_hashtag_gql(item["node"])
            for item in data["hashtag"]["edge_hashtag_to_related_tags"]["edges"]
        ]

    async def hashtag_medias_a1_chunk(
        self, name: str, max_amount: int = 27, tab_key: str = "", end_cursor: str = None
    ) -> Tuple[List[Media], str]:
        """
        Get chunk of medias and end_cursor by Public Web API

        Parameters
        ----------
        name: str
            Name of the hashtag
        max_amount: int, optional
            Maximum number of media to return, default is 27
        tab_key: str, optional
            Tab Key, default value is ""
        end_cursor: str, optional
            End Cursor, default value is None

        Returns
        -------
        Tuple[List[Media], str]
            List of objects of Media and end_cursor
        """
        assert tab_key in (
            "recent",
            "top",
        ), 'You must specify one of the options for "tab_key" ("recent" or "top")'
        url = f"/explore/tags/{name}/"
        # unique_set = set()
        medias = []
        while True:
            params = {"max_id": end_cursor} if end_cursor else {}
            try:
                data = await self.public_a1_request(url, params=params)
            except ClientUnauthorizedError:
                self.inject_sessionid_to_public()
                data = await self.public_a1_request(url, params=params)

            result = data["data"][tab_key]
            for section in result["sections"]:
                layout_content = section.get("layout_content") or {}
                nodes = layout_content.get("medias") or []
                for node in nodes:
                    if max_amount and len(medias) >= max_amount:
                        break
                    media = extract_media_v1(node["media"])
                    # media_pk = node["media"]["id"]
                    # if media_pk in unique_set:
                    #     continue
                    # unique_set.add(media_pk)
                    # check contains hashtag in caption
                    # if f"#{name}" not in media.caption_text:
                    #     continue
                    medias.append(media)
            if not result["more_available"]:
                break
            if max_amount and len(medias) >= max_amount:
                break
            end_cursor = result["next_max_id"]
        return medias, end_cursor

    async def hashtag_medias_a1(
        self, name: str, amount: int = 27, tab_key: str = ""
    ) -> List[Media]:
        """
        Get medias for a hashtag by Public Web API

        Parameters
        ----------
        name: str
            Name of the hashtag
        amount: int, optional
            Maximum number of media to return, default is 27
        tab_key: str, optional
            Tab Key, default value is ""

        Returns
        -------
        List[Media]
            List of objects of Media
        """
        medias, _ = await self.hashtag_medias_a1_chunk(name, amount, tab_key)
        if amount:
            medias = medias[:amount]
        return medias

    async def hashtag_medias_v1_chunk(
        self, name: str, tab_key: str = "", max_id: str = None
    ) -> Tuple[List[Media], str]:
        """
        Get chunk of medias for a hashtag and max_id (cursor) by Private Mobile API

        Parameters
        ----------
        name: str
            Name of the hashtag
        max_amount: int, optional
            Maximum number of media to return, default is 27
        tab_key: str, optional
            Tab Key, default value is ""
        max_id: str
            Max ID, default value is None

        Returns
        -------
        Tuple[List[Media], str]
            List of objects of Media and max_id
        """
        assert tab_key in (
            "top",
            "recent",
            "clips",
            "top_recent",
        ), 'You must specify one of the options for "tab_key" ("top", "recent", "clips", "top_recent")'
        media_recency_filter = {
            "top": "default",
            "top_recent": "top_recent_posts",
        }
        data = {
            "media_recency_filter": media_recency_filter.get(tab_key, tab_key),
            # "page": 1,
            "_uuid": self.uuid,
            "include_persistent": "false",
            "rank_token": self.rank_token,
        }
        page_id = 0
        if max_id:
            try:
                [max_id, nm_ids, page_id] = orjson.loads(base64.b64decode(max_id))
            except Exception:
                raise WrongCursorError()
            data["max_id"] = max_id
            if page_id:
                data["page"] = page_id
            data["next_media_ids"] = orjson.dumps(nm_ids).decode()
        medias = []
        result = await self.private_request(
            f"tags/{name}/sections/",
            # params={"max_id": max_id} if max_id else {},
            data=data,
            with_signature=False,
        )
        next_max_id = None
        if result.get("next_max_id"):
            next_max_id = result.get("next_max_id")
            next_page_id = page_id + 1
            ids = result.get("next_media_ids")
            items = [next_max_id, ids, next_page_id]
            next_max_id = base64.b64encode(dumps(items).encode()).decode()
        for section in result["sections"]:
            layout_content = section.get("layout_content") or {}
            nodes = layout_content.get("medias") or []
            for node in nodes:
                # if max_amount and len(medias) >= max_amount:
                #     break
                media = extract_media_v1(node["media"])
                # check contains hashtag in caption
                # if f"#{name}" not in media.caption_text:
                #     continue
                medias.append(media)
        # max_id = result["next_max_id"]
        if not result["more_available"]:
            next_max_id = None  # stop
        return medias, next_max_id

    async def hashtag_medias_v1(
        self, name: str, amount: int = 27, tab_key: str = ""
    ) -> List[Media]:
        """
        Get medias for a hashtag by Private Mobile API

        Parameters
        ----------
        name: str
            Name of the hashtag
        amount: int, optional
            Maximum number of media to return, default is 27
        tab_key: str, optional
            Tab Key, default value is ""

        Returns
        -------
        List[Media]
            List of objects of Media
        """
        medias = []
        max_id = None
        while True:
            items, max_id = await self.hashtag_medias_v1_chunk(name, tab_key, max_id)
            medias.extend(items)
            if amount and len(medias) >= amount:
                break
            if not max_id:
                break
        if amount:
            medias = medias[:amount]
        return medias

    async def hashtag_medias_top_a1(self, name: str, amount: int = 9) -> List[Media]:
        """
        Get top medias for a hashtag by Public Web API

        Parameters
        ----------
        name: str
            Name of the hashtag
        amount: int, optional
            Maximum number of media to return, default is 9

        Returns
        -------
        List[Media]
            List of objects of Media
        """
        return await self.hashtag_medias_a1(
            name, amount, tab_key="edge_hashtag_to_top_posts"
        )

    async def hashtag_medias_top_v1(self, name: str, amount: int = 9) -> List[Media]:
        """
        Get top medias for a hashtag by Private Mobile API

        Parameters
        ----------
        name: str
            Name of the hashtag
        amount: int, optional
            Maximum number of media to return, default is 9

        Returns
        -------
        List[Media]
            List of objects of Media
        """
        return await self.hashtag_medias_v1(name, amount, tab_key="top")

    async def hashtag_medias_top(self, name: str, amount: int = 9) -> List[Media]:
        """
        Get top medias for a hashtag

        Parameters
        ----------
        name: str
            Name of the hashtag
        amount: int, optional
            Maximum number of media to return, default is 9

        Returns
        -------
        List[Media]
            List of objects of Media
        """
        try:
            medias = await self.hashtag_medias_top_a1(name, amount)
        except ClientError:
            medias = await self.hashtag_medias_top_v1(name, amount)
        return medias

    async def hashtag_medias_recent_a1(
        self, name: str, amount: int = 71
    ) -> List[Media]:
        """
        Get recent medias for a hashtag by Public Web API

        Parameters
        ----------
        name: str
            Name of the hashtag
        amount: int, optional
            Maximum number of media to return, default is 71

        Returns
        -------
        List[Media]
            List of objects of Media
        """
        return await self.hashtag_medias_a1(
            name, amount, tab_key="edge_hashtag_to_media"
        )

    async def hashtag_medias_recent_v1(
        self, name: str, amount: int = 27
    ) -> List[Media]:
        """
        Get recent medias for a hashtag by Private Mobile API

        Parameters
        ----------
        name: str
            Name of the hashtag
        amount: int, optional
            Maximum number of media to return, default is 71

        Returns
        -------
        List[Media]
            List of objects of Media
        """
        return await self.hashtag_medias_v1(name, amount, tab_key="recent")

    async def hashtag_medias_recent(self, name: str, amount: int = 27) -> List[Media]:
        """
        Get recent medias for a hashtag

        Parameters
        ----------
        name: str
            Name of the hashtag
        amount: int, optional
            Maximum number of media to return, default is 71

        Returns
        -------
        List[Media]
            List of objects of Media
        """
        try:
            medias = await self.hashtag_medias_recent_a1(name, amount)
        except ClientError:
            medias = await self.hashtag_medias_recent_v1(name, amount)
        return medias

    async def hashtag_medias_reels_v1(self, name: str, amount: int = 27) -> List[Media]:
        """
        Get reels medias for a hashtag by Private Mobile API

        Parameters
        ----------
        name: str
            Name of the hashtag
        amount: int, optional
            Maximum number of media to return, default is 71

        Returns
        -------
        List[Media]
            List of objects of Media
        """
        return await self.hashtag_medias_v1(name, amount, tab_key="clips")

    async def hashtag_follow(self, hashtag: str, unfollow: bool = False) -> bool:
        """
        Follow to hashtag
        Parameters
        ----------
        hashtag: str
            Unique identifier of a Hashtag
        unfollow: bool, optional
            Unfollow when True
        Returns
        -------
        bool
            A boolean value
        """
        if not self.user_id:
            raise PreLoginRequired
        name = "unfollow" if unfollow else "follow"
        data = self.with_action_data({"user_id": self.user_id})
        result = await self.private_request(
            f"web/tags/{name}/{hashtag}/", domain="www.instagram.com", data=data
        )
        return result["status"] == "ok"

    async def hashtag_unfollow(self, hashtag: str) -> bool:
        """
        Unfollow to hashtag
        Parameters
        ----------
        hashtag: str
            Unique identifier of a Hashtag
        Returns
        -------
        bool
            A boolean value
        """
        return await self.hashtag_follow(hashtag, unfollow=True)

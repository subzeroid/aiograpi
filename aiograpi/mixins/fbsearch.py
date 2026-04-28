from typing import Dict, List, Optional, Tuple, Union

from aiograpi.extractors import (
    extract_hashtag_v1,
    extract_location,
    extract_track,
    extract_user_short,
)
from aiograpi.types import Hashtag, Location, Track, UserShort


class FbSearchMixin:
    async def fbsearch_places(
        self, query: str, lat: float = 40.74, lng: float = -73.94
    ) -> List[Location]:
        params = {
            "search_surface": "places_search_page",
            "timezone_offset": self.timezone_offset,
            "lat": lat,
            "lng": lng,
            "count": 30,
            "query": query,
        }
        result = await self.private_request("fbsearch/places/", params=params)
        locations = []
        for item in result["items"]:
            locations.append(extract_location(item["location"]))
        return locations

    async def web_search_topsearch(self, query: str) -> dict:
        params = {
            "search_surface": "web_top_search",
            "context": "blended",
            "include_reel": "true",
            "query": query,
        }
        result = await self.private_request("web/search/topsearch/", params=params)
        return result

    async def fbsearch_topsearch_flat(self, query: str) -> List[dict]:
        params = {
            "search_surface": "top_search_page",
            "context": "blended",
            "timezone_offset": self.timezone_offset,
            "count": 30,
            "query": query,
        }
        result = await self.private_request("fbsearch/topsearch_flat/", params=params)
        return result["list"]

    async def search_users(self, query: str) -> List[UserShort]:
        params = {
            "search_surface": "user_search_page",
            "timezone_offset": self.timezone_offset,
            "count": 30,
            "q": query,
        }
        result = await self.private_request("users/search/", params=params)
        return [extract_user_short(item) for item in result["users"]]

    async def search_music(self, query: str) -> List[Track]:
        params = {
            "query": query,
            "browse_session_id": self.generate_uuid(),
        }
        result = await self.private_request("music/audio_global_search/", params=params)
        return [extract_track(item["track"]) for item in result["items"]]

    async def search_hashtags(self, query: str) -> List[Hashtag]:
        params = {
            "search_surface": "hashtag_search_page",
            "timezone_offset": self.timezone_offset,
            "count": 30,
            "q": query,
        }
        result = await self.private_request("tags/search/", params=params)
        return [extract_hashtag_v1(ht) for ht in result["results"]]

    async def fbsearch_suggested_profiles(self, user_id: str) -> List[UserShort]:
        params = {
            "target_user_id": user_id,
            "include_friendship_status": "true",
        }
        result = await self.private_request("fbsearch/accounts_recs/", params=params)
        return result["users"]

    async def web_search_topsearch_hashtags(self, query: str) -> List[Hashtag]:
        result = await self.web_search_topsearch(query)
        hashtags = []
        for item in result.get("hashtags", []):
            hashtags.append(extract_hashtag_v1(item["hashtag"]))
        return hashtags

    async def fbsearch_item(
        self,
        item_id: str,
        search_surface: str,
        query: str,
        timezone_offset: int = 0,
        count: int = 30,
        reels_page_index: int = None,
        has_more_reels: str = None,
        reels_max_id: str = None,
        next_max_id: str = None,
        rank_token: str = None,
        page_index: int = None,
        page_token: str = None,
        paging_token: str = None,
    ) -> dict:
        """
        Generic fbsearch tab endpoint ``GET /fbsearch/{item_id}/``.

        IG hosts every search-results-page tab (top, users, hashtags, reels,
        clips, popular, ...) under a per-tab path. ``item_id`` is the tab
        slug (e.g. ``"top_serp"``, ``"clips_serp_page"``, ``"user_serp"``)
        and ``search_surface`` selects the analytics/ranking surface.

        Parameters
        ----------
        item_id: str
            Tab path segment, e.g. ``"top_serp"`` or ``"clips_serp_page"``.
        search_surface: str
            Surface tag, e.g. ``"top_serp"``, ``"user_serp"``,
            ``"clips_serp_page"``, ``"popular_serp"``.
        query: str
            User-entered search string. Hashtag queries should include the
            leading ``#``.
        timezone_offset: int, default 0
        count: int, default 30
        reels_page_index, has_more_reels, reels_max_id, next_max_id,
        rank_token, page_index, page_token, paging_token:
            Optional pagination cursors returned by previous calls.

        Returns
        -------
        dict
            Parsed JSON response. Shape varies per tab — TODO: consider
            extracting tab-specific pydantic models.
        """
        params = {
            "search_surface": search_surface,
            "query": query,
        }
        if timezone_offset:
            params["timezone_offset"] = timezone_offset
        if count:
            params["count"] = count
        if reels_page_index is not None:
            params["reels_page_index"] = reels_page_index
        if has_more_reels:
            params["has_more_reels"] = has_more_reels
        if reels_max_id:
            params["reels_max_id"] = reels_max_id
        if next_max_id:
            params["next_max_id"] = next_max_id
        if rank_token:
            params["rank_token"] = rank_token
        if page_index is not None:
            params["page_index"] = page_index
        if page_token:
            params["page_token"] = page_token
        if paging_token:
            params["paging_token"] = paging_token
        return await self.private_request(f"fbsearch/{item_id}/", params=params)

    async def fbsearch_keyword_typeahead(
        self,
        query: str,
        timezone_offset: int = 0,
        count: int = 30,
    ) -> dict:
        """
        Typeahead/autocomplete suggestions for a search query.

        ``GET /fbsearch/keyword_typeahead/`` — returns blended suggestions
        (users, hashtags, places, keywords) the typeahead UI shows while
        the user is still typing.

        Parameters
        ----------
        query: str
            Partial query string.
        timezone_offset: int, default 0
        count: int, default 30

        Returns
        -------
        dict
            Parsed JSON response.
        """
        params = {
            "search_surface": "typeahead_search_page",
            "query": query,
            "context": "blended",
        }
        if timezone_offset:
            params["timezone_offset"] = timezone_offset
        if count:
            params["count"] = count
        return await self.private_request("fbsearch/keyword_typeahead/", params=params)

    async def fbsearch_typeahead_stream(
        self,
        query: str,
        timezone_offset: int = 0,
        count: int = 30,
    ) -> dict:
        """
        Streaming variant of ``fbsearch_keyword_typeahead``.

        ``GET /fbsearch/typeahead_stream/`` — returns the same blended
        typeahead payload but as a server-side streamed response. The
        helper transparently aggregates the streamed chunks into a single
        dict (see ``private_request`` ``stream_rows`` fallback).

        Parameters
        ----------
        query: str
            Partial query string.
        timezone_offset: int, default 0
        count: int, default 30

        Returns
        -------
        dict
            Parsed JSON response. May contain ``stream_rows`` for
            chunked envelopes.
        """
        params = {
            "search_surface": "typeahead_search_page",
            "query": query,
            "context": "blended",
        }
        if timezone_offset:
            params["timezone_offset"] = timezone_offset
        if count:
            params["count"] = count
        return await self.private_request("fbsearch/typeahead_stream/", params=params)

    async def fbsearch_recent(
        self,
    ) -> List[Tuple[int, Union[UserShort, Hashtag, Dict]]]:
        """
        Retrieves recently searched results

        Returns
        -------
        List[Tuple[int, Union[UserShort, Hashtag, Dict]]]
            Returns list of Tuples where first value is timestamp of searh, second is retrived result
        """
        result = await self.private_request("fbsearch/recent_searches/")
        assert result.get("status", "") == "ok", "Failed to retrieve recent searches"

        data = []
        for item in result.get("recent", []):
            if "user" in item.keys():
                data.append(
                    (item.get("client_time", None), extract_user_short(item["user"]))
                )
            if "hashtag" in item.keys():
                hashtag = item.get("hashtag")
                hashtag["media_count"] = hashtag.pop("formatted_media_count")
                data.append((item.get("client_time", None), Hashtag(**hashtag)))
            if "keyword" in item.keys():
                data.append((item.get("client_time", None), item["keyword"]))
        return data

    async def fbsearch_accounts_v2(
        self, query: str, page_token: Optional[str] = None
    ) -> dict:
        """
        Search accounts via the v2 SERP endpoint.

        ``GET /fbsearch/account_serp/`` — the surface IG's app uses for
        the "Accounts" tab inside search. Returns the raw payload with
        full ``users`` list plus pagination cursor.

        Parameters
        ----------
        query: str
            Search query.
        page_token: Optional[str], default None
            Pagination cursor from a previous response.

        Returns
        -------
        dict
            Raw account-serp payload (``users``, ``has_more``,
            ``next_page_token``, etc.).
        """
        params = {
            "search_surface": "account_serp",
            "timezone_offset": self.timezone_offset,
            "query": query,
        }
        if page_token:
            params["page_token"] = page_token
        return await self.private_request("fbsearch/account_serp/", params=params)

    async def fbsearch_reels_v2(
        self,
        query: str,
        reels_max_id: Optional[str] = None,
        rank_token: Optional[str] = None,
    ) -> dict:
        """
        Search reels via the v2 SERP endpoint.

        ``GET /fbsearch/reels_serp/`` — the surface IG's app uses for
        the "Reels" tab inside search.

        Parameters
        ----------
        query: str
            Search query.
        reels_max_id: Optional[str], default None
            Pagination cursor for the next page of reels.
        rank_token: Optional[str], default None
            Optional client-side ranking token (forwarded to IG to
            keep ordering stable across paginated calls).

        Returns
        -------
        dict
            Raw reels-serp payload.
        """
        params = {
            "search_surface": "clips_search_page",
            "timezone_offset": self.timezone_offset,
            "query": query,
        }
        if reels_max_id:
            params["reels_max_id"] = reels_max_id
        if rank_token:
            params["rank_token"] = rank_token
        return await self.private_request("fbsearch/reels_serp/", params=params)

    async def fbsearch_topsearch_v2(
        self,
        query: str,
        next_max_id: Optional[str] = None,
        reels_max_id: Optional[str] = None,
        rank_token: Optional[str] = None,
    ) -> dict:
        """
        Search blended (accounts + hashtags + media + reels) via the
        v2 SERP endpoint.

        ``GET /fbsearch/top_serp/`` — the surface IG's app uses for
        the default "Top" tab inside search.

        Parameters
        ----------
        query: str
            Search query.
        next_max_id: Optional[str], default None
            Pagination cursor for the next page of results.
        reels_max_id: Optional[str], default None
            Pagination cursor for the embedded reels carousel.
        rank_token: Optional[str], default None
            Optional client-side ranking token.

        Returns
        -------
        dict
            Raw top-serp payload.
        """
        params = {
            "search_surface": "top_serp",
            "timezone_offset": self.timezone_offset,
            "query": query,
            "rank_token": self.rank_token,
        }
        if next_max_id:
            params["next_max_id"] = next_max_id
        if rank_token:
            params["rank_token"] = rank_token
        if reels_max_id:
            params["reels_max_id"] = reels_max_id
        return await self.private_request("fbsearch/top_serp/", params=params)

    async def fbsearch_typehead(self, query: str) -> List[dict]:
        """
        Typeahead user suggestions via the streaming endpoint.

        ``GET /fbsearch/typeahead_stream/`` — convenience wrapper that
        flattens the ``stream_rows`` envelope into a flat list of
        user dicts (each row contains a list of users; rows are
        concatenated).

        Use :meth:`fbsearch_typeahead_stream` if you need the raw
        envelope (with hashtags/keywords mixed in).

        Parameters
        ----------
        query: str
            Partial query string.

        Returns
        -------
        List[dict]
            Flat list of suggested user dicts.
        """
        params = {
            "search_surface": "typeahead_search_page",
            "timezone_offset": self.timezone_offset,
            "query": query,
            "context": "blended",
        }
        res = await self.private_request("fbsearch/typeahead_stream/", params=params)
        rows = res.get("stream_rows", []) or []
        return [user for row in rows for user in row.get("users", [])]

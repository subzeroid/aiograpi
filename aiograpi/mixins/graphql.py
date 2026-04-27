import asyncio
import json
import logging
import time

import orjson

from aiograpi import httpx_ext
from aiograpi.exceptions import (
    AboutUsError,
    AccountSuspended,
    ChallengeRequired,
    CheckpointRequired,
    ClientBadRequestError,
    ClientConnectionError,
    ClientError,
    ClientForbiddenError,
    ClientJSONDecodeError,
    ClientLoginRequired,
    ClientNotFoundError,
    ClientThrottledError,
    ClientUnauthorizedError,
    ConsentRequired,
    FeedbackRequired,
    LoginRequired,
    PrivateAccount,
    RateLimitError,
    SentryBlock,
    TermsAccept,
    TermsUnblock,
    UserNotFound,
)
from aiograpi.utils import random_delay

GRAPHQL_API_URL = "https://www.instagram.com/api/graphql"
PRIVATE_GRAPHQL_QUERY_URL = "https://i.instagram.com/graphql/query"

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
    "fb_api_req_friendly_name": "PolarisPostCommentsPaginationQuery",
    "server_timestamps": "true",
}


class GraphQLRequestMixin:
    _fb_dtsg = None
    graphql_requests_count = 0
    last_graphql_response = None
    last_graphql_json = {}
    request_logger = logging.getLogger("graphql_request")

    def __init__(self, *args, **kwargs):
        self.graphql = httpx_ext.Session()
        # NB: TLS verification is ON. To disable for a misbehaving
        # MITM proxy, set self.graphql.verify = False AFTER construction.
        self.graphql.headers.update(
            {
                "Connection": "Keep-Alive",
                "Accept": "*/*",
                "Accept-Encoding": "gzip,deflate",
                "Accept-Language": "en-US,en;q=0.9",
                "origin": "https://www.instagram.com",
                "authority": "www.instagram.com",
                "sec-fetch-site": "same-origin",
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/121.0.0.0 Safari/537.36"
                ),
            }
        )
        super().__init__(*args, **kwargs)

    @property
    async def fb_dtsg(self):
        if not self._fb_dtsg:
            self._fb_dtsg = await self.fetch_fb_dtsg()
        return self._fb_dtsg

    async def fetch_fb_dtsg(self):
        self.inject_sessionid_to_public()
        response = await self.graphql.get(GRAPHQL_API_URL)
        if html := response.content.decode():
            s = html.find("__eqmc")
            e = s + 1000
            eqmc = html[s:e]
            s, e = eqmc.find("{"), eqmc.find("</script>")
            eqmc = eqmc[s:e]
            eqmc = orjson.loads(eqmc)
            return eqmc["f"]
        return None

    async def graphql_request(
        self,
        data=None,
        params=None,
        headers=None,
        return_json=True,
        retries_count=1,
        retries_timeout=2,
    ):
        kwargs = dict(
            data=data,
            params=params,
            headers=headers,
            return_json=return_json,
        )
        if retries_count > 10:
            raise Exception("Retries count is too high")
        if retries_timeout > 600:
            raise Exception("Retries timeout is too high")
        self.inject_sessionid_to_public()
        for iteration in range(retries_count):
            try:
                if self.delay_range:
                    await random_delay(delay_range=self.delay_range)
                return await self._send_graphql_request(**kwargs)
            except (
                ClientLoginRequired,
                ClientNotFoundError,
                ClientBadRequestError,
            ) as e:
                raise e  # Stop retries
            except ClientError as e:
                msg = str(e)
                if all(
                    (
                        isinstance(e, ClientConnectionError),
                        "SOCKSHTTPSConnectionPool" in msg,
                        "Max retries exceeded with url" in msg,
                        "Failed to establish a new connection" in msg,
                    )
                ):
                    raise e
                if retries_count > iteration + 1:
                    await asyncio.sleep(retries_timeout)
                else:
                    raise e
                continue

    async def _send_graphql_request(
        self, data=None, params=None, headers=None, return_json=False
    ):
        self.last_graphql_response = None
        self.graphql_requests_count += 1
        if headers:
            self.graphql.headers.update(headers)
        if self.last_response_ts and (time.time() - self.last_response_ts) < 1.0:
            await asyncio.sleep(1.0)
        try:
            if data is not None:
                response = await self.graphql.post(
                    GRAPHQL_API_URL, data=data, params=params
                )
            else:
                response = await self.graphql.get(GRAPHQL_API_URL, params=params)
            self.request_logger.debug(
                "graphql_request %s: %s", response.status_code, response.url
            )
            self.request_logger.info(
                "GraphQL: [%s] [%s] %s %s",
                self.graphql.proxy,
                response.status_code,
                "POST" if data else "GET",
                response.url,
            )
            self.last_graphql_response = response
            response.raise_for_status()
            if return_json:
                self.last_graphql_json = response.json()
                return self.last_graphql_json
            return response.text

        except orjson.JSONDecodeError as e:
            url = str(response.url)
            if "/login/" in url:
                raise ClientLoginRequired(e, response=response)
            elif "/challenge/" in url:
                raise ChallengeRequired(e, response=response)
            elif "/suspended/" in url:
                raise AccountSuspended(e, response=response)
            elif "/terms/unblock" in url:
                raise TermsUnblock(e, response=response)
            elif "/terms/accept" in url:
                raise TermsAccept(e, response=response)
            elif "/about-us" in url:
                raise AboutUsError(e, response=response)

            self.request_logger.error(
                "Status %s: JSONDecodeError in graphql_request (url=%s) >>> %s",
                response.status_code,
                url,
                response.text,
            )
            raise ClientJSONDecodeError(
                "JSONDecodeError {0!s} while opening {1!s}".format(e, url),
                response=response,
            )
        except httpx_ext.HTTPError as e:
            match getattr(self.last_graphql_response, "status_code", None):
                case 401:
                    exc = ClientUnauthorizedError
                case 403:
                    exc = ClientForbiddenError
                case 400:
                    exc = ClientBadRequestError
                case 429:
                    exc = ClientThrottledError
                case 404:
                    exc = ClientNotFoundError
                case _:
                    exc = ClientError
            raise exc(e, response=self.last_graphql_response)
        except (httpx_ext.ConnectError, httpx_ext.ReadError) as e:
            raise ClientConnectionError("{} {}".format(e.__class__.__name__, str(e)))
        finally:
            self.last_response_ts = time.time()

    async def private_graphql_query_request(
        self,
        friendly_name: str,
        root_field_name: str,
        variables: dict = None,
        client_doc_id: str = None,
        priority: str = None,
        extra_headers: dict = None,
    ) -> dict:
        """
        POST a doc_id-based GraphQL query to the private
        ``i.instagram.com/graphql/query`` surface used by the IG mobile app.

        Newer mobile-side GraphQL endpoints (FollowersList, FollowingList,
        ClipsProfileQuery, MemoriesPogQuery, ...) live behind the private
        domain and are addressed by ``X-FB-Friendly-Name`` and a numeric
        ``client_doc_id``. The call uses the authenticated mobile session
        (``self.private``) so all standard private headers/cookies apply.

        Parameters
        ----------
        friendly_name: str
            Value sent as ``X-FB-Friendly-Name`` and
            ``fb_api_req_friendly_name`` (e.g. ``"FollowersList"``).
        root_field_name: str
            Value for ``X-Root-Field-Name`` header (e.g.
            ``"xdt_api__v1__friendships__followers"``).
        variables: dict, optional
            Query variables, JSON-encoded into the ``variables`` form field.
        client_doc_id: str, optional
            Numeric doc id of the registered query. Sent both in the form
            payload and as ``X-Client-Doc-Id`` header when provided.
        priority: str, optional
            Optional ``Priority`` header (e.g. ``"u=3, i"``).
        extra_headers: dict, optional
            Additional headers merged on top of the defaults.

        Returns
        -------
        dict
            The parsed JSON response from Instagram. May contain a top-level
            ``data`` key for canonical responses or a streaming envelope —
            callers should be tolerant of both. Returned as raw ``dict``
            because shapes vary widely between friendly_names — TODO:
            consider extracting per-query pydantic models.
        """
        data = {
            "method": "post",
            "pretty": "false",
            "format": "json",
            "server_timestamps": "true",
            "locale": "user",
            "fb_api_req_friendly_name": friendly_name,
            "enable_canonical_naming": "true",
            "enable_canonical_variable_overrides": "true",
            "enable_canonical_naming_ambiguous_type_prefixing": "true",
            "variables": json.dumps(variables or {}, separators=(",", ":")),
        }
        if client_doc_id:
            data["client_doc_id"] = client_doc_id
        headers = {
            "X-FB-Friendly-Name": friendly_name,
            "X-Root-Field-Name": root_field_name,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }
        if client_doc_id:
            headers["X-Client-Doc-Id"] = str(client_doc_id)
        if priority:
            headers["Priority"] = priority
        if extra_headers:
            headers.update(extra_headers)
        # Merge base headers from private session, then our overrides.
        merged = dict(self.base_headers)
        merged.update(headers)
        if self.authorization:
            merged.setdefault("Authorization", self.authorization)
        # Clear last_json BEFORE the request so callers inspecting it on
        # exception don't see stale data from the previous successful call
        # (private.py:339 does the same).
        self.last_json = {}
        response = await self.private.post(
            PRIVATE_GRAPHQL_QUERY_URL,
            data=data,
            headers=merged,
            timeout=self.read_timeout,
        )
        self.last_response = response
        try:
            response.raise_for_status()
        except httpx_ext.HTTPError as e:
            # First, attempt body-based promotion to the IG-specific
            # exception types — `_send_private_request` does the same
            # because IG returns recoverable account-state failures
            # (login_required, challenge_required, rate_limit_error)
            # as JSON 4xx bodies that the caller's relogin/challenge
            # flow needs to recognize. Only fall back to HTTP-status
            # mapping if the body is missing or doesn't match.
            try:
                body_json = response.json()
                if isinstance(body_json, dict):
                    self.last_json = body_json
                    last_json = body_json
                else:
                    last_json = {}
            except Exception:
                last_json = {}

            message = ""
            error_type = None
            if isinstance(last_json, dict):
                message = (last_json.get("message") or "").lower()
                error_type = last_json.get("error_type")

            # Body promotions (priority over status code).
            if message == "login_required":
                raise LoginRequired(e, response=response, **last_json)
            if message == "challenge_required":
                raise ChallengeRequired(**last_json)
            if message == "checkpoint_required":
                raise CheckpointRequired(**last_json)
            if message == "consent_required":
                raise ConsentRequired(**last_json)
            if message == "feedback_required":
                raise FeedbackRequired(e, response=response, **last_json)
            if error_type == "rate_limit_error":
                raise RateLimitError(e, response=response, **last_json)
            if message == "user_blocked":
                raise SentryBlock(e, response=response, **last_json)
            if "not authorized to view user" in message:
                raise PrivateAccount(e, response=response, **last_json)
            if (
                "unable to fetch followers" in message
                or "error generating user info response" in message
            ):
                raise UserNotFound(e, response=response, **last_json)

            # 404 with body b"Not Found" is a masked challenge on the
            # private mobile surface (mirrors private.py:598). Promote
            # before the generic 404 → ClientNotFoundError fallback.
            if (
                getattr(response, "status_code", None) == 404
                and getattr(response, "content", None) == b"Not Found"
            ):
                raise ChallengeRequired(**last_json)

            # HTTP-status fallback.
            match getattr(response, "status_code", None):
                case 400:
                    exc = ClientBadRequestError
                case 401:
                    exc = ClientUnauthorizedError
                case 403:
                    exc = ClientForbiddenError
                case 404:
                    exc = ClientNotFoundError
                case 429:
                    exc = ClientThrottledError
                case _:
                    exc = ClientError
            raise exc(e, response=response, **last_json)
        try:
            body = response.json()
        except orjson.JSONDecodeError:
            # Streamed line-delimited JSON envelope (similar to
            # _send_private_request fallback for stream endpoints).
            text = response.text.strip()
            rows = [
                orjson.loads(item if item.endswith('"}') else f'{item}"}}')
                for item in text.split('"}\n')
                if item
            ]
            body = {"stream_rows": rows}
        self.last_json = body
        return body

    async def private_graphql_memories_pog(
        self,
        client_doc_id: str = "4160563056814166588457451196",
        direct_region_hint: str = None,
    ) -> dict:
        """
        Private-side ``MemoriesPogQuery`` GraphQL query.

        Returns the "story memories" pog (the round avatar in the home
        feed that surfaces older stories). Root field
        ``xdt_get_story_memories_pog``.

        Parameters
        ----------
        client_doc_id: str, optional
            Defaults to the value observed in the wild — bump when IG
            rotates the registered query.
        direct_region_hint: str, optional
            Optional ``ig-u-ig-direct-region-hint`` header override.
        """
        extra_headers = None
        if direct_region_hint:
            extra_headers = {"ig-u-ig-direct-region-hint": direct_region_hint}
        return await self.private_graphql_query_request(
            friendly_name="MemoriesPogQuery",
            root_field_name="xdt_get_story_memories_pog",
            variables={"request": {"user_id": 0}},
            client_doc_id=client_doc_id,
            extra_headers=extra_headers,
        )

    async def private_graphql_realtime_region_hint(
        self,
        client_doc_id: str = "52232106018313849661757113193",
    ) -> dict:
        """
        Private-side ``IGRealtimeRegionHintQuery`` GraphQL query.

        Returns the realtime/MQTT region hint the IG mobile app uses to
        pick the lowest-latency endpoint for direct messaging. Root field
        ``xdt_igd_msg_region``.

        Parameters
        ----------
        client_doc_id: str, optional
            Defaults to the value observed in the wild.
        """
        return await self.private_graphql_query_request(
            friendly_name="IGRealtimeRegionHintQuery",
            root_field_name="xdt_igd_msg_region",
            variables={},
            client_doc_id=client_doc_id,
            priority="u=3, i",
        )

    async def private_graphql_top_audio_trends_eligible_categories(
        self,
        client_doc_id: str = "10243243298540497152200027985",
    ) -> dict:
        """
        Private-side ``GetTopAudioTrendsEligibleCategories`` GraphQL query.

        Returns the list of audio-trend tabs the user is eligible to see
        on the music/audio surface. Root field
        ``xdt_top_audio_trends_eligible_tabs``.
        """
        return await self.private_graphql_query_request(
            friendly_name="GetTopAudioTrendsEligibleCategories",
            root_field_name="xdt_top_audio_trends_eligible_tabs",
            variables={},
            client_doc_id=client_doc_id,
        )

    async def private_graphql_update_inbox_tray_last_seen(
        self,
        client_doc_id: str = "41048505499858972910914091441",
    ) -> dict:
        """
        Private-side ``UpdateInboxTrayLastSeenTimestamp`` GraphQL mutation.

        Marks the direct-inbox tray as seen at the current timestamp.
        Root field ``__typename``.
        """
        return await self.private_graphql_query_request(
            friendly_name="UpdateInboxTrayLastSeenTimestamp",
            root_field_name="__typename",
            variables={},
            client_doc_id=client_doc_id,
        )

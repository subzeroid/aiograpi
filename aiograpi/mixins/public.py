import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional

import orjson

from aiograpi import httpx_ext
from aiograpi.exceptions import (
    AboutUsError,
    AccountSuspended,
    ChallengeRequired,
    ClientBadRequestError,
    ClientConnectionError,
    ClientError,
    ClientForbiddenError,
    ClientGraphqlError,
    ClientJSONDecodeError,
    ClientLoginRequired,
    ClientNotFoundError,
    ClientThrottledError,
    ClientUnauthorizedError,
    IsRegulatedC18Error,
    TermsAccept,
    TermsUnblock,
)
from aiograpi.utils import random_delay


class PublicRequestMixin:
    public_requests_count = 0
    PUBLIC_API_URL = "https://www.instagram.com/"
    GRAPHQL_PUBLIC_API_URL = "https://www.instagram.com/graphql/query/"
    last_public_response = None
    last_public_json = {}
    public_request_logger = logging.getLogger("public_request")
    public_request_retries_count = 3
    public_request_retries_timeout = 2
    last_response_ts = 0

    def __init__(self, *args, **kwargs):
        self.public = httpx_ext.Session()
        # NB: TLS verification is ON. To disable for a misbehaving
        # MITM proxy, set self.public.verify = False AFTER construction.
        self.public.headers.update(
            {
                "Connection": "Keep-Alive",
                "Accept": "*/*",
                "Accept-Encoding": "gzip,deflate",
                "Accept-Language": "en-US",
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                    "Version/11.1.2 Safari/605.1.15"
                ),
            }
        )
        self.public_request_retries_count = kwargs.pop(
            "public_request_retries_count",
            getattr(
                self,
                "public_request_retries_count",
                self.public_request_retries_count,
            ),
        )
        self.public_request_retries_timeout = kwargs.pop(
            "public_request_retries_timeout",
            getattr(
                self,
                "public_request_retries_timeout",
                self.public_request_retries_timeout,
            ),
        )
        super().__init__(*args, **kwargs)

    async def public_head(self, url: str, follow_redirects: bool = False):
        """
        Issue a ``HEAD`` request through the public session — useful
        for resolving short-link redirects without downloading the
        body (e.g. ``instagram.com/share/...`` link expansion).

        Bypasses :meth:`public_request`'s GET/POST machinery and goes
        straight through ``httpx_ext.request`` so the per-call
        ``follow_redirects`` flag actually takes effect (the Session
        wrapper filters falsy kwargs and would drop
        ``follow_redirects=False``).

        Parameters
        ----------
        url: str
            Absolute URL.
        follow_redirects: bool, default False
            Whether httpx should follow 3xx responses. Default
            ``False`` means callers can read ``response.headers["location"]``
            to inspect the redirect target without actually fetching it.

        Returns
        -------
        httpx.Response
            The raw response. Status code typically 200 / 301 / 302 /
            307 / 308.
        """
        self.public_requests_count += 1
        return await httpx_ext.request(
            "HEAD",
            url,
            proxy=self.public.proxy,
            verify=self.public.verify,
            follow_redirects=follow_redirects,
            headers=self.public.headers,
        )

    async def public_request(
        self,
        url,
        data=None,
        params=None,
        headers=None,
        update_headers=None,
        return_json=False,
        retries_count=None,
        retries_timeout=None,
    ):
        kwargs = dict(
            data=data,
            params=params,
            headers=headers,
            return_json=return_json,
        )
        retries_count = (
            self.public_request_retries_count
            if retries_count is None
            else retries_count
        )
        retries_timeout = (
            self.public_request_retries_timeout
            if retries_timeout is None
            else retries_timeout
        )
        assert retries_count <= 10, "Retries count is too high"
        assert retries_timeout <= 600, "Retries timeout is too high"
        for iteration in range(retries_count):
            try:
                if self.delay_range:
                    await random_delay(delay_range=self.delay_range)
                return await self._send_public_request(
                    url, update_headers=update_headers, **kwargs
                )
            except (
                ClientLoginRequired,
                ClientNotFoundError,
                ClientBadRequestError,
            ) as e:
                raise e  # Stop retries
            # except JSONDecodeError as e:
            #     raise ClientJSONDecodeError(e, respones=self.last_public_response)
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

    async def _send_public_request(
        self,
        url,
        data=None,
        params=None,
        headers=None,
        return_json=False,
        update_headers=None,
    ):
        self.last_public_response = None
        self.public_requests_count += 1
        # Two header modes:
        #   update_headers in (None, True): merge into the session (legacy
        #     behavior — persists across subsequent requests).
        #   update_headers is False: pass per-request only, no mutation.
        per_request_headers = None
        if headers:
            if update_headers in [None, True]:
                self.public.headers.update(headers)
            else:
                per_request_headers = headers
        if self.last_response_ts and (time.time() - self.last_response_ts) < 1.0:
            await asyncio.sleep(1.0)
        try:
            if data is not None:
                response = await self.public.post(
                    url, data=data, params=params, headers=per_request_headers
                )
            else:
                response = await self.public.get(
                    url, params=params, headers=per_request_headers
                )
            self.public_request_logger.debug(
                "public_request %s: %s", response.status_code, response.url
            )
            self.public_request_logger.info(
                "[%s] [%s] %s %s",
                self.public.proxy,
                response.status_code,
                "POST" if data else "GET",
                response.url,
            )
            self.last_public_response = response
            response.raise_for_status()
            if return_json:
                self.last_public_json = response.json()
                return self.last_public_json
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

            self.public_request_logger.error(
                "Status %s: JSONDecodeError in public_request (url=%s) >>> %s",
                response.status_code,
                url,
                response.text,
            )
            raise ClientJSONDecodeError(
                "JSONDecodeError {0!s} while opening {1!s}".format(e, url),
                response=response,
            )
        except httpx_ext.HTTPError as e:
            match getattr(self.last_public_response, "status_code", None):
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
                case 500:
                    if "Oops, an error occurred" in self.last_public_response.text:
                        exc = IsRegulatedC18Error
                case _:
                    exc = ClientError
            raise exc(e, response=self.last_public_response)
        except (httpx_ext.ConnectError, httpx_ext.ReadError) as e:
            raise ClientConnectionError("{} {}".format(e.__class__.__name__, str(e)))
        finally:
            self.last_response_ts = time.time()

    async def public_a1_request(
        self, endpoint, data=None, params=None, headers=None, full=False
    ):
        url = self.PUBLIC_API_URL + endpoint.lstrip("/")
        params = params or {}
        params |= {"__a": 1, "__d": "dis"}
        response = await self.public_request(
            url, data=data, params=params, headers=headers, return_json=True
        )
        if full:
            return response
        return response.get("graphql") or response

    async def public_a1_request_user_info_by_username(
        self, username, data=None, params=None
    ):
        params = params or {}
        url = (
            self.PUBLIC_API_URL + f"api/v1/users/web_profile_info/?username={username}"
        )
        headers = {"x-ig-app-id": "936619743392459"}
        response = await self.public_request(
            url, data=data, params=params, headers=headers, return_json=True
        )
        return response.get("user") or response

    async def public_graphql_request(
        self,
        variables,
        query_hash=None,
        query_id=None,
        data=None,
        params=None,
        headers=None,
    ):
        assert query_id or query_hash, "Must provide valid one of: query_id, query_hash"
        default_params = {"variables": json.dumps(variables, separators=(",", ":"))}
        if query_id:
            default_params["query_id"] = query_id
        if query_hash:
            default_params["query_hash"] = query_hash
        if params:
            params.update(default_params)
        else:
            params = default_params

        try:
            body_json = await self.public_request(
                self.GRAPHQL_PUBLIC_API_URL,
                data=data,
                params=params,
                headers=headers,
                return_json=True,
            )

            if body_json.get("status", None) != "ok":
                raise ClientGraphqlError(
                    "Unexpected status '{}' in response. Message: '{}'".format(
                        body_json.get("status", None), body_json.get("message", None)
                    ),
                    response=body_json,
                )

            if "data" not in body_json:
                errors = body_json.get("errors") or []
                summary = errors[0].get("summary") if errors else None
                description = errors[0].get("description") if errors else None
                raise ClientGraphqlError(
                    "Missing 'data' in GraphQL response. Summary: '{}'. Description: '{}'".format(
                        summary, description
                    )
                )

            return body_json["data"]

        except ClientBadRequestError as e:
            message = None
            try:
                body_json = e.response.json()
                message = body_json.get("message", None)
            except orjson.JSONDecodeError:
                pass
            raise ClientGraphqlError(
                "Error: '{}'. Message: '{}'".format(e, message), response=e.response
            )

    async def public_doc_id_graphql_request(
        self,
        doc_id: str,
        variables: Dict[str, Any],
        referer: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        POST a doc_id-based GraphQL query to www.instagram.com/graphql/query/.

        Newer IG GraphQL endpoints (e.g. PolarisProfilePageContentQuery) are
        addressed by ``doc_id`` rather than the legacy ``query_hash`` /
        ``query_id`` scheme. Returns the parsed ``data`` payload.

        Parameters
        ----------
        doc_id: str
            doc_id of the registered query (e.g. "25980296051578533").
        variables: dict
            Query variables — will be JSON-encoded compactly into the
            ``variables`` form field.
        referer: str, optional
            Value for the ``Referer`` request header.
        headers: dict, optional
            Extra request headers merged on top of the public session's.
        """
        data = {
            "variables": json.dumps(variables, separators=(",", ":")),
            "doc_id": doc_id,
            "server_timestamps": "true",
        }
        # IG rejects bare /graphql/query/ POSTs — needs the iPhone web-app
        # signalling headers it sees from m.instagram.com (instaloader does
        # the same: see _default_http_header(empty_session_only=True)).
        merged_headers = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "en-US,en;q=0.8",
            "Referer": referer or "https://www.instagram.com/",
            "User-Agent": (
                "Instagram 273.0.0.16.70 (iPhone15,2; iOS 17_5_1; en_US; en-US; "
                "scale=3.00; 1290x2796; 470085518)"
            ),
        }
        if headers:
            merged_headers.update(headers)
        body_json = await self.public_request(
            self.GRAPHQL_PUBLIC_API_URL,
            data=data,
            headers=merged_headers,
            update_headers=False,
            return_json=True,
        )
        if "data" not in body_json:
            errors = body_json.get("errors") or []
            summary = errors[0].get("summary") if errors else None
            description = errors[0].get("description") if errors else None
            raise ClientGraphqlError(
                "Missing 'data' in doc_id GraphQL response (doc_id={}). "
                "Summary: '{}'. Description: '{}'".format(doc_id, summary, description),
                response=body_json,
            )
        return body_json["data"]


class TopSearchesPublicMixin:
    async def top_search(self, query):
        """Anonymous IG search request"""
        url = "https://www.instagram.com/web/search/topsearch/"
        params = {
            "context": "blended",
            "query": query,
            "rank_token": 0.7763938004511706,
            "include_reel": "true",
        }
        return await self.public_request(url, params=params, return_json=True)


class ProfilePublicMixin:
    async def location_feed(self, location_id, count=16, end_cursor=None):
        if count > 50:
            raise ValueError("Count cannot be greater than 50")
        variables = {
            "id": location_id,
            "first": int(count),
        }
        if end_cursor:
            variables["after"] = end_cursor
        data = await self.public_graphql_request(
            variables, query_hash="1b84447a4d8b6d6d0426fefb34514485"
        )
        return data["location"]

    async def profile_related_info(self, profile_id):
        variables = {
            "user_id": profile_id,
            "include_chaining": True,
            "include_reel": True,
            "include_suggested_users": True,
            "include_logged_out_extras": True,
            "include_highlight_reels": True,
            "include_related_profiles": True,
        }
        data = await self.public_graphql_request(
            variables, query_hash="e74d51c10ecc0fe6250a295b9bb9db74"
        )
        return data["user"]

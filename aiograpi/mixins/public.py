import asyncio
import json
import logging
import time

import orjson

from aiograpi import reqwests
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
    request_logger = logging.getLogger("public_request")
    last_response_ts = 0
    # Need some timeout for avoid sockets and memory leaks.
    # Remember - igerl timeout 45sec
    max_read_timeout = 46

    def __init__(self, *args, **kwargs):
        self.public = reqwests.Session()
        self.public.verify = False  # fix SSLError/HTTPSConnectionPool
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
        super().__init__(*args, **kwargs)

    async def public_request(
        self,
        url,
        data=None,
        params=None,
        headers=None,
        return_json=False,
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
        for iteration in range(retries_count):
            try:
                if self.delay_range:
                    await random_delay(delay_range=self.delay_range)
                return await self._send_public_request(url, **kwargs)
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
        self, url, data=None, params=None, headers=None, return_json=False
    ):
        self.last_public_response = None
        self.public_requests_count += 1
        if headers:
            self.public.headers.update(headers)
        if self.last_response_ts and (time.time() - self.last_response_ts) < 1.0:
            await asyncio.sleep(1.0)
        try:
            if data is not None:
                response = await self.public.post(url, data=data, params=params)
            else:
                response = await self.public.get(url, params=params)
            self.request_logger.debug(
                "public_request %s: %s", response.status_code, response.url
            )
            self.request_logger.info(
                "[%s] [%s] %s %s",
                self.public.proxies.get("https"),
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

            self.request_logger.error(
                "Status %s: JSONDecodeError in public_request (url=%s) >>> %s",
                response.status_code,
                url,
                response.text,
            )
            raise ClientJSONDecodeError(
                "JSONDecodeError {0!s} while opening {1!s}".format(e, url),
                response=response,
            )
        except reqwests.HTTPError as e:
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
                case _:
                    exc = ClientError
            raise exc(e, response=self.last_public_response)
        except (reqwests.ConnectError, reqwests.ReadError) as e:
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

    async def public_graphql_request(
        self,
        variables,
        query_hash=None,
        query_id=None,
        data=None,
        params=None,
        headers=None,
    ):
        if not (query_id or query_hash):
            raise Exception("Must provide valid one of: query_id, query_hash")
        default_params = {"variables": json.dumps(variables, separators=(",", ":"))}
        if query_id:
            # 17851374694183129
            default_params["query_id"] = query_id
        if query_hash:
            # 7dd9a7e2160524fd85f50317462cff9f
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

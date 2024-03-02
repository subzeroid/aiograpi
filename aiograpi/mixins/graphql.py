import asyncio
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
    ClientJSONDecodeError,
    ClientLoginRequired,
    ClientNotFoundError,
    ClientThrottledError,
    ClientUnauthorizedError,
    TermsAccept,
    TermsUnblock,
)
from aiograpi.utils import random_delay

GRAPHQL_API_URL = "https://www.instagram.com/api/graphql"

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
        self.graphql = reqwests.Session()
        self.graphql.verify = False  # fix SSLError/HTTPSConnectionPool
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
                self.graphql.proxies.get("https"),
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
        except reqwests.HTTPError as e:
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
        except (reqwests.ConnectError, reqwests.ReadError) as e:
            raise ClientConnectionError("{} {}".format(e.__class__.__name__, str(e)))
        finally:
            self.last_response_ts = time.time()

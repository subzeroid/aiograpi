import asyncio
import json
import logging
import random
import time

import orjson

from aiograpi import config, reqwests
from aiograpi.exceptions import (
    AuthRequiredProxyError,
    BadPassword,
    ChallengeRequired,
    CheckpointRequired,
    ClientBadRequestError,
    ClientConnectionError,
    ClientErrorWithTitle,
    ClientForbiddenError,
    ClientJSONDecodeError,
    ClientNotFoundError,
    ClientRequestTimeout,
    ClientStatusFail,
    ClientThrottledError,
    ClientUnknownError,
    CommentsDisabled,
    ConnectProxyError,
    ConsentRequired,
    FeedbackRequired,
    GeoBlockRequired,
    HashtagPageWarning,
    InvalidMediaId,
    InvalidTargetUser,
    LoginRequired,
    MediaUnavailable,
    PleaseWaitFewMinutes,
    PrivateAccount,
    ProxyAddressIsBlocked,
    RateLimitError,
    SentryBlock,
    TwoFactorRequired,
    UnknownError,
    UserNotFound,
    VideoTooLongException,
)
from aiograpi.utils import dumps, generate_signature, random_delay


async def manual_input_code(self, username: str, choice=None):
    """
    Manual security code helper

    Parameters
    ----------
    username: str
        User name of a Instagram account
    choice: optional
        Whether sms or email

    Returns
    -------
    str
        Code
    """
    code = None
    while True:
        code = input(f"Enter code (6 digits) for {username} ({choice}): ").strip()
        if code and code.isdigit():
            break
    return code  # is not int, because it can start from 0


async def manual_change_password(self, username: str):
    pwd = None
    while not pwd:
        pwd = input(f"Enter password for {username}: ").strip()
    return pwd


class PrivateRequestMixin:
    """
    Helpers for private request
    """

    private_requests_count = 0
    handle_exception = None
    challenge_code_handler = manual_input_code
    change_password_handler = manual_change_password
    request_logger = logging.getLogger("private_request")
    last_response_ts = 0
    read_timeout = 25
    request_timeout = 1
    domain = config.API_DOMAIN
    last_response = None
    last_json = {}

    def __init__(self, *args, **kwargs):
        self.private = reqwests.Session()
        self.private.verify = False  # fix SSLError/HTTPSConnectionPool
        self.email = kwargs.pop("email", None)
        self.phone_number = kwargs.pop("phone_number", None)
        self.request_timeout = kwargs.pop("request_timeout", self.request_timeout)
        super().__init__(*args, **kwargs)

    async def small_delay(self):
        """
        Small Delay

        Returns
        -------
        Void
        """
        await asyncio.sleep(random.uniform(0.75, 3.75))

    async def very_small_delay(self):
        """
        Very small delay

        Returns
        -------
        Void
        """
        await asyncio.sleep(random.uniform(0.175, 0.875))

    @property
    def base_headers(self):
        locale = self.locale.replace("-", "_")
        accept_language = ["en-US"]
        if locale:
            lang = locale.replace("_", "-")
            if lang not in accept_language:
                accept_language.insert(0, lang)
        headers = {
            "X-IG-App-Locale": locale,
            "X-IG-Device-Locale": locale,
            "X-IG-Mapped-Locale": locale,
            "X-Pigeon-Session-Id": self.generate_uuid("UFS-", "-1"),
            "X-Pigeon-Rawclienttime": str(round(time.time(), 3)),
            # "X-IG-Connection-Speed": "-1kbps",
            "X-IG-Bandwidth-Speed-KBPS": str(
                random.randint(2500000, 3000000) / 1000
            ),  # "-1.000"
            "X-IG-Bandwidth-TotalBytes-B": str(
                random.randint(5000000, 90000000)
            ),  # "0"
            "X-IG-Bandwidth-TotalTime-MS": str(random.randint(2000, 9000)),  # "0"
            # "X-IG-EU-DC-ENABLED": "true", # <- type of DC? Eu is euro, but we use US
            # "X-IG-Prefetch-Request": "foreground",  # OLD from instabot
            "X-IG-App-Startup-Country": self.country.upper(),
            "X-Bloks-Version-Id": self.bloks_versioning_id,
            "X-IG-WWW-Claim": "0",
            # X-IG-WWW-Claim: hmac.AR3zruvyGTlwHvVd2ACpGCWLluOppXX4NAVDV-iYslo9CaDd
            "X-Bloks-Is-Layout-RTL": "false",
            "X-Bloks-Is-Panorama-Enabled": "true",
            "X-IG-Device-ID": self.uuid,
            "X-IG-Family-Device-ID": self.phone_id,
            "X-IG-Android-ID": self.android_device_id,
            "X-IG-Timezone-Offset": str(self.timezone_offset),
            "X-IG-Connection-Type": "WIFI",
            "X-IG-Capabilities": "3brTvx0=",  # "3brTvwE=" in instabot
            "X-IG-App-ID": self.app_id,
            "Priority": "u=3",
            "User-Agent": self.user_agent,
            "Accept-Language": ", ".join(accept_language),
            "X-MID": self.mid,  # e.g. X--ijgABABFjLLQ1NTEe0A6JSN7o
            "Accept-Encoding": "zstd, gzip, deflate",
            "Host": self.domain or config.API_DOMAIN,
            "X-FB-HTTP-Engine": "Liger",
            "Connection": "keep-alive",
            # "Pragma": "no-cache",
            # "Cache-Control": "no-cache",
            "X-FB-Client-IP": "True",
            "X-FB-Server-Cluster": "True",
            "IG-INTENDED-USER-ID": str(self.user_id or 0),
            "X-IG-Nav-Chain": (
                "9MV:self_profile:2,ProfileMediaTabFragment:"
                "self_profile:3,9Xf:self_following:4"
            ),
            "X-IG-SALT-IDS": str(random.randint(1061162222, 1061262222)),
        }
        if self.user_id:
            next_year = time.time() + 31536000  # + 1 year in seconds
            headers.update(
                {
                    "IG-U-DS-USER-ID": str(self.user_id),
                    # Direct:
                    "IG-U-IG-DIRECT-REGION-HINT": (
                        f"LLA,{self.user_id},{next_year}:"
                        "01f7bae7d8b131877d8e0ae1493252280d72"
                        "f6d0d554447cb1dc9049b6b2c507c08605b7"
                    ),
                    "IG-U-SHBID": (
                        f"12695,{self.user_id},{next_year}:"
                        "01f778d9c9f7546cf3722578fbf9b85143cd"
                        "6e5132723e5c93f40f55ca0459c8ef8a0d9f"
                    ),
                    "IG-U-SHBTS": (
                        f"{int(time.time())},{self.user_id},{next_year}:"
                        "01f7ace11925d0388080078d0282b75b8059"
                        "844855da27e23c90a362270fddfb3fae7e28"
                    ),
                    "IG-U-RUR": (
                        f"RVA,{self.user_id},{next_year}:"
                        "01f7f627f9ae4ce2874b2e04463efdb18434"
                        "0968b1b006fa88cb4cc69a942a04201e544c"
                    ),
                }
            )
        if self.ig_u_rur:
            headers.update({"IG-U-RUR": '"%s"' % self.ig_u_rur})
        if self.ig_www_claim:
            headers.update({"X-IG-WWW-Claim": self.ig_www_claim})
        return headers

    def set_country(self, country: str = "US"):
        """Set you country code (ISO 3166-1/3166-2)

        Parameters
        ----------
        country: str
            Your country code (ISO 3166-1/3166-2) string identifier (e.g. US, UK, RU)
            Advise to specify the country code of your proxy

        Returns
        -------
        bool
            A boolean value
        """
        self.settings["country"] = self.country = str(country)
        return True

    def set_country_code(self, country_code: int = 1):
        """Set country calling code

        Parameters
        ----------
        country_code: int

        Returns
        -------
        bool
            A boolean value
        """
        self.settings["country_code"] = self.country_code = int(country_code)
        return True

    def set_locale(self, locale: str = "en_US"):
        """Set you locale (ISO 3166-1/3166-2)

        Parameters
        ----------
        locale: str
            Your locale code (ISO 3166-1/3166-2) string identifier (e.g. US, UK, RU)
            Advise to specify the locale code of your proxy

        Returns
        -------
        bool
            A boolean value
        """
        user_agent = (self.settings.get("user_agent") or "").replace(
            self.locale, locale
        )
        self.settings["locale"] = self.locale = str(locale)
        self.set_user_agent(user_agent)  # update locale in user_agent
        if "_" in locale:
            self.set_country(locale.rsplit("_", 1)[1])
        return True

    def set_timezone_offset(self, seconds: int = 0):
        """Set you timezone offset in seconds

        Parameters
        ----------
        seconds: int
            Specify the offset in seconds from UTC

        Returns
        -------
        bool
            A boolean value
        """
        self.settings["timezone_offset"] = self.timezone_offset = int(seconds)
        return True

    def set_ig_u_rur(self, value):
        self.settings["ig_u_rur"] = self.ig_u_rur = value
        return True

    def set_ig_www_claim(self, value):
        self.settings["ig_www_claim"] = self.ig_www_claim = value
        return True

    @staticmethod
    def with_query_params(data, params):
        return dict(data, **{"query_params": json.dumps(params, separators=(",", ":"))})

    async def _send_private_request(
        self,
        endpoint,
        data=None,
        params=None,
        login=False,
        with_signature=True,
        headers=None,
        extra_sig=None,
        domain: str = None,
    ):
        self.last_response = None
        self.last_json = last_json = {}  # for Sentry context in traceback
        self.private.headers.update(self.base_headers)
        if headers:
            self.private.headers.update(headers)
        if self.last_response_ts and (time.time() - self.last_response_ts) < 1.0:
            await self.small_delay()
        if not login:
            await asyncio.sleep(self.request_timeout)
        # if self.user_id and login:
        #     raise Exception(f"User already logged ({self.user_id})")
        try:
            if not endpoint.startswith("/"):
                endpoint = f"/v1/{endpoint}"

            if endpoint == "/challenge/":  # wow so hard, is it safe tho?
                endpoint = "/v1/challenge/"

            api_url = f"https://{self.domain or config.API_DOMAIN}/api{endpoint}"
            self.logger.info(api_url)
            if data:  # POST
                # Client.direct_answer raw dict
                # data = json.dumps(data)
                self.private.headers[
                    "Content-Type"
                ] = "application/x-www-form-urlencoded; charset=UTF-8"
                if with_signature:
                    # Client.direct_answer doesn't need a signature
                    data = generate_signature(dumps(data))
                    if extra_sig:
                        data += "&".join(extra_sig)
                response = await self.private.post(
                    api_url,
                    data=data,
                    params=params,
                    timeout=self.read_timeout,
                )
            else:  # GET
                self.private.headers.pop("Content-Type", None)
                response = await self.private.get(
                    api_url,
                    params=params,
                    timeout=self.read_timeout,
                )
            response_text = response.text.strip()
            # if "zstd" in (response.headers.get("Content-Encoding") or ""):
            #     dctx = zstandard.ZstdDecompressor()
            #     response_text = dctx.decompress(response.content)
            self.logger.debug(
                "private_request %s: %s (%s)",
                response.status_code,
                response.url,
                response_text,
            )
            mid = response.headers.get("ig-set-x-mid")
            if mid:
                self.mid = mid
            self.request_log(response)
            self.last_response = response
            # hack for re-request without paging cursor if cursor is broken
            if (
                response.status_code == 500
                and params
                and (params.get("min_id") or params.get("max_id"))
            ):
                params.pop("min_id", None)
                params.pop("max_id", None)
                self.logger.warning(
                    "Resend request without cursor %r (%r)", endpoint, params
                )
                return await self._send_private_request(
                    endpoint,
                    data=data,
                    params=params,
                    login=login,
                    with_signature=False,
                )

            response.raise_for_status()
            # last_json - for Sentry context in traceback
            try:
                self.last_json = last_json = response.json()
            except orjson.JSONDecodeError:
                rows = [
                    orjson.loads(item if item.endswith('"}') else f'{item}"}}')
                    for item in response_text.split('"}\n')
                ]
                self.last_json = last_json = {"stream_rows": rows}
            self.logger.debug("last_json %s", last_json)
            warning_message = last_json.get("warning_message") or {}
            category_name = warning_message.get("category_name")
            null_state = last_json.get("null_state") or {}
            if category_name == "HASHTAG_PAGE_WARNING_MESSAGE":
                details = [
                    null_state.get("title"),
                    warning_message.get("body_text") or null_state.get("text"),
                ]
                raise HashtagPageWarning(
                    ": ".join(d for d in details if d), response=response, **last_json
                )
            elif last_json.get("comments_disabled"):
                raise CommentsDisabled(**last_json)
        except orjson.JSONDecodeError as e:
            self.logger.error(
                (
                    "Status %r: JSONDecodeError in private_request "
                    "(user_id=%s, endpoint=%s) >>> %r"
                ),
                response.headers,
                self.user_id,
                endpoint,
                response_text,
            )
            self.logger.error(e)
            raise ClientJSONDecodeError(
                "JSONDecodeError {0!s} while opening {1!s}".format(e, response.url),
                response=response,
            )
        except (reqwests.ConnectError, reqwests.ConnectTimeout) as e:
            self.logger.error(
                (
                    "ConnectProxyError(pay attention, in 1/100 it could be ig error) "
                    "in private_request (user_id=%s, endpoint=%s)"
                ),
                self.user_id,
                endpoint,
            )
            raise ConnectProxyError(e, response=self.last_response)
        except reqwests.ProxyError as e:
            self.logger.error(
                "AuthRequiredProxyError in private_request (user_id=%s, endpoint=%s)",
                self.user_id,
                endpoint,
            )
            raise AuthRequiredProxyError(e, response=self.last_response)
        except (reqwests.HTTPStatusError, reqwests.HTTPError) as e:
            response = self.last_response
            try:
                self.last_json = last_json = response.json()
            except (orjson.JSONDecodeError, AttributeError):
                self.logger.warning(
                    "ClientUnknownError1. response text: %r (%r)",
                    response and response.text,
                    e,
                )
                if not response:
                    raise ClientUnknownError(e, response=response)
                self.last_json = last_json = {}
            message = last_json.get("message", "")
            if "Please wait a few minutes" in message:
                raise PleaseWaitFewMinutes(e, response=response, **last_json)
            if response.status_code == 403:
                if message == "login_required":
                    raise LoginRequired(response=response, **last_json)
                if response and len(response.text) < 512:
                    last_json["message"] = response.text
                raise ClientForbiddenError(e, response=response, **last_json)
            elif response.status_code == 400:
                error_type = last_json.get("error_type")
                if message == "challenge_required":
                    raise ChallengeRequired(**last_json)
                elif message == "feedback_required":
                    raise FeedbackRequired(
                        **dict(
                            last_json,
                            message="%s: %s"
                            % (message, last_json.get("feedback_message")),
                        )
                    )
                elif message == "consent_required":
                    raise ConsentRequired(**last_json)
                elif message == "geoblock_required":
                    raise GeoBlockRequired(**last_json)
                elif message == "checkpoint_required":
                    raise CheckpointRequired(**last_json)
                elif error_type == "sentry_block":
                    raise SentryBlock(**last_json)
                elif error_type == "rate_limit_error":
                    raise RateLimitError(**last_json)
                elif error_type == "bad_password":
                    raise BadPassword(**last_json)
                elif error_type == "two_factor_required":
                    if not last_json.get("message"):
                        last_json["message"] = "Two-factor authentication required"
                    raise TwoFactorRequired(**last_json)
                elif "Please wait a few minutes before you try again" in message:
                    raise PleaseWaitFewMinutes(e, response=response, **last_json)
                elif "VideoTooLongException" in message:
                    raise VideoTooLongException(e, response=response, **last_json)
                elif "Not authorized to view user" in message:
                    raise PrivateAccount(e, response=response, **last_json)
                elif "Invalid target user" in message:
                    raise InvalidTargetUser(e, response=response, **last_json)
                elif "Invalid media_id" in message:
                    raise InvalidMediaId(e, response=response, **last_json)
                elif (
                    "Media is unavailable" in message
                    or "Media not found or unavailable" in message
                ):
                    raise MediaUnavailable(e, response=response, **last_json)
                elif "has been deleted" in message:
                    # Sorry, this photo has been deleted.
                    raise MediaUnavailable(e, response=response, **last_json)
                elif (
                    "unable to fetch followers" in message
                    or "Error generating user info response" in message
                ):
                    # returned when user not found
                    raise UserNotFound(e, response=response, **last_json)
                elif "The username you entered" in message:
                    # The username you entered doesn't appear to belong to an account.
                    # Please check your username and try again.
                    last_json["message"] = (
                        "Instagram has blocked your IP address, "
                        "use a quality proxy provider (not free, not shared)"
                    )
                    raise ProxyAddressIsBlocked(**last_json)
                elif error_type or message:
                    self.logger.warning("UnkNownError %r (%r)", last_json, response)
                    raise UnknownError(**last_json)
                # TODO: Handle last_json with
                #   {'message': 'counter get error', 'status': 'fail'}
                self.logger.exception(e)
                self.logger.warning(
                    "Status 400: %s",
                    message or "Empty response message. Maybe enabled Two-factor auth?",
                )
                raise ClientBadRequestError(e, response=response, **last_json)
            elif response.status_code == 429:
                self.logger.warning("Status 429: Too many requests")
                if "Please wait a few minutes before you try again" in message:
                    raise PleaseWaitFewMinutes(e, response=response, **last_json)
                raise ClientThrottledError(e, response=response, **last_json)
            elif response.status_code == 404:
                self.logger.warning("Status 404: Endpoint %s does not exists", endpoint)
                raise ClientNotFoundError(e, response=response, **last_json)
            elif response.status_code == 408:
                self.logger.warning("Status 408: Request Timeout")
                raise ClientRequestTimeout(e, response=response, **last_json)
            self.logger.warning("ClientUnknownError2. response json: %r", last_json)
            raise ClientUnknownError(e, response=response, **last_json)
        except (reqwests.ConnectError, reqwests.ReadError) as e:
            raise ClientConnectionError("{e.__class__.__name__} {e}".format(e=e))
        finally:
            self.last_response_ts = time.time()
        if last_json.get("status") == "fail":
            raise ClientStatusFail(response=response, **last_json)
        elif "error_title" in last_json:
            """Example: {
            'error_title': 'bad image input extra:{}', <-------------
            'media': {
                'device_timestamp': '1588184737203',
                'upload_id': '1588184737203'
            },
            'message': 'media_needs_reupload', <-------------
            'status': 'ok' <-------------
            }"""
            raise ClientErrorWithTitle(response=response, **last_json)
        return last_json

    def request_log(self, response):
        self.request_logger.info(
            "%s [%s] %s %s (%s)",
            self.username,
            response.status_code,
            response.request.method,
            response.url,
            "{app_version}, {manufacturer} {model}".format(
                app_version=self.device_settings.get("app_version"),
                manufacturer=self.device_settings.get("manufacturer"),
                model=self.device_settings.get("model"),
            ),
        )

    async def private_request(
        self,
        endpoint,
        data=None,
        params=None,
        login=False,
        with_signature=True,
        headers=None,
        extra_sig=None,
        domain: str = None,
    ):
        if self.authorization:
            if not headers:
                headers = {}
            if "authorization" not in headers:
                headers.update({"Authorization": self.authorization})
        kwargs = dict(
            data=data,
            params=params,
            login=login,
            with_signature=with_signature,
            headers=headers,
            extra_sig=extra_sig,
            domain=domain,
        )
        try:
            if self.delay_range:
                await random_delay(delay_range=self.delay_range)
            self.private_requests_count += 1
            await self._send_private_request(endpoint, **kwargs)
        except Exception as e:
            if self.handle_exception:
                self.handle_exception(self, e)
            elif isinstance(e, ChallengeRequired):
                if self.with_challenge_flow:
                    await self.challenge_resolve(self.last_json)
            else:
                raise e
            if login and self.user_id:
                # After challenge resolve return last_json
                return self.last_json
            return await self._send_private_request(endpoint, **kwargs)
        return self.last_json

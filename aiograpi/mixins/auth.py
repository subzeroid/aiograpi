import base64

# import datetime
import hashlib
import hmac
import json
import random
import re
import time
import uuid
from pathlib import Path
from typing import Dict, List
from uuid import uuid4

from pydantic import ValidationError

from aiograpi import config
from aiograpi.exceptions import (
    BadCredentials,
    ClientThrottledError,
    PleaseWaitFewMinutes,
    PrivateError,
    ReloginAttemptExceeded,
    TwoFactorRequired,
)
from aiograpi.utils import dumps, gen_token, generate_jazoest

# from aiograpi.zones import CET


class PreLoginFlowMixin:
    """
    Helpers for pre login flow
    """

    async def pre_login_flow(self) -> bool:
        """
        Emulation mobile app behavior before login

        Returns
        -------
        bool
            A boolean value
        """
        # self.set_contact_point_prefill("prefill")
        # self.get_prefill_candidates(True)
        # self.set_contact_point_prefill("prefill")
        await self.sync_launcher(True)
        # self.sync_device_features(True)
        return True

    async def get_prefill_candidates(self, login: bool = False) -> Dict:
        """
        Get prefill candidates value from Instagram

        Parameters
        ----------
        login: bool, optional
            Whether to login or not

        Returns
        -------
        bool
            A boolean value
        """
        data = {
            "android_device_id": self.android_device_id,
            "client_contact_points": (
                '[{"type":"omnistring","value":"%s","source":"last_login_attempt"}]'
            )
            % self.username,
            "phone_id": self.phone_id,
            "usages": '["account_recovery_omnibox"]',
            "logged_in_user_ids": "[]",  # "[\"123456789\",\"987654321\"]",
            "device_id": self.uuid,
        }
        # if login is False:
        data["_csrftoken"] = self.token
        return await self.private_request(
            "accounts/get_prefill_candidates/", data, login=login
        )

    async def sync_device_features(self, login: bool = False) -> Dict:
        """
        Sync device features to your Instagram account

        Parameters
        ----------
        login: bool, optional
            Whether to login or not

        Returns
        -------
        Dict
            A dictionary of response from the call
        """
        data = {
            "id": self.uuid,
            "server_config_retrieval": "1",
            # "experiments": config.LOGIN_EXPERIMENTS,
        }
        if login is False:
            data["_uuid"] = self.uuid
            data["_uid"] = self.user_id
            data["_csrftoken"] = self.token
        # headers={"X-DEVICE-ID": self.uuid}
        return await self.private_request("qe/sync/", data, login=login)

    async def sync_launcher(self, login: bool = False) -> Dict:
        """
        Sync Launcher

        Parameters
        ----------
        login: bool, optional
            Whether to login or not

        Returns
        -------
        Dict
            A dictionary of response from the call
        """
        data = {
            "id": self.uuid,
            "server_config_retrieval": "1",
        }
        if login is False:
            data["_uid"] = self.user_id
            data["_uuid"] = self.uuid
            data["_csrftoken"] = self.token
        return await self.private_request("launcher/sync/", data, login=login)

    async def set_contact_point_prefill(self, usage: str = "prefill") -> Dict:
        """
        Sync Launcher

        Parameters
        ----------
        usage: str, optional
            Default "prefill"

        Returns
        -------
        Dict
            A dictionary of response from the call
        """
        data = {
            "phone_id": self.phone_id,
            "usage": usage,
            # "_csrftoken": self.token
        }
        return await self.private_request(
            "accounts/contact_point_prefill/", data, login=True
        )


class PostLoginFlowMixin:
    """
    Helpers for post login flow
    """

    async def login_flow(self) -> bool:
        """
        Emulation mobile app behaivor after login

        Returns
        -------
        bool
            A boolean value
        """
        check_flow = []
        # chance = random.randint(1, 100) % 2 == 0
        # reason = "pull_to_refresh" if chance else "cold_start"
        check_flow.append(await self.get_reels_tray_feed("cold_start"))
        check_flow.append(await self.get_timeline_feed(["cold_start_fetch"]))
        return all(check_flow)

    async def get_timeline_feed(
        self, options: List[Dict] = ["pull_to_refresh"]
    ) -> Dict:
        """
        Get your timeline feed

        Parameters
        ----------
        options: List, optional
            Configurable options

        Returns
        -------
        Dict
            A dictionary of response from the call
        """
        headers = {
            "X-Ads-Opt-Out": "0",
            "X-DEVICE-ID": self.uuid,
            "X-CM-Bandwidth-KBPS": "-1.000",  # str(random.randint(2000, 5000)),
            "X-CM-Latency": str(random.randint(1, 5)),
        }
        data = {
            "feed_view_info": "[]",
            "phone_id": self.phone_id,
            "battery_level": random.randint(25, 100),
            "timezone_offset": str(self.timezone_offset),
            "_csrftoken": self.token,
            "device_id": self.uuid,
            "request_id": self.request_id,
            "_uuid": self.uuid,
            "is_charging": random.randint(0, 1),
            "will_sound_on": random.randint(0, 1),
            "session_id": self.client_session_id,
            "bloks_versioning_id": self.bloks_versioning_id,
        }
        if "pull_to_refresh" in options:
            data["reason"] = "pull_to_refresh"
            data["is_pull_to_refresh"] = "1"
        elif "cold_start_fetch" in options:
            data["reason"] = "cold_start_fetch"
            data["is_pull_to_refresh"] = "0"
        # if "push_disabled" in options:
        #     data["push_disabled"] = "true"
        # if "recovered_from_crash" in options:
        #     data["recovered_from_crash"] = "1"
        return await self.private_request(
            "feed/timeline/", json.dumps(data), with_signature=False, headers=headers
        )

    async def get_reels_tray_feed(self, reason: str = "pull_to_refresh") -> Dict:
        """
        Get your reels tray feed

        Parameters
        ----------
        reason: str, optional
            Default "pull_to_refresh"

        Returns
        -------
        Dict
            A dictionary of response from the call
        """
        data = {
            "supported_capabilities_new": config.SUPPORTED_CAPABILITIES,
            "reason": reason,
            "timezone_offset": str(self.timezone_offset),
            "tray_session_id": self.tray_session_id,
            "request_id": self.request_id,
            "latest_preloaded_reel_ids": "[]",
            "page_size": 50,
            # "_csrftoken": self.token,
            "_uuid": self.uuid,
        }
        return await self.private_request("feed/reels_tray/", data)


class LoginMixin(PreLoginFlowMixin, PostLoginFlowMixin):
    username = None
    password = None
    authorization_data = {}  # decoded authorization header
    last_login = None
    relogin_attempt = 0
    device_settings = {}
    client_session_id = ""
    tray_session_id = ""
    advertising_id = ""
    android_device_id = ""
    request_id = ""
    phone_id = ""
    app_id = "567067343352427"
    uuid = ""
    mid = ""
    country = "US"
    country_code = 1  # Phone code, default USA
    locale = "en_US"
    timezone_offset: int = -14400  # New York, GMT-4 in seconds
    ig_u_rur = ""  # e.g. CLN,49897488153,1666640702:01...834e2d1f731e20
    ig_www_claim = ""  # e.g. hmac.AR2uidim8es5kYgDiNxY0UG_ZhffFFSt8TGCV5eA1VYYsMNx

    def __init__(self):
        self.user_agent = None
        self.settings = None

    def init(self) -> bool:
        """
        Initialize Login helpers

        Returns
        -------
        bool
            A boolean value
        """
        if "cookies" in self.settings:
            self.private.set_cookies(self.settings["cookies"])
        self.authorization_data = self.settings.get("authorization_data", {})
        self.last_login = self.settings.get("last_login")
        self.set_timezone_offset(
            self.settings.get("timezone_offset", self.timezone_offset)
        )
        self.set_device(self.settings.get("device_settings"))
        # self.bloks_versioning_id = hashlib.sha256(
        #     json.dumps(self.device_settings)
        # ).hexdigest()
        # this param is constant and will change by Instagram app version
        self.bloks_versioning_id = (
            "ce555e5500576acd8e84a66018f54a05720f2dce29f0bb5a1f97f0c10d6fac48"
        )
        self.set_user_agent(self.settings.get("user_agent"))
        self.set_uuids(self.settings.get("uuids") or {})
        self.set_locale(self.settings.get("locale", self.locale))
        self.set_country(self.settings.get("country", self.country))
        self.set_country_code(self.settings.get("country_code", self.country_code))
        self.mid = self.settings.get("mid", self.cookie_dict.get("mid"))
        self.set_ig_u_rur(self.settings.get("ig_u_rur"))
        self.set_ig_www_claim(self.settings.get("ig_www_claim"))
        # init headers
        headers = self.base_headers
        headers.update({"Authorization": self.authorization})
        self.private.headers.update(headers)
        return True

    async def login_by_sessionid(self, sessionid: str) -> bool:
        """
        Login using session id

        Parameters
        ----------
        sessionid: str
            Session ID

        Returns
        -------
        bool
            A boolean value
        """
        assert isinstance(sessionid, str) and len(sessionid) > 30, "Invalid sessionid"
        self.settings["cookies"] = {"sessionid": sessionid}
        self.init()
        user_id = re.search(r"^\d+", sessionid).group()
        self.authorization_data = {
            "ds_user_id": user_id,
            "sessionid": sessionid,
            "should_use_header_over_cookies": True,
        }
        try:
            user = await self.user_info_v1(int(user_id))
        except (PrivateError, ValidationError):
            self.inject_sessionid_to_public()
            # ClientUnauthorizedError
            user = await self.user_short_gql(int(user_id))
        self.username = user.username
        self.cookie_dict["ds_user_id"] = user.pk
        return True

    async def login(
        self,
        username: str,
        password: str,
        relogin: bool = False,
        verification_code: str = "",
    ) -> bool:
        """
        Login

        Parameters
        ----------
        username: str
            Instagram Username
        password: str
            Instagram Password
        relogin: bool
            Whether or not to re login, default False
        verification_code: str
            2FA verification code

        Returns
        -------
        bool
            A boolean value
        """

        if not self.username or not self.password:
            if username is None or password is None:
                raise BadCredentials("Both username and password must be provided.")

            self.username = username
            self.password = password

        if relogin:
            self.authorization_data = {}
            self.private.headers.pop("Authorization", None)
            self.private.cookies.clear()
            if self.relogin_attempt > 1:
                raise ReloginAttemptExceeded()
            self.relogin_attempt += 1
        # if self.user_id and self.last_login:
        #     if time.time() - self.last_login < 60 * 60 * 24:
        #        return True  # already login
        if self.user_id and not relogin:
            return True  # already login
        try:
            await self.pre_login_flow()
        except (PleaseWaitFewMinutes, ClientThrottledError):
            self.logger.warning("Ignore 429: Continue login")
            # The instagram application ignores this error
            # and continues to log in (repeat this behavior)
        enc_password = await self.password_encrypt(password)
        data = {
            "jazoest": generate_jazoest(self.phone_id),
            "country_codes": '[{"country_code":"%d","source":["default"]}]'
            % int(self.country_code),
            "phone_id": self.phone_id,
            "enc_password": enc_password,
            "username": username,
            "adid": self.advertising_id,
            "guid": self.uuid,
            "device_id": self.android_device_id,
            "google_tokens": "[]",
            "login_attempt_count": "0",
        }
        try:
            logged = await self.private_request("accounts/login/", data, login=True)
            self.authorization_data = self.parse_authorization(
                self.last_response.headers.get("ig-set-authorization")
            )
        except TwoFactorRequired as e:
            if not verification_code.strip():
                raise TwoFactorRequired(
                    f"{e} (you did not provide verification_code for login method)"
                )
            two_factor_identifier = self.last_json.get("two_factor_info", {}).get(
                "two_factor_identifier"
            )
            data = {
                "verification_code": verification_code,
                "phone_id": self.phone_id,
                "_csrftoken": self.token,
                "two_factor_identifier": two_factor_identifier,
                "username": username,
                "trust_this_device": "0",
                "guid": self.uuid,
                "device_id": self.android_device_id,
                "waterfall_id": str(uuid4()),
                "verification_method": "3",
            }
            logged = await self.private_request(
                "accounts/two_factor_login/", data, login=True
            )
            self.authorization_data = self.parse_authorization(
                self.last_response.headers.get("ig-set-authorization")
            )
        if logged:
            await self.login_flow()
            self.last_login = time.time()
            return True
        return False

    async def one_tap_app_login(self, user_id: int, nonce: str) -> bool:
        """One tap login emulation

        Parameters
        ----------
        user_id: int
            User ID
        nonce: str
            Login nonce (from Instagram, e.g. in /logout/)

        Returns
        -------
        bool
            A boolean value
        """
        user_id = int(user_id)
        data = {
            "phone_id": self.phone_id,
            "user_id": user_id,
            "adid": self.advertising_id,
            "guid": self.uuid,
            "device_id": self.uuid,
            "login_nonce": nonce,
            "_csrftoken": self.token,
        }
        return await self.private_request("accounts/one_tap_app_login/", data)

    async def relogin(self) -> bool:
        """
        Relogin helper

        Returns
        -------
        bool
            A boolean value
        """
        return await self.login(self.username, self.password, relogin=True)

    @property
    def cookie_dict(self) -> dict:
        return self.private.cookies_dict()

    @property
    def sessionid(self) -> str:
        sessionid = self.cookie_dict.get("sessionid")
        if not sessionid and self.authorization_data:
            sessionid = self.authorization_data.get("sessionid")
        return sessionid

    @property
    def token(self) -> str:
        """CSRF token
        e.g. vUJGjpst6szjI38mZ6Pb1dROsWVerZelGSYGe0W1tuugpSUefVjRLj2Pom2SWNoA
        """
        if not getattr(self, "_token", None):
            self._token = self.cookie_dict.get("csrftoken", gen_token(64))
        return self._token

    @property
    def rank_token(self) -> str:
        # return f"{self.user_id}_{self.uuid}"
        # fixme: wrong rank_token
        return self.uuid

    @property
    def user_id(self) -> int:
        user_id = getattr(self, "_user_id", None)
        if not user_id and self.authorization_data:
            user_id = self.authorization_data.get("ds_user_id")
        if user_id:
            return int(user_id)
        return None

    @property
    def device(self) -> dict:
        return {
            key: val
            for key, val in self.device_settings.items()
            if key in ["manufacturer", "model", "android_version", "android_release"]
        }

    def get_settings(self) -> Dict:
        """
        Get current session settings

        Returns
        -------
        Dict
            Current session settings as a Dict
        """
        return {
            "uuids": {
                "phone_id": self.phone_id,
                "uuid": self.uuid,
                "client_session_id": self.client_session_id,
                "advertising_id": self.advertising_id,
                "android_device_id": self.android_device_id,
                # "device_id": self.uuid,
                "request_id": self.request_id,
                "tray_session_id": self.tray_session_id,
            },
            "mid": self.mid,
            "ig_u_rur": self.ig_u_rur,
            "ig_www_claim": self.ig_www_claim,
            "authorization_data": self.authorization_data,
            "cookies": self.private.cookies_dict(),
            "last_login": self.last_login,
            "device_settings": self.device_settings,
            "user_agent": self.user_agent,
            "country": self.country,
            "country_code": self.country_code,
            "locale": self.locale,
            "timezone_offset": self.timezone_offset,
        }

    def set_settings(self, settings: Dict) -> bool:
        """
        Set session settings

        Returns
        -------
        Bool
        """
        self.settings = settings
        self.init()
        return True

    def load_settings(self, path: Path) -> Dict:
        """
        Load session settings

        Parameters
        ----------
        path: Path
            Path to storage file

        Returns
        -------
        Dict
            Current session settings as a Dict
        """
        with open(path, "r") as fp:
            self.set_settings(json.load(fp))
            return self.settings
        return None

    def dump_settings(self, path: Path) -> bool:
        """
        Serialize and save session settings

        Parameters
        ----------
        path: Path
            Path to storage file

        Returns
        -------
        Bool
        """
        with open(path, "w") as fp:
            json.dump(self.get_settings(), fp, indent=4)
        return True

    def set_device(self, device: Dict = None, reset: bool = False) -> bool:
        """
        Helper to set a device for login

        Parameters
        ----------
        device: Dict, optional
            Dict of device settings, default is None

        Returns
        -------
        bool
            A boolean value
        """
        self.device_settings = device or {
            "app_version": "269.0.0.18.75",
            "android_version": 26,
            "android_release": "8.0.0",
            "dpi": "480dpi",
            "resolution": "1080x1920",
            "manufacturer": "OnePlus",
            "device": "devitron",
            "model": "6T Dev",
            "cpu": "qcom",
            "version_code": "314665256",
        }
        self.settings["device_settings"] = self.device_settings
        if reset:
            self.set_uuids({})
            # self.settings = self.get_settings()
        return True

    def set_user_agent(self, user_agent: str = "", reset: bool = False) -> bool:
        """
        Helper to set user agent

        Parameters
        ----------
        user_agent: str, optional
            User agent, default is ""

        Returns
        -------
        bool
            A boolean value
        """
        data = dict(self.device_settings, locale=self.locale)
        self.user_agent = user_agent or config.USER_AGENT_BASE.format(**data)
        # changed in base_headers:
        # self.private.headers.update({"User-Agent": self.user_agent})
        self.settings["user_agent"] = self.user_agent
        if reset:
            self.set_uuids({})
            # self.settings = self.get_settings()
        return True

    def set_uuids(self, uuids: Dict = None) -> bool:
        """
        Helper to set uuids

        Parameters
        ----------
        uuids: Dict, optional
            UUIDs, default is None

        Returns
        -------
        bool
            A boolean value
        """
        self.phone_id = uuids.get("phone_id", self.generate_uuid())
        self.uuid = uuids.get("uuid", self.generate_uuid())
        self.client_session_id = uuids.get("client_session_id", self.generate_uuid())
        self.advertising_id = uuids.get("advertising_id", self.generate_uuid())
        self.android_device_id = uuids.get(
            "android_device_id", self.generate_android_device_id()
        )
        self.request_id = uuids.get("request_id", self.generate_uuid())
        self.tray_session_id = uuids.get("tray_session_id", self.generate_uuid())
        # self.device_id = uuids.get("device_id", self.generate_uuid())
        self.settings["uuids"] = uuids
        return True

    def generate_uuid(self, prefix: str = "", suffix: str = "") -> str:
        """
        Helper to generate uuids

        Returns
        -------
        str
            A stringified UUID
        """
        return f"{prefix}{uuid.uuid4()}{suffix}"

    def generate_mutation_token(self) -> str:
        """
        Token used when DM sending and upload media

        Returns
        -------
        str
            A stringified int
        """
        return str(random.randint(6800011111111111111, 6800099999999999999))

    def generate_android_device_id(self) -> str:
        """
        Helper to generate Android Device ID

        Returns
        -------
        str
            A random android device id
        """
        return "android-%s" % hashlib.sha256(str(time.time()).encode()).hexdigest()[:16]

    async def expose(self) -> Dict:
        """
        Helper to expose

        Returns
        -------
        Dict
            A dictionary of response from the call
        """
        data = {"id": self.uuid, "experiment": "ig_android_profile_contextual_feed"}
        return await self.private_request("qe/expose/", self.with_default_data(data))

    def with_extra_data(self, data: Dict) -> Dict:
        """
        Helper to get extra data

        Returns
        -------
        Dict
            A dictionary of default data
        """
        return self.with_default_data(
            {
                "phone_id": self.phone_id,
                "_uid": str(self.user_id),
                "guid": self.uuid,
                **data,
            }
        )

    def with_default_data(self, data: Dict) -> Dict:
        """
        Helper to get default data

        Returns
        -------
        Dict
            A dictionary of default data
        """
        return {
            "_uuid": self.uuid,
            # "_uid": str(self.user_id),
            # "_csrftoken": self.token,
            "device_id": self.android_device_id,
            **data,
        }

    def with_action_data(self, data: Dict) -> Dict:
        """
        Helper to get action data

        Returns
        -------
        Dict
            A dictionary of action data
        """
        return dict(self.with_default_data({"radio_type": "wifi-none"}), **data)

    def gen_user_breadcrumb(self, size: int) -> str:
        """
        Helper to generate user breadcrumbs

        Parameters
        ----------
        size: int
            Integer value

        Returns
        -------
        Str
            A string
        """
        key = "iN4$aGr0m"
        dt = int(time.time() * 1000)
        time_elapsed = random.randint(500, 1500) + size * random.randint(500, 1500)
        text_change_event_count = max(1, size / random.randint(3, 5))
        data = "{size!s} {elapsed!s} {count!s} {dt!s}".format(
            **{
                "size": size,
                "elapsed": time_elapsed,
                "count": text_change_event_count,
                "dt": dt,
            }
        )
        return "{!s}\n{!s}\n".format(
            base64.b64encode(
                hmac.new(
                    key.encode("ascii"), data.encode("ascii"), digestmod=hashlib.sha256
                ).digest()
            ),
            base64.b64encode(data.encode("ascii")),
        )

    def inject_sessionid_to_public(self) -> bool:
        """
        Inject sessionid from private session to public session

        Returns
        -------
        bool
            A boolean value
        """
        if not self.sessionid:
            return False
        cookie = {"sessionid": self.sessionid}
        s = self.settings
        if rur := s.get("ig_u_rur"):
            cookie["rur"] = rur
        if mid := s.get("mid"):
            cookie["mid"] = mid
        if ds := self.authorization_data.get("ds_user_id"):
            cookie["ds_user_id"] = ds
        if ig_did := s.get("ig_did"):
            cookie["ig_did"] = ig_did
        self.public.set_cookies(cookie)
        self.graphql.set_cookies(cookie)
        return True

    async def logout(self) -> bool:
        result = await self.private_request(
            "accounts/logout/", {"one_tap_app_login": True}
        )
        return result["status"] == "ok"

    def parse_authorization(self, authorization) -> dict:
        """Parse authorization header"""
        try:
            b64part = authorization.rsplit(":", 1)[-1]
            if not b64part:
                return {}
            return json.loads(base64.b64decode(b64part))
        except Exception as e:
            self.logger.exception(e)
        return {}

    @property
    def authorization(self) -> str:
        """Build authorization header
        Example: Bearer IGT:2:eaW9u.....aWQiOiI0NzM5=
        """
        if self.authorization_data:
            b64part = base64.b64encode(dumps(self.authorization_data).encode()).decode()
            return f"Bearer IGT:2:{b64part}"
        return ""

    def dump_instaman(self):
        """IAM format"""
        uuids = ";".join(
            [
                self.android_device_id.replace("android-", ""),
                self.uuid,
                self.phone_id,
                self.client_session_id,
            ]
        )
        headers = {
            "X-MID": self.mid,
            "IG-U-DS-USER-ID": self.user_id,
            "IG-U-RUR": self.ig_u_rur,
            "Authorization": self.authorization,
            "X-IG-WWW-Claim": self.ig_www_claim or "0",
        }
        headers = ";".join([f"{key}={value}" for key, value in headers.items()])
        return f"{self.username}:{self.password}|{self.user_agent}|{uuids}|{headers};||"

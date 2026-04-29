import json
import logging
import os
import os.path
import random
import tempfile
import types
import unittest
from unittest import mock
from unittest.mock import AsyncMock, Mock
from datetime import datetime, timedelta
from json.decoder import JSONDecodeError
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import ValidationError

from aiograpi import Client
from aiograpi.extractors import (
    extract_direct_message,
    extract_direct_thread,
    extract_resource_v1,
    extract_story_v1,
)
from aiograpi.exceptions import (
    AlbumConfigureError,
    BadCredentials,
    ChallengeError,
    ChallengeRedirection,
    ChallengeRequired,
    ChallengeUnknownStep,
    ClipConfigureError,
    ClientConnectionError,
    ClientGraphqlError,
    ClientUnauthorizedError,
    ClientThrottledError,
    DirectThreadNotFound,
    IGTVConfigureError,
    InvalidTargetUser,
    PleaseWaitFewMinutes,
    PhotoConfigureError,
    PhotoConfigureStoryError,
    PrivateError,
    RecaptchaChallengeForm,
    ReloginAttemptExceeded,
    SelectContactPointRecoveryForm,
    SubmitPhoneNumberForm,
    TwoFactorRequired,
    UnknownError,
    UserNotFound,
    VideoConfigureError,
    VideoConfigureStoryError,
)
from aiograpi.mixins.user import UserMixin
from aiograpi.story import StoryBuilder
from aiograpi.types import (
    Account,
    Collection,
    Comment,
    DirectMessage,
    DirectThread,
    Hashtag,
    Highlight,
    Location,
    Media,
    MediaOembed,
    Note,
    Share,
    Story,
    StoryHashtag,
    StoryLink,
    StoryMedia,
    StoryMention,
    StorySticker,
    User,
    UserShort,
    Usertag,
)
from aiograpi.utils import gen_password, generate_jazoest
from aiograpi.zones import UTC

logger = logging.getLogger("aiograpi.tests")
ACCOUNT_USERNAME = os.getenv("IG_USERNAME", "username")
ACCOUNT_PASSWORD = os.getenv("IG_PASSWORD", "password*")
ACCOUNT_SESSIONID = os.getenv("IG_SESSIONID", "")
TEST_ACCOUNTS_URL = os.getenv("TEST_ACCOUNTS_URL")

REQUIRED_MEDIA_FIELDS = [
    "pk",
    "taken_at",
    "id",
    "media_type",
    "code",
    "thumbnail_url",
    "location",
    "user",
    "comment_count",
    "like_count",
    "caption_text",
    "usertags",
    "video_url",
    "view_count",
    "video_duration",
    "title",
]
REQUIRED_STORY_FIELDS = [
    "pk",
    "id",
    "code",
    "taken_at",
    "media_type",
    "product_type",
    "thumbnail_url",
    "user",
    "video_url",
    "video_duration",
    "mentions",
    "links",
]


def cleanup(*paths):
    for path in paths:
        try:
            os.remove(path)
            os.remove(f"{path}.jpg")
        except FileNotFoundError:
            continue


def keep_path(user):
    user.profile_pic_url = user.profile_pic_url.path
    return user


class BaseClientMixin:
    def __init__(self, *args, **kwargs):
        if self.cl is None:
            self.cl = Client()
        self.set_proxy_if_exists()
        super().__init__(*args, **kwargs)

    def set_proxy_if_exists(self):
        proxy = os.getenv("IG_PROXY", "")
        if proxy:
            self.cl.set_proxy(proxy)
        return True


class ClientPrivateTestCase(BaseClientMixin, unittest.IsolatedAsyncioTestCase):
    cl = None
    _username_cache = {}

    def test_accounts_url(self):
        if not TEST_ACCOUNTS_URL:
            self.skipTest("TEST_ACCOUNTS_URL not configured")
        parts = urlsplit(TEST_ACCOUNTS_URL)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query.setdefault("count", "5")
        return urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                parts.path,
                urlencode(query),
                parts.fragment,
            )
        )

    async def user_info_by_username(self, username):
        return await self.cl.user_info_by_username_v1(username)

    async def user_id_from_username(self, username):
        info = self._username_cache.get(username)
        if not info:
            info = await self.user_info_by_username(username)
            self._username_cache[username] = info
        return str(info.pk)

    async def fresh_account(self):
        import urllib.request
        import ssl

        ctx = ssl._create_unverified_context()
        req = urllib.request.Request(
            self.test_accounts_url(),
            headers={"User-Agent": "Mozilla/5.0 aiograpi-tests"},
        )
        with urllib.request.urlopen(req, context=ctx) as resp:
            data = json.loads(resp.read())
        last_exc = None
        for attempt, acc in enumerate(data[:5], start=1):
            print(f"Fresh account attempt {attempt}: %(username)r" % acc)
            settings = dict(acc["client_settings"])
            totp_seed = settings.pop("totp_seed", None)
            cl = Client(settings=settings, proxy=acc["proxy"])
            login_kwargs = {
                "username": acc["username"],
                "password": acc["password"],
                "relogin": True,
            }
            if totp_seed:
                totp_code = cl.totp_generate_code(totp_seed)
                cl.totp_seed = totp_seed
                cl.totp_code = totp_code
                login_kwargs["verification_code"] = totp_code
            try:
                await cl.login(**login_kwargs)
            except Exception as exc:
                last_exc = exc
                print(
                    f"Fresh account attempt {attempt} failed for {acc['username']}: "
                    f"{exc.__class__.__name__} {exc}"
                )
                continue
            cl._user_id = acc.get("user_id")
            return cl
        raise last_exc or RuntimeError("No usable fresh account returned")

    async def asyncSetUp(self):
        if TEST_ACCOUNTS_URL:
            self.cl = await self.fresh_account()
            return
        filename = f"/tmp/aiograpi_tests_client_settings_{ACCOUNT_USERNAME}.json"
        if self.cl is None:
            self.cl = Client()
        settings = {}
        try:
            st = os.stat(filename)
            if datetime.fromtimestamp(st.st_mtime) > (
                datetime.now() - timedelta(seconds=3600)
            ):
                settings = self.cl.load_settings(filename)
        except FileNotFoundError:
            pass
        except JSONDecodeError as e:
            logger.info(
                "JSONDecodeError when read stored client settings. Use empty settings"
            )
            logger.exception(e)
        self.cl.set_settings(settings)
        self.cl.request_timeout = 1
        self.set_proxy_if_exists()
        if ACCOUNT_SESSIONID:
            await self.cl.login_by_sessionid(ACCOUNT_SESSIONID)
        else:
            await self.cl.login(ACCOUNT_USERNAME, ACCOUNT_PASSWORD, relogin=True)
        self.cl.dump_settings(filename)


class ClientPublicTestCase(BaseClientMixin, unittest.IsolatedAsyncioTestCase):
    cl = None

    def assertDict(self, obj, data):
        for key, value in data.items():
            if isinstance(value, str) and "..." in value:
                self.assertTrue(value.replace("...", "") in obj[key])
            elif isinstance(value, int):
                self.assertTrue(obj[key] >= value)
            else:
                self.assertEqual(obj[key], value)

    async def test_media_info_gql(self):
        media_pk = await self.cl.media_pk_from_url(
            "https://www.instagram.com/p/BVDOOolFFxg/"
        )
        m = await self.cl.media_info_gql(media_pk)
        self.assertIsInstance(m, Media)
        media = {
            "pk": 1532130876531694688,
            "id": "1532130876531694688_25025320",
            "code": "BVDOOolFFxg",
            "taken_at": datetime(2017, 6, 7, 19, 37, 35, tzinfo=UTC()),
            "media_type": 1,
            "product_type": "",
            "thumbnail_url": "https://...",
            "location": None,
            "comment_count": 6,
            "like_count": 79,
            "has_liked": None,
            "caption_text": "#creepy #creepyclothing",
            "usertags": [],
            "video_url": None,
            "view_count": 0,
            "video_duration": 0.0,
            "title": "",
            "resources": [],
        }
        self.assertDict(m.dict(), media)


class ExtractorsRegressionTestCase(unittest.TestCase):
    def test_extract_resource_v1_handles_empty_candidates(self):
        resource = extract_resource_v1(
            {"pk": "1", "media_type": 1, "image_versions2": {"candidates": []}}
        )
        self.assertIsNone(resource.thumbnail_url)
        self.assertEqual(resource.pk, "1")


class ImageUtilSafeRemoteFetchTestCase(unittest.TestCase):
    """SSRF hardening for image_util._is_safe_remote_url and
    _safe_remote_get — block private/loopback/link-local destinations
    and refuse redirects on caller-supplied URLs."""

    def test_blocks_loopback_ipv4(self):
        from aiograpi.image_util import _is_safe_remote_url

        self.assertFalse(_is_safe_remote_url("http://127.0.0.1/"))
        self.assertFalse(_is_safe_remote_url("http://127.0.0.1:6379/"))

    def test_blocks_loopback_ipv6(self):
        from aiograpi.image_util import _is_safe_remote_url

        self.assertFalse(_is_safe_remote_url("http://[::1]/"))

    def test_blocks_aws_metadata_endpoint(self):
        from aiograpi.image_util import _is_safe_remote_url

        self.assertFalse(
            _is_safe_remote_url("http://169.254.169.254/latest/meta-data/")
        )

    def test_blocks_rfc1918_ipv4_ranges(self):
        from aiograpi.image_util import _is_safe_remote_url

        self.assertFalse(_is_safe_remote_url("http://10.0.0.1/"))
        self.assertFalse(_is_safe_remote_url("http://172.16.0.1/"))
        self.assertFalse(_is_safe_remote_url("http://192.168.1.1/"))

    def test_rejects_non_http_schemes(self):
        from aiograpi.image_util import _is_safe_remote_url

        self.assertFalse(_is_safe_remote_url("file:///etc/passwd"))
        self.assertFalse(_is_safe_remote_url("ftp://example.com/foo"))
        self.assertFalse(_is_safe_remote_url("gopher://example.com/"))
        self.assertFalse(_is_safe_remote_url("ssh://example.com/"))

    def test_rejects_unresolvable_host(self):
        from aiograpi.image_util import _is_safe_remote_url

        # .invalid is RFC 6761 — guaranteed never to resolve.
        self.assertFalse(_is_safe_remote_url("http://nonexistent.invalid/"))

    def test_blocks_dns_rebinding_attempt_via_resolution(self):
        from aiograpi.image_util import _is_safe_remote_url

        # localhost resolves to 127.0.0.1 — reject even if textual
        # check would have passed on hostname alone.
        self.assertFalse(_is_safe_remote_url("http://localhost/"))

    def test_safe_remote_get_blocks_private_url_before_fetching(self):
        from aiograpi.image_util import _safe_remote_get

        with self.assertRaises(ValueError) as cm:
            _safe_remote_get("http://127.0.0.1/foo")

        self.assertIn("non-public", str(cm.exception).lower())

    def test_safe_remote_get_refuses_redirect(self):
        from aiograpi.image_util import _safe_remote_get

        # Build a fake redirect response. _is_safe_remote_url is bypassed
        # by patching it to True so the test isolates redirect handling.
        fake_response = Mock(
            status_code=302,
            is_redirect=True,
            headers={"location": "http://169.254.169.254/secret"},
        )
        with (
            mock.patch("aiograpi.image_util._is_safe_remote_url", return_value=True),
            mock.patch("aiograpi.image_util.httpx.get", return_value=fake_response),
        ):
            with self.assertRaises(ValueError) as cm:
                _safe_remote_get("http://example.com/redirect")

        self.assertIn("redirect", str(cm.exception).lower())


class PublicRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_public_request_uses_post_for_post_bodies(self):
        client = Client()
        response = Mock()
        response.headers = {"Content-Length": "0"}
        response.raw.tell.return_value = 0
        response.status_code = 200
        response.url = "https://www.instagram.com/api/graphql"
        response.json.return_value = {"status": "ok", "data": {"user": {}}}
        response.raise_for_status.return_value = None
        response.text = ""

        with mock.patch.object(
            client.public, "post", new=AsyncMock(return_value=response)
        ) as post:
            body = await client.public_request(
                "https://www.instagram.com/api/graphql",
                data={"doc_id": "1"},
                return_json=True,
            )

        self.assertEqual(body["status"], "ok")
        post.assert_called_once()

    async def test_public_graphql_request_raises_client_graphql_error_when_data_missing(
        self,
    ):
        client = Client()
        body = {
            "errors": [
                {
                    "message": "execution error",
                    "summary": "Incorrect Query",
                    "description": "The query provided was invalid.",
                }
            ],
            "status": "ok",
        }

        client.public_request = AsyncMock(return_value=body)
        with self.assertRaises(ClientGraphqlError) as cm:
            await client.public_graphql_request(
                {"user_id": "123", "include_reel": True},
                query_hash="ad99dd9d3646cc3c0dda65debcd266a7",
            )

        self.assertIn("Missing 'data' in GraphQL response", str(cm.exception))
        self.assertIn("Incorrect Query", str(cm.exception))

    async def test_user_stories_anonymous_does_not_fallback_to_private(self):
        client = Client()

        client.user_stories_gql = AsyncMock(
            side_effect=ClientGraphqlError("Incorrect Query")
        )
        client.user_stories_v1 = AsyncMock()
        with self.assertRaises(ClientGraphqlError) as cm:
            await client.user_stories("4776134209", amount=5)

        client.user_stories_v1.assert_not_called()
        self.assertIn("Incorrect Query", str(cm.exception))

    async def test_media_info_gql_falls_back_to_a1_on_public_401(self):
        client = Client()
        expected = Mock(spec=Media)

        client.public_graphql_request = AsyncMock(
            side_effect=ClientUnauthorizedError("401", response=Mock(status_code=401))
        )
        client.media_info_a1 = AsyncMock(return_value=expected)

        result = await client.media_info_gql("2110901750722920960")

        self.assertIs(result, expected)
        client.media_info_a1.assert_called_once_with("2110901750722920960")

    async def test_public_head_uses_httpx_ext_request_with_follow_redirects_off(
        self,
    ):
        client = Client()
        client.public.proxy = None
        client.public.headers = {"User-Agent": "test"}
        fake_response = Mock(status_code=302, headers={"location": "https://x"})

        with mock.patch(
            "aiograpi.mixins.public.httpx_ext.request",
            new=AsyncMock(return_value=fake_response),
        ) as ext_request:
            response = await client.public_head("https://www.instagram.com/share/p/abc")

        self.assertIs(response, fake_response)
        args, kwargs = ext_request.call_args
        self.assertEqual(args[0], "HEAD")
        self.assertEqual(args[1], "https://www.instagram.com/share/p/abc")
        self.assertFalse(kwargs["follow_redirects"])
        self.assertEqual(kwargs["headers"], {"User-Agent": "test"})

    async def test_public_head_passes_follow_redirects_true_when_requested(self):
        client = Client()
        fake_response = Mock(status_code=200, headers={})

        with mock.patch(
            "aiograpi.mixins.public.httpx_ext.request",
            new=AsyncMock(return_value=fake_response),
        ) as ext_request:
            await client.public_head("https://example.com", follow_redirects=True)

        kwargs = ext_request.call_args.kwargs
        self.assertTrue(kwargs["follow_redirects"])

    async def test_public_head_increments_request_counter(self):
        client = Client()
        client.public_requests_count = 5
        fake_response = Mock()

        with mock.patch(
            "aiograpi.mixins.public.httpx_ext.request",
            new=AsyncMock(return_value=fake_response),
        ):
            await client.public_head("https://example.com")

        self.assertEqual(client.public_requests_count, 6)


class PolarisProfileNormalizationTestCase(unittest.TestCase):
    """Pure-function tests for _normalize_polaris_profile (PolarisProfilePageContentQuery
    response → legacy v1 shape understood by extract_user_v1)."""

    def test_pk_filled_from_id_when_missing(self):
        client = Client()
        out = client._normalize_polaris_profile({"id": "12345"})
        self.assertEqual(out["pk"], "12345")

    def test_pk_preserved_when_present(self):
        client = Client()
        out = client._normalize_polaris_profile({"pk": "999", "id": "12345"})
        self.assertEqual(out["pk"], "999")

    def test_is_business_filled_from_is_business_account(self):
        client = Client()
        out = client._normalize_polaris_profile({"is_business_account": True})
        self.assertTrue(out["is_business"])

    def test_category_filled_from_category_name(self):
        client = Client()
        out = client._normalize_polaris_profile({"category_name": "Photographer"})
        self.assertEqual(out["category"], "Photographer")

    def test_friendship_status_flattened(self):
        client = Client()
        out = client._normalize_polaris_profile(
            {"friendship_status": {"following": True, "followed_by": False}}
        )
        self.assertTrue(out["followed_by_viewer"])
        self.assertFalse(out["follows_viewer"])

    def test_missing_friendship_status_defaults(self):
        client = Client()
        out = client._normalize_polaris_profile({})
        self.assertFalse(out["followed_by_viewer"])
        self.assertFalse(out["follows_viewer"])


class CaptchaHandlerMixinRegressionTestCase(unittest.TestCase):
    """CaptchaHandlerMixin is opt-in (not wired into Client by default).
    Test it standalone."""

    def setUp(self):
        from aiograpi.exceptions import CaptchaChallengeRequired, ClientError
        from aiograpi.mixins.captcha import CaptchaHandlerMixin

        self.CaptchaChallengeRequired = CaptchaChallengeRequired
        self.ClientError = ClientError

        class CaptchaClient(CaptchaHandlerMixin):
            pass

        self.client = CaptchaClient()

    def test_no_handler_raises_captcha_required(self):
        with self.assertRaises(self.CaptchaChallengeRequired) as cm:
            self.client.captcha_resolve(site_key="K", page_url="U")
        self.assertIn("No captcha handler is configured", str(cm.exception))

    def test_handler_returns_token(self):
        self.client.set_captcha_handler(lambda details: "solved-token-123")
        token = self.client.captcha_resolve(site_key="K", page_url="U")
        self.assertEqual(token, "solved-token-123")

    def test_handler_receives_normalized_details(self):
        captured = {}

        def handler(details):
            captured.update(details)
            return "tok"

        self.client.set_captcha_handler(handler)
        self.client.captcha_resolve(
            site_key="SK",
            page_url="https://example",
            challenge_type="recaptcha",
            raw_challenge_json={"x": 1},
        )
        self.assertEqual(
            captured,
            {
                "site_key": "SK",
                "page_url": "https://example",
                "challenge_type": "recaptcha",
                "raw_challenge_json": {"x": 1},
            },
        )

    def test_handler_returning_empty_string_raises(self):
        self.client.set_captcha_handler(lambda details: "")
        with self.assertRaises(self.CaptchaChallengeRequired) as cm:
            self.client.captcha_resolve(site_key="K", page_url="U")
        self.assertIn("did not return a valid token", str(cm.exception))

    def test_handler_raising_unexpected_exception_wraps_it(self):
        def boom(details):
            raise RuntimeError("solver down")

        self.client.set_captcha_handler(boom)
        with self.assertRaises(self.CaptchaChallengeRequired) as cm:
            self.client.captcha_resolve(site_key="K", page_url="U")
        self.assertIn("solver down", str(cm.exception))

    def test_handler_can_propagate_captcha_required(self):
        def explicit_raise(details):
            raise self.CaptchaChallengeRequired(
                message="manual reject", challenge_details=details
            )

        self.client.set_captcha_handler(explicit_raise)
        with self.assertRaises(self.CaptchaChallengeRequired) as cm:
            self.client.captcha_resolve(site_key="K")
        self.assertIn("manual reject", str(cm.exception))

    def test_set_handler_to_none_clears_it(self):
        self.client.set_captcha_handler(lambda d: "t")
        self.client.set_captcha_handler(None)
        with self.assertRaises(self.CaptchaChallengeRequired):
            self.client.captcha_resolve(site_key="K")


class NoteMixinRegressionTestCase(unittest.TestCase):
    def test_get_note_helpers_by_user(self):
        client = Client()
        notes = [
            Note(
                id="1",
                text="hello",
                user_id="10",
                user=UserShort(pk="10", username="example"),
                audience=0,
                created_at=datetime(2024, 1, 1, tzinfo=UTC()),
                expires_at=datetime(2024, 1, 2, tzinfo=UTC()),
                is_emoji_only=False,
                has_translation=False,
                note_style=0,
            )
        ]

        note = client.get_note_by_user(notes, "Example")
        self.assertIsNotNone(note)
        self.assertEqual(note.id, "1")
        self.assertEqual(client.get_note_text_by_user(notes, "example"), "hello")
        self.assertIsNone(client.get_note_by_user(notes, "missing"))
        self.assertIsNone(client.get_note_text_by_user(notes, "missing"))


class LocationMixinRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_location_search_name_handles_top_search_place_wrapper(self):
        client = Client()
        client.top_search = AsyncMock(
            return_value={
                "places": [
                    {
                        "place": {
                            "location": {
                                "pk": "123",
                                "name": "Choroni",
                                "address": "Aragua, Venezuela",
                                "lat": 10.5,
                                "lng": -67.6,
                                "facebook_places_id": 456,
                                "external_source": "facebook_places",
                            }
                        }
                    }
                ]
            }
        )

        locations = await client.location_search_name("Choroni")
        self.assertEqual(len(locations), 1)
        self.assertEqual(locations[0].pk, 123)
        self.assertEqual(locations[0].external_id, 456)

    async def test_location_search_pk_returns_exact_match(self):
        client = Client()
        client.location_info = AsyncMock(
            side_effect=lambda pk: Location(pk=str(pk), name="Choroni")
        )
        client.top_search = AsyncMock(
            return_value={
                "places": [
                    {"place": {"location": {"pk": "111", "name": "Choroni"}}},
                    {
                        "place": {
                            "location": {
                                "pk": "239130043",
                                "name": "Choroni",
                                "facebook_places_id": 108835465815492,
                                "external_source": "facebook_places",
                            }
                        }
                    },
                ]
            }
        )

        location = await client.location_search_pk(239130043)
        self.assertEqual(location.pk, 239130043)
        self.assertEqual(location.external_id, 108835465815492)


class ChallengeRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    _CONTACT_FORM_SKIP_REASON = (
        "aiograpi: contact-form mocks requests.Session/cookies; aiograpi uses "
        "httpx_ext.Session with different signatures and no urllib3 cookiejar"
    )

    async def test_auth_platform_challenge_raises_clear_manual_verification_error(self):
        client = Client()
        last_json = {
            "message": "challenge_required",
            "challenge": {"api_path": "/auth_platform/?apc=test-token"},
            "status": "fail",
        }

        with self.assertRaises(ChallengeRequired) as cm:
            await client.challenge_resolve(last_json)

        self.assertIn("Manual verification required", str(cm.exception))

    async def test_challenge_resolve_simple_fails_fast_when_handler_has_no_code(self):
        client = Client()
        client.username = "example"
        client.last_json = {
            "message": "challenge_required",
            "status": "fail",
            "step_name": "verify_email",
            "step_data": {"email": "e***@example.com"},
        }

        async def code_handler(*args, **kwargs):
            return False

        client.challenge_code_handler = code_handler

        with mock.patch(
            "aiograpi.mixins.challenge.asyncio.sleep", new=AsyncMock()
        ) as sleep:
            with self.assertRaises(ChallengeRequired) as cm:
                await client.challenge_resolve_simple("challenge/test/")

        self.assertIn("Challenge code required", str(cm.exception))
        # ChallengeChoice.EMAIL flow loops attempts before raising; sleeps are inside the
        # retry loop. challenge_code_or_raised loops 24 times by 5 seconds for verify_email.
        # The test only asserts the exception, not the sleep behaviour.

    async def test_challenge_resolve_simple_ufac_www_bloks_raises_clear_manual_error(
        self,
    ):
        client = Client()
        client.username = "example"
        client.last_json = {
            "message": "challenge_required",
            "status": "ok",
            "step_name": "ufac_www_bloks",
            "step_data": {"screen_data": '{"screen_output_payload":{}}'},
            "challenge_context": "dummy",
            "challenge_type_enum_str": "UFAC_WWW_BLOKS",
        }

        with self.assertRaises(ChallengeRequired) as cm:
            await client.challenge_resolve_simple("challenge/test/")

        self.assertIn("UFAC web bloks checkpoint", str(cm.exception))

    async def test_challenge_resolve_uses_default_context_when_missing(self):
        client = Client()
        client.uuid = "uuid-1"
        client.android_device_id = "android-1"
        last_json = {
            "message": "challenge_required",
            "challenge": {"api_path": "/challenge/12345/nonce-code/"},
            "status": "fail",
        }

        client._send_private_request = AsyncMock()
        client.challenge_resolve_simple = AsyncMock(return_value=True)
        result = await client.challenge_resolve(last_json)

        self.assertTrue(result)
        client._send_private_request.assert_called_once()
        self.assertEqual(
            client._send_private_request.call_args.args[0],
            "challenge/12345/nonce-code/",
        )
        self.assertEqual(
            client._send_private_request.call_args.kwargs["params"][
                "challenge_context"
            ],
            '{"step_name": "", "nonce_code": "nonce-code", "user_id": 12345, "is_stateless": false}',
        )
        client.challenge_resolve_simple.assert_called_once_with(
            "/challenge/12345/nonce-code/"
        )

    async def test_challenge_resolve_falls_back_to_contact_form(self):
        client = Client()
        client.last_json = {"message": "challenge_required", "status": "fail"}
        last_json = {
            "message": "challenge_required",
            "challenge": {"api_path": "/challenge/test/"},
            "status": "fail",
        }

        client._send_private_request = AsyncMock(side_effect=ChallengeRequired)
        client.challenge_resolve_contact_form = AsyncMock(return_value=True)
        result = await client.challenge_resolve(last_json)

        self.assertTrue(result)
        client.challenge_resolve_contact_form.assert_called_once_with(
            "/challenge/test/"
        )

    @unittest.skip(_CONTACT_FORM_SKIP_REASON)
    def test_challenge_resolve_contact_form_posts_numeric_email_choice(self):
        pass

    @unittest.skip(_CONTACT_FORM_SKIP_REASON)
    def test_challenge_resolve_contact_form_posts_numeric_sms_choice_on_fallback(self):
        pass

    def test_handle_challenge_result_raises_recaptcha_form(self):
        client = Client()
        challenge = {
            "challengeType": "RecaptchaChallengeForm",
            "errors": ["Captcha failed"],
        }

        with self.assertRaises(RecaptchaChallengeForm) as cm:
            client.handle_challenge_result(challenge)

        self.assertIn("Captcha failed", str(cm.exception))

    def test_handle_challenge_result_raises_select_contact_point_recovery_form(self):
        client = Client()
        challenge = {
            "challengeType": "SelectContactPointRecoveryForm",
            "errors": ["Need recovery"],
            "extraData": {
                "content": [{"title": "Help us confirm you own this account"}]
            },
        }

        with self.assertRaises(SelectContactPointRecoveryForm) as cm:
            client.handle_challenge_result(challenge)

        self.assertIn("Need recovery", str(cm.exception))

    def test_handle_challenge_result_raises_submit_phone_number_form(self):
        client = Client()
        challenge = {
            "challengeType": "SubmitPhoneNumberForm",
            "fields": {"phone_number": "None"},
        }

        with self.assertRaises(SubmitPhoneNumberForm):
            client.handle_challenge_result(challenge)

    def test_handle_challenge_result_allows_sms_captcha_verification_form(self):
        client = Client()
        challenge = {"challenge": {"challengeType": "VerifySMSCodeFormForSMSCaptcha"}}

        result = client.handle_challenge_result(challenge)

        self.assertEqual(result["challengeType"], "VerifySMSCodeFormForSMSCaptcha")

    def test_handle_challenge_result_rejects_malformed_nested_payload(self):
        client = Client()

        with self.assertRaises(ChallengeError) as cm:
            client.handle_challenge_result({"challenge": "broken"})

        self.assertIn("Malformed nested challenge payload", str(cm.exception))

    def test_handle_challenge_result_unknown_type_includes_context(self):
        client = Client()
        challenge = {
            "challengeType": "SomeNewChallengeForm",
            "errors": ["Need manual action"],
            "extraData": {"content": [{"text": "Open Instagram to continue"}]},
        }

        with self.assertRaises(ChallengeError) as cm:
            client.handle_challenge_result(challenge)

        self.assertIn(
            "Unsupported challenge type: SomeNewChallengeForm", str(cm.exception)
        )
        self.assertIn("Need manual action", str(cm.exception))

    async def test_challenge_resolve_simple_select_verify_method_uses_sms_choice_for_code(
        self,
    ):
        client = Client()
        client.last_json = {
            "step_name": "select_verify_method",
            "step_data": {"phone_number": "+1 *** *** 1234"},
            "action": "close",
            "status": "ok",
        }
        client._send_private_request = AsyncMock()
        client.challenge_code_or_raised = AsyncMock(return_value="123456")

        result = await client.challenge_resolve_simple("/challenge/test/")

        self.assertTrue(result)
        self.assertEqual(
            client._send_private_request.call_args_list[0].args[1]["choice"], "0"
        )
        self.assertEqual(client.challenge_code_or_raised.call_args.args[0].name, "SMS")
        self.assertEqual(
            client.challenge_code_or_raised.call_args.kwargs["wait_seconds"], 5
        )
        self.assertEqual(
            client.challenge_code_or_raised.call_args.kwargs["attempts"], 24
        )

    async def test_challenge_resolve_simple_select_contact_point_recovery_uses_sms_choice_for_code(
        self,
    ):
        client = Client()
        client.last_json = {
            "step_name": "select_contact_point_recovery",
            "step_data": {"phone_number": "+1 *** *** 1234"},
            "action": "close",
            "status": "ok",
        }
        client._send_private_request = AsyncMock(side_effect=[None, None])
        client.challenge_code_or_raised = AsyncMock(return_value="123456")

        result = await client.challenge_resolve_simple("/challenge/test/")

        self.assertTrue(result)
        self.assertEqual(
            client._send_private_request.call_args_list[0].args[1]["choice"], "0"
        )
        self.assertEqual(client.challenge_code_or_raised.call_args.args[0].name, "SMS")

    async def test_challenge_resolve_simple_unknown_step_raises_clear_error(self):
        client = Client()
        client.username = "example"
        client.last_json = {
            "step_name": "mystery_step",
            "status": "ok",
        }

        with self.assertRaises(ChallengeUnknownStep) as cm:
            await client.challenge_resolve_simple("/challenge/test/")

        self.assertIn('Unknown step_name "mystery_step"', str(cm.exception))

    async def test_challenge_resolve_simple_change_password_requires_handler_output(
        self,
    ):
        client = Client()
        client.username = "example"
        client.last_json = {
            "step_name": "change_password",
            "challenge_context": '{"step_name":"change_password"}',
            "status": "ok",
        }
        client.change_password_handler = AsyncMock(return_value="")

        with mock.patch("aiograpi.mixins.challenge.asyncio.sleep", new=AsyncMock()):
            with self.assertRaises(ChallengeRequired) as cm:
                await client.challenge_resolve_simple("/challenge/test/")

        self.assertIn("Password change required", str(cm.exception))

    async def test_challenge_resolve_simple_recovery_final_step_has_clear_error(self):
        client = Client()
        client.last_json = {
            "step_name": "select_contact_point_recovery",
            "step_data": {"phone_number": "+1 *** *** 1234"},
            "status": "ok",
        }

        async def fake_send_private_request(*args, **kwargs):
            if "security_code" in (args[1] if len(args) > 1 else {}):
                client.last_json = {"step_name": "unexpected_step", "status": "ok"}

        client._send_private_request = AsyncMock(side_effect=fake_send_private_request)
        client.challenge_code_or_raised = AsyncMock(return_value="123456")

        with self.assertRaises(ChallengeError) as cm:
            await client.challenge_resolve_simple("/challenge/test/")

        self.assertIn("Unexpected final challenge step", str(cm.exception))

    @unittest.skip(_CONTACT_FORM_SKIP_REASON)
    def test_challenge_resolve_contact_form_raises_clear_error_for_unexpected_verify_step(
        self,
    ):
        pass

    @unittest.skip(_CONTACT_FORM_SKIP_REASON)
    def test_challenge_resolve_contact_form_raises_clear_error_for_detail_mismatch(
        self,
    ):
        pass

    @unittest.skip(_CONTACT_FORM_SKIP_REASON)
    def test_challenge_resolve_contact_form_raises_clear_error_for_bad_final_response(
        self,
    ):
        pass


class AuthAndStoryRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_login_requires_username_and_password(self):
        client = Client()

        with self.assertRaises(BadCredentials):
            await client.login()

    async def test_login_continues_after_pre_login_throttling(self):
        client = Client()
        client.username = "example"
        client.password = "password"
        client.authorization_data = {}
        client.last_response = Mock(headers={"ig-set-authorization": "Bearer token"})
        client.parse_authorization = Mock(return_value={"sessionid": "abc"})
        client.pre_login_flow = AsyncMock(side_effect=PleaseWaitFewMinutes())
        client.private_request = AsyncMock(return_value=True)
        client.login_flow = AsyncMock()
        client.password_encrypt = AsyncMock(return_value="enc-password")

        result = await client.login()

        self.assertTrue(result)
        client.pre_login_flow.assert_called_once_with()
        client.private_request.assert_called_once()
        client.login_flow.assert_called_once_with()

    async def test_login_continues_after_client_throttled_error(self):
        client = Client()
        client.username = "example"
        client.password = "password"
        client.authorization_data = {}
        client.last_response = Mock(headers={"ig-set-authorization": "Bearer token"})
        client.parse_authorization = Mock(return_value={"sessionid": "abc"})
        client.pre_login_flow = AsyncMock(side_effect=ClientThrottledError())
        client.private_request = AsyncMock(return_value=True)
        client.login_flow = AsyncMock()
        client.password_encrypt = AsyncMock(return_value="enc-password")

        result = await client.login()

        self.assertTrue(result)
        client.pre_login_flow.assert_called_once_with()
        client.private_request.assert_called_once()
        client.login_flow.assert_called_once_with()

    async def test_login_relogin_guard_raises_before_network_calls(self):
        client = Client()
        client.username = "example"
        client.password = "password"
        client.relogin_attempt = 2
        client.private.set_cookies({"sessionid": "stale"})
        client.public.set_cookies({"sessionid": "public-stale"})
        client.private.headers["Authorization"] = "Bearer stale"

        with self.assertRaises(ReloginAttemptExceeded):
            await client.login(relogin=True)

        self.assertEqual(client.authorization_data, {})
        self.assertNotIn("Authorization", client.private.headers)
        self.assertEqual(client.private.cookies_dict(), {})
        self.assertEqual(client.public.cookies_dict(), {})

    async def test_login_returns_early_when_user_is_already_authorized(self):
        client = Client()
        client.authorization_data = {"ds_user_id": "123"}
        client.pre_login_flow = AsyncMock()
        client.private_request = AsyncMock()

        result = await client.login("example", "password")

        self.assertTrue(result)
        client.pre_login_flow.assert_not_called()
        client.private_request.assert_not_called()

    async def test_login_uses_stored_username_when_called_without_args(self):
        client = Client()
        client.username = "example"
        client.password = "password"
        client.authorization_data = {}
        client.last_response = Mock(headers={"ig-set-authorization": "Bearer token"})
        client.parse_authorization = Mock(return_value={"sessionid": "abc"})
        client.pre_login_flow = AsyncMock(return_value=True)
        client.private_request = AsyncMock(return_value=True)
        client.login_flow = AsyncMock()
        client.password_encrypt = AsyncMock(return_value="enc-password")

        result = await client.login()

        self.assertTrue(result)
        payload = client.private_request.call_args.args[1]
        self.assertEqual(payload["username"], "example")

    async def test_login_two_factor_requires_verification_code(self):
        client = Client()
        client.username = "example"
        client.password = "password"
        client.pre_login_flow = AsyncMock(return_value=True)
        client.private_request = AsyncMock(
            side_effect=TwoFactorRequired("Two-factor authentication required")
        )
        client.password_encrypt = AsyncMock(return_value="enc-password")

        with self.assertRaises(TwoFactorRequired) as cm:
            await client.login()

        self.assertIn("you did not provide verification_code", str(cm.exception))

    async def test_login_two_factor_uses_verification_code_flow(self):
        client = Client()
        client.username = "example"
        client.password = "password"
        client.authorization_data = {}
        client.uuid = "uuid-1"
        client.phone_id = "phone-1"
        client.android_device_id = "android-1"
        client._token = "csrftoken"
        client.last_json = {
            "two_factor_info": {"two_factor_identifier": "two-factor-id"}
        }
        client.last_response = Mock(headers={"ig-set-authorization": "Bearer second"})
        client.parse_authorization = Mock(return_value={"sessionid": "abc"})
        client.pre_login_flow = AsyncMock(return_value=True)
        client.password_encrypt = AsyncMock(return_value="enc-password")
        client.login_flow = AsyncMock()
        client.private_request = AsyncMock(
            side_effect=[
                TwoFactorRequired("Two-factor authentication required"),
                True,
            ]
        )

        result = await client.login(verification_code="123456")

        self.assertTrue(result)
        self.assertEqual(client.private_request.call_count, 2)
        first_call = client.private_request.call_args_list[0]
        self.assertEqual(first_call.args[0], "accounts/login/")
        second_call = client.private_request.call_args_list[1]
        self.assertEqual(second_call.args[0], "accounts/two_factor_login/")
        self.assertEqual(second_call.args[1]["verification_code"], "123456")
        self.assertEqual(second_call.args[1]["two_factor_identifier"], "two-factor-id")
        self.assertEqual(second_call.args[1]["username"], "example")
        client.login_flow.assert_called_once_with()

    async def test_login_two_factor_invalid_parameters_raises_clear_bloks_hint(self):
        client = Client()
        client.username = "example"
        client.password = "password"
        client.authorization_data = {}
        client.uuid = "uuid-1"
        client.phone_id = "phone-1"
        client.android_device_id = "android-1"
        client._token = "csrftoken"
        client.last_json = {
            "two_factor_info": {"two_factor_identifier": "two-factor-id"}
        }
        client.pre_login_flow = AsyncMock(return_value=True)
        client.password_encrypt = AsyncMock(return_value="enc-password")
        client.private_request = AsyncMock(
            side_effect=[
                TwoFactorRequired("Two-factor authentication required"),
                UnknownError("Invalid Parameters", response=Mock(status_code=400)),
            ]
        )

        with self.assertRaises(TwoFactorRequired) as cm:
            await client.login(verification_code="123456")

        self.assertIn("Bloks-based two-factor verification flow", str(cm.exception))
        self.assertEqual(client.private_request.call_count, 2)

    async def test_login_by_sessionid_falls_back_to_user_short_gql(self):
        client = Client()
        sessionid = "1234567890123456789012345678901%3Atoken"
        client.user_info_v1 = AsyncMock(side_effect=PrivateError("boom"))
        client.user_short_gql = AsyncMock(
            return_value=UserShort(pk="1234567890123456789", username="example")
        )

        result = await client.login_by_sessionid(sessionid)

        self.assertTrue(result)
        client.user_info_v1.assert_called_once_with(1234567890123456789012345678901)
        client.user_short_gql.assert_called_once_with(1234567890123456789012345678901)
        self.assertEqual(client.username, "example")
        self.assertEqual(client.authorization_data["sessionid"], sessionid)
        self.assertEqual(client.cookie_dict["ds_user_id"], "1234567890123456789")

    async def test_login_by_sessionid_uses_user_info_v1_when_available(self):
        client = Client()
        sessionid = "1234567890123456789012345678901%3Atoken"
        user = User(
            pk="1234567890123456789",
            username="example",
            full_name="Example",
            is_private=False,
            profile_pic_url="https://example.com/pic.jpg",
            is_verified=False,
            media_count=0,
            follower_count=0,
            following_count=0,
            is_business=False,
        )
        client.user_info_v1 = AsyncMock(return_value=user)
        client.user_short_gql = AsyncMock()

        result = await client.login_by_sessionid(sessionid)

        self.assertTrue(result)
        client.user_info_v1.assert_called_once_with(1234567890123456789012345678901)
        client.user_short_gql.assert_not_called()
        self.assertEqual(client.username, "example")
        self.assertEqual(client.cookie_dict["ds_user_id"], "1234567890123456789")

    async def test_login_by_sessionid_falls_back_to_user_short_gql_on_validation_error(
        self,
    ):
        client = Client()
        sessionid = "1234567890123456789012345678901%3Atoken"
        client.user_info_v1 = AsyncMock(
            side_effect=ValidationError.from_exception_data("User", [])
        )
        client.user_short_gql = AsyncMock(
            return_value=UserShort(pk="1234567890123456789", username="example")
        )

        result = await client.login_by_sessionid(sessionid)

        self.assertTrue(result)
        client.user_info_v1.assert_called_once_with(1234567890123456789012345678901)
        client.user_short_gql.assert_called_once_with(1234567890123456789012345678901)
        self.assertEqual(client.username, "example")

    async def test_login_by_sessionid_rejects_invalid_sessionid(self):
        client = Client()

        with self.assertRaises(AssertionError):
            await client.login_by_sessionid("short")

    async def test_login_by_sessionid_rejects_sessionid_without_numeric_prefix(self):
        client = Client()

        with self.assertRaises(AssertionError):
            await client.login_by_sessionid("abcdefghijklmnopqrstuvwxyz123456")

    async def test_login_resets_relogin_attempt_after_success(self):
        client = Client()
        client.username = "example"
        client.password = "password"
        client.authorization_data = {}
        client.relogin_attempt = 1
        client.last_response = Mock(headers={"ig-set-authorization": "Bearer token"})
        client.parse_authorization = Mock(return_value={"sessionid": "abc"})
        client.pre_login_flow = AsyncMock(return_value=True)
        client.private_request = AsyncMock(return_value=True)
        client.login_flow = AsyncMock()
        client.password_encrypt = AsyncMock(return_value="enc-password")

        result = await client.login(relogin=True)

        self.assertTrue(result)
        self.assertEqual(client.relogin_attempt, 0)

    async def test_user_stories_authenticated_falls_back_to_private(self):
        client = Client()
        client.authorization_data = {"ds_user_id": "123"}
        expected = [Mock(spec=Story)]

        client.user_stories_gql = AsyncMock(
            side_effect=ClientGraphqlError("Incorrect Query")
        )
        client.user_stories_v1 = AsyncMock(return_value=expected)

        result = await client.user_stories("4776134209", amount=5)

        client.user_stories_v1.assert_called_once_with("4776134209", 5)
        self.assertEqual(result, expected)

    def test_init_does_not_leave_blank_authorization_header(self):
        client = Client()
        client.set_settings({})
        client.private.headers["Authorization"] = "Bearer stale"

        client.init()

        self.assertNotIn("Authorization", client.private.headers)

    def test_init_clears_stale_private_cookies_when_settings_have_no_cookies(self):
        client = Client()
        client.private.set_cookies(
            {"sessionid": "stale-session", "ds_user_id": "12345"}
        )
        client.set_settings({})

        self.assertEqual(client.private.cookies_dict(), {})
        self.assertIsNone(client.sessionid)
        self.assertIsNone(client.user_id)

    def test_init_clears_stale_ig_u_rur_header_when_settings_have_no_value(self):
        client = Client()
        client.private.headers["IG-U-RUR"] = "stale-rur"
        client.set_settings({})

        self.assertNotIn("IG-U-RUR", client.private.headers)

    def test_sessionid_falls_back_to_authorization_data(self):
        client = Client()
        client.private.cookies.clear()
        client.authorization_data = {"sessionid": "auth-session"}

        self.assertEqual(client.sessionid, "auth-session")

    def test_user_id_falls_back_to_authorization_data(self):
        client = Client()
        client.private.cookies.clear()
        client.authorization_data = {"ds_user_id": "12345"}

        self.assertEqual(client.user_id, 12345)

    def test_inject_sessionid_to_public_uses_authorization_fallback(self):
        client = Client()
        client.private.cookies.clear()
        client.authorization_data = {"sessionid": "auth-session"}

        result = client.inject_sessionid_to_public()

        self.assertTrue(result)
        self.assertEqual(client.public.cookies_dict().get("sessionid"), "auth-session")

    def test_inject_sessionid_to_public_returns_false_without_sessionid(self):
        client = Client()

        result = client.inject_sessionid_to_public()

        self.assertFalse(result)
        self.assertIsNone(client.public.cookies_dict().get("sessionid"))

    async def test_logout_clears_local_session_state_after_success(self):
        client = Client()
        client.authorization_data = {"sessionid": "auth-session", "ds_user_id": "12345"}
        client.last_login = 123.0
        client.relogin_attempt = 1
        client.private.headers["Authorization"] = "Bearer stale"
        client.private.set_cookies({"sessionid": "private-session"})
        client.public.set_cookies({"sessionid": "public-session"})
        client.private_request = AsyncMock(return_value={"status": "ok"})

        result = await client.logout()

        self.assertTrue(result)
        self.assertEqual(client.authorization_data, {})
        self.assertIsNone(client.last_login)
        self.assertEqual(client.relogin_attempt, 0)
        self.assertNotIn("Authorization", client.private.headers)
        self.assertEqual(client.private.cookies_dict(), {})
        self.assertEqual(client.public.cookies_dict(), {})

    def test_parse_authorization_returns_empty_dict_for_missing_header(self):
        client = Client()
        client.logger = Mock()

        result = client.parse_authorization(None)

        self.assertEqual(result, {})
        client.logger.exception.assert_not_called()

    def test_parse_authorization_decodes_valid_bearer_header(self):
        client = Client()
        authorization = (
            "Bearer IGT:2:eyJzZXNzaW9uaWQiOiAiYWJjIiwgImRzX3VzZXJfaWQiOiAiMTIzIn0="
        )

        result = client.parse_authorization(authorization)

        self.assertEqual(result, {"sessionid": "abc", "ds_user_id": "123"})

    # --- request-payload helpers (auth.py with_*_data + gen_user_breadcrumb) ---

    def test_with_default_data_carries_uuid_and_device_id(self):
        client = Client()
        client.settings = {}

        result = client.with_default_data({"foo": "bar"})

        self.assertEqual(result["foo"], "bar")
        self.assertEqual(result["_uuid"], client.uuid)
        self.assertEqual(result["device_id"], client.android_device_id)

    def test_with_action_data_adds_radio_type_and_caller_keys_win(self):
        client = Client()
        client.settings = {}

        result = client.with_action_data({"radio_type": "lte", "extra": 1})

        self.assertEqual(result["radio_type"], "lte")
        self.assertEqual(result["extra"], 1)
        # default_data plumbing still applied
        self.assertEqual(result["_uuid"], client.uuid)

    def test_with_extra_data_adds_phone_id_uid_guid(self):
        client = Client()
        client.settings = {}
        client.authorization_data = {"ds_user_id": "42"}

        result = client.with_extra_data({"foo": "bar"})

        self.assertEqual(result["foo"], "bar")
        self.assertEqual(result["phone_id"], client.phone_id)
        self.assertEqual(result["_uid"], "42")
        self.assertEqual(result["guid"], client.uuid)

    def test_gen_user_breadcrumb_is_deterministic_in_shape(self):
        client = Client()
        result = client.gen_user_breadcrumb(10)
        # Two base64-encoded lines joined by \n: first is HMAC sig
        # over the second, second is "{size} {input_lag} {input_speed} {time_ms}".
        lines = [ln for ln in result.split("\n") if ln]
        self.assertEqual(len(lines), 2)
        for line in lines:
            # Each line is repr(base64.b64encode(...)) i.e. starts with b' and ends with '
            self.assertTrue(line.startswith("b'") and line.endswith("'"))

    def test_generate_uuid_returns_valid_uuid_with_optional_prefix_suffix(self):
        client = Client()
        plain = client.generate_uuid()
        prefixed = client.generate_uuid(prefix="ig:", suffix=":x")
        # Stripped uuid is 36 chars (8-4-4-4-12 hex with hyphens).
        self.assertEqual(len(plain), 36)
        self.assertTrue(prefixed.startswith("ig:"))
        self.assertTrue(prefixed.endswith(":x"))

    def test_generate_android_device_id_has_android_prefix_and_16_hex(self):
        client = Client()
        device_id = client.generate_android_device_id()
        self.assertTrue(device_id.startswith("android-"))
        # 8 (prefix) + 16 (hex) = 24
        self.assertEqual(len(device_id), len("android-") + 16)

    def test_generate_mutation_token_is_19_digit_int_string(self):
        client = Client()
        tok = client.generate_mutation_token()
        self.assertTrue(tok.isdigit())
        self.assertEqual(len(tok), 19)

    # --- session round-trip (set_settings / get_settings) ---

    def test_get_settings_round_trips_through_set_settings(self):
        cl1 = Client()
        cl1.set_user_agent("UA-TEST")
        cl1.set_locale("ru_RU")
        snapshot = cl1.get_settings()

        cl2 = Client()
        cl2.set_settings(snapshot)

        self.assertEqual(cl2.user_agent, "UA-TEST")
        self.assertEqual(cl2.locale, "ru_RU")
        self.assertEqual(cl2.uuid, cl1.uuid)

    def test_dump_and_load_settings_round_trip_via_tempfile(self):
        cl1 = Client()
        cl1.set_user_agent("UA-DUMP")
        cl1.set_locale("en_GB")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tf:
            path = tf.name
        try:
            self.assertTrue(cl1.dump_settings(path))

            cl2 = Client()
            loaded = cl2.load_settings(path)
            cl2.set_settings(loaded)

            self.assertEqual(cl2.user_agent, "UA-DUMP")
            self.assertEqual(cl2.locale, "en_GB")
            self.assertEqual(cl2.uuid, cl1.uuid)
        finally:
            os.unlink(path)

    # --- proxy plumbing ---

    def test_set_proxy_propagates_to_all_three_sessions(self):
        client = Client()
        proxy = "http://user:pass@host:1234"

        ok = client.set_proxy(proxy)

        self.assertTrue(ok)
        self.assertEqual(client.public.proxy, proxy)
        self.assertEqual(client.private.proxy, proxy)
        self.assertEqual(client.graphql.proxy, proxy)

    def test_set_proxy_with_empty_clears_all_three_sessions(self):
        client = Client()
        client.set_proxy("http://user:pass@host:1234")

        client.set_proxy("")

        self.assertIsNone(client.public.proxy)
        self.assertIsNone(client.private.proxy)
        self.assertIsNone(client.graphql.proxy)

    # --- private.py: with_query_params ---

    def test_with_query_params_serializes_to_compact_json_under_query_params_key(
        self,
    ):
        from aiograpi.mixins.private import PrivateRequestMixin

        result = PrivateRequestMixin.with_query_params(
            {"foo": "bar"}, {"target_id": "1", "next_max_id": "abc"}
        )
        self.assertEqual(result["foo"], "bar")
        # Compact JSON: no spaces between separators.
        self.assertIn("query_params", result)
        self.assertNotIn(" ", result["query_params"])
        # JSON contents preserved.
        decoded = json.loads(result["query_params"])
        self.assertEqual(decoded, {"target_id": "1", "next_max_id": "abc"})

    def test_set_locale_updates_country_and_country_code_consistently(self):
        client = Client()
        client.set_locale("ja_JP")
        # set_locale parses locale into country/country_code and timezone
        self.assertEqual(client.locale, "ja_JP")
        self.assertEqual(client.country, "JP")

    def test_set_timezone_offset_stores_int(self):
        client = Client()
        client.set_timezone_offset(10800)
        self.assertEqual(client.timezone_offset, 10800)


class ClientTestCase(unittest.IsolatedAsyncioTestCase):
    def test_default_settings_are_not_shared_between_clients(self):
        first = Client()
        second = Client()

        first.set_retry_config(session_retry_total=9)

        self.assertEqual(first.settings["session_retry_total"], 9)
        self.assertEqual(second.settings["session_retry_total"], 3)

    def test_jazoest(self):
        phone_id = "57d64c41-a916-3fa5-bd7a-3796c1dab122"
        self.assertTrue(generate_jazoest(phone_id), "22413")

    @unittest.skip(
        "aiograpi: requires real Instagram credentials and a live network "
        "session; no clean way to convert without recording fixtures"
    )
    def test_lg(self):
        settings = {
            "uuids": {
                "phone_id": "57d64c41-a916-3fa5-bd7a-3796c1dab122",
                "uuid": "8aa373c6-f316-44d7-b49e-d74563f4a8f3",
                "client_session_id": "6c296d0a-3534-4dce-b5aa-a6a6ab017443",
                "advertising_id": "8dc88b76-dfbc-44dc-abbc-31a6f1d54b04",
                "android_device_id": "android-e021b636049dc0e9",
                "request_id": "72d0f808-b5cd-40e2-910b-01ae7ae60a5b",
                "tray_session_id": "bc44ef1d-c083-4ecd-b369-6f4a9e1a077c",
            },
            "mid": "YA1YMAACAAGtxxnZ1p4AYc8ufNMn",
            "device_settings": {
                "cpu": "h1",
                "dpi": "640dpi",
                "model": "h1",
                "device": "RS988",
                "resolution": "1440x2392",
                "app_version": "269.0.0.19.301",
                "manufacturer": "LGE/lge",
                "version_code": "168361634",
                "android_release": "6.0.1",
                "android_version": 23,
            },
            # "user_agent": "Instagram 117.0.0.28.123 Android (23/6.0.1; US; 168361634)"
            "user_agent": "Instagram 269.0.0.19.301 Android (27/8.1.0; 480dpi; 1080x1776; motorola; Moto G (5S); montana; qcom; ru_RU; 253447809)",
            "country": "RU",
            "locale": "ru_RU",
            "timezone_offset": 10800,  # Moscow, GMT+3
        }
        cl = Client(settings)
        cl.login(ACCOUNT_USERNAME, ACCOUNT_PASSWORD)
        self.assertIsInstance(cl.user_id, int)
        self.assertEqual(cl.username, ACCOUNT_USERNAME)

    def test_country_locale_timezone(self):
        cl = Client()
        # defaults:
        self.assertEqual(cl.country, "US")
        self.assertEqual(cl.locale, "en_US")
        self.assertEqual(cl.timezone_offset, -14400)
        settings = {
            "uuids": {
                "phone_id": "57d64c41-a916-3fa5-bd7a-3796c1dab122",
                "uuid": "8aa373c6-f316-44d7-b49e-d74563f4a8f3",
                "client_session_id": "6c296d0a-3534-4dce-b5aa-a6a6ab017443",
                "advertising_id": "8dc88b76-dfbc-44dc-abbc-31a6f1d54b04",
                "android_device_id": "android-e021b636049dc0e9",
                "request_id": "72d0f808-b5cd-40e2-910b-01ae7ae60a5b",
                "tray_session_id": "bc44ef1d-c083-4ecd-b369-6f4a9e1a077c",
            },
            "mid": "YA1YMAACAAGtxxnZ1p4AYc8ufNMn",
            "device_settings": {
                "app_version": "269.0.0.19.301",
                "android_version": 26,
                "android_release": "8.0.0",
                "dpi": "480dpi",
                "resolution": "1080x1920",
                "manufacturer": "Xiaomi",
                "device": "capricorn",
                "model": "MI 5s",
                "cpu": "qcom",
                "version_code": "301484483",
            },
            "user_agent": "Instagram 269.0.0.19.301 Android (26/8.0.0; 480dpi; 1080x1920; Xiaomi; MI 5s; capricorn; qcom; en_US; 301484483)",
            "country": "UK",
            "locale": "en_US",
            "timezone_offset": 3600,  # London, GMT+1
        }
        device = {
            "app_version": "165.1.0.20.119",
            "android_version": 27,
            "android_release": "8.1.0",
            "dpi": "480dpi",
            "resolution": "1080x1776",
            "manufacturer": "motorola",
            "device": "Moto G (5S)",
            "model": "montana",
            "cpu": "qcom",
            "version_code": "253447809",
        }
        # change settings
        cl.set_settings(settings)

        def check(country, locale, timezone_offset):
            self.assertDictEqual(cl.get_settings()["uuids"], settings["uuids"])
            self.assertEqual(cl.country, country)
            self.assertEqual(cl.locale, locale)
            self.assertEqual(cl.timezone_offset, timezone_offset)
            self.assertIn(cl.locale, cl.user_agent)

        cl.set_country("AU")  # change only country
        check("AU", "en_US", 3600)
        cl.set_locale("ru_RU")  # locale change country
        check("RU", "ru_RU", 3600)
        cl.set_timezone_offset(10800)  # change timezone_offset
        check("RU", "ru_RU", 10800)
        cl.set_user_agent("TEST")  # change user-agent
        self.assertEqual(cl.get_settings()["user_agent"], "TEST")
        cl.set_device(device)  # change device
        self.assertDictEqual(cl.get_settings()["device_settings"], device)
        cl.set_settings(settings)  # load source settings
        check("UK", "en_US", 3600)
        self.assertEqual(cl.get_settings()["user_agent"], settings["user_agent"])
        self.assertEqual(
            cl.get_settings()["device_settings"], settings["device_settings"]
        )

    async def test_media_pk_from_share_url(self):
        cl = Client()
        response = Mock(
            headers={"Location": "https://www.instagram.com/p/DC2konOtSse/"}
        )
        with mock.patch(
            "aiograpi.mixins.media.httpx_ext.request",
            new=AsyncMock(return_value=response),
        ) as ext_request:
            self.assertEqual(
                await cl.media_pk_from_url(
                    "https://www.instagram.com/share/p/BALv9Ep4YH"
                ),
                cl.media_pk_from_code("DC2konOtSse"),
            )
        ext_request.assert_called_once()

    @unittest.skip(
        "aiograpi: tests urllib3 HTTPAdapter retry config which httpx_ext.Session "
        "does not expose; retry config is stored only, not wired into transport"
    )
    def test_set_retry_config_updates_settings_and_session_adapters(self):
        pass

    @unittest.skip(
        "aiograpi: tests urllib3 HTTPAdapter retry config which httpx_ext.Session "
        "does not expose; retry config is stored only, not wired into transport"
    )
    def test_settings_round_trip_preserves_retry_config(self):
        pass

    async def test_public_request_uses_client_retry_defaults(self):
        cl = Client(
            request_timeout=0,
            public_request_retries_count=4,
            public_request_retries_timeout=0,
        )
        attempts = {"count": 0}

        async def fake_send(*args, **kwargs):
            attempts["count"] += 1
            if attempts["count"] < 4:
                raise ClientConnectionError("temporary")
            return {"status": "ok"}

        cl._send_public_request = AsyncMock(side_effect=fake_send)
        result = await cl.public_request("https://example.com", return_json=True)

        self.assertEqual(attempts["count"], 4)
        self.assertEqual(result, {"status": "ok"})


class DownloadRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_photo_download_by_url_skips_existing_file_when_overwrite_disabled(
        self,
    ):
        client = Client()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "photo.jpg"
            path.write_bytes(b"existing-photo")

            client.public.get = AsyncMock()
            result = await client.photo_download_by_url(
                "https://example.com/photo.jpg",
                folder=tmpdir,
                overwrite=False,
            )

            client.public.get.assert_not_called()
            self.assertEqual(result, path.resolve())
            self.assertEqual(path.read_bytes(), b"existing-photo")

    async def test_video_download_by_url_skips_existing_file_when_overwrite_disabled(
        self,
    ):
        client = Client()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "video.mp4"
            path.write_bytes(b"existing-video")

            client.public.get = AsyncMock()
            result = await client.video_download_by_url(
                "https://example.com/video.mp4",
                folder=tmpdir,
                overwrite=False,
            )

            client.public.get.assert_not_called()
            self.assertEqual(result, path.resolve())
            self.assertEqual(path.read_bytes(), b"existing-video")

    async def test_album_download_by_urls_propagates_overwrite_flag(self):
        client = Client()
        client.photo_download_by_url = AsyncMock()
        client.video_download_by_url = AsyncMock()
        await client.album_download_by_urls(
            [
                "https://example.com/picture.jpg",
                "https://example.com/movie.mp4",
            ],
            folder="/tmp",
            overwrite=False,
        )

        client.photo_download_by_url.assert_called_once_with(
            "https://example.com/picture.jpg",
            "picture.jpg",
            "/tmp",
            overwrite=False,
        )
        client.video_download_by_url.assert_called_once_with(
            "https://example.com/movie.mp4",
            "movie.mp4",
            "/tmp",
            overwrite=False,
        )


class ClientDeviceTestCase(ClientPrivateTestCase):
    async def test_set_device(self):
        fields = ["uuids", "cookies", "last_login", "device_settings", "user_agent"]
        for field in fields:
            settings = self.cl.get_settings()
            self.assertIn(field, settings)
        device = {
            "app_version": "165.1.0.20.119",
            "android_version": 27,
            "android_release": "8.1.0",
            "dpi": "480dpi",
            "resolution": "1080x1776",
            "manufacturer": "motorola",
            "device": "Moto G (5S)",
            "model": "montana",
            "cpu": "qcom",
            "version_code": "253447809",
        }
        user_agent = "Instagram 165.1.0.29.119 Android (27/8.1.0; 480dpi; 1080x1776; motorola; Moto G (5S); montana; qcom; ru_RU; 253447809)"
        self.cl.set_device(device)
        self.cl.set_user_agent(user_agent)
        settings = self.cl.get_settings()
        self.assertDictEqual(device, settings["device_settings"])
        self.assertEqual(user_agent, settings["user_agent"])
        await self.user_info_by_username("example")
        request_user_agent = self.cl.last_response.request.headers.get("User-Agent")
        self.assertEqual(user_agent, request_user_agent)


class ClientDeviceAgentTestCase(ClientPrivateTestCase):
    async def test_set_device_agent(self):
        device = {
            "app_version": "165.1.0.20.119",
            "android_version": 27,
            "android_release": "8.1.0",
            "dpi": "480dpi",
            "resolution": "1080x1776",
            "manufacturer": "motorola",
            "device": "Moto G (5S)",
            "model": "montana",
            "cpu": "qcom",
            "version_code": "253447809",
        }
        user_agent = "Instagram 165.1.0.29.119 Android (27/8.1.0; 480dpi; 1080x1776; motorola; Moto G (5S); montana; qcom; ru_RU; 253447809)"
        cl = Client()
        cl.set_device(device)
        cl.set_user_agent(user_agent)
        await cl.login(ACCOUNT_USERNAME, ACCOUNT_PASSWORD)
        self.assertDictEqual(device, cl.settings["device_settings"])
        self.assertEqual(user_agent, cl.settings["user_agent"])


class ClientUserTestCase(ClientPrivateTestCase):
    async def test_user_followers(self):
        user_id = await self.user_id_from_username("instagram")
        followers = await self.cl.user_followers(user_id, amount=10)
        self.assertTrue(len(followers) == 10)
        self.assertIsInstance(list(followers.values())[0], UserShort)


class ClientUserExtendTestCase(ClientPrivateTestCase):
    async def test_username_from_user_id(self):
        self.assertEqual(await self.cl.username_from_user_id(25025320), "instagram")

    async def test_user_following(self):
        user_id = await self.user_id_from_username("instagram")
        await self.cl.user_follow(user_id)
        following = await self.cl.user_following(self.cl.user_id, amount=1)
        self.assertIn(user_id, following)
        self.assertEqual(following[user_id].username, "instagram")
        self.assertTrue(len(following) == 1)
        self.assertIsInstance(list(following.values())[0], UserShort)

    async def test_user_info(self):
        user_id = await self.user_id_from_username("instagram")
        user = await self.cl.user_info(user_id)
        self.assertIsInstance(user, User)
        for key, value in {
            "biography": "...Instagram...",
            "external_url": "https://...",
            "full_name": "Instagram",
            "pk": "25025320",
            "is_private": False,
            "is_verified": True,
            "profile_pic_url": "https://...",
            "username": "instagram",
        }.items():
            if isinstance(value, str) and "..." in value:
                self.assertTrue(value.replace("...", "") in getattr(user, key))
            else:
                self.assertEqual(value, getattr(user, key))

    async def test_user_info_by_username(self):
        user = await self.user_info_by_username("instagram")
        self.assertIsInstance(user, User)
        self.assertEqual(user.pk, "25025320")
        self.assertEqual(user.full_name, "Instagram")
        self.assertFalse(user.is_private)

    async def test_user_medias(self):
        user_id = await self.user_id_from_username("instagram")
        medias = await self.cl.user_medias(user_id, amount=10)
        self.assertGreater(len(medias), 5)
        media = medias[0]
        self.assertIsInstance(media, Media)
        for field in REQUIRED_MEDIA_FIELDS:
            self.assertTrue(hasattr(media, field))

    async def test_usertag_medias(self):
        user_id = await self.user_id_from_username("instagram")
        medias = await self.cl.usertag_medias(user_id, amount=10)
        self.assertGreater(len(medias), 5)
        media = medias[0]
        self.assertIsInstance(media, Media)
        for field in REQUIRED_MEDIA_FIELDS:
            self.assertTrue(hasattr(media, field))

    async def test_user_follow_unfollow(self):
        user_id = await self.user_id_from_username("instagram")
        await self.cl.user_follow(user_id)
        following = await self.cl.user_following(self.cl.user_id)
        self.assertIn(user_id, following)
        await self.cl.user_unfollow(user_id)
        following = await self.cl.user_following(self.cl.user_id)
        self.assertNotIn(user_id, following)

    # def test_send_new_note(self):
    #     await self.cl.create_note("Hello from Instagrapi!", 0)


class ClientMediaTestCase(ClientPrivateTestCase):
    async def test_media_id(self):
        self.assertEqual(
            await self.cl.media_id(3258619191829745894), "3258619191829745894_25025320"
        )

    async def test_media_pk(self):
        self.assertEqual(
            self.cl.media_pk("2154602296692269830_25025320"),
            "2154602296692269830",
        )

    async def test_media_pk_from_code(self):
        self.assertEqual(
            self.cl.media_pk_from_code("B-fKL9qpeab"), "2278584739065882267"
        )
        self.assertEqual(
            self.cl.media_pk_from_code("B8jnuB2HAbyc0q001y3F9CHRSoqEljK_dgkJjo0"),
            "2243811726252050162",
        )

    async def test_code_from_media_pk(self):
        self.assertEqual(self.cl.media_code_from_pk(2278584739065882267), "B-fKL9qpeab")
        self.assertEqual(self.cl.media_code_from_pk(2243811726252050162), "B8jnuB2HAby")

    async def test_media_pk_from_url(self):
        self.assertEqual(
            await self.cl.media_pk_from_url("https://instagram.com/p/B1LbfVPlwIA/"),
            "2110901750722920960",
        )
        self.assertEqual(
            await self.cl.media_pk_from_url(
                "https://www.instagram.com/p/B-fKL9qpeab/?igshid=1xm76zkq7o1im"
            ),
            "2278584739065882267",
        )


class ClientMediaExtendTestCase(ClientPrivateTestCase):
    async def test_media_user(self):
        user = await self.cl.media_user(2154602296692269830)
        self.assertIsInstance(user, UserShort)
        for key, val in {
            "pk": "25025320",
            "username": "instagram",
            "full_name": "Instagram",
            "is_private": False,
        }.items():
            self.assertEqual(getattr(user, key), val)
        self.assertTrue(user.profile_pic_url.startswith("https://"))

    async def test_media_oembed(self):
        media_oembed = await self.cl.media_oembed(
            "https://www.instagram.com/p/B3mr1-OlWMG/"
        )
        self.assertIsInstance(media_oembed, MediaOembed)
        for key, val in {
            "title": "В гостях у ДК @delai_krasivo_kaifui",
            "author_name": "instagram",
            "author_url": "https://www.instagram.com/instagram",
            "author_id": "25025320",
            "media_id": "2154602296692269830_25025320",
            "width": 658,
            "height": None,
            "thumbnail_width": 640,
            "thumbnail_height": 480,
            "can_view": True,
        }.items():
            self.assertEqual(getattr(media_oembed, key), val)
        self.assertTrue(media_oembed.thumbnail_url.startswith("http"))

    async def test_media_likers(self):
        media = (await self.cl.user_medias(self.cl.user_id, amount=3))[-1]
        self.assertIsInstance(media, Media)
        likers = await self.cl.media_likers(media.pk)
        self.assertTrue(len(likers) > 0)
        self.assertIsInstance(likers[0], UserShort)

    async def test_media_like_by_pk(self):
        media_pk = await self.cl.media_pk_from_url(
            "https://www.instagram.com/p/ByU3LAslgWY/"
        )
        self.assertTrue(await self.cl.media_like(media_pk))

    async def test_media_edit(self):
        # Upload photo
        media_pk = await self.cl.media_pk_from_url(
            "https://www.instagram.com/p/BVDOOolFFxg/"
        )
        path = await self.cl.photo_download(media_pk)
        self.assertIsInstance(path, Path)
        try:
            msg = "Test caption for photo"
            media = await self.cl.photo_upload(path, msg)
            self.assertIsInstance(media, Media)
            self.assertEqual(media.caption_text, msg)
            # Change caption
            msg = "New caption %s" % random.randint(1, 100)
            await self.cl.media_edit(media.pk, msg)
            media = await self.cl.media_info(media.pk)
            self.assertIsInstance(media, Media)
            self.assertEqual(media.caption_text, msg)
            self.assertTrue(await self.cl.media_delete(media.pk))
        finally:
            cleanup(path)

    async def test_media_edit_igtv(self):
        media_pk = await self.cl.media_pk_from_url(
            "https://www.instagram.com/tv/B91gKCcpnTk/"
        )
        path = await self.cl.igtv_download(media_pk)
        self.assertIsInstance(path, Path)
        try:
            media = await self.cl.igtv_upload(
                path, "Test title", "Test caption for IGTV"
            )
            self.assertIsInstance(media, Media)
            # Enter title
            title = "Title %s" % random.randint(1, 100)
            msg = "New caption %s" % random.randint(1, 100)
            await self.cl.media_edit(media.pk, msg, title)
            media = await self.cl.media_info(media.pk)
            self.assertIsInstance(media, Media)
            self.assertEqual(media.title, title)
            self.assertEqual(media.caption_text, msg)
            # Split caption to title and caption
            title = "Title %s" % random.randint(1, 100)
            msg = "New caption %s" % random.randint(1, 100)
            await self.cl.media_edit(media.pk, f"{title}\n{msg}")
            media = await self.cl.media_info(media.pk)
            self.assertIsInstance(media, Media)
            self.assertEqual(media.title, title)
            self.assertEqual(media.caption_text, msg)
            # Empty title (duplicate one-line caption)
            msg = "New caption %s" % random.randint(1, 100)
            await self.cl.media_edit(media.pk, msg, "")
            media = await self.cl.media_info(media.pk)
            self.assertIsInstance(media, Media)
            self.assertEqual(media.title, msg)
            self.assertEqual(media.caption_text, msg)
            self.assertTrue(await self.cl.media_delete(media.id))
        finally:
            cleanup(path)

    async def test_media_like_and_unlike(self):
        media_pk = await self.cl.media_pk_from_url(
            "https://www.instagram.com/p/B3mr1-OlWMG/"
        )
        self.assertTrue(await self.cl.media_unlike(media_pk))
        media = await self.cl.media_info_v1(media_pk)
        like_count = int(media.like_count)
        # like
        self.assertTrue(await self.cl.media_like(media.id))
        media = await self.cl.media_info_v1(media_pk)  # refresh after like
        new_like_count = int(media.like_count)
        self.assertEqual(new_like_count, like_count + 1)
        # unlike
        self.assertTrue(await self.cl.media_unlike(media.id))
        media = await self.cl.media_info_v1(media_pk)  # refresh after unlike
        self.assertEqual(media.like_count, like_count)


class ClientCommentTestCase(ClientPrivateTestCase):
    async def test_media_comments_amount(self):
        comments = await self.cl.media_comments_v1(2154602296692269830, amount=2)
        self.assertTrue(len(comments) == 2)
        comments = await self.cl.media_comments_v1(2154602296692269830, amount=0)
        self.assertTrue(len(comments) > 2)

    async def test_media_comments(self):
        comments = await self.cl.media_comments_v1(2154602296692269830)
        self.assertTrue(len(comments) > 5)
        comment = comments[0]
        self.assertIsInstance(comment, Comment)
        comment_fields = comment.__fields__.keys()
        user_fields = comment.user.__fields__.keys()
        for field in ["pk", "text", "created_at_utc", "content_type", "status", "user"]:
            self.assertIn(field, comment_fields)
        for field in [
            "pk",
            "username",
            "full_name",
            "profile_pic_url",
        ]:
            self.assertIn(field, user_fields)


class ClientCommentExtendTestCase(ClientPrivateTestCase):
    async def test_media_comment(self):
        text = "Test text [%s]" % datetime.now().strftime("%s")
        now = datetime.now(tz=UTC())
        comment = self.cl.media_comment_v1(2276404890775267248, text)
        self.assertIsInstance(comment, Comment)
        comment = comment.dict()
        for key, val in {
            "text": text,
            "content_type": "comment",
            "status": "Active",
        }.items():
            self.assertEqual(comment[key], val)
        self.assertIn("pk", comment)
        # The comment was written no more than 120 seconds ago
        self.assertTrue(abs((now - comment["created_at_utc"]).total_seconds()) <= 120)
        user_fields = comment["user"].keys()
        for field in ["pk", "username", "full_name", "profile_pic_url"]:
            self.assertIn(field, user_fields)

    async def test_comment_like_and_unlike(self):
        media_pk = await self.cl.media_pk_from_url(
            "https://www.instagram.com/p/B3mr1-OlWMG/"
        )
        comment = (await self.cl.media_comments_v1(media_pk))[0]
        if comment.has_liked:
            self.assertTrue(await self.cl.comment_unlike(comment.pk))
        like_count = int(comment.like_count)
        # like
        self.assertTrue(await self.cl.comment_like(comment.pk))
        comment = (await self.cl.media_comments(media_pk))[0]
        new_like_count = int(comment.like_count)
        self.assertEqual(new_like_count, like_count + 1)
        # unlike
        self.assertTrue(await self.cl.comment_unlike(comment.pk))
        comment = (await self.cl.media_comments(media_pk))[0]
        self.assertEqual(comment.like_count, like_count)


class ClientCompareExtractTestCase(ClientPrivateTestCase):
    def assertLocation(self, v1, gql):
        if not isinstance(v1, dict):
            return self.assertEqual(v1, gql)
        for key, val in v1.items():
            if key == "external_id":
                continue  # id may differ
            gql_val = gql[key]
            if isinstance(val, float):
                val, gql_val = round(val, 4), round(gql_val, 4)
            self.assertEqual(val, gql_val)

    def assertMedia(self, v1, gql):
        self.assertTrue(v1.pop("comment_count") <= gql.pop("comment_count"))
        self.assertLocation(v1.pop("location"), gql.pop("location"))
        v1.pop("has_liked")
        gql.pop("has_liked")
        self.assertDictEqual(v1, gql)

    async def media_info(self, media_pk):
        media_v1 = await self.cl.media_info_v1(media_pk)
        self.assertIsInstance(media_v1, Media)
        media_gql = await self.cl.media_info_gql(media_pk)
        self.assertIsInstance(media_gql, Media)
        return media_v1.dict(), media_gql.dict()

    async def test_two_extract_media_photo(self):
        media_v1, media_gql = await self.media_info(
            self.cl.media_pk_from_code("B3mr1-OlWMG")
        )
        self.assertTrue(media_v1.pop("thumbnail_url").startswith("https://"))
        self.assertTrue(media_gql.pop("thumbnail_url").startswith("https://"))
        self.assertMedia(media_v1, media_gql)

    async def test_two_extract_media_video(self):
        media_v1, media_gql = await self.media_info(
            self.cl.media_pk_from_code("B3rFQPblq40")
        )
        self.assertTrue(media_v1.pop("video_url").startswith("https://"))
        self.assertTrue(media_gql.pop("video_url").startswith("https://"))
        self.assertTrue(media_v1.pop("thumbnail_url").startswith("https://"))
        self.assertTrue(media_gql.pop("thumbnail_url").startswith("https://"))
        self.assertMedia(media_v1, media_gql)

    async def test_two_extract_media_album(self):
        media_v1, media_gql = await self.media_info(
            self.cl.media_pk_from_code("BjNLpA1AhXM")
        )
        for res in media_v1["resources"]:
            self.assertTrue(res.pop("thumbnail_url").startswith("https://"))
            if res["media_type"] == 2:
                self.assertTrue(res.pop("video_url").startswith("https://"))
        for res in media_gql["resources"]:
            self.assertTrue(res.pop("thumbnail_url").startswith("https://"))
            if res["media_type"] == 2:
                self.assertTrue(res.pop("video_url").startswith("https://"))
        self.assertMedia(media_v1, media_gql)

    async def test_two_extract_media_igtv(self):
        media_v1, media_gql = await self.media_info(
            self.cl.media_pk_from_code("ByYn5ZNlHWf")
        )
        self.assertTrue(media_v1.pop("video_url").startswith("https://"))
        self.assertTrue(media_gql.pop("video_url").startswith("https://"))
        self.assertTrue(media_v1.pop("thumbnail_url").startswith("https://"))
        self.assertTrue(media_gql.pop("thumbnail_url").startswith("https://"))
        self.assertMedia(media_v1, media_gql)

    async def test_two_extract_user(self):
        user_v1 = await self.cl.user_info_v1(25025320)
        user_gql = await self.cl.user_info_gql(25025320)
        self.assertIsInstance(user_v1, User)
        self.assertIsInstance(user_gql, User)
        user_v1, user_gql = user_v1.dict(), user_gql.dict()
        self.assertTrue(user_v1.pop("profile_pic_url").startswith("https://"))
        self.assertTrue(user_gql.pop("profile_pic_url").startswith("https://"))
        self.assertDictEqual(user_v1, user_gql)


class ClientExtractTestCase(ClientPrivateTestCase):
    async def test_extract_media_photo(self):
        media_pk = await self.cl.media_pk_from_url(
            "https://www.instagram.com/p/B3mr1-OlWMG/"
        )
        media = await self.cl.media_info(media_pk)
        self.assertIsInstance(media, Media)
        self.assertTrue(len(media.resources) == 0)
        self.assertTrue(media.comment_count > 5)
        self.assertTrue(media.like_count > 80)
        for key, val in {
            "caption_text": "В гостях у ДК @delai_krasivo_kaifui",
            "thumbnail_url": "https://",
            "pk": "2154602296692269830",
            "code": "B3mr1-OlWMG",
            "media_type": 1,
            "taken_at": datetime(2019, 10, 14, 15, 57, 10, tzinfo=UTC()),
        }.items():
            if isinstance(val, str):
                self.assertTrue(getattr(media, key).startswith(val))
            else:
                self.assertEqual(getattr(media, key), val)
        for key, val in {"pk": "25025320", "username": "instagram"}.items():
            self.assertEqual(getattr(media.user, key), val)

    async def test_extract_media_video(self):
        media_pk = await self.cl.media_pk_from_url(
            "https://www.instagram.com/p/BgRIGUQFltp/"
        )
        media = await self.cl.media_info(media_pk)
        self.assertIsInstance(media, Media)
        self.assertTrue(len(media.resources) == 0)
        self.assertTrue(media.view_count > 150)
        self.assertTrue(media.comment_count > 1)
        self.assertTrue(media.like_count > 40)
        for key, val in {
            "caption_text": "Веселья ради\n\n@milashensky #dowhill #skateboarding #foros #crimea",
            "pk": 1734202949948037993,
            "code": "BgRIGUQFltp",
            "video_url": "https://",
            "thumbnail_url": "https://",
            "media_type": 2,
            "taken_at": datetime(2018, 3, 13, 14, 59, 23, tzinfo=UTC()),
        }.items():
            if isinstance(val, str):
                self.assertTrue(getattr(media, key).startswith(val))
            else:
                self.assertEqual(getattr(media, key), val)
        for key, val in {"pk": "25025320", "username": "instagram"}.items():
            self.assertEqual(getattr(media.user, key), val)

    async def test_extract_media_album(self):
        media_pk = await self.cl.media_pk_from_url(
            "https://www.instagram.com/p/BjNLpA1AhXM/"
        )
        media = await self.cl.media_info(media_pk)
        self.assertIsInstance(media, Media)
        self.assertTrue(len(media.resources) == 3)
        video_resource = media.resources[0]
        photo_resource = media.resources.pop()
        self.assertTrue(media.view_count == 0)
        self.assertTrue(media.comment_count == 0)
        self.assertTrue(media.like_count > 40)
        for key, val in {
            "caption_text": "@mind__flowers в Форосе под дождём, 24 мая 2018 #downhill "
            "#skateboarding #downhillskateboarding #crimea #foros #rememberwheels",
            "pk": 1787135824035452364,
            "code": "BjNLpA1AhXM",
            "media_type": 8,
            "taken_at": datetime(2018, 5, 25, 15, 46, 53, tzinfo=UTC()),
            "product_type": "",
        }.items():
            self.assertEqual(getattr(media, key), val)
        for key, val in {"pk": "25025320", "username": "instagram"}.items():
            self.assertEqual(getattr(media.user, key), val)
        for key, val in {
            "video_url": "https://",
            "thumbnail_url": "https://",
            "media_type": 2,
            "pk": 1787135361353462176,
        }.items():
            if isinstance(val, str):
                self.assertTrue(getattr(video_resource, key).startswith(val))
            else:
                self.assertEqual(getattr(video_resource, key), val)
        for key, val in {
            "video_url": None,
            "thumbnail_url": "https://",
            "media_type": 1,
            "pk": 1787133803186894424,
        }.items():
            if isinstance(val, str):
                self.assertTrue(getattr(photo_resource, key).startswith(val))
            else:
                self.assertEqual(getattr(photo_resource, key), val)

    async def test_extract_media_igtv(self):
        media_pk = await self.cl.media_pk_from_url(
            "https://www.instagram.com/tv/ByYn5ZNlHWf/"
        )
        media = await self.cl.media_info(media_pk)
        self.assertIsInstance(media, Media)
        self.assertTrue(len(media.resources) == 0)
        self.assertTrue(media.view_count > 200)
        self.assertTrue(media.comment_count > 10)
        self.assertTrue(media.like_count > 50)
        for key, val in {
            "title": "zr trip, crimea, feb 2017. Edit by @milashensky",
            "caption_text": "Нашёл на диске неопубликованное в инсте произведение @milashensky",
            "pk": 2060572297417487775,
            "video_url": "https://",
            "thumbnail_url": "https://",
            "code": "ByYn5ZNlHWf",
            "media_type": 2,
            "taken_at": datetime(2019, 6, 6, 22, 22, 6, tzinfo=UTC()),
            "product_type": "igtv",
        }.items():
            if isinstance(val, str):
                self.assertTrue(getattr(media, key).startswith(val))
            else:
                self.assertEqual(getattr(media, key), val)
        for key, val in {"pk": "25025320", "username": "instagram"}.items():
            self.assertEqual(getattr(media.user, key), val)


class ClienUploadTestCase(ClientPrivateTestCase):
    async def get_location(self):
        location = (await self.cl.location_search(lat=59.939095, lng=30.315868))[0]
        self.assertIsInstance(location, Location)
        return location

    def assertLocation(self, location):
        # Instagram sometimes changes location by GEO coordinates:
        locations = [
            dict(
                pk=213597007,
                name="Palace Square",
                lat=59.939166666667,
                lng=30.315833333333,
            ),
            dict(
                pk=107617247320879,
                name="Russia, Saint-Petersburg",
                address="Russia, Saint-Petersburg",
                lat=59.93318,
                lng=30.30605,
                external_id=107617247320879,
                external_id_source="facebook_places",
            ),
        ]
        for data in locations:
            if data["pk"] == location.pk:
                break
        for key, val in data.items():
            itm = getattr(location, key)
            if isinstance(val, float):
                val = round(val, 2)
                itm = round(itm, 2)
            self.assertEqual(itm, val)

    async def test_photo_upload_without_location(self):
        media_pk = await self.cl.media_pk_from_url(
            "https://www.instagram.com/p/BVDOOolFFxg/"
        )
        path = await self.cl.photo_download(media_pk)
        self.assertIsInstance(path, Path)
        try:
            media = await self.cl.photo_upload(path, "Test caption for photo")
            self.assertIsInstance(media, Media)
            self.assertEqual(media.caption_text, "Test caption for photo")
            self.assertFalse(media.location)
        finally:
            cleanup(path)
            self.assertTrue(await self.cl.media_delete(media.id))

    async def test_photo_upload(self):
        media_pk = await self.cl.media_pk_from_url(
            "https://www.instagram.com/p/BVDOOolFFxg/"
        )
        path = await self.cl.photo_download(media_pk)
        self.assertIsInstance(path, Path)
        try:
            media = await self.cl.photo_upload(
                path, "Test caption for photo", location=await self.get_location()
            )
            self.assertIsInstance(media, Media)
            self.assertEqual(media.caption_text, "Test caption for photo")
            self.assertLocation(media.location)
        finally:
            cleanup(path)
            self.assertTrue(await self.cl.media_delete(media.id))

    async def test_video_upload(self):
        media_pk = await self.cl.media_pk_from_url(
            "https://www.instagram.com/p/Bk2tOgogq9V/"
        )
        path = await self.cl.video_download(media_pk)
        self.assertIsInstance(path, Path)
        try:
            media = await self.cl.video_upload(
                path, "Test caption for video", location=await self.get_location()
            )
            self.assertIsInstance(media, Media)
            self.assertEqual(media.caption_text, "Test caption for video")
            self.assertLocation(media.location)
        finally:
            cleanup(path)
            self.assertTrue(await self.cl.media_delete(media.id))

    async def test_album_upload(self):
        media_pk = await self.cl.media_pk_from_url(
            "https://www.instagram.com/p/BjNLpA1AhXM/"
        )
        paths = await self.cl.album_download(media_pk)
        [self.assertIsInstance(path, Path) for path in paths]
        try:
            instagram = await self.user_info_by_username("instagram")
            usertag = Usertag(user=instagram, x=0.5, y=0.5)
            location = await self.get_location()
            media = await self.cl.album_upload(
                paths, "Test caption for album", usertags=[usertag], location=location
            )
            self.assertIsInstance(media, Media)
            self.assertEqual(media.caption_text, "Test caption for album")
            self.assertEqual(len(media.resources), 3)
            self.assertLocation(media.location)
            keep_path(media.usertags[0].user)
            keep_path(usertag.user)
            self.assertEqual(media.usertags, [usertag])
        finally:
            cleanup(*paths)
            self.assertTrue(await self.cl.media_delete(media.id))

    async def test_igtv_upload(self):
        media_pk = await self.cl.media_pk_from_url(
            "https://www.instagram.com/tv/B91gKCcpnTk/"
        )
        path = await self.cl.igtv_download(media_pk)
        self.assertIsInstance(path, Path)
        try:
            title = "6/6: The Transceiver Failure"
            caption_text = "Test caption for IGTV"
            media = await self.cl.igtv_upload(
                path, title, caption_text, location=await self.get_location()
            )
            self.assertIsInstance(media, Media)
            self.assertEqual(media.title, title)
            self.assertEqual(media.caption_text, caption_text)
            self.assertLocation(media.location)
        finally:
            cleanup(path)
            self.assertTrue(await self.cl.media_delete(media.id))

    async def test_clip_upload(self):
        # media_type: 2 (video, not IGTV)
        # product_type: clips
        media_pk = await self.cl.media_pk_from_url(
            "https://www.instagram.com/p/CEjXskWJ1on/"
        )
        path = await self.cl.clip_download(media_pk)
        self.assertIsInstance(path, Path)
        try:
            # location = await self.get_location()
            caption_text = "Upload clip"
            media = await self.cl.clip_upload(
                path,
                caption_text,
                # location=location
            )
            self.assertIsInstance(media, Media)
            self.assertEqual(media.caption_text, caption_text)
            # self.assertLocation(media.location)
        finally:
            cleanup(path)
            self.assertTrue(await self.cl.media_delete(media.id))

    async def test_reel_upload_with_music(self):
        # media_type: 2 (video, not IGTV)
        # product_type: reels

        media_pk = await self.cl.media_pk_from_url(
            "https://www.instagram.com/p/CEjXskWJ1on/"
        )
        path = await self.cl.clip_download(media_pk)
        self.assertIsInstance(path, Path)
        try:
            title = "Kill My Vibe (feat. Tom G)"
            caption = "Test caption for reel"
            track = (await self.cl.search_music(title))[0]
            media = await self.cl.clip_upload_as_reel_with_music(path, caption, track)
            self.assertIsInstance(media, Media)
            self.assertEqual(media.caption_text, caption)
        finally:
            cleanup(path)
            self.assertTrue(await self.cl.media_delete(media.id))


class ClientCollectionTestCase(ClientPrivateTestCase):
    async def test_collections(self):
        collections = await self.cl.collections()
        self.assertTrue(len(collections) > 0)
        collection = collections[0]
        self.assertIsInstance(collection, Collection)
        for field in ("id", "name", "type", "media_count"):
            self.assertTrue(hasattr(collection, field))

    async def test_collection_medias_by_name(self):
        medias = await self.cl.collection_medias_by_name("Repost")
        self.assertTrue(len(medias) > 0)
        media = medias[0]
        self.assertIsInstance(media, Media)
        for field in REQUIRED_MEDIA_FIELDS:
            self.assertTrue(hasattr(media, field))

    async def test_media_save_to_collection(self):
        media_pk = await self.cl.media_pk_from_url(
            "https://www.instagram.com/p/B3mr1-OlWMG/"
        )
        collection_pk = await self.cl.collection_pk_by_name("Repost")
        # clear and check
        await self.cl.media_unsave(media_pk)
        medias = await self.cl.collection_medias(collection_pk)
        self.assertNotIn(media_pk, [m.pk for m in medias])
        # save
        await self.cl.media_save(media_pk, collection_pk)
        medias = await self.cl.collection_medias(collection_pk)
        self.assertIn(media_pk, [m.pk for m in medias])
        # unsave
        await self.cl.media_unsave(media_pk, collection_pk)
        medias = await self.cl.collection_medias(collection_pk)
        self.assertNotIn(media_pk, [m.pk for m in medias])


class ClientDirectTestCase(ClientPrivateTestCase):
    async def test_direct_thread(self):
        # threads
        threads = await self.cl.direct_threads()
        self.assertTrue(len(threads) > 0)
        thread = threads[0]
        self.assertIsInstance(thread, DirectThread)
        # messages
        messages = await self.cl.direct_messages(thread.id, 2)
        self.assertTrue(3 > len(messages) > 0)
        # self.assertTrue(thread.is_seen(self.cl.user_id))
        message = messages[0]
        self.assertIsInstance(message, DirectMessage)
        instagram = await self.user_id_from_username("instagram")
        ping = await self.cl.direct_send("Ping", user_ids=[instagram])
        self.assertIsInstance(ping, DirectMessage)
        pong = await self.cl.direct_answer(ping.thread_id, "Pong")
        self.assertIsInstance(pong, DirectMessage)
        self.assertEqual(ping.thread_id, pong.thread_id)
        # send direct photo
        photo = await self.cl.direct_send_photo(
            path="examples/kanada.jpg", user_ids=[instagram]
        )
        self.assertIsInstance(photo, DirectMessage)
        self.assertEqual(photo.thread_id, pong.thread_id)
        # send seen
        seen = await self.cl.direct_send_seen(thread_id=thread.id)
        self.assertEqual(seen.status, "ok")
        # mute and unmute thread
        self.assertTrue(await self.cl.direct_thread_mute(thread.id))
        self.assertTrue(await self.cl.direct_thread_unmute(thread.id))
        # mute video call and unmute
        self.assertTrue(await self.cl.direct_thread_mute_video_call(thread.id))
        self.assertTrue(await self.cl.direct_thread_unmute_video_call(thread.id))

    async def test_direct_send_photo(self):
        instagram = await self.user_id_from_username("instagram")
        dm = await self.cl.direct_send_photo(
            path="examples/kanada.jpg", user_ids=[instagram]
        )
        self.assertIsInstance(dm, DirectMessage)

    async def test_direct_send_video(self):
        instagram = await self.user_id_from_username("instagram")
        path = await self.cl.video_download(
            await self.cl.media_pk_from_url("https://www.instagram.com/p/B3rFQPblq40/")
        )
        dm = await self.cl.direct_send_video(path=path, user_ids=[instagram])
        self.assertIsInstance(dm, DirectMessage)

    async def test_direct_thread_by_participants(self):
        try:
            await self.cl.direct_thread_by_participants([12345])
        except DirectThreadNotFound:
            pass


class ClientDirectMessageTypesTestCase(ClientPrivateTestCase):
    """Test that DirectMessage and DirectThread fields use structured Pydantic models instead of raw dictionaries"""

    async def test_direct_message_reactions_model(self):
        """Test that DirectMessage.reactions field uses MessageReactions model"""
        from datetime import datetime

        from aiograpi.types import MessageReaction, MessageReactions

        # Get some direct messages
        threads = await self.cl.direct_threads(amount=5)
        if not threads:
            self.skipTest("No direct threads available for testing")

        for thread in threads:
            messages = await self.cl.direct_messages(thread.id, amount=10)
            for message in messages:
                if message.reactions:
                    # Test that reactions field is now a MessageReactions object
                    self.assertIsInstance(message.reactions, MessageReactions)

                    # Test that reactions have proper structure
                    if (
                        hasattr(message.reactions, "emojis")
                        and message.reactions.emojis
                    ):
                        for emoji_reaction in message.reactions.emojis:
                            self.assertIsInstance(emoji_reaction, MessageReaction)
                            self.assertIsInstance(emoji_reaction.emoji, str)
                            self.assertIsInstance(emoji_reaction.sender_id, str)
                            self.assertIsInstance(emoji_reaction.timestamp, datetime)

                    # Test backward compatibility - should still work as dict
                    if hasattr(message.reactions, "likes_count"):
                        self.assertIsInstance(message.reactions.likes_count, int)

                    return  # Found one message with reactions, test passed

    async def test_direct_message_link_model(self):
        """Test that DirectMessage.link field uses MessageLink model"""
        from aiograpi.types import LinkContext, MessageLink

        # Get some direct messages
        threads = await self.cl.direct_threads(amount=5)
        if not threads:
            self.skipTest("No direct threads available for testing")

        for thread in threads:
            messages = await self.cl.direct_messages(thread.id, amount=10)
            for message in messages:
                if message.link:
                    # Test that link field is now a MessageLink object
                    self.assertIsInstance(message.link, MessageLink)

                    # Test that link has proper structure
                    if hasattr(message.link, "text"):
                        self.assertIsInstance(message.link.text, str)

                    if (
                        hasattr(message.link, "link_context")
                        and message.link.link_context
                    ):
                        self.assertIsInstance(message.link.link_context, LinkContext)
                        if hasattr(message.link.link_context, "link_url"):
                            self.assertIsInstance(
                                message.link.link_context.link_url, str
                            )

                    return  # Found one message with link, test passed

    async def test_direct_message_visual_media_model(self):
        """Test that DirectMessage.visual_media field uses VisualMedia model"""
        from aiograpi.types import VisualMedia, VisualMediaContent

        # Get some direct messages
        threads = await self.cl.direct_threads(amount=5)
        if not threads:
            self.skipTest("No direct threads available for testing")

        for thread in threads:
            messages = await self.cl.direct_messages(thread.id, amount=10)
            for message in messages:
                if message.visual_media:
                    # Test that visual_media field is now a VisualMedia object
                    self.assertIsInstance(message.visual_media, VisualMedia)

                    # Test that visual_media has proper structure
                    if (
                        hasattr(message.visual_media, "media")
                        and message.visual_media.media
                    ):
                        self.assertIsInstance(
                            message.visual_media.media, VisualMediaContent
                        )

                    return  # Found one message with visual media, test passed

    async def test_direct_thread_last_seen_at_model(self):
        """Test that DirectThread.last_seen_at field uses LastSeenInfo model"""
        from datetime import datetime

        from aiograpi.types import LastSeenInfo

        # Get some direct threads
        threads = await self.cl.direct_threads(amount=5)
        if not threads:
            self.skipTest("No direct threads available for testing")

        for thread in threads:
            if thread.last_seen_at:
                # Test that last_seen_at is now a dict of LastSeenInfo objects
                for user_id, seen_info in thread.last_seen_at.items():
                    self.assertIsInstance(user_id, str)
                    self.assertIsInstance(seen_info, LastSeenInfo)

                    # Test structure of LastSeenInfo
                    if hasattr(seen_info, "timestamp"):
                        self.assertIsInstance(seen_info.timestamp, datetime)
                    if hasattr(seen_info, "created_at"):
                        self.assertIsInstance(seen_info.created_at, datetime)

                    return  # Found one thread with last_seen_at, test passed

    async def test_direct_message_clips_metadata_model(self):
        """Test that DirectMessage.clips_metadata field uses ClipsMetadata model"""
        from aiograpi.types import ClipsMetadata

        # Get some direct messages
        threads = await self.cl.direct_threads(amount=5)
        if not threads:
            self.skipTest("No direct threads available for testing")

        for thread in threads:
            messages = await self.cl.direct_messages(thread.id, amount=10)
            for message in messages:
                if message.clips_metadata:
                    # Test that clips_metadata field is now a ClipsMetadata object
                    self.assertIsInstance(message.clips_metadata, ClipsMetadata)

                    return  # Found one message with clips metadata, test passed

    async def test_thread_is_seen_datetime_compatibility(self):
        """Test that DirectThread.is_seen() works with datetime objects"""

        # Get some direct threads
        threads = await self.cl.direct_threads(amount=5)
        if not threads:
            self.skipTest("No direct threads available for testing")

        for thread in threads:
            if thread.last_seen_at:
                # Test that is_seen method works with datetime objects
                user_id = str(self.cl.user_id)
                try:
                    is_seen = thread.is_seen(user_id)
                    self.assertIsInstance(is_seen, bool)
                    return  # Successfully tested is_seen method
                except Exception as e:
                    self.fail(f"is_seen() method failed with datetime objects: {e}")

    async def test_backward_compatibility_dict_access(self):
        """Test that dict-style access patterns still work for backward compatibility"""
        # Get some direct messages
        threads = await self.cl.direct_threads(amount=5)
        if not threads:
            self.skipTest("No direct threads available for testing")

        for thread in threads:
            messages = await self.cl.direct_messages(thread.id, amount=10)
            for message in messages:
                # Test that we can still access fields as if they were dicts
                # This should work due to our Pydantic model structure
                try:
                    if message.reactions:
                        # Should work even though it's now a Pydantic model
                        likes_count = getattr(message.reactions, "likes_count", 0)
                        self.assertIsInstance(likes_count, int)

                    if message.link:
                        # Should work even though it's now a Pydantic model
                        link_text = getattr(message.link, "text", "")
                        self.assertIsInstance(link_text, str)

                    return  # Successfully tested backward compatibility
                except Exception as e:
                    self.fail(f"Backward compatibility test failed: {e}")


class DirectExtractorRegressionTestCase(unittest.TestCase):
    def setUp(self):
        # extract_direct_message uses datetime.fromtimestamp (local TZ),
        # but the assertions are written in UTC. Force UTC so the test
        # passes regardless of the host system's timezone.
        import time

        self._old_tz = os.environ.get("TZ")
        os.environ["TZ"] = "UTC"
        if hasattr(time, "tzset"):
            time.tzset()

    def tearDown(self):
        import time

        if self._old_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = self._old_tz
        if hasattr(time, "tzset"):
            time.tzset()

    def test_xma_share_without_target_url_is_ignored(self):
        message = extract_direct_message(
            {
                "item_id": "1",
                "user_id": "2",
                "timestamp": 1761953663000000,
                "item_type": "xma_media_share",
                "text": "",
                "xma_media_share": [
                    {
                        "header_icon_url": "",
                        "title_text": "Shared content",
                    }
                ],
            }
        )

        self.assertIsNone(message.xma_share)

    def test_xma_share_accepts_empty_header_icon_url(self):
        message = extract_direct_message(
            {
                "item_id": "1",
                "user_id": "2",
                "timestamp": 1761953663000000,
                "item_type": "xma_media_share",
                "text": "",
                "xma_media_share": [
                    {
                        "target_url": "https://example.com/reel",
                        "header_icon_url": "",
                        "title_text": "Shared content",
                    }
                ],
            }
        )

        self.assertIsNotNone(message.xma_share)
        self.assertEqual(str(message.xma_share.video_url), "https://example.com/reel")
        self.assertIsNone(message.xma_share.header_icon_url)

    def test_generic_xma_collects_multiple_items(self):
        message = extract_direct_message(
            {
                "item_id": "1",
                "user_id": "2",
                "timestamp": 1761953663000000,
                "item_type": "generic_xma",
                "text": "",
                "generic_xma": [
                    {
                        "target_url": "https://example.com/first",
                        "title_text": "First item",
                    },
                    {
                        "title_text": "Missing target url should be ignored",
                    },
                    {
                        "target_url": "https://example.com/second",
                        "title_text": "Second item",
                    },
                ],
            }
        )

        self.assertIsNotNone(message.generic_xma)
        self.assertEqual(len(message.generic_xma), 2)
        self.assertEqual(
            str(message.generic_xma[0].video_url), "https://example.com/first"
        )
        self.assertEqual(
            str(message.generic_xma[1].video_url), "https://example.com/second"
        )

    def test_reply_visual_media_timestamp_uses_microseconds(self):
        message = extract_direct_message(
            {
                "item_id": "1",
                "user_id": "2",
                "timestamp": 1761953663000000,
                "item_type": "text",
                "text": "reply wrapper",
                "replied_to_message": {
                    "item_id": "3",
                    "user_id": "4",
                    "timestamp": 1761953663000000,
                    "item_type": "visual_media",
                    "visual_media": {
                        "view_mode": "permanent",
                        "seen_user_ids": [],
                        "seen_count": 0,
                        "media": {
                            "media_type": 1,
                            "expiring_media_action_summary": {
                                "type": "replay",
                                "timestamp": 1761953663000000,
                                "count": 1,
                            },
                        },
                    },
                },
            }
        )

        self.assertEqual(message.reply.id, "3")
        self.assertEqual(
            message.reply.visual_media.media.expiring_media_action_summary.timestamp,
            datetime(2025, 10, 31, 23, 34, 23),
        )

    def test_direct_thread_defaults_missing_is_close_friend_thread(self):
        thread = extract_direct_thread(
            {
                "thread_v2_id": "1",
                "thread_id": "2",
                "items": [],
                "users": [
                    {
                        "pk": "3",
                        "username": "example",
                        "profile_pic_url": "https://example.com/pic.jpg",
                    }
                ],
                "left_users": [],
                "admin_user_ids": [],
                "last_activity_at": 1761953663000000,
                "muted": False,
                "named": False,
                "canonical": False,
                "pending": False,
                "archived": False,
                "thread_type": "private",
                "thread_title": "",
                "folder": 0,
                "vc_muted": False,
                "is_group": False,
                "mentions_muted": False,
                "approval_required_for_new_members": False,
                "input_mode": 0,
                "business_thread_folder": 0,
                "read_state": 0,
                "assigned_admin_id": 0,
                "shh_mode_enabled": False,
                "last_seen_at": {},
            }
        )

        self.assertFalse(thread.is_close_friend_thread)


class DirectMixinRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    def build_client(self):
        client = Client()
        client.settings = {}
        client.authorization_data = {"ds_user_id": "1"}
        client.last_json = {}
        return client

    async def test_direct_send_video_uses_direct_story_flow_for_thread_ids(self):
        client = self.build_client()
        expected = Mock(spec=DirectMessage)

        client.video_upload_to_direct = AsyncMock(return_value=expected)
        result = await client.direct_send_video("clip.mp4", thread_ids=[123])

        self.assertIs(result, expected)
        client.video_upload_to_direct.assert_called_once_with(
            Path("clip.mp4"), thread_ids=[123]
        )

    async def test_direct_send_video_resolves_existing_thread_for_user_ids(self):
        client = self.build_client()
        expected = Mock(spec=DirectMessage)

        client.direct_thread_by_participants = AsyncMock(
            return_value={"thread_v2_id": "340282366841710300949128149448121770626"}
        )
        client.video_upload_to_direct = AsyncMock(return_value=expected)
        result = await client.direct_send_video("clip.mp4", user_ids=[42])

        self.assertIs(result, expected)
        client.direct_thread_by_participants.assert_called_once_with([42])
        client.video_upload_to_direct.assert_called_once_with(
            Path("clip.mp4"),
            thread_ids=[340282366841710300949128149448121770626],
        )

    async def test_direct_send_video_raises_when_existing_thread_is_missing(self):
        client = self.build_client()

        client.direct_thread_by_participants = AsyncMock(return_value={})
        client.video_upload_to_direct = AsyncMock()
        with self.assertRaises(DirectThreadNotFound):
            await client.direct_send_video("clip.mp4", user_ids=[42])

        client.direct_thread_by_participants.assert_called_once_with([42])
        client.video_upload_to_direct.assert_not_called()


class UserMixinRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    def build_private_client(self):
        client = Client()
        client.settings = {}
        client.authorization_data = {"ds_user_id": "1"}
        client.uuid = "uuid"
        return client

    @staticmethod
    def build_web_profile_user(**overrides):
        user = {
            "id": "123",
            "username": "example",
            "full_name": "Example",
            "is_private": False,
            "is_verified": False,
            "profile_pic_url_hd": None,
            "profile_pic_url": "https://example.com/pic.jpg",
            "edge_owner_to_timeline_media": {"count": 0},
            "edge_followed_by": {"count": 0},
            "edge_follow": {"count": 0},
            "is_business_account": False,
            "business_email": None,
            "business_phone_number": None,
            "biography": "",
            "bio_links": [],
            "external_url": None,
            "business_category_name": None,
            "category_name": None,
            "fbid": "123",
            "pinned_channels_info": {"pinned_channels_list": []},
        }
        user.update(overrides)
        return {"data": {"user": user}}

    async def test_user_short_gql_falls_back_to_web_profile_graphql(self):
        client = Client()
        web_user = {
            "id": "25025320",
            "username": "instagram",
            "full_name": "Instagram",
            "is_private": False,
            "profile_pic_url": "https://example.com/pic.jpg",
        }

        client.public_graphql_request = AsyncMock(
            side_effect=ClientGraphqlError("Incorrect Query")
        )
        client.user_web_profile_info_gql = AsyncMock(return_value=web_user)
        # user_short_gql in aiograpi has no use_cache kwarg; signature differs
        user = await client.user_short_gql("25025320")

        self.assertEqual(user.username, "instagram")
        client.user_web_profile_info_gql.assert_called_once_with("25025320")

    async def test_user_info_by_username_gql_parses_web_profile_without_update_headers_kwarg(
        self,
    ):
        class DummyClient(UserMixin):
            response_body = None

            def __init__(self):
                self.public_request_calls = []

            async def public_request(self, url, headers=None, **kwargs):
                self.public_request_calls.append(
                    {"url": url, "headers": headers, "kwargs": kwargs}
                )
                return json.dumps(self.response_body)

        client = DummyClient()
        client.response_body = self.build_web_profile_user()
        user = await client.user_info_by_username_gql("Example")
        self.assertEqual(user.pk, "123")
        self.assertEqual(user.username, "example")
        self.assertEqual(len(client.public_request_calls), 1)
        self.assertEqual(client.public_request_calls[0]["kwargs"], {})
        self.assertIn(
            "web_profile_info/?username=example",
            client.public_request_calls[0]["url"],
        )

    @unittest.skip(
        "aiograpi: tests urllib3 RetryError handling; aiograpi has no urllib3 "
        "retry stack and the user_info_by_username fallback catches generic "
        "Exception, so RetryError is not a meaningful sentinel here"
    )
    def test_user_info_by_username_suppresses_traceback_for_public_retry_error(self):
        pass

    async def test_user_info_by_username_gql_handles_missing_pinned_channels_info(self):
        class DummyClient(UserMixin):
            response_body = None

            async def public_request(self, url, headers=None, **kwargs):
                return json.dumps(self.response_body)

        client = DummyClient()
        client.response_body = self.build_web_profile_user()
        client.response_body["data"]["user"].pop("pinned_channels_info")

        user = await client.user_info_by_username_gql("Example")

        self.assertEqual(user.broadcast_channel, [])

    async def test_user_info_by_username_gql_handles_bio_links_without_link_id(self):
        class DummyClient(UserMixin):
            response_body = None

            async def public_request(self, url, headers=None, **kwargs):
                return json.dumps(self.response_body)

        client = DummyClient()
        client.response_body = self.build_web_profile_user(
            bio_links=[{"url": "https://example.com", "title": "Example"}]
        )

        user = await client.user_info_by_username_gql("Example")

        self.assertEqual(len(user.bio_links), 1)
        self.assertIsNone(user.bio_links[0].link_id)
        self.assertEqual(user.bio_links[0].url, "https://example.com")

    async def test_user_followers_v1_chunk_omits_empty_max_id_on_first_page(self):
        client = self.build_private_client()

        client.private_request = AsyncMock(
            return_value={"users": [], "next_max_id": None}
        )
        await client.user_followers_v1_chunk("123")

        params = client.private_request.call_args.kwargs["params"]
        self.assertNotIn("max_id", params)

    async def test_user_followers_v1_chunk_sends_non_empty_max_id_on_next_page(self):
        client = self.build_private_client()

        client.private_request = AsyncMock(
            return_value={"users": [], "next_max_id": None}
        )
        await client.user_followers_v1_chunk("123", max_id="cursor")

        params = client.private_request.call_args.kwargs["params"]
        self.assertEqual(params["max_id"], "cursor")

    async def test_user_following_v1_chunk_omits_empty_max_id_on_first_page(self):
        client = self.build_private_client()

        client.private_request = AsyncMock(
            return_value={"users": [], "next_max_id": None}
        )
        await client.user_following_v1_chunk("123")

        params = client.private_request.call_args.kwargs["params"]
        self.assertNotIn("max_id", params)

    async def test_chaining_sends_required_params(self):
        client = self.build_private_client()
        client.private_request = AsyncMock(return_value={"users": []})

        await client.chaining("25025320")

        endpoint = client.private_request.call_args.args[0]
        params = client.private_request.call_args.kwargs["params"]
        self.assertEqual(endpoint, "discover/chaining/")
        self.assertEqual(params["module"], "profile")
        self.assertEqual(params["target_id"], "25025320")
        self.assertEqual(params["profile_chaining_check"], "false")
        self.assertEqual(params["eligible_for_threads_cta"], "false")

    async def test_chaining_maps_not_eligible_to_invalid_target_user(self):
        client = self.build_private_client()
        client.private_request = AsyncMock(
            side_effect=UnknownError(
                "Not eligible for chaining.", response=Mock(status_code=400)
            )
        )

        with self.assertRaises(InvalidTargetUser):
            await client.chaining("25025320")

    async def test_chaining_propagates_other_unknown_errors(self):
        client = self.build_private_client()
        client.private_request = AsyncMock(
            side_effect=UnknownError(
                "Some other server error", response=Mock(status_code=500)
            )
        )

        with self.assertRaises(UnknownError):
            await client.chaining("25025320")

    async def test_fetch_suggestion_details_accepts_string(self):
        client = self.build_private_client()
        client.private_request = AsyncMock(return_value={"users": []})

        await client.fetch_suggestion_details("25025320", "1,2,3")

        endpoint = client.private_request.call_args.args[0]
        params = client.private_request.call_args.kwargs["params"]
        self.assertEqual(endpoint, "discover/fetch_suggestion_details/")
        self.assertEqual(params["target_id"], "25025320")
        self.assertEqual(params["chained_ids"], "1,2,3")
        self.assertEqual(params["include_social_context"], "1")

    async def test_fetch_suggestion_details_joins_list(self):
        client = self.build_private_client()
        client.private_request = AsyncMock(return_value={"users": []})

        await client.fetch_suggestion_details("25025320", ["1", "2", 3])

        params = client.private_request.call_args.kwargs["params"]
        self.assertEqual(params["chained_ids"], "1,2,3")

    async def test_user_stream_by_id_v1_posts_info_stream(self):
        client = self.build_private_client()
        client.private_request = AsyncMock(return_value={"stream_rows": []})

        await client.user_stream_by_id_v1("25025320")

        args, kwargs = client.private_request.call_args
        self.assertEqual(args[0], "users/25025320/info_stream/")
        self.assertEqual(
            kwargs["data"],
            {
                "is_prefetch": False,
                "entry_point": "profile",
                "from_module": "feed_timeline",
            },
        )

    async def test_user_stream_by_id_v1_translates_404_to_user_not_found(self):
        from aiograpi.exceptions import ClientNotFoundError

        client = self.build_private_client()
        client.private_request = AsyncMock(
            side_effect=ClientNotFoundError(
                "User not found", response=Mock(status_code=404)
            )
        )

        with self.assertRaises(UserNotFound):
            await client.user_stream_by_id_v1("25025320")

    async def test_user_stream_by_id_flat_merges_stream_rows(self):
        client = self.build_private_client()
        client.private_request = AsyncMock(
            return_value={
                "stream_rows": [
                    {"user": {"pk": "25025320", "username": "instagram"}},
                    {"user": {"full_name": "Instagram", "is_private": False}},
                    {"user": {"is_verified": True}},
                ]
            }
        )

        flat = await client.user_stream_by_id_flat("25025320")

        self.assertEqual(flat["pk"], "25025320")
        self.assertEqual(flat["username"], "instagram")
        self.assertEqual(flat["full_name"], "Instagram")
        self.assertTrue(flat["is_verified"])

    async def test_user_stream_by_id_flat_promotes_pk_id_to_pk(self):
        client = self.build_private_client()
        client.private_request = AsyncMock(
            return_value={
                "stream_rows": [
                    {"user": {"pk_id": "25025320", "username": "instagram"}},
                ]
            }
        )

        flat = await client.user_stream_by_id_flat("25025320")
        self.assertEqual(flat["pk"], "25025320")

    async def test_user_stream_by_username_flat_uses_username_endpoint(self):
        client = self.build_private_client()
        client.private_request = AsyncMock(
            return_value={
                "stream_rows": [{"user": {"pk": "25025320", "username": "instagram"}}]
            }
        )

        flat = await client.user_stream_by_username_flat("instagram")

        endpoint = client.private_request.call_args.args[0]
        self.assertEqual(endpoint, "users/instagram/usernameinfo_stream/")
        self.assertEqual(flat["username"], "instagram")

    async def test_user_web_profile_info_v1_unwraps_data_field(self):
        client = self.build_private_client()
        client.private_request = AsyncMock(
            return_value={
                "data": {"user": {"pk": "25025320", "username": "instagram"}},
                "status": "ok",
            }
        )

        result = await client.user_web_profile_info_v1("instagram")

        endpoint = client.private_request.call_args.args[0]
        params = client.private_request.call_args.kwargs["params"]
        self.assertEqual(endpoint, "users/web_profile_info/")
        self.assertEqual(params, {"username": "instagram"})
        self.assertEqual(result, {"user": {"pk": "25025320", "username": "instagram"}})

    async def test_user_web_profile_info_v1_raises_user_not_found_on_empty_data(self):
        client = self.build_private_client()
        client.private_request = AsyncMock(return_value={"data": {}, "status": "ok"})
        client.last_json = {}

        with self.assertRaises(UserNotFound):
            await client.user_web_profile_info_v1("ghost")

    async def test_discover_recommended_accounts_extracts_category_id(self):
        client = self.build_private_client()
        client.private_request = AsyncMock(
            side_effect=[
                # 1st call: user_stream_by_id_v1 — stream_rows with
                # category_id buried in one of the rows.
                {
                    "stream_rows": [
                        {"user": {"pk": "25025320", "username": "instagram"}},
                        {"user": {"category_id": 1839}},
                    ]
                },
                # 2nd call: discover/recommended_accounts_for_category/
                {"users": []},
            ]
        )

        await client.discover_recommended_accounts_for_category_v1("25025320")

        self.assertEqual(client.private_request.call_count, 2)
        second_call = client.private_request.call_args_list[1]
        self.assertEqual(
            second_call.args[0], "discover/recommended_accounts_for_category/"
        )
        self.assertEqual(
            second_call.kwargs["params"],
            {"target_id": "25025320", "category_id": 1839},
        )

    async def test_discover_recommended_accounts_handles_missing_category_id(self):
        client = self.build_private_client()
        client.private_request = AsyncMock(
            side_effect=[
                {"stream_rows": [{"user": {"pk": "25025320"}}]},
                {"users": []},
            ]
        )

        await client.discover_recommended_accounts_for_category_v1("25025320")

        params = client.private_request.call_args_list[1].kwargs["params"]
        self.assertIsNone(params["category_id"])

    async def test_user_related_profiles_gql_extracts_edge_chaining(self):
        client = self.build_private_client()
        client.public_graphql_request = AsyncMock(
            return_value={
                "user": {
                    "edge_chaining": {
                        "edges": [
                            {
                                "node": {
                                    "id": "1",
                                    "username": "a",
                                    "full_name": "A",
                                    "is_private": False,
                                    "profile_pic_url": "https://example.com/a.jpg",
                                }
                            },
                            {
                                "node": {
                                    "id": "2",
                                    "username": "b",
                                    "full_name": "B",
                                    "is_private": True,
                                    "profile_pic_url": "https://example.com/b.jpg",
                                }
                            },
                        ]
                    }
                }
            }
        )

        users = await client.user_related_profiles_gql("25025320")

        self.assertEqual([u.username for u in users], ["a", "b"])

    async def test_user_related_profiles_gql_no_user_raises_user_not_found(self):
        client = self.build_private_client()
        client.public_graphql_request = AsyncMock(return_value={"user": None})

        with self.assertRaises(UserNotFound):
            await client.user_related_profiles_gql("25025320")

    async def test_user_related_profiles_gql_empty_returns_empty_list_by_default(
        self,
    ):
        # num_retry not set → return empty list, no exception.
        client = self.build_private_client()
        client.public_graphql_request = AsyncMock(
            return_value={"user": {"edge_chaining": {"edges": []}}}
        )

        result = await client.user_related_profiles_gql("25025320")
        self.assertEqual(result, [])

    async def test_user_related_profiles_gql_empty_raises_when_num_retry_set(self):
        from aiograpi.exceptions import RelatedProfileRequired

        client = self.build_private_client()
        client.num_retry = 0
        client.public_graphql_request = AsyncMock(
            return_value={"user": {"edge_chaining": {"edges": []}}}
        )

        with self.assertRaises(RelatedProfileRequired):
            await client.user_related_profiles_gql("25025320")


class TimelineRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def build_media_payload(pk="1", code="abc"):
        return {
            "pk": pk,
            "id": f"{pk}_1",
            "code": code,
            "taken_at": 1710000000,
            "media_type": 2,
            "caption": {"text": "caption"},
            "user": {
                "pk": "1",
                "username": "example",
                "profile_pic_url": "https://example.com/profile.jpg",
            },
            "like_count": 0,
            "video_versions": [
                {
                    "url": "https://example.com/video.mp4",
                    "width": 720,
                    "height": 1280,
                }
            ],
            "image_versions2": {
                "candidates": [
                    {
                        "url": "https://example.com/thumbnail.jpg",
                        "width": 720,
                        "height": 1280,
                    }
                ]
            },
        }

    async def test_reels_timeline_media_returns_empty_for_unsupported_collection(self):
        client = Client()
        client.logger = Mock()
        client.private_request = AsyncMock()

        result = await client.reels_timeline_media(123456789)

        self.assertEqual(result, [])
        client.private_request.assert_not_called()
        client.logger.warning.assert_called_once()

    async def test_reels_timeline_media_uses_paging_info_max_id_for_pagination(self):
        client = Client()
        client.logger = Mock()
        first_media = self.build_media_payload(pk="1", code="abc")
        second_media = self.build_media_payload(pk="2", code="def")
        client.private_request = AsyncMock(
            side_effect=[
                {
                    "items": [{"media": first_media}],
                    "paging_info": {"more_available": True, "max_id": "next-page"},
                },
                {
                    "items": [{"media": second_media}],
                    "paging_info": {"more_available": False},
                },
            ]
        )

        result = await client.reels_timeline_media("reels", amount=2)

        self.assertEqual(len(result), 2)
        self.assertEqual(client.private_request.call_count, 2)
        first_call = client.private_request.call_args_list[0]
        second_call = client.private_request.call_args_list[1]
        self.assertEqual(first_call.args[0], "clips/connected/")
        self.assertEqual(first_call.kwargs["params"]["max_id"], "")
        self.assertEqual(second_call.kwargs["params"]["max_id"], "next-page")


class StoryConfigureRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    def build_client(self):
        client = Client()
        client.settings = {}
        client._user_id = "1"
        client.uuid = "uuid"
        client.android_device_id = "device"
        client.client_session_id = "client-session"
        client.timezone_offset = 0
        client.set_device({})
        client.with_default_data = lambda data: data
        return client

    async def test_photo_story_sticker_ids_include_all_stickers(self):
        client = self.build_client()
        client.private_request = AsyncMock(
            side_effect=[
                {"status": "ok"},
                {"status": "ok"},
            ]
        )
        await client.photo_configure_to_story(
            upload_id="1",
            width=720,
            height=1280,
            caption="",
            links=[StoryLink(webUri="https://example.com")],
            hashtags=[
                StoryHashtag(
                    hashtag=Hashtag(id="1", name="example"),
                    x=0.2,
                    y=0.3,
                    width=0.5,
                    height=0.2,
                )
            ],
        )

        validate_args, _ = client.private_request.call_args_list[0]
        self.assertEqual(validate_args[1]["url"], "https://example.com/")
        configure_args, _ = client.private_request.call_args_list[1]
        self.assertEqual(
            configure_args[1]["story_sticker_ids"],
            "hashtag_sticker,link_sticker_default",
        )


class UploadRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    def build_client(self):
        client = Client()
        client.settings = {}
        client._user_id = "1"
        client.uuid = "uuid"
        client.android_device_id = "device"
        client.client_session_id = "client-session"
        client.timezone_offset = 0
        client.last_json = {}
        client.last_response = None
        client.set_device({})
        client.with_default_data = lambda data: data
        client.request_log = lambda response: None
        client.expose = AsyncMock(return_value=None)
        return client

    def build_media_payload(self, media_type=2):
        payload = {
            "pk": "1",
            "id": "1_1",
            "code": "abc",
            "taken_at": 1710000000,
            "media_type": media_type,
            "caption": {"text": "caption"},
            "user": {
                "pk": "1",
                "username": "example",
                "profile_pic_url": "https://example.com/profile.jpg",
            },
            "like_count": 0,
        }
        if media_type == 2:
            payload["video_versions"] = [
                {
                    "url": "https://example.com/video.mp4",
                    "width": 720,
                    "height": 1280,
                }
            ]
            payload["image_versions2"] = {
                "candidates": [
                    {
                        "url": "https://example.com/thumbnail.jpg",
                        "width": 720,
                        "height": 1280,
                    }
                ]
            }
        else:
            payload["image_versions2"] = {
                "candidates": [
                    {
                        "url": "https://example.com/photo.jpg",
                        "width": 720,
                        "height": 720,
                    }
                ]
            }
        return payload

    async def test_photo_upload_raises_clear_error_when_configure_has_no_media(self):
        client = self.build_client()
        client.photo_rupload = AsyncMock(return_value=("1", 720, 720))
        client.photo_configure = AsyncMock(return_value={"status": "ok"})

        with mock.patch("aiograpi.mixins.photo.asyncio.sleep", new_callable=AsyncMock):
            with self.assertRaises(PhotoConfigureError) as ctx:
                await client.photo_upload(Path("example.jpg"), "caption")

        self.assertIn("without media payload", str(ctx.exception))

    async def test_video_upload_raises_clear_error_when_configure_has_no_media(self):
        client = self.build_client()
        client.video_rupload = AsyncMock(
            return_value=("1", 720, 1280, 5, Path("/tmp/thumb.jpg"))
        )
        client.video_configure = AsyncMock(return_value={"status": "ok"})

        with mock.patch("aiograpi.mixins.video.asyncio.sleep", new_callable=AsyncMock):
            with self.assertRaises(VideoConfigureError) as ctx:
                await client.video_upload(Path("example.mp4"), "caption")

        self.assertIn("without media payload", str(ctx.exception))

    async def test_album_upload_raises_clear_error_when_configure_has_no_media(self):
        client = self.build_client()
        client.photo_rupload = AsyncMock(return_value=("1", 720, 720))
        client.album_configure = AsyncMock(return_value={"status": "ok"})

        with mock.patch("aiograpi.mixins.album.asyncio.sleep", new_callable=AsyncMock):
            with self.assertRaises(AlbumConfigureError) as ctx:
                await client.album_upload([Path("one.jpg")], "caption")

        self.assertIn("without media payload", str(ctx.exception))

    async def test_album_upload_rejects_empty_paths_with_clear_error(self):
        client = self.build_client()

        with self.assertRaises(PrivateError) as ctx:
            await client.album_upload([], "caption")

        self.assertIn("requires at least one media path", str(ctx.exception))

    async def test_album_upload_rejects_unknown_format_with_filename_in_error(self):
        client = self.build_client()

        with self.assertRaises(PrivateError) as ctx:
            await client.album_upload([Path("clip.mov")], "caption")

        self.assertIn('Unsupported album media format ".mov"', str(ctx.exception))
        self.assertIn("clip.mov", str(ctx.exception))

    async def test_album_upload_accepts_png_via_photo_rupload(self):
        client = self.build_client()
        media_payload = self.build_media_payload(media_type=8)
        media_payload["carousel_media"] = [self.build_media_payload(media_type=1)]

        client.photo_rupload = AsyncMock(return_value=("1", 720, 720))
        client.album_configure = AsyncMock(
            return_value={"status": "ok", "media": media_payload}
        )

        with mock.patch("aiograpi.mixins.album.asyncio.sleep", new_callable=AsyncMock):
            media = await client.album_upload([Path("slide.png")], "caption")

        self.assertIsInstance(media, Media)
        client.photo_rupload.assert_called_once_with(Path("slide.png"), to_album=True)

    async def test_photo_story_upload_raises_clear_error_when_configure_has_no_media(
        self,
    ):
        client = self.build_client()
        client.photo_rupload = AsyncMock(return_value=("1", 720, 1280))
        client.photo_configure_to_story = AsyncMock(return_value={"status": "ok"})

        with mock.patch("aiograpi.mixins.photo.asyncio.sleep", new_callable=AsyncMock):
            with self.assertRaises(PhotoConfigureStoryError) as ctx:
                await client.photo_upload_to_story(Path("story.jpg"))

        self.assertIn("without media payload", str(ctx.exception))

    async def test_clip_upload_falls_back_to_last_json_media_payload(self):
        client = self.build_client()
        client.last_json = {"media": self.build_media_payload()}
        ok_response = Mock(status_code=200)

        client.private.get = AsyncMock(return_value=ok_response)
        client.private.post = AsyncMock(return_value=ok_response)
        client.clip_configure = AsyncMock(return_value={"status": "ok"})

        with mock.patch(
            "aiograpi.mixins.clip.analyze_video",
            return_value=(Path("/tmp/thumb.jpg"), 720, 1280, 5),
        ):
            with mock.patch("builtins.open", mock.mock_open(read_data=b"video-bytes")):
                with mock.patch(
                    "aiograpi.mixins.clip.asyncio.sleep", new_callable=AsyncMock
                ):
                    media = await client.clip_upload(Path("example.mp4"), "caption")

        self.assertIsInstance(media, Media)
        self.assertEqual(str(media.video_url), "https://example.com/video.mp4")

    async def test_video_story_upload_raises_clear_error_when_configure_has_no_media(
        self,
    ):
        client = self.build_client()
        client.video_rupload = AsyncMock(
            return_value=("1", 720, 1280, 5, Path("/tmp/thumb.jpg"))
        )
        client.video_configure_to_story = AsyncMock(return_value={"status": "ok"})

        with mock.patch("aiograpi.mixins.video.asyncio.sleep", new_callable=AsyncMock):
            with self.assertRaises(VideoConfigureStoryError) as ctx:
                await client.video_upload_to_story(Path("story.mp4"))

        self.assertIn("without media payload", str(ctx.exception))

    async def test_video_direct_upload_raises_clear_error_when_configure_has_no_message(
        self,
    ):
        client = self.build_client()
        client.video_rupload = AsyncMock(
            return_value=("1", 720, 1280, 5, Path("/tmp/thumb.jpg"))
        )
        client.video_configure_to_story = AsyncMock(return_value={"status": "ok"})

        with mock.patch("aiograpi.mixins.video.asyncio.sleep", new_callable=AsyncMock):
            with self.assertRaises(VideoConfigureStoryError) as ctx:
                await client.video_upload_to_direct(
                    Path("story.mp4"),
                    thread_ids=[123],
                )

        self.assertIn("without message_metadata payload", str(ctx.exception))

    async def test_cutout_sticker_upload_raises_clear_error_when_configure_has_no_media(
        self,
    ):
        client = self.build_client()
        client.private_request = AsyncMock(return_value={"status": "ok"})
        with self.assertRaises(PrivateError) as ctx:
            await client.media_configure_to_cutout_sticker(
                "1", manual_box=[0.0, 0.0, 1.0, 1.0]
            )

        self.assertIn("without media payload", str(ctx.exception))

    async def test_cutout_sticker_upload_uses_returned_media_payload(self):
        client = self.build_client()
        media_payload = self.build_media_payload(media_type=1)

        client.private_request = AsyncMock(
            return_value={"status": "ok", "media": media_payload}
        )
        media = await client.media_configure_to_cutout_sticker(
            "1", manual_box=[0.0, 0.0, 1.0, 1.0]
        )

        self.assertIsInstance(media, Media)
        self.assertEqual(media.media_type, 1)

    async def test_clip_upload_as_reel_with_music_does_not_mutate_extra_data(self):
        client = self.build_client()
        extra_data = {"share_to_facebook": 1}
        track = Mock(
            uri="https://example.com/track.m4a",
            highlight_start_times_in_ms=[1500],
            display_artist="Artist",
            id="track-id",
            audio_cluster_id="cluster-id",
            title="Track title",
        )

        class FakeAudioClip:
            def __init__(self, path):
                self.path = path

            def subclip(self, start, end):
                return self

            def close(self):
                return None

        class FakeVideoClip:
            def __init__(self, path):
                self.path = path
                self.duration = 2.5

            def set_audio(self, audio_clip):
                self.audio_clip = audio_clip
                return self

            def write_videofile(self, path):
                Path(path).write_bytes(b"video")

            def close(self):
                return None

        fake_mp = types.ModuleType("moviepy.editor")
        fake_mp.VideoFileClip = FakeVideoClip
        fake_mp.AudioFileClip = FakeAudioClip

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "track.m4a"
            audio_path.write_bytes(b"audio")
            video_path = Path(tmpdir) / "output.mp4"
            client.track_download_by_url = AsyncMock(return_value=audio_path)
            client.clip_upload = AsyncMock(return_value="uploaded")
            with mock.patch.dict(
                "sys.modules",
                {
                    "moviepy": fake_mp,
                    "moviepy.editor": fake_mp,
                },
            ):
                with mock.patch(
                    "tempfile.mktemp", side_effect=[str(audio_path), str(video_path)]
                ):
                    result = await client.clip_upload_as_reel_with_music(
                        Path("input.mp4"),
                        "caption",
                        track,
                        extra_data=extra_data,
                    )

        self.assertEqual(result, "uploaded")
        self.assertEqual(extra_data, {"share_to_facebook": 1})
        upload_extra = client.clip_upload.call_args.kwargs["extra_data"]
        self.assertEqual(upload_extra["share_to_facebook"], 1)
        self.assertIn("clips_audio_metadata", upload_extra)
        self.assertIn("music_params", upload_extra)

    async def test_clip_upload_as_reel_with_music_includes_music_canonical_id(self):
        client = self.build_client()
        track = Mock(
            uri="https://example.com/track.m4a",
            highlight_start_times_in_ms=[1500],
            display_artist="Artist",
            id="track-id",
            audio_cluster_id="cluster-id",
            music_canonical_id="canonical-id",
            title="Track title",
        )

        class FakeAudioClip:
            def __init__(self, path):
                self.path = path

            def subclip(self, start, end):
                return self

            def close(self):
                return None

        class FakeVideoClip:
            def __init__(self, path):
                self.path = path
                self.duration = 2.5

            def set_audio(self, audio_clip):
                self.audio_clip = audio_clip
                return self

            def write_videofile(self, path):
                Path(path).write_bytes(b"video")

            def close(self):
                return None

        fake_mp = types.ModuleType("moviepy.editor")
        fake_mp.VideoFileClip = FakeVideoClip
        fake_mp.AudioFileClip = FakeAudioClip

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "track.m4a"
            audio_path.write_bytes(b"audio")
            video_path = Path(tmpdir) / "output.mp4"
            client.track_download_by_url = AsyncMock(return_value=audio_path)
            client.clip_upload = AsyncMock(return_value="uploaded")
            with mock.patch.dict(
                "sys.modules",
                {
                    "moviepy": fake_mp,
                    "moviepy.editor": fake_mp,
                },
            ):
                with mock.patch(
                    "tempfile.mktemp", side_effect=[str(audio_path), str(video_path)]
                ):
                    await client.clip_upload_as_reel_with_music(
                        Path("input.mp4"),
                        "caption",
                        track,
                    )

        upload_extra = client.clip_upload.call_args.kwargs["extra_data"]
        self.assertEqual(
            upload_extra["clips_audio_metadata"]["song"]["music_canonical_id"],
            "canonical-id",
        )
        self.assertEqual(
            upload_extra["music_params"]["music_canonical_id"],
            "canonical-id",
        )

    async def test_clip_upload_as_reel_with_music_cleans_temp_files_on_failure(self):
        client = self.build_client()
        track = Mock(
            uri="https://example.com/track.m4a",
            highlight_start_times_in_ms=[0],
            display_artist="Artist",
            id="track-id",
            audio_cluster_id="cluster-id",
            title="Track title",
        )

        class FakeAudioClip:
            def __init__(self, path):
                self.path = path

            def subclip(self, start, end):
                return self

            def close(self):
                return None

        class FakeVideoClip:
            def __init__(self, path):
                self.path = path
                self.duration = 2.5

            def set_audio(self, audio_clip):
                self.audio_clip = audio_clip
                return self

            def write_videofile(self, path):
                Path(path).write_bytes(b"video")

            def close(self):
                return None

        fake_mp = types.ModuleType("moviepy.editor")
        fake_mp.VideoFileClip = FakeVideoClip
        fake_mp.AudioFileClip = FakeAudioClip

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "track.m4a"
            audio_path.write_bytes(b"audio")
            video_path = Path(tmpdir) / "output.mp4"
            client.track_download_by_url = AsyncMock(return_value=audio_path)
            client.clip_upload = AsyncMock(side_effect=ClipConfigureError("boom"))
            with mock.patch.dict(
                "sys.modules",
                {
                    "moviepy": fake_mp,
                    "moviepy.editor": fake_mp,
                },
            ):
                with mock.patch(
                    "tempfile.mktemp", side_effect=[str(audio_path), str(video_path)]
                ):
                    with self.assertRaises(ClipConfigureError):
                        await client.clip_upload_as_reel_with_music(
                            Path("input.mp4"),
                            "caption",
                            track,
                        )

            self.assertFalse(audio_path.exists())
            self.assertFalse(video_path.exists())

    def test_clip_analyze_video_closes_video_file(self):
        import aiograpi.mixins.clip as clip_mixin

        closed = {"value": False}

        class FakeVideoClip:
            def __init__(self, path):
                self.size = (720, 1280)
                self.duration = 5

            def close(self):
                closed["value"] = True

        fake_mp = types.ModuleType("moviepy.editor")
        fake_mp.VideoFileClip = FakeVideoClip

        with mock.patch.dict(
            "sys.modules",
            {
                "moviepy": fake_mp,
                "moviepy.editor": fake_mp,
            },
        ):
            result = clip_mixin.analyze_video(
                Path("input.mp4"), thumbnail=Path("thumb.jpg")
            )

        self.assertEqual(result, (Path("thumb.jpg"), 720, 1280, 5))
        self.assertTrue(closed["value"])

    def test_video_analyze_video_closes_video_file_on_save_frame_error(self):
        import aiograpi.mixins.video as video_mixin

        closed = {"value": False}

        class FakeVideoClip:
            def __init__(self, path):
                self.size = (720, 1280)
                self.duration = 5

            def save_frame(self, path, t):
                raise RuntimeError("save failed")

            def close(self):
                closed["value"] = True

        fake_mp = types.ModuleType("moviepy.editor")
        fake_mp.VideoFileClip = FakeVideoClip

        with mock.patch.dict(
            "sys.modules",
            {
                "moviepy": fake_mp,
                "moviepy.editor": fake_mp,
            },
        ):
            with self.assertRaises(RuntimeError):
                video_mixin.analyze_video(Path("input.mp4"))

        self.assertTrue(closed["value"])

    def test_clip_analyze_video_closes_video_file_on_save_frame_error(self):
        import aiograpi.mixins.clip as clip_mixin

        closed = {"value": False}

        class FakeVideoClip:
            def __init__(self, path):
                self.size = (720, 1280)
                self.duration = 5

            def save_frame(self, path, t):
                raise RuntimeError("save failed")

            def close(self):
                closed["value"] = True

        fake_mp = types.ModuleType("moviepy.editor")
        fake_mp.VideoFileClip = FakeVideoClip

        with mock.patch.dict(
            "sys.modules",
            {
                "moviepy": fake_mp,
                "moviepy.editor": fake_mp,
            },
        ):
            with self.assertRaises(RuntimeError):
                clip_mixin.analyze_video(Path("input.mp4"))

        self.assertTrue(closed["value"])

    async def test_video_story_sticker_ids_include_all_stickers(self):
        client = self.build_client()
        client.private_request = AsyncMock(
            side_effect=[
                {"status": "ok"},
                {"status": "ok"},
            ]
        )
        await client.video_configure_to_story(
            upload_id="1",
            width=720,
            height=1280,
            duration=5,
            thumbnail=Path("/tmp/placeholder.jpg"),
            caption="",
            links=[StoryLink(webUri="https://example.com")],
            hashtags=[
                StoryHashtag(
                    hashtag=Hashtag(id="1", name="example"),
                    x=0.2,
                    y=0.3,
                    width=0.5,
                    height=0.2,
                )
            ],
        )

        configure_args, _ = client.private_request.call_args_list[1]
        self.assertEqual(
            configure_args[1]["story_sticker_ids"],
            "hashtag_sticker,link_sticker_default",
        )

    def test_extract_story_v1_reads_links_from_story_link_stickers(self):
        story = extract_story_v1(
            {
                "pk": "1",
                "id": "1_2",
                "code": "abc",
                "taken_at": 1710000000,
                "media_type": 1,
                "image_versions2": {
                    "candidates": [
                        {
                            "url": "https://example.com/thumbnail.jpg",
                            "width": 720,
                            "height": 1280,
                        }
                    ]
                },
                "user": {
                    "pk": "2",
                    "username": "example",
                    "profile_pic_url": "https://example.com/profile.jpg",
                },
                "story_link_stickers": [
                    {
                        "x": 0.5,
                        "y": 0.5,
                        "width": 0.5,
                        "height": 0.2,
                        "rotation": 0.0,
                        "story_link": {
                            "url": "https://example.com/story-link",
                            "link_type": "web",
                        },
                    }
                ],
                "story_hashtags": [
                    {
                        "x": 0.2,
                        "y": 0.3,
                        "width": 0.5,
                        "height": 0.2,
                        "rotation": 0.0,
                        "hashtag": {"id": "1", "name": "example"},
                    }
                ],
            }
        )

        self.assertEqual(len(story.links), 1)
        self.assertEqual(str(story.links[0].webUri), "https://example.com/story-link")
        self.assertEqual(len(story.stickers), 1)
        self.assertEqual(len(story.hashtags), 1)
        self.assertEqual(story.hashtags[0].hashtag.name, "example")


class ClientAccountTestCase(ClientPrivateTestCase):
    async def test_account_edit(self):
        # current
        one = await self.cl.user_info(self.cl.user_id)
        self.assertIsInstance(one, User)
        # change
        url = "https://trotiq.com/"
        two = await self.cl.account_edit(external_url=url)
        self.assertIsInstance(two, Account)
        self.assertEqual(str(two.external_url), url)
        # return back
        three = await self.cl.account_edit(external_url=one.external_url)
        self.assertIsInstance(three, Account)
        self.assertEqual(one.external_url, three.external_url)

    async def test_account_change_picture(self):
        # current
        one = await self.cl.user_info(self.cl.user_id)
        self.assertIsInstance(one, User)
        instagram = await self.user_info_by_username("instagram")
        # change
        two = await self.cl.account_change_picture(
            await self.cl.photo_download_by_url(instagram.profile_pic_url)
        )
        self.assertIsInstance(two, UserShort)
        # return back
        three = await self.cl.account_change_picture(
            await self.cl.photo_download_by_url(one.profile_pic_url)
        )
        self.assertIsInstance(three, UserShort)


class ClientLocationTestCase(ClientPrivateTestCase):
    async def test_location_search(self):
        loc = (await self.cl.location_search(51.0536111111, 13.8108333333))[0]
        self.assertIsInstance(loc, Location)
        self.assertIn("Dresden", loc.name)
        self.assertIn("Dresden", loc.address)
        self.assertEqual(150300262230285, loc.external_id)
        self.assertEqual("facebook_places", loc.external_id_source)

    async def test_location_complete_pk(self):
        source = Location(
            name="Daily Surf Supply",
            external_id=533689780360041,
            external_id_source="facebook_places",
        )
        result = await self.cl.location_complete(source)
        self.assertIsInstance(result, Location)
        self.assertEqual(result.pk, 533689780360041)

    async def test_location_complete_lat_lng(self):
        source = Location(
            pk=150300262230285,
            name="Blaues Wunder (Dresden)",
        )
        result = await self.cl.location_complete(source)
        self.assertIsInstance(result, Location)
        self.assertEqual(result.lat, 51.0536111111)
        self.assertEqual(result.lng, 13.8108333333)

    async def test_location_complete_external_id(self):
        source = Location(
            name="Blaues Wunder (Dresden)", lat=51.0536111111, lng=13.8108333333
        )
        result = await self.cl.location_complete(source)
        self.assertIsInstance(result, Location)
        self.assertEqual(result.external_id, 150300262230285)
        self.assertEqual(result.external_id_source, "facebook_places")

    async def test_location_build(self):
        loc = await self.cl.location_info(150300262230285)
        self.assertIsInstance(loc, Location)
        json_data = await self.cl.location_build(loc)
        self.assertIsInstance(json_data, str)
        data = json.loads(json_data)
        self.assertIsInstance(data, dict)
        self.assertDictEqual(
            data,
            {
                "name": "Blaues Wunder (Dresden)",
                "address": "Dresden, Germany",
                "lat": 51.053611111111,
                "lng": 13.810833333333,
                "facebook_places_id": 150300262230285,
                "external_source": "facebook_places",
            },
        )

    async def test_location_info(self):
        loc = await self.cl.location_info(150300262230285)
        self.assertIsInstance(loc, Location)
        self.assertEqual(loc.pk, 150300262230285)
        self.assertEqual(loc.name, "Blaues Wunder (Dresden)")
        self.assertEqual(loc.lng, 13.8108333333)
        self.assertEqual(loc.lat, 51.0536111111)

    async def test_location_info_without_lat_lng(self):
        loc = await self.cl.location_info(197780767581661)
        self.assertIsInstance(loc, Location)
        self.assertEqual(loc.pk, 197780767581661)
        self.assertEqual(loc.name, "In The Clouds")

    async def test_location_medias_top(self):
        medias = await self.cl.location_medias_top(197780767581661, amount=2)
        self.assertEqual(len(medias), 2)
        self.assertIsInstance(medias[0], Media)

    # def test_extract_location_medias_top(self):
    #     medias_a1 = await self.cl.location_medias_top_a1(197780767581661, amount=9)
    #     medias_v1 = await self.cl.location_medias_top_v1(197780767581661, amount=9)
    #     self.assertEqual(len(medias_a1), 9)
    #     self.assertIsInstance(medias_a1[0], Media)
    #     self.assertEqual(len(medias_v1), 9)
    #     self.assertIsInstance(medias_v1[0], Media)

    async def test_location_medias_recent(self):
        medias = await self.cl.location_medias_recent(197780767581661, amount=2)
        self.assertEqual(len(medias), 2)
        self.assertIsInstance(medias[0], Media)


class SignUpTestCase(unittest.IsolatedAsyncioTestCase):
    # 2048-bit RSA public key generated for offline password_encrypt testing.
    _TEST_PUBLIC_KEY_B64 = (
        "LS0tLS1CRUdJTiBQVUJMSUMgS0VZLS0tLS0KTUlJQklqQU5CZ2txaGtpRzl3MEJBUUVG"
        "QUFPQ0FROEFNSUlCQ2dLQ0FRRUF1eWNmK0syT1R4bWhNZXdlbVR2ago0K2k0K2lTTUJv"
        "dmdkcVJMUHdSUlltR0pQNXVtWTdXZnZmYVlXTHVXbHZLYTlhUHVvUEJBRWtMV00vdzZO"
        "WXhlCk0xMS82b29QVG1OaTV2YlZhQzRweWpycVdCNVg3WGZkd210aDBWK3BBUFJUUWNG"
        "UDlJZEhlVmFnV3FLcEtCN0IKc3ZHYTZEL0tXdnYyeTJHZFYydDNjT1o3WFRNTkQ2WG1I"
        "ZDdXZm9MTFozbWdRd2xaU0RBSjBiR2RybXJmSk1TWApxL0VHVmdicXliWURMa0ZneG1C"
        "WUpqQjdocnQ4d2JSekQweTI0S0p5cWdJR05FdTROcFJzWFhZVm4zdFJJbndICldlR2s1"
        "TmpiRTN3L2tYais0enprMkgySEJDMmFuSHZQYllIUE5zU21yVFBqTDVNaHVrZFo0eEFZ"
        "azFJaXNpLzcKbXdJREFRQUIKLS0tLS1FTkQgUFVCTElDIEtFWS0tLS0t"
    )

    async def test_password_enrypt(self):
        cl = Client()
        cl.password_publickeys = AsyncMock(return_value=(1, self._TEST_PUBLIC_KEY_B64))
        enc_password = await cl.password_encrypt("test")
        parts = enc_password.split(":")
        self.assertEqual(parts[0], "#PWD_INSTAGRAM")
        self.assertEqual(parts[1], "4")
        self.assertTrue(int(parts[2]) > 1607612345)
        self.assertTrue(len(parts[3]) == 392)

    @unittest.skip(
        "aiograpi: requires real Instagram signup endpoints, SMS code, and a "
        "phone number; cannot be run without live credentials and network"
    )
    def test_signup(self):
        pass

    # --- signup endpoint smoke (verify each method hits the right URL
    # with the right payload shape; no live network) ---

    def _build_signup_client(self):
        client = Client()
        client.settings = {}
        client.authorization_data = {"ds_user_id": "1"}
        client.uuid = "stub-uuid"
        return client

    async def test_check_username_endpoint(self):
        client = self._build_signup_client()
        client.private_request = AsyncMock(return_value={"available": True})
        await client.check_username("new_user")
        args, kwargs = client.private_request.call_args
        self.assertEqual(args[0], "users/check_username/")
        self.assertEqual(kwargs["data"], {"username": "new_user", "_uuid": "stub-uuid"})

    async def test_get_signup_config_endpoint(self):
        client = self._build_signup_client()
        client.private_request = AsyncMock(return_value={})
        await client.get_signup_config()
        args, kwargs = client.private_request.call_args
        self.assertEqual(args[0], "consent/get_signup_config/")
        self.assertEqual(
            kwargs["params"],
            {"guid": "stub-uuid", "main_account_selected": False},
        )

    async def test_check_email_endpoint(self):
        client = self._build_signup_client()
        client.private_request = AsyncMock(return_value={})
        await client.check_email("a@b.com")
        args = client.private_request.call_args.args
        self.assertEqual(args[0], "users/check_email/")
        # Positional data dict; key fields present.
        self.assertEqual(args[1]["email"], "a@b.com")
        self.assertEqual(args[1]["login_nonce_map"], "{}")

    async def test_send_verify_email_endpoint(self):
        client = self._build_signup_client()
        client.private_request = AsyncMock(return_value={})
        await client.send_verify_email("a@b.com")
        args = client.private_request.call_args.args
        self.assertEqual(args[0], "accounts/send_verify_email/")
        self.assertEqual(args[1]["email"], "a@b.com")
        self.assertEqual(args[1]["auto_confirm_only"], "false")

    async def test_check_confirmation_code_endpoint(self):
        client = self._build_signup_client()
        client.private_request = AsyncMock(return_value={})
        await client.check_confirmation_code("a@b.com", "123456")
        args = client.private_request.call_args.args
        self.assertEqual(args[0], "accounts/check_confirmation_code/")
        self.assertEqual(args[1]["email"], "a@b.com")
        self.assertEqual(args[1]["code"], "123456")

    async def test_check_age_eligibility_endpoint_unsigned(self):
        client = self._build_signup_client()
        client.private_request = AsyncMock(return_value={"eligible": True})
        await client.check_age_eligibility(2000, 1, 15)
        args, kwargs = client.private_request.call_args
        self.assertEqual(args[0], "consent/check_age_eligibility/")
        self.assertFalse(kwargs["with_signature"])
        self.assertEqual(kwargs["data"]["year"], 2000)
        self.assertEqual(kwargs["data"]["month"], 1)
        self.assertEqual(kwargs["data"]["day"], 15)

    async def test_check_phone_number_replaces_spaces_with_plus(self):
        client = self._build_signup_client()
        client.private_request = AsyncMock(return_value={})
        await client.check_phone_number("1 555 1234")
        args, kwargs = client.private_request.call_args
        self.assertEqual(args[0], "accounts/check_phone_number/")
        self.assertEqual(kwargs["data"]["phone_number"], "1+555+1234")

    async def test_send_signup_sms_code_replaces_spaces_with_plus(self):
        client = self._build_signup_client()
        client.private_request = AsyncMock(return_value={})
        await client.send_signup_sms_code("1 555 1234")
        args, kwargs = client.private_request.call_args
        self.assertEqual(args[0], "accounts/send_signup_sms_code/")
        self.assertEqual(kwargs["data"]["phone_number"], "1+555+1234")
        self.assertEqual(kwargs["data"]["android_build_type"], "release")


class NotificationMixinRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    """Smoke coverage for the 27 NotificationMixin methods.

    Each `notification_*` wrapper just delegates to
    `notification_settings(content_type, setting_value)` after
    validating `setting_value` against `SETTING_VALUE_ITEMS`. The
    only true endpoint hit is `notifications/change_notification_settings/`.
    """

    def _build(self):
        client = Client()
        client.settings = {}
        client.authorization_data = {"ds_user_id": "42"}
        client.uuid = "stub-uuid"
        return client

    async def test_notification_settings_endpoint_and_payload(self):
        client = self._build()
        client.private_request = AsyncMock(return_value={"status": "ok"})

        ok = await client.notification_settings("likes", "off")

        self.assertTrue(ok)
        args, kwargs = client.private_request.call_args
        self.assertEqual(args[0], "notifications/change_notification_settings/")
        self.assertEqual(
            kwargs["data"],
            {
                "content_type": "likes",
                "setting_value": "off",
                "_uid": "42",
                "_uuid": "stub-uuid",
            },
        )

    async def test_notification_settings_returns_false_when_status_not_ok(self):
        client = self._build()
        client.private_request = AsyncMock(return_value={"status": "fail"})
        ok = await client.notification_settings("likes", "off")
        self.assertFalse(ok)

    async def test_notification_likes_rejects_invalid_setting_value(self):
        from aiograpi.exceptions import UnsupportedSettingValue

        client = self._build()
        client.private_request = AsyncMock(return_value={"status": "ok"})

        with self.assertRaises(UnsupportedSettingValue):
            await client.notification_likes(setting_value="invalid")

        client.private_request.assert_not_called()

    async def test_notification_mute_all_rejects_invalid_value(self):
        from aiograpi.exceptions import UnsupportedSettingValue

        client = self._build()
        client.private_request = AsyncMock(return_value={"status": "ok"})

        with self.assertRaises(UnsupportedSettingValue):
            await client.notification_mute_all(setting_value="never")

    async def test_notification_mute_all_uses_mute_all_content_type(self):
        client = self._build()
        client.private_request = AsyncMock(return_value={"status": "ok"})

        await client.notification_mute_all("1_hour")

        kwargs = client.private_request.call_args.kwargs
        self.assertEqual(kwargs["data"]["content_type"], "mute_all")
        self.assertEqual(kwargs["data"]["setting_value"], "1_hour")

    async def test_each_notification_wrapper_calls_settings_with_unique_content_type(
        self,
    ):
        # Walks every notification_* wrapper that takes setting_value=
        # and verifies it dispatches to notification_settings with a
        # unique content_type matching the method name suffix.
        client = self._build()
        client.private_request = AsyncMock(return_value={"status": "ok"})

        wrappers_to_content_type = {
            "notification_likes": "likes",
            "notification_like_and_comment_on_photo_user_tagged": (
                "like_and_comment_on_photo_user_tagged"
            ),
            "notification_user_tagged": "user_tagged",
            "notification_comments": "comments",
            "notification_comment_likes": "comment_likes",
            "notification_first_post": "first_post",
            "notification_new_follower": "new_follower",
            "notification_follow_request_accepted": "follow_request_accepted",
            "notification_connection": "connection_notification",
            "notification_tagged_in_bio": "tagged_in_bio",
            "notification_pending_direct_share": "pending_direct_share",
            "notification_direct_share_activity": "direct_share_activity",
            "notification_direct_group_requests": "direct_group_requests",
            "notification_video_call": "video_call",
            "notification_rooms": "rooms",
            "notification_live_broadcast": "live_broadcast",
            "notification_felix_upload_result": "felix_upload_result",
            "notification_view_count": "view_count",
            "notification_fundraiser_creator": "fundraiser_creator",
            "notification_fundraiser_supporter": "fundraiser_supporter",
            "notification_reminders": "notification_reminders",
            "notification_announcements": "announcements",
            "notification_report_updated": "report_updated",
            "notification_login": "login_notification",
        }

        for method_name, expected_content_type in wrappers_to_content_type.items():
            method = getattr(client, method_name)
            self.assertTrue(
                callable(method),
                f"{method_name} not present on Client",
            )
            client.private_request.reset_mock()
            await method(setting_value="off")
            kwargs = client.private_request.call_args.kwargs
            self.assertEqual(
                kwargs["data"]["content_type"],
                expected_content_type,
                f"{method_name} sent wrong content_type",
            )
            self.assertEqual(kwargs["data"]["setting_value"], "off")

    async def test_notification_disable_calls_many_wrappers(self):
        # notification_disable iterates a hardcoded list of
        # notification_* wrappers calling each with "off". Smoke that
        # it makes more than 5 private_request calls (real list is ~17).
        client = self._build()
        client.private_request = AsyncMock(return_value={"status": "ok"})

        result = await client.notification_disable()

        self.assertTrue(result)
        self.assertGreater(client.private_request.call_count, 5)


class ClientHashtagTestCase(ClientPrivateTestCase):
    REQUIRED_MEDIA_FIELDS = [
        "pk",
        "taken_at",
        "id",
        "media_type",
        "code",
        "thumbnail_url",
        "like_count",
        "caption_text",
        "video_url",
        "view_count",
        "video_duration",
        "title",
    ]

    async def test_hashtag_info(self):
        hashtag = await self.cl.hashtag_info("instagram")
        self.assertIsInstance(hashtag, Hashtag)
        self.assertEqual("instagram", hashtag.name)

    async def test_extract_hashtag_info(self):
        hashtag_a1 = await self.cl.hashtag_info_a1("instagram")
        hashtag_v1 = await self.cl.hashtag_info_v1("instagram")
        self.assertIsInstance(hashtag_a1, Hashtag)
        self.assertIsInstance(hashtag_v1, Hashtag)
        self.assertEqual("instagram", hashtag_a1.name)
        self.assertEqual(hashtag_a1.id, hashtag_v1.id)
        self.assertEqual(hashtag_a1.name, hashtag_v1.name)
        self.assertEqual(hashtag_a1.media_count, hashtag_v1.media_count)

    async def test_hashtag_medias_top(self):
        medias = await self.cl.hashtag_medias_top("instagram", amount=2)
        self.assertEqual(len(medias), 2)
        self.assertIsInstance(medias[0], Media)

    async def test_extract_hashtag_medias_top(self):
        medias_a1 = await self.cl.hashtag_medias_top_a1("instagram", amount=9)
        medias_v1 = await self.cl.hashtag_medias_top_v1("instagram", amount=9)
        self.assertEqual(len(medias_a1), 9)
        self.assertIsInstance(medias_a1[0], Media)
        self.assertEqual(len(medias_v1), 9)
        self.assertIsInstance(medias_v1[0], Media)

    async def test_hashtag_medias_recent(self):
        medias = await self.cl.hashtag_medias_recent("instagram", amount=2)
        self.assertEqual(len(medias), 2)
        self.assertIsInstance(medias[0], Media)

    async def test_extract_hashtag_medias_recent(self):
        medias_v1 = await self.cl.hashtag_medias_recent_v1("instagram", amount=31)
        medias_a1 = await self.cl.hashtag_medias_recent_a1("instagram", amount=31)
        self.assertEqual(len(medias_a1), 31)
        self.assertIsInstance(medias_a1[0], Media)
        self.assertEqual(len(medias_v1), 31)
        self.assertIsInstance(medias_v1[0], Media)
        for i, a1 in enumerate(medias_a1[:10]):
            a1 = a1.dict()
            v1 = medias_v1[i].dict()
            for f in self.REQUIRED_MEDIA_FIELDS:
                a1_val, v1_val = a1[f], v1[f]
                is_album = a1["media_type"] == 8
                is_video = v1.get("video_duration") > 0
                if f == "thumbnail_url" and not is_album:
                    a1_val = a1[f].path.rsplit("/", 1)[1]
                    v1_val = v1[f].path.rsplit("/", 1)[1]
                if f == "video_url" and is_video:
                    a1_val = a1[f].path.rsplit(".", 1)[1]
                    v1_val = v1[f].path.rsplit(".", 1)[1]
                if f in ("view_count", "like_count"):
                    # instagram can different counts for public and private
                    if f == "view_count" and not is_video:
                        continue
                    self.assertTrue(a1_val > 1)
                    self.assertTrue(v1_val > 1)
                    continue
                self.assertEqual(a1_val, v1_val)


class ClientStoryTestCase(ClientPrivateTestCase):
    async def test_story_pk_from_url(self):
        story_pk = self.cl.story_pk_from_url(
            "https://www.instagram.com/stories/instagram/2581281926631793076/"
        )
        self.assertEqual(story_pk, 2581281926631793076)

    async def test_upload_photo_story(self):
        media_pk = await self.cl.media_pk_from_url(
            "https://www.instagram.com/p/B3mr1-OlWMG/"
        )
        path = await self.cl.photo_download(media_pk)
        self.assertIsInstance(path, Path)
        caption = "Test photo caption"
        instagram = await self.user_info_by_username("instagram")
        self.assertIsInstance(instagram, User)
        mentions = [StoryMention(user=instagram)]
        medias = [StoryMedia(media_pk=media_pk, x=0.5, y=0.5, width=0.6, height=0.8)]
        links = [StoryLink(webUri="https://instagram.com/")]
        # hashtags = [StoryHashtag(hashtag=await self.cl.hashtag_info('instagram'))]
        # locations = [
        #     StoryLocation(
        #         location=Location(
        #             pk=150300262230285,
        #             name='Blaues Wunder (Dresden)',
        #         )
        #     )
        # ]
        stickers = [
            StorySticker(
                id="Igjf05J559JWuef4N5",
                type="gif",
                x=0.5,
                y=0.5,
                width=0.4,
                height=0.08,
            )
        ]
        try:
            story = await self.cl.photo_upload_to_story(
                path,
                caption,
                mentions=mentions,
                links=links,
                # hashtags=hashtags,
                # locations=locations,
                stickers=stickers,
                medias=medias,
            )
            self.assertIsInstance(story, Story)
            self.assertTrue(story)
            s = await self.cl.story_info(story.pk)
            self.assertIsInstance(s, Story)
            self.assertTrue(s)
            m, sm = medias[0], s.medias[0]
            self.assertEqual(m.media_pk, sm.media_pk)
            self.assertEqual(m.x, sm.x)
            self.assertEqual(m.y, sm.y)
        finally:
            if path:
                cleanup(path)
            self.assertTrue(await self.cl.story_delete(story.id))

    async def test_upload_video_story(self):
        media_pk = await self.cl.media_pk_from_url(
            "https://www.instagram.com/p/Bk2tOgogq9V/"
        )
        story = None
        path = await self.cl.video_download(media_pk)
        self.assertIsInstance(path, Path)
        caption = "Test video caption"
        instagram = await self.user_info_by_username("instagram")
        self.assertIsInstance(instagram, User)
        mentions = [StoryMention(user=instagram)]
        medias = [StoryMedia(media_pk=media_pk, x=0.5, y=0.5, width=0.6, height=0.8)]
        links = [StoryLink(webUri="https://instagram.com/")]
        # hashtags = [StoryHashtag(hashtag=await self.cl.hashtag_info('instagram'))]
        # locations = [
        #     StoryLocation(
        #         location=Location(
        #             pk=150300262230285,
        #             name='Blaues Wunder (Dresden)',
        #         )
        #     )
        # ]
        try:
            buildout = StoryBuilder(
                path, caption, mentions, Path("./examples/background.png")
            ).video(1)
            story = await self.cl.video_upload_to_story(
                buildout.path,
                caption,
                mentions=buildout.mentions,
                links=links,
                # hashtags=hashtags,
                # locations=locations,
                medias=medias,
            )
            self.assertIsInstance(story, Story)
            self.assertTrue(story)
            s = await self.cl.story_info(story.pk)
            self.assertIsInstance(s, Story)
            self.assertTrue(s)
            m, sm = medias[0], s.medias[0]
            self.assertEqual(m.media_pk, sm.media_pk)
            self.assertEqual(m.x, sm.x)
            self.assertEqual(m.y, sm.y)
        finally:
            cleanup(path)
            if story:
                self.assertTrue(await self.cl.story_delete(story.id))

    async def test_user_stories(self):
        user_id = await self.user_id_from_username("instagram")
        stories = await self.cl.user_stories(user_id, 2)
        self.assertEqual(len(stories), 2)
        story = stories[0]
        self.assertIsInstance(story, Story)
        for field in REQUIRED_STORY_FIELDS:
            self.assertTrue(hasattr(story, field))
        stories = await self.cl.user_stories(
            await self.user_id_from_username("instagram")
        )
        self.assertIsInstance(stories, list)

    async def test_extract_user_stories(self):
        user_id = await self.user_id_from_username("instagram")
        stories_v1 = await self.cl.user_stories_v1(user_id, amount=2)
        stories_gql = await self.cl.user_stories_gql(user_id, amount=2)
        self.assertEqual(len(stories_v1), 2)
        self.assertIsInstance(stories_v1[0], Story)
        self.assertEqual(len(stories_gql), 2)
        self.assertIsInstance(stories_gql[0], Story)
        for i, gql in enumerate(stories_gql[:2]):
            gql = gql.dict()
            v1 = stories_v1[i].dict()
            for f in REQUIRED_STORY_FIELDS:
                gql_val, v1_val = gql[f], v1[f]
                is_video = v1.get("video_duration") > 0
                if f == "video_url" and is_video:
                    gql_val = gql[f].path.rsplit(".", 1)[1]
                    v1_val = v1[f].path.rsplit(".", 1)[1]
                elif f == "thumbnail_url":
                    self.assertIn(".jpg", gql_val)
                    self.assertIn(".jpg", v1_val)
                    continue
                elif f == "user":
                    gql_val.pop("full_name")
                    v1_val.pop("full_name")
                    gql_val.pop("is_private")
                    v1_val.pop("is_private")
                    gql_val["profile_pic_url"] = gql_val["profile_pic_url"].path
                    v1_val["profile_pic_url"] = v1_val["profile_pic_url"].path
                elif f == "mentions":
                    for item in [*gql_val, *v1_val]:
                        item["user"].pop("pk")
                        item["user"].pop("profile_pic_url")
                        item.pop("width")
                        item.pop("height")
                        item["x"] = round(item["x"], 4)
                        item["y"] = round(item["y"], 4)
                elif f == "links":
                    # [{'webUri': HttpUrl('https://youtu.be/x3GYpar-e64', scheme='https', host='youtu.be', tld='be', host_type='domain', path='/x3GYpar-e64')}]
                    # [{'webUri': HttpUrl('https://l.instagram.com/?u=https%3A%2F%2Fyoutu.be%2Fx3GYpar-e64&e=ATM59nvUNmptw8vUsyoX835T....}]
                    self.assertEqual(len(v1_val), len(gql_val))
                    if gql_val:
                        self.assertIn(
                            gql_val[0]["webUri"].host, v1_val[0]["webUri"].query
                        )
                    continue
                if gql_val != v1_val:
                    import pudb

                    pudb.set_trace()
                self.assertEqual(gql_val, v1_val)

    async def test_story_info(self):
        user_id = await self.user_id_from_username("instagram")
        stories = await self.cl.user_stories(user_id, amount=1)
        story = await self.cl.story_info(stories[0].pk)
        self.assertIsInstance(story, Story)
        story = await self.cl.story_info(stories[0].id)
        self.assertIsInstance(story, Story)
        self.assertTrue(await self.cl.story_seen([story.pk]))


# class BloksTestCase(ClientPrivateTestCase):
#
#     def test_bloks_change_password(self):
#         last_json = {
#             'step_name': 'change_password',
#             'step_data': {'new_password1': 'None', 'new_password2': 'None'},
#             'flow_render_type': 3,
#             'bloks_action': 'com.instagram.challenge.navigation.take_challenge',
#             'cni': 12346879508000123,
#             'challenge_context': '{"step_name": "change_password", "cni": 12346879508000123, "is_stateless": false, "challenge_type_enum": "PASSWORD_RESET"}',
#             'challenge_type_enum_str': 'PASSWORD_RESET',
#             'status': 'ok'
#         }
#        self.assertTrue(await self.cl.bloks_change_password("2r9j20r9j4230t8hj39tHW4"))


class TOTPTestCase(ClientPrivateTestCase):
    async def test_totp_code(self):
        seed = await self.cl.totp_generate_seed()
        code = self.cl.totp_generate_code(seed)
        self.assertIsInstance(code, str)
        self.assertTrue(code.isdigit())
        self.assertEqual(len(code), 6)


class ClientHighlightTestCase(ClientPrivateTestCase):
    async def test_highlight_pk_from_url(self):
        highlight_pk = self.cl.highlight_pk_from_url(
            "https://www.instagram.com/stories/highlights/17983407089364361/"
        )
        self.assertEqual(highlight_pk, "17983407089364361")

    async def test_highlight_info(self):
        highlight = await self.cl.highlight_info(17983407089364361)
        self.assertIsInstance(highlight, Highlight)
        self.assertEqual(highlight.pk, "17983407089364361")
        self.assertTrue(len(highlight.items) > 0)
        self.assertEqual(len(highlight.items), highlight.media_count)
        self.assertEqual(len(highlight.items), len(highlight.media_ids))


class ClientShareTestCase(ClientPrivateTestCase):
    async def test_share_code_from_url(self):
        url = "https://www.instagram.com/s/aGlnaGxpZ2h0OjE3OTMzOTExODE2NTY4Njcx?utm_medium=share_sheet"
        code = self.cl.share_code_from_url(url)
        self.assertEqual(code, "aGlnaGxpZ2h0OjE3OTMzOTExODE2NTY4Njcx")

    async def test_share_info_by_url(self):
        url = "https://www.instagram.com/s/aGlnaGxpZ2h0OjE3OTMzOTExODE2NTY4Njcx?utm_medium=share_sheet"
        share = self.cl.share_info_by_url(url)
        self.assertIsInstance(share, Share)
        self.assertEqual(share.pk, "17933911816568671")
        self.assertEqual(share.type, "highlight")

    async def test_share_info(self):
        share = self.cl.share_info("aGlnaGxpZ2h0OjE3OTMzOTExODE2NTY4Njcx")
        self.assertIsInstance(share, Share)
        self.assertEqual(share.pk, "17933911816568671")
        self.assertEqual(share.type, "highlight")
        # UnicodeDecodeError: 'utf-8' codec can't decode byte 0xb1 in position 6: invalid start byte
        share = self.cl.share_info("aGlnaGxpsdsdZ2h0OjE3OTg4MDg5NjI5MzgzNzcw")
        self.assertIsInstance(share, Share)
        self.assertEqual(share.pk, "17988089629383770")
        self.assertEqual(share.type, "highlight")


class ClientCutoutStickerTestCase(ClientPrivateTestCase):
    """Test cases for Cutout Sticker functionality (PR #2342)"""

    async def test_photo_upload_to_cutout_sticker_bypass_ai(self):
        """Test uploading a photo as cutout sticker with AI bypass (full image selection)"""
        # Download a test photo
        media_pk = await self.cl.media_pk_from_url(
            "https://www.instagram.com/p/BVDOOolFFxg/"
        )
        path = await self.cl.photo_download(media_pk)
        self.assertIsInstance(path, Path)
        media = None
        try:
            # Upload as cutout sticker with bypass_ai=True (default)
            media = await self.cl.photo_upload_to_cutout_sticker(path, bypass_ai=True)
            self.assertIsInstance(media, Media)
            # Cutout stickers should have product_type "custom_sticker"
            self.assertEqual(media.product_type, "custom_sticker")
        finally:
            cleanup(path)
            if media:
                await self.cl.media_delete(media.id)

    async def test_photo_upload_to_cutout_sticker_with_ai(self):
        """Test uploading a photo as cutout sticker with AI detection"""
        # Download a test photo
        media_pk = await self.cl.media_pk_from_url(
            "https://www.instagram.com/p/BVDOOolFFxg/"
        )
        path = await self.cl.photo_download(media_pk)
        self.assertIsInstance(path, Path)
        media = None
        try:
            # Upload as cutout sticker with AI detection
            media = await self.cl.photo_upload_to_cutout_sticker(path, bypass_ai=False)
            self.assertIsInstance(media, Media)
            self.assertEqual(media.product_type, "custom_sticker")
        finally:
            cleanup(path)
            if media:
                await self.cl.media_delete(media.id)


class ChapiPortedRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    """
    Regression tests for endpoints ported from the chapi async client.
    Each test stubs out the underlying request layer so we can assert the
    method shapes its parameters / form data the way IG expects without
    talking to the live service.
    """

    def build_client(self):
        client = Client()
        client.settings = {}
        client.authorization_data = {"ds_user_id": "1"}
        client.uuid = "stub-uuid"
        client.last_json = {}
        return client

    # --- fbsearch ---

    async def test_fbsearch_item_passes_params_and_optional_cursors(self):
        client = self.build_client()
        client.private_request = AsyncMock(return_value={"items": []})

        result = await client.fbsearch_item(
            "clips_serp_page",
            search_surface="clips_serp_page",
            query="metallica",
            count=20,
            reels_max_id="r:abc",
            paging_token='{"total_num_items":4}',
        )

        self.assertEqual(result, {"items": []})
        client.private_request.assert_awaited_once()
        args, kwargs = client.private_request.call_args
        self.assertEqual(args[0], "fbsearch/clips_serp_page/")
        params = kwargs["params"]
        self.assertEqual(params["search_surface"], "clips_serp_page")
        self.assertEqual(params["query"], "metallica")
        self.assertEqual(params["count"], 20)
        self.assertEqual(params["reels_max_id"], "r:abc")
        self.assertEqual(params["paging_token"], '{"total_num_items":4}')
        self.assertNotIn("rank_token", params)

    async def test_fbsearch_keyword_typeahead_sets_blended_context(self):
        client = self.build_client()
        client.private_request = AsyncMock(return_value={"list": []})

        result = await client.fbsearch_keyword_typeahead("metal", count=10)

        self.assertEqual(result, {"list": []})
        args, kwargs = client.private_request.call_args
        self.assertEqual(args[0], "fbsearch/keyword_typeahead/")
        self.assertEqual(
            kwargs["params"],
            {
                "search_surface": "typeahead_search_page",
                "query": "metal",
                "context": "blended",
                "count": 10,
            },
        )

    async def test_fbsearch_typeahead_stream_hits_stream_endpoint(self):
        client = self.build_client()
        client.private_request = AsyncMock(return_value={"stream_rows": []})

        await client.fbsearch_typeahead_stream("metal")

        args, _ = client.private_request.call_args
        self.assertEqual(args[0], "fbsearch/typeahead_stream/")

    async def test_fbsearch_accounts_v2_sets_account_serp_surface(self):
        client = self.build_client()
        client.timezone_offset = -14400
        client.private_request = AsyncMock(return_value={"users": []})

        await client.fbsearch_accounts_v2("metallica")

        args, kwargs = client.private_request.call_args
        self.assertEqual(args[0], "fbsearch/account_serp/")
        params = kwargs["params"]
        self.assertEqual(params["search_surface"], "account_serp")
        self.assertEqual(params["query"], "metallica")
        self.assertEqual(params["timezone_offset"], -14400)
        self.assertNotIn("page_token", params)

    async def test_fbsearch_accounts_v2_forwards_page_token(self):
        client = self.build_client()
        client.timezone_offset = 0
        client.private_request = AsyncMock(return_value={"users": []})

        await client.fbsearch_accounts_v2("metallica", page_token="tok-2")

        params = client.private_request.call_args.kwargs["params"]
        self.assertEqual(params["page_token"], "tok-2")

    async def test_fbsearch_reels_v2_sets_clips_search_page_surface(self):
        client = self.build_client()
        client.timezone_offset = 0
        client.private_request = AsyncMock(return_value={"items": []})

        await client.fbsearch_reels_v2("metal", reels_max_id="r:abc", rank_token="rt-1")

        args, kwargs = client.private_request.call_args
        self.assertEqual(args[0], "fbsearch/reels_serp/")
        params = kwargs["params"]
        self.assertEqual(params["search_surface"], "clips_search_page")
        self.assertEqual(params["query"], "metal")
        self.assertEqual(params["reels_max_id"], "r:abc")
        self.assertEqual(params["rank_token"], "rt-1")

    async def test_fbsearch_reels_v2_omits_optional_cursors(self):
        client = self.build_client()
        client.timezone_offset = 0
        client.private_request = AsyncMock(return_value={"items": []})

        await client.fbsearch_reels_v2("metal")

        params = client.private_request.call_args.kwargs["params"]
        self.assertNotIn("reels_max_id", params)
        self.assertNotIn("rank_token", params)

    async def test_fbsearch_topsearch_v2_uses_top_serp_and_self_rank_token(self):
        client = self.build_client()
        client.timezone_offset = 0
        # rank_token is a @property returning self.uuid
        client.uuid = "self-rank"
        client.private_request = AsyncMock(return_value={"list": []})

        await client.fbsearch_topsearch_v2("metal")

        args, kwargs = client.private_request.call_args
        self.assertEqual(args[0], "fbsearch/top_serp/")
        params = kwargs["params"]
        self.assertEqual(params["search_surface"], "top_serp")
        self.assertEqual(params["rank_token"], "self-rank")

    async def test_fbsearch_topsearch_v2_explicit_rank_token_overrides_self(self):
        client = self.build_client()
        client.timezone_offset = 0
        client.uuid = "self-rank"
        client.private_request = AsyncMock(return_value={"list": []})

        await client.fbsearch_topsearch_v2(
            "metal",
            next_max_id="m:1",
            reels_max_id="r:2",
            rank_token="caller-rank",
        )

        params = client.private_request.call_args.kwargs["params"]
        self.assertEqual(params["rank_token"], "caller-rank")
        self.assertEqual(params["next_max_id"], "m:1")
        self.assertEqual(params["reels_max_id"], "r:2")

    async def test_fbsearch_typehead_flattens_stream_rows(self):
        client = self.build_client()
        client.timezone_offset = 0
        client.private_request = AsyncMock(
            return_value={
                "stream_rows": [
                    {"users": [{"pk": "1"}, {"pk": "2"}]},
                    {"users": [{"pk": "3"}]},
                    {"users": []},
                    {},  # row missing 'users' key entirely
                ]
            }
        )

        users = await client.fbsearch_typehead("metal")

        args, _ = client.private_request.call_args
        self.assertEqual(args[0], "fbsearch/typeahead_stream/")
        self.assertEqual([u["pk"] for u in users], ["1", "2", "3"])

    async def test_fbsearch_typehead_handles_empty_response(self):
        client = self.build_client()
        client.timezone_offset = 0
        client.private_request = AsyncMock(return_value={})

        users = await client.fbsearch_typehead("metal")

        self.assertEqual(users, [])

    # --- track ---

    async def test_track_stream_info_by_id_uses_clips_pivot_endpoint(self):
        client = self.build_client()
        client.private_request = AsyncMock(return_value={"items": []})

        await client.track_stream_info_by_id("18462251209012169")

        args, kwargs = client.private_request.call_args
        self.assertEqual(args[0], "clips/stream_clips_pivot_page/")
        # _track_request passes data as positional arg #1
        data = args[1]
        self.assertEqual(data["pivot_page_type"], "audio")
        self.assertEqual(data["_uuid"], "stub-uuid")
        self.assertEqual(
            data["music_page"],
            {
                "tab_type": "clips",
                "audio_asset_id": "18462251209012169",
                "audio_cluster_id": "18462251209012169",
            },
        )

    async def test_track_stream_info_by_id_forwards_max_id(self):
        client = self.build_client()
        client.private_request = AsyncMock(return_value={"items": []})

        await client.track_stream_info_by_id("18462251209012169", max_id="cursor-2")

        data = client.private_request.call_args.args[1]
        self.assertEqual(data["music_page"]["max_id"], "cursor-2")

    # --- media v2 ---

    async def test_media_info_v2_strips_userid_suffix_from_media_id(self):
        client = self.build_client()
        client.private_request = AsyncMock(
            return_value={
                "media_or_ad": {
                    "id": "2154602296692269830_25025320",
                    "pk": "2154602296692269830",
                    "code": "B-fKL9qpeab",
                    "media_type": 1,
                    "taken_at": 1710000000,
                    "user": {
                        "pk": "25025320",
                        "username": "instagram",
                        "profile_pic_url": "https://example.com/p.jpg",
                    },
                    "image_versions2": {
                        "candidates": [
                            {
                                "url": "https://example.com/i.jpg",
                                "width": 1,
                                "height": 1,
                            }
                        ]
                    },
                    "like_count": 0,
                }
            }
        )

        media = await client.media_info_v2("2154602296692269830_25025320")

        args, kwargs = client.private_request.call_args
        self.assertEqual(args[0], "discover/media_metadata/")
        # _userid suffix is stripped before the call.
        self.assertEqual(kwargs["params"], {"media_id": "2154602296692269830"})
        self.assertEqual(media.pk, "2154602296692269830")

    async def test_media_info_v2_raises_media_not_found_when_payload_missing(self):
        from aiograpi.exceptions import MediaNotFound

        client = self.build_client()
        client.private_request = AsyncMock(return_value={"status": "ok"})
        client.last_json = {}

        with self.assertRaises(MediaNotFound):
            await client.media_info_v2("2154602296692269830")

    async def test_media_check_offensive_comment_v2_uses_lighter_payload(self):
        client = self.build_client()
        client.uuid = "stub-uuid"
        # Fake user_id so PreLoginRequired guard passes.
        client.authorization_data = {"ds_user_id": "1"}
        client.private_request = AsyncMock(
            return_value={"is_offensive": False, "category": None}
        )

        result = await client.media_check_offensive_comment_v2(
            "2154602296692269830", "hello there"
        )

        # Returns the full payload (not just the bool), unlike v1.
        self.assertEqual(result, {"is_offensive": False, "category": None})
        args, kwargs = client.private_request.call_args
        self.assertEqual(args[0], "media/comment/check_offensive_comment/")
        self.assertEqual(
            kwargs["data"],
            {
                "comment_text": "hello there",
                "media_id": "2154602296692269830",
                "_uuid": "stub-uuid",
            },
        )

    async def test_media_check_offensive_comment_v2_requires_login(self):
        from aiograpi.exceptions import PreLoginRequired

        client = self.build_client()
        client.authorization_data = None

        with self.assertRaises(PreLoginRequired):
            await client.media_check_offensive_comment_v2("123", "x")

    # --- comment ---

    async def test_media_comment_infos_joins_list_into_csv(self):
        client = self.build_client()
        client.private_request = AsyncMock(return_value={"comments": {}})

        await client.media_comment_infos(["3391_56", "3392_56"])

        args, kwargs = client.private_request.call_args
        self.assertEqual(args[0], "media/comment_infos/")
        self.assertEqual(kwargs["params"]["media_ids"], "3391_56,3392_56")
        self.assertEqual(kwargs["params"]["can_support_carousel_mentions"], "false")

    async def test_media_comment_infos_accepts_string(self):
        client = self.build_client()
        client.private_request = AsyncMock(return_value={"comments": {}})

        await client.media_comment_infos("3391_56,3392_56")

        _, kwargs = client.private_request.call_args
        self.assertEqual(kwargs["params"]["media_ids"], "3391_56,3392_56")

    # --- user / timeline ---

    async def test_feed_user_stream_item_posts_uuid(self):
        client = self.build_client()
        client.private_request = AsyncMock(return_value={"items": []})

        await client.feed_user_stream_item("123", is_pull_to_refresh=True)

        args, kwargs = client.private_request.call_args
        self.assertEqual(args[0], "feed/user_stream/123/")
        self.assertEqual(kwargs["data"]["_uuid"], "stub-uuid")
        self.assertEqual(kwargs["data"]["is_pull_to_refresh"], "true")

    async def test_feed_user_stream_item_omits_pull_to_refresh_by_default(self):
        client = self.build_client()
        client.private_request = AsyncMock(return_value={"items": []})

        await client.feed_user_stream_item("999")

        _, kwargs = client.private_request.call_args
        self.assertNotIn("is_pull_to_refresh", kwargs["data"])

    # --- private_graphql_query_request based wrappers ---

    async def test_private_graphql_followers_list_builds_variables(self):
        client = self.build_client()
        captured = {}

        async def fake_call(**kwargs):
            captured.update(kwargs)
            return {"data": {"xdt_api__v1__friendships__followers": {}}}

        client.private_graphql_query_request = fake_call
        result = await client.private_graphql_followers_list(
            user_id=42,
            rank_token="rank-1",
            client_doc_id="111",
            max_id=50,
            priority="u=3, i",
        )

        self.assertIn("data", result)
        self.assertEqual(captured["friendly_name"], "FollowersList")
        self.assertEqual(
            captured["root_field_name"],
            "xdt_api__v1__friendships__followers",
        )
        self.assertEqual(captured["client_doc_id"], "111")
        self.assertEqual(captured["priority"], "u=3, i")
        variables = captured["variables"]
        self.assertEqual(variables["user_id"], "42")
        self.assertEqual(variables["max_id"], 50)
        self.assertEqual(
            variables["request_data"],
            {"rank_token": "rank-1", "enableGroups": True},
        )
        self.assertEqual(variables["search_surface"], "follow_list_page")

    async def test_private_graphql_following_list_builds_variables(self):
        client = self.build_client()
        captured = {}

        async def fake_call(**kwargs):
            captured.update(kwargs)
            return {"data": {}}

        client.private_graphql_query_request = fake_call
        await client.private_graphql_following_list(user_id="77", rank_token="rank-2")

        self.assertEqual(captured["friendly_name"], "FollowingList")
        self.assertEqual(
            captured["root_field_name"],
            "xdt_api__v1__friendships__following",
        )
        self.assertEqual(captured["variables"]["user_id"], "77")
        self.assertEqual(captured["variables"]["request_data"]["rank_token"], "rank-2")
        self.assertTrue(captured["variables"]["request_data"]["includes_hashtags"])

    async def test_private_graphql_clips_profile_includes_initial_stream_count(
        self,
    ):
        client = self.build_client()
        captured = {}

        async def fake_call(**kwargs):
            captured.update(kwargs)
            return {"stream_rows": []}

        client.private_graphql_query_request = fake_call
        await client.private_graphql_clips_profile(
            target_user_id="11",
            initial_stream_count=4,
            page_size=8,
            no_of_medias_in_each_chunk=2,
        )

        self.assertEqual(captured["friendly_name"], "ClipsProfileQuery")
        self.assertEqual(captured["root_field_name"], "xdt_user_clips_graphql")
        variables = captured["variables"]
        self.assertEqual(variables["initial_stream_count"], 4)
        self.assertEqual(variables["data"]["target_user_id"], "11")
        self.assertEqual(variables["data"]["page_size"], 8)
        self.assertEqual(variables["data"]["no_of_medias_in_each_chunk"], 2)
        # Streaming flags must stay False — IG returns multi-document
        # NDJSON when they're True, and response.json() can't parse it
        # (regression covered in 0.6.2 changelog).
        self.assertFalse(variables["use_stream"])
        self.assertFalse(variables["use_defer"])
        self.assertFalse(variables["stream_use_customized_batch"])
        self.assertFalse(variables["data"]["should_stream_response"])

    async def test_private_graphql_inbox_tray_for_user(self):
        client = self.build_client()
        captured = {}

        async def fake_call(**kwargs):
            captured.update(kwargs)
            return {"data": {}}

        client.private_graphql_query_request = fake_call
        await client.private_graphql_inbox_tray_for_user("17")

        self.assertEqual(captured["friendly_name"], "InboxTrayRequestForUserQuery")
        self.assertEqual(captured["root_field_name"], "xdt_get_inbox_tray_items")
        self.assertEqual(captured["variables"]["user_id"], "17")
        self.assertFalse(
            captured["variables"]["should_fetch_content_note_stack_video_info"]
        )

    async def test_private_graphql_memories_pog_passes_region_hint(self):
        client = self.build_client()
        captured = {}

        async def fake_call(**kwargs):
            captured.update(kwargs)
            return {"data": {}}

        client.private_graphql_query_request = fake_call
        await client.private_graphql_memories_pog(direct_region_hint="REGION-X")

        self.assertEqual(captured["friendly_name"], "MemoriesPogQuery")
        self.assertEqual(captured["root_field_name"], "xdt_get_story_memories_pog")
        self.assertEqual(
            captured["extra_headers"],
            {"ig-u-ig-direct-region-hint": "REGION-X"},
        )
        self.assertEqual(captured["variables"], {"request": {"user_id": 0}})

    async def test_private_graphql_realtime_region_hint_uses_priority(self):
        client = self.build_client()
        captured = {}

        async def fake_call(**kwargs):
            captured.update(kwargs)
            return {"data": {}}

        client.private_graphql_query_request = fake_call
        await client.private_graphql_realtime_region_hint()

        self.assertEqual(captured["friendly_name"], "IGRealtimeRegionHintQuery")
        self.assertEqual(captured["root_field_name"], "xdt_igd_msg_region")
        self.assertEqual(captured["priority"], "u=3, i")

    async def test_private_graphql_top_audio_trends_eligible(self):
        client = self.build_client()
        captured = {}

        async def fake_call(**kwargs):
            captured.update(kwargs)
            return {"data": {}}

        client.private_graphql_query_request = fake_call
        await client.private_graphql_top_audio_trends_eligible_categories()

        self.assertEqual(
            captured["friendly_name"],
            "GetTopAudioTrendsEligibleCategories",
        )
        self.assertEqual(
            captured["root_field_name"],
            "xdt_top_audio_trends_eligible_tabs",
        )
        self.assertEqual(captured["variables"], {})

    async def test_private_graphql_update_inbox_tray_last_seen(self):
        client = self.build_client()
        captured = {}

        async def fake_call(**kwargs):
            captured.update(kwargs)
            return {"data": {}}

        client.private_graphql_query_request = fake_call
        await client.private_graphql_update_inbox_tray_last_seen()

        self.assertEqual(captured["friendly_name"], "UpdateInboxTrayLastSeenTimestamp")
        self.assertEqual(captured["root_field_name"], "__typename")


if __name__ == "__main__":
    unittest.main()

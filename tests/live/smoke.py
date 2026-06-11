"""Live end-to-end smoke for aiograpi.

Exits 0 if all REQUIRED checks pass; non-zero otherwise. Optional
checks (anonymous public web paths and chapi-style new endpoints) are
reported but never fail the build — IG rotates doc_ids and throttles
anonymous web requests, and we don't want a flaky CI gate.

Required env: TEST_ACCOUNTS_URL pointing at an accounts endpoint
that returns at least one usable account (with TOTP seed if 2FA is
enabled). Skips cleanly if unset.
"""

import asyncio
import json
import os
import ssl
import sys
import urllib.request
import uuid
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from aiograpi import Client
from tests.live.auth_helpers import login_with_timeout


def _summarize(out):
    if hasattr(out, "username"):
        return f"{out.username}/{out.pk}"
    if hasattr(out, "name"):
        return out.name
    if isinstance(out, tuple) and out:
        first = out[0]
        if isinstance(first, (list, dict, set, tuple)):
            cursor = out[1] if len(out) > 1 else None
            return f"len={len(first)} cursor={bool(cursor)}"
    if isinstance(out, (list, dict, set, tuple)):
        return f"len={len(out)}"
    return str(out)[:50]


async def _fetch_accounts(url, count=10):
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["count"] = str(count)
    url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 aiograpi-smoke"},
    )
    with urllib.request.urlopen(req, context=ssl._create_unverified_context()) as r:
        return json.loads(r.read())


async def _login_first_usable(accs):
    for i, acc in enumerate(accs, 1):
        try:
            c = Client()
            settings = dict(acc.get("client_settings") or acc.get("settings") or {})
            totp_seed = settings.pop("totp_seed", None) or acc.get("totp_seed")
            c.set_settings(settings)
            if acc.get("proxy"):
                c.set_proxy(acc["proxy"])
            kwargs = {
                "username": acc["username"],
                "password": acc["password"],
                "relogin": True,
            }
            if totp_seed:
                kwargs["verification_code"] = c.totp_generate_code(totp_seed)
            await login_with_timeout(c, **kwargs)
            print(f"LOGIN_OK acc{i} {acc['username']} (user_id={c.user_id})")
            return c
        except Exception as e:
            print(f"acc{i} {acc.get('username', '?')}: {type(e).__name__}: {str(e)[:120]}")
    return None


async def main():
    if not os.environ.get("TEST_ACCOUNTS_URL"):
        print("SKIP: TEST_ACCOUNTS_URL not set")
        return 0

    accs = await _fetch_accounts(os.environ["TEST_ACCOUNTS_URL"])
    print(f"pool: {len(accs)} accs")

    failures = []

    # OPTIONAL: anonymous public path. IG often throttles this web endpoint
    # with 429 while logged-in app-backed checks are healthy.
    try:
        c = Client()
        u = await c.user_info_by_username_gql("instagram")
        assert u.username == "instagram" and u.pk == "25025320"
        print(f"opt anonymous_public_gql: {u.username}/{u.pk}")
    except Exception as e:
        print(f"opt anonymous_public_gql: {type(e).__name__}: {str(e)[:140]}")

    try:
        import curl_adapter  # noqa: F401

        c = Client(public_transport="curl", public_request_retries_count=2)
        u = await c.user_info_by_username_gql("instagram")
        assert u.username == "instagram" and u.pk == "25025320"
        print(f"opt curl_public_gql: {u.username}/{u.pk}")
    except ImportError:
        print("opt curl_public_gql: skipped (install aiograpi[curl])")
    except Exception as e:
        print(f"opt curl_public_gql: {type(e).__name__}: {str(e)[:140]}")

    # REQUIRED: login (TOTP) + private path
    cl = await _login_first_usable(accs)
    if cl is None:
        failures.append(("login", "all pool accounts unusable"))
    else:
        try:
            if not cl.sessionid:
                raise RuntimeError("logged-in client did not expose sessionid")
            by_session = Client()
            proxy = getattr(cl, "proxy", None)
            if isinstance(proxy, str) and proxy:
                by_session.set_proxy(proxy)
            await by_session.login_by_sessionid(cl.sessionid)
            account = await by_session.account_info()
            assert str(account.pk) == str(cl.user_id)
            await by_session.get_timeline_feed("cold_start_fetch")
            print("REQ sessionid_login: account_info/timeline")
        except Exception as e:
            failures.append(("sessionid_login", f"{type(e).__name__}: {str(e)[:140]}"))

        for name, fn in [
            ("private_v1", lambda: cl.user_info_by_username_v1("instagram")),
            ("user_info_by_username", lambda: cl.user_info_by_username("instagram")),
            ("user_info", lambda: cl.user_info("25025320")),
            ("username_from_user_id", lambda: cl.username_from_user_id("25025320")),
            ("hashtag_info_v1", lambda: cl.hashtag_info_v1("python")),
            ("timeline_feed", lambda: cl.get_timeline_feed("cold_start_fetch")),
            ("clip_info_for_creation", lambda: cl.clip_info_for_creation()),
            ("direct_search", lambda: cl.direct_search("instagram")),
            ("user_medias", lambda: cl.user_medias("25025320", amount=3)),
            ("user_medias_paginated", lambda: cl.user_medias_paginated("25025320", amount=2)),
            ("user_followers", lambda: cl.user_followers("25025320", amount=10, use_cache=False)),
            ("user_following", lambda: cl.user_following("25025320", amount=10, use_cache=False)),
            ("user_stories", lambda: cl.user_stories("25025320", amount=10)),
            ("highlight_info", lambda: cl.highlight_info(17983407089364361)),
        ]:
            try:
                out = await fn()
                print(f"REQ {name}: {_summarize(out)}")
            except Exception as e:
                failures.append((name, e))
                print(f"REQ {name} FAIL: {type(e).__name__}: {str(e)[:140]}")

        try:
            followers = await cl.user_followers_v1("25025320", amount=5)
            assert len(followers) == 5
            follower = followers[0]
            assert isinstance(follower.is_verified, bool)
            assert isinstance(follower.latest_reel_media, int)
            assert isinstance(follower.has_anonymous_profile_picture, bool)
            print("REQ user_followers_extended_fields: ok")
        except Exception as e:
            failures.append(("user_followers_extended_fields", e))
            print(f"REQ user_followers_extended_fields FAIL: {type(e).__name__}: {str(e)[:140]}")

    # OPTIONAL: chapi-ported endpoints — record but don't fail
    if cl is not None:
        rank_token = str(uuid.uuid4())
        instagram_pk = "25025320"
        opt_pass = 0
        opt_skipped = 0
        opt_checks = [
            (
                "fbsearch_keyword_typeahead",
                "fbsearch_keyword_typeahead",
                ("python",),
                {},
            ),
            (
                "fbsearch_typeahead_stream",
                "fbsearch_typeahead_stream",
                ("python",),
                {},
            ),
            (
                "fbsearch_item_top",
                "fbsearch_item",
                ("top_serp", "top_serp", "python"),
                {},
            ),
            ("fbsearch_accounts_v2", "fbsearch_accounts_v2", ("python",), {}),
            ("fbsearch_reels_v2", "fbsearch_reels_v2", ("python",), {}),
            ("fbsearch_topsearch_v2", "fbsearch_topsearch_v2", ("python",), {}),
            ("fbsearch_typehead", "fbsearch_typehead", ("pyt",), {}),
            ("user_stream_by_id_v1", "user_stream_by_id_v1", (instagram_pk,), {}),
            ("user_stream_by_id_flat", "user_stream_by_id_flat", (instagram_pk,), {}),
            (
                "user_stream_by_username_flat",
                "user_stream_by_username_flat",
                ("instagram",),
                {},
            ),
            (
                "user_web_profile_info_v1",
                "user_web_profile_info_v1",
                ("instagram",),
                {},
            ),
            (
                "discover_recommended_accounts_for_category_v1",
                "discover_recommended_accounts_for_category_v1",
                (instagram_pk,),
                {},
            ),
            (
                "user_related_profiles_gql",
                "user_related_profiles_gql",
                (instagram_pk,),
                {},
            ),
            (
                "public_head_share_link",
                "public_head",
                ("https://www.instagram.com/share/p/BALv9Ep4YH",),
                {},
            ),
            (
                "track_stream_info_by_id",
                "track_stream_info_by_id",
                ("18462251209012169",),
                {},
            ),
            (
                "media_info_v2",
                "media_info_v2",
                ("2278584739065882267",),
                {},
            ),
            ("feed_user_stream_item", "feed_user_stream_item", (instagram_pk,), {}),
            (
                "private_graphql_followers_list",
                "private_graphql_followers_list",
                (instagram_pk,),
                {"rank_token": rank_token, "order": "date_followed_latest"},
            ),
            (
                "private_graphql_following_list",
                "private_graphql_following_list",
                (instagram_pk,),
                {"rank_token": rank_token, "order": "date_followed_earliest"},
            ),
            (
                "private_graphql_clips_profile",
                "private_graphql_clips_profile",
                (instagram_pk,),
                {},
            ),
            (
                "private_graphql_inbox_tray_for_user",
                "private_graphql_inbox_tray_for_user",
                (cl.user_id,),
                {},
            ),
            (
                "private_graphql_realtime_region_hint",
                "private_graphql_realtime_region_hint",
                (),
                {},
            ),
            (
                "private_graphql_top_audio_trends",
                "private_graphql_top_audio_trends_eligible_categories",
                (),
                {},
            ),
            ("private_graphql_memories_pog", "private_graphql_memories_pog", (), {}),
            (
                "private_graphql_update_inbox_tray_last_seen",
                "private_graphql_update_inbox_tray_last_seen",
                (),
                {},
            ),
            (
                "logged_user_info_v2_gql",
                "user_info_by_username_v2_gql",
                ("instagram",),
                {},
            ),
            ("logged_user_short_gql", "user_short_gql", (instagram_pk,), {}),
            ("logged_user_medias_gql", "user_medias_gql", (instagram_pk,), {"amount": 3}),
            ("direct_pending_requests_preview", "direct_pending_requests_preview", (), {}),
            ("direct_has_interop_upgraded", "direct_has_interop_upgraded", (), {}),
            ("direct_search_gen_ai_bots", "direct_search_gen_ai_bots", (), {"amount": 2}),
            ("direct_channels", "direct_channels", (), {}),
            (
                "music_verify_original_audio_title",
                "music_verify_original_audio_title",
                ("Original Audio",),
                {},
            ),
            ("music_trending", "music_trending", (), {}),
            ("music_search_v2", "music_search_v2", ("love",), {}),
            ("music_clips_audio_browser", "music_clips_audio_browser", (), {}),
        ]
        for name, attr, args, kwargs in opt_checks:
            fn = getattr(cl, attr, None)
            if fn is None:
                opt_skipped += 1
                print(f"opt {name}: skipped (not implemented)")
                continue
            try:
                await fn(*args, **kwargs)
                print(f"opt {name}: PASS")
                opt_pass += 1
            except Exception as e:
                print(f"opt {name}: {type(e).__name__}: {str(e)[:140]}")
        print(f"OPTIONAL: {opt_pass}/{len(opt_checks)} chapi methods OK ({opt_skipped} skipped)")

    if failures:
        print(f"\nFAILED: {len(failures)} required check(s)")
        return 1
    print("\nALL REQUIRED PASS")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

"""Live end-to-end smoke for aiograpi.

Exits 0 if all REQUIRED checks pass; non-zero otherwise. Optional
checks (anonymous public web paths and chapi-style new endpoints) are
reported but never fail the build — IG rotates doc_ids and throttles
anonymous web requests, and we don't want a flaky CI gate.

Required env: TEST_ACCOUNTS_URL pointing at an accounts endpoint
that returns at least one usable account (with TOTP seed if 2FA is
enabled). Skips cleanly if unset.

Reports only operation labels, attempt indices, collection counts, exception
classes, and numeric HTTP status codes. Dependency output is suppressed;
account data, endpoint responses, and raw exception messages are never printed.
"""

import asyncio
import json
import logging
import os
import ssl
import sys
import tempfile
import urllib.request
import uuid
from contextlib import ExitStack, contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from aiograpi import Client
from aiograpi.types import UserShort
from tests.live.auth_helpers import login_with_timeout


def _summarize(out):
    if isinstance(out, tuple) and out:
        first = out[0]
        if isinstance(first, (list, dict, set, tuple)):
            cursor = out[1] if len(out) > 1 else None
            return f"len={len(first)} cursor={bool(cursor)}"
    if isinstance(out, (list, dict, set, tuple)):
        return f"len={len(out)}"
    return "ok"


def _error_summary(exc):
    name = type(exc).__name__
    response = getattr(exc, "response", None)
    for status in (getattr(response, "status_code", None), getattr(exc, "code", None)):
        if type(status) is int and 100 <= status <= 599:
            return f"{name} HTTP {status}"
    return name


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


async def _login_first_usable(accs, report=print):
    for i, acc in enumerate(accs, 1):
        try:
            # Fresh login tests use the supported app profile while retaining the supplied device.
            c = Client(override_app_version=True)
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
            report(f"LOGIN_OK acc{i}")
            return c
        except Exception as e:
            report(f"acc{i}: {_error_summary(e)}")
    return None


async def _check_fbsearch_suggested_profiles(primary, accounts, report):
    async def check(client):
        suggested = await client.fbsearch_suggested_profiles("25025320")
        assert suggested
        assert isinstance(suggested[0], UserShort)
        assert isinstance(suggested[0].stories, list)
        return suggested

    try:
        suggested = await check(primary)
        report(f"REQ fbsearch_suggested_profiles: {_summarize(suggested)}")
        return True
    except Exception as exc:
        report(f"REQ fbsearch_suggested_profiles primary: {_error_summary(exc)}")

    attempts = 0
    for index, account in enumerate(accounts, 1):
        if account.get("username") == primary.username:
            continue
        settings = account.get("client_settings") or account.get("settings") or {}
        if isinstance(settings, str):
            try:
                settings = json.loads(settings)
            except ValueError:
                continue
        if not isinstance(settings, dict):
            continue
        alternate = None
        try:
            alternate = Client(settings=settings, proxy=account.get("proxy"))
            if not alternate.sessionid:
                continue
            attempts += 1
            control = await alternate.user_info_v1("25025320")
            assert str(control.pk) == "25025320"
            suggested = await check(alternate)
            report(f"REQ fbsearch_suggested_profiles: {_summarize(suggested)} (saved acc{index})")
            return True
        except Exception as exc:
            report(f"REQ fbsearch_suggested_profiles saved acc{index}: {_error_summary(exc)}")
        finally:
            if alternate is not None:
                for name in ("private", "public", "graphql"):
                    session = getattr(alternate, name, None)
                    close = getattr(session, "_close", None)
                    if close is not None:
                        try:
                            await close()
                        except Exception:
                            pass
        if attempts >= 2:
            break

    report("REQ fbsearch_suggested_profiles FAIL: no successful account")
    return False


@contextmanager
def _quiet_output():
    stdout = sys.stdout
    streams = [stream for stream in (stdout, sys.stderr, sys.__stdout__, sys.__stderr__) if stream is not None]
    for stream in streams:
        stream.flush()
    with ExitStack() as cleanup:
        try:
            output_fd = stdout.fileno()
        except (AttributeError, OSError, ValueError):
            output = stdout  # StringIO and pytest's capsys have no descriptor.
        else:
            report_fd = os.dup(output_fd)
            cleanup.callback(os.close, report_fd)
            output = cleanup.enter_context(
                os.fdopen(report_fd, "w", encoding=stdout.encoding or "utf-8", closefd=False)
            )

        def report(message):
            print(message, file=output, flush=True)

        discard = cleanup.enter_context(open(os.devnull, "w", encoding="utf-8"))
        for fd in (1, 2):
            saved_fd = os.dup(fd)
            cleanup.callback(os.close, saved_fd)
            cleanup.callback(os.dup2, saved_fd, fd)
            os.dup2(discard.fileno(), fd)
        with redirect_stdout(discard), redirect_stderr(discard):
            try:
                yield report
            finally:
                # Flush retained stream references while their descriptors are muted.
                for stream in streams:
                    stream.flush()


async def main():
    if not os.environ.get("TEST_ACCOUNTS_URL"):
        print("SKIP: TEST_ACCOUNTS_URL not set")
        return 0

    previous_logging_level = logging.root.manager.disable
    logging.disable(max(logging.CRITICAL, previous_logging_level))
    try:
        with _quiet_output() as report:
            try:
                return await _run_smoke(report)
            except Exception as exc:
                report(f"FAILED smoke: {_error_summary(exc)}")
                return 1
    finally:
        logging.disable(previous_logging_level)


async def _run_smoke(report):
    try:
        accs = await _fetch_accounts(os.environ["TEST_ACCOUNTS_URL"])
        report(f"pool: {len(accs)} accs")
    except Exception as exc:
        report(f"REQ account_allocation FAIL: {_error_summary(exc)}")
        return 1

    failures = []

    # OPTIONAL: anonymous public path. IG often throttles this web endpoint
    # with 429 while logged-in app-backed checks are healthy.
    try:
        c = Client()
        u = await c.user_info_by_username_gql("instagram")
        assert u.username == "instagram" and u.pk == "25025320"
        report("opt anonymous_public_gql: ok")
    except Exception as e:
        report(f"opt anonymous_public_gql: {_error_summary(e)}")

    try:
        import curl_adapter  # noqa: F401

        c = Client(public_transport="curl", public_request_retries_count=2)
        u = await c.user_info_by_username_gql("instagram")
        assert u.username == "instagram" and u.pk == "25025320"
        report("opt curl_public_gql: ok")
    except ImportError:
        report("opt curl_public_gql: skipped (install aiograpi[curl])")
    except Exception as e:
        report(f"opt curl_public_gql: {_error_summary(e)}")

    # REQUIRED: login (TOTP) + private path
    cl = await _login_first_usable(accs, report)
    if cl is None:
        failures.append(("login", "all pool accounts unusable"))
    else:
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                session_file = Path(tmpdir) / "session.json"
                cl.dump_settings(session_file)

                restored = Client()
                proxy = getattr(cl, "proxy", None)
                if isinstance(proxy, str) and proxy:
                    restored.set_proxy(proxy)
                restored.load_settings(session_file)
                account_info = restored.account_info
                validation_calls = 0

                async def validating_account_info():
                    nonlocal validation_calls
                    validation_calls += 1
                    return await account_info()

                restored.account_info = validating_account_info
                logged_in = await restored.login(cl.username, cl.password)
                restored.dump_settings(session_file)

            assert logged_in
            assert validation_calls == 1
            assert str(restored.user_id) == str(cl.user_id)
            report("REQ saved_session_login: validated/reused")
        except Exception as e:
            failures.append(("saved_session_login", e))
            report(f"REQ saved_session_login FAIL: {_error_summary(e)}")

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
            report("REQ sessionid_login: account_info/timeline")
        except Exception as e:
            failures.append(("sessionid_login", e))
            report(f"REQ sessionid_login FAIL: {_error_summary(e)}")

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
            ("user_highlights", lambda: cl.user_highlights("25025320", amount=1)),
        ]:
            try:
                out = await fn()
                report(f"REQ {name}: {_summarize(out)}")
            except Exception as e:
                failures.append((name, e))
                report(f"REQ {name} FAIL: {_error_summary(e)}")

        try:
            followers = await cl.user_followers_v1("25025320", amount=5)
            assert len(followers) == 5
            follower = followers[0]
            assert isinstance(follower.is_verified, bool)
            assert isinstance(follower.latest_reel_media, int)
            assert isinstance(follower.has_anonymous_profile_picture, bool)
            report("REQ user_followers_extended_fields: ok")
        except Exception as e:
            failures.append(("user_followers_extended_fields", e))
            report(f"REQ user_followers_extended_fields FAIL: {_error_summary(e)}")

        if not await _check_fbsearch_suggested_profiles(cl, accs, report):
            failures.append(("fbsearch_suggested_profiles", "no successful account"))

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
            ("music_bookmarked", "music_bookmarked", (), {}),
            ("music_search_v2", "music_search_v2", ("love",), {}),
            ("music_clips_audio_browser", "music_clips_audio_browser", (), {}),
        ]
        for name, attr, args, kwargs in opt_checks:
            fn = getattr(cl, attr, None)
            if fn is None:
                opt_skipped += 1
                report(f"opt {name}: skipped (not implemented)")
                continue
            try:
                await fn(*args, **kwargs)
                report(f"opt {name}: PASS")
                opt_pass += 1
            except Exception as e:
                report(f"opt {name}: {_error_summary(e)}")
        report(f"OPTIONAL: {opt_pass}/{len(opt_checks)} chapi methods OK ({opt_skipped} skipped)")

    if failures:
        report(f"\nFAILED: {len(failures)} required check(s)")
        return 1
    report("\nALL REQUIRED PASS")
    return 0


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    sys.exit(asyncio.run(main()))

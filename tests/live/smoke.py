"""Live end-to-end smoke for aiograpi.

Exits 0 if all REQUIRED checks pass; non-zero otherwise. Optional
checks (chapi-style new endpoints) are reported but never fail the
build — IG rotates doc_ids and we don't want a flaky CI gate.

Required env: TEST_ACCOUNTS_URL pointing at a HikerAPI-style accounts
endpoint that returns at least one usable account (with TOTP seed if
2FA is enabled). Skips cleanly if unset.
"""

import asyncio
import json
import os
import ssl
import sys
import urllib.request
import uuid

from aiograpi import Client


async def _fetch_accounts(url, count=10):
    sep = "&" if "?" in url else "?"
    req = urllib.request.Request(
        url + sep + f"count={count}",
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
            await c.login(**kwargs)
            print(f"LOGIN_OK acc{i} {acc['username']} (user_id={c.user_id})")
            return c
        except Exception as e:
            print(
                f"acc{i} {acc.get('username','?')}: {type(e).__name__}: {str(e)[:120]}"
            )
    return None


async def main():
    if not os.environ.get("TEST_ACCOUNTS_URL"):
        print("SKIP: TEST_ACCOUNTS_URL not set")
        return 0

    accs = await _fetch_accounts(os.environ["TEST_ACCOUNTS_URL"])
    print(f"pool: {len(accs)} accs")

    failures = []

    # REQUIRED: anonymous public path
    try:
        c = Client()
        u = await c.user_info_by_username_gql("instagram")
        assert u.username == "instagram" and u.pk == "25025320"
        print(f"REQ public_gql: {u.username}/{u.pk}")
    except Exception as e:
        failures.append(("public_gql", e))
        print(f"REQ public_gql FAIL: {type(e).__name__}: {e}")

    # REQUIRED: login (TOTP) + private path
    cl = await _login_first_usable(accs)
    if cl is None:
        failures.append(("login", "all pool accounts unusable"))
    else:
        for name, fn in [
            ("private_v1", lambda: cl.user_info_by_username_v1("instagram")),
            ("private_v2_gql", lambda: cl.user_info_by_username_v2_gql("instagram")),
            ("hashtag_info_v1", lambda: cl.hashtag_info_v1("python")),
            ("user_medias_v1", lambda: cl.user_medias_v1("25025320", amount=3)),
            ("user_followers", lambda: cl.user_followers("25025320", amount=10)),
            ("highlight_info", lambda: cl.highlight_info(17983407089364361)),
        ]:
            try:
                out = await fn()
                summary = (
                    f"{out.username}/{out.pk}"
                    if hasattr(out, "username")
                    else (
                        out.name
                        if hasattr(out, "name")
                        else (
                            f"len={len(out)}"
                            if isinstance(out, list)
                            else str(out)[:50]
                        )
                    )
                )
                print(f"REQ {name}: {summary}")
            except Exception as e:
                failures.append((name, e))
                print(f"REQ {name} FAIL: {type(e).__name__}: {str(e)[:140]}")

    # OPTIONAL: chapi-ported endpoints — record but don't fail
    if cl is not None:
        rank_token = str(uuid.uuid4())
        instagram_pk = "25025320"
        opt_pass = 0
        opt_total = 0
        for name, fn in [
            (
                "fbsearch_keyword_typeahead",
                lambda: cl.fbsearch_keyword_typeahead("python"),
            ),
            (
                "fbsearch_typeahead_stream",
                lambda: cl.fbsearch_typeahead_stream("python"),
            ),
            (
                "fbsearch_item_top",
                lambda: cl.fbsearch_item("top_serp", "top_serp", "python"),
            ),
            ("fbsearch_accounts_v2", lambda: cl.fbsearch_accounts_v2("python")),
            ("fbsearch_reels_v2", lambda: cl.fbsearch_reels_v2("python")),
            ("fbsearch_topsearch_v2", lambda: cl.fbsearch_topsearch_v2("python")),
            ("fbsearch_typehead", lambda: cl.fbsearch_typehead("pyt")),
            ("user_stream_by_id_v1", lambda: cl.user_stream_by_id_v1(instagram_pk)),
            ("user_stream_by_id_flat", lambda: cl.user_stream_by_id_flat(instagram_pk)),
            (
                "user_stream_by_username_flat",
                lambda: cl.user_stream_by_username_flat("instagram"),
            ),
            (
                "user_web_profile_info_v1",
                lambda: cl.user_web_profile_info_v1("instagram"),
            ),
            (
                "discover_recommended_accounts_for_category_v1",
                lambda: cl.discover_recommended_accounts_for_category_v1(instagram_pk),
            ),
            (
                "user_related_profiles_gql",
                lambda: cl.user_related_profiles_gql(instagram_pk),
            ),
            ("feed_user_stream_item", lambda: cl.feed_user_stream_item(instagram_pk)),
            (
                "private_graphql_followers_list",
                lambda: cl.private_graphql_followers_list(
                    instagram_pk, rank_token=rank_token
                ),
            ),
            (
                "private_graphql_following_list",
                lambda: cl.private_graphql_following_list(
                    instagram_pk, rank_token=rank_token
                ),
            ),
            (
                "private_graphql_clips_profile",
                lambda: cl.private_graphql_clips_profile(instagram_pk),
            ),
            (
                "private_graphql_inbox_tray_for_user",
                lambda: cl.private_graphql_inbox_tray_for_user(cl.user_id),
            ),
            (
                "private_graphql_realtime_region_hint",
                lambda: cl.private_graphql_realtime_region_hint(),
            ),
            (
                "private_graphql_top_audio_trends",
                lambda: cl.private_graphql_top_audio_trends_eligible_categories(),
            ),
            ("private_graphql_memories_pog", lambda: cl.private_graphql_memories_pog()),
            (
                "private_graphql_update_inbox_tray_last_seen",
                lambda: cl.private_graphql_update_inbox_tray_last_seen(),
            ),
        ]:
            opt_total += 1
            try:
                await fn()
                print(f"opt {name}: PASS")
                opt_pass += 1
            except Exception as e:
                print(f"opt {name}: {type(e).__name__}: {str(e)[:140]}")
        print(f"OPTIONAL: {opt_pass}/{opt_total} chapi methods OK")

    if failures:
        print(f"\nFAILED: {len(failures)} required check(s)")
        return 1
    print("\nALL REQUIRED PASS")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

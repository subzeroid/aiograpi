# Private GraphQL & doc_id endpoints

Instagram is migrating off the legacy `query_hash` / `query_id` GraphQL
scheme onto a `doc_id`-based mobile GraphQL surface
(`i.instagram.com/graphql/query`) and onto a parallel public-host
PolarisProfilePageContentQuery family
(`www.instagram.com/graphql/query/`).

aiograpi exposes both as **base helpers** (so you can call any registered
query) and as **named convenience wrappers** (`user_info_v2_gql`,
`private_graphql_followers_list`, etc.).

## When to use what

| Scenario | Method |
|---|---|
| Profile by `user_id`, logged-in friendly | `Client.user_info_v2_gql(user_id)` |
| Profile by `username`, logged-in friendly | `Client.user_info_by_username_v2_gql(username)` |
| Streamed profile envelope by `user_id` | `Client.user_stream_by_id_v1(user_id)` |
| Streamed profile envelope by `username` | `Client.user_stream_by_username_v1(username)` |
| Flat (merged) profile dict by `user_id` | `Client.user_stream_by_id_flat(user_id)` |
| Flat (merged) profile dict by `username` | `Client.user_stream_by_username_flat(username)` |
| Web-scraper-style profile via private host | `Client.user_web_profile_info_v1(username)` |
| "Suggested" profiles by user_id (chaining) | `Client.chaining(user_id)` |
| Suggested-profile expanded details | `Client.fetch_suggestion_details(user_id, chained_ids)` |
| Similar businesses by user's category | `Client.discover_recommended_accounts_for_category_v1(user_id)` |
| Related profiles via legacy GraphQL `edge_chaining` | `Client.user_related_profiles_gql(user_id)` |
| HEAD a public URL (resolve short-link redirects without body) | `Client.public_head(url, follow_redirects=False)` |
| Audio/track clips-pivot stream | `Client.track_stream_info_by_id(track_id, max_id="")` |
| Media info via discover/media_metadata fallback | `Client.media_info_v2(media_id)` |
| Lightweight offensive-comment check (raw payload) | `Client.media_check_offensive_comment_v2(media_id, comment)` |
| Followers list (mobile-app surface) | `Client.private_graphql_followers_list(user_id, rank_token)` |
| Following list (mobile-app surface) | `Client.private_graphql_following_list(user_id, rank_token)` |
| Profile reels stream | `Client.private_graphql_clips_profile(target_user_id)` |
| Direct inbox tray digest | `Client.private_graphql_inbox_tray_for_user(user_id)` |
| Realtime region hints | `Client.private_graphql_realtime_region_hint()` |
| Top audio trends categories | `Client.private_graphql_top_audio_trends_eligible_categories()` |
| Memories pog (story memories pog in home tray) | `Client.private_graphql_memories_pog()` |
| Mark inbox tray as seen | `Client.private_graphql_update_inbox_tray_last_seen()` |
| Search keyword typeahead | `Client.fbsearch_keyword_typeahead(query)` |
| Search typeahead stream | `Client.fbsearch_typeahead_stream(query)` |
| Typeahead users (flattened) | `Client.fbsearch_typehead(query)` |
| Generic SERP fetch (top / user / clips / popular) | `Client.fbsearch_item(item_id, search_surface, query)` |
| Accounts SERP (v2) | `Client.fbsearch_accounts_v2(query, page_token=None)` |
| Reels SERP (v2) | `Client.fbsearch_reels_v2(query, reels_max_id=None, rank_token=None)` |
| Top blended SERP (v2) | `Client.fbsearch_topsearch_v2(query, next_max_id=None, reels_max_id=None, rank_token=None)` |
| Per-user feed stream | `Client.feed_user_stream_item(item_id)` |
| Bulk comments digest | `Client.media_comment_infos(media_ids)` |

All of the above are convenience wrappers around two primitives:

- `Client.public_doc_id_graphql_request(doc_id, variables)` — public host
  (`www.instagram.com/graphql/query/`). Uses iPhone Instagram-app
  `User-Agent` and forwards logged-in cookies (`sessionid`,
  `ds_user_id`) so doc_ids that need authenticated context still work.
- `Client.private_graphql_query_request(friendly_name, root_field_name, variables, client_doc_id)`
   — mobile host (`i.instagram.com/graphql/query`). Uses the
  authenticated `self.private` session so all standard mobile
  headers/cookies apply.

## Using the named wrappers

```python
from aiograpi import Client

cl = Client()
await cl.login(USERNAME, PASSWORD, verification_code="123456")

# v2 GraphQL profile fetch — preferred over user_info_by_username_gql
# when you're logged in (the legacy api/v1/users/web_profile_info/
# endpoint is increasingly flaky for authenticated callers).
user = await cl.user_info_by_username_v2_gql("instagram")
print(user.username, user.pk, user.follower_count)

# Followers via the mobile-app GraphQL surface. rank_token is a UUID
# that IG generates per follow-list session.
import uuid
rank_token = str(uuid.uuid4())
data = await cl.private_graphql_followers_list(
    user_id="25025320",
    rank_token=rank_token,
)
# Returns the raw GraphQL envelope: {"data": {...}, "status": "ok", ...}.
# Schema is large and varies — pick what you need from data["data"].

# Search typeahead
hits = await cl.fbsearch_keyword_typeahead("python")
for hit in hits["list"]:
    print(hit.get("title") or hit.get("user", {}).get("username"))

# v2 SERP endpoints — same surfaces the IG app uses for the Top /
# Accounts / Reels tabs. Return raw payloads (users / items /
# pagination tokens) — caller decides what to extract.
top = await cl.fbsearch_topsearch_v2("python")
accounts = await cl.fbsearch_accounts_v2("python")
reels = await cl.fbsearch_reels_v2("python")

# Pagination: pass the cursor from the previous response back in.
more_accounts = await cl.fbsearch_accounts_v2(
    "python", page_token=accounts.get("next_page_token")
)
```

## Calling unwrapped doc_ids directly

When you have a `doc_id` from a Charles capture or from
[instaloader](https://github.com/instaloader/instaloader)'s registry,
go through the primitive:

```python
# Public host (PolarisProfilePageContentQuery family)
data = await cl.public_doc_id_graphql_request(
    doc_id="25980296051578533",  # PolarisProfilePageContentQuery
    variables={
        "id": "25025320",
        "render_surface": "PROFILE",
        # ... relay provider flags
    },
)
user_data = data["user"]

# Mobile host (XDT-prefixed root fields)
result = await cl.private_graphql_query_request(
    friendly_name="MyCustomQuery",
    root_field_name="xdt_my_custom_root",
    variables={"some_id": "123"},
    client_doc_id="123456789012345678901234567890",
)
```

## doc_id rotation

**IG rotates registered queries.** A `doc_id` that worked today may stop
working tomorrow without notice — the server just returns HTTP 400.
Every named wrapper ships a default `client_doc_id` captured from a
working mobile-app session, but you can override per-call:

```python
await cl.private_graphql_followers_list(
    user_id="25025320",
    rank_token=rank_token,
    client_doc_id="<freshly captured doc_id>",
)
```

If a wrapper starts failing with HTTP 400, the first thing to try is
re-capturing the `doc_id` against a current Instagram-app build (Charles
+ a rooted device, or an mitm proxy on a simulator).

## Streaming responses

Some doc_ids — notably `ClipsProfileQuery` — have a `should_stream_response`
/ `use_stream` / `use_defer` / `stream_use_customized_batch` family of
flags that, when `True`, make IG return a multi-document NDJSON envelope
(`{...}\n{...}\n{...}`). aiograpi's wrappers default these to `False` so
the response is a single JSON that `response.json()` can parse:

```python
# Default — single-JSON, easy to parse:
data = await cl.private_graphql_clips_profile(target_user_id="25025320")
clips = data["data"]["xdt_user_clips_graphql"]["edges"]

# Raw stream — you parse it yourself from response.text:
# (would need to subclass and pass should_stream_response=True in
# variables, then read self.last_response.text and split on document
# boundaries.)
```

## Exception handling

Both primitives map HTTP failure modes onto the canonical
[`aiograpi.exceptions`](../exceptions.md) hierarchy. Wrap calls in the
exception clauses you'd use anywhere else:

```python
from aiograpi.exceptions import (
    ClientBadRequestError,        # 400 — usually stale doc_id
    ClientUnauthorizedError,      # 401 — session expired
    ClientForbiddenError,         # 403 — endpoint requires login or geo
    ClientThrottledError,         # 429 — rate-limited
    UserNotFound,                 # for user_info_*_v2_gql when the
                                  #   target doesn't exist
    ClientGraphqlError,           # GraphQL-level error in the response
                                  #   body (status != "ok" or no "data")
)

try:
    user = await cl.user_info_by_username_v2_gql("missing_user")
except UserNotFound:
    # IG returned a valid response but no matching user.
    pass
except ClientBadRequestError:
    # Most often: a rotated doc_id. Re-capture from a current app build.
    pass
except ClientGraphqlError as e:
    # The endpoint returned a structured GraphQL error.
    print("GraphQL error:", e)
```

## How this maps to upstream and prior art

- **`public_doc_id_graphql_request`** is the aiograpi equivalent of
  instaloader's `InstaloaderContext.doc_id_graphql_query` (introduced in
  instaloader 4.13, see PR
  [#2652](https://github.com/instaloader/instaloader/pull/2652) — the
  "Fix obtaining Profiles when logged in" fix that aiograpi 0.5.0
  ported).
- **`private_graphql_query_request`** mirrors the wrapper used by the
  HikerAPI team's `chapi` client. The 13 chapi-ported methods landed in
  aiograpi 0.6.0; live-verified in 0.6.2 / 0.6.4.
- The default `client_doc_id` values for FollowersList, FollowingList,
  ClipsProfileQuery, and InboxTrayRequestForUser are captures from
  chapi's reference invocations.

See the [Migration Guide](../migration.md) for the breaking changes
that led to these methods, and the
[CHANGELOG](https://github.com/subzeroid/aiograpi/blob/main/CHANGELOG.md)
for per-release detail.

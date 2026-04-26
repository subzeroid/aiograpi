# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
(with the pre-1.0 caveat that minor bumps may include breaking changes).

## [0.6.0] — 2026-04-26

### Added — chapi sweep

13 new IG endpoints ported from `/Users/colinfrl/work/ng/chapi`
(standalone async client by the same team behind `hiker-next`). All
on real Instagram — no proprietary infrastructure imported. Methods
funnel through our existing `private_request` /
`public_doc_id_graphql_request` stack.

#### `GraphQLRequestMixin` (private mobile GraphQL)

- `private_graphql_query_request(friendly_name, root_field_name, variables, client_doc_id, ...)`
  — base helper that POSTs to `i.instagram.com/graphql/query`
  using the private session.
- `private_graphql_memories_pog(...)` — `MemoriesPogQuery`.
- `private_graphql_realtime_region_hint()` — `IGRealtimeRegionHintQuery`.
- `private_graphql_top_audio_trends_eligible_categories()` —
  `GetTopAudioTrendsEligibleCategories`.
- `private_graphql_update_inbox_tray_last_seen()` —
  `UpdateInboxTrayLastSeenTimestamp` mutation.

#### `UserMixin`

- `feed_user_stream_item(item_id, is_pull_to_refresh)` — POST
  `feed/user_stream/{item_id}/`.
- `private_graphql_followers_list(user_id, rank_token, ...)` —
  `FollowersList` private GQL.
- `private_graphql_following_list(user_id, rank_token, ...)` —
  `FollowingList`.
- `private_graphql_clips_profile(target_user_id, ...)` —
  `ClipsProfileQuery` (profile reels stream).
- `private_graphql_inbox_tray_for_user(user_id, ...)` —
  `InboxTrayRequestForUserQuery`.

#### `CommentMixin`

- `media_comment_infos(media_ids)` — GET `media/comment_infos/`
  (bulk comments digest, accepts list or CSV).

#### `FbSearchMixin`

- `fbsearch_item(item_id, search_surface, query, ...)` — generic GET
  `fbsearch/{item_id}/` for all serp tabs (top/user/clips/popular).
- `fbsearch_keyword_typeahead(query, ...)` — GET
  `fbsearch/keyword_typeahead/`.
- `fbsearch_typeahead_stream(query, ...)` — GET
  `fbsearch/typeahead_stream/`.

### Tests

- `ChapiPortedRegressionTestCase` — 15 unit tests covering endpoint
  paths, params/data shaping, and friendly_name/root_field_name for
  private GQL methods. Wired into the unit-test CI job.

### Caveats

- `client_doc_id` defaults are taken from chapi captures. IG rotates
  registered queries; if a method starts failing, override
  `client_doc_id=` per call.
- `mobile-only` headers (`X-IG-Bandwidth-*`, `X-IG-Nav-Chain`,
  `x-pigeon-*`, etc.) are not copied — our `_send_private_request`
  already fills the standard mobile headers via `base_headers`. If a
  specific endpoint demands extra headers in production, pass
  `headers=...` per call.

No breaking changes; existing methods unchanged.

## [0.5.0] — 2026-04-26

### Added

Phase 2 Tier 2 — porting the still-relevant pieces from instaloader's
recent fixes; rest is N/A or already covered.

- `Client.public_doc_id_graphql_request(doc_id, variables)` — POSTs to
  `/graphql/query/` with the new doc_id-based scheme. Replaces the legacy
  `query_hash` / `query_id` path for endpoints IG migrated.
- `Client.user_info_v2_gql(user_id)` — fetches a profile via the new
  `PolarisProfilePageContentQuery` (doc_id `25980296051578533`).
- `Client.user_info_by_username_v2_gql(username)` — resolves
  username → user_id via the FB search query
  (doc_id `26347858941511777`), then chains to `user_info_v2_gql`.
  Logged-in-friendly alternative to `user_info_by_username_gql`,
  which still uses the increasingly-flaky
  `api/v1/users/web_profile_info/` endpoint.
- `aiograpi.exceptions.CommentUnavailable` — distinguishes
  "comment is unavailable" from generic `UnknownError`.

### Sources

- instaloader #2652 — "Fix obtaining Profiles (when logged in) by
  migrating to new GraphQL endpoints" (Mar 2026).
- instaloader #2533 — "Fix anonymous fetch of profile posts": the
  underlying primitive (`public_doc_id_graphql_request`) is what's
  needed. Fallback in `user_medias_chunk` is deferred; existing
  `query_hash="e7e2f4da4b..."` still works.
- aiodns >=4.0.0 — **N/A** for aiograpi (we use httpx, not aiohttp).

No breaking changes; existing methods unchanged.

## [0.4.1] — 2026-04-26

### Fixed

Phase 2 of the modernization — porting hardening fixes that the
`hiker-next` fork had on top of `instagrapi==2.4.4` but never made
it back to upstream.

- **`extract_story_v1`**: fall back to `InstagramIdCodec.encode(pk)`
  for missing `code`, and `device_timestamp` / `taken_at_timestamp`
  for missing `taken_at`. IG sometimes returns story payloads
  without these fields; `Story.code` / `Story.taken_at` are required,
  so missing values caused `ValidationError` on legitimate stories.
- **`private._send_private_request`** — `401` is now explicitly
  raised as `ClientUnauthorizedError` (the class existed but was
  never raised; previously `401` fell through to `ClientUnknownError`).
- **`private._send_private_request`** — `404` with body `b"Not Found"`
  is a masked challenge (often on `/media/.../comments/`), not a
  missing endpoint. Now raises `ChallengeRequired` so callers can
  resolve it instead of confusingly retrying.
- **`hashtag_medias_*_v1_chunk`** — wrap `extract_media_v1(node["media"])`
  in `try/except (KeyError, AttributeError, TypeError)`. One malformed
  node was crashing the whole chunk and losing the rest of the page;
  now we log and skip the bad node.

## [0.4.0] — 2026-04-26

### Added

- **PEP 561 type marker (`py.typed`).** mypy / pyright will now pick
  up aiograpi's type annotations from the installed package.
- **Migration guide** at `docs/migration.md` — for users coming from
  `0.0.x` or the third-party `aiograpi-fixed` namespace fork.
- **CaptchaHandlerMixin tests** — `CaptchaHandlerMixinRegressionTestCase`
  with 7 unit tests. The mixin was at 0% coverage (opt-in, not auto-wired
  into `Client`); now at 95.8%.

### Changed

- **CI: split tests into `unit-test` (network-free, runs everywhere)
  and `live-test` (gated to canonical-repo pushes).** `unit-test` runs
  ~107 regression tests on Python 3.10/3.11/3.12 — covers parsing,
  mocked plumbing, captcha handler — without needing
  `TEST_ACCOUNTS_URL`. `live-test` keeps the existing
  `ClientMediaTestCase` / `ClientUserTestCase` / `ClientHighlightTestCase`
  but only on `subzeroid/aiograpi` pushes (not on PRs from forks
  where the secret isn't available).

No runtime / API changes.

## [0.3.1] — 2026-04-26

### Tests

97 regression tests previously class-level `@unittest.skip`-ped are
now runnable (and passing). All 11 affected classes are unskipped;
only 10 individual tests stay `@unittest.skip` with concrete reasons:

- 5 in `ChallengeRegressionTestCase` — contact-form tests use
  upstream `requests.Session` / `requests.cookies.cookiejar_from_dict`
  fixtures that don't translate cleanly to `httpx_ext.Session`.
- 3 in `ClientTestCase` — two test urllib3 `HTTPAdapter` retry config
  which `httpx_ext.Session` doesn't expose (see comment in
  `aiograpi/mixins/private.py:107-129`); one needs live IG creds.
- 1 in `UserMixinRegressionTestCase` — references urllib3 `RetryError`
  which the user fallback no longer catches specifically.
- 1 in `SignUpTestCase` — needs live Instagram signup + SMS.

No runtime / API changes.

## [0.3.0] — 2026-04-26

### Breaking

Six more pure helpers go synchronous — same principle as the media-pk
helpers in `0.2.0` (`async def` is reserved for IO). Drop the `await`
from any caller; old code raises `TypeError` or quietly returns a
coroutine that never runs.

| Method | What it does |
|---|---|
| `Client.share_info(code)` | base64-decode + split |
| `Client.share_code_from_url(url)` | urlparse + split |
| `Client.share_info_by_url(url)` | composes the two above |
| `Client.highlight_pk_from_url(url)` | urlparse + filter digits |
| `Client.handle_challenge_result(d)` | dict inspection + `raise` |
| `Client.challenge_resolve_new_password_form(r)` | extract_messages + `raise` |

`handle_challenge_result` is also a latent-bug fix: tests in
`ChallengeRegressionTestCase` already call it without `await` inside
`assertRaises`. With the previous async signature those `assertRaises`
caught a coroutine warning, not the typed exception. They now work as
written when the regression class is unskipped.

### Fixed

- `Client.igtv_download(...)` and `Client.highlight_remove_stories(...)`
  were returning a coroutine instead of awaiting the inner async call.
  Callers `await client.igtv_download(...)` got a wrapped coroutine
  that was never scheduled. Both now correctly `await`.

### Added

- `CHANGELOG.md`.
- CI: `.github/workflows/publish.yml` — push a version tag and the
  workflow builds, publishes to PyPI via trusted publishing (no API
  token in secrets), and creates a GitHub release. One-time PyPI
  setup needed (pending publisher).
- `docs/usage-guide/captcha.md`, `docs/usage-guide/explore.md`,
  `docs/usage-guide/fundraiser.md` — pages for the new mixins.
- `docs/usage-guide/highlight.md`, `docs/usage-guide/notes.md`,
  `docs/usage-guide/totp.md`, `docs/usage-guide/challenge_resolver.md`,
  `docs/usage-guide/best-practices.md` — orphan files now in nav.

### Changed

- `mkdocs build --strict` is now clean. `superpowers/` (gitignored
  local plans/specs) excluded from the build.
- `DirectExtractorRegressionTestCase` forces `TZ=UTC` in
  `setUp`/`tearDown` so the timestamp tests pass on non-UTC hosts
  (upstream test bug — it relied on CI being UTC).

## [0.2.0] — 2026-04-26

### Breaking

- `Client.media_pk_from_code(code)`, `Client.media_code_from_pk(pk)`, and
  `Client.media_pk(media_id)` are now **synchronous** — they only call
  `InstagramIdCodec.encode/decode` or split a string and don't do any IO.
  Drop the `await` from callers; old code raises
  `TypeError: object str can't be used in 'await' expression`.
  `Client.media_pk_from_url` stays async (it does HTTP redirect-following
  for `/share/p/` short URLs).

## [0.1.1] — 2026-04-26

First published release of the upstream `instagrapi==2.4.4` sync
(`0.1.0` filename was globally reserved on PyPI from a prior deletion).

### Added

- Three new mixins ported from upstream:
  - `ExploreMixin` (`explore_page`, `report_explore_media`,
    `explore_page_media_info`) — wired into `Client`.
  - `FundraiserMixin` (`standalone_fundraiser_info_v1`) — wired into `Client`.
  - `CaptchaHandlerMixin` — opt-in (matches upstream; not auto-wired).
- `generic_xma: List[MediaXma]` field on `DirectMessage` and `ReplyMessage`,
  with matching extraction in `extract_direct_message` / `extract_reply_message`.
- `overwrite` flag on media downloads.
- Cutout sticker support on video/clip create.
- `DEFAULT_LOGGER` module-level logger; `Client(logger=...)` for per-instance override.
- `Pillow>=8.1.1` declared as explicit dependency.

### Changed

- Full upstream sync with `instagrapi==2.4.4`: every mixin and infrastructure
  module ported file-by-file, plus the StoryBuilder.
- Auth/session hardening: clear stale cookies / IG-U-RUR / sessionid on
  relogin; isolate default client settings state; harden numeric
  private/contact-form challenge choices; preserve SMS choice across
  challenge follow-ups.
- Media configure response handling hardened across photo/video/album/
  igtv/clip/story/direct upload paths.
- Direct messages: handle incomplete XMA shares.
- `Client.__init__` now takes `Optional[dict]` for `settings` and uses
  `deepcopy(settings)` so caller mutations don't leak.
- Internal `aiograpi/reqwests.py` renamed to `aiograpi/httpx_ext.py`
  (it's an httpx shim with orjson/zstd/exception re-exports, not a
  requests-compat layer).
- Tests ported wholesale from upstream and async-converted to
  `unittest.IsolatedAsyncioTestCase`. 218 tests collected.

### aiograpi-specific divergences preserved

- `GraphQLRequestMixin` (no upstream counterpart).
- httpx-style single-string `.proxy` attribute on each session
  (vs upstream's requests-style `proxies` dict).
- No `urllib3.disable_warnings` (httpx-incompatible).

### Known follow-ups

- 11 upstream regression test classes are class-level `@unittest.skip`-ped —
  they mock `requests.Session` / urllib3 adapters / cookiejar internals that
  don't translate cleanly to `httpx_ext`. They need per-test rewrites with
  `AsyncMock` + httpx equivalents.

## [0.0.4] — 2025-05-29

Last release on the pre-`instagrapi==2.4.4`-sync codebase. See git history
for incremental changes since 0.0.3.

## [0.0.3] — 2024-05-19

## [0.0.2] — 2024-04-13

## [0.0.1] — 2024-02-27

Initial release.

[0.6.0]: https://github.com/subzeroid/aiograpi/releases/tag/0.6.0
[0.5.0]: https://github.com/subzeroid/aiograpi/releases/tag/0.5.0
[0.4.1]: https://github.com/subzeroid/aiograpi/releases/tag/0.4.1
[0.4.0]: https://github.com/subzeroid/aiograpi/releases/tag/0.4.0
[0.3.1]: https://github.com/subzeroid/aiograpi/releases/tag/0.3.1
[0.3.0]: https://github.com/subzeroid/aiograpi/releases/tag/0.3.0
[0.2.0]: https://github.com/subzeroid/aiograpi/releases/tag/0.2.0
[0.1.1]: https://github.com/subzeroid/aiograpi/releases/tag/0.1.1
[0.0.4]: https://github.com/subzeroid/aiograpi/releases/tag/0.0.4
[0.0.3]: https://github.com/subzeroid/aiograpi/releases/tag/0.0.3
[0.0.2]: https://github.com/subzeroid/aiograpi/releases/tag/0.0.2
[0.0.1]: https://github.com/subzeroid/aiograpi/releases/tag/0.0.1

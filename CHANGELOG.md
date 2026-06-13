# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
starting with 1.0.0.

## [1.3.17] - 2026-06-13

### Added

- Added async `music_bookmarked(max_id="")` for retrieving bookmarked music tracks.

### Changed

- Synced the recorded upstream baseline to `instagrapi` 2.9.17.

## [1.3.16] - 2026-06-13

### Added

- Added async `clip_mashup_info(media_pk)` for Instagram's Reel remix/reuse availability metadata endpoint.

### Changed

- Synced the recorded upstream baseline to `instagrapi` 2.9.16.

## [1.3.1] - 2026-06-11

### Added

- Added async `user_suggested_profiles(user_id, expand_suggestion=False)` as a convenience wrapper over `chaining(...)` and `fetch_suggestion_details(...)`.

### Changed

- Synced the recorded upstream baseline to `instagrapi` 2.9.1.

## [1.3.0] - 2026-06-10

### Added

- Added `clip_share_to_fb_destination(...)` to normalize confirmed Reel Facebook destination fields without treating Account Center linking ids such as `account_id` as publish destinations.
- Added experimental modern CAA email signup via `signup_caa_email(...)`, including the mobile `graphql_www` Bloks app wrapper used by registration.

### Changed

- Private mobile requests now retry one incomplete-read transport failure once after a short delay.
- Challenge, signup email, and signup SMS helpers no longer print verification codes or password-reset values to stdout.
- Synced the recorded upstream baseline to `instagrapi` 2.8.19.
- Synced the recorded upstream baseline to `instagrapi` 2.9.0.

## [1.2.0] - 2026-06-06

### Added

- Added `direct_media_share(..., thread_ids=[...])` for sharing feed media into existing Direct threads or groups.
- Added `DirectMessageRequestsDisabled` for recipients whose privacy settings reject new Direct message requests.

### Changed

- Synced the recorded upstream baseline to `instagrapi` 2.8.13.
- Prefer private mobile lookups first for authenticated high-level user, media, tagged media, stories, followers, and following calls.
- `login_by_sessionid()` now tries the private profile stream before public/web GraphQL when recovering the username after a private profile lookup failure.
- Bumped the test ruff pin to `0.15.16`.

### Fixed

- Parse first-line JSON profile stream responses for `user_stream_by_id_v1()` and support top-level `{"user": ...}` stream payloads.
- Raise a clearer `ChallengeRequired` for Instagram Bloks redirect checkpoints that require manual confirmation in the official app or web flow.

## [1.1.0] - 2026-06-02

### Added

- Added experimental async Realtime MQTT / MQTToT support through `Client.realtime_*` helpers and
  `aiograpi.realtime.RealtimeClient`.
- Added async Direct message sync over MQTT, including `direct_subscribe()` and event callbacks for `message`,
  `direct`, `typing`, `seen`, and `presence`.
- Added lightweight async Direct MQTT actions: `direct_send_text()`, `direct_send_reaction()`,
  `direct_mark_seen()`, and `direct_indicate_activity()`.
- Added async FBNS push MQTT support through `Client.fbns_*` helpers and `aiograpi.realtime.FbnsClient`,
  including device-auth persistence in `settings["fbns_auth"]`, token registration, and `push` callbacks.
- Added async `confirm_phone_number(...)`, `hashtag_following(...)`, and `media_share_to_story(...)`.
- Added async Bloks challenge navigation helper that preserves opaque `challenge_context` values.

### Fixed

- Improved Reel/clip upload failures so early upload stages include stage, HTTP status, response JSON, and response text.

### Changed

- Added `PySocks` as a runtime dependency for realtime MQTT proxy transport.
- Synced the recorded upstream baseline to `instagrapi` 2.8.2.

## [1.0.11] - 2026-05-28

### Added

- Added async professional account conversion helpers: `account_convert_to_professional()`, `account_convert_to_business()`, and `account_convert_to_creator()`.
- Added private GraphQL followers helpers: `user_followers_private_gql_chunk()` and `user_followers_private_gql()`, plus followers ordering support for private followers fetches.
- Added scheduled feed publishing support for `photo_upload()`, `video_upload()`, `album_upload()`, `photo_upload_with_music()`, and `album_upload_with_music()` on accounts where Instagram enables scheduled content.
- Added Story music upload helpers: `story_music_extra_data()`, `video_upload_to_story_with_music()`, and `photo_upload_to_story_with_music()`. These helpers render the selected track into the uploaded Story media and attach music metadata; they do not expose Instagram's native interactive lyrics/music sticker UI.

### Fixed

- Normalized username lookup inputs by trimming whitespace, removing a leading `@`, and lowercasing before user lookup requests.
- Changed `video_download()` to fetch video metadata through the private `media_info_v1()` path directly before downloading.

### Changed

- Synced the recorded upstream baseline to `instagrapi` 2.7.17.
- Updated docs and regression coverage for the synced upstream APIs.

## [1.0.10] - 2026-05-21

### Added

- Added per-slide album usertags: `album_upload(..., usertags=[[...]])` now tags each carousel item by index.

### Changed

- Preserved album resource usertags from carousel media responses so per-slide tags are available on `media.resources[index].usertags`.
- Fixed async `comment_pin()` / `comment_unpin()` endpoint paths to keep comment pinning on the current mobile endpoint.
- Synced the recorded upstream baseline to `instagrapi` 2.7.10.

## [1.0.9] - 2026-05-21

### Added

- Added async `send_password_reset(identifier, recaptcha_challenge_field="")` to request an Instagram password reset link or code by username, email, or phone.

### Changed

- Kept `reset_password(username)` as a backward-compatible alias for `send_password_reset(...)`.
- Routed password reset requests through the configured public request session so proxy, TLS verification, retry, transport, and logging settings are reused.
- Synced the recorded upstream baseline to `instagrapi` 2.7.9.

## [1.0.8] - 2026-05-20

### Added

- Added async `confirm_email(email, code)` for confirming profile email changes
  when Instagram sends a numeric email confirmation code after
  `send_confirm_email(...)`.

### Changed

- Synced the recorded upstream baseline to `instagrapi` 2.7.8.

## [1.0.7] - 2026-05-20

### Added

- Added async Bloks backup-code support for
  `Client.login(..., verification_code=...)`, including 8-digit codes copied as
  `1234 5678`.
- Added `bloks_two_step_verification_enter_backup_code(...)` for manual
  backup-code verification flows.

### Changed

- Synced the recorded upstream baseline to `instagrapi` 2.7.7.

## [1.0.6] - 2026-05-20

### Added

- Added automatic async CAA/Bloks login fallback for
  `Client.login(..., verification_code=...)` when legacy login does not expose
  `two_step_verification_context` directly.
- Added low-level async helpers for inspecting CAA/Bloks login responses and
  extracting the returned two-factor context.

### Changed

- Synced the recorded upstream baseline to `instagrapi` 2.7.6.

## [1.0.5] - 2026-05-20

### Added

- Added automatic async Bloks two-factor login fallback for
  `Client.login(..., verification_code=...)` when Instagram provides
  `two_step_verification_context`.

### Changed

- Synced the recorded upstream baseline to `instagrapi` 2.7.5.

## [1.0.4] - 2026-05-20

### Added

- Added async low-level Bloks two-factor helpers for newer login verification
  flows.
- Added async submit-phone login challenge support for accounts that receive
  `challenge_required` with a phone collection step.

### Fixed

- Mirrored the current `media_comment()` write payload from `instagrapi`,
  including feed action context fields used by recent app requests.
- Added a feed photo upload read-back fallback for configure responses that
  return `{"status": "ok"}` without an embedded `media` object.
- Fixed pooled live account URL construction so an existing `count` query
  parameter is overridden instead of duplicated.

### Changed

- Added a manual live workflow target for comment writes and updated the live
  comment test to upload/read back/cleanup its own media fixture.
- Verified uploaded Reel music metadata in live upload tests.
- Documented that comment creation is still an Instagram trust-checked write
  action even with current request metadata.
- Synced the recorded upstream baseline to `instagrapi` 2.7.4.

## [1.0.3] - 2026-05-19

### Fixed

- Mirrored the `instagrapi` 2.7.3 story upload read-back fallback: async
  photo/video story uploads now return the newly uploaded story when Instagram
  accepts `configure_to_story` but omits the `media` object from the configure
  response.

### Changed

- Synced the recorded upstream baseline to `instagrapi` 2.7.3.

## [1.0.2] - 2026-05-19

### Added

- Added async Direct bootstrap helpers for pending request previews, interop
  upgrade state, GenAI bot search, channels, and E2EE eligibility.
- Added async media note create/delete helpers.
- Added async music app surfaces for trending audio, search, keyword search,
  bookmarks, clips audio browser, and original-audio title validation.
- Added async Bloks action helpers and Reel Facebook crosspost/link-share
  wrapper support.
- Added `clip_upload_with_music()` for Reel upload with explicit music metadata.
- Added signup challenge support for submit-phone and SMS-captcha challenge
  forms.

### Changed

- Synced the recorded upstream baseline to `instagrapi` 2.7.2.
- Updated Direct, media, track, challenge resolver, and Pydroid docs plus
  regression/live smoke coverage for the new async surfaces.

## [1.0.1] - 2026-05-19

### Added

- Added `Client(push_disabled=...)`, `settings["push_disabled"]`, and
  `client.set_push_disabled(...)` so request metadata can report the push state
  explicitly.
- Added `timezone_name` session metadata support. Timeline feed requests now use
  `settings["timezone_name"]` when present, otherwise derive a GMT offset name
  from `timezone_offset`.

### Changed

- Synced the recorded upstream baseline to `instagrapi` 2.7.1.
- Aligned current Android 428 timeline, Direct inbox, Reel creation preflight,
  media social action, and user follow/unfollow request payload metadata.

## [1.0.0] - 2026-05-18

### Changed

- Graduated aiograpi from ZeroVer to SemVer 1.0.0.
- Synced the recorded upstream baseline to `instagrapi` 2.7.0.
- Removed the legacy public A1 API surface (`public_a1_request`,
  `public_a1_request_user_info_by_username`, and the async `*_a1`
  media/user/location/hashtag helpers) because Instagram's old `?__a=1`
  public web payload is no longer reliable.
- High-level hashtag and location helpers now use authenticated private/mobile
  `_v1` flows directly.
- Kept `media_info_gql()` GraphQL-only: it can fall back from legacy
  `query_hash` GraphQL to current `doc_id` GraphQL, but no longer falls back to
  `media_info_v1()`.

### Removed

- Removed `hashtag_related_hashtags()` because it depended on the removed public
  related-tags web payload.

## [0.9.12] - 2026-05-17

### Changed

- Mirrored targeted `instagrapi` maintenance updates for Android 428 private transport/network headers while keeping
  device-bound integrity headers out of default generation.

### Fixed

- Fixed `search_music()` crashes when Instagram returns artist, playlist, or null-track rows mixed with valid tracks.

## [0.9.11] - 2026-05-17

### Fixed

- Fixed Termux installs on Android/Python 3.13 by using `pydantic==2.12.5` on Android so pip can resolve a `pydantic-core` release with Android wheels from the Termux User Repository PyPI index.

## [0.9.10] - 2026-05-17

### Security

- Hardened signup challenge path handling so server-supplied challenge paths must be safe relative Instagram API paths
  before aiograpi builds request URLs, starts captcha solving, or submits phone/SMS challenge forms.

## [0.9.9] - 2026-05-17

### Added

- Added async Reel Facebook cross-post payload helpers for linked Facebook users/pages, including explicit
  `fb_destination_id` and `fb_destination_type` support when Instagram's lightweight preflight does not return a usable
  destination.
- Added `Client(tls_verify=...)` and `client.set_tls_verify(...)` so users can keep TLS verification enabled by default,
  pass a trusted CA bundle for debugging proxies, or explicitly disable verification for local captures.

### Changed

- Synced the recorded upstream baseline to `instagrapi` 2.6.8.

### Security

- Replaced the remaining Reel music upload `tempfile.mktemp()` calls with an atomic `mkstemp` helper and clarified the
  challenge web-flow ajax seed so CodeQL no longer treats it as password hashing.

## [0.9.8] - 2026-05-16

### Added

- Added a `video` optional extra for MoviePy-backed helpers and Termux install notes.

### Changed

- Removed MoviePy/NumPy from the default install path; standard MP4 video uploads with `thumbnail=...` continue to use the built-in parser without MoviePy.
- Migrated optional video helpers to the MoviePy 2 API and added real MoviePy 2.2.1 video-generation regression coverage for `StoryBuilder.photo()` and `prepare_video()`.
- Documented the Pillow 12.2.0 security floor and the temporary `pip install --no-deps "moviepy==2.2.1"` install step required while MoviePy 2.2.1 declares `Pillow<12`.

## [0.9.7] - 2026-05-15

### Added

- Added optional curl-backed public web transport with Chrome impersonation for public lookup requests: install with
  `pip install "aiograpi[curl]"` and use `Client(public_transport="curl")`.
- Added public transport docs, README examples, settings roundtrip coverage, and optional live smoke coverage for curl
  public GraphQL lookups.

### Changed

- Synced the recorded upstream baseline to `instagrapi` 2.6.6.
- Synced timeline feed pagination telemetry with upstream: paginated `get_timeline_feed()` calls now send
  `seen_posts`, `feed_view_info`, and `reason="pagination"` by default.

## [0.9.6] - 2026-05-13

### Changed

- Made the anonymous public web lookup in `tests/live/smoke.py` optional so Instagram 429 throttling does not fail otherwise healthy logged-in live checks.
- Updated the recorded upstream sync baseline to `instagrapi` 2.6.4.
- Synced the remaining non-Facebook `instagrapi` 2.6.4 client methods into the async API: Trial Reel preflight, Direct voice/video attachments, follow request helpers, comment reply helpers, friends reels, media pagination aliases, media likers GraphQL parity, and the media-info GraphQL `doc_id` fallback.
- Deduplicated Direct messenger rupload header construction for video and voice attachment uploads.
- Hardened the mypy regression gate so it runs via `python -m mypy`, reports parse failures, and compares against the current legacy baseline instead of silently passing when `mypy` is unavailable.

## [0.9.5] - 2026-05-13

### Added

- Added async `direct_thread_add_users(thread_id, user_ids)` for adding users to existing group Direct threads.

### Changed

- Synced profile GraphQL lookups with the current upstream flow: `user_short_gql` now uses the web profile `doc_id`, `user_medias_gql` uses the app `IGProfileTimelineQuery` `client_doc_id`, and private GraphQL accepts incremental JSON-lines responses.
- Added an internal typing-only `ClientMixin` contract so mixins can use shared client attributes directly without `getattr` workarounds, eliminating the remaining `[attr-defined]` errors and reducing the internal mypy regression baseline from 1176 to 270 errors.
- Removed the `py.typed` package marker and user-facing PEP 561 messaging until aiograpi's annotations are ready to be supported as a public typing surface.

### Fixed

- Normalized nullable XDT media fields returned by profile timeline GraphQL so media extraction accepts missing usertags, missing carousel resources, and incomplete scrubber spritesheet blocks.

## [0.9.4] - 2026-05-12

### Fixed

- Accepted scalar Direct recipient ids such as `user_ids=123` and `thread_ids=123` across async Direct send/share helpers.

## [0.9.3] - 2026-05-12

### Added

- Added async `direct_thread_create(user_ids, title="")` for creating group Direct threads.
- Preserved raw Direct XMA payloads such as `xma_clip`, `xma_media_share`, `xma_story_share`, and `xma_profile` in
  `message.raw_xma`.

### Fixed

- Accepted Direct microsecond timestamps returned as strings, including reply timestamps and thread `last_activity_at`.

## [0.9.2] - 2026-05-12

### Added

- Synced the async Direct helper API with `instagrapi` `2.6.1`.
- Added `direct_message(thread_id, message_id, amount=20)` to fetch a Direct message by id.
- Added clearer Direct message request helpers: `direct_requests()` and `direct_request_approve(thread_id)`.
- Added `direct_message_unsend(thread_id, message_id)` as the unsend-style alias for the Direct item delete endpoint.

### Changed

- Updated Direct docs with message request, single-message lookup, and unsend examples.

## [0.9.1] - 2026-05-12

### Security

- Added a `pip-audit --strict .` CI gate so known-vulnerable runtime dependencies block future releases.
- Documented the published `GHSA-7mw3-79jq-xc7f` advisory in `SECURITY.md`, including the yanked affected versions and
  the fixed upgrade path.

### Changed

- Synced the async client with `instagrapi` `2.6.0`.
- Updated the default Android app profile to Instagram `428.0.0.47.67` with a physical Pixel 8 Pro device tuple.
- Switched private request headers to the current Android transport value.
- Added `Client(settings=..., override_app_version=True)` so saved session app metadata can be explicitly upgraded during construction.

### Fixed

- Truncated long public/GraphQL JSON decode error response bodies in logs so HTML error pages no longer flood consoles.
- Preserved saved legacy app profiles by default while still allowing explicit opt-in app profile upgrades.

## [0.9.0] - 2026-05-11

### Added

- Synced the async public API with `instagrapi` through upstream `2.5.18`.
- Added Trial Reels support to `clip_upload(trial=True, trial_graduation_strategy="manual")`.
- Added Reel helpers: `clip_pin`, `clip_unpin`, and `clip_share_to_fb_config`.
- Updated Reel upload to the current mobile upload flow with `upload_settings` and modern rupload headers.
- Added feed music helpers: `music_in_feed_audio_browser`, `photo_upload_with_music`, and `album_upload_with_music`.
- Added music Notes support via `notes_music_browser` and `create_music_note`.
- Added archived media/story readers: `archive_medias`, `archive_story_days`, and `archive_stories`.
- Added tagged-media pagination helpers and safer location pagination cursors.
- Added Direct reactions and thread-title updates.
- Added a Pydroid usage guide for Android environments without ffmpeg.

### Fixed

- Video uploads with a user-provided thumbnail no longer require MoviePy/ffmpeg just to read basic MP4 metadata.
- Missing ffmpeg now reports an actionable error: pass `thumbnail=...` or install/configure ffmpeg with `IMAGEIO_FFMPEG_EXE`.
- Story location stickers now prefer the external Facebook Places id when Instagram requires it.

### Changed

- Split the legacy `aiograpi.utils` module into a package while preserving old import compatibility.
- Modernized local tooling around `uv`, Ruff, current test pins, and the upstream sync workflow.

## [0.8.11] — 2026-05-05

### Fixed — Telegram support link in `docs/index.md`

The mass-rewrite in #246 missed one occurrence of `t.me/aiograpi` in
`docs/index.md`. The bare `@aiograpi` Telegram group has been
restricted by Meta and is no longer maintained — the published
`/latest/` docs were still pointing readers there. Now points at
`@aiograpi_support` like every other support link in the project.

No code changes. PR: #248.

## [0.8.10] — 2026-05-05

### Fixed — broken README doc links

All `https://subzeroid.github.io/aiograpi/X.html` links in `README.md`,
`CONTRIBUTING.md`, and `docs/index.md` returned **404**. The published
docs site uses `mike` (versioned) on top of `mkdocs` with
`use_directory_urls: true`, so the actual paths are
`/aiograpi/latest/X/` (no `.html`, trailing slash). Rewritten across
all three files to the working pattern. Bare root link
(`https://subzeroid.github.io/aiograpi/`) preserved — it now redirects
to `/latest/` (see CI section).

### CI — release-time docs publishing

`publish.yml` gains a `publish-docs` job that runs after the PyPI
upload and invokes the existing `publish-docs-with-mike` action with
`new_version: true`. Each release tag now publishes a versioned doc
set at `/aiograpi/X.Y.Z/` and updates the `latest` alias to point at
the newest. The mike action was tightened to:

- Accept tag-push events (not only `release: published`) — aiograpi's
  `publish.yml` triggers on tag push.
- Strip an optional leading `v` rather than unconditionally slicing
  the first character — aiograpi tags are unprefixed (`0.8.10`, not
  `v0.8.10`), so the old `${RELEASE_TAG:1}` would have corrupted the
  version.
- Run `mike set-default latest` so the gh-pages root has a meta-refresh
  redirect to `/latest/` instead of returning 404.

The `latest` alias and root redirect for 0.8.9 were seeded manually in
the same PR so the rewritten README links resolved on merge without
waiting for the next release.

PR: #247.

## [0.8.9] — 2026-04-29

### Security

Closes three findings from a `/cso` security audit (#242):

- **HIGH — SSRF + reachable Pillow OOB-write in `image_util.prepare_image` /
  `prepare_video`.** The `is_remote(img)` branch was calling
  `httpx.get(url, follow_redirects=True)` on caller-supplied URLs with no
  allowlist, then feeding bytes straight to `Image.open(BytesIO)`
  (CVE-2026-25990 PSD OOB write, CVE-2026-40192 FITS bomb) or
  `VideoFileClip`. Three layers of defense added:

  1. **DNS-resolved private-network denylist** — rejects 10/8, 172.16/12,
     192.168/16, 127/8, ::1, 169.254/16 (cloud metadata!), fe80::/10,
     fc00::/7. Resolves the host so `attacker.com → 127.0.0.1` fails the
     same as the literal IP. Non-http(s) schemes also rejected.
  2. **`follow_redirects=False`** — a permitted public host can't redirect
     us into a blocked target.
  3. **`Image.open(..., formats=("JPEG","PNG","WEBP","GIF"))`** — restricts
     Pillow's parser to formats IG accepts; drops PSD/FITS/TIFF parsers
     that historically carry memory-corruption CVEs.

  New helper `image_util._safe_remote_get()` shared by both prepare_*
  paths.

- **MEDIUM — Unpinned `pypa/gh-action-pypi-publish`.** Was `@release/v1`
  (moving ref); now pinned to commit SHA `cef221092ed1bacb1cc03d23a2d87d1d172e277b`
  (v1.14.0). The job has `id-token: write` for trusted PyPI publishing;
  upstream compromise of the moving ref would have given attackers PyPI
  publish authority for `aiograpi`.

- **MEDIUM — `Pillow>=8.1.1` runtime constraint allowed resolution of
  known-vulnerable versions.** Bumped to `Pillow>=12.2.0`. Compatible with
  aiograpi's Python 3.10+ requirement (Pillow 12 dropped 3.9). Test pin
  also bumped to 12.2.0; `pip-audit` reports zero known CVEs.

### Tests

- New `ImageUtilSafeRemoteFetchTestCase` with 9 cases covering loopback
  v4/v6, AWS metadata endpoint, RFC1918, non-http schemes, DNS rebinding
  via `localhost`, refusing redirects on safe-fetch path. 198 unit tests
  pass (was 189).

## [0.8.8] — 2026-04-29

### Tests — notification + signup smoke coverage

Coverage batch 3/3 from the docs+tests audit (#241). Adds smoke
tests for the two niche mixins that previously had **zero test
coverage**:

- **`SignUpTestCase` +8 cases** for the signup endpoints
  (`check_username`, `get_signup_config`, `check_email`,
  `send_verify_email`, `check_confirmation_code`,
  `check_age_eligibility`, `check_phone_number`,
  `send_signup_sms_code`). Each verifies the endpoint URL plus key
  payload fields. The phone-number tests confirm the `" "` → `"+"`
  normalization.
- **New `NotificationMixinRegressionTestCase` +7 cases** including a
  parameterized walk over all 24 `notification_*` wrappers
  verifying each dispatches to `notification_settings` with the
  correct IG-side `content_type` label. Surfaced three naming
  surprises that downstream callers may want to know about:
  `notification_connection` → `"connection_notification"`,
  `notification_login` → `"login_notification"`,
  `notification_reminders` → `"notification_reminders"`.

### Fixed — `notification_disable`

The new smoke surfaced that `Client.notification_disable` was
**unconditionally broken**: the line

```python
return all(await func("off") for func in notifications)
```

is an async generator expression and `all()` doesn't accept async
generators, so every call raised
`TypeError: 'async_generator' object is not iterable`. Replaced
with list-comprehension materialization. The path had been silently
broken since the mixin landed.

### CI

`NotificationMixinRegressionTestCase` added to the unit-test matrix.

### Audit complete

This release closes the docs+tests coverage audit started in 0.8.6.
Three batches over 0.8.6 → 0.8.8:

- **0.8.6** (#239): 15 tests on `auth.py` / `private.py` request
  payload helpers, ID generators, session round-trip, proxy
  plumbing.
- **0.8.7** (#240): 7 docstrings on high-traffic mixins (`user`,
  `media`, `comment`, `highlight`, `story`, `account`).
- **0.8.8** (#241): 15 tests on `signup.py` / `notification.py`
  + drive-by fix for `notification_disable`.

Net unit-test count: 159 → 189 (+30 tests, +1 real bug fix).

## [0.8.7] — 2026-04-29

### Docs — high-traffic-mixin docstrings

Coverage batch 2/3 from the docs+tests audit (#240). Adds proper
docstrings to 7 public methods on the high-traffic mixins where the
audit found either no docstring at all or a misleading one-liner:

- **`user.user_web_profile_info_gql`** — documents the doc_id
  PolarisProfilePageContentQuery fallback path used by
  `user_short_gql`, with all three raise-types spelled out.
- **`media.media_template_v1`** — clip "Use as template" remix flow.
- **`comment.media_comments`** — the try/fallback orchestration
  between GraphQL, sessionid-retry, and v1.
- **`highlight.highlight_edit`** — all four optional fields (title /
  cover / added_media_ids / removed_media_ids) spelled out.
- **`story.story_viewers_chunk`** — owner-only endpoint; documents
  the `(viewers, next_max_id)` tuple return shape.
- **`account.remove_bio_links`** — companion to `set_external_url`,
  notes the manual pre-signed body shape.
- **`account.set_external_url`** — was a misleading one-liner
  (`"Set new biography"`). Now documents that it replaces (not
  appends) the bio-link list with a single `external`-type link.

No behavior changes.

## [0.8.6] — 2026-04-29

### Tests — auth + private coverage

Coverage batch 1/3 from the docs+tests audit (#239). 15 new
`AuthAndStoryRegressionTestCase` cases covering request-payload
plumbing that other code paths depend on but had no direct unit
tests:

- **Request-payload helpers** (`with_default_data`,
  `with_action_data`, `with_extra_data`, `gen_user_breadcrumb`).
- **Stable ID generators** (`generate_uuid`,
  `generate_android_device_id`, `generate_mutation_token`).
- **Session round-trip** (`get_settings` ↔ `set_settings`;
  `dump_settings` ↔ `load_settings` via a real tempfile).
- **Proxy plumbing** (`set_proxy(dsn)` propagates to all three
  sessions; empty string clears all three).
- **`private.py` helpers** (`with_query_params` compact-JSON,
  `set_locale` parsing into country, `set_timezone_offset`).

No behavior changes. 174 unit tests pass (was 159).

## [0.8.5] — 2026-04-29

### Added — media v2 batch (final upstream-port batch)

Final batch (5/5) of the gap audit (#238). Two media-side
endpoints close the audit:

- **`Client.media_info_v2(media_id)`** — alternative source for
  media info via `GET discover/media_metadata/?media_id={pk}`.
  Returns the same `Media` model as `media_info_v1`, but the
  underlying `media_or_ad` payload sometimes succeeds where the
  canonical `media/{pk}/info/` path fails (ad-tagged, sponsored,
  regulated). Strips a `_userid` suffix from `media_id` automatically.
- **`Client.media_check_offensive_comment_v2(media_id, comment)`**
  — same endpoint as the v1 we shipped in 0.8.0
  (`POST media/comment/check_offensive_comment/`), but with the
  lighter payload IG's app actually sends in production:
  `{comment_text, media_id, _uuid}` directly, no `with_action_data`
  wrapping. Returns the **raw response** (not just `bool`) so callers
  can inspect any new flags IG adds beyond `is_offensive` (e.g.
  `category` / `confidence`). v1 stays for backward compat.

Test coverage: 4 new `ChapiPortedRegressionTestCase` cases
(`_userid`-suffix stripping for `media_info_v2`, `MediaNotFound`
on missing payload; lighter-payload shape, raw response, and
`PreLoginRequired` guard for the v2 offensive-check). 1 new
OPTIONAL `media_info_v2` check in `tests/live/smoke.py`.

### Hiker-next audit complete

This release closes a five-batch port (#234–#238) of every
production-confirmed method that `hapi` consumes but public
aiograpi was missing. Net additions across 0.8.1 → 0.8.5:

- **14 new methods**: `fbsearch_accounts_v2`, `fbsearch_reels_v2`,
  `fbsearch_topsearch_v2`, `fbsearch_typehead`, `user_stream_by_id_v1`,
  `user_stream_by_id_flat`, `user_stream_by_username_flat`,
  `user_web_profile_info_v1`,
  `discover_recommended_accounts_for_category_v1`,
  `user_related_profiles_gql`, `public_head`,
  `track_stream_info_by_id`, `media_info_v2`,
  `media_check_offensive_comment_v2`.
- **1 new exception**: `RelatedProfileRequired`.
- **30 new unit tests + 13 OPTIONAL live-smoke checks**.

## [0.8.4] — 2026-04-29

### Added — public_head + track_stream batch

Batch 4/5 of the gap audit (#237). Two utility endpoints:

- **`Client.public_head(url, follow_redirects=False)`** — `HEAD`
  request through the public session. Useful for resolving
  `instagram.com/share/...` short-link redirects without downloading
  the body — call with `follow_redirects=False` and read
  `response.headers["Location"]`. Bypasses `public_request`'s
  GET/POST machinery and goes straight through `httpx_ext.request`
  so the per-call `follow_redirects` flag actually takes effect.
- **`Client.track_stream_info_by_id(track_id, max_id="")`** — `POST
  clips/stream_clips_pivot_page/`. The surface IG's app uses to
  render the "Audio" page (clips-using-this-audio + audio-asset
  metadata).

### Internal

- **`httpx_ext.request`** now forwards `follow_redirects` (default
  `True` so existing callers are unaffected).
- **`TrackMixin._track_request`** now accepts a `path=` kwarg
  (default `"clips/music/"` so existing callers are unaffected).

Test coverage: 5 new cases (3 `PublicRegressionTestCase` for
`public_head` — endpoint+headers, `follow_redirects` plumbing,
`public_requests_count` increments; 2 `ChapiPortedRegressionTestCase`
for `track_stream_info_by_id` — payload shape, `max_id` forwarding
into nested `music_page`). 2 new OPTIONAL checks in
`tests/live/smoke.py`.

Docs: `docs/usage-guide/private-graphql.md` "When to use what" gets
two new rows.

## [0.8.3] — 2026-04-29

### Added — discover/related batch

Batch 3/5 of the gap audit (#236). Two
recommendation/discovery endpoints used by `hapi/routers/v2_user.py`
+ `gql_user.py`:

- **`Client.discover_recommended_accounts_for_category_v1(user_id)`**
  — two-step flow: fetches the target's profile via
  `user_stream_by_id_v1` to extract `category_id`, then calls
  `GET /discover/recommended_accounts_for_category/`. Returns the
  raw payload. `category_id` falls through as `None` if the target
  has no business category (IG still returns a payload, typically
  empty).
- **`Client.user_related_profiles_gql(user_id)`** — public GraphQL
  with the legacy `query_hash="ad99dd9d3646cc3c0dda65debcd266a7"` +
  `edge_chaining` field. Returns `List[UserShort]`. IG has been
  gating this query_hash more aggressively; for a more reliable
  mobile-app-style suggestion list, prefer `chaining()` (private API).

### New exception

- **`RelatedProfileRequired`** in `aiograpi.exceptions` — opt-in
  retry signal raised by `user_related_profiles_gql` when
  `edge_chaining` is empty AND `client.num_retry < 4`. By default
  the method just returns `[]`; callers that want upstream
  an upstream fork's retry semantics can set `num_retry` themselves.

Test coverage: 6 new `UserMixinRegressionTestCase` cases (two-step
orchestration, missing-category fall-through, edge_chaining
extraction, missing-user → `UserNotFound`, empty edges with/without
`num_retry`). 2 new OPTIONAL checks in `tests/live/smoke.py`.

Docs: `docs/usage-guide/private-graphql.md` "When to use what" gets
four new rows covering `chaining`, `fetch_suggestion_details`,
`discover_recommended_accounts_for_category_v1`, and
`user_related_profiles_gql`.

## [0.8.2] — 2026-04-29

### Added — user stream batch

Batch 2/5 of the gap audit (#235). Ports four
profile-fetch endpoints used in production by `hapi/routers/v2_user.py`
+ `v1_user.py` + `gql_user.py`:

- **`Client.user_stream_by_id_v1(user_id)`** — `POST users/{user_id}/info_stream/`,
  the pk-keyed mirror of the existing `user_stream_by_username_v1`.
- **`Client.user_stream_by_id_flat(user_id)`** — calls
  `user_stream_by_id_v1` then collapses `stream_rows[*].user`
  partial payloads into a single dict via the new
  `_user_stream_collector` helper. Promotes `pk_id` → `pk` if `pk`
  is missing.
- **`Client.user_stream_by_username_flat(username)`** — same helper,
  username variant.
- **`Client.user_web_profile_info_v1(username)`** —
  `GET users/web_profile_info/?username={username}` via the private
  host. Carries the logged-in session, bypasses public-side rate
  limiting, returns the inner `data` block already unwrapped.

Internal helper `_user_stream_collector` matches upstream
an upstream fork's defensive empty-rows fallback (one extra fetch +
`last_json`) one-for-one.

Test coverage: 7 new `UserMixinRegressionTestCase` cases (endpoint
URL, data payload, `ClientNotFoundError` → `UserNotFound` mapping,
merge ordering, `pk_id` → `pk` promotion, `web_profile_info_v1`
data unwrap + empty-data → `UserNotFound`). 4 new OPTIONAL checks
in `tests/live/smoke.py`.

Docs: `docs/usage-guide/private-graphql.md` "When to use what"
table gets five new rows.

## [0.8.1] — 2026-04-29

### Added — fbsearch v2 batch

Ports four `fbsearch_*` v2 SERP endpoints from `an upstream fork` —
the first batch of a five-batch audit of methods used in production
by hapi but missing from public aiograpi (#234):

- **`Client.fbsearch_accounts_v2(query, page_token=None)`** — hits
  `fbsearch/account_serp/`, the surface IG's app uses for the
  "Accounts" tab inside search. Returns the raw payload (`users`,
  `has_more`, `next_page_token`).
- **`Client.fbsearch_reels_v2(query, reels_max_id=None, rank_token=None)`**
  — hits `fbsearch/reels_serp/`, the "Reels" tab.
- **`Client.fbsearch_topsearch_v2(query, next_max_id=None, reels_max_id=None, rank_token=None)`**
  — hits `fbsearch/top_serp/`, the default "Top" blended tab.
  Defaults `rank_token` to `self.rank_token` (which is `self.uuid`)
  if the caller doesn't provide one.
- **`Client.fbsearch_typehead(query)`** — convenience wrapper around
  the existing `fbsearch_typeahead_stream`. Flattens the
  `stream_rows` envelope into a flat list of suggested user dicts.

Test coverage: 8 new `ChapiPortedRegressionTestCase` cases (param
shapes, optional-cursor omission, `rank_token` resolution,
`stream_rows` flattening edge cases). 4 new OPTIONAL checks in
`tests/live/smoke.py` against the test accounts pool.

Docs: `docs/usage-guide/private-graphql.md` updated with a row per
new method and an example block showing top/accounts/reels +
pagination via `page_token`.

## [0.8.0] — 2026-04-28

### Added

- **`Client.chaining(user_id)`** — calls `discover/chaining/`, the
  same private endpoint the IG app uses to render the
  "Suggested for you" carousel under a profile. Returns the raw
  payload. Maps `"Not eligible for chaining."` → `InvalidTargetUser`.
- **`Client.fetch_suggestion_details(user_id, chained_ids)`** — calls
  `discover/fetch_suggestion_details/` with `include_social_context=1`,
  expanding the suggestion list with mutual-follower / friendship
  state. `chained_ids` accepts `Union[str, List[Union[str, int]]]`
  (lists are joined internally with `,`).
- **`Client.media_check_offensive_comment(media_id, text)`** — calls
  `media/comment/check_offensive_comment/`, returns IG's
  `is_offensive` flag so callers can surface the auto-mod verdict
  before actually posting a comment. Last meaningful upstream gap
  vs instagrapi 2.4.4.

### Fixed

- **`media_seen()` (and via it `story_seen()`) actually work now.**
  Two bugs lived together: `gen(media_ids)` was passed into the
  request data dict without `await`, raising
  `TypeError: Object of type coroutine is not JSON serializable`;
  and `gen` itself used `async for` over a `List[str]`, which
  would raise `TypeError: object list can't be used in 'async for'`
  once the first bug was fixed. Closes #116 (sat in queue 18 months).
- **`extract_reply_message` now extracts `xma_share` from `xma_clip`
  / `xma_media_share`.** `extract_direct_message` already did this
  but the parallel `extract_reply_message` only handled the inline
  `clip` block, so replies quoting reel/clip shares dropped
  `xma_share=None` even though `ReplyMessage.xma_share` exists.
- **`Location.external_id` no longer crashes on missing/None payloads.**
  The model declares `Optional[int]`, but `extract_location` was
  passing the raw IG value through without coercion. When IG returned
  the field missing, `None`, `""`, or the literal string `"None"`,
  pydantic raised `int_parsing` and bubbled out of `media_info_gql`.
  Now: take `external_id` or fall back to `facebook_places_id`,
  treat empty / "None" as missing, otherwise `int()`. Closes #72.
- **`DirectThread` parses degraded payloads.**
  `business_thread_folder`, `read_state`, `assigned_admin_id`,
  `shh_mode_enabled` were declared as required scalars; IG omits
  them on older inbox shapes / Threads-app threads, breaking parsing.
  All four are now `Optional[...] = None`. Closes #7.

### CI / Tooling

- **`actions/checkout` v5 → v6** (Node 24 runtime).
- **`actions/upload-artifact` v5 → v7**, **`actions/download-artifact`
  v5 → v8.**
- **`Pillow` 11.3.0 → 12.0.0**, **`pydantic` 2.12.3 → 2.12.4**,
  **`mkdocs-material` 9.6.22 → 9.7.0**, **`bandit` 1.8.6 → 1.9.1**,
  **`pytest` ~=8.4.2 → ~=9.0.1**.
- **`mkdocstrings-python==2.0.3` pinned.** mkdocstrings 0.19+ split
  the python handler into a separate package; CI was building docs
  without it.
- **`update-dev-docs` job actually publishes now.** Fixed three
  things in one go: created the missing `gh-pages` branch (orphan,
  empty), granted the job `permissions: contents: write`, and
  flipped Pages source from `main:/docs` to `gh-pages:/`. Dev docs
  live at <https://subzeroid.github.io/aiograpi/dev/>.
- **`live-test` job is reliable.** Pure-helper pytest classes
  (`ClientMediaTestCase`, `ClientUserTestCase`, `ClientHighlightTestCase`)
  required `ACCOUNT_USERNAME`/`PASSWORD` env vars that don't exist
  in this repo's secrets — they crashed in setUp before any
  assertion ran. Removed; their pure helpers are covered by
  unit-test, and `user_followers` / `highlight_info` are now
  REQUIRED checks in `tests/live/smoke.py` against the test
  accounts pool. Plus `bandit` is green (the new `try/except/pass` in
  `_inject_sessionid_for_v2_gql` got an explicit `# nosec B110`).

### Test coverage

- New `UserMixinRegressionTestCase` cases for `chaining` /
  `fetch_suggestion_details` cover param shape, the
  `"Not eligible for chaining."` → `InvalidTargetUser` mapping,
  and `Union[str, List]` normalization.

## [0.7.2] — 2026-04-27

### Security

- **`orjson` 3.11.4 → 3.11.8 on PyPI installs.** The bug: `requirements.txt`
  was bumped to 3.11.6 in 0.6.6 (CVE-2025-67221 — `orjson.dumps` stack
  overflow on deeply nested JSON), and again to 3.11.8 in this release,
  but `setup.py` had a **hard-coded duplicate** `requirements = [...]`
  list that was never updated. So `pip install aiograpi==0.7.1` and
  every prior release back to 0.6.6 was actually pulling the vulnerable
  `orjson==3.11.4` despite our changelog claiming the bump. Fixed by
  the migration to `pyproject.toml` (single source of truth — `dependencies`
  in `[project]`).

### Packaging

- **Migrated to `pyproject.toml` (PEP 621).** Replaces `setup.py` —
  no more drift between hard-coded duplicate metadata. Long description
  now reads from `README.md` directly (PyPI showed a 700-char hand-cut
  blurb before; now shows the full README, ~17 KB). Project URLs added:
  Documentation, Changelog, Issues, Repository — all visible on PyPI's
  sidebar. Python 3.12 / 3.13 added to `classifiers`. `Framework :: AsyncIO`
  and `Operating System :: OS Independent` classifiers added.
- `dependencies` now sourced from one place (`[project] dependencies`).
  Old `setup.py`'s hard-coded `requirements = [...]` is gone.
- `.github/workflows/publish.yml` Verify step reads
  `pyproject.toml.[project].version` (was `setup.py`).

### Documentation

- **README refreshed.** Added Session Persistence section (logging in
  fresh on every run flags accounts — persist + reuse). Added Typical
  Tasks (list/download user posts, location search, followers via new
  private GraphQL). Added badges: Python versions, License, Docs,
  ZeroVer. Pointed to the new private-graphql.md page from the README.
- **GH repo `homepageUrl` → docs site** (was pointing at a marketing
  promo page; users clicking "About" landed on a sales page instead
  of `https://subzeroid.github.io/aiograpi/`).
- **Issue + PR templates upgraded to instagrapi-style v2** —
  observed/expected split, traceback `render: pytb`, login_method +
  proxy + current_master dropdowns, `raw_data` field for
  `cl.last_json`, title prefix `[BUG]` / `[Feature]`. Plus contact
  links to Discussions / Security Advisories / Telegram.
- **`docs/usage-guide/troubleshooting.md`** added (240 lines): every
  common error category with what / why / how to fix.

## [0.7.1] — 2026-04-27

### Documentation

- README: explicit ZeroVer policy section. We will not ship 1.0
  because Instagram's API rotates / deprecates / changes shapes
  without notice; pretending otherwise would mislead users who'd
  read "1.0" as "safe to pin and forget". What we commit to instead:
  `Breaking` sections in CHANGELOG per release, deprecation cycles
  ≥2 minors with `DeprecationWarning`, live CI smoke against a real
  account every push, full migration guide.

### CI

- `.github/dependabot.yml` for GitHub Actions ecosystem. Keeps
  `actions/*` and `pypa/gh-action-pypi-publish` SHA-pinned via
  auto-PR. Closes the deferred MEDIUM finding from the `/cso` audit
  (mutable tags vulnerable to upstream tag-poisoning à la
  tj-actions/changed-files, March 2025).

No runtime / API changes.

## [0.7.0] — 2026-04-27

DX audit (`/devex-review` on 0.6.6 — overall 5.5/10) drove this
release. Closes 4 of 5 actionable findings; the namespace refactor
(`client.search.*` / `client.audio.*`) is deferred to its own
milestone since it's a 200+ call-site change.

### Breaking — but fixes a hidden bug

- **`PreLoginRequired` guard on `private_request`.** Calling any
  private method (most `_v1`, all `private_graphql_*`,
  account/comment/direct mutations) without a logged-in session
  now raises `PreLoginRequired` immediately with a clear message,
  instead of letting the request proceed, get back a degraded
  payload, and crash downstream in the extractor with
  `pydantic.ValidationError: 7 validation errors for User: full_name
  field required`.

  Before:
  ```
  await Client().user_info_v1("25025320")
  # → ValidationError: 7 validation errors for User
  #     full_name: Field required ...
  ```

  After:
  ```
  await Client().user_info_v1("25025320")
  # → PreLoginRequired: Authentication required: call
  #     `await client.login(...)` (or `client.set_settings(...)`
  #     with a valid sessionid) before this method.
  ```

  If your code was `except ValidationError`-ing to detect "not
  logged in", switch to `except PreLoginRequired`. `login(login=True)`
  bypasses the guard so the login flow itself can run.

### Fixed

- **Input validation on pure-helper methods.** `media_pk_from_code(None)`
  / `('')` / non-string used to crash with
  `TypeError: 'NoneType' object is not subscriptable`. Now raises
  `ValueError("code is required and must be a non-empty string ...")`.
  Same for `media_code_from_pk(None)` and `media_pk(None)`.

### Documentation

- **`docs/getting-started.md`** was 3 sentences and 5 links. Rewrote
  with a real hello-world inline, an honest "what you'll need beyond
  `pip install`" block (account / residential proxy / TOTP), a quick
  anonymous-call example, and links into the rest of the docs.
- **`docs/migration.md`** said "the current 0.3.x line"; refreshed to
  0.7.x and prepended sections for the 0.7.0 `PreLoginRequired` break
  and the 0.6.6 TLS-verify default.

### Internal

- `.mypy-baseline` 1094 → 1095 (the new `self.user_id` reference in
  the guard adds one cross-mixin `[attr-defined]` error — same legacy
  pattern as the existing 1094, no new debt).

### Live verification

13/13 chapi methods + login (TOTP) + private endpoints all PASS through
the residential pool. Guard correctly admits authenticated calls and
rejects pre-login ones.

### Deferred to next milestone

- **Namespace objects** (`client.search.*`, `client.audio.*`,
  `client.user.followers_list_gql()`, etc.) — flat 433-method `Client`
  surface is the biggest remaining DX friction (current suffix families:
  `_v1` / `_gql` / `_v2_gql` plus `private_graphql_*` prefix
  that reads as "internal" but isn't). Big refactor with deprecation
  aliases on every old name; needs its own minor.

## [0.6.6] — 2026-04-27

### Security

Two findings from a `/cso` audit (Chief Security Officer mode —
infrastructure + code + supply chain).

- **[CRITICAL] TLS verification enabled by default.** Every
  `httpx_ext.Session()` shipped with `verify=False`, plus three
  explicit `self.{private,public,graphql}.verify = False` overrides
  in the request mixins. The historical comment was "fix
  SSLError/HTTPSConnectionPool" — a workaround for one broken proxy
  that became the global default. Effect: any MITM on the network
  path (corporate inspection gateway, malicious proxy, public Wi-Fi
  attacker, BGP hijack) could intercept `sessionid` / `password` /
  TOTP secret in the clear. Now `verify=True` by default. To
  re-enable for a known-MITM proxy: `client.private.verify = False`
  (and `.public` / `.graphql`) AFTER construction.
  Live-verified: 13/13 chapi methods + login + TOTP still PASS
  through the residential proxy pool with `verify=True`. The pool
  proxies are CONNECT-tunnels, not SSL-MITM, so the IG cert reaches
  the client honestly.
- **[MEDIUM] `orjson` 3.11.4 → 3.11.8.** CVE-2025-67221 — `orjson.dumps`
  did not bound recursion on deeply nested JSON, causing stack
  overflow on adversarial input. Fixed in 3.11.6; bumping to current
  latest 3.11.8 to absorb the intervening patches.

### Note on outstanding findings

`/cso` also flagged two MEDIUM CI/CD items: `pypa/gh-action-pypi-publish@release/v1`
and `actions/*` / `github/codeql-action/*` are pinned on mutable tags.
Both will be closed by enabling Dependabot for `github-actions`
(pin to SHA + auto-PR for updates) — separate change, not blocking.

## [0.6.5] — 2026-04-27

### Fixed

`/codex challenge` (adversarial mode, 198K tokens) caught 3 edge cases
in the bug_006 fix from 0.6.3. The HTTP-status mapping I added to
`private_graphql_query_request` was correct but incomplete — IG's
mobile-private-GraphQL surface returns recoverable account-state
failures as JSON 4xx bodies, not just HTTP status codes:

- **Body-based promotion** missing. `{"message":"login_required"}` /
  `challenge_required` / `checkpoint_required` / `consent_required` /
  `feedback_required`, `{"error_type":"rate_limit_error"}`,
  `{"message":"unable to fetch followers"}`, `{"message":"user_blocked"}`,
  `not authorized to view user` now correctly raise
  `LoginRequired` / `ChallengeRequired` / `CheckpointRequired` /
  `ConsentRequired` / `FeedbackRequired` / `RateLimitError` /
  `UserNotFound` / `SentryBlock` / `PrivateAccount`. Without this every
  mobile-GQL relogin/challenge/recovery flow was silently broken.
- **404 `b"Not Found"` masked-challenge promotion** missing. The fix
  landed in `_send_private_request:598` in 0.4.1 wasn't carried into
  the new private GraphQL path. checkpoint/challenge looked like a
  missing resource — now also raises `ChallengeRequired`.
- **`self.last_json` staleness**. Cleared before the request so callers
  inspecting it on exception don't see stale data from the prior
  successful call (mirrors `private.py:339`).

Live re-verified: 13/13 chapi methods still PASS.

### Added

- **`docs/usage-guide/private-graphql.md`** — single page covering the
  two primitives (`public_doc_id_graphql_request`,
  `private_graphql_query_request`), the 13 named convenience wrappers
  with a "when to use what" table, doc_id rotation playbook, streaming
  flag caveats (clips_profile NDJSON gotcha), and exception handling.
  Wired into mkdocs nav. `mkdocs build --strict` still clean.

## [0.6.4] — 2026-04-27

### Fixed

`/codex review` (run as an independent second opinion after the 0.6.3
ultrareview pass) caught a regression in the bug_001 fix that landed
in 0.6.3:

- **`public._send_public_request`** applied per-call `headers` ONLY by
  merging into `self.public.headers` when `update_headers in (None, True)`,
  and never passed them to `.post()` / `.get()` at all. So passing
  `update_headers=False` (which 0.6.3 did to stop session mutation)
  silently *dropped* the iPhone UA / Referer / Accept-* overrides that
  `public_doc_id_graphql_request` relies on. Live on the current pool
  it kept working (sessionid cookies carried it), but on a fresh client
  the doc_id endpoint would 403 again.
- `_send_public_request` now supports two modes explicitly:
  - `update_headers in (None, True)` — merge into session (legacy).
  - `update_headers is False` — per-request only, no mutation.
- Live re-verified: 13/13 chapi methods still PASS.

### Added

- **mypy regression gate** (CI job `mypy` + `scripts/check-mypy-baseline.sh`).
  Counts errors against `.mypy-baseline` (currently 1094) and fails if
  the count goes up; prints a notice when it goes down so the baseline
  can be ratcheted. Strict-pass is years away — 1000+ legacy untyped
  errors, mostly `[attr-defined]` from cross-mixin attribute refs that
  need Protocol scaffolding — but this stops new code from making it
  worse.
- `mypy==1.20.2` in `requirements-test.txt`.
- Type annotations on `public_doc_id_graphql_request` parameters and
  return type (`Dict[str, Any]` / `Optional`). Drops 2 mypy errors.

### Changed

- README refresh: "What's new in 0.6.x" section, Migration Guide link,
  doc-pages for the three new mixins, replaced stale
  `python setup.py sdist` instructions with the current
  trusted-publishing flow.

## [0.6.3] — 2026-04-27

### Fixed — ultrareview audit findings

Five issues surfaced by an `/ultrareview` cloud audit of the 0.5.0–0.6.2
diff. All non-breaking; live-verified 13/13 chapi methods still pass.

- **`tests.py`** (CI-breaking) — `test_private_graphql_clips_profile_includes_initial_stream_count`
  asserted `use_stream=True`, but 0.6.2 deliberately hard-coded the
  streaming flags to `False`. Test was guaranteed to fail every CI
  run on this branch and on every future PR. Flipped to `assertFalse`
  + added coverage for `use_defer`, `stream_use_customized_batch`,
  `data.should_stream_response`.
- **`Client.public_doc_id_graphql_request`** was permanently mutating
  the public session's `User-Agent` / `Accept-*` / `Referer` because
  `public_request` defaults `update_headers=None`, which is treated
  as `True`. A single `user_info_v2_gql` call left every subsequent
  public request sending the iPhone IG-app UA. Now passes
  `update_headers=False`.
- **`Client.user_info_by_username_v2_gql`** crashed with
  `AttributeError` instead of `UserNotFound` when IG returned
  `{"xdt_api__v1__fbsearch__non_profiled_serp": null}`. Intermediate
  `None` is now promoted to `{}` explicitly.
- **`private_graphql_query_request`** leaked raw
  `httpx.HTTPStatusError` from `raise_for_status()` instead of mapping
  to the documented `aiograpi.exceptions` hierarchy. Every
  `except ClientBadRequestError` / `ClientUnauthorizedError` /
  `ClientThrottledError` clause around the eight `private_graphql_*`
  wrappers was silently bypassed. Now wrapped in the same
  `except httpx_ext.HTTPError` + status-code match used by
  `_send_graphql_request`.
- **`private_graphql_followers_list` / `private_graphql_following_list`**
  wrapped `exclude_field_is_favorite` / `exclude_unused_fields` in
  `str()`, so the JSON variables payload sent `"True"` / `"False"`
  (Python repr) instead of native JSON booleans. IG's typed
  `BooleanValue` input either rejects the string (HTTP 400) or
  coerces it truthily (any non-empty string is truthy — passing
  `False` would actually flip the flag *on*). Dropped the `str()`
  wrappers.

## [0.6.2] — 2026-04-27

### Fixed

The 3 chapi-ported endpoints that were returning HTTP 400 in the
0.6.1 live verification (`private_graphql_followers_list`,
`private_graphql_following_list`, `private_graphql_clips_profile`)
now work end-to-end. Two distinct issues:

- **`client_doc_id` is mandatory**, not optional. Without it IG
  returns 400 (it can't resolve which registered query to execute).
  These methods now default `client_doc_id` to the captures shipped
  in `chapi/client.py`. Callers can still override per-call when IG
  rotates a doc_id. Defaults baked in:

  | Method | Default client_doc_id |
  |---|---|
  | `private_graphql_followers_list` | `28479704798344003308647327139` |
  | `private_graphql_following_list` | `16104639289023609826830352479` |
  | `private_graphql_clips_profile` | `209049231614685382737238866578` |
  | `private_graphql_inbox_tray_for_user` | `2035639076042015234490020607` |

- **`private_graphql_clips_profile` was asking for streaming.** With
  `should_stream_response` / `use_stream` / `use_defer` /
  `stream_use_customized_batch = True` IG returns a multi-document
  NDJSON envelope that `response.json()` can't parse
  (`JSONDecodeError: "unexpected content after document"`). All four
  flags now default to `False`. If you want raw streamed chunks,
  read `response.text` and split on document boundaries yourself.

### Live verification status (0.6.2)

13/13 chapi methods now PASS through the live smoke. All required
checks remain ✅.

## [0.6.1] — 2026-04-27

### Fixed

`Client.user_info_v2_gql` and `Client.user_info_by_username_v2_gql`
(added in 0.5.0) were 403'ing against
`https://www.instagram.com/graphql/query/`. Live-tested with a
working proxy and discovered:

- `public_doc_id_graphql_request` was sending a desktop User-Agent.
  IG rejects bare desktop POSTs to that endpoint as not-a-browser,
  not-a-mobile-app. Now sends the iPhone Instagram-app User-Agent
  (mirrors `instaloader._default_http_header(empty_session_only=True)`).
- The PolarisProfilePageContentQuery and FB-search doc_ids need
  logged-in cookies even though they go through the "public" host.
  `user_info_v2_gql` / `user_info_by_username_v2_gql` now bridge the
  private session's `sessionid` / `ds_user_id` into the public session
  via `inject_sessionid_to_public()` before the request.

### Added

- `tests/live/smoke.py` — end-to-end live smoke. Wired into the
  `live-test` GitHub Actions job. Required checks: anonymous
  `public_gql`, login (TOTP), `private_v1`, `private_v2_gql`,
  `hashtag_info_v1`, `user_medias_v1`. Optional (reports counts,
  doesn't fail the build): all 12 chapi-ported endpoints from 0.6.0.

### Live verification status (0.6.1)

Tested on a TOTP-authenticated pool account through a working proxy:

- ✅ all 6 required checks pass.
- ✅ 10/12 optional chapi endpoints pass.
- ❌ 2 chapi endpoints fail with HTTP 400 — `private_graphql_followers_list`,
  `private_graphql_following_list`, `private_graphql_clips_profile`. Tracked
  separately; doc_ids likely need refresh or payload tweaks.

## [0.6.0] — 2026-04-26

### Added — chapi sweep

13 new IG endpoints ported from `/Users/colinfrl/work/ng/chapi`
(standalone async client by the team behind related forks). All
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
`an upstream fork` fork had on top of `instagrapi==2.4.4` but never made
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
  `0.0.x`.
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

[1.2.0]: https://github.com/subzeroid/aiograpi/releases/tag/1.2.0
[1.1.0]: https://github.com/subzeroid/aiograpi/releases/tag/1.1.0
[1.0.11]: https://github.com/subzeroid/aiograpi/releases/tag/1.0.11
[1.0.10]: https://github.com/subzeroid/aiograpi/releases/tag/1.0.10
[1.0.9]: https://github.com/subzeroid/aiograpi/releases/tag/1.0.9
[1.0.8]: https://github.com/subzeroid/aiograpi/releases/tag/1.0.8
[1.0.7]: https://github.com/subzeroid/aiograpi/releases/tag/1.0.7
[1.0.6]: https://github.com/subzeroid/aiograpi/releases/tag/1.0.6
[1.0.5]: https://github.com/subzeroid/aiograpi/releases/tag/1.0.5
[1.0.4]: https://github.com/subzeroid/aiograpi/releases/tag/1.0.4
[1.0.3]: https://github.com/subzeroid/aiograpi/releases/tag/1.0.3
[1.0.2]: https://github.com/subzeroid/aiograpi/releases/tag/1.0.2
[1.0.1]: https://github.com/subzeroid/aiograpi/releases/tag/1.0.1
[1.0.0]: https://github.com/subzeroid/aiograpi/releases/tag/1.0.0
[0.7.2]: https://github.com/subzeroid/aiograpi/releases/tag/0.7.2
[0.7.1]: https://github.com/subzeroid/aiograpi/releases/tag/0.7.1
[0.7.0]: https://github.com/subzeroid/aiograpi/releases/tag/0.7.0
[0.6.6]: https://github.com/subzeroid/aiograpi/releases/tag/0.6.6
[0.6.5]: https://github.com/subzeroid/aiograpi/releases/tag/0.6.5
[0.6.4]: https://github.com/subzeroid/aiograpi/releases/tag/0.6.4
[0.6.3]: https://github.com/subzeroid/aiograpi/releases/tag/0.6.3
[0.6.2]: https://github.com/subzeroid/aiograpi/releases/tag/0.6.2
[0.6.1]: https://github.com/subzeroid/aiograpi/releases/tag/0.6.1
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

# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
(with the pre-1.0 caveat that minor bumps may include breaking changes).

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

[0.3.1]: https://github.com/subzeroid/aiograpi/releases/tag/0.3.1
[0.3.0]: https://github.com/subzeroid/aiograpi/releases/tag/0.3.0
[0.2.0]: https://github.com/subzeroid/aiograpi/releases/tag/0.2.0
[0.1.1]: https://github.com/subzeroid/aiograpi/releases/tag/0.1.1
[0.0.4]: https://github.com/subzeroid/aiograpi/releases/tag/0.0.4
[0.0.3]: https://github.com/subzeroid/aiograpi/releases/tag/0.0.3
[0.0.2]: https://github.com/subzeroid/aiograpi/releases/tag/0.0.2
[0.0.1]: https://github.com/subzeroid/aiograpi/releases/tag/0.0.1

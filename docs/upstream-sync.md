# Upstream sync policy

`aiograpi` is the async port of `instagrapi`. Package versions remain
independent, but every sync release records the `instagrapi` tag it has been
ported through.

The current recorded API baseline is:

```text
instagrapi 2.7.9
```

`aiograpi 1.0.5` includes the video dependency split, MoviePy 2 helper migration, Reel Facebook cross-post payload
follow-up, client TLS verification setting, public A1 API removal, current flow request metadata alignment, and social
action payload updates from `instagrapi` through 2.7.1, the async Direct/music/signup sync through 2.7.2, and the story
upload read-back fallback from 2.7.3. It also includes the submit-phone challenge step, refreshed comment action
metadata, upload read-back/live-test hardening, Reel music live read-back verification, and low-level Bloks two-factor
helpers from 2.7.4, plus the automatic Bloks two-factor login fallback from 2.7.5.

Subsequent 1.0.x releases continue that baseline through `instagrapi 2.7.9`, including Bloks login fallback updates,
backup-code 2FA, email confirmation helpers, password reset helpers, and album per-slide usertags.

## Release policy

- Use one `aiograpi` feature release for a large upstream sync.
- Keep patch releases for urgent fixes after that sync lands.
- Mention the upstream range in GitHub, PyPI, and Telegram release notes.

For the 2026-05 sync, the public releases are `aiograpi 0.9.0` and newer.
`aiograpi 0.9.0` synced through `instagrapi 2.5.18`, and subsequent
`aiograpi 0.9.x` patch releases continued that baseline through `instagrapi 2.6.8`, plus targeted maintenance
ports. `aiograpi 1.0.x` records the current SemVer baseline synced through `instagrapi 2.7.9`.

## Porting rules

- Preserve the async public API.
- Convert `instagrapi` imports to `aiograpi`.
- Await network-bound methods such as `private_request`, `public_request`, and
  `public_graphql_request`.
- Keep pure helpers synchronous.
- Add or port regression tests before behavior changes when practical.
- Run Ruff, regression tests, docs build, and package build before tagging.

## Future automation

When `instagrapi` publishes a release, `aiograpi` should get a visible follow-up
task even when no async changes are needed. The preferred workflow is a GitHub
Actions `workflow_dispatch` or `repository_dispatch` job that records:

- previous `instagrapi` baseline;
- new `instagrapi` tag;
- compare URL;
- checklist of changed files and release-note items.

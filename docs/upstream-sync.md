# Upstream sync policy

`aiograpi` is the async port of `instagrapi`. Package versions remain independent, but every sync release records the `instagrapi` tag it has been ported through.

The current recorded API baseline is:

```text
instagrapi 2.9.1
```

`aiograpi 1.0.x` established the SemVer async baseline through `instagrapi 2.7.17`, including Bloks login fallback
updates, backup-code 2FA, email and phone helper work, password reset helpers, album per-slide usertags, comment
pin/unpin endpoint fixes, username normalization, private GraphQL followers helpers, Story music upload helpers,
scheduled feed uploads, professional account conversion helpers, and the private media-info lookup fix for video
downloads.

`aiograpi 1.1.0` continues the mirror through `instagrapi 2.8.2`. It adds experimental async Realtime MQTT/MQTToT,
Direct message sync and lightweight Direct MQTT actions, async FBNS push MQTT with token registration and persisted
device-auth state, phone confirmation-code support, followed hashtag helpers, feed-media share-to-story, opaque Bloks
challenge context handling, and clearer Reel/clip upload failure details.

`aiograpi 1.2.x` continues the mirror through `instagrapi 2.8.19`. It adds Direct media share to existing threads, Direct message request privacy exceptions, private-first high-level user/media/story lookups for authenticated clients, sessionid username recovery via private profile stream, clear manual handling for Bloks redirect checkpoints, confirmed Reel Facebook destination normalization, hashtag private section fixes, private business contact field mapping, story metadata extraction, and private incomplete-read retry handling.

`aiograpi 1.3.0` continues the mirror through `instagrapi 2.9.0`. It adds the experimental modern CAA email signup flow via `signup_caa_email(...)`, the `graphql_www` Bloks app wrapper used by registration, and per-request private headers/domain routing so Bloks friendly names do not leak onto unrelated private requests.

The next mirror continues the baseline through `instagrapi 2.9.1` and adds the async `user_suggested_profiles(...)` convenience helper for composing chaining and expanded suggestion details.

## Release policy

- Use one `aiograpi` feature release for a large upstream sync.
- Keep patch releases for urgent fixes after that sync lands.
- Mention the upstream range in GitHub, PyPI, and Telegram release notes.

For the 2026-05 sync, the public releases are `aiograpi 0.9.0` and newer.
`aiograpi 0.9.0` synced through `instagrapi 2.5.18`, and subsequent `aiograpi 0.9.x` patch releases continued that baseline through `instagrapi 2.6.8`, plus targeted maintenance ports. `aiograpi 1.0.x` recorded the SemVer baseline through `instagrapi 2.7.17`; `aiograpi 1.1.0` records the MQTT/FBNS baseline through `instagrapi 2.8.2`; `aiograpi 1.2.x` records the follow-up high-level/private-first, Reel Facebook destination, hashtag, metadata, and private incomplete-read retry baseline through `instagrapi 2.8.19`; `aiograpi 1.3.0` records the CAA signup baseline through `instagrapi 2.9.0`; the next mirror records the suggested-profiles helper baseline through `instagrapi 2.9.1`.

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

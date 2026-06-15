# Upstream sync policy

`aiograpi` is the async port of `instagrapi`. Package versions remain independent, but every sync release records the `instagrapi` tag it has been ported through.

The current recorded API baseline is:

```text
instagrapi 2.12.0
```

`aiograpi 1.0.x` established the SemVer async baseline through `instagrapi 2.7.17`, including Bloks login fallback
updates, backup-code 2FA, email and phone helper work, password reset helpers, album per-slide usertags, comment
pin/unpin endpoint fixes, username normalization, private GraphQL followers helpers, Story music upload helpers,
scheduled feed uploads, professional account conversion helpers, coauthor upload helpers, and the private media-info lookup fix for video
downloads.

`aiograpi 1.1.0` continues the mirror through `instagrapi 2.8.2`. It adds experimental async Realtime MQTT/MQTToT,
Direct message sync and lightweight Direct MQTT actions, async FBNS push MQTT with token registration and persisted
device-auth state, phone confirmation-code support, followed hashtag helpers, feed-media share-to-story, opaque Bloks
challenge context handling, and clearer Reel/clip upload failure details.

`aiograpi 1.2.x` continues the mirror through `instagrapi 2.8.19`. It adds Direct media share to existing threads, Direct message request privacy exceptions, private-first high-level user/media/story lookups for authenticated clients, sessionid username recovery via private profile stream, clear manual handling for Bloks redirect checkpoints, confirmed Reel Facebook destination normalization, hashtag private section fixes, private business contact field mapping, story metadata extraction, and private incomplete-read retry handling.

`aiograpi 1.3.0` continues the mirror through `instagrapi 2.9.0`. It adds the experimental modern CAA email signup flow via `signup_caa_email(...)`, the `graphql_www` Bloks app wrapper used by registration, and per-request private headers/domain routing so Bloks friendly names do not leak onto unrelated private requests.

`aiograpi 1.3.1` continues the baseline through `instagrapi 2.9.1` and adds the async `user_suggested_profiles(...)` convenience helper for composing chaining and expanded suggestion details.

`aiograpi 1.4.15` continues the baseline through `instagrapi 2.10.14` and adds async story poll voting via `story_poll_vote(...)` plus private `Story.polls` extraction for story poll sticker ids, questions, options, and vote state.

`aiograpi 1.5.0` continues the baseline through `instagrapi 2.11.0` and ports the `user_follow(...)` action-count/cache semantics fix so duplicate follow attempts return `False` when the relationship already exists or is pending.

`aiograpi 1.6.0` continues the baseline through `instagrapi 2.12.0` and ports typed preservation for v2-only `UserShort` fields in private GraphQL follow-list payloads, including `friendship_status` and normalized `latest_reel_media`.

## Release policy

- Use one `aiograpi` feature release for a large upstream sync.
- Keep patch releases for urgent fixes after that sync lands.
- Mention the upstream range in GitHub, PyPI, and Telegram release notes.

For the 2026-05 sync, the public releases are `aiograpi 0.9.0` and newer.
`aiograpi 0.9.0` synced through `instagrapi 2.5.18`, and subsequent `aiograpi 0.9.x` patch releases continued that baseline through `instagrapi 2.6.8`, plus targeted maintenance ports. `aiograpi 1.0.x` recorded the SemVer async baseline through `instagrapi 2.7.17`; `aiograpi 1.1.0` records the MQTT/FBNS baseline through `instagrapi 2.8.2`; `aiograpi 1.2.x` records the follow-up high-level/private-first, Reel Facebook destination, hashtag, metadata, and private incomplete-read retry baseline through `instagrapi 2.8.19`; `aiograpi 1.3.0` records the CAA signup baseline through `instagrapi 2.9.0`; `aiograpi 1.3.1` records the suggested-profiles helper baseline through `instagrapi 2.9.1`; `aiograpi 1.3.16` records the Reel mashup-info helper baseline through `instagrapi 2.9.16`; `aiograpi 1.3.17` records the bookmarked music helper baseline through `instagrapi 2.9.17`; `aiograpi 1.3.18` records the address book suggestions helper baseline through `instagrapi 2.9.18`; `aiograpi 1.3.19` records the typed address book helper baseline through `instagrapi 2.9.19`; `aiograpi 1.4.0` records the challenge api-path normalization baseline through `instagrapi 2.10.0`; `aiograpi 1.4.1` records the canonical track not-found baseline through `instagrapi 2.10.1`; `aiograpi 1.4.2` records the XDT sidecar media-info baseline through `instagrapi 2.10.2`; `aiograpi 1.4.3` records the account-edit exception mapping baseline through `instagrapi 2.10.3`; `aiograpi 1.4.4` records the `UserShort.stories` regression baseline through `instagrapi 2.10.4`; `aiograpi 1.4.5` records the typed suggested-profiles helper baseline through `instagrapi 2.10.5`; `aiograpi 1.4.6` records the collection cursor fallback regression baseline through `instagrapi 2.10.6`; `aiograpi 1.4.7` records the Windows thumbnail-handle upload cleanup baseline through `instagrapi 2.10.7`; `aiograpi 1.4.8` records the Bloks redirect challenge resume baseline through `instagrapi 2.10.8`; `aiograpi 1.4.9` records the coauthor upload helper baseline through `instagrapi 2.10.9`; `aiograpi 1.4.10` records the public comments helper baseline through `instagrapi 2.10.10`; `aiograpi 1.4.11` records the public-first photo download baseline through `instagrapi 2.10.11`; `aiograpi 1.4.12` keeps that baseline and fixes sessionless legacy signup requests in the async port; `aiograpi 1.4.13` records the Clips seen-state helper baseline through `instagrapi 2.10.12`; `aiograpi 1.4.14` records the Reel topics/upload auth baseline through `instagrapi 2.10.13`; `aiograpi 1.4.15` records the story poll vote baseline through `instagrapi 2.10.14`; `aiograpi 1.5.0` records the user-follow action-count/cache baseline through `instagrapi 2.11.0`; `aiograpi 1.6.0` records the v2 `UserShort` field preservation baseline through `instagrapi 2.12.0`.

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

# Upstream sync policy

`aiograpi` is the async port of `instagrapi`. Package versions remain
independent, but every sync release records the `instagrapi` tag it has been
ported through.

The current non-Facebook sync baseline is:

```text
instagrapi 2.6.4
```

## Release policy

- Use one `aiograpi` feature release for a large upstream sync.
- Keep patch releases for urgent fixes after that sync lands.
- Mention the upstream range in GitHub, PyPI, and Telegram release notes.

For the 2026-05 sync, the public releases are `aiograpi 0.9.0` and newer.
`aiograpi 0.9.0` synced through `instagrapi 2.5.18`, and subsequent
`aiograpi 0.9.x` patch releases continue that non-Facebook baseline through
`instagrapi 2.6.4`. Facebook-linked account helpers are tracked separately.

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

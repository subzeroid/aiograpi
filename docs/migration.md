# Migration Guide

If you're on `aiograpi==0.0.x`, here's how to move to the current
`0.7.x` line.

## Why migrate

- **Sync with `instagrapi==2.4.4`** — months of upstream auth/session
  hardening, media configure fixes, new mixins
  (`ExploreMixin`, `FundraiserMixin`, opt-in `CaptchaHandlerMixin`),
  cutout sticker support, and `generic_xma` direct messages.
- **Pure helpers are sync.** Methods that don't do IO (URL parsing,
  base64 decode) no longer require `await`. Faster in hot paths,
  clearer signal that `await` only marks IO.
- **Active maintenance.** PyPI releases on every tag via trusted
  publishing CI.

## Version-by-version breaking changes

### 0.7.0 — `PreLoginRequired` on private endpoints

Calling any private method (anything via `private_request` — most `_v1`
methods, `private_graphql_*`, account/comment/direct mutations) without
a logged-in session now raises `PreLoginRequired` immediately with a
clear message:

```
PreLoginRequired: Authentication required: call `await client.login(...)`
(or `client.set_settings(...)` with a valid sessionid) before this method.
```

Previously these calls would hit IG anyway, get back a degraded payload,
and then fail in the extractor with a confusing pydantic
`ValidationError: 7 validation errors for User: full_name field required ...`.
The new `PreLoginRequired` is the same message you'd debug your way
toward, just delivered upfront.

If your code was catching `ValidationError` to detect "not logged in",
switch to `except PreLoginRequired`.

Pure helpers (`media_pk_from_code`, `media_code_from_pk`, `media_pk`)
also now `raise ValueError` on empty/None input instead of crashing
with `TypeError: 'NoneType' object is not subscriptable`.

### 0.6.6 — TLS verification on by default

`httpx_ext.Session` and the three Client sessions
(`client.private` / `.public` / `.graphql`) ship with `verify=True`
now. If your proxy is a known SSL-MITM (e.g. corporate inspection
gateway), you'll need to opt out explicitly **after** construction:

```python
client = Client()
client.private.verify = False
client.public.verify = False
client.graphql.verify = False
```

Most residential / CONNECT-tunnel proxies don't terminate SSL — they
just pass packets — so they keep working with the new default. Only
flip `verify=False` if you actually see SSL errors and you've verified
the proxy is trustworthy.

### 0.3.0 — six pure helpers go sync

Drop the `await`:

```python
# Before
share = await client.share_info(code)
share = await client.share_info_by_url(url)
code  = await client.share_code_from_url(url)
pk    = await client.highlight_pk_from_url(url)
client.handle_challenge_result(challenge)               # was async
client.challenge_resolve_new_password_form(result)      # was async

# After
share = client.share_info(code)
share = client.share_info_by_url(url)
code  = client.share_code_from_url(url)
pk    = client.highlight_pk_from_url(url)
client.handle_challenge_result(challenge)
client.challenge_resolve_new_password_form(result)
```

Old code with `await` raises:

```
TypeError: object str can't be used in 'await' expression
```

(or quietly returns a coroutine that's never scheduled). A grep helps:

```bash
grep -nE "await\s+\w+\.(share_info|share_info_by_url|share_code_from_url|highlight_pk_from_url|handle_challenge_result|challenge_resolve_new_password_form)\(" your_code/
```

Bonus fixes in the same release:

- `igtv_download(...)` and `highlight_remove_stories(...)` were silently
  returning a coroutine instead of awaiting their inner async call.
  If you used `await client.igtv_download(...)`, you got a coroutine
  wrapped in a coroutine — the inner one never ran. **No change to
  your call site needed**, but the result is now a real `Path` /
  `Highlight` instead of an unscheduled coroutine.

### 0.2.0 — three pure media-pk helpers go sync

Same pattern. Drop the `await`:

```python
# Before
pk    = await client.media_pk_from_code(code)
code  = await client.media_code_from_pk(pk)
short = await client.media_pk(media_id)

# After
pk    = client.media_pk_from_code(code)
code  = client.media_code_from_pk(pk)
short = client.media_pk(media_id)  # staticmethod
```

### 0.1.1 — the `instagrapi==2.4.4` sync

Pure additive on the `Client` API. No method renames, no removed
methods. New things you can use:

- `client.explore_page()`, `client.report_explore_media(media_pk)`,
  `client.explore_page_media_info(media_pk)`.
- `client.standalone_fundraiser_info_v1(user_id)`.
- `client.set_captcha_handler(handler)` — opt-in via `CaptchaHandlerMixin`
  (not auto-wired into `Client` to match upstream; subclass if you
  need it: `class MyClient(Client, CaptchaHandlerMixin): ...`).
- `DirectMessage.generic_xma` and `ReplyMessage.generic_xma` —
  `Optional[List[MediaXma]]` for new IG share formats.
- `Client(logger=...)` — pass a custom `logging.Logger` per instance
  instead of subclassing.

Constructor changes that may surprise you:

```python
# Before
Client(settings={"some": "dict"})  # caller-supplied dict was held by reference

# After
Client(settings={"some": "dict"})  # deepcopy'd, mutating it later won't leak in
```

If your code relied on `cl.settings is the_dict_i_passed`, that's no
longer true. Use `cl.settings` directly.

Internal: `aiograpi/reqwests.py` was renamed to `aiograpi/httpx_ext.py`.
If you imported `from aiograpi.reqwests import ...` (unusual — it was
an httpx shim, not a stable API), update to `from aiograpi.httpx_ext`.

## What didn't change

- **Async surface for IO methods** — every `private_request`,
  `public_request`, `public_graphql_request`, `public_a1_request`,
  upload, download, and login helper is still `async def`. Your
  existing `await client.user_info_by_username_v1(...)` keeps working.
- **`GraphQLRequestMixin`** — aiograpi-only mixin, still wired in
  the same MRO position.
- **Proxy** — `client.set_proxy(dsn)` and `client.proxy` (single
  string) work the same. We don't use a `requests`-style `proxies`
  dict like upstream does.

## Verifying the migration

After updating, run:

```bash
python -m compileall your_code/      # catches syntax errors
mypy your_code/                      # picks up aiograpi's PEP 561
                                     # types (added in 0.4.0)
```

Then exercise your hot paths against a single account before rolling
out to your full pool — the auth/session hardening in 0.1.1 changed
relogin and challenge flows; behaviour is more correct but not
identical.

## Going further

- [CHANGELOG](https://github.com/subzeroid/aiograpi/blob/main/CHANGELOG.md)
  — full per-release notes.
- [Usage Guide](usage-guide/fundamentals.md) — full method reference.
- [GitHub issues](https://github.com/subzeroid/aiograpi/issues) — if
  something broke that isn't covered here.

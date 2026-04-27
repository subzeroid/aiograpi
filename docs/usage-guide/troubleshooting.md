# Troubleshooting

Common errors and what to do about them. If your case isn't listed,
check [Handle Exceptions](handle_exception.md) for the full exception
hierarchy or open a [bug report](https://github.com/subzeroid/aiograpi/issues/new/choose).

## Authentication

### `PreLoginRequired: Authentication required`

You called a private method (most `_v1`, `private_graphql_*`, anything
that mutates account state) without logging in first.

```python
client = Client()
await client.login(USERNAME, PASSWORD)   # do this first
user = await client.user_info_v1("25025320")
```

Or restore from a saved session:

```python
client = Client()
client.set_settings(saved_dict)   # contains a valid sessionid
user = await client.user_info_v1("25025320")
```

### `BadCredentials: Both username and password must be provided`

Empty / missing username or password. Check env vars are loaded.

### `BadPassword`

Wrong password, OR Instagram flagged your account and silently invalidated
the password. If the same credentials work in the IG app, you've been
flagged — wait 24-48 hours, change IP, log in via app first.

### `TwoFactorRequired`

Pass `verification_code=` to `login()`:

```python
await client.login(USER, PASS, verification_code="123456")
```

For TOTP-based 2FA, generate the code from the seed:

```python
code = client.totp_generate_code(seed)
await client.login(USER, PASS, verification_code=code)
```

### `ChallengeRequired`

Instagram wants you to solve a challenge (email/SMS code, photo verification,
phone confirmation). See [Challenge Resolver](challenge_resolver.md) for the
flow. Often triggered by:

- New IP / device combination they haven't seen.
- Datacenter proxy (they fingerprint).
- Too many requests in a short window.

### `LoginRequired` (after a successful login)

Your `sessionid` expired or was invalidated server-side. Re-login:

```python
await client.login(USER, PASS, relogin=True)
```

Some `private_graphql_*` endpoints surface this via the 0.6.5+ body-error
promotion — you'll get `LoginRequired`, not generic `ClientForbiddenError`,
so your retry logic can branch on it correctly.

## Network & TLS

### `httpx.ConnectError` / `httpx.ReadError`

Connection-level failure. Most common causes:

- Proxy is dead or wrong port.
- Proxy provider rate-limited you (try other accounts in your pool).
- Instagram blocked the proxy IP — switch to residential.

### `ssl.SSLCertVerificationError` / TLS handshake failures

Since 0.6.6 aiograpi verifies TLS by default. If your proxy is a known
SSL-MITM (corporate inspection gateway), opt out **after** construction:

```python
client = Client()
client.private.verify = False
client.public.verify = False
client.graphql.verify = False
```

Don't blindly disable on residential proxies — that's how MITM attackers
intercept your sessionid.

### `AuthRequiredProxyError: 302 Found`

Your proxy provider redirected you to their captive portal. Usually means:

- Out of bandwidth quota.
- Subscription expired.
- Proxy creds invalid.

Open the proxy's management URL (often the redirect target) to confirm.

## IG-side rate limits & blocks

### `PleaseWaitFewMinutes`

Self-explanatory. Wait, don't retry-loop. aiograpi already retries with
backoff on 429, so this means you've exhausted that and Instagram wants
you to actually pause.

### `ClientThrottledError` (HTTP 429)

You're hitting the endpoint too fast. Slow down:

```python
client.delay_range = [3, 6]   # random delay 3-6s between requests
```

### `RateLimitError`

Account-level rate limit (vs endpoint-level `ClientThrottledError`).
Different account, different proxy, or wait it out.

### `ProxyAddressIsBlocked`

Instagram has blocklisted your proxy IP. Switch to a different (preferably
residential) IP.

### `FeedbackRequired`

Instagram thinks your account is doing automated activity (likes, follows,
DMs). Stop those operations on this account for 24-72 hours. The account
isn't banned, just on a behavioural watch.

## Data / parsing

### `pydantic.ValidationError: N validation errors for User/Media/...`

Should be rare since 0.7.0 — `PreLoginRequired` now fires upfront for
unauthenticated calls instead of letting them reach the extractor.

If you see this on an authenticated call:

- Instagram changed the response shape. File a bug with the full traceback
  and the response body (`client.last_json`, redacted).
- Your `last_json` may have a clue: `print(client.last_json)` after the failure.

### `ClientGraphqlError: Missing 'data' in GraphQL response`

GraphQL endpoint returned an error envelope. The doc_id may have rotated
(IG re-registers queries periodically). Capture a fresh `client_doc_id`
from a current Instagram-app build and pass it explicitly:

```python
data = await client.private_graphql_followers_list(
    user_id="25025320",
    rank_token=rank_token,
    client_doc_id="<fresh capture>",
)
```

See [Private GraphQL & doc_id](private-graphql.md) for the rotation
playbook.

### `ClientNotFoundError` on `/media/.../comments/`

Could be a real "media doesn't exist", or could be a masked challenge.
Since 0.4.1 aiograpi promotes `404 b"Not Found"` to `ChallengeRequired`
on the private path; since 0.6.5 it does the same on the
`private_graphql_*` path. If you're on an older version, upgrade — you
may be silently dropping work that's actually a challenge.

## Uploads

### `PhotoConfigureError` / `VideoConfigureError` / `AlbumConfigureError`

Instagram accepted the upload but the configure call failed. Common
causes:

- Image / video doesn't meet IG specs (aspect ratio, codec, size).
- Account flagged — uploads work less reliably than reads on flagged accounts.
- Cross-region upload (uploaded from one IP, configured from another).

### `VideoTooLongException`

Self-explanatory. Trim or split.

### Resource leak warnings on upload retries

Since 0.4.1 aiograpi closes file handles in `finally:` blocks across
photo/video/album/clip/story/igtv. If you see `ResourceWarning: unclosed file`
on `0.0.x`, upgrade.

## Setup

### `pip install aiograpi` succeeds but `import aiograpi` fails on `httpx`

`requirements.txt` pins `httpx==0.28.1`. If `pip` resolved a different
version due to a constraint elsewhere in your project, force-pin:

```
aiograpi==0.7.1
httpx==0.28.1
```

### `RuntimeError: This event loop is already running`

You're calling `await ...` outside an async function. Wrap in
`asyncio.run(main())` or use `nest_asyncio` for Jupyter.

### `mypy` complains about cross-mixin attributes

Known issue (`.mypy-baseline = 1095`). aiograpi mixins reference each
other's attributes (`self.user_id`, `self.private_request`) which mypy
sees as `[attr-defined]` because each mixin is checked in isolation.
We ratchet the baseline down per release. For now, suppress with
`# type: ignore[attr-defined]` if you subclass.

## When in doubt

1. Check `client.last_json` — Instagram's actual response body is often
   more informative than the exception class.
2. Check `client.last_response.status_code` and `client.last_response.url`.
3. Run [`tests/live/smoke.py`](https://github.com/subzeroid/aiograpi/blob/main/tests/live/smoke.py)
   on your environment to confirm the basic flow works at all.
4. File a [bug report](https://github.com/subzeroid/aiograpi/issues/new/choose) —
   include the traceback (redact creds), `aiograpi.__version__`, Python
   version, OS, and proxy type. The issue template has all of this.

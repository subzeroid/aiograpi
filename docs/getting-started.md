# Getting Started

## Installation

```bash
python -m pip install aiograpi
```

Requires Python 3.11+.

## Hello world

```python
import asyncio
from aiograpi import Client

async def main():
    client = Client()
    await client.login("YOUR_USERNAME", "YOUR_PASSWORD")
    user = await client.user_info_by_username("instagram")
    print(user.full_name, user.follower_count)
    medias = await client.user_medias(user.pk, amount=3)
    for m in medias:
        print(m.code, m.caption_text[:60])

asyncio.run(main())
```

That's it. You're talking to Instagram's private API.

### What you'll need beyond `pip install`

- **An Instagram account.** A real one — IG flags fresh / unverified
  accounts within a few requests.
- **(Strongly recommended) A residential proxy.** Datacenter IPs get
  rate-limited and challenge-walled fast. Pass it via
  `client.set_proxy(proxy_url)` after loading `proxy_url` from an environment variable.
- **(If 2FA is on) A TOTP code or seed.** Pass `verification_code=`
  to `login()`, or pre-generate from a seed via
  `client.totp_generate_code(seed)`.

If `login()` raises `ChallengeRequired` or `BadPassword`, that's
Instagram pushing back — see the [Challenge Resolver](usage-guide/challenge_resolver.md)
and [Handle Exceptions](usage-guide/handle_exception.md) guides.

## Reuse a saved session

```python
client = Client()
client.load_settings("session.json")
await client.login("YOUR_USERNAME", "YOUR_PASSWORD")
client.dump_settings("session.json")
```

The saved session is validated during `login()`. If Instagram rejects it with
`login_required`, aiograpi performs a fresh login with the supplied
credentials. Saving the settings again persists any refreshed session.

## Public web profile calls

Public describes the web API surface; profile queries may require session cookies. Reuse a saved session with the modern username resolver:

```python
client = Client()
client.load_settings("session.json")
user = await client.user_info_by_username_v2_gql("instagram")
print(user.username, user.pk)
```

The resolver searches for an exact username match, then fetches the profile by ID. `user_info_v2_gql(user_id)` performs that profile fetch directly. The older `user_info_by_username_gql()` helper remains available explicitly; it is not used by automatic profile routing. Other public methods can have different session requirements. `user_medias*_gql()` uses the private app GraphQL timeline first and falls back to public GraphQL on `ClientError`. Methods with `_v1` need login.

## What's Next?

* [Runnable examples](usage-guide/examples.md) — practical async scripts
* [Usage Guide](usage-guide/fundamentals.md) — every method, grouped by topic
* [Interactions](usage-guide/interactions.md) — like, follow, comment, edit
* [Private GraphQL & doc_id](usage-guide/private-graphql.md) — newer mobile-app API surface (followers, clips, search, inbox)
* [Handle Exceptions](usage-guide/handle_exception.md) — every exception you'll see and what to do
* [Challenge Resolver](usage-guide/challenge_resolver.md) — what to do when IG challenges you
* [Migration Guide](migration.md) — upgrading from `0.0.x`
* [Exceptions](exceptions.md) — full exception class reference

[docs-main]: index.md

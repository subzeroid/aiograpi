# Getting Started

## Installation

```bash
python -m pip install aiograpi
```

Requires Python 3.10+.

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
  `client.set_proxy("http://user:pass@host:port")`.
- **(If 2FA is on) A TOTP code or seed.** Pass `verification_code=`
  to `login()`, or pre-generate from a seed via
  `client.totp_generate_code(seed)`.

If `login()` raises `ChallengeRequired` or `BadPassword`, that's
Instagram pushing back — see the [Challenge Resolver](usage-guide/challenge_resolver.md)
and [Handle Exceptions](usage-guide/handle_exception.md) guides.

## Public, anonymous calls (no login)

For some endpoints you can skip login entirely:

```python
client = Client()
user = await client.user_info_by_username_gql("instagram")
print(user.username, user.pk)  # → "instagram", "25025320"
```

Methods with the `_gql` suffix hit the public web GraphQL surface and
work anonymously. Methods with `_v1` need login.

## What's Next?

* [Usage Guide](usage-guide/fundamentals.md) — every method, grouped by topic
* [Interactions](usage-guide/interactions.md) — like, follow, comment, edit
* [Private GraphQL & doc_id](usage-guide/private-graphql.md) — newer mobile-app API surface (followers, clips, search, inbox)
* [Handle Exceptions](usage-guide/handle_exception.md) — every exception you'll see and what to do
* [Challenge Resolver](usage-guide/challenge_resolver.md) — what to do when IG challenges you
* [Migration Guide](migration.md) — upgrading from `0.0.x`
* [Exceptions](exceptions.md) — full exception class reference

[docs-main]: index.md

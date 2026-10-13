You can handle exceptions centrally with `client.handle_exception`. A handler receives the client and the original exception. It may be synchronous or return an awaitable; aiograpi awaits that result before continuing.

``` python
from aiograpi import Client
from aiograpi.exceptions import ChallengeRequired


async def handle_exception(client, error):
    if isinstance(error, ChallengeRequired):
        client.logger.warning("Manual verification required; pausing this account")
    raise error


cl = Client()
cl.handle_exception = handle_exception
await cl.login(USERNAME, PASSWORD)
```

Raising from the handler stops processing and propagates the error. Returning normally tells `private_request(...)` to continue with its existing replay behavior, so a handler should return only after it has handled the error. A custom handler takes precedence over `with_challenge_flow`, including when that option is `False`.

If your application deliberately resolves a challenge in this handler, use `await client.challenge_resolve(client.last_json)` and let unresolved exceptions propagate. Configure code and password handlers as described in [challenge resolution](challenge_resolver.md).

# Best Practices

This is a best practices guide around using the Instagram API so that you don't get rate limited or banned.

## Use a Proxy

If you're getting errors like this

- "The username you entered doesn't appear to belong to an account. Please check your username and try again."

Or you notice that Instagram is sending you emails about a suspicious login attempt, you should consider using a proxy. You are getting rate limited by Instagram or they are suspicious of your location.

You should have an IP address that you use consistently per user when making API requests. This will be
less suspicious than using a different IP address every time you make a request.

From our experience, here are safe limits we've seen for various actions:
- using 10 accounts per IP address
- publishing 4-16 posts for each account
- publishing 24-48 stories

We recommend using the [SOAX](https://soax.com/?r=sEysufQI) proxy service. Here's an example of using it with `aiograpi`

``` python
from aiograpi import Client

cl = Client()
before_ip = await cl._send_public_request("https://api.ipify.org/")
cl.set_proxy("http://<api_key>:wifi;ca;;;toronto@proxy.soax.com:9137")
after_ip = await cl._send_public_request("https://api.ipify.org/")

print(f"Before: {before_ip}")
print(f"After: {after_ip}")
```

## Add Delays

It's recommended you try to mimic the behavior of a real user. This means you should add delays
between requests. The delays should be random and not too long.

The following is a good example of how to add delays between requests.

``` python
from aiograpi import Client

cl = Client()

# adds a random delay between 1 and 3 seconds after each request
cl.delay_range = [1, 3]
```


## Use Sessions

When using `.login()` you will login and create a new session with Instagram every time.
This is suspicious for Instagram.
For example, when you use your mobile device, you login to Instagram once
and then you can use it for a long time without logging in again. This is because Instagram stores
your session on your device and you can use it to login to Instagram without entering your username
and password again.

To mimic this behavior, you can use the `.login()` method once to create a session and then store that session using `.dump_settings()` and then load it again using `.load_settings()`.

The first time you run your script

``` python
from aiograpi import Client

async def main():
    cl = Client()
    await cl.login(USERNAME, PASSWORD)
    cl.dump_settings("session.json")
```

And the next time

``` python
from aiograpi import Client

async def main():
    cl = Client()
    cl.load_settings("session.json")
    await cl.login(USERNAME, PASSWORD)
    cl.dump_settings("session.json")
```

`login()` validates the loaded session before reusing it. When Instagram
returns `login_required`, aiograpi clears the rejected authorization and logs
in again with the supplied credentials. Other errors still propagate so rate
limits, challenges, and network failures are not mistaken for an expired
session. Save the settings again in case the session was refreshed.

Putting this all together, you can write a reusable login helper like this:

``` python
from aiograpi import Client
from pathlib import Path

async def login_user():
    """Login with a saved session and refresh it only when required."""
    session_file = Path("session.json")
    cl = Client()
    if session_file.exists():
        cl.load_settings(session_file)

    await cl.login(USERNAME, PASSWORD)
    cl.dump_settings(session_file)
    return cl
```


## Controlling automatic resolution

`Client()` defaults to `with_challenge_flow=False`. When `private_request(...)` encounters a challenge, it raises the original `ChallengeRequired` before calling the resolver, reading stdin, or replaying the request. You can set `cl.with_challenge_flow` on an existing client. Explicit calls to challenge helpers remain available.

To opt into automatic resolution, use `Client(with_challenge_flow=True)`. With this option, the default code and password handlers read stdin and can block the event loop while waiting. Valid piped input remains supported. End of input raises `ChallengeRequired` with the current challenge context and a hint to configure `challenge_code_handler` or `change_password_handler`. For unattended applications, keep automatic resolution disabled or provide asynchronous code/password handlers. Exceptions raised by custom handlers are propagated unchanged.

A custom `handle_exception(client, error)` takes precedence over this policy. Both synchronous handlers and handlers returning an awaitable are supported; awaitables are awaited before processing continues. Raise the error from that handler to stop the request. Returning normally retains the existing request replay behavior. When automatic resolution succeeds, the original request may also be replayed. See [exception handling](handle_exception.md).

## New password challenge

You can automatically change your password to solve the challenge from Instagram.

Declare `change_password_handler` which will return a new password.

``` python
async def change_password_handler(username):
    # Simple way to generate a random string
    chars = list("abcdefghijklmnopqrstuvwxyz1234567890!&£@#")
    password = "".join(random.sample(chars, 8))
    return password

cl = Client(with_challenge_flow=True)
cl.change_password_handler = change_password_handler
await cl.login(IG_USERNAME, IG_PASSWORD)
```


## Code verification challenge

You can automatically process the codes sent to you to solve the challenge from Instagram.

You need to declare `challenge_code_handler` which will return the code received from Instagram via Email or SMS:

``` python
from aiograpi.mixins.challenge import ChallengeChoice


async def challenge_code_handler(username, choice, challenge_url=None, sessionid=None):
    if choice == ChallengeChoice.SMS:
        return await get_code_from_sms(username)
    elif choice == ChallengeChoice.EMAIL:
        return await get_code_from_email(username)
    return False

cl = Client(with_challenge_flow=True)
cl.phone_number = "+15551234567"  # required for submit_phone challenges
cl.challenge_code_handler = challenge_code_handler
await cl.login(IG_USERNAME, IG_PASSWORD)
```

Code handlers can receive optional `challenge_url` and `sessionid` keyword arguments from legacy challenge steps. Keep these parameters (or accept `**kwargs`) in custom handlers used with those steps. The built-in manual code handler accepts the same metadata.

Login `submit_phone` challenges use `client.phone_number`, then call `challenge_code_handler(username, ChallengeChoice.SMS)` for the received code.
Signup SMS challenges use the `phone_number` passed to `signup(...)` and call `challenge_code_handler(username, ChallengeChoice.SMS)` for the received code.

Phone-only signup is supported with `await cl.signup(username, password, email="", phone_number="+15551234567")`. If both `email` and `phone_number` are provided, aiograpi keeps the email signup flow and uses the phone number only for signup challenges.

`signup(...)` emits a `RuntimeWarning` because it uses Instagram's legacy account-create flow and should be treated as experimental. On modern Instagram app versions this flow is often rejected with `SignupSpamError` / `feedback_required` because the official app uses additional signup checks that aiograpi does not currently generate. Treat this as a platform rejection, not as a malformed SMS/email code.

`signup_caa_email(...)` is the experimental modern CAA/Bloks email signup helper. It sends the current Android registration flow and uses `challenge_code_handler(username, ChallengeChoice.EMAIL)` to fetch the email confirmation code.

Native challenge payloads with `challenge.native_flow=true` and an opaque `/challenge/...` `api_path` are manual checkpoints. They do not expose an SMS/email/password step, so `challenge_code_handler` and `change_password_handler` will not be called for them.

Bloks redirect checkpoints such as `bloks_action="com.bloks.www.ig.challenge.redirect.async"` or placeholder `step_name="STEP_NAME"` require manual confirmation in the official Instagram app or web flow on a trusted device; aiograpi raises `ChallengeRequired` with the sanitized challenge context instead of treating this as a legacy step.

For example, you can get the code through the IMAP of Gmail:

``` python
async def get_code_from_email(username):
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(CHALLENGE_EMAIL, CHALLENGE_PASSWORD)
    mail.select("inbox")
    result, data = mail.search(None, "(UNSEEN)")
    assert result == "OK", "Error1 during get_code_from_email: %s" % result
    ids = data.pop().split()
    for num in reversed(ids):
        mail.store(num, "+FLAGS", "\\Seen")  # mark as read
        result, data = mail.fetch(num, "(RFC822)")
        assert result == "OK", "Error2 during get_code_from_email: %s" % result
        msg = email.message_from_string(data[0][1].decode())
        payloads = msg.get_payload()
        if not isinstance(payloads, list):
            payloads = [msg]
        code = None
        for payload in payloads:
            body = payload.get_payload(decode=True).decode()
            if "<div" not in body:
                continue
            match = re.search(">([^>]*?({u})[^<]*?)<".format(u=username), body)
            if not match:
                continue
            print("Match from email:", match.group(1))
            match = re.search(r">(\d{6})<", body)
            if not match:
                print('Skip this email, "code" not found')
                continue
            code = match.group(1)
            if code:
                return code
    return False
```

Challenge resolution helpers are implemented in [challenge.py](https://github.com/subzeroid/aiograpi/blob/main/aiograpi/mixins/challenge.py).

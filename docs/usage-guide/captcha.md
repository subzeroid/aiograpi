# Captcha

Helpers for handling Instagram captcha challenges. Register a custom handler
with `set_captcha_handler()` that receives the challenge details and returns
the solved token.

| Method                                            | Return | Description
| ------------------------------------------------- | ------ | --------------------------------------------------
| set_captcha_handler(handler)                      | None   | Register a callable that solves captcha challenges
| captcha_resolve(**challenge_details)              | str    | Resolve a captcha using the registered handler

Example:

``` python
from aiograpi import Client


def my_captcha_handler(details: dict) -> str:
    # details contains: site_key, page_url, challenge_type, raw_challenge_json
    # Forward to your favorite captcha solver and return the token
    return solve_recaptcha(
        site_key=details["site_key"],
        page_url=details["page_url"],
    )


cl = Client()
cl.set_captcha_handler(my_captcha_handler)
await cl.login(USERNAME, PASSWORD)
```

::: aiograpi.mixins.captcha.CaptchaHandlerMixin

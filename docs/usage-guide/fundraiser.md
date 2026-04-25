# Fundraiser

Helpers for fundraisers attached to Instagram accounts.

| Method                                     | Return | Description
| ------------------------------------------ | ------ | -----------------------------------
| standalone_fundraiser_info_v1(user_id)     | dict   | Get fundraiser info for a user

Example:

``` python
>>> from aiograpi import Client
>>> cl = Client()
>>> await cl.login(USERNAME, PASSWORD)

>>> user_id = await cl.user_id_from_username("instagram")
>>> await cl.standalone_fundraiser_info_v1(user_id)
{...}
```

::: aiograpi.mixins.fundraiser.FundraiserMixin

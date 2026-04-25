# Explore

Helpers for the explore page.

| Method                              | Return | Description
| ----------------------------------- | ------ | -------------------------------------------------
| explore_page()                      | dict   | Get the explore page payload
| explore_page_media_info(media_pk)   | dict   | Get media metadata for an explore page item
| report_explore_media(media_pk)      | bool   | Report a media on explore ("not interested" button)

Example:

``` python
>>> from aiograpi import Client
>>> cl = Client()
>>> await cl.login(USERNAME, PASSWORD)

>>> page = await cl.explore_page()

>>> media_pk = await cl.media_pk_from_url(
...     "https://www.instagram.com/p/ByU3LAslgWY/"
... )
>>> await cl.explore_page_media_info(media_pk)
{...}

>>> await cl.report_explore_media(media_pk)
True
```

::: aiograpi.mixins.explore.ExploreMixin

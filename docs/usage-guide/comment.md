# Comment

Post comment, viewing, like and unlike comments

Comment creation is a write action and can still trigger Instagram spam or
trust checks. Reuse saved sessions, keep volume low on new accounts, and stop
when Instagram returns feedback/challenge responses.

| Method                                                                                  | Return             | Description
| --------------------------------------------------------------------------------------- | ------------------ | --------------------------
| media_comment(media_id: str, text: str, replied_to_comment_id: Optional[int] = None) | Comment            | Add new comment to media
| media_comments(media_id: str, amount: int = 0)                                          | List\[Comment]     | Get a list comments for media (amount=0 - all comments)
| media_comments_chunk(media_id: str, max_amount: int, min_id: str = None) | Tuple[List[Comment], str] | Get chunk of comments on a media and end_cursor
| media_comments_gql(media_pk: str, amount: int = 50, max_requests: int = 0) | List\[dict] | Get comments through the public web GraphQL doc_id endpoint
| media_comments_gql_chunk(media_pk: str, end_cursor: str = "") | Tuple[List[dict], str] | Get one public web GraphQL comments page
| media_comments_public_gql(code: str, amount: int = 50, max_requests: int = 0) | List\[dict] | Get public web GraphQL comments by media shortcode
| media_comments_public_gql_chunk(code: str, end_cursor: str = "") | Tuple[List[dict], str] | Get one public web GraphQL comments page by media shortcode
| media_comment_replies(media_id: str, comment_id: str, amount: int = 0) | List\[Comment] | Get replies for a parent media comment
| media_comment_replies_chunk(media_id: str, comment_id: str, max_amount: int, min_id: str = None) | Tuple[List[Comment], str] | Get chunk of replies and the next child cursor
| media_check_offensive_comment_v2(media_id: str, comment: str) | dict | Lightweight offensive-comment preflight response
| comment_like(comment_pk: int)                                                           | bool               | Like a comment
| comment_unlike(comment_pk: int)                                                         | bool               | Unlike a comment
| comment_pin(media_id: str,comment_pk: int)                                              | bool               | Pin a comment
| comment_unpin(media_id: str,comment_pk: int)                                            | bool               | Unpin a comment
| comment_bulk_delete(media_id: str, comment_pks: List[int])                              | bool               | Delete a comment


Example:

``` python
>>> from aiograpi import Client

>>> cl = Client()
>>> await cl.login(USERNAME, PASSWORD)

>>> media_id = await cl.media_id(
>>>     await cl.media_pk_from_url('https://www.instagram.com/p/ByU3LAslgWY/')
>>> )

>>> comment = await cl.media_comment(media_id, "Test comment")
>>> comment.dict()
{'pk': 17926777897585108,
 'text': 'Test comment',
 'user': {'pk': 1903424587,
  'username': 'example',
  'full_name': 'Example Example',
  'profile_pic_url': HttpUrl('https://scontent-hel3-1.cdninstagram.com/v/t51.2885-19/s150x150/156689363_269505058076642_6448820957073669709_n.jpg?tp=1&_nc_ht=scontent-hel3-1.cdninstagram.com&_nc_ohc=EtzrL0pAdg8AX9pE_wN&edm=ABQSlwABAAAA&ccb=7-4&oh=e04d45b7651140e7fef61b1f67f1f408&oe=60C65AD1&_nc_sid=b2b2bd', scheme='https', host='scontent-hel3-1.cdninstagram.com', tld='com', host_type='domain', path='/v/t51.2885-19/s150x150/156689363_269505058076642_6448820957073669709_n.jpg', query='tp=1&_nc_ht=scontent-hel3-1.cdninstagram.com&_nc_ohc=EtzrL0pAdg8AX9pE_wN&edm=ABQSlwABAAAA&ccb=7-4&oh=e04d45b7651140e7fef61b1f67f1f408&oe=60C65AD1&_nc_sid=b2b2bd'),
  'stories': []},
 'created_at_utc': datetime.datetime(2021, 5, 15, 14, 50, 3, tzinfo=datetime.timezone.utc),
 'content_type': 'comment',
 'status': 'Active',
 'has_liked': None,
 'like_count': None}

>>> comment = await cl.media_comment(media_id, "Test comment 2", replied_to_comment_id=comment.pk)
>>> comment.dict()
{'pk': 17926777897585109,
 'text': 'Test comment 2',
 'user': {'pk': 1903424587,
  'username': 'example',
  'full_name': 'Example Example',
  'profile_pic_url': HttpUrl('https://scontent-hel3-1.cdninstagram.com/v/t51.2885-19/s150x150/156689363_269505058076642_6448820957073669709_n.jpg?tp=1&_nc_ht=scontent-hel3-1.cdninstagram.com&_nc_ohc=EtzrL0pAdg8AX9pE_wN&edm=ABQSlwABAAAA&ccb=7-4&oh=e04d45b7651140e7fef61b1f67f1f408&oe=60C65AD1&_nc_sid=b2b2bd', scheme='https', host='scontent-hel3-1.cdninstagram.com', tld='com', host_type='domain', path='/v/t51.2885-19/s150x150/156689363_269505058076642_6448820957073669709_n.jpg', query='tp=1&_nc_ht=scontent-hel3-1.cdninstagram.com&_nc_ohc=EtzrL0pAdg8AX9pE_wN&edm=ABQSlwABAAAA&ccb=7-4&oh=e04d45b7651140e7fef61b1f67f1f408&oe=60C65AD1&_nc_sid=b2b2bd'),
  'stories': []},
 'created_at_utc': datetime.datetime(2021, 5, 15, 14, 50, 3, tzinfo=datetime.timezone.utc),
 'content_type': 'comment',
 'status': 'Active',
 'has_liked': None,
 'like_count': None}

>>> comments = await cl.media_comments(media_id)
>>> comments[0].dict()
 {'pk': 17926777897585108,
 'text': 'Test comment',
 'user': {'pk': 1903424587,
  'username': 'example',
  'full_name': 'Example Example',
  'profile_pic_url': HttpUrl('https://scontent-hel3-1.cdninstagram.com/v/t51.2885-19/s150x150/156689363_269505058076642_6448820957073669709_n.jpg?tp=1&_nc_ht=scontent-hel3-1.cdninstagram.com&_nc_ohc=EtzrL0pAdg8AX9pE_wN&edm=AId3EpQBAAAA&ccb=7-4&oh=e3fbafcdb63cec3535004e85eb3397ae&oe=60C65AD1&_nc_sid=705020', scheme='https', host='scontent-hel3-1.cdninstagram.com', tld='com', host_type='domain', path='/v/t51.2885-19/s150x150/156689363_269505058076642_6448820957073669709_n.jpg', query='tp=1&_nc_ht=scontent-hel3-1.cdninstagram.com&_nc_ohc=EtzrL0pAdg8AX9pE_wN&edm=AId3EpQBAAAA&ccb=7-4&oh=e3fbafcdb63cec3535004e85eb3397ae&oe=60C65AD1&_nc_sid=705020'),
  'stories': []},
 'created_at_utc': datetime.datetime(2021, 5, 15, 14, 50, 3, tzinfo=datetime.timezone.utc),
 'content_type': 'comment',
 'status': 'Active',
 'has_liked': False,
 'like_count': 0}

>>> (comments_part1, next_min_id) = await cl.media_comments_chunk(media_id, 100)
>>> next_min_id
QVFBQmZCa1dxaFB5eFpBY2luVFMwLWdmN2ZCcUV6OF9hQWlIQk12ZWZqUlctZ2pOa1J5YjJ6bFY5Q1doSGNuUmpxSS1DdXRvZ0NLemJrR1hXd2p0dS1JMg==
>>> (comments_part2, next_min_id) = await cl.media_comments_chunk(media_id, 100, next_min_id)
>>> next_min_id
QVFEbHpIWmpFc3BNUkgzUFVuOGZOQlhDQ1hHeWlVWHlJSnBhb2FHbFB3YlJtNThnOUlrd01JUWdKRmRwZTRpWWU0bnZmX3VMNHlwcDBkWTJpZjQ2NE9SeQ==

>>> public_comments = await cl.media_comments_public_gql("CjPUjEvDKT4", amount=40)
>>> public_comments[0]["text"]
'Example public comment'

>>> preflight = await cl.media_check_offensive_comment_v2(media_id, "Some draft text")
>>> preflight["is_offensive"]
False

>>> if not preflight["is_offensive"]:
...     await cl.media_comment(media_id, "Some draft text")

>>> await cl.comment_like(17926777897585108)
True

>>> await cl.comment_unlike(17926777897585108)
True

>>> await cl.comment_bulk_delete(media_id, [17926777897585108])
True
```

Notes:

* `media_comments_public_gql()` accepts a media shortcode and automatically builds the current public GraphQL `doc_id` request and post referer. Public web endpoints are still Instagram-gated and may return 401/403/429 depending on IP, TLS fingerprint, cookies, or session state.
* `media_check_offensive_comment_v2()` can be used as an explicit lightweight preflight before `media_comment()`. `media_comment()` does not run extra preflight requests automatically, so callers can choose the request volume and handle the raw response.

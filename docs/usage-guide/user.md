# User

View a list of a user's medias, following and followers

* `user_id` - Integer ID of user, example `1903424587`

| Method                                        | Return                | Description                                                  |
|-----------------------------------------------|-----------------------|--------------------------------------------------------------|
| user_followers(user_id: str, amount: int = 0, order: str = None) | Dict\[str, UserShort] | Get dict of follower users (amount=0 - fetch all followers); `order` uses the private mobile followers endpoint |
| user_following(user_id: str, amount: int = 0) | Dict\[str, UserShort] | Get dict of following users (amount=0 - fetch all)           |
| search_followers(user_id: str, query: str)    | List[UserShort]       | Search by followers                                          |
| search_following(user_id: str, query: str)    | List[UserShort]       | Search by following                                          |
| user_info(user_id: str)                       | User                  | Get user info                                                |
| user_info_by_username(username: str)          | User                  | Get user info by username                                    |
| user_follow(user_id: str)                     | bool                  | Follow user, or request to follow a private user             |
| user_unfollow(user_id: str)                   | bool                  | Unfollow user                                                |
| user_follow_requests(amount: int = 0)         | List[UserShort]       | Get pending incoming follow requests                         |
| user_follow_request_approve(user_id: str)     | bool                  | Approve a pending incoming follow request                    |
| user_follow_request_decline(user_id: str)     | bool                  | Decline a pending incoming follow request                    |
| user_follow_requests_approve(user_ids: List[str]) | Dict[str, bool]  | Approve pending incoming follow requests                     |
| user_follow_requests_decline(user_ids: List[str]) | Dict[str, bool]  | Decline pending incoming follow requests                     |
| user_id_from_username(username: str)          | int                   | Get user_id by username                                      |
| username_from_user_id(user_id: str)           | str                   | Get username by user_id                                      |
| user_remove_follower(user_id: str)            | bool                  | Remove your follower                                         |
| mute_posts_from_follow(user_id: str)          | bool                  | Mute posts from following user                               |
| unmute_posts_from_follow(user_id: str)        | bool                  | Unmute posts from following user                             |
| mute_stories_from_follow(user_id: str)        | bool                  | Mute stories from following user                             |
| enable_posts_notifications(user_id: str)      | bool                  | Enable post notifications of user                            |
| disable_posts_notifications(user_id: str)     | bool                  | Disable post notifications of user                           |
| enable_videos_notifications(user_id: str)     | bool                  | Enable videos notifications of user                          |
| disable_videos_notifications(user_id: str)    | bool                  | Disable videos notifications of user                         |
| enable_reels_notifications(user_id: str)      | bool                  | Enable reels notifications of user                           |
| disable_reels_notifications(user_id: str)     | bool                  | Disable reels notifications of user                          |
| enable_stories_notifications(user_id: str)    | bool                  | Enable stories notifications of user                         |
| disable_stories_notifications(user_id: str)   | bool                  | Disable stories notifications of user                        |
| close_friend_add(user_id: str)                | bool                  | Add to Close Friends List                                    |
| close_friend_remove(user_id: str)             | bool                  | Remove from Close Friends List                               |
| user_suggested_profiles(user_id: str, expand_suggestion: bool = False) | dict | Suggested profiles ("Suggested for you") for a profile. Wraps `chaining` and, with `expand_suggestion=True`, returns the raw `fetch_suggestion_details` payload (`items` in current app responses) |
| address_book_link(contacts: List[AddressBookContact \| dict], include: Sequence[str] \| str = ("extra_display_name", "thumbnails")) | dict | Upload/link address book contacts and return Instagram's raw contact-based suggestions response |
| address_book_unlink()                         | dict                  | Disconnect the uploaded address book from the current account |

Low level methods:

| Method                                                                              | Return                      | Description                                                                |
|-------------------------------------------------------------------------------------|-----------------------------|----------------------------------------------------------------------------|
| user_followers_gql_chunk(user_id: str, max_amount: int = 0, end_cursor: str = None) | Tuple[List[UserShort], str] | Get user's followers information by Public Graphql API and end_cursor      |
| user_followers_gql(user_id: str, amount: int = 0)                                   | List[UserShort]             | Get user's followers information by Public Graphql API                     |
| user_followers_v1_chunk(user_id: str, max_amount: int = 0, max_id: str = "", order: str = None) | Tuple[List[UserShort], str] | Get user's followers information by Private Mobile API and max_id (cursor) |
| user_followers_v1(user_id: str, amount: int = 0, order: str = None)                 | List[UserShort]             | Get user's followers information by Private Mobile API                     |
| user_followers_private_gql_chunk(user_id: str, max_amount: int = 0, max_id: str = None, rank_token: str = None, order: str = None) | Tuple[List[UserShort], str] | Get user's followers information by Private GraphQL API and max_id         |
| user_followers_private_gql(user_id: str, amount: int = 0, rank_token: str = None, order: str = None) | List[UserShort] | Get user's followers information by Private GraphQL API                    |
| user_following_v1(user_id: str, amount: int = 0)                                    | List[UserShort]             | Get user's following users information by Private Mobile API               |
| user_following_gql(user_id: str, amount: int = 0)                                   | List[UserShort]             | Get user's following information by Public Graphql API                     |
| user_follow_requests_chunk(max_amount: int = 0, max_id: str = "")                   | Tuple[List[UserShort], str] | Get pending incoming follow requests by Private Mobile API and max_id      |
| search_followers_v1(user_id: str, query: str)                                       | List[UserShort]             | Search by followers by Private Mobile API                                  |
| search_following_v1(user_id: str, query: str)                                       | List[UserShort]             | Search by following by Private Mobile API                                  |

`user_follow()` returns `True` only when it sends a new follow action and Instagram reports either an immediate follow or a new outgoing follow request for a private account. It returns `False` when the current account already follows the target or already has a pending outgoing follow request. Use `user_friendship_v1()` when you need to distinguish `following` from `outgoing_request`.

Example:

``` python
>>> [user.pk for user in (await cl.user_followers(cl.user_id)).values()]
[5563084402, 43848984510, 1498977320, ...]

>>> await cl.user_following(cl.user_id)
{
  8530498223: UserShort(
    pk=8530498223,
    username="something",
    full_name="Example description",
    profile_pic_url=HttpUrl(
      'https://instagram.frix7-1.fna.fbcdn.net/v/t5...9217617140_n.jpg',
      scheme='https',
      host='instagram.frix7-1.fna.fbcdn.net',
      ...
    ),
  ),
  49114585: UserShort(
    pk=49114585,
    username='gx1000',
    full_name='GX1000',
    profile_pic_url=HttpUrl(
      'https://scontent-hel3-1.cdninstagram.com/v/t51.2885-19/10388...jpg',
      scheme='https',
      host='scontent-hel3-1.cdninstagram.com',
      ...
    )
  ),
  ...
}

>>> (await cl.user_info_by_username('example')).dict()
{'pk': 1903424587,
 'username': 'example',
 'full_name': 'Example Example',
 'is_private': False,
 'profile_pic_url': HttpUrl('https://scontent-hel3-1.cdninstagram.com/v/t51.2885-19/s150x150/123884060_803537687159702_2508263208740189974_n.jpg?...', scheme='https', host='scontent-hel3-1.cdninstagram.com', tld='com', host_type='domain', ...'),
 'is_verified': False,
 'media_count': 102,
 'follower_count': 576,
 'following_count': 538,
 'biography': 'Engineer: Python, JavaScript, Erlang',
 'external_url': HttpUrl('https://example.org/', scheme='https', host='example.org', tld='com', host_type='domain', path='/'),
 'is_business': False}

```

Example: We go around the list of our followers and unfollow from them:

``` python
from aiograpi import Client
cl = Client()
await cl.login(USERNAME, PASSWORD)

followers = await cl.user_followers(cl.user_id)
for follower in followers.values():
    await cl.user_unfollow(follower.pk)
```

Example: Suggested profiles ("Suggested for you") for a target user:

``` python
from aiograpi import Client
from aiograpi.exceptions import InvalidTargetUser

cl = Client()
await cl.login(USERNAME, PASSWORD)

user_id = await cl.user_id_from_username("example")
try:
    suggested = await cl.user_suggested_profiles(user_id)
    # Expanded social-context fields (current app responses expose them under "items"):
    detailed = await cl.user_suggested_profiles(user_id, expand_suggestion=True)
except InvalidTargetUser:
    # Instagram refuses chaining for locked-down / private targets
    suggested = {"users": []}
```

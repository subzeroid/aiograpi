from aiograpi.types import UserShort


def test_user_short_keeps_story_items_attached_by_story_mixins():
    user = UserShort(pk="1", username="example")

    user.stories = []

    assert user.stories == []

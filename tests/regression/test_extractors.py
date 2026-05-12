from datetime import datetime

from aiograpi.extractors import extract_direct_message, extract_direct_thread


def test_reply_message_accepts_string_microsecond_timestamp():
    message = extract_direct_message(
        {
            "item_id": "1",
            "user_id": "2",
            "timestamp": 1761953663000000,
            "item_type": "text",
            "text": "reply wrapper",
            "replied_to_message": {
                "item_id": "3",
                "user_id": "4",
                "timestamp": "1761953663000000",
                "item_type": "text",
                "text": "reply",
            },
        }
    )

    assert message.reply.timestamp == datetime.fromtimestamp(1761953663000000 // 1_000_000)


def test_direct_thread_accepts_string_last_activity_at():
    thread = extract_direct_thread(
        {
            "thread_v2_id": "1",
            "thread_id": "2",
            "items": [],
            "users": [
                {
                    "pk": "3",
                    "username": "example",
                    "profile_pic_url": "https://example.com/pic.jpg",
                }
            ],
            "left_users": [],
            "admin_user_ids": [],
            "last_activity_at": "1761953663000000",
            "muted": False,
            "named": False,
            "canonical": False,
            "pending": False,
            "archived": False,
            "thread_type": "private",
            "thread_title": "",
            "folder": 0,
            "vc_muted": False,
            "is_group": False,
            "mentions_muted": False,
            "approval_required_for_new_members": False,
            "input_mode": 0,
            "business_thread_folder": 0,
            "read_state": 0,
            "assigned_admin_id": 0,
            "shh_mode_enabled": False,
            "last_seen_at": {},
        }
    )

    assert thread.last_activity_at == datetime.fromtimestamp(1761953663000000 // 1_000_000)


def test_xma_clip_without_target_url_keeps_raw_payload():
    message = extract_direct_message(
        {
            "item_id": "1",
            "user_id": "2",
            "timestamp": 1761953663000000,
            "item_type": "xma_clip",
            "text": "",
            "xma_clip": [
                {
                    "title_text": "Shared reel",
                    "preview_media_fbid": "123456789",
                }
            ],
        }
    )

    assert message.xma_share is None
    assert message.raw_xma["xma_clip"][0]["preview_media_fbid"] == "123456789"


def test_xma_media_share_keeps_raw_payload_when_normalized():
    message = extract_direct_message(
        {
            "item_id": "1",
            "user_id": "2",
            "timestamp": 1761953663000000,
            "item_type": "xma_media_share",
            "text": "",
            "xma_media_share": [
                {
                    "target_url": "https://example.com/p/abc/",
                    "title_text": "Shared post",
                    "preview_media_fbid": "987654321",
                }
            ],
        }
    )

    assert str(message.xma_share.video_url) == "https://example.com/p/abc/"
    assert message.raw_xma["xma_media_share"][0]["preview_media_fbid"] == "987654321"

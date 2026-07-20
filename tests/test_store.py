"""Tests for the Gotify message store."""

from datetime import datetime, timezone, timedelta

from custom_components.gotify_notifications.store import GotifyMessageStore


def _make_msg(msg_id: int, appid: int = 1, priority: int = 4, hours_ago: float = 0) -> dict:
    """Create a test message."""
    dt = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return {
        "id": msg_id,
        "appid": appid,
        "message": f"Message {msg_id}",
        "title": f"Title {msg_id}",
        "priority": priority,
        "date": dt.isoformat(),
        "extras": {},
    }


def test_add_message_and_count():
    store = GotifyMessageStore(max_messages=100)
    store.add_message(_make_msg(1))
    store.add_message(_make_msg(2))
    assert store.count() == 2


def test_add_messages_bulk():
    store = GotifyMessageStore(max_messages=100)
    store.add_messages([_make_msg(1), _make_msg(2), _make_msg(3)])
    assert store.count() == 3


def test_eviction_at_max():
    store = GotifyMessageStore(max_messages=3)
    for i in range(1, 6):
        store.add_message(_make_msg(i))
    assert store.count() == 3
    msgs = store.get_messages()
    ids = [m["id"] for m in msgs]
    assert ids == [5, 4, 3]  # newest first, oldest evicted


def test_get_latest_id():
    store = GotifyMessageStore(max_messages=100)
    assert store.get_latest_id() == 0
    store.add_message(_make_msg(5))
    store.add_message(_make_msg(3))
    assert store.get_latest_id() == 5


def test_duplicate_id_ignored():
    store = GotifyMessageStore(max_messages=100)
    store.add_message(_make_msg(1))
    store.add_message(_make_msg(1))
    assert store.count() == 1


def test_count_per_app():
    store = GotifyMessageStore(max_messages=100)
    store.add_message(_make_msg(1, appid=1))
    store.add_message(_make_msg(2, appid=2))
    store.add_message(_make_msg(3, appid=1))
    assert store.count(appid=1) == 2
    assert store.count(appid=2) == 1


def test_filter_by_app():
    store = GotifyMessageStore(max_messages=100)
    store.add_message(_make_msg(1, appid=1))
    store.add_message(_make_msg(2, appid=2))
    store.add_message(_make_msg(3, appid=1))
    result = store.get_messages(filters={"apps": [1]})
    assert len(result) == 2
    assert all(m["appid"] == 1 for m in result)


def test_filter_by_priority():
    store = GotifyMessageStore(max_messages=100)
    store.add_message(_make_msg(1, priority=2))
    store.add_message(_make_msg(2, priority=5))
    store.add_message(_make_msg(3, priority=8))
    result = store.get_messages(filters={"min_priority": 5})
    assert len(result) == 2


def test_filter_by_time_range():
    store = GotifyMessageStore(max_messages=100)
    store.add_message(_make_msg(1, hours_ago=0.5))  # 30 min ago
    store.add_message(_make_msg(2, hours_ago=12))  # 12h ago
    store.add_message(_make_msg(3, hours_ago=48))  # 2 days ago
    result = store.get_messages(filters={"time_range": "1h"})
    assert len(result) == 1
    result = store.get_messages(filters={"time_range": "24h"})
    assert len(result) == 2


def test_filter_with_limit():
    store = GotifyMessageStore(max_messages=100)
    for i in range(1, 11):
        store.add_message(_make_msg(i))
    result = store.get_messages(filters={"limit": 3})
    assert len(result) == 3
    assert result[0]["id"] == 10  # newest first


def test_combined_filters():
    store = GotifyMessageStore(max_messages=100)
    store.add_message(_make_msg(1, appid=1, priority=2, hours_ago=0.5))
    store.add_message(_make_msg(2, appid=1, priority=8, hours_ago=0.5))
    store.add_message(_make_msg(3, appid=2, priority=8, hours_ago=0.5))
    store.add_message(_make_msg(4, appid=1, priority=8, hours_ago=48))
    result = store.get_messages(filters={"apps": [1], "min_priority": 5, "time_range": "24h"})
    assert len(result) == 1
    assert result[0]["id"] == 2


def test_persistence_round_trip():
    store = GotifyMessageStore(max_messages=100)
    store.add_message(_make_msg(1))
    store.add_message(_make_msg(2))
    data = store.to_dict()
    restored = GotifyMessageStore.from_dict(data, max_messages=100)
    assert restored.count() == 2
    assert restored.get_latest_id() == 2

"""In-memory message store with persistence support."""

from __future__ import annotations

import bisect
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

_LOGGER = logging.getLogger(__name__)

TIME_RANGE_MAP: dict[str, timedelta] = {
    "1h": timedelta(hours=1),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}


class GotifyMessageStore:
    """Stores Gotify messages in memory, sorted by ID descending."""

    def __init__(self, max_messages: int = 500) -> None:
        self._max = max_messages
        self._messages: list[dict] = []  # sorted by id descending
        self._ids: set[int] = set()

    def add_message(self, msg: dict) -> None:
        """Add a single message. Ignores duplicates. Evicts oldest if at capacity."""
        msg_id = msg["id"]
        if msg_id in self._ids:
            return
        self._ids.add(msg_id)
        # Insert sorted by id descending using bisect on negated ids
        neg_ids = [-m["id"] for m in self._messages]
        pos = bisect.bisect_left(neg_ids, -msg_id)
        self._messages.insert(pos, msg)
        self._evict()

    def add_messages(self, msgs: list[dict]) -> None:
        """Bulk add messages."""
        for msg in msgs:
            msg_id = msg["id"]
            if msg_id not in self._ids:
                self._ids.add(msg_id)
                self._messages.append(msg)
        self._messages.sort(key=lambda m: m["id"], reverse=True)
        self._evict()

    def _evict(self) -> None:
        """Remove oldest messages if over capacity."""
        while len(self._messages) > self._max:
            removed = self._messages.pop()
            self._ids.discard(removed["id"])

    def get_messages(self, filters: dict[str, Any] | None = None) -> list[dict]:
        """Return messages matching the given filters."""
        result = list(self._messages)

        if filters:
            if apps := filters.get("apps"):
                app_set = set(apps)
                result = [m for m in result if m["appid"] in app_set]

            if (min_pri := filters.get("min_priority")) is not None:
                result = [m for m in result if m.get("priority", 0) >= min_pri]

            if time_range := filters.get("time_range"):
                if time_range != "all" and time_range in TIME_RANGE_MAP:
                    cutoff = datetime.now(timezone.utc) - TIME_RANGE_MAP[time_range]
                    result = [m for m in result if _parse_date(m.get("date", "")) >= cutoff]

            if limit := filters.get("limit"):
                result = result[:limit]

        return result

    def get_latest_id(self) -> int:
        """Return the highest message ID, or 0 if empty."""
        return self._messages[0]["id"] if self._messages else 0

    def count(self, appid: int | None = None) -> int:
        """Return message count, optionally filtered by app."""
        if appid is None:
            return len(self._messages)
        return sum(1 for m in self._messages if m["appid"] == appid)

    def get_latest_for_app(self, appid: int) -> dict | None:
        """Return the most recent message for a given app."""
        for m in self._messages:
            if m["appid"] == appid:
                return m
        return None

    def to_dict(self) -> dict:
        """Serialize for persistence."""
        return {"messages": list(self._messages)}

    @classmethod
    def from_dict(cls, data: dict, max_messages: int = 500) -> GotifyMessageStore:
        """Restore from persisted data."""
        store = cls(max_messages=max_messages)
        store.add_messages(data.get("messages", []))
        return store


def _parse_date(date_str: str) -> datetime:
    """Parse ISO 8601 date string to datetime."""
    try:
        return datetime.fromisoformat(date_str)
    except (ValueError, TypeError):
        return datetime.min.replace(tzinfo=timezone.utc)

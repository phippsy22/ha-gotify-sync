"""Tests for Gotify sensor entities."""

from unittest.mock import MagicMock

import pytest

from custom_components.gotify_notifications.sensor import (
    GotifyNotificationSensor,
    GotifyAppSensor,
)
from custom_components.gotify_notifications.binary_sensor import (
    GotifyConnectionSensor,
)
from custom_components.gotify_notifications.store import GotifyMessageStore


SAMPLE_APPS = {
    1: {
        "id": 1,
        "name": "Backup Server",
        "description": "Backups",
        "image": "img/b.png",
        "defaultPriority": 4,
    },
    2: {
        "id": 2,
        "name": "Monitor",
        "description": "Uptime",
        "image": "img/m.png",
        "defaultPriority": 7,
    },
}


@pytest.fixture
def store():
    s = GotifyMessageStore(max_messages=100)
    s.add_messages(
        [
            {
                "id": 3,
                "appid": 1,
                "message": "m3",
                "title": "t3",
                "priority": 4,
                "date": "2025-07-19T10:00:00Z",
                "extras": {},
                "app_name": "Backup Server",
            },
            {
                "id": 2,
                "appid": 2,
                "message": "m2",
                "title": "t2",
                "priority": 8,
                "date": "2025-07-19T09:00:00Z",
                "extras": {},
                "app_name": "Monitor",
            },
            {
                "id": 1,
                "appid": 1,
                "message": "m1",
                "title": "t1",
                "priority": 2,
                "date": "2025-07-19T08:00:00Z",
                "extras": {},
                "app_name": "Backup Server",
            },
        ]
    )
    return s


@pytest.fixture
def coordinator(store):
    coord = MagicMock()
    coord.store = store
    coord.apps = SAMPLE_APPS
    coord.connected = True
    coord.last_connected = "2025-07-19T10:00:00Z"
    coord.reconnect_attempts = 0
    coord.async_add_listener = MagicMock(return_value=MagicMock())
    return coord


@pytest.fixture
def entry():
    e = MagicMock()
    e.entry_id = "test_entry"
    e.options = {"max_sensor_messages": 50}
    return e


def test_main_sensor_state(coordinator, entry):
    sensor = GotifyNotificationSensor(coordinator, entry)
    assert sensor.native_value == 3


def test_main_sensor_attributes(coordinator, entry):
    sensor = GotifyNotificationSensor(coordinator, entry)
    attrs = sensor.extra_state_attributes
    assert "messages" in attrs
    assert len(attrs["messages"]) == 3
    assert "apps" in attrs
    assert attrs["connection_status"] == "connected"


def test_app_sensor_state(coordinator, entry):
    sensor = GotifyAppSensor(coordinator, entry, app_id=1, app_info=SAMPLE_APPS[1])
    assert sensor.native_value == 2


def test_app_sensor_attributes(coordinator, entry):
    sensor = GotifyAppSensor(coordinator, entry, app_id=1, app_info=SAMPLE_APPS[1])
    attrs = sensor.extra_state_attributes
    assert attrs["app_id"] == 1
    assert attrs["app_description"] == "Backups"
    assert "latest_message" in attrs


def test_connection_sensor_connected(coordinator, entry):
    sensor = GotifyConnectionSensor(coordinator, entry)
    assert sensor.is_on is True


def test_connection_sensor_disconnected(coordinator, entry):
    coordinator.connected = False
    coordinator.reconnect_attempts = 3
    sensor = GotifyConnectionSensor(coordinator, entry)
    assert sensor.is_on is False
    attrs = sensor.extra_state_attributes
    assert attrs["reconnect_attempts"] == 3

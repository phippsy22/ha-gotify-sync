"""Tests for the Gotify coordinator."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.gotify_notifications.coordinator import GotifyCoordinator
from custom_components.gotify_notifications.store import GotifyMessageStore


SAMPLE_APPS = [
    {
        "id": 1,
        "name": "Backup",
        "description": "Backups",
        "image": "img/b.png",
        "defaultPriority": 4,
    },
    {
        "id": 2,
        "name": "Monitor",
        "description": "Uptime",
        "image": "img/m.png",
        "defaultPriority": 7,
    },
]

SAMPLE_MESSAGES_RESPONSE = {
    "messages": [
        {
            "id": 5,
            "appid": 1,
            "message": "Done",
            "title": "Backup",
            "priority": 4,
            "date": "2025-07-19T10:00:00Z",
            "extras": {},
        },
        {
            "id": 4,
            "appid": 2,
            "message": "Down",
            "title": "Alert",
            "priority": 8,
            "date": "2025-07-19T09:00:00Z",
            "extras": {},
        },
    ],
    "paging": {"limit": 200, "since": 4, "size": 2, "next": ""},
}


@pytest.fixture
def mock_hass():
    hass = MagicMock()
    hass.bus = MagicMock()
    hass.bus.async_fire = MagicMock()
    hass.async_create_task = lambda coro: coro
    def _create_bg_task(coro, **kwargs):
        coro.close()  # discard without awaiting to suppress RuntimeWarning
        return MagicMock()

    hass.async_create_background_task = MagicMock(side_effect=_create_bg_task)
    return hass


@pytest.fixture
def mock_entry():
    entry = MagicMock()
    entry.entry_id = "test_entry_123"
    entry.options = {}
    return entry


@pytest.fixture
def mock_api():
    api = AsyncMock()
    api.async_get_applications = AsyncMock(return_value=SAMPLE_APPS)
    api.async_get_messages = AsyncMock(return_value=SAMPLE_MESSAGES_RESPONSE)
    api.async_connect_websocket = AsyncMock()
    api.async_disconnect_websocket = AsyncMock()
    api.connected = False
    api.server_url = "https://gotify.example.com"
    return api


@pytest.fixture
def store():
    return GotifyMessageStore(max_messages=500)


@pytest.fixture
def coordinator(mock_hass, mock_entry, mock_api, store):
    apps = {a["id"]: a for a in SAMPLE_APPS}
    return GotifyCoordinator(
        hass=mock_hass,
        entry=mock_entry,
        api_client=mock_api,
        store=store,
        apps=apps,
    )


async def test_initial_message_load(coordinator, mock_api, store):
    await coordinator.async_start()
    mock_api.async_get_messages.assert_called_once()
    assert store.count() == 2
    assert store.get_latest_id() == 5


async def test_websocket_started_after_load(coordinator, mock_api):
    await coordinator.async_start()
    mock_api.async_connect_websocket.assert_called_once()


async def test_on_message_adds_to_store_and_fires_event(coordinator, mock_hass, store):
    await coordinator.async_start()
    new_msg = {
        "id": 6,
        "appid": 1,
        "message": "New backup",
        "title": "Backup",
        "priority": 4,
        "date": "2025-07-19T11:00:00Z",
        "extras": {},
    }
    coordinator._on_message(new_msg)
    assert store.count() == 3
    assert store.get_latest_id() == 6
    mock_hass.bus.async_fire.assert_called()
    call_args = mock_hass.bus.async_fire.call_args
    event_data = call_args[1].get("event_data") or call_args[0][1]
    assert event_data["id"] == 6


async def test_listener_notified_on_message(coordinator):
    await coordinator.async_start()
    callback = MagicMock()
    coordinator.async_add_listener(callback)
    coordinator._on_message(
        {
            "id": 7,
            "appid": 1,
            "message": "test",
            "title": "T",
            "priority": 1,
            "date": "2025-07-19T12:00:00Z",
            "extras": {},
        }
    )
    callback.assert_called_once()


async def test_stop_disconnects(coordinator, mock_api):
    await coordinator.async_start()
    await coordinator.async_stop()
    mock_api.async_disconnect_websocket.assert_called_once()


async def test_reconnect_retries_after_failed_attempt(coordinator, mock_api):
    """A failed reconnect attempt must schedule another retry (regression)."""
    from custom_components.gotify_notifications.api import GotifyConnectionError

    await coordinator.async_start()
    assert coordinator.connected

    # Simulate disconnect, then make reconnection fail
    mock_api.async_connect_websocket.side_effect = GotifyConnectionError("down")
    coordinator._on_disconnect()
    first_attempts = coordinator.reconnect_attempts
    assert first_attempts == 1

    # Run the scheduled reconnect coroutine directly (bypassing sleep)
    await coordinator._reconnect(0)

    # The failed reconnect must have scheduled ANOTHER attempt
    assert coordinator.reconnect_attempts > first_attempts

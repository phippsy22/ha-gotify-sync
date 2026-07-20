"""Tests for integration setup and WebSocket API."""

from unittest.mock import MagicMock

import pytest

from custom_components.gotify_notifications.const import (
    WS_TYPE_GET_MESSAGES,
)


SAMPLE_APPS = [{"id": 1, "name": "Test", "description": "d", "image": "", "defaultPriority": 0}]
SAMPLE_MESSAGES = {"messages": [], "paging": {"limit": 200, "since": 0, "size": 0, "next": ""}}


@pytest.fixture
def mock_hass():
    hass = MagicMock()
    hass.data = {}
    hass.bus = MagicMock()
    hass.bus.async_fire = MagicMock()
    hass.async_create_task = lambda coro: coro
    return hass


@pytest.fixture
def mock_entry():
    entry = MagicMock()
    entry.entry_id = "test_123"
    entry.data = {
        "url": "https://gotify.example.com",
        "token": "CTest123",
        "verify_ssl": True,
    }
    entry.options = {}
    return entry


async def test_ws_api_get_messages_schema():
    """Verify the WS API message type constant is set correctly."""
    assert WS_TYPE_GET_MESSAGES == "gotify_notifications/get_messages"

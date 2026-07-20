"""Tests for the Gotify Notifications config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.gotify_notifications.const import (
    CONF_TOKEN,
    CONF_URL,
    CONF_VERIFY_SSL,
)
from custom_components.gotify_notifications.config_flow import GotifyConfigFlow
from custom_components.gotify_notifications.api import (
    GotifyAuthError,
    GotifyConnectionError,
)


USER_INPUT = {
    CONF_URL: "https://gotify.example.com",
    CONF_TOKEN: "CTestToken123",
    CONF_VERIFY_SSL: True,
}


@pytest.fixture
def mock_api():
    with patch("custom_components.gotify_notifications.config_flow.GotifyApiClient") as mock_cls:
        client = AsyncMock()
        client.async_get_applications = AsyncMock(return_value=[{"id": 1, "name": "Test"}])
        mock_cls.return_value = client
        yield client


def _make_flow():
    """Create a GotifyConfigFlow with a properly mocked hass."""
    flow = GotifyConfigFlow()
    hass = MagicMock()
    hass.config_entries.flow.async_progress_by_handler.return_value = []
    hass.config_entries.async_entries.return_value = []
    hass.config_entries.async_entry_for_domain_unique_id.return_value = None
    flow.hass = hass
    flow.context = {}
    return flow


async def test_config_flow_success(mock_api):
    flow = _make_flow()

    result = await flow.async_step_user(user_input=None)
    assert result["type"] == "form"

    result = await flow.async_step_user(user_input=USER_INPUT)
    assert result["type"] == "create_entry"
    assert result["title"] == "gotify.example.com"
    assert result["data"][CONF_URL] == USER_INPUT[CONF_URL]


async def test_config_flow_auth_error(mock_api):
    mock_api.async_get_applications.side_effect = GotifyAuthError("bad token")
    flow = _make_flow()

    result = await flow.async_step_user(user_input=USER_INPUT)
    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_config_flow_connection_error(mock_api):
    mock_api.async_get_applications.side_effect = GotifyConnectionError("timeout")
    flow = _make_flow()

    result = await flow.async_step_user(user_input=USER_INPUT)
    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}

"""Config flow for Gotify Notifications integration."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .api import GotifyApiClient, GotifyAuthError, GotifyConnectionError
from .const import (
    CONF_MAX_MESSAGES,
    CONF_MAX_SENSOR_MESSAGES,
    CONF_POLL_INTERVAL,
    CONF_TOKEN,
    CONF_URL,
    CONF_VERIFY_SSL,
    DEFAULT_MAX_MESSAGES,
    DEFAULT_MAX_SENSOR_MESSAGES,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_TOKEN): str,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
    }
)


class GotifyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Gotify Notifications."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            token = user_input[CONF_TOKEN]
            verify_ssl = user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)

            # Check for duplicates
            await self.async_set_unique_id(f"{url}_{token[:8]}")
            self._abort_if_unique_id_configured()

            try:
                async with aiohttp.ClientSession() as session:
                    client = GotifyApiClient(
                        session=session,
                        url=url,
                        token=token,
                        verify_ssl=verify_ssl,
                    )
                    await client.async_get_applications()
            except GotifyAuthError:
                errors["base"] = "invalid_auth"
            except GotifyConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during config flow")
                errors["base"] = "unknown"
            else:
                parsed = urlparse(url)
                title = parsed.hostname or url
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_URL: url,
                        CONF_TOKEN: token,
                        CONF_VERIFY_SSL: verify_ssl,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> GotifyOptionsFlow:
        """Get the options flow."""
        return GotifyOptionsFlow(config_entry)


class GotifyOptionsFlow(OptionsFlow):
    """Handle options for Gotify Notifications."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self._config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_MAX_MESSAGES,
                        default=options.get(CONF_MAX_MESSAGES, DEFAULT_MAX_MESSAGES),
                    ): vol.All(int, vol.Range(min=50, max=2000)),
                    vol.Optional(
                        CONF_MAX_SENSOR_MESSAGES,
                        default=options.get(CONF_MAX_SENSOR_MESSAGES, DEFAULT_MAX_SENSOR_MESSAGES),
                    ): vol.All(int, vol.Range(min=10, max=200)),
                    vol.Optional(
                        CONF_POLL_INTERVAL,
                        default=options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
                    ): vol.All(int, vol.Range(min=60, max=3600)),
                }
            ),
        )

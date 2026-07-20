"""Gotify Notifications integration for Home Assistant."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .api import GotifyApiClient, GotifyAuthError, GotifyConnectionError
from .const import (
    CONF_MAX_MESSAGES,
    CONF_TOKEN,
    CONF_URL,
    CONF_VERIFY_SSL,
    DEFAULT_MAX_MESSAGES,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    PLATFORMS,
    WS_TYPE_GET_MESSAGES,
)
from .coordinator import GotifyCoordinator
from .frontend import GotifyCardRegistration
from .store import GotifyMessageStore

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY_PREFIX = f"{DOMAIN}"
STORAGE_VERSION = 1


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Gotify Notifications from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    url = entry.data[CONF_URL]
    token = entry.data[CONF_TOKEN]
    verify_ssl = entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
    max_messages = entry.options.get(CONF_MAX_MESSAGES, DEFAULT_MAX_MESSAGES)

    session = async_get_clientsession(hass, verify_ssl=verify_ssl)
    api_client = GotifyApiClient(session=session, url=url, token=token, verify_ssl=verify_ssl)

    # Fetch application metadata
    try:
        app_list = await api_client.async_get_applications()
    except GotifyAuthError as err:
        raise ConfigEntryAuthFailed("Invalid Gotify client token") from err
    except GotifyConnectionError as err:
        raise ConfigEntryNotReady("Cannot connect to Gotify server") from err
    apps = {a["id"]: a for a in app_list}

    # Load or create message store
    store_key = f"{STORAGE_KEY_PREFIX}.{entry.entry_id}"
    ha_store = Store(hass, STORAGE_VERSION, store_key)
    persisted = await ha_store.async_load()
    if persisted:
        message_store = GotifyMessageStore.from_dict(persisted, max_messages=max_messages)
    else:
        message_store = GotifyMessageStore(max_messages=max_messages)

    coordinator = GotifyCoordinator(
        hass=hass,
        entry=entry,
        api_client=api_client,
        store=message_store,
        apps=apps,
    )

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api": api_client,
        "store": message_store,
        "ha_store": ha_store,
    }

    # Register the WebSocket API (once)
    _register_websocket_api(hass)

    # Start coordinator (initial load + WebSocket)
    try:
        await coordinator.async_start()
    except GotifyConnectionError as err:
        raise ConfigEntryNotReady("Cannot connect to Gotify server") from err

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Persist store periodically via listener
    async def _persist_on_stop(event: Any) -> None:
        await ha_store.async_save(message_store.to_dict())

    entry.async_on_unload(hass.bus.async_listen_once("homeassistant_stop", _persist_on_stop))

    # Also persist on new messages (debounced — 30 s delay to avoid thrashing)
    def _get_store_data() -> dict:
        return message_store.to_dict()

    def _persist_on_message() -> None:
        ha_store.async_delay_save(_get_store_data, 30)

    coordinator.async_add_listener(_persist_on_message)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    # Register frontend card
    async def _setup_frontend(_event=None) -> None:
        registrar = GotifyCardRegistration(hass, version="1.0.0")
        await registrar.async_register()

    if hass.state == CoreState.running:
        await _setup_frontend()
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _setup_frontend)

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    data = hass.data[DOMAIN].get(entry.entry_id)
    if data:
        coordinator: GotifyCoordinator = data["coordinator"]
        await coordinator.async_stop()

        # Persist before unloading
        ha_store = data["ha_store"]
        await ha_store.async_save(data["store"].to_dict())

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok


_WS_API_REGISTERED = False


def _register_websocket_api(hass: HomeAssistant) -> None:
    """Register the WebSocket API commands (only once)."""
    global _WS_API_REGISTERED
    if _WS_API_REGISTERED:
        return
    _WS_API_REGISTERED = True

    @websocket_api.websocket_command(
        {
            vol.Required("type"): WS_TYPE_GET_MESSAGES,
            vol.Optional("entry_id"): str,
            vol.Optional("filters"): {
                vol.Optional("apps"): [int],
                vol.Optional("min_priority"): int,
                vol.Optional("time_range"): str,
                vol.Optional("limit"): int,
            },
        }
    )
    @callback
    def ws_get_messages(
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        msg: dict,
    ) -> None:
        """Handle get_messages WebSocket command."""
        entries = hass.data.get(DOMAIN, {})

        entry_id = msg.get("entry_id")
        if entry_id:
            entry_data = entries.get(entry_id)
        elif len(entries) == 1:
            entry_data = next(iter(entries.values()))
            entry_id = next(iter(entries.keys()))
        elif not entries:
            connection.send_error(msg["id"], "not_found", "No Gotify servers configured")
            return
        else:
            connection.send_error(
                msg["id"],
                "multiple_entries",
                f"Multiple Gotify servers configured. Specify entry_id."
                f" Available: {list(entries.keys())}",
            )
            return

        if not entry_data:
            connection.send_error(msg["id"], "not_found", "Entry not found")
            return

        coordinator: GotifyCoordinator = entry_data["coordinator"]
        filters = msg.get("filters")
        messages = coordinator.store.get_messages(filters=filters)

        # Build full image URLs for apps
        server_url = coordinator._api.server_url
        apps_with_urls = {}
        for aid, ainfo in coordinator.apps.items():
            app_copy = dict(ainfo)
            if image := ainfo.get("image"):
                app_copy["image_url"] = f"{server_url}/{image}"
            apps_with_urls[aid] = app_copy

        connection.send_result(
            msg["id"],
            {
                "messages": messages,
                "total": coordinator.store.count(),
                "filtered": len(messages),
                "apps": apps_with_urls,
                "server_url": server_url,
            },
        )

    websocket_api.async_register_command(hass, ws_get_messages)

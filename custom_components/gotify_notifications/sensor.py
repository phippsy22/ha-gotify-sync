"""Sensor entities for Gotify Notifications."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_MAX_SENSOR_MESSAGES, DEFAULT_MAX_SENSOR_MESSAGES, DOMAIN
from .coordinator import GotifyCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Gotify sensor entities."""
    coordinator: GotifyCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities: list[SensorEntity] = []

    # Main notification sensor
    entities.append(GotifyNotificationSensor(coordinator, entry))

    # Per-app sensors
    for app_id, app_info in coordinator.apps.items():
        entities.append(GotifyAppSensor(coordinator, entry, app_id, app_info))

    async_add_entities(entities)


def _slugify(name: str) -> str:
    """Simple slugify for entity IDs."""
    return name.lower().replace(" ", "_").replace("-", "_")


class GotifyNotificationSensor(SensorEntity):
    """Main Gotify notification count sensor."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: GotifyCoordinator, entry: ConfigEntry) -> None:
        self._coordinator = coordinator
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_notifications"
        self._attr_name = "Gotify Notifications"
        self._attr_icon = "mdi:bell"
        self._unsub: Any = None

    @property
    def native_value(self) -> int:
        return self._coordinator.store.count()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        max_msgs = self._entry.options.get(CONF_MAX_SENSOR_MESSAGES, DEFAULT_MAX_SENSOR_MESSAGES)
        messages = self._coordinator.store.get_messages(filters={"limit": max_msgs})
        return {
            "messages": messages,
            "apps": self._coordinator.apps,
            "last_updated": self._coordinator.last_connected,
            "connection_status": ("connected" if self._coordinator.connected else "disconnected"),
        }

    async def async_added_to_hass(self) -> None:
        self._unsub = self._coordinator.async_add_listener(self._handle_update)

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub:
            self._unsub()

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()


class GotifyAppSensor(SensorEntity):
    """Per-app notification count sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GotifyCoordinator,
        entry: ConfigEntry,
        app_id: int,
        app_info: dict,
    ) -> None:
        self._coordinator = coordinator
        self._entry = entry
        self._app_id = app_id
        self._app_info = app_info
        slug = _slugify(app_info.get("name", f"app_{app_id}"))
        self._attr_unique_id = f"{entry.entry_id}_{slug}"
        self._attr_name = f"Gotify {app_info.get('name', f'App {app_id}')}"
        self._attr_icon = "mdi:bell-outline"
        self._unsub: Any = None

    @property
    def native_value(self) -> int:
        return self._coordinator.store.count(appid=self._app_id)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        latest = self._coordinator.store.get_latest_for_app(self._app_id)
        return {
            "app_id": self._app_id,
            "app_description": self._app_info.get("description", ""),
            "default_priority": self._app_info.get("defaultPriority", 0),
            "latest_message": latest,
        }

    async def async_added_to_hass(self) -> None:
        self._unsub = self._coordinator.async_add_listener(self._handle_update)

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub:
            self._unsub()

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()

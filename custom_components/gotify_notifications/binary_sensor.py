"""Binary sensor for Gotify connection status."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import GotifyCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Gotify binary sensor."""
    coordinator: GotifyCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([GotifyConnectionSensor(coordinator, entry)])


class GotifyConnectionSensor(BinarySensorEntity):
    """Binary sensor for Gotify WebSocket connection health."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: GotifyCoordinator, entry: ConfigEntry) -> None:
        self._coordinator = coordinator
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_connection"
        self._attr_name = "Gotify Connection"
        self._unsub: Any = None

    @property
    def is_on(self) -> bool:
        return self._coordinator.connected

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "last_connected": self._coordinator.last_connected,
            "reconnect_attempts": self._coordinator.reconnect_attempts,
        }

    async def async_added_to_hass(self) -> None:
        self._unsub = self._coordinator.async_add_listener(self._handle_update)

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub:
            self._unsub()

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()

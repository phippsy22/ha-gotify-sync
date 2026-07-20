"""Frontend resource registration for Gotify Notifications."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

URL_BASE = "/gotify-notification-card"
FILENAME = "gotify-notification-card.js"


class GotifyCardRegistration:
    """Registers the Gotify Lovelace card in Home Assistant."""

    def __init__(self, hass: HomeAssistant, version: str) -> None:
        self.hass = hass
        self.version = version

    async def async_register(self) -> None:
        """Register static path and Lovelace resource."""
        await self._async_register_static_path()

        lovelace = self.hass.data.get("lovelace")
        if lovelace and lovelace.mode == "storage":
            await self._async_register_resource(lovelace)
        else:
            _LOGGER.info(
                "Lovelace is in YAML mode. Manually add resource: url: %s/%s, type: module",
                URL_BASE,
                FILENAME,
            )

    async def _async_register_static_path(self) -> None:
        """Register the static HTTP path to serve the JS file."""
        card_dir = Path(__file__).parent / "frontend"
        try:
            await self.hass.http.async_register_static_paths(
                [StaticPathConfig(URL_BASE, str(card_dir), False)]
            )
        except RuntimeError:
            _LOGGER.debug("Static path %s already registered", URL_BASE)

    async def _async_register_resource(self, lovelace: Any) -> None:
        """Register or update the Lovelace resource."""
        url = f"{URL_BASE}/{FILENAME}"
        url_with_version = f"{url}?v={self.version}"

        if not lovelace.resources.loaded:
            await lovelace.resources.async_load()

        existing = [r for r in lovelace.resources.async_items() if r["url"].startswith(URL_BASE)]

        for resource in existing:
            if resource["url"].split("?")[0] == url:
                current_ver = resource["url"].split("?v=")[-1] if "?v=" in resource["url"] else "0"
                if current_ver != self.version:
                    await lovelace.resources.async_update_item(
                        resource["id"],
                        {"res_type": "module", "url": url_with_version},
                    )
                    _LOGGER.info("Updated Gotify Card resource to v%s", self.version)
                return

        await lovelace.resources.async_create_item({"res_type": "module", "url": url_with_version})
        _LOGGER.info("Registered Gotify Card resource v%s", self.version)

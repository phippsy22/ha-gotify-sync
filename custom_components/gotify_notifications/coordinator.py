"""Coordinator for Gotify Notifications — WebSocket-first hybrid."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .api import GotifyApiClient, GotifyConnectionError
from .store import GotifyMessageStore
from .const import (
    EVENT_NOTIFICATION_RECEIVED,
)

_LOGGER = logging.getLogger(__name__)

BACKOFF_INTERVALS = [5, 10, 20, 60]  # seconds


class GotifyCoordinator:
    """Manages Gotify WebSocket connection and message state."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api_client: GotifyApiClient,
        store: GotifyMessageStore,
        apps: dict[int, dict],
    ) -> None:
        self.hass = hass
        self._entry = entry
        self._api = api_client
        self._store = store
        self._apps = apps
        self._listeners: list[Callable] = []
        self._connected = False
        self._last_connected: str | None = None
        self._reconnect_attempts = 0
        self._reconnect_task: asyncio.Task | None = None
        self._running = False

    @property
    def store(self) -> GotifyMessageStore:
        return self._store

    @property
    def apps(self) -> dict[int, dict]:
        return self._apps

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def last_connected(self) -> str | None:
        return self._last_connected

    @property
    def reconnect_attempts(self) -> int:
        return self._reconnect_attempts

    @property
    def listeners(self) -> list[Callable]:
        return self._listeners

    def async_add_listener(self, callback: Callable) -> Callable:
        """Register a listener. Returns a callable to unsubscribe."""
        self._listeners.append(callback)

        def remove():
            self._listeners.remove(callback)

        return remove

    def _notify_listeners(self) -> None:
        for cb in self._listeners:
            try:
                cb()
            except Exception:
                _LOGGER.exception("Error in coordinator listener")

    async def async_start(self) -> None:
        """Load initial messages and start WebSocket connection."""
        self._running = True

        # Fetch initial message history
        try:
            result = await self._api.async_get_messages(limit=200)
            messages = result.get("messages", [])
            if messages:
                self._store.add_messages(messages)
                _LOGGER.info("Loaded %d initial messages from Gotify", len(messages))
        except GotifyConnectionError:
            _LOGGER.warning("Could not fetch initial messages — will retry via WebSocket")

        # Start WebSocket
        await self._connect_websocket()

    async def _connect_websocket(self) -> None:
        """Open the WebSocket connection."""
        try:
            await self._api.async_connect_websocket(
                on_message=self._on_message,
                on_disconnect=self._on_disconnect,
            )
            self._connected = True
            self._last_connected = datetime.now(timezone.utc).isoformat()
            self._reconnect_attempts = 0
            _LOGGER.info("Connected to Gotify WebSocket stream")
            self._notify_listeners()
        except GotifyConnectionError:
            _LOGGER.warning("WebSocket connection failed, scheduling reconnect")
            self._on_disconnect()

    def _on_message(self, data: dict) -> None:
        """Handle an incoming WebSocket message."""
        # Enrich with app name
        appid = data.get("appid")
        app = self._apps.get(appid, {})
        data["app_name"] = app.get("name", f"App {appid}")

        self._store.add_message(data)

        # Fire HA event
        self.hass.bus.async_fire(
            EVENT_NOTIFICATION_RECEIVED,
            {
                "entry_id": self._entry.entry_id,
                **data,
            },
        )

        self._notify_listeners()

    def _on_disconnect(self) -> None:
        """Handle WebSocket disconnection."""
        self._connected = False
        self._notify_listeners()
        if self._running:
            self._schedule_reconnect()

    def _schedule_reconnect(self) -> None:
        """Schedule a reconnection attempt with exponential backoff."""
        current = asyncio.current_task()
        if (
            self._reconnect_task
            and not self._reconnect_task.done()
            and self._reconnect_task is not current
        ):
            return

        idx = min(self._reconnect_attempts, len(BACKOFF_INTERVALS) - 1)
        delay = BACKOFF_INTERVALS[idx]
        self._reconnect_attempts += 1
        _LOGGER.info(
            "Scheduling reconnect in %ds (attempt %d)",
            delay,
            self._reconnect_attempts,
        )
        self._reconnect_task = self.hass.async_create_background_task(
            self._reconnect(delay), name="gotify_reconnect"
        )

    async def _reconnect(self, delay: float) -> None:
        """Reconnect after a delay, catching up on missed messages."""
        await asyncio.sleep(delay)
        if not self._running:
            return

        # Catch up on missed messages via REST
        last_id = self._store.get_latest_id()
        if last_id > 0:
            try:
                missed = await self._api.async_get_all_messages_since(last_id)
                if missed:
                    for msg in missed:
                        appid = msg.get("appid")
                        app = self._apps.get(appid, {})
                        msg["app_name"] = app.get("name", f"App {appid}")
                    self._store.add_messages(missed)
                    _LOGGER.info("Caught up on %d missed messages", len(missed))
            except GotifyConnectionError:
                _LOGGER.warning("REST catch-up failed")

        # Reconnect WebSocket
        await self._connect_websocket()

    async def async_stop(self) -> None:
        """Stop the coordinator and close connections."""
        self._running = False
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
        await self._api.async_disconnect_websocket()
        self._connected = False

    async def async_refresh_apps(self) -> None:
        """Refresh application metadata from the server."""
        try:
            app_list = await self._api.async_get_applications()
            self._apps = {a["id"]: a for a in app_list}
        except GotifyConnectionError:
            _LOGGER.warning("Could not refresh app metadata")

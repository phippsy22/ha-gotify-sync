"""Gotify REST and WebSocket API client."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

import aiohttp

_LOGGER = logging.getLogger(__name__)


class GotifyApiError(Exception):
    """Base exception for Gotify API errors."""


class GotifyAuthError(GotifyApiError):
    """Authentication failed."""


class GotifyConnectionError(GotifyApiError):
    """Connection to Gotify server failed."""


class GotifyApiClient:
    """Client for the Gotify REST and WebSocket API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        url: str,
        token: str,
        verify_ssl: bool = True,
    ) -> None:
        self._session = session
        self._url = url.rstrip("/")
        self._token = token
        self._verify_ssl = verify_ssl
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._ws_task: asyncio.Task | None = None

    @property
    def connected(self) -> bool:
        """Return True if WebSocket is connected."""
        return self._ws is not None and not self._ws.closed

    @property
    def server_url(self) -> str:
        """Return the Gotify server URL."""
        return self._url

    def _headers(self) -> dict[str, str]:
        return {"X-Gotify-Key": self._token}

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Make an authenticated request to the Gotify API."""
        url = f"{self._url}{path}"
        ssl = None if self._verify_ssl else False
        try:
            async with self._session.request(
                method, url, headers=self._headers(), ssl=ssl, **kwargs
            ) as resp:
                if resp.status == 401:
                    raise GotifyAuthError("Invalid client token")
                if resp.status == 403:
                    raise GotifyAuthError("Forbidden — check token permissions")
                resp.raise_for_status()
                return await resp.json()
        except aiohttp.ClientError as err:
            if isinstance(err, aiohttp.ClientResponseError):
                raise
            raise GotifyConnectionError(f"Cannot connect to {url}: {err}") from err

    async def async_get_applications(self) -> list[dict]:
        """Fetch all applications from the Gotify server."""
        return await self._request("GET", "/application")

    async def async_get_messages(self, limit: int = 200, since: int | None = None) -> dict:
        """Fetch messages with pagination support."""
        params: dict[str, int] = {"limit": min(limit, 200)}
        if since is not None:
            params["since"] = since
        return await self._request("GET", "/message", params=params)

    async def async_get_all_messages_since(
        self, last_id: int, limit_per_page: int = 200
    ) -> list[dict]:
        """Fetch all messages newer than last_id by paginating.

        Gotify returns messages newest-first and has no `after_id` param,
        so we fetch pages and filter client-side until we hit a message
        with id <= last_id.
        """
        all_new: list[dict] = []
        since: int | None = None

        while True:
            page = await self.async_get_messages(limit=limit_per_page, since=since)
            messages = page.get("messages", [])

            if not messages:
                break

            for msg in messages:
                if msg["id"] > last_id:
                    all_new.append(msg)
                else:
                    return all_new

            paging = page.get("paging", {})
            if not paging.get("next"):
                break
            since = paging.get("since")

        return all_new

    async def async_connect_websocket(
        self,
        on_message: Callable[[dict], None],
        on_disconnect: Callable[[], None],
    ) -> None:
        """Connect to the Gotify WebSocket stream."""
        ws_url = self._url.replace("https://", "wss://").replace("http://", "ws://")
        stream_url = f"{ws_url}/stream?token={self._token}"
        ssl = None if self._verify_ssl else False

        try:
            self._ws = await self._session.ws_connect(stream_url, ssl=ssl, heartbeat=30)
        except aiohttp.ClientError as err:
            raise GotifyConnectionError(f"WebSocket connection failed: {err}") from err

        self._ws_task = asyncio.ensure_future(self._ws_listen(on_message, on_disconnect))

    async def _ws_listen(
        self,
        on_message: Callable[[dict], None],
        on_disconnect: Callable[[], None],
    ) -> None:
        """Listen for messages on the WebSocket."""
        assert self._ws is not None
        try:
            async for msg in self._ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = msg.json()
                        on_message(data)
                    except Exception:
                        _LOGGER.exception("Error processing WebSocket message")
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    _LOGGER.error("WebSocket error: %s", self._ws.exception())
                    break
                elif msg.type in (
                    aiohttp.WSMsgType.CLOSE,
                    aiohttp.WSMsgType.CLOSING,
                    aiohttp.WSMsgType.CLOSED,
                ):
                    break
        except asyncio.CancelledError:
            return
        except Exception:
            _LOGGER.exception("WebSocket listener error")
        finally:
            on_disconnect()

    async def async_disconnect_websocket(self) -> None:
        """Disconnect from the WebSocket stream."""
        if self._ws_task and not self._ws_task.done():
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
        if self._ws and not self._ws.closed:
            await self._ws.close()
        self._ws = None
        self._ws_task = None

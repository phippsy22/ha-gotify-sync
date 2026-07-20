"""Tests for the Gotify API client."""

import aiohttp
import pytest
from aioresponses import aioresponses

from custom_components.gotify_notifications.api import (
    GotifyApiClient,
    GotifyAuthError,
    GotifyConnectionError,
)


@pytest.fixture
def mock_aiohttp():
    with aioresponses() as m:
        yield m


@pytest.fixture
def api_client(aiohttp_session, gotify_url, gotify_token):
    return GotifyApiClient(
        session=aiohttp_session,
        url=gotify_url,
        token=gotify_token,
        verify_ssl=False,
    )


SAMPLE_APPS = [
    {
        "id": 1,
        "name": "Backup Server",
        "description": "Nightly backups",
        "internal": False,
        "image": "image/backup.png",
        "defaultPriority": 4,
    },
    {
        "id": 2,
        "name": "Uptime Kuma",
        "description": "Monitoring",
        "internal": False,
        "image": "image/uptime.png",
        "defaultPriority": 7,
    },
]

SAMPLE_MESSAGES = {
    "messages": [
        {
            "id": 10,
            "appid": 1,
            "message": "Backup completed",
            "title": "Backup",
            "priority": 4,
            "date": "2025-07-19T10:00:00Z",
            "extras": {},
        },
        {
            "id": 9,
            "appid": 2,
            "message": "Service down",
            "title": "Alert",
            "priority": 8,
            "date": "2025-07-19T09:30:00Z",
            "extras": {},
        },
    ],
    "paging": {"limit": 200, "since": 9, "size": 2, "next": ""},
}


async def test_get_applications(api_client, mock_aiohttp, gotify_url):
    mock_aiohttp.get(f"{gotify_url}/application", payload=SAMPLE_APPS)
    apps = await api_client.async_get_applications()
    assert len(apps) == 2
    assert apps[0]["name"] == "Backup Server"


async def test_get_applications_auth_error(api_client, mock_aiohttp, gotify_url):
    mock_aiohttp.get(f"{gotify_url}/application", status=401)
    with pytest.raises(GotifyAuthError):
        await api_client.async_get_applications()


async def test_get_applications_connection_error(api_client, mock_aiohttp, gotify_url):
    mock_aiohttp.get(f"{gotify_url}/application", exception=aiohttp.ClientError())
    with pytest.raises(GotifyConnectionError):
        await api_client.async_get_applications()


async def test_get_messages(api_client, mock_aiohttp, gotify_url):
    mock_aiohttp.get(f"{gotify_url}/message?limit=200", payload=SAMPLE_MESSAGES)
    result = await api_client.async_get_messages(limit=200)
    assert len(result["messages"]) == 2
    assert result["messages"][0]["id"] == 10


async def test_get_messages_with_since(api_client, mock_aiohttp, gotify_url):
    mock_aiohttp.get(f"{gotify_url}/message?limit=100&since=20", payload=SAMPLE_MESSAGES)
    result = await api_client.async_get_messages(limit=100, since=20)
    assert len(result["messages"]) == 2


async def test_get_all_messages_since_single_page(api_client, mock_aiohttp, gotify_url):
    """When all new messages fit in one page."""
    mock_aiohttp.get(f"{gotify_url}/message?limit=200", payload=SAMPLE_MESSAGES)
    messages = await api_client.async_get_all_messages_since(last_id=8)
    assert len(messages) == 2
    assert messages[0]["id"] == 10


async def test_get_all_messages_since_no_new(api_client, mock_aiohttp, gotify_url):
    """When there are no new messages."""
    mock_aiohttp.get(f"{gotify_url}/message?limit=200", payload=SAMPLE_MESSAGES)
    messages = await api_client.async_get_all_messages_since(last_id=10)
    assert len(messages) == 0

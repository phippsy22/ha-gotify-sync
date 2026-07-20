"""Shared test fixtures."""

import aiohttp
import pytest


@pytest.fixture
def gotify_url():
    return "https://gotify.example.com"


@pytest.fixture
def gotify_token():
    return "CTestClientToken123"


@pytest.fixture
async def aiohttp_session():
    async with aiohttp.ClientSession() as session:
        yield session

"""Pytest configuration and fixtures."""

import asyncio
from typing import AsyncGenerator, Generator

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

from app.main import app, create_app


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Create sync test client."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def sample_task() -> dict:
    """Sample task data for testing."""
    return {
        "task_id": "test_task_001",
        "task_name": "Extract Product Info",
        "task_type": "extraction",
        "target_fields": ["name", "price", "description"],
        "target_url": "https://example.com/product/123",
    }


@pytest.fixture
def sample_action() -> dict:
    """Sample action data for testing."""
    return {
        "action_type": "extract_field",
        "parameters": {
            "field_name": "price",
            "selector": ".product-price",
        },
        "confidence": 0.95,
    }

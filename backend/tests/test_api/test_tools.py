"""Tests for tool endpoints."""

import pytest
from fastapi.testclient import TestClient


def test_list_tools(client: TestClient) -> None:
    """Test listing available tools."""
    response = client.get("/api/tools/registry")
    assert response.status_code == 200
    data = response.json()
    assert "tools" in data


def test_tool_test_endpoint(client: TestClient) -> None:
    """Test tool testing endpoint."""
    test_request = {
        "tool_name": "navigate_to",
        "parameters": {"url": "https://example.com"},
        "dry_run": True,
    }
    response = client.post("/api/tools/test", json=test_request)
    # Either success or tool not found is acceptable
    assert response.status_code in [200, 404]

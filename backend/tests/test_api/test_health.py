"""Tests for health check endpoints."""

import pytest
from fastapi.testclient import TestClient


def test_health_endpoint(client: TestClient) -> None:
    """Test health check returns OK."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_ready_endpoint(client: TestClient) -> None:
    """Test readiness check."""
    response = client.get("/api/ready")
    assert response.status_code == 200
    data = response.json()
    assert "ready" in data

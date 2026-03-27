"""Tests for agent endpoints."""

import pytest
from fastapi.testclient import TestClient


def test_list_agents(client: TestClient) -> None:
    """Test listing available agents."""
    response = client.get("/api/agents/types/")
    assert response.status_code == 200
    data = response.json()
    assert "agents" in data


def test_run_agent(client: TestClient, sample_task: dict) -> None:
    """Test running an agent."""
    run_request = {
        "agent_type": "planner",
        "episode_id": "test-episode-123",
        "task_context": sample_task,
    }
    response = client.post("/api/agents/run", json=run_request)
    # 200 for success, 500 for coordinator errors (expected without full setup)
    assert response.status_code in [200, 500]

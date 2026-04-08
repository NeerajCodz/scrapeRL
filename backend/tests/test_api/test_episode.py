"""Tests for episode endpoints."""

import pytest
from fastapi.testclient import TestClient


def test_reset_episode(client: TestClient, sample_task: dict) -> None:
    """Test resetting an episode."""
    reset_request = {"task_id": sample_task["task_id"]}
    response = client.post("/api/episode/reset", json=reset_request)
    assert response.status_code == 201
    data = response.json()
    assert "episode_id" in data
    assert "observation" in data


def test_step_episode(client: TestClient, sample_task: dict, sample_action: dict) -> None:
    """Test stepping through an episode."""
    # First reset
    reset_request = {"task_id": sample_task["task_id"]}
    reset_response = client.post("/api/episode/reset", json=reset_request)
    assert reset_response.status_code == 201
    episode_id = reset_response.json()["episode_id"]
    
    # Then step
    step_data = {
        "episode_id": episode_id,
        "action": sample_action,
    }
    response = client.post("/api/episode/step", json=step_data)
    assert response.status_code == 200
    data = response.json()
    assert "observation" in data
    assert "reward" in data


def test_get_state(client: TestClient, sample_task: dict) -> None:
    """Test getting episode state."""
    # First reset
    reset_request = {"task_id": sample_task["task_id"]}
    reset_response = client.post("/api/episode/reset", json=reset_request)
    episode_id = reset_response.json()["episode_id"]
    
    # Get state
    response = client.get(f"/api/episode/state/{episode_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["episode_id"] == episode_id


def test_openenv_reset_alias(client: TestClient, sample_task: dict) -> None:
    """Test OpenEnv-compatible reset alias at root path."""
    response = client.post("/reset", json={"task": sample_task["task_id"]})
    assert response.status_code == 200
    data = response.json()
    assert "episode_id" in data
    assert data["task_id"] == sample_task["task_id"]


def test_openenv_step_alias_with_string_action(client: TestClient, sample_task: dict) -> None:
    """Test OpenEnv-compatible step alias accepts string action payloads."""
    reset_response = client.post("/reset", json={"task_id": sample_task["task_id"]})
    assert reset_response.status_code == 200
    episode_id = reset_response.json()["episode_id"]

    step_response = client.post(
        "/step",
        json={
            "episode_id": episode_id,
            "action": "done",
        },
    )
    assert step_response.status_code == 200
    data = step_response.json()
    assert "done" in data

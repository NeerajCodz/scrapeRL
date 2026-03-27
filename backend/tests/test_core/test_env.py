"""Tests for environment."""

import pytest
from app.core.env import WebScraperEnv


def test_env_creation() -> None:
    """Test creating environment."""
    env = WebScraperEnv(episode_id="test-episode-001")
    assert env is not None
    assert env.episode_id == "test-episode-001"


@pytest.mark.asyncio
async def test_env_reset() -> None:
    """Test environment reset."""
    env = WebScraperEnv(episode_id="test-episode-002")
    observation, info = await env.reset(task_id="test_task", seed=42)
    assert observation is not None
    assert observation.step_number == 0

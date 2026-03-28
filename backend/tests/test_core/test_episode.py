"""Tests for episode management."""

import pytest
from app.core.episode import Episode, EpisodeStep, EpisodeStatus, EpisodeManager


class TestEpisode:
    """Test Episode class."""

    def test_episode_creation(self) -> None:
        """Test creating an episode."""
        episode = Episode(
            episode_id="ep_001",
            task_id="task_001",
            max_steps=10,
        )

        assert episode.episode_id == "ep_001"
        assert episode.task_id == "task_001"
        assert episode.max_steps == 10
        assert episode.status == EpisodeStatus.PENDING
        assert len(episode.steps) == 0

    def test_episode_start(self) -> None:
        """Test starting an episode."""
        episode = Episode(episode_id="ep_002", task_id="task_002")
        episode.start()

        assert episode.status == EpisodeStatus.RUNNING
        assert episode.started_at is not None

    def test_episode_add_step(self) -> None:
        """Test adding a step to episode."""
        episode = Episode(episode_id="ep_003", task_id="task_003")
        episode.start()

        step = episode.add_step(
            action_type="navigate",
            action_params={"target": "/login"},
            reward=0.5,
            reward_breakdown={"progress": 0.5},
            observation_summary={"url": "https://example.com"},
        )

        assert len(episode.steps) == 1
        assert episode.steps[0].step_number == 1
        assert episode.total_reward == 0.5

    def test_episode_multiple_steps(self) -> None:
        """Test adding multiple steps."""
        episode = Episode(episode_id="ep_004", task_id="task_004")
        episode.start()

        rewards = [0.1, 0.2, 0.3, 0.4]
        for i, reward in enumerate(rewards):
            episode.add_step(
                action_type="test",
                action_params={"step": i},
                reward=reward,
                reward_breakdown={"base": reward},
                observation_summary={"step": i},
            )

        assert len(episode.steps) == 4
        assert episode.total_reward == pytest.approx(1.0)
        assert episode.current_step == 4

    def test_episode_completion(self) -> None:
        """Test completing an episode."""
        episode = Episode(episode_id="ep_005", task_id="task_005")
        episode.start()
        episode.complete(success=True)

        assert episode.status == EpisodeStatus.COMPLETED
        assert episode.ended_at is not None

    def test_episode_failure(self) -> None:
        """Test failing an episode."""
        episode = Episode(episode_id="ep_006", task_id="task_006")
        episode.start()
        episode.fail(reason="Test failure")

        assert episode.status == EpisodeStatus.FAILED
        assert episode.failure_reason == "Test failure"

    def test_episode_truncation(self) -> None:
        """Test truncating an episode."""
        episode = Episode(episode_id="ep_007", task_id="task_007", max_steps=5)
        episode.start()

        # Add steps up to max
        for i in range(5):
            episode.add_step(
                action_type="test",
                action_params={},
                reward=0.1,
                reward_breakdown={"base": 0.1},
                observation_summary={},
            )

        episode.truncate()
        assert episode.status == EpisodeStatus.TRUNCATED

    def test_episode_is_terminal(self) -> None:
        """Test terminal state check."""
        episode = Episode(episode_id="ep_008", task_id="task_008")

        assert not episode.is_terminal

        episode.start()
        assert not episode.is_terminal

        episode.complete(success=True)
        assert episode.is_terminal

    def test_episode_duration(self) -> None:
        """Test episode duration calculation."""
        episode = Episode(episode_id="ep_009", task_id="task_009")
        episode.start()

        # Duration should be None before completion
        import time

        time.sleep(0.01)  # Small delay
        episode.complete(success=True)

        assert episode.duration_seconds is not None
        assert episode.duration_seconds >= 0

    def test_episode_average_reward(self) -> None:
        """Test average reward calculation."""
        episode = Episode(episode_id="ep_010", task_id="task_010")
        episode.start()

        rewards = [0.2, 0.4, 0.6]
        for i, reward in enumerate(rewards):
            episode.add_step(
                action_type="test",
                action_params={},
                reward=reward,
                reward_breakdown={"base": reward},
                observation_summary={},
            )

        assert episode.average_reward == pytest.approx(0.4)

    def test_episode_summary(self) -> None:
        """Test episode summary."""
        episode = Episode(episode_id="ep_011", task_id="task_011")
        episode.start()

        summary = episode.get_summary()

        assert summary["episode_id"] == "ep_011"
        assert summary["task_id"] == "task_011"
        assert "status" in summary
        assert "steps" in summary

    def test_episode_cancel(self) -> None:
        """Test episode cancellation."""
        episode = Episode(episode_id="ep_012", task_id="task_012")
        episode.start()
        episode.cancel()

        assert episode.status == EpisodeStatus.CANCELLED
        assert episode.is_terminal

    def test_episode_get_action_sequence(self) -> None:
        """Test getting action sequence."""
        episode = Episode(episode_id="ep_013", task_id="task_013")
        episode.start()

        episode.add_step("navigate", {}, 0.1, {}, {})
        episode.add_step("click", {}, 0.2, {}, {})
        episode.add_step("extract", {}, 0.3, {}, {})

        actions = episode.get_action_sequence()
        assert actions == ["navigate", "click", "extract"]

    def test_episode_get_reward_history(self) -> None:
        """Test getting reward history."""
        episode = Episode(episode_id="ep_014", task_id="task_014")
        episode.start()

        episode.add_step("a", {}, 0.1, {}, {})
        episode.add_step("b", {}, 0.2, {}, {})
        episode.add_step("c", {}, 0.3, {}, {})

        rewards = episode.get_reward_history()
        assert rewards == [0.1, 0.2, 0.3]


class TestEpisodeStep:
    """Test EpisodeStep class."""

    def test_step_creation(self) -> None:
        """Test creating an episode step."""
        from datetime import datetime, timezone

        step = EpisodeStep(
            step_number=1,
            timestamp=datetime.now(timezone.utc).isoformat(),
            action_type="click",
            action_params={"selector": "#btn"},
            reward=0.75,
            reward_breakdown={"progress": 0.75},
            observation_summary={"url": "https://example.com", "title": "Test"},
        )

        assert step.step_number == 1
        assert step.action_type == "click"
        assert step.action_params["selector"] == "#btn"
        assert step.reward == 0.75

    def test_step_with_error(self) -> None:
        """Test step with error."""
        from datetime import datetime, timezone

        step = EpisodeStep(
            step_number=1,
            timestamp=datetime.now(timezone.utc).isoformat(),
            action_type="click",
            action_params={},
            reward=-0.5,
            reward_breakdown={"error": -0.5},
            observation_summary={},
            error="Element not found",
            duration_ms=150.0,
        )

        assert step.error == "Element not found"
        assert step.duration_ms == 150.0

    def test_step_with_reasoning(self) -> None:
        """Test step with action reasoning."""
        from datetime import datetime, timezone

        step = EpisodeStep(
            step_number=1,
            timestamp=datetime.now(timezone.utc).isoformat(),
            action_type="extract",
            action_params={"field": "price"},
            action_reasoning="Extracting price from product page",
            reward=0.5,
            reward_breakdown={"extraction": 0.5},
            observation_summary={},
        )

        assert step.action_reasoning == "Extracting price from product page"


class TestEpisodeManager:
    """Test EpisodeManager class."""

    def test_manager_create_episode(self) -> None:
        """Test creating episode via manager."""
        manager = EpisodeManager()
        episode = manager.create_episode("ep_100", "task_100")

        assert episode.episode_id == "ep_100"
        assert episode.task_id == "task_100"

    def test_manager_get_episode(self) -> None:
        """Test getting episode from manager."""
        manager = EpisodeManager()
        manager.create_episode("ep_101", "task_101")

        episode = manager.get_episode("ep_101")
        assert episode is not None
        assert episode.episode_id == "ep_101"

    def test_manager_get_nonexistent(self) -> None:
        """Test getting non-existent episode."""
        manager = EpisodeManager()
        episode = manager.get_episode("nonexistent")
        assert episode is None

    def test_manager_remove_episode(self) -> None:
        """Test removing episode from manager."""
        manager = EpisodeManager()
        manager.create_episode("ep_102", "task_102")

        removed = manager.remove_episode("ep_102")
        assert removed is True

        episode = manager.get_episode("ep_102")
        assert episode is None

    def test_manager_list_episodes(self) -> None:
        """Test listing episodes."""
        manager = EpisodeManager()
        manager.create_episode("ep_103", "task_103")
        manager.create_episode("ep_104", "task_104")
        manager.create_episode("ep_105", "task_105")

        episodes = manager.list_episodes()
        assert len(episodes) == 3

    def test_manager_list_episodes_by_status(self) -> None:
        """Test listing episodes by status."""
        manager = EpisodeManager()

        ep1 = manager.create_episode("ep_106", "task_106")
        ep2 = manager.create_episode("ep_107", "task_107")
        ep3 = manager.create_episode("ep_108", "task_108")

        ep1.start()
        ep2.start()
        ep2.complete(success=True)

        running = manager.list_episodes(status=EpisodeStatus.RUNNING)
        assert len(running) == 1
        assert running[0].episode_id == "ep_106"

        completed = manager.list_episodes(status=EpisodeStatus.COMPLETED)
        assert len(completed) == 1
        assert completed[0].episode_id == "ep_107"

    def test_manager_list_episodes_by_task(self) -> None:
        """Test listing episodes by task ID."""
        manager = EpisodeManager()
        manager.create_episode("ep_109", "task_A")
        manager.create_episode("ep_110", "task_A")
        manager.create_episode("ep_111", "task_B")

        task_a_episodes = manager.list_episodes(task_id="task_A")
        assert len(task_a_episodes) == 2

        task_b_episodes = manager.list_episodes(task_id="task_B")
        assert len(task_b_episodes) == 1

"""Episode state machine and management."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EpisodeStatus(str, Enum):
    """Status of an episode."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TRUNCATED = "truncated"
    CANCELLED = "cancelled"


class EpisodeStep(BaseModel):
    """Record of a single step in the episode."""

    step_number: int
    timestamp: str
    action_type: str
    action_params: dict[str, Any]
    action_reasoning: str | None = None
    reward: float
    reward_breakdown: dict[str, float]
    observation_summary: dict[str, Any]
    error: str | None = None
    duration_ms: float = 0.0


class Episode(BaseModel):
    """
    Represents a complete episode in the RL environment.
    
    An episode is a sequence of steps from reset to termination,
    tracking all actions, rewards, and observations.
    """

    # Identification
    episode_id: str
    task_id: str

    # Timing
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    started_at: str | None = None
    ended_at: str | None = None

    # State
    status: EpisodeStatus = EpisodeStatus.PENDING
    current_step: int = 0
    max_steps: int = 50

    # Seed for reproducibility
    seed: int | None = None

    # Configuration
    config: dict[str, Any] = Field(default_factory=dict)

    # Step history
    steps: list[EpisodeStep] = Field(default_factory=list)

    # Aggregates
    total_reward: float = 0.0
    tokens_used: int = 0
    api_calls: int = 0
    estimated_cost_usd: float = 0.0

    # Results
    extracted_data: dict[str, Any] = Field(default_factory=dict)
    final_accuracy: float | None = None
    success: bool | None = None
    failure_reason: str | None = None

    # Navigation history
    urls_visited: list[str] = Field(default_factory=list)

    def start(self) -> None:
        """Mark the episode as started."""
        self.status = EpisodeStatus.RUNNING
        self.started_at = datetime.now(timezone.utc).isoformat()

    def add_step(
        self,
        action_type: str,
        action_params: dict[str, Any],
        reward: float,
        reward_breakdown: dict[str, float],
        observation_summary: dict[str, Any],
        action_reasoning: str | None = None,
        error: str | None = None,
        duration_ms: float = 0.0,
    ) -> EpisodeStep:
        """Add a step to the episode."""
        self.current_step += 1

        step = EpisodeStep(
            step_number=self.current_step,
            timestamp=datetime.now(timezone.utc).isoformat(),
            action_type=action_type,
            action_params=action_params,
            action_reasoning=action_reasoning,
            reward=reward,
            reward_breakdown=reward_breakdown,
            observation_summary=observation_summary,
            error=error,
            duration_ms=duration_ms,
        )

        self.steps.append(step)
        self.total_reward += reward

        return step

    def complete(
        self,
        success: bool,
        extracted_data: dict[str, Any] | None = None,
        final_accuracy: float | None = None,
    ) -> None:
        """Mark the episode as completed."""
        self.status = EpisodeStatus.COMPLETED
        self.ended_at = datetime.now(timezone.utc).isoformat()
        self.success = success
        if extracted_data:
            self.extracted_data = extracted_data
        self.final_accuracy = final_accuracy

    def fail(self, reason: str) -> None:
        """Mark the episode as failed."""
        self.status = EpisodeStatus.FAILED
        self.ended_at = datetime.now(timezone.utc).isoformat()
        self.success = False
        self.failure_reason = reason

    def truncate(self, reason: str = "max_steps_reached") -> None:
        """Mark the episode as truncated (stopped early)."""
        self.status = EpisodeStatus.TRUNCATED
        self.ended_at = datetime.now(timezone.utc).isoformat()
        self.failure_reason = reason

    def cancel(self) -> None:
        """Mark the episode as cancelled."""
        self.status = EpisodeStatus.CANCELLED
        self.ended_at = datetime.now(timezone.utc).isoformat()

    @property
    def is_terminal(self) -> bool:
        """Check if the episode has terminated."""
        return self.status in [
            EpisodeStatus.COMPLETED,
            EpisodeStatus.FAILED,
            EpisodeStatus.TRUNCATED,
            EpisodeStatus.CANCELLED,
        ]

    @property
    def duration_seconds(self) -> float | None:
        """Get episode duration in seconds."""
        if not self.started_at:
            return None
        end = self.ended_at or datetime.now(timezone.utc).isoformat()
        start_dt = datetime.fromisoformat(self.started_at.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
        return (end_dt - start_dt).total_seconds()

    @property
    def average_reward(self) -> float:
        """Get average reward per step."""
        if not self.steps:
            return 0.0
        return self.total_reward / len(self.steps)

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the episode."""
        return {
            "episode_id": self.episode_id,
            "task_id": self.task_id,
            "status": self.status.value,
            "steps": self.current_step,
            "total_reward": self.total_reward,
            "average_reward": self.average_reward,
            "duration_seconds": self.duration_seconds,
            "tokens_used": self.tokens_used,
            "estimated_cost_usd": self.estimated_cost_usd,
            "success": self.success,
            "fields_extracted": len(self.extracted_data),
        }

    def get_step_history(
        self,
        start: int = 0,
        end: int | None = None,
    ) -> list[EpisodeStep]:
        """Get a slice of the step history."""
        return self.steps[start:end]

    def get_action_sequence(self) -> list[str]:
        """Get the sequence of action types taken."""
        return [step.action_type for step in self.steps]

    def get_reward_history(self) -> list[float]:
        """Get the sequence of rewards received."""
        return [step.reward for step in self.steps]


class EpisodeManager:
    """Manager for episode lifecycle."""

    def __init__(self) -> None:
        """Initialize the episode manager."""
        self._episodes: dict[str, Episode] = {}

    def create_episode(
        self,
        episode_id: str,
        task_id: str,
        max_steps: int = 50,
        seed: int | None = None,
        config: dict[str, Any] | None = None,
    ) -> Episode:
        """Create a new episode."""
        episode = Episode(
            episode_id=episode_id,
            task_id=task_id,
            max_steps=max_steps,
            seed=seed,
            config=config or {},
        )
        self._episodes[episode_id] = episode
        return episode

    def get_episode(self, episode_id: str) -> Episode | None:
        """Get an episode by ID."""
        return self._episodes.get(episode_id)

    def remove_episode(self, episode_id: str) -> bool:
        """Remove an episode."""
        if episode_id in self._episodes:
            del self._episodes[episode_id]
            return True
        return False

    def list_episodes(
        self,
        status: EpisodeStatus | None = None,
        task_id: str | None = None,
    ) -> list[Episode]:
        """List episodes with optional filtering."""
        episodes = list(self._episodes.values())
        if status:
            episodes = [e for e in episodes if e.status == status]
        if task_id:
            episodes = [e for e in episodes if e.task_id == task_id]
        return episodes

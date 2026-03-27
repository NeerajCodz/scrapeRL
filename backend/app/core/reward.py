"""Reward computation engine with component breakdown."""

from dataclasses import dataclass, field
from typing import Any

from app.config import Settings, get_settings
from app.core.action import Action, ActionType
from app.core.observation import Observation


@dataclass
class RewardBreakdown:
    """Detailed breakdown of reward components."""

    # Core components
    accuracy: float = 0.0
    efficiency: float = 0.0
    cost: float = 0.0
    completeness: float = 0.0

    # Bonus/penalty components
    progress_bonus: float = 0.0
    error_penalty: float = 0.0
    time_penalty: float = 0.0
    redundancy_penalty: float = 0.0
    exploration_bonus: float = 0.0
    verification_bonus: float = 0.0

    # Metadata
    total: float = 0.0
    components: dict[str, float] = field(default_factory=dict)

    def compute_total(self, weights: dict[str, float]) -> float:
        """Compute total reward with weights."""
        self.total = (
            self.accuracy * weights.get("accuracy", 0.4)
            + self.efficiency * weights.get("efficiency", 0.2)
            + self.cost * weights.get("cost", 0.2)
            + self.completeness * weights.get("completeness", 0.2)
            + self.progress_bonus
            + self.exploration_bonus
            + self.verification_bonus
            - self.error_penalty
            - self.time_penalty
            - self.redundancy_penalty
        )

        self.components = {
            "accuracy": self.accuracy,
            "efficiency": self.efficiency,
            "cost": self.cost,
            "completeness": self.completeness,
            "progress_bonus": self.progress_bonus,
            "error_penalty": self.error_penalty,
            "time_penalty": self.time_penalty,
            "redundancy_penalty": self.redundancy_penalty,
            "exploration_bonus": self.exploration_bonus,
            "verification_bonus": self.verification_bonus,
        }

        return self.total

    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary."""
        return {
            "total": self.total,
            **self.components,
        }


class RewardEngine:
    """
    Computes rewards for actions in the web scraping environment.
    
    Reward components:
    - Accuracy: How correct extracted data is
    - Efficiency: Steps taken vs optimal
    - Cost: API/compute costs
    - Completeness: Progress towards task completion
    
    Plus bonuses/penalties for:
    - Progress: Making progress towards goal
    - Errors: Failed actions or invalid extractions
    - Time: Taking too long
    - Redundancy: Repeating unsuccessful actions
    - Exploration: Discovering new information
    - Verification: Validating extracted data
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize the reward engine."""
        self.settings = settings or get_settings()
        self.weights = {
            "accuracy": self.settings.reward_accuracy_weight,
            "efficiency": self.settings.reward_efficiency_weight,
            "cost": self.settings.reward_cost_weight,
            "completeness": self.settings.reward_completeness_weight,
        }

        # Tracking for penalties
        self._action_history: list[Action] = []
        self._extraction_attempts: dict[str, int] = {}
        self._url_visits: dict[str, int] = {}

    def reset(self) -> None:
        """Reset tracking state for a new episode."""
        self._action_history.clear()
        self._extraction_attempts.clear()
        self._url_visits.clear()

    def compute_reward(
        self,
        action: Action,
        prev_observation: Observation,
        new_observation: Observation,
        ground_truth: dict[str, Any] | None = None,
        max_steps: int = 50,
    ) -> tuple[float, RewardBreakdown]:
        """
        Compute reward for an action.
        
        Args:
            action: The action that was taken.
            prev_observation: Observation before the action.
            new_observation: Observation after the action.
            ground_truth: Optional ground truth data for accuracy calculation.
            max_steps: Maximum steps allowed in episode.
        
        Returns:
            Tuple of (total_reward, breakdown).
        """
        breakdown = RewardBreakdown()

        # Track action
        self._action_history.append(action)

        # Compute accuracy component
        breakdown.accuracy = self._compute_accuracy(
            action, new_observation, ground_truth
        )

        # Compute efficiency component
        breakdown.efficiency = self._compute_efficiency(
            new_observation.step_number, max_steps
        )

        # Compute cost component
        breakdown.cost = self._compute_cost_reward(new_observation)

        # Compute completeness component
        breakdown.completeness = self._compute_completeness(
            prev_observation, new_observation
        )

        # Compute bonuses
        breakdown.progress_bonus = self._compute_progress_bonus(
            prev_observation, new_observation
        )
        breakdown.exploration_bonus = self._compute_exploration_bonus(
            action, new_observation
        )
        breakdown.verification_bonus = self._compute_verification_bonus(
            action, new_observation
        )

        # Compute penalties
        breakdown.error_penalty = self._compute_error_penalty(new_observation)
        breakdown.time_penalty = self._compute_time_penalty(new_observation, max_steps)
        breakdown.redundancy_penalty = self._compute_redundancy_penalty(action)

        # Compute total
        total = breakdown.compute_total(self.weights)

        return total, breakdown

    def _compute_accuracy(
        self,
        action: Action,
        observation: Observation,
        ground_truth: dict[str, Any] | None,
    ) -> float:
        """Compute accuracy reward component."""
        if ground_truth is None:
            # Without ground truth, use confidence scores
            if observation.extracted_so_far:
                avg_confidence = sum(
                    f.confidence for f in observation.extracted_so_far
                ) / len(observation.extracted_so_far)
                return avg_confidence
            return 0.5  # Neutral

        # With ground truth, compute actual accuracy
        extracted = observation.get_extraction_dict()
        if not extracted:
            return 0.0

        correct = 0
        total = 0
        for field_name, expected_value in ground_truth.items():
            if field_name in extracted:
                total += 1
                actual_value = extracted[field_name]
                if self._values_match(actual_value, expected_value):
                    correct += 1

        if total == 0:
            return 0.0

        return correct / total

    def _values_match(self, actual: Any, expected: Any) -> bool:
        """Check if extracted value matches expected value."""
        if actual == expected:
            return True

        # Fuzzy matching for strings
        if isinstance(actual, str) and isinstance(expected, str):
            actual_clean = actual.strip().lower()
            expected_clean = expected.strip().lower()
            if actual_clean == expected_clean:
                return True
            # Partial match
            if expected_clean in actual_clean or actual_clean in expected_clean:
                return True

        # Numeric comparison with tolerance
        if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
            tolerance = abs(expected) * 0.01 if expected != 0 else 0.01
            return abs(actual - expected) <= tolerance

        return False

    def _compute_efficiency(self, current_step: int, max_steps: int) -> float:
        """Compute efficiency based on steps taken."""
        # Higher reward for completing tasks in fewer steps
        remaining_ratio = (max_steps - current_step) / max_steps
        return max(0.0, remaining_ratio)

    def _compute_cost_reward(self, observation: Observation) -> float:
        """Compute reward based on cost efficiency."""
        # Penalize high token usage and API calls
        max_expected_tokens = 10000
        max_expected_calls = 50

        token_efficiency = 1.0 - min(
            observation.tokens_used / max_expected_tokens, 1.0
        )
        call_efficiency = 1.0 - min(
            observation.api_calls_made / max_expected_calls, 1.0
        )

        return (token_efficiency + call_efficiency) / 2

    def _compute_completeness(
        self,
        prev_observation: Observation,
        new_observation: Observation,
    ) -> float:
        """Compute completeness based on extraction progress."""
        return new_observation.extraction_progress

    def _compute_progress_bonus(
        self,
        prev_observation: Observation,
        new_observation: Observation,
    ) -> float:
        """Bonus for making progress."""
        progress_delta = (
            new_observation.extraction_progress - prev_observation.extraction_progress
        )

        # Bonus for new extractions
        new_extractions = len(new_observation.extracted_so_far) - len(
            prev_observation.extracted_so_far
        )

        bonus = 0.0
        if progress_delta > 0:
            bonus += progress_delta * 0.5
        if new_extractions > 0:
            bonus += new_extractions * 0.1

        return bonus

    def _compute_exploration_bonus(
        self,
        action: Action,
        observation: Observation,
    ) -> float:
        """Bonus for exploring new pages."""
        bonus = 0.0

        if action.action_type == ActionType.NAVIGATE:
            url = action.get_param("url", "")
            if url and url not in self._url_visits:
                bonus += 0.05
            self._url_visits[url] = self._url_visits.get(url, 0) + 1

        return bonus

    def _compute_verification_bonus(
        self,
        action: Action,
        observation: Observation,
    ) -> float:
        """Bonus for verification actions."""
        if action.action_type in [ActionType.VERIFY_FACT, ActionType.VERIFY_FIELD]:
            return 0.05
        return 0.0

    def _compute_error_penalty(self, observation: Observation) -> float:
        """Penalty for errors."""
        if observation.last_action_error:
            base_penalty = 0.1
            consecutive_penalty = observation.consecutive_errors * 0.05
            return base_penalty + consecutive_penalty
        return 0.0

    def _compute_time_penalty(
        self,
        observation: Observation,
        max_steps: int,
    ) -> float:
        """Penalty for taking too long."""
        step_ratio = observation.step_number / max_steps
        if step_ratio > 0.8:
            return (step_ratio - 0.8) * 0.5
        return 0.0

    def _compute_redundancy_penalty(self, action: Action) -> float:
        """Penalty for redundant actions."""
        if len(self._action_history) < 2:
            return 0.0

        # Check for repeated extract attempts on same field
        if action.action_type == ActionType.EXTRACT_FIELD:
            field = action.get_param("field_name", "")
            attempts = self._extraction_attempts.get(field, 0)
            self._extraction_attempts[field] = attempts + 1
            if attempts > 0:
                return min(attempts * 0.05, 0.2)

        # Check for repeated navigation to same URL
        if action.action_type == ActionType.NAVIGATE:
            url = action.get_param("url", "")
            visits = self._url_visits.get(url, 0)
            if visits > 1:
                return min((visits - 1) * 0.03, 0.15)

        return 0.0

    def compute_terminal_reward(
        self,
        observation: Observation,
        success: bool,
        ground_truth: dict[str, Any] | None = None,
    ) -> tuple[float, RewardBreakdown]:
        """
        Compute final reward at episode termination.
        
        Args:
            observation: Final observation.
            success: Whether the task was completed successfully.
            ground_truth: Optional ground truth for accuracy.
        
        Returns:
            Tuple of (total_reward, breakdown).
        """
        breakdown = RewardBreakdown()

        if success:
            # Big bonus for successful completion
            breakdown.completeness = 1.0
            breakdown.progress_bonus = 0.5

            # Compute final accuracy
            if ground_truth:
                extracted = observation.get_extraction_dict()
                correct = sum(
                    1 for k, v in ground_truth.items()
                    if k in extracted and self._values_match(extracted[k], v)
                )
                total = len(ground_truth)
                breakdown.accuracy = correct / total if total > 0 else 1.0
            else:
                breakdown.accuracy = observation.extraction_progress

            # Efficiency bonus for fast completion
            breakdown.efficiency = 1.0 - (
                observation.step_number / self.settings.max_steps_per_episode
            )
        else:
            # Partial credit for progress made
            breakdown.completeness = observation.extraction_progress * 0.5
            breakdown.error_penalty = 0.3

        total = breakdown.compute_total(self.weights)
        return total, breakdown

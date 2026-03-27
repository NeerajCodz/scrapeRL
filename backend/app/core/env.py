"""Web scraper RL environment."""

import logging
import time
from typing import Any

from app.config import Settings, get_settings
from app.core.action import Action, ActionType
from app.core.episode import Episode, EpisodeManager
from app.core.observation import (
    AvailableAction,
    ExtractedField,
    MemoryContext,
    Observation,
    TaskContext,
)
from app.core.reward import RewardBreakdown, RewardEngine

logger = logging.getLogger(__name__)


class WebScraperEnv:
    """
    Reinforcement Learning environment for web scraping.
    
    Follows the Gymnasium API pattern:
    - reset(task_id, seed) -> observation, info
    - step(action) -> observation, reward, terminated, truncated, info
    - get_state() -> state dict
    """

    def __init__(
        self,
        episode_id: str,
        settings: Settings | None = None,
    ) -> None:
        """
        Initialize the environment.
        
        Args:
            episode_id: Unique identifier for this episode.
            settings: Application settings.
        """
        self.episode_id = episode_id
        self.settings = settings or get_settings()
        self.reward_engine = RewardEngine(settings)
        self.episode_manager = EpisodeManager()

        # State
        self._episode: Episode | None = None
        self._current_observation: Observation | None = None
        self._task_context: TaskContext | None = None
        self._ground_truth: dict[str, Any] | None = None

        # Browser state (placeholder - would use Playwright in production)
        self._current_url: str | None = None
        self._page_html: str | None = None
        self._page_title: str | None = None

        # Extraction state
        self._extracted_fields: list[ExtractedField] = []
        self._navigation_history: list[str] = []

        # Timing
        self._start_time: float | None = None

    async def reset(
        self,
        task_id: str,
        seed: int | None = None,
        config: dict[str, Any] | None = None,
    ) -> tuple[Observation, dict[str, Any]]:
        """
        Reset the environment for a new episode.
        
        Args:
            task_id: ID of the task to execute.
            seed: Random seed for reproducibility.
            config: Optional episode configuration.
        
        Returns:
            Tuple of (initial_observation, info_dict).
        """
        logger.info(f"Resetting environment for task {task_id}")

        # Reset state
        self.reward_engine.reset()
        self._extracted_fields = []
        self._navigation_history = []
        self._start_time = time.time()
        self._current_url = None
        self._page_html = None
        self._page_title = None

        # Create episode
        self._episode = self.episode_manager.create_episode(
            episode_id=self.episode_id,
            task_id=task_id,
            max_steps=self.settings.max_steps_per_episode,
            seed=seed,
            config=config or {},
        )
        self._episode.start()

        # Load task context
        self._task_context = await self._load_task_context(task_id)

        # Create initial observation
        self._current_observation = self._create_observation()

        info = {
            "episode_id": self.episode_id,
            "task_id": task_id,
            "max_steps": self._episode.max_steps,
            "target_fields": self._task_context.target_fields if self._task_context else [],
        }

        return self._current_observation, info

    async def step(
        self,
        action: Action,
    ) -> tuple[Observation, float, dict[str, float], bool, bool, dict[str, Any]]:
        """
        Execute an action and return the result.
        
        Args:
            action: The action to execute.
        
        Returns:
            Tuple of (observation, reward, reward_breakdown, terminated, truncated, info).
        """
        if self._episode is None or self._current_observation is None:
            raise RuntimeError("Environment not reset. Call reset() first.")

        if self._episode.is_terminal:
            raise RuntimeError("Episode has already terminated.")

        step_start = time.time()
        prev_observation = self._current_observation

        # Validate action
        errors = action.validate_params()
        if errors:
            logger.warning(f"Invalid action parameters: {errors}")

        # Execute action
        action_result = await self._execute_action(action)

        # Update observation
        self._current_observation = self._create_observation()
        if action_result.get("error"):
            self._current_observation.last_action_error = action_result["error"]
            self._current_observation.consecutive_errors = (
                prev_observation.consecutive_errors + 1
            )
        else:
            self._current_observation.consecutive_errors = 0

        # Compute reward
        reward, breakdown = self.reward_engine.compute_reward(
            action=action,
            prev_observation=prev_observation,
            new_observation=self._current_observation,
            ground_truth=self._ground_truth,
            max_steps=self._episode.max_steps,
        )

        # Check termination
        terminated = self._check_terminated(action)
        truncated = self._check_truncated()

        # Update episode
        step_duration = (time.time() - step_start) * 1000
        self._episode.add_step(
            action_type=action.action_type.value,
            action_params=action.parameters,
            action_reasoning=action.reasoning,
            reward=reward,
            reward_breakdown=breakdown.to_dict(),
            observation_summary={
                "url": self._current_observation.current_url,
                "progress": self._current_observation.extraction_progress,
                "fields_extracted": len(self._current_observation.extracted_so_far),
            },
            error=action_result.get("error"),
            duration_ms=step_duration,
        )

        # Handle terminal states
        if terminated:
            success = action.action_type == ActionType.DONE and action.get_param(
                "success", True
            )
            self._episode.complete(
                success=success,
                extracted_data=self._current_observation.get_extraction_dict(),
            )

            # Add terminal reward
            terminal_reward, terminal_breakdown = (
                self.reward_engine.compute_terminal_reward(
                    self._current_observation,
                    success=success,
                    ground_truth=self._ground_truth,
                )
            )
            reward += terminal_reward
            breakdown.total += terminal_reward
        elif truncated:
            self._episode.truncate()

        info = {
            "action_result": action_result,
            "step_duration_ms": step_duration,
            "episode_step": self._episode.current_step,
        }

        return (
            self._current_observation,
            reward,
            breakdown.to_dict(),
            terminated,
            truncated,
            info,
        )

    def get_state(self) -> dict[str, Any]:
        """Get the current state of the environment."""
        if self._episode is None:
            return {
                "episode_id": self.episode_id,
                "status": "not_started",
            }

        return {
            "episode_id": self.episode_id,
            "task_id": self._episode.task_id,
            "step_number": self._episode.current_step,
            "current_url": self._current_url,
            "is_terminal": self._episode.is_terminal,
            "total_reward": self._episode.total_reward,
            "extracted_data": (
                self._current_observation.get_extraction_dict()
                if self._current_observation
                else {}
            ),
            "status": self._episode.status.value,
        }

    async def _load_task_context(self, task_id: str) -> TaskContext:
        """Load task context from task repository."""
        # In production, this would fetch from database
        from app.api.routes.tasks import TASK_REPOSITORY

        task = TASK_REPOSITORY.get(task_id)
        if task:
            return TaskContext(
                task_id=task.id,
                task_name=task.name,
                task_type=task.task_type.value,
                target_fields=[f.name for f in task.fields_to_extract],
                required_fields=task.success_criteria.get("required_fields", []),
                hints=task.hints,
                success_criteria=task.success_criteria,
            )

        # Default context
        return TaskContext(
            task_id=task_id,
            task_name=f"Task {task_id}",
            task_type="unknown",
            target_fields=[],
            required_fields=[],
        )

    def _create_observation(self) -> Observation:
        """Create an observation from current state."""
        if self._episode is None:
            raise RuntimeError("Episode not initialized")

        elapsed = time.time() - (self._start_time or time.time())

        # Get available actions
        available_actions = self._get_available_actions()

        # Calculate progress
        target_fields = (
            self._task_context.target_fields if self._task_context else []
        )
        extracted_names = {f.field_name for f in self._extracted_fields}
        fields_remaining = [f for f in target_fields if f not in extracted_names]
        progress = (
            len(self._extracted_fields) / len(target_fields)
            if target_fields
            else 0.0
        )

        return Observation(
            episode_id=self.episode_id,
            task_id=self._episode.task_id,
            step_number=self._episode.current_step,
            elapsed_seconds=elapsed,
            current_url=self._current_url,
            page_title=self._page_title,
            page_html=self._page_html,
            navigation_history=self._navigation_history.copy(),
            can_go_back=len(self._navigation_history) > 1,
            task_context=self._task_context,
            extracted_so_far=self._extracted_fields.copy(),
            extraction_progress=progress,
            fields_remaining=fields_remaining,
            memory_context=MemoryContext(),
            available_actions=available_actions,
            tokens_used=self._episode.tokens_used,
            api_calls_made=self._episode.api_calls,
        )

    def _get_available_actions(self) -> list[AvailableAction]:
        """Get list of currently available actions."""
        actions = []

        # Navigation actions
        actions.append(
            AvailableAction(
                action_type="navigate",
                description="Navigate to a URL",
                parameters={"url": "required"},
            )
        )

        if self._current_url:
            # Page interaction actions
            actions.extend([
                AvailableAction(
                    action_type="click",
                    description="Click on an element",
                    parameters={"selector": "required"},
                ),
                AvailableAction(
                    action_type="extract_field",
                    description="Extract a field from the page",
                    parameters={"field_name": "required", "selector": "optional"},
                ),
                AvailableAction(
                    action_type="search_page",
                    description="Search within the current page",
                    parameters={"query": "required"},
                ),
            ])

        # Always available
        actions.extend([
            AvailableAction(
                action_type="search_engine",
                description="Perform a web search",
                parameters={"query": "required", "engine": "optional"},
            ),
            AvailableAction(
                action_type="done",
                description="Mark task as complete",
                parameters={"success": "boolean"},
            ),
        ])

        return actions

    async def _execute_action(self, action: Action) -> dict[str, Any]:
        """Execute an action and return the result."""
        result: dict[str, Any] = {"success": False}

        try:
            match action.action_type:
                case ActionType.NAVIGATE:
                    result = await self._execute_navigate(action)
                case ActionType.CLICK:
                    result = await self._execute_click(action)
                case ActionType.FILL:
                    result = await self._execute_fill(action)
                case ActionType.EXTRACT_FIELD:
                    result = await self._execute_extract(action)
                case ActionType.SEARCH_ENGINE:
                    result = await self._execute_search_engine(action)
                case ActionType.DONE:
                    result = {"success": True, "done": True}
                case ActionType.WAIT:
                    await self._execute_wait(action)
                    result = {"success": True}
                case _:
                    result = {
                        "success": False,
                        "error": f"Action type {action.action_type} not implemented",
                    }
        except Exception as e:
            logger.error(f"Action execution failed: {e}")
            result = {"success": False, "error": str(e)}

        return result

    async def _execute_navigate(self, action: Action) -> dict[str, Any]:
        """Execute a navigate action."""
        url = action.get_param("url")
        if not url:
            return {"success": False, "error": "URL is required"}

        # Placeholder - in production would use Playwright
        self._current_url = url
        self._navigation_history.append(url)
        self._page_title = f"Page at {url}"
        self._page_html = f"<html><body><h1>Mock page for {url}</h1></body></html>"

        return {"success": True, "url": url}

    async def _execute_click(self, action: Action) -> dict[str, Any]:
        """Execute a click action."""
        selector = action.get_param("selector")
        if not selector:
            return {"success": False, "error": "Selector is required"}

        # Placeholder
        return {"success": True, "selector": selector, "clicked": True}

    async def _execute_fill(self, action: Action) -> dict[str, Any]:
        """Execute a fill action."""
        selector = action.get_param("selector")
        value = action.get_param("value")

        if not selector or value is None:
            return {"success": False, "error": "Selector and value are required"}

        # Placeholder
        return {"success": True, "selector": selector, "filled": True}

    async def _execute_extract(self, action: Action) -> dict[str, Any]:
        """Execute an extract action."""
        field_name = action.get_param("field_name")
        if not field_name:
            return {"success": False, "error": "field_name is required"}

        # Placeholder - in production would actually extract from page
        extracted_field = ExtractedField(
            field_name=field_name,
            value=f"mock_value_for_{field_name}",
            confidence=0.9,
            source_selector=action.get_param("selector"),
            extraction_step=self._episode.current_step if self._episode else 0,
        )

        self._extracted_fields.append(extracted_field)

        return {
            "success": True,
            "field_name": field_name,
            "value": extracted_field.value,
            "confidence": extracted_field.confidence,
        }

    async def _execute_search_engine(self, action: Action) -> dict[str, Any]:
        """Execute a search engine action."""
        query = action.get_param("query")
        if not query:
            return {"success": False, "error": "Query is required"}

        engine = action.get_param("engine", "google")

        # Placeholder
        return {
            "success": True,
            "query": query,
            "engine": engine,
            "results": [
                {"title": f"Result 1 for {query}", "url": "https://example.com/1"},
                {"title": f"Result 2 for {query}", "url": "https://example.com/2"},
            ],
        }

    async def _execute_wait(self, action: Action) -> None:
        """Execute a wait action."""
        import asyncio
        duration_ms = action.get_param("duration_ms", 1000)
        await asyncio.sleep(duration_ms / 1000)

    def _check_terminated(self, action: Action) -> bool:
        """Check if the episode should terminate."""
        if action.action_type == ActionType.DONE:
            return True
        if action.action_type == ActionType.FAIL:
            return True
        return False

    def _check_truncated(self) -> bool:
        """Check if the episode should be truncated."""
        if self._episode is None:
            return False
        if self._episode.current_step >= self._episode.max_steps:
            return True
        return False

"""Planner agent for goal decomposition and task planning."""

from typing import Any

from app.core.action import Action, ActionType
from app.core.observation import Observation

from .base import BaseAgent


class PlannerAgent(BaseAgent):
    """
    Agent responsible for high-level planning and goal decomposition.
    
    The PlannerAgent analyzes the task requirements and creates
    structured plans that other agents can execute. It handles:
    - Breaking down complex tasks into subtasks
    - Determining the optimal sequence of actions
    - Adapting plans based on execution results
    - Coordinating multi-step extraction workflows
    """

    def __init__(
        self,
        agent_id: str = "planner",
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize the PlannerAgent.
        
        Args:
            agent_id: Unique identifier for this agent.
            config: Optional configuration with keys:
                - max_plan_depth: Maximum depth of nested plans (default: 5)
                - replan_threshold: Error count before replanning (default: 2)
                - planning_model: LLM model to use for planning
        """
        super().__init__(agent_id, config)
        self.max_plan_depth = self.config.get("max_plan_depth", 5)
        self.replan_threshold = self.config.get("replan_threshold", 2)
        self._current_plan: list[Action] | None = None
        self._plan_step: int = 0

    async def act(self, observation: Observation) -> Action:
        """
        Select the next action based on the current plan or create a new one.
        
        If no plan exists or the current plan has failed, creates a new plan.
        Otherwise, returns the next action in the current plan.
        
        Args:
            observation: The current state observation.
            
        Returns:
            The next action to execute.
        """
        try:
            # Check if we need to replan due to errors
            if observation.consecutive_errors >= self.replan_threshold:
                self._current_plan = None
                self._plan_step = 0

            # Create plan if none exists
            if self._current_plan is None or self._plan_step >= len(self._current_plan):
                self._current_plan = await self.plan(observation)
                self._plan_step = 0

            if not self._current_plan:
                return self._create_done_action("No actions planned")

            # Get next action from plan
            action = self._current_plan[self._plan_step]
            action.plan_step = self._plan_step
            action.agent_id = self.agent_id
            self._plan_step += 1

            return action

        except Exception as e:
            return self._create_error_action(f"Planning error: {e}")

    async def plan(self, observation: Observation) -> list[Action]:
        """
        Create a plan of actions to achieve the task goals.
        
        Analyzes the observation to determine:
        - What fields still need to be extracted
        - What navigation may be required
        - What verification steps are needed
        
        Args:
            observation: The current state observation.
            
        Returns:
            A list of planned actions in execution order.
        """
        try:
            actions: list[Action] = []
            task_context = observation.task_context

            if not task_context:
                return [self._create_done_action("No task context provided")]

            # Determine remaining fields to extract
            remaining_fields = observation.fields_remaining
            extracted_fields = [f.field_name for f in observation.extracted_so_far]

            # If no URL loaded, plan navigation first
            if not observation.current_url:
                search_action = self._plan_initial_navigation(task_context)
                if search_action:
                    actions.append(search_action)

            # Plan extraction for remaining fields
            for field in remaining_fields:
                extraction_action = self._plan_field_extraction(
                    field,
                    observation,
                )
                actions.append(extraction_action)

            # Plan verification if fields have been extracted
            if extracted_fields:
                verify_action = self._plan_verification(extracted_fields)
                actions.append(verify_action)

            # Add completion action
            actions.append(
                Action(
                    action_type=ActionType.DONE,
                    parameters={"success": True, "message": "Plan completed"},
                    reasoning="All planned steps completed",
                    confidence=0.9,
                    agent_id=self.agent_id,
                )
            )

            return actions

        except Exception as e:
            return [self._create_error_action(f"Plan creation failed: {e}")]

    def _plan_initial_navigation(self, task_context: Any) -> Action | None:
        """Plan initial navigation based on task context."""
        if task_context.hints:
            # Use hints for navigation
            for hint in task_context.hints:
                if hint.startswith("http"):
                    return Action(
                        action_type=ActionType.NAVIGATE,
                        parameters={"url": hint},
                        reasoning=f"Navigating to hinted URL: {hint}",
                        confidence=0.85,
                        agent_id=self.agent_id,
                    )

        # Default to search
        search_query = f"{task_context.task_name} site information"
        return Action(
            action_type=ActionType.SEARCH_ENGINE,
            parameters={"query": search_query, "engine": "google"},
            reasoning=f"Searching for: {search_query}",
            confidence=0.7,
            agent_id=self.agent_id,
        )

    def _plan_field_extraction(
        self,
        field_name: str,
        observation: Observation,
    ) -> Action:
        """Plan extraction for a specific field."""
        # Check if we have page elements that might contain the field
        selector = None
        confidence = 0.6

        for element in observation.page_elements:
            element_text = (element.text or "").lower()
            if field_name.lower() in element_text:
                selector = element.selector
                confidence = 0.8
                break

        return Action(
            action_type=ActionType.EXTRACT_FIELD,
            parameters={
                "field_name": field_name,
                "selector": selector,
                "extraction_method": "text",
            },
            reasoning=f"Extracting field: {field_name}",
            confidence=confidence,
            agent_id=self.agent_id,
        )

    def _plan_verification(self, fields: list[str]) -> Action:
        """Plan verification for extracted fields."""
        return Action(
            action_type=ActionType.VERIFY_FIELD,
            parameters={
                "field_name": fields[0] if fields else "unknown",
                "validation_rules": ["not_empty", "format_check"],
            },
            reasoning=f"Verifying extracted fields: {fields}",
            confidence=0.75,
            agent_id=self.agent_id,
        )

    def _create_done_action(self, message: str) -> Action:
        """Create a done action."""
        return Action(
            action_type=ActionType.DONE,
            parameters={"success": True, "message": message},
            reasoning=message,
            confidence=1.0,
            agent_id=self.agent_id,
        )

    def _create_error_action(self, error: str) -> Action:
        """Create a fail action for errors."""
        return Action(
            action_type=ActionType.FAIL,
            parameters={"success": False, "message": error},
            reasoning=error,
            confidence=1.0,
            agent_id=self.agent_id,
        )

    def get_current_plan(self) -> list[Action] | None:
        """Get the current plan."""
        return self._current_plan

    def get_plan_progress(self) -> tuple[int, int]:
        """Get current plan progress as (current_step, total_steps)."""
        total = len(self._current_plan) if self._current_plan else 0
        return (self._plan_step, total)

    def reset(self) -> None:
        """Reset the planner state."""
        super().reset()
        self._current_plan = None
        self._plan_step = 0

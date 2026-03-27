"""Agent coordinator for orchestrating multiple agents with message passing."""

import asyncio
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.core.action import Action, ActionType
from app.core.observation import Observation

from .base import BaseAgent
from .extractor import ExtractorAgent
from .memory_agent import MemoryAgent
from .navigator import NavigatorAgent
from .planner import PlannerAgent
from .verifier import VerifierAgent


class AgentRole(str, Enum):
    """Roles that agents can fulfill."""

    PLANNER = "planner"
    NAVIGATOR = "navigator"
    EXTRACTOR = "extractor"
    VERIFIER = "verifier"
    MEMORY = "memory"


class Message:
    """A message between agents."""

    def __init__(
        self,
        sender: str,
        recipient: str,
        message_type: str,
        content: dict[str, Any],
        priority: int = 0,
    ):
        """Initialize a message."""
        self.sender = sender
        self.recipient = recipient
        self.message_type = message_type
        self.content = content
        self.priority = priority
        self.timestamp = datetime.now(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "sender": self.sender,
            "recipient": self.recipient,
            "message_type": self.message_type,
            "content": self.content,
            "priority": self.priority,
            "timestamp": self.timestamp.isoformat(),
        }


class AgentCoordinator:
    """
    Orchestrator for multiple specialized agents.
    
    The AgentCoordinator manages:
    - Agent lifecycle and initialization
    - Message passing between agents
    - Action selection and routing
    - Coordination of multi-agent workflows
    - Error handling and recovery
    """

    def __init__(
        self,
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize the AgentCoordinator.
        
        Args:
            config: Optional configuration with keys:
                - enable_parallel: Allow parallel agent execution (default: False)
                - max_messages_per_step: Max messages per step (default: 10)
                - default_timeout: Default timeout for agent actions (default: 30)
        """
        self.config = config or {}
        self.enable_parallel = self.config.get("enable_parallel", False)
        self.max_messages_per_step = self.config.get("max_messages_per_step", 10)
        self.default_timeout = self.config.get("default_timeout", 30)

        # Initialize agents
        self._agents: dict[str, BaseAgent] = {}
        self._message_queue: list[Message] = []
        self._action_history: list[tuple[str, Action]] = []
        self._current_lead: str | None = None

        # Initialize default agents
        self._initialize_default_agents()

    def _initialize_default_agents(self) -> None:
        """Initialize the default set of agents."""
        self._agents = {
            AgentRole.PLANNER: PlannerAgent(
                agent_id="planner",
                config=self.config.get("planner_config"),
            ),
            AgentRole.NAVIGATOR: NavigatorAgent(
                agent_id="navigator",
                config=self.config.get("navigator_config"),
            ),
            AgentRole.EXTRACTOR: ExtractorAgent(
                agent_id="extractor",
                config=self.config.get("extractor_config"),
            ),
            AgentRole.VERIFIER: VerifierAgent(
                agent_id="verifier",
                config=self.config.get("verifier_config"),
            ),
            AgentRole.MEMORY: MemoryAgent(
                agent_id="memory",
                config=self.config.get("memory_config"),
            ),
        }

    def register_agent(self, role: str, agent: BaseAgent) -> None:
        """
        Register an agent for a specific role.
        
        Args:
            role: The role this agent fulfills.
            agent: The agent instance.
        """
        self._agents[role] = agent

    def get_agent(self, role: str) -> BaseAgent | None:
        """
        Get an agent by role.
        
        Args:
            role: The role to look up.
            
        Returns:
            The agent if found, None otherwise.
        """
        return self._agents.get(role)

    async def step(self, observation: Observation) -> Action:
        """
        Perform one coordination step.
        
        Determines which agent should act, processes messages,
        and returns the selected action.
        
        Args:
            observation: The current state observation.
            
        Returns:
            The action to execute.
        """
        try:
            # Process pending messages
            await self._process_messages()

            # Determine lead agent based on state
            lead_role = self._determine_lead_agent(observation)
            self._current_lead = lead_role

            # Get action from lead agent
            lead_agent = self._agents.get(lead_role)
            if not lead_agent:
                return self._create_error_action(f"No agent for role: {lead_role}")

            # Get action from the lead agent
            action = await lead_agent.act(observation)
            action.agent_id = lead_agent.agent_id

            # Record action
            self._action_history.append((lead_role, action))
            lead_agent.record_action(action)

            # Handle inter-agent communication actions
            if action.action_type == ActionType.SEND_MESSAGE:
                self._handle_send_message(action)

            return action

        except Exception as e:
            return self._create_error_action(f"Coordination error: {e}")

    async def plan(self, observation: Observation) -> list[Action]:
        """
        Create a coordinated plan using multiple agents.
        
        The planner agent creates the high-level plan, which is then
        refined by other agents.
        
        Args:
            observation: The current state observation.
            
        Returns:
            A coordinated list of actions.
        """
        try:
            # Get plan from planner
            planner = self._agents.get(AgentRole.PLANNER)
            if not planner:
                return []

            plan = await planner.plan(observation)

            # Refine with navigator for navigation steps
            navigator = self._agents.get(AgentRole.NAVIGATOR)
            if navigator:
                nav_plan = await navigator.plan(observation)
                # Insert navigation at the beginning if needed
                if nav_plan and not observation.current_url:
                    plan = nav_plan + plan

            return plan

        except Exception as e:
            return [self._create_error_action(f"Planning error: {e}")]

    def send_message(
        self,
        sender: str,
        recipient: str,
        message_type: str,
        content: dict[str, Any],
        priority: int = 0,
    ) -> None:
        """
        Send a message between agents.
        
        Args:
            sender: ID of the sending agent.
            recipient: ID of the receiving agent.
            message_type: Type of the message.
            content: Message content.
            priority: Message priority (higher = more urgent).
        """
        message = Message(
            sender=sender,
            recipient=recipient,
            message_type=message_type,
            content=content,
            priority=priority,
        )
        self._message_queue.append(message)

    async def _process_messages(self) -> None:
        """Process queued messages and deliver to agents."""
        # Sort by priority (highest first)
        self._message_queue.sort(key=lambda m: -m.priority)

        # Process up to max messages
        messages_processed = 0
        while self._message_queue and messages_processed < self.max_messages_per_step:
            message = self._message_queue.pop(0)

            # Find recipient agent
            recipient = None
            for role, agent in self._agents.items():
                if agent.agent_id == message.recipient or role == message.recipient:
                    recipient = agent
                    break

            if recipient:
                recipient.receive_message(message.to_dict())
                messages_processed += 1

    def _determine_lead_agent(self, observation: Observation) -> str:
        """
        Determine which agent should lead based on state.
        
        Args:
            observation: Current observation.
            
        Returns:
            The role of the agent that should lead.
        """
        # If no URL, navigator should lead
        if not observation.current_url:
            return AgentRole.NAVIGATOR

        # If there are unverified fields, verifier should lead
        unverified = [f for f in observation.extracted_so_far if not f.verified]
        if unverified and observation.extraction_progress > 0.5:
            return AgentRole.VERIFIER

        # If there are remaining fields to extract, extractor should lead
        if observation.fields_remaining:
            return AgentRole.EXTRACTOR

        # If we have errors, planner should re-plan
        if observation.consecutive_errors > 0:
            return AgentRole.PLANNER

        # Default to planner
        return AgentRole.PLANNER

    def _handle_send_message(self, action: Action) -> None:
        """Handle a send_message action from an agent."""
        params = action.parameters
        self.send_message(
            sender=action.agent_id or "unknown",
            recipient=params.get("target_agent", ""),
            message_type=params.get("message_type", "generic"),
            content=params.get("content", {}),
        )

    def _create_error_action(self, error: str) -> Action:
        """Create a fail action for errors."""
        return Action(
            action_type=ActionType.FAIL,
            parameters={"success": False, "message": error},
            reasoning=error,
            confidence=1.0,
            agent_id="coordinator",
        )

    async def run_parallel_agents(
        self,
        observation: Observation,
        roles: list[str],
    ) -> dict[str, Action]:
        """
        Run multiple agents in parallel.
        
        Args:
            observation: Current observation.
            roles: List of agent roles to run.
            
        Returns:
            Dictionary mapping role to action.
        """
        if not self.enable_parallel:
            # Fallback to sequential
            results = {}
            for role in roles:
                agent = self._agents.get(role)
                if agent:
                    results[role] = await agent.act(observation)
            return results

        # Run agents in parallel
        async def run_agent(role: str) -> tuple[str, Action]:
            agent = self._agents.get(role)
            if agent:
                action = await agent.act(observation)
                return (role, action)
            return (role, self._create_error_action(f"No agent for role: {role}"))

        tasks = [run_agent(role) for role in roles]
        results = await asyncio.gather(*tasks)

        return dict(results)

    def get_action_history(self) -> list[tuple[str, Action]]:
        """Get the history of actions with their agent roles."""
        return self._action_history.copy()

    def get_current_lead(self) -> str | None:
        """Get the current lead agent role."""
        return self._current_lead

    def get_message_queue_length(self) -> int:
        """Get the number of pending messages."""
        return len(self._message_queue)

    def reset(self) -> None:
        """Reset all agents and coordinator state."""
        for agent in self._agents.values():
            agent.reset()

        self._message_queue.clear()
        self._action_history.clear()
        self._current_lead = None

    def get_stats(self) -> dict[str, Any]:
        """Get coordinator statistics."""
        return {
            "agents": list(self._agents.keys()),
            "current_lead": self._current_lead,
            "pending_messages": len(self._message_queue),
            "action_count": len(self._action_history),
            "enable_parallel": self.enable_parallel,
        }

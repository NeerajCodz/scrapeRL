"""Base agent abstract class for ScrapeRL agents."""

from abc import ABC, abstractmethod
from typing import Any

from app.core.action import Action
from app.core.observation import Observation


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the ScrapeRL system.
    
    Each agent specializes in a specific aspect of the scraping workflow:
    - Planning and goal decomposition
    - Navigation and URL prioritization
    - Data extraction
    - Verification and validation
    - Memory operations
    
    Agents communicate through message passing and coordinate via
    the AgentCoordinator.
    """

    def __init__(self, agent_id: str, config: dict[str, Any] | None = None):
        """
        Initialize the agent.
        
        Args:
            agent_id: Unique identifier for this agent instance.
            config: Optional configuration dictionary for the agent.
        """
        self.agent_id = agent_id
        self.config = config or {}
        self._message_queue: list[dict[str, Any]] = []
        self._action_history: list[Action] = []

    @abstractmethod
    async def act(self, observation: Observation) -> Action:
        """
        Select an action based on the current observation.
        
        This is the main decision-making method. The agent analyzes
        the observation and returns the best action to take.
        
        Args:
            observation: The current state observation from the environment.
            
        Returns:
            The action to execute.
        """
        pass

    @abstractmethod
    async def plan(self, observation: Observation) -> list[Action]:
        """
        Create a plan of actions based on the current observation.
        
        Unlike act() which returns a single action, plan() creates
        a sequence of actions to achieve a goal.
        
        Args:
            observation: The current state observation from the environment.
            
        Returns:
            A list of planned actions in execution order.
        """
        pass

    async def explain(self, action: Action) -> str:
        """
        Explain why this action was chosen.
        
        Args:
            action: The action to explain.
            
        Returns:
            A human-readable explanation of the action choice.
        """
        return action.reasoning or "No explanation provided"

    def receive_message(self, message: dict[str, Any]) -> None:
        """
        Receive a message from another agent.
        
        Args:
            message: The message dictionary containing sender, type, and content.
        """
        self._message_queue.append(message)

    def get_pending_messages(self) -> list[dict[str, Any]]:
        """
        Get all pending messages and clear the queue.
        
        Returns:
            List of pending messages.
        """
        messages = self._message_queue.copy()
        self._message_queue.clear()
        return messages

    def record_action(self, action: Action) -> None:
        """
        Record an action in the agent's history.
        
        Args:
            action: The action that was executed.
        """
        self._action_history.append(action)

    def get_action_history(self) -> list[Action]:
        """
        Get the history of actions taken by this agent.
        
        Returns:
            List of past actions.
        """
        return self._action_history.copy()

    def reset(self) -> None:
        """Reset the agent state for a new episode."""
        self._message_queue.clear()
        self._action_history.clear()

    def __repr__(self) -> str:
        """String representation of the agent."""
        return f"{self.__class__.__name__}(agent_id={self.agent_id!r})"

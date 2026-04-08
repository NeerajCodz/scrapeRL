"""
Agents module for ScrapeRL.

This module contains specialized agents for web scraping with RL:
- BaseAgent: Abstract base class for all agents
- PlannerAgent: Goal decomposition and task planning
- NavigatorAgent: URL prioritization and page navigation
- ExtractorAgent: Data extraction with selectors
- VerifierAgent: Cross-source verification
- MemoryAgent: Memory operations and knowledge management
- AgentCoordinator: Orchestrates multiple agents with message passing
- AgentToolCaller: LLM-driven tool selection and execution
"""

from .base import BaseAgent
from .coordinator import AgentCoordinator, AgentRole, Message
from .extractor import ExtractorAgent
from .memory_agent import MemoryAgent, MemoryEntry
from .navigator import NavigatorAgent
from .planner import PlannerAgent
from .verifier import VerificationResult, VerifierAgent
from .tool_caller import AgentToolCaller, ToolExecutor, ToolCall, ToolCallResult

__all__ = [
    # Base
    "BaseAgent",
    # Agents
    "PlannerAgent",
    "NavigatorAgent",
    "ExtractorAgent",
    "VerifierAgent",
    "MemoryAgent",
    "AgentToolCaller",
    # Coordinator
    "AgentCoordinator",
    "AgentRole",
    "Message",
    # Tool calling
    "ToolExecutor",
    "ToolCall",
    "ToolCallResult",
    # Data classes
    "VerificationResult",
    "MemoryEntry",
]

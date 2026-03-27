"""Agent management endpoints."""

import logging
from enum import Enum
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

router = APIRouter(prefix="/agents")
logger = logging.getLogger(__name__)


class AgentType(str, Enum):
    """Types of agents in the system."""

    PLANNER = "planner"
    NAVIGATOR = "navigator"
    EXTRACTOR = "extractor"
    VERIFIER = "verifier"
    MEMORY = "memory"
    COORDINATOR = "coordinator"


class AgentStatus(str, Enum):
    """Agent execution status."""

    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentRunRequest(BaseModel):
    """Request to run an agent."""

    agent_type: AgentType
    episode_id: str
    task_context: dict[str, Any] = Field(default_factory=dict)
    observation: dict[str, Any] | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class AgentRunResponse(BaseModel):
    """Response from agent execution."""

    run_id: str
    agent_type: AgentType
    status: AgentStatus
    action: dict[str, Any] | None = None
    reasoning: str | None = None
    confidence: float | None = None
    tokens_used: int = 0
    execution_time_ms: float = 0.0


class PlanRequest(BaseModel):
    """Request for creating a plan."""

    episode_id: str
    task_description: str
    current_state: dict[str, Any] = Field(default_factory=dict)
    constraints: list[str] = Field(default_factory=list)


class PlanStep(BaseModel):
    """A single step in a plan."""

    step_number: int
    action_type: str
    description: str
    agent: AgentType
    dependencies: list[int] = Field(default_factory=list)
    estimated_cost: float = 0.0


class PlanResponse(BaseModel):
    """Response containing a generated plan."""

    plan_id: str
    episode_id: str
    steps: list[PlanStep]
    total_estimated_steps: int
    reasoning: str
    confidence: float


class AgentState(BaseModel):
    """Current state of an agent."""

    agent_id: str
    agent_type: AgentType
    status: AgentStatus
    current_task: str | None = None
    messages_processed: int = 0
    actions_taken: int = 0
    last_action: dict[str, Any] | None = None
    memory_snapshot: dict[str, Any] = Field(default_factory=dict)


# Store for agent states
_agent_states: dict[str, AgentState] = {}


@router.post(
    "/run",
    response_model=AgentRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Run an agent",
    description="Execute an agent to produce an action",
)
async def run_agent(request: AgentRunRequest) -> AgentRunResponse:
    """
    Run an agent to produce an action for the current observation.
    
    Args:
        request: Agent run configuration.
    
    Returns:
        AgentRunResponse: Result of agent execution.
    """
    run_id = str(uuid4())
    logger.info(f"Running {request.agent_type} agent for episode {request.episode_id}")

    try:
        # Import and instantiate the appropriate agent
        from app.agents.coordinator import AgentCoordinator

        coordinator = AgentCoordinator()
        result = await coordinator.run_agent(
            agent_type=request.agent_type,
            episode_id=request.episode_id,
            observation=request.observation,
            config=request.config,
        )

        return AgentRunResponse(
            run_id=run_id,
            agent_type=request.agent_type,
            status=AgentStatus.COMPLETED,
            action=result.get("action"),
            reasoning=result.get("reasoning"),
            confidence=result.get("confidence"),
            tokens_used=result.get("tokens_used", 0),
            execution_time_ms=result.get("execution_time_ms", 0.0),
        )
    except Exception as e:
        logger.error(f"Agent execution failed: {e}")
        return AgentRunResponse(
            run_id=run_id,
            agent_type=request.agent_type,
            status=AgentStatus.FAILED,
            reasoning=str(e),
        )


@router.post(
    "/plan",
    response_model=PlanResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate a plan",
    description="Use the planner agent to generate an execution plan",
)
async def generate_plan(request: PlanRequest) -> PlanResponse:
    """
    Generate a plan for completing a task.
    
    Args:
        request: Planning request with task details.
    
    Returns:
        PlanResponse: Generated plan with steps.
    """
    plan_id = str(uuid4())
    logger.info(f"Generating plan for episode {request.episode_id}")

    try:
        from app.agents.planner import PlannerAgent

        planner = PlannerAgent()
        plan_result = await planner.create_plan(
            task_description=request.task_description,
            current_state=request.current_state,
            constraints=request.constraints,
        )

        steps = [
            PlanStep(
                step_number=i + 1,
                action_type=step["action_type"],
                description=step["description"],
                agent=AgentType(step["agent"]),
                dependencies=step.get("dependencies", []),
                estimated_cost=step.get("estimated_cost", 0.0),
            )
            for i, step in enumerate(plan_result["steps"])
        ]

        return PlanResponse(
            plan_id=plan_id,
            episode_id=request.episode_id,
            steps=steps,
            total_estimated_steps=len(steps),
            reasoning=plan_result.get("reasoning", ""),
            confidence=plan_result.get("confidence", 0.8),
        )
    except Exception as e:
        logger.error(f"Plan generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate plan: {str(e)}",
        )


@router.get(
    "/state/{agent_id}",
    response_model=AgentState,
    status_code=status.HTTP_200_OK,
    summary="Get agent state",
    description="Get the current state of an agent",
)
async def get_agent_state(agent_id: str) -> AgentState:
    """
    Get the current state of an agent.
    
    Args:
        agent_id: ID of the agent.
    
    Returns:
        AgentState: Current agent state.
    """
    if agent_id not in _agent_states:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found",
        )
    return _agent_states[agent_id]


@router.get(
    "/types/",
    status_code=status.HTTP_200_OK,
    summary="Get agent types",
    description="Get all available agent types",
)
async def get_agent_types() -> dict[str, list[dict[str, str]]]:
    """
    Get available agent types with descriptions.
    
    Returns:
        Dict with agent type information.
    """
    agent_info = [
        {"type": AgentType.PLANNER.value, "description": "Creates execution plans for tasks"},
        {"type": AgentType.NAVIGATOR.value, "description": "Handles page navigation and URL management"},
        {"type": AgentType.EXTRACTOR.value, "description": "Extracts data from web pages"},
        {"type": AgentType.VERIFIER.value, "description": "Validates extracted data"},
        {"type": AgentType.MEMORY.value, "description": "Manages memory operations"},
        {"type": AgentType.COORDINATOR.value, "description": "Orchestrates multi-agent collaboration"},
    ]
    return {"agents": agent_info}


@router.post(
    "/message",
    status_code=status.HTTP_200_OK,
    summary="Send inter-agent message",
    description="Send a message between agents",
)
async def send_agent_message(
    from_agent: str,
    to_agent: str,
    message_type: str,
    content: dict[str, Any],
) -> dict[str, Any]:
    """
    Send a message between agents.
    
    Args:
        from_agent: Source agent ID.
        to_agent: Target agent ID.
        message_type: Type of message.
        content: Message content.
    
    Returns:
        Acknowledgment of message delivery.
    """
    message_id = str(uuid4())
    logger.info(f"Message {message_id}: {from_agent} -> {to_agent} ({message_type})")

    # In production, this would go through a message broker
    return {
        "message_id": message_id,
        "status": "delivered",
        "from": from_agent,
        "to": to_agent,
        "type": message_type,
    }

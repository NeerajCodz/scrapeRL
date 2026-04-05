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


class AgentModule(BaseModel):
    """Installable/browsable agent module definition."""

    id: str
    name: str
    role: str
    description: str
    version: str
    installed: bool
    default: bool
    orchestrator_compatible: bool = True


class AgentModuleAction(BaseModel):
    """Install/uninstall request for an agent module."""

    agent_id: str


# Store for agent states
_agent_states: dict[str, AgentState] = {}

_AGENT_MODULE_CATALOG: list[dict[str, Any]] = [
    {
        "id": "planner-agent",
        "name": "Planner Agent",
        "role": "planner",
        "description": "Creates scrape plans and execution strategy",
        "version": "1.0.0",
        "default": True,
        "orchestrator_compatible": True,
    },
    {
        "id": "navigator-agent",
        "name": "Navigator Agent",
        "role": "navigator",
        "description": "Finds links and chooses crawl paths",
        "version": "1.0.0",
        "default": True,
        "orchestrator_compatible": True,
    },
    {
        "id": "extractor-agent",
        "name": "Extractor Agent",
        "role": "extractor",
        "description": "Extracts structured data from fetched content",
        "version": "1.0.0",
        "default": True,
        "orchestrator_compatible": True,
    },
    {
        "id": "verifier-agent",
        "name": "Verifier Agent",
        "role": "verifier",
        "description": "Validates extracted values and output quality",
        "version": "1.0.0",
        "default": True,
        "orchestrator_compatible": True,
    },
    {
        "id": "memory-agent",
        "name": "Memory Agent",
        "role": "memory",
        "description": "Manages memory writes and retrieval",
        "version": "1.0.0",
        "default": True,
        "orchestrator_compatible": True,
    },
    {
        "id": "coordinator-agent",
        "name": "Coordinator Agent",
        "role": "coordinator",
        "description": "Orchestrates multi-agent execution",
        "version": "1.0.0",
        "default": True,
        "orchestrator_compatible": True,
    },
    {
        "id": "research-agent",
        "name": "Research Agent",
        "role": "research",
        "description": "Focused web search and source discovery",
        "version": "1.0.0",
        "default": False,
        "orchestrator_compatible": True,
    },
    {
        "id": "dataset-agent",
        "name": "Dataset Builder Agent",
        "role": "dataset",
        "description": "Builds/normalizes datasets from scraped files",
        "version": "1.0.0",
        "default": False,
        "orchestrator_compatible": True,
    },
]

_DEFAULT_AGENT_MODULES: set[str] = {
    item["id"] for item in _AGENT_MODULE_CATALOG if item.get("default")
}
_installed_agent_modules: set[str] = set(_DEFAULT_AGENT_MODULES)


@router.get(
    "/list",
    status_code=status.HTTP_200_OK,
    summary="List all agents",
    description="Get list of all available agents and their status",
)
async def list_agents() -> dict[str, Any]:
    """
    List all available agents and their current states.

    Returns:
        Dictionary with agent types and their states.
    """
    agent_types = [
        {
            "type": at.value,
            "name": at.name.title(),
            "description": f"{at.name.title()} agent for web scraping tasks",
        }
        for at in AgentType
    ]

    active_agents = [
        {
            "agent_id": agent_id,
            "type": state.agent_type,
            "status": state.status,
        }
        for agent_id, state in _agent_states.items()
    ]

    return {
        "agent_types": agent_types,
        "active_agents": active_agents,
        "installed_agents": sorted(_installed_agent_modules),
        "total_types": len(AgentType),
        "active_count": len(_agent_states),
    }


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

    steps = [
        PlanStep(
            step_number=1,
            action_type="create_plan",
            description=f"Analyze task goal: {request.task_description}",
            agent=AgentType.PLANNER,
            estimated_cost=0.001,
        ),
        PlanStep(
            step_number=2,
            action_type="navigate",
            description="Navigate to target pages and gather context",
            agent=AgentType.NAVIGATOR,
            dependencies=[1],
            estimated_cost=0.01,
        ),
        PlanStep(
            step_number=3,
            action_type="extract_field",
            description="Extract required fields from observed content",
            agent=AgentType.EXTRACTOR,
            dependencies=[2],
            estimated_cost=0.02,
        ),
        PlanStep(
            step_number=4,
            action_type="verify_field",
            description="Validate extracted fields against constraints",
            agent=AgentType.VERIFIER,
            dependencies=[3],
            estimated_cost=0.005,
        ),
    ]

    if request.constraints:
        steps.append(
            PlanStep(
                step_number=len(steps) + 1,
                action_type="apply_constraints",
                description=f"Apply constraints: {', '.join(request.constraints)}",
                agent=AgentType.PLANNER,
                dependencies=[4],
                estimated_cost=0.001,
            )
        )

    return PlanResponse(
        plan_id=plan_id,
        episode_id=request.episode_id,
        steps=steps,
        total_estimated_steps=len(steps),
        reasoning="Generated a deterministic multi-agent plan for navigation, extraction, and verification.",
        confidence=0.82,
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


@router.get(
    "/catalog",
    status_code=status.HTTP_200_OK,
    summary="Get installable agents catalog",
    description="List all agent modules with install status and orchestrator compatibility",
)
async def get_agent_catalog() -> dict[str, Any]:
    """Get catalog of agent modules available for installation."""
    agents = [
        AgentModule(
            id=item["id"],
            name=item["name"],
            role=item["role"],
            description=item["description"],
            version=item["version"],
            installed=item["id"] in _installed_agent_modules,
            default=bool(item.get("default")),
            orchestrator_compatible=bool(item.get("orchestrator_compatible", True)),
        ).model_dump()
        for item in _AGENT_MODULE_CATALOG
    ]
    return {
        "agents": agents,
        "stats": {
            "total": len(agents),
            "installed": len(_installed_agent_modules),
            "available": len(agents) - len(_installed_agent_modules),
        },
    }


@router.get(
    "/installed",
    status_code=status.HTTP_200_OK,
    summary="Get installed agent modules",
    description="List currently installed agent modules",
)
async def get_installed_agents() -> dict[str, Any]:
    """Get installed agent module list."""
    installed = []
    for item in _AGENT_MODULE_CATALOG:
        if item["id"] in _installed_agent_modules:
            installed.append(
                AgentModule(
                    id=item["id"],
                    name=item["name"],
                    role=item["role"],
                    description=item["description"],
                    version=item["version"],
                    installed=True,
                    default=bool(item.get("default")),
                    orchestrator_compatible=bool(item.get("orchestrator_compatible", True)),
                ).model_dump()
            )
    return {"agents": installed, "count": len(installed)}


@router.post(
    "/install",
    status_code=status.HTTP_200_OK,
    summary="Install an agent module",
    description="Install an available agent module for orchestration",
)
async def install_agent(action: AgentModuleAction) -> dict[str, Any]:
    """Install an agent module."""
    selected = next((item for item in _AGENT_MODULE_CATALOG if item["id"] == action.agent_id), None)
    if not selected:
        raise HTTPException(status_code=404, detail=f"Agent module not found: {action.agent_id}")

    if action.agent_id in _installed_agent_modules:
        return {
            "status": "already_installed",
            "message": f"{selected['name']} is already installed",
            "agent": {
                **selected,
                "installed": True,
            },
        }

    _installed_agent_modules.add(action.agent_id)
    return {
        "status": "success",
        "message": f"{selected['name']} installed successfully",
        "agent": {
            **selected,
            "installed": True,
        },
    }


@router.post(
    "/uninstall",
    status_code=status.HTTP_200_OK,
    summary="Uninstall an agent module",
    description="Uninstall a non-default agent module",
)
async def uninstall_agent(action: AgentModuleAction) -> dict[str, Any]:
    """Uninstall an installed non-default agent module."""
    selected = next((item for item in _AGENT_MODULE_CATALOG if item["id"] == action.agent_id), None)
    if not selected:
        raise HTTPException(status_code=404, detail=f"Agent module not found: {action.agent_id}")

    if action.agent_id not in _installed_agent_modules:
        return {
            "status": "not_installed",
            "message": f"{selected['name']} is not installed",
            "agent": {
                **selected,
                "installed": False,
            },
        }

    if action.agent_id in _DEFAULT_AGENT_MODULES:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot uninstall default agent module: {selected['name']}",
        )

    _installed_agent_modules.discard(action.agent_id)
    return {
        "status": "success",
        "message": f"{selected['name']} uninstalled successfully",
        "agent": {
            **selected,
            "installed": False,
        },
    }


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

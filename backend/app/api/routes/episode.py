"""Episode management endpoints - reset, step, and state operations."""

import logging
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import SettingsDep, create_environment, get_environment, remove_environment, list_environments
from app.core.action import Action, ActionType
from app.core.observation import Observation

router = APIRouter(prefix="/episode")
logger = logging.getLogger(__name__)


class ResetRequest(BaseModel):
    """Request model for resetting an episode."""

    task_id: str = Field(..., description="ID of the task to execute")
    seed: int | None = Field(default=None, description="Random seed for reproducibility")
    config: dict[str, Any] | None = Field(default=None, description="Episode configuration overrides")


class ResetResponse(BaseModel):
    """Response model for episode reset."""

    episode_id: str
    task_id: str
    observation: Observation
    info: dict[str, Any]


class StepRequest(BaseModel):
    """Request model for taking a step."""

    episode_id: str = Field(..., description="ID of the episode")
    action: Action = Field(..., description="Action to execute")


class StepResponse(BaseModel):
    """Response model for step execution."""

    observation: Observation
    reward: float
    reward_breakdown: dict[str, float]
    terminated: bool
    truncated: bool
    info: dict[str, Any]


class EpisodeState(BaseModel):
    """Current state of an episode."""

    episode_id: str
    task_id: str
    step_number: int
    current_url: str | None
    is_terminal: bool
    total_reward: float
    extracted_data: dict[str, Any]


class EpisodeListResponse(BaseModel):
    """Response model for listing episodes."""

    episodes: list[str]
    count: int


@router.post(
    "/reset",
    response_model=ResetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Reset/create new episode",
    description="Create a new episode for a given task",
)
async def reset_episode(
    request: ResetRequest,
    settings: SettingsDep,
) -> ResetResponse:
    """
    Reset and initialize a new episode.
    
    Args:
        request: Reset request containing task_id and optional seed.
        settings: Application settings.
    
    Returns:
        ResetResponse: New episode ID and initial observation.
    """
    episode_id = str(uuid4())
    logger.info(f"Creating new episode {episode_id} for task {request.task_id}")

    try:
        env = create_environment(episode_id, settings)
        observation, info = await env.reset(
            task_id=request.task_id,
            seed=request.seed,
            config=request.config,
        )

        return ResetResponse(
            episode_id=episode_id,
            task_id=request.task_id,
            observation=observation,
            info=info,
        )
    except Exception as e:
        logger.error(f"Failed to reset episode: {e}")
        remove_environment(episode_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create episode: {str(e)}",
        )


@router.post(
    "/step",
    response_model=StepResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute action step",
    description="Execute an action in the episode and receive observation and reward",
)
async def step_episode(request: StepRequest) -> StepResponse:
    """
    Execute an action step in the episode.
    
    Args:
        request: Step request containing episode_id and action.
    
    Returns:
        StepResponse: New observation, reward, and termination status.
    """
    logger.info(f"Step in episode {request.episode_id}: {request.action.action_type}")

    env = get_environment(request.episode_id)

    try:
        observation, reward, reward_breakdown, terminated, truncated, info = await env.step(
            request.action
        )

        # Clean up if episode is done
        if terminated or truncated:
            logger.info(f"Episode {request.episode_id} completed")

        return StepResponse(
            observation=observation,
            reward=reward,
            reward_breakdown=reward_breakdown,
            terminated=terminated,
            truncated=truncated,
            info=info,
        )
    except Exception as e:
        logger.error(f"Step failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Step execution failed: {str(e)}",
        )


@router.get(
    "/state/{episode_id}",
    response_model=EpisodeState,
    status_code=status.HTTP_200_OK,
    summary="Get episode state",
    description="Get the current state of an episode",
)
async def get_episode_state(episode_id: str) -> EpisodeState:
    """
    Get the current state of an episode.
    
    Args:
        episode_id: ID of the episode.
    
    Returns:
        EpisodeState: Current episode state.
    """
    env = get_environment(episode_id)
    state = env.get_state()

    return EpisodeState(
        episode_id=episode_id,
        task_id=state["task_id"],
        step_number=state["step_number"],
        current_url=state["current_url"],
        is_terminal=state["is_terminal"],
        total_reward=state["total_reward"],
        extracted_data=state["extracted_data"],
    )


@router.delete(
    "/{episode_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete episode",
    description="Clean up and delete an episode",
)
async def delete_episode(episode_id: str) -> None:
    """
    Delete an episode and clean up resources.
    
    Args:
        episode_id: ID of the episode to delete.
    """
    if not remove_environment(episode_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Episode {episode_id} not found",
        )
    logger.info(f"Deleted episode {episode_id}")


@router.get(
    "/",
    response_model=EpisodeListResponse,
    status_code=status.HTTP_200_OK,
    summary="List episodes",
    description="List all active episodes",
)
async def list_episodes() -> EpisodeListResponse:
    """
    List all active episodes.
    
    Returns:
        EpisodeListResponse: List of active episode IDs.
    """
    episodes = list_environments()
    return EpisodeListResponse(
        episodes=episodes,
        count=len(episodes),
    )

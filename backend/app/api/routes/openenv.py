"""OpenEnv compatibility endpoints exposed at root-level paths."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import SettingsDep
from app.api.routes.episode import (
    EpisodeState,
    ResetRequest,
    ResetResponse,
    StepRequest,
    get_episode_state,
    reset_episode,
    step_episode,
)
from app.core.action import Action, ActionType

router = APIRouter(tags=["OpenEnv"])


class OpenEnvResetRequest(BaseModel):
    """Lenient reset request supporting common OpenEnv field aliases."""

    task_id: str | None = Field(default=None)
    task: str | None = Field(default=None)
    task_name: str | None = Field(default=None)
    seed: int | None = Field(default=None)
    config: dict[str, Any] | None = Field(default=None)


class OpenEnvStepRequest(BaseModel):
    """Lenient step request supporting common OpenEnv field aliases."""

    episode_id: str | None = Field(default=None)
    episode: str | None = Field(default=None)
    session_id: str | None = Field(default=None)
    action: Any = Field(default_factory=dict)


def _coerce_action(action_payload: Any) -> Action:
    """Coerce OpenEnv-style actions into internal Action model."""
    if isinstance(action_payload, Action):
        return action_payload

    if isinstance(action_payload, str):
        action_type = action_payload.strip().lower()
        try:
            return Action(action_type=ActionType(action_type), parameters={})
        except ValueError:
            return Action.wait()

    if isinstance(action_payload, dict):
        payload = dict(action_payload)

        if "action_type" not in payload:
            for alias in ("action", "type", "name"):
                alias_value = payload.get(alias)
                if isinstance(alias_value, str) and alias_value.strip():
                    payload["action_type"] = alias_value.strip().lower()
                    break

        if "parameters" not in payload:
            params = payload.get("params")
            payload["parameters"] = params if isinstance(params, dict) else {}

        if "reasoning" not in payload and isinstance(payload.get("thought"), str):
            payload["reasoning"] = payload["thought"]

        action_type = payload.get("action_type")
        if not isinstance(action_type, str):
            payload["action_type"] = ActionType.WAIT.value
            payload["parameters"] = {}
        else:
            normalized = action_type.strip().lower()
            try:
                ActionType(normalized)
                payload["action_type"] = normalized
            except ValueError:
                payload["action_type"] = ActionType.WAIT.value
                payload["parameters"] = {}

        try:
            return Action.model_validate(payload)
        except Exception:
            return Action.wait()

    return Action.wait()


@router.post(
    "/reset",
    response_model=ResetResponse,
    status_code=status.HTTP_200_OK,
    summary="OpenEnv-compatible reset endpoint",
)
@router.post(
    "/api/reset",
    response_model=ResetResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def openenv_reset(
    settings: SettingsDep,
    request: OpenEnvResetRequest | None = Body(default=None),
) -> ResetResponse:
    """
    Root-level reset alias used by OpenEnv evaluators.

    Defaults to `task_001` when no explicit task identifier is provided.
    """
    payload = request or OpenEnvResetRequest()
    task_id = payload.task_id or payload.task or payload.task_name or "task_001"
    normalized_request = ResetRequest(task_id=task_id, seed=payload.seed, config=payload.config)
    return await reset_episode(normalized_request, settings)


@router.post(
    "/step",
    status_code=status.HTTP_200_OK,
    summary="OpenEnv-compatible step endpoint",
)
@router.post(
    "/api/step",
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def openenv_step(
    request: OpenEnvStepRequest = Body(default_factory=OpenEnvStepRequest),
) -> dict[str, Any]:
    """Root-level step alias used by OpenEnv evaluators."""
    episode_id = request.episode_id or request.episode or request.session_id
    if not episode_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing episode_id",
        )

    result = await step_episode(
        StepRequest(
            episode_id=episode_id,
            action=_coerce_action(request.action),
        )
    )
    payload = result.model_dump()
    payload["done"] = bool(result.terminated or result.truncated)
    return payload


@router.get(
    "/state/{episode_id}",
    response_model=EpisodeState,
    status_code=status.HTTP_200_OK,
    summary="OpenEnv-compatible state endpoint",
)
@router.get(
    "/api/state/{episode_id}",
    response_model=EpisodeState,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def openenv_state(episode_id: str) -> EpisodeState:
    """Root-level state alias used by OpenEnv evaluators."""
    return await get_episode_state(episode_id)


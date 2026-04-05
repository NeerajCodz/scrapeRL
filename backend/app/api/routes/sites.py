"""Site template API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.sites import (
    get_site_template,
    list_site_templates,
    match_site_template,
    serialize_site_template,
)

router = APIRouter(prefix="/sites", tags=["sites"])


class SiteMatchRequest(BaseModel):
    """Payload to match a site template."""

    instructions: str = Field(default="", description="Task instructions")
    assets: list[str] = Field(default_factory=list, description="Task assets/URLs")


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="List inbuilt site templates",
    description="Return all site templates available for agent planning",
)
async def list_sites() -> dict[str, Any]:
    """List all available site templates."""

    templates = list_site_templates()
    return {"count": len(templates), "sites": templates}


@router.get(
    "/{site_id}",
    status_code=status.HTTP_200_OK,
    summary="Get one site template",
    description="Return one template by site_id",
)
async def get_site(site_id: str) -> dict[str, Any]:
    """Get one site template."""

    template = get_site_template(site_id)
    if not template:
        raise HTTPException(status_code=404, detail=f"Site template '{site_id}' not found")

    return serialize_site_template(template)


@router.post(
    "/match",
    status_code=status.HTTP_200_OK,
    summary="Match a template for task input",
    description="Find the best matching site template from instructions/assets",
)
async def match_site(payload: SiteMatchRequest) -> dict[str, Any]:
    """Resolve best site template for given instructions and assets."""

    template = match_site_template(payload.instructions, payload.assets)
    if not template:
        return {"matched": False, "site": None}

    return {"matched": True, "site": serialize_site_template(template)}

"""Regression tests for asset URL resolution and site-template matching."""

from __future__ import annotations

import pytest

from app.api.routes import scrape as scrape_routes
from app.sites import match_site_template


@pytest.mark.asyncio
async def test_resolve_assets_treats_bare_domain_as_url() -> None:
    """Bare domains should resolve directly, without query fallback/search discovery."""

    resolved, discoveries = await scrape_routes._resolve_assets(["github.com"], enabled_plugins=[])

    assert resolved == ["https://github.com"]
    assert discoveries == []


def test_match_site_template_with_bare_domain() -> None:
    """Site template matching should work when assets omit URL scheme."""

    template = match_site_template("top 10 trending repos", ["github.com"])

    assert template is not None
    assert template.site_id == "github"


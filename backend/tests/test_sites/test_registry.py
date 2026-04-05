"""Comprehensive tests for all built-in site templates."""

from fastapi.testclient import TestClient

from app.api.routes.scrape import _create_intelligent_navigation_plan
from app.sites.registry import list_site_templates, match_site_template
from app.sites.templates import SITE_TEMPLATES


def test_site_template_catalog_is_large_and_unique() -> None:
    """Catalog should contain many unique templates for production coverage."""

    assert len(SITE_TEMPLATES) >= 50
    ids = [template.site_id for template in SITE_TEMPLATES]
    assert len(ids) == len(set(ids))


def test_every_template_matches_its_primary_domain() -> None:
    """Every template must be discoverable from its primary domain."""

    for template in SITE_TEMPLATES:
        primary_domain = template.domains[0]
        matched = match_site_template("extract structured data", [f"https://{primary_domain}"])
        assert matched is not None, f"No match for {template.site_id} ({primary_domain})"
        assert matched.site_id == template.site_id


def test_every_template_generates_site_aware_navigation_plan() -> None:
    """Planner should attach site template metadata for all known domains."""

    for template in SITE_TEMPLATES:
        primary_domain = template.domains[0]
        plan = _create_intelligent_navigation_plan("collect entries", [f"https://{primary_domain}"])
        assert plan.get("site_template_id") == template.site_id
        assert plan.get("site_template_name") == template.name


def test_every_template_available_through_api(client: TestClient) -> None:
    """Each template should be retrievable via /api/sites/{site_id}."""

    for template in SITE_TEMPLATES:
        response = client.get(f"/api/sites/{template.site_id}")
        assert response.status_code == 200, f"API retrieval failed for {template.site_id}"
        payload = response.json()
        assert payload["site_id"] == template.site_id
        assert len(payload["domains"]) >= 1
        assert "navigation_steps" in payload


def test_registry_serialization_covers_all_templates() -> None:
    """Serialized registry output should include every template exactly once."""

    serialized = list_site_templates()
    serialized_ids = {item["site_id"] for item in serialized}
    template_ids = {template.site_id for template in SITE_TEMPLATES}
    assert serialized_ids == template_ids

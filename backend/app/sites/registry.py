"""Template registry and matching helpers for known sites."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from app.sites.models import SiteTemplate
from app.sites.templates import SITE_TEMPLATES

_SITE_BY_ID: dict[str, SiteTemplate] = {template.site_id: template for template in SITE_TEMPLATES}


def serialize_site_template(template: SiteTemplate) -> dict[str, Any]:
    """Serialize a site template into API/event payload format."""

    return {
        "site_id": template.site_id,
        "name": template.name,
        "domains": list(template.domains),
        "aliases": list(template.aliases),
        "default_strategy": template.default_strategy,
        "extraction_goal": template.extraction_goal,
        "navigation_steps": list(template.navigation_steps),
        "output_fields": list(template.output_fields),
        "target_urls": list(template.target_urls),
        "description": template.description,
    }


def list_site_templates() -> list[dict[str, Any]]:
    """Return all site templates as serializable dictionaries."""

    return [serialize_site_template(template) for template in SITE_TEMPLATES]


def get_site_template(site_id: str) -> SiteTemplate | None:
    """Get a template by site_id."""

    return _SITE_BY_ID.get(site_id)


def _normalize_domain(value: str) -> str:
    """Normalize a domain string."""

    lowered = value.lower().strip()
    if lowered.startswith("www."):
        return lowered[4:]
    return lowered


def _extract_domains_from_assets(assets: list[str]) -> list[str]:
    """Extract normalized domains from URL assets."""

    domains: list[str] = []
    for asset in assets:
        parsed = urlparse(asset.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue
        domain = _normalize_domain(parsed.netloc)
        if domain not in domains:
            domains.append(domain)
    return domains


def match_site_template(instructions: str, assets: list[str]) -> SiteTemplate | None:
    """Match site template by URL domain first, then instruction aliases."""

    asset_domains = _extract_domains_from_assets(assets)
    instructions_lower = instructions.lower()

    # Domain-first matching
    for domain in asset_domains:
        for template in SITE_TEMPLATES:
            if any(domain == _normalize_domain(candidate) or domain.endswith(f".{_normalize_domain(candidate)}")
                   for candidate in template.domains):
                return template

    # Alias fallback
    for template in SITE_TEMPLATES:
        alias_tokens = [template.name.lower(), template.site_id.lower(), *[alias.lower() for alias in template.aliases]]
        if any(token and token in instructions_lower for token in alias_tokens):
            return template

    return None

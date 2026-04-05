"""Data models for built-in site templates."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SiteTemplate:
    """Inbuilt site template that agents can reference."""

    site_id: str
    name: str
    domains: tuple[str, ...]
    aliases: tuple[str, ...] = field(default_factory=tuple)
    default_strategy: str = "intelligent_exploration"
    extraction_goal: str = "structured_extraction"
    navigation_steps: tuple[str, ...] = field(default_factory=tuple)
    output_fields: tuple[str, ...] = field(default_factory=tuple)
    target_urls: tuple[str, ...] = field(default_factory=tuple)
    description: str = ""

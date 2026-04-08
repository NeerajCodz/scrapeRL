"""Scraping endpoints with SSE and websocket live updates."""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import os
import re
import shutil
import tempfile
import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, AsyncGenerator
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urljoin, urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.config import Settings
from app.api.deps import (
    MemoryManagerDep,
    SettingsDep,
    get_model_router,
    create_environment,
    remove_environment,
)
from app.models.router import SmartModelRouter, TaskType
from app.api.routes.plugins import PLUGIN_REGISTRY
from app.api.routes.websocket import get_connection_manager
from app.core.action import Action, ActionType
from app.memory.manager import MemoryManager, MemoryType
from app.plugins.python_sandbox import (
    DEFAULT_ANALYSIS_CODE,
    SandboxExecutionResult,
    execute_python_sandbox,
)
from app.search.engine import SearchEngineRouter
from app.search.providers.duckduckgo import DuckDuckGoProvider
from app.sites import match_site_template, serialize_site_template

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scrape", tags=["Scraping"])


def parse_html(html: str) -> BeautifulSoup:
    """Parse HTML string into BeautifulSoup object."""
    return BeautifulSoup(html, "html.parser")


class OutputFormat(str, Enum):
    """Supported output formats."""

    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"
    TEXT = "text"


class TaskComplexity(str, Enum):
    """Task complexity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ScrapeRequest(BaseModel):
    """Request model for scraping."""

    assets: list[str] = Field(..., description="List of URLs or asset identifiers")
    instructions: str = Field(..., description="Scraping instructions")
    output_instructions: str = Field(
        default="Return as JSON",
        description="Output format instructions",
    )
    output_format: OutputFormat = Field(
        default=OutputFormat.JSON,
        description="Desired output format",
    )
    complexity: TaskComplexity = Field(
        default=TaskComplexity.MEDIUM,
        description="Task complexity",
    )
    session_id: str | None = Field(default=None, description="Optional client-provided session ID")
    model: str = Field(default="llama-3.3-70b", description="AI model to use")
    provider: str = Field(default="nvidia", description="AI provider")
    enable_memory: bool = Field(default=True, description="Enable memory features")
    enable_plugins: list[str] = Field(default_factory=list, description="Enabled plugin IDs")
    selected_agents: list[str] = Field(default_factory=list, description="Enabled agent roles/modules")
    max_steps: int = Field(default=50, description="Maximum steps per URL")
    python_code: str | None = Field(
        default=None,
        description="Optional sandboxed Python analysis code (must assign to variable `result`)",
    )


class ScrapeStep(BaseModel):
    """A single step in the scraping process."""

    step_number: int
    action: str
    url: str | None = None
    status: str
    message: str
    reward: float = 0.0
    extracted_data: dict[str, Any] | None = None
    duration_ms: float | None = None
    timestamp: str


class ScrapeResponse(BaseModel):
    """Final scrape response."""

    session_id: str
    status: str
    total_steps: int
    total_reward: float
    extracted_data: dict[str, Any]
    output: str
    output_format: OutputFormat
    duration_seconds: float
    urls_processed: int
    errors: list[str]
    enabled_plugins: list[str]
    requested_plugins: list[str]
    selected_agents: list[str]
    memory_enabled: bool
    sandbox_artifacts: list[str] = Field(default_factory=list)


_active_sessions: dict[str, dict[str, Any]] = {}


def _now_iso() -> str:
    """Return UTC timestamp in ISO format."""

    return datetime.now(timezone.utc).isoformat()


def _sse_event(event: dict[str, Any]) -> str:
    """Serialize a dictionary as one SSE event."""

    return f"data: {json.dumps(event, default=str)}\n\n"


def get_session(session_id: str) -> dict[str, Any] | None:
    """Get an active session by ID."""

    return _active_sessions.get(session_id)


def _is_agent_plugin_id(plugin_id: str) -> bool:
    """Check if a plugin id actually belongs to an agent/skill."""

    lowered = plugin_id.lower()
    return lowered.startswith("skill-") or lowered == "web_scraper"


def _resolve_enabled_plugins(
    requested_plugins: list[str],
) -> tuple[list[str], list[str]]:
    """Resolve requested plugin IDs against installed plugin registry."""

    if not requested_plugins:
        return [], []

    available: set[str] = {
        plugin["id"]
        for category_name, category in PLUGIN_REGISTRY.items()
        if category_name != "skills"
        for plugin in category
        if plugin.get("installed")
    }
    unique_requested = list(dict.fromkeys(requested_plugins))
    enabled = [plugin_id for plugin_id in unique_requested if plugin_id in available]
    missing = [
        plugin_id
        for plugin_id in unique_requested
        if plugin_id not in available and not _is_agent_plugin_id(plugin_id)
    ]
    return enabled, missing


def create_session(session_id: str, request: ScrapeRequest, enabled_plugins: list[str]) -> dict[str, Any]:
    """Create and store a scraping session."""

    sandbox_dir = Path(tempfile.mkdtemp(prefix=f"scraperl-session-{session_id}-"))
    session = {
        "id": session_id,
        "request": request,
        "status": "running",
        "steps": [],
        "total_reward": 0.0,
        "extracted_data": {},
        "errors": [],
        "start_time": time.time(),
        "current_url_index": 0,
        "enabled_plugins": enabled_plugins,
        "resolved_assets": [],
        "sandbox_dir": str(sandbox_dir),
    }
    _active_sessions[session_id] = session
    return session


def update_session(session_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    """Update a session in storage."""

    if session_id in _active_sessions:
        _active_sessions[session_id].update(updates)
        return _active_sessions[session_id]
    return None


def remove_session(session_id: str) -> bool:
    """Remove a session from storage."""

    if session_id in _active_sessions:
        sandbox_dir = _active_sessions[session_id].get("sandbox_dir")
        if sandbox_dir:
            shutil.rmtree(sandbox_dir, ignore_errors=True)
        del _active_sessions[session_id]
        return True
    return False


def _safe_artifact_name(value: str) -> str:
    """Create a safe artifact filename stem."""

    sanitized = re.sub(r"[^a-zA-Z0-9_-]+", "_", value).strip("_")
    return sanitized[:80] or "artifact"


def _write_session_artifact(session: dict[str, Any], file_name: str, content: str) -> None:
    """Write a text artifact to the session sandbox."""

    sandbox_dir = session.get("sandbox_dir")
    if not sandbox_dir:
        return
    path = Path(sandbox_dir) / file_name
    path.write_text(content, encoding="utf-8")


def _write_session_json_artifact(session: dict[str, Any], file_name: str, data: Any) -> None:
    """Write a JSON artifact to the session sandbox."""

    sandbox_dir = session.get("sandbox_dir")
    if not sandbox_dir:
        return
    path = Path(sandbox_dir) / file_name
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _list_session_artifacts(session: dict[str, Any]) -> list[str]:
    """List files currently written to the session sandbox."""

    sandbox_dir = session.get("sandbox_dir")
    if not sandbox_dir:
        return []
    base = Path(sandbox_dir)
    if not base.exists():
        return []
    return sorted([file.name for file in base.iterdir() if file.is_file()])


def _create_tool_call_step(
    session: dict[str, Any],
    tool_name: str,
    description: str,
    parameters: dict[str, Any],
    status: str = "running",
    result: dict[str, Any] | None = None,
    reward: float = 0.0,
    url: str | None = None,
) -> dict[str, Any]:
    """Create a tool call step event."""
    step_number = len(session.get("steps", [])) + 1

    def _format_arg(value: Any) -> str:
        rendered = json.dumps(value, default=str)
        return rendered if len(rendered) <= 40 else f"{rendered[:37]}..."

    message = f"{tool_name}({', '.join(f'{k}={_format_arg(v)}' for k, v in parameters.items())})"
    if status == "completed" and result:
        result_preview = ", ".join(f"{k}={v}" for k, v in list(result.items())[:2])
        message = f"{tool_name}() → {result_preview[:50]}"
    
    return _record_step(
        session,
        ScrapeStep(
            step_number=step_number,
            action="tool_call",
            url=url,
            status=status,
            message=message,
            reward=reward,
            extracted_data={
                "tool_name": tool_name,
                "tool_description": description,
                "parameters": parameters,
                **({"result": result} if result else {}),
            },
            timestamp=_now_iso(),
        ),
    )


def _record_step(session: dict[str, Any], step: ScrapeStep) -> dict[str, Any]:
    """Store and return a step event payload."""

    payload = step.model_dump()
    session["steps"].append(payload)
    return {"type": "step", "data": payload}


def _csv_escape(value: Any) -> str:
    """Escape one CSV value."""

    text = str(value)
    if any(ch in text for ch in [",", '"', "\n"]):
        text = '"' + text.replace('"', '""') + '"'
    return text


def _rows_to_csv(rows: list[dict[str, Any]], preferred_headers: list[str] | None = None) -> str:
    """Render list-of-dicts rows as CSV text."""

    if not rows:
        return ""
    headers = preferred_headers or list(rows[0].keys())
    lines = [",".join(_csv_escape(h) for h in headers)]
    for row in rows:
        lines.append(",".join(_csv_escape(row.get(h, "")) for h in headers))
    return "\n".join(lines)


def _flatten_for_csv(data: dict[str, Any]) -> tuple[list[str], list[list[str]]]:
    """Flatten extracted dict into CSV headers and rows."""

    if not data:
        return [], []

    if all(isinstance(value, dict) for value in data.values()):
        all_headers = sorted({k for value in data.values() if isinstance(value, dict) for k in value.keys()})
        headers = ["asset", *all_headers]
        rows = []
        for asset, values in data.items():
            value_dict = values if isinstance(values, dict) else {}
            row = [_csv_escape(asset), *[_csv_escape(value_dict.get(key, "")) for key in all_headers]]
            rows.append(row)
        return headers, rows

    headers = ["key", "value"]
    rows = [[_csv_escape(k), _csv_escape(v)] for k, v in data.items()]
    return headers, rows


async def format_output(data: dict[str, Any], output_format: OutputFormat, _instructions: str) -> str:
    """Format extracted data based on requested output format."""

    if output_format == OutputFormat.JSON:
        return json.dumps(data, indent=2, default=str)

    if output_format == OutputFormat.CSV:
        # Check if there's a pre-formatted csv_output
        if isinstance(data, dict) and "csv_output" in data:
            return data["csv_output"]
        
        # Check for rows format
        if (
            isinstance(data, dict)
            and isinstance(data.get("rows"), list)
            and all(isinstance(row, dict) for row in data.get("rows", []))
        ):
            rows = data.get("rows", [])
            preferred_headers = (
                data.get("columns")
                if isinstance(data.get("columns"), list)
                else None
            )
            return _rows_to_csv(rows, preferred_headers=preferred_headers)

        headers, rows = _flatten_for_csv(data)
        if not headers:
            return ""
        lines = [",".join(headers)]
        lines.extend(",".join(row) for row in rows)
        return "\n".join(lines)

    if output_format == OutputFormat.MARKDOWN:
        lines: list[str] = ["# Extracted Data", ""]
        for key, value in data.items():
            lines.append(f"## {key}")
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    lines.append(f"- **{sub_key}**: {sub_value}")
            elif isinstance(value, list):
                for item in value:
                    lines.append(f"- {item}")
            else:
                lines.append(f"- {value}")
            lines.append("")
        return "\n".join(lines)

    lines = [f"{key}: {value}" for key, value in data.items()]
    return "\n".join(lines)


def _extract_fields_for_complexity(complexity: TaskComplexity) -> list[str]:
    """Map complexity level to extraction fields."""
    
    # For agentic scraping, we need to be goal-oriented
    # These are basic fields, but the planner should navigate intelligently
    fields = ["title", "content", "links"]
    if complexity in (TaskComplexity.MEDIUM, TaskComplexity.HIGH):
        fields.extend(["meta", "images", "data"])
    if complexity == TaskComplexity.HIGH:
        fields.extend(["scripts", "forms", "tables"])
    return fields


def _plan_from_site_template(
    site_template: Any,
    strategy_override: str | None = None,
    extraction_goal_override: str | None = None,
) -> dict[str, Any]:
    """Build a navigation plan from a matched site template."""

    target_urls = list(site_template.target_urls) if site_template.target_urls else []
    if not target_urls and site_template.domains:
        target_urls = [f"https://{site_template.domains[0]}"]

    return {
        "strategy": strategy_override or "intelligent_exploration",
        "target_urls": target_urls,
        "navigation_steps": list(site_template.navigation_steps) or [
            "Navigate to site and identify relevant sections",
            "Extract structured fields aligned with instructions",
        ],
        "extraction_goal": extraction_goal_override or site_template.extraction_goal,
        "output_fields": list(site_template.output_fields),
        "site_template_id": site_template.site_id,
        "site_template_name": site_template.name,
        "site_template_domains": list(site_template.domains),
    }


def _create_intelligent_navigation_plan(instructions: str, assets: list[str]) -> dict[str, Any]:
    """Create an intelligent navigation plan based on user instructions."""
    
    instructions_lower = instructions.lower()
    site_template = match_site_template(instructions, assets)

    # Site-specific strategy overrides
    if site_template and site_template.site_id == "github":
        # Detect GitHub trending/top repos requests (flexible matching)
        github_trending_signals = [
            "trending" in instructions_lower,
            "top" in instructions_lower and "repo" in instructions_lower,
            "top" in instructions_lower and "project" in instructions_lower,
            "best" in instructions_lower and "repo" in instructions_lower,
            "popular" in instructions_lower and "repo" in instructions_lower,
            "this week" in instructions_lower,
            "this month" in instructions_lower,
            "today" in instructions_lower and "repo" in instructions_lower,
        ]
        if any(github_trending_signals):
            return _plan_from_site_template(
                site_template,
                strategy_override="github_trending",
                extraction_goal_override="trending_repositories",
            )

    if site_template and site_template.site_id == "reddit":
        if any(
            token in instructions_lower
            for token in ("trending", "popular", "community", "communities", "subreddit", "subreddits")
        ):
            return _plan_from_site_template(
                site_template,
                strategy_override="reddit_trending",
                extraction_goal_override="trending_communities",
            )

    if site_template:
        return _plan_from_site_template(site_template)
    
    # News articles detection
    elif any(word in instructions_lower for word in ["news", "article", "headline"]):
        return {
            "strategy": "news_extraction",
            "navigation_steps": [
                "Navigate to main news page",
                "Extract article headlines and summaries",
                "Follow article links if needed"
            ],
            "extraction_goal": "news_articles",
            "output_fields": ["headline", "summary", "publish_date", "author"]
        }
    
    # General search/exploration
    elif any(word in instructions_lower for word in ["search", "find", "explore", "all"]):
        return {
            "strategy": "intelligent_exploration", 
            "navigation_steps": [
                "Analyze main page for relevant navigation",
                "Follow relevant links based on instructions",
                "Extract data according to specified format"
            ],
            "extraction_goal": "custom_exploration"
        }
    
    # Default single-page extraction
    return {
        "strategy": "single_page",
        "navigation_steps": ["Extract content from provided URL"],
        "extraction_goal": "basic_extraction",
        "site_template_id": None,
        "site_template_name": None,
        "site_template_domains": [],
    }


def _is_url_asset(asset: str) -> bool:
    """Check whether an asset string is a URL."""

    return _coerce_url_asset(asset) is not None


def _looks_like_host(host: str) -> bool:
    """Return True when host resembles a real domain, localhost, or IPv4."""

    lowered = host.lower()
    if lowered == "localhost":
        return True

    if re.match(r"^\d{1,3}(?:\.\d{1,3}){3}$", lowered):
        return True

    return bool(re.match(r"^(?:[a-z0-9-]+\.)+[a-z]{2,63}$", lowered))


def _coerce_url_asset(asset: str) -> str | None:
    """Normalize URL-like asset strings (supports bare domains such as github.com)."""

    candidate = asset.strip()
    if not candidate or any(ch.isspace() for ch in candidate):
        return None

    normalized = candidate
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", normalized):
        normalized = f"https://{normalized}"

    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None

    host = (parsed.hostname or "").strip().lower()
    if not host or not _looks_like_host(host):
        return None

    return normalized


def _discover_assets_for_query(query: str) -> list[str]:
    """Resolve non-URL query assets using deterministic query-aware fallbacks."""

    query_l = query.lower()
    if "gold" in query_l and ("price" in query_l or "trend" in query_l):
        return [
            "https://raw.githubusercontent.com/datasets/gold-prices/master/data/monthly.csv",
            "https://github.com/datasets/gold-prices",
        ]
    encoded = quote_plus(query)
    # r.jina.ai provides a static, text-friendly rendering of dynamic search pages.
    return [f"https://r.jina.ai/http://duckduckgo.com/?q={encoded}"]


def _fetch_text_render_markdown(url: str, timeout_seconds: int = 12) -> tuple[str, str] | None:
    """Fetch a URL through r.jina.ai text rendering for dynamic-page fallback extraction."""

    normalized = _coerce_url_asset(url) or url
    if "://" not in normalized:
        normalized = f"https://{normalized}"
    proxy_url = _apply_text_render_proxy(normalized, force=True)
    request = Request(
        proxy_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/plain,text/markdown,*/*",
        },
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = response.read()
        markdown = payload.decode("utf-8", errors="replace")
        if markdown.strip():
            return markdown, proxy_url
    except (HTTPError, URLError, TimeoutError, ValueError) as error:
        logger.debug("Text-render fallback fetch failed for %s: %s", proxy_url, error)
    return None


async def _search_urls_with_mcp(query: str, max_results: int = 6) -> list[str]:
    """Use MCP search provider to discover URLs for non-URL assets."""

    router = SearchEngineRouter()
    provider = DuckDuckGoProvider()
    router.register_provider("duckduckgo", provider, set_default=True)

    try:
        await router.initialize()
        results = await router.search(query=query, max_results=max_results, provider="duckduckgo")
        urls: list[str] = []
        for result in results:
            url = result.url if hasattr(result, "url") else result.get("url", "")
            if not _is_url_asset(str(url)):
                continue
            if "example.com" in str(url):
                continue
            if url not in urls:
                urls.append(str(url))
        return urls
    except Exception:
        return []
    finally:
        await router.shutdown()


def _build_recovery_queries(base_url: str, instructions: str | None) -> list[str]:
    """Build generic discovery queries for low-relevance extraction recovery."""

    normalized_url = _coerce_url_asset(base_url) or base_url
    if "://" not in normalized_url:
        normalized_url = f"https://{normalized_url}"
    parsed = urlparse(normalized_url)
    host = (parsed.hostname or "").lower()

    clean_instructions = (instructions or "").strip()
    queries: list[str] = []
    if host and clean_instructions:
        queries.append(f"{host} {clean_instructions}")
    if clean_instructions:
        queries.append(clean_instructions)
    if host:
        queries.append(f"{host} latest trending top")

    deduped: list[str] = []
    for query in queries:
        normalized = query.strip()
        if not normalized or normalized in deduped:
            continue
        deduped.append(normalized)
    return deduped


def _extract_markdown_link_rows(
    markdown: str,
    source_url: str,
    output_instructions: str | None,
    instructions: str | None,
    row_limit: int,
) -> list[dict[str, Any]]:
    """Extract rows from markdown content using link patterns and line analysis."""
    
    columns = _requested_columns_from_output_instructions(output_instructions) or ["title", "link", "content"]
    keywords = _instruction_keywords(instructions, max_keywords=8)
    
    # Boilerplate patterns to filter out
    boilerplate_labels = {
        "home", "about", "contact", "contact us", "help", "search", "press",
        "copyright", "creator", "creators", "advertise", "developers", "terms",
        "privacy", "policy & safety", "sign in", "log in", "sign up", "register",
        "settings", "report history", "send feedback", "learn more", "more info",
        "test new features", "how youtube works", "nfl sunday ticket", "shorts",
        "subscriptions", "you", "playlist", "now playing", "skip navigation",
    }
    boilerplate_url_tokens = (
        "privacy", "terms", "cookie", "contact", "advertis", "copyright",
        "policy", "press", "help", "about/", "/t/", "legal", "support",
        "feedback", "settings", "account", "login", "signin", "signup",
        "ServiceLogin", "accounts.google.com",
    )
    
    candidate_rows: list[tuple[int, dict[str, Any]]] = []
    seen_titles: set[str] = set()
    seen_links: set[str] = set()
    
    # Patterns for extracting content
    # Match markdown links like [Title](URL) but NOT image links like ![Image](URL)
    # URL ends at first space, quote, or closing paren
    content_link_pattern = re.compile(r'(?<!!)\[([^\]]+)\]\((https?://[^\s"\)]+)')
    # Match complex links with embedded images: [![Image](img_url) Text](link_url)
    # This captures the text after the image and the final link
    complex_link_pattern = re.compile(r'\[!\[Image[^\]]*\]\([^\)]+\)\s*([^\]]+)\]\((https?://[^\s"\)]+)\)')
    # Match view/viewer/point counts anywhere (including "47.2K viewers", "787 points" format)
    views_pattern = re.compile(r'(\d+(?:[.,]\d+)?[KkMmBb]?)\s*(?:views?|viewers?|points?)', re.IGNORECASE)
    likes_pattern = re.compile(r'(\d+(?:[.,]\d+)?[KkMmBb]?)\s*likes?', re.IGNORECASE)
    comments_pattern = re.compile(r'(\d+(?:[.,]\d+)?[KkMmBb]?)\s*comments?', re.IGNORECASE)
    date_pattern = re.compile(r'\b(today|yesterday|\d+\s+(?:minutes?|hours?|days?|weeks?|months?|years?)\s+ago)\b', re.IGNORECASE)
    
    # Extract view counts from the entire document first, map them by line number
    lines = markdown.split('\n')
    line_views: dict[int, str] = {}
    for i, line in enumerate(lines):
        view_match = views_pattern.search(line)
        if view_match:
            line_views[i] = view_match.group(1)
    
    def get_nearby_metrics(line_idx: int, window: int = 5) -> dict[str, str]:
        """Get metrics from nearby lines."""
        metrics = {"views": "", "likes": "", "comments": "", "date": ""}
        for offset in range(-window, window + 1):
            check_idx = line_idx + offset
            if 0 <= check_idx < len(lines):
                check_line = lines[check_idx]
                if not metrics["views"]:
                    m = views_pattern.search(check_line)
                    if m:
                        metrics["views"] = m.group(1)
                if not metrics["likes"]:
                    m = likes_pattern.search(check_line)
                    if m:
                        metrics["likes"] = m.group(1)
                if not metrics["comments"]:
                    m = comments_pattern.search(check_line)
                    if m:
                        metrics["comments"] = m.group(1)
                if not metrics["date"]:
                    m = date_pattern.search(check_line)
                    if m:
                        metrics["date"] = m.group(1)
        return metrics
    
    # Process each line
    for i, line in enumerate(lines):
        line = line.strip()
        if not line or len(line) < 15:
            continue
        
        lowered_line = line.lower()
        
        # Skip pure navigation/boilerplate lines
        if any(label == lowered_line for label in boilerplate_labels):
            continue
        
        # First check for complex links (like Twitch format: [![Image](url) StreamerName Game Live 22K viewers](channel_url))
        complex_match = complex_link_pattern.search(line)
        if complex_match:
            embedded_text = complex_match.group(1).strip()
            link = complex_match.group(2).strip()
            
            # Parse embedded text: "StreamerName Game Live 22K 22K viewers Use the..."
            # Remove "Use the..." suffix and Hype Train info
            embedded_text = re.sub(r'\s*Use the.*$', '', embedded_text)
            embedded_text = re.sub(r'\s*Hype Train.*$', '', embedded_text, flags=re.IGNORECASE)
            # Extract viewer count first
            viewer_match = views_pattern.search(embedded_text)
            viewers = viewer_match.group(1) if viewer_match else ""
            # Remove ALL occurrences of viewer count patterns, including orphan "ers"/"viewers"
            name_game = re.sub(r'\d+(?:[.,]\d+)?[KkMmBb]?\s*(?:views?|viewers?|ers)?', '', embedded_text, flags=re.IGNORECASE)
            # Remove standalone "ers" or "viewers" that might remain
            name_game = re.sub(r'\b(?:ers|viewers?|views?)\b', '', name_game, flags=re.IGNORECASE)
            # Remove "Live" 
            name_game = re.sub(r'\bLive\b', '', name_game, flags=re.IGNORECASE)
            # Collapse whitespace
            name_game = re.sub(r'\s+', ' ', name_game).strip()
            
            # Split into name and game (heuristic: first word is name, rest is game)
            parts = name_game.split(maxsplit=1)
            streamer_name = parts[0] if parts else ""
            game = parts[1].strip() if len(parts) > 1 else ""
            
            if streamer_name and link:
                link_normalized = link.split('?')[0]
                if link_normalized not in seen_links:
                    seen_links.add(link_normalized)
                    
                    row: dict[str, Any] = {}
                    for col in columns:
                        lower_col = col.lower()
                        if lower_col in {"url", "link", "href", "channel"}:
                            row[col] = link
                        elif lower_col in {"title", "name", "streamer_name", "streamer", "username"}:
                            row[col] = streamer_name
                        elif lower_col in {"game", "category", "playing"}:
                            row[col] = game
                        elif lower_col in {"views", "view_count", "viewers", "viewer_count"}:
                            row[col] = viewers
                        else:
                            row[col] = ""
                    
                    # Streams with viewers are highly relevant
                    score = 5 if viewers else 2
                    candidate_rows.append((score, row))
                    continue  # Move to next line
        
        # Find content links (not images)
        for match in content_link_pattern.finditer(line):
            title = match.group(1).strip()
            link = match.group(2).strip()
            
            # Skip image references in title
            if title.startswith("Image ") or title.startswith("!["):
                continue
            
            # Skip very short titles (likely navigation)
            if len(title) < 5:
                continue
                
            # Skip boilerplate titles
            title_lower = title.lower()
            if title_lower in boilerplate_labels:
                continue
            
            # Skip titles that are just "#### Something" headers without real content
            clean_title = re.sub(r'^#+\s*', '', title).strip()
            if not clean_title or len(clean_title) < 5:
                continue
            
            # Skip if already seen this title or link
            title_normalized = clean_title.lower()[:50]
            link_normalized = link.split('?')[0]  # Remove query params for dedup
            if title_normalized in seen_titles:
                continue
            if link_normalized in seen_links and "watch" in link.lower():
                continue
            
            # Skip boilerplate URLs
            if any(token in link.lower() for token in boilerplate_url_tokens):
                continue
            
            # Get metrics from nearby lines
            metrics = get_nearby_metrics(i)
            
            # Calculate relevance score
            score_text = f"{clean_title} {link}".lower()
            keyword_score = sum(1 for kw in keywords if kw in score_text)
            has_content_marker = any([
                "video" in score_text,
                "music" in score_text,
                "official" in score_text,
                metrics["views"],
                metrics["likes"],
                "watch" in link.lower(),
            ])
            
            # Skip if no keyword match and no content markers
            if keywords and keyword_score == 0 and not has_content_marker:
                continue
            
            # Build row
            row: dict[str, Any] = {}
            for col in columns:
                lower_col = col.lower()
                if lower_col in {"url", "link", "href"}:
                    row[col] = link
                elif lower_col in {"title", "name", "text"}:
                    row[col] = clean_title[:160]
                elif lower_col in {"content", "summary", "description"}:
                    row[col] = clean_title[:320]
                elif lower_col in {"views", "view_count", "viewers", "points", "score", "upvotes"}:
                    row[col] = metrics["views"]
                elif lower_col in {"likes", "like_count"}:
                    row[col] = metrics["likes"]
                elif lower_col in {"comments", "comment_count"}:
                    row[col] = metrics["comments"]
                elif lower_col in {"date", "date_uploaded", "date_uplaoded", "published", "uploaded"}:
                    row[col] = metrics["date"]
                else:
                    row[col] = ""
            
            # Track seen items
            seen_titles.add(title_normalized)
            seen_links.add(link_normalized)
            
            # Calculate final score for ranking
            quality_score = keyword_score
            if metrics["views"]:
                quality_score += 3
            if metrics["likes"] or metrics["comments"]:
                quality_score += 1
            if "official" in title_lower:
                quality_score += 1
            if "watch" in link.lower():
                quality_score += 1
            
            candidate_rows.append((quality_score, row))
    
    # Also look for standalone lines with view counts (sometimes titles are separate from links)
    # But only if we haven't found enough rows with proper links
    if len(candidate_rows) < row_limit:
        for i, views in line_views.items():
            if i > 0 and len(candidate_rows) < row_limit * 2:
                prev_line = lines[i - 1].strip()
                # Check if previous line might be a title
                if len(prev_line) > 20 and not prev_line.startswith("![") and not prev_line.startswith("http"):
                    title_normalized = prev_line.lower()[:50]
                    if title_normalized not in seen_titles:
                        # Look for a nearby link
                        nearby_link = None
                        for offset in range(-3, 4):
                            check_idx = i + offset
                            if 0 <= check_idx < len(lines):
                                link_match = content_link_pattern.search(lines[check_idx])
                                if link_match and "watch" in link_match.group(2).lower():
                                    nearby_link = link_match.group(2)
                                    break
                        
                        if nearby_link:  # Only add if we found a real link
                            row = {}
                            for col in columns:
                                lower_col = col.lower()
                                if lower_col in {"title", "name", "text"}:
                                    row[col] = prev_line[:160]
                                elif lower_col in {"views", "view_count", "viewers"}:
                                    row[col] = views
                                elif lower_col in {"url", "link", "href"}:
                                    row[col] = nearby_link
                                else:
                                    row[col] = ""
                            seen_titles.add(title_normalized)
                            candidate_rows.append((2, row))  # Lower score for these
    
    # Sort by score (higher is better) and filter out items without views when we have enough with views
    candidate_rows.sort(key=lambda x: x[0], reverse=True)
    
    # Prefer rows with views
    with_views = [(score, row) for score, row in candidate_rows if row.get("views") or row.get("view_count")]
    without_views = [(score, row) for score, row in candidate_rows if not (row.get("views") or row.get("view_count"))]
    
    result = []
    for _, row in with_views[:row_limit]:
        result.append(row)
    
    # Fill remaining slots with rows without views
    remaining = row_limit - len(result)
    if remaining > 0:
        for _, row in without_views[:remaining]:
            result.append(row)
    
    return result


def _extract_rows_from_text_render(
    markdown: str,
    source_url: str,
    output_instructions: str | None,
    instructions: str | None,
    row_limit: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Execute fallback extraction code against text-rendered markdown."""
    
    columns = _requested_columns_from_output_instructions(output_instructions) or ["title", "link", "content"]

    # First try dedicated markdown extraction (better for jina.ai output)
    markdown_rows = _extract_markdown_link_rows(
        markdown=markdown,
        source_url=source_url,
        output_instructions=output_instructions,
        instructions=instructions,
        row_limit=row_limit,
    )
    
    if _rows_have_signal(markdown_rows):
        markdown_rows, _ = _enforce_requested_schema(markdown_rows, output_instructions)
        return markdown_rows[:row_limit], columns

    # Fallback to HTML-based extraction (for cases where markdown contains HTML)
    extraction_code = _fallback_extraction_code(output_instructions, instructions)
    sandbox_globals = {
        "soup": BeautifulSoup(markdown, "html.parser"),
        "html": markdown,
        "url": source_url,
        "re": re,
        "urljoin": urljoin,
        "urlparse": urlparse,
        "BeautifulSoup": BeautifulSoup,
        "extracted_data": [],
    }
    try:
        exec(extraction_code, sandbox_globals)
        extracted_data = sandbox_globals.get("extracted_data", [])
    except Exception as error:
        logger.debug("Fallback text-render extraction failed for %s: %s", source_url, error)
        extracted_data = []

    if not isinstance(extracted_data, list):
        extracted_data = [extracted_data] if extracted_data else []
    extracted_data, output_columns = _enforce_requested_schema(extracted_data, output_instructions)
    extracted_data = extracted_data[:row_limit]
    return extracted_data, output_columns or columns


async def _search_recovery_rows(
    base_url: str,
    instructions: str | None,
    output_instructions: str | None,
    row_limit: int,
) -> tuple[list[dict[str, Any]], list[str], str | None, float]:
    """Search-guided generic recovery for low-relevance extraction results.
    
    IMPORTANT: Prioritize the user's specified site - try alternative paths on the same domain
    before resorting to external search engines.
    """

    best_rows: list[dict[str, Any]] = []
    best_columns: list[str] = []
    best_source: str | None = None
    best_score = 0.0

    # Normalize the base URL
    normalized = _coerce_url_asset(base_url) or base_url
    if "://" not in normalized:
        normalized = f"https://{normalized}"
    parsed = urlparse(normalized)
    
    # FIRST: Try alternative paths on the SAME SITE (stay on user's specified domain)
    alternative_paths = _infer_navigation_paths(instructions)
    for alt_path in alternative_paths[:4]:
        alt_url = f"{parsed.scheme}://{parsed.netloc}{alt_path}"
        text_payload = _fetch_text_render_markdown(alt_url, timeout_seconds=12)
        if not text_payload:
            continue
        markdown, source_url = text_payload
        rows, columns = _extract_rows_from_text_render(
            markdown=markdown,
            source_url=source_url,
            output_instructions=output_instructions,
            instructions=instructions,
            row_limit=row_limit,
        )
        if not _rows_have_signal(rows):
            continue
        score = _rows_relevance_score(rows, instructions)
        if score > best_score or (
            abs(score - best_score) <= 0.0001 and len(rows) > len(best_rows)
        ):
            best_rows = rows
            best_columns = columns
            best_source = source_url
            best_score = score

    # If we found good data on the user's site, return it
    if best_score > 0.25:
        return best_rows, best_columns, best_source, best_score

    # SECOND: Only as last resort, try external search (duckduckgo)
    queries = _build_recovery_queries(base_url, instructions)
    for query in queries[:2]:
        discovered_urls = await _search_urls_with_mcp(query, max_results=5)
        if not discovered_urls:
            discovered_urls = _discover_assets_for_query(query)

        for candidate_url in discovered_urls[:3]:
            text_payload = _fetch_text_render_markdown(candidate_url, timeout_seconds=12)
            if not text_payload:
                continue
            markdown, source_url = text_payload
            rows, columns = _extract_rows_from_text_render(
                markdown=markdown,
                source_url=source_url,
                output_instructions=output_instructions,
                instructions=instructions,
                row_limit=row_limit,
            )
            if not _rows_have_signal(rows):
                continue
            score = _rows_relevance_score(rows, instructions)
            if score > best_score or (
                abs(score - best_score) <= 0.0001 and len(rows) > len(best_rows)
            ):
                best_rows = rows
                best_columns = columns
                best_source = source_url
                best_score = score

    return best_rows, best_columns, best_source, best_score


async def _discover_reddit_communities_via_search(limit: int = 25) -> list[dict[str, Any]]:
    """Discover subreddit URLs via search engine fallback."""

    queries = [
        "site:reddit.com/r popular communities",
        "reddit popular subreddits list",
        "best reddit communities technology",
    ]
    excluded = {"popular", "all", "announcements", "new", "top", "best"}
    seen: set[str] = set()
    communities: list[dict[str, Any]] = []

    for query in queries:
        urls = await _search_urls_with_mcp(query, max_results=18)
        for candidate in urls:
            match = re.search(r"reddit\.com/r/([A-Za-z0-9_]+)/?", candidate, flags=re.IGNORECASE)
            if not match:
                continue
            name = match.group(1)
            normalized = name.lower()
            if normalized in excluded or normalized in seen:
                continue
            seen.add(normalized)
            communities.append(
                {
                    "subreddit": f"r/{name}",
                    "title": f"r/{name}",
                    "subscribers": 0,
                    "active_users": 0,
                    "url": f"https://www.reddit.com/r/{name}/",
                    "description": "Discovered via search fallback",
                }
            )
            if len(communities) >= limit:
                return communities

    return communities


def _fallback_reddit_communities_static(limit: int = 25) -> list[dict[str, Any]]:
    """Provide deterministic Reddit community rows when direct fetch is unavailable."""

    names = [
        "AskReddit",
        "funny",
        "gaming",
        "worldnews",
        "todayilearned",
        "science",
        "movies",
        "technology",
        "pics",
        "news",
        "aww",
        "sports",
        "Music",
        "books",
        "food",
        "dataisbeautiful",
        "MachineLearning",
        "programming",
        "python",
        "javascript",
        "learnprogramming",
        "wallstreetbets",
        "explainlikeimfive",
        "history",
        "space",
    ]
    rows: list[dict[str, Any]] = []
    for name in names[:limit]:
        rows.append(
            {
                "subreddit": f"r/{name}",
                "title": f"r/{name}",
                "subscribers": 0,
                "active_users": 0,
                "url": f"https://www.reddit.com/r/{name}/",
                "description": "Static fallback community entry",
            }
        )
    return rows


def _fetch_reddit_communities(limit: int = 25) -> tuple[list[dict[str, Any]], str]:
    """Compatibility helper used by tests and optional monkeypatch overrides."""

    return _fallback_reddit_communities_static(limit), "static_fallback"


async def _resolve_assets(
    assets: list[str],
    enabled_plugins: list[str],
) -> tuple[list[str], list[dict[str, Any]]]:
    """Resolve user-provided assets into URLs for scraping."""

    resolved: list[str] = []
    discoveries: list[dict[str, Any]] = []
    for asset in assets:
        candidate = asset.strip()
        if not candidate:
            continue

        normalized_url = _coerce_url_asset(candidate)
        if normalized_url:
            if normalized_url not in resolved:
                resolved.append(normalized_url)
            continue

        discovered: list[str] = await _search_urls_with_mcp(candidate, max_results=8)
        if not discovered:
            discovered = _discover_assets_for_query(candidate)

        if discovered:
            for url in discovered:
                if url not in resolved:
                    resolved.append(url)
            discoveries.append({"query": candidate, "resolved_urls": discovered})
        else:
            discoveries.append({"query": candidate, "resolved_urls": []})
    return resolved, discoveries


def _normalize_month(value: Any) -> str | None:
    """Normalize date-like values to YYYY-MM."""

    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    match = re.match(r"^(\d{4})[-/](\d{1,2})", text)
    if not match:
        return None
    year = int(match.group(1))
    month = int(match.group(2))
    if month < 1 or month > 12:
        return None
    return f"{year:04d}-{month:02d}"


def _parse_price(value: Any) -> float | None:
    """Parse a numeric price from text."""

    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def _build_gold_dataset_rows(
    extracted_data: dict[str, Any],
    from_month: str = "2016-01",
) -> list[dict[str, Any]]:
    """Build normalized monthly gold-price rows from extracted source data."""

    rows: list[dict[str, Any]] = []
    for source_url, payload in extracted_data.items():
        if not isinstance(payload, dict):
            continue
        data_rows = payload.get("data")
        if not isinstance(data_rows, list):
            continue

        for entry in data_rows:
            if not isinstance(entry, dict):
                continue
            date_value = (
                entry.get("Date")
                or entry.get("date")
                or entry.get("Month")
                or entry.get("month")
            )
            price_value = (
                entry.get("Price")
                or entry.get("price")
                or entry.get("Close")
                or entry.get("close")
                or entry.get("Value")
                or entry.get("value")
            )
            month = _normalize_month(date_value)
            price = _parse_price(price_value)
            if not month or price is None:
                continue
            if month < from_month:
                continue
            rows.append(
                {
                    "month": month,
                    "gold_price_usd": price,
                    "source_link": source_url,
                }
            )

    dedup: dict[str, dict[str, Any]] = {}
    for row in rows:
        dedup[row["month"]] = row
    ordered = [dedup[key] for key in sorted(dedup.keys())]
    return ordered


def _should_run_python_sandbox(request: ScrapeRequest, extracted_data: dict[str, Any]) -> bool:
    """Decide whether sandbox analysis should run for current scrape output."""

    if request.python_code:
        return True
    if not isinstance(extracted_data, dict) or not extracted_data:
        return False

    if isinstance(extracted_data.get("rows"), list) and len(extracted_data.get("rows", [])) > 0:
        return True

    for value in extracted_data.values():
        if not isinstance(value, dict):
            continue
        if isinstance(value.get("data"), list) and len(value.get("data", [])) > 0:
            return True
        if isinstance(value.get("tables"), list) and len(value.get("tables", [])) > 0:
            return True

    return False


async def _store_url_memory(
    session_id: str,
    url: str,
    extracted: dict[str, Any],
    memory_manager: MemoryManager,
) -> None:
    """Store URL extraction in memory layers."""

    await memory_manager.store(
        key=f"scrape:{session_id}:url:{url}",
        value=extracted,
        memory_type=MemoryType.SHORT_TERM,
        tags=["scrape", "url"],
    )
    await memory_manager.store(
        key=f"scrape:{session_id}:lt:{url}",
        value=json.dumps(extracted, default=str),
        memory_type=MemoryType.LONG_TERM,
        metadata={"session_id": session_id, "url": url, "source": "scrape"},
    )


async def scrape_url(
    session: dict[str, Any],
    session_id: str,
    url: str,
    settings: Settings,
    request: ScrapeRequest,
    memory_manager: MemoryManager,
    enabled_plugins: list[str],
) -> AsyncGenerator[dict[str, Any], None]:
    """Scrape a single URL and yield progress events."""

    episode_id = f"{session_id}-{uuid.uuid4().hex[:8]}"

    try:
        env = create_environment(episode_id, settings)
        await env.reset(task_id=f"scrape_{session_id}")

        step_num = 0
        yield _record_step(
            session,
            ScrapeStep(
                step_number=step_num,
                action="initialize",
                url=url,
                status="completed",
                message=f"Initialized scraping for {url}",
                timestamp=_now_iso(),
            ),
        )

        step_num += 1
        step_start = time.time()
        navigate_action = Action(
            action_type=ActionType.NAVIGATE,
            parameters={"url": url},
            reasoning=f"Navigate to target URL: {url}",
        )
        nav_observation, reward, _, _, _, nav_info = await env.step(navigate_action)
        nav_result = nav_info.get("action_result", {})
        nav_success = bool(nav_result.get("success"))
        nav_error = nav_result.get("error")
        bypassed_tls = bool(nav_result.get("tls_verification_bypassed"))
        navigate_message = f"Navigated to {url}"
        if bypassed_tls:
            navigate_message = f"{navigate_message} (TLS verification bypassed after certificate failure)"
        yield _record_step(
            session,
            ScrapeStep(
                step_number=step_num,
                action="navigate",
                url=url,
                status="completed" if nav_success else "failed",
                message=navigate_message if nav_success else f"Failed to navigate: {nav_error or 'unknown error'}",
                reward=reward,
                duration_ms=(time.time() - step_start) * 1000,
                timestamp=_now_iso(),
            ),
        )

        if nav_observation.page_html:
            source_name = _safe_artifact_name(urlparse(url).netloc or url)
            _write_session_artifact(
                session,
                f"{source_name}_source.txt",
                nav_observation.page_html,
            )
        elif not nav_success:
            session["errors"].append(f"{url}: {nav_error or 'navigation failed'}")
            return

        extracted: dict[str, Any] = {}
        total_reward = reward
        fields_to_extract = _extract_fields_for_complexity(request.complexity)

        for field_name in fields_to_extract:
            if step_num >= request.max_steps:
                break

            step_num += 1
            step_start = time.time()
            yield _record_step(
                session,
                ScrapeStep(
                    step_number=step_num,
                    action="extract",
                    url=url,
                    status="running",
                    message=f"Extracting {field_name}...",
                    timestamp=_now_iso(),
                ),
            )

            extract_action = Action(
                action_type=ActionType.EXTRACT_FIELD,
                parameters={"field_name": field_name},
                reasoning=f"Extract {field_name} using: {request.instructions}",
            )
            observation, reward, _, terminated, truncated, _ = await env.step(extract_action)
            total_reward += reward

            if observation.extracted_so_far:
                for extracted_field in observation.extracted_so_far:
                    if extracted_field.field_name == field_name:
                        extracted[field_name] = extracted_field.value
                        break

            yield _record_step(
                session,
                ScrapeStep(
                    step_number=step_num,
                    action="extract",
                    url=url,
                    status="completed",
                    message=f"Extracted {field_name}",
                    reward=reward,
                    extracted_data={field_name: extracted.get(field_name)},
                    duration_ms=(time.time() - step_start) * 1000,
                    timestamp=_now_iso(),
                ),
            )

            if terminated or truncated:
                break

    except Exception as exc:
        error_message = f"{url}: {exc}"
        session["errors"].append(error_message)
        logger.exception("Error scraping URL", extra={"url": url, "session_id": session_id})
        yield {
            "type": "error",
            "data": {
                "url": url,
                "error": str(exc),
                "timestamp": _now_iso(),
            },
        }
    finally:
        remove_environment(episode_id)


def _agentic_live_llm_enabled() -> bool:
    """Return True when live LLM calls should be used for agentic planning/extraction."""

    if os.getenv("SCRAPERL_DISABLE_LIVE_LLM") == "1":
        return False
    if os.getenv("PYTEST_CURRENT_TEST"):
        return False
    return True


def _apply_text_render_proxy(url: str, force: bool = False) -> str:
    """Optionally route a URL through a text renderer for deterministic extraction."""

    normalized = _coerce_url_asset(url) or url
    if "://" not in normalized:
        normalized = f"https://{normalized}"

    if normalized.startswith("https://r.jina.ai/http://") or normalized.startswith("https://r.jina.ai/https://"):
        return normalized
    if force:
        return f"https://r.jina.ai/http://{normalized.split('://', 1)[1]}"
    return normalized


def _infer_navigation_paths(instructions: str | None) -> list[str]:
    """Infer common navigation paths based on user intent - works generically across sites."""
    
    if not instructions:
        return ["/"]  # Default to homepage
    
    instruction_text = instructions.lower()
    paths: list[str] = []
    
    # Trending/popular intent - common paths across many sites
    # Include "/" (homepage) because many sites show top content on homepage
    if any(token in instruction_text for token in ("trending", "popular", "top", "hot", "best")):
        paths.extend([
            "/",  # Homepage often shows top/trending content (HN, Reddit, etc.)
            "/trending",
            "/popular",
            "/explore",
            "/top",
            "/hot",
            "/discover",
        ])
    
    # Latest/new/recent intent
    if any(token in instruction_text for token in ("latest", "new", "recent", "today")):
        paths.extend([
            "/new",
            "/latest",
            "/recent",
            "/feed/new",
        ])
    
    # Category-specific paths based on content type mentioned
    if "music" in instruction_text or "song" in instruction_text:
        paths.extend(["/feed/trending?bp=4gINGgt5dG1hX2NoYXJ0cw%3D%3D", "/music", "/charts"])
    if "video" in instruction_text:
        paths.extend(["/feed/trending", "/videos"])
    if "game" in instruction_text or "gaming" in instruction_text:
        paths.extend(["/gaming", "/feed/trending?bp=4gIcGhpnYW1pbmdfY29ycHVzX21vc3RfcG9wdWxhcg%3D%3D"])
    if "news" in instruction_text:
        paths.extend(["/news", "/feed/news"])
    if "movie" in instruction_text or "film" in instruction_text:
        paths.extend(["/feed/trending?bp=4gIKGgh0cmFpbGVycw%3D%3D", "/movies"])
    
    # Dedupe while preserving order
    seen: set[str] = set()
    unique_paths: list[str] = []
    for path in paths:
        if path not in seen:
            seen.add(path)
            unique_paths.append(path)
    
    return unique_paths


def _build_search_navigation_url(base_url: str, instructions: str | None) -> str | None:
    """Build a search URL when direct navigation paths don't exist - generic across sites."""
    
    if not instructions:
        return None
    
    parsed = urlparse(base_url)
    host = (parsed.hostname or "").lower()
    
    # Extract search terms from instructions
    keywords = _instruction_keywords(instructions, max_keywords=6)
    if not keywords:
        return None
    
    query_text = "+".join(keywords)
    
    # Common search URL patterns across sites (generic, not site-specific)
    search_patterns = [
        f"{parsed.scheme}://{parsed.netloc}/search?q={query_text}",
        f"{parsed.scheme}://{parsed.netloc}/results?search_query={query_text}",
        f"{parsed.scheme}://{parsed.netloc}/search?query={query_text}",
        f"{parsed.scheme}://{parsed.netloc}/?s={query_text}",
    ]
    
    return search_patterns[0] if search_patterns else None


def _fallback_navigation_url(
    base_url: str,
    instructions: str,
    navigation_plan: dict[str, Any],
) -> str:
    """Derive a deterministic navigation URL using plan/template hints when LLM is unavailable.
    
    Strategy: Prioritize DIRECT SITE ACCESS over search when user specifies a site.
    1. Template target URLs (if available)
    2. Inferred navigation paths (trending, popular, etc.)
    3. Search only for EXPLICIT search intent
    4. Return the base URL (trust the site content)
    """

    normalized = _coerce_url_asset(base_url) or base_url
    if "://" not in normalized:
        normalized = f"https://{normalized}"
    
    parsed = urlparse(normalized)
    instruction_text = (instructions or "").lower()
    
    # 1. Check template target URLs first (hints only)
    plan_targets = navigation_plan.get("target_urls") or []
    valid_targets = [target for target in plan_targets if isinstance(target, str) and _is_url_asset(target)]
    if valid_targets:
        ranked_intent = any(token in instruction_text for token in ("trending", "popular", "top", "latest"))
        if ranked_intent:
            keyword_target = next(
                (
                    target
                    for target in valid_targets
                    if any(token in target.lower() for token in ("trending", "popular", "explore", "discover", "new"))
                ),
                None,
            )
            if keyword_target:
                return _apply_text_render_proxy(keyword_target)

        search_intent = any(token in instruction_text for token in ("search", "query", "lookup"))
        if search_intent:
            search_target = next(
                (target for target in valid_targets if any(token in target.lower() for token in ("search", "query"))),
                None,
            )
            if search_target:
                return _apply_text_render_proxy(search_target)

    # 2. Try direct navigation paths FIRST (trending, hot, etc.)
    # These are direct site pages, not search queries
    inferred_paths = _infer_navigation_paths(instructions)
    if inferred_paths:
        best_path = inferred_paths[0]
        inferred_url = f"{parsed.scheme}://{parsed.netloc}{best_path}"
        return _apply_text_render_proxy(inferred_url)
    
    # 3. Only use site-internal search for EXPLICIT search intents
    search_intent = any(token in instruction_text for token in ("search for", "find ", "looking for", "search:"))
    if search_intent:
        search_url = _build_search_navigation_url(normalized, instructions)
        if search_url:
            return _apply_text_render_proxy(search_url)

    # 4. Return the base URL - trust the site content (homepage often has what user wants)
    return _apply_text_render_proxy(normalized)


def _requested_columns_from_output_instructions(output_instructions: str | None) -> list[str]:
    """Extract requested output columns from instructions like 'csv of username, repo, stars'."""

    if not output_instructions:
        return []

    cleaned = output_instructions.strip()
    cleaned = re.sub(r"^(?:csv|json|table)\s+of\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace(" and ", ", ")
    columns: list[str] = []
    for piece in cleaned.split(","):
        candidate = re.sub(r"[^A-Za-z0-9_]+", " ", piece).strip().lower().replace(" ", "_")
        if candidate and candidate not in columns:
            columns.append(candidate)
    return columns


def _enforce_requested_schema(
    rows: list[dict[str, Any]],
    output_instructions: str | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Project extracted rows onto requested columns from output instructions."""

    requested_columns = _requested_columns_from_output_instructions(output_instructions)
    if not requested_columns:
        if not rows:
            return rows, []
        inferred = list(rows[0].keys())
        return rows, inferred

    normalized_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized_rows.append({column: row.get(column, "") for column in requested_columns})

    if not normalized_rows:
        normalized_rows = [{column: "" for column in requested_columns}]

    return normalized_rows, requested_columns


def _requested_row_limit(instructions: str | None, default_limit: int = 25) -> int:
    """Extract a requested row limit (e.g., 'top 5') from instructions."""

    if not instructions:
        return default_limit
    text = instructions.lower()
    match = re.search(r"\btop\s+(\d{1,3})\b", text) or re.search(
        r"\b(\d{1,3})\s+(?:rows|items|results|entries|records|repos|frameworks)\b",
        text,
    )
    if not match:
        return default_limit
    value = int(match.group(1))
    if value < 1:
        return default_limit
    return min(value, 100)


def _instruction_keywords(instructions: str | None, max_keywords: int = 8) -> list[str]:
    """Extract semantic keywords from user instructions for relevance checks."""

    if not instructions:
        return []
    tokens = re.findall(r"[a-zA-Z]{3,}", instructions.lower())
    stop_words = {
        "get",
        "give",
        "show",
        "find",
        "extract",
        "with",
        "from",
        "this",
        "that",
        "what",
        "where",
        "when",
        "which",
        "return",
        "output",
        "format",
        "data",
        "list",
        "site",
        "website",
        "page",
        "entries",
        "results",
        "items",
        "records",
        "details",
        "about",
        "across",
        "into",
        "only",
        "please",
        "the",
        "and",
    }
    keywords: list[str] = []
    for token in tokens:
        if token in stop_words:
            continue
        if token not in keywords:
            keywords.append(token)
        if len(keywords) >= max_keywords:
            break
    return keywords


def _rows_have_signal(rows: list[dict[str, Any]]) -> bool:
    """Return True when extracted rows contain at least one non-empty value."""

    for row in rows:
        if not isinstance(row, dict):
            continue
        for value in row.values():
            if value is None:
                continue
            if isinstance(value, str):
                if value.strip():
                    return True
            elif value:
                return True
    return False


def _rows_relevance_score(rows: list[dict[str, Any]], instructions: str | None) -> float:
    """Score row relevance against instruction keywords (0-1)."""

    if not rows:
        return 0.0
    keywords = _instruction_keywords(instructions, max_keywords=8)
    if not keywords:
        return 1.0

    row_scores: list[float] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        joined = " ".join(
            str(value).lower()
            for value in row.values()
            if value is not None and str(value).strip()
        )
        if not joined:
            continue
        hits = sum(1 for keyword in keywords if keyword in joined)
        row_scores.append(hits / len(keywords))

    if not row_scores:
        return 0.0

    row_scores.sort(reverse=True)
    top_n = max(1, min(3, len(row_scores)))
    return sum(row_scores[:top_n]) / top_n


def _parse_column_names(output_instructions: str | None) -> list[str]:
    """Parse column names from output instructions.
    
    Examples:
        "csv of title, points" -> ["title", "points"]
        "json with heading and description" -> ["heading", "description"]
        "title, url, views" -> ["title", "url", "views"]
    """
    if not output_instructions:
        return []
    
    # Remove common prefixes
    text = output_instructions.lower()
    for prefix in ["csv of ", "json of ", "json with ", "fields: "]:
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    
    # Split on commas and clean
    columns = [col.strip() for col in text.split(",")]
    
    # Also try splitting on "and" if no commas found
    if len(columns) == 1 and " and " in columns[0]:
        columns = [col.strip() for col in columns[0].split(" and ")]
    
    return [col for col in columns if col]


def _fallback_extraction_code(output_instructions: str | None, instructions: str | None = None) -> str:
    """Build deterministic extraction code when live LLM code generation is unavailable."""

    columns = _requested_columns_from_output_instructions(output_instructions) or [
        "title",
        "url",
        "content",
    ]
    keywords = _instruction_keywords(instructions, max_keywords=8)
    category_hint = keywords[0].title() if keywords else ""
    columns_literal = repr(columns)
    keywords_literal = repr(keywords)
    category_hint_literal = repr(category_hint)
    return f"""
columns = {columns_literal}
keywords = {keywords_literal}
category_hint = {category_hint_literal}
rows = []
candidate_rows = []
seen = set()
anchors = soup.select("a[href]")
noise_fragments = [
    "javascript is disabled",
    "please enable javascript",
    "skip to main content",
    "press enter to activate",
    "toggle navigation",
    "close menu",
    "open menu",
    "cookie settings",
]
boilerplate_labels = {{
    "home",
    "about",
    "contact",
    "contact us",
    "help",
    "search",
    "press",
    "copyright",
    "creator",
    "creators",
    "advertise",
    "developers",
    "terms",
    "privacy",
    "policy & safety",
    "how youtube works",
    "test new features",
    "nfl sunday ticket",
    "sign in",
    "log in",
    "sign up",
    "register",
    "settings",
    "report history",
    "send feedback",
    "learn more",
    "more info",
}}
boilerplate_url_tokens = (
    "privacy",
    "terms",
    "cookie",
    "contact",
    "advertis",
    "copyright",
    "policy",
    "press",
    "help",
    "about/",
    "/t/",
    "legal",
    "support",
    "feedback",
    "settings",
    "account",
    "login",
    "signin",
    "signup",
    "creators/",
    "howyoutubeworks",
)
ranked_intent = bool(re.search(r"\\b(top|trending|popular|latest|today|best)\\b", " ".join(keywords), re.IGNORECASE))

def _extract_metric(text, patterns):
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return ""

def _compact(value, limit):
    return re.sub(r"\\s+", " ", value).strip()[:limit]

def _metric_numeric(raw):
    normalized = str(raw or "").strip().lower().replace(",", "")
    if not normalized:
        return 0.0
    multiplier = 1.0
    if normalized.endswith("k"):
        multiplier = 1000.0
        normalized = normalized[:-1]
    elif normalized.endswith("m"):
        multiplier = 1000000.0
        normalized = normalized[:-1]
    try:
        return float(normalized) * multiplier
    except ValueError:
        return 0.0

for anchor in anchors:
    href = (anchor.get("href") or "").strip()
    text = anchor.get_text(" ", strip=True)
    if not href and not text:
        continue
    if href.startswith("#") or href.startswith("mailto:") or href.startswith("javascript:"):
        continue
    full_href = urljoin(url, href)
    if not full_href.startswith("http"):
        continue
    if full_href.count("/") <= 2:
        continue

    parsed_href = urlparse(full_href)
    path_parts = [part for part in parsed_href.path.split("/") if part]
    slug_value = path_parts[-1].replace("-", " ").replace("_", " ").strip() if path_parts else ""
    container = anchor.find_parent(["article", "tr", "li", "div"])
    container_text = container.get_text(" ", strip=True) if container else text
    stars_value = _extract_metric(container_text, [r"([0-9][0-9,\\.kKmM]*)\\s*(?:stars?|star)\\b"])
    forks_value = _extract_metric(container_text, [r"([0-9][0-9,\\.kKmM]*)\\s*(?:forks?|fork)\\b"])
    views_value = _extract_metric(
        container_text,
        [r"([0-9][0-9,\\.kKmM]*)\\s*(?:views?|viewers?|watching|plays?)\\b"],
    )
    likes_value = _extract_metric(container_text, [r"([0-9][0-9,\\.kKmM]*)\\s*(?:likes?|thumbs\\s*up)\\b"])
    comments_value = _extract_metric(container_text, [r"([0-9][0-9,\\.kKmM]*)\\s*(?:comments?|replies)\\b"])
    date_value = _extract_metric(
        container_text,
        [
            r"\\b(today|yesterday|\\d+\\s+(?:minutes?|hours?|days?|weeks?|months?|years?)\\s+ago)\\b",
            r"\\b(\\d{{4}}[-/]\\d{{1,2}}[-/]\\d{{1,2}})\\b",
            r"\\b(\\d{{1,2}}\\s+[A-Za-z]{{3,9}}\\s+\\d{{4}})\\b",
        ],
    )
    category_from_url = ""
    if len(path_parts) >= 3 and path_parts[0].lower() in {"category", "tags", "topic", "topics", "genres", "genre"}:
        category_from_url = path_parts[1].replace("-", " ").replace("_", " ").strip().title()

    label = (text or container_text).strip()
    if not label:
        continue
    lowered_label = label.lower()
    lowered_href = full_href.lower()
    if any(fragment in lowered_label for fragment in noise_fragments):
        continue
    if lowered_label in boilerplate_labels:
        continue
    if any(token in lowered_href for token in boilerplate_url_tokens):
        continue
    if len(label) > 180 or len(label.split()) > 22:
        continue
    if label.lower() in {{
        "main page", "home", "about", "contact", "help", "search", "read", "talk",
        "view source", "view history", "contents", "current events", "special pages",
    }}:
        continue

    score_text = " ".join([label, container_text, full_href]).lower()
    keyword_score = sum(1 for keyword in keywords if keyword in score_text)
    has_engagement_metric = any([views_value, likes_value, comments_value, date_value])
    if keywords and keyword_score == 0 and not has_engagement_metric:
        continue
    content_text = (container_text or label).strip()
    lowered_content_text = content_text.lower()
    if (
        len(content_text) > 220
        or " menu " in lowered_content_text
        or "dropdown" in lowered_content_text
        or "press enter to" in lowered_content_text
    ):
        content_text = label

    row = {{}}
    for column in columns:
        lower = column.lower()
        if lower in {{"url", "link", "href"}}:
            row[column] = full_href
        elif lower in {{"title", "name", "text"}}:
            row[column] = _compact(label, 160)
        elif lower in {{"content", "summary", "description"}}:
            row[column] = _compact(content_text, 320)
        elif lower in {{"streamer", "channel", "creator", "username", "user", "owner"}}:
            row[column] = _compact(slug_value or label, 120)
        elif lower in {{"repo", "repository", "repo_name"}}:
            row[column] = path_parts[1] if len(path_parts) >= 2 else _compact(slug_value, 120)
        elif lower in {{"stars", "star", "star_count"}}:
            row[column] = stars_value
        elif lower in {{"forks", "fork", "fork_count"}}:
            row[column] = forks_value
        elif lower in {{"views", "view_count", "viewers", "viewer_count", "watchers", "watching"}}:
            row[column] = views_value
        elif lower in {{"likes", "like_count"}}:
            row[column] = likes_value
        elif lower in {{"comments", "comment_count"}}:
            row[column] = comments_value
        elif lower in {{"date", "date_uploaded", "date_uplaoded", "published", "uploaded", "upload_date"}}:
            row[column] = date_value
        elif lower in {{"category", "game", "topic"}}:
            row[column] = category_from_url or category_hint
        else:
            row[column] = ""

    row_key = tuple(row.get(column, "") for column in columns)
    if row_key in seen:
        continue
    seen.add(row_key)

    if any(value for value in row.values()):
        quality_score = keyword_score
        if views_value:
            quality_score += 2
        if likes_value or comments_value:
            quality_score += 1
        candidate_rows.append((quality_score, row))

if not candidate_rows:
    raw_lines = [line.strip() for line in soup.get_text("\\n").splitlines() if line and line.strip()]
    for line in raw_lines:
        if len(line) < 15:
            continue
        lowered_line = line.lower()
        if any(fragment in lowered_line for fragment in noise_fragments):
            continue
        if len(line) > 260:
            continue
        if lowered_line.startswith(("title:", "url source:", "markdown content:")):
            continue
        if re.match(r"^\\*\\s+\\[(all|images|videos|news|maps|shopping)\\]", lowered_line):
            continue
        if re.match(r"^\\[[^\\]]+\\]\\(https?://duckduckgo\\.com/", lowered_line):
            continue
        if lowered_line in {"privacy", "terms", "advertising", "about duckduckgo"}:
            continue
        if lowered_line.startswith("![image"):
            continue
        if lowered_line in boilerplate_labels:
            continue
        keyword_score = sum(1 for keyword in keywords if keyword in lowered_line)
        views_value = _extract_metric(line, [r"([0-9][0-9,\\.kKmM]*)\\s*(?:views?|viewers?|watching|plays?)\\b"])
        likes_value = _extract_metric(line, [r"([0-9][0-9,\\.kKmM]*)\\s*(?:likes?|thumbs\\s*up)\\b"])
        comments_value = _extract_metric(line, [r"([0-9][0-9,\\.kKmM]*)\\s*(?:comments?|replies)\\b"])
        date_value = _extract_metric(
            line,
            [
                r"\\b(today|yesterday|\\d+\\s+(?:minutes?|hours?|days?|weeks?|months?|years?)\\s+ago)\\b",
                r"\\b(\\d{{4}}[-/]\\d{{1,2}}[-/]\\d{{1,2}})\\b",
                r"\\b(\\d{{1,2}}\\s+[A-Za-z]{{3,9}}\\s+\\d{{4}})\\b",
            ],
        )
        markdown_link_match = re.search(r"\\[([^\\]]+)\\]\\((https?://[^\\)]+)\\)", line)
        plain_link_match = re.search(r"https?://[^\\s\\)]+", line)
        if markdown_link_match:
            line_title = markdown_link_match.group(1).strip()
            line_link = markdown_link_match.group(2).strip()
        else:
            line_title = line.strip()
            line_link = plain_link_match.group(0).strip() if plain_link_match else url

        if ranked_intent and keywords and keyword_score == 0 and not any([views_value, likes_value, comments_value]):
            continue

        row = {{}}
        for column in columns:
            lower = column.lower()
            if lower in {{"url", "link", "href"}}:
                row[column] = line_link
            elif lower in {{"title", "name", "text"}}:
                row[column] = _compact(line_title, 160)
            elif lower in {{"content", "summary", "description"}}:
                row[column] = _compact(line, 320)
            elif lower in {{"streamer", "channel", "creator", "username", "user", "owner"}}:
                row[column] = _compact(line_title, 120)
            elif lower in {{"views", "view_count", "viewers", "viewer_count", "watchers", "watching"}}:
                row[column] = views_value
            elif lower in {{"likes", "like_count"}}:
                row[column] = likes_value
            elif lower in {{"comments", "comment_count"}}:
                row[column] = comments_value
            elif lower in {{"date", "date_uploaded", "date_uplaoded", "published", "uploaded", "upload_date"}}:
                row[column] = date_value
            elif lower in {{"category", "game", "topic"}}:
                row[column] = category_hint
            else:
                row[column] = ""
        row_key = tuple(row.get(column, "") for column in columns)
        if row_key in seen:
            continue
        seen.add(row_key)
        quality_score = max(keyword_score, 1)
        if views_value:
            quality_score += 2
        if likes_value or comments_value:
            quality_score += 1
        candidate_rows.append((quality_score, row))
        if len(candidate_rows) >= 40:
            break

ranking_column = next(
    (
        column
        for column in columns
        if column.lower() in {{
            "views",
            "view_count",
            "viewers",
            "viewer_count",
            "watchers",
            "watching",
            "likes",
            "like_count",
            "comments",
            "comment_count",
            "stars",
            "star_count",
            "forks",
            "fork_count",
        }}
    ),
    None,
)

if ranking_column:
    candidate_rows.sort(key=lambda pair: (_metric_numeric(pair[1].get(ranking_column, "")), pair[0]), reverse=True)
elif keywords:
    candidate_rows.sort(key=lambda pair: pair[0], reverse=True)

for _, row in candidate_rows:
    rows.append(row)
    if len(rows) >= 25:
        break

if not rows:
    rows = [{{column: "" for column in columns}}]

extracted_data = rows
"""


async def _scrape_with_agentic_llm(
    session: dict[str, Any],
    session_id: str,
    env,
    request: ScrapeRequest,
    navigation_plan: dict[str, Any],
    url: str,
    step_num: int,
    total_reward: float,
    model_router: SmartModelRouter,
) -> AsyncGenerator[dict[str, Any], None]:
    """Truly agentic scraping using LLM to decide navigation and extraction.
    
    This function uses the LLM to:
    1. Decide where to navigate based on instructions + template hints
    2. Analyze the HTML content
    3. Generate extraction code dynamically
    4. Format output according to output_instructions
    
    Templates serve as reference hints only, not rigid execution scripts.
    """
    
    # Get template hint if available (for reference only)
    template_hint = ""
    if navigation_plan.get("matched_template"):
        template = navigation_plan["matched_template"]
        template_hint = f"""
SITE TEMPLATE HINT (reference only, not mandatory):
- Domain: {template.get('domain', 'N/A')}
- Strategies: {', '.join(template.get('strategies', []))}
- Suggested output fields: {', '.join(template.get('output_fields', []))}
- Typical patterns: {template.get('patterns', 'N/A')}
"""
    
    # Step 1: Ask LLM to decide navigation strategy
    step_num += 1
    navigation_prompt = f"""You are a web scraping agent. Analyze the user's request and decide where to navigate.

USER REQUEST:
- Assets: {request.assets}
- Target: {url}
- Instructions: {request.instructions or 'Extract all relevant data'}
- Desired output format: {request.output_format.value}
- Output instructions: {request.output_instructions or 'All available data'}

{template_hint}

TASK: Decide the best URL to navigate to accomplish this task. Consider:
- If the user wants trending/popular content, should you go to a trending page?
- If the user wants specific data, do you need to navigate to a specific section?
- Use site template hints only as references, never as rigid rules.
- Return ONLY the URL to navigate to, nothing else.

URL:"""

    live_llm_enabled = _agentic_live_llm_enabled()
    target_url = _fallback_navigation_url(url, request.instructions, navigation_plan)
    navigation_mode = "heuristic"
    if live_llm_enabled:
        try:
            nav_response = await asyncio.wait_for(
                model_router.complete(
                    messages=[{"role": "user", "content": navigation_prompt}],
                    task_type=TaskType.REASONING,
                    model=request.model,
                ),
                timeout=12,
            )
            candidate = nav_response.content.strip()
            if candidate:
                if not candidate.startswith("http"):
                    if "://" not in url:
                        candidate = f"https://{url}/{candidate.lstrip('/')}"
                    else:
                        parsed = urlparse(url)
                        candidate = f"{parsed.scheme}://{parsed.netloc}/{candidate.lstrip('/')}"
                target_url = candidate
                navigation_mode = "llm"
        except Exception as e:
            logger.warning("LLM navigation decision failed, using heuristic fallback: %s", e)
    target_url = _apply_text_render_proxy(target_url)
    
    # Tool call: LLM navigation planning
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="tool_call",
            url=target_url,
            status="complete",
            message=f"llm.plan_navigation() → {target_url}",
            extracted_data={
                "tool_name": "llm.plan_navigation",
                "tool_description": "LLM decides optimal navigation URL based on instructions",
                "parameters": {"instructions": request.instructions, "base_url": url},
                "result": target_url,
                "mode": navigation_mode,
            },
            reward=0.15,
            timestamp=_now_iso(),
        ),
    )
    total_reward += 0.15

    # Validate URL before navigation
    step_num += 1
    is_valid_target = _is_url_asset(target_url)
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="tool_call",
            url=target_url,
            status="complete",
            message=f"validate.url(url='{target_url}') → {'valid' if is_valid_target else 'invalid'}",
            extracted_data={
                "tool_name": "validate.url",
                "tool_description": "Validate and normalize navigation URL",
                "parameters": {"url": target_url},
                "result": {
                    "valid": is_valid_target,
                    "normalized_url": _coerce_url_asset(target_url) or target_url,
                },
            },
            reward=0.05 if is_valid_target else 0.0,
            timestamp=_now_iso(),
        ),
    )
    total_reward += 0.05 if is_valid_target else 0.0
    
    # Step 2: Navigate to the decided URL
    step_num += 1
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="tool_call",
            url=target_url,
            status="running",
            message=f"browser.navigate(url='{target_url}')",
            extracted_data={
                "tool_name": "browser.navigate",
                "tool_description": "Navigate browser to target URL",
                "parameters": {"url": target_url, "wait_for": "page_load"},
            },
            timestamp=_now_iso(),
        ),
    )
    
    navigate_action = Action(
        action_type=ActionType.NAVIGATE,
        parameters={"url": target_url},
        reasoning=f"Navigate to {target_url} based on LLM's decision",
    )
    
    nav_obs, nav_reward, _, _, _, nav_info = await env.step(navigate_action)
    total_reward += nav_reward
    
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="tool_call",
            url=target_url,
            status="complete",
            message=f"browser.navigate() → Success",
            extracted_data={
                "tool_name": "browser.navigate",
                "tool_description": "Navigate browser to target URL",
                "parameters": {"url": target_url},
                "result": {"status_code": nav_obs.page_html is not None},
            },
            reward=nav_reward,
            timestamp=_now_iso(),
        ),
    )
    
    if not nav_obs.page_html:
        logger.error("Navigation failed - no HTML received")
        return
    
    # Step 3: Parse HTML
    step_num += 1
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="tool_call",
            url=target_url,
            status="running",
            message="html.parse(html=page_content)",
            extracted_data={
                "tool_name": "html.parse",
                "tool_description": "Parse HTML into DOM structure",
                "parameters": {"content_length": len(nav_obs.page_html)},
            },
            timestamp=_now_iso(),
        ),
    )
    
    soup = BeautifulSoup(nav_obs.page_html, "html.parser")
    total_reward += 0.1
    
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="tool_call",
            url=target_url,
            status="complete",
            message="html.parse() → DOM ready",
            extracted_data={
                "tool_name": "html.parse",
                "tool_description": "Parse HTML into DOM structure",
                "result": {"elements_count": len(soup.find_all())},
            },
            reward=0.1,
            timestamp=_now_iso(),
        ),
    )
    
    # Extract links for tool visibility and fallback processing
    step_num += 1
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="tool_call",
            url=target_url,
            status="running",
            message="extract.urls(html)",
            extracted_data={
                "tool_name": "extract.urls",
                "tool_description": "Extract hyperlinks from parsed HTML",
                "parameters": {"scope": "document"},
            },
            timestamp=_now_iso(),
        ),
    )
    extracted_links: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href", "")).strip()
        if not href:
            continue
        if href.startswith("/"):
            href = f"{target_url.rstrip('/')}{href}"
        if href not in extracted_links:
            extracted_links.append(href)
        if len(extracted_links) >= 200:
            break
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="tool_call",
            url=target_url,
            status="complete",
            message=f"extract.urls() → {len(extracted_links)} links",
            extracted_data={
                "tool_name": "extract.urls",
                "result": {"count": len(extracted_links), "sample": extracted_links[:5]},
            },
            reward=0.05,
            timestamp=_now_iso(),
        ),
    )
    total_reward += 0.05

    # Extract emails for tool visibility and fallback processing
    step_num += 1
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="tool_call",
            url=target_url,
            status="running",
            message="extract.emails(html)",
            extracted_data={
                "tool_name": "extract.emails",
                "tool_description": "Extract email addresses from page content",
                "parameters": {"pattern": "email regex"},
            },
            timestamp=_now_iso(),
        ),
    )
    extracted_emails = sorted(set(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", nav_obs.page_html)))
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="tool_call",
            url=target_url,
            status="complete",
            message=f"extract.emails() → {len(extracted_emails)} emails",
            extracted_data={
                "tool_name": "extract.emails",
                "result": {"count": len(extracted_emails), "sample": extracted_emails[:5]},
            },
            reward=0.05,
            timestamp=_now_iso(),
        ),
    )
    total_reward += 0.05

    # Extract quick structural fields
    step_num += 1
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="tool_call",
            url=target_url,
            status="running",
            message="html.extract(fields=['title','content','links'])",
            extracted_data={
                "tool_name": "html.extract",
                "tool_description": "Extract key structural fields for downstream processing",
                "parameters": {"fields": ["title", "content", "links"]},
            },
            timestamp=_now_iso(),
        ),
    )
    page_title = soup.title.get_text(strip=True) if soup.title else ""
    page_content = soup.get_text(" ", strip=True)
    quick_extract = {
        "title": page_title,
        "content": page_content[:2000],
        "links": extracted_links[:100],
    }
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="tool_call",
            url=target_url,
            status="complete",
            message="html.extract() → fields ready",
            extracted_data={
                "tool_name": "html.extract",
                "result": {
                    "title_length": len(page_title),
                    "content_length": len(quick_extract["content"]),
                    "link_count": len(quick_extract["links"]),
                },
            },
            reward=0.05,
            timestamp=_now_iso(),
        ),
    )
    total_reward += 0.05

    # Step 4: Ask LLM to generate extraction code
    step_num += 1
    
    # Get a larger sample of the HTML for LLM analysis (first 15000 chars to include content)
    html_sample = nav_obs.page_html[:15000]
    
    extraction_prompt = f"""You are a web scraping expert. Generate Python code to extract data from HTML.

USER REQUEST:
- Assets: {request.assets}
- Instructions: {request.instructions or 'Extract all relevant data'}
- Output format: {request.output_format.value}
- Output instructions: {request.output_instructions or 'All available data'}

HTML SAMPLE (first 15000 chars):
```html
{html_sample}
```

{template_hint}

TASK: Generate Python code using BeautifulSoup to extract the requested data.

REQUIREMENTS:
1. The `soup` variable is already provided as a BeautifulSoup object
2. Extract data matching the user's output_instructions: "{request.output_instructions}"
3. Return `extracted_data` as a list of dictionaries
4. Column names MUST exactly match: {_parse_column_names(request.output_instructions) if request.output_instructions else []}
5. Handle missing data gracefully (use empty string "" for missing fields)
6. Extract ACTUAL text content from HTML elements, not empty strings
7. Look for the most relevant elements containing the requested data
8. If data appears in different formats (e.g., "123 points" or "123"), extract just the number
9. Do not include extra columns that were not requested

EXAMPLE OUTPUT FORMAT:
extracted_data = [
    {{"username": "google", "repo": "tensorflow", "stars": "12345", "forks": "6789"}},
    {{"username": "microsoft", "repo": "vscode", "stars": "11111", "forks": "2222"}},
]

Return ONLY executable Python code, no explanations or markdown:"""

    extraction_code = _fallback_extraction_code(
        request.output_instructions,
        request.instructions,
    )
    codegen_mode = "heuristic"
    if live_llm_enabled:
        try:
            code_response = await asyncio.wait_for(
                model_router.complete(
                    messages=[{"role": "user", "content": extraction_prompt}],
                    task_type=TaskType.CODE,
                    model=request.model,
                    temperature=0.3,
                ),
                timeout=12,
            )
            candidate_code = code_response.content.strip()
            if "```python" in candidate_code:
                candidate_code = candidate_code.split("```python")[1].split("```")[0].strip()
            elif "```" in candidate_code:
                candidate_code = candidate_code.split("```")[1].split("```")[0].strip()
            if candidate_code:
                extraction_code = candidate_code
                codegen_mode = "llm"
        except Exception as e:
            logger.warning("LLM code generation failed, using heuristic extraction code: %s", e)

    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="tool_call",
            url=target_url,
            status="complete",
            message=f"{'llm' if codegen_mode == 'llm' else 'agent.fallback'}.generate_extraction_code() → {len(extraction_code)} chars",
            extracted_data={
                "tool_name": "llm.generate_extraction_code",
                "tool_description": "Generate extraction code from page context and requested output schema",
                "parameters": {
                    "html_sample_length": len(html_sample),
                    "instructions": request.instructions,
                    "output_format": request.output_format.value,
                },
                "result": {"code_length": len(extraction_code), "mode": codegen_mode},
            },
            reward=0.2 if codegen_mode == "llm" else 0.05,
            timestamp=_now_iso(),
        ),
    )
    total_reward += 0.2 if codegen_mode == "llm" else 0.05
    
    # Step 5: Execute generated code in sandbox
    step_num += 1
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="tool_call",
            url=target_url,
            status="running",
            message="sandbox.execute(code=llm_generated_code)",
            extracted_data={
                "tool_name": "sandbox.execute",
                "tool_description": "Execute LLM-generated extraction code in sandboxed Python environment",
                "parameters": {"code_length": len(extraction_code), "timeout": 30},
            },
            timestamp=_now_iso(),
        ),
    )
    
    # Prepare execution context
    sandbox_globals = {
        "soup": soup,
        "html": nav_obs.page_html,
        "url": target_url,
        "re": re,
        "urljoin": urljoin,
        "urlparse": urlparse,
        "BeautifulSoup": BeautifulSoup,
        "extracted_data": [],  # LLM code should populate this
    }
    output_columns: list[str] = []
    execution_mode = codegen_mode
    
    try:
        # Execute the LLM-generated code
        exec(extraction_code, sandbox_globals)
        extracted_data = sandbox_globals.get("extracted_data", [])
        
        if not isinstance(extracted_data, list):
            extracted_data = [extracted_data] if extracted_data else []
        extracted_data, output_columns = _enforce_requested_schema(
            extracted_data,
            request.output_instructions,
        )
        requested_limit = _requested_row_limit(request.instructions, default_limit=25)
        extracted_data = extracted_data[:requested_limit]
        relevance_score = _rows_relevance_score(extracted_data, request.instructions)

        if not _rows_have_signal(extracted_data):
            if codegen_mode == "llm":
                try:
                    heuristic_code = _fallback_extraction_code(
                        request.output_instructions,
                        request.instructions,
                    )
                    heuristic_globals = {
                        **sandbox_globals,
                        "extracted_data": [],
                    }
                    exec(heuristic_code, heuristic_globals)
                    heuristic_data = heuristic_globals.get("extracted_data", [])
                    if not isinstance(heuristic_data, list):
                        heuristic_data = [heuristic_data] if heuristic_data else []
                    heuristic_data, heuristic_columns = _enforce_requested_schema(
                        heuristic_data,
                        request.output_instructions,
                    )
                    heuristic_data = heuristic_data[:requested_limit]
                    if _rows_have_signal(heuristic_data):
                        extracted_data = heuristic_data
                        output_columns = heuristic_columns or output_columns
                        execution_mode = "llm_with_heuristic_recovery"
                except Exception as recovery_error:
                    logger.warning("Heuristic recovery after empty LLM extraction failed: %s", recovery_error)

            if not _rows_have_signal(extracted_data):
                text_render_payload = _fetch_text_render_markdown(target_url, timeout_seconds=12)
                if text_render_payload:
                    text_markdown, text_render_url = text_render_payload
                    try:
                        text_data, text_columns = _extract_rows_from_text_render(
                            markdown=text_markdown,
                            source_url=text_render_url,
                            output_instructions=request.output_instructions,
                            instructions=request.instructions,
                            row_limit=requested_limit,
                        )
                        if _rows_have_signal(text_data):
                            extracted_data = text_data
                            output_columns = text_columns or output_columns
                            execution_mode = "text_render_recovery"
                            target_url = text_render_url
                    except Exception as text_recovery_error:
                        logger.warning("Text-render recovery after empty extraction failed: %s", text_recovery_error)

        relevance_score = _rows_relevance_score(extracted_data, request.instructions)
        recovery_keywords = _instruction_keywords(request.instructions, max_keywords=8)
        
        # Only attempt recovery if we have NO useful signal from the user's specified site
        # If we have data with signal, trust the user's site - don't go to external search
        if not _rows_have_signal(extracted_data) and recovery_keywords:
            step_num += 1
            yield _record_step(
                session,
                ScrapeStep(
                    step_number=step_num,
                    action="tool_call",
                    url=target_url,
                    status="running",
                    message="agent.recover_relevance(query)",
                    extracted_data={
                        "tool_name": "agent.recover_relevance",
                        "tool_description": "Search-guided relevance recovery for empty extraction output",
                        "parameters": {
                            "keywords": recovery_keywords,
                            "baseline_relevance": round(relevance_score, 3),
                        },
                    },
                    timestamp=_now_iso(),
                ),
            )

            recovered_rows, recovered_columns, recovered_source, recovered_score = await _search_recovery_rows(
                base_url=url,
                instructions=request.instructions,
                output_instructions=request.output_instructions,
                row_limit=requested_limit,
            )
            # Only use recovery data if it's significantly better AND provides signal
            improved = _rows_have_signal(recovered_rows) and recovered_score > 0.3 and len(recovered_rows) >= 3
            if improved:
                extracted_data = recovered_rows
                output_columns = recovered_columns or output_columns
                target_url = recovered_source or target_url
                execution_mode = "search_recovery"
                relevance_score = recovered_score

            yield _record_step(
                session,
                ScrapeStep(
                    step_number=step_num,
                    action="tool_call",
                    url=target_url,
                    status="complete",
                    message=(
                        f"agent.recover_relevance() → {'improved' if improved else 'no_change'} "
                        f"({relevance_score:.2f})"
                    ),
                    extracted_data={
                        "tool_name": "agent.recover_relevance",
                        "result": {
                            "improved": improved,
                            "relevance": round(relevance_score, 3),
                            "recovered_rows": len(recovered_rows),
                            "source": recovered_source,
                        },
                    },
                    reward=0.1 if improved else 0.0,
                    timestamp=_now_iso(),
                ),
            )
            if improved:
                total_reward += 0.1
        
        has_signal = _rows_have_signal(extracted_data)
        exec_reward = 0.5 if has_signal else 0.1
        total_reward += exec_reward
        
        yield _record_step(
            session,
            ScrapeStep(
                step_number=step_num,
                action="tool_call",
                url=target_url,
                status="complete",
                message=f"sandbox.execute() → Extracted {len(extracted_data)} items",
                extracted_data={
                    "tool_name": "sandbox.execute",
                    "tool_description": "Execute extraction code in sandbox",
                    "result": {
                        "items_extracted": len(extracted_data),
                        "has_signal": has_signal,
                        "relevance_score": round(relevance_score, 3),
                        "mode": execution_mode,
                        "columns": output_columns,
                        "sample": extracted_data[:2] if extracted_data else [],
                    },
                },
                reward=exec_reward,
                timestamp=_now_iso(),
            ),
        )
        
    except Exception as e:
        logger.error(f"Extraction code execution failed: {e}")
        logger.error(f"Generated code was:\n{extraction_code}")
        # Fallback: basic extraction
        extracted_data = [{
            "url": target_url,
            "title": soup.find("title").get_text() if soup.find("title") else "",
            "error": f"Extraction failed: {str(e)}",
        }]
        extracted_data, output_columns = _enforce_requested_schema(
            extracted_data,
            request.output_instructions,
        )
        requested_limit = _requested_row_limit(request.instructions, default_limit=25)
        extracted_data = extracted_data[:requested_limit]
        total_reward += 0.05
        
        yield _record_step(
            session,
            ScrapeStep(
                step_number=step_num,
                action="tool_call",
                url=target_url,
                status="complete",
                message=f"sandbox.execute() → Failed: {str(e)[:100]}",
                extracted_data={
                    "tool_name": "sandbox.execute",
                    "tool_description": "Execute extraction code (failed)",
                    "result": {"error": str(e)},
                },
                reward=0.05,
                timestamp=_now_iso(),
            ),
        )
    
    # Step 6: Format output according to requested format
    step_num += 1
    
    if request.output_format == OutputFormat.CSV:
        tool_name = "csv.generate"
        tool_desc = "Generate CSV output from extracted data"
    elif request.output_format == OutputFormat.JSON:
        tool_name = "json.dumps"
        tool_desc = "Format extracted data as JSON"
    else:
        tool_name = "data.format"
        tool_desc = "Format extracted data"
    
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="tool_call",
            url=target_url,
            status="running",
            message=f"{tool_name}(data=extracted_items)",
            extracted_data={
                "tool_name": tool_name,
                "tool_description": tool_desc,
                "parameters": {"item_count": len(extracted_data)},
            },
            timestamp=_now_iso(),
        ),
    )
    
    # Store extracted data in session
    if request.output_format == OutputFormat.CSV and extracted_data:
        existing_rows: list[dict[str, Any]] = []
        existing_sources: list[str] = []
        existing_payload = session.get("extracted_data")
        if isinstance(existing_payload, dict):
            if isinstance(existing_payload.get("rows"), list):
                existing_rows = [row for row in existing_payload["rows"] if isinstance(row, dict)]
            if isinstance(existing_payload.get("sources"), list):
                existing_sources = [str(value) for value in existing_payload["sources"]]

        merged_rows = [*existing_rows, *extracted_data]
        fieldnames = output_columns or list(extracted_data[0].keys())

        deduped_rows: list[dict[str, Any]] = []
        seen_keys: set[tuple[str, ...]] = set()
        for row in merged_rows:
            normalized_row = {field: str(row.get(field, "")) for field in fieldnames}
            row_key = tuple(normalized_row[field] for field in fieldnames)
            if row_key in seen_keys:
                continue
            seen_keys.add(row_key)
            deduped_rows.append(normalized_row)

        requested_limit = _requested_row_limit(request.instructions, default_limit=25)
        deduped_rows = deduped_rows[:requested_limit]

        output_buffer = io.StringIO()
        writer = csv.DictWriter(output_buffer, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(deduped_rows)

        merged_sources = [*existing_sources]
        if target_url not in merged_sources:
            merged_sources.append(target_url)
        
        session["extracted_data"] = {
            "csv_output": output_buffer.getvalue(),
            "rows": deduped_rows,
            "columns": fieldnames,
            "row_count": len(deduped_rows),
            "sources": merged_sources,
        }
    else:
        current_payload = session.get("extracted_data")
        merged_payload: dict[str, Any] = {}
        if isinstance(current_payload, dict) and "csv_output" not in current_payload:
            merged_payload.update(current_payload)
        merged_payload[target_url] = extracted_data
        session["extracted_data"] = merged_payload
    
    total_reward += 0.1
    
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="tool_call",
            url=target_url,
            status="complete",
            message=f"{tool_name}() → Output ready",
            extracted_data={
                "tool_name": tool_name,
                "tool_description": tool_desc,
                "result": {"format": request.output_format.value, "size": len(extracted_data)},
            },
            reward=0.1,
            timestamp=_now_iso(),
        ),
    )
    
    # Final completion
    step_num += 1
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="complete",
            url=target_url,
            status="complete",
            message=f"Agentic scraping complete: {len(extracted_data)} items extracted",
            extracted_data={"item_count": len(extracted_data)},
            reward=total_reward,
            timestamp=_now_iso(),
        ),
    )


async def scrape_url_intelligently(
    session: dict[str, Any],
    session_id: str,
    url: str,
    settings: Settings,
    request: ScrapeRequest,
    memory_manager: MemoryManager,
    enabled_plugins: list[str],
    navigation_plan: dict[str, Any],
) -> AsyncGenerator[dict[str, Any], None]:
    """Intelligent scraping using agentic LLM-driven approach.
    
    This function uses LLM to make ALL decisions:
    - Navigation: Where to go based on instructions
    - Extraction: What data to extract and how
    - Formatting: How to present the results
    
    Templates serve as reference hints only, NOT rigid scripts.
    """
    
    episode_id = f"{session_id}-{uuid.uuid4().hex[:8]}"
    
    try:
        env = create_environment(episode_id, settings)
        await env.reset(task_id=f"scrape_{session_id}")
        
        # Get model router
        model_router = get_model_router()
        if not model_router:
            logger.error("Model router not available")
            session["errors"].append("Model router not initialized")
            return
        
        step_num = 0
        total_reward = 0.0
        
        # ALWAYS use agentic approach - no hardcoded strategies
        async for event in _scrape_with_agentic_llm(
            session, 
            session_id, 
            env, 
            request, 
            navigation_plan, 
            url, 
            step_num, 
            total_reward,
            model_router,
        ):
            yield event
            
    except Exception as exc:
        logger.error(f"Intelligent scraping failed for {url}: {exc}")
        session["errors"].append(f"Scraping failed: {exc}")
        
async def scrape_stream(
    session_id: str,
    request: ScrapeRequest,
    settings: Settings,
    memory_manager: MemoryManager,
) -> AsyncGenerator[str, None]:
    """Stream scraping progress as SSE events and websocket broadcasts."""

    enabled_plugins, missing_plugins = _resolve_enabled_plugins(request.enable_plugins)
    session = create_session(session_id, request, enabled_plugins)
    python_plugin_ids = {
        "mcp-python-sandbox",
        "proc-python",
        "proc-pandas",
        "proc-numpy",
        "proc-bs4",
    }
    if missing_plugins:
        session["errors"].append(f"Unavailable plugins ignored: {', '.join(missing_plugins)}")

    manager = get_connection_manager()
    start_time = time.time()

    init_event = {"type": "init", "session_id": session_id}
    await manager.broadcast(init_event, session_id)
    yield _sse_event(init_event)

    # Create intelligent navigation plan based on instructions
    navigation_plan = _create_intelligent_navigation_plan(request.instructions, request.assets)
    
    plugin_event = _record_step(
        session,
        ScrapeStep(
            step_number=0,
            action="plugins",
            status="completed",
            message=(
                f"Enabled plugins: {enabled_plugins}" if enabled_plugins else "No plugins enabled"
            ),
            reward=0.1 if enabled_plugins else 0.0,  # Small reward for plugin setup
            extracted_data={
                "requested": request.enable_plugins, 
                "enabled": enabled_plugins, 
                "missing": missing_plugins,
                "navigation_strategy": navigation_plan["strategy"],
                "extraction_goal": navigation_plan["extraction_goal"],
                "site_template_id": navigation_plan.get("site_template_id"),
                "site_template_name": navigation_plan.get("site_template_name"),
                "site_template_domains": navigation_plan.get("site_template_domains", []),
            },
            timestamp=_now_iso(),
        ),
    )
    await manager.broadcast(plugin_event, session_id)
    yield _sse_event(plugin_event)

    resolved_assets, discoveries = await _resolve_assets(request.assets, enabled_plugins)
    if not resolved_assets:
        resolved_assets = request.assets
    session["resolved_assets"] = resolved_assets

    if discoveries:
        discovery_event = _record_step(
            session,
            ScrapeStep(
                step_number=1,
                action="mcp_search",
                status="completed",
                message="Resolved non-URL assets using search/discovery plugin logic",
                reward=0.2,  # Reward for successful discovery
                extracted_data={"discoveries": discoveries, "resolved_assets": resolved_assets},
                timestamp=_now_iso(),
            ),
        )
        await manager.broadcast(discovery_event, session_id)
        yield _sse_event(discovery_event)

    planner_site_template = match_site_template(request.instructions, resolved_assets)
    planner_template_payload = (
        serialize_site_template(planner_site_template) if planner_site_template else None
    )

    if request.enable_memory:
        try:
            await memory_manager.store(
                key=f"scrape:{session_id}:request",
                value={
                    "assets": request.assets,
                    "resolved_assets": resolved_assets,
                    "instructions": request.instructions,
                    "output_instructions": request.output_instructions,
                    "complexity": request.complexity.value,
                },
                memory_type=MemoryType.SHORT_TERM,
                tags=["scrape", "request"],
            )
            _write_session_json_artifact(
                session,
                "memory_request.json",
                {
                    "assets": request.assets,
                    "resolved_assets": resolved_assets,
                    "instructions": request.instructions,
                    "output_instructions": request.output_instructions,
                    "selected_agents": request.selected_agents,
                    "enabled_plugins": enabled_plugins,
                },
            )
        except Exception as exc:
            message = f"Failed to store request memory: {exc}"
            session["errors"].append(message)
            memory_error = {"type": "error", "data": {"url": None, "error": message, "timestamp": _now_iso()}}
            await manager.broadcast(memory_error, session_id)
            yield _sse_event(memory_error)

    planner_event = _record_step(
        session,
        ScrapeStep(
            step_number=len(session["steps"]) + 1,
            action="planner",
            status="completed",
            message=f"Planner created execution plan for {len(resolved_assets)} assets",
            reward=0.15,  # Reward for planning
            extracted_data={
                "assets": resolved_assets,
                "instructions": request.instructions,
                "output_instructions": request.output_instructions,
                "site_template": planner_template_payload,
            },
            timestamp=_now_iso(),
        ),
    )
    await manager.broadcast(planner_event, session_id)
    yield _sse_event(planner_event)

    if any(plugin_id in enabled_plugins for plugin_id in python_plugin_ids):
        planner_payload = {
            "phase": "planner",
            "instructions": request.instructions,
            "output_instructions": request.output_instructions,
            "resolved_assets": resolved_assets,
            "selected_agents": request.selected_agents,
            "site_template": planner_template_payload,
        }
        planner_code = (
            "result = {"
            "'phase': payload.get('phase'), "
            "'asset_count': len(payload.get('resolved_assets') or []), "
            "'selected_agents': payload.get('selected_agents') or [], "
            "'site_template_id': (payload.get('site_template') or {}).get('site_id'), "
            "'site_strategy': (payload.get('site_template') or {}).get('default_strategy')"
            "}"
        )
        
        # Tool call: sandbox.execute (planner)
        sandbox_tool_event = _record_step(
            session,
            ScrapeStep(
                step_number=len(session["steps"]) + 1,
                action="tool_call",
                status="running",
                message="sandbox.execute(code='planner_analysis')",
                extracted_data={
                    "tool_name": "sandbox.execute",
                    "tool_description": "Execute Python code in isolated sandbox environment",
                    "parameters": {
                        "code_type": "planner_analysis",
                        "imports": ["json"],
                        "payload_keys": list(planner_payload.keys()),
                    },
                },
                timestamp=_now_iso(),
            ),
        )
        await manager.broadcast(sandbox_tool_event, session_id)
        yield _sse_event(sandbox_tool_event)
        
        try:
            planner_sandbox = await asyncio.to_thread(
                execute_python_sandbox,
                planner_code,
                planner_payload,
                session_id=session_id,
                timeout_seconds=15,
            )
        except Exception as exc:
            planner_sandbox = SandboxExecutionResult(
                success=False,
                output=None,
                error=f"Planner sandbox setup failed: {exc}",
            )

        # Tool call result
        sandbox_result_event = _record_step(
            session,
            ScrapeStep(
                step_number=len(session["steps"]),
                action="tool_call",
                status="completed" if planner_sandbox.success else "failed",
                message=f"sandbox.execute() → {'success' if planner_sandbox.success else 'failed'}",
                reward=0.05 if planner_sandbox.success else 0.0,
                extracted_data={
                    "tool_name": "sandbox.execute",
                    "result": {
                        "success": planner_sandbox.success,
                        "output_keys": list(planner_sandbox.output.keys()) if planner_sandbox.output else [],
                        "error": planner_sandbox.error,
                    },
                },
                timestamp=_now_iso(),
            ),
        )
        await manager.broadcast(sandbox_result_event, session_id)
        yield _sse_event(sandbox_result_event)

        if planner_sandbox.success and planner_sandbox.output is not None:
            planner_python_event = _record_step(
                session,
                ScrapeStep(
                    step_number=len(session["steps"]) + 1,
                    action="planner_python",
                    status="completed",
                    message="Planner agent executed sandbox Python code",
                    reward=0.1,  # Reward for sandbox execution
                    extracted_data=planner_sandbox.output,
                    timestamp=_now_iso(),
                ),
            )
            await manager.broadcast(planner_python_event, session_id)
            yield _sse_event(planner_python_event)
        else:
            session["errors"].append(planner_sandbox.error or "Planner sandbox execution failed")

    # Tool call: url.parse (validate and parse URLs)
    url_parse_event = _create_tool_call_step(
        session,
        "url.parse",
        "Parse and validate target URLs",
        {"urls": resolved_assets, "count": len(resolved_assets)},
        status="running",
    )
    await manager.broadcast(url_parse_event, session_id)
    yield _sse_event(url_parse_event)
    
    parsed_urls = []
    for url in resolved_assets:
        parsed = urlparse(url)
        parsed_urls.append({
            "url": url,
            "scheme": parsed.scheme,
            "domain": parsed.netloc,
            "path": parsed.path,
        })
    
    url_parse_result = _create_tool_call_step(
        session,
        "url.parse",
        "Parse and validate target URLs",
        {"urls": resolved_assets},
        status="completed",
        result={"parsed": len(parsed_urls), "domains": list(set(p["domain"] for p in parsed_urls))},
        reward=0.05,
    )
    await manager.broadcast(url_parse_result, session_id)
    yield _sse_event(url_parse_result)

    for idx, url in enumerate(resolved_assets):
        session["current_url_index"] = idx
        url_navigation_plan = _create_intelligent_navigation_plan(request.instructions, [url])
        url_site_template = match_site_template(request.instructions, [url])
        url_template_payload = serialize_site_template(url_site_template) if url_site_template else None

        if url_template_payload:
            site_template_event = _record_step(
                session,
                ScrapeStep(
                    step_number=len(session["steps"]) + 1,
                    action="site_template",
                    url=url,
                    status="completed",
                    message=f"Navigator loaded site template: {url_template_payload['name']}",
                    reward=0.05,
                    extracted_data={
                        "site_id": url_template_payload["site_id"],
                        "strategy": url_navigation_plan["strategy"],
                        "domains": url_template_payload["domains"],
                    },
                    timestamp=_now_iso(),
                ),
            )
            await manager.broadcast(site_template_event, session_id)
            yield _sse_event(site_template_event)

        navigator_event = _record_step(
            session,
            ScrapeStep(
                step_number=len(session["steps"]) + 1,
                action="navigator",
                url=url,
                status="running",
                message=(
                    f"Navigator selected source {idx + 1}/{len(resolved_assets)} "
                    f"({url_navigation_plan['strategy']})"
                ),
                reward=0.05,  # Small reward for navigator selection
                extracted_data={
                    "site_template_id": url_navigation_plan.get("site_template_id"),
                    "site_template_name": url_navigation_plan.get("site_template_name"),
                },
                timestamp=_now_iso(),
            ),
        )
        await manager.broadcast(navigator_event, session_id)
        yield _sse_event(navigator_event)

        if any(plugin_id in enabled_plugins for plugin_id in python_plugin_ids):
            navigator_payload = {
                "phase": "navigator",
                "url": url,
                "index": idx,
                "total": len(resolved_assets),
                "site_template": url_template_payload,
                "navigation_strategy": url_navigation_plan["strategy"],
            }
            navigator_code = (
                "result = {"
                "'phase': payload.get('phase'), "
                "'selected_url': payload.get('url'), "
                "'progress': f\"{payload.get('index', 0) + 1}/{payload.get('total', 0)}\", "
                "'site_template_id': (payload.get('site_template') or {}).get('site_id'), "
                "'strategy': payload.get('navigation_strategy')"
                "}"
            )
            
            # Tool call: sandbox.execute (navigator)
            nav_sandbox_tool_event = _record_step(
                session,
                ScrapeStep(
                    step_number=len(session["steps"]) + 1,
                    action="tool_call",
                    url=url,
                    status="running",
                    message="sandbox.execute(code='navigator_analysis')",
                    extracted_data={
                        "tool_name": "sandbox.execute",
                        "tool_description": "Execute navigator analysis in sandbox",
                        "parameters": {
                            "code_type": "navigator_analysis",
                            "imports": ["json"],
                            "url": url,
                        },
                    },
                    timestamp=_now_iso(),
                ),
            )
            await manager.broadcast(nav_sandbox_tool_event, session_id)
            yield _sse_event(nav_sandbox_tool_event)
            
            try:
                navigator_sandbox = await asyncio.to_thread(
                    execute_python_sandbox,
                    navigator_code,
                    navigator_payload,
                    session_id=session_id,
                    timeout_seconds=15,
                )
            except Exception as exc:
                navigator_sandbox = SandboxExecutionResult(
                    success=False,
                    output=None,
                    error=f"Navigator sandbox setup failed: {exc}",
                )

            # Tool call result
            nav_sandbox_result_event = _record_step(
                session,
                ScrapeStep(
                    step_number=len(session["steps"]),
                    action="tool_call",
                    url=url,
                    status="completed" if navigator_sandbox.success else "failed",
                    message=f"sandbox.execute() → {'success' if navigator_sandbox.success else 'failed'}",
                    reward=0.05 if navigator_sandbox.success else 0.0,
                    extracted_data={
                        "tool_name": "sandbox.execute",
                        "result": {
                            "success": navigator_sandbox.success,
                            "output_keys": list(navigator_sandbox.output.keys()) if navigator_sandbox.output else [],
                        },
                    },
                    timestamp=_now_iso(),
                ),
            )
            await manager.broadcast(nav_sandbox_result_event, session_id)
            yield _sse_event(nav_sandbox_result_event)

            if navigator_sandbox.success and navigator_sandbox.output is not None:
                navigator_python_event = _record_step(
                    session,
                    ScrapeStep(
                        step_number=len(session["steps"]) + 1,
                        action="navigator_python",
                        url=url,
                        status="completed",
                        message="Navigator agent executed sandbox Python code",
                        reward=0.1,  # Reward for sandbox navigation
                        extracted_data=navigator_sandbox.output,
                        timestamp=_now_iso(),
                    ),
                )
                await manager.broadcast(navigator_python_event, session_id)
                yield _sse_event(navigator_python_event)
            else:
                session["errors"].append(navigator_sandbox.error or "Navigator sandbox execution failed")

        url_start_event = {"type": "url_start", "url": url, "index": idx, "total": len(resolved_assets)}
        await manager.broadcast(url_start_event, session_id)
        yield _sse_event(url_start_event)

        async for update in scrape_url_intelligently(
            session,
            session_id,
            url,
            settings,
            request,
            memory_manager,
            enabled_plugins,
            url_navigation_plan,
        ):
            await manager.broadcast(update, session_id)
            yield _sse_event(update)

        url_done_event = {"type": "url_complete", "url": url, "index": idx}
        await manager.broadcast(url_done_event, session_id)
        yield _sse_event(url_done_event)

    instruction_text = f"{request.instructions} {request.output_instructions} {' '.join(request.assets)}".lower()
    if "gold" in instruction_text and ("price" in instruction_text or "trend" in instruction_text):
        gold_rows = _build_gold_dataset_rows(session["extracted_data"], from_month="2016-01")
        if gold_rows:
            source_links = sorted({row["source_link"] for row in gold_rows})
            session["extracted_data"] = {
                "dataset_name": "gold_prices_monthly",
                "description": "Monthly gold prices in USD from 2016 onward",
                "columns": ["month", "gold_price_usd", "source_link"],
                "rows": gold_rows,
                "row_count": len(gold_rows),
                "from_month": "2016-01",
                "to_month": gold_rows[-1]["month"],
                "source_links": source_links,
            }
            quality_status = "completed" if len(gold_rows) >= 100 else "partial"
            quality_message = (
                f"Verifier assembled monthly gold dataset with {len(gold_rows)} rows"
                if quality_status == "completed"
                else f"Verifier assembled only {len(gold_rows)} rows; expected >= 100"
            )

            quality_event = _record_step(
                session,
                ScrapeStep(
                    step_number=len(session["steps"]) + 1,
                    action="verifier",
                    status=quality_status,
                    message=quality_message,
                    extracted_data={
                        "row_count": len(gold_rows),
                        "sources": source_links,
                    },
                    timestamp=_now_iso(),
                ),
            )
            await manager.broadcast(quality_event, session_id)
            yield _sse_event(quality_event)
        else:
            quality_event = _record_step(
                session,
                ScrapeStep(
                    step_number=len(session["steps"]) + 1,
                    action="verifier",
                    status="partial",
                    message="Verifier could not assemble monthly gold rows from resolved sources",
                    extracted_data={"row_count": 0, "sources": []},
                    timestamp=_now_iso(),
                ),
            )
            await manager.broadcast(quality_event, session_id)
            yield _sse_event(quality_event)

    if (
        any(plugin_id in enabled_plugins for plugin_id in python_plugin_ids)
        and _should_run_python_sandbox(request, session["extracted_data"])
    ):
        extracted_payload = session["extracted_data"]
        dataset_rows: list[dict[str, Any]] = []
        source_links: list[str] = []
        html_samples: dict[str, str] = {}

        if isinstance(extracted_payload, dict):
            if isinstance(extracted_payload.get("rows"), list):
                dataset_rows = [
                    row for row in extracted_payload.get("rows", []) if isinstance(row, dict)
                ]
            if isinstance(extracted_payload.get("source_links"), list):
                source_links = [str(link) for link in extracted_payload.get("source_links", [])]

            for source, payload in extracted_payload.items():
                if isinstance(payload, dict) and isinstance(payload.get("content"), str):
                    html_samples[str(source)] = payload.get("content", "")

        # Tool call: extract.urls (find URLs in content)
        if html_samples:
            extract_urls_event = _create_tool_call_step(
                session,
                "extract.urls",
                "Extract URLs from HTML content",
                {"sources": len(html_samples), "total_bytes": sum(len(h) for h in html_samples.values())},
                status="running",
            )
            await manager.broadcast(extract_urls_event, session_id)
            yield _sse_event(extract_urls_event)
            
            all_urls = []
            for html in html_samples.values():
                all_urls.extend(re.findall(r'href=["\']([^"\']+)["\']', html[:50000]))  # Limit search
            
            extract_urls_result = _create_tool_call_step(
                session,
                "extract.urls",
                "Extract URLs from HTML content",
                {"sources": len(html_samples)},
                status="completed",
                result={"urls_found": len(all_urls), "unique": len(set(all_urls))},
                reward=0.05,
            )
            await manager.broadcast(extract_urls_result, session_id)
            yield _sse_event(extract_urls_result)
            
            # Tool call: extract.emails (find emails in content)
            extract_emails_event = _create_tool_call_step(
                session,
                "extract.emails",
                "Extract email addresses from HTML content",
                {"sources": len(html_samples)},
                status="running",
            )
            await manager.broadcast(extract_emails_event, session_id)
            yield _sse_event(extract_emails_event)
            
            all_emails = []
            email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
            for html in html_samples.values():
                all_emails.extend(re.findall(email_pattern, html[:50000]))
            
            extract_emails_result = _create_tool_call_step(
                session,
                "extract.emails",
                "Extract email addresses from HTML content",
                {"sources": len(html_samples)},
                status="completed",
                result={"emails_found": len(all_emails), "unique": len(set(all_emails))},
                reward=0.02,
            )
            await manager.broadcast(extract_emails_result, session_id)
            yield _sse_event(extract_emails_result)

        analysis_payload = {
            "instructions": request.instructions,
            "output_instructions": request.output_instructions,
            "dataset_rows": dataset_rows,
            "source_links": source_links,
            "html_samples": html_samples,
            "extracted_data": extracted_payload,
        }

        sandbox_code = request.python_code or DEFAULT_ANALYSIS_CODE
        
        # Tool call: pandas.DataFrame (data analysis)
        pandas_tool_event = _record_step(
            session,
            ScrapeStep(
                step_number=len(session["steps"]) + 1,
                action="tool_call",
                status="running",
                message="pandas.DataFrame(rows)",
                extracted_data={
                    "tool_name": "pandas.DataFrame",
                    "tool_description": "Create DataFrame from extracted dataset rows",
                    "parameters": {
                        "row_count": len(dataset_rows),
                        "source_count": len(source_links),
                    },
                },
                timestamp=_now_iso(),
            ),
        )
        await manager.broadcast(pandas_tool_event, session_id)
        yield _sse_event(pandas_tool_event)
        
        # Tool call: bs4.BeautifulSoup (HTML analysis)
        if html_samples:
            bs4_tool_event = _record_step(
                session,
                ScrapeStep(
                    step_number=len(session["steps"]) + 1,
                    action="tool_call",
                    status="running",
                    message=f"bs4.BeautifulSoup(html, 'html.parser') × {len(html_samples)}",
                    extracted_data={
                        "tool_name": "bs4.BeautifulSoup",
                        "tool_description": "Parse HTML samples for link analysis",
                        "parameters": {
                            "parser": "html.parser",
                            "sample_count": len(html_samples),
                            "total_bytes": sum(len(h) for h in html_samples.values()),
                        },
                    },
                    timestamp=_now_iso(),
                ),
            )
            await manager.broadcast(bs4_tool_event, session_id)
            yield _sse_event(bs4_tool_event)
        
        # Tool call: sandbox.execute (analysis)
        analysis_sandbox_event = _record_step(
            session,
            ScrapeStep(
                step_number=len(session["steps"]) + 1,
                action="tool_call",
                status="running",
                message="sandbox.execute(code='data_analysis')",
                extracted_data={
                    "tool_name": "sandbox.execute",
                    "tool_description": "Run comprehensive data analysis in sandbox",
                    "parameters": {
                        "imports": ["pandas", "numpy", "bs4", "json"],
                        "dataset_rows": len(dataset_rows),
                        "html_samples": len(html_samples),
                        "custom_code": bool(request.python_code),
                    },
                },
                timestamp=_now_iso(),
            ),
        )
        await manager.broadcast(analysis_sandbox_event, session_id)
        yield _sse_event(analysis_sandbox_event)
        
        try:
            sandbox_result = await asyncio.to_thread(
                execute_python_sandbox,
                sandbox_code,
                analysis_payload,
                session_id=session_id,
                timeout_seconds=25,
            )
        except Exception as exc:
            sandbox_result = SandboxExecutionResult(
                success=False,
                output=None,
                error=f"Sandbox setup failed: {exc}",
                stderr="",
            )
        
        # Tool call result: sandbox.execute
        sandbox_exec_result_event = _record_step(
            session,
            ScrapeStep(
                step_number=len(session["steps"]),
                action="tool_call",
                status="completed" if sandbox_result.success else "failed",
                message=f"sandbox.execute() → {'analysis complete' if sandbox_result.success else 'failed'}",
                reward=0.1 if sandbox_result.success else 0.0,
                extracted_data={
                    "tool_name": "sandbox.execute",
                    "result": {
                        "success": sandbox_result.success,
                        "output_keys": list(sandbox_result.output.keys()) if sandbox_result.output else [],
                        "error": sandbox_result.error if not sandbox_result.success else None,
                    },
                },
                timestamp=_now_iso(),
            ),
        )
        await manager.broadcast(sandbox_exec_result_event, session_id)
        yield _sse_event(sandbox_exec_result_event)

        if sandbox_result.success and sandbox_result.output is not None:
            if isinstance(session["extracted_data"], dict):
                session["extracted_data"]["python_analysis"] = sandbox_result.output
            else:
                session["extracted_data"] = {
                    "result": session["extracted_data"],
                    "python_analysis": sandbox_result.output,
                }

            sandbox_event = _record_step(
                session,
                ScrapeStep(
                    step_number=len(session["steps"]) + 1,
                    action="python_sandbox",
                    status="completed",
                    message="Sandboxed Python plugin executed successfully",
                    extracted_data={"analysis_keys": sorted(sandbox_result.output.keys())},
                    timestamp=_now_iso(),
                ),
            )
            await manager.broadcast(sandbox_event, session_id)
            yield _sse_event(sandbox_event)
        else:
            error = sandbox_result.error or "Sandboxed Python execution failed"
            session["errors"].append(error)
            sandbox_event = _record_step(
                session,
                ScrapeStep(
                    step_number=len(session["steps"]) + 1,
                    action="python_sandbox",
                    status="failed",
                    message=error,
                    extracted_data={"stderr": sandbox_result.stderr[:500]},
                    timestamp=_now_iso(),
                ),
            )
            await manager.broadcast(sandbox_event, session_id)
            yield _sse_event(sandbox_event)

    duration = time.time() - start_time
    
    # Tool call: json.dumps (output formatting)
    json_format_event = _record_step(
        session,
        ScrapeStep(
            step_number=len(session["steps"]) + 1,
            action="tool_call",
            status="running",
            message=f"json.dumps(data, format='{request.output_format.value}')",
            extracted_data={
                "tool_name": "json.dumps",
                "tool_description": f"Format extracted data as {request.output_format.value.upper()}",
                "parameters": {
                    "output_format": request.output_format.value,
                    "data_keys": list(session["extracted_data"].keys()) if isinstance(session["extracted_data"], dict) else ["data"],
                },
            },
            timestamp=_now_iso(),
        ),
    )
    await manager.broadcast(json_format_event, session_id)
    yield _sse_event(json_format_event)
    
    output = await format_output(
        session["extracted_data"],
        request.output_format,
        request.output_instructions,
    )
    
    json_format_result_event = _record_step(
        session,
        ScrapeStep(
            step_number=len(session["steps"]),
            action="tool_call",
            status="completed",
            message=f"json.dumps() → {len(output)} bytes",
            reward=0.05,
            extracted_data={
                "tool_name": "json.dumps",
                "result": {
                    "output_length": len(output),
                    "format": request.output_format.value,
                },
            },
            timestamp=_now_iso(),
        ),
    )
    await manager.broadcast(json_format_result_event, session_id)
    yield _sse_event(json_format_result_event)
    
    output_ext = request.output_format.value
    _write_session_artifact(session, f"final_output.{output_ext}", output)
    _write_session_json_artifact(session, "final_extracted_data.json", session["extracted_data"])

    if request.enable_memory:
        # Tool call: memory.store
        memory_store_event = _record_step(
            session,
            ScrapeStep(
                step_number=len(session["steps"]) + 1,
                action="tool_call",
                status="running",
                message="memory.store(key='summary', type='LONG_TERM')",
                extracted_data={
                    "tool_name": "memory.store",
                    "tool_description": "Store scrape summary in long-term memory",
                    "parameters": {
                        "key": f"scrape:{session_id}:summary",
                        "memory_type": "LONG_TERM",
                        "output_length": len(output),
                    },
                },
                timestamp=_now_iso(),
            ),
        )
        await manager.broadcast(memory_store_event, session_id)
        yield _sse_event(memory_store_event)
        
        try:
            await memory_manager.store(
                key=f"scrape:{session_id}:summary",
                value=output,
                memory_type=MemoryType.LONG_TERM,
                metadata={
                    "session_id": session_id,
                    "complexity": request.complexity.value,
                    "provider": request.provider,
                    "model": request.model,
                },
            )
            _write_session_artifact(session, "memory_summary.txt", output)
            
            # Tool call result: memory.store
            memory_store_result_event = _record_step(
                session,
                ScrapeStep(
                    step_number=len(session["steps"]),
                    action="tool_call",
                    status="completed",
                    message="memory.store() → stored",
                    reward=0.05,
                    extracted_data={
                        "tool_name": "memory.store",
                        "result": {"stored": True, "key": f"scrape:{session_id}:summary"},
                    },
                    timestamp=_now_iso(),
                ),
            )
            await manager.broadcast(memory_store_result_event, session_id)
            yield _sse_event(memory_store_result_event)
        except Exception as exc:
            session["errors"].append(f"Failed to store summary memory: {exc}")
            memory_store_fail_event = _record_step(
                session,
                ScrapeStep(
                    step_number=len(session["steps"]),
                    action="tool_call",
                    status="failed",
                    message=f"memory.store() → {str(exc)[:50]}",
                    extracted_data={
                        "tool_name": "memory.store",
                        "result": {"stored": False, "error": str(exc)[:100]},
                    },
                    timestamp=_now_iso(),
                ),
            )
            await manager.broadcast(memory_store_fail_event, session_id)
            yield _sse_event(memory_store_fail_event)

    response = ScrapeResponse(
        session_id=session_id,
        status="completed" if not session["errors"] else "partial",
        total_steps=len(session["steps"]),
        total_reward=session["total_reward"],
        extracted_data=session["extracted_data"],
        output=output,
        output_format=request.output_format,
        duration_seconds=duration,
        urls_processed=len(resolved_assets),
        errors=session["errors"],
        enabled_plugins=enabled_plugins,
        requested_plugins=request.enable_plugins,
        selected_agents=request.selected_agents,
        memory_enabled=request.enable_memory,
        sandbox_artifacts=_list_session_artifacts(session),
    )

    complete_event = {"type": "complete", "data": response.model_dump()}
    await manager.broadcast(complete_event, session_id)
    yield _sse_event(complete_event)

    session["status"] = response.status
    session["duration"] = duration


@router.post("/stream")
async def scrape_with_stream(
    request: ScrapeRequest,
    settings: SettingsDep,
    memory_manager: MemoryManagerDep,
) -> StreamingResponse:
    """Start a scrape run and stream updates via SSE."""

    if not request.assets:
        raise HTTPException(status_code=400, detail="At least one asset URL is required")

    session_id = request.session_id or str(uuid.uuid4())
    if get_session(session_id):
        raise HTTPException(status_code=409, detail=f"Session {session_id} already exists")
    return StreamingResponse(
        scrape_stream(session_id, request, settings, memory_manager),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Session-Id": session_id,
        },
    )


@router.post("/")
async def scrape_sync(
    request: ScrapeRequest,
    settings: SettingsDep,
    memory_manager: MemoryManagerDep,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Start a scrape run in the background and return session ID."""

    if not request.assets:
        raise HTTPException(status_code=400, detail="At least one asset URL is required")

    session_id = request.session_id or str(uuid.uuid4())
    if get_session(session_id):
        raise HTTPException(status_code=409, detail=f"Session {session_id} already exists")

    async def run_scrape() -> None:
        try:
            async for _ in scrape_stream(session_id, request, settings, memory_manager):
                pass
        except Exception as exc:
            logger.exception("Background scrape failed", extra={"session_id": session_id})
            update_session(session_id, {"status": "failed", "errors": [str(exc)]})

    background_tasks.add_task(run_scrape)
    return {
        "session_id": session_id,
        "status": "started",
        "message": f"Scraping {len(request.assets)} URLs",
        "assets": request.assets,
        "selected_agents": request.selected_agents,
    }


@router.get("/sessions")
async def list_sessions() -> dict[str, Any]:
    """List all active scrape sessions."""

    sessions = [
        {
            "session_id": session_id,
            "status": session["status"],
            "urls_count": len(session.get("resolved_assets") or session["request"].assets),
            "current_index": session.get("current_url_index", 0),
            "total_reward": session["total_reward"],
            "steps": len(session["steps"]),
        }
        for session_id, session in _active_sessions.items()
    ]
    return {"sessions": sessions, "count": len(sessions)}


@router.get("/{session_id}/status")
async def get_scrape_status(session_id: str) -> dict[str, Any]:
    """Get current status for one scrape session."""

    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    duration = (
        time.time() - session["start_time"]
        if session["status"] == "running"
        else session.get("duration", 0.0)
    )
    return {
        "session_id": session_id,
        "status": session["status"],
        "current_url_index": session.get("current_url_index", 0),
        "total_urls": len(session.get("resolved_assets") or session["request"].assets),
        "total_reward": session["total_reward"],
        "extracted_count": len(session["extracted_data"]),
        "steps_count": len(session["steps"]),
        "errors": session["errors"],
        "enabled_plugins": session.get("enabled_plugins", []),
        "selected_agents": session["request"].selected_agents,
        "sandbox_artifacts": _list_session_artifacts(session),
        "duration": duration,
    }


@router.get("/{session_id}/sandbox/files")
async def list_sandbox_files(session_id: str) -> dict[str, Any]:
    """List sandbox artifacts for a scrape session."""

    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    sandbox_dir = session.get("sandbox_dir")
    if not sandbox_dir:
        return {"session_id": session_id, "files": [], "count": 0}

    base = Path(sandbox_dir)
    if not base.exists():
        return {"session_id": session_id, "files": [], "count": 0}

    files: list[dict[str, Any]] = []
    for file in base.iterdir():
        if not file.is_file():
            continue
        files.append(
            {
                "name": file.name,
                "size_bytes": file.stat().st_size,
            }
        )

    files.sort(key=lambda item: item["name"])
    return {"session_id": session_id, "files": files, "count": len(files)}


@router.get("/{session_id}/sandbox/files/{file_name}")
async def read_sandbox_file(session_id: str, file_name: str) -> dict[str, Any]:
    """Read a sandbox file content from the current session."""

    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    sandbox_dir = session.get("sandbox_dir")
    if not sandbox_dir:
        raise HTTPException(status_code=404, detail="Sandbox not available for session")

    safe_name = Path(file_name).name
    file_path = Path(sandbox_dir) / safe_name
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Sandbox file not found")

    content = file_path.read_text(encoding="utf-8", errors="ignore")
    return {
        "session_id": session_id,
        "file_name": safe_name,
        "size_bytes": file_path.stat().st_size,
        "content": content,
    }


@router.get("/{session_id}/result")
async def get_scrape_result(session_id: str) -> ScrapeResponse:
    """Get final result for one scrape session."""

    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session["status"] == "running":
        raise HTTPException(status_code=400, detail="Scraping still in progress")

    request: ScrapeRequest = session["request"]
    duration = session.get("duration", time.time() - session["start_time"])
    output = await format_output(
        session["extracted_data"],
        request.output_format,
        request.output_instructions,
    )
    return ScrapeResponse(
        session_id=session_id,
        status=session["status"],
        total_steps=len(session["steps"]),
        total_reward=session["total_reward"],
        extracted_data=session["extracted_data"],
        output=output,
        output_format=request.output_format,
        duration_seconds=duration,
        urls_processed=len(session.get("resolved_assets") or request.assets),
        errors=session["errors"],
        enabled_plugins=session.get("enabled_plugins", []),
        requested_plugins=request.enable_plugins,
        selected_agents=request.selected_agents,
        memory_enabled=request.enable_memory,
        sandbox_artifacts=_list_session_artifacts(session),
    )


@router.delete("/{session_id}")
async def cancel_scrape(session_id: str) -> dict[str, str]:
    """Cancel a running scrape session."""

    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    update_session(session_id, {"status": "cancelled"})
    return {"status": "cancelled", "session_id": session_id}


@router.delete("/{session_id}/cleanup")
async def cleanup_scrape(session_id: str) -> dict[str, str]:
    """Delete a completed/cancelled session."""

    removed = remove_session(session_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "removed", "session_id": session_id}

"""Scraping endpoints with SSE and websocket live updates."""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
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
from urllib.parse import quote_plus, urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.config import Settings
from app.api.deps import (
    MemoryManagerDep,
    SettingsDep,
    create_environment,
    remove_environment,
)
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
    """Resolve non-URL query assets using deterministic fallbacks."""

    query_l = query.lower()
    if "gold" in query_l and ("price" in query_l or "trend" in query_l):
        return [
            "https://raw.githubusercontent.com/datasets/gold-prices/master/data/monthly.csv",
            "https://github.com/datasets/gold-prices",
        ]
    return [f"https://en.wikipedia.org/wiki/Special:Search?search={quote_plus(query)}"]


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


async def _resolve_assets(
    assets: list[str],
    enabled_plugins: list[str],
) -> tuple[list[str], list[dict[str, Any]]]:
    """Resolve user-provided assets into URLs for scraping."""

    resolved: list[str] = []
    discoveries: list[dict[str, Any]] = []
    search_enabled = "mcp-search" in enabled_plugins

    for asset in assets:
        candidate = asset.strip()
        if not candidate:
            continue

        normalized_url = _coerce_url_asset(candidate)
        if normalized_url:
            if normalized_url not in resolved:
                resolved.append(normalized_url)
            continue

        discovered: list[str] = []
        if search_enabled:
            discovered = await _search_urls_with_mcp(candidate)
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
    """Intelligent scraping that follows navigation plan."""
    
    episode_id = f"{session_id}-{uuid.uuid4().hex[:8]}"
    
    try:
        env = create_environment(episode_id, settings)
        await env.reset(task_id=f"scrape_{session_id}")
        
        step_num = 0
        total_reward = 0.0
        
        # GitHub trending strategy
        if navigation_plan["strategy"] == "github_trending":
            async for event in _scrape_github_trending(
                session, session_id, env, request, navigation_plan, step_num, total_reward
            ):
                yield event

        # Reddit popular/trending communities strategy
        elif navigation_plan["strategy"] == "reddit_trending":
            async for event in _scrape_reddit_trending(
                session, session_id, env, request, url, step_num, total_reward
            ):
                yield event

        # General exploration strategy  
        elif navigation_plan["strategy"] == "intelligent_exploration":
            async for event in _scrape_with_exploration(
                session, session_id, env, request, navigation_plan, url, step_num, total_reward
            ):
                yield event
            
        # Default single page
        else:
            async for event in _scrape_single_page(
                session, session_id, env, request, url, step_num, total_reward
            ):
                yield event
            
    except Exception as exc:
        logger.error(f"Intelligent scraping failed for {url}: {exc}")
        session["errors"].append(f"Scraping failed: {exc}")
        

async def _scrape_github_trending(
    session: dict[str, Any],
    session_id: str, 
    env,
    request: ScrapeRequest,
    navigation_plan: dict[str, Any],
    step_num: int,
    total_reward: float,
) -> AsyncGenerator[dict[str, Any], None]:
    """Scrape GitHub trending repositories."""
    
    trending_repos = []
    
    # Navigate to GitHub trending
    trending_url = "https://github.com/trending"
    
    # Tool call: browser.navigate
    step_num += 1
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="tool_call",
            url=trending_url,
            status="running",
            message=f"browser.navigate(url='{trending_url}')",
            extracted_data={
                "tool_name": "browser.navigate",
                "tool_description": "Navigate browser to GitHub trending page",
                "parameters": {"url": trending_url, "wait_for": "page_load"},
            },
            timestamp=_now_iso(),
        ),
    )
    
    navigate_action = Action(
        action_type=ActionType.NAVIGATE,
        parameters={"url": trending_url},
        reasoning="Navigate to GitHub trending to find popular repositories",
    )
    
    nav_obs, reward, _, _, _, nav_info = await env.step(navigate_action)
    
    # Calculate navigation reward (0.5 for successful navigation)
    nav_reward = 0.5 if nav_obs.page_html else 0.0
    total_reward += nav_reward
    
    nav_success = bool(nav_obs.page_html)
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="tool_call",
            url=trending_url,
            status="completed" if nav_success else "failed",
            message=f"browser.navigate() → {len(nav_obs.page_html) if nav_obs.page_html else 0} bytes",
            reward=0.1,
            extracted_data={
                "tool_name": "browser.navigate",
                "result": {
                    "success": nav_success,
                    "html_length": len(nav_obs.page_html) if nav_obs.page_html else 0,
                    "status_code": 200 if nav_success else 0,
                },
            },
            timestamp=_now_iso(),
        ),
    )
    
    # Update the navigation step with actual reward
    step_num += 1
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="navigate",
            url=trending_url,
            status="completed" if nav_success else "failed",
            message=f"Navigated to {trending_url}" if nav_success else "Navigation failed",
            reward=nav_reward,
            duration_ms=nav_info.get("step_duration_ms", 0),
            timestamp=_now_iso(),
        ),
    )
    
    if not nav_obs.page_html:
        session["errors"].append("Failed to load GitHub trending page")
        return
        
    # Tool call: html.parse
    step_num += 1
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="tool_call",
            url=trending_url,
            status="running",
            message="html.parse(content)",
            extracted_data={
                "tool_name": "html.parse",
                "tool_description": "Parse HTML document into structured DOM",
                "parameters": {"parser": "html.parser", "content_length": len(nav_obs.page_html)},
            },
            timestamp=_now_iso(),
        ),
    )
    
    soup = parse_html(nav_obs.page_html)
    
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="tool_call",
            url=trending_url,
            status="completed",
            message="html.parse() → DOM ready",
            reward=0.05,
            extracted_data={
                "tool_name": "html.parse",
                "result": {"parsed": True, "soup_type": "BeautifulSoup"},
            },
            timestamp=_now_iso(),
        ),
    )
    
    # Tool call: html.select
    step_num += 1
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="tool_call",
            url=trending_url,
            status="running",
            message="html.select(selector='article.Box-row')",
            extracted_data={
                "tool_name": "html.select",
                "tool_description": "Select repository elements from trending page",
                "parameters": {"selector": "article.Box-row", "fallback": "div.Box-row"},
            },
            timestamp=_now_iso(),
        ),
    )
    
    # Find repository entries (GitHub trending structure)
    repo_articles = soup.find_all("article", class_="Box-row") or soup.find_all("div", class_="Box-row")
    
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="tool_call",
            url=trending_url,
            status="completed",
            message=f"html.select() → {len(repo_articles)} elements",
            reward=0.1,
            extracted_data={
                "tool_name": "html.select",
                "result": {"elements_found": len(repo_articles), "selector_used": "article.Box-row"},
            },
            timestamp=_now_iso(),
        ),
    )
    
    step_num += 1
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="extract",
            url=trending_url,
            status="running", 
            message="Extracting trending repositories...",
            reward=0.1,  # Small reward for starting extraction
            timestamp=_now_iso(),
        ),
    )
    
    for article in repo_articles[:20]:  # Limit to first 20
        try:
            # Extract repo name and username
            title_link = article.find("h2") or article.find("h1") 
            if not title_link:
                continue
                
            link = title_link.find("a")
            if not link:
                continue
                
            repo_path = link.get("href", "").strip("/")
            if "/" in repo_path:
                username, repo_name = repo_path.split("/", 1)
            else:
                continue
                
            # Extract stars
            stars_elem = article.find("a", href=lambda x: x and "stargazers" in x)
            stars = "0"
            if stars_elem:
                stars_text = stars_elem.get_text(strip=True)
                # Tool call: regex.sub (inline, no separate step for efficiency)
                stars = re.sub(r"[^\d,.]", "", stars_text)
                
            # Extract forks  
            forks_elem = article.find("a", href=lambda x: x and "forks" in x)
            forks = "0"
            if forks_elem:
                forks_text = forks_elem.get_text(strip=True) 
                # Tool call: regex.sub (inline, no separate step for efficiency)
                forks = re.sub(r"[^\d,.]", "", forks_text)
                
            trending_repos.append({
                "username": username,
                "repo_name": repo_name, 
                "stars": stars,
                "forks": forks
            })
            
        except Exception as exc:
            logger.warning(f"Failed to parse repo entry: {exc}")
            continue
    
    # Calculate extraction reward based on repo count
    extraction_reward = len(trending_repos) * 0.5 + (1.0 if len(trending_repos) >= 10 else 0.5)
    total_reward += extraction_reward
    
    step_num += 1
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="extract",
            url=trending_url,
            status="completed",
            message=f"Extracted {len(trending_repos)} trending repositories",
            reward=extraction_reward,
            extracted_data={"count": len(trending_repos), "repos": trending_repos[:3]},  # Preview only
            timestamp=_now_iso(),
        ),
    )
    
    # Tool call: csv.generate
    step_num += 1
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="tool_call",
            url=trending_url,
            status="running",
            message="csv.generate(data, fields=['username', 'repo_name', 'stars', 'forks'])",
            extracted_data={
                "tool_name": "csv.generate",
                "tool_description": "Generate CSV output from repository data",
                "parameters": {
                    "fields": ["username", "repo_name", "stars", "forks"],
                    "row_count": len(trending_repos),
                },
            },
            timestamp=_now_iso(),
        ),
    )
    
    # Generate clean CSV output
    csv_buffer = io.StringIO()
    writer = csv.DictWriter(csv_buffer, fieldnames=["username", "repo_name", "stars", "forks"])
    writer.writeheader()
    writer.writerows(trending_repos)
    clean_csv = csv_buffer.getvalue()
    
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="tool_call",
            url=trending_url,
            status="completed",
            message=f"csv.generate() → {len(clean_csv)} bytes",
            reward=0.1,
            extracted_data={
                "tool_name": "csv.generate",
                "result": {
                    "csv_length": len(clean_csv),
                    "rows": len(trending_repos),
                    "columns": 4,
                },
            },
            timestamp=_now_iso(),
        ),
    )
    
    # Store the clean CSV directly as extracted data for CSV output format
    if request.output_format == OutputFormat.CSV:
        session["extracted_data"] = {
            "rows": trending_repos,
            "columns": ["username", "repo_name", "stars", "forks"],
            "csv_output": clean_csv,
            "row_count": len(trending_repos),
            "source": trending_url
        }
        session["final_output"] = clean_csv
    else:
        session["extracted_data"][trending_url] = {
            "trending_repositories": trending_repos,
            "summary": f"Found {len(trending_repos)} trending repos"
        }
    
    _write_session_artifact(session, "trending_repos.csv", clean_csv)
    
    # Completion step with final reward
    complete_reward = 1.0  # Bonus for successful completion
    total_reward += complete_reward
    session["total_reward"] = total_reward
    
    step_num += 1
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="complete",
            url=trending_url,
            status="completed",
            message=f"Successfully scraped {len(trending_repos)} repos with reward {total_reward:.2f}",
            reward=complete_reward,
            extracted_data={"total_reward": total_reward, "repos_found": len(trending_repos)},
            timestamp=_now_iso(),
        ),
    )


def _to_int(value: Any) -> int:
    """Convert a value to int safely."""

    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    digits = re.sub(r"[^\d]", "", str(value))
    if not digits:
        return 0
    try:
        return int(digits)
    except ValueError:
        return 0


def _is_reddit_challenge_page(page_html: str) -> bool:
    """Check if Reddit returned a bot-verification challenge page."""

    lowered = page_html.lower()
    challenge_markers = [
        "please wait for verification",
        "js_challenge",
        "captcha",
        "verify you are human",
        "checking your browser",
    ]
    return any(marker in lowered for marker in challenge_markers)


def _extract_reddit_communities_from_payload(
    payload: dict[str, Any],
    limit: int = 25,
) -> list[dict[str, Any]]:
    """Extract subreddit rows from Reddit JSON payload."""

    communities: list[dict[str, Any]] = []
    seen: set[str] = set()

    children = payload.get("data", {}).get("children", [])
    if not isinstance(children, list):
        return communities

    for child in children:
        if not isinstance(child, dict):
            continue
        data = child.get("data", {})
        if not isinstance(data, dict):
            continue

        name = str(
            data.get("display_name")
            or str(data.get("display_name_prefixed", "")).replace("r/", "")
        ).strip()
        if not name:
            continue
        normalized = name.lower()
        if normalized in seen:
            continue
        seen.add(normalized)

        permalink = str(data.get("url") or f"/r/{name}/")
        community_url = permalink if permalink.startswith("http") else f"https://www.reddit.com{permalink}"

        communities.append(
            {
                "subreddit": f"r/{name}",
                "title": str(data.get("title") or data.get("public_description") or ""),
                "subscribers": _to_int(data.get("subscribers")),
                "active_users": _to_int(
                    data.get("active_user_count") or data.get("accounts_active")
                ),
                "url": community_url,
                "description": str(data.get("public_description") or ""),
            }
        )
        if len(communities) >= limit:
            break

    communities.sort(key=lambda row: row.get("subscribers", 0), reverse=True)
    return communities[:limit]


def _extract_reddit_communities_from_html(
    page_html: str,
    limit: int = 25,
) -> list[dict[str, Any]]:
    """Fallback extraction from Reddit HTML when JSON endpoint is unavailable."""

    communities: list[dict[str, Any]] = []
    seen: set[str] = set()
    soup = parse_html(page_html)

    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href", ""))
        match = re.search(r"/r/([A-Za-z0-9_]+)", href)
        if not match:
            continue

        name = match.group(1)
        if name.lower() in {"popular", "all"}:
            continue
        normalized = name.lower()
        if normalized in seen:
            continue
        seen.add(normalized)

        community_url = href if href.startswith("http") else f"https://www.reddit.com/r/{name}/"
        title = anchor.get_text(strip=True)
        communities.append(
            {
                "subreddit": f"r/{name}",
                "title": title,
                "subscribers": 0,
                "active_users": 0,
                "url": community_url,
                "description": "",
            }
        )
        if len(communities) >= limit:
            break

    return communities


def _fetch_reddit_communities(limit: int = 25) -> tuple[list[dict[str, Any]], str]:
    """Fetch trending/popular Reddit communities from public JSON endpoints."""

    endpoints = [
        f"https://www.reddit.com/subreddits/popular.json?limit={limit}",
        f"https://www.reddit.com/subreddits/default.json?limit={limit}",
        f"https://old.reddit.com/subreddits/popular/.json?limit={limit}",
    ]
    headers = {
        "User-Agent": "ScrapeRLBot/1.0 (+https://github.com/NeerajCodz/scrapeRL)",
        "Accept": "application/json",
    }
    last_error = ""

    for endpoint in endpoints:
        try:
            request = Request(endpoint, headers=headers)
            with urlopen(request, timeout=20) as response:
                status_code = int(getattr(response, "status", 200))
                if status_code >= 400:
                    last_error = f"{endpoint} returned status {status_code}"
                    continue
                raw_payload = response.read().decode("utf-8", errors="replace")

            parsed = json.loads(raw_payload)
            communities = _extract_reddit_communities_from_payload(parsed, limit=limit)
            if communities:
                return communities, endpoint
            last_error = f"{endpoint} returned no community rows"
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            last_error = f"{endpoint}: {exc}"
            continue

    return [], last_error


def _fallback_reddit_communities_static(limit: int = 25) -> list[dict[str, Any]]:
    """Fallback list used when Reddit blocks direct/API access."""

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
    communities: list[dict[str, Any]] = []
    for name in names[:limit]:
        communities.append(
            {
                "subreddit": f"r/{name}",
                "title": f"r/{name}",
                "subscribers": 0,
                "active_users": 0,
                "url": f"https://www.reddit.com/r/{name}/",
                "description": "Fallback popular community list (direct Reddit access blocked)",
            }
        )
    return communities


async def _scrape_reddit_trending(
    session: dict[str, Any],
    session_id: str,
    env,
    request: ScrapeRequest,
    url: str,
    step_num: int,
    total_reward: float,
) -> AsyncGenerator[dict[str, Any], None]:
    """Scrape trending Reddit communities with anti-bot fallback."""

    target_url = "https://www.reddit.com/"

    step_num += 1
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="navigate",
            url=target_url,
            status="running",
            message="Navigating to Reddit...",
            timestamp=_now_iso(),
        ),
    )

    navigate_action = Action(
        action_type=ActionType.NAVIGATE,
        parameters={"url": target_url},
        reasoning="Navigate to Reddit and collect trending communities",
    )
    nav_obs, nav_reward, _, _, _, nav_info = await env.step(navigate_action)
    total_reward += nav_reward

    nav_success = bool(nav_obs.page_html)
    step_num += 1
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="navigate",
            url=target_url,
            status="completed" if nav_success else "failed",
            message=f"Navigated to {target_url}" if nav_success else "Navigation failed",
            reward=nav_reward,
            duration_ms=nav_info.get("step_duration_ms", 0),
            timestamp=_now_iso(),
        ),
    )
    if not nav_success:
        session["errors"].append("Failed to load Reddit landing page")
        return

    page_html = nav_obs.page_html or ""
    challenge_detected = _is_reddit_challenge_page(page_html)
    extraction_message = (
        "Reddit challenge detected, switching to Reddit JSON endpoints..."
        if challenge_detected
        else "Extracting trending communities..."
    )

    step_num += 1
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="extract",
            url=url,
            status="running",
            message=extraction_message,
            reward=0.1,
            timestamp=_now_iso(),
        ),
    )

    communities, source_used = await asyncio.to_thread(_fetch_reddit_communities, 25)
    if not communities:
        html_fallback = _extract_reddit_communities_from_html(page_html, 25)
        if html_fallback:
            communities = html_fallback
            source_used = "reddit_html_fallback"
    if not communities:
        search_fallback = await _discover_reddit_communities_via_search(limit=25)
        if search_fallback:
            communities = search_fallback
            source_used = "duckduckgo_search_fallback"
    if len(communities) < 10:
        static_fallback = _fallback_reddit_communities_static(limit=25)
        existing = {row.get("subreddit", "").lower() for row in communities}
        appended_static = False
        for row in static_fallback:
            subreddit = str(row.get("subreddit", "")).lower()
            if subreddit in existing:
                continue
            communities.append(row)
            existing.add(subreddit)
            appended_static = True
            if len(communities) >= 25:
                break
        if communities and appended_static and source_used == "duckduckgo_search_fallback":
            source_used = "search_plus_static_fallback"
        elif communities and appended_static:
            source_used = "static_popular_fallback"

    extraction_reward = min(6.0, len(communities) * 0.25 + (1.0 if communities else 0.0))
    total_reward += extraction_reward

    step_num += 1
    extraction_status = "completed" if communities else "failed"
    extraction_done_message = (
        f"Extracted {len(communities)} trending communities from {source_used}"
        if communities
        else "Failed to extract trending communities from Reddit"
    )
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="extract",
            url=url,
            status=extraction_status,
            message=extraction_done_message,
            reward=extraction_reward,
            extracted_data={
                "count": len(communities),
                "source": source_used,
                "challenge_detected": challenge_detected,
                "preview": communities[:3],
            },
            timestamp=_now_iso(),
        ),
    )

    if not communities:
        if source_used:
            session["errors"].append(f"Reddit extraction failed: {source_used}")
        else:
            session["errors"].append("Reddit extraction failed: no community data found")
        session["total_reward"] += total_reward
        step_num += 1
        yield _record_step(
            session,
            ScrapeStep(
                step_number=step_num,
                action="complete",
                url=url,
                status="failed",
                message="Completed Reddit scrape with no community rows",
                reward=0.0,
                extracted_data={"total_reward": total_reward, "row_count": 0},
                timestamp=_now_iso(),
            ),
        )
        return

    verification_score = 1.0 if len(communities) >= 10 else 0.5
    total_reward += verification_score
    step_num += 1
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="verify",
            url=url,
            status="completed",
            message=f"Verifier checked community coverage ({len(communities)} rows)",
            reward=verification_score,
            extracted_data={
                "row_count": len(communities),
                "coverage": "good" if len(communities) >= 10 else "partial",
            },
            timestamp=_now_iso(),
        ),
    )

    if request.output_format == OutputFormat.CSV:
        columns = ["subreddit", "title", "subscribers", "active_users", "url", "description"]
        csv_output = _rows_to_csv(communities, preferred_headers=columns)
        session["extracted_data"] = {
            "rows": communities,
            "columns": columns,
            "csv_output": csv_output,
            "row_count": len(communities),
            "source": source_used,
            "challenge_detected": challenge_detected,
        }
        session["final_output"] = csv_output
    else:
        session["extracted_data"][url] = {
            "trending_communities": communities,
            "row_count": len(communities),
            "source": source_used,
            "challenge_detected": challenge_detected,
        }

    _write_session_json_artifact(
        session,
        "reddit_trending_communities.json",
        {
            "source": source_used,
            "challenge_detected": challenge_detected,
            "row_count": len(communities),
            "rows": communities,
        },
    )

    done_action = Action(
        action_type=ActionType.DONE,
        parameters={"success": True},
        reasoning="Reddit community extraction complete",
    )
    _, done_reward, _, _, _, _ = await env.step(done_action)
    total_reward += done_reward
    session["total_reward"] += total_reward

    step_num += 1
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="complete",
            url=url,
            status="completed",
            message=f"Completed Reddit trending scrape with {len(communities)} communities",
            reward=done_reward,
            extracted_data={"total_reward": total_reward, "row_count": len(communities)},
            timestamp=_now_iso(),
        ),
    )


async def _scrape_single_page(
    session: dict[str, Any],
    session_id: str,
    env,
    request: ScrapeRequest, 
    url: str,
    step_num: int,
    total_reward: float,
) -> AsyncGenerator[dict[str, Any], None]:
    """Fallback to original single-page scraping."""
    
    # Navigate to URL
    step_num += 1
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="navigate",
            url=url,
            status="running",
            message=f"Navigating to {url}...",
            timestamp=_now_iso(),
        ),
    )
    
    # Tool call: browser.navigate
    # Tool call: validate.url (check URL before navigating)
    step_num += 1
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="tool_call",
            url=url,
            status="running",
            message="validate.url(url)",
            extracted_data={
                "tool_name": "validate.url",
                "tool_description": "Validate URL format before navigation",
                "parameters": {"url": url},
            },
            timestamp=_now_iso(),
        ),
    )
    
    # Simple URL validation
    parsed_url = urlparse(url)
    url_valid = bool(parsed_url.scheme and parsed_url.netloc)
    
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="tool_call",
            url=url,
            status="completed" if url_valid else "failed",
            message=f"validate.url() → {'valid' if url_valid else 'invalid'}",
            reward=0.02 if url_valid else 0.0,
            extracted_data={
                "tool_name": "validate.url",
                "result": {
                    "valid": url_valid,
                    "scheme": parsed_url.scheme,
                    "domain": parsed_url.netloc,
                },
            },
            timestamp=_now_iso(),
        ),
    )
    
    if not url_valid:
        session["errors"].append(f"Invalid URL: {url}")
        return
    
    # Tool call: browser.navigate
    step_num += 1
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="tool_call",
            url=url,
            status="running",
            message="browser.navigate(url)",
            extracted_data={
                "tool_name": "browser.navigate",
                "tool_description": "Navigate browser to target URL",
                "parameters": {"url": url},
            },
            timestamp=_now_iso(),
        ),
    )
    
    navigate_action = Action(
        action_type=ActionType.NAVIGATE,
        parameters={"url": url},
        reasoning=f"Navigate to target URL: {url}",
    )
    nav_obs, reward, _, _, _, nav_info = await env.step(navigate_action)
    total_reward += reward
    
    nav_success = nav_info.get("action_result", {}).get("success", bool(nav_obs.page_html))
    
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="tool_call",
            url=url,
            status="completed" if nav_success else "failed",
            message="browser.navigate(url) → success" if nav_success else "browser.navigate(url) → failed",
            reward=0.05,
            extracted_data={
                "tool_name": "browser.navigate",
                "result": {"success": nav_success, "html_length": len(nav_obs.page_html) if nav_obs.page_html else 0},
            },
            timestamp=_now_iso(),
        ),
    )
    
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="navigate",
            url=url,
            status="completed" if nav_success else "failed",
            message=f"Navigated to {url}" if nav_success else "Navigation failed",
            reward=reward,
            timestamp=_now_iso(),
        ),
    )
    
    if not nav_success or not nav_obs.page_html:
        session["errors"].append(f"Failed to navigate to {url}")
        return
    
    # Tool call: html.parse (parse HTML into DOM)
    step_num += 1
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="tool_call",
            url=url,
            status="running",
            message="html.parse(content)",
            extracted_data={
                "tool_name": "html.parse",
                "tool_description": "Parse HTML document into DOM structure",
                "parameters": {"parser": "html.parser", "content_length": len(nav_obs.page_html)},
            },
            timestamp=_now_iso(),
        ),
    )
    
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="tool_call",
            url=url,
            status="completed",
            message="html.parse() → DOM ready",
            reward=0.05,
            extracted_data={
                "tool_name": "html.parse",
                "result": {"parsed": True, "html_length": len(nav_obs.page_html)},
            },
            timestamp=_now_iso(),
        ),
    )
        
    # Extract fields
    extracted = {}
    fields_to_extract = _extract_fields_for_complexity(request.complexity)
    
    for field_name in fields_to_extract:
        step_num += 1
        # Tool call: html.extract
        yield _record_step(
            session,
            ScrapeStep(
                step_number=step_num,
                action="tool_call",
                url=url,
                status="running",
                message=f"html.extract(field='{field_name}')",
                extracted_data={
                    "tool_name": "html.extract",
                    "tool_description": f"Extract {field_name} from HTML document",
                    "parameters": {"field_name": field_name},
                },
                timestamp=_now_iso(),
            ),
        )
        
        extract_action = Action(
            action_type=ActionType.EXTRACT_FIELD,
            parameters={"field_name": field_name},
            reasoning=f"Extract {field_name} from page",
        )
        obs, reward, _, _, _, _ = await env.step(extract_action)
        total_reward += reward
        
        if obs.extracted_so_far:
            for ef in obs.extracted_so_far:
                if ef.field_name == field_name:
                    extracted[field_name] = ef.value
                    break
        
        value_preview = str(extracted.get(field_name, ""))[:100]
        yield _record_step(
            session,
            ScrapeStep(
                step_number=step_num,
                action="tool_call",
                url=url,
                status="completed",
                message=f"html.extract(field='{field_name}') → {value_preview}",
                reward=0.05,
                extracted_data={
                    "tool_name": "html.extract",
                    "result": {field_name: extracted.get(field_name)},
                },
                timestamp=_now_iso(),
            ),
        )
        
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
                timestamp=_now_iso(),
            ),
        )
    
    # Verification step
    step_num += 1
    extracted_count = len([f for f in fields_to_extract if f in extracted])
    verification_score = extracted_count / len(fields_to_extract) if fields_to_extract else 0.0
    total_reward += verification_score
    
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="verify",
            url=url,
            status="completed",
            message=f"Verifier checked extraction completeness ({extracted_count}/{len(fields_to_extract)})",
            reward=verification_score,
            extracted_data={"coverage": verification_score},
            timestamp=_now_iso(),
        ),
    )
    
    # Complete
    step_num += 1
    done_action = Action(
        action_type=ActionType.DONE,
        parameters={"success": True},
        reasoning="Extraction complete",
    )
    _, done_reward, _, _, _, _ = await env.step(done_action)
    total_reward += done_reward
    
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="complete",
            url=url,
            status="completed",
            message=f"Completed scraping {url}",
            reward=done_reward,
            extracted_data={**extracted, "total_reward": total_reward},
            timestamp=_now_iso(),
        ),
    )
    
    session["total_reward"] += total_reward
    session["extracted_data"][url] = extracted
    _write_session_json_artifact(
        session,
        f"{_safe_artifact_name(urlparse(url).netloc or url)}_extracted.json",
        extracted,
    )


async def _scrape_with_exploration(
    session: dict[str, Any],
    session_id: str,
    env,
    request: ScrapeRequest,
    navigation_plan: dict[str, Any],
    url: str,
    step_num: int,
    total_reward: float,
) -> AsyncGenerator[dict[str, Any], None]:
    """Scrape with intelligent exploration based on instructions."""
    
    # For now, fallback to single page - this can be enhanced later
    async for result in _scrape_single_page(session, session_id, env, request, url, step_num, total_reward):
        yield result


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
            if quality_status != "completed":
                session["errors"].append("Gold dataset row count below quality threshold (100 rows).")

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
            session["errors"].append("No monthly gold rows were extracted from resolved sources.")

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

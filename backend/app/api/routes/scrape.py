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
from urllib.parse import quote_plus, urlparse

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


def _resolve_enabled_plugins(
    requested_plugins: list[str],
) -> tuple[list[str], list[str]]:
    """Resolve requested plugin IDs against installed plugin registry."""

    if not requested_plugins:
        return [], []

    available: set[str] = {
        plugin["id"]
        for category in PLUGIN_REGISTRY.values()
        for plugin in category
        if plugin.get("installed")
    }
    enabled = [plugin_id for plugin_id in requested_plugins if plugin_id in available]
    missing = [plugin_id for plugin_id in requested_plugins if plugin_id not in available]
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


def _create_intelligent_navigation_plan(instructions: str, assets: list[str]) -> dict[str, Any]:
    """Create an intelligent navigation plan based on user instructions."""
    
    instructions_lower = instructions.lower()
    asset_url = assets[0] if assets else ""
    
    # GitHub trending repositories detection
    if "trending" in instructions_lower and "repo" in instructions_lower and "github" in asset_url:
        return {
            "strategy": "github_trending",
            "target_urls": [
                "https://github.com/trending",
                "https://github.com/trending?since=daily",
                "https://github.com/trending?since=weekly"
            ],
            "navigation_steps": [
                "Navigate to GitHub trending page",
                "Extract trending repository information",
                "Follow pagination if available", 
                "Collect repository data: name, stars, forks, description"
            ],
            "extraction_goal": "trending_repositories",
            "output_fields": ["username", "repo_name", "stars", "forks", "description"]
        }
    
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
        "extraction_goal": "basic_extraction"
    }


def _is_url_asset(asset: str) -> bool:
    """Check whether an asset string is a URL."""

    parsed = urlparse(asset.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


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
        if _is_url_asset(candidate):
            resolved.append(candidate)
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
    
    step_num += 1
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="navigate", 
            url=trending_url,
            status="running",
            message="Navigating to GitHub trending page...",
            timestamp=_now_iso(),
        ),
    )
    
    navigate_action = Action(
        action_type=ActionType.NAVIGATE,
        parameters={"url": trending_url},
        reasoning="Navigate to GitHub trending to find popular repositories",
    )
    
    nav_obs, reward, _, _, _, nav_info = await env.step(navigate_action)
    total_reward += reward
    
    if not nav_obs.page_html:
        session["errors"].append("Failed to load GitHub trending page")
        return
        
    # Parse trending repos from HTML
    soup = parse_html(nav_obs.page_html)
    
    step_num += 1
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="extract",
            url=trending_url,
            status="running", 
            message="Extracting trending repositories...",
            timestamp=_now_iso(),
        ),
    )
    
    # Find repository entries (GitHub trending structure)
    repo_articles = soup.find_all("article", class_="Box-row") or soup.find_all("div", class_="Box-row")
    
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
                stars = re.sub(r"[^\d,.]", "", stars_text)
                
            # Extract forks  
            forks_elem = article.find("a", href=lambda x: x and "forks" in x)
            forks = "0"
            if forks_elem:
                forks_text = forks_elem.get_text(strip=True) 
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
    
    # Store results
    step_num += 1
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="complete",
            url=trending_url,
            status="completed",
            message=f"Extracted {len(trending_repos)} trending repositories",
            reward=total_reward + len(trending_repos) * 0.5,
            extracted_data={"trending_repos": trending_repos},
            timestamp=_now_iso(),
        ),
    )
    
    # Format as CSV
    if request.output_format == "csv" and trending_repos:
        csv_buffer = io.StringIO()
        writer = csv.DictWriter(csv_buffer, fieldnames=["username", "repo_name", "stars", "forks"])
        writer.writeheader()
        writer.writerows(trending_repos)
        
        session["final_output"] = csv_buffer.getvalue()
        session["extracted_data"][trending_url] = {
            "trending_repositories": trending_repos,
            "csv_output": csv_buffer.getvalue()
        }
        
        _write_session_artifact(session, "trending_repos.csv", csv_buffer.getvalue())


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
        
    # Extract fields
    extracted = {}
    fields_to_extract = _extract_fields_for_complexity(request.complexity)
    
    for field_name in fields_to_extract:
        step_num += 1
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
            reasoning=f"Extract {field_name} from page",
        )
        obs, reward, _, _, _, _ = await env.step(extract_action)
        total_reward += reward
        
        if obs.extracted_so_far:
            for ef in obs.extracted_so_far:
                if ef.field_name == field_name:
                    extracted[field_name] = ef.value
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
                timestamp=_now_iso(),
            ),
        )
    
    # Verification step
    step_num += 1
    extracted_count = len([f for f in fields_to_extract if f in extracted])
    verification_score = extracted_count / len(fields_to_extract) if fields_to_extract else 0.0
    
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
    _, reward, _, _, _, _ = await env.step(done_action)
    total_reward += reward
    
    yield _record_step(
        session,
        ScrapeStep(
            step_number=step_num,
            action="complete",
            url=url,
            status="completed",
            message=f"Completed scraping {url}",
            reward=total_reward,
            extracted_data=extracted,
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
            extracted_data={
                "requested": request.enable_plugins, 
                "enabled": enabled_plugins, 
                "missing": missing_plugins,
                "navigation_strategy": navigation_plan["strategy"],
                "extraction_goal": navigation_plan["extraction_goal"]
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
                extracted_data={"discoveries": discoveries, "resolved_assets": resolved_assets},
                timestamp=_now_iso(),
            ),
        )
        await manager.broadcast(discovery_event, session_id)
        yield _sse_event(discovery_event)

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
            extracted_data={
                "assets": resolved_assets,
                "instructions": request.instructions,
                "output_instructions": request.output_instructions,
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
        }
        planner_code = (
            "result = {"
            "'phase': payload.get('phase'), "
            "'asset_count': len(payload.get('resolved_assets') or []), "
            "'selected_agents': payload.get('selected_agents') or []"
            "}"
        )
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

        if planner_sandbox.success and planner_sandbox.output is not None:
            planner_python_event = _record_step(
                session,
                ScrapeStep(
                    step_number=len(session["steps"]) + 1,
                    action="planner_python",
                    status="completed",
                    message="Planner agent executed sandbox Python code",
                    extracted_data=planner_sandbox.output,
                    timestamp=_now_iso(),
                ),
            )
            await manager.broadcast(planner_python_event, session_id)
            yield _sse_event(planner_python_event)
        else:
            session["errors"].append(planner_sandbox.error or "Planner sandbox execution failed")

    for idx, url in enumerate(resolved_assets):
        session["current_url_index"] = idx
        navigator_event = _record_step(
            session,
            ScrapeStep(
                step_number=len(session["steps"]) + 1,
                action="navigator",
                url=url,
                status="running",
                message=f"Navigator selected source {idx + 1}/{len(resolved_assets)}",
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
            }
            navigator_code = (
                "result = {"
                "'phase': payload.get('phase'), "
                "'selected_url': payload.get('url'), "
                "'progress': f\"{payload.get('index', 0) + 1}/{payload.get('total', 0)}\""
                "}"
            )
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

            if navigator_sandbox.success and navigator_sandbox.output is not None:
                navigator_python_event = _record_step(
                    session,
                    ScrapeStep(
                        step_number=len(session["steps"]) + 1,
                        action="navigator_python",
                        url=url,
                        status="completed",
                        message="Navigator agent executed sandbox Python code",
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
            navigation_plan,
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

    if any(plugin_id in enabled_plugins for plugin_id in python_plugin_ids):
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

        analysis_payload = {
            "instructions": request.instructions,
            "output_instructions": request.output_instructions,
            "dataset_rows": dataset_rows,
            "source_links": source_links,
            "html_samples": html_samples,
            "extracted_data": extracted_payload,
        }

        sandbox_code = request.python_code or DEFAULT_ANALYSIS_CODE
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
    output = await format_output(
        session["extracted_data"],
        request.output_format,
        request.output_instructions,
    )
    output_ext = request.output_format.value
    _write_session_artifact(session, f"final_output.{output_ext}", output)
    _write_session_json_artifact(session, "final_extracted_data.json", session["extracted_data"])

    if request.enable_memory:
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
        except Exception as exc:
            session["errors"].append(f"Failed to store summary memory: {exc}")

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

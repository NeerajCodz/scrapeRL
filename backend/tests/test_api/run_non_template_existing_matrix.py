"""Run non-template existing-domain matrix across question/csv/json output modes."""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi.testclient import TestClient

from app.api.routes import scrape as scrape_routes
from app.core.env import WebScraperEnv
from app.main import app

BASE_PLUGINS = ["mcp-browser", "mcp-search", "mcp-html"]
DEFAULT_AGENTS = ["planner", "navigator", "extractor", "verifier"]

NON_TEMPLATE_EXISTING_ASSETS = [
    "https://www.python.org/",
    "https://www.mozilla.org/",
    "https://www.apple.com/",
    "https://www.microsoft.com/",
    "https://openai.com/",
    "https://www.cloudflare.com/",
    "https://www.digitalocean.com/",
    "https://www.oracle.com/",
    "https://www.ibm.com/",
    "https://www.cisco.com/",
    "https://www.adobe.com/",
    "https://slack.com/",
    "https://www.notion.so/",
    "https://vercel.com/",
    "https://www.netlify.com/",
    "https://www.heroku.com/",
    "https://www.docker.com/",
    "https://kubernetes.io/",
    "https://ubuntu.com/",
    "https://www.debian.org/",
    "https://archlinux.org/",
    "https://www.rust-lang.org/",
    "https://go.dev/",
    "https://nodejs.org/",
    "https://deno.com/",
    "https://www.postgresql.org/",
    "https://www.mysql.com/",
    "https://www.sqlite.org/",
    "https://www.apache.org/",
    "https://nginx.org/",
    "https://home.cern/",
    "https://www.nasa.gov/",
    "https://www.who.int/",
    "https://www.un.org/",
    "https://example.com/",
]


@dataclass(frozen=True)
class Case:
    asset: str
    mode: str
    output_format: str
    instructions: str
    output_instructions: str
    expected_columns: tuple[str, ...]


def _build_html_payload(url: str) -> str:
    parsed = urlparse(url)
    domain = parsed.netloc or "example.com"
    path = parsed.path or "/"
    slug = path.strip("/").replace("/", "-") or "home"

    return f"""
    <html>
      <head>
        <title>{domain} :: {slug}</title>
        <meta name="description" content="Mock page for {domain} and {slug}" />
      </head>
      <body>
        <h1>{domain} heading</h1>
        <p>Offline deterministic content for {url}. Contact: test+{slug}@example.com</p>
        <article class="card">
          <h2><a href="/alpha/item-one">alpha / item-one</a></h2>
          <div>stars 1,234 forks 210</div>
        </article>
        <article class="card">
          <h2><a href="/beta/item-two">beta / item-two</a></h2>
          <div>stars 987 forks 145</div>
        </article>
        <a href="https://{domain}/about">About</a>
        <a href="https://{domain}/contact">Contact</a>
      </body>
    </html>
    """


def _requested_columns(output_instructions: str) -> tuple[str, ...]:
    cleaned = output_instructions.strip()
    cleaned = re.sub(r"^(?:csv|json|table)\s+of\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace(" and ", ", ")
    columns: list[str] = []
    for piece in cleaned.split(","):
        value = re.sub(r"[^A-Za-z0-9_]+", " ", piece).strip().lower().replace(" ", "_")
        if value and value not in columns:
            columns.append(value)
    return tuple(columns)


def _cases() -> list[Case]:
    matrix: list[Case] = []
    for asset in NON_TEMPLATE_EXISTING_ASSETS:
        matrix.append(
            Case(
                asset=asset,
                mode="question",
                output_format="text",
                instructions="What is the main content and key sections on this website?",
                output_instructions="Answer as plain text with a concise summary.",
                expected_columns=(),
            )
        )
        csv_instruction = "csv of title, url, content"
        matrix.append(
            Case(
                asset=asset,
                mode="csv",
                output_format="csv",
                instructions="Extract key entities and links from this website.",
                output_instructions=csv_instruction,
                expected_columns=_requested_columns(csv_instruction),
            )
        )
        json_instruction = "json of title, url, content"
        matrix.append(
            Case(
                asset=asset,
                mode="json",
                output_format="json",
                instructions="Extract key entities and links from this website.",
                output_instructions=json_instruction,
                expected_columns=_requested_columns(json_instruction),
            )
        )
    return matrix


def _build_payload(case: Case) -> dict[str, Any]:
    return {
        "assets": [case.asset],
        "instructions": case.instructions,
        "output_instructions": case.output_instructions,
        "output_format": case.output_format,
        "complexity": "low",
        "model": "llama-3.1-70b-versatile",
        "provider": "groq",
        "enable_memory": True,
        "enable_plugins": list(BASE_PLUGINS),
        "selected_agents": list(DEFAULT_AGENTS),
        "max_steps": 30,
    }


def _collect_stream_events(client: TestClient, payload: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    with client.stream("POST", "/api/scrape/stream", json=payload) as response:
        if response.status_code != 200:
            raise RuntimeError(f"stream request failed with status {response.status_code}")
        for raw_line in response.iter_lines():
            if not raw_line:
                continue
            line = raw_line if isinstance(raw_line, str) else raw_line.decode("utf-8", errors="ignore")
            if not line.startswith("data: "):
                continue
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                continue
    return events


def _schema_ok(complete_data: dict[str, Any], case: Case) -> bool:
    if not case.expected_columns:
        output = complete_data.get("output")
        return isinstance(output, str) and bool(output.strip())

    extracted_data = complete_data.get("extracted_data")
    if case.output_format == "csv":
        if not isinstance(extracted_data, dict):
            return False
        return tuple(extracted_data.get("columns") or []) == case.expected_columns

    if not isinstance(extracted_data, dict):
        return False
    rows: list[dict[str, Any]] = []
    for value in extracted_data.values():
        if isinstance(value, list):
            rows = value
            break
    if not rows or not isinstance(rows[0], dict):
        return False
    return tuple(rows[0].keys()) == case.expected_columns


def run_matrix() -> dict[str, Any]:
    os.environ["SCRAPERL_DISABLE_LIVE_LLM"] = "1"

    original_execute_navigate = WebScraperEnv._execute_navigate
    original_search_urls = scrape_routes._search_urls_with_mcp
    original_fetch_reddit = scrape_routes._fetch_reddit_communities

    async def fake_execute_navigate(self: WebScraperEnv, url: str) -> dict[str, Any]:
        normalized = str(url).strip()
        if not normalized.startswith("http"):
            normalized = f"https://{normalized}"
        self._page_content_type = "text/html; charset=utf-8"
        self._page_html = _build_html_payload(normalized)
        self._page_title = urlparse(normalized).netloc or "example.com"
        return {
            "success": True,
            "url": normalized,
            "status_code": 200,
            "content_type": self._page_content_type,
            "tls_verification_bypassed": False,
        }

    async def fake_search_urls(query: str, max_results: int = 6) -> list[str]:
        token = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-") or "query"
        count = max(1, min(max_results, 3))
        return [f"https://{token}.example.com/source-{index}" for index in range(1, count + 1)]

    def fake_fetch_reddit_communities(limit: int = 25) -> tuple[list[dict[str, Any]], str]:
        rows: list[dict[str, Any]] = []
        for index in range(limit):
            rows.append(
                {
                    "subreddit": f"r/mockcommunity{index + 1}",
                    "title": f"Mock Community {index + 1}",
                    "subscribers": 200000 - (index * 1000),
                    "active_users": 15000 - (index * 100),
                    "url": f"https://www.reddit.com/r/mockcommunity{index + 1}/",
                    "description": "Offline mocked Reddit community",
                }
            )
        return rows, "mock_reddit_json"

    WebScraperEnv._execute_navigate = fake_execute_navigate
    scrape_routes._search_urls_with_mcp = fake_search_urls
    scrape_routes._fetch_reddit_communities = fake_fetch_reddit_communities

    started = time.time()
    summary: dict[str, Any] = {
        "target_count": len(NON_TEMPLATE_EXISTING_ASSETS),
        "cases": len(_cases()),
        "completed": 0,
        "partial": 0,
        "failed": 0,
        "schema_failures": 0,
        "format_failures": 0,
        "failures": [],
    }

    try:
        with TestClient(app) as client:
            for case in _cases():
                payload = _build_payload(case)
                session_id: str | None = None
                try:
                    events = _collect_stream_events(client, payload)
                    init_event = next((event for event in events if event.get("type") == "init"), None)
                    complete_event = next((event for event in events if event.get("type") == "complete"), None)
                    if not init_event or not complete_event:
                        raise RuntimeError("missing init/complete events")
                    session_id = str(init_event.get("session_id", ""))
                    complete_data = complete_event.get("data") or {}
                    status = str(complete_data.get("status", "failed"))
                    output_format = str(complete_data.get("output_format", ""))
                    if output_format != case.output_format:
                        summary["format_failures"] += 1
                        raise RuntimeError(f"output format mismatch: expected {case.output_format}, got {output_format}")
                    if not _schema_ok(complete_data, case):
                        summary["schema_failures"] += 1
                        raise RuntimeError("schema check failed")

                    if status == "completed":
                        summary["completed"] += 1
                    else:
                        summary["partial"] += 1
                except Exception as exc:  # noqa: BLE001
                    summary["failed"] += 1
                    if len(summary["failures"]) < 30:
                        summary["failures"].append(
                            {
                                "asset": case.asset,
                                "mode": case.mode,
                                "error": str(exc),
                            }
                        )
                finally:
                    if session_id:
                        client.delete(f"/api/scrape/{session_id}/cleanup")
    finally:
        WebScraperEnv._execute_navigate = original_execute_navigate
        scrape_routes._search_urls_with_mcp = original_search_urls
        scrape_routes._fetch_reddit_communities = original_fetch_reddit

    summary["duration_seconds"] = round(time.time() - started, 2)
    return summary


def write_report(summary: dict[str, Any]) -> None:
    project_root = Path(__file__).resolve().parents[3]
    reports_dir = project_root / "docs" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    out_path = reports_dir / "non-template-existing-summary.json"
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def main() -> None:
    summary = run_matrix()
    write_report(summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

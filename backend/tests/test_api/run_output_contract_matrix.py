"""Strict output-contract matrix: 100 template + 100 non-template cases."""

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
from app.sites.templates import SITE_TEMPLATES

BASE_PLUGINS = ["mcp-browser", "mcp-search", "mcp-html"]
DEFAULT_AGENTS = ["planner", "navigator", "extractor", "verifier"]
CASE_COUNT_PER_BUCKET = 100

NON_TEMPLATE_ASSETS = [
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
    "open source scraping frameworks comparison",
    "synthetic unknown portal data feed",
]


@dataclass(frozen=True)
class ContractCase:
    bucket: str  # template or non-template
    id: str
    asset: str
    mode: str  # csv/json/text
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
        <p>Mock content for {url}. Contact: test+{slug}@example.com</p>
        <article class="card">
          <h2><a href="/alpha/repo-one">alpha / repo-one</a></h2>
          <div>stars 1,234 forks 210</div>
        </article>
        <article class="card">
          <h2><a href="/beta/repo-two">beta / repo-two</a></h2>
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


def _build_template_cases() -> list[ContractCase]:
    cases: list[ContractCase] = []
    templates = list(SITE_TEMPLATES)
    for index in range(CASE_COUNT_PER_BUCKET):
        template = templates[index % len(templates)]
        mode = ("csv", "json", "text")[index % 3]
        fields = tuple(str(field).lower() for field in template.output_fields[:4]) or ("title", "url")
        asset = f"https://{template.domains[0]}"
        case_id = f"template-{index + 1:03d}-{template.site_id}"
        if mode == "csv":
            output_instructions = f"csv of {', '.join(fields)}"
            cases.append(
                ContractCase(
                    bucket="template",
                    id=case_id,
                    asset=asset,
                    mode=mode,
                    output_format="csv",
                    instructions=f"Extract top visible {template.extraction_goal} records from this asset.",
                    output_instructions=output_instructions,
                    expected_columns=_requested_columns(output_instructions),
                )
            )
        elif mode == "json":
            output_instructions = f"json of {', '.join(fields)}"
            cases.append(
                ContractCase(
                    bucket="template",
                    id=case_id,
                    asset=asset,
                    mode=mode,
                    output_format="json",
                    instructions=f"Extract structured {template.extraction_goal} entities.",
                    output_instructions=output_instructions,
                    expected_columns=_requested_columns(output_instructions),
                )
            )
        else:
            cases.append(
                ContractCase(
                    bucket="template",
                    id=case_id,
                    asset=asset,
                    mode=mode,
                    output_format="text",
                    instructions=f"What are the top visible {template.extraction_goal} on this target?",
                    output_instructions="Answer in concise plain text.",
                    expected_columns=(),
                )
            )
    return cases


def _build_non_template_cases() -> list[ContractCase]:
    cases: list[ContractCase] = []
    assets = NON_TEMPLATE_ASSETS
    csv_contracts = [
        "csv of title, url, content",
        "csv of username, repo, stars, forks",
        "csv of name, url, summary",
    ]
    json_contracts = [
        "json of title, url, content",
        "json of entity, metric, value",
        "json of name, url, summary",
    ]
    for index in range(CASE_COUNT_PER_BUCKET):
        asset = assets[index % len(assets)]
        mode = ("csv", "json", "text")[index % 3]
        case_id = f"non-template-{index + 1:03d}"
        if mode == "csv":
            output_instructions = csv_contracts[index % len(csv_contracts)]
            cases.append(
                ContractCase(
                    bucket="non-template",
                    id=case_id,
                    asset=asset,
                    mode=mode,
                    output_format="csv",
                    instructions="Extract key entities and metadata from this asset.",
                    output_instructions=output_instructions,
                    expected_columns=_requested_columns(output_instructions),
                )
            )
        elif mode == "json":
            output_instructions = json_contracts[index % len(json_contracts)]
            cases.append(
                ContractCase(
                    bucket="non-template",
                    id=case_id,
                    asset=asset,
                    mode=mode,
                    output_format="json",
                    instructions="Extract key entities and metadata from this asset.",
                    output_instructions=output_instructions,
                    expected_columns=_requested_columns(output_instructions),
                )
            )
        else:
            cases.append(
                ContractCase(
                    bucket="non-template",
                    id=case_id,
                    asset=asset,
                    mode=mode,
                    output_format="text",
                    instructions="What is on this target and what are the most relevant points?",
                    output_instructions="Answer in concise plain text.",
                    expected_columns=(),
                )
            )
    return cases


def _build_payload(case: ContractCase) -> dict[str, Any]:
    return {
        "assets": [case.asset],
        "instructions": case.instructions,
        "output_instructions": case.output_instructions,
        "output_format": case.output_format,
        "complexity": "high",
        "model": "llama-3.1-70b-versatile",
        "provider": "groq",
        "enable_memory": True,
        "enable_plugins": list(BASE_PLUGINS),
        "selected_agents": list(DEFAULT_AGENTS),
        "max_steps": 999,  # effectively unlimited for this matrix
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


def _csv_header(output: str) -> tuple[str, ...]:
    first_line = output.splitlines()[0] if output else ""
    if not first_line:
        return tuple()
    return tuple(part.strip().lower() for part in first_line.split(","))


def _extract_first_rows(extracted_data: Any) -> list[dict[str, Any]]:
    if isinstance(extracted_data, dict):
        if isinstance(extracted_data.get("rows"), list):
            return extracted_data.get("rows", [])
        for value in extracted_data.values():
            if isinstance(value, list):
                return value
    return []


def _contract_ok(complete_data: dict[str, Any], case: ContractCase) -> tuple[bool, str]:
    if str(complete_data.get("output_format", "")) != case.output_format:
        return False, "output_format mismatch"

    if case.output_format == "text":
        output = complete_data.get("output")
        return (isinstance(output, str) and bool(output.strip())), "empty text output"

    extracted_data = complete_data.get("extracted_data")
    if not case.expected_columns:
        return False, "missing expected contract columns"

    if case.output_format == "csv":
        if not isinstance(extracted_data, dict):
            return False, "csv extracted_data is not dict"
        columns = tuple((extracted_data.get("columns") or []))
        if columns != case.expected_columns:
            return False, f"csv column mismatch expected={case.expected_columns} got={columns}"
        header = _csv_header(str(complete_data.get("output", "")))
        if header != case.expected_columns:
            return False, f"csv header mismatch expected={case.expected_columns} got={header}"
        return True, ""

    rows = _extract_first_rows(extracted_data)
    if not rows or not isinstance(rows[0], dict):
        return False, "json rows missing"
    keys = tuple(rows[0].keys())
    if keys != case.expected_columns:
        return False, f"json key mismatch expected={case.expected_columns} got={keys}"
    return True, ""


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

    template_cases = _build_template_cases()
    non_template_cases = _build_non_template_cases()
    all_cases = [*template_cases, *non_template_cases]

    started = time.time()
    summary: dict[str, Any] = {
        "template_cases": len(template_cases),
        "non_template_cases": len(non_template_cases),
        "total_cases": len(all_cases),
        "completed": 0,
        "partial": 0,
        "failed": 0,
        "contract_failures": 0,
        "failures": [],
    }

    try:
        with TestClient(app) as client:
            for case in all_cases:
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
                    ok, reason = _contract_ok(complete_data, case)
                    if not ok:
                        summary["contract_failures"] += 1
                        raise RuntimeError(reason)
                    if status == "completed":
                        summary["completed"] += 1
                    else:
                        summary["partial"] += 1
                except Exception as exc:  # noqa: BLE001
                    summary["failed"] += 1
                    if len(summary["failures"]) < 40:
                        summary["failures"].append(
                            {
                                "case_id": case.id,
                                "bucket": case.bucket,
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


def write_summary(summary: dict[str, Any]) -> None:
    project_root = Path(__file__).resolve().parents[3]
    reports_dir = project_root / "docs" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    out_path = reports_dir / "output-contract-200-summary.json"
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def main() -> None:
    summary = run_matrix()
    write_summary(summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

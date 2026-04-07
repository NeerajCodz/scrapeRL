"""Run a large deterministic template/non-template scrape matrix and write docs/test-report.md."""

from __future__ import annotations

import json
import os
import re
import time
from collections import defaultdict
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
ITERATIONS_PER_TARGET = 100
NON_TEMPLATE_ASSETS = [
    "https://unknown-synth-alpha.test",
    "https://unknown-synth-beta.test",
    "https://unknown-synth-gamma.test",
    "open source scraping tools benchmark",
    "synthetic market intelligence dashboard comparison",
]


@dataclass(frozen=True)
class Scenario:
    """One test scenario for a specific asset/template target."""

    target_id: str
    asset: str
    is_template: bool
    output_format: str
    instructions: str
    output_instructions: str
    requested_columns: tuple[str, ...]
    mode: str


def _build_gold_csv(months: int = 180) -> str:
    lines = ["Date,Price"]
    year = 2012
    month = 1
    for index in range(months):
        price = 1120.0 + (index * 2.75)
        lines.append(f"{year:04d}-{month:02d}-01,{price:.2f}")
        month += 1
        if month > 12:
            month = 1
            year += 1
    return "\n".join(lines)


def _build_html_payload(url: str) -> str:
    parsed = urlparse(url)
    domain = parsed.netloc or "example.com"
    path = parsed.path or "/"
    slug = path.strip("/").replace("/", "-") or "home"

    sample_cards = """
    <article class="card">
      <h2><a href="/alpha/item-one">alpha / item-one</a></h2>
      <div>stars 1,234 forks 210</div>
    </article>
    <article class="card">
      <h2><a href="/beta/item-two">beta / item-two</a></h2>
      <div>stars 987 forks 145</div>
    </article>
    <article class="card">
      <h2><a href="/gamma/item-three">gamma / item-three</a></h2>
      <div>stars 876 forks 132</div>
    </article>
    """

    return f"""
    <html>
      <head>
        <title>{domain} :: {slug}</title>
        <meta name="description" content="Mock page for {domain} and {slug}" />
      </head>
      <body>
        <h1>{domain} heading</h1>
        <p>Offline deterministic content for {url}. Contact: test+{slug}@example.com</p>
        <a href="https://{domain}/about">About</a>
        <a href="https://{domain}/contact">Contact</a>
        <a href="mailto:hello@example.com">Email</a>
        <table>
          <tr><th>month</th><th>gold_price_usd</th></tr>
          <tr><td>2016-01</td><td>1101.00</td></tr>
          <tr><td>2016-02</td><td>1104.00</td></tr>
        </table>
        {sample_cards}
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


def _build_payload(scenario: Scenario) -> dict[str, Any]:
    return {
        "assets": [scenario.asset],
        "instructions": scenario.instructions,
        "output_instructions": scenario.output_instructions,
        "output_format": scenario.output_format,
        "complexity": "low",
        "model": "llama-3.1-70b-versatile",
        "provider": "groq",
        "enable_memory": True,
        "enable_plugins": list(BASE_PLUGINS),
        "selected_agents": list(DEFAULT_AGENTS),
        "max_steps": 30,
    }


def _build_template_scenario(template: Any, iteration: int) -> Scenario:
    mode_idx = iteration % 3
    fields = tuple(str(field).lower() for field in template.output_fields[:4]) or ("title", "url")
    asset = f"https://{template.domains[0]}"

    if mode_idx == 0:
        return Scenario(
            target_id=template.site_id,
            asset=asset,
            is_template=True,
            output_format="text",
            instructions=f"What are the top visible {template.extraction_goal} on {template.name} right now?",
            output_instructions="Answer the question clearly in plain text.",
            requested_columns=(),
            mode="question",
        )
    if mode_idx == 1:
        output_instructions = f"csv of {', '.join(fields)}"
        return Scenario(
            target_id=template.site_id,
            asset=asset,
            is_template=True,
            output_format="csv",
            instructions=f"Extract the top visible {template.extraction_goal} and return rows.",
            output_instructions=output_instructions,
            requested_columns=_requested_columns(output_instructions),
            mode="csv",
        )

    output_instructions = f"json of {', '.join(fields)}"
    return Scenario(
        target_id=template.site_id,
        asset=asset,
        is_template=True,
        output_format="json",
        instructions=f"Extract structured {template.extraction_goal} entities from this asset.",
        output_instructions=output_instructions,
        requested_columns=_requested_columns(output_instructions),
        mode="json",
    )


def _build_non_template_scenario(asset: str, iteration: int) -> Scenario:
    mode_idx = iteration % 3
    if mode_idx == 0:
        return Scenario(
            target_id=f"non-template:{asset}",
            asset=asset,
            is_template=False,
            output_format="text",
            instructions="What is available on this target and what can be extracted?",
            output_instructions="Answer the question clearly in plain text.",
            requested_columns=(),
            mode="question",
        )
    if mode_idx == 1:
        output_instructions = "csv of title, url, content"
        return Scenario(
            target_id=f"non-template:{asset}",
            asset=asset,
            is_template=False,
            output_format="csv",
            instructions="Extract key entities and metadata from the target.",
            output_instructions=output_instructions,
            requested_columns=_requested_columns(output_instructions),
            mode="csv",
        )

    output_instructions = "json of title, url, content"
    return Scenario(
        target_id=f"non-template:{asset}",
        asset=asset,
        is_template=False,
        output_format="json",
        instructions="Extract key entities and metadata from the target.",
        output_instructions=output_instructions,
        requested_columns=_requested_columns(output_instructions),
        mode="json",
    )


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


def _schema_ok_for_complete(complete_data: dict[str, Any], scenario: Scenario) -> bool:
    if not scenario.requested_columns:
        output = complete_data.get("output")
        return isinstance(output, str) and bool(output.strip())

    extracted_data = complete_data.get("extracted_data")
    if scenario.output_format == "csv":
        if not isinstance(extracted_data, dict):
            return False
        columns = tuple((extracted_data.get("columns") or []))
        return columns == scenario.requested_columns

    if not isinstance(extracted_data, dict):
        return False
    rows: list[dict[str, Any]] = []
    for value in extracted_data.values():
        if isinstance(value, list):
            rows = value
            break
    if not rows:
        return False
    first = rows[0]
    if not isinstance(first, dict):
        return False
    return tuple(first.keys()) == scenario.requested_columns


def _run_matrix() -> dict[str, Any]:
    os.environ["SCRAPERL_DISABLE_LIVE_LLM"] = "1"

    original_execute_navigate = WebScraperEnv._execute_navigate
    original_search_urls = scrape_routes._search_urls_with_mcp
    original_fetch_reddit = scrape_routes._fetch_reddit_communities

    async def fake_execute_navigate(self: WebScraperEnv, url: str) -> dict[str, Any]:
        normalized = str(url).strip()
        if not normalized.startswith("http"):
            normalized = f"https://{normalized}"
        if "gold" in normalized and normalized.endswith(".csv"):
            self._page_content_type = "text/csv; charset=utf-8"
            self._page_html = _build_gold_csv()
            self._page_title = "gold-prices-monthly"
        else:
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
    stats: dict[str, Any] = {
        "iterations_per_target": ITERATIONS_PER_TARGET,
        "template_count": len(SITE_TEMPLATES),
        "non_template_target_count": len(NON_TEMPLATE_ASSETS),
        "total_runs": 0,
        "completed_runs": 0,
        "partial_runs": 0,
        "failed_runs": 0,
        "schema_failures": 0,
        "format_failures": 0,
        "error_samples": [],
        "template_results": defaultdict(lambda: {"runs": 0, "completed": 0, "partial": 0, "failed": 0}),
        "non_template_results": defaultdict(lambda: {"runs": 0, "completed": 0, "partial": 0, "failed": 0}),
    }

    try:
        with TestClient(app) as client:
            for template in SITE_TEMPLATES:
                for iteration in range(ITERATIONS_PER_TARGET):
                    scenario = _build_template_scenario(template, iteration)
                    payload = _build_payload(scenario)
                    target_bucket = stats["template_results"][template.site_id]
                    target_bucket["runs"] += 1
                    stats["total_runs"] += 1
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
                        if output_format != scenario.output_format:
                            stats["format_failures"] += 1
                            raise RuntimeError(
                                f"output_format mismatch expected={scenario.output_format} got={output_format}"
                            )
                        if not _schema_ok_for_complete(complete_data, scenario):
                            stats["schema_failures"] += 1
                            raise RuntimeError("schema validation failed")
                        if status == "completed":
                            stats["completed_runs"] += 1
                            target_bucket["completed"] += 1
                        else:
                            stats["partial_runs"] += 1
                            target_bucket["partial"] += 1
                    except Exception as exc:  # noqa: BLE001
                        stats["failed_runs"] += 1
                        target_bucket["failed"] += 1
                        if len(stats["error_samples"]) < 30:
                            stats["error_samples"].append(
                                {
                                    "target_id": scenario.target_id,
                                    "mode": scenario.mode,
                                    "asset": scenario.asset,
                                    "error": str(exc),
                                }
                            )
                    finally:
                        if session_id:
                            client.delete(f"/api/scrape/{session_id}/cleanup")

            for asset in NON_TEMPLATE_ASSETS:
                for iteration in range(ITERATIONS_PER_TARGET):
                    scenario = _build_non_template_scenario(asset, iteration)
                    payload = _build_payload(scenario)
                    target_bucket = stats["non_template_results"][asset]
                    target_bucket["runs"] += 1
                    stats["total_runs"] += 1
                    session_id = None
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
                        if output_format != scenario.output_format:
                            stats["format_failures"] += 1
                            raise RuntimeError(
                                f"output_format mismatch expected={scenario.output_format} got={output_format}"
                            )
                        if not _schema_ok_for_complete(complete_data, scenario):
                            stats["schema_failures"] += 1
                            raise RuntimeError("schema validation failed")
                        if status == "completed":
                            stats["completed_runs"] += 1
                            target_bucket["completed"] += 1
                        else:
                            stats["partial_runs"] += 1
                            target_bucket["partial"] += 1
                    except Exception as exc:  # noqa: BLE001
                        stats["failed_runs"] += 1
                        target_bucket["failed"] += 1
                        if len(stats["error_samples"]) < 30:
                            stats["error_samples"].append(
                                {
                                    "target_id": scenario.target_id,
                                    "mode": scenario.mode,
                                    "asset": scenario.asset,
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

    stats["duration_seconds"] = round(time.time() - started, 2)
    stats["template_results"] = dict(stats["template_results"])
    stats["non_template_results"] = dict(stats["non_template_results"])
    return stats


def _write_report(stats: dict[str, Any]) -> None:
    project_root = Path(__file__).resolve().parents[3]
    docs_dir = project_root / "docs"
    reports_dir = docs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    json_path = reports_dir / "template-stress-summary.json"
    json_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")

    total = int(stats["total_runs"])
    completed = int(stats["completed_runs"])
    partial = int(stats["partial_runs"])
    failed = int(stats["failed_runs"])
    pass_rate = (completed / total * 100.0) if total else 0.0

    template_lines = []
    for site_id, row in sorted(stats["template_results"].items()):
        template_lines.append(
            f"| `{site_id}` | {row['runs']} | {row['completed']} | {row['partial']} | {row['failed']} |"
        )

    non_template_lines = []
    for asset, row in sorted(stats["non_template_results"].items()):
        non_template_lines.append(
            f"| `{asset}` | {row['runs']} | {row['completed']} | {row['partial']} | {row['failed']} |"
        )

    error_lines = []
    for sample in stats["error_samples"]:
        error_lines.append(
            f"- `{sample['target_id']}` ({sample['mode']}) asset=`{sample['asset']}` error=`{sample['error']}`"
        )
    if not error_lines:
        error_lines.append("- No failures captured.")

    report = f"""# Template Stress Test Report

## Scope
- Template targets: **{stats['template_count']}**
- Non-template targets: **{stats['non_template_target_count']}**
- Iterations per target: **{stats['iterations_per_target']}**
- Total runs: **{total}**
- Modes cycled per target: **question**, **csv**, **json**
- Execution mode: deterministic offline mocks (`SCRAPERL_DISABLE_LIVE_LLM=1`)

## Aggregate Result
- Completed: **{completed}**
- Partial: **{partial}**
- Failed: **{failed}**
- Pass rate (completed/total): **{pass_rate:.2f}%**
- Schema failures: **{stats['schema_failures']}**
- Output-format mismatches: **{stats['format_failures']}**
- Duration: **{stats['duration_seconds']} seconds**

## Per-Template Results
| Template | Runs | Completed | Partial | Failed |
|---|---:|---:|---:|---:|
{chr(10).join(template_lines)}

## Non-Template Results
| Asset | Runs | Completed | Partial | Failed |
|---|---:|---:|---:|---:|
{chr(10).join(non_template_lines)}

## Failure Samples
{chr(10).join(error_lines)}

## Notes
- Templates are used as **reference hints** (navigation targets/field hints), not rigid scraper scripts.
- Agent flow evaluates **assets + instructions + output_format + output_instructions** per request.
- Output schema validation checks strict column adherence for CSV/JSON runs.
- Raw machine summary: `docs/reports/template-stress-summary.json`.
"""

    report_path = docs_dir / "test-report.md"
    report_path.write_text(report, encoding="utf-8")


def main() -> None:
    stats = _run_matrix()
    _write_report(stats)
    print(json.dumps(
        {
            "total_runs": stats["total_runs"],
            "completed_runs": stats["completed_runs"],
            "partial_runs": stats["partial_runs"],
            "failed_runs": stats["failed_runs"],
            "duration_seconds": stats["duration_seconds"],
        },
        indent=2,
    ))


if __name__ == "__main__":
    main()

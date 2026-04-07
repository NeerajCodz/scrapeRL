"""High-coverage end-to-end scrape tests with deterministic offline fixtures."""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient

from app.api.routes import scrape as scrape_routes
from app.core.action import Action
from app.core.env import WebScraperEnv
from app.sites.templates import SITE_TEMPLATES

BASE_PLUGINS = ["mcp-browser", "mcp-search", "mcp-html"]
PYTHON_PLUGINS = [
    "mcp-python-sandbox",
    "proc-python",
    "proc-pandas",
    "proc-numpy",
    "proc-bs4",
]
DEFAULT_AGENTS = ["planner", "navigator", "extractor", "verifier"]


def _is_live_network_mode() -> bool:
    """Return True when live-network E2E mode is enabled."""

    raw = os.getenv("SCRAPERL_E2E_LIVE_NETWORK", "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _env_positive_int(name: str) -> int | None:
    """Read an optional positive integer environment variable."""

    raw = os.getenv(name)
    if raw is None:
        return None

    try:
        value = int(raw)
    except ValueError:
        return None

    if value <= 0:
        return None
    return value


@dataclass(frozen=True)
class E2ECase:
    """One end-to-end scrape test case."""

    name: str
    payload: dict[str, Any]
    expected_template_id: str | None = None
    expected_strategy: str | None = None
    expect_sandbox: bool = False


def _build_gold_csv(months: int = 180) -> str:
    """Create deterministic monthly gold CSV data for offline tests."""

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
    """Build deterministic HTML content with rich extraction surfaces."""

    parsed = urlparse(url)
    domain = parsed.netloc or "example.com"
    path = parsed.path or "/"
    slug = path.strip("/").replace("/", "-") or "home"

    github_cards = ""
    if "github.com" in domain and ("trending" in path or "explore" in path or path == "/"):
        github_cards = """
        <article class="Box-row">
          <h2><a href="/alpha/repo-one">alpha / repo-one</a></h2>
          <a href="/alpha/repo-one/stargazers">1,234</a>
          <a href="/alpha/repo-one/network/members">210</a>
        </article>
        <article class="Box-row">
          <h2><a href="/beta/repo-two">beta / repo-two</a></h2>
          <a href="/beta/repo-two/stargazers">987</a>
          <a href="/beta/repo-two/network/members">145</a>
        </article>
        <article class="Box-row">
          <h2><a href="/gamma/repo-three">gamma / repo-three</a></h2>
          <a href="/gamma/repo-three/stargazers">876</a>
          <a href="/gamma/repo-three/network/members">132</a>
        </article>
        """

    return f"""
    <html>
      <head>
        <title>{domain} :: {slug}</title>
        <meta name="description" content="Mock page for {domain} and {slug}" />
        <meta property="og:title" content="{domain} sample" />
      </head>
      <body>
        <h1>{domain} heading</h1>
        <p>
          Offline content for {url}. Contact: test+{slug}@example.com
        </p>
        <a href="https://{domain}/about">About</a>
        <a href="https://{domain}/contact">Contact</a>
        <a href="mailto:hello@example.com">Email</a>
        <img src="https://{domain}/logo.png" alt="logo" />
        <form action="/submit" method="post">
          <input type="text" name="query" />
          <textarea name="notes"></textarea>
        </form>
        <table>
          <tr><th>month</th><th>gold_price_usd</th></tr>
          <tr><td>2016-01</td><td>1101.00</td></tr>
          <tr><td>2016-02</td><td>1104.00</td></tr>
        </table>
        <script src="/assets/app.js"></script>
        {github_cards}
      </body>
    </html>
    """


@pytest.fixture(autouse=True)
def patch_network_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch network-facing dependencies for deterministic E2E execution."""

    if _is_live_network_mode():
        return

    gold_csv = _build_gold_csv()

    async def fake_execute_navigate(self: WebScraperEnv, action: Action) -> dict[str, Any]:
        raw_url = str(action.get_param("url") or "https://example.com").strip()
        normalized = raw_url
        if not re.match(r"^https?://", normalized, flags=re.IGNORECASE):
            normalized = f"https://{normalized}"

        parsed = urlparse(normalized)
        if not parsed.netloc:
            return {"success": False, "error": f"Invalid URL: {raw_url}"}

        self._current_url = normalized
        self._navigation_history.append(normalized)
        self._page_status_code = 200

        if normalized.endswith(".csv") or "gold-prices" in normalized:
            self._page_content_type = "text/csv"
            self._page_html = gold_csv
            self._page_title = "gold-prices-monthly"
        else:
            self._page_content_type = "text/html; charset=utf-8"
            self._page_html = _build_html_payload(normalized)
            self._page_title = parsed.netloc

        return {
            "success": True,
            "url": normalized,
            "status_code": 200,
            "content_type": self._page_content_type,
            "tls_verification_bypassed": False,
        }

    async def fake_search_urls(query: str, max_results: int = 6) -> list[str]:
        lowered = query.lower()

        if "gold" in lowered and ("price" in lowered or "trend" in lowered):
            return [
                "https://data.mock/gold/monthly.csv",
                "https://github.com/datasets/gold-prices",
            ]

        if "reddit" in lowered:
            return [
                "https://www.reddit.com/r/python/",
                "https://www.reddit.com/r/machinelearning/",
                "https://www.reddit.com/r/programming/",
            ]

        token = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-") or "query"
        count = max(1, min(max_results, 3))
        return [f"https://{token}.example.com/source-{idx}" for idx in range(1, count + 1)]

    def fake_fetch_reddit_communities(limit: int = 25) -> tuple[list[dict[str, Any]], str]:
        communities = []
        for idx in range(limit):
            communities.append(
                {
                    "subreddit": f"r/mockcommunity{idx + 1}",
                    "title": f"Mock Community {idx + 1}",
                    "subscribers": 200000 - (idx * 1000),
                    "active_users": 15000 - (idx * 100),
                    "url": f"https://www.reddit.com/r/mockcommunity{idx + 1}/",
                    "description": "Offline mocked Reddit community",
                }
            )

        return communities, "mock_reddit_json"

    monkeypatch.setattr(WebScraperEnv, "_execute_navigate", fake_execute_navigate)
    monkeypatch.setattr(scrape_routes, "_search_urls_with_mcp", fake_search_urls)
    monkeypatch.setattr(scrape_routes, "_fetch_reddit_communities", fake_fetch_reddit_communities)


def _build_payload(
    *,
    assets: list[str],
    instructions: str,
    output_format: str = "json",
    complexity: str = "low",
    enable_plugins: list[str] | None = None,
    selected_agents: list[str] | None = None,
    python_code: str | None = None,
) -> dict[str, Any]:
    """Build a scrape payload using defaults aligned with app behavior."""

    output_instructions = {
        "json": "Return as structured JSON",
        "csv": "Return as CSV with stable column order",
        "markdown": "Return as Markdown sections",
        "text": "Return as plain text summary",
    }[output_format]

    payload: dict[str, Any] = {
        "assets": assets,
        "instructions": instructions,
        "output_instructions": output_instructions,
        "output_format": output_format,
        "complexity": complexity,
        "model": "llama-3.3-70b",
        "provider": "nvidia",
        "enable_memory": True,
        "enable_plugins": enable_plugins or list(BASE_PLUGINS),
        "selected_agents": selected_agents or list(DEFAULT_AGENTS),
        "max_steps": 50,
    }

    if python_code:
        payload["python_code"] = python_code

    return payload


def _build_e2e_cases() -> list[E2ECase]:
    """Build exactly 100 distinct E2E cases across templates and generic inputs."""

    cases: list[E2ECase] = []
    formats = ["json", "markdown", "text", "csv"]

    for idx, template in enumerate(SITE_TEMPLATES):
        output_format = formats[idx % len(formats)]
        complexity = "low"
        if idx % 17 == 0:
            complexity = "medium"
        if idx % 29 == 0:
            complexity = "high"

        plugins = list(BASE_PLUGINS)
        expect_sandbox = False
        python_code = None

        if idx % 14 == 0:
            plugins.extend(PYTHON_PLUGINS)
            plugins.append("skill-planner")
            expect_sandbox = True
            python_code = (
                "rows = payload.get('dataset_rows') or []\n"
                "result = {'rows_seen': len(rows), 'source_links': len(payload.get('source_links') or [])}"
            )

        instructions = f"Collect structured highlights for {template.name} template case {idx + 1}"
        expected_strategy = None

        if template.site_id == "github":
            instructions = f"Extract trending repo stats from GitHub case {idx + 1}"
            expected_strategy = "github_trending"
        elif template.site_id == "reddit":
            instructions = f"Extract trending communities from Reddit case {idx + 1}"
            expected_strategy = "reddit_trending"

        cases.append(
            E2ECase(
                name=f"template-{idx + 1:02d}-{template.site_id}",
                payload=_build_payload(
                    assets=[f"https://{template.domains[0]}"],
                    instructions=instructions,
                    output_format=output_format,
                    complexity=complexity,
                    enable_plugins=plugins,
                    python_code=python_code,
                ),
                expected_template_id=template.site_id,
                expected_strategy=expected_strategy,
                expect_sandbox=expect_sandbox,
            )
        )

    for idx in range(20):
        query_assets = [f"synthetic discovery query batch {idx + 1}"]
        if idx % 5 == 0:
            query_assets.append(f"synthetic companion signal {idx + 1}")

        plugins = list(BASE_PLUGINS)
        if idx % 4 == 0:
            plugins.append("skill-navigator")

        cases.append(
            E2ECase(
                name=f"query-{idx + 1:02d}",
                payload=_build_payload(
                    assets=query_assets,
                    instructions=f"Search and extract useful findings for synthetic query case {idx + 1}",
                    output_format="json",
                    complexity="low",
                    enable_plugins=plugins,
                ),
            )
        )

    for idx in range(10):
        cases.append(
            E2ECase(
                name=f"gold-dataset-{idx + 1:02d}",
                payload=_build_payload(
                    assets=[f"gold price trend monthly dataset request {idx + 1}"],
                    instructions=f"Build monthly gold price trend dataset from 2016 case {idx + 1}",
                    output_format="csv",
                    complexity="high",
                    enable_plugins=[*BASE_PLUGINS, *PYTHON_PLUGINS, "skill-extractor"],
                    python_code=(
                        "rows = payload.get('dataset_rows') or []\n"
                        "columns = sorted(list(rows[0].keys())) if rows else []\n"
                        "result = {'rows_seen': len(rows), 'columns': columns}"
                    ),
                ),
                expect_sandbox=True,
            )
        )

    for idx in range(7):
        cases.append(
            E2ECase(
                name=f"github-trending-extra-{idx + 1:02d}",
                payload=_build_payload(
                    assets=[f"https://github.com/trending?since=daily&batch={idx + 1}"],
                    instructions=f"List trending GitHub repositories and stats case {idx + 1}",
                    output_format="csv",
                    complexity="medium",
                    enable_plugins=list(BASE_PLUGINS),
                ),
                expected_template_id="github",
                expected_strategy="github_trending",
            )
        )

    for idx in range(7):
        cases.append(
            E2ECase(
                name=f"reddit-trending-extra-{idx + 1:02d}",
                payload=_build_payload(
                    assets=[f"https://www.reddit.com/?batch={idx + 1}"],
                    instructions=f"List trending Reddit communities and activity case {idx + 1}",
                    output_format="csv",
                    complexity="medium",
                    enable_plugins=list(BASE_PLUGINS),
                ),
                expected_template_id="reddit",
                expected_strategy="reddit_trending",
            )
        )

    assert len(cases) == 100
    assert len({case.name for case in cases}) == 100
    return cases


def _build_live_network_cases() -> list[E2ECase]:
    """Build live-network E2E cases (no mocks) for staging validation."""

    return [
        E2ECase(
            name="live-github-trending",
            payload=_build_payload(
                assets=["https://github.com/trending"],
                instructions="Extract trending repo stats from GitHub",
                output_format="csv",
                complexity="medium",
                enable_plugins=[*BASE_PLUGINS, "skill-planner"],
            ),
            expected_template_id="github",
            expected_strategy="github_trending",
        ),
        E2ECase(
            name="live-reddit-trending",
            payload=_build_payload(
                assets=["https://www.reddit.com/"],
                instructions="Extract trending communities from Reddit",
                output_format="csv",
                complexity="medium",
                enable_plugins=[*BASE_PLUGINS, "skill-navigator"],
            ),
            expected_template_id="reddit",
            expected_strategy="reddit_trending",
        ),
        E2ECase(
            name="live-wikipedia-main",
            payload=_build_payload(
                assets=["https://en.wikipedia.org/wiki/Main_Page"],
                instructions="Extract reference content summary",
                output_format="json",
                complexity="low",
            ),
            expected_template_id="wikipedia",
        ),
        E2ECase(
            name="live-python-home",
            payload=_build_payload(
                assets=["https://www.python.org/"],
                instructions="Extract homepage highlights and links",
                output_format="markdown",
                complexity="low",
            ),
        ),
        E2ECase(
            name="live-huggingface-models",
            payload=_build_payload(
                assets=["https://huggingface.co/models"],
                instructions="Extract model hub highlights",
                output_format="json",
                complexity="low",
            ),
            expected_template_id="huggingface",
        ),
        E2ECase(
            name="live-arxiv-new",
            payload=_build_payload(
                assets=["https://arxiv.org/list/cs/new"],
                instructions="Extract latest computer science papers",
                output_format="json",
                complexity="low",
            ),
            expected_template_id="arxiv",
        ),
        E2ECase(
            name="live-stackoverflow-questions",
            payload=_build_payload(
                assets=["https://stackoverflow.com/questions"],
                instructions="Extract top question cards and metadata",
                output_format="text",
                complexity="low",
            ),
            expected_template_id="stackoverflow",
        ),
        E2ECase(
            name="live-example-domain",
            payload=_build_payload(
                assets=["https://example.com"],
                instructions="Extract title, content, and links",
                output_format="text",
                complexity="low",
            ),
        ),
        E2ECase(
            name="live-query-discovery-1",
            payload=_build_payload(
                assets=["open source scraping frameworks comparison"],
                instructions="Search and extract useful findings",
                output_format="json",
                complexity="low",
            ),
        ),
        E2ECase(
            name="live-query-discovery-2",
            payload=_build_payload(
                assets=["python data extraction tutorials"],
                instructions="Search and extract useful findings",
                output_format="markdown",
                complexity="low",
            ),
        ),
        E2ECase(
            name="live-gold-dataset",
            payload=_build_payload(
                assets=["gold price trend monthly dataset"],
                instructions="Build monthly gold price trend dataset from 2016 onward",
                output_format="csv",
                complexity="high",
                enable_plugins=[*BASE_PLUGINS, *PYTHON_PLUGINS, "skill-extractor"],
                python_code=(
                    "rows = payload.get('dataset_rows') or []\n"
                    "result = {'rows_seen': len(rows), 'columns': sorted(list(rows[0].keys())) if rows else []}"
                ),
            ),
            expect_sandbox=True,
        ),
        E2ECase(
            name="live-github-explore",
            payload=_build_payload(
                assets=["https://github.com/explore"],
                instructions="Extract repository metadata from GitHub explore",
                output_format="json",
                complexity="medium",
            ),
            expected_template_id="github",
        ),
    ]


def _collect_stream_events(client: TestClient, payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Run one stream scrape request and collect SSE events."""

    events: list[dict[str, Any]] = []

    with client.stream("POST", "/api/scrape/stream", json=payload) as response:
        assert response.status_code == 200

        for raw_line in response.iter_lines():
            if not raw_line:
                continue

            line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
            if not line.startswith("data: "):
                continue

            event = json.loads(line[6:])
            events.append(event)
            if event.get("type") == "complete":
                break

    return events


def _run_case_batch(client: TestClient, cases: list[E2ECase]) -> dict[str, Any]:
    """Execute a batch of cases and collect validation stats."""

    failures: list[str] = []
    tool_call_counts: Counter[str] = Counter()
    strategy_counts: Counter[str] = Counter()
    seen_template_ids: set[str] = set()
    sandbox_success_cases = 0
    completed_cases = 0

    for case in cases:
        session_id: str | None = None

        try:
            events = _collect_stream_events(client, case.payload)

            init_event = next((event for event in events if event.get("type") == "init"), None)
            complete_event = next(
                (event for event in events if event.get("type") == "complete"),
                None,
            )

            assert init_event is not None, "missing init event"
            session_id = str(init_event["session_id"])
            assert complete_event is not None, "missing complete event"

            complete_data = complete_event.get("data")
            assert isinstance(complete_data, dict), "complete payload is not a dictionary"
            assert complete_data["session_id"] == session_id
            assert complete_data["status"] in {"completed", "partial"}
            assert int(complete_data["total_steps"]) > 0
            assert int(complete_data["urls_processed"]) >= 1

            if complete_data["status"] == "completed":
                completed_cases += 1

            enabled_plugins = complete_data.get("enabled_plugins") or []
            assert all(not str(plugin_id).startswith("skill-") for plugin_id in enabled_plugins)
            assert "web_scraper" not in enabled_plugins

            steps = [
                event.get("data")
                for event in events
                if event.get("type") == "step" and isinstance(event.get("data"), dict)
            ]
            assert steps, "no step events emitted"

            case_template_ids: set[str] = set()
            case_strategies: set[str] = set()

            for step in steps:
                action = step.get("action")
                extracted = step.get("extracted_data")
                if not isinstance(extracted, dict):
                    continue

                if action == "tool_call":
                    tool_name = extracted.get("tool_name")
                    if isinstance(tool_name, str) and tool_name:
                        tool_call_counts[tool_name] += 1

                if action == "plugins":
                    strategy = extracted.get("navigation_strategy")
                    if isinstance(strategy, str) and strategy:
                        case_strategies.add(strategy)
                        strategy_counts[strategy] += 1

                if action == "site_template":
                    site_id = extracted.get("site_id")
                    if isinstance(site_id, str) and site_id:
                        case_template_ids.add(site_id)

            seen_template_ids.update(case_template_ids)

            if case.expected_template_id:
                assert case.expected_template_id in case_template_ids, (
                    f"expected site template '{case.expected_template_id}' not emitted"
                )

            if case.expected_strategy:
                assert case.expected_strategy in case_strategies, (
                    f"expected strategy '{case.expected_strategy}' not emitted"
                )

            sandbox_seen = any(
                step.get("action") in {"planner_python", "navigator_python", "python_sandbox"}
                for step in steps
            )
            if case.expect_sandbox:
                assert sandbox_seen, "sandbox execution steps not emitted"
                sandbox_success_cases += 1

        except AssertionError as exc:
            failures.append(f"{case.name}: {exc}")
        finally:
            if session_id:
                cleanup_response = client.delete(f"/api/scrape/{session_id}/cleanup")
                assert cleanup_response.status_code in {200, 404}

    return {
        "failures": failures,
        "tool_call_counts": tool_call_counts,
        "strategy_counts": strategy_counts,
        "seen_template_ids": seen_template_ids,
        "sandbox_success_cases": sandbox_success_cases,
        "completed_cases": completed_cases,
    }


def test_plugins_registry_excludes_agent_skills(client: TestClient) -> None:
    """Plugin API should not duplicate agent skills from /api/agents."""

    response = client.get("/api/plugins")
    assert response.status_code == 200
    payload = response.json()

    categories = payload["categories"]
    assert "skills" not in categories

    plugin_ids = [plugin["id"] for plugins in payload["plugins"].values() for plugin in plugins]
    assert all(not plugin_id.startswith("skill-") for plugin_id in plugin_ids)
    assert "web_scraper" not in plugin_ids


def test_scraper_e2e_100_inputs_templates_tools_plugins_and_sandbox(
    client: TestClient,
) -> None:
    """Run 100 end-to-end scrape inputs and validate major system behavior."""

    if _is_live_network_mode():
        pytest.skip("Offline deterministic E2E suite is skipped in live-network mode")

    cases = _build_e2e_cases()
    summary = _run_case_batch(client, cases)

    assert len(cases) == 100
    assert not summary["failures"], " | ".join(summary["failures"][:12])

    expected_template_ids = {template.site_id for template in SITE_TEMPLATES}
    assert expected_template_ids.issubset(summary["seen_template_ids"])

    required_tool_calls = {
        "url.parse",
        "validate.url",
        "browser.navigate",
        "html.parse",
        "html.extract",
        "memory.store",
        "sandbox.execute",
        "extract.urls",
        "extract.emails",
        "csv.generate",
    }
    assert required_tool_calls.issubset(set(summary["tool_call_counts"].keys()))

    assert summary["strategy_counts"]["github_trending"] >= 1
    assert summary["strategy_counts"]["reddit_trending"] >= 1
    assert summary["sandbox_success_cases"] >= 10
    assert summary["completed_cases"] >= 95


@pytest.mark.skipif(
    not _is_live_network_mode(),
    reason="Enable SCRAPERL_E2E_LIVE_NETWORK=1 for live-network staging runs",
)
def test_scraper_e2e_live_network_mode_staging(client: TestClient) -> None:
    """Live-network E2E mode with no mocks, controlled by environment flag."""

    cases = _build_live_network_cases()
    case_limit = _env_positive_int("SCRAPERL_E2E_LIVE_CASE_LIMIT")
    if case_limit is not None:
        cases = cases[: min(case_limit, len(cases))]

    summary = _run_case_batch(client, cases)

    assert not summary["failures"], " | ".join(summary["failures"][:10])

    expected_templates = {case.expected_template_id for case in cases if case.expected_template_id}
    assert expected_templates.issubset(summary["seen_template_ids"])

    required_tool_calls = {
        "url.parse",
        "browser.navigate",
        "html.parse",
        "html.extract",
        "memory.store",
    }
    assert required_tool_calls.issubset(set(summary["tool_call_counts"].keys()))

    expected_sandbox_cases = sum(1 for case in cases if case.expect_sandbox)
    assert summary["sandbox_success_cases"] >= expected_sandbox_cases

    assert summary["strategy_counts"]["github_trending"] >= 1
    assert summary["strategy_counts"]["reddit_trending"] >= 1
    assert summary["completed_cases"] >= max(1, len(cases) // 2)

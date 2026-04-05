# Agentic Scraper Sandbox + Plugin Execution Report

## Goal
Enable scraper as an agent that can:
- search from non-URL prompts,
- navigate and scrape links,
- execute plugin-based Python analysis (`numpy`, `pandas`, `bs4`) safely,
- run in a sandboxed per-request environment with cleanup.

## What Was Implemented
- Added sandbox plugin executor: `backend/app/plugins/python_sandbox.py`
  - AST safety validation (restricted imports and blocked dangerous calls/attributes)
  - isolated execution with `python -I`
  - per-request temp workspace
  - automatic cleanup after execution
- Wired sandbox plugin execution into scrape flow (`/api/scrape/stream` and `/api/scrape/` via shared pipeline):
  - `mcp-python-sandbox`
  - `proc-python`
  - `proc-pandas`
  - `proc-numpy`
  - `proc-bs4`
- Added optional request field:
  - `python_code` (sandboxed code, must assign `result`)
- Enhanced non-URL asset resolution:
  - MCP search attempt via DuckDuckGo provider
  - deterministic fallback resolution for scraper workflows
- Updated plugin registry and installed plugin set for new plugins.

## Safety Model
- Sandbox runs in isolated temp directory per request (`scraperl-sandbox-<session>-*`)
- Dangerous operations blocked by static AST checks (`open`, `exec`, `eval`, `subprocess`, `os`-style operations, dunder access, etc.)
- No persistent artifacts are kept after run (workspace removed in `finally` cleanup).

## One-Request Validation (real `curl -N` runs)
All tests executed with one request to `POST /api/scrape/stream` each.

| Test | Status | Errors | URLs Processed | Python Analysis Present | Dataset Row Count |
| --- | --- | ---: | ---: | --- | ---: |
| gold-csv-agentic | completed | 0 | 2 | true | 123 |
| ev-data-search-json | completed | 0 | 6 | true | - |
| direct-dataset-python-analysis | completed | 0 | 1 | true | 123 |

## Notes
- Gold trend request produced monthly dataset rows from 2016 onward with source links in one stream request.
- Python plugin analysis was present in all validation scenarios.
- Agent step stream included planner/search/navigator/extractor/verifier + sandbox analysis events.

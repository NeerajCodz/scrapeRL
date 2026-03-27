# System Architecture

## Overview

WebScraper-OpenEnv is designed as a modular, dashboard-first RL environment with extensible APIs, MCP tools, and multi-model routing.

## High-Level Topology

```text
Frontend Dashboard (React/Vite)
        |
        v
FastAPI Control Plane
  - episode lifecycle
  - action dispatch
  - reward engine
  - tool registry API
  - settings + policy
        |
        +--> Agent Runtime
        |      - planner/navigator/extractor/verifier
        |      - memory manager
        |      - model router
        |
        +--> MCP Gateway
        |      - tool discovery
        |      - lazy install/load
        |      - schema + timeout + retries
        |
        +--> Search Layer
        |      - provider routing
        |      - query optimization
        |      - credibility scoring
        |
        +--> Memory Layer
        |      - short/working/long/shared
        |      - vector index + persistent storage
        |
        +--> Observability
               - traces/logs/metrics/cost dashboard
```

## Core Subsystems

### 1. Control Plane

Responsibilities:

- reset/step/state APIs
- request validation
- action authorization and policy checks
- deterministic episode management

### 2. Agent Runtime

Responsibilities:

- policy inference
- strategy execution
- fallback handling
- action explainability

### 3. Tooling Plane (MCP)

Responsibilities:

- dynamic tool registry
- server health checks
- lazy installation
- composition workflows

### 4. Data Plane

Responsibilities:

- HTML ingestion and chunking
- extraction and normalization
- verification and reconciliation
- output persistence

### 5. Analytics Plane

Responsibilities:

- reward component logging
- model/token/cost accounting
- tool usage telemetry
- memory quality analytics

## Processing Pipeline

1. `reset(task_id, seed)`
2. observation emitted
3. policy selects action
4. action executes (native/MCP/search/memory)
5. reward computed and logged
6. done check
7. repeat until terminal

## Batch and Parallel Design

### Batch

- large HTML split into semantic chunks
- chunk extraction batched with bounded size
- merge + dedupe + confidence rank

### Parallel

- independent chunk tasks run concurrently
- search and verification can run in parallel branches
- configurable worker limits and queue priorities

## Queue and Scheduler

Task queue supports:

- priority classes (`high`, `normal`, `low`)
- cancellation tokens
- retry policy with backoff
- dead-letter queue for repeated failures

## Storage Architecture

- Episode state: in-memory + optional persistence
- Long-term memory: vector DB + metadata store
- Logs/metrics: append-only time-series-friendly sink
- Exports: JSON/CSV trace packs

## Reliability

- per-tool timeout and retry
- per-step safety budget
- circuit breaker for failing providers
- deterministic fallback chains

## Security

- API key vaulting via env/config secrets
- MCP allowlist
- output sanitization
- redaction of sensitive tokens in logs

## Deployment

Single-container baseline:

- frontend static build served by API backend
- optional sidecars for DB/vector/MCP infra

Scale-out profile:

- separate API and worker pools
- managed vector DB
- queue-backed distributed execution
- central observability backend

## Compatibility Goals

- local dev mode with minimal dependencies
- cloud mode with managed infra
- optional self-hosted LLM endpoints

## Future Architecture Extensions

- distributed multi-agent graph execution
- adaptive autoscaling by queue pressure
- global memory federation across projects

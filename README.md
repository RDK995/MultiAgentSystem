# Google ADK Multi-Agent UK Resell Lead System

This project runs a Google ADK-oriented sourcing pipeline to identify UK resale opportunities from Japanese trading-card retailers.

## Current Scope

- Category focus: trading cards (Pokemon, One Piece, Yu-Gi-Oh, Digimon, related TCG products).
- Active sources:
  - HobbyLink Japan (`https://www.hlj.com/`)
  - Nin-Nin-Game (`https://www.nin-nin-game.com/en/`)
- Output: JSON (optional) plus a formatted timestamped HTML report.

## Agent Design

The ADK graph is a simple orchestrator + specialists sequence:

1. `item_sourcing_agent`
   - Calls `find_candidate_items` for configured sources.
2. `profitability_agent`
   - Calls `assess_profitability_against_ebay` for each candidate.
3. `report_writer_agent`
   - Produces a structured lead report.
4. `uk_resell_orchestrator`
   - Parent `SequentialAgent` combining all stages.

## Project Layout

- `src/uk_resell_adk/agents.py` – ADK multi-agent construction
- `src/uk_resell_adk/tools.py` – tool functions and source diagnostics
- `src/uk_resell_adk/sources/` – source adapters and shared parsing helpers
- `src/uk_resell_adk/html_renderer.py` – HTML report generation
- `src/uk_resell_adk/main.py` – local dry-run CLI entrypoint
- `src/uk_resell_adk/app.py` – exposes `root_agent` for ADK runtime

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
python -m uk_resell_adk.main --json
```

## CLI Flags

- `--json` print workflow payload as JSON
- `--html-out <path>` write report to a fixed path
- `--allow-fallback` allow static fallback catalog items when live scrape fails
- `--strict-live` fail run when a required source has zero live candidates
- `--debug-sources` write raw source snapshots to debug folder
- `--debug-dir <path>` set debug snapshot directory (default `debug/sources`)

By default, reports are written to unique files like `reports/uk_resell_report_20260217_204113.html`.

## Tracing (LangSmith + Langfuse)

Tracing is optional and can run to both providers concurrently.

```bash
export ENABLE_LANGSMITH_TRACING="true"   # optional, defaults true
export ENABLE_LANGFUSE_TRACING="true"    # optional, defaults true

export LANGSMITH_API_KEY="your-langsmith-api-key"
export LANGSMITH_PROJECT="uk-resell-adk" # optional

export LANGFUSE_PUBLIC_KEY="your-langfuse-public-key"
export LANGFUSE_SECRET_KEY="your-langfuse-secret-key"
export LANGFUSE_BASE_URL="https://cloud.langfuse.com" # optional
```

Traced spans include:
- `run_local_dry_run`
- `build_multi_agent_system`
- sourcing/profitability tool calls

## ADK Runtime

Use `uk_resell_adk.app:root_agent` as the ADK entrypoint.

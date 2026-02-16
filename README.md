# Google ADK Multi-Agent UK Resell Lead System

This repository contains a Google ADK-oriented multi-agent system for identifying cross-border resale opportunities into the UK.

## Agent Design

The system follows an orchestrator + specialist pattern:

1. **Orchestrator Agent** (`uk_resell_orchestrator`)
   - Manages the end-to-end workflow.
   - Interacts with the user and consolidates outputs from specialist agents.
2. **Agent 1: Marketplace Discovery**
   - Focuses on Meccha Japan as the primary sourcing marketplace for Japan-exclusive products.
3. **Agent 2: Item Sourcing**
   - Finds candidate items on the discovered marketplaces.
4. **Agent 3: Profitability Analysis**
   - Cross-references candidate items with `ebay.co.uk` sold-price signals.
5. **Agent 4: Data Lead Report Writer**
   - Produces a lead report with confidence levels, risks, and recommendations.

## Project Layout

- `src/uk_resell_adk/agents.py` – ADK multi-agent construction
- `src/uk_resell_adk/tools.py` – function tools used by specialist agents
- `src/uk_resell_adk/app.py` – exports `root_agent` for ADK runtime
- `src/uk_resell_adk/main.py` – local dry-run entrypoint (non-ADK fallback)

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
python -m uk_resell_adk.main --json
```

Each run also writes a formatted HTML report to a unique timestamped file, for example `reports/uk_resell_report_20260216_164500.html`.
You can override the path with `--html-out`, for example:

```bash
python -m uk_resell_adk.main --html-out reports/latest.html
```


## LangSmith Tracing

Tracing is integrated for the local workflow and ADK entrypoint. To enable it:

```bash
export LANGSMITH_API_KEY="your-api-key"
export LANGSMITH_TRACING="true"              # optional, auto-defaults to true when API key exists
export LANGSMITH_PROJECT="uk-resell-adk"     # optional
```

Traced spans include:
- Local dry-run workflow
- Agent system build step
- Discovery/sourcing/profitability tool calls

## Run with ADK

If your environment has ADK CLI configured, point it at `uk_resell_adk.app:root_agent`.

## Notes on Best Practice

- Keep external APIs behind explicit tools (clear boundaries and testability).
- Keep all model/runtime knobs in a central config object.
- Return structured outputs from each agent stage for deterministic downstream processing.
- Use compliant APIs for production data acquisition (especially marketplace scraping constraints).
- Profitability currently assumes UK-based private seller eBay fees (0% final value baseline for eligible categories); adjust for business accounts or category-specific fees as needed.

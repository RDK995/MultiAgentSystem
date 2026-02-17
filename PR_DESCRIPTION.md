## Summary
This PR performs a full simplification-oriented refactor of the resale workflow, focused on trading-card sourcing and explainable reporting.

## What Changed
- Refactored the pipeline for clarity and smaller, reusable units in `tools.py`, `main.py`, and `html_renderer.py`.
- Introduced source adapter architecture under `src/uk_resell_adk/sources/`:
  - `base.py` for shared source protocol/descriptors
  - `common.py` for fetch/parsing helpers, sitemap crawling, debug snapshots, currency handling
  - `hlj.py` and `ninningame.py` concrete adapters
  - `trading_cards.py` shared trading-card filtering and candidate-item construction helpers
- Updated runtime/docs/config/model wiring to match current supported sources and simplify configuration.
- Expanded unit tests for sources, parsing, diagnostics, renderer output, and CLI behavior.

## Diff-Based Review Comments
1. **Sourcing logic decomposition (`src/uk_resell_adk/tools.py`)**
   - Split diagnostics and status resolution into dedicated helpers (`_resolve_source_status`, `_record_source_diagnostics`, `_dedupe_items_by_url`) to reduce branching complexity in `find_candidate_items`.
   - Strict-live handling remains enforced while now producing cleaner diagnostics for blocked/fetch/parse conditions.

2. **Adapter abstraction (`src/uk_resell_adk/sources/base.py`, `src/uk_resell_adk/sources/*.py`)**
   - Added protocol-driven adapter interface to isolate source-specific scraping details from workflow orchestration.
   - HLJ and Nin-Nin implementations now follow the same 3-pass pattern: search -> sitemap -> optional fallback.

3. **Reusable parsing/fetching (`src/uk_resell_adk/sources/common.py`)**
   - Centralized page fetch retries, anti-bot block detection, JSON-LD extraction, HTML extraction, and sitemap traversal.
   - Added debug snapshot write-paths for parser tuning (`--debug-sources` / `--debug-dir`).

4. **Trading-card specialization (`src/uk_resell_adk/sources/trading_cards.py`)**
   - Consolidated product-title filtering and candidate append semantics so all sources apply consistent rules.

5. **CLI/reporting simplification (`src/uk_resell_adk/main.py`, `src/uk_resell_adk/html_renderer.py`)**
   - Added parser builder function and streamlined CLI output flow.
   - Renderer now uses focused helper functions and explicitly surfaces provenance and diagnostics in report output.

6. **Configuration/model cleanup (`src/uk_resell_adk/config.py`, `src/uk_resell_adk/models.py`)**
   - Removed stale fields/enums and kept only currently used runtime settings and model structures.

7. **Documentation alignment (`README.md`)**
   - Removed stale references to legacy sources and marketplace-discovery stage.
   - Updated scope, CLI flags, tracing setup, and current architecture.

8. **Test coverage (`tests/*.py`)**
   - Added source parser tests and common extraction tests.
   - Updated existing tests to current source set and stricter diagnostics model.

## Validation
- `pytest -q`
- Result: `28 passed`

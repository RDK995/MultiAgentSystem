from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from uk_resell_adk.application.workflow import (
    profitability_worker_count,
    run_profitability_stage,
    run_report_stage,
    run_source_stage,
    select_report_candidates,
    select_top_profitable_assessments,
)
from uk_resell_adk.config import DEFAULT_CONFIG, RuntimeConfig
from uk_resell_adk.html_renderer import write_html_report
from uk_resell_adk.live_events import emit_visual_event, stop_visual_run_requested, update_agent_status, visualizer_events_enabled
from uk_resell_adk.models import CandidateItem, ProfitabilityAssessment
from uk_resell_adk.tools import (
    assess_profitability_against_ebay,
    configure_source_runtime,
    discover_foreign_marketplaces,
    find_candidate_items,
    get_source_diagnostics,
    reset_source_diagnostics,
)
from uk_resell_adk.tracing import configure_tracing, traceable


def _select_top_profitable_assessments(
    assessments: list[ProfitabilityAssessment], *, limit: int | None
) -> list[ProfitabilityAssessment]:
    return select_top_profitable_assessments(assessments, limit=limit)


def _select_report_candidates(
    candidates: list[CandidateItem], shortlisted_assessments: list[ProfitabilityAssessment]
) -> list[CandidateItem]:
    return select_report_candidates(candidates, shortlisted_assessments)


def _profitability_worker_count(candidate_count: int) -> int:
    return profitability_worker_count(
        candidate_count=candidate_count,
        default_concurrency=DEFAULT_CONFIG.profitability_concurrency,
    )


def _assess_candidates_in_parallel(candidates: list[CandidateItem]) -> list[ProfitabilityAssessment]:
    return run_profitability_stage(
        candidates=candidates,
        default_concurrency=DEFAULT_CONFIG.profitability_concurrency,
        assess_profitability=assess_profitability_against_ebay,
        stop_requested=stop_visual_run_requested,
        events_enabled=lambda: False,
    ).all_assessments


@traceable(name="run_local_dry_run", run_type="chain")
def run_local_dry_run(*, runtime_config: RuntimeConfig | None = None) -> dict:
    """Run the end-to-end workflow: deep sourcing, full analysis, and full report output."""
    config = runtime_config or DEFAULT_CONFIG
    if stop_visual_run_requested():
        raise RuntimeError("Run stopped by user.")
    source_result = run_source_stage(
        max_foreign_sites=config.max_foreign_sites,
        discover_marketplaces=discover_foreign_marketplaces,
        find_candidates=find_candidate_items,
        reset_diagnostics=reset_source_diagnostics,
        read_diagnostics=get_source_diagnostics,
        stop_requested=stop_visual_run_requested,
        events_enabled=visualizer_events_enabled,
        emit_event=emit_visual_event,
        update_agent=update_agent_status,
        source_concurrency=config.source_concurrency,
    )
    profitability_result = run_profitability_stage(
        candidates=source_result.candidates,
        default_concurrency=config.profitability_concurrency,
        assess_profitability=assess_profitability_against_ebay,
        stop_requested=stop_visual_run_requested,
        events_enabled=visualizer_events_enabled,
        emit_event=emit_visual_event,
        update_agent=update_agent_status,
    )
    return run_report_stage(
        marketplaces=source_result.marketplaces,
        candidates=source_result.candidates,
        assessments=profitability_result.all_assessments,
        source_diagnostics=source_result.source_diagnostics,
    )


def _default_html_output_path() -> Path:
    """Generate unique report names so historical runs are preserved."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return Path("reports") / f"uk_resell_report_{timestamp}.html"


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="UK resale ADK multi-agent dry run helper")
    parser.add_argument("--json", action="store_true", help="Print workflow output as JSON")
    parser.add_argument("--allow-fallback", action="store_true", help="Allow static fallback items when live scrape fails")
    parser.add_argument("--strict-live", action="store_true", help="Fail run if any source returns no live candidates")
    parser.add_argument("--debug-sources", action="store_true", help="Write source HTML snapshots to debug directory")
    parser.add_argument("--debug-dir", default="debug/sources", help="Debug snapshot directory for --debug-sources")
    parser.add_argument(
        "--html-out",
        default=None,
        help="Path to write formatted HTML report (default: reports/uk_resell_report_<UTC timestamp>.html)",
    )
    return parser


def main() -> None:
    """CLI entrypoint."""
    configure_tracing()
    args = _build_arg_parser().parse_args()

    configure_source_runtime(
        allow_fallback=args.allow_fallback,
        strict_live=args.strict_live,
        debug_sources=args.debug_sources,
        debug_dir=args.debug_dir,
    )

    result = run_local_dry_run()
    report_path = write_html_report(result, Path(args.html_out) if args.html_out else _default_html_output_path())
    if visualizer_events_enabled():
        update_agent_status(
            agent_id="orchestrator",
            name="Agent Orchestrator",
            role="Workflow manager",
            status="completed",
            current_step="Workflow complete",
            progress=100,
            tools=["traceable"],
            current_tool="workflow orchestration",
            current_target="completed run",
            completed_count=3,
            total_count=3,
            last_result=f"{len(result['assessments'])} profitable items delivered",
        )
        update_agent_status(
            agent_id="report",
            name="Report Writer Agent",
            role="Narrative and artifact writer",
            status="completed",
            current_step="Publishing artifacts",
            progress=100,
            tools=["write_html_report"],
            current_tool="write_html_report",
            current_target=str(report_path.name),
            completed_count=1,
            total_count=1,
            last_result=report_path.name,
        )
        emit_visual_event(
            agent_id="report",
            event_type="agent.file_changed",
            title="HTML report packaged",
            summary="The formatted report artifact was written successfully.",
            status="completed",
            metadata={"artifact": str(report_path)},
        )

    if args.json:
        print(json.dumps(result, indent=2))
        print(f"HTML report written to: {report_path}", file=sys.stderr)
        return

    print(f"Discovered marketplaces: {len(result['marketplaces'])}")
    print(f"Candidate items: {len(result['candidate_items'])}")
    print(f"Profitability assessments: {len(result['assessments'])}")
    print(f"HTML report written to: {report_path}")


if __name__ == "__main__":
    main()

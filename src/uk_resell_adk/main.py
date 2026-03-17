from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from uk_resell_adk.config import DEFAULT_CONFIG
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
    profitable = [assessment for assessment in assessments if assessment.estimated_profit_gbp > 0]
    if limit is not None and limit > 0:
        return sorted(
            profitable,
            key=lambda a: (a.estimated_profit_gbp, a.estimated_margin_percent),
            reverse=True,
        )[:limit]
    return sorted(
        profitable,
        key=lambda a: (a.estimated_profit_gbp, a.estimated_margin_percent),
        reverse=True,
    )


def _select_report_candidates(
    candidates: list[CandidateItem], shortlisted_assessments: list[ProfitabilityAssessment]
) -> list[CandidateItem]:
    if not shortlisted_assessments:
        return []
    candidate_by_url = {item.url: item for item in candidates}
    ordered: list[CandidateItem] = []
    seen_urls: set[str] = set()
    for assessment in shortlisted_assessments:
        if assessment.item_url in seen_urls:
            continue
        candidate = candidate_by_url.get(assessment.item_url)
        if candidate is None:
            continue
        seen_urls.add(assessment.item_url)
        ordered.append(candidate)
    return ordered


def _profitability_worker_count(candidate_count: int) -> int:
    raw = os.getenv("PROFITABILITY_CONCURRENCY", str(DEFAULT_CONFIG.profitability_concurrency)).strip()
    try:
        configured = int(raw)
    except ValueError:
        configured = DEFAULT_CONFIG.profitability_concurrency
    return max(1, min(configured, max(1, candidate_count)))


def _assess_candidates_in_parallel(candidates: list[CandidateItem]) -> list[ProfitabilityAssessment]:
    if not candidates:
        return []

    worker_count = _profitability_worker_count(len(candidates))
    if worker_count == 1:
        assessments: list[ProfitabilityAssessment] = []
        for item in candidates:
            if stop_visual_run_requested():
                raise RuntimeError("Run stopped by user.")
            assessments.append(assess_profitability_against_ebay(item))
        return assessments

    assessments: list[ProfitabilityAssessment] = []
    pending: dict[Future[ProfitabilityAssessment], CandidateItem] = {}
    next_index = 0

    with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="profitability") as executor:
        while next_index < len(candidates) and len(pending) < worker_count:
            item = candidates[next_index]
            pending[executor.submit(assess_profitability_against_ebay, item)] = item
            next_index += 1

        while pending:
            done, _ = wait(pending.keys(), return_when=FIRST_COMPLETED)
            for future in done:
                pending.pop(future, None)
                assessments.append(future.result())

                if stop_visual_run_requested():
                    for pending_future in pending:
                        pending_future.cancel()
                    raise RuntimeError("Run stopped by user.")

                if next_index < len(candidates):
                    item = candidates[next_index]
                    pending[executor.submit(assess_profitability_against_ebay, item)] = item
                    next_index += 1

    return assessments


@traceable(name="run_local_dry_run", run_type="chain")
def run_local_dry_run() -> dict:
    """Run the end-to-end workflow: deep sourcing, full analysis, and full report output."""
    if stop_visual_run_requested():
        raise RuntimeError("Run stopped by user.")
    reset_source_diagnostics()
    if visualizer_events_enabled():
        update_agent_status(
            agent_id="orchestrator",
            name="Agent Orchestrator",
            role="Workflow manager",
            status="running",
            current_step="Discovering foreign marketplaces",
            progress=8,
            tools=["traceable"],
            current_tool="workflow orchestration",
            current_target="market discovery and sourcing",
            completed_count=0,
            total_count=3,
            last_result="Sourcing phase starting",
        )
        update_agent_status(
            agent_id="sourcing",
            name="Item Sourcing Agent",
            role="Discovery specialist",
            status="running",
            current_step="Discovering sources",
            progress=12,
            tools=["discover_foreign_marketplaces", "find_candidate_items"],
            current_tool="discover_foreign_marketplaces",
            current_target="configured marketplaces",
        )
        emit_visual_event(
            agent_id="sourcing",
            event_type="agent.started",
            title="Sourcing agent activated",
            summary="Scanning configured marketplaces for trading card candidates.",
            status="running",
        )
    marketplaces = discover_foreign_marketplaces()[: DEFAULT_CONFIG.max_foreign_sites]
    if visualizer_events_enabled():
        emit_visual_event(
            agent_id="sourcing",
            event_type="agent.tool_completed",
            title="Marketplaces discovered",
            summary=f"{len(marketplaces)} source marketplaces are in scope for this run.",
            status="running",
            metadata={"marketplaces": len(marketplaces)},
        )

    candidates: list[CandidateItem] = []
    for market in marketplaces:
        if stop_visual_run_requested():
            raise RuntimeError("Run stopped by user.")
        if visualizer_events_enabled():
            emit_visual_event(
                agent_id="sourcing",
                event_type="agent.tool_called",
                title="Tool call: find_candidate_items",
                summary=f"Fetching candidate items from {market.name}.",
                status="running",
                metadata={"marketplace": market.name},
            )
        candidates.extend(find_candidate_items(market))

    if visualizer_events_enabled():
        update_agent_status(
            agent_id="sourcing",
            name="Item Sourcing Agent",
            role="Discovery specialist",
            status="completed",
            current_step="Candidate pool finalized",
            progress=100,
            tools=["discover_foreign_marketplaces", "find_candidate_items"],
            current_tool="find_candidate_items",
            current_target="all marketplaces",
            completed_count=len(candidates),
            total_count=len(candidates),
            last_result=f"{len(candidates)} candidates collected",
        )
        emit_visual_event(
            agent_id="sourcing",
            event_type="agent.tool_completed",
            title="Candidate pool expanded",
            summary=f"{len(candidates)} candidate items collected across all sources.",
            status="completed",
            metadata={"candidate_count": len(candidates)},
        )
        update_agent_status(
            agent_id="orchestrator",
            name="Agent Orchestrator",
            role="Workflow manager",
            status="running",
            current_step="Transitioning to profitability analysis",
            progress=38,
            tools=["traceable"],
            current_tool="workflow orchestration",
            current_target="profitability analysis",
            completed_count=1,
            total_count=3,
            last_result=f"{len(candidates)} candidates ready",
        )
        update_agent_status(
            agent_id="profitability",
            name="Profitability Agent",
            role="Margin analyst",
            status="running",
            current_step="Analyzing resale margins",
            progress=24,
            tools=["assess_profitability_against_ebay"],
            current_tool="assess_profitability_against_ebay",
            current_target=f"{len(candidates)} candidates",
            completed_count=0,
            total_count=len(candidates),
        )
        emit_visual_event(
            agent_id="profitability",
            event_type="agent.started",
            title="Profitability agent activated",
            summary="Cross-referencing the candidate pool against eBay UK sold-price signals.",
            status="running",
        )

    all_assessments = _assess_candidates_in_parallel(candidates)
    shortlisted_assessments = _select_top_profitable_assessments(all_assessments, limit=None)
    if visualizer_events_enabled():
        update_agent_status(
            agent_id="orchestrator",
            name="Agent Orchestrator",
            role="Workflow manager",
            status="running",
            current_step="Transitioning to report generation",
            progress=72,
            tools=["traceable"],
            current_tool="workflow orchestration",
            current_target="report generation",
            completed_count=2,
            total_count=3,
            last_result=f"{len(shortlisted_assessments)} profitable items ready",
        )
        update_agent_status(
            agent_id="profitability",
            name="Profitability Agent",
            role="Margin analyst",
            status="completed",
            current_step="Ranking opportunities",
            progress=100,
            tools=["assess_profitability_against_ebay"],
            current_tool="assess_profitability_against_ebay",
            current_target="shortlisted opportunities",
            completed_count=len(shortlisted_assessments),
            total_count=len(candidates),
            last_result=f"{len(shortlisted_assessments)} shortlisted",
        )
        emit_visual_event(
            agent_id="profitability",
            event_type="agent.file_changed",
            title="Profitability analysis complete",
            summary=f"{len(shortlisted_assessments)} opportunities were shortlisted for reporting.",
            status="completed",
            metadata={
                "assessment_count": len(shortlisted_assessments),
                "topItems": [
                    {
                        "title": assessment.item_title,
                        "profitGbp": assessment.estimated_profit_gbp,
                        "marginPercent": assessment.estimated_margin_percent,
                        "confidence": assessment.confidence,
                        "url": assessment.item_url,
                    }
                    for assessment in shortlisted_assessments
                ],
            },
        )
    return {
        "marketplaces": [m.to_dict() for m in marketplaces],
        # Report should include every analyzed candidate and every assessment outcome.
        "candidate_items": [c.to_dict() for c in candidates],
        "assessments": [a.to_dict() for a in all_assessments],
        "analyzed_candidate_count": len(candidates),
        "analyzed_assessment_count": len(all_assessments),
        "source_diagnostics": get_source_diagnostics(),
    }


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

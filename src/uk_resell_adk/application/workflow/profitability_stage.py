from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
import os
from typing import Any, Callable

from uk_resell_adk.live_events import emit_visual_event, stop_visual_run_requested, update_agent_status, visualizer_events_enabled
from uk_resell_adk.models import CandidateItem, ProfitabilityAssessment
from uk_resell_adk.tools import assess_profitability_against_ebay


@dataclass(slots=True)
class ProfitabilityStageResult:
    all_assessments: list[ProfitabilityAssessment]
    shortlisted_assessments: list[ProfitabilityAssessment]


def select_top_profitable_assessments(
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


def profitability_worker_count(*, candidate_count: int, default_concurrency: int) -> int:
    raw = os.getenv("PROFITABILITY_CONCURRENCY", str(default_concurrency)).strip()
    try:
        configured = int(raw)
    except ValueError:
        configured = default_concurrency
    return max(1, min(configured, max(1, candidate_count)))


def assess_candidates_in_parallel(
    candidates: list[CandidateItem],
    *,
    default_concurrency: int,
    assess_profitability: Callable[[CandidateItem], ProfitabilityAssessment] = assess_profitability_against_ebay,
    stop_requested: Callable[[], bool] = stop_visual_run_requested,
) -> list[ProfitabilityAssessment]:
    if not candidates:
        return []

    worker_count = profitability_worker_count(candidate_count=len(candidates), default_concurrency=default_concurrency)
    if worker_count == 1:
        serial_assessments: list[ProfitabilityAssessment] = []
        for item in candidates:
            if stop_requested():
                raise RuntimeError("Run stopped by user.")
            serial_assessments.append(assess_profitability(item))
        return serial_assessments

    assessments: list[ProfitabilityAssessment] = []
    pending: dict[Future[ProfitabilityAssessment], CandidateItem] = {}
    next_index = 0

    with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="profitability") as executor:
        while next_index < len(candidates) and len(pending) < worker_count:
            item = candidates[next_index]
            pending[executor.submit(assess_profitability, item)] = item
            next_index += 1

        while pending:
            done, _ = wait(pending.keys(), return_when=FIRST_COMPLETED)
            for future in done:
                pending.pop(future, None)
                assessments.append(future.result())

                if stop_requested():
                    for pending_future in pending:
                        pending_future.cancel()
                    raise RuntimeError("Run stopped by user.")

                if next_index < len(candidates):
                    item = candidates[next_index]
                    pending[executor.submit(assess_profitability, item)] = item
                    next_index += 1

    return assessments


def run_profitability_stage(
    *,
    candidates: list[CandidateItem],
    default_concurrency: int,
    assess_profitability: Callable[[CandidateItem], ProfitabilityAssessment] = assess_profitability_against_ebay,
    stop_requested: Callable[[], bool] = stop_visual_run_requested,
    events_enabled: Callable[[], bool] = visualizer_events_enabled,
    emit_event: Callable[..., dict[str, Any] | None] = emit_visual_event,
    update_agent: Callable[..., None] = update_agent_status,
) -> ProfitabilityStageResult:
    if events_enabled():
        update_agent(
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
        emit_event(
            agent_id="profitability",
            event_type="agent.started",
            title="Profitability agent activated",
            summary="Cross-referencing the candidate pool against eBay UK sold-price signals.",
            status="running",
        )

    all_assessments = assess_candidates_in_parallel(
        candidates,
        default_concurrency=default_concurrency,
        assess_profitability=assess_profitability,
        stop_requested=stop_requested,
    )
    shortlisted_assessments = select_top_profitable_assessments(all_assessments, limit=None)

    if events_enabled():
        update_agent(
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
        update_agent(
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
        emit_event(
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

    return ProfitabilityStageResult(
        all_assessments=all_assessments,
        shortlisted_assessments=shortlisted_assessments,
    )

from __future__ import annotations

from uk_resell_adk.application.workflow.profitability_stage import (
    profitability_worker_count,
    run_profitability_stage,
    select_top_profitable_assessments,
)
from uk_resell_adk.models import CandidateItem, ProfitabilityAssessment


def test_profitability_worker_count_respects_env(monkeypatch) -> None:
    monkeypatch.setenv("PROFITABILITY_CONCURRENCY", "9")
    assert profitability_worker_count(candidate_count=3, default_concurrency=2) == 3

    monkeypatch.setenv("PROFITABILITY_CONCURRENCY", "bad")
    assert profitability_worker_count(candidate_count=3, default_concurrency=2) == 2


def test_select_top_profitable_assessments_filters_and_orders() -> None:
    assessments = [
        ProfitabilityAssessment("A", "u1", 10, 20, 2, 8.0, 12.0, "high"),
        ProfitabilityAssessment("B", "u2", 10, 19, 2, 7.0, 15.0, "high"),
        ProfitabilityAssessment("C", "u3", 10, 9, 2, -3.0, -10.0, "low"),
    ]

    shortlisted = select_top_profitable_assessments(assessments, limit=None)
    assert [item.item_title for item in shortlisted] == ["A", "B"]


def test_run_profitability_stage_returns_all_and_shortlisted_without_events() -> None:
    candidates = [
        CandidateItem("S", "One", "u1", 10.0, 1.0, "New"),
        CandidateItem("S", "Two", "u2", 10.0, 1.0, "New"),
    ]
    by_url = {
        "u1": ProfitabilityAssessment("One", "u1", 11.0, 20.0, 2.0, 7.0, 30.0, "high"),
        "u2": ProfitabilityAssessment("Two", "u2", 11.0, 10.0, 2.0, -3.0, -20.0, "low"),
    }

    result = run_profitability_stage(
        candidates=candidates,
        default_concurrency=1,
        assess_profitability=lambda candidate: by_url[candidate.url],
        stop_requested=lambda: False,
        events_enabled=lambda: False,
    )

    assert len(result.all_assessments) == 2
    assert [item.item_title for item in result.shortlisted_assessments] == ["One"]

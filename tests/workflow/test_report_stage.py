from __future__ import annotations

from uk_resell_adk.application.workflow.report_stage import run_report_stage, select_report_candidates
from uk_resell_adk.models import CandidateItem, MarketplaceSite, ProfitabilityAssessment


def test_select_report_candidates_preserves_shortlist_order() -> None:
    candidates = [
        CandidateItem("S", "One", "u1", 10.0, 1.0, "New"),
        CandidateItem("S", "Two", "u2", 10.0, 1.0, "New"),
    ]
    shortlist = [
        ProfitabilityAssessment("Two", "u2", 11.0, 19.0, 2.0, 6.0, 22.0, "high"),
        ProfitabilityAssessment("One", "u1", 11.0, 20.0, 2.0, 7.0, 30.0, "high"),
    ]

    ordered = select_report_candidates(candidates, shortlist)
    assert [item.title for item in ordered] == ["Two", "One"]


def test_run_report_stage_builds_full_analyzed_payload() -> None:
    markets = [MarketplaceSite("M1", "JP", "https://m1.example", "reason")]
    candidates = [CandidateItem("M1", "One", "u1", 10.0, 1.0, "New")]
    assessments = [ProfitabilityAssessment("One", "u1", 11.0, 20.0, 2.0, 7.0, 30.0, "high")]

    payload = run_report_stage(
        marketplaces=markets,
        candidates=candidates,
        assessments=assessments,
        source_diagnostics=[{"diagnostic": True}],
    )

    assert payload["analyzed_candidate_count"] == 1
    assert payload["analyzed_assessment_count"] == 1
    assert payload["source_diagnostics"] == [{"diagnostic": True}]
    assert payload["candidate_items"][0]["title"] == "One"
    assert payload["assessments"][0]["item_title"] == "One"

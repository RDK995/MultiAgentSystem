from __future__ import annotations

from typing import Any

from uk_resell_adk.models import CandidateItem, MarketplaceSite, ProfitabilityAssessment


def select_report_candidates(
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


def run_report_stage(
    *,
    marketplaces: list[MarketplaceSite],
    candidates: list[CandidateItem],
    assessments: list[ProfitabilityAssessment],
    source_diagnostics: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "marketplaces": [marketplace.to_dict() for marketplace in marketplaces],
        "candidate_items": [candidate.to_dict() for candidate in candidates],
        "assessments": [assessment.to_dict() for assessment in assessments],
        "analyzed_candidate_count": len(candidates),
        "analyzed_assessment_count": len(assessments),
        "source_diagnostics": source_diagnostics,
    }

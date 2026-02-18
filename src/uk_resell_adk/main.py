from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from uk_resell_adk.config import DEFAULT_CONFIG
from uk_resell_adk.html_renderer import write_html_report
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
    assessments: list[ProfitabilityAssessment], *, limit: int
) -> list[ProfitabilityAssessment]:
    if limit <= 0:
        return []
    return sorted(
        assessments,
        key=lambda a: (a.estimated_profit_gbp, a.estimated_margin_percent),
        reverse=True,
    )[:limit]


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


@traceable(name="run_local_dry_run", run_type="chain")
def run_local_dry_run() -> dict:
    """Run the end-to-end workflow: deep sourcing, full analysis, focused report shortlist."""
    reset_source_diagnostics()
    marketplaces = discover_foreign_marketplaces()[: DEFAULT_CONFIG.max_foreign_sites]

    candidates: list[CandidateItem] = []
    for market in marketplaces:
        candidates.extend(find_candidate_items(market))

    all_assessments = [assess_profitability_against_ebay(item) for item in candidates]
    shortlisted_assessments = _select_top_profitable_assessments(
        all_assessments, limit=DEFAULT_CONFIG.max_items_per_source
    )
    report_candidates = _select_report_candidates(candidates, shortlisted_assessments)
    return {
        "marketplaces": [m.to_dict() for m in marketplaces],
        "candidate_items": [c.to_dict() for c in report_candidates],
        "assessments": [a.to_dict() for a in shortlisted_assessments],
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

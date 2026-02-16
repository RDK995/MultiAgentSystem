from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from uk_resell_adk.config import DEFAULT_CONFIG
from uk_resell_adk.html_renderer import write_html_report
from uk_resell_adk.tracing import configure_langsmith, traceable
from uk_resell_adk.tools import (
    assess_profitability_against_ebay,
    discover_foreign_marketplaces,
    find_candidate_items,
)


@traceable(name="run_local_dry_run", run_type="chain")
def run_local_dry_run() -> dict:
    marketplaces = discover_foreign_marketplaces()[: DEFAULT_CONFIG.max_foreign_sites]

    candidates = []
    for market in marketplaces:
        candidates.extend(find_candidate_items(market)[: DEFAULT_CONFIG.max_items_per_site])

    assessments = [assess_profitability_against_ebay(item) for item in candidates]

    return {
        "marketplaces": [m.to_dict() for m in marketplaces],
        "candidate_items": [c.to_dict() for c in candidates],
        "assessments": [a.to_dict() for a in assessments],
    }


def _default_html_output_path() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return Path("reports") / f"uk_resell_report_{timestamp}.html"


def main() -> None:
    configure_langsmith()
    parser = argparse.ArgumentParser(description="UK resale ADK multi-agent dry run helper")
    parser.add_argument("--json", action="store_true", help="Print workflow output as JSON")
    parser.add_argument(
        "--html-out",
        default=None,
        help="Path to write formatted HTML report (default: reports/uk_resell_report_<UTC timestamp>.html)",
    )
    args = parser.parse_args()

    result = run_local_dry_run()
    report_path = write_html_report(result, Path(args.html_out) if args.html_out else _default_html_output_path())
    if args.json:
        print(json.dumps(result, indent=2))
        print(f"HTML report written to: {report_path}", file=sys.stderr)
    else:
        print(f"Discovered marketplaces: {len(result['marketplaces'])}")
        print(f"Candidate items: {len(result['candidate_items'])}")
        print(f"Profitability assessments: {len(result['assessments'])}")
        print(f"HTML report written to: {report_path}")


if __name__ == "__main__":
    main()

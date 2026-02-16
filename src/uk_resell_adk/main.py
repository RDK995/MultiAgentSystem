from __future__ import annotations

import argparse
import json

from uk_resell_adk.config import DEFAULT_CONFIG
from uk_resell_adk.tools import (
    assess_profitability_against_ebay,
    discover_foreign_marketplaces,
    find_candidate_items,
)


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


def main() -> None:
    parser = argparse.ArgumentParser(description="UK resale ADK multi-agent dry run helper")
    parser.add_argument("--json", action="store_true", help="Print workflow output as JSON")
    args = parser.parse_args()

    result = run_local_dry_run()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Discovered marketplaces: {len(result['marketplaces'])}")
        print(f"Candidate items: {len(result['candidate_items'])}")
        print(f"Profitability assessments: {len(result['assessments'])}")


if __name__ == "__main__":
    main()

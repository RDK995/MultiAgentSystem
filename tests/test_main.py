from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from uk_resell_adk import main


SAMPLE_RESULT = {
    "marketplaces": [
        {
            "name": "Meccha Japan",
            "country": "Japan",
            "url": "https://meccha-japan.com/",
            "reason": "focused catalog",
        }
    ],
    "candidate_items": [
        {
            "site_name": "Meccha Japan",
            "title": "Item A",
            "url": "https://meccha-japan.com/a",
            "source_price_gbp": 20.0,
            "shipping_to_uk_gbp": 10.0,
            "condition": "New",
        }
    ],
    "assessments": [
        {
            "item_title": "Low",
            "item_url": "https://meccha-japan.com/l",
            "total_landed_cost_gbp": 100.0,
            "ebay_median_sale_price_gbp": 90.0,
            "estimated_fees_gbp": 10.0,
            "estimated_profit_gbp": -20.0,
            "estimated_margin_percent": -20.0,
            "confidence": "low",
        },
        {
            "item_title": "High",
            "item_url": "https://meccha-japan.com/h",
            "total_landed_cost_gbp": 100.0,
            "ebay_median_sale_price_gbp": 160.0,
            "estimated_fees_gbp": 20.0,
            "estimated_profit_gbp": 40.0,
            "estimated_margin_percent": 40.0,
            "confidence": "high",
        },
    ],
}


def test_run_local_dry_run_respects_config_limits(monkeypatch: Any) -> None:
    from uk_resell_adk.models import CandidateItem, MarketplaceSite, ProfitabilityAssessment

    original_sites = main.DEFAULT_CONFIG.max_foreign_sites
    original_items = main.DEFAULT_CONFIG.max_items_per_site

    try:
        main.DEFAULT_CONFIG.max_foreign_sites = 1
        main.DEFAULT_CONFIG.max_items_per_site = 2

        monkeypatch.setattr(
            main,
            "discover_foreign_marketplaces",
            lambda: [
                MarketplaceSite("Meccha Japan", "Japan", "https://meccha-japan.com", "a"),
                MarketplaceSite("Ignored", "Japan", "https://x.com", "b"),
            ],
        )

        monkeypatch.setattr(
            main,
            "find_candidate_items",
            lambda _m: [
                CandidateItem("Meccha Japan", "A", "u1", 1.0, 1.0, "New"),
                CandidateItem("Meccha Japan", "B", "u2", 1.0, 1.0, "New"),
                CandidateItem("Meccha Japan", "C", "u3", 1.0, 1.0, "New"),
            ],
        )

        monkeypatch.setattr(
            main,
            "assess_profitability_against_ebay",
            lambda item: ProfitabilityAssessment(
                item_title=item.title,
                item_url=item.url,
                total_landed_cost_gbp=2.0,
                ebay_median_sale_price_gbp=3.0,
                estimated_fees_gbp=0.4,
                estimated_profit_gbp=0.6,
                estimated_margin_percent=30.0,
                confidence="medium",
            ),
        )

        result = main.run_local_dry_run()

        assert len(result["marketplaces"]) == 1
        assert len(result["candidate_items"]) == 2
        assert len(result["assessments"]) == 2
    finally:
        main.DEFAULT_CONFIG.max_foreign_sites = original_sites
        main.DEFAULT_CONFIG.max_items_per_site = original_items


def test_main_json_mode_writes_json_to_stdout_and_report_notice_to_stderr(
    monkeypatch: Any, capsys: Any, tmp_path: Path
) -> None:
    out = tmp_path / "report.html"
    monkeypatch.setattr(main, "run_local_dry_run", lambda: SAMPLE_RESULT)
    monkeypatch.setattr(main, "configure_langsmith", lambda: None)

    monkeypatch.setattr(sys, "argv", ["prog", "--json", "--html-out", str(out)])
    main.main()

    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed["marketplaces"][0]["name"] == "Meccha Japan"
    assert "HTML report written to" in captured.err
    assert out.exists()


def test_main_text_mode_prints_summary(monkeypatch: Any, capsys: Any, tmp_path: Path) -> None:
    out = tmp_path / "report.html"
    monkeypatch.setattr(main, "run_local_dry_run", lambda: SAMPLE_RESULT)
    monkeypatch.setattr(main, "configure_langsmith", lambda: None)

    monkeypatch.setattr(sys, "argv", ["prog", "--html-out", str(out)])
    main.main()

    captured = capsys.readouterr()
    assert "Discovered marketplaces: 1" in captured.out
    assert "Candidate items: 1" in captured.out
    assert "Profitability assessments: 2" in captured.out
    assert "HTML report written to" in captured.out
    assert out.exists()


def test_main_uses_unique_default_html_output_path(monkeypatch: Any, capsys: Any, tmp_path: Path) -> None:
    out = tmp_path / "uk_resell_report_20260216_120000.html"
    monkeypatch.setattr(main, "run_local_dry_run", lambda: SAMPLE_RESULT)
    monkeypatch.setattr(main, "configure_langsmith", lambda: None)
    monkeypatch.setattr(main, "_default_html_output_path", lambda: out)

    monkeypatch.setattr(sys, "argv", ["prog", "--json"])
    main.main()

    captured = capsys.readouterr()
    assert str(out) in captured.err
    assert out.exists()

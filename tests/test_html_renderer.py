from __future__ import annotations

from uk_resell_adk.html_renderer import build_html_report


def test_build_html_report_uses_green_for_profitable_and_red_for_unprofitable() -> None:
    result = {
        "marketplaces": [
            {
                "name": "Meccha Japan",
                "country": "Japan",
                "url": "https://meccha-japan.com/",
                "reason": "focused catalog",
            }
        ],
        "candidate_items": [],
        "assessments": [
            {
                "item_title": "Profit Item",
                "item_url": "https://meccha-japan.com/p",
                "total_landed_cost_gbp": 100.0,
                "ebay_median_sale_price_gbp": 130.0,
                "estimated_fees_gbp": 0.0,
                "estimated_profit_gbp": 30.0,
                "estimated_margin_percent": 30.0,
                "confidence": "high",
            },
            {
                "item_title": "Loss Item",
                "item_url": "https://meccha-japan.com/l",
                "total_landed_cost_gbp": 100.0,
                "ebay_median_sale_price_gbp": 80.0,
                "estimated_fees_gbp": 0.0,
                "estimated_profit_gbp": -20.0,
                "estimated_margin_percent": -20.0,
                "confidence": "low",
            },
        ],
    }

    html = build_html_report(result)

    assert "<td class=\"good\">GBP 30.00</td>" in html
    assert "<td class=\"bad\">GBP -20.00</td>" in html
    assert "<td class=\"good\">30.00%</td>" in html
    assert "<td class=\"bad\">-20.00%</td>" in html

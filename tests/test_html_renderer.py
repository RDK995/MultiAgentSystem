from __future__ import annotations

from uk_resell_adk.html_renderer import build_html_report


def test_build_html_report_uses_green_for_profitable_and_red_for_unprofitable() -> None:
    result = {
        "marketplaces": [
            {
                "name": "HobbyLink Japan",
                "country": "Japan",
                "url": "https://www.hlj.com/",
                "reason": "focused catalog",
            }
        ],
        "candidate_items": [
            {
                "site_name": "HobbyLink Japan",
                "title": "Profit Item",
                "url": "https://www.hlj.com/p",
                "source_price_gbp": 70.0,
                "shipping_to_uk_gbp": 15.0,
                "condition": "New",
                "data_origin": "live",
            },
            {
                "site_name": "HobbyLink Japan",
                "title": "Loss Item",
                "url": "https://www.hlj.com/l",
                "source_price_gbp": 70.0,
                "shipping_to_uk_gbp": 15.0,
                "condition": "New",
                "data_origin": "fallback",
            },
        ],
        "assessments": [
            {
                "item_title": "Profit Item",
                "item_url": "https://www.hlj.com/p",
                "total_landed_cost_gbp": 100.0,
                "ebay_median_sale_price_gbp": 130.0,
                "estimated_fees_gbp": 0.0,
                "estimated_profit_gbp": 30.0,
                "estimated_margin_percent": 30.0,
                "confidence": "high",
            },
            {
                "item_title": "Loss Item",
                "item_url": "https://www.hlj.com/l",
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
    assert "Live Scrape" in html
    assert "Fallback" in html
    assert "<li>Live: 1</li>" in html
    assert "<li>Fallback: 1</li>" in html

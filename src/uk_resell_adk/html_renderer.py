from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path


def build_html_report(result: dict) -> str:
    marketplaces = result["marketplaces"]
    candidate_items = result["candidate_items"]
    assessments = sorted(result["assessments"], key=lambda x: x["estimated_profit_gbp"], reverse=True)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    rows = []
    for item in assessments:
        margin = float(item["estimated_margin_percent"])
        profit = float(item["estimated_profit_gbp"])
        profit_class = "good" if profit >= 0 else "bad"
        margin_class = "good" if margin >= 0 else "bad"
        rows.append(
            "<tr>"
            f"<td>{html.escape(item['item_title'])}</td>"
            f"<td><a href=\"{html.escape(item['item_url'])}\" target=\"_blank\">Link</a></td>"
            f"<td>GBP {item['total_landed_cost_gbp']:.2f}</td>"
            f"<td>GBP {item['ebay_median_sale_price_gbp']:.2f}</td>"
            f"<td>GBP {item['estimated_fees_gbp']:.2f}</td>"
            f"<td class=\"{profit_class}\">GBP {profit:.2f}</td>"
            f"<td class=\"{margin_class}\">{margin:.2f}%</td>"
            f"<td>{html.escape(item['confidence'])}</td>"
            "</tr>"
        )

    marketplace_lines = "".join(
        f"<li><strong>{html.escape(site['name'])}</strong> ({html.escape(site['country'])}) - "
        f"<a href=\"{html.escape(site['url'])}\" target=\"_blank\">{html.escape(site['url'])}</a><br>"
        f"{html.escape(site['reason'])}</li>"
        for site in marketplaces
    )

    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>UK Resell Lead Report</title>
  <style>
    body {{ font-family: 'Segoe UI', Tahoma, sans-serif; margin: 24px; background: #f7fafc; color: #1f2937; }}
    h1 {{ margin-bottom: 4px; }}
    .meta {{ color: #4b5563; margin-bottom: 20px; }}
    .card {{ background: white; border-radius: 10px; padding: 16px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
    .stats {{ display: flex; gap: 16px; flex-wrap: wrap; }}
    .stat {{ background: #eef2ff; border-radius: 8px; padding: 10px 12px; min-width: 180px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ border-bottom: 1px solid #e5e7eb; padding: 10px 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f9fafb; }}
    .good {{ color: #065f46; font-weight: 600; }}
    .bad {{ color: #991b1b; font-weight: 600; }}
  </style>
</head>
<body>
  <h1>UK Resell Lead Report</h1>
  <div class=\"meta\">Generated: {generated_at}</div>

  <div class=\"card stats\">
    <div class=\"stat\"><strong>Marketplaces:</strong> {len(marketplaces)}</div>
    <div class=\"stat\"><strong>Candidate Items:</strong> {len(candidate_items)}</div>
    <div class=\"stat\"><strong>Assessments:</strong> {len(assessments)}</div>
  </div>

  <div class=\"card\">
    <h2>Source Marketplace</h2>
    <ul>{marketplace_lines}</ul>
  </div>

  <div class=\"card\">
    <h2>Profitability Assessments</h2>
    <table>
      <thead>
        <tr>
          <th>Item</th>
          <th>Source</th>
          <th>Landed Cost</th>
          <th>eBay Median</th>
          <th>Fees</th>
          <th>Profit</th>
          <th>Margin</th>
          <th>Confidence</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows)}
      </tbody>
    </table>
  </div>
</body>
</html>
"""


def write_html_report(result: dict, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_html_report(result), encoding="utf-8")
    return output_path

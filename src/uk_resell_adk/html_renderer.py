from __future__ import annotations

"""HTML report rendering helpers.

The renderer intentionally keeps logic local and template-free so output remains
predictable and testable.
"""

from datetime import datetime, timezone
import html
from pathlib import Path


def _origin_label_and_class(origin: str) -> tuple[str, str]:
    if origin == "live":
        return "Live Scrape", "live"
    if origin == "fallback":
        return "Fallback", "fallback"
    return "Unknown", "unknown"


def _build_source_lines(marketplaces: list[dict]) -> str:
    return "".join(
        f"<li><strong>{html.escape(site['name'])}</strong> ({html.escape(site['country'])}) - "
        f"<a href=\"{html.escape(site['url'])}\" target=\"_blank\">{html.escape(site['url'])}</a><br>"
        f"{html.escape(site['reason'])}</li>"
        for site in marketplaces
    )


def _build_diagnostics_rows(source_diagnostics: list[dict]) -> str:
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(d.get('source_name', '')))}</td>"
        f"<td>{html.escape(str(d.get('status', '')))}</td>"
        f"<td>{int(d.get('live_count', 0))}</td>"
        f"<td>{int(d.get('fallback_count', 0))}</td>"
        f"<td>{int(d.get('blocked_count', 0))}</td>"
        f"<td>{int(d.get('parse_miss_count', 0))}</td>"
        f"<td>{int(d.get('error_count', 0))}</td>"
        "</tr>"
        for d in source_diagnostics
    )
    return rows or '<tr><td colspan="7">No diagnostics.</td></tr>'


def _build_assessment_rows(assessments: list[dict], origin_by_url: dict[str, str]) -> str:
    rows: list[str] = []
    for item in assessments:
        margin = float(item.get("estimated_margin_percent", 0.0))
        profit = float(item.get("estimated_profit_gbp", 0.0))
        profit_class = "good" if profit >= 0 else "bad"
        margin_class = "good" if margin >= 0 else "bad"
        origin = origin_by_url.get(item["item_url"], "unknown")
        origin_label, origin_class = _origin_label_and_class(origin)

        rows.append(
            "<tr>"
            f"<td>{html.escape(item['item_title'])}</td>"
            f"<td><a href=\"{html.escape(item['item_url'])}\" target=\"_blank\">Link</a></td>"
            f"<td><span class=\"tag {origin_class}\">{origin_label}</span></td>"
            f"<td>GBP {float(item.get('total_landed_cost_gbp', 0.0)):.2f}</td>"
            f"<td>GBP {float(item.get('ebay_median_sale_price_gbp', 0.0)):.2f}</td>"
            f"<td>GBP {float(item.get('estimated_fees_gbp', 0.0)):.2f}</td>"
            f"<td class=\"{profit_class}\">GBP {profit:.2f}</td>"
            f"<td class=\"{margin_class}\">{margin:.2f}%</td>"
            f"<td>{html.escape(str(item.get('confidence', 'unknown')))}</td>"
            "</tr>"
        )
    return "".join(rows)


def build_html_report(result: dict) -> str:
    """Render the report as a standalone HTML document."""
    marketplaces = result["marketplaces"]
    candidate_items = result["candidate_items"]
    assessments = sorted(
        result["assessments"],
        key=lambda x: float(x.get("estimated_profit_gbp", 0.0)),
        reverse=True,
    )
    source_diagnostics = result.get("source_diagnostics", [])

    by_source: dict[str, int] = {}
    by_origin: dict[str, int] = {}
    origin_by_url: dict[str, str] = {}
    for item in candidate_items:
        source_name = item["site_name"]
        by_source[source_name] = by_source.get(source_name, 0) + 1

        origin = str(item.get("data_origin", "unknown")).lower()
        by_origin[origin] = by_origin.get(origin, 0) + 1
        origin_by_url[str(item.get("url", ""))] = origin

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    assessment_rows = _build_assessment_rows(assessments, origin_by_url)
    marketplace_lines = _build_source_lines(marketplaces)
    diagnostics_rows = _build_diagnostics_rows(source_diagnostics)

    by_source_lines = "".join(f"<li>{html.escape(k)}: {v}</li>" for k, v in sorted(by_source.items()))
    by_origin_lines = "".join(f"<li>{html.escape(k.title())}: {v}</li>" for k, v in sorted(by_origin.items()))

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
    .tag {{ display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; font-weight: 600; }}
    .tag.live {{ background: #dcfce7; color: #065f46; }}
    .tag.fallback {{ background: #fee2e2; color: #991b1b; }}
    .tag.unknown {{ background: #e5e7eb; color: #374151; }}
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
    <h2>Candidate Count by Source</h2>
    <ul>{by_source_lines or '<li>No candidates found.</li>'}</ul>
  </div>
  <div class=\"card\">
    <h2>Data Provenance</h2>
    <ul>{by_origin_lines or '<li>No provenance data.</li>'}</ul>
  </div>
  <div class=\"card\">
    <h2>Source Diagnostics</h2>
    <table>
      <thead>
        <tr>
          <th>Source</th>
          <th>Status</th>
          <th>Live</th>
          <th>Fallback</th>
          <th>Blocked</th>
          <th>Parse Misses</th>
          <th>Errors</th>
        </tr>
      </thead>
      <tbody>
        {diagnostics_rows}
      </tbody>
    </table>
  </div>

  <div class=\"card\">
    <h2>Profitability Assessments</h2>
    <table>
      <thead>
        <tr>
          <th>Item</th>
          <th>Source</th>
          <th>Data Origin</th>
          <th>Landed Cost</th>
          <th>eBay Median</th>
          <th>Fees</th>
          <th>Profit</th>
          <th>Margin</th>
          <th>Confidence</th>
        </tr>
      </thead>
      <tbody>
        {assessment_rows}
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

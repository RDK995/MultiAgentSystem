from __future__ import annotations

from statistics import median

from urllib.parse import urlencode
from urllib.request import Request, urlopen

from uk_resell_adk.models import CandidateItem, MarketplaceSite, ProfitabilityAssessment


USER_AGENT = "uk-resell-adk/0.1 (+research assistant)"


def discover_foreign_marketplaces() -> list[MarketplaceSite]:
    """Agent 1 tool: return foreign marketplaces frequently used for export arbitrage.

    This is deliberately curated because many marketplaces have anti-bot terms and rate limits.
    In production, replace this with a compliant search/index source and jurisdiction checks.
    """

    return [
        MarketplaceSite(
            name="Mercari Japan",
            country="Japan",
            url="https://jp.mercari.com/",
            reason="High volume of collectible categories with price spread to UK buyers.",
        ),
        MarketplaceSite(
            name="Yahoo! Auctions Japan",
            country="Japan",
            url="https://auctions.yahoo.co.jp/",
            reason="Frequent underpriced bundles and niche hobby listings.",
        ),
        MarketplaceSite(
            name="Buyee (proxy marketplace)",
            country="Japan",
            url="https://buyee.jp/",
            reason="Aggregates Japanese marketplaces and supports international shipping.",
        ),
        MarketplaceSite(
            name="Kleinanzeigen",
            country="Germany",
            url="https://www.kleinanzeigen.de/",
            reason="Strong local second-hand supply in electronics and bike components.",
        ),
    ]


def find_candidate_items(marketplace: MarketplaceSite) -> list[CandidateItem]:
    """Agent 2 tool: seed examples per marketplace.

    Keep the output structured and conservative; do not claim live availability unless
    a compliant live search integration is attached.
    """

    sample_catalog: dict[str, list[tuple[str, str, float, float, str]]] = {
        "Mercari Japan": [
            (
                "Sony Walkman WM-EX series cassette player",
                "https://jp.mercari.com/search?keyword=sony%20walkman",
                85.0,
                22.0,
                "Used",
            ),
            (
                "Pokémon Center plush (limited regional release)",
                "https://jp.mercari.com/search?keyword=pokemon%20center%20plush",
                28.0,
                18.0,
                "New",
            ),
        ],
        "Yahoo! Auctions Japan": [
            (
                "Retro game bundle (Super Famicom titles)",
                "https://auctions.yahoo.co.jp/search/search?p=super+famicom",
                60.0,
                24.0,
                "Used",
            ),
        ],
        "Buyee (proxy marketplace)": [
            (
                "Seiko JDM watch model",
                "https://buyee.jp/item/search/query/seiko%20jdm",
                140.0,
                20.0,
                "Used",
            ),
        ],
        "Kleinanzeigen": [
            (
                "Shimano Ultegra groupset",
                "https://www.kleinanzeigen.de/s-shimano-ultegra/k0",
                250.0,
                30.0,
                "Used",
            ),
        ],
    }

    rows = sample_catalog.get(marketplace.name, [])
    return [
        CandidateItem(
            site_name=marketplace.name,
            title=title,
            url=url,
            source_price_gbp=source_price,
            shipping_to_uk_gbp=shipping,
            condition=condition,
        )
        for title, url, source_price, shipping, condition in rows
    ]


def _safe_fetch_ebay_price_snapshots(query: str) -> list[float]:
    """Fetch rough sold-price snapshots from eBay search page JSON snippets.

    This lightweight fallback avoids requiring API keys. For production usage, replace with
    official eBay Browse API / Marketplace Insights API and robust parsing.
    """

    endpoint = "https://www.ebay.co.uk/sch/i.html"
    params = {
        "_nkw": query,
        "LH_Sold": "1",
        "LH_Complete": "1",
        "rt": "nc",
    }
    headers = {"User-Agent": USER_AGENT}

    query = urlencode(params)
    request = Request(f"{endpoint}?{query}", headers=headers)
    try:
        with urlopen(request, timeout=10) as response:
            content = response.read().decode("utf-8", errors="ignore")
    except Exception:
        return []

    prices: list[float] = []
    for token in content.split("\u00a3"):
        number = []
        for char in token:
            if char.isdigit() or char in {".", ","}:
                number.append(char)
            elif number:
                break
        if not number:
            continue
        raw = "".join(number).replace(",", "")
        try:
            value = float(raw)
        except ValueError:
            continue
        if 3 <= value <= 10000:
            prices.append(value)
        if len(prices) >= 20:
            break
    return prices


def assess_profitability_against_ebay(item: CandidateItem) -> ProfitabilityAssessment:
    """Agent 3 tool: estimate arbitrage profitability from eBay sold-price snapshots."""

    sold_prices = _safe_fetch_ebay_price_snapshots(item.title)
    benchmark = median(sold_prices) if sold_prices else item.source_price_gbp * 1.35

    landed_cost = item.source_price_gbp + item.shipping_to_uk_gbp
    fees = benchmark * 0.145
    profit = benchmark - landed_cost - fees
    margin = (profit / landed_cost) * 100 if landed_cost else 0

    if sold_prices and len(sold_prices) >= 8:
        confidence = "high"
    elif sold_prices:
        confidence = "medium"
    else:
        confidence = "low"

    return ProfitabilityAssessment(
        item_title=item.title,
        item_url=item.url,
        total_landed_cost_gbp=round(landed_cost, 2),
        ebay_median_sale_price_gbp=round(benchmark, 2),
        estimated_fees_gbp=round(fees, 2),
        estimated_profit_gbp=round(profit, 2),
        estimated_margin_percent=round(margin, 2),
        confidence=confidence,
    )

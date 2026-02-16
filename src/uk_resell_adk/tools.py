from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen

from uk_resell_adk.models import CandidateItem, MarketplaceSite, ProfitabilityAssessment
from uk_resell_adk.tracing import traceable


USER_AGENT = "uk-resell-adk/0.1 (+research assistant)"

# eBay UK private seller baseline (non-vehicle categories):
# "No transaction or final value fees" for UK-based private sellers.
# Source: https://www.ebay.co.uk/help/fees-credits-invoices/selling-fees/fees-private-sellers?id=4822
EBAY_FINAL_VALUE_FEE_RATE = 0.0
EBAY_PER_ORDER_FEE_GBP = 0.0


@dataclass(frozen=True, slots=True)
class _MecchaSeed:
    title: str
    query: str
    source_price_gbp: float
    shipping_to_uk_gbp: float
    demand_weight: float
    competition_penalty: float
    volatility_penalty: float


_MECCHA_JAPAN_SEEDS: tuple[_MecchaSeed, ...] = (
    _MecchaSeed(
        title="Pokemon Center Japan Exclusive Plush (seasonal release)",
        query="pokemon center japan exclusive plush",
        source_price_gbp=28.0,
        shipping_to_uk_gbp=16.0,
        demand_weight=9.1,
        competition_penalty=2.4,
        volatility_penalty=1.2,
    ),
    _MecchaSeed(
        title="Bandai Metal Build Gundam figure (Japan release)",
        query="bandai metal build gundam japan",
        source_price_gbp=170.0,
        shipping_to_uk_gbp=22.0,
        demand_weight=8.4,
        competition_penalty=2.8,
        volatility_penalty=2.2,
    ),
    _MecchaSeed(
        title="S.H.Figuarts Dragon Ball event-limited figure",
        query="sh figuarts dragon ball event limited",
        source_price_gbp=72.0,
        shipping_to_uk_gbp=18.0,
        demand_weight=8.7,
        competition_penalty=2.6,
        volatility_penalty=1.9,
    ),
    _MecchaSeed(
        title="One Piece Portrait.Of.Pirates limited statue",
        query="one piece portrait of pirates limited",
        source_price_gbp=118.0,
        shipping_to_uk_gbp=21.0,
        demand_weight=8.3,
        competition_penalty=2.3,
        volatility_penalty=2.1,
    ),
    _MecchaSeed(
        title="Studio Ghibli Donguri collectible figure",
        query="studio ghibli donguri collectible figure",
        source_price_gbp=34.0,
        shipping_to_uk_gbp=17.0,
        demand_weight=7.9,
        competition_penalty=2.0,
        volatility_penalty=1.4,
    ),
    _MecchaSeed(
        title="Sanrio Japan collaboration mascot keychain set",
        query="sanrio japan collaboration mascot keychain set",
        source_price_gbp=24.0,
        shipping_to_uk_gbp=16.0,
        demand_weight=8.1,
        competition_penalty=2.2,
        volatility_penalty=1.3,
    ),
    _MecchaSeed(
        title="Pokemon Card Japanese special set box (sealed)",
        query="pokemon card japanese special set box sealed",
        source_price_gbp=62.0,
        shipping_to_uk_gbp=18.0,
        demand_weight=9.0,
        competition_penalty=3.2,
        volatility_penalty=2.5,
    ),
    _MecchaSeed(
        title="Blue Lock Japan-only acrylic stand collection",
        query="blue lock japan only acrylic stand",
        source_price_gbp=21.0,
        shipping_to_uk_gbp=15.0,
        demand_weight=7.5,
        competition_penalty=1.8,
        volatility_penalty=1.1,
    ),
)


def _meccha_search_url(query: str) -> str:
    return f"https://meccha-japan.com/en/search?controller=search&s={quote_plus(query)}"


def _seed_priority_score(seed: _MecchaSeed) -> float:
    """Rank products by resale potential and listing risk.

    This replaces the old static marketplace mapping with category-aware scoring,
    giving preference to strong UK demand while penalizing volatile categories.
    """

    landed_cost = seed.source_price_gbp + seed.shipping_to_uk_gbp
    landed_cost_penalty = landed_cost / 90
    return (
        seed.demand_weight
        - seed.competition_penalty
        - seed.volatility_penalty
        - landed_cost_penalty
    )


@traceable(name="discover_foreign_marketplaces", run_type="tool")
def discover_foreign_marketplaces() -> list[MarketplaceSite]:
    """Agent 1 tool: return foreign marketplaces frequently used for export arbitrage.

    This is deliberately curated because many marketplaces have anti-bot terms and rate limits.
    In production, replace this with a compliant search/index source and jurisdiction checks.
    """

    return [
        MarketplaceSite(
            name="Meccha Japan",
            country="Japan",
            url="https://meccha-japan.com/",
            reason=(
                "Focused catalog of Japan-exclusive anime, gaming, and collectible products "
                "that resellers can source with clearer product specificity than auction feeds."
            ),
        ),
    ]


@traceable(name="find_candidate_items", run_type="tool")
def find_candidate_items(marketplace: MarketplaceSite) -> list[CandidateItem]:
    """Agent 2 tool: seed examples per marketplace.

    Keep the output structured and conservative; do not claim live availability unless
    a compliant live search integration is attached.
    """

    if marketplace.name != "Meccha Japan":
        return []

    ranked_seeds = sorted(_MECCHA_JAPAN_SEEDS, key=_seed_priority_score, reverse=True)
    return [
        CandidateItem(
            site_name=marketplace.name,
            title=seed.title,
            url=_meccha_search_url(seed.query),
            source_price_gbp=seed.source_price_gbp,
            shipping_to_uk_gbp=seed.shipping_to_uk_gbp,
            condition="New",
        )
        for seed in ranked_seeds
    ]


@traceable(name="_safe_fetch_ebay_price_snapshots", run_type="tool")
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


@traceable(name="assess_profitability_against_ebay", run_type="tool")
def assess_profitability_against_ebay(item: CandidateItem) -> ProfitabilityAssessment:
    """Agent 3 tool: estimate arbitrage profitability from eBay sold-price snapshots."""

    sold_prices = _safe_fetch_ebay_price_snapshots(item.title)
    benchmark = median(sold_prices) if sold_prices else item.source_price_gbp * 1.35

    landed_cost = item.source_price_gbp + item.shipping_to_uk_gbp
    fees = (benchmark * EBAY_FINAL_VALUE_FEE_RATE) + EBAY_PER_ORDER_FEE_GBP
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

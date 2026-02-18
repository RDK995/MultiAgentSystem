from __future__ import annotations

"""Tool functions used by both the CLI dry-run and ADK agents.

Design goals:
- Keep each tool deterministic and easy to reason about.
- Centralize diagnostics/status generation for source fetches.
- Preserve compatibility with existing tests and reports.
"""

from dataclasses import dataclass
import hashlib
import logging
import os
import random
from statistics import median
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from uk_resell_adk.models import CandidateItem, MarketplaceSite, ProfitabilityAssessment
from uk_resell_adk.sources import HLJAdapter, NinNinGameAdapter
from uk_resell_adk.sources.base import SourceAdapter
from uk_resell_adk.sources.common import configure_debug
from uk_resell_adk.tracing import traceable


USER_AGENT = "uk-resell-adk/0.2 (+research assistant)"
LOGGER = logging.getLogger(__name__)

# eBay UK private seller baseline (non-vehicle categories):
# "No transaction or final value fees" for UK-based private sellers.
# Source: https://www.ebay.co.uk/help/fees-credits-invoices/selling-fees/fees-private-sellers?id=4822
EBAY_FINAL_VALUE_FEE_RATE = 0.0
EBAY_PER_ORDER_FEE_GBP = 0.0
DEFAULT_SOURCE_ITEM_LIMIT = 12
DEFAULT_SOURCE_RESEARCH_DEPTH_MULTIPLIER = 3


@dataclass
class SourceRuntimeOptions:
    """Runtime flags that control source-fetch behavior."""

    allow_fallback: bool = False
    strict_live: bool = False
    debug_sources: bool = False
    debug_dir: str = "debug/sources"


SOURCE_RUNTIME = SourceRuntimeOptions()
LAST_SOURCE_DIAGNOSTICS: dict[str, dict] = {}

SOURCE_ADAPTERS: tuple[SourceAdapter, ...] = (
    HLJAdapter(),
    NinNinGameAdapter(),
)


def _get_adapter_for_marketplace(marketplace: MarketplaceSite) -> SourceAdapter | None:
    """Resolve a source adapter by marketplace display name."""
    name = marketplace.name.strip().lower()
    for adapter in SOURCE_ADAPTERS:
        if adapter.descriptor.name.lower() == name:
            return adapter
    return None


def _dedupe_items_by_url(items: list[CandidateItem]) -> list[CandidateItem]:
    """Deduplicate candidate items by normalized URL while preserving order."""
    deduped: list[CandidateItem] = []
    seen_urls: set[str] = set()
    for item in items:
        key = item.url.strip().lower()
        if not key or key in seen_urls:
            continue
        seen_urls.add(key)
        deduped.append(item)
    return deduped


def _source_fetch_limit() -> int:
    raw = os.getenv("SOURCE_RESEARCH_DEPTH_MULTIPLIER", str(DEFAULT_SOURCE_RESEARCH_DEPTH_MULTIPLIER)).strip()
    try:
        multiplier = int(raw)
    except ValueError:
        multiplier = DEFAULT_SOURCE_RESEARCH_DEPTH_MULTIPLIER
    multiplier = max(1, min(multiplier, 10))
    return DEFAULT_SOURCE_ITEM_LIMIT * multiplier


def _build_run_rng(scope: str) -> random.Random:
    seed_override = os.getenv("SOURCE_RANDOM_SEED")
    if seed_override:
        digest = hashlib.sha256(f"{seed_override}:{scope}".encode("utf-8")).hexdigest()[:16]
        return random.Random(int(digest, 16))
    return random.SystemRandom()


def _resolve_source_status(*, live_count: int, fallback_count: int, blocked_count: int, parse_miss_count: int, error_count: int) -> str:
    """Collapse counters into a single report status.

    Priority is intentionally strict so root causes are obvious in reports:
    live > blocked > fetch_error > parse_failed > fallback > no_data.
    """
    if live_count > 0:
        return "live"
    if blocked_count > 0:
        return "blocked"
    if error_count > 0:
        return "fetch_error"
    if parse_miss_count > 0:
        return "parse_failed"
    if fallback_count > 0:
        return "fallback"
    return "no_data"


def _record_source_diagnostics(
    *,
    source_name: str,
    status: str,
    live_count: int,
    fallback_count: int,
    blocked_count: int,
    parse_miss_count: int,
    error_count: int,
) -> None:
    LAST_SOURCE_DIAGNOSTICS[source_name] = {
        "source_name": source_name,
        "status": status,
        "live_count": live_count,
        "fallback_count": fallback_count,
        "blocked_count": blocked_count,
        "parse_miss_count": parse_miss_count,
        "error_count": error_count,
    }


def configure_source_runtime(
    *,
    allow_fallback: bool = False,
    strict_live: bool = False,
    debug_sources: bool = False,
    debug_dir: str = "debug/sources",
) -> None:
    """Apply runtime options for source adapters and shared debug capture."""
    SOURCE_RUNTIME.allow_fallback = allow_fallback
    SOURCE_RUNTIME.strict_live = strict_live
    SOURCE_RUNTIME.debug_sources = debug_sources
    SOURCE_RUNTIME.debug_dir = debug_dir
    configure_debug(debug_sources, debug_dir)


def reset_source_diagnostics() -> None:
    LAST_SOURCE_DIAGNOSTICS.clear()


def get_source_diagnostics() -> list[dict]:
    return [LAST_SOURCE_DIAGNOSTICS[k] for k in sorted(LAST_SOURCE_DIAGNOSTICS.keys())]


@traceable(name="discover_foreign_marketplaces", run_type="tool")
def discover_foreign_marketplaces() -> list[MarketplaceSite]:
    """Return configured source marketplaces exposed to the workflow."""
    return [
        MarketplaceSite(
            name=adapter.descriptor.name,
            country=adapter.descriptor.country,
            url=adapter.descriptor.home_url,
            reason=adapter.descriptor.reason,
        )
        for adapter in SOURCE_ADAPTERS
    ]


@traceable(name="find_candidate_items", run_type="tool")
def find_candidate_items(marketplace: MarketplaceSite) -> list[CandidateItem]:
    """Fetch candidate items from one marketplace and update diagnostics."""
    adapter = _get_adapter_for_marketplace(marketplace)
    if adapter is None:
        return []

    try:
        raw_items = list(
            adapter.fetch_candidates(
                limit=_source_fetch_limit(),
                allow_fallback=SOURCE_RUNTIME.allow_fallback,
            )
        )
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Source adapter fetch failed for %s: %s", marketplace.name, exc)
        _record_source_diagnostics(
            source_name=marketplace.name,
            status="fetch_error",
            live_count=0,
            fallback_count=0,
            blocked_count=0,
            parse_miss_count=0,
            error_count=1,
        )
        return []

    deduped = _dedupe_items_by_url(raw_items)
    _build_run_rng(marketplace.name).shuffle(deduped)
    live_count = sum(1 for x in deduped if x.data_origin == "live")
    fallback_count = sum(1 for x in deduped if x.data_origin == "fallback")

    meta = getattr(adapter, "last_fetch_meta", {}) or {}
    blocked_count = int(meta.get("blocked", 0))
    parse_miss_count = int(meta.get("parse_misses", 0))
    error_count = int(meta.get("fetch_errors", 0))
    status = _resolve_source_status(
        live_count=live_count,
        fallback_count=fallback_count,
        blocked_count=blocked_count,
        parse_miss_count=parse_miss_count,
        error_count=error_count,
    )

    _record_source_diagnostics(
        source_name=marketplace.name,
        status=status,
        live_count=live_count,
        fallback_count=fallback_count,
        blocked_count=blocked_count,
        parse_miss_count=parse_miss_count,
        error_count=error_count,
    )

    if SOURCE_RUNTIME.strict_live and adapter.descriptor.strict_live_required and live_count == 0:
        raise RuntimeError(
            f"Strict live mode: source '{marketplace.name}' returned zero live candidates (status={status})."
        )

    if not deduped:
        LOGGER.warning("No candidates found for source: %s (status=%s)", marketplace.name, status)

    return deduped


@traceable(name="_safe_fetch_ebay_price_snapshots", run_type="tool")
def _safe_fetch_ebay_price_snapshots(query: str) -> list[float]:
    endpoint = "https://www.ebay.co.uk/sch/i.html"
    params = {
        "_nkw": query,
        "LH_Sold": "1",
        "LH_Complete": "1",
        "rt": "nc",
    }
    request = Request(f"{endpoint}?{urlencode(params)}", headers={"User-Agent": USER_AGENT})

    try:
        with urlopen(request, timeout=10) as response:
            content = response.read().decode("utf-8", errors="ignore")
    except Exception:
        return []

    # Simple token-based extraction is intentionally lightweight and resilient
    # to minor eBay HTML changes.
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
    """Estimate resale profitability using eBay sold listing snapshots."""
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

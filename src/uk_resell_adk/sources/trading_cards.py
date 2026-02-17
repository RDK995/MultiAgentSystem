from __future__ import annotations

"""Shared helpers for trading-card source adapters.

This module intentionally keeps the helpers small and explicit so each source
adapter can stay easy to read while sharing core behavior.
"""

from datetime import datetime, timezone

from uk_resell_adk.models import CandidateItem
from uk_resell_adk.sources.common import estimate_shipping_to_uk_gbp


# Core keyword set used by all trading-card sources.
BASE_TRADING_CARD_TERMS: tuple[str, ...] = (
    "card",
    "tcg",
    "booster",
    "starter deck",
    "deck",
    "yugioh",
    "yu-gi-oh",
    "pokemon",
    "one piece card",
    "duel masters",
    "weiss schwarz",
)


def now_utc_iso() -> str:
    """Return an ISO8601 UTC timestamp for source records."""
    return datetime.now(timezone.utc).isoformat()


def new_fetch_meta() -> dict[str, int]:
    """Create the canonical diagnostics structure for a source run."""
    return {
        "blocked": 0,
        "fetch_errors": 0,
        "parse_misses": 0,
        "live_items": 0,
        "fallback_items": 0,
    }


def is_trading_card_item(title: str, extra_terms: tuple[str, ...] = ()) -> bool:
    """Return True when title appears to be a trading-card product."""
    low = title.lower()
    return any(term in low for term in (*BASE_TRADING_CARD_TERMS, *extra_terms))


def append_candidate_from_row(
    *,
    items: list[CandidateItem],
    seen_urls: set[str],
    row: dict[str, str | float],
    site_name: str,
    source_id: str,
    fetched_at_utc: str,
    data_origin: str,
    require_card_title: bool = True,
    card_terms: tuple[str, ...] = (),
) -> bool:
    """Append a candidate item from a parsed row.

    Returns True when a new item was appended. Returns False for duplicates,
    malformed rows, or rows filtered out by the trading-card title check.
    """
    url = str(row.get("url", "")).strip()
    title = str(row.get("title", "")).strip()
    if not url or not title or url in seen_urls:
        return False
    if require_card_title and not is_trading_card_item(title, extra_terms=card_terms):
        return False

    source_price_gbp = float(row["source_price_gbp"])
    seen_urls.add(url)
    items.append(
        CandidateItem(
            site_name=site_name,
            title=title,
            url=url,
            source_price_gbp=source_price_gbp,
            shipping_to_uk_gbp=estimate_shipping_to_uk_gbp(source_price_gbp),
            condition="New",
            source_id=source_id,
            fetched_at_utc=fetched_at_utc,
            data_origin=data_origin,
        )
    )
    return True

from __future__ import annotations

from collections.abc import Sequence
from urllib.parse import quote_plus

from uk_resell_adk.models import CandidateItem
from uk_resell_adk.sources.base import SourceAdapter, SourceDescriptor
from uk_resell_adk.sources.common import (
    SourceBlockedError,
    extract_first_product_from_page,
    extract_products_from_html,
    extract_products_from_json_ld,
    fetch_page,
    fetch_sitemap_product_urls,
)
from uk_resell_adk.sources.trading_cards import (
    append_candidate_from_row,
    is_trading_card_item,
    new_fetch_meta,
    now_utc_iso,
)


class NinNinGameAdapter(SourceAdapter):
    """Source adapter for Nin-Nin-Game trading-card discovery."""

    descriptor = SourceDescriptor(
        key="ninningame",
        name="Nin-Nin-Game",
        country="Japan",
        home_url="https://www.nin-nin-game.com/en/",
        reason="Broad catalog of Japan exclusives with established UK shipping methods.",
    )

    _queries = ("pokemon card", "one piece card game", "yugioh", "digimon card")
    _sitemap_hints = ("/en/", "/product")
    _sitemap_excludes = ("/blog", "/news", "/content/", "/search", "/module/")
    _extra_card_terms = ("digimon",)

    _fallback_catalog: tuple[tuple[str, str, float], ...] = (
        (
            "Pokemon Card Game Booster Box",
            "https://www.nin-nin-game.com/en/search?controller=search&search_query=pokemon+card+booster+box",
            47.0,
        ),
        (
            "One Piece Card Game Booster Box",
            "https://www.nin-nin-game.com/en/search?controller=search&search_query=one+piece+card+game+booster+box",
            55.0,
        ),
        (
            "Yu-Gi-Oh OCG Pack",
            "https://www.nin-nin-game.com/en/search?controller=search&search_query=yugioh+ocg",
            21.0,
        ),
        (
            "Digimon Card Game Starter Deck",
            "https://www.nin-nin-game.com/en/search?controller=search&search_query=digimon+card+starter+deck",
            19.0,
        ),
    )

    def __init__(self) -> None:
        self.last_fetch_meta: dict[str, int] = {}

    @classmethod
    def _is_trading_card_item(cls, title: str) -> bool:
        return is_trading_card_item(title, extra_terms=cls._extra_card_terms)

    def _search_url(self, query: str) -> str:
        return f"https://www.nin-nin-game.com/en/search?controller=search&search_query={quote_plus(query)}"

    def fetch_candidates(
        self,
        limit: int,
        timeout_seconds: float = 10,
        retries: int = 2,
        allow_fallback: bool = False,
    ) -> Sequence[CandidateItem]:
        items: list[CandidateItem] = []
        seen: set[str] = set()
        fetched_at = now_utc_iso()
        meta = new_fetch_meta()

        # Pass 1: card-specific search pages.
        for query in self._queries:
            search_url = self._search_url(query)
            try:
                content = fetch_page(
                    search_url,
                    timeout_seconds=timeout_seconds,
                    retries=retries,
                    source_key=self.descriptor.key,
                    debug_label=f"search_{query}",
                )
            except SourceBlockedError:
                meta["blocked"] += 1
                continue
            except Exception:  # noqa: BLE001
                meta["fetch_errors"] += 1
                continue

            rows = extract_products_from_json_ld(content) or extract_products_from_html(content, search_url)
            if not rows:
                meta["parse_misses"] += 1
            for row in rows:
                added = append_candidate_from_row(
                    items=items,
                    seen_urls=seen,
                    row=row,
                    site_name=self.descriptor.name,
                    source_id=self.descriptor.key,
                    fetched_at_utc=fetched_at,
                    data_origin="live",
                    card_terms=self._extra_card_terms,
                )
                if not added:
                    continue
                meta["live_items"] += 1
                if len(items) >= limit:
                    self.last_fetch_meta = meta
                    return items

        # Pass 2: sitemap exploration for larger product volume.
        if len(items) < limit:
            sitemap_urls = fetch_sitemap_product_urls(
                self.descriptor.home_url,
                url_hints=self._sitemap_hints,
                url_excludes=self._sitemap_excludes,
                limit=max(limit * 12, 80),
                timeout_seconds=timeout_seconds,
                retries=retries,
                source_key=self.descriptor.key,
            )
            for url in sitemap_urls:
                if url in seen:
                    continue
                try:
                    page = fetch_page(
                        url,
                        timeout_seconds=timeout_seconds,
                        retries=retries,
                        source_key=self.descriptor.key,
                        debug_label="sitemap_page",
                    )
                except SourceBlockedError:
                    meta["blocked"] += 1
                    continue
                except Exception:  # noqa: BLE001
                    meta["fetch_errors"] += 1
                    continue

                row = extract_first_product_from_page(url, page)
                if not row:
                    meta["parse_misses"] += 1
                    continue
                added = append_candidate_from_row(
                    items=items,
                    seen_urls=seen,
                    row=row,
                    site_name=self.descriptor.name,
                    source_id=self.descriptor.key,
                    fetched_at_utc=fetched_at,
                    data_origin="live",
                    card_terms=self._extra_card_terms,
                )
                if not added:
                    continue
                meta["live_items"] += 1
                if len(items) >= limit:
                    self.last_fetch_meta = meta
                    return items

        # Pass 3: optional deterministic fallback catalog.
        if allow_fallback and len(items) < limit:
            for title, url, source_price_gbp in self._fallback_catalog:
                added = append_candidate_from_row(
                    items=items,
                    seen_urls=seen,
                    row={"title": title, "url": url, "source_price_gbp": source_price_gbp},
                    site_name=self.descriptor.name,
                    source_id=self.descriptor.key,
                    fetched_at_utc=fetched_at,
                    data_origin="fallback",
                    card_terms=self._extra_card_terms,
                )
                if not added:
                    continue
                meta["fallback_items"] += 1
                if len(items) >= limit:
                    break

        self.last_fetch_meta = meta
        return items

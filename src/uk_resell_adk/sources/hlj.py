from __future__ import annotations

from collections.abc import Sequence
import json
import re
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


class HLJAdapter(SourceAdapter):
    """Source adapter for HobbyLink Japan.

    Strategy:
    1) Query card-focused search terms.
    2) Prefer HLJ live-price endpoint because it is structured and stable.
    3) Fall back to generic page parsing.
    4) Expand using sitemap crawl when needed.
    5) Optionally use static fallback catalog if explicitly enabled.
    """

    descriptor = SourceDescriptor(
        key="hlj",
        name="HobbyLink Japan",
        country="Japan",
        home_url="https://www.hlj.com/",
        reason="Large Japan-collectibles catalog with stable international shipping coverage.",
    )

    _queries = ("pokemon card", "one piece card game", "yugioh ocg", "japanese tcg")
    _sitemap_hints = ("/product/", "/p/", "/-")
    _sitemap_excludes = ("/blog", "/news", "/category", "/search")
    _extra_card_terms = ("union arena",)

    _fallback_catalog: tuple[tuple[str, str, float], ...] = (
        ("Pokemon TCG Booster Box", "https://www.hlj.com/search/?q=pokemon+card+booster+box", 41.0),
        ("One Piece Card Game Booster Box", "https://www.hlj.com/search/?q=one+piece+card+game+booster+box", 56.0),
        ("Yu-Gi-Oh OCG Booster Pack", "https://www.hlj.com/search/?q=yugioh+ocg+booster", 24.0),
        ("Union Arena TCG Starter Deck", "https://www.hlj.com/search/?q=union+arena+starter+deck", 18.0),
    )

    def __init__(self) -> None:
        self.last_fetch_meta: dict[str, int] = {}

    @classmethod
    def _is_trading_card_item(cls, title: str) -> bool:
        return is_trading_card_item(title, extra_terms=cls._extra_card_terms)

    def _search_url(self, query: str) -> str:
        return f"https://www.hlj.com/search/?q={quote_plus(query)}"

    def _extract_search_item_codes(self, content: str) -> list[str]:
        return re.findall(r'id="en_name_([A-Za-z0-9]+)"', content)

    def _extract_search_item_names(self, content: str) -> dict[str, str]:
        names: dict[str, str] = {}
        for code, name in re.findall(
            r'id="en_name_([A-Za-z0-9]+)"[^>]*value="([^"]+)"',
            content,
            flags=re.IGNORECASE,
        ):
            names[code] = name
        return names

    def _extract_search_item_links(self, content: str) -> dict[str, str]:
        links: dict[str, str] = {}
        for code, href in re.findall(
            r'id="en_name_([A-Za-z0-9]+)".*?<a[^>]+href="([^"]+)"',
            content,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            links[code] = href
        return links

    def _fetch_live_prices(
        self,
        item_codes: list[str],
        timeout_seconds: float,
        retries: int,
    ) -> dict[str, dict[str, str | float]]:
        if not item_codes:
            return {}

        payload = fetch_page(
            f"https://www.hlj.com/search/livePrice/?item_codes={','.join(item_codes)}",
            timeout_seconds=timeout_seconds,
            retries=retries,
            source_key=self.descriptor.key,
            debug_label="search_live_price",
        )
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _append_from_live_price_rows(
        self,
        *,
        items: list[CandidateItem],
        seen: set[str],
        item_codes: list[str],
        item_names: dict[str, str],
        item_links: dict[str, str],
        price_map: dict[str, dict[str, str | float]],
        fetched_at: str,
        meta: dict[str, int],
        limit: int,
    ) -> bool:
        """Append products parsed from HLJ live-price endpoint.

        Returns True if the adapter reached `limit`.
        """
        for code in item_codes:
            row = price_map.get(code)
            if not isinstance(row, dict):
                continue
            raw_price = row.get("priceNoFormat")
            if raw_price is None:
                continue
            try:
                source_price_gbp = round(float(str(raw_price).replace(",", "")), 2)
            except ValueError:
                continue

            raw_url = item_links.get(code, "")
            if not raw_url:
                continue
            url = raw_url if raw_url.startswith("http") else f"https://www.hlj.com{raw_url}"
            title = str(item_names.get(code) or row.get("name") or code)
            added = append_candidate_from_row(
                items=items,
                seen_urls=seen,
                row={"title": title, "url": url, "source_price_gbp": source_price_gbp},
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
                return True
        return False

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

        # Pass 1: search pages + live-price API.
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
            item_codes = self._extract_search_item_codes(content)
            item_names = self._extract_search_item_names(content)
            item_links = self._extract_search_item_links(content)
            if item_codes:
                price_map = self._fetch_live_prices(item_codes, timeout_seconds=timeout_seconds, retries=retries)
                if self._append_from_live_price_rows(
                    items=items,
                    seen=seen,
                    item_codes=item_codes,
                    item_names=item_names,
                    item_links=item_links,
                    price_map=price_map,
                    fetched_at=fetched_at,
                    meta=meta,
                    limit=limit,
                ):
                    self.last_fetch_meta = meta
                    return items

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

        # Pass 2: crawl sitemap product URLs for additional inventory.
        if len(items) < limit:
            sitemap_urls = fetch_sitemap_product_urls(
                self.descriptor.home_url,
                url_hints=self._sitemap_hints,
                url_excludes=self._sitemap_excludes,
                limit=max(limit * 3, 30),
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

        # Pass 3: deterministic fallback list for non-live scenarios.
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

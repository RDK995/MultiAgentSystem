from __future__ import annotations

from collections.abc import Sequence
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
    shuffle_for_source,
)
from uk_resell_adk.sources.trading_cards import append_candidate_from_row, is_trading_card_item, new_fetch_meta, now_utc_iso


class SurugaYaAdapter(SourceAdapter):
    """Source adapter for Suruga-ya Japanese collectibles."""

    descriptor = SourceDescriptor(
        key="surugaya",
        name="Suruga-ya",
        country="Japan",
        home_url="https://www.suruga-ya.com/en",
        reason="Deep catalog for Japanese trading cards and accessories, including discounted used stock.",
    )

    _queries = ("pokemon card", "one piece card game", "yugioh", "dragon ball super card")
    _sitemap_hints = ("/en/product/", "/en/detail/")
    _sitemap_excludes = ("/news", "/special", "/guide", "/faq")
    _extra_card_terms = ("dragon ball",)

    _fallback_catalog: tuple[tuple[str, str, float], ...] = (
        ("Pokemon Card Japanese Booster Box", "https://www.suruga-ya.com/en/products?keyword=pokemon+card+booster+box", 49.0),
        ("Yu-Gi-Oh OCG Japanese Box", "https://www.suruga-ya.com/en/products?keyword=yugioh+ocg+box", 34.0),
    )

    def __init__(self) -> None:
        self.last_fetch_meta: dict[str, object] = {}

    @classmethod
    def _is_trading_card_item(cls, title: str) -> bool:
        return is_trading_card_item(title, extra_terms=cls._extra_card_terms)

    def _search_url(self, query: str) -> str:
        return f"https://www.suruga-ya.com/en/products?keyword={quote_plus(query)}"

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
        meta["parse_miss_examples"] = []
        meta["fetch_error_examples"] = []
        meta["blocked_examples"] = []
        queries = shuffle_for_source(self._queries, source_key=self.descriptor.key, purpose="queries")

        for query in queries:
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
                if len(meta["blocked_examples"]) < 5:
                    meta["blocked_examples"].append(search_url)
                continue
            except Exception as exc:  # noqa: BLE001
                meta["fetch_errors"] += 1
                if len(meta["fetch_error_examples"]) < 5:
                    meta["fetch_error_examples"].append(f"{search_url} ({type(exc).__name__}: {exc})")
                continue

            rows = extract_products_from_json_ld(content) or extract_products_from_html(content, search_url)
            if not rows:
                meta["parse_misses"] += 1
                if len(meta["parse_miss_examples"]) < 5:
                    jsonld_count = content.lower().count("application/ld+json")
                    detail_link_count = len(re.findall(r"/en/(?:product|detail)/", content, flags=re.IGNORECASE))
                    meta["parse_miss_examples"].append(
                        f"{search_url} [jsonld={jsonld_count}, detail_links={detail_link_count}]"
                    )
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

        if len(items) < limit:
            sitemap_urls = fetch_sitemap_product_urls(
                self.descriptor.home_url,
                url_hints=self._sitemap_hints,
                url_excludes=self._sitemap_excludes,
                limit=max(limit * 8, 60),
                timeout_seconds=timeout_seconds,
                retries=retries,
                source_key=self.descriptor.key,
            )
            sitemap_urls = shuffle_for_source(sitemap_urls, source_key=self.descriptor.key, purpose="sitemap")
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
                    if len(meta["blocked_examples"]) < 5:
                        meta["blocked_examples"].append(url)
                    continue
                except Exception as exc:  # noqa: BLE001
                    meta["fetch_errors"] += 1
                    if len(meta["fetch_error_examples"]) < 5:
                        meta["fetch_error_examples"].append(f"{url} ({type(exc).__name__}: {exc})")
                    continue

                row = extract_first_product_from_page(url, page)
                if not row:
                    meta["parse_misses"] += 1
                    if len(meta["parse_miss_examples"]) < 5:
                        jsonld_count = page.lower().count("application/ld+json")
                        detail_link_count = len(re.findall(r"/en/(?:product|detail)/", page, flags=re.IGNORECASE))
                        meta["parse_miss_examples"].append(
                            f"{url} [jsonld={jsonld_count}, detail_links={detail_link_count}]"
                        )
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

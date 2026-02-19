from __future__ import annotations

from typing import Any

from uk_resell_adk.models import CandidateItem
from uk_resell_adk.sources.hlj import HLJAdapter
from uk_resell_adk.sources.ninningame import NinNinGameAdapter
from uk_resell_adk.sources.surugaya import SurugaYaAdapter


SAMPLE_JSON_LD = '''
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "Pokemon Card Booster Box",
  "url": "https://example.com/product/sample-figure",
  "offers": {
    "@type": "Offer",
    "price": "59.99",
    "priceCurrency": "USD"
  }
}
</script>
'''


def test_source_descriptors_are_configured() -> None:
    adapters = [HLJAdapter(), NinNinGameAdapter(), SurugaYaAdapter()]
    names = {a.descriptor.name for a in adapters}
    assert names == {"HobbyLink Japan", "Nin-Nin-Game", "Suruga-ya"}


def test_hlj_adapter_parses_candidates_from_json_ld(monkeypatch: Any) -> None:
    adapter = HLJAdapter()
    monkeypatch.setattr("uk_resell_adk.sources.hlj.fetch_page", lambda *args, **kwargs: SAMPLE_JSON_LD)

    items = adapter.fetch_candidates(limit=2)

    assert items
    item = items[0]
    assert isinstance(item, CandidateItem)
    assert item.site_name == "HobbyLink Japan"
    assert item.url == "https://example.com/product/sample-figure"
    assert "card" in item.title.lower()
    assert item.source_id == "hlj"
    assert item.data_origin == "live"


def test_hlj_adapter_parses_candidates_from_live_price_endpoint(monkeypatch: Any) -> None:
    adapter = HLJAdapter()
    search_html = """
    <div class="search search-widget-blocks">
      <input id="en_name_ABC123" class="en_name" hidden="hidden" value="Pokemon Card Booster Box">
      <div class="search-widget-block">
        <p class="product-item-name "><a href="/pokemon-card-booster-abc123">Pokemon Card Booster Box</a></p>
      </div>
    </div>
    """
    live_price_json = '{"ABC123": {"name": "Pokemon Card Booster Box", "priceNoFormat": "4500"}}'

    def fake_fetch(url: str, *_args: Any, **_kwargs: Any) -> str:
        if "livePrice" in url:
            return live_price_json
        return search_html

    monkeypatch.setattr("uk_resell_adk.sources.hlj.fetch_page", fake_fetch)
    monkeypatch.setattr("uk_resell_adk.sources.hlj.fetch_sitemap_product_urls", lambda *args, **kwargs: [])

    items = adapter.fetch_candidates(limit=1)

    assert len(items) == 1
    assert items[0].title == "Pokemon Card Booster Box"
    assert items[0].url == "https://www.hlj.com/pokemon-card-booster-abc123"
    assert items[0].source_id == "hlj"
    assert items[0].data_origin == "live"
    assert items[0].source_price_gbp > 0


def test_ninningame_search_url_uses_search_query_param() -> None:
    adapter = NinNinGameAdapter()
    url = adapter._search_url("dragon ball")
    assert "search_query=dragon+ball" in url
    assert "controller=search" in url


def test_trading_card_filters_accept_card_titles() -> None:
    assert HLJAdapter._is_trading_card_item("Pokemon Card Game Booster Box")
    assert NinNinGameAdapter._is_trading_card_item("One Piece Card Game Starter Deck")
    assert not HLJAdapter._is_trading_card_item("Nendoroid Action Figure")


def test_hlj_adapter_query_order_is_reproducible_with_source_random_seed(monkeypatch: Any) -> None:
    adapter = HLJAdapter()
    seen_urls: list[str] = []

    def fake_fetch(url: str, *_args: Any, **_kwargs: Any) -> str:
        if "search/livePrice" in url:
            return "{}"
        if "/search/?q=" in url:
            seen_urls.append(url)
        return ""

    monkeypatch.setenv("SOURCE_RANDOM_SEED", "seed-123")
    monkeypatch.setattr("uk_resell_adk.sources.hlj.fetch_page", fake_fetch)
    monkeypatch.setattr("uk_resell_adk.sources.hlj.fetch_sitemap_product_urls", lambda *args, **kwargs: [])

    adapter.fetch_candidates(limit=1)
    first_order = tuple(seen_urls)
    seen_urls.clear()
    adapter.fetch_candidates(limit=1)
    second_order = tuple(seen_urls)

    assert len(first_order) == len(adapter._queries)
    assert first_order == second_order


def test_ninningame_adapter_query_order_is_reproducible_with_source_random_seed(monkeypatch: Any) -> None:
    adapter = NinNinGameAdapter()
    seen_urls: list[str] = []

    def fake_fetch(url: str, *_args: Any, **_kwargs: Any) -> str:
        if "search?controller=search&search_query=" in url:
            seen_urls.append(url)
        return ""

    monkeypatch.setenv("SOURCE_RANDOM_SEED", "seed-123")
    monkeypatch.setattr("uk_resell_adk.sources.ninningame.fetch_page", fake_fetch)
    monkeypatch.setattr("uk_resell_adk.sources.ninningame.fetch_sitemap_product_urls", lambda *args, **kwargs: [])

    adapter.fetch_candidates(limit=1)
    first_order = tuple(seen_urls)
    seen_urls.clear()
    adapter.fetch_candidates(limit=1)
    second_order = tuple(seen_urls)

    assert len(first_order) == len(adapter._queries)
    assert first_order == second_order


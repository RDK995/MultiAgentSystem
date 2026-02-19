from __future__ import annotations

from typing import Any

from uk_resell_adk.sources import common
from uk_resell_adk.sources.common import extract_products_from_html, extract_products_from_json_ld


def test_extract_products_from_html_parses_yen_symbol_prices() -> None:
    html = """
    <div class="item-inner">
      <h3 class="s_title_block">
        <a class="product-name" href="https://www.nin-nin-game.com/en/example-item.html">Example Item</a>
      </h3>
      <div class="item-bottom">
        <span class="price">¥4,290</span>
      </div>
    </div>
    """
    rows = extract_products_from_html(html, "https://www.nin-nin-game.com/en/search?search_query=test")
    assert rows
    assert rows[0]["title"] == "Example Item"
    assert rows[0]["url"] == "https://www.nin-nin-game.com/en/example-item.html"
    assert float(rows[0]["source_price_gbp"]) > 0


def test_extract_products_from_html_parses_trailing_yen_currency_symbol() -> None:
    html = """
    <div class="product">
      <a href="/en/detail/1234">Suruga Product Example</a>
      <div class="price">4,980円</div>
    </div>
    """
    rows = extract_products_from_html(html, "https://www.suruga-ya.com")
    assert rows
    assert rows[0]["url"] == "https://www.suruga-ya.com/en/detail/1234"
    assert float(rows[0]["source_price_gbp"]) > 0


def test_extract_products_from_html_parses_price_before_link_in_same_card() -> None:
    html = """
    <div class="product-card">
      <span class="price">JPY 5,200</span>
      <a href="/en/product/abc">Collectible Item Example</a>
    </div>
    """
    rows = extract_products_from_html(html, "https://example.com")
    assert rows
    assert rows[0]["url"] == "https://example.com/en/product/abc"
    assert float(rows[0]["source_price_gbp"]) > 0


def test_extract_products_from_html_uses_nearest_pre_link_price_per_card() -> None:
    html = """
    <div class="card">
      <span class="price">JPY 5,200</span>
      <a href="/en/product/first">First Item Example</a>
    </div>
    <div class="card">
      <span class="price">JPY 9,800</span>
      <a href="/en/product/second">Second Item Example</a>
    </div>
    """
    rows = extract_products_from_html(html, "https://example.com")
    assert len(rows) >= 2
    by_url = {str(row["url"]): float(row["source_price_gbp"]) for row in rows}
    assert by_url["https://example.com/en/product/first"] == round(5200 * 0.0053, 2)
    assert by_url["https://example.com/en/product/second"] == round(9800 * 0.0053, 2)


def test_extract_products_from_json_ld_inferrs_usd_when_currency_missing() -> None:
    html = """
    <script type="application/ld+json">
    {
      "@context":"https://schema.org",
      "@type":"Product",
      "name":"Example USD Product",
      "url":"https://example.com/p/usd",
      "offers":{"@type":"Offer","price":"$100.00"}
    }
    </script>
    """
    rows = extract_products_from_json_ld(html)
    assert rows
    assert rows[0]["url"] == "https://example.com/p/usd"
    # USD 100 converted via configured 0.79 factor.
    assert float(rows[0]["source_price_gbp"]) == 79.0


def test_extract_products_from_json_ld_inferrs_jpy_when_currency_missing() -> None:
    html = """
    <script type="application/ld+json">
    {
      "@context":"https://schema.org",
      "@type":"Product",
      "name":"Example JPY Product",
      "url":"https://example.com/p/jpy",
      "offers":{"@type":"Offer","price":"4,980円"}
    }
    </script>
    """
    rows = extract_products_from_json_ld(html)
    assert rows
    assert rows[0]["url"] == "https://example.com/p/jpy"
    assert float(rows[0]["source_price_gbp"]) > 0


def test_refresh_currency_rates_updates_map_from_api(monkeypatch: Any) -> None:
    class _FakeResponse:
        def __enter__(self) -> "_FakeResponse":
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            return None

        def read(self) -> bytes:
            return b'{"base":"GBP","rates":{"USD":1.25,"EUR":1.15,"JPY":190.0}}'

    monkeypatch.setenv("ENABLE_LIVE_FX_RATES", "true")
    monkeypatch.setenv("FX_API_URL", "https://api.frankfurter.dev/v1/latest")
    monkeypatch.setattr(common, "urlopen", lambda request, timeout=8: _FakeResponse())
    monkeypatch.setattr(common, "_FX_LAST_REFRESH_TS", 0.0)

    refreshed = common.refresh_currency_rates(force=True)
    assert refreshed is True
    # 1 USD = 1/1.25 GBP
    assert round(common.currency_to_gbp(100.0, "USD"), 2) == 80.0


def test_refresh_currency_rates_keeps_existing_rates_on_failure(monkeypatch: Any) -> None:
    monkeypatch.setenv("ENABLE_LIVE_FX_RATES", "true")
    monkeypatch.setenv("FX_API_URL", "https://api.frankfurter.dev/v1/latest")
    monkeypatch.setattr(common, "urlopen", lambda request, timeout=8: (_ for _ in ()).throw(TimeoutError("fx down")))
    monkeypatch.setattr(common, "_FX_LAST_REFRESH_TS", 0.0)

    usd_before = common.currency_to_gbp(1.0, "USD")
    refreshed = common.refresh_currency_rates(force=True)
    usd_after = common.currency_to_gbp(1.0, "USD")

    assert refreshed is False
    assert usd_after == usd_before

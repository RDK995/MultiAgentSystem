from __future__ import annotations

from uk_resell_adk.sources.common import extract_products_from_html


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

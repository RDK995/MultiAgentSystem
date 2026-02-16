from __future__ import annotations

from typing import Any

from uk_resell_adk.models import CandidateItem, MarketplaceSite
from uk_resell_adk import tools


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self._content = content

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    def read(self) -> bytes:
        return self._content.encode("utf-8")


def test_discover_foreign_marketplaces_returns_only_meccha_japan() -> None:
    marketplaces = tools.discover_foreign_marketplaces()

    assert len(marketplaces) == 1
    site = marketplaces[0]
    assert site.name == "Meccha Japan"
    assert site.country == "Japan"
    assert site.url == "https://meccha-japan.com/"


def test_find_candidate_items_for_known_marketplace_returns_ranked_new_items() -> None:
    marketplace = MarketplaceSite(
        name="Meccha Japan",
        country="Japan",
        url="https://meccha-japan.com/",
        reason="catalog",
    )

    items = tools.find_candidate_items(marketplace)

    assert len(items) == len(tools._MECCHA_JAPAN_SEEDS)
    assert all(item.site_name == "Meccha Japan" for item in items)
    assert all(item.condition == "New" for item in items)
    assert all(item.url.startswith("https://meccha-japan.com/en/search") for item in items)

    seed_scores = {seed.title: tools._seed_priority_score(seed) for seed in tools._MECCHA_JAPAN_SEEDS}
    item_scores = [seed_scores[item.title] for item in items]
    assert item_scores == sorted(item_scores, reverse=True)


def test_find_candidate_items_for_unknown_marketplace_returns_empty() -> None:
    unknown = MarketplaceSite(
        name="Other Site",
        country="Japan",
        url="https://example.com",
        reason="n/a",
    )

    assert tools.find_candidate_items(unknown) == []


def test_meccha_search_url_encodes_query_terms() -> None:
    url = tools._meccha_search_url("one piece portrait pirates")

    assert url == (
        "https://meccha-japan.com/en/search?controller=search"
        "&s=one+piece+portrait+pirates"
    )


def test_safe_fetch_ebay_price_snapshots_parses_and_filters(monkeypatch: Any) -> None:
    seen: dict[str, str] = {}

    def fake_urlopen(request: Any, timeout: int) -> _FakeResponse:
        seen["url"] = request.full_url
        seen["ua"] = request.headers.get("User-agent", "")
        assert timeout == 10
        content = "".join(
            [
                "noise £2 ignored",
                "£3.00 keep",
                "£9,999.99 keep",
                "£10001 ignore",
                "£12.50 keep",
                "£abc ignore",
            ]
        )
        return _FakeResponse(content)

    monkeypatch.setattr(tools, "urlopen", fake_urlopen)

    prices = tools._safe_fetch_ebay_price_snapshots("pokemon plush")

    assert prices == [3.0, 9999.99, 12.5]
    assert "_nkw=pokemon+plush" in seen["url"]
    assert "LH_Sold=1" in seen["url"]
    assert "LH_Complete=1" in seen["url"]
    assert "uk-resell-adk" in seen["ua"].lower()


def test_safe_fetch_ebay_price_snapshots_limits_to_twenty(monkeypatch: Any) -> None:
    content = " ".join([f"£{i}.00" for i in range(3, 40)])

    def fake_urlopen(request: Any, timeout: int) -> _FakeResponse:
        return _FakeResponse(content)

    monkeypatch.setattr(tools, "urlopen", fake_urlopen)

    prices = tools._safe_fetch_ebay_price_snapshots("x")

    assert len(prices) == 20
    assert prices[0] == 3.0


def test_safe_fetch_ebay_price_snapshots_returns_empty_on_network_error(monkeypatch: Any) -> None:
    def raising_urlopen(request: Any, timeout: int) -> _FakeResponse:
        raise TimeoutError("boom")

    monkeypatch.setattr(tools, "urlopen", raising_urlopen)

    assert tools._safe_fetch_ebay_price_snapshots("x") == []


def test_assess_profitability_uses_fallback_when_no_prices(monkeypatch: Any) -> None:
    monkeypatch.setattr(tools, "_safe_fetch_ebay_price_snapshots", lambda _query: [])
    item = CandidateItem(
        site_name="Meccha Japan",
        title="Test Item",
        url="https://meccha-japan.com/item",
        source_price_gbp=100.0,
        shipping_to_uk_gbp=20.0,
        condition="New",
    )

    assessment = tools.assess_profitability_against_ebay(item)

    assert assessment.ebay_median_sale_price_gbp == 135.0
    assert assessment.total_landed_cost_gbp == 120.0
    assert assessment.estimated_fees_gbp == 0.0
    assert assessment.estimated_profit_gbp == 15.0
    assert assessment.confidence == "low"


def test_assess_profitability_confidence_medium_and_high(monkeypatch: Any) -> None:
    item = CandidateItem(
        site_name="Meccha Japan",
        title="Confidence Item",
        url="https://meccha-japan.com/item",
        source_price_gbp=10.0,
        shipping_to_uk_gbp=5.0,
        condition="New",
    )

    monkeypatch.setattr(tools, "_safe_fetch_ebay_price_snapshots", lambda _query: [20.0, 30.0])
    medium = tools.assess_profitability_against_ebay(item)
    assert medium.confidence == "medium"
    assert medium.ebay_median_sale_price_gbp == 25.0

    monkeypatch.setattr(
        tools,
        "_safe_fetch_ebay_price_snapshots",
        lambda _query: [10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 24.0],
    )
    high = tools.assess_profitability_against_ebay(item)
    assert high.confidence == "high"
    assert high.ebay_median_sale_price_gbp == 17.0

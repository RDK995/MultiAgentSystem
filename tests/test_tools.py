from __future__ import annotations

from typing import Any

from uk_resell_adk import tools
from uk_resell_adk.models import CandidateItem, MarketplaceSite


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self._content = content

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    def read(self) -> bytes:
        return self._content.encode("utf-8")


def test_discover_foreign_marketplaces_returns_expected_sources() -> None:
    marketplaces = tools.discover_foreign_marketplaces()

    names = {m.name for m in marketplaces}
    assert names == {"HobbyLink Japan", "Nin-Nin-Game"}


def test_find_candidate_items_for_known_marketplace_uses_adapter(monkeypatch: Any) -> None:
    marketplace = MarketplaceSite(
        name="Nin-Nin-Game",
        country="Japan",
        url="https://www.nin-nin-game.com/en/",
        reason="catalog",
    )

    class _FakeAdapter:
        last_fetch_meta = {"blocked": 0, "fetch_errors": 0, "parse_misses": 0, "live_items": 0, "fallback_items": 0}

        def fetch_candidates(
            self,
            limit: int,
            timeout_seconds: float = 10,
            retries: int = 2,
            allow_fallback: bool = False,
        ) -> list[CandidateItem]:
            return [
                CandidateItem("Nin-Nin-Game", "Item A", "https://example.com/a", 30.0, 12.0, "New", data_origin="live"),
                CandidateItem("Nin-Nin-Game", "Item A duplicate", "https://example.com/a", 40.0, 13.0, "New", data_origin="live"),
                CandidateItem("Nin-Nin-Game", "Item B", "https://example.com/b", 22.0, 12.0, "New", data_origin="live"),
            ]

    monkeypatch.setattr(tools, "_get_adapter_for_marketplace", lambda _m: _FakeAdapter())

    items = tools.find_candidate_items(marketplace)

    assert len(items) == 2
    assert {i.url for i in items} == {"https://example.com/a", "https://example.com/b"}
    assert all(i.site_name == "Nin-Nin-Game" for i in items)


def test_find_candidate_items_requests_deeper_source_research(monkeypatch: Any) -> None:
    marketplace = MarketplaceSite(
        name="Nin-Nin-Game",
        country="Japan",
        url="https://www.nin-nin-game.com/en/",
        reason="catalog",
    )
    seen: dict[str, int] = {"limit": 0}

    class _FakeAdapter:
        last_fetch_meta = {"blocked": 0, "fetch_errors": 0, "parse_misses": 0, "live_items": 0, "fallback_items": 0}

        def fetch_candidates(
            self,
            limit: int,
            timeout_seconds: float = 10,
            retries: int = 2,
            allow_fallback: bool = False,
        ) -> list[CandidateItem]:
            seen["limit"] = limit
            return []

    monkeypatch.delenv("SOURCE_RESEARCH_DEPTH_MULTIPLIER", raising=False)
    monkeypatch.setattr(tools, "_get_adapter_for_marketplace", lambda _m: _FakeAdapter())

    tools.find_candidate_items(marketplace)

    assert seen["limit"] == tools.DEFAULT_SOURCE_ITEM_LIMIT * tools.DEFAULT_SOURCE_RESEARCH_DEPTH_MULTIPLIER


def test_find_candidate_items_for_unknown_marketplace_returns_empty() -> None:
    unknown = MarketplaceSite(
        name="Other Site",
        country="Japan",
        url="https://example.com",
        reason="n/a",
    )

    assert tools.find_candidate_items(unknown) == []


def test_source_fetch_limit_uses_env_and_clamps(monkeypatch: Any) -> None:
    monkeypatch.setenv("SOURCE_RESEARCH_DEPTH_MULTIPLIER", "5")
    assert tools._source_fetch_limit() == tools.DEFAULT_SOURCE_ITEM_LIMIT * 5

    monkeypatch.setenv("SOURCE_RESEARCH_DEPTH_MULTIPLIER", "999")
    assert tools._source_fetch_limit() == tools.DEFAULT_SOURCE_ITEM_LIMIT * 10

    monkeypatch.setenv("SOURCE_RESEARCH_DEPTH_MULTIPLIER", "invalid")
    assert tools._source_fetch_limit() == tools.DEFAULT_SOURCE_ITEM_LIMIT * tools.DEFAULT_SOURCE_RESEARCH_DEPTH_MULTIPLIER


def test_find_candidate_items_marks_fetch_error_status(monkeypatch: Any) -> None:
    marketplace = MarketplaceSite(
        name="Nin-Nin-Game",
        country="Japan",
        url="https://www.nin-nin-game.com/en/",
        reason="catalog",
    )

    class _FakeAdapter:
        last_fetch_meta = {"blocked": 0, "fetch_errors": 2, "parse_misses": 0, "live_items": 0, "fallback_items": 0}

        def fetch_candidates(
            self,
            limit: int,
            timeout_seconds: float = 10,
            retries: int = 2,
            allow_fallback: bool = False,
        ) -> list[CandidateItem]:
            return []

    monkeypatch.setattr(tools, "_get_adapter_for_marketplace", lambda _m: _FakeAdapter())
    tools.reset_source_diagnostics()

    items = tools.find_candidate_items(marketplace)

    assert items == []
    assert tools.LAST_SOURCE_DIAGNOSTICS[marketplace.name]["status"] == "fetch_error"


def test_find_candidate_items_strict_live_skips_non_required_source(monkeypatch: Any) -> None:
    marketplace = MarketplaceSite(
        name="Nin-Nin-Game",
        country="Japan",
        url="https://www.nin-nin-game.com/en/",
        reason="catalog",
    )

    class _Descriptor:
        strict_live_required = False

    class _FakeAdapter:
        descriptor = _Descriptor()
        last_fetch_meta = {"blocked": 0, "fetch_errors": 1, "parse_misses": 0, "live_items": 0, "fallback_items": 0}

        def fetch_candidates(
            self,
            limit: int,
            timeout_seconds: float = 10,
            retries: int = 2,
            allow_fallback: bool = False,
        ) -> list[CandidateItem]:
            return []

    monkeypatch.setattr(tools, "_get_adapter_for_marketplace", lambda _m: _FakeAdapter())
    tools.SOURCE_RUNTIME.strict_live = True
    tools.reset_source_diagnostics()

    items = tools.find_candidate_items(marketplace)

    assert items == []
    assert tools.LAST_SOURCE_DIAGNOSTICS[marketplace.name]["status"] == "fetch_error"
    tools.SOURCE_RUNTIME.strict_live = False


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
        site_name="Nin-Nin-Game",
        title="Test Item",
        url="https://example.com/item",
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
        site_name="Nin-Nin-Game",
        title="Confidence Item",
        url="https://example.com/item",
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

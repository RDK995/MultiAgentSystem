from __future__ import annotations

from threading import Event
from typing import Any

from uk_resell_adk.application.workflow.source_stage import fetch_market_candidates, run_source_stage, source_worker_count
from uk_resell_adk.models import CandidateItem, MarketplaceSite


def test_run_source_stage_respects_site_limit_and_aggregates_candidates() -> None:
    marketplaces = [
        MarketplaceSite("A", "JP", "https://a.example", "one"),
        MarketplaceSite("B", "JP", "https://b.example", "two"),
    ]

    def discover() -> list[MarketplaceSite]:
        return marketplaces

    def find_candidates(market: MarketplaceSite) -> list[CandidateItem]:
        return [CandidateItem(market.name, f"{market.name}-item", f"https://{market.name}.example/item", 10.0, 2.0, "New")]

    result = run_source_stage(
        max_foreign_sites=1,
        discover_marketplaces=discover,
        find_candidates=find_candidates,
        reset_diagnostics=lambda: None,
        read_diagnostics=lambda: [{"mode": "test"}],
        stop_requested=lambda: False,
        events_enabled=lambda: False,
    )

    assert [market.name for market in result.marketplaces] == ["A"]
    assert [item.title for item in result.candidates] == ["A-item"]
    assert result.source_diagnostics == [{"mode": "test"}]


def test_run_source_stage_raises_when_stop_requested_mid_loop() -> None:
    marketplaces = [MarketplaceSite("A", "JP", "https://a.example", "one")]
    state = {"calls": 0}

    def stop_requested() -> bool:
        state["calls"] += 1
        return state["calls"] >= 2

    raised = False
    try:
        run_source_stage(
            max_foreign_sites=1,
            discover_marketplaces=lambda: marketplaces,
            find_candidates=lambda _market: [],
            reset_diagnostics=lambda: None,
            read_diagnostics=lambda: [],
            stop_requested=stop_requested,
            events_enabled=lambda: False,
        )
    except RuntimeError as exc:
        raised = True
        assert "Run stopped by user." in str(exc)

    assert raised is True


def test_source_worker_count_respects_env_bounds(monkeypatch) -> None:
    monkeypatch.setenv("SOURCE_CONCURRENCY", "8")
    assert source_worker_count(marketplace_count=3) == 3

    monkeypatch.setenv("SOURCE_CONCURRENCY", "invalid")
    assert source_worker_count(marketplace_count=3, default_concurrency=2) == 2

    monkeypatch.setenv("SOURCE_CONCURRENCY", "-1")
    assert source_worker_count(marketplace_count=3) == 1


def test_fetch_market_candidates_records_latency_and_payload() -> None:
    market = MarketplaceSite("A", "JP", "https://a.example", "one")

    result = fetch_market_candidates(
        market,
        find_candidates=lambda _market: [CandidateItem("A", "item", "https://a.example/item", 10.0, 2.0, "New")],
    )

    assert result.marketplace.name == "A"
    assert len(result.candidates) == 1
    assert result.latency_ms >= 0


def test_run_source_stage_raises_immediately_if_stop_requested_before_work() -> None:
    raised = False
    try:
        run_source_stage(
            max_foreign_sites=1,
            discover_marketplaces=lambda: [MarketplaceSite("A", "JP", "https://a.example", "one")],
            find_candidates=lambda _market: [],
            reset_diagnostics=lambda: None,
            read_diagnostics=lambda: [],
            stop_requested=lambda: True,
            events_enabled=lambda: False,
        )
    except RuntimeError as exc:
        raised = True
        assert "Run stopped by user." in str(exc)
    assert raised is True


def test_run_source_stage_parallel_mode_emits_live_metrics(monkeypatch) -> None:
    marketplaces = [
        MarketplaceSite("A", "JP", "https://a.example", "one"),
        MarketplaceSite("B", "JP", "https://b.example", "two"),
    ]
    captured_events: list[dict[str, Any]] = []
    captured_updates: list[dict[str, Any]] = []

    monkeypatch.setenv("SOURCE_CONCURRENCY", "2")

    def _emit_event(**kwargs: Any) -> dict[str, Any]:
        captured_events.append(kwargs)
        return {"ok": True}

    def _update_agent(**kwargs: Any) -> None:
        captured_updates.append(kwargs)

    def _find_candidates(market: MarketplaceSite) -> list[CandidateItem]:
        return [CandidateItem(market.name, f"{market.name}-item", f"https://{market.name}.example/item", 10.0, 2.0, "New")]

    result = run_source_stage(
        max_foreign_sites=2,
        discover_marketplaces=lambda: marketplaces,
        find_candidates=_find_candidates,
        reset_diagnostics=lambda: None,
        read_diagnostics=lambda: [{"mode": "parallel"}],
        stop_requested=lambda: False,
        events_enabled=lambda: True,
        emit_event=_emit_event,
        update_agent=_update_agent,
    )

    assert len(result.candidates) == 2
    assert result.source_diagnostics == [{"mode": "parallel"}]
    assert any(event["title"] == "Tool call: find_candidate_items" for event in captured_events)
    assert any(event["title"] == "Candidate pool expanded" for event in captured_events)
    sourcing_complete_events = [event for event in captured_events if "sourcing complete" in event["title"]]
    assert sourcing_complete_events
    assert all("sourceLatencyMs" in event.get("metadata", {}) for event in sourcing_complete_events)
    assert any(update["agent_id"] == "sourcing" and update["status"] == "completed" for update in captured_updates)


def test_run_source_stage_parallel_mode_stops_before_queueing_all_markets(monkeypatch) -> None:
    marketplaces = [
        MarketplaceSite("A", "JP", "https://a.example", "one"),
        MarketplaceSite("B", "JP", "https://b.example", "two"),
        MarketplaceSite("C", "JP", "https://c.example", "three"),
        MarketplaceSite("D", "JP", "https://d.example", "four"),
    ]
    start_stop = Event()
    calls: list[str] = []

    monkeypatch.setenv("SOURCE_CONCURRENCY", "2")

    def _find_candidates(market: MarketplaceSite) -> list[CandidateItem]:
        calls.append(market.name)
        # Trigger stop as soon as work starts so the stage should avoid
        # queueing additional marketplaces beyond the initial in-flight set.
        start_stop.set()
        return [CandidateItem(market.name, f"{market.name}-item", f"https://{market.name}.example/item", 10.0, 2.0, "New")]

    raised = False
    try:
        run_source_stage(
            max_foreign_sites=4,
            discover_marketplaces=lambda: marketplaces,
            find_candidates=_find_candidates,
            reset_diagnostics=lambda: None,
            read_diagnostics=lambda: [],
            stop_requested=start_stop.is_set,
            events_enabled=lambda: False,
        )
    except RuntimeError as exc:
        raised = True
        assert "Run stopped by user." in str(exc)

    assert raised is True
    assert len(calls) < len(marketplaces)

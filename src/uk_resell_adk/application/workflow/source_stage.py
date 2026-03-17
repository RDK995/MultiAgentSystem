from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import os
from time import perf_counter
from typing import Any, Callable

from uk_resell_adk.live_events import emit_visual_event, stop_visual_run_requested, update_agent_status, visualizer_events_enabled
from uk_resell_adk.models import CandidateItem, MarketplaceSite
from uk_resell_adk.tools import (
    discover_foreign_marketplaces,
    find_candidate_items,
    get_source_diagnostics,
    reset_source_diagnostics,
)


@dataclass(slots=True)
class SourceStageResult:
    marketplaces: list[MarketplaceSite]
    candidates: list[CandidateItem]
    source_diagnostics: list[dict[str, Any]]


@dataclass(slots=True)
class SourceFetchResult:
    marketplace: MarketplaceSite
    candidates: list[CandidateItem]
    latency_ms: int


def source_worker_count(*, marketplace_count: int, default_concurrency: int = 4) -> int:
    """Resolve bounded source-stage concurrency from env/runtime values."""
    raw = os.getenv("SOURCE_CONCURRENCY", str(default_concurrency)).strip()
    try:
        configured = int(raw)
    except ValueError:
        configured = default_concurrency
    return max(1, min(configured, max(1, marketplace_count)))


def fetch_market_candidates(
    market: MarketplaceSite,
    *,
    find_candidates: Callable[[MarketplaceSite], list[CandidateItem]],
) -> SourceFetchResult:
    """Fetch one marketplace and return item payload + latency telemetry."""
    started_at = perf_counter()
    candidates = find_candidates(market)
    latency_ms = int((perf_counter() - started_at) * 1000)
    return SourceFetchResult(
        marketplace=market,
        candidates=candidates,
        latency_ms=latency_ms,
    )


def run_source_stage(
    *,
    max_foreign_sites: int,
    discover_marketplaces: Callable[[], list[MarketplaceSite]] = discover_foreign_marketplaces,
    find_candidates: Callable[[MarketplaceSite], list[CandidateItem]] = find_candidate_items,
    reset_diagnostics: Callable[[], None] = reset_source_diagnostics,
    read_diagnostics: Callable[[], list[dict[str, Any]]] = get_source_diagnostics,
    stop_requested: Callable[[], bool] = stop_visual_run_requested,
    events_enabled: Callable[[], bool] = visualizer_events_enabled,
    emit_event: Callable[..., dict[str, Any] | None] = emit_visual_event,
    update_agent: Callable[..., None] = update_agent_status,
    source_concurrency: int | None = None,
) -> SourceStageResult:
    if stop_requested():
        raise RuntimeError("Run stopped by user.")

    reset_diagnostics()
    if events_enabled():
        update_agent(
            agent_id="orchestrator",
            name="Agent Orchestrator",
            role="Workflow manager",
            status="running",
            current_step="Discovering foreign marketplaces",
            progress=8,
            tools=["traceable"],
            current_tool="workflow orchestration",
            current_target="market discovery and sourcing",
            completed_count=0,
            total_count=3,
            last_result="Sourcing phase starting",
        )
        update_agent(
            agent_id="sourcing",
            name="Item Sourcing Agent",
            role="Discovery specialist",
            status="running",
            current_step="Discovering sources",
            progress=12,
            tools=["discover_foreign_marketplaces", "find_candidate_items"],
            current_tool="discover_foreign_marketplaces",
            current_target="configured marketplaces",
        )
        emit_event(
            agent_id="sourcing",
            event_type="agent.started",
            title="Sourcing agent activated",
            summary="Scanning configured marketplaces for trading card candidates.",
            status="running",
        )

    marketplaces = discover_marketplaces()[:max_foreign_sites]
    if events_enabled():
        emit_event(
            agent_id="sourcing",
            event_type="agent.tool_completed",
            title="Marketplaces discovered",
            summary=f"{len(marketplaces)} source marketplaces are in scope for this run.",
            status="running",
            metadata={"marketplaces": len(marketplaces)},
        )

    candidates: list[CandidateItem] = []
    markets_processed = 0
    cumulative_scanned = 0
    cumulative_emitted = 0
    worker_count = source_worker_count(
        marketplace_count=len(marketplaces),
        default_concurrency=source_concurrency if source_concurrency and source_concurrency > 0 else 4,
    )

    if events_enabled():
        update_agent(
            agent_id="sourcing",
            name="Item Sourcing Agent",
            role="Discovery specialist",
            status="running",
            current_step="Sourcing marketplaces in parallel",
            progress=18,
            tools=["discover_foreign_marketplaces", "find_candidate_items"],
            current_tool="find_candidate_items",
            current_target=f"{len(marketplaces)} marketplaces",
            completed_count=0,
            total_count=len(marketplaces),
            last_result="Waiting for source responses",
        )

    def _record_market_result(result: SourceFetchResult) -> None:
        nonlocal markets_processed, cumulative_scanned, cumulative_emitted
        markets_processed += 1
        scanned_count = len(result.candidates)
        emitted_count = len(result.candidates)
        cumulative_scanned += scanned_count
        cumulative_emitted += emitted_count
        candidates.extend(result.candidates)

        if not events_enabled():
            return

        progress = min(92, 18 + int((markets_processed / max(1, len(marketplaces))) * 74))
        update_agent(
            agent_id="sourcing",
            name="Item Sourcing Agent",
            role="Discovery specialist",
            status="running",
            current_step=f"Sourcing: {result.marketplace.name}",
            progress=progress,
            tools=["discover_foreign_marketplaces", "find_candidate_items"],
            current_tool="find_candidate_items",
            current_target=result.marketplace.name,
            completed_count=markets_processed,
            total_count=len(marketplaces),
            last_result=f"{cumulative_emitted} candidates collected",
        )
        emit_event(
            agent_id="sourcing",
            event_type="agent.tool_completed",
            title=f"{result.marketplace.name} sourcing complete",
            summary=f"{emitted_count} candidates from {result.marketplace.name} in {result.latency_ms}ms.",
            status="running",
            metadata={
                "marketplace": result.marketplace.name,
                "sourceLatencyMs": result.latency_ms,
                "itemsScanned": scanned_count,
                "itemsEmitted": emitted_count,
                "cumulativeScanned": cumulative_scanned,
                "cumulativeEmitted": cumulative_emitted,
                "marketsProcessed": markets_processed,
                "marketsTotal": len(marketplaces),
            },
        )

    if worker_count == 1:
        for market in marketplaces:
            if stop_requested():
                raise RuntimeError("Run stopped by user.")
            if events_enabled():
                emit_event(
                    agent_id="sourcing",
                    event_type="agent.tool_called",
                    title="Tool call: find_candidate_items",
                    summary=f"Fetching candidate items from {market.name}.",
                    status="running",
                    metadata={"marketplace": market.name},
                )
            _record_market_result(fetch_market_candidates(market, find_candidates=find_candidates))
    else:
        with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="source-fetch") as executor:
            future_to_market = {}
            for market in marketplaces:
                if events_enabled():
                    emit_event(
                        agent_id="sourcing",
                        event_type="agent.tool_called",
                        title="Tool call: find_candidate_items",
                        summary=f"Fetching candidate items from {market.name}.",
                        status="running",
                        metadata={"marketplace": market.name},
                    )
                future = executor.submit(fetch_market_candidates, market, find_candidates=find_candidates)
                future_to_market[future] = market

            for completed in as_completed(future_to_market):
                if stop_requested():
                    raise RuntimeError("Run stopped by user.")
                _record_market_result(completed.result())

    if events_enabled():
        update_agent(
            agent_id="sourcing",
            name="Item Sourcing Agent",
            role="Discovery specialist",
            status="completed",
            current_step="Candidate pool finalized",
            progress=100,
            tools=["discover_foreign_marketplaces", "find_candidate_items"],
            current_tool="find_candidate_items",
            current_target="all marketplaces",
            completed_count=markets_processed,
            total_count=len(marketplaces),
            last_result=f"{len(candidates)} candidates collected",
        )
        emit_event(
            agent_id="sourcing",
            event_type="agent.tool_completed",
            title="Candidate pool expanded",
            summary=f"{len(candidates)} candidate items collected across all sources.",
            status="completed",
            metadata={
                "candidate_count": len(candidates),
                "cumulativeScanned": cumulative_scanned,
                "cumulativeEmitted": cumulative_emitted,
                "marketsProcessed": markets_processed,
                "marketsTotal": len(marketplaces),
            },
        )
        update_agent(
            agent_id="orchestrator",
            name="Agent Orchestrator",
            role="Workflow manager",
            status="running",
            current_step="Transitioning to profitability analysis",
            progress=38,
            tools=["traceable"],
            current_tool="workflow orchestration",
            current_target="profitability analysis",
            completed_count=1,
            total_count=3,
            last_result=f"{len(candidates)} candidates ready",
        )

    return SourceStageResult(
        marketplaces=marketplaces,
        candidates=candidates,
        source_diagnostics=read_diagnostics(),
    )

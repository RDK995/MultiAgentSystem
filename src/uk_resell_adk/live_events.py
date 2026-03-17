from __future__ import annotations

"""Live visualizer run/event API used across the backend runtime."""

from typing import Any

from uk_resell_adk.infrastructure.event_store import (
    LiveEventStore,
    enable_visualizer_events,
    get_live_event_store,
    visualizer_events_enabled,
)


AgentStatus = str
EventType = str


def stop_visual_run_requested() -> bool:
    return get_live_event_store().stop_requested()


def request_visual_run_stop() -> None:
    get_live_event_store().request_stop()


def start_visual_run(*, title: str, objective: str) -> dict[str, Any]:
    store = get_live_event_store()
    run = store.reset_run(title=title, objective=objective)
    store.emit(
        agent_id="orchestrator",
        event_type="run.started",
        title="Run initialized",
        summary="Workflow bootstrapped and awaiting agent activity.",
        status="running",
        metadata={"title": title},
    )
    return run.to_dict()


def complete_visual_run(*, summary: str, metadata: dict[str, Any] | None = None) -> None:
    store = get_live_event_store()
    store.update_run_status("completed")
    completion_metadata: dict[str, Any] = {
        "agentName": "Agent Orchestrator",
        "agentRole": "Workflow manager",
        "currentStep": "Workflow complete",
        "progress": 100,
        "currentTool": "workflow orchestration",
        "currentTarget": "completed run",
        "completedCount": 3,
        "totalCount": 3,
        "lastResult": summary,
    }
    if metadata:
        completion_metadata.update(metadata)
    store.emit(
        agent_id="orchestrator",
        event_type="run.completed",
        title="Run complete",
        summary=summary,
        status="completed",
        metadata=completion_metadata,
    )
    store.set_running(False)


def fail_visual_run(*, summary: str, metadata: dict[str, Any] | None = None) -> None:
    store = get_live_event_store()
    store.update_run_status("failed")
    store.emit(
        agent_id="orchestrator",
        event_type="agent.error",
        title="Run failed",
        summary=summary,
        status="failed",
        metadata=metadata,
    )
    store.set_running(False)


def register_agent(
    *,
    agent_id: str,
    name: str,
    role: str,
    status: AgentStatus = "queued",
    current_step: str = "Waiting to start",
    progress: int = 0,
    tools: list[str] | None = None,
    current_tool: str | None = None,
    current_target: str | None = None,
    completed_count: int | None = None,
    total_count: int | None = None,
    last_result: str | None = None,
) -> None:
    get_live_event_store().upsert_agent(
        agent_id=agent_id,
        name=name,
        role=role,
        status=status,
        current_step=current_step,
        progress=progress,
        tools=tools,
        current_tool=current_tool,
        current_target=current_target,
        completed_count=completed_count,
        total_count=total_count,
        last_result=last_result,
    )


def update_agent_status(
    *,
    agent_id: str,
    name: str,
    role: str,
    status: AgentStatus,
    current_step: str,
    progress: int,
    tools: list[str] | None = None,
    current_tool: str | None = None,
    current_target: str | None = None,
    completed_count: int | None = None,
    total_count: int | None = None,
    last_result: str | None = None,
) -> None:
    get_live_event_store().upsert_agent(
        agent_id=agent_id,
        name=name,
        role=role,
        status=status,
        current_step=current_step,
        progress=progress,
        tools=tools,
        current_tool=current_tool,
        current_target=current_target,
        completed_count=completed_count,
        total_count=total_count,
        last_result=last_result,
    )


def emit_visual_event(
    *,
    agent_id: str,
    event_type: EventType,
    title: str,
    summary: str,
    status: AgentStatus,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not visualizer_events_enabled():
        return None
    return get_live_event_store().emit(
        agent_id=agent_id,
        event_type=event_type,
        title=title,
        summary=summary,
        status=status,
        metadata=metadata,
    ).to_dict()

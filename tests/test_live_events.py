from __future__ import annotations

from uk_resell_adk.live_events import (
    complete_visual_run,
    emit_visual_event,
    enable_visualizer_events,
    get_live_event_store,
    register_agent,
    start_visual_run,
    update_agent_status,
)


def test_visual_run_snapshot_contains_agent_updates() -> None:
    enable_visualizer_events(True)
    start_visual_run(title="Test Run", objective="Verify live event snapshot behavior.")
    register_agent(
        agent_id="alpha",
        name="Alpha Agent",
        role="Researcher",
        status="queued",
        current_step="Waiting",
        progress=0,
        tools=["search"],
    )
    update_agent_status(
        agent_id="alpha",
        name="Alpha Agent",
        role="Researcher",
        status="running",
        current_step="Searching",
        progress=45,
        tools=["search"],
    )

    event = emit_visual_event(
        agent_id="alpha",
        event_type="agent.tool_called",
        title="Search started",
        summary="The agent kicked off a search request.",
        status="running",
    )
    assert event is not None
    assert event["metadata"]["currentStep"] == "Searching"
    assert event["metadata"]["progress"] == 45

    snapshot = get_live_event_store().snapshot()
    assert snapshot["run"]["title"] == "Test Run"
    assert snapshot["agents"][0]["currentStep"] == "Searching"
    assert snapshot["events"][-1]["title"] == "Search started"


def test_complete_visual_run_updates_run_status() -> None:
    enable_visualizer_events(True)
    start_visual_run(title="Completion Run", objective="Verify completion behavior.")

    complete_visual_run(summary="Done", metadata={"count": 2})

    snapshot = get_live_event_store().snapshot()
    assert snapshot["run"]["status"] == "completed"
    assert snapshot["events"][-1]["type"] == "run.completed"
    assert snapshot["events"][-1]["metadata"]["count"] == 2


def test_wait_for_events_resyncs_after_new_run_sequence_reset() -> None:
    enable_visualizer_events(True)

    start_visual_run(title="Run A", objective="First run.")
    emit_visual_event(
        agent_id="alpha",
        event_type="agent.started",
        title="Alpha started",
        summary="Alpha work started.",
        status="running",
    )
    complete_visual_run(summary="Run A complete")

    snapshot_a = get_live_event_store().snapshot()
    last_sequence_from_run_a = int(snapshot_a["events"][-1]["sequence"])

    start_visual_run(title="Run B", objective="Second run.")
    emit_visual_event(
        agent_id="beta",
        event_type="agent.started",
        title="Beta started",
        summary="Beta work started.",
        status="running",
    )

    # Simulate a long-lived SSE client that still tracks the old run sequence.
    fresh = get_live_event_store().wait_for_events(last_sequence_from_run_a, timeout=0.01)

    assert fresh
    assert fresh[0]["runId"] == get_live_event_store().snapshot()["run"]["id"]
    enable_visualizer_events(False)

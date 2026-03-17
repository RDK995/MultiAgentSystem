from __future__ import annotations

from uk_resell_adk.infrastructure.event_store import LiveEventStore


def test_wait_for_events_resyncs_after_run_sequence_reset() -> None:
    store = LiveEventStore()

    first_run = store.reset_run(title="Run A", objective="First run")
    store.emit(
        agent_id="orchestrator",
        event_type="run.started",
        title="Run A start",
        summary="Start",
        status="running",
    )
    done_a = store.emit(
        agent_id="orchestrator",
        event_type="run.completed",
        title="Run A done",
        summary="Done",
        status="completed",
    )

    assert done_a.sequence >= 2

    second_run = store.reset_run(title="Run B", objective="Second run")
    store.emit(
        agent_id="orchestrator",
        event_type="run.started",
        title="Run B start",
        summary="Start",
        status="running",
    )

    fresh = store.wait_for_events(done_a.sequence, timeout=0.01)

    assert fresh
    assert fresh[0]["runId"] == second_run.id
    assert fresh[0]["sequence"] == 1
    assert first_run.id != second_run.id

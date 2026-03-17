from __future__ import annotations

from pathlib import Path

from uk_resell_adk.application.run_service import run_visualized_workflow
from uk_resell_adk.live_events import get_live_event_store


def _fake_workflow_payload() -> dict:
    return {
        "marketplaces": [{"name": "A"}],
        "candidate_items": [{"title": "Item"}],
        "assessments": [{"item_title": "Item"}],
    }


def test_two_back_to_back_runs_resync_from_single_stream_cursor() -> None:
    store = get_live_event_store()
    store.set_running(False)
    store.clear_stop_request()

    run_visualized_workflow(
        run_workflow=_fake_workflow_payload,
        write_report=lambda _result, _path: Path("reports/run_a.html"),
    )
    snapshot_a = store.snapshot()
    cursor_from_run_a = int(snapshot_a["events"][-1]["sequence"]) + 100
    run_a_id = snapshot_a["run"]["id"]

    run_visualized_workflow(
        run_workflow=_fake_workflow_payload,
        write_report=lambda _result, _path: Path("reports/run_b.html"),
    )
    snapshot_b = store.snapshot()
    run_b_id = snapshot_b["run"]["id"]

    assert run_b_id != run_a_id

    # Simulate one long-lived stream consumer still carrying a much higher cursor
    # from a prior run sequence, forcing a resync from sequence reset.
    fresh_events = store.wait_for_events(cursor_from_run_a, timeout=0.01)

    assert fresh_events
    assert fresh_events[0]["runId"] == run_b_id
    assert fresh_events[0]["sequence"] == 1

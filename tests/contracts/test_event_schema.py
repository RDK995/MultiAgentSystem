from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from uk_resell_adk.contracts.events import validate_event_envelope, validate_stream_snapshot
from uk_resell_adk.live_events import (
    emit_visual_event,
    enable_visualizer_events,
    get_live_event_store,
    register_agent,
    start_visual_run,
)


def test_application_event_contract_accepts_live_event_payload() -> None:
    enable_visualizer_events(True)
    start_visual_run(title="Contract Run", objective="Validate event payload contract.")
    register_agent(
        agent_id="alpha",
        name="Alpha Agent",
        role="Contract tester",
        status="running",
        current_step="Emitting contract event",
        progress=55,
        tools=["contract_probe"],
    )
    payload = emit_visual_event(
        agent_id="alpha",
        event_type="agent.message",
        title="Contract payload",
        summary="Schema contract validation payload.",
        status="running",
        metadata={
            "nested": {"flag": True, "scores": [1, 2, 3]},
            "label": "ok",
        },
    )

    assert payload is not None
    envelope = validate_event_envelope(payload)
    assert envelope.agentId == "alpha"
    assert envelope.type == "agent.message"
    assert envelope.metadata is not None
    assert envelope.metadata["label"] == "ok"


def test_api_stream_snapshot_contract_accepts_current_snapshot() -> None:
    enable_visualizer_events(True)
    start_visual_run(title="Snapshot Contract", objective="Validate snapshot contract.")
    register_agent(
        agent_id="beta",
        name="Beta Agent",
        role="Snapshot tester",
        status="queued",
        current_step="Waiting",
        progress=0,
        tools=["snapshot_probe"],
    )
    payload = emit_visual_event(
        agent_id="beta",
        event_type="agent.started",
        title="Snapshot event",
        summary="Populate stream snapshot events.",
        status="running",
    )
    assert payload is not None

    snapshot = get_live_event_store().snapshot()
    typed_snapshot = validate_stream_snapshot(snapshot)
    assert typed_snapshot.run is not None
    assert any(agent.id == "beta" for agent in typed_snapshot.agents)
    assert any(event.agentId == "beta" for event in typed_snapshot.events)


def test_application_event_contract_rejects_missing_required_fields() -> None:
    bad_payload: dict[str, Any] = {
        "id": "event_123",
        # sequence intentionally omitted
        "runId": "run_123",
        "agentId": "alpha",
        "type": "agent.message",
        "title": "Missing sequence",
        "summary": "Should fail schema validation.",
        "createdAt": "2026-03-17T10:00:00Z",
        "status": "running",
    }
    with pytest.raises(ValidationError):
        validate_event_envelope(bad_payload)

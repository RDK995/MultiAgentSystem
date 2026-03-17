from __future__ import annotations

import pytest

from uk_resell_adk.domain.entities import Agent, Event, Run


def test_entities_are_slot_based_without_dynamic_dict() -> None:
    run = Run(
        id="run_1",
        started_at="2026-03-17T00:00:00Z",
        status="running",
        title="Run",
        objective="Objective",
    )

    assert not hasattr(run, "__dict__")

    with pytest.raises(AttributeError):
        run.random_field = "nope"  # type: ignore[attr-defined]


def test_agent_defaults_and_event_metadata() -> None:
    agent = Agent(
        id="orchestrator",
        name="Agent Orchestrator",
        role="Workflow manager",
        status="queued",
        current_step="Waiting",
        progress=0,
    )
    event = Event(
        id="event_1",
        sequence=1,
        run_id="run_1",
        agent_id="orchestrator",
        type="agent.started",
        title="Started",
        summary="Summary",
        created_at="2026-03-17T00:00:00Z",
        status="running",
        metadata={"k": "v"},
    )

    assert agent.tools == []
    assert agent.current_tool == ""
    assert event.metadata == {"k": "v"}

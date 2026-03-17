from __future__ import annotations

"""Canonical event/snapshot contracts shared by API and application layers."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

AGENT_STATUSES = ("queued", "running", "waiting", "completed", "failed")
EVENT_TYPES = (
    "run.started",
    "run.completed",
    "agent.started",
    "agent.progress",
    "agent.message",
    "agent.tool_called",
    "agent.tool_completed",
    "agent.file_changed",
    "agent.blocked",
    "agent.error",
)

AgentStatus = Literal["queued", "running", "waiting", "completed", "failed"]
EventType = Literal[
    "run.started",
    "run.completed",
    "agent.started",
    "agent.progress",
    "agent.message",
    "agent.tool_called",
    "agent.tool_completed",
    "agent.file_changed",
    "agent.blocked",
    "agent.error",
]

EventMetadata = dict[str, Any]


class RunSnapshotPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    startedAt: str
    status: AgentStatus
    title: str
    objective: str


class AgentSnapshotPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    role: str
    status: AgentStatus
    currentStep: str
    progress: int
    tools: list[str] = Field(default_factory=list)
    currentTool: str = ""
    currentTarget: str = ""
    stepStartedAt: str = ""
    completedCount: int = 0
    totalCount: int = 0
    lastResult: str = ""
    lastEventAt: str = ""


class EventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    sequence: int
    runId: str
    agentId: str
    type: EventType
    title: str
    summary: str
    createdAt: str
    status: AgentStatus
    metadata: EventMetadata | None = None


class StreamSnapshotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run: RunSnapshotPayload | None
    agents: list[AgentSnapshotPayload]
    events: list[EventEnvelope]
    running: bool


def validate_event_envelope(payload: dict[str, Any]) -> EventEnvelope:
    """Validate one event payload against the canonical contract."""
    return EventEnvelope.model_validate(payload)


def validate_stream_snapshot(payload: dict[str, Any]) -> StreamSnapshotResponse:
    """Validate one stream snapshot payload against the canonical contract."""
    return StreamSnapshotResponse.model_validate(payload)

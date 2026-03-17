from __future__ import annotations

"""Core domain entities for run/agent/event state."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Run:
    id: str
    started_at: str
    status: str
    title: str
    objective: str


@dataclass(slots=True)
class Agent:
    id: str
    name: str
    role: str
    status: str
    current_step: str
    progress: int
    tools: list[str] = field(default_factory=list)
    current_tool: str = ""
    current_target: str = ""
    step_started_at: str = ""
    completed_count: int = 0
    total_count: int = 0
    last_result: str = ""
    last_event_at: str = ""


@dataclass(slots=True)
class Event:
    id: str
    sequence: int
    run_id: str
    agent_id: str
    type: str
    title: str
    summary: str
    created_at: str
    status: str
    metadata: dict[str, Any] | None = None


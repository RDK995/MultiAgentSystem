from __future__ import annotations

"""In-process event store used by the live agent activity visualizer."""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import itertools
import threading
import uuid
from typing import Any


AgentStatus = str
EventType = str


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class AgentSnapshot:
    id: str
    name: str
    role: str
    status: AgentStatus
    current_step: str
    progress: int
    tools: list[str] = field(default_factory=list)
    current_tool: str = ""
    current_target: str = ""
    step_started_at: str = field(default_factory=_utc_now)
    completed_count: int = 0
    total_count: int = 0
    last_result: str = ""
    last_event_at: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "status": self.status,
            "currentStep": self.current_step,
            "progress": self.progress,
            "tools": list(self.tools),
            "currentTool": self.current_tool,
            "currentTarget": self.current_target,
            "stepStartedAt": self.step_started_at,
            "completedCount": self.completed_count,
            "totalCount": self.total_count,
            "lastResult": self.last_result,
            "lastEventAt": self.last_event_at,
        }


@dataclass(slots=True)
class RunSnapshot:
    id: str
    started_at: str
    status: AgentStatus
    title: str
    objective: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "startedAt": self.started_at,
            "status": self.status,
            "title": self.title,
            "objective": self.objective,
        }


@dataclass(slots=True)
class AgentEvent:
    id: str
    sequence: int
    run_id: str
    agent_id: str
    type: EventType
    title: str
    summary: str
    created_at: str
    status: AgentStatus
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "id": self.id,
            "sequence": self.sequence,
            "runId": self.run_id,
            "agentId": self.agent_id,
            "type": self.type,
            "title": self.title,
            "summary": self.summary,
            "createdAt": self.created_at,
            "status": self.status,
        }
        if self.metadata:
            payload["metadata"] = self.metadata
        return payload


class LiveEventStore:
    """Thread-safe state container for one active visualized run."""

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._events: list[AgentEvent] = []
        self._agents: dict[str, AgentSnapshot] = {}
        self._run: RunSnapshot | None = None
        self._running = False
        self._stop_requested = False
        self._sequence = itertools.count(1)

    def _reset_run_locked(self, *, title: str, objective: str) -> RunSnapshot:
        self._events = []
        self._agents = {}
        self._sequence = itertools.count(1)
        self._stop_requested = False
        self._run = RunSnapshot(
            id=f"run_{uuid.uuid4().hex[:10]}",
            started_at=_utc_now(),
            status="running",
            title=title,
            objective=objective,
        )
        self._running = True
        return self._run

    def reset_run(self, *, title: str, objective: str) -> RunSnapshot:
        with self._condition:
            return self._reset_run_locked(title=title, objective=objective)

    def set_running(self, running: bool) -> None:
        with self._condition:
            self._running = running
            self._condition.notify_all()

    def request_stop(self) -> None:
        with self._condition:
            self._stop_requested = True
            self._condition.notify_all()

    def clear_stop_request(self) -> None:
        with self._condition:
            self._stop_requested = False
            self._condition.notify_all()

    def stop_requested(self) -> bool:
        with self._condition:
            return self._stop_requested

    def is_running(self) -> bool:
        with self._condition:
            return self._running

    def current_run(self) -> RunSnapshot | None:
        with self._condition:
            return self._run

    def update_run_status(self, status: AgentStatus) -> None:
        with self._condition:
            if self._run is None:
                return
            self._run.status = status
            self._condition.notify_all()

    def upsert_agent(
        self,
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
        event_time: str | None = None,
    ) -> None:
        with self._condition:
            snapshot = self._agents.get(agent_id)
            last_event_at = event_time or _utc_now()
            if snapshot is None:
                snapshot = AgentSnapshot(
                    id=agent_id,
                    name=name,
                    role=role,
                    status=status,
                    current_step=current_step,
                    progress=progress,
                    tools=list(tools or []),
                    current_tool=current_tool or "",
                    current_target=current_target or "",
                    step_started_at=last_event_at,
                    completed_count=completed_count or 0,
                    total_count=total_count or 0,
                    last_result=last_result or "",
                    last_event_at=last_event_at,
                )
                self._agents[agent_id] = snapshot
            else:
                step_changed = snapshot.current_step != current_step
                snapshot.name = name
                snapshot.role = role
                snapshot.status = status
                snapshot.current_step = current_step
                snapshot.progress = progress
                snapshot.last_event_at = last_event_at
                if step_changed:
                    snapshot.step_started_at = last_event_at
                if tools is not None:
                    snapshot.tools = list(tools)
                if current_tool is not None:
                    snapshot.current_tool = current_tool
                if current_target is not None:
                    snapshot.current_target = current_target
                if completed_count is not None:
                    snapshot.completed_count = completed_count
                if total_count is not None:
                    snapshot.total_count = total_count
                if last_result is not None:
                    snapshot.last_result = last_result
            self._condition.notify_all()

    def emit(
        self,
        *,
        agent_id: str,
        event_type: EventType,
        title: str,
        summary: str,
        status: AgentStatus,
        metadata: dict[str, Any] | None = None,
    ) -> AgentEvent:
        with self._condition:
            if self._run is None:
                self._reset_run_locked(title="Agent Activity Run", objective="Visualize live agent activity.")
            assert self._run is not None
            created_at = _utc_now()
            merged_metadata = dict(metadata or {})
            agent = self._agents.get(agent_id)
            if agent is not None:
                merged_metadata.setdefault("agentName", agent.name)
                merged_metadata.setdefault("agentRole", agent.role)
                merged_metadata.setdefault("currentStep", agent.current_step)
                merged_metadata.setdefault("progress", agent.progress)
                merged_metadata.setdefault("tools", ",".join(agent.tools))
                merged_metadata.setdefault("currentTool", agent.current_tool)
                merged_metadata.setdefault("currentTarget", agent.current_target)
                merged_metadata.setdefault("stepStartedAt", agent.step_started_at)
                merged_metadata.setdefault("completedCount", agent.completed_count)
                merged_metadata.setdefault("totalCount", agent.total_count)
                merged_metadata.setdefault("lastResult", agent.last_result)
            event = AgentEvent(
                id=f"event_{uuid.uuid4().hex[:10]}",
                sequence=next(self._sequence),
                run_id=self._run.id,
                agent_id=agent_id,
                type=event_type,
                title=title,
                summary=summary,
                created_at=created_at,
                status=status,
                metadata=merged_metadata or None,
            )
            self._events.append(event)
            self._condition.notify_all()
            return event

    def snapshot(self) -> dict[str, Any]:
        with self._condition:
            run = self._run.to_dict() if self._run is not None else None
            agents = [agent.to_dict() for agent in self._agents.values()]
            events = [event.to_dict() for event in self._events]
            return {
                "run": run,
                "agents": agents,
                "events": events,
                "running": self._running,
            }

    def events_after(self, sequence: int) -> list[dict[str, Any]]:
        with self._condition:
            # A new run resets event sequence numbers back to 1.
            # If a long-lived client asks for a much higher sequence from
            # a previous run, return the full current buffer so it can resync.
            if self._events and self._events[-1].sequence < sequence:
                return [event.to_dict() for event in self._events]
            return [event.to_dict() for event in self._events if event.sequence > sequence]

    def wait_for_events(self, sequence: int, timeout: float = 10.0) -> list[dict[str, Any]]:
        with self._condition:
            if self._events and self._events[-1].sequence < sequence:
                return [event.to_dict() for event in self._events]
            fresh = [event.to_dict() for event in self._events if event.sequence > sequence]
            if fresh:
                return fresh
            self._condition.wait(timeout=timeout)
            if self._events and self._events[-1].sequence < sequence:
                return [event.to_dict() for event in self._events]
            return [event.to_dict() for event in self._events if event.sequence > sequence]


_STORE = LiveEventStore()
_VISUALIZER_ENABLED = False


def enable_visualizer_events(enabled: bool = True) -> None:
    global _VISUALIZER_ENABLED
    _VISUALIZER_ENABLED = enabled


def visualizer_events_enabled() -> bool:
    return _VISUALIZER_ENABLED


def get_live_event_store() -> LiveEventStore:
    return _STORE


def stop_visual_run_requested() -> bool:
    return _STORE.stop_requested()


def request_visual_run_stop() -> None:
    _STORE.request_stop()


def start_visual_run(*, title: str, objective: str) -> dict[str, Any]:
    run = _STORE.reset_run(title=title, objective=objective)
    _STORE.emit(
        agent_id="orchestrator",
        event_type="run.started",
        title="Run initialized",
        summary="Workflow bootstrapped and awaiting agent activity.",
        status="running",
        metadata={"title": title},
    )
    return run.to_dict()


def complete_visual_run(*, summary: str, metadata: dict[str, Any] | None = None) -> None:
    _STORE.update_run_status("completed")
    _STORE.emit(
        agent_id="orchestrator",
        event_type="run.completed",
        title="Run complete",
        summary=summary,
        status="completed",
        metadata=metadata,
    )
    _STORE.set_running(False)


def fail_visual_run(*, summary: str, metadata: dict[str, Any] | None = None) -> None:
    _STORE.update_run_status("failed")
    _STORE.emit(
        agent_id="orchestrator",
        event_type="agent.error",
        title="Run failed",
        summary=summary,
        status="failed",
        metadata=metadata,
    )
    _STORE.set_running(False)


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
    _STORE.upsert_agent(
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
    _STORE.upsert_agent(
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
    if not _VISUALIZER_ENABLED:
        return None
    return _STORE.emit(
        agent_id=agent_id,
        event_type=event_type,
        title=title,
        summary=summary,
        status=status,
        metadata=metadata,
    ).to_dict()

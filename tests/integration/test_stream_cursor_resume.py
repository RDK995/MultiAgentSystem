from __future__ import annotations

import json

from uk_resell_adk.api.handlers import stream_events
from uk_resell_adk.infrastructure.event_store import LiveEventStore


class _BreakingWriter:
    def __init__(self) -> None:
        self.value = b""

    def write(self, data: bytes) -> None:
        self.value += data

    def flush(self) -> None:
        # End the endless SSE loop after the first payload flush.
        raise BrokenPipeError


class _Handler:
    def __init__(self) -> None:
        self.wfile = _BreakingWriter()
        self.headers: list[tuple[str, str]] = []
        self.status: int | None = None

    def send_response(self, status: int) -> None:
        self.status = status

    def send_header(self, key: str, value: str) -> None:
        self.headers.append((key, value))

    def end_headers(self) -> None:
        return


def _seed_store_with_three_events() -> LiveEventStore:
    store = LiveEventStore()
    store.reset_run(title="Cursor Run", objective="Validate resume behavior")
    for sequence in range(1, 4):
        store.emit(
            agent_id="orchestrator",
            event_type="agent.message",
            title=f"Event {sequence}",
            summary=f"Summary {sequence}",
            status="running",
        )
    return store


def test_stream_events_replays_only_events_after_cursor(monkeypatch) -> None:
    store = _seed_store_with_three_events()
    handler = _Handler()
    monkeypatch.setattr("uk_resell_adk.api.handlers.get_live_event_store", lambda: store)

    stream_events(handler, query="cursor=1")

    payloads: list[dict[str, object]] = []
    for line in handler.wfile.value.decode("utf-8").splitlines():
        if not line.startswith("data: "):
            continue
        payloads.append(json.loads(line[len("data: ") :]))

    assert [payload["sequence"] for payload in payloads] == [2, 3]

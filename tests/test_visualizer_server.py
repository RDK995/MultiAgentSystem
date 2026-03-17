from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from uk_resell_adk.api import handlers as api_handlers
from uk_resell_adk.infrastructure.event_store import get_live_event_store
from uk_resell_adk.visualizer_server import VisualizerHandler
import uk_resell_adk.visualizer_server as visualizer_server


def _make_handler(path: str) -> VisualizerHandler:
    handler = VisualizerHandler.__new__(VisualizerHandler)
    handler.path = path
    handler.headers = {}
    handler.rfile = io.BytesIO()
    return handler


def test_snapshot_endpoint_returns_seeded_agents(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    def _capture_send_json(_handler: Any, payload: dict[str, Any], status: Any = None) -> None:
        captured["payload"] = payload
        captured["status"] = status

    handler = _make_handler("/api/snapshot")
    monkeypatch.setattr(api_handlers, "send_json", _capture_send_json)

    VisualizerHandler.do_GET(handler)

    payload = captured["payload"]
    assert payload["run"] is None or isinstance(payload["run"], dict)
    agent_ids = {agent["id"] for agent in payload["agents"]}
    assert {"orchestrator", "sourcing", "profitability", "report"}.issubset(agent_ids)


def test_events_endpoint_dispatches_stream_handler(monkeypatch: Any) -> None:
    called = {"stream": False, "query": None}
    handler = _make_handler("/api/events?cursor=27")

    def _capture_stream(_handler: Any, *, query: str = "") -> None:
        called["stream"] = True
        called["query"] = query

    monkeypatch.setattr(api_handlers, "stream_events", _capture_stream)
    VisualizerHandler.do_GET(handler)

    assert called["stream"] is True
    assert called["query"] == "cursor=27"


def test_parse_stream_cursor_handles_missing_invalid_and_negative_values() -> None:
    assert api_handlers.parse_stream_cursor("") == 0
    assert api_handlers.parse_stream_cursor("cursor=18") == 18
    assert api_handlers.parse_stream_cursor("cursor=invalid") == 0
    assert api_handlers.parse_stream_cursor("cursor=-5") == 0


def test_run_start_endpoint_starts_thread_and_returns_started(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}
    thread_started = {"value": False}

    class _FakeThread:
        def __init__(self, target: Any, daemon: bool = False) -> None:
            self._target = target
            self._daemon = daemon

        def start(self) -> None:
            thread_started["value"] = True

    store = get_live_event_store()
    store.set_running(False)

    handler = _make_handler("/api/runs/start")
    monkeypatch.setattr(visualizer_server.threading, "Thread", _FakeThread)
    monkeypatch.setattr(
        api_handlers,
        "send_json",
        lambda _handler, payload, status=None: captured.update({"payload": payload, "status": status}),
    )

    VisualizerHandler.do_POST(handler)

    assert thread_started["value"] is True
    assert captured["payload"] == {"started": True, "runConfig": {}}


def test_run_start_endpoint_parses_and_forwards_run_config(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}
    forwarded: dict[str, Any] = {"value": None}

    def _fake_run_target(run_config: dict[str, int] | None) -> None:
        forwarded["value"] = run_config

    class _ImmediateThread:
        def __init__(self, target: Any, daemon: bool = False) -> None:
            self._target = target
            self._daemon = daemon

        def start(self) -> None:
            self._target()

    handler = _make_handler("/api/runs/start")
    payload = b'{"max_foreign_sites": 6, "source_concurrency": 3, "profitability_concurrency": 12}'
    handler.headers = {"Content-Length": str(len(payload))}
    handler.rfile = io.BytesIO(payload)

    monkeypatch.setattr(
        api_handlers,
        "send_json",
        lambda _handler, body, status=None: captured.update({"payload": body, "status": status}),
    )

    api_handlers.handle_post(handler, run_target=_fake_run_target, thread_factory=_ImmediateThread)

    assert forwarded["value"] == {
        "max_foreign_sites": 6,
        "source_concurrency": 3,
        "profitability_concurrency": 12,
    }
    assert captured["payload"] == {
        "started": True,
        "runConfig": {
            "max_foreign_sites": 6,
            "source_concurrency": 3,
            "profitability_concurrency": 12,
        },
    }


def test_run_stop_endpoint_sets_stop_flag_and_returns_payload(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}
    store = get_live_event_store()
    store.clear_stop_request()

    handler = _make_handler("/api/runs/stop")
    monkeypatch.setattr(
        api_handlers,
        "send_json",
        lambda _handler, payload, status=None: captured.update({"payload": payload, "status": status}),
    )

    VisualizerHandler.do_POST(handler)

    assert captured["payload"] == {"stopping": True}
    assert store.stop_requested() is True


def test_artifact_file_endpoint_serves_html(monkeypatch: Any) -> None:
    artifact_path = Path("reports/test_visualizer_artifact.html")
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text("<html><body>artifact test</body></html>", encoding="utf-8")

    captured: dict[str, Any] = {"headers": []}
    handler = _make_handler(f"/api/artifact/file?path={artifact_path.as_posix()}")
    handler.wfile = _BufferWriter()

    monkeypatch.setattr(handler, "send_response", lambda code: captured.update({"code": code}))
    monkeypatch.setattr(handler, "send_header", lambda key, value: captured["headers"].append((key, value)))
    monkeypatch.setattr(handler, "end_headers", lambda: captured.update({"ended": True}))

    try:
        VisualizerHandler.do_GET(handler)
    finally:
        artifact_path.unlink(missing_ok=True)

    assert captured["code"] == 200
    assert any(key == "Content-Type" and "text/html" in value for key, value in captured["headers"])
    assert "artifact test" in handler.wfile.value.decode("utf-8")


class _BufferWriter:
    def __init__(self) -> None:
        self.value = b""

    def write(self, data: bytes) -> None:
        self.value += data

    def flush(self) -> None:
        return

from __future__ import annotations

"""HTTP handler helpers for the visualizer API surface."""

import json
import logging
from http import HTTPStatus
import threading
from time import perf_counter
from urllib.parse import parse_qs, urlparse
from typing import Any, Callable, IO, Protocol

from uk_resell_adk.infrastructure.artifact_store import (
    read_artifact_file,
    read_artifact_preview,
    resolve_artifact_path,
)
from uk_resell_adk.live_events import get_live_event_store, request_visual_run_stop

LOGGER = logging.getLogger(__name__)
RunConfigPayload = dict[str, int]


class RequestHandlerProtocol(Protocol):
    path: str
    wfile: IO[bytes]
    rfile: IO[bytes]
    headers: Any

    def send_response(self, code: int) -> None: ...

    def send_header(self, key: str, value: str) -> None: ...

    def end_headers(self) -> None: ...


def _log_route(method: str, path: str, status: int, started_at: float) -> None:
    """Emit structured route telemetry for request timing and status."""
    LOGGER.info(
        "request_complete",
        extra={
            "method": method,
            "path": path,
            "status": status,
            "latency_ms": round((perf_counter() - started_at) * 1000, 2),
        },
    )


def handle_options(handler: RequestHandlerProtocol) -> None:
    started_at = perf_counter()
    handler.send_response(HTTPStatus.NO_CONTENT)
    set_cors_headers(handler)
    handler.end_headers()
    _log_route("OPTIONS", handler.path, int(HTTPStatus.NO_CONTENT), started_at)


def handle_get(handler: RequestHandlerProtocol, *, seed_agents: Callable[[], None]) -> None:
    started_at = perf_counter()
    parsed = urlparse(handler.path)
    if parsed.path == "/health":
        send_json(handler, {"ok": True})
        _log_route("GET", parsed.path, int(HTTPStatus.OK), started_at)
        return
    if parsed.path == "/api/snapshot":
        seed_agents()
        send_json(handler, get_live_event_store().snapshot())
        _log_route("GET", parsed.path, int(HTTPStatus.OK), started_at)
        return
    if parsed.path == "/api/events":
        stream_events(handler, query=parsed.query)
        _log_route("GET", parsed.path, int(HTTPStatus.OK), started_at)
        return
    if parsed.path == "/api/artifact":
        send_artifact_preview(handler, parsed.query)
        _log_route("GET", parsed.path, int(HTTPStatus.OK), started_at)
        return
    if parsed.path == "/api/artifact/file":
        send_artifact_file(handler, parsed.query)
        _log_route("GET", parsed.path, int(HTTPStatus.OK), started_at)
        return

    send_json(handler, {"error": "not_found"}, status=HTTPStatus.NOT_FOUND)
    _log_route("GET", parsed.path, int(HTTPStatus.NOT_FOUND), started_at)


def handle_post(
    handler: RequestHandlerProtocol,
    *,
    run_target: Callable[[RunConfigPayload | None], None],
    thread_factory: Callable[..., threading.Thread] = threading.Thread,
) -> None:
    started_at = perf_counter()
    parsed = urlparse(handler.path)
    if parsed.path == "/api/runs/start":
        store = get_live_event_store()
        run_config = parse_run_config_payload(handler)
        if not store.is_running():
            thread = thread_factory(target=lambda: run_target(run_config), daemon=True)
            thread.start()
        send_json(handler, {"started": True, "runConfig": run_config or {}})
        _log_route("POST", parsed.path, int(HTTPStatus.OK), started_at)
        return
    if parsed.path == "/api/runs/stop":
        request_visual_run_stop()
        send_json(handler, {"stopping": True})
        _log_route("POST", parsed.path, int(HTTPStatus.OK), started_at)
        return

    send_json(handler, {"error": "not_found"}, status=HTTPStatus.NOT_FOUND)
    _log_route("POST", parsed.path, int(HTTPStatus.NOT_FOUND), started_at)


def set_cors_headers(handler: RequestHandlerProtocol) -> None:
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type, Cache-Control")


def send_json(
    handler: RequestHandlerProtocol,
    payload: dict[str, object],
    status: HTTPStatus = HTTPStatus.OK,
) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    set_cors_headers(handler)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def parse_stream_cursor(query: str) -> int:
    """Parse the replay cursor from query params.

    The frontend reconnect policy passes the last observed SSE sequence as
    `cursor=<sequence>`. Invalid or negative values are treated as zero so
    the stream falls back to replaying from the beginning of the current run.
    """
    if not query:
        return 0
    raw_cursor = parse_qs(query).get("cursor", ["0"])[0]
    try:
        parsed = int(raw_cursor)
    except ValueError:
        return 0
    return max(0, parsed)


def parse_run_config_payload(handler: RequestHandlerProtocol) -> RunConfigPayload | None:
    """Read optional run-config JSON body from /api/runs/start."""
    try:
        length = int(handler.headers.get("Content-Length", "0"))
    except (TypeError, ValueError, AttributeError):
        length = 0
    if length <= 0:
        return None

    raw_body = handler.rfile.read(length)
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None

    parsed: RunConfigPayload = {}
    for key in ("max_foreign_sites", "profitability_concurrency", "source_concurrency"):
        value = payload.get(key)
        if isinstance(value, int):
            parsed[key] = value
    return parsed or None


def stream_events(handler: RequestHandlerProtocol, *, query: str = "") -> None:
    store = get_live_event_store()
    handler.send_response(HTTPStatus.OK)
    set_cors_headers(handler)
    handler.send_header("Content-Type", "text/event-stream")
    handler.send_header("Cache-Control", "no-cache")
    handler.send_header("Connection", "keep-alive")
    handler.end_headers()

    # Resume from the client-provided cursor so reconnects can recover
    # missed events after transient disconnects.
    last_sequence = parse_stream_cursor(query)
    try:
        while True:
            events = store.wait_for_events(last_sequence, timeout=10.0)
            if not events:
                handler.wfile.write(b": keepalive\n\n")
                handler.wfile.flush()
                continue

            for event in events:
                last_sequence = int(event["sequence"])
                payload = json.dumps(event).encode("utf-8")
                handler.wfile.write(b"event: agent-event\n")
                handler.wfile.write(b"data: ")
                handler.wfile.write(payload)
                handler.wfile.write(b"\n\n")
            handler.wfile.flush()
    except (BrokenPipeError, ConnectionResetError):
        return


def send_artifact_preview(handler: RequestHandlerProtocol, query: str) -> None:
    resolved = resolve_artifact_path(query)
    if resolved is None:
        send_json(handler, {"error": "artifact_unavailable"}, status=HTTPStatus.NOT_FOUND)
        return
    send_json(handler, read_artifact_preview(resolved))


def send_artifact_file(handler: RequestHandlerProtocol, query: str) -> None:
    resolved = resolve_artifact_path(query)
    if resolved is None:
        send_json(handler, {"error": "artifact_unavailable"}, status=HTTPStatus.NOT_FOUND)
        return

    content, content_type = read_artifact_file(resolved)
    handler.send_response(HTTPStatus.OK)
    set_cors_headers(handler)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(content)))
    handler.end_headers()
    handler.wfile.write(content)

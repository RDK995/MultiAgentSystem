from __future__ import annotations

"""HTTP endpoints that expose live run state to the frontend dashboard."""

from datetime import datetime, timezone
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
from urllib.parse import urlparse
from urllib.parse import parse_qs

from uk_resell_adk.live_events import (
    complete_visual_run,
    emit_visual_event,
    enable_visualizer_events,
    fail_visual_run,
    get_live_event_store,
    request_visual_run_stop,
    register_agent,
    start_visual_run,
    update_agent_status,
)
from uk_resell_adk.html_renderer import write_html_report
from uk_resell_adk.tracing import configure_tracing

enable_visualizer_events(True)

from uk_resell_adk.main import run_local_dry_run


SERVER_TITLE = "UK Resell Lead Scan"
SERVER_OBJECTIVE = "Find profitable Japanese trading card opportunities for UK resale."


def _default_html_output_path() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return Path("reports") / f"uk_resell_report_{timestamp}.html"


def _seed_available_agents() -> None:
    register_agent(
        agent_id="orchestrator",
        name="Agent Orchestrator",
        role="Workflow manager",
        status="queued",
        current_step="Waiting to start",
        progress=0,
        tools=["traceable"],
        current_tool="workflow orchestration",
        current_target="run lifecycle",
        completed_count=0,
        total_count=3,
        last_result="Waiting for run start",
    )
    register_agent(
        agent_id="sourcing",
        name="Item Sourcing Agent",
        role="Discovery specialist",
        status="queued",
        current_step="Waiting for run start",
        progress=0,
        tools=["discover_foreign_marketplaces", "find_candidate_items"],
    )
    register_agent(
        agent_id="profitability",
        name="Profitability Agent",
        role="Margin analyst",
        status="queued",
        current_step="Waiting for sourced candidates",
        progress=0,
        tools=["assess_profitability_against_ebay"],
    )
    register_agent(
        agent_id="report",
        name="Report Writer Agent",
        role="Narrative and artifact writer",
        status="queued",
        current_step="Waiting for ranked opportunities",
        progress=0,
        tools=["write_html_report"],
    )


def _run_visualized_workflow() -> None:
    store = get_live_event_store()
    if store.is_running():
        return

    start_visual_run(title=SERVER_TITLE, objective=SERVER_OBJECTIVE)
    _seed_available_agents()
    update_agent_status(
        agent_id="orchestrator",
        name="Agent Orchestrator",
        role="Workflow manager",
        status="running",
        current_step="Preparing workflow",
        progress=4,
        tools=["traceable"],
        current_tool="workflow orchestration",
        current_target="activating agents",
        completed_count=0,
        total_count=3,
        last_result="Run started",
    )
    store.set_running(True)

    try:
        result = run_local_dry_run()
        update_agent_status(
            agent_id="report",
            name="Report Writer Agent",
            role="Narrative and artifact writer",
            status="running",
            current_step="Rendering HTML report",
            progress=92,
            tools=["write_html_report"],
        )
        emit_visual_event(
            agent_id="report",
            event_type="agent.started",
            title="Report writer activated",
            summary="Packaging the final HTML artifact for operator review.",
            status="running",
        )
        report_path = write_html_report(result, _default_html_output_path())
        update_agent_status(
            agent_id="report",
            name="Report Writer Agent",
            role="Narrative and artifact writer",
            status="completed",
            current_step="Publishing artifacts",
            progress=100,
            tools=["write_html_report"],
        )
        emit_visual_event(
            agent_id="report",
            event_type="agent.file_changed",
            title="HTML report packaged",
            summary="Final report artifact generated for this run.",
            status="completed",
            metadata={"artifact": str(report_path)},
        )
        complete_visual_run(
            summary="Three-agent pipeline finished successfully.",
            metadata={
                "marketplaces": len(result["marketplaces"]),
                "candidate_items": len(result["candidate_items"]),
                "assessments": len(result["assessments"]),
                "report_path": str(report_path),
            },
        )
    except Exception as exc:  # noqa: BLE001
        fail_visual_run(summary=f"Workflow crashed: {exc}", metadata={"error": str(exc)})


class VisualizerHandler(BaseHTTPRequestHandler):
    server_version = "UKResellVisualizer/0.1"

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self._set_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._send_json({"ok": True})
            return
        if parsed.path == "/api/snapshot":
            _seed_available_agents()
            self._send_json(get_live_event_store().snapshot())
            return
        if parsed.path == "/api/events":
            self._stream_events()
            return
        if parsed.path == "/api/artifact":
            self._send_artifact_preview(parsed.query)
            return
        if parsed.path == "/api/artifact/file":
            self._send_artifact_file(parsed.query)
            return

        self._send_json({"error": "not_found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/runs/start":
            store = get_live_event_store()
            if not store.is_running():
                thread = threading.Thread(target=_run_visualized_workflow, daemon=True)
                thread.start()
            self._send_json({"started": True})
            return
        if parsed.path == "/api/runs/stop":
            request_visual_run_stop()
            self._send_json({"stopping": True})
            return

        self._send_json({"error": "not_found"}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: object) -> None:
        return

    def _set_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Cache-Control")

    def _send_json(self, payload: dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self._set_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _stream_events(self) -> None:
        store = get_live_event_store()
        self.send_response(HTTPStatus.OK)
        self._set_cors_headers()
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        last_sequence = 0
        try:
            while True:
                events = store.wait_for_events(last_sequence, timeout=10.0)
                if not events:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                    continue

                for event in events:
                    last_sequence = int(event["sequence"])
                    payload = json.dumps(event).encode("utf-8")
                    self.wfile.write(b"event: agent-event\n")
                    self.wfile.write(b"data: ")
                    self.wfile.write(payload)
                    self.wfile.write(b"\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return

    def _resolve_artifact_path(self, query: str) -> Path | None:
        params = parse_qs(query)
        raw_path = params.get("path", [""])[0]
        if not raw_path:
            return None

        artifact_path = Path(raw_path)
        if not artifact_path.is_absolute():
            artifact_path = Path.cwd() / artifact_path

        try:
            resolved = artifact_path.resolve(strict=True)
        except FileNotFoundError:
            return None

        project_root = Path.cwd().resolve()
        if project_root not in resolved.parents and resolved != project_root:
            return None
        return resolved

    def _send_artifact_preview(self, query: str) -> None:
        resolved = self._resolve_artifact_path(query)
        if resolved is None:
            self._send_json({"error": "artifact_unavailable"}, status=HTTPStatus.NOT_FOUND)
            return

        if resolved.suffix.lower() == ".html":
            preview = resolved.read_text(encoding="utf-8", errors="ignore")
            self._send_json(
                {
                    "path": str(resolved),
                    "kind": "html",
                    "content": preview,
                }
            )
            return

        preview = resolved.read_text(encoding="utf-8", errors="ignore")
        self._send_json(
            {
                "path": str(resolved),
                "kind": "text",
                "content": preview[:12000],
            }
        )

    def _send_artifact_file(self, query: str) -> None:
        resolved = self._resolve_artifact_path(query)
        if resolved is None:
            self._send_json({"error": "artifact_unavailable"}, status=HTTPStatus.NOT_FOUND)
            return

        content = resolved.read_bytes()
        content_type = "text/html; charset=utf-8" if resolved.suffix.lower() == ".html" else "text/plain; charset=utf-8"
        self.send_response(HTTPStatus.OK)
        self._set_cors_headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def run_server(host: str = "127.0.0.1", port: int = 8008) -> None:
    configure_tracing()
    _seed_available_agents()
    server = ThreadingHTTPServer((host, port), VisualizerHandler)
    print(f"Visualizer server listening on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()

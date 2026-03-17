from __future__ import annotations

"""HTTP server bootstrap for the visualizer API."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import logging
import threading

from uk_resell_adk.api import handlers as api_handlers
from uk_resell_adk.application.run_service import run_visualized_workflow, seed_available_agents
from uk_resell_adk.config import RuntimeConfigOverrides, runtime_config_with_overrides
from uk_resell_adk.html_renderer import write_html_report
from uk_resell_adk.live_events import enable_visualizer_events
from uk_resell_adk.main import run_local_dry_run
from uk_resell_adk.tracing import configure_tracing

enable_visualizer_events(True)
LOGGER = logging.getLogger(__name__)


def _seed_available_agents() -> None:
    seed_available_agents()


def _run_visualized_workflow(run_config: RuntimeConfigOverrides | None = None) -> None:
    runtime_config = runtime_config_with_overrides(run_config)
    run_visualized_workflow(
        run_workflow=lambda: run_local_dry_run(runtime_config=runtime_config),
        write_report=write_html_report,
    )


class VisualizerHandler(BaseHTTPRequestHandler):
    server_version = "UKResellVisualizer/0.1"

    def do_OPTIONS(self) -> None:  # noqa: N802
        api_handlers.handle_options(self)

    def do_GET(self) -> None:  # noqa: N802
        api_handlers.handle_get(self, seed_agents=_seed_available_agents)

    def do_POST(self) -> None:  # noqa: N802
        api_handlers.handle_post(self, run_target=_run_visualized_workflow, thread_factory=threading.Thread)

    def log_message(self, format: str, *args: object) -> None:
        return


def run_server(host: str = "127.0.0.1", port: int = 8008) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    configure_tracing()
    _seed_available_agents()
    server = ThreadingHTTPServer((host, port), VisualizerHandler)
    LOGGER.info("visualizer_server_start", extra={"host": host, "port": port})
    server.serve_forever()


if __name__ == "__main__":
    run_server()

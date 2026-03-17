from __future__ import annotations

"""Run orchestration service used by the visualizer API layer."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from uk_resell_adk.live_events import (
    complete_visual_run,
    emit_visual_event,
    fail_visual_run,
    get_live_event_store,
    register_agent,
    start_visual_run,
    update_agent_status,
)


SERVER_TITLE = "UK Resell Lead Scan"
SERVER_OBJECTIVE = "Find profitable Japanese trading card opportunities for UK resale."


def default_html_output_path() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return Path("reports") / f"uk_resell_report_{timestamp}.html"


def seed_available_agents() -> None:
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


def run_visualized_workflow(
    *,
    run_workflow: Callable[[], dict[str, Any]],
    write_report: Callable[[dict[str, Any], Path], Path],
) -> None:
    """Run one workflow execution and emit visualizer lifecycle events."""
    store = get_live_event_store()
    if store.is_running():
        return

    start_visual_run(title=SERVER_TITLE, objective=SERVER_OBJECTIVE)
    seed_available_agents()
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
        result = run_workflow()
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
        report_path = write_report(result, default_html_output_path())
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
        update_agent_status(
            agent_id="orchestrator",
            name="Agent Orchestrator",
            role="Workflow manager",
            status="completed",
            current_step="Workflow complete",
            progress=100,
            tools=["traceable"],
            current_tool="workflow orchestration",
            current_target="completed run",
            completed_count=3,
            total_count=3,
            last_result=f"{len(result['assessments'])} profitable items delivered",
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

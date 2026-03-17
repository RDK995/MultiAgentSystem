import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import App from "../App";

const subscribeToAgentEventsMock = vi.fn();

vi.mock("../shared/api/runClient", () => {
  return {
    API_BASE_URL: "http://127.0.0.1:8008",
    loadBackendSnapshot: async () => ({
      run: {
        id: "run_1",
        startedAt: "2026-03-17T00:00:00Z",
        status: "running",
        title: "Demo Run",
        objective: "Objective",
      },
      agents: [
        {
          id: "orchestrator",
          name: "Agent Orchestrator",
          role: "Workflow manager",
          status: "running",
          currentStep: "Preparing workflow",
          progress: 4,
          tools: [],
          lastEventAt: "2026-03-17T00:00:00Z",
        },
        {
          id: "sourcing",
          name: "Item Sourcing Agent",
          role: "Discovery specialist",
          status: "queued",
          currentStep: "Waiting",
          progress: 0,
          tools: [],
          lastEventAt: "2026-03-17T00:00:00Z",
        },
        {
          id: "profitability",
          name: "Profitability Agent",
          role: "Margin analyst",
          status: "queued",
          currentStep: "Waiting",
          progress: 0,
          tools: [],
          lastEventAt: "2026-03-17T00:00:00Z",
        },
        {
          id: "report",
          name: "Report Writer Agent",
          role: "Narrative and artifact writer",
          status: "running",
          currentStep: "Rendering HTML report",
          progress: 92,
          tools: ["write_html_report"],
          lastEventAt: "2026-03-17T00:00:00Z",
        },
      ],
      events: [
        {
          id: "event_1",
          sequence: 5,
          runId: "run_1",
          agentId: "orchestrator",
          type: "agent.message",
          title: "Boot",
          summary: "Boot",
          createdAt: "2026-03-17T00:00:00Z",
          status: "running",
        },
      ],
      running: true,
    }),
    startBackendRun: vi.fn(async () => {}),
    stopBackendRun: vi.fn(async () => {}),
  };
});

vi.mock("../shared/api/eventClient", () => {
  return {
    subscribeToAgentEvents: (...args: unknown[]) => subscribeToAgentEventsMock(...args),
  };
});

describe("App integration", () => {
  it("hydrates from snapshot, subscribes with cursor, and shows report link from SSE artifact event", async () => {
    subscribeToAgentEventsMock.mockImplementation(({ cursor, onEvent, onConnectionStateChange }) => {
      expect(cursor).toBe(5);
      onConnectionStateChange?.("reconnecting");
      onEvent({
        id: "event_report",
        sequence: 6,
        runId: "run_1",
        agentId: "report",
        type: "agent.file_changed",
        title: "Report ready",
        summary: "Artifact generated",
        createdAt: "2026-03-17T00:01:00Z",
        status: "completed",
        metadata: {
          artifact: "reports/uk_resell_report_20260317_100000.html",
        },
      });
      onConnectionStateChange?.("connected");
      return {
        close: () => {},
        getCursor: () => 6,
      };
    });

    render(<App />);

    expect(await screen.findByText("Resell Intelligence Console")).toBeInTheDocument();
    expect(screen.getByText("Live backend stream")).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Open full analyzed-items report" })).toBeInTheDocument();
  });
});

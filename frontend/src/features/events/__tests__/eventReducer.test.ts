import { describe, expect, it } from "vitest";

import { createInitialEventStoreState, eventReducer } from "../eventReducer";

describe("eventReducer", () => {
  it("hydrates snapshot and tracks last sequence", () => {
    const next = eventReducer(createInitialEventStoreState(), {
      type: "snapshot/hydrated",
      payload: {
        run: null,
        agents: [],
        events: [
          {
            id: "event-1",
            sequence: 4,
            runId: "run-1",
            agentId: "orchestrator",
            type: "agent.message",
            title: "Msg",
            summary: "Summary",
            createdAt: "2026-03-17T00:00:00Z",
            status: "running",
          },
        ],
        running: true,
      },
    });

    expect(next.lastSequence).toBe(4);
    expect(next.events).toHaveLength(1);
    expect(next.eventIds["event-1"]).toBe(true);
  });

  it("deduplicates repeated event ids", () => {
    const state = eventReducer(createInitialEventStoreState(), {
      type: "event/received",
      payload: {
        id: "event-1",
        sequence: 1,
        runId: "run-1",
        agentId: "sourcing",
        type: "agent.started",
        title: "Started",
        summary: "Summary",
        createdAt: "2026-03-17T00:00:00Z",
        status: "running",
      },
    });

    const next = eventReducer(state, {
      type: "event/received",
      payload: {
        id: "event-1",
        sequence: 1,
        runId: "run-1",
        agentId: "sourcing",
        type: "agent.started",
        title: "Started",
        summary: "Summary",
        createdAt: "2026-03-17T00:00:00Z",
        status: "running",
      },
    });

    expect(next.events).toHaveLength(1);
  });

  it("marks run completed on run.completed", () => {
    const hydrated = eventReducer(createInitialEventStoreState(), {
      type: "snapshot/hydrated",
      payload: {
        run: {
          id: "run-1",
          startedAt: "2026-03-17T00:00:00Z",
          status: "running",
          title: "Run",
          objective: "Objective",
        },
        agents: [],
        events: [],
        running: true,
      },
    });
    const next = eventReducer(hydrated, {
      type: "event/received",
      payload: {
        id: "event-2",
        sequence: 2,
        runId: "run-1",
        agentId: "orchestrator",
        type: "run.completed",
        title: "Done",
        summary: "Finished",
        createdAt: "2026-03-17T00:01:00Z",
        status: "completed",
      },
    });

    expect(next.run?.status).toBe("completed");
  });

  it("applies orchestrator 100% progress from run.completed metadata", () => {
    const hydrated = eventReducer(createInitialEventStoreState(), {
      type: "snapshot/hydrated",
      payload: {
        run: {
          id: "run-1",
          startedAt: "2026-03-17T00:00:00Z",
          status: "running",
          title: "Run",
          objective: "Objective",
        },
        agents: [
          {
            id: "orchestrator",
            name: "Agent Orchestrator",
            role: "Workflow manager",
            status: "running",
            currentStep: "Transitioning to report generation",
            progress: 76,
            tools: ["traceable"],
            completedCount: 2,
            totalCount: 3,
            lastEventAt: "2026-03-17T00:00:00Z",
          },
        ],
        events: [],
        running: true,
      },
    });

    const next = eventReducer(hydrated, {
      type: "event/received",
      payload: {
        id: "event-3",
        sequence: 3,
        runId: "run-1",
        agentId: "orchestrator",
        type: "run.completed",
        title: "Run complete",
        summary: "Workflow complete",
        createdAt: "2026-03-17T00:01:00Z",
        status: "completed",
        metadata: {
          progress: 100,
          completedCount: 3,
          totalCount: 3,
          currentStep: "Workflow complete",
        },
      },
    });

    expect(next.run?.status).toBe("completed");
    expect(next.agents[0]?.progress).toBe(100);
    expect(next.agents[0]?.completedCount).toBe(3);
    expect(next.agents[0]?.totalCount).toBe(3);
    expect(next.agents[0]?.status).toBe("completed");
  });

  it("incrementally tracks profitable items and latest report artifact", () => {
    const state = eventReducer(createInitialEventStoreState(), {
      type: "events/received",
      payload: [
        {
          id: "event-profitability",
          sequence: 1,
          runId: "run-1",
          agentId: "profitability",
          type: "agent.file_changed",
          title: "Shortlist",
          summary: "Top items available",
          createdAt: "2026-03-17T00:00:00Z",
          status: "completed",
          metadata: {
            topItems: [
              { title: "A", url: "https://item/a", profitGbp: 12.5, marginPercent: 20 },
              { title: "B", url: "https://item/b", profitGbp: -2, marginPercent: -1 },
            ],
          },
        },
        {
          id: "event-report",
          sequence: 2,
          runId: "run-1",
          agentId: "report",
          type: "agent.file_changed",
          title: "Report ready",
          summary: "Artifact generated",
          createdAt: "2026-03-17T00:01:00Z",
          status: "completed",
          metadata: {
            artifact: "reports/demo.html",
          },
        },
      ],
    });

    expect(state.profitableItems).toHaveLength(1);
    expect(state.profitableItems[0]?.url).toBe("https://item/a");
    expect(state.latestReportArtifactPath).toBe("reports/demo.html");
    expect(state.latestEventAgentId).toBe("report");
  });
});

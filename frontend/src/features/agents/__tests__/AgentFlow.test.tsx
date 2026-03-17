import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AgentFlow } from "../AgentFlow";

describe("AgentFlow", () => {
  it("renders report artifact link when report event includes artifact metadata", () => {
    render(
      <AgentFlow
        agents={[
          {
            id: "orchestrator",
            name: "Agent Orchestrator",
            role: "Workflow manager",
            status: "completed",
            currentStep: "Done",
            progress: 100,
            tools: [],
            lastEventAt: "2026-03-17T00:00:00Z",
          },
          {
            id: "sourcing",
            name: "Item Sourcing Agent",
            role: "Discovery specialist",
            status: "completed",
            currentStep: "Done",
            progress: 100,
            tools: [],
            lastEventAt: "2026-03-17T00:00:00Z",
          },
          {
            id: "profitability",
            name: "Profitability Agent",
            role: "Margin analyst",
            status: "completed",
            currentStep: "Done",
            progress: 100,
            tools: [],
            lastEventAt: "2026-03-17T00:00:00Z",
          },
          {
            id: "report",
            name: "Report Writer Agent",
            role: "Narrative and artifact writer",
            status: "completed",
            currentStep: "Done",
            progress: 100,
            tools: [],
            lastEventAt: "2026-03-17T00:00:00Z",
          },
        ]}
        profitableItemCount={3}
        signalsSeen={12}
        latestEventAgentId="report"
        latestReportArtifactPath="reports/demo.html"
      />,
    );

    expect(screen.getByRole("link", { name: "Open full analyzed-items report" })).toBeInTheDocument();
    expect(screen.getByText("Profitable items: 3")).toBeInTheDocument();
  });
});

import { memo } from "react";
import type { Agent } from "../../types";
import { ReportLink } from "../artifacts/ReportLink";

const agentAccent: Record<string, string> = {
  orchestrator: "accent-blue",
  sourcing: "accent-green",
  profitability: "accent-amber",
  report: "accent-coral",
};

const flowOrder = ["orchestrator", "sourcing", "profitability", "report"];
const agentGlyph: Record<string, string> = {
  orchestrator: "◎",
  sourcing: "◉",
  profitability: "◌",
  report: "◈",
};

const labelByStatus = {
  queued: "Queued",
  running: "Running",
  waiting: "Waiting",
  completed: "Completed",
  failed: "Failed",
};

type AgentFlowProps = {
  agents: Agent[];
  profitableItemCount: number;
  signalsSeen: number;
  latestEventAgentId: string | null;
  latestReportArtifactPath: string | null;
};

export const AgentFlow = memo(function AgentFlow({
  agents,
  profitableItemCount,
  signalsSeen,
  latestEventAgentId,
  latestReportArtifactPath,
}: AgentFlowProps) {
  const activeAgentsRunningCount = agents.filter((candidate) => candidate.status === "running").length;
  const flowAgents = flowOrder
    .map((agentId) => agents.find((agent) => agent.id === agentId))
    .filter((agent): agent is Agent => Boolean(agent));

  if (flowAgents.length === 0) {
    return <p className="empty-copy">No agents have started yet.</p>;
  }

  return (
    <div className="flow-track">
      {flowAgents.map((agent, index) => {
        const isLive = latestEventAgentId === agent.id && agent.status === "running";
        const isLatest = latestEventAgentId === agent.id;
        const isManagementAgent = agent.id === "orchestrator";
        const isSourcingAgent = agent.id === "sourcing";
        const isReportAgent = agent.id === "report";
        const reportPath = isReportAgent ? latestReportArtifactPath : null;
        const progressValue = Math.max(0, Math.min(100, Math.round(agent.progress ?? 0)));
        return (
          <div className="flow-segment" key={agent.id}>
            <article
              className={`flow-node ${agentAccent[agent.id] ?? "accent-blue"} ${isLive ? "is-live" : ""} ${agent.status === "running" ? "is-running" : ""}`}
            >
              <div className="flow-robot-row">
                <div className={`robot-badge ${agentAccent[agent.id] ?? "accent-blue"} ${agent.status === "running" ? "robot-active" : ""}`}>
                  <span className="robot-eye left" />
                  <span className="robot-eye right" />
                  <span className="robot-mouth" />
                  <span className="robot-glyph">{agentGlyph[agent.id] ?? "◉"}</span>
                </div>
                <div className="flow-node-heading">
                  <span className="flow-node-label">{agent.name}</span>
                </div>
              </div>
              <div className="flow-progress" aria-hidden="true">
                <div className="flow-progress-fill" style={{ width: `${progressValue}%` }} />
              </div>
              <div className="flow-metric-row">
                <span className="flow-metric-pill">{`${progressValue}%`}</span>
                <span className="flow-metric-pill">{formatCounts(agent.completedCount, agent.totalCount)}</span>
              </div>
              <strong>{labelByStatus[agent.status]}</strong>
              <p>{agent.currentStep}</p>
              <div className="agent-detail-lines">
                {isManagementAgent ? (
                  <>
                    <span>{`Managing: ${agent.currentTarget || "run lifecycle"}`}</span>
                    <span>{`Stages: ${formatCounts(agent.completedCount, agent.totalCount)}`}</span>
                    <span>{`Active agents: ${activeAgentsRunningCount}`}</span>
                    <span>{`Profitable items: ${profitableItemCount}`}</span>
                    <span>{`Signals seen: ${signalsSeen}`}</span>
                  </>
                ) : isReportAgent ? (
                  <>
                    <span>{agent.currentTool ? `Tool: ${agent.currentTool}` : "Tool: waiting"}</span>
                    <span>{agent.currentTarget ? `Target: ${agent.currentTarget}` : "Target: pending"}</span>
                    <span>{formatCounts(agent.completedCount, agent.totalCount)}</span>
                    <span>{agent.lastResult ? `Last result: ${agent.lastResult}` : "Last result: none yet"}</span>
                    <ReportLink artifactPath={reportPath} />
                  </>
                ) : isSourcingAgent ? (
                  <>
                    <span>{agent.currentTool ? `Tool: ${agent.currentTool}` : "Tool: waiting"}</span>
                    <span>{agent.currentTarget ? `Target: ${agent.currentTarget}` : "Target: pending"}</span>
                    <span>{`Items scanned: ${agent.itemsScanned ?? 0}`}</span>
                    <span>{`Items emitted: ${agent.itemsEmitted ?? 0}`}</span>
                    <span>{`Last source latency: ${agent.sourceLatencyMs ?? 0}ms`}</span>
                    <span>{`Markets done: ${agent.marketsProcessed ?? 0}/${agent.marketsTotal ?? 0}`}</span>
                  </>
                ) : (
                  <>
                    <span>{agent.currentTool ? `Tool: ${agent.currentTool}` : "Tool: waiting"}</span>
                    <span>{agent.currentTarget ? `Target: ${agent.currentTarget}` : "Target: pending"}</span>
                    <span>{formatCounts(agent.completedCount, agent.totalCount)}</span>
                    <span>{agent.lastResult ? `Last result: ${agent.lastResult}` : "Last result: none yet"}</span>
                  </>
                )}
              </div>
            </article>
            {index < flowAgents.length - 1 ? (
              <div className={`flow-arrow ${isLatest ? "flow-arrow-active" : ""}`} aria-hidden="true" />
            ) : null}
          </div>
        );
      })}
    </div>
  );
});

function formatCounts(completedCount?: number, totalCount?: number): string {
  if (!totalCount) {
    return "Counts: pending";
  }
  return `Counts: ${completedCount ?? 0}/${totalCount}`;
}

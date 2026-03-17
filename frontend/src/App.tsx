import { useEffect, useState } from "react";
import {
  API_BASE_URL,
  createInitialStreamState,
  loadBackendSnapshot,
  reduceAgents,
  startBackendRun,
  stopBackendRun,
  subscribeToBackendRun,
} from "./lib/streaming";
import type { Agent, AgentEvent, RunSnapshot } from "./types";

const agentAccent: Record<string, string> = {
  orchestrator: "accent-blue",
  sourcing: "accent-green",
  profitability: "accent-amber",
  report: "accent-coral",
};

const labelByStatus = {
  queued: "Queued",
  running: "Running",
  waiting: "Waiting",
  completed: "Completed",
  failed: "Failed",
};

const flowOrder = ["orchestrator", "sourcing", "profitability", "report"];
const agentGlyph: Record<string, string> = {
  orchestrator: "◎",
  sourcing: "◉",
  profitability: "◌",
  report: "◈",
};

function App() {
  const [initialState] = useState(() => createInitialStreamState());
  const [run, setRun] = useState<RunSnapshot | null>(initialState.run);
  const [agents, setAgents] = useState<Agent[]>(initialState.agents);
  const [events, setEvents] = useState<AgentEvent[]>(initialState.events);
  const [connectionLabel, setConnectionLabel] = useState("Connecting");
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [isStartingRun, setIsStartingRun] = useState(false);
  const [isStoppingRun, setIsStoppingRun] = useState(false);

  useEffect(() => {
    let cleanup: () => void = () => {};
    let cancelled = false;

    const applyIncomingEvent = (event: AgentEvent) => {
      setEvents((current) => {
        if (current.some((candidate) => candidate.id === event.id)) {
          return current;
        }
        return [...current, event];
      });
      setAgents((current) => reduceAgents(current, event));
      if (event.type === "run.completed") {
        setRun((current) => (current ? { ...current, status: "completed" } : current));
      }
    };

    async function connect() {
      try {
        const snapshot = await loadBackendSnapshot();
        if (cancelled) {
          return;
        }
        setConnectionError(null);
        setRun(snapshot.run);
        setAgents(snapshot.agents);
        setEvents(snapshot.events);
        setConnectionLabel(snapshot.run ? "Live backend stream" : "Connected");
        cleanup = subscribeToBackendRun(applyIncomingEvent);
      } catch (error) {
        if (cancelled) {
          return;
        }
        setConnectionLabel("Backend offline");
        setConnectionError(error instanceof Error ? error.message : "Unable to connect to the backend stream.");
        setRun(null);
        setAgents([]);
        setEvents([]);
      }
    }

    void connect();

    return () => {
      cancelled = true;
      cleanup();
    };
  }, [initialState.events.length]);

  const latestEvent = events[events.length - 1] ?? null;
  const flowAgents = flowOrder
    .map((agentId) => agents.find((agent) => agent.id === agentId))
    .filter((agent): agent is Agent => Boolean(agent));
  const profitableItems = findTopProfitableItems(events);

  async function handleStartRun() {
    try {
      setIsStartingRun(true);
      setConnectionError(null);
      await startBackendRun();
      const snapshot = await loadBackendSnapshot();
      setRun(snapshot.run);
      setAgents(snapshot.agents);
      setEvents(snapshot.events);
      setConnectionLabel("Live backend stream");
    } catch (error) {
      setConnectionError(error instanceof Error ? error.message : "Unable to start the backend run.");
    } finally {
      setIsStartingRun(false);
    }
  }

  async function handleStopRun() {
    try {
      setIsStoppingRun(true);
      setConnectionError(null);
      await stopBackendRun();
      setConnectionLabel("Stopping run");
    } catch (error) {
      setConnectionError(error instanceof Error ? error.message : "Unable to stop the backend run.");
    } finally {
      setIsStoppingRun(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-copy">
          <p className="eyebrow">Live Agent Flow</p>
          <h1>Resell Intelligence Console</h1>
          <p className="topbar-subtitle">Real-time orchestration across sourcing, profitability analysis, and reporting.</p>
        </div>
        <div className="topbar-actions">
          <div className="chip chip-live">{connectionLabel}</div>
          <div className="chip">{labelByStatus[run?.status ?? "queued"]}</div>
        </div>
      </header>

      {connectionError ? <div className="error-banner">{connectionError}</div> : null}

      <main className="simple-layout">
        <section className="summary-card">
          <p className="eyebrow">Current run</p>
          <h2>{run?.title ?? "Waiting for backend"}</h2>
          <p className="hero-copy">
            {run?.objective ?? "Start the Python visualizer server to stream the real agent flow."}
          </p>
          <div className="summary-actions">
            <button
              className="start-button"
              onClick={() => void handleStartRun()}
              type="button"
              disabled={isStartingRun || isStoppingRun || run?.status === "running"}
            >
              {run?.status === "running" ? "Run in progress" : isStartingRun ? "Starting run..." : "Start run"}
            </button>
            <button
              className="stop-button"
              onClick={() => void handleStopRun()}
              type="button"
              disabled={isStoppingRun || run?.status !== "running"}
            >
              {isStoppingRun ? "Stopping..." : "Stop run"}
            </button>
          </div>
        </section>

        <section className="flow-card">
          <div className="section-title-row">
            <div>
              <p className="eyebrow">Flow</p>
              <h2>Agents</h2>
            </div>
          </div>
          {flowAgents.length > 0 ? (
            <div className="flow-track">
              {flowAgents.map((agent, index) => {
                const isLive = latestEvent?.agentId === agent.id && agent.status === "running";
                const isManagementAgent = agent.id === "orchestrator";
                const isReportAgent = agent.id === "report";
                const reportPath = isReportAgent ? findLatestReportArtifactPath(events) : null;
                const reportHref = reportPath ? `${API_BASE_URL}/api/artifact/file?path=${encodeURIComponent(reportPath)}` : "";
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
                      <strong>{labelByStatus[agent.status]}</strong>
                      <p>{agent.currentStep}</p>
                      <div className="agent-detail-lines">
                        {isManagementAgent ? (
                          <>
                            <span>{`Managing: ${agent.currentTarget || "run lifecycle"}`}</span>
                            <span>{`Stages: ${formatCounts(agent.completedCount, agent.totalCount)}`}</span>
                            <span>{`Active agents: ${agents.filter((candidate) => candidate.status === "running").length}`}</span>
                            <span>{`Profitable items: ${profitableItems.length}`}</span>
                            <span>{`Signals seen: ${events.length}`}</span>
                          </>
                        ) : isReportAgent ? (
                          <>
                            <span>{agent.currentTool ? `Tool: ${agent.currentTool}` : "Tool: waiting"}</span>
                            <span>{agent.currentTarget ? `Target: ${agent.currentTarget}` : "Target: pending"}</span>
                            <span>{formatCounts(agent.completedCount, agent.totalCount)}</span>
                            <span>{agent.lastResult ? `Last result: ${agent.lastResult}` : "Last result: none yet"}</span>
                            {reportPath ? (
                              <a className="report-agent-link" href={reportHref} target="_blank" rel="noreferrer">
                                Open full analyzed-items report
                              </a>
                            ) : (
                              <span>Report link appears after generation.</span>
                            )}
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
                    {index < flowAgents.length - 1 ? <div className="flow-arrow" aria-hidden="true" /> : null}
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="empty-copy">No agents have started yet.</p>
          )}
        </section>

        <section className="live-card">
          <div className="section-title-row">
            <div>
              <p className="eyebrow">Profitable items</p>
              <h2>{profitableItems.length > 0 ? "Best opportunities found" : "Waiting for profitability results"}</h2>
            </div>
            <div className="chip">{profitableItems.length > 0 ? `${profitableItems.length} items` : "--"}</div>
          </div>
          <p className="hero-copy">
            {profitableItems.length > 0
              ? "Items are ordered by estimated profit, with the strongest opportunities first."
              : "Once profitability analysis completes, the best items will appear here."}
          </p>
          <div className="recent-feed">
            {profitableItems.length > 0 ? (
              profitableItems.map((item) => (
                <article className="item-card" key={`${item.title}-${item.url}`}>
                  <div className="item-card-header">
                    <strong>{item.title}</strong>
                    <span className="item-profit">GBP {item.profitGbp.toFixed(2)}</span>
                  </div>
                  <div className="item-card-meta">
                    <span>{item.marginPercent.toFixed(2)}% margin</span>
                  </div>
                  <a className="item-link" href={item.url} target="_blank" rel="noreferrer">
                    View source item
                  </a>
                </article>
              ))
            ) : (
              <p className="empty-copy">No profitable items yet.</p>
            )}
          </div>
        </section>

      </main>
    </div>
  );
}

function formatCounts(completedCount?: number, totalCount?: number): string {
  if (!totalCount) {
    return "Counts: pending";
  }
  return `Counts: ${completedCount ?? 0}/${totalCount}`;
}

type TopItem = {
  title: string;
  profitGbp: number;
  marginPercent: number;
  url: string;
};

function findTopProfitableItems(events: AgentEvent[]): TopItem[] {
  const byUrl = new Map<string, TopItem>();

  for (let index = events.length - 1; index >= 0; index -= 1) {
    const liveTitle = events[index]?.metadata?.profitableItemTitle;
    const liveUrl = events[index]?.metadata?.profitableItemUrl;
    const liveProfit = events[index]?.metadata?.profitableItemProfitGbp;
    const liveMargin = events[index]?.metadata?.profitableItemMarginPercent;

    if (
      typeof liveTitle === "string" &&
      typeof liveUrl === "string" &&
      typeof liveProfit === "number" &&
      typeof liveMargin === "number" &&
      liveProfit > 0 &&
      !byUrl.has(liveUrl)
    ) {
      byUrl.set(liveUrl, {
        title: liveTitle,
        profitGbp: liveProfit,
        marginPercent: liveMargin,
        url: liveUrl,
      });
    }

    const candidate = events[index]?.metadata?.topItems;
    if (!Array.isArray(candidate)) {
      continue;
    }

    for (const item of candidate) {
      const url = typeof item.url === "string" ? item.url : "#";
      if (byUrl.has(url)) {
        continue;
      }
      const profit = typeof item.profitGbp === "number" ? item.profitGbp : 0;
      if (profit <= 0) {
        continue;
      }
      byUrl.set(url, {
        title: typeof item.title === "string" ? item.title : "Untitled item",
        profitGbp: profit,
        marginPercent: typeof item.marginPercent === "number" ? item.marginPercent : 0,
        url,
      });
    }
  }

  return Array.from(byUrl.values()).sort((left, right) => right.profitGbp - left.profitGbp);
}

function findLatestReportArtifactPath(events: AgentEvent[]): string | null {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const event = events[index];
    if (!event || event.agentId !== "report") {
      continue;
    }
    const artifact = event.metadata?.artifact;
    if (typeof artifact === "string" && artifact.length > 0) {
      return artifact;
    }
  }
  return null;
}

export default App;

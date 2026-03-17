import { useDeferredValue } from "react";
import { AgentFlow } from "./features/agents/AgentFlow";
import { ProfitableItemGrid } from "./features/events/ProfitableItemGrid";
import { useEventStore } from "./features/events/eventStore";
import { useLiveEventStream } from "./features/events/useLiveEventStream";
import { RunControls } from "./features/runs/RunControls";
import { useRunController } from "./features/runs/useRunController";

const labelByStatus = {
  queued: "Queued",
  running: "Running",
  waiting: "Waiting",
  completed: "Completed",
  failed: "Failed",
};

function App() {
  const { state, hydrateSnapshot, receiveEvents } = useEventStore();
  const { connectionLabel, connectionError, clearConnectionError } = useLiveEventStream({
    hydrateSnapshot,
    receiveEvents,
  });
  const {
    actionError,
    isStartingRun,
    isStoppingRun,
    runConfig,
    setSourceConcurrency,
    setProfitabilityConcurrency,
    startRun,
    stopRun,
  } = useRunController({
    hydrateSnapshot,
    clearConnectionError,
  });

  const deferredAgents = useDeferredValue(state.agents);
  const deferredProfitableItems = useDeferredValue(state.profitableItems);

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
          <div className="chip">{labelByStatus[state.run?.status ?? "queued"]}</div>
        </div>
      </header>

      {actionError || connectionError ? <div className="error-banner">{actionError ?? connectionError}</div> : null}

      <main className="simple-layout">
        <RunControls
          run={state.run}
          runConfig={runConfig}
          onSourceConcurrencyChange={setSourceConcurrency}
          onProfitabilityConcurrencyChange={setProfitabilityConcurrency}
          onStartRun={() => void startRun()}
          onStopRun={() => void stopRun()}
          isStartingRun={isStartingRun}
          isStoppingRun={isStoppingRun}
        />

        <section className="flow-card">
          <div className="section-title-row">
            <div>
              <p className="eyebrow">Flow</p>
              <h2>Agents</h2>
            </div>
          </div>
          <AgentFlow
            agents={deferredAgents}
            profitableItemCount={deferredProfitableItems.length}
            signalsSeen={state.totalSignalsSeen}
            latestEventAgentId={state.latestEventAgentId}
            latestReportArtifactPath={state.latestReportArtifactPath}
          />
        </section>

        <section className="live-card">
          <div className="section-title-row">
            <div>
              <p className="eyebrow">Profitable items</p>
              <h2>{deferredProfitableItems.length > 0 ? "Best opportunities found" : "Waiting for profitability results"}</h2>
            </div>
            <div className="chip">{deferredProfitableItems.length > 0 ? `${deferredProfitableItems.length} items` : "--"}</div>
          </div>
          <p className="hero-copy">
            {deferredProfitableItems.length > 0
              ? "Items are ordered by estimated profit, with the strongest opportunities first."
              : "Once profitability analysis completes, the best items will appear here."}
          </p>
          {deferredProfitableItems.length > 0 ? (
            <ProfitableItemGrid items={deferredProfitableItems} />
          ) : (
            <p className="empty-copy">No profitable items yet.</p>
          )}
        </section>
      </main>
    </div>
  );
}

export default App;

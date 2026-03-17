import type { RunSnapshot } from "../../types";
import type { RunConfig } from "../../shared/api/runClient";

type RunControlsProps = {
  run: RunSnapshot | null;
  runConfig: RunConfig;
  onSourceConcurrencyChange: (value: number) => void;
  onProfitabilityConcurrencyChange: (value: number) => void;
  onStartRun: () => void;
  onStopRun: () => void;
  isStartingRun: boolean;
  isStoppingRun: boolean;
};

/**
 * Render-only run controls component.
 *
 * Business logic lives in callers/hooks; this component keeps markup stable
 * and testable while preserving existing UI behavior.
 */
export function RunControls({
  run,
  runConfig,
  onSourceConcurrencyChange,
  onProfitabilityConcurrencyChange,
  onStartRun,
  onStopRun,
  isStartingRun,
  isStoppingRun,
}: RunControlsProps) {
  return (
    <section className="summary-card">
      <p className="eyebrow">Current run</p>
      <h2>{run?.title ?? "Waiting for backend"}</h2>
      <p className="hero-copy">{run?.objective ?? "Start the Python visualizer server to stream the real agent flow."}</p>
      <div className="run-config-grid">
        <label className="run-config-field">
          <span>Source concurrency</span>
          <input
            type="number"
            min={1}
            step={1}
            value={runConfig.sourceConcurrency}
            onChange={(event) => onSourceConcurrencyChange(Math.max(1, Number(event.target.value) || 1))}
          />
        </label>
        <label className="run-config-field">
          <span>Profitability concurrency</span>
          <input
            type="number"
            min={1}
            step={1}
            value={runConfig.profitabilityConcurrency}
            onChange={(event) => onProfitabilityConcurrencyChange(Math.max(1, Number(event.target.value) || 1))}
          />
        </label>
      </div>
      <div className="summary-actions">
        <button
          className="start-button"
          onClick={onStartRun}
          type="button"
          disabled={isStartingRun || isStoppingRun || run?.status === "running"}
        >
          {run?.status === "running" ? "Run in progress" : isStartingRun ? "Starting run..." : "Start run"}
        </button>
        <button className="stop-button" onClick={onStopRun} type="button" disabled={isStoppingRun || run?.status !== "running"}>
          {isStoppingRun ? "Stopping..." : "Stop run"}
        </button>
      </div>
    </section>
  );
}

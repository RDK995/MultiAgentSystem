import { useCallback, useState } from "react";
import type { StreamState } from "../../types";
import { loadBackendSnapshot, startBackendRun, stopBackendRun, type RunConfig } from "../../shared/api/runClient";

type UseRunControllerArgs = {
  hydrateSnapshot: (snapshot: StreamState) => void;
  clearConnectionError: () => void;
};

type RunControllerState = {
  actionError: string | null;
  isStartingRun: boolean;
  isStoppingRun: boolean;
  runConfig: RunConfig;
  setSourceConcurrency: (value: number) => void;
  setProfitabilityConcurrency: (value: number) => void;
  startRun: () => Promise<void>;
  stopRun: () => Promise<void>;
};

/**
 * Owns run start/stop side effects and action-level error state.
 */
export function useRunController({ hydrateSnapshot, clearConnectionError }: UseRunControllerArgs): RunControllerState {
  const [actionError, setActionError] = useState<string | null>(null);
  const [isStartingRun, setIsStartingRun] = useState(false);
  const [isStoppingRun, setIsStoppingRun] = useState(false);
  const [runConfig, setRunConfig] = useState<RunConfig>({
    sourceConcurrency: 4,
    profitabilityConcurrency: 10,
  });

  const setSourceConcurrency = useCallback((value: number) => {
    setRunConfig((current) => ({ ...current, sourceConcurrency: Math.max(1, value) }));
  }, []);

  const setProfitabilityConcurrency = useCallback((value: number) => {
    setRunConfig((current) => ({ ...current, profitabilityConcurrency: Math.max(1, value) }));
  }, []);

  const startRun = useCallback(async () => {
    try {
      setIsStartingRun(true);
      setActionError(null);
      clearConnectionError();
      await startBackendRun(runConfig);
      const snapshot = await loadBackendSnapshot();
      hydrateSnapshot(snapshot);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Unable to start the backend run.");
    } finally {
      setIsStartingRun(false);
    }
  }, [clearConnectionError, hydrateSnapshot, runConfig]);

  const stopRun = useCallback(async () => {
    try {
      setIsStoppingRun(true);
      setActionError(null);
      clearConnectionError();
      await stopBackendRun();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Unable to stop the backend run.");
    } finally {
      setIsStoppingRun(false);
    }
  }, [clearConnectionError]);

  return {
    actionError,
    isStartingRun,
    isStoppingRun,
    runConfig,
    setSourceConcurrency,
    setProfitabilityConcurrency,
    startRun,
    stopRun,
  };
}

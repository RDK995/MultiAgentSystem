import type { StreamState } from "../../types";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8008";

export type RunConfig = {
  sourceConcurrency: number;
  profitabilityConcurrency: number;
};

export async function loadBackendSnapshot(): Promise<StreamState> {
  const response = await fetch(`${API_BASE_URL}/api/snapshot`);
  if (!response.ok) {
    throw new Error(`Snapshot request failed with status ${response.status}`);
  }
  return (await response.json()) as StreamState;
}

export async function startBackendRun(runConfig?: RunConfig): Promise<void> {
  const payload = runConfig
    ? {
        source_concurrency: runConfig.sourceConcurrency,
        profitability_concurrency: runConfig.profitabilityConcurrency,
      }
    : undefined;
  const response = await fetch(`${API_BASE_URL}/api/runs/start`, {
    method: "POST",
    headers: payload ? { "Content-Type": "application/json" } : undefined,
    body: payload ? JSON.stringify(payload) : undefined,
  });
  if (!response.ok) {
    throw new Error(`Run start failed with status ${response.status}`);
  }
}

export async function stopBackendRun(): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/runs/stop`, { method: "POST" });
  if (!response.ok) {
    throw new Error(`Run stop failed with status ${response.status}`);
  }
}

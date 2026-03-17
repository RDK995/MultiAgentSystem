import type { Agent, AgentEvent, StreamState } from "../types";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8008";

export function createInitialStreamState(): StreamState {
  return {
    run: null,
    agents: [],
    events: [],
    running: false,
  };
}

export function reduceAgents(agents: Agent[], event: AgentEvent): Agent[] {
  const metadata = event.metadata ?? {};
  const currentStep = typeof metadata.currentStep === "string" ? metadata.currentStep : null;
  const progress = typeof metadata.progress === "number" ? metadata.progress : null;
  const agentName = typeof metadata.agentName === "string" ? metadata.agentName : null;
  const agentRole = typeof metadata.agentRole === "string" ? metadata.agentRole : null;
  const tools = typeof metadata.tools === "string" ? metadata.tools.split(",").filter(Boolean) : null;
  const currentTool = typeof metadata.currentTool === "string" ? metadata.currentTool : null;
  const currentTarget = typeof metadata.currentTarget === "string" ? metadata.currentTarget : null;
  const stepStartedAt = typeof metadata.stepStartedAt === "string" ? metadata.stepStartedAt : null;
  const completedCount = typeof metadata.completedCount === "number" ? metadata.completedCount : null;
  const totalCount = typeof metadata.totalCount === "number" ? metadata.totalCount : null;
  const lastResult = typeof metadata.lastResult === "string" ? metadata.lastResult : null;

  if (currentStep || progress !== null || agentName || agentRole || tools || currentTool || currentTarget || stepStartedAt || completedCount !== null || totalCount !== null || lastResult) {
    const existingAgent = agents.find((agent) => agent.id === event.agentId);
    const nextAgent: Agent = {
      id: event.agentId,
      name: agentName ?? existingAgent?.name ?? event.agentId,
      role: agentRole ?? existingAgent?.role ?? "Observed agent",
      status: event.status,
      currentStep: currentStep ?? existingAgent?.currentStep ?? event.title,
      progress: progress ?? existingAgent?.progress ?? 0,
      tools: tools ?? existingAgent?.tools ?? [],
      currentTool: currentTool ?? existingAgent?.currentTool ?? "",
      currentTarget: currentTarget ?? existingAgent?.currentTarget ?? "",
      stepStartedAt: stepStartedAt ?? existingAgent?.stepStartedAt ?? event.createdAt,
      completedCount: completedCount ?? existingAgent?.completedCount ?? 0,
      totalCount: totalCount ?? existingAgent?.totalCount ?? 0,
      lastResult: lastResult ?? existingAgent?.lastResult ?? "",
      lastEventAt: event.createdAt,
    };

    if (existingAgent) {
      return agents.map((agent) => (agent.id === event.agentId ? nextAgent : agent));
    }

    return [...agents, nextAgent];
  }

  const existingAgent = agents.find((agent) => agent.id === event.agentId);
  const nextAgent: Agent = {
    id: event.agentId,
    name: existingAgent?.name ?? event.agentId,
    role: existingAgent?.role ?? "Observed agent",
    status: event.status,
    currentStep: existingAgent?.currentStep ?? event.title,
    progress: existingAgent?.progress ?? 0,
    tools: existingAgent?.tools ?? [],
    currentTool: existingAgent?.currentTool ?? "",
    currentTarget: existingAgent?.currentTarget ?? "",
    stepStartedAt: existingAgent?.stepStartedAt ?? event.createdAt,
    completedCount: existingAgent?.completedCount ?? 0,
    totalCount: existingAgent?.totalCount ?? 0,
    lastResult: existingAgent?.lastResult ?? "",
    lastEventAt: event.createdAt,
  };

  if (existingAgent) {
    return agents.map((agent) => (agent.id === event.agentId ? nextAgent : agent));
  }

  return [...agents, nextAgent];
}

export function countStatus(agents: Agent[]) {
  return {
    active: agents.filter((agent) => agent.status === "running").length,
    blocked: agents.filter((agent) => agent.status === "waiting" || agent.status === "failed").length,
    completed: agents.filter((agent) => agent.status === "completed").length,
  };
}

export async function loadBackendSnapshot(): Promise<StreamState> {
  const response = await fetch(`${API_BASE_URL}/api/snapshot`);
  if (!response.ok) {
    throw new Error(`Snapshot request failed with status ${response.status}`);
  }
  return (await response.json()) as StreamState;
}

export async function startBackendRun(): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/runs/start`, { method: "POST" });
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

export function subscribeToBackendRun(onEvent: (event: AgentEvent) => void): () => void {
  const source = new EventSource(`${API_BASE_URL}/api/events`);
  source.addEventListener("agent-event", (message) => {
    const payload = JSON.parse((message as MessageEvent<string>).data) as AgentEvent;
    onEvent(payload);
  });
  return () => source.close();
}

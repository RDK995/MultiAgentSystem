export type AgentStatus = "queued" | "running" | "waiting" | "completed" | "failed";

export type EventType =
  | "run.started"
  | "run.completed"
  | "agent.started"
  | "agent.progress"
  | "agent.message"
  | "agent.tool_called"
  | "agent.tool_completed"
  | "agent.file_changed"
  | "agent.blocked"
  | "agent.error";

export type Agent = {
  id: string;
  name: string;
  role: string;
  status: AgentStatus;
  currentStep: string;
  progress: number;
  tools: string[];
  currentTool?: string;
  currentTarget?: string;
  stepStartedAt?: string;
  completedCount?: number;
  totalCount?: number;
  lastResult?: string;
  lastEventAt: string;
};

export type AgentEvent = {
  id: string;
  sequence?: number;
  runId: string;
  agentId: string;
  type: EventType;
  title: string;
  summary: string;
  createdAt: string;
  status: AgentStatus;
  metadata?: Record<string, string | number | boolean | Array<Record<string, string | number | boolean>>>;
};

export type RunSnapshot = {
  id: string;
  startedAt: string;
  status: AgentStatus;
  title: string;
  objective: string;
};

export type StreamState = {
  run: RunSnapshot | null;
  agents: Agent[];
  events: AgentEvent[];
  running?: boolean;
};

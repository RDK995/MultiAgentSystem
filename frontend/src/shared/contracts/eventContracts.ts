/**
 * Canonical frontend event contract values.
 *
 * Keep this list in sync with backend values defined in:
 * `src/uk_resell_adk/contracts/events.py`.
 */
export const AGENT_STATUSES = ["queued", "running", "waiting", "completed", "failed"] as const;

export const EVENT_TYPES = [
  "run.started",
  "run.completed",
  "agent.started",
  "agent.progress",
  "agent.message",
  "agent.tool_called",
  "agent.tool_completed",
  "agent.file_changed",
  "agent.blocked",
  "agent.error",
] as const;

export type AgentStatus = (typeof AGENT_STATUSES)[number];
export type EventType = (typeof EVENT_TYPES)[number];

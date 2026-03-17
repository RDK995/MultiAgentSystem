import type { Agent, AgentEvent, StreamState } from "../../types";
import { findLatestReportArtifactPath, findTopProfitableItems, type TopItem } from "./selectors";

export type EventStoreState = StreamState & {
  lastSequence: number;
  eventIds: Record<string, true>;
  profitableItems: TopItem[];
  profitableItemsByUrl: Record<string, TopItem>;
  latestReportArtifactPath: string | null;
  latestEventAgentId: string | null;
  totalSignalsSeen: number;
};

export type EventStoreAction =
  | { type: "snapshot/hydrated"; payload: StreamState }
  | { type: "event/received"; payload: AgentEvent }
  | { type: "events/received"; payload: AgentEvent[] };

export function createInitialEventStoreState(): EventStoreState {
  return {
    run: null,
    agents: [],
    events: [],
    running: false,
    lastSequence: 0,
    eventIds: {},
    profitableItems: [],
    profitableItemsByUrl: {},
    latestReportArtifactPath: null,
    latestEventAgentId: null,
    totalSignalsSeen: 0,
  };
}

export function eventReducer(state: EventStoreState, action: EventStoreAction): EventStoreState {
  if (action.type === "snapshot/hydrated") {
    const lastSequence = findLastSequence(action.payload.events);
    const eventIds = buildEventIds(action.payload.events);
    const profitableItems = findTopProfitableItems(action.payload.events);
    const profitableItemsByUrl = Object.fromEntries(profitableItems.map((item) => [item.url, item]));
    const latestReportArtifactPath = findLatestReportArtifactPath(action.payload.events);
    const latestEventAgentId = action.payload.events[action.payload.events.length - 1]?.agentId ?? null;
    return {
      ...action.payload,
      lastSequence,
      eventIds,
      profitableItems,
      profitableItemsByUrl,
      latestReportArtifactPath,
      latestEventAgentId,
      totalSignalsSeen: action.payload.events.length,
    };
  }

  if (action.type === "event/received") {
    return applyEvent(state, action.payload);
  }

  if (action.type === "events/received") {
    let next = state;
    for (const event of action.payload) {
      next = applyEvent(next, event);
    }
    return next;
  }

  return state;
}

function applyEvent(state: EventStoreState, event: AgentEvent): EventStoreState {
  if (state.eventIds[event.id]) {
    return state;
  }

  const events = appendBoundedEvents(state.events, event);
  const agents = reduceAgents(state.agents, event);
  const eventIds = buildBoundedEventIds(state.eventIds, events, event.id);
  const run: EventStoreState["run"] =
    event.type === "run.completed"
      ? state.run
        ? { ...state.run, status: "completed" as const }
        : state.run
      : state.run;
  const lastSequence = typeof event.sequence === "number" ? Math.max(state.lastSequence, event.sequence) : state.lastSequence;
  const profitableItemsByUrl = maybeUpdateProfitableItemsByUrl(state.profitableItemsByUrl, event);
  const profitableItems =
    profitableItemsByUrl === state.profitableItemsByUrl
      ? state.profitableItems
      : Object.values(profitableItemsByUrl).sort((left, right) => right.profitGbp - left.profitGbp);
  const latestReportArtifactPath = extractReportArtifact(event) ?? state.latestReportArtifactPath;

  return {
    ...state,
    run,
    agents,
    events,
    eventIds,
    lastSequence,
    profitableItems,
    profitableItemsByUrl,
    latestReportArtifactPath,
    latestEventAgentId: event.agentId,
    totalSignalsSeen: state.totalSignalsSeen + 1,
  };
}

const MAX_BUFFERED_EVENTS = 1200;
const MAX_BUFFERED_EVENT_IDS = 2500;

function appendBoundedEvents(events: AgentEvent[], incoming: AgentEvent): AgentEvent[] {
  if (events.length < MAX_BUFFERED_EVENTS) {
    return [...events, incoming];
  }
  return [...events.slice(events.length - MAX_BUFFERED_EVENTS + 1), incoming];
}

function buildBoundedEventIds(
  eventIds: Record<string, true>,
  currentEvents: AgentEvent[],
  incomingEventId: string,
): Record<string, true> {
  const next: Record<string, true> = { ...eventIds, [incomingEventId]: true };
  if (Object.keys(next).length <= MAX_BUFFERED_EVENT_IDS) {
    return next;
  }
  // Keep dedupe IDs aligned with buffered events to avoid unbounded growth.
  const rebuilt: Record<string, true> = {};
  for (const event of currentEvents) {
    rebuilt[event.id] = true;
  }
  return rebuilt;
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
  const sourceLatencyMs = typeof metadata.sourceLatencyMs === "number" ? metadata.sourceLatencyMs : null;
  const itemsScanned =
    typeof metadata.cumulativeScanned === "number"
      ? metadata.cumulativeScanned
      : typeof metadata.itemsScanned === "number"
        ? metadata.itemsScanned
        : null;
  const itemsEmitted =
    typeof metadata.cumulativeEmitted === "number"
      ? metadata.cumulativeEmitted
      : typeof metadata.itemsEmitted === "number"
        ? metadata.itemsEmitted
        : null;
  const marketsProcessed = typeof metadata.marketsProcessed === "number" ? metadata.marketsProcessed : null;
  const marketsTotal = typeof metadata.marketsTotal === "number" ? metadata.marketsTotal : null;

  if (
    currentStep ||
    progress !== null ||
    agentName ||
    agentRole ||
    tools ||
    currentTool ||
    currentTarget ||
    stepStartedAt ||
    completedCount !== null ||
    totalCount !== null ||
    lastResult
    || sourceLatencyMs !== null
    || itemsScanned !== null
    || itemsEmitted !== null
    || marketsProcessed !== null
    || marketsTotal !== null
  ) {
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
      sourceLatencyMs: sourceLatencyMs ?? existingAgent?.sourceLatencyMs,
      itemsScanned: itemsScanned ?? existingAgent?.itemsScanned,
      itemsEmitted: itemsEmitted ?? existingAgent?.itemsEmitted,
      marketsProcessed: marketsProcessed ?? existingAgent?.marketsProcessed,
      marketsTotal: marketsTotal ?? existingAgent?.marketsTotal,
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
    sourceLatencyMs: existingAgent?.sourceLatencyMs,
    itemsScanned: existingAgent?.itemsScanned,
    itemsEmitted: existingAgent?.itemsEmitted,
    marketsProcessed: existingAgent?.marketsProcessed,
    marketsTotal: existingAgent?.marketsTotal,
    lastEventAt: event.createdAt,
  };

  if (existingAgent) {
    return agents.map((agent) => (agent.id === event.agentId ? nextAgent : agent));
  }
  return [...agents, nextAgent];
}

function findLastSequence(events: AgentEvent[]): number {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const sequence = events[index]?.sequence;
    if (typeof sequence === "number") {
      return sequence;
    }
  }
  return 0;
}

function buildEventIds(events: AgentEvent[]): Record<string, true> {
  const eventIds: Record<string, true> = {};
  for (const event of events) {
    eventIds[event.id] = true;
  }
  return eventIds;
}

function maybeUpdateProfitableItemsByUrl(
  profitableItemsByUrl: Record<string, TopItem>,
  event: AgentEvent,
): Record<string, TopItem> {
  const newItems = extractTopItemsFromEvent(event);
  if (newItems.length === 0) {
    return profitableItemsByUrl;
  }

  let changed = false;
  const next = { ...profitableItemsByUrl };
  for (const item of newItems) {
    const current = next[item.url];
    if (!current || current.profitGbp !== item.profitGbp || current.marginPercent !== item.marginPercent || current.title !== item.title) {
      next[item.url] = item;
      changed = true;
    }
  }
  return changed ? next : profitableItemsByUrl;
}

function extractTopItemsFromEvent(event: AgentEvent): TopItem[] {
  const metadata = event.metadata;
  if (!metadata) {
    return [];
  }

  const topItems: TopItem[] = [];
  const liveTitle = metadata.profitableItemTitle;
  const liveUrl = metadata.profitableItemUrl;
  const liveProfit = metadata.profitableItemProfitGbp;
  const liveMargin = metadata.profitableItemMarginPercent;
  if (typeof liveTitle === "string" && typeof liveUrl === "string" && typeof liveProfit === "number" && typeof liveMargin === "number" && liveProfit > 0) {
    topItems.push({
      title: liveTitle,
      url: liveUrl,
      profitGbp: liveProfit,
      marginPercent: liveMargin,
    });
  }

  const candidate = metadata.topItems;
  if (!Array.isArray(candidate)) {
    return topItems;
  }

  for (const item of candidate) {
    if (!item || typeof item !== "object") {
      continue;
    }
    const url = typeof item.url === "string" ? item.url : "";
    const title = typeof item.title === "string" ? item.title : "Untitled item";
    const profitGbp = typeof item.profitGbp === "number" ? item.profitGbp : 0;
    const marginPercent = typeof item.marginPercent === "number" ? item.marginPercent : 0;
    if (!url || profitGbp <= 0) {
      continue;
    }
    topItems.push({ title, url, profitGbp, marginPercent });
  }

  return topItems;
}

function extractReportArtifact(event: AgentEvent): string | null {
  if (event.agentId !== "report") {
    return null;
  }
  const artifact = event.metadata?.artifact;
  if (typeof artifact === "string" && artifact.length > 0) {
    return artifact;
  }
  return null;
}

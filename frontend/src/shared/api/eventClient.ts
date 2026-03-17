import type { AgentEvent } from "../../types";
import { API_BASE_URL } from "./runClient";

type ConnectionState = "connecting" | "connected" | "reconnecting" | "closed";

type EventSourceFactory = (url: string) => EventSource;

type SubscribeAgentEventsOptions = {
  cursor?: number;
  retryDelayMs?: number;
  onEvent: (event: AgentEvent) => void;
  onConnectionStateChange?: (state: ConnectionState) => void;
  onError?: (error: Error) => void;
  eventSourceFactory?: EventSourceFactory;
};

type AgentEventSubscription = {
  close: () => void;
  getCursor: () => number;
};

function buildEventsUrl(cursor: number): string {
  const query = cursor > 0 ? `?cursor=${encodeURIComponent(String(cursor))}` : "";
  return `${API_BASE_URL}/api/events${query}`;
}

export function subscribeToAgentEvents(options: SubscribeAgentEventsOptions): AgentEventSubscription {
  const {
    onEvent,
    onConnectionStateChange,
    onError,
    eventSourceFactory = (url: string) => new EventSource(url),
    retryDelayMs = 1200,
  } = options;

  let isActive = true;
  let source: EventSource | null = null;
  let reconnectTimer: number | null = null;
  let cursor = options.cursor ?? 0;

  const clearReconnectTimer = () => {
    if (reconnectTimer !== null) {
      window.clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  };

  const connect = () => {
    if (!isActive) {
      return;
    }

    onConnectionStateChange?.(cursor > 0 ? "reconnecting" : "connecting");
    source = eventSourceFactory(buildEventsUrl(cursor));

    source.addEventListener("agent-event", (message) => {
      try {
        const payload = JSON.parse((message as MessageEvent<string>).data) as AgentEvent;
        if (typeof payload.sequence === "number") {
          cursor = Math.max(cursor, payload.sequence);
        }
        onEvent(payload);
        onConnectionStateChange?.("connected");
      } catch {
        onError?.(new Error("Unable to parse stream event payload."));
      }
    });

    source.onerror = () => {
      if (!isActive) {
        return;
      }
      onConnectionStateChange?.("reconnecting");
      onError?.(new Error("Live event stream disconnected. Reconnecting..."));
      source?.close();
      source = null;
      clearReconnectTimer();
      reconnectTimer = window.setTimeout(connect, retryDelayMs);
    };
  };

  connect();

  return {
    close: () => {
      isActive = false;
      clearReconnectTimer();
      source?.close();
      source = null;
      onConnectionStateChange?.("closed");
    },
    getCursor: () => cursor,
  };
}

import { startTransition, useCallback, useEffect, useRef, useState } from "react";
import type { AgentEvent, StreamState } from "../../types";
import { subscribeToAgentEvents } from "../../shared/api/eventClient";
import { loadBackendSnapshot } from "../../shared/api/runClient";

type StreamCallbacks = {
  hydrateSnapshot: (snapshot: StreamState) => void;
  receiveEvents: (events: AgentEvent[]) => void;
};

type StreamConnectionState = {
  connectionLabel: string;
  connectionError: string | null;
  clearConnectionError: () => void;
};

function findLastSequence(events: Array<{ sequence?: number }>): number {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const sequence = events[index]?.sequence;
    if (typeof sequence === "number") {
      return sequence;
    }
  }
  return 0;
}

/**
 * Subscribes to the backend snapshot + SSE stream lifecycle.
 *
 * The hook batches bursty SSE traffic into timed commits, reducing render
 * pressure while preserving event order guarantees.
 */
export function useLiveEventStream({ hydrateSnapshot, receiveEvents }: StreamCallbacks): StreamConnectionState {
  const [connectionLabel, setConnectionLabel] = useState("Connecting");
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const pendingEventsRef = useRef<AgentEvent[]>([]);
  const flushTimerRef = useRef<number | null>(null);

  const flushPendingEvents = useEventCallback(() => {
    flushTimerRef.current = null;
    if (pendingEventsRef.current.length === 0) {
      return;
    }
    const batch = pendingEventsRef.current;
    pendingEventsRef.current = [];
    startTransition(() => {
      receiveEvents(batch);
    });
  });

  const queueEvent = useEventCallback((event: AgentEvent) => {
    pendingEventsRef.current.push(event);
    if (flushTimerRef.current === null) {
      // Coalesce frequent SSE packets into fewer state writes.
      flushTimerRef.current = window.setTimeout(flushPendingEvents, 32);
    }
  });

  const handleConnectionState = useEventCallback((nextState: "connecting" | "connected" | "reconnecting" | "closed") => {
    if (nextState === "connected") {
      setConnectionLabel("Live backend stream");
      return;
    }
    if (nextState === "reconnecting") {
      setConnectionLabel("Reconnecting stream");
      return;
    }
    if (nextState === "connecting") {
      setConnectionLabel("Connecting");
      return;
    }
    setConnectionLabel("Disconnected");
  });

  const handleStreamError = useEventCallback((error: Error) => {
    setConnectionError(error.message);
  });

  useEffect(() => {
    let cancelled = false;
    let unsubscribe: (() => void) | null = null;

    async function connect() {
      try {
        const snapshot = await loadBackendSnapshot();
        if (cancelled) {
          return;
        }
        hydrateSnapshot(snapshot);
        setConnectionError(null);
        setConnectionLabel(snapshot.run ? "Live backend stream" : "Connected");

        const cursor = findLastSequence(snapshot.events);
        const subscription = subscribeToAgentEvents({
          cursor,
          onEvent: queueEvent,
          onConnectionStateChange: handleConnectionState,
          onError: handleStreamError,
        });
        unsubscribe = subscription.close;
      } catch (error) {
        if (cancelled) {
          return;
        }
        setConnectionLabel("Backend offline");
        setConnectionError(error instanceof Error ? error.message : "Unable to connect to the backend stream.");
      }
    }

    void connect();

    return () => {
      cancelled = true;
      if (flushTimerRef.current !== null) {
        window.clearTimeout(flushTimerRef.current);
        flushTimerRef.current = null;
      }
      pendingEventsRef.current = [];
      unsubscribe?.();
    };
  }, [handleConnectionState, handleStreamError, hydrateSnapshot, queueEvent]);

  return {
    connectionLabel,
    connectionError,
    clearConnectionError: () => setConnectionError(null),
  };
}

/**
 * Stable callback wrapper that always invokes the latest closure.
 *
 * This mirrors the core ergonomics of `useEffectEvent` for environments where
 * that API is not yet available.
 */
function useEventCallback<Args extends unknown[], Return>(
  callback: (...args: Args) => Return,
): (...args: Args) => Return {
  const callbackRef = useRef(callback);
  callbackRef.current = callback;
  return useCallback((...args: Args) => callbackRef.current(...args), []);
}

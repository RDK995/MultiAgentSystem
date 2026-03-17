import { useCallback, useReducer } from "react";
import type { AgentEvent, StreamState } from "../../types";
import { createInitialEventStoreState, eventReducer } from "./eventReducer";

export function useEventStore(initialState?: StreamState) {
  const baseState = createInitialEventStoreState();
  const [state, dispatch] = useReducer(
    eventReducer,
    initialState ? { ...baseState, ...initialState } : baseState,
  );
  const hydrateSnapshot = useCallback(
    (snapshot: StreamState) => dispatch({ type: "snapshot/hydrated", payload: snapshot }),
    [],
  );
  const receiveEvent = useCallback(
    (event: AgentEvent) => dispatch({ type: "event/received", payload: event }),
    [],
  );
  const receiveEvents = useCallback(
    (events: AgentEvent[]) => dispatch({ type: "events/received", payload: events }),
    [],
  );

  return {
    state,
    hydrateSnapshot,
    receiveEvent,
    receiveEvents,
  };
}

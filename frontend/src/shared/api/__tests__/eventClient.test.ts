import { describe, expect, it, vi } from "vitest";

import { subscribeToAgentEvents } from "../eventClient";

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  url: string;
  onerror: (() => void) | null = null;
  private listeners = new Map<string, Array<(message: MessageEvent<string>) => void>>();

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: (message: MessageEvent<string>) => void) {
    const current = this.listeners.get(type) ?? [];
    current.push(listener);
    this.listeners.set(type, current);
  }

  emit(type: string, data: object) {
    const listeners = this.listeners.get(type) ?? [];
    const message = { data: JSON.stringify(data) } as MessageEvent<string>;
    listeners.forEach((listener) => listener(message));
  }

  close() {
    return;
  }
}

describe("eventClient", () => {
  it("reconnects using latest cursor sequence", () => {
    vi.useFakeTimers();
    FakeEventSource.instances = [];

    const received: number[] = [];
    const subscription = subscribeToAgentEvents({
      cursor: 4,
      retryDelayMs: 10,
      eventSourceFactory: (url) => new FakeEventSource(url) as unknown as EventSource,
      onEvent: (event) => {
        if (typeof event.sequence === "number") {
          received.push(event.sequence);
        }
      },
      onError: () => {},
    });

    expect(FakeEventSource.instances[0]?.url).toContain("cursor=4");

    FakeEventSource.instances[0]?.emit("agent-event", {
      id: "event_5",
      sequence: 5,
      runId: "run_1",
      agentId: "orchestrator",
      type: "agent.message",
      title: "msg",
      summary: "msg",
      createdAt: "2026-03-17T00:00:00Z",
      status: "running",
    });
    expect(received).toEqual([5]);

    FakeEventSource.instances[0]?.onerror?.();
    vi.advanceTimersByTime(10);

    expect(FakeEventSource.instances[1]?.url).toContain("cursor=5");
    subscription.close();
    vi.useRealTimers();
  });
});

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "../App";

const { startBackendRunMock } = vi.hoisted(() => ({
  startBackendRunMock: vi.fn(async () => {}),
}));

vi.mock("../shared/api/runClient", () => {
  return {
    API_BASE_URL: "http://127.0.0.1:8008",
    loadBackendSnapshot: async () => ({
      run: null,
      agents: [],
      events: [],
      running: false,
    }),
    startBackendRun: startBackendRunMock,
    stopBackendRun: vi.fn(async () => {}),
  };
});

vi.mock("../shared/api/eventClient", () => {
  return {
    subscribeToAgentEvents: vi.fn(() => ({
      close: () => {},
      getCursor: () => 0,
    })),
  };
});

afterEach(() => {
  cleanup();
  startBackendRunMock.mockClear();
});

describe("App", () => {
  it("renders the main dashboard sections", async () => {
    render(<App />);

    expect(await screen.findByText("Resell Intelligence Console")).toBeInTheDocument();
    expect(screen.getByText("Current run")).toBeInTheDocument();
    expect(screen.getByText("Agents")).toBeInTheDocument();
    expect(screen.getByText("Profitable items")).toBeInTheDocument();
  });

  it("sends configured run values when starting a run", async () => {
    render(<App />);

    fireEvent.change(screen.getAllByLabelText("Source concurrency")[0], { target: { value: "3" } });
    fireEvent.change(screen.getAllByLabelText("Profitability concurrency")[0], { target: { value: "11" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Start run" })[0]);

    await waitFor(() => {
      expect(startBackendRunMock).toHaveBeenCalledWith({
        sourceConcurrency: 3,
        profitabilityConcurrency: 11,
      });
    });
  });
});

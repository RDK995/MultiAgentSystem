import { beforeEach, describe, expect, it, vi } from "vitest";

import { startBackendRun } from "../runClient";

describe("runClient", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("posts configured run values to the start endpoint", async () => {
    const fetchMock = vi.fn(async () => ({ ok: true })) as unknown as typeof fetch;
    vi.stubGlobal("fetch", fetchMock);

    await startBackendRun({
      sourceConcurrency: 5,
      profitabilityConcurrency: 12,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/runs/start"),
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_concurrency: 5,
          profitability_concurrency: 12,
        }),
      }),
    );
  });
});

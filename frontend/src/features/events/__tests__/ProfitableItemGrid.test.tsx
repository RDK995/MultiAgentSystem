import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ProfitableItemGrid } from "../ProfitableItemGrid";

describe("ProfitableItemGrid", () => {
  it("virtualizes large result sets by rendering a bounded subset of cards", () => {
    const items = Array.from({ length: 200 }, (_, index) => ({
      title: `Item ${index + 1}`,
      url: `https://items/${index + 1}`,
      profitGbp: 100 - index,
      marginPercent: 20,
    }));

    render(<ProfitableItemGrid items={items} />);

    const links = screen.getAllByRole("link", { name: "View source item" });
    expect(links.length).toBeGreaterThan(0);
    expect(links.length).toBeLessThan(items.length);
  });
});

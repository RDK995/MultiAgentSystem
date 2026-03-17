import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ReportLink } from "../ReportLink";

describe("ReportLink", () => {
  it("renders fallback text when artifact path is missing", () => {
    render(<ReportLink artifactPath={null} />);

    expect(screen.getByText("Report link appears after generation.")).toBeInTheDocument();
  });

  it("renders encoded artifact link when path is provided", () => {
    render(<ReportLink artifactPath="reports/demo report.html" />);

    const link = screen.getByRole("link", { name: "Open full analyzed-items report" });
    expect(link).toBeInTheDocument();
    expect(link.getAttribute("href")).toContain("reports%2Fdemo%20report.html");
  });
});

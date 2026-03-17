import type { AgentEvent } from "../../types";

export type TopItem = {
  title: string;
  profitGbp: number;
  marginPercent: number;
  url: string;
};

export function findTopProfitableItems(events: AgentEvent[]): TopItem[] {
  const byUrl = new Map<string, TopItem>();

  for (let index = events.length - 1; index >= 0; index -= 1) {
    const liveTitle = events[index]?.metadata?.profitableItemTitle;
    const liveUrl = events[index]?.metadata?.profitableItemUrl;
    const liveProfit = events[index]?.metadata?.profitableItemProfitGbp;
    const liveMargin = events[index]?.metadata?.profitableItemMarginPercent;

    if (
      typeof liveTitle === "string" &&
      typeof liveUrl === "string" &&
      typeof liveProfit === "number" &&
      typeof liveMargin === "number" &&
      liveProfit > 0 &&
      !byUrl.has(liveUrl)
    ) {
      byUrl.set(liveUrl, {
        title: liveTitle,
        profitGbp: liveProfit,
        marginPercent: liveMargin,
        url: liveUrl,
      });
    }

    const candidate = events[index]?.metadata?.topItems;
    if (!Array.isArray(candidate)) {
      continue;
    }

    for (const item of candidate) {
      const url = typeof item.url === "string" ? item.url : "#";
      if (byUrl.has(url)) {
        continue;
      }
      const profit = typeof item.profitGbp === "number" ? item.profitGbp : 0;
      if (profit <= 0) {
        continue;
      }
      byUrl.set(url, {
        title: typeof item.title === "string" ? item.title : "Untitled item",
        profitGbp: profit,
        marginPercent: typeof item.marginPercent === "number" ? item.marginPercent : 0,
        url,
      });
    }
  }

  return Array.from(byUrl.values()).sort((left, right) => right.profitGbp - left.profitGbp);
}

export function findLatestReportArtifactPath(events: AgentEvent[]): string | null {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const event = events[index];
    if (!event || event.agentId !== "report") {
      continue;
    }
    const artifact = event.metadata?.artifact;
    if (typeof artifact === "string" && artifact.length > 0) {
      return artifact;
    }
  }
  return null;
}

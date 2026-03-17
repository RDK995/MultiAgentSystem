import { useEffect, useMemo, useState } from "react";
import type { TopItem } from "./selectors";

const ROW_HEIGHT = 156;
const GRID_HEIGHT = 420;
const OVERSCAN_ROWS = 2;

type ProfitableItemGridProps = {
  items: TopItem[];
};

export function ProfitableItemGrid({ items }: ProfitableItemGridProps) {
  const [columns, setColumns] = useState(() => getColumns(window.innerWidth));
  const [scrollTop, setScrollTop] = useState(0);

  useEffect(() => {
    const onResize = () => setColumns(getColumns(window.innerWidth));
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const rowCount = Math.ceil(items.length / columns);
  const totalHeight = rowCount * ROW_HEIGHT;
  const startRow = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - OVERSCAN_ROWS);
  const visibleRows = Math.ceil(GRID_HEIGHT / ROW_HEIGHT) + OVERSCAN_ROWS * 2;
  const endRow = Math.min(rowCount, startRow + visibleRows);

  const visibleItems = useMemo(() => {
    const rows: Array<{ rowIndex: number; rowItems: TopItem[] }> = [];
    for (let rowIndex = startRow; rowIndex < endRow; rowIndex += 1) {
      const rowItems = items.slice(rowIndex * columns, rowIndex * columns + columns);
      rows.push({ rowIndex, rowItems });
    }
    return rows;
  }, [columns, endRow, items, startRow]);

  return (
    <div
      className="recent-feed-virtualized"
      style={{ height: `${GRID_HEIGHT}px` }}
      onScroll={(event) => setScrollTop(event.currentTarget.scrollTop)}
      data-testid="virtualized-profitable-items"
    >
      <div className="recent-feed-inner" style={{ height: `${totalHeight}px` }}>
        {visibleItems.map(({ rowIndex, rowItems }) => (
          <div
            className="recent-feed-row"
            key={rowIndex}
            style={{
              height: `${ROW_HEIGHT}px`,
              transform: `translateY(${rowIndex * ROW_HEIGHT}px)`,
              gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`,
            }}
          >
            {rowItems.map((item) => (
              <article className="item-card" key={`${item.title}-${item.url}`}>
                <div className="item-card-header">
                  <strong>{item.title}</strong>
                  <span className="item-profit-wrap">
                    <span className="item-profit-label">Profit</span>
                    <span className="item-profit">GBP {item.profitGbp.toFixed(2)}</span>
                  </span>
                </div>
                <div className="item-card-meta">
                  <span>{item.marginPercent.toFixed(2)}% margin</span>
                </div>
                <a className="item-link" href={item.url} target="_blank" rel="noreferrer">
                  View source item
                </a>
              </article>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

function getColumns(width: number): number {
  if (width < 760) {
    return 1;
  }
  if (width < 1120) {
    return 2;
  }
  return 4;
}

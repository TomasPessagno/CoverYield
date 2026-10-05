"use client";

import { useState, type ReactNode } from "react";

export type Column<T> = {
  key: string;
  header: string;
  /** Tooltip explaining the column */
  hint?: string;
  value: (row: T) => number | string | null;
  render?: (row: T) => ReactNode;
  align?: "left" | "right";
  /** Background tint 0..1 for heat-shaded cells */
  heat?: (row: T) => number;
  /** Set false for columns like links that make no sense to sort */
  sortable?: boolean;
};

type Sort = { key: string; dir: "asc" | "desc" } | null;

/** A dense, sortable table. Click a header to sort; click again to flip. */
export function DataTable<T>({
  rows,
  columns,
  rowKey,
  initialSort = null,
  maxHeight = 560,
}: {
  rows: T[];
  columns: Column<T>[];
  rowKey: (row: T) => string;
  initialSort?: Sort;
  maxHeight?: number;
}) {
  const [sort, setSort] = useState<Sort>(initialSort);

  const sorted = (() => {
    if (!sort) return rows;
    const col = columns.find((c) => c.key === sort.key);
    if (!col) return rows;
    const factor = sort.dir === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => {
      const va = col.value(a);
      const vb = col.value(b);
      if (va === vb) return 0;
      if (va === null) return 1;
      if (vb === null) return -1;
      return (va < vb ? -1 : 1) * factor;
    });
  })();

  function toggle(key: string) {
    setSort((s) =>
      s?.key === key ? { key, dir: s.dir === "desc" ? "asc" : "desc" } : { key, dir: "desc" },
    );
  }

  return (
    <div className="overflow-auto" style={{ maxHeight }}>
      <table className="w-full border-collapse text-sm">
        <thead className="sticky top-0 z-10 bg-panel">
          <tr>
            {columns.map((c) => {
              const active = sort?.key === c.key;
              return (
                <th
                  key={c.key}
                  scope="col"
                  title={c.hint}
                  aria-sort={active ? (sort.dir === "asc" ? "ascending" : "descending") : "none"}
                  className={`border-b border-border px-2.5 py-2 font-normal whitespace-nowrap ${
                    c.align === "left" ? "text-left" : "text-right"
                  }`}
                >
                  {c.sortable === false ? (
                    <span className="sr-only">{c.hint ?? c.key}</span>
                  ) : (
                  <button
                    type="button"
                    onClick={() => toggle(c.key)}
                    className={`label inline-flex items-center gap-1 hover:text-text-2 ${
                      active ? "text-text" : ""
                    } ${c.hint ? "decoration-dotted underline-offset-4 hover:underline" : ""}`}
                  >
                    {c.header}
                    <span className="w-2 text-[9px]">
                      {active ? (sort.dir === "asc" ? "▲" : "▼") : ""}
                    </span>
                  </button>
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr key={rowKey(row)} className="border-b border-grid hover:bg-panel-2">
              {columns.map((c) => {
                const h = c.heat?.(row);
                return (
                  <td
                    key={c.key}
                    className={`num px-2.5 py-1.5 whitespace-nowrap ${
                      c.align === "left" ? "text-left" : "text-right"
                    }`}
                    style={
                      h !== undefined && h > 0
                        ? { backgroundColor: `rgb(var(--heat-rgb) / ${(0.02 + h * 0.11).toFixed(3)})` }
                        : undefined
                    }
                  >
                    {c.render ? c.render(row) : (c.value(row) ?? "—")}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

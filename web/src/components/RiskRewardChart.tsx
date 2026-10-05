"use client";

import { useEffect, useRef, useState, type MouseEvent } from "react";

import type { Contract } from "@/lib/api";
import { fmtDate, fmtInt, fmtPct, fmtUsd } from "@/lib/format";

// Sequential ramp (one hue, dim -> bright on the dark surface) for implied volatility.
const IV_RAMP = ["#6e4610", "#9a610f", "#c87d10", "#f29a24", "#ffc06a"];
const HEIGHT = 380;
const M = { top: 22, right: 24, bottom: 40, left: 52 };

function lerpColor(a: string, b: string, t: number): string {
  const pa = [1, 3, 5].map((i) => parseInt(a.slice(i, i + 2), 16));
  const pb = [1, 3, 5].map((i) => parseInt(b.slice(i, i + 2), 16));
  return `rgb(${pa.map((v, i) => Math.round(v + (pb[i] - v) * t)).join(",")})`;
}

function rampColor(t: number): string {
  const x = Math.min(Math.max(t, 0), 1) * (IV_RAMP.length - 1);
  const i = Math.min(Math.floor(x), IV_RAMP.length - 2);
  return lerpColor(IV_RAMP[i], IV_RAMP[i + 1], x - i);
}

function niceTicks(lo: number, hi: number, count = 5): number[] {
  const span = hi - lo || 1;
  const raw = span / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => span / s <= count) ?? mag * 10;
  const ticks: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) ticks.push(+v.toFixed(10));
  return ticks;
}

function extent(values: number[], pad = 0.06): [number, number] {
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const p = (hi - lo || Math.abs(hi) || 1) * pad;
  return [lo - p, hi + p];
}

/**
 * Distance to strike (safety) vs annualized return (reward), one dot per
 * contract. Dot size = open interest, color = implied volatility.
 */
export function RiskRewardChart({ contracts }: { contracts: Contract[] }) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(800);
  const [hover, setHover] = useState<number | null>(null);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => setWidth(Math.max(320, entry.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  if (contracts.length === 0) return null;

  const [x0, x1] = extent(contracts.map((c) => c.distance_to_strike_pct));
  const [y0raw, y1] = extent(contracts.map((c) => c.annualized_return_pct));
  const y0 = Math.min(0, y0raw);
  const ivs = contracts.map((c) => c.iv_pct);
  const ivLo = Math.min(...ivs);
  const ivHi = Math.max(...ivs);
  const oiMax = Math.max(1, ...contracts.map((c) => c.open_interest));

  const iw = width - M.left - M.right;
  const ih = HEIGHT - M.top - M.bottom;
  const sx = (v: number) => M.left + ((v - x0) / (x1 - x0)) * iw;
  const sy = (v: number) => M.top + ih - ((v - y0) / (y1 - y0)) * ih;
  const sr = (oi: number) => 5 + Math.sqrt(oi / oiMax) * 12;
  const sc = (iv: number) => rampColor(ivHi > ivLo ? (iv - ivLo) / (ivHi - ivLo) : 0.5);

  // Draw big dots first so small ones stay visible on top.
  const order = contracts
    .map((_, i) => i)
    .sort((a, b) => contracts[b].open_interest - contracts[a].open_interest);

  function onMove(e: MouseEvent<SVGSVGElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    let best: number | null = null;
    let bestD = 18 ** 2; // hit radius bigger than the dots
    for (let i = 0; i < contracts.length; i++) {
      const c = contracts[i];
      const d = (sx(c.distance_to_strike_pct) - mx) ** 2 + (sy(c.annualized_return_pct) - my) ** 2;
      if (d < bestD) {
        bestD = d;
        best = i;
      }
    }
    setHover(best);
  }

  const h = hover !== null ? contracts[hover] : null;
  const tipLeft = h ? sx(h.distance_to_strike_pct) : 0;
  const tipTop = h ? sy(h.annualized_return_pct) : 0;

  return (
    <div ref={wrapRef} className="relative">
      <svg
        width={width}
        height={HEIGHT}
        role="img"
        aria-label="Scatter of distance to strike versus annualized return"
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
        className="block"
      >
        {niceTicks(y0, y1).map((t) => (
          <g key={`y${t}`}>
            <line x1={M.left} x2={width - M.right} y1={sy(t)} y2={sy(t)} stroke="var(--grid)" />
            <text x={M.left - 8} y={sy(t)} dy="0.32em" textAnchor="end" className="num fill-muted text-[10px]">
              {t}%
            </text>
          </g>
        ))}
        {niceTicks(x0, x1).map((t) => (
          <g key={`x${t}`}>
            <line x1={sx(t)} x2={sx(t)} y1={M.top} y2={M.top + ih} stroke="var(--grid)" />
            <text x={sx(t)} y={M.top + ih + 16} textAnchor="middle" className="num fill-muted text-[10px]">
              {t}%
            </text>
          </g>
        ))}
        <line x1={M.left} x2={width - M.right} y1={sy(0)} y2={sy(0)} stroke="#383c43" />
        <text x={M.left + iw / 2} y={HEIGHT - 6} textAnchor="middle" className="label fill-muted">
          Distance to strike (safety) →
        </text>
        <text
          transform={`translate(13 ${M.top + ih / 2}) rotate(-90)`}
          textAnchor="middle"
          className="label fill-muted"
        >
          Annualized return (reward) →
        </text>

        {order.map((i) => {
          const c = contracts[i];
          return (
            <circle
              key={c.contract_symbol}
              cx={sx(c.distance_to_strike_pct)}
              cy={sy(c.annualized_return_pct)}
              r={sr(c.open_interest)}
              fill={sc(c.iv_pct)}
              fillOpacity={hover === null || hover === i ? 0.9 : 0.35}
              stroke="var(--panel)"
              strokeWidth={2}
            />
          );
        })}
        {h && (
          <circle
            cx={sx(h.distance_to_strike_pct)}
            cy={sy(h.annualized_return_pct)}
            r={sr(h.open_interest) + 3}
            fill="none"
            stroke="var(--text)"
            strokeWidth={1.5}
          />
        )}
      </svg>

      {h && (
        <div
          className="pointer-events-none absolute z-10 w-56 rounded-sm border border-border bg-panel-2 px-3 py-2 text-xs shadow-xl shadow-black/50"
          style={{
            left: Math.min(tipLeft + 14, width - 236),
            top: Math.max(tipTop - 20, 0),
          }}
        >
          <div className="num mb-1.5 flex justify-between text-text">
            <span>
              {h.ticker} {fmtUsd(h.strike)}C
            </span>
            <span className="text-muted">{fmtDate(h.expiration)}</span>
          </div>
          {(
            [
              ["Distance", fmtPct(h.distance_to_strike_pct)],
              ["Annualized", fmtPct(h.annualized_return_pct)],
              ["Static", fmtPct(h.static_return_pct)],
              ["Bid", fmtUsd(h.bid)],
              ["IV", fmtPct(h.iv_pct, 1)],
              ["Open interest", fmtInt(h.open_interest)],
            ] as const
          ).map(([k, v]) => (
            <div key={k} className="flex justify-between gap-4">
              <span className="text-muted">{k}</span>
              <span className="num text-text">{v}</span>
            </div>
          ))}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 px-1 pt-2 text-xs text-muted">
        <span className="flex items-center gap-2">
          <span className="label">IV</span>
          <span className="num">{fmtPct(ivLo, 0)}</span>
          <span
            className="h-2 w-28 rounded-[1px]"
            style={{ background: `linear-gradient(to right, ${IV_RAMP.join(",")})` }}
          />
          <span className="num">{fmtPct(ivHi, 0)}</span>
        </span>
        <span className="flex items-center gap-2">
          <span className="label">Size</span>
          <span>open interest</span>
        </span>
      </div>
    </div>
  );
}

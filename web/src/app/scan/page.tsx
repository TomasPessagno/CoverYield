"use client";

import { useEffect, useState } from "react";

import { DataTable, type Column } from "@/components/DataTable";
import { Button, ErrorNote, Field, NumberInput, Panel, SliderInput } from "@/components/fields";
import {
  api,
  errorMessage,
  type Opportunity,
  type OpportunitiesResponse,
  type UniverseTicker,
  type Weights,
} from "@/lib/api";
import { YahooLink } from "@/components/YahooLink";
import { fmtDate, fmtInt, fmtPct, fmtTime, fmtUsd } from "@/lib/format";

const CONCURRENCY = 4;
const DEFAULT_WEIGHTS: Weights = { yield: 40, assign: 30, liq: 15, vol: 10, div: 5 };
const WEIGHT_LABELS: [keyof Weights, string, string][] = [
  ["yield", "Yield", "Premium relative to the stock price (actual and annualized)"],
  ["assign", "Assignment risk", "Lower probability of being called away scores higher"],
  ["liq", "Liquidity", "Open interest, volume and a tight bid-ask spread"],
  ["vol", "Volatility", "Rewards moderate IV (~30%), penalizes extremes"],
  ["div", "Dividend", "Placeholder: neutral for every contract today"],
];

type Progress = { done: number; total: number; current: string; failed: string[] };
type Result = { key: string; data?: OpportunitiesResponse; error?: string };

export default function ScanPage() {
  const [universe, setUniverse] = useState<UniverseTicker[]>([]);
  const [universeSize, setUniverseSize] = useState(20);
  const [minReturn, setMinReturn] = useState(1);
  const [maxDte, setMaxDte] = useState(45);
  const [minOtm, setMinOtm] = useState(2);
  const [topN, setTopN] = useState(50);
  const [weights, setWeights] = useState<Weights>(DEFAULT_WEIGHTS);
  const [yieldActual, setYieldActual] = useState(70);

  const [progress, setProgress] = useState<Progress | null>(null);
  const [scanned, setScanned] = useState<string[] | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [lastData, setLastData] = useState<OpportunitiesResponse | null>(null);

  useEffect(() => {
    api.universe().then(setUniverse).catch(() => {});
  }, []);

  const running = progress !== null && progress.done < progress.total;

  async function runScan() {
    const tickers = universe.slice(0, universeSize).map((t) => t.symbol);
    if (tickers.length === 0) return;
    const failed: string[] = [];
    let done = 0;
    setProgress({ done: 0, total: tickers.length, current: tickers[0], failed });
    const queue = [...tickers];
    const worker = async () => {
      for (let t = queue.shift(); t; t = queue.shift()) {
        setProgress((p) => p && { ...p, current: t });
        try {
          const r = await api.scanTicker(t);
          if (!r.ok) failed.push(t);
        } catch {
          failed.push(t);
        }
        done += 1;
        setProgress((p) => p && { ...p, done, failed: [...failed] });
      }
    };
    await Promise.all(Array.from({ length: CONCURRENCY }, worker));
    setScanned(tickers);
  }

  // Goals and weights re-rank the scanned contracts live (the backend caches the chains).
  const request = scanned && {
    tickers: scanned,
    min_static_return_pct: minReturn,
    max_days_to_expiry: maxDte,
    min_otm_pct: minOtm,
    weights,
    yield_actual_frac: yieldActual / 100,
    top_n: topN,
  };
  const key = request ? JSON.stringify(request) : null;

  useEffect(() => {
    if (!key) return;
    const ctrl = new AbortController();
    const timer = setTimeout(() => {
      api
        .opportunities(JSON.parse(key), ctrl.signal)
        .then((data) => {
          setResult({ key, data });
          setLastData(data);
        })
        .catch((e: unknown) => {
          if (!ctrl.signal.aborted) setResult({ key, error: errorMessage(e) });
        });
    }, 250);
    return () => {
      clearTimeout(timer);
      ctrl.abort();
    };
  }, [key]);

  const error = result?.key === key ? result.error : undefined;
  const data = error ? null : (result?.key === key ? result.data : lastData) ?? null;
  const ranking = key !== null && result?.key !== key;
  const weightTotal = Object.values(weights).reduce((s, w) => s + w, 0) || 1;

  return (
    <div className="flex flex-col gap-4">
      <p className="max-w-3xl text-sm leading-relaxed text-text-2">
        Set your goals, scan a universe of liquid stocks and ETFs, and every covered-call contract
        gets an <span className="text-text">Opportunity Score</span> from 0 to 100. Goals and
        weights re-rank the results instantly once the scan is done.
      </p>

      <Panel title="Goals">
        <div className="grid grid-cols-1 gap-x-6 gap-y-3 px-4 py-3 sm:grid-cols-3">
          <Field label="Min return (this trade)" hint="Premium / stock price over the contract's life: real cash, not a projection">
            <SliderInput value={minReturn} onChange={setMinReturn} min={0} max={10} step={0.25} format={(v) => fmtPct(v, 2)} />
          </Field>
          <Field label="Max days to expiry">
            <SliderInput value={maxDte} onChange={setMaxDte} min={1} max={120} format={(v) => `${v}d`} />
          </Field>
          <Field label="Min distance OTM" hint="How far above today's price the strike must be">
            <SliderInput value={minOtm} onChange={setMinOtm} min={0} max={30} step={0.5} format={(v) => fmtPct(v, 1)} />
          </Field>
        </div>
        <details className="group border-t border-border">
          <summary className="label flex cursor-pointer list-none items-center gap-2 px-4 py-2.5 hover:text-text-2">
            <span className="transition-transform group-open:rotate-90">▸</span>
            Scoring weights
            <span className="num text-muted">
              {WEIGHT_LABELS.map(([k]) => Math.round((weights[k] / weightTotal) * 100)).join(" / ")}
            </span>
          </summary>
          <div className="grid grid-cols-1 gap-x-6 gap-y-3 px-4 pb-4 sm:grid-cols-2 lg:grid-cols-3">
            {WEIGHT_LABELS.map(([k, label, hint]) => (
              <Field key={k} label={label} hint={hint}>
                <SliderInput
                  value={weights[k]}
                  onChange={(v) => setWeights((w) => ({ ...w, [k]: v }))}
                  min={0}
                  max={100}
                />
              </Field>
            ))}
            <Field label="Yield: actual vs annualized" hint="How the yield score is built: share of actual return vs annualized rate">
              <SliderInput value={yieldActual} onChange={setYieldActual} min={0} max={100} step={5} format={(v) => `${v}%`} />
            </Field>
            <div className="flex items-end">
              <Button variant="ghost" onClick={() => { setWeights(DEFAULT_WEIGHTS); setYieldActual(70); }}>
                Reset weights
              </Button>
            </div>
          </div>
        </details>
      </Panel>

      <div className="flex flex-wrap items-end gap-3">
        <Field label="Universe size" className="w-40">
          <NumberInput value={universeSize} onChange={(v) => setUniverseSize(Math.round(v))} min={1} max={universe.length || 57} />
        </Field>
        <Field label="Show top" className="w-32">
          <NumberInput value={topN} onChange={(v) => setTopN(Math.round(v))} min={1} max={500} step={10} />
        </Field>
        <Button onClick={runScan} disabled={running || universe.length === 0}>
          {running ? "Scanning…" : `Scan ${Math.min(universeSize, universe.length || universeSize)} tickers`}
        </Button>
        {progress && (
          <div className="flex min-w-60 flex-1 flex-col gap-1.5">
            <div className="h-1 w-full overflow-hidden rounded-full bg-border">
              <div
                className="h-full bg-accent transition-[width] duration-300"
                style={{ width: `${(progress.done / progress.total) * 100}%` }}
              />
            </div>
            <span className="num text-xs text-muted">
              {running
                ? `Scanning ${progress.current} (${progress.done}/${progress.total})`
                : `Scanned ${progress.total} tickers${progress.failed.length ? ` · no data for ${progress.failed.join(", ")}` : ""}`}
            </span>
          </div>
        )}
      </div>

      {error && <ErrorNote>{error}</ErrorNote>}

      {data ? (
        <Panel
          title="Ranked opportunities"
          right={
            <span className="num text-xs text-muted">
              {ranking
                ? "re-ranking…"
                : `top ${data.results.length} of ${fmtInt(data.matched)} matches · ${data.scanned} tickers${
                    data.oldest_data_at ? ` · data as of ${fmtTime(data.oldest_data_at)}` : ""
                  }`}
            </span>
          }
        >
          {data.results.length > 0 ? (
            <DataTable
              rows={data.results}
              columns={OPPORTUNITY_COLUMNS}
              rowKey={(o) => o.contract_symbol}
              initialSort={{ key: "score", dir: "desc" }}
              maxHeight={640}
            />
          ) : (
            <p className="px-4 py-8 text-center text-sm text-muted">
              Nothing matches these goals. Lower the minimum return, raise max days to expiry or
              lower the minimum distance OTM. Results update instantly.
            </p>
          )}
        </Panel>
      ) : (
        !progress && (
          <p className="label py-10 text-center">Set your goals and run a scan to rank opportunities.</p>
        )
      )}
    </div>
  );
}

function ScoreCell({ o }: { o: Opportunity }) {
  const breakdown = [
    `Yield ${o.score_yield.toFixed(0)}`,
    `Assignment ${o.score_assignment.toFixed(0)}`,
    `Liquidity ${o.score_liquidity.toFixed(0)}`,
    `Volatility ${o.score_volatility.toFixed(0)}`,
    `Dividend ${o.score_dividend.toFixed(0)}`,
  ].join(" · ");
  return (
    <span className="flex items-center justify-end gap-2" title={`Component scores (0-100): ${breakdown}`}>
      <span className="h-1.5 w-16 overflow-hidden rounded-full bg-border">
        <span className="block h-full bg-accent" style={{ width: `${o.score}%` }} />
      </span>
      <span className="w-6 text-text">{o.score.toFixed(0)}</span>
    </span>
  );
}

const OPPORTUNITY_COLUMNS: Column<Opportunity>[] = [
  {
    key: "score",
    header: "Score",
    hint: "Opportunity Score 0-100. Hover a score for its components",
    value: (o) => o.score,
    render: (o) => <ScoreCell o={o} />,
  },
  {
    key: "ticker",
    header: "Ticker",
    align: "left",
    value: (o) => o.ticker,
    render: (o) => <span className="font-medium text-text">{o.ticker}</span>,
  },
  { key: "price", header: "Price", value: (o) => o.price, render: (o) => fmtUsd(o.price) },
  { key: "strike", header: "Strike", value: (o) => o.strike, render: (o) => fmtUsd(o.strike) },
  { key: "dist", header: "Dist", hint: "Distance to strike", value: (o) => o.distance_to_strike_pct, render: (o) => fmtPct(o.distance_to_strike_pct, 1) },
  { key: "dte", header: "DTE", value: (o) => o.days_to_expiry },
  { key: "exp", header: "Expiry", value: (o) => o.expiration, render: (o) => fmtDate(o.expiration) },
  { key: "bid", header: "Premium", hint: "Bid", value: (o) => o.bid, render: (o) => fmtUsd(o.bid) },
  {
    key: "static",
    header: "Return",
    hint: "Actual return on this trade: bid / stock price",
    value: (o) => o.static_return_pct,
    render: (o) => fmtPct(o.static_return_pct),
    heat: (o) => Math.min(o.static_return_pct / 5, 1),
  },
  { key: "annual", header: "Annual", value: (o) => o.annualized_return_pct, render: (o) => fmtPct(o.annualized_return_pct, 1) },
  {
    key: "assign",
    header: "P(assign)",
    hint: "Black-Scholes call delta",
    value: (o) => o.assignment_prob ?? null,
    render: (o) => (o.assignment_prob == null ? "—" : fmtPct(o.assignment_prob * 100, 0)),
  },
  { key: "iv", header: "IV", value: (o) => o.iv_pct, render: (o) => fmtPct(o.iv_pct, 0) },
  { key: "oi", header: "OI", hint: "Open interest", value: (o) => o.open_interest, render: (o) => fmtInt(o.open_interest) },
  {
    key: "contract",
    header: "Contract",
    hint: "Open this exact contract on Yahoo Finance",
    sortable: false,
    value: () => null,
    render: (o) => <YahooLink contractSymbol={o.contract_symbol} />,
  },
];

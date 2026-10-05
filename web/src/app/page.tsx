"use client";

import { useEffect, useState } from "react";

import { DataTable, type Column } from "@/components/DataTable";
import {
  ErrorNote,
  Field,
  NumberInput,
  OptionalNumberInput,
  Panel,
  SliderInput,
} from "@/components/fields";
import { RiskRewardChart } from "@/components/RiskRewardChart";
import { TickerSearch } from "@/components/TickerSearch";
import { YahooLink } from "@/components/YahooLink";
import { api, errorMessage, type Contract, type ScreenerResponse, type UniverseTicker } from "@/lib/api";
import {
  fmtAgo,
  fmtDate,
  fmtInt,
  fmtPct,
  fmtSigned,
  fmtTime,
  fmtUsd,
  yahooQuoteUrl,
} from "@/lib/format";

const QUICK_PICKS = ["AAPL", "MSFT", "NVDA", "SPY", "KO", "JPM"];

type Result = { key: string; data?: ScreenerResponse; error?: string };

export default function ScreenerPage() {
  const [universe, setUniverse] = useState<UniverseTicker[]>([]);
  const [ticker, setTicker] = useState<string | null>(null);
  // Expiry window in days; null = no limit on that side.
  const [minDays, setMinDays] = useState<number | null>(null);
  const [maxDays, setMaxDays] = useState<number | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [lastData, setLastData] = useState<ScreenerResponse | null>(null);
  const [scanning, setScanning] = useState(false);
  const [scanError, setScanError] = useState<string | null>(null);
  // Ticks so "12 min ago" and the refresh countdown stay current.
  const [now, setNow] = useState(() => Date.now());

  // Client-side filters: applied instantly to the loaded chain, no refetch.
  const [minOffset, setMinOffset] = useState(0);
  const [maxOffset, setMaxOffset] = useState<number | null>(null); // null = no upper limit
  const [minStatic, setMinStatic] = useState(0);
  const [minAnnual, setMinAnnual] = useState(0);

  useEffect(() => {
    api.universe().then(setUniverse).catch(() => {});
    const timer = setInterval(() => setNow(Date.now()), 15_000);
    return () => clearInterval(timer);
  }, []);

  const swap = minDays !== null && maxDays !== null && minDays > maxDays;
  const lo = swap ? maxDays : minDays;
  const hi = swap ? minDays : maxDays;
  const key = ticker ? `${ticker}|${lo}|${hi}` : null;

  useEffect(() => {
    if (!ticker || !key) return;
    let live = true;
    const timer = setTimeout(() => {
      api
        .screener(ticker, lo, hi)
        .then((data) => {
          if (!live) return;
          setResult({ key, data });
          setLastData(data);
          setNow(Date.now());
        })
        .catch((e: unknown) => live && setResult({ key, error: errorMessage(e) }));
    }, 200);
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [key, ticker, lo, hi]);

  const loading = key !== null && result?.key !== key;
  const error = result?.key === key ? result.error : undefined;
  const data = error ? null : (result?.key === key ? result.data : lastData) ?? null;

  async function scanNow() {
    if (!ticker || !key) return;
    setScanning(true);
    setScanError(null);
    try {
      const fresh = await api.refresh(ticker, lo, hi);
      setResult({ key, data: fresh });
      setLastData(fresh);
    } catch (e) {
      setScanError(errorMessage(e));
    } finally {
      setScanning(false);
      setNow(Date.now());
    }
  }

  const contracts =
    data?.contracts.filter(
      (c) =>
        c.strike >= data.price + minOffset &&
        (maxOffset === null || c.strike <= data.price + maxOffset) &&
        c.static_return_pct >= minStatic &&
        c.annualized_return_pct >= minAnnual,
    ) ?? [];

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 items-end gap-3 sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)]">
        <Field label="Ticker">
          <TickerSearch universe={universe} onSubmit={setTicker} />
        </Field>
        <Field label="Min days to expiry" hint="Shortest expiry to include. Leave empty for no limit">
          <OptionalNumberInput value={minDays} onChange={setMinDays} min={0} suffix="d" placeholder="No min" />
        </Field>
        <Field label="Max days to expiry" hint="Longest expiry to include. Leave empty for no limit">
          <OptionalNumberInput value={maxDays} onChange={setMaxDays} min={0} suffix="d" placeholder="No max" />
        </Field>
      </div>

      {!ticker && <Intro onPick={setTicker} />}
      {error && <ErrorNote>{error}</ErrorNote>}
      {ticker && loading && !data && <p className="label py-10 text-center">Loading {ticker}…</p>}

      {data && (
        <>
          <QuoteHeader
            data={data}
            loading={loading}
            now={now}
            scanning={scanning}
            scanError={scanError}
            onScanNow={scanNow}
            summary={[
              expiryLabel(lo, hi),
              `strike +$${minOffset} to ${maxOffset === null ? "no max" : `+$${maxOffset}`}`,
              ...(minStatic > 0 ? [`static ≥ ${fmtPct(minStatic, 1)}`] : []),
              ...(minAnnual > 0 ? [`annual ≥ ${fmtPct(minAnnual, 0)}`] : []),
              `${contracts.length} contracts`,
            ].join(" · ")}
          />

          <Panel
            title="Filtered options chain"
            right={
              <span className="num text-xs text-muted">
                {contracts.length} of {data.contracts.length} contracts
              </span>
            }
          >
            <div className="grid grid-cols-1 gap-x-6 gap-y-3 border-b border-border px-4 py-3 sm:grid-cols-2 lg:grid-cols-4">
              <Field label="Min strike offset" hint="Strike at least this far above the stock price">
                <NumberInput value={minOffset} onChange={setMinOffset} step={1} suffix="$" />
              </Field>
              <Field label="Max strike offset" hint="Strike at most this far above the stock price. Leave empty for no limit">
                <OptionalNumberInput
                  value={maxOffset}
                  onChange={setMaxOffset}
                  min={0}
                  step={1}
                  suffix="$"
                  placeholder="No max"
                />
              </Field>
              <Field label="Min static return" hint="Premium / stock price">
                <SliderInput value={minStatic} onChange={setMinStatic} min={0} max={20} step={0.5} format={(v) => fmtPct(v, 1)} />
              </Field>
              <Field label="Min annualized return" hint="Static return x 365 / days to expiry">
                <SliderInput value={minAnnual} onChange={setMinAnnual} min={0} max={150} step={5} format={(v) => fmtPct(v, 0)} />
              </Field>
            </div>
            {contracts.length > 0 ? (
              <>
                <Stats contracts={contracts} />
                <DataTable
                  rows={contracts}
                  columns={screenerColumns(data.price)}
                  rowKey={(c) => c.contract_symbol}
                  initialSort={{ key: "dte", dir: "asc" }}
                />
              </>
            ) : (
              <p className="px-4 py-8 text-center text-sm text-muted">
                No contracts match these filters. Try lowering the minimums or raising the max strike offset.
              </p>
            )}
          </Panel>

          {contracts.length > 0 && (
            <Panel title="Risk vs reward">
              <div className="px-3 pt-3 pb-3">
                <RiskRewardChart contracts={contracts} />
              </div>
            </Panel>
          )}
        </>
      )}
    </div>
  );
}

function Intro({ onPick }: { onPick: (t: string) => void }) {
  return (
    <Panel>
      <div className="flex flex-col gap-4 px-5 py-6">
        <p className="max-w-2xl text-sm leading-relaxed text-text-2">
          Pick a stock to see every call option in your expiry window, with the return you&apos;d
          earn by selling it against shares you own, how far the stock can rise before they get
          called away, and the Black-Scholes probability that they will.
        </p>
        <div className="flex flex-wrap gap-2">
          {QUICK_PICKS.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => onPick(t)}
              className="num rounded-sm border border-border px-3 py-1.5 text-sm text-text-2 transition-colors hover:border-border-strong hover:text-text"
            >
              {t}
            </button>
          ))}
        </div>
      </div>
    </Panel>
  );
}

/** Stays pinned under the top bar while scrolling, with a one-line summary of the filters. */
function QuoteHeader({
  data,
  loading,
  summary,
  now,
  scanning,
  scanError,
  onScanNow,
}: {
  data: ScreenerResponse;
  loading: boolean;
  summary: string;
  now: number;
  scanning: boolean;
  scanError: string | null;
  onScanNow: () => void;
}) {
  const waitMs = data.next_refresh_at ? new Date(data.next_refresh_at).getTime() - now : 0;
  const coolingDown = waitMs > 0;
  const scanLabel = scanning
    ? "Scanning…"
    : coolingDown
      ? `Available in ${Math.max(1, Math.ceil(waitMs / 60_000))} min`
      : "Scan now";
  const scanHint = coolingDown
    ? `${data.ticker} was refreshed ${fmtAgo(data.as_of, now)}. To keep load on the data source low, each ticker can be refreshed once every 10 minutes; everyone sees the latest copy.`
    : `Fetch ${data.ticker}'s option chain live now`;
  const change = data.open_price > 0 ? data.price - data.open_price : null;
  const changePct = change !== null ? (change / data.open_price) * 100 : null;
  return (
    <div className="sticky top-12 z-20 -mx-4 flex flex-wrap items-baseline gap-x-6 gap-y-1 border-b border-border bg-bg/95 px-4 py-3 backdrop-blur sm:-mx-6 sm:px-6">
      <h1 className="text-2xl font-semibold tracking-tight">{data.ticker}</h1>
      <span className="num text-2xl">{fmtUsd(data.price)}</span>
      {change !== null && changePct !== null && (
        <span className={`num text-sm ${change >= 0 ? "text-up" : "text-down"}`}>
          {change >= 0 ? "▲" : "▼"} {fmtSigned(change)} ({fmtSigned(changePct)}%) today
        </span>
      )}
      <span className="num hidden text-xs text-muted sm:inline" title={new Date(data.as_of).toString()}>
        {loading ? "updating…" : `data as of ${fmtTime(data.as_of)} · ${fmtAgo(data.as_of, now)}`}
      </span>
      <button
        type="button"
        onClick={onScanNow}
        disabled={scanning || coolingDown}
        title={scanHint}
        className="h-7 rounded-sm border border-border px-3 text-xs text-text-2 transition-colors hover:border-border-strong hover:text-text disabled:cursor-not-allowed disabled:opacity-60"
      >
        {scanLabel}
      </button>
      {(data.stale || scanError) && (
        <span className="text-xs text-down">
          {scanError ?? "Live refresh failed, showing the last data"}
        </span>
      )}
      <span className="num ml-auto hidden text-xs text-muted md:inline">{summary}</span>
      <a
        href={yahooQuoteUrl(data.ticker)}
        target="_blank"
        rel="noreferrer"
        className="hidden text-xs text-muted hover:text-text sm:inline"
      >
        Yahoo ↗
      </a>
      <a
        href={`https://www.tradingview.com/symbols/${encodeURIComponent(data.ticker)}/`}
        target="_blank"
        rel="noreferrer"
        className="hidden text-xs text-muted hover:text-text sm:inline"
      >
        TradingView ↗
      </a>
    </div>
  );
}

function Stats({ contracts }: { contracts: Contract[] }) {
  const avg = (f: (c: Contract) => number) =>
    contracts.reduce((s, c) => s + f(c), 0) / contracts.length;
  const items = [
    ["Avg premium (bid)", fmtUsd(avg((c) => c.bid))],
    ["Avg static return", fmtPct(avg((c) => c.static_return_pct))],
    ["Best static return", fmtPct(Math.max(...contracts.map((c) => c.static_return_pct)))],
    ["Avg distance to strike", fmtPct(avg((c) => c.distance_to_strike_pct))],
  ];
  return (
    <dl className="grid grid-cols-2 border-b border-border lg:grid-cols-4">
      {items.map(([k, v]) => (
        <div key={k} className="border-r border-border px-4 py-3 last:border-r-0">
          <dt className="label">{k}</dt>
          <dd className="num mt-1 text-lg text-text">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

function expiryLabel(lo: number | null, hi: number | null): string {
  if (lo === null && hi === null) return "all expiries";
  if (lo === null) return `≤${hi}d`;
  if (hi === null) return `≥${lo}d`;
  return `${lo}–${hi}d`;
}

const clamp01 = (v: number) => Math.min(Math.max(v, 0), 1);

function screenerColumns(price: number): Column<Contract>[] {
  return [
    { key: "exp", header: "Expiry", value: (c) => c.expiration, render: (c) => fmtDate(c.expiration) },
    { key: "dte", header: "DTE", hint: "Days to expiry", value: (c) => c.days_to_expiry },
    {
      key: "strike",
      header: "Strike",
      value: (c) => c.strike,
      render: (c) => (
        <>
          {fmtUsd(c.strike)} <span className="text-muted">({fmtSigned(c.strike - price)})</span>
        </>
      ),
    },
    {
      key: "dist",
      header: "Dist",
      hint: "How far the stock must rise to reach the strike",
      value: (c) => c.distance_to_strike_pct,
      render: (c) => fmtPct(c.distance_to_strike_pct),
    },
    { key: "bid", header: "Bid", hint: "Premium you can sell at now", value: (c) => c.bid, render: (c) => fmtUsd(c.bid) },
    { key: "mid", header: "Mid", value: (c) => c.mid, render: (c) => fmtUsd(c.mid) },
    { key: "ask", header: "Ask", value: (c) => c.ask, render: (c) => fmtUsd(c.ask) },
    {
      key: "spread",
      header: "Spread",
      hint: "Ask minus bid: the cost of trading in and out",
      value: (c) => c.spread,
      render: (c) => fmtUsd(c.spread),
    },
    {
      key: "be",
      header: "Breakeven",
      hint: "Stock price minus the premium collected",
      value: (c) => c.breakeven,
      render: (c) => fmtUsd(c.breakeven),
    },
    {
      key: "static",
      header: "Static",
      hint: "Bid / stock price: your return if the stock doesn't move",
      value: (c) => c.static_return_pct,
      render: (c) => fmtPct(c.static_return_pct),
      heat: (c) => clamp01(c.static_return_pct / 5),
    },
    {
      key: "annual",
      header: "Annual",
      hint: "Static return x 365 / days to expiry",
      value: (c) => c.annualized_return_pct,
      render: (c) => fmtPct(c.annualized_return_pct, 1),
      heat: (c) => clamp01(c.annualized_return_pct / 60),
    },
    {
      key: "assign",
      header: "P(assign)",
      hint: "Black-Scholes call delta: approx. probability the shares get called away",
      value: (c) => c.assignment_prob ?? null,
      render: (c) => (c.assignment_prob == null ? "—" : fmtPct(c.assignment_prob * 100, 0)),
    },
    { key: "iv", header: "IV", hint: "Implied volatility", value: (c) => c.iv_pct, render: (c) => fmtPct(c.iv_pct, 1) },
    { key: "vol", header: "Volume", value: (c) => c.volume, render: (c) => fmtInt(c.volume) },
    { key: "oi", header: "OI", hint: "Open interest", value: (c) => c.open_interest, render: (c) => fmtInt(c.open_interest) },
    {
      key: "link",
      header: "Contract",
      hint: "Open this exact contract on Yahoo Finance",
      sortable: false,
      value: () => null,
      render: (c) => <YahooLink contractSymbol={c.contract_symbol} />,
    },
  ];
}

"use client";

import { Fragment, useEffect, useRef, type ReactNode } from "react";

import { Tex } from "@/components/Tex";
import { YahooLink } from "@/components/YahooLink";
import type { Contract } from "@/lib/api";
import { fmtDate, fmtPct, fmtUsd } from "@/lib/format";

const SHARES_PER_CONTRACT = 100;
// A typical day's move shifting delta by this much or more is flagged as fast-changing risk.
const GAMMA_FLAG_SWING = 0.1;

const fx = (n: number, digits: number) => n.toFixed(digits);
const signedUsd = (n: number) => `${n < 0 ? "−" : "+"}${fmtUsd(Math.abs(n))}`;

/**
 * Everything about one contract from the call seller's side: the Greeks in plain
 * sentences with this contract's numbers, and the formulas with the inputs plugged in.
 */
export function ContractPanel({
  contract: c,
  price,
  rate,
  onClose,
}: {
  contract: Contract;
  price: number;
  rate: number;
  onClose: () => void;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = overflow;
      window.removeEventListener("keydown", onKey);
    };
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-40" role="dialog" aria-modal="true" aria-labelledby="contract-title">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <aside className="absolute top-0 right-0 flex h-full w-full max-w-[480px] flex-col border-l border-border bg-panel shadow-xl">
        <header className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
          <div>
            <h2 id="contract-title" className="text-lg font-semibold tracking-tight">
              {c.ticker} {fmtUsd(c.strike)} call
            </h2>
            <p className="num mt-0.5 text-xs text-muted">
              Expires {fmtDate(c.expiration)} · {c.days_to_expiry} days · stock {fmtUsd(price)} ·{" "}
              <YahooLink contractSymbol={c.contract_symbol} />
            </p>
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="h-7 w-7 shrink-0 rounded-sm border border-border text-text-2 hover:border-border-strong hover:text-text"
          >
            ✕
          </button>
        </header>
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {c.delta == null ? (
            <p className="text-sm text-text-2">
              No Greeks for this contract: the data source has no usable implied volatility for it.
            </p>
          ) : (
            <Breakdown c={c} price={price} rate={rate} />
          )}
        </div>
      </aside>
    </div>
  );
}

function Breakdown({ c, price, rate }: { c: Contract; price: number; rate: number }) {
  const delta = c.delta ?? 0;
  const gamma = c.gamma ?? 0;
  const theta = c.theta_per_day ?? 0;
  const vega = c.vega ?? 0;
  const rho = c.rho ?? 0;
  const pAssign = c.assignment_prob ?? 0;
  const n = SHARES_PER_CONTRACT;

  const sharesLike = (d: number) => Math.round(n * (1 - d));
  const deltaUp = Math.min(delta + gamma, 1); // delta after a $1 rise (gamma's linear estimate)
  const sigma = c.iv_pct / 100;
  const dailyMove = price * sigma * Math.sqrt(1 / 365);
  const dailySwing = gamma * dailyMove;

  return (
    <div className="flex flex-col gap-5">
      <dl className="grid grid-cols-2 rounded-sm border border-border">
        <Stat label="Premium" value={fmtUsd(c.bid * n)} note={`${fmtUsd(c.bid)} per share`} />
        <Stat label="P(ITM)" symbol="N(d₂)" value={fmtPct(pAssign * 100, 0)} note="chance of assignment" />
        <Stat label="You earn per day" symbol="Θ" value={fmtUsd(-theta * n)} note="per contract" />
        <Stat label="Moves like" symbol="Δ" value={`${sharesLike(delta)} shares`} note="shares + this call" />
      </dl>

      <section>
        <p className="label">Per share · 1 contract = {n} shares</p>
        <ul className="mt-1">
          <Greek symbol="Δ" name="Delta" value={fx(delta, 3)}>
            Stock +$1 → call +{fmtUsd(delta)}. Your {n} shares minus this call move like{" "}
            {sharesLike(delta)} shares.
          </Greek>
          <Greek symbol="Γ" name="Gamma" value={fx(gamma, 4)}>
            Stock +$1 → Δ goes from {fx(delta, 2)} to {fx(deltaUp, 2)} (you&apos;d move like{" "}
            {sharesLike(deltaUp)} shares). A typical day&apos;s move (±{fmtUsd(dailyMove)}) shifts Δ
            by {fx(dailySwing, 2)}.
            {dailySwing >= GAMMA_FLAG_SWING && (
              <span className="mt-1.5 block rounded-sm border border-down/40 bg-down/10 px-2 py-1 text-down">
                Fast-changing risk: near the strike and close to expiry, a normal day can swing your
                odds of assignment a lot.
              </span>
            )}
          </Greek>
          <Greek symbol="Θ" name="Theta" value={`${fx(theta, 4)}/day`}>
            Each day the call loses {fmtUsd(-theta)} per share. You sold it, so you earn about{" "}
            {fmtUsd(-theta * n)} per contract per day if nothing else changes.
          </Greek>
          <Greek symbol="ν" name="Vega" value={fx(vega, 4)}>
            Volatility +1 point → call +{fmtUsd(vega)}. For you as the seller that&apos;s{" "}
            {signedUsd(-vega * n)} per contract.
          </Greek>
          <Greek symbol="ρ" name="Rho" value={fx(rho, 4)}>
            Interest rate +1 point → call +{fmtUsd(rho)}: {signedUsd(-rho * n)} per contract for you.
            Matters most for long-dated calls.
          </Greek>
          <Greek symbol="N(d₂)" name="Probability ITM" value={fmtPct(pAssign * 100, 1)}>
            The chance {c.ticker} ends above {fmtUsd(c.strike)} on {fmtDate(c.expiration)}, so your
            shares get called away.
            <span className="mt-1 block text-muted">
              Delta ({fmtPct(delta * 100, 1)}) is higher because it also weighs how far above the
              strike the stock might end.
            </span>
          </Greek>
        </ul>
      </section>

      {c.model_price != null && (
        <section>
          <p className="label">Model check · per share</p>
          <dl className="num mt-2 grid grid-cols-[auto_1fr] gap-x-6 gap-y-1 text-sm">
            <dt className="text-text-2">Black-Scholes price</dt>
            <dd className="text-text">{fmtUsd(c.model_price)}</dd>
            <dt className="text-text-2">Market quote</dt>
            <dd className="text-text">
              {fmtUsd(c.bid)} bid / {fmtUsd(c.ask)} ask
            </dd>
          </dl>
          <p className="mt-1.5 text-xs text-muted">
            The model uses Yahoo&apos;s implied volatility for this contract.
          </p>
        </section>
      )}

      <Formulas c={c} price={price} rate={rate} />
    </div>
  );
}

function Stat({
  label,
  symbol,
  value,
  note,
}: {
  label: string;
  symbol?: string;
  value: string;
  note: string;
}) {
  return (
    <div className="border-border px-3 py-2.5 odd:border-r [&:nth-child(-n+2)]:border-b">
      <dt className="label">
        {label}
        {symbol && <span className="font-normal opacity-60"> ({symbol})</span>}
      </dt>
      <dd className="num mt-0.5 text-base text-text">{value}</dd>
      <dd className="text-xs text-muted">{note}</dd>
    </div>
  );
}

function Greek({
  symbol,
  name,
  value,
  children,
}: {
  symbol: string;
  name: string;
  value: string;
  children: ReactNode;
}) {
  return (
    <li className="grid grid-cols-[2.5rem_1fr] gap-x-2 border-b border-grid py-3 last:border-b-0">
      <span
        className={`leading-tight whitespace-nowrap text-muted ${symbol.length > 1 ? "pt-0.5 text-sm" : "text-lg"}`}
      >
        {symbol}
      </span>
      <div>
        <div className="flex items-baseline justify-between gap-3">
          <span className="text-sm text-text">{name}</span>
          <span className="num text-sm text-text">{value}</span>
        </div>
        <p className="mt-1 text-xs leading-relaxed text-text-2">{children}</p>
      </div>
    </li>
  );
}

function Formulas({ c, price, rate }: { c: Contract; price: number; rate: number }) {
  if (c.d1 == null || c.d2 == null || c.delta == null || c.assignment_prob == null) return null;
  const S = fx(price, 2);
  const K = fx(c.strike, 2);
  const t = fx(c.years_to_expiry, 4);
  const daysLeft = fx(c.years_to_expiry * 365, 2);
  const sigma = fx(c.iv_pct / 100, 3);
  const r = fx(rate, 3);
  const d1 = fx(c.d1, 3);
  const d2 = fx(c.d2, 3);
  const nd1 = fx(c.delta, 4);
  const nd2 = fx(c.assignment_prob, 4);
  const pdf = fx(Math.exp(-0.5 * c.d1 * c.d1) / Math.sqrt(2 * Math.PI), 4);
  const theta = c.theta_per_day ?? 0;
  const vega = c.vega ?? 0;
  const rho = c.rho ?? 0;

  const inputs: [string, string, string?][] = [
    ["Stock", `S = ${S}`],
    ["Strike", `K = ${K}`],
    ["Time", `T = ${daysLeft}/365 = ${t}`, "years, to the 4pm close"],
    ["Volatility", `\\sigma = ${sigma}`],
    ["Rate", `r = ${r}`],
  ];

  // Each formula: its symbol, then the steps (general form, numbers plugged in, result).
  const lines: [string, string, string[]][] = [
    [
      "How many typical moves the stock is from the strike",
      "d_1",
      [
        `\\frac{\\ln(S/K) + (r + \\sigma^2/2)\\,T}{\\sigma\\sqrt{T}}`,
        `\\frac{\\ln(${S}/${K}) + (${r} + ${sigma}^2/2)(${t})}{${sigma}\\sqrt{${t}}}`,
        d1,
      ],
    ],
    ["", "d_2", [`d_1 - \\sigma\\sqrt{T}`, `${d1} - ${sigma}\\sqrt{${t}}`, d2]],
    [
      "Call price: the average payout over every possible future",
      "C",
      [
        `S\\,N(d_1) - K e^{-rT} N(d_2)`,
        `${S}(${nd1}) - ${K}\\,e^{-${r}\\cdot ${t}}(${nd2})`,
        fx(c.model_price ?? 0, 2),
      ],
    ],
    ["Delta", "\\Delta", [`\\frac{\\partial C}{\\partial S} = N(d_1)`, `N(${d1})`, fx(c.delta, 3)]],
    [
      "Gamma",
      "\\Gamma",
      [
        `\\frac{\\partial^2 C}{\\partial S^2} = \\frac{\\varphi(d_1)}{S\\sigma\\sqrt{T}}`,
        `\\frac{${pdf}}{${S}\\cdot ${sigma}\\sqrt{${t}}}`,
        fx(c.gamma ?? 0, 4),
      ],
    ],
    [
      "Theta, per year, then ÷ 365 for per day",
      "\\Theta",
      [
        `\\frac{\\partial C}{\\partial t} = -\\frac{S\\,\\varphi(d_1)\\,\\sigma}{2\\sqrt{T}} - rKe^{-rT}N(d_2)`,
        `${fx(theta * 365, 3)}\\text{ per year}`,
        `${fx(theta, 4)}\\text{ per day}`,
      ],
    ],
    [
      "Vega, per 1.00 of volatility, then ÷ 100 for per point",
      "\\nu",
      [
        `\\frac{\\partial C}{\\partial \\sigma} = S\\,\\varphi(d_1)\\sqrt{T}`,
        `${fx(vega * 100, 3)}\\text{ per 1.00}`,
        `${fx(vega, 4)}\\text{ per point}`,
      ],
    ],
    [
      "Rho, per 1.00 of interest rate, then ÷ 100 for per point",
      "\\rho",
      [
        `\\frac{\\partial C}{\\partial r} = K\\,T\\,e^{-rT}N(d_2)`,
        `${fx(rho * 100, 3)}\\text{ per 1.00}`,
        `${fx(rho, 4)}\\text{ per point}`,
      ],
    ],
    ["Probability of assignment", "P(S_T > K)", [`N(d_2)`, `N(${d2})`, nd2]],
  ];

  return (
    <details className="group rounded-sm border border-border">
      <summary className="label flex cursor-pointer list-none items-center gap-2 px-3 py-2.5 hover:text-text-2">
        <span className="transition-transform group-open:rotate-90">▸</span>
        Show formulas
      </summary>
      <div className="border-t border-border px-3 py-3 text-[13px] text-text">
        <p className="text-xs text-muted">Inputs</p>
        <dl className="mt-1 mb-3 grid grid-cols-[auto_1fr] items-baseline gap-x-4 gap-y-1">
          {inputs.map(([label, tex, note]) => (
            <Fragment key={label}>
              <dt className="text-xs text-text-2">{label}</dt>
              <dd>
                <Tex>{tex}</Tex>
                {note && <span className="ml-1.5 text-xs text-muted">{note}</span>}
              </dd>
            </Fragment>
          ))}
        </dl>
        {lines.map(([caption, symbol, steps], i) => (
          <div key={i} className="mt-2">
            {caption && <p className="text-xs text-muted">{caption}</p>}
            <Tex block>{`\\begin{aligned} ${symbol} &= ${steps.join(" \\\\ &= ")} \\end{aligned}`}</Tex>
          </div>
        ))}
        <p className="mt-3 text-xs leading-relaxed text-muted">
          <Tex>{"N"}</Tex> is the bell curve&apos;s area to the left of a point (a probability);{" "}
          <Tex>{"\\varphi"}</Tex> is its height. Dividends are not included yet, and the rate is a
          fixed {fmtPct(rate * 100, 1)}.
        </p>
      </div>
    </details>
  );
}

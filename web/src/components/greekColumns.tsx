import type { Column } from "@/components/DataTable";
import type { Contract } from "@/lib/api";
import { fmtPct, fmtUsd } from "@/lib/format";
import { GLOSSARY } from "@/lib/glossary";

/** What the seller earns per day per contract (100 shares): minus theta. */
export function perDayColumn<T extends Contract>(): Column<T> {
  return {
    key: "perday",
    header: "$/day",
    symbol: "Θ",
    hint: GLOSSARY.perDay,
    value: (c) => (c.theta_per_day == null ? null : -c.theta_per_day * 100),
    render: (c) => (c.theta_per_day == null ? "—" : fmtUsd(-c.theta_per_day * 100)),
  };
}

/** P(ITM) = N(d2): the Black-Scholes probability the call ends in the money (shares called away). */
export function assignColumn<T extends Contract>(): Column<T> {
  return {
    key: "assign",
    header: "P(ITM)",
    symbol: "N(d₂)",
    hint: GLOSSARY.assign,
    value: (c) => c.assignment_prob ?? null,
    render: (c) => (c.assignment_prob == null ? "—" : fmtPct(c.assignment_prob * 100, 0)),
  };
}

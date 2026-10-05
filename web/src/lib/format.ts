const usd = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
const int = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

export const fmtUsd = (n: number) => usd.format(n);
export const fmtInt = (n: number) => int.format(n);
export const fmtPct = (n: number, digits = 2) => `${n.toFixed(digits)}%`;
export const fmtSigned = (n: number, digits = 2) => `${n >= 0 ? "+" : ""}${n.toFixed(digits)}`;

/** "2026-10-14" -> "Oct 14" (parsed as a calendar date, not shifted by timezone) */
export function fmtDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function fmtTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-US", { hour12: false });
}

export const yahooQuoteUrl = (symbol: string) =>
  `https://finance.yahoo.com/quote/${encodeURIComponent(symbol)}`;

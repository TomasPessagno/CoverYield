import { yahooQuoteUrl } from "@/lib/format";

/** Link to the exact option contract (OCC symbol) on Yahoo Finance. */
export function YahooLink({ contractSymbol }: { contractSymbol: string }) {
  return (
    <a
      href={yahooQuoteUrl(contractSymbol)}
      target="_blank"
      rel="noreferrer"
      title={`Open ${contractSymbol} on Yahoo Finance`}
      className="text-muted underline decoration-border-strong underline-offset-4 hover:text-text hover:decoration-text"
    >
      Yahoo ↗
    </a>
  );
}

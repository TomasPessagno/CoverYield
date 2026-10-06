"""Yahoo Finance market data via yfinance."""

from __future__ import annotations

import time

import pandas as pd
import yfinance as yf

from coveryield.data.provider import CallChain, DataFetchError


class YahooFinanceProvider:
    """MarketDataProvider backed by yfinance (free, unofficial, rate-limited)."""

    def __init__(self, retry_delay_seconds: float = 0.5) -> None:
        self._retry_delay = retry_delay_seconds

    def fetch_call_chain(self, ticker: str) -> CallChain:
        """Extract raw CALL options data for every listed expiration of ``ticker``."""
        try:
            ticker_obj = yf.Ticker(ticker)

            # Get all available expiration dates. yfinance reports network errors
            # as "no expirations", so retry once before concluding there are none.
            expirations = ticker_obj.options
            if not expirations:
                time.sleep(self._retry_delay)
                ticker_obj = yf.Ticker(ticker)
                expirations = ticker_obj.options
            if not expirations:
                return CallChain(ticker, 0.0, 0.0, pd.DataFrame())

            # Fetch CALL options for each expiration date
            all_calls = []
            for exp in expirations:
                try:
                    opt_chain = ticker_obj.option_chain(exp)
                    if opt_chain.calls is not None and len(opt_chain.calls) > 0:
                        calls = opt_chain.calls.copy()
                        calls["optionType"] = "call"
                        calls["expirationDate"] = exp
                        all_calls.append(calls)
                except Exception:
                    continue

            if not all_calls:
                return CallChain(ticker, 0.0, 0.0, pd.DataFrame())

            # Combine all call options
            options_df = pd.concat(all_calls, ignore_index=True)

            # Get current stock price and today's open
            info = ticker_obj.info
            current_price = float(info.get("regularMarketPrice", 0))
            open_price = float(info.get("regularMarketOpen", info.get("open", 0)))

            # Convert expiration dates to datetime
            options_df["expirationDate"] = pd.to_datetime(options_df["expirationDate"])

            return CallChain(ticker, current_price, open_price, options_df)

        except Exception as e:
            raise DataFetchError(str(e)) from e

    def search_tickers(self, query: str) -> list[tuple[str, str]]:
        """
        Search Yahoo Finance for tickers matching the query string.
        Returns a list of (display_label, ticker_symbol) tuples for the searchbox.
        """
        if not query or len(query) < 1:
            return []

        try:
            results = yf.Search(query, max_results=10)
            suggestions = []
            for quote in results.quotes:
                symbol = quote.get("symbol", "")
                name = quote.get("shortname", quote.get("longname", ""))
                exchange = quote.get("exchange", "")
                quote_type = quote.get("quoteType", "")

                label_parts = [symbol]
                if name:
                    label_parts.append(f"— {name}")
                if exchange:
                    label_parts.append(f"({exchange})")
                if quote_type and quote_type not in ("EQUITY",):
                    label_parts.append(f"[{quote_type}]")

                label = " ".join(label_parts)
                suggestions.append((label, symbol))

            return suggestions
        except Exception:
            return []

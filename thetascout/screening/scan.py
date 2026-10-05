"""Multi-stock scan: fetch, filter and enrich call chains across a universe."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime

import pandas as pd

from thetascout.data.provider import DataFetchError, MarketDataProvider
from thetascout.data.yahoo import YahooFinanceProvider
from thetascout.pricing.black_scholes import call_delta
from thetascout.screening.filters import add_contract_metrics, filter_calls, numeric_column

ProgressCallback = Callable[[float, str], None]
ScanOne = Callable[[str, int, int], pd.DataFrame]


def scan_one_ticker(
    ticker: str,
    min_days: int,
    max_days: int,
    provider: MarketDataProvider | None = None,
    now: datetime | None = None,
) -> pd.DataFrame:
    """
    Fetch + filter a single ticker's calls and enrich them with the metrics the
    scoring engine needs. Returns an empty DataFrame on any failure.
    """
    provider = provider or YahooFinanceProvider()
    try:
        chain = provider.fetch_call_chain(ticker)
    except DataFetchError:
        return pd.DataFrame()
    if chain.is_empty:
        return pd.DataFrame()
    price = chain.price

    df = filter_calls(ticker, price, chain.calls, min_days, max_days, now=now)
    if df.empty:
        return pd.DataFrame()

    df = df[df["BidPrice"] > 0].copy()  # liquidity gate: drop zero-bid junk
    if df.empty:
        return pd.DataFrame()

    df["Current Price"] = price
    df = add_contract_metrics(df, price, now=now)
    df = df[df["Days to Expiry"] > 0].copy()
    if df.empty:
        return pd.DataFrame()

    iv_decimal = numeric_column(df, "impliedVolatility")
    df["Assignment Prob"] = [
        call_delta(price, strike, dte / 365.0, iv)
        for strike, dte, iv in zip(df["Strike"], df["Days to Expiry"], iv_decimal, strict=True)
    ]
    return df


def scan_universe(
    tickers: Sequence[str],
    min_days: int,
    max_days: int,
    progress_cb: ProgressCallback | None = None,
    scan_one: ScanOne = scan_one_ticker,
) -> pd.DataFrame:
    """Scan a list of tickers and concatenate their enriched option chains.

    ``scan_one`` lets callers pass a cached version of ``scan_one_ticker``.
    """
    frames = []
    total = len(tickers)
    for i, ticker in enumerate(tickers):
        try:
            df = scan_one(ticker, min_days, max_days)
        except Exception:
            df = pd.DataFrame()
        if not df.empty:
            frames.append(df)
        if progress_cb:
            progress_cb((i + 1) / total, ticker)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)

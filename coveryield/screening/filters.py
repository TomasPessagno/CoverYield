"""Option-chain filters and per-contract metrics for covered calls.

Column names match what the UI displays (e.g. ``"Static Return %"``) so the
frames can be shown directly.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

import pandas as pd

from coveryield.market_time import days_to_expiry, market_now, years_to_expiry
from coveryield.pricing.black_scholes import DEFAULT_RISK_FREE_RATE, CallGreeks, call_greeks
from coveryield.pricing.implied_vol import implied_vol

# Strikes below this fraction of the stock price are deep in the money and dropped.
MIN_STRIKE_FRACTION = 0.90


def numeric_column(df: pd.DataFrame, column: str) -> pd.Series:
    """A column coerced to float, with missing values (or a missing column) as 0."""
    values = df[column] if column in df.columns else pd.Series(0.0, index=df.index)
    return pd.to_numeric(values, errors="coerce").fillna(0)


def filter_calls(
    ticker: str,
    current_price: float,
    options_df: pd.DataFrame,
    min_days_to_expiry: int,
    max_days_to_expiry: int,
    now: datetime | None = None,
) -> pd.DataFrame:
    """
    Filter a raw call chain and compute the basic pricing columns.

    Steps:
    1. Keep expirations between ``min_days_to_expiry`` and ``max_days_to_expiry`` from now
    2. Keep calls only
    3. Drop deep ITM strikes (strike < 90% of the current price)
    4. Add Strike, BidPrice, AskPrice, MidPrice, Spread, Static Return % and Ticker
    """
    if options_df.empty:
        return pd.DataFrame()

    now = now or market_now()
    min_expiry = now + timedelta(days=min_days_to_expiry)
    max_expiry = now + timedelta(days=max_days_to_expiry)

    df = options_df[
        (options_df["expirationDate"] >= min_expiry) & (options_df["expirationDate"] <= max_expiry)
    ].copy()
    if df.empty:
        return pd.DataFrame()

    df = df[df["optionType"] == "call"].copy()

    df["Strike"] = df["strike"].round(2)
    df = df[df["Strike"] >= current_price * MIN_STRIKE_FRACTION].copy()

    df["BidPrice"] = numeric_column(df, "bid")
    df["AskPrice"] = numeric_column(df, "ask")
    df["MidPrice"] = (df["BidPrice"] + df["AskPrice"]) / 2
    df["Spread"] = df["AskPrice"] - df["BidPrice"]

    # Static return uses the bid: the price you can actually sell at right now.
    if current_price > 0:
        df["Static Return %"] = (df["BidPrice"] / current_price) * 100
    else:
        df["Static Return %"] = 0.0

    df["Ticker"] = ticker
    return df


def add_contract_metrics(
    df: pd.DataFrame,
    current_price: float,
    now: datetime | None = None,
    quoted_at: datetime | None = None,
) -> pd.DataFrame:
    """
    Add derived per-contract metrics to a frame produced by ``filter_calls``.

    Days to Expiry (calendar days from ``now``), Years to Expiry (the Black-Scholes
    T: from ``quoted_at`` to the 4pm close on expiry day), Annualized Return % (0
    when expiry is today or past), Distance to Strike %, Breakeven Price, Volume,
    Open Interest and Yahoo IV (in percent).

    ``quoted_at`` is when the prices were captured (defaults to ``now``). A quote
    reflects the time left *when it was taken*, so pricing a stored snapshot needs
    that moment: a 3-day-old quote on a 4-day option, priced as if it had 1 day
    left, implies a wildly inflated volatility. Both are New York wall time (see
    ``coveryield.market_time``).
    """
    out = df.copy()
    now = now or market_now()
    quoted_at = quoted_at or now

    out["Days to Expiry"] = days_to_expiry(out["expirationDate"], now)
    out["Years to Expiry"] = years_to_expiry(out["expirationDate"], quoted_at)
    dte = out["Days to Expiry"]
    out["Annualized Return %"] = (out["Static Return %"] * (365 / dte.where(dte > 0))).fillna(0.0)

    out["Distance to Strike %"] = ((out["Strike"] - current_price) / current_price) * 100
    out["Breakeven Price"] = current_price - out["BidPrice"]

    out["Volume"] = numeric_column(out, "volume").astype(int)
    out["Open Interest"] = numeric_column(out, "openInterest").astype(int)
    # The data source's own IV, kept for comparison; add_greeks solves our own.
    out["Yahoo IV"] = numeric_column(out, "impliedVolatility") * 100
    return out


# Columns added by ``add_greeks``, in display units (per share).
GREEK_COLUMNS = (
    "Assignment Prob",  # N(d2): probability the stock ends above the strike
    "Delta",  # call price change per $1 stock move
    "Gamma",  # delta change per $1 stock move
    "Theta/Day",  # call price change per calendar day (negative)
    "Vega",  # call price change per 1 percentage point of volatility
    "Rho",  # call price change per 1 percentage point of interest rate
    "Model Price",  # Black-Scholes price at our IV (equals the mid by construction)
    "d1",
    "d2",
)


def _greek_values(greeks: CallGreeks | None) -> tuple[float | None, ...]:
    if greeks is None:
        return (None,) * len(GREEK_COLUMNS)
    return (
        greeks.prob_itm,
        greeks.delta,
        greeks.gamma,
        greeks.theta / 365.0,
        greeks.vega / 100.0,
        greeks.rho / 100.0,
        greeks.price,
        greeks.d1,
        greeks.d2,
    )


def mid_implied_vol(
    bid: float, ask: float, spot: float, strike: float, t_years: float, r: float
) -> float | None:
    """Implied volatility (decimal) solved from the bid/ask mid, or None.

    Needs a two-sided quote (bid > 0, ask >= bid): a mid built from a zero bid
    or a crossed market isn't a price anyone traded at.
    """
    if not (bid > 0 and ask >= bid):
        return None
    return implied_vol((bid + ask) / 2, spot, strike, t_years, r)


def add_greeks(
    df: pd.DataFrame, current_price: float, r: float = DEFAULT_RISK_FREE_RATE
) -> pd.DataFrame:
    """Solve each contract's implied volatility from its mid, then add the Greeks.

    ``IV`` (percent) is our own implied volatility, so Black-Scholes reproduces
    the mid price exactly. ``Assignment Prob`` is N(d2), the model's probability
    that the stock finishes above the strike. Expects ``Years to Expiry`` and the
    quote columns (see ``filter_calls`` and ``add_contract_metrics``). Contracts
    whose quote no volatility can explain, or that are past their expiry close,
    get NaN for IV and ``None`` for every Greek. ``Yahoo Model Price`` is the
    Black-Scholes price at the data source's IV, for comparison.
    """
    out = df.copy()
    ivs = [
        mid_implied_vol(bid, ask, current_price, strike, t, r)
        for bid, ask, strike, t in zip(
            out["BidPrice"], out["AskPrice"], out["Strike"], out["Years to Expiry"], strict=True
        )
    ]
    out["IV"] = [math.nan if iv is None else iv * 100 for iv in ivs]
    rows = [
        _greek_values(None if iv is None else call_greeks(current_price, strike, t, iv, r))
        for strike, t, iv in zip(out["Strike"], out["Years to Expiry"], ivs, strict=True)
    ]
    values = pd.DataFrame(rows, columns=list(GREEK_COLUMNS), index=out.index, dtype=object)
    for column in GREEK_COLUMNS:
        out[column] = values[column]

    # For comparison: what Black-Scholes would say using the data source's IV.
    yahoo_prices = [
        call_greeks(current_price, strike, t, yahoo_iv / 100, r)
        for strike, t, yahoo_iv in zip(
            out["Strike"], out["Years to Expiry"], out["Yahoo IV"], strict=True
        )
    ]
    out["Yahoo Model Price"] = [math.nan if g is None else g.price for g in yahoo_prices]
    return out


def filter_by_strike_and_return(
    df: pd.DataFrame,
    current_price: float,
    min_strike_offset: float,
    max_strike_offset: float,
    min_static_return: float,
    min_annualized_return: float,
) -> pd.DataFrame:
    """Single-ticker screen: strike within ``current_price + offset`` bounds, minimum returns."""
    return df[
        (df["Strike"] >= current_price + min_strike_offset)
        & (df["Strike"] <= current_price + max_strike_offset)
        & (df["Static Return %"] >= min_static_return)
        & (df["Annualized Return %"] >= min_annualized_return)
    ].copy()


def filter_by_goals(
    df: pd.DataFrame, min_static_return: float, max_days_to_expiry: int, min_otm_pct: float
) -> pd.DataFrame:
    """Multi-stock screen: minimum actual return, maximum DTE and minimum distance OTM."""
    return df[
        (df["Static Return %"] >= min_static_return)
        & (df["Days to Expiry"] <= max_days_to_expiry)
        & (df["Distance to Strike %"] >= min_otm_pct)
    ].copy()

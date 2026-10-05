"""ThetaScout HTTP API: a thin FastAPI layer over the thetascout package.

Run locally from the repo root:  uvicorn api.app:app --reload
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from datetime import datetime
from typing import Annotated, Any

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Path, Query

from api.schemas import (
    Contract,
    OpportunitiesRequest,
    OpportunitiesResponse,
    Opportunity,
    ScanTickerResponse,
    ScreenerResponse,
    TickerMatch,
    UniverseTicker,
)
from thetascout import __version__
from thetascout.data.cache import CachedProvider
from thetascout.data.provider import DataFetchError, MarketDataProvider
from thetascout.data.universe import TICKER_MAP
from thetascout.data.yahoo import YahooFinanceProvider
from thetascout.screening.filters import (
    add_assignment_probability,
    add_contract_metrics,
    filter_by_goals,
    filter_calls,
)
from thetascout.screening.scan import scan_one_ticker
from thetascout.screening.scoring import (
    compute_opportunity_score,
    normalize_weights,
    rank_opportunities,
)

# The multi-stock scan always covers this window; goal filters narrow it afterwards.
SCAN_MIN_DAYS = 1
SCAN_MAX_DAYS = 120

app = FastAPI(
    title="ThetaScout API",
    version=__version__,
    description="Covered call screening, Black-Scholes assignment probability and scoring.",
)

_provider = CachedProvider(YahooFinanceProvider())


def get_provider() -> MarketDataProvider:
    return _provider


Provider = Annotated[MarketDataProvider, Depends(get_provider)]
Ticker = Annotated[str, Path(min_length=1, max_length=12, pattern=r"^[A-Za-z0-9.\-^=]+$")]


def _num(value: Any, default: float = 0.0) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    return default if math.isnan(f) else f


def _contract_fields(row: dict[str, Any]) -> dict[str, Any]:
    delta = row.get("Assignment Prob")
    return {
        "contract_symbol": str(row["contractSymbol"]),
        "ticker": str(row["Ticker"]),
        "expiration": pd.Timestamp(row["expirationDate"]).date(),
        "days_to_expiry": int(row["Days to Expiry"]),
        "strike": _num(row["Strike"]),
        "bid": _num(row["BidPrice"]),
        "ask": _num(row["AskPrice"]),
        "mid": _num(row["MidPrice"]),
        "spread": _num(row["Spread"]),
        "static_return_pct": _num(row["Static Return %"]),
        "annualized_return_pct": _num(row["Annualized Return %"]),
        "distance_to_strike_pct": _num(row["Distance to Strike %"]),
        "breakeven": _num(row["Breakeven Price"]),
        "volume": int(_num(row["Volume"])),
        "open_interest": int(_num(row["Open Interest"])),
        "iv_pct": _num(row["IV"]),
        "assignment_prob": None if delta is None or pd.isna(delta) else float(delta),
    }


def _records(df: pd.DataFrame) -> Iterator[dict[str, Any]]:
    for row in df.to_dict("records"):
        yield {str(k): v for k, v in row.items()}


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/api/universe")
def universe() -> list[UniverseTicker]:
    return [UniverseTicker(symbol=s, name=n) for s, n in TICKER_MAP.items()]


@app.get("/api/search")
def search(
    provider: Provider, q: Annotated[str, Query(min_length=1, max_length=40)]
) -> list[TickerMatch]:
    return [TickerMatch(label=label, symbol=sym) for label, sym in provider.search_tickers(q)]


@app.get("/api/screener/{ticker}")
def screener(
    ticker: Ticker,
    provider: Provider,
    min_days: Annotated[int, Query(ge=0, le=365)] = 7,
    max_days: Annotated[int, Query(ge=1, le=730)] = 42,
) -> ScreenerResponse:
    """Every call in the expiry window with its metrics; finer filters are applied client-side."""
    symbol = ticker.upper()
    try:
        chain = provider.fetch_call_chain(symbol)
    except DataFetchError as e:
        raise HTTPException(status_code=502, detail=f"Market data unavailable: {e}") from e
    if chain.is_empty:
        raise HTTPException(status_code=404, detail=f"No option data for '{symbol}'.")

    now = datetime.now()
    df = filter_calls(symbol, chain.price, chain.calls, min_days, max_days, now=now)
    contracts: list[Contract] = []
    if not df.empty:
        df = add_assignment_probability(add_contract_metrics(df, chain.price, now=now), chain.price)
        contracts = [Contract(**_contract_fields(r)) for r in _records(df)]
    return ScreenerResponse(
        ticker=symbol,
        price=chain.price,
        open_price=chain.open_price,
        as_of=now,
        contracts=contracts,
    )


@app.post("/api/scan/{ticker}")
def scan_ticker(ticker: Ticker, provider: Provider) -> ScanTickerResponse:
    """Fetch and enrich one ticker (warming the cache). Lets clients show scan progress."""
    symbol = ticker.upper()
    df = scan_one_ticker(symbol, SCAN_MIN_DAYS, SCAN_MAX_DAYS, provider=provider)
    return ScanTickerResponse(ticker=symbol, ok=not df.empty, contracts=len(df))


@app.post("/api/opportunities")
def opportunities(req: OpportunitiesRequest, provider: Provider) -> OpportunitiesResponse:
    """Filter the scanned tickers by the user's goals, score every contract and rank them."""
    now = datetime.now()
    frames = [
        scan_one_ticker(t.upper(), SCAN_MIN_DAYS, SCAN_MAX_DAYS, provider=provider, now=now)
        for t in dict.fromkeys(req.tickers)
    ]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return OpportunitiesResponse(scanned=len(req.tickers), matched=0, results=[])

    scanned = pd.concat(frames, ignore_index=True)
    matched = filter_by_goals(
        scanned, req.min_static_return_pct, req.max_days_to_expiry, req.min_otm_pct
    )
    weights = normalize_weights(
        req.weights.model_dump(by_alias=True), yield_actual_frac=req.yield_actual_frac
    )
    ranked = rank_opportunities(compute_opportunity_score(matched, weights), req.top_n)

    results = [
        Opportunity(
            **_contract_fields(r),
            price=_num(r["Current Price"]),
            score=_num(r["Opportunity Score"]),
            score_yield=_num(r["s_yield"]),
            score_assignment=_num(r["s_assign"]),
            score_liquidity=_num(r["s_liq"]),
            score_volatility=_num(r["s_vol"]),
            score_dividend=_num(r["s_div"]),
        )
        for r in _records(ranked)
    ]
    return OpportunitiesResponse(scanned=len(req.tickers), matched=len(matched), results=results)

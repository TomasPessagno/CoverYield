"""ThetaScout HTTP API: a thin FastAPI layer over the thetascout package.

Run locally from the repo root:  uvicorn api.app:app --reload

Option chains are read through a ChainService: stored copies are served when
available, and live fetches are limited to one per ticker per cooldown window
(see api/settings.py for local vs hosted behavior).
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from datetime import datetime
from functools import lru_cache
from typing import Annotated, Any

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Path, Query

from api.schemas import (
    AppConfig,
    Contract,
    OpportunitiesRequest,
    OpportunitiesResponse,
    Opportunity,
    ScanTickerResponse,
    ScreenerResponse,
    TickerMatch,
    UniverseTicker,
)
from api.settings import Settings, load_settings
from thetascout import __version__
from thetascout.data.provider import DataFetchError, MarketDataProvider
from thetascout.data.service import ChainResult, ChainService
from thetascout.data.store import ChainStore, MemoryStore, RedisStore
from thetascout.data.universe import TICKER_MAP
from thetascout.data.yahoo import YahooFinanceProvider
from thetascout.screening.filters import (
    add_assignment_probability,
    add_contract_metrics,
    filter_by_goals,
    filter_calls,
)
from thetascout.screening.scan import enrich_chain
from thetascout.screening.scoring import (
    compute_opportunity_score,
    normalize_weights,
    rank_opportunities,
)

# The multi-stock scan always covers this window; goal filters narrow it afterwards.
SCAN_MIN_DAYS = 1
SCAN_MAX_DAYS = 120
# Upper bound used when the screener is asked for "no max" days to expiry (~10 years).
NO_MAX_DAYS = 3650

app = FastAPI(
    title="ThetaScout API",
    version=__version__,
    description="Covered call screening, Black-Scholes assignment probability and scoring.",
)


@lru_cache
def get_settings() -> Settings:
    return load_settings()


@lru_cache
def _provider() -> YahooFinanceProvider:
    return YahooFinanceProvider()


@lru_cache
def get_service() -> ChainService:
    settings = get_settings()
    store: ChainStore = (
        RedisStore.from_url(settings.redis_url) if settings.redis_url else MemoryStore()
    )
    return ChainService(
        _provider(),
        store,
        cooldown_seconds=settings.refresh_cooldown_seconds,
        max_age_seconds=settings.max_age_seconds,
    )


def get_provider() -> MarketDataProvider:
    return _provider()


Service = Annotated[ChainService, Depends(get_service)]
Provider = Annotated[MarketDataProvider, Depends(get_provider)]
AppSettings = Annotated[Settings, Depends(get_settings)]
Ticker = Annotated[str, Path(min_length=1, max_length=12, pattern=r"^[A-Za-z0-9.\-^=]+$")]
MinDays = Annotated[int | None, Query(ge=0, le=NO_MAX_DAYS)]
MaxDays = Annotated[int | None, Query(ge=0, le=NO_MAX_DAYS)]


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


def _screener_response(
    symbol: str, result: ChainResult, min_days: int | None, max_days: int | None
) -> ScreenerResponse:
    chain = result.chain
    if chain.is_empty:
        raise HTTPException(status_code=404, detail=f"No option data for '{symbol}'.")

    now = datetime.now()
    lo = 0 if min_days is None else min_days
    hi = NO_MAX_DAYS if max_days is None else max_days
    df = filter_calls(symbol, chain.price, chain.calls, lo, hi, now=now)
    contracts: list[Contract] = []
    if not df.empty:
        df = add_assignment_probability(add_contract_metrics(df, chain.price, now=now), chain.price)
        contracts = [Contract(**_contract_fields(r)) for r in _records(df)]
    return ScreenerResponse(
        ticker=symbol,
        price=chain.price,
        open_price=chain.open_price,
        as_of=result.fetched_at,
        refreshed=result.refreshed,
        stale=result.stale,
        next_refresh_at=result.next_refresh_at,
        contracts=contracts,
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/api/config")
def config(settings: AppSettings) -> AppConfig:
    """What this deployment allows, so the frontend can show the right controls."""
    return AppConfig(
        mode=settings.mode,
        refresh_cooldown_seconds=settings.refresh_cooldown_seconds,
        shared_store=settings.redis_url is not None,
    )


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
    ticker: Ticker, service: Service, min_days: MinDays = None, max_days: MaxDays = None
) -> ScreenerResponse:
    """Every call in the expiry window with its metrics; finer filters are applied client-side.

    Serves the stored copy of the ticker when there is one. Omitting ``min_days``
    or ``max_days`` means no limit on that side.
    """
    symbol = ticker.upper()
    try:
        result = service.get(symbol)
    except DataFetchError as e:
        raise HTTPException(status_code=502, detail=f"Market data unavailable: {e}") from e
    return _screener_response(symbol, result, min_days, max_days)


@app.post("/api/refresh/{ticker}")
def refresh(
    ticker: Ticker, service: Service, min_days: MinDays = None, max_days: MaxDays = None
) -> ScreenerResponse:
    """'Scan now': fetch this ticker live, unless it was fetched within the cooldown.

    Within the cooldown the stored copy is returned with ``refreshed: false`` and
    ``next_refresh_at`` set, so the client can show when a refresh is allowed.
    """
    symbol = ticker.upper()
    try:
        result = service.refresh(symbol)
    except DataFetchError as e:
        raise HTTPException(status_code=502, detail=f"Market data unavailable: {e}") from e
    return _screener_response(symbol, result, min_days, max_days)


@app.post("/api/scan/{ticker}")
def scan_ticker(ticker: Ticker, service: Service) -> ScanTickerResponse:
    """Load and enrich one ticker (from the store when possible). Lets clients show progress."""
    symbol = ticker.upper()
    try:
        df = enrich_chain(service.get(symbol).chain, SCAN_MIN_DAYS, SCAN_MAX_DAYS)
    except DataFetchError:
        df = pd.DataFrame()
    return ScanTickerResponse(ticker=symbol, ok=not df.empty, contracts=len(df))


@app.post("/api/opportunities")
def opportunities(req: OpportunitiesRequest, service: Service) -> OpportunitiesResponse:
    """Filter the scanned tickers by the user's goals, score every contract and rank them."""
    now = datetime.now()
    frames = []
    fetched_times = []
    for t in dict.fromkeys(s.upper() for s in req.tickers):
        try:
            result = service.get(t)
        except DataFetchError:
            continue
        df = enrich_chain(result.chain, SCAN_MIN_DAYS, SCAN_MAX_DAYS, now=now)
        if not df.empty:
            frames.append(df)
            fetched_times.append(result.fetched_at)
    if not frames:
        return OpportunitiesResponse(
            scanned=len(req.tickers), matched=0, oldest_data_at=None, results=[]
        )

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
    return OpportunitiesResponse(
        scanned=len(req.tickers),
        matched=len(matched),
        oldest_data_at=min(fetched_times),
        results=results,
    )

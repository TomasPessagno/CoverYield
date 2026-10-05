"""Request and response models for the ThetaScout API.

These define the JSON contract (and the generated OpenAPI schema the web
frontend's TypeScript types are built from).
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class TickerMatch(BaseModel):
    label: str
    symbol: str


class UniverseTicker(BaseModel):
    symbol: str
    name: str


class Contract(BaseModel):
    """One call option with the metrics a covered-call seller cares about."""

    contract_symbol: str
    ticker: str
    expiration: date
    days_to_expiry: int
    strike: float
    bid: float
    ask: float
    mid: float
    spread: float
    static_return_pct: float = Field(description="bid / stock price, in percent")
    annualized_return_pct: float = Field(description="static return x 365 / days to expiry")
    distance_to_strike_pct: float = Field(description="(strike - price) / price, in percent")
    breakeven: float = Field(description="stock price minus the premium collected")
    volume: int
    open_interest: int
    iv_pct: float = Field(description="implied volatility, in percent")
    assignment_prob: float | None = Field(
        description="Black-Scholes call delta: approx. probability of finishing in the money"
    )


class ScreenerResponse(BaseModel):
    ticker: str
    price: float
    open_price: float
    as_of: datetime
    contracts: list[Contract]


class ScanTickerResponse(BaseModel):
    ticker: str
    ok: bool
    contracts: int


class Weights(BaseModel):
    """Raw Opportunity Score weights (normalized server-side)."""

    yield_: float = Field(default=40, ge=0, le=100, alias="yield")
    assign: float = Field(default=30, ge=0, le=100)
    liq: float = Field(default=15, ge=0, le=100)
    vol: float = Field(default=10, ge=0, le=100)
    div: float = Field(default=5, ge=0, le=100)

    model_config = {"populate_by_name": True}


class OpportunitiesRequest(BaseModel):
    tickers: list[str] = Field(min_length=1, max_length=100)
    min_static_return_pct: float = Field(default=1.0, ge=0)
    max_days_to_expiry: int = Field(default=45, ge=1, le=365)
    min_otm_pct: float = Field(default=2.0)
    weights: Weights = Field(default_factory=Weights)
    yield_actual_frac: float = Field(default=0.7, ge=0, le=1)
    top_n: int = Field(default=50, ge=1, le=500)


class Opportunity(Contract):
    price: float
    score: float
    score_yield: float
    score_assignment: float
    score_liquidity: float
    score_volatility: float
    score_dividend: float


class OpportunitiesResponse(BaseModel):
    scanned: int
    matched: int
    results: list[Opportunity]

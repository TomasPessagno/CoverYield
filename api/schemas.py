"""Request and response models for the CoverYield API.

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
    days_to_expiry: int = Field(description="Calendar days until expiry (0 = expires today)")
    years_to_expiry: float = Field(
        description="Time until the 4pm New York close on the expiry date, in years (T)"
    )
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
    iv_pct: float | None = Field(
        description="Implied volatility in percent, solved from the bid/ask mid "
        "(null when no volatility explains the quote)"
    )
    yahoo_iv_pct: float = Field(description="The data source's own implied volatility, in percent")
    assignment_prob: float | None = Field(
        description="N(d2): Black-Scholes probability the stock finishes above the strike"
    )
    delta: float | None = Field(description="Call price change per $1 stock move, per share")
    gamma: float | None = Field(description="Delta change per $1 stock move")
    theta_per_day: float | None = Field(
        description="Call price change per calendar day, per share (negative)"
    )
    vega: float | None = Field(
        description="Call price change per 1 percentage point of volatility, per share"
    )
    rho: float | None = Field(
        description="Call price change per 1 percentage point of interest rate, per share"
    )
    model_price: float | None = Field(
        description="Black-Scholes price at our IV (equals the mid by construction)"
    )
    yahoo_model_price: float | None = Field(
        description="Black-Scholes price at the data source's IV, for comparison"
    )
    d1: float | None
    d2: float | None


class AppConfig(BaseModel):
    mode: str = Field(description='"local" or "hosted"')
    refresh_cooldown_seconds: float = Field(
        description="Minimum time between live refreshes of the same ticker (0 = no limit)"
    )
    shared_store: bool = Field(description="Chains are stored in Redis rather than memory")


class ScreenerResponse(BaseModel):
    ticker: str
    price: float
    open_price: float
    as_of: datetime = Field(description="When this ticker's data was fetched from the source")
    refreshed: bool = Field(description="The data was fetched live for this request")
    stale: bool = Field(description="A live fetch failed, so this is the last good copy")
    next_refresh_at: datetime | None = Field(
        description="When a live refresh is allowed again (null = now)"
    )
    risk_free_rate: float = Field(description="Annual rate used in the Black-Scholes formulas")
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
    risk_free_rate: float = Field(description="Annual rate used in the Black-Scholes formulas")
    scanned: int
    matched: int
    oldest_data_at: datetime | None = Field(
        description="Fetch time of the oldest ticker data used in the ranking"
    )
    results: list[Opportunity]

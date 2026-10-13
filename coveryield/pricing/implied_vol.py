"""Implied volatility: the sigma that makes Black-Scholes match a market price.

Black-Scholes can't be rearranged to give sigma directly, so we search. The call
price rises with volatility (vega > 0), which makes the search well behaved:

* Newton's method: next = sigma - (model price - market price) / vega. Usually
  converges in 2-4 steps.
* Bisection fallback: we keep a bracket [lo, hi] that must contain the answer.
  Whenever a Newton step would leave it (vega near zero, far from the money),
  we take the bracket's midpoint instead. Each fallback step halves the bracket,
  so the search always converges.
"""

from __future__ import annotations

import math

from coveryield.pricing.black_scholes import DEFAULT_RISK_FREE_RATE, call_greeks

IV_MIN = 1e-4  # 0.01%
IV_MAX = 5.0  # 500%
INITIAL_GUESS = 0.30
MAX_ITERATIONS = 100
PRICE_TOLERANCE = 1e-8  # dollars per share
VOL_TOLERANCE = 1e-10


def _price(spot: float, strike: float, t_years: float, iv: float, r: float, q: float) -> float:
    greeks = call_greeks(spot, strike, t_years, iv, r, q)
    assert greeks is not None  # inputs were validated by the caller
    return greeks.price


def implied_vol(
    price: float,
    spot: float,
    strike: float,
    t_years: float,
    r: float = DEFAULT_RISK_FREE_RATE,
    q: float = 0.0,
) -> float | None:
    """
    The volatility (decimal, e.g. 0.277) at which Black-Scholes prices a call at ``price``.

    Returns None when no volatility in [IV_MIN, IV_MAX] reproduces the price:
    degenerate inputs, or a quote outside what any volatility can produce (for
    example a price below the call's no-arbitrage minimum, or above the stock).
    """
    values = (price, spot, strike, t_years, r, q)
    if not all(math.isfinite(v) for v in values):
        return None
    if price <= 0 or spot <= 0 or strike <= 0 or t_years <= 0:
        return None

    lo, hi = IV_MIN, IV_MAX
    # Since the price rises with volatility, these are the cheapest and dearest
    # prices any volatility in range can produce. The tolerance absorbs rounding
    # noise when a quote sits right at a bound (e.g. a deep ITM call at low vol).
    floor = _price(spot, strike, t_years, lo, r, q)
    ceiling = _price(spot, strike, t_years, hi, r, q)
    if not floor - PRICE_TOLERANCE <= price <= ceiling + PRICE_TOLERANCE:
        return None

    sigma = INITIAL_GUESS
    for _ in range(MAX_ITERATIONS):
        greeks = call_greeks(spot, strike, t_years, sigma, r, q)
        assert greeks is not None
        diff = greeks.price - price
        if abs(diff) < PRICE_TOLERANCE:
            return sigma

        # The answer lies on the side where the model price crosses the market price.
        if diff > 0:
            hi = sigma
        else:
            lo = sigma
        if hi - lo < VOL_TOLERANCE:
            return sigma

        step = sigma - diff / greeks.vega if greeks.vega > 0 else math.nan
        sigma = step if lo < step < hi else (lo + hi) / 2

    return sigma

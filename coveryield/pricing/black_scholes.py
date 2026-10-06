"""Black-Scholes pricing helpers.

Today this covers call delta, which the scanner uses as the approximate
probability that a call finishes in the money (i.e. that shares get called
away). The other Greeks and an implied-volatility solver will live here too.
"""

from __future__ import annotations

import math

DEFAULT_RISK_FREE_RATE = 0.045


def norm_cdf(x: float) -> float:
    """Standard normal CDF via erf, which avoids a scipy dependency."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def call_delta(
    spot: float,
    strike: float,
    t_years: float,
    iv: float,
    r: float = DEFAULT_RISK_FREE_RATE,
) -> float | None:
    """
    Call delta = N(d1), which also approximates the risk-neutral probability
    that the option finishes in-the-money, i.e. the probability of assignment.

    Args:
        spot:    current stock price
        strike:  option strike
        t_years: time to expiry in years
        iv:      implied volatility as a DECIMAL (0.35, not 35)
        r:       risk-free rate (annual, decimal)

    Returns:
        delta in [0, 1], or None if inputs are degenerate.
    """
    if spot <= 0 or strike <= 0 or t_years <= 0 or iv <= 0:
        return None
    try:
        d1 = (math.log(spot / strike) + (r + 0.5 * iv * iv) * t_years) / (iv * math.sqrt(t_years))
        return norm_cdf(d1)
    except (ValueError, ZeroDivisionError):
        return None

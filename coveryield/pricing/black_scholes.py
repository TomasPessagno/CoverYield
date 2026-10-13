"""Black-Scholes-Merton pricing for European calls: price, Greeks and probability.

The model takes five market inputs (stock price S, strike K, time to expiry T in
years, volatility sigma, risk-free rate r) plus a continuous dividend yield q:

    d1 = (ln(S/K) + (r - q + sigma^2 / 2) T) / (sigma sqrt(T))
    d2 = d1 - sigma sqrt(T)
    C  = S e^(-qT) N(d1) - K e^(-rT) N(d2)

Each Greek is a partial derivative of C. They are returned in textbook units
(theta per year, vega and rho per 1.00 change in sigma or r); callers convert
to per-day and per-percentage-point figures for display.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

DEFAULT_RISK_FREE_RATE = 0.045


def norm_cdf(x: float) -> float:
    """Standard normal CDF via erf, which avoids a scipy dependency."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_pdf(x: float) -> float:
    """Standard normal density: the height of the bell curve at x."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


@dataclass(frozen=True)
class CallGreeks:
    """A European call's model price, Greeks and probability of finishing ITM."""

    price: float  # C
    delta: float  # dC/dS
    gamma: float  # d^2C/dS^2
    theta: float  # dC/dt, per year (negative: the call loses value as time passes)
    vega: float  # dC/dsigma, per 1.00 of volatility
    rho: float  # dC/dr, per 1.00 of interest rate
    prob_itm: float  # N(d2): risk-neutral probability that S_T > K
    d1: float
    d2: float


def call_greeks(
    spot: float,
    strike: float,
    t_years: float,
    iv: float,
    r: float = DEFAULT_RISK_FREE_RATE,
    q: float = 0.0,
) -> CallGreeks | None:
    """
    Black-Scholes-Merton price and Greeks of a European call.

    Args:
        spot:    current stock price
        strike:  option strike
        t_years: time to expiry in years
        iv:      implied volatility as a DECIMAL (0.35, not 35)
        r:       risk-free rate (annual, decimal)
        q:       continuous dividend yield (annual, decimal)

    Returns:
        CallGreeks, or None if inputs are degenerate (non-positive price,
        strike, time or volatility).
    """
    if spot <= 0 or strike <= 0 or t_years <= 0 or iv <= 0:
        return None
    try:
        sqrt_t = math.sqrt(t_years)
        vol_t = iv * sqrt_t  # one "typical move" over the option's life
        d1 = (math.log(spot / strike) + (r - q + 0.5 * iv * iv) * t_years) / vol_t
        d2 = d1 - vol_t
    except (ValueError, ZeroDivisionError, OverflowError):
        return None

    disc_q = math.exp(-q * t_years)  # dividends the stock pays out before expiry
    disc_r = math.exp(-r * t_years)  # today's value of $1 paid at expiry
    nd1, nd2 = norm_cdf(d1), norm_cdf(d2)
    pdf_d1 = norm_pdf(d1)

    return CallGreeks(
        price=spot * disc_q * nd1 - strike * disc_r * nd2,
        delta=disc_q * nd1,
        gamma=disc_q * pdf_d1 / (spot * vol_t),
        theta=(
            -spot * disc_q * pdf_d1 * iv / (2.0 * sqrt_t)
            - r * strike * disc_r * nd2
            + q * spot * disc_q * nd1
        ),
        vega=spot * disc_q * pdf_d1 * sqrt_t,
        rho=strike * t_years * disc_r * nd2,
        prob_itm=nd2,
        d1=d1,
        d2=d2,
    )


def call_delta(
    spot: float,
    strike: float,
    t_years: float,
    iv: float,
    r: float = DEFAULT_RISK_FREE_RATE,
) -> float | None:
    """Call delta, N(d1): how much the call moves per $1 the stock moves."""
    greeks = call_greeks(spot, strike, t_years, iv, r)
    return None if greeks is None else greeks.delta

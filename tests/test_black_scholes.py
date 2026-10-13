import math
from collections.abc import Callable

import pytest
from hypothesis import given
from hypothesis import strategies as st

from coveryield.pricing.black_scholes import call_delta, call_greeks, norm_cdf, norm_pdf

# --- Normal distribution helpers -------------------------------------------------


def test_norm_cdf_known_values() -> None:
    assert norm_cdf(0.0) == pytest.approx(0.5)
    assert norm_cdf(1.96) == pytest.approx(0.9750, abs=1e-4)
    assert norm_cdf(-1.96) == pytest.approx(0.0250, abs=1e-4)


def test_norm_pdf_known_values() -> None:
    assert norm_pdf(0.0) == pytest.approx(0.398942, abs=1e-6)
    assert norm_pdf(1.0) == pytest.approx(0.241971, abs=1e-6)
    assert norm_pdf(-1.0) == norm_pdf(1.0)


# --- Textbook values (Hull, Options, Futures, and Other Derivatives) ---------------


def test_call_price_textbook_case() -> None:
    # Hull Example 15.6: S=42, K=40, r=10%, sigma=20%, T=0.5 -> c = 4.76
    g = call_greeks(42, 40, 0.5, 0.20, r=0.10)
    assert g is not None
    assert g.d1 == pytest.approx(0.7693, abs=1e-4)
    assert g.d2 == pytest.approx(0.6278, abs=1e-4)
    assert g.price == pytest.approx(4.76, abs=5e-3)


def test_call_greeks_textbook_case() -> None:
    # Hull's running Greeks example: S=49, K=50, r=5%, sigma=20%, T=20 weeks
    g = call_greeks(49, 50, 20 / 52, 0.20, r=0.05)
    assert g is not None
    assert g.delta == pytest.approx(0.522, abs=5e-4)
    assert g.gamma == pytest.approx(0.066, abs=5e-4)
    assert g.theta == pytest.approx(-4.31, abs=5e-3)  # per year
    assert g.vega == pytest.approx(12.1, abs=5e-2)  # per 1.00 of volatility
    assert g.rho == pytest.approx(8.91, abs=5e-3)  # per 1.00 of interest rate


def test_call_delta_textbook_case() -> None:
    # S=100, K=100, T=1y, r=5%, sigma=20% -> d1 = 0.35, N(0.35) = 0.6368
    assert call_delta(100, 100, 1.0, 0.20, r=0.05) == pytest.approx(0.6368, abs=1e-4)


def test_deep_itm_and_otm() -> None:
    deep_itm = call_greeks(200, 100, 0.1, 0.2)
    deep_otm = call_greeks(50, 100, 0.1, 0.2)
    assert deep_itm is not None and deep_otm is not None
    assert deep_itm.delta == pytest.approx(1.0, abs=1e-6)
    assert deep_itm.prob_itm == pytest.approx(1.0, abs=1e-6)
    assert deep_otm.delta == pytest.approx(0.0, abs=1e-6)
    assert deep_otm.price == pytest.approx(0.0, abs=1e-6)


@pytest.mark.parametrize(
    "spot,strike,t,iv",
    [(0, 100, 1, 0.2), (100, 0, 1, 0.2), (100, 100, 0, 0.2), (100, 100, 1, 0), (-1, 100, 1, 0.2)],
)
def test_degenerate_inputs_return_none(spot: float, strike: float, t: float, iv: float) -> None:
    assert call_greeks(spot, strike, t, iv) is None
    assert call_delta(spot, strike, t, iv) is None


# --- Properties that must hold for any valid inputs --------------------------------

spots = st.floats(min_value=1.0, max_value=1_000.0)
moneyness = st.floats(min_value=0.5, max_value=2.0)  # strike / spot
years = st.floats(min_value=7 / 365, max_value=3.0)
vols = st.floats(min_value=0.05, max_value=1.5)
rates = st.floats(min_value=0.0, max_value=0.10)
yields = st.floats(min_value=0.0, max_value=0.08)


@given(spot=spots, m=moneyness, t=years, iv=vols, r=rates, q=yields)
def test_price_stays_within_no_arbitrage_bounds(
    spot: float, m: float, t: float, iv: float, r: float, q: float
) -> None:
    # A call is worth at least what exercising a forward would give, and never
    # more than the (dividend-adjusted) stock itself.
    strike = spot * m
    g = call_greeks(spot, strike, t, iv, r, q)
    assert g is not None
    upper = spot * math.exp(-q * t)
    lower = max(upper - strike * math.exp(-r * t), 0.0)
    tol = 1e-9 * spot
    assert lower - tol <= g.price <= upper + tol


@given(spot=spots, m=moneyness, t=years, iv=vols, r=rates, q=yields)
def test_greeks_have_the_right_signs(
    spot: float, m: float, t: float, iv: float, r: float, q: float
) -> None:
    g = call_greeks(spot, spot * m, t, iv, r, q)
    assert g is not None
    assert 0.0 <= g.delta <= 1.0
    assert 0.0 <= g.prob_itm <= 1.0
    assert g.gamma >= 0.0
    assert g.vega >= 0.0
    assert g.rho >= 0.0


@given(spot=spots, m=moneyness, t=years, iv=vols, r=rates)
def test_probability_itm_is_below_delta_without_dividends(
    spot: float, m: float, t: float, iv: float, r: float
) -> None:
    # d2 = d1 - sigma sqrt(T) < d1, so N(d2) < N(d1): delta overstates the odds.
    g = call_greeks(spot, spot * m, t, iv, r)
    assert g is not None
    assert g.prob_itm <= g.delta + 1e-12


@given(spot=spots, m=moneyness, t=years, iv=vols)
def test_price_rises_with_volatility(spot: float, m: float, t: float, iv: float) -> None:
    low = call_greeks(spot, spot * m, t, iv)
    high = call_greeks(spot, spot * m, t, iv * 1.1)
    assert low is not None and high is not None
    assert high.price >= low.price - 1e-9 * spot


@given(spot=spots, m=moneyness, t=years, iv=vols, r=rates, q=yields)
def test_dividend_yield_equals_a_lower_spot(
    spot: float, m: float, t: float, iv: float, r: float, q: float
) -> None:
    # Merton: a stock paying yield q prices like a non-paying stock at S e^(-qT).
    strike = spot * m
    with_q = call_greeks(spot, strike, t, iv, r, q)
    shifted = call_greeks(spot * math.exp(-q * t), strike, t, iv, r)
    assert with_q is not None and shifted is not None
    assert with_q.price == pytest.approx(shifted.price, rel=1e-9, abs=1e-9 * spot)


# --- Each Greek is a derivative: check it against a nudge-and-reprice ------------

PriceFn = Callable[[float], float]


def central_difference(f: PriceFn, x: float, h: float) -> float:
    return (f(x + h) - f(x - h)) / (2 * h)


def price(spot: float, strike: float, t: float, iv: float, r: float, q: float) -> float:
    g = call_greeks(spot, strike, t, iv, r, q)
    assert g is not None
    return g.price


@given(spot=spots, m=moneyness, t=years, iv=vols, r=rates, q=yields)
def test_greeks_match_finite_differences(
    spot: float, m: float, t: float, iv: float, r: float, q: float
) -> None:
    strike = spot * m
    g = call_greeks(spot, strike, t, iv, r, q)
    assert g is not None

    hs = spot * 1e-4
    num_delta = central_difference(lambda s: price(s, strike, t, iv, r, q), spot, hs)
    num_gamma = central_difference(
        lambda s: price(s + hs, strike, t, iv, r, q) - price(s - hs, strike, t, iv, r, q),
        spot,
        hs,
    ) / (2 * hs)
    # Theta is the change as calendar time passes, i.e. as T shrinks.
    num_theta = -central_difference(lambda tt: price(spot, strike, tt, iv, r, q), t, 1e-5)
    num_vega = central_difference(lambda v: price(spot, strike, t, v, r, q), iv, 1e-5)
    num_rho = central_difference(lambda rr: price(spot, strike, t, iv, rr, q), r, 1e-5)

    assert g.delta == pytest.approx(num_delta, rel=1e-4, abs=1e-6)
    assert g.gamma == pytest.approx(num_gamma, rel=1e-2, abs=1e-5 / spot)
    assert g.theta == pytest.approx(num_theta, rel=1e-4, abs=1e-5 * spot)
    assert g.vega == pytest.approx(num_vega, rel=1e-4, abs=1e-5 * spot)
    assert g.rho == pytest.approx(num_rho, rel=1e-4, abs=1e-5 * spot)

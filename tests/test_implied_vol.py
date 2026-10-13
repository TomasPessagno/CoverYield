import math

import pytest
from hypothesis import assume, example, given
from hypothesis import strategies as st

from coveryield.pricing.black_scholes import call_greeks
from coveryield.pricing.implied_vol import IV_MAX, IV_MIN, implied_vol


def price(
    spot: float, strike: float, t: float, iv: float, r: float = 0.045, q: float = 0.0
) -> float:
    g = call_greeks(spot, strike, t, iv, r, q)
    assert g is not None
    return g.price


def test_textbook_case() -> None:
    # Hull Example 15.6: c = 4.759 at S=42, K=40, r=10%, T=0.5 -> sigma = 20%
    assert implied_vol(4.759422392871528, 42, 40, 0.5, r=0.10) == pytest.approx(0.20, abs=1e-8)


def test_short_dated_aapl_example() -> None:
    # A call expiring tomorrow: the market mid of $1.30 implies ~27.7% volatility.
    iv = implied_vol(1.30, 343.13, 345, 1.10 / 365)
    assert iv == pytest.approx(0.2769, abs=1e-4)
    assert price(343.13, 345, 1.10 / 365, iv or 0) == pytest.approx(1.30, abs=1e-6)


def test_far_from_the_money_uses_the_fallback() -> None:
    # Deep OTM: vega is tiny, so plain Newton would jump wildly. Must still converge.
    target = price(100, 160, 0.1, 0.9)
    iv = implied_vol(target, 100, 160, 0.1)
    assert iv == pytest.approx(0.9, rel=1e-6)


@pytest.mark.parametrize(
    "quote,spot,strike,t",
    [
        (0.0, 100, 100, 0.5),  # no price
        (-1.0, 100, 100, 0.5),
        (1.0, 0, 100, 0.5),  # degenerate inputs
        (1.0, 100, 0, 0.5),
        (1.0, 100, 100, 0),
        (math.nan, 100, 100, 0.5),
        (101.0, 100, 100, 0.5),  # above the stock price: impossible for a call
        (19.0, 120, 100, 0.5),  # below the ~$22 a 120-stock / 100-strike call must be worth
    ],
)
def test_impossible_quotes_return_none(quote: float, spot: float, strike: float, t: float) -> None:
    assert implied_vol(quote, spot, strike, t) is None


spots = st.floats(min_value=5.0, max_value=1_000.0)
moneyness = st.floats(min_value=0.6, max_value=1.6)  # strike / spot
years = st.floats(min_value=0.5 / 365, max_value=3.0)
vols = st.floats(min_value=0.03, max_value=3.0)
rates = st.floats(min_value=0.0, max_value=0.10)
yields = st.floats(min_value=0.0, max_value=0.08)


@given(spot=spots, m=moneyness, t=years, iv=vols, r=rates, q=yields)
# Found by Hypothesis: deep ITM at low vol, where the price sits at the floor up to rounding.
@example(spot=5.0, m=0.6015625, t=1.21875, iv=0.06510835247057027, r=0.0625, q=0.0)
def test_round_trip_recovers_the_price_and_the_volatility(
    spot: float, m: float, t: float, iv: float, r: float, q: float
) -> None:
    strike = spot * m
    g = call_greeks(spot, strike, t, iv, r, q)
    assert g is not None
    # Skip quotes too small to carry information (a fraction of a cent per share).
    assume(g.price > 1e-4)

    solved = implied_vol(g.price, spot, strike, t, r, q)
    assert solved is not None
    assert IV_MIN <= solved <= IV_MAX
    # Repricing at the solved volatility reproduces the market price...
    assert price(spot, strike, t, solved, r, q) == pytest.approx(g.price, abs=1e-7)
    # ...and wherever the price is sensitive to volatility, the volatility itself.
    if g.vega > 1e-3 * spot:
        assert solved == pytest.approx(iv, rel=1e-5)

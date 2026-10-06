import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from coveryield.pricing.black_scholes import call_delta, norm_cdf


def test_norm_cdf_known_values() -> None:
    assert norm_cdf(0.0) == pytest.approx(0.5)
    assert norm_cdf(1.96) == pytest.approx(0.9750, abs=1e-4)
    assert norm_cdf(-1.96) == pytest.approx(0.0250, abs=1e-4)


def test_call_delta_textbook_case() -> None:
    # S=100, K=100, T=1y, r=5%, sigma=20% -> d1 = 0.35, N(0.35) = 0.6368
    assert call_delta(100, 100, 1.0, 0.20, r=0.05) == pytest.approx(0.6368, abs=1e-4)


def test_call_delta_deep_itm_and_otm() -> None:
    assert call_delta(200, 100, 0.1, 0.2) == pytest.approx(1.0, abs=1e-6)
    assert call_delta(50, 100, 0.1, 0.2) == pytest.approx(0.0, abs=1e-6)


@pytest.mark.parametrize(
    "spot,strike,t,iv",
    [(0, 100, 1, 0.2), (100, 0, 1, 0.2), (100, 100, 0, 0.2), (100, 100, 1, 0), (-1, 100, 1, 0.2)],
)
def test_call_delta_degenerate_inputs_return_none(
    spot: float, strike: float, t: float, iv: float
) -> None:
    assert call_delta(spot, strike, t, iv) is None


prices = st.floats(min_value=1.0, max_value=1_000.0)
years = st.floats(min_value=1 / 365, max_value=3.0)
vols = st.floats(min_value=0.01, max_value=3.0)


@given(spot=prices, strike=prices, t=years, iv=vols)
def test_call_delta_is_a_probability(spot: float, strike: float, t: float, iv: float) -> None:
    delta = call_delta(spot, strike, t, iv)
    assert delta is not None
    assert 0.0 <= delta <= 1.0


@given(spot=prices, strike=prices, t=years, iv=vols)
def test_call_delta_falls_as_strike_rises(spot: float, strike: float, t: float, iv: float) -> None:
    lower = call_delta(spot, strike, t, iv)
    higher = call_delta(spot, strike * 1.05, t, iv)
    assert lower is not None and higher is not None
    assert higher <= lower + 1e-12


def test_call_delta_matches_finite_difference_of_price() -> None:
    # Delta is dPrice/dSpot; check against a central difference of the BS call price.
    def bs_call(
        s: float, k: float = 100, t: float = 0.5, sigma: float = 0.3, r: float = 0.045
    ) -> float:
        d1 = (math.log(s / k) + (r + 0.5 * sigma**2) * t) / (sigma * math.sqrt(t))
        d2 = d1 - sigma * math.sqrt(t)
        return s * norm_cdf(d1) - k * math.exp(-r * t) * norm_cdf(d2)

    h = 1e-4
    numeric = (bs_call(105 + h) - bs_call(105 - h)) / (2 * h)
    assert call_delta(105, 100, 0.5, 0.3) == pytest.approx(numeric, abs=1e-6)

import pandas as pd
import pytest
from hypothesis import given
from hypothesis import strategies as st

from coveryield.screening.scoring import (
    DEFAULT_WEIGHTS,
    compute_opportunity_score,
    normalize_weights,
    rank_opportunities,
)


def contracts(**overrides: list[float]) -> pd.DataFrame:
    base: dict[str, list[float]] = {
        "Static Return %": [2.0, 1.0],
        "Annualized Return %": [24.0, 12.0],
        "Assignment Prob": [0.3, 0.3],
        "Open Interest": [500, 500],
        "Volume": [200, 200],
        "Spread": [0.05, 0.05],
        "IV": [30.0, 30.0],
    }
    base.update(overrides)
    return pd.DataFrame(base)


def test_normalize_weights_sums_to_one() -> None:
    w = normalize_weights(DEFAULT_WEIGHTS, 0.7)
    assert sum(w[k] for k in ("yield", "assign", "liq", "vol", "div")) == pytest.approx(1.0)
    assert w["yield"] == pytest.approx(0.4)
    assert w["yield_actual_frac"] == 0.7


def test_normalize_weights_all_zero_does_not_divide_by_zero() -> None:
    w = normalize_weights({"yield": 0, "assign": 0, "liq": 0, "vol": 0, "div": 0})
    assert w["yield"] == 0


def test_higher_yield_scores_higher() -> None:
    scored = compute_opportunity_score(contracts(), normalize_weights(DEFAULT_WEIGHTS))
    assert scored["Opportunity Score"][0] > scored["Opportunity Score"][1]


def test_higher_assignment_risk_scores_lower() -> None:
    df = contracts(**{"Static Return %": [2.0, 2.0], "Annualized Return %": [24.0, 24.0]})
    df["Assignment Prob"] = [0.2, 0.6]
    scored = compute_opportunity_score(df, normalize_weights(DEFAULT_WEIGHTS))
    assert scored["Opportunity Score"][0] > scored["Opportunity Score"][1]


def test_missing_delta_counts_as_coin_flip() -> None:
    df = contracts()
    df["Assignment Prob"] = [None, 0.5]
    scored = compute_opportunity_score(df, normalize_weights(DEFAULT_WEIGHTS))
    assert scored["s_assign"][0] == pytest.approx(50.0)


def test_rank_opportunities_orders_and_truncates() -> None:
    scored = compute_opportunity_score(
        contracts(**{"Static Return %": [1.0, 3.0], "Annualized Return %": [12.0, 36.0]}),
        normalize_weights(DEFAULT_WEIGHTS),
    )
    top = rank_opportunities(scored, 1)
    assert len(top) == 1
    assert top["Static Return %"].iloc[0] == 3.0


@given(
    static=st.floats(0, 50),
    annual=st.floats(0, 500),
    delta=st.floats(0, 1),
    oi=st.integers(0, 100_000),
    vol=st.integers(0, 100_000),
    spread=st.floats(0, 10),
    iv=st.floats(0, 300),
    weights=st.lists(st.floats(0, 100), min_size=5, max_size=5),
    frac=st.floats(0, 1),
)
def test_score_is_always_between_0_and_100(
    static: float,
    annual: float,
    delta: float,
    oi: int,
    vol: int,
    spread: float,
    iv: float,
    weights: list[float],
    frac: float,
) -> None:
    df = pd.DataFrame(
        {
            "Static Return %": [static],
            "Annualized Return %": [annual],
            "Assignment Prob": [delta],
            "Open Interest": [oi],
            "Volume": [vol],
            "Spread": [spread],
            "IV": [iv],
        }
    )
    raw = dict(zip(("yield", "assign", "liq", "vol", "div"), weights, strict=True))
    w = normalize_weights(raw, frac)
    score = compute_opportunity_score(df, w)["Opportunity Score"].iloc[0]
    assert -1e-9 <= score <= 100 + 1e-9

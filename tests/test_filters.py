from datetime import datetime

import pandas as pd
import pytest

from coveryield.screening.filters import (
    add_contract_metrics,
    filter_by_goals,
    filter_by_strike_and_return,
    filter_calls,
)
from tests.conftest import make_calls


def test_filter_calls_keeps_expiry_window(now: datetime) -> None:
    calls = make_calls([{"strike": 105, "days": d} for d in (3, 10.5, 30.5, 60)])
    out = filter_calls("TEST", 100.0, calls, 7, 42, now=now)
    assert sorted(out["contractSymbol"]) == ["TEST0001", "TEST0002"]


def test_filter_calls_drops_deep_itm_and_puts(now: datetime) -> None:
    calls = make_calls(
        [
            {"strike": 85, "days": 20},  # below 90% of spot -> dropped
            {"strike": 90, "days": 20},  # exactly 90% -> kept
            {"strike": 110, "days": 20, "optionType": "put"},  # not a call -> dropped
        ]
    )
    out = filter_calls("TEST", 100.0, calls, 7, 42, now=now)
    assert list(out["Strike"]) == [90]


def test_filter_calls_pricing_columns(now: datetime) -> None:
    calls = make_calls([{"strike": 105, "days": 30, "bid": 2.0, "ask": 2.2}])
    row = filter_calls("TEST", 100.0, calls, 7, 42, now=now).iloc[0]
    assert row["MidPrice"] == pytest.approx(2.1)
    assert row["Spread"] == pytest.approx(0.2)
    assert row["Static Return %"] == pytest.approx(2.0)  # 2 / 100, uses the bid
    assert row["Ticker"] == "TEST"


def test_filter_calls_missing_quotes_become_zero(now: datetime) -> None:
    calls = make_calls([{"strike": 105, "days": 30}])
    calls["bid"] = None
    row = filter_calls("TEST", 100.0, calls, 7, 42, now=now).iloc[0]
    assert row["BidPrice"] == 0
    assert row["Static Return %"] == 0


def test_filter_calls_empty_input() -> None:
    assert filter_calls("TEST", 100.0, pd.DataFrame(), 7, 42).empty


def test_add_contract_metrics_worked_example(now: datetime) -> None:
    # The textbook example: $100 stock, $105 strike, $2 premium, 30 days.
    calls = make_calls([{"strike": 105, "days": 30.5, "bid": 2.0, "iv": 0.25}])
    df = filter_calls("TEST", 100.0, calls, 7, 42, now=now)
    row = add_contract_metrics(df, 100.0, now=now).iloc[0]
    assert row["Days to Expiry"] == 30
    assert row["Annualized Return %"] == pytest.approx(2.0 * 365 / 30)
    assert row["Distance to Strike %"] == pytest.approx(5.0)
    assert row["Breakeven Price"] == pytest.approx(98.0)
    assert row["IV"] == pytest.approx(25.0)


def test_annualized_return_is_zero_at_expiry(now: datetime) -> None:
    calls = make_calls([{"strike": 105, "days": 0.5, "bid": 1.0}])
    df = filter_calls("TEST", 100.0, calls, 0, 42, now=now)
    row = add_contract_metrics(df, 100.0, now=now).iloc[0]
    assert row["Days to Expiry"] == 0
    assert row["Annualized Return %"] == 0.0


def test_filter_by_strike_and_return(now: datetime) -> None:
    calls = make_calls(
        [
            {"strike": 100, "days": 30.5, "bid": 3.0},
            {"strike": 105, "days": 30.5, "bid": 2.0},
            {"strike": 115, "days": 30.5, "bid": 0.5},  # beyond +$10 offset
            {"strike": 104, "days": 30.5, "bid": 0.2},  # static return too low
        ]
    )
    df = add_contract_metrics(filter_calls("TEST", 100.0, calls, 7, 42, now=now), 100.0, now=now)
    out = filter_by_strike_and_return(df, 100.0, 0, 10, 1.0, 0)
    assert sorted(out["Strike"]) == [100, 105]


def test_filter_by_goals(now: datetime) -> None:
    calls = make_calls(
        [
            {"strike": 105, "days": 30.5, "bid": 2.0},  # 5% OTM, 2% return: kept
            {"strike": 101, "days": 30.5, "bid": 2.0},  # only 1% OTM
            {"strike": 105, "days": 80.5, "bid": 2.0},  # too far out
            {"strike": 110, "days": 30.5, "bid": 0.5},  # return too low
        ]
    )
    df = add_contract_metrics(filter_calls("TEST", 100.0, calls, 1, 120, now=now), 100.0, now=now)
    out = filter_by_goals(df, min_static_return=1.0, max_days_to_expiry=45, min_otm_pct=2.0)
    assert list(out["contractSymbol"]) == ["TEST0000"]

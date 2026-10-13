from datetime import datetime, timedelta

import pandas as pd
import pytest

from coveryield.screening.filters import (
    GREEK_COLUMNS,
    add_contract_metrics,
    add_greeks,
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
    calls = make_calls([{"strike": 105, "days": 30, "bid": 2.0, "iv": 0.25}])
    df = filter_calls("TEST", 100.0, calls, 7, 42, now=now)
    row = add_contract_metrics(df, 100.0, now=now).iloc[0]
    assert row["Days to Expiry"] == 30
    assert row["Years to Expiry"] == pytest.approx((30 + 4 / 24) / 365)  # to the 4pm close
    assert row["Annualized Return %"] == pytest.approx(2.0 * 365 / 30)
    assert row["Distance to Strike %"] == pytest.approx(5.0)
    assert row["Breakeven Price"] == pytest.approx(98.0)
    assert row["Yahoo IV"] == pytest.approx(25.0)


def test_annualized_return_is_zero_at_expiry(now: datetime) -> None:
    calls = make_calls([{"strike": 105, "days": 0, "bid": 1.0}])
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


def test_days_to_expiry_counts_calendar_days(now: datetime) -> None:
    # At noon, a contract expiring tomorrow is 1 day out and has ~1.17 days to the close.
    calls = make_calls([{"strike": 105, "days": 1}, {"strike": 105, "days": 3}])
    row = add_contract_metrics(filter_calls("TEST", 100.0, calls, 0, 42, now=now), 100.0, now=now)
    assert list(row["Days to Expiry"]) == [1, 3]
    assert row["Years to Expiry"].iloc[0] == pytest.approx((1 + 4 / 24) / 365)


def test_add_greeks_skips_quotes_no_volatility_can_explain(now: datetime) -> None:
    calls = make_calls(
        [
            {"strike": 105, "days": 30, "bid": 2.0, "ask": 2.2},  # fine
            {"strike": 105, "days": 30, "bid": 2.2, "ask": 2.0},  # crossed market
            {"strike": 105, "days": 30, "bid": 0.0, "ask": 0.5},  # no bid
            {"strike": 90, "days": 30, "bid": 5.0, "ask": 5.2},  # below the ~$10 minimum
        ]
    )
    df = add_contract_metrics(filter_calls("TEST", 100.0, calls, 0, 42, now=now), 100.0, now=now)
    out = add_greeks(df, 100.0)
    assert out["IV"].iloc[0] > 0
    assert out["IV"].iloc[1:].isna().all()
    for column in GREEK_COLUMNS:
        assert out[column].iloc[0] is not None
        assert out[column].iloc[1:].isna().all()


def test_stored_quotes_are_priced_from_when_they_were_taken(now: datetime) -> None:
    # A quote captured 3 days ago on an option expiring in 4 days had 4 days left
    # when it was priced; today's calendar still shows 4 days to expiry.
    calls = make_calls([{"strike": 105, "days": 4}])
    df = filter_calls("TEST", 100.0, calls, 0, 42, now=now)
    row = add_contract_metrics(df, 100.0, now=now, quoted_at=now - timedelta(days=3)).iloc[0]
    assert row["Days to Expiry"] == 4
    assert row["Years to Expiry"] == pytest.approx((7 + 4 / 24) / 365)

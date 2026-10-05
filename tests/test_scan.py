from datetime import datetime

import pandas as pd
import pytest

from tests.conftest import FakeProvider, make_calls
from thetascout.data.provider import CallChain
from thetascout.pricing.black_scholes import call_delta
from thetascout.screening.scan import scan_one_ticker, scan_universe


def chain(ticker: str, price: float = 100.0) -> CallChain:
    calls = make_calls(
        [
            {"strike": 105, "days": 30.5, "bid": 2.0, "iv": 0.30},
            {"strike": 110, "days": 30.5, "bid": 0.0},  # zero bid -> dropped
            {"strike": 105, "days": 0.5, "bid": 1.0},  # expires today -> dropped
        ]
    )
    return CallChain(ticker, price, price, calls)


def test_scan_one_ticker_enriches_and_gates(now: datetime) -> None:
    provider = FakeProvider({"AAA": chain("AAA")})
    out = scan_one_ticker("AAA", 0, 120, provider=provider, now=now)
    assert len(out) == 1
    row = out.iloc[0]
    assert row["Current Price"] == 100.0
    assert row["Days to Expiry"] == 30
    assert row["Assignment Prob"] == pytest.approx(call_delta(100.0, 105, 30 / 365, 0.30))


def test_scan_one_ticker_returns_empty_on_failure_or_no_data(now: datetime) -> None:
    provider = FakeProvider({}, failing={"BAD"})
    assert scan_one_ticker("BAD", 0, 120, provider=provider, now=now).empty
    assert scan_one_ticker("NONE", 0, 120, provider=provider, now=now).empty


def test_scan_universe_concatenates_and_reports_progress(now: datetime) -> None:
    provider = FakeProvider({"AAA": chain("AAA"), "BBB": chain("BBB", 50.0)}, failing={"BAD"})
    progress: list[tuple[float, str]] = []

    def scan_one(t: str, lo: int, hi: int) -> pd.DataFrame:
        return scan_one_ticker(t, lo, hi, provider=provider, now=now)

    out = scan_universe(
        ["AAA", "BAD", "BBB"],
        0,
        120,
        progress_cb=lambda f, t: progress.append((f, t)),
        scan_one=scan_one,
    )
    assert sorted(out["Ticker"]) == ["AAA", "BBB"]
    assert [t for _, t in progress] == ["AAA", "BAD", "BBB"]
    assert progress[-1][0] == pytest.approx(1.0)


def test_scan_universe_survives_exceptions() -> None:
    def explode(t: str, lo: int, hi: int) -> pd.DataFrame:
        raise RuntimeError("unexpected")

    assert scan_universe(["AAA"], 0, 120, scan_one=explode).empty

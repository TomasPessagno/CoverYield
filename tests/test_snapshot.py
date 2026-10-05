from datetime import UTC, datetime

import pandas as pd
import pytest

from api.snapshot import in_snapshot_window, run_snapshot
from tests.conftest import FakeProvider
from thetascout.data.provider import CallChain
from thetascout.data.store import MemoryStore


@pytest.mark.parametrize(
    "utc,expected",
    [
        (datetime(2026, 7, 6, 14, 5, tzinfo=UTC), True),  # Mon 10:05 EDT
        (datetime(2026, 7, 6, 13, 50, tzinfo=UTC), False),  # Mon 9:50 EDT, too early
        (datetime(2026, 7, 6, 20, 20, tzinfo=UTC), True),  # Mon 16:20 EDT, post-close run
        (datetime(2026, 7, 6, 21, 5, tzinfo=UTC), False),  # Mon 17:05 EDT, too late
        (datetime(2026, 1, 5, 15, 5, tzinfo=UTC), True),  # Mon 10:05 EST (winter time)
        (datetime(2026, 1, 5, 14, 5, tzinfo=UTC), False),  # Mon 9:05 EST
        (datetime(2026, 7, 4, 16, 0, tzinfo=UTC), False),  # Saturday
    ],
)
def test_snapshot_window_follows_new_york_time(utc: datetime, expected: bool) -> None:
    assert in_snapshot_window(utc) is expected


def chain(ticker: str) -> CallChain:
    return CallChain(ticker, 100.0, 99.0, pd.DataFrame({"contractSymbol": [f"{ticker}1"]}))


def test_run_snapshot_stores_each_ticker_and_reports_failures() -> None:
    provider = FakeProvider({"AAA": chain("AAA"), "BBB": chain("BBB")}, failing={"BAD"})
    store = MemoryStore()
    pauses: list[float] = []
    report = run_snapshot(
        ["AAA", "BAD", "BBB", "NONE"], provider, store, 1.5, sleep=pauses.append, log=lambda _: None
    )
    assert report.ok == ["AAA", "BBB"]
    assert report.failed == ["BAD", "NONE"]
    assert report.success_rate == 0.5
    assert store.get("AAA") is not None and store.get("NONE") is None
    assert pauses == [1.5, 1.5, 1.5]  # a pause between tickers, none before the first

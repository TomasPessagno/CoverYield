from datetime import UTC, datetime

from coveryield.market_time import to_market_time


def test_to_market_time_converts_utc_to_new_york_wall_time() -> None:
    # 19:28 UTC in October (daylight time) is 15:28 in New York.
    moment = datetime(2026, 10, 9, 19, 28, tzinfo=UTC)
    assert to_market_time(moment) == datetime(2026, 10, 9, 15, 28)


def test_to_market_time_leaves_naive_times_alone() -> None:
    naive = datetime(2026, 1, 5, 12, 0)
    assert to_market_time(naive) == naive

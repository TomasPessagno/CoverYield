"""Market clock: US option expiries are New York dates, settling at the 4pm close.

Naive datetimes throughout the package are New York wall time, which keeps
"days to expiry" the same wherever the code runs (a laptop, or a UTC server).
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

NEW_YORK = ZoneInfo("America/New_York")
MARKET_CLOSE = pd.Timedelta(hours=16)
SECONDS_PER_YEAR = 365 * 24 * 60 * 60


def market_now() -> datetime:
    """The current New York wall time, as a naive datetime."""
    return datetime.now(NEW_YORK).replace(tzinfo=None)


def days_to_expiry(expirations: pd.Series, now: datetime) -> pd.Series:
    """Calendar days from today to each expiry date (0 = expires today)."""
    days: pd.Series = (expirations.dt.normalize() - pd.Timestamp(now).normalize()).dt.days
    return days


def years_to_expiry(expirations: pd.Series, now: datetime) -> pd.Series:
    """Time left until each expiry's 4pm close, in years (365-day), floored at 0.

    This is the T in Black-Scholes. Counting to the close rather than whole days
    matters for short-dated options: a call expiring tomorrow has ~1.2 days left
    at noon, not 0 or 1.
    """
    close = expirations.dt.normalize() + MARKET_CLOSE
    seconds: pd.Series = (close - pd.Timestamp(now)).dt.total_seconds()
    return (seconds / SECONDS_PER_YEAR).clip(lower=0.0)

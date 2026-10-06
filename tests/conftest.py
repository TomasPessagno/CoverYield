from datetime import datetime, timedelta

import pandas as pd
import pytest

from coveryield.data.provider import CallChain, DataFetchError

NOW = datetime(2026, 1, 5, 12, 0, 0)


def make_calls(rows: list[dict[str, object]], now: datetime = NOW) -> pd.DataFrame:
    """A raw call chain in the shape a provider returns.

    Each row needs ``strike`` and ``days`` (days from ``now`` to expiry); other
    columns get sensible defaults.
    """
    records = []
    for i, row in enumerate(rows):
        records.append(
            {
                "contractSymbol": f"TEST{i:04d}",
                "strike": row["strike"],
                "bid": row.get("bid", 1.0),
                "ask": row.get("ask", 1.1),
                "volume": row.get("volume", 100),
                "openInterest": row.get("openInterest", 500),
                "impliedVolatility": row.get("iv", 0.30),
                "optionType": row.get("optionType", "call"),
                "expirationDate": now + timedelta(days=float(row["days"])),  # type: ignore[arg-type]
            }
        )
    return pd.DataFrame(records)


class FakeProvider:
    """In-memory MarketDataProvider for tests (no network)."""

    def __init__(self, chains: dict[str, CallChain], failing: set[str] | None = None) -> None:
        self.chains = chains
        self.failing = failing or set()

    def fetch_call_chain(self, ticker: str) -> CallChain:
        if ticker in self.failing:
            raise DataFetchError(f"boom: {ticker}")
        return self.chains.get(ticker, CallChain(ticker, 0.0, 0.0, pd.DataFrame()))

    def search_tickers(self, query: str) -> list[tuple[str, str]]:
        return []


@pytest.fixture
def now() -> datetime:
    return NOW

"""Market-data provider interface.

The screening code depends on this protocol rather than on yfinance directly,
so the data source can be swapped (or faked in tests) without touching the math.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import pandas as pd


class DataFetchError(Exception):
    """Raised when a provider fails unexpectedly (network error, bad response)."""


@dataclass(frozen=True)
class CallChain:
    """All listed call options for one ticker, plus the quote they were priced against.

    ``calls`` has one row per contract with at least ``contractSymbol``, ``strike``,
    ``bid``, ``ask``, ``volume``, ``openInterest``, ``impliedVolatility``,
    ``optionType`` and ``expirationDate`` (datetime64) columns. A chain with
    ``price == 0`` or empty ``calls`` means the provider had no usable data.
    """

    ticker: str
    price: float
    open_price: float
    calls: pd.DataFrame

    @property
    def is_empty(self) -> bool:
        return self.price <= 0 or self.calls.empty


class MarketDataProvider(Protocol):
    def fetch_call_chain(self, ticker: str) -> CallChain:
        """Return every listed call for ``ticker``. Raises DataFetchError on failure."""
        ...

    def search_tickers(self, query: str) -> list[tuple[str, str]]:
        """Return ``(display_label, symbol)`` matches for a free-text query."""
        ...

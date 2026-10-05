"""A time-based cache around any MarketDataProvider."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from thetascout.data.provider import CallChain, MarketDataProvider

DEFAULT_TTL_SECONDS = 600.0


class CachedProvider:
    """Caches call chains per ticker for ``ttl_seconds``.

    Option chains change slowly enough for a screener that refetching the same
    ticker within a few minutes is wasted work (and gets you rate-limited).
    Failed fetches are not cached. Ticker search is passed through uncached.
    """

    def __init__(
        self,
        inner: MarketDataProvider,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._inner = inner
        self._ttl = ttl_seconds
        self._clock = clock
        self._chains: dict[str, tuple[float, CallChain]] = {}
        self._lock = threading.Lock()

    def fetch_call_chain(self, ticker: str) -> CallChain:
        key = ticker.upper()
        now = self._clock()
        with self._lock:
            hit = self._chains.get(key)
        if hit is not None and now - hit[0] < self._ttl:
            return hit[1]
        chain = self._inner.fetch_call_chain(key)
        with self._lock:
            self._chains[key] = (now, chain)
        return chain

    def search_tickers(self, query: str) -> list[tuple[str, str]]:
        return self._inner.search_tickers(query)

    def clear(self) -> None:
        with self._lock:
            self._chains.clear()

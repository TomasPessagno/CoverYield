"""Read-through access to option chains with a per-ticker refresh cooldown.

All reads go through the store. Live fetches from the provider happen only when
a ticker isn't stored yet, when its copy is older than ``max_age_seconds``, or
when someone asks for a refresh and the ticker's cooldown has passed. The
cooldown is per ticker and shared by every caller: within the window, everyone
gets the copy that was just fetched instead of triggering another fetch.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from thetascout.data.provider import CallChain, DataFetchError, MarketDataProvider
from thetascout.data.store import ChainStore, StoredChain

LOCK_TTL_SECONDS = 60
LOCK_WAIT_SECONDS = 30.0
LOCK_POLL_SECONDS = 0.5


@dataclass(frozen=True)
class ChainResult:
    chain: CallChain
    fetched_at: datetime
    refreshed: bool  # fetched live during this call
    next_refresh_at: datetime | None  # when a refresh is allowed again (None = now)
    stale: bool = False  # a live fetch failed, so this is the last good copy


def utc_now() -> datetime:
    return datetime.now(UTC)


class ChainService:
    def __init__(
        self,
        provider: MarketDataProvider,
        store: ChainStore,
        cooldown_seconds: float = 0,
        max_age_seconds: float | None = None,
        clock: Callable[[], datetime] = utc_now,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._provider = provider
        self._store = store
        self._cooldown = timedelta(seconds=cooldown_seconds)
        self._max_age = None if max_age_seconds is None else timedelta(seconds=max_age_seconds)
        self._clock = clock
        self._sleep = sleep

    def get(self, ticker: str) -> ChainResult:
        """The stored chain, fetching live only if missing or older than max_age."""
        symbol = ticker.upper()
        stored = self._store.get(symbol)
        if stored is not None and not self._too_old(stored):
            return self._result(stored, refreshed=False)
        return self._fetch(symbol, stored)

    def refresh(self, ticker: str) -> ChainResult:
        """Fetch live unless the ticker was fetched within the cooldown window."""
        symbol = ticker.upper()
        stored = self._store.get(symbol)
        if stored is not None and self._clock() - stored.fetched_at < self._cooldown:
            return self._result(stored, refreshed=False)
        return self._fetch(symbol, stored)

    def _too_old(self, stored: StoredChain) -> bool:
        return self._max_age is not None and self._clock() - stored.fetched_at >= self._max_age

    def _result(self, stored: StoredChain, refreshed: bool, stale: bool = False) -> ChainResult:
        ready_at = stored.fetched_at + self._cooldown
        return ChainResult(
            chain=stored.chain,
            fetched_at=stored.fetched_at,
            refreshed=refreshed,
            next_refresh_at=ready_at if ready_at > self._clock() else None,
            stale=stale,
        )

    def _fetch(self, symbol: str, previous: StoredChain | None) -> ChainResult:
        if not self._store.acquire_lock(symbol, LOCK_TTL_SECONDS):
            return self._wait_for_other_fetch(symbol, previous)
        # Hold the lock until the result is stored, so nobody fetches in between.
        try:
            try:
                chain = self._provider.fetch_call_chain(symbol)
            except DataFetchError:
                if previous is not None:
                    return self._result(previous, refreshed=False, stale=True)
                raise

            if chain.is_empty:
                # Often a transient upstream glitch: keep the last good copy if there is one.
                if previous is not None:
                    return self._result(previous, refreshed=False, stale=True)
                return ChainResult(chain, self._clock(), refreshed=True, next_refresh_at=None)

            stored = StoredChain(chain, self._clock())
            self._store.put(symbol, stored)
            return self._result(stored, refreshed=True)
        finally:
            self._store.release_lock(symbol)

    def _wait_for_other_fetch(self, symbol: str, previous: StoredChain | None) -> ChainResult:
        """Another caller is fetching this ticker: wait for its result instead of fetching too."""
        waited = 0.0
        while waited < LOCK_WAIT_SECONDS:
            self._sleep(LOCK_POLL_SECONDS)
            waited += LOCK_POLL_SECONDS
            current = self._store.get(symbol)
            if current is not None and (
                previous is None or current.fetched_at > previous.fetched_at
            ):
                return self._result(current, refreshed=False)
        if previous is not None:
            return self._result(previous, refreshed=False, stale=True)
        raise DataFetchError(f"Timed out waiting for {symbol} to be fetched")

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from coveryield.data.provider import CallChain, DataFetchError
from coveryield.data.service import ChainService
from coveryield.data.store import MemoryStore, StoredChain

T0 = datetime(2026, 1, 5, 15, 0, tzinfo=UTC)


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


class CountingProvider:
    def __init__(self) -> None:
        self.calls = 0
        self.fail = False
        self.empty = False

    def fetch_call_chain(self, ticker: str) -> CallChain:
        self.calls += 1
        if self.fail:
            raise DataFetchError("boom")
        if self.empty:
            return CallChain(ticker, 0.0, 0.0, pd.DataFrame())
        return CallChain(ticker, 100.0 + self.calls, 99.0, pd.DataFrame({"x": [self.calls]}))

    def search_tickers(self, query: str) -> list[tuple[str, str]]:
        return []


Setup = tuple[ChainService, CountingProvider, Clock, MemoryStore]


def make(cooldown: float = 600, max_age: float | None = None) -> Setup:
    provider, clock, store = CountingProvider(), Clock(), MemoryStore()
    service = ChainService(provider, store, cooldown, max_age, clock=clock, sleep=lambda s: None)
    return service, provider, clock, store


def test_get_fetches_once_then_serves_the_stored_copy() -> None:
    service, provider, _, _ = make()
    first = service.get("aaa")
    second = service.get("AAA")
    assert provider.calls == 1
    assert first.refreshed and not second.refreshed
    assert second.chain.price == first.chain.price


def test_get_refetches_after_max_age() -> None:
    service, provider, clock, _ = make(max_age=600)
    service.get("AAA")
    clock.advance(601)
    assert service.get("AAA").refreshed
    assert provider.calls == 2


def test_refresh_respects_the_per_ticker_cooldown() -> None:
    service, provider, clock, _ = make(cooldown=600)
    service.refresh("AAA")
    clock.advance(240)
    blocked = service.refresh("AAA")
    assert provider.calls == 1 and not blocked.refreshed
    assert blocked.next_refresh_at == T0 + timedelta(seconds=600)

    clock.advance(361)
    allowed = service.refresh("AAA")
    assert provider.calls == 2 and allowed.refreshed


def test_no_cooldown_always_fetches_live() -> None:
    service, provider, _, _ = make(cooldown=0)
    service.refresh("AAA")
    result = service.refresh("AAA")
    assert provider.calls == 2 and result.refreshed and result.next_refresh_at is None


def test_failed_refresh_falls_back_to_the_last_good_copy() -> None:
    service, provider, clock, _ = make(cooldown=0)
    good = service.refresh("AAA")
    provider.fail = True
    clock.advance(60)
    result = service.refresh("AAA")
    assert result.stale and result.chain.price == good.chain.price


def test_failed_fetch_with_nothing_stored_raises() -> None:
    service, provider, _, _ = make()
    provider.fail = True
    with pytest.raises(DataFetchError):
        service.get("AAA")


def test_empty_response_is_not_stored() -> None:
    service, provider, _, store = make()
    provider.empty = True
    assert service.get("AAA").chain.is_empty
    assert store.get("AAA") is None


def test_waits_for_another_callers_fetch_instead_of_fetching_again() -> None:
    service, provider, clock, store = make(cooldown=0)
    store.acquire_lock("AAA", ttl_seconds=60)  # someone else is mid-fetch

    def finish_other_fetch(_: float) -> None:
        chain = CallChain("AAA", 123.0, 99.0, pd.DataFrame({"x": [1]}))
        store.put("AAA", StoredChain(chain, clock()))

    service._sleep = finish_other_fetch  # the other caller stores its result while we wait
    result = service.refresh("AAA")
    assert provider.calls == 0
    assert result.chain.price == 123.0 and not result.refreshed

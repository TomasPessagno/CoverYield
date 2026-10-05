import pandas as pd
import pytest

from tests.conftest import FakeProvider
from thetascout.data.cache import CachedProvider
from thetascout.data.provider import CallChain, DataFetchError


class CountingProvider(FakeProvider):
    def __init__(self) -> None:
        super().__init__({"AAA": CallChain("AAA", 100.0, 99.0, pd.DataFrame({"x": [1]}))})
        self.calls = 0

    def fetch_call_chain(self, ticker: str) -> CallChain:
        self.calls += 1
        return super().fetch_call_chain(ticker)


def test_cache_hits_within_ttl_and_refetches_after() -> None:
    inner = CountingProvider()
    clock = [0.0]
    cache = CachedProvider(inner, ttl_seconds=60, clock=lambda: clock[0])

    cache.fetch_call_chain("AAA")
    cache.fetch_call_chain("aaa")  # case-insensitive key
    assert inner.calls == 1

    clock[0] = 61
    cache.fetch_call_chain("AAA")
    assert inner.calls == 2


def test_cache_does_not_store_failures() -> None:
    inner = FakeProvider({}, failing={"BAD"})
    cache = CachedProvider(inner)
    with pytest.raises(DataFetchError):
        cache.fetch_call_chain("BAD")
    inner.failing.clear()
    assert cache.fetch_call_chain("BAD").is_empty  # retried, not a cached error

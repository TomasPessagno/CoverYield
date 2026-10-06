from collections.abc import Iterator
from datetime import UTC, datetime

import pandas as pd
import pytest

from coveryield.data.provider import CallChain
from coveryield.data.store import (
    ChainStore,
    MemoryStore,
    RedisStore,
    StoredChain,
    decode,
    encode,
)
from tests.conftest import make_calls

FETCHED = datetime(2026, 1, 5, 15, 0, tzinfo=UTC)


def stored_chain() -> StoredChain:
    calls = make_calls([{"strike": 105, "days": 30}, {"strike": 110, "days": 60, "bid": 0.5}])
    calls["lastPrice"] = 1.23  # an extra yfinance column that shouldn't be stored
    return StoredChain(CallChain("AAA", 100.0, 99.0, calls), FETCHED)


def test_encode_decode_round_trip() -> None:
    original = stored_chain()
    restored = decode(encode(original))
    assert restored.fetched_at == FETCHED
    assert restored.chain.ticker == "AAA" and restored.chain.price == 100.0
    assert "lastPrice" not in restored.chain.calls.columns
    expected = original.chain.calls.drop(columns=["lastPrice"])
    pd.testing.assert_frame_equal(
        restored.chain.calls[expected.columns], expected, check_dtype=False
    )


def test_encoding_is_compressed() -> None:
    calls = make_calls([{"strike": 50 + i * 0.5, "days": 30} for i in range(2000)])
    stored = StoredChain(CallChain("BIG", 100.0, 99.0, calls), FETCHED)
    raw = len(calls.to_json(orient="split"))
    assert len(encode(stored)) < raw / 4


@pytest.fixture(params=["memory", "redis"])
def store(request: pytest.FixtureRequest) -> Iterator[ChainStore]:
    if request.param == "memory":
        yield MemoryStore()
    else:
        fakeredis = pytest.importorskip("fakeredis")
        yield RedisStore(fakeredis.FakeRedis())


def test_get_put(store: ChainStore) -> None:
    assert store.get("AAA") is None
    store.put("aaa", stored_chain())
    got = store.get("AAA")
    assert got is not None and got.fetched_at == FETCHED


def test_lock_is_exclusive_until_released(store: ChainStore) -> None:
    assert store.acquire_lock("AAA", ttl_seconds=60)
    assert not store.acquire_lock("aaa", ttl_seconds=60)
    assert store.acquire_lock("BBB", ttl_seconds=60)  # other tickers are independent
    store.release_lock("AAA")
    assert store.acquire_lock("AAA", ttl_seconds=60)

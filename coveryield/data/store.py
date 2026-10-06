"""Where fetched option chains are kept, so they can be shared and reused.

Two implementations behind one interface:

- ``MemoryStore``: a dict in the current process. For local installs and tests.
- ``RedisStore``: Redis (e.g. Upstash). For the hosted site, where each request
  may run on a different serverless instance that shares no memory.

Each ticker is stored as one gzip-compressed JSON record with the time it was
fetched. A short-lived per-ticker lock lets exactly one caller refresh a ticker
while others wait for its result (avoiding a cache stampede on the data source).
"""

from __future__ import annotations

import gzip
import json
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from typing import TYPE_CHECKING, Protocol

import pandas as pd

from coveryield.data.provider import CallChain

if TYPE_CHECKING:
    from redis import Redis

# Only the columns the screening code reads are stored, which keeps records small.
STORED_COLUMNS = [
    "contractSymbol",
    "strike",
    "bid",
    "ask",
    "volume",
    "openInterest",
    "impliedVolatility",
    "optionType",
    "expirationDate",
]


@dataclass(frozen=True)
class StoredChain:
    chain: CallChain
    fetched_at: datetime  # timezone-aware (UTC)


class ChainStore(Protocol):
    def get(self, ticker: str) -> StoredChain | None: ...

    def put(self, ticker: str, stored: StoredChain) -> None: ...

    def acquire_lock(self, ticker: str, ttl_seconds: int) -> bool:
        """Take the refresh lock for ``ticker``. False if someone else holds it."""
        ...

    def release_lock(self, ticker: str) -> None: ...


def encode(stored: StoredChain) -> bytes:
    """Serialize a stored chain to gzip-compressed JSON."""
    calls = stored.chain.calls
    calls = calls[[c for c in STORED_COLUMNS if c in calls.columns]]
    payload = {
        "ticker": stored.chain.ticker,
        "price": stored.chain.price,
        "open_price": stored.chain.open_price,
        "fetched_at": stored.fetched_at.isoformat(),
        "calls": calls.to_json(orient="split", index=False, date_format="iso"),
    }
    return gzip.compress(json.dumps(payload).encode("utf-8"))


def decode(data: bytes) -> StoredChain:
    payload = json.loads(gzip.decompress(data).decode("utf-8"))
    calls = pd.read_json(StringIO(payload["calls"]), orient="split", convert_dates=False)
    if "expirationDate" in calls.columns:
        calls["expirationDate"] = pd.to_datetime(calls["expirationDate"]).dt.tz_localize(None)
    chain = CallChain(payload["ticker"], payload["price"], payload["open_price"], calls)
    return StoredChain(chain, datetime.fromisoformat(payload["fetched_at"]))


class MemoryStore:
    """Chains held in this process's memory (lost on restart)."""

    def __init__(self) -> None:
        self._chains: dict[str, StoredChain] = {}
        self._locks: dict[str, float] = {}  # ticker -> lock expiry (monotonic time)
        self._mutex = threading.Lock()

    def get(self, ticker: str) -> StoredChain | None:
        with self._mutex:
            return self._chains.get(ticker.upper())

    def put(self, ticker: str, stored: StoredChain) -> None:
        with self._mutex:
            self._chains[ticker.upper()] = stored

    def acquire_lock(self, ticker: str, ttl_seconds: int) -> bool:
        key = ticker.upper()
        now = time.monotonic()
        with self._mutex:
            if self._locks.get(key, 0.0) > now:
                return False
            self._locks[key] = now + ttl_seconds
            return True

    def release_lock(self, ticker: str) -> None:
        with self._mutex:
            self._locks.pop(ticker.upper(), None)


class RedisStore:
    """Chains held in Redis, shared by every server instance."""

    def __init__(self, client: Redis, prefix: str = "coveryield", ttl_days: int = 7) -> None:
        self._redis = client
        self._prefix = prefix
        # Records expire eventually so tickers nobody looks at don't linger forever.
        self._ttl_seconds = ttl_days * 86_400

    @classmethod
    def from_url(cls, url: str) -> RedisStore:
        from redis import Redis

        return cls(Redis.from_url(url))

    def _chain_key(self, ticker: str) -> str:
        return f"{self._prefix}:chain:{ticker.upper()}"

    def _lock_key(self, ticker: str) -> str:
        return f"{self._prefix}:lock:{ticker.upper()}"

    def get(self, ticker: str) -> StoredChain | None:
        data = self._redis.get(self._chain_key(ticker))
        return decode(data) if isinstance(data, bytes) else None

    def put(self, ticker: str, stored: StoredChain) -> None:
        self._redis.set(self._chain_key(ticker), encode(stored), ex=self._ttl_seconds)

    def acquire_lock(self, ticker: str, ttl_seconds: int) -> bool:
        # SET key value NX EX ttl: atomic "take it only if nobody holds it",
        # with an expiry so a crashed holder can't block the ticker forever.
        return bool(self._redis.set(self._lock_key(ticker), b"1", nx=True, ex=ttl_seconds))

    def release_lock(self, ticker: str) -> None:
        self._redis.delete(self._lock_key(ticker))

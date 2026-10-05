"""Fetch the ticker universe into the store (the hourly snapshot job).

Run by .github/workflows/snapshot.yml with REDIS_URL pointing at the hosted
store, so the website serves everyone from these snapshots instead of calling
Yahoo per visitor.

Usage:
    python -m api.snapshot                 # only during market hours
    python -m api.snapshot --force         # any time
    python -m api.snapshot --tickers AAPL,MSFT --delay 1
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from datetime import time as dtime
from zoneinfo import ZoneInfo

from api.settings import load_settings
from thetascout.data.provider import DataFetchError, MarketDataProvider
from thetascout.data.service import ChainService
from thetascout.data.store import ChainStore, MemoryStore, RedisStore
from thetascout.data.universe import DEFAULT_UNIVERSE
from thetascout.data.yahoo import YahooFinanceProvider

NEW_YORK = ZoneInfo("America/New_York")
# From shortly after the open (skip the noisy first half hour) to just after the close.
WINDOW_START = dtime(9, 55)
WINDOW_END = dtime(16, 30)


def in_snapshot_window(now: datetime) -> bool:
    """True on weekdays between 9:55 and 16:30 New York time (DST-aware)."""
    local = now.astimezone(NEW_YORK)
    return local.weekday() < 5 and WINDOW_START <= local.time() <= WINDOW_END


@dataclass
class SnapshotReport:
    ok: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        total = len(self.ok) + len(self.failed)
        return len(self.ok) / total if total else 1.0


def run_snapshot(
    tickers: Sequence[str],
    provider: MarketDataProvider,
    store: ChainStore,
    delay_seconds: float = 2.0,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = print,
) -> SnapshotReport:
    """Fetch every ticker live and store it, pausing between tickers to stay polite."""
    service = ChainService(provider, store, cooldown_seconds=0)
    report = SnapshotReport()
    for i, ticker in enumerate(tickers):
        if i:
            sleep(delay_seconds)
        try:
            result = service.refresh(ticker)
        except DataFetchError as e:
            report.failed.append(ticker)
            log(f"  {ticker:6} FAILED  {e}")
            continue
        if result.refreshed and not result.chain.is_empty:
            report.ok.append(ticker)
            log(f"  {ticker:6} ok      {len(result.chain.calls)} contracts")
        else:
            report.failed.append(ticker)
            log(f"  {ticker:6} FAILED  no data (kept previous copy)")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="run outside market hours")
    parser.add_argument("--tickers", help="comma-separated tickers (default: the universe)")
    parser.add_argument("--delay", type=float, default=2.0, help="seconds between tickers")
    args = parser.parse_args(argv)

    now = datetime.now(NEW_YORK)
    if not args.force and not in_snapshot_window(now):
        print(f"Outside the snapshot window ({now:%a %H:%M} New York). Nothing to do.")
        return 0

    settings = load_settings()
    store: ChainStore
    if settings.redis_url:
        store = RedisStore.from_url(settings.redis_url)
    else:
        print("REDIS_URL is not set: fetching into memory only (a dry run).")
        store = MemoryStore()

    tickers = (
        [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
        if args.tickers
        else DEFAULT_UNIVERSE
    )
    print(f"Snapshot of {len(tickers)} tickers at {now:%Y-%m-%d %H:%M} New York")
    started = time.monotonic()
    report = run_snapshot(tickers, YahooFinanceProvider(), store, args.delay)
    elapsed = time.monotonic() - started
    print(
        f"Done in {elapsed:.0f}s: {len(report.ok)} ok, {len(report.failed)} failed"
        + (f" ({', '.join(report.failed)})" if report.failed else "")
    )
    # Fail the job (so it shows red) only if most tickers failed, e.g. Yahoo throttling.
    return 0 if report.success_rate >= 0.5 else 1


if __name__ == "__main__":
    sys.exit(main())

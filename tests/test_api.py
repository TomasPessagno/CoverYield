from collections.abc import Iterator
from datetime import datetime

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from api.app import app, get_provider, get_service, get_settings  # noqa: E402
from api.settings import Settings  # noqa: E402
from coveryield.data.provider import CallChain  # noqa: E402
from coveryield.data.service import ChainService  # noqa: E402
from coveryield.data.store import MemoryStore  # noqa: E402
from tests.conftest import FakeProvider, make_calls  # noqa: E402


def chain(ticker: str, price: float = 100.0) -> CallChain:
    calls = make_calls(
        [
            {"strike": price * 1.05, "days": 30.5, "bid": price * 0.02, "iv": 0.30},  # 5% OTM
            {"strike": price * 1.02, "days": 30.5, "bid": price * 0.03, "iv": 0.30},  # 2% OTM
            {"strike": price * 1.10, "days": 30.5, "bid": 0.0},  # zero bid
        ],
        now=datetime.now(),
    )
    calls["contractSymbol"] = [f"{ticker}{i}" for i in range(len(calls))]
    return CallChain(ticker, price, price * 0.99, calls)


class CountingFakeProvider(FakeProvider):
    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self.fetches = 0

    def fetch_call_chain(self, ticker: str) -> CallChain:
        self.fetches += 1
        return super().fetch_call_chain(ticker)


def make_client(cooldown: float) -> tuple[TestClient, CountingFakeProvider]:
    provider = CountingFakeProvider(
        {"AAA": chain("AAA"), "BBB": chain("BBB", 50.0)}, failing={"BAD"}
    )
    service = ChainService(provider, MemoryStore(), cooldown_seconds=cooldown)
    settings = Settings("hosted" if cooldown else "local", None, cooldown, None)
    app.dependency_overrides[get_provider] = lambda: provider
    app.dependency_overrides[get_service] = lambda: service
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app), provider


@pytest.fixture
def client() -> Iterator[TestClient]:
    test_client, _ = make_client(cooldown=0)
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def hosted() -> Iterator[tuple[TestClient, CountingFakeProvider]]:
    yield make_client(cooldown=600)
    app.dependency_overrides.clear()


def test_health(client: TestClient) -> None:
    assert client.get("/api/health").json()["status"] == "ok"


def test_universe_lists_symbols(client: TestClient) -> None:
    symbols = [t["symbol"] for t in client.get("/api/universe").json()]
    assert "AAPL" in symbols and "SPY" in symbols


def test_screener_returns_contracts_with_metrics(client: TestClient) -> None:
    res = client.get("/api/screener/aaa", params={"min_days": 7, "max_days": 42})
    assert res.status_code == 200
    body = res.json()
    assert body["ticker"] == "AAA" and body["price"] == 100.0
    assert len(body["contracts"]) == 3  # the screener keeps zero-bid rows; the UI filters
    c = next(c for c in body["contracts"] if c["strike"] == pytest.approx(105))
    assert c["static_return_pct"] == pytest.approx(2.0)
    assert c["distance_to_strike_pct"] == pytest.approx(5.0)
    assert c["days_to_expiry"] == 30
    assert 0 < c["assignment_prob"] < 0.5


def test_screener_without_day_limits_returns_every_expiry(client: TestClient) -> None:
    body = client.get("/api/screener/AAA").json()
    assert len(body["contracts"]) == 3


def test_screener_day_window_excludes_contracts(client: TestClient) -> None:
    assert client.get("/api/screener/AAA", params={"max_days": 20}).json()["contracts"] == []
    assert client.get("/api/screener/AAA", params={"min_days": 40}).json()["contracts"] == []


def test_screener_serves_the_stored_copy(
    hosted: tuple[TestClient, CountingFakeProvider],
) -> None:
    client, provider = hosted
    first = client.get("/api/screener/AAA").json()
    second = client.get("/api/screener/AAA").json()
    assert provider.fetches == 1
    assert first["refreshed"] and not second["refreshed"]
    assert second["as_of"] == first["as_of"]


def test_refresh_is_limited_by_the_cooldown_when_hosted(
    hosted: tuple[TestClient, CountingFakeProvider],
) -> None:
    client, provider = hosted
    client.get("/api/screener/AAA")
    res = client.post("/api/refresh/AAA").json()
    assert provider.fetches == 1  # within the cooldown: no new fetch
    assert res["refreshed"] is False and res["next_refresh_at"] is not None


def test_refresh_always_fetches_locally(client: TestClient) -> None:
    client.get("/api/screener/AAA")
    res = client.post("/api/refresh/AAA").json()
    assert res["refreshed"] is True and res["next_refresh_at"] is None


def test_config_reports_mode_and_cooldown(
    hosted: tuple[TestClient, CountingFakeProvider],
) -> None:
    client, _ = hosted
    assert client.get("/api/config").json() == {
        "mode": "hosted",
        "refresh_cooldown_seconds": 600.0,
        "shared_store": False,
    }


def test_screener_unknown_ticker_is_404(client: TestClient) -> None:
    assert client.get("/api/screener/NONE").status_code == 404


def test_screener_provider_failure_is_502(client: TestClient) -> None:
    assert client.get("/api/screener/BAD").status_code == 502


def test_screener_rejects_bad_symbols(client: TestClient) -> None:
    assert client.get("/api/screener/not a ticker!").status_code in (404, 422)


def test_scan_ticker_reports_contract_count(client: TestClient) -> None:
    assert client.post("/api/scan/AAA").json() == {"ticker": "AAA", "ok": True, "contracts": 2}
    assert client.post("/api/scan/BAD").json()["ok"] is False


def test_opportunities_filters_scores_and_ranks(client: TestClient) -> None:
    res = client.post(
        "/api/opportunities",
        json={"tickers": ["AAA", "BBB", "BAD"], "min_static_return_pct": 1, "min_otm_pct": 3},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["scanned"] == 3
    assert body["matched"] == 2  # the 5%-OTM contract on AAA and BBB
    assert body["oldest_data_at"] is not None
    scores = [r["score"] for r in body["results"]]
    assert scores == sorted(scores, reverse=True)
    assert all(0 <= s <= 100 for s in scores)
    assert {r["ticker"] for r in body["results"]} == {"AAA", "BBB"}


def test_opportunities_validates_input(client: TestClient) -> None:
    assert client.post("/api/opportunities", json={"tickers": []}).status_code == 422
    bad_weights = {"tickers": ["AAA"], "weights": {"yield": 500}}
    assert client.post("/api/opportunities", json=bad_weights).status_code == 422

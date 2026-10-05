from collections.abc import Iterator
from datetime import datetime

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from api.app import app, get_provider  # noqa: E402
from tests.conftest import FakeProvider, make_calls  # noqa: E402
from thetascout.data.provider import CallChain  # noqa: E402


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


@pytest.fixture
def client() -> Iterator[TestClient]:
    provider = FakeProvider({"AAA": chain("AAA"), "BBB": chain("BBB", 50.0)}, failing={"BAD"})
    app.dependency_overrides[get_provider] = lambda: provider
    yield TestClient(app)
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
    scores = [r["score"] for r in body["results"]]
    assert scores == sorted(scores, reverse=True)
    assert all(0 <= s <= 100 for s in scores)
    assert {r["ticker"] for r in body["results"]} == {"AAA", "BBB"}


def test_opportunities_validates_input(client: TestClient) -> None:
    assert client.post("/api/opportunities", json={"tickers": []}).status_code == 422
    bad_weights = {"tickers": ["AAA"], "weights": {"yield": 500}}
    assert client.post("/api/opportunities", json=bad_weights).status_code == 422

# ThetaScout

[![CI](https://github.com/TomasPessagno/ThetaScout/actions/workflows/ci.yml/badge.svg)](https://github.com/TomasPessagno/ThetaScout/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A covered call screener. It pulls live option chains, computes the metrics a call
seller cares about, and ranks opportunities across many stocks with a transparent
scoring model.

> **Covered call:** you own 100 shares and sell someone the right to buy them at a
> higher price (the strike) before a date (the expiry). You collect a premium up
> front and give up gains above the strike.

## Features

- **Screener:** pick a ticker and see every call in your expiry window with static
  and annualized return, distance to strike, breakeven, bid-ask spread, volume,
  open interest and implied volatility, plus a risk-vs-reward chart.
- **Scan:** set goals (minimum return, maximum days to expiry, minimum
  distance out of the money) and scan a universe of liquid stocks and ETFs. Every
  contract gets an **Opportunity Score** (0-100), and the weights are adjustable.

## How it works

| Metric | Definition |
|---|---|
| Static return | bid ÷ stock price, the return if the stock doesn't move |
| Annualized return | static return × 365 ÷ days to expiry, to compare contracts with different expiries |
| Distance to strike | (strike − price) ÷ price |
| Assignment probability | Black-Scholes call delta, N(d1), using the contract's implied volatility |

The **Opportunity Score** is a weighted blend of five normalized components:
yield (40%), assignment risk (30%), liquidity (15%), volatility (10%) and
dividend (5%, currently neutral).

## Tech stack

- **Frontend:** Next.js (App Router), TypeScript, Tailwind CSS; charts drawn in SVG
- **API:** FastAPI with Pydantic models; the frontend's TypeScript types are generated
  from its OpenAPI schema
- **Analytics:** Python 3.11+, pandas, yfinance for market data, with a 10-minute
  per-ticker cache
- **Quality:** pytest + Hypothesis (property-based tests), ruff, mypy --strict,
  ESLint, GitHub Actions CI

All data access and math live in the `thetascout` package, which has no UI code.

```
thetascout/
  data/        market-data provider interface, Yahoo Finance implementation, cache, universe
  pricing/     Black-Scholes
  screening/   chain filters, per-contract metrics, multi-stock scan, scoring
api/           FastAPI app exposing the package over HTTP
web/           Next.js frontend
tests/         unit, property-based and API tests (offline, no network needed)
streamlit_app.py   the original Streamlit UI, kept while the new frontend is rolled out
```

## Run it locally

```bash
git clone https://github.com/TomasPessagno/ThetaScout.git
cd ThetaScout
pip install -e ".[api]"
uvicorn api.app:app --port 8000
```

In a second terminal:

```bash
cd web
npm install
npm run dev
```

Then open http://localhost:3000.

For development: `pip install -e ".[app,api,dev]"`, then `ruff check .`, `mypy` and
`pytest`; in `web/`, `npm run lint` and `npm run typecheck`.

## How data flows

Yahoo Finance rate-limits aggressively, so the hosted site never calls it per visitor:

- An hourly GitHub Actions job (market hours only) fetches the ticker universe and stores
  each option chain, compressed, in Redis.
- The site serves everyone from those snapshots and shows when the data was fetched.
- **Scan now** refreshes a single ticker live. On the hosted site each ticker can be
  refreshed once every 10 minutes, shared by all visitors (enforced with a Redis lock);
  running locally there is no limit.

| Setting | Local (default) | Hosted |
|---|---|---|
| `THETASCOUT_MODE` | `local` | `hosted` |
| Chain storage | in memory | Redis via `REDIS_URL` |
| Scan now cooldown | none | 10 minutes per ticker |

## Deployment

One Vercel project using [Services](https://vercel.com/docs/services) (`vercel.json`):
the Next.js app serves `/` and the FastAPI app serves `/api/*`. Redis is Upstash, added
through the Vercel Marketplace. The snapshot workflow needs a `REDIS_URL` repository secret.

## Disclaimer

For educational purposes only. Not financial advice. Market data comes from Yahoo
Finance via the unofficial `yfinance` library and may be delayed or incomplete.

## License

[MIT](LICENSE)

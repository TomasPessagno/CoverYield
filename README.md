# CoverYield

[![CI](https://github.com/TomasPessagno/CoverYield/actions/workflows/ci.yml/badge.svg)](https://github.com/TomasPessagno/CoverYield/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

*Formerly ThetaScout. Renamed to avoid confusion with an unrelated commercial product.*

A covered call screener. It pulls live option chains, computes the metrics a call
seller cares about, and ranks opportunities across many stocks with a transparent
scoring model.

**Live demo:** https://coveryield.vercel.app

> **Covered call:** you own 100 shares and sell someone the right to buy them at a
> higher price (the strike) before a date (the expiry). You collect a premium up
> front and give up gains above the strike.

## Features

- **Screener:** pick a ticker and see every call in your expiry window with static
  and annualized return, distance to strike, breakeven, bid-ask spread, what you earn
  per day (theta), the probability of finishing in the money, implied volatility,
  volume and open interest, plus a risk-vs-reward chart. Every column has a (?) with a
  plain-language explanation. Calls with no bid (nothing to collect) are hidden unless
  you ask for them.
- **Contract detail:** click any contract for its premium, the five Greeks in plain
  terms with that contract's numbers (e.g. "your shares + this call move like 60
  shares"), a warning when assignment risk can change quickly, and the Black-Scholes
  formulas with the inputs plugged in.
- **Scan:** set goals (minimum return, maximum days to expiry, minimum
  distance out of the money) and scan a universe of liquid stocks and ETFs. Every
  contract gets an **Opportunity Score** (0-100), and the weights are adjustable.

## How it works

| Metric | Definition |
|---|---|
| Static return | bid ÷ stock price, the return if the stock doesn't move |
| Annualized return | static return × 365 ÷ days to expiry, to compare contracts with different expiries |
| Distance to strike | (strike − price) ÷ price |
| Implied volatility | the volatility at which Black-Scholes reproduces the contract's bid/ask mid (solved, see below) |
| P(ITM) | N(d₂), the Black-Scholes probability that the stock ends above the strike, i.e. that the shares get called away |
| $/day | −theta × 100: what one contract earns per day as time passes, all else equal |
| Greeks | delta, gamma, theta, vega and rho of the call under Black-Scholes-Merton |

The **Opportunity Score** is a weighted blend of five normalized components:
yield (40%), assignment risk (30%), liquidity (15%), volatility (10%) and
dividend (5%, currently neutral).

### Pricing details

- **Implied volatility is solved, not taken from the data feed.** For each contract we
  find the volatility that makes Black-Scholes match the bid/ask mid, using Newton's
  method on vega with a bisection fallback when vega is too small. Quotes that no
  volatility can produce (no bid, crossed, below the call's no-arbitrage minimum) get
  no IV rather than a made-up one. Yahoo's own IV is kept for comparison: for options a
  day or two from expiry it is inconsistent with the market price (e.g. an AAPL call
  with 1.1 days left: Yahoo 20.9%, while the mid implies 27.7%).
- **Time to expiry** runs to the 4pm New York close on expiry day, in fractional years,
  and is measured from when the quote was taken, so stored snapshots are priced with the
  time that was left at that moment.
- **Tested** against textbook values (Hull), against finite differences (each Greek
  matches nudging its input and repricing), no-arbitrage bounds, and IV round trips on
  randomly generated contracts (Hypothesis).
- **Known simplifications:** a fixed 4.5% risk-free rate, no dividends yet, and
  European exercise (US equity options can be exercised early, most often just before a
  dividend).

## Tech stack

- **Frontend:** Next.js (App Router), TypeScript, Tailwind CSS; charts drawn in SVG,
  formulas typeset with KaTeX
- **API:** FastAPI with Pydantic models; the frontend's TypeScript types are generated
  from its OpenAPI schema
- **Analytics:** Python 3.11+, pandas, yfinance for market data, stored per ticker in
  Redis (see below)
- **Quality:** pytest + Hypothesis (property-based tests), ruff, mypy --strict,
  ESLint, GitHub Actions CI

All data access and math live in the `coveryield` package, which has no UI code.

```
coveryield/
  data/        market-data provider interface, Yahoo Finance implementation, chain store, universe
  pricing/     Black-Scholes price and Greeks, implied volatility solver
  market_time.py   New York market clock: days and years to the 4pm close
  screening/   chain filters, per-contract metrics, multi-stock scan, scoring
api/           FastAPI app exposing the package over HTTP
web/           Next.js frontend
tests/         unit, property-based and API tests (offline, no network needed)
streamlit_app.py   the original Streamlit UI, kept while the new frontend is rolled out
```

## Run it locally

```bash
git clone https://github.com/TomasPessagno/CoverYield.git
cd CoverYield
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
| `COVERYIELD_MODE` | `local` | `hosted` |
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

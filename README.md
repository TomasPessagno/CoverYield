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
- **Custom Analysis:** set goals (minimum return, maximum days to expiry, minimum
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

- **Python 3.11+**, **pandas** for the analytics, **yfinance** for market data
- **Streamlit** + **Altair** for the current UI
- **pytest** + **Hypothesis** (property-based tests), **ruff**, **mypy --strict**,
  GitHub Actions CI

All data access and math live in the `thetascout` package, which has no UI code, so
the same logic can back other frontends.

```
thetascout/
  data/        market-data provider interface, Yahoo Finance implementation, ticker universe
  pricing/     Black-Scholes
  screening/   chain filters, per-contract metrics, multi-stock scan, scoring
tests/         unit and property-based tests (offline, no network needed)
streamlit_app.py
```

## Run it locally

```bash
git clone https://github.com/TomasPessagno/ThetaScout.git
cd ThetaScout
pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

For development: `pip install -e ".[app,dev]"`, then `ruff check .`, `mypy` and `pytest`.

## Disclaimer

For educational purposes only. Not financial advice. Market data comes from Yahoo
Finance via the unofficial `yfinance` library and may be delayed or incomplete.

## License

[MIT](LICENSE)

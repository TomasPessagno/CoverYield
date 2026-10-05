"""The Opportunity Score: a weighted 0-100 ranking of covered-call contracts."""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd

COMPONENTS = ("yield", "assign", "liq", "vol", "div")
DEFAULT_WEIGHTS: dict[str, float] = {"yield": 40, "assign": 30, "liq": 15, "vol": 10, "div": 5}
DEFAULT_YIELD_ACTUAL_FRAC = 0.7


def normalize_weights(
    raw: Mapping[str, float], yield_actual_frac: float = DEFAULT_YIELD_ACTUAL_FRAC
) -> dict[str, float]:
    """Scale the five component weights to sum to 1 and attach the yield split."""
    total = max(sum(raw[k] for k in COMPONENTS), 1)
    weights = {k: raw[k] / total for k in COMPONENTS}
    weights["yield_actual_frac"] = yield_actual_frac
    return weights


def compute_opportunity_score(df: pd.DataFrame, weights: Mapping[str, float]) -> pd.DataFrame:
    """
    Blend five normalized 0-100 components into a single Opportunity Score.

    weights: keys yield/assign/liq/vol/div (already normalized to sum 1), plus an
    optional yield_actual_frac. See ``normalize_weights``.
    """
    out = df.copy()

    # 40% Yield — blend of ACTUAL return (real cash this trade) and annualized
    # (capital efficiency). Leans on actual by default so the ranking reflects
    # real money, not a short-DTE-favoring projection. Split is user-tunable.
    actual_norm = (out["Static Return %"] / 5.0).clip(0, 1) * 100  # 0..5% -> 0..100
    annual_norm = (out["Annualized Return %"] / 60.0).clip(0, 1) * 100  # 0..60% -> 0..100
    actual_frac = weights.get("yield_actual_frac", DEFAULT_YIELD_ACTUAL_FRAC)
    out["s_yield"] = actual_frac * actual_norm + (1 - actual_frac) * annual_norm

    # 30% Assignment risk — lower delta (prob. of being called away) = better
    delta = out["Assignment Prob"].fillna(0.5)
    out["s_assign"] = (1 - delta).clip(0, 1) * 100

    # 15% Liquidity — open interest + volume, penalize wide spreads
    oi = (out["Open Interest"] / 500.0).clip(0, 1)
    vol = (out["Volume"] / 200.0).clip(0, 1)
    spread_quality = 1 - (out["Spread"] / 0.5).clip(0, 1)
    out["s_liq"] = (oi * 0.5 + vol * 0.3 + spread_quality * 0.2) * 100

    # 10% Volatility — reward moderate IV (~30%), penalize extremes
    out["s_vol"] = (100 - (out["IV"] - 30).abs() * 1.5).clip(0, 100)

    # 5% Dividend — placeholder neutral (ex-div timing is a v2 item)
    out["s_div"] = 50.0

    out["Opportunity Score"] = (
        weights["yield"] * out["s_yield"]
        + weights["assign"] * out["s_assign"]
        + weights["liq"] * out["s_liq"]
        + weights["vol"] * out["s_vol"]
        + weights["div"] * out["s_div"]
    )
    return out


def rank_opportunities(scored: pd.DataFrame, top_n: int) -> pd.DataFrame:
    """The ``top_n`` highest-scoring contracts, best first."""
    return scored.sort_values("Opportunity Score", ascending=False).head(top_n)

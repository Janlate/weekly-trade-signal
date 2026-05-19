"""Layer 2 — Margin Sustainability."""
from __future__ import annotations

from tradingview_mcp.core.services.fundamentals.industry_config import get_margin_median
from tradingview_mcp.core.services.fundamentals.providers.base import TickerFinancials
from tradingview_mcp.core.services.fundamentals.schemas import LayerScore
from tradingview_mcp.core.services.fundamentals.scorers._utils import (
    clamp, linear_slope, safe_div,
)


def score_layer_2(f: TickerFinancials) -> LayerScore:
    rev, gp, op = f.revenue_5y, f.gross_profit_5y, f.operating_income_5y
    if not (rev and gp and op) or len(rev) < 3:
        return LayerScore(
            layer_id=2, name="Margin Sustainability", score=0,
            verdict="INSUFFICIENT_DATA",
            rationale="missing revenue/gross/operating data",
            inputs={}, data_completeness=0.0,
        )

    gm = [safe_div(g, r, default=0.0) for g, r in zip(gp, rev)]
    om = [safe_div(o, r, default=0.0) for o, r in zip(op, rev)]

    median = get_margin_median(f.industry, f.sub_industry)
    gm_latest = gm[-1]
    om_latest = om[-1]

    # Level vs median (0-5)
    level_score = 0
    if gm_latest >= median["gross"] * 1.10:
        level_score += 2.5
    elif gm_latest >= median["gross"] * 0.90:
        level_score += 1.5
    if om_latest >= median["operating"] * 1.10:
        level_score += 2.5
    elif om_latest >= median["operating"] * 0.90:
        level_score += 1.5

    # Trend (slope > 0 over last 3y) (0-5)
    slope_gm = linear_slope(gm[-3:])
    slope_op = linear_slope(om[-3:])
    trend_score = 0
    if slope_gm > 0.005:
        trend_score += 2.5
    elif slope_gm > -0.005:
        trend_score += 1.5
    if slope_op > 0.005:
        trend_score += 2.5
    elif slope_op > -0.005:
        trend_score += 1.5

    # Penalty for volatility (std of GM > 5pp)
    import statistics
    vol_penalty = 2 if statistics.pstdev(gm) > 0.05 else 0

    raw = level_score + trend_score - vol_penalty
    score = clamp(raw, 0, 10)
    verdict = "PASS" if score >= 7 else ("CAUTION" if score >= 4 else "FAIL")

    rationale = (
        f"GM {gm_latest*100:.1f}% vs median {median['gross']*100:.0f}%; "
        f"OpM {om_latest*100:.1f}% vs median {median['operating']*100:.0f}%; "
        f"GM slope {slope_gm*100:+.2f}pp/y"
        + (" [volatile]" if vol_penalty else "")
    )

    return LayerScore(
        layer_id=2, name="Margin Sustainability", score=score, verdict=verdict,
        rationale=rationale,
        inputs={"gm_5y": gm, "om_5y": om, "median": median,
                "slope_gm": slope_gm, "slope_op": slope_op},
        data_completeness=1.0,
    )

"""Layer 4 — Moat (Phase 1: quantitative proxies only, capped 7/10)."""
from __future__ import annotations

import statistics

from tradingview_mcp.core.services.fundamentals.industry_config import get_margin_median
from tradingview_mcp.core.services.fundamentals.providers.base import TickerFinancials
from tradingview_mcp.core.services.fundamentals.schemas import LayerScore
from tradingview_mcp.core.services.fundamentals.scorers._utils import clamp, safe_div


def score_layer_4(f: TickerFinancials) -> LayerScore:
    rev, gp, op, ni, ic = (
        f.revenue_5y, f.gross_profit_5y, f.operating_income_5y,
        f.net_income_5y, f.invested_capital_5y,
    )
    if not all([rev, gp, op, ni, ic]) or len(rev) < 3:
        return LayerScore(
            layer_id=4, name="Moat", score=0,
            verdict="INSUFFICIENT_DATA",
            rationale="missing data for moat proxy",
            inputs={}, data_completeness=0.0,
        )

    # ROIC persistence — low std of ROIC over 5y
    nopat = [o * 0.79 for o in op]  # 21% tax
    roics = [safe_div(n, i, default=0.0) for n, i in zip(nopat, ic)]
    roic_std = statistics.pstdev(roics) if len(roics) > 1 else 0.0
    if roic_std < 0.03:
        roic_score = 3
    elif roic_std < 0.06:
        roic_score = 2
    elif roic_std < 0.10:
        roic_score = 1
    else:
        roic_score = 0

    # GM premium vs peer median
    gms = [safe_div(g, r, default=0.0) for g, r in zip(gp, rev)]
    gm_latest = gms[-1]
    median_gm = get_margin_median(f.industry, f.sub_industry).get("gross", 0.40)
    premium = gm_latest - median_gm
    if premium >= 0.10:
        gm_score = 2
    elif premium >= 0.03:
        gm_score = 1
    else:
        gm_score = 0

    # Scale rank — Phase 1 use raw market cap thresholds
    mc = f.market_cap_current
    if mc >= 100e9:
        scale_score = 2
    elif mc >= 20e9:
        scale_score = 1
    else:
        scale_score = 0

    raw = roic_score + gm_score + scale_score
    score = clamp(raw, 0, 7)  # Phase 1 cap
    verdict = "PASS" if score >= 6 else ("CAUTION" if score >= 4 else "FAIL")

    rationale = (
        f"ROIC std {roic_std*100:.1f}pp; GM premium {premium*100:+.1f}pp vs peer; "
        f"market cap ${mc/1e9:.0f}B [Phase 1 proxy-only — capped 7/10]"
    )

    return LayerScore(
        layer_id=4, name="Moat", score=score, verdict=verdict,
        rationale=rationale,
        inputs={"roic_std": roic_std, "gm_premium": premium,
                "market_cap": mc, "moat_override_applied": False},
        data_completeness=1.0,
    )

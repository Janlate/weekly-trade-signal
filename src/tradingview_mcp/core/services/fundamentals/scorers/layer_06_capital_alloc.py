"""Layer 6 — Capital Allocation."""
from __future__ import annotations

from tradingview_mcp.core.services.fundamentals.providers.base import TickerFinancials
from tradingview_mcp.core.services.fundamentals.schemas import LayerScore
from tradingview_mcp.core.services.fundamentals.scorers._utils import (
    clamp, linear_slope, safe_div,
)


def score_layer_6(f: TickerFinancials) -> LayerScore:
    if not f.diluted_shares_5y or not f.buyback_5y:
        return LayerScore(
            layer_id=6, name="Capital Allocation", score=0,
            verdict="INSUFFICIENT_DATA",
            rationale="missing buyback/share data",
            inputs={}, data_completeness=0.0,
        )

    # Buyback timing approx: total buyback $ / Δshares retired
    total_bb = sum(f.buyback_5y[-3:])  # last 3y
    shares = f.diluted_shares_5y
    delta_shares = shares[-1] - shares[-3] if len(shares) >= 3 else 0
    # If shares decreased (delta < 0), we retired |delta| shares
    avg_bb_price = (total_bb / abs(delta_shares)) if delta_shares < 0 else None

    bb_score = 0
    if avg_bb_price and f.price_current:
        ratio = avg_bb_price / f.price_current  # < 1 = bought below current = good
        if ratio < 0.7:
            bb_score = 3
        elif ratio < 0.9:
            bb_score = 2
        elif ratio < 1.1:
            bb_score = 1
    elif total_bb > 0:
        bb_score = 1  # buying back but timing unclear

    # Dividend consistency: did they pay consistently and growing?
    div_score = 0
    if f.dividend_paid_5y and any(f.dividend_paid_5y):
        slope = linear_slope(f.dividend_paid_5y)
        if slope > 0:
            div_score = 3
        elif slope >= 0:
            div_score = 2
        else:
            div_score = 1

    # ROIC trend (proxy via OpInc / InvestedCapital trend)
    roic_score = 0
    if f.operating_income_5y and f.invested_capital_5y:
        roics = [safe_div(o * 0.79, ic, default=0.0)
                 for o, ic in zip(f.operating_income_5y, f.invested_capital_5y)]
        if linear_slope(roics) > 0:
            roic_score = 2
        elif linear_slope(roics) >= 0:
            roic_score = 1

    # Cash hoarding penalty
    cash_penalty = 0
    if f.cash_5y and f.market_cap_current:
        cash_ratio = f.cash_5y[-1] / f.market_cap_current
        if cash_ratio > 0.30 and div_score < 2 and bb_score < 2:
            cash_penalty = 1

    raw = bb_score + div_score + roic_score - cash_penalty
    score = clamp(raw, 0, 10)
    verdict = "PASS" if score >= 6 else ("CAUTION" if score >= 3 else "FAIL")

    rationale = (
        f"Buyback {bb_score}/3 (avg ${avg_bb_price:.0f}/sh proxy)"
        if avg_bb_price else f"Buyback {bb_score}/3 (no shares retired)"
    ) + f"; Dividend {div_score}/3; ROIC trend {roic_score}/2"

    return LayerScore(
        layer_id=6, name="Capital Allocation", score=score, verdict=verdict,
        rationale=rationale,
        inputs={"buyback_score": bb_score, "div_score": div_score,
                "roic_trend_score": roic_score, "cash_penalty": cash_penalty,
                "avg_buyback_price_proxy": avg_bb_price},
        data_completeness=1.0,
    )

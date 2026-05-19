"""Layer 1 — Revenue Growth scoring."""
from __future__ import annotations

from tradingview_mcp.core.services.fundamentals.industry_config import (
    GROWTH_BANDS, gics_to_tier, is_cyclical,
)
from tradingview_mcp.core.services.fundamentals.providers.base import TickerFinancials
from tradingview_mcp.core.services.fundamentals.schemas import LayerScore
from tradingview_mcp.core.services.fundamentals.scorers._utils import (
    cagr, clamp, coefficient_of_variation,
)


def score_layer_1(f: TickerFinancials) -> LayerScore:
    rev = f.revenue_5y
    cyclical = is_cyclical(f.industry, f.sub_industry)
    preferred_years = 7 if cyclical else 5
    min_years_hard = 3
    actual_years = len(rev)

    if actual_years < min_years_hard:
        return LayerScore(
            layer_id=1, name="Revenue Growth", score=0.0,
            verdict="INSUFFICIENT_DATA",
            rationale=f"only {actual_years} years of data (hard min 3)",
            inputs={"revenue_5y": rev, "years": actual_years},
            data_completeness=actual_years / preferred_years,
        )
    # 3 ≤ actual < preferred → degrade data_completeness but proceed

    g = cagr(rev[0], rev[-1], len(rev) - 1)
    tier = gics_to_tier(f.industry)
    lo, hi = GROWTH_BANDS.get(tier, (0.08, 0.15))

    # Base score from tier match (0-6)
    if g < 0:
        base = 0
    elif g < lo:
        base = 2
    elif g <= hi:
        base = 5
    elif tier == "fast":
        base = 6  # hyper-growth above fast ceiling — still rewarded
    elif g <= 1.0:
        base = 5  # hyper — but flag
    else:
        base = 3  # implausible

    # Consistency on YoY growth rates (lower CV = higher) — skip for cyclicals
    yoy = [(rev[i + 1] - rev[i]) / rev[i] for i in range(len(rev) - 1)] if len(rev) >= 2 else []
    cv = coefficient_of_variation(yoy) if len(yoy) >= 2 else 0.0
    if cyclical:
        consistency = 1.5  # cyclicals get neutral
    elif cv < 0.10:
        consistency = 2.0
    elif cv < 0.20:
        consistency = 1.5
    elif cv < 0.35:
        consistency = 0.5
    else:
        consistency = 0.0

    # Quality bonus (recurring/concentration) — Phase 1 stubbed
    quality = 1.0  # neutral

    raw = base + consistency + quality
    score = clamp(raw, 0, 10)

    verdict = "PASS" if score >= 7 else ("CAUTION" if score >= 4 else "FAIL")

    rationale = (
        f"CAGR {g*100:.1f}% over {len(rev)} years; tier={tier} "
        f"(expected {lo*100:.0f}-{hi*100:.0f}%); cv={cv:.2f}"
        + (" [cyclical]" if cyclical else "")
    )

    return LayerScore(
        layer_id=1, name="Revenue Growth", score=score, verdict=verdict,
        rationale=rationale,
        inputs={"revenue_5y": rev, "cagr": g, "tier": tier, "cv": cv, "is_cyclical": cyclical},
        data_completeness=min(1.0, actual_years / preferred_years),
    )

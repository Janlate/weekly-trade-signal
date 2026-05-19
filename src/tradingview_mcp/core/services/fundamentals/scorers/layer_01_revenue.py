"""Layer 1 — Revenue Growth scoring."""
from __future__ import annotations

from tradingview_mcp.core.services.fundamentals.industry_config import (
    GROWTH_BANDS, gics_to_tier, is_cyclical,
)
from tradingview_mcp.core.services.fundamentals.providers.base import TickerFinancials
from tradingview_mcp.core.services.fundamentals.schemas import LayerScore
from tradingview_mcp.core.services.fundamentals.scorers._utils import (
    cagr, clamp, coefficient_of_variation, cyclical_trough_recovery_score,
)

# Preferred data window: cyclicals need a full cycle, non-cyclicals 5y is enough
_PREFERRED_YEARS_CYCLICAL = 7
_PREFERRED_YEARS_STANDARD = 5
_MIN_YEARS_HARD = 3
_MIN_YEARS_CYCLICAL_SOFT = 4  # need at least 4 to split into two halves


def score_layer_1(f: TickerFinancials) -> LayerScore:
    rev = f.revenue_5y
    cyclical = is_cyclical(f.industry, f.sub_industry)
    tier = gics_to_tier(f.industry)  # may be "cyclical" for energy/materials

    preferred_years = _PREFERRED_YEARS_CYCLICAL if cyclical else _PREFERRED_YEARS_STANDARD
    actual_years = len(rev)

    if actual_years < _MIN_YEARS_HARD:
        return LayerScore(
            layer_id=1, name="Revenue Growth", score=0.0,
            verdict="INSUFFICIENT_DATA",
            rationale=f"only {actual_years} years of data (hard min {_MIN_YEARS_HARD})",
            inputs={"revenue_5y": rev, "years": actual_years, "is_cyclical": cyclical,
                    "tier": tier, "cagr": None, "cv": None},
            data_completeness=actual_years / preferred_years,
        )

    # ── CYCLICAL PATH ──────────────────────────────────────────────────────────
    # Do NOT judge by CAGR vs tier band — use trough-recovery heuristic instead.
    if cyclical:
        if actual_years < _MIN_YEARS_CYCLICAL_SOFT:
            return LayerScore(
                layer_id=1, name="Revenue Growth", score=0.0,
                verdict="INSUFFICIENT_DATA",
                rationale=(
                    f"cyclical requires >= {_MIN_YEARS_CYCLICAL_SOFT}y to assess trough-recovery "
                    f"(have {actual_years})"
                ),
                inputs={"revenue_5y": rev, "years": actual_years, "is_cyclical": True,
                        "tier": tier, "cagr": None, "cv": None, "trough_recovery": None},
                data_completeness=actual_years / preferred_years,
            )

        recovery_score, recovery_fragment, extra_inputs = cyclical_trough_recovery_score(rev)

        # Still compute CAGR + CV as informational metadata (kept for API contract)
        g = cagr(rev[0], rev[-1], actual_years - 1)
        yoy = [(rev[i + 1] - rev[i]) / rev[i] for i in range(len(rev) - 1)] if len(rev) >= 2 else []
        cv = coefficient_of_variation(yoy) if len(yoy) >= 2 else 0.0

        # Map 0-6 recovery score to 0-10 final score with quality neutral bonus (1.0)
        # recovery_score 4+2=6 → 7 (PASS), 4+0=4 → 5 (CAUTION), etc.
        quality = 1.0  # neutral placeholder
        raw = recovery_score + quality
        score = clamp(raw, 0, 10)

        verdict = "PASS" if score >= 7 else ("CAUTION" if score >= 4 else "FAIL")

        rationale = (
            f"[cyclical] {recovery_fragment}; "
            f"CAGR {g*100:.1f}% over {actual_years}y (informational only, not used for scoring)"
        )

        inputs = {
            "revenue_5y": rev,
            "cagr": g,
            "tier": tier,       # "cyclical" — kept for API contract
            "cv": cv,
            "is_cyclical": True,
            **extra_inputs,     # trough_recovery, rising_base, peak_revenue, latest_revenue
        }
        return LayerScore(
            layer_id=1, name="Revenue Growth", score=score, verdict=verdict,
            rationale=rationale,
            inputs=inputs,
            data_completeness=min(1.0, actual_years / preferred_years),
        )

    # ── STANDARD PATH (non-cyclical) ──────────────────────────────────────────
    g = cagr(rev[0], rev[-1], actual_years - 1)
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

    # Consistency on YoY growth rates (lower CV = higher)
    yoy = [(rev[i + 1] - rev[i]) / rev[i] for i in range(len(rev) - 1)] if len(rev) >= 2 else []
    cv = coefficient_of_variation(yoy) if len(yoy) >= 2 else 0.0
    if cv < 0.10:
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
        f"CAGR {g*100:.1f}% over {actual_years} years; tier={tier} "
        f"(expected {lo*100:.0f}-{hi*100:.0f}%); cv={cv:.2f}"
    )

    return LayerScore(
        layer_id=1, name="Revenue Growth", score=score, verdict=verdict,
        rationale=rationale,
        inputs={
            "revenue_5y": rev, "cagr": g, "tier": tier, "cv": cv,
            "is_cyclical": False,
            # trough_recovery keys absent for non-cyclicals — checklist20.ts handles undefined gracefully
        },
        data_completeness=min(1.0, actual_years / preferred_years),
    )

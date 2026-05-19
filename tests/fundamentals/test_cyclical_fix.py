"""Golden tests for cyclical industry scoring fix.

Covers:
- Cyclical energy/materials with recovered revenue should PASS or CAUTION L1
- Cyclical still in trough (below 65% of prior peak) should CAUTION/FAIL L1
- GOOGL (Communication Services sector 50) moved to "mid" tier — 12.5% CAGR should PASS L1
- L3 cyclical 3y-avg ROIC prevents single trough year from failing spread gate
- Non-cyclical fast-grower regression guard
"""
from __future__ import annotations
import pytest
from tradingview_mcp.core.services.fundamentals.providers.base import TickerFinancials
from tradingview_mcp.core.services.fundamentals.scorers.layer_01_revenue import score_layer_1
from tradingview_mcp.core.services.fundamentals.scorers.layer_03_fcf_quality import score_layer_3
from tradingview_mcp.core.services.fundamentals.industry_config import gics_to_tier, is_cyclical


# ── industry_config ────────────────────────────────────────────────────────────

def test_energy_sector_is_cyclical_tier():
    assert gics_to_tier("10") == "cyclical"

def test_materials_sector_is_cyclical_tier():
    assert gics_to_tier("15") == "cyclical"

def test_comm_services_is_mid_tier():
    """GOOGL/META live in sector 50; mature platforms grow 8-15%, not fast."""
    assert gics_to_tier("50") == "mid"

def test_it_remains_fast():
    """IT sector 45 (NVDA, MSFT) stays fast."""
    assert gics_to_tier("45") == "fast"

def test_energy_still_flagged_is_cyclical():
    assert is_cyclical("10") is True

def test_materials_still_flagged_is_cyclical():
    assert is_cyclical("15") is True


# ── Layer 1 — cyclical recovered ───────────────────────────────────────────────

def _energy_financials(revenue, **kw) -> TickerFinancials:
    return TickerFinancials(ticker="CYC", industry="10", revenue_5y=revenue, **kw)


def test_l1_cyclical_recovered_revenue_passes():
    """Energy co: revenue peaked then dipped then recovered >= 95% of peak.
    Pattern: 100 → 140 → 90 → 80 → 135 — latest 135 >= peak 140 * 0.95 = 133."""
    rev = [100, 140, 90, 80, 135]
    s = score_layer_1(_energy_financials(rev))
    assert s.verdict in ("PASS", "CAUTION"), f"Expected PASS or CAUTION, got {s.verdict}: {s.rationale}"
    # Must not be FAIL solely due to CAGR vs tier mismatch
    assert s.score >= 4


def test_l1_cyclical_recovered_with_rising_base_passes():
    """7y series: trough in first half (80) < trough in second half (90) = rising base.
    Latest 160 vs peak 160 = full recovery. Should PASS."""
    rev = [100, 130, 80, 120, 90, 140, 160]
    s = score_layer_1(_energy_financials(rev))
    assert s.verdict == "PASS", f"Got {s.verdict}: {s.rationale}"
    assert s.score >= 7


def test_l1_cyclical_still_in_trough_cautions():
    """Energy co in deep trough: latest 60 vs peak 140 = 43% recovery (< 65%). Should FAIL or CAUTION."""
    rev = [100, 140, 90, 80, 60]
    s = score_layer_1(_energy_financials(rev))
    assert s.verdict in ("CAUTION", "FAIL"), f"Got {s.verdict}: {s.rationale}"
    assert s.score < 7


def test_l1_cyclical_stores_trough_recovery_in_inputs():
    """API contract: inputs must include trough_recovery key."""
    rev = [100, 130, 85, 95, 120]
    s = score_layer_1(_energy_financials(rev))
    assert "trough_recovery" in s.inputs, "missing trough_recovery in inputs"
    assert "is_cyclical" in s.inputs
    assert s.inputs["is_cyclical"] is True


def test_l1_cyclical_still_has_cagr_and_tier_in_inputs():
    """API contract: cagr + tier must still be present (checklist20.ts reads them)."""
    rev = [100, 130, 85, 95, 120]
    s = score_layer_1(_energy_financials(rev))
    assert "cagr" in s.inputs
    assert "tier" in s.inputs
    assert s.inputs["tier"] == "cyclical"


def test_l1_cyclical_insufficient_data_under_4_years():
    """Cyclical with only 3 data points → INSUFFICIENT_DATA (need >= 4 for trough split)."""
    rev = [100, 130, 90]
    s = score_layer_1(_energy_financials(rev))
    assert s.verdict == "INSUFFICIENT_DATA"


def test_l1_materials_cyclical_treated_same():
    """Materials sector (15) is also cyclical — same path."""
    rev = [100, 140, 70, 80, 135]
    s = score_layer_1(TickerFinancials(ticker="MAT", industry="15", revenue_5y=rev))
    assert s.verdict in ("PASS", "CAUTION"), f"Got {s.verdict}: {s.rationale}"
    assert s.inputs.get("tier") == "cyclical"


# ── Layer 1 — GOOGL Communication Services regression ─────────────────────────

def _googl_like(revenue) -> TickerFinancials:
    """Simulate GOOGL: sector 50, CAGR ~12.5%, non-cyclical."""
    return TickerFinancials(ticker="GOOGL", industry="50", revenue_5y=revenue)


def test_l1_googl_12pct_cagr_no_longer_fails():
    """CAGR 12.5% on mid tier (8-15%) must NOT be FAIL.
    Previous bug: sector 50 mapped to 'fast' tier (lo=15%) → base=2 → FAIL.
    After fix: sector 50 is 'mid' (lo=8%) → base=5 → CAUTION or PASS depending on cv.
    The key assertion: verdict != FAIL (growth-tier-mismatch no longer the cause).
    """
    rev = [282836, 307394, 350018, 402836]  # real GOOGL proportions, CAGR ~12.5%
    s = score_layer_1(_googl_like(rev))
    assert s.verdict != "FAIL", (
        f"GOOGL at 12.5% CAGR on mid tier must not FAIL, got {s.verdict}: {s.rationale}"
    )
    assert s.inputs["tier"] == "mid"
    assert s.inputs["is_cyclical"] is False
    assert s.score >= 4  # CAUTION minimum


def test_l1_fast_grower_non_regression():
    """IT sector 45 at 35% CAGR must still PASS (regression guard)."""
    rev = [100, 135, 182, 246, 332]
    s = score_layer_1(TickerFinancials(ticker="SW", industry="45", revenue_5y=rev))
    assert s.verdict == "PASS"
    assert s.score >= 7


def test_l1_utility_slow_non_regression():
    """Utility sector 55 at 5%/y must still PASS (regression guard)."""
    rev = [100, 105, 110, 116, 122]
    s = score_layer_1(TickerFinancials(ticker="UTL", industry="55", revenue_5y=rev))
    assert s.verdict == "PASS"


# ── Layer 3 — cyclical 3y-avg ROIC ────────────────────────────────────────────

def _make_l3_cyclical(op_income_5y, invested_capital_5y, **kw) -> TickerFinancials:
    """Minimal cyclical TickerFinancials for L3 testing."""
    n = len(op_income_5y)
    return TickerFinancials(
        ticker="OIL",
        industry="10",
        revenue_5y=[1000] * n,
        net_income_5y=[max(0, o * 0.7) for o in op_income_5y],
        operating_income_5y=op_income_5y,
        ocf_5y=[max(0, o * 0.9) for o in op_income_5y],
        capex_5y=[50] * n,
        sbc_5y=[0] * n,
        invested_capital_5y=invested_capital_5y,
        **kw,
    )


def test_l3_cyclical_trough_year_uses_3y_avg_roic():
    """An oil company with excellent ROIC most years but a single trough year (negative op_income)
    should not get a FAIL from spread scoring when 3y avg is positive.

    op_income: [200, 180, -50 (trough), 160, 190] against IC=1000 each year.
    Latest-year ROIC = -50*0.79 / 1000 = -3.95% → spread = -12.95% → spread_score 0 → FAIL.
    3y-avg ROIC = mean([-50, 160, 190]*0.79/1000) = mean([-3.95%, 12.6%, 15%]) = 7.9% → spread positive.
    """
    op = [200, 180, -50, 160, 190]
    ic = [1000, 1000, 1000, 1000, 1000]
    s = score_layer_3(_make_l3_cyclical(op, ic))
    assert s.verdict in ("PASS", "CAUTION"), (
        f"Cyclical with single trough year should not FAIL L3; got {s.verdict}: {s.rationale}"
    )
    assert s.inputs.get("roic_3y_avg") is not None
    assert "cyclical" in s.rationale


def test_l3_non_cyclical_roic_3y_avg_is_none():
    """Non-cyclical (IT sector 45) should not use 3y-avg — roic_3y_avg must be None."""
    f = TickerFinancials(
        ticker="MSFT", industry="45",
        revenue_5y=[100, 120, 140, 160, 180],
        net_income_5y=[20, 25, 30, 36, 44],
        operating_income_5y=[25, 32, 40, 48, 58],
        ocf_5y=[30, 38, 46, 55, 66],
        capex_5y=[5, 6, 8, 10, 12],
        sbc_5y=[5, 6, 7, 8, 9],
        invested_capital_5y=[80, 85, 90, 100, 110],
    )
    s = score_layer_3(f)
    assert s.inputs.get("roic_3y_avg") is None


def test_l3_cyclical_consistently_negative_roic_still_fails():
    """Cyclical with 3 out of 5 years of negative op_income hits historical_loss_penalty (50% threshold).
    Score should be low (FAIL or CAUTION)."""
    op = [-100, -80, 50, -90, 30]
    ic = [1000] * 5
    s = score_layer_3(_make_l3_cyclical(op, ic))
    # 3/5 = 60% negative years >= 50% threshold → historical_loss_penalty = 2
    assert s.inputs.get("historical_loss_penalty") == 2
    assert s.verdict in ("CAUTION", "FAIL")

"""Insurance scorer tests — PGR, BRK.B, AIG archetypes."""
import pytest

from tradingview_mcp.core.services.fundamentals.providers.base import TickerFinancials
from tradingview_mcp.core.services.fundamentals.scorers.financial.insurance_scorer import (
    score, _score_l1_insurance, _score_l2_insurance, _score_l3_insurance, _score_l5_insurance,
)


# ── Fixtures ───────────────────────────────────────────────────────────────

def _pgr_like() -> TickerFinancials:
    """Progressive — auto-heavy P&C, consistent premium growth, low combined ratio."""
    return TickerFinancials(
        ticker="PGR",
        industry="40",
        sub_industry="Insurance—Property & Casualty",
        sector_name="Financial Services",
        industry_name="Insurance—Property & Casualty",
        gics_full="Financial Services / Insurance—Property & Casualty",
        premium_earned_5y=[30e9, 34e9, 38e9, 45e9, 55e9],
        losses_incurred_5y=[21e9, 24e9, 27e9, 32e9, 39e9],
        expenses_incurred_5y=[4e9, 4.5e9, 5e9, 5.8e9, 7e9],
        investment_income_fin_5y=[2e9, 2.3e9, 2.6e9, 3e9, 3.5e9],
        net_income_5y=[3e9, 3.5e9, 4e9, 5e9, 7e9],
        revenue_5y=[32e9, 36e9, 40e9, 47e9, 58e9],
        operating_income_5y=[5e9, 5.5e9, 6e9, 7.5e9, 10e9],
        equity_5y=[15e9, 17e9, 20e9, 23e9, 28e9],
        total_debt_5y=[4e9, 4.2e9, 4.5e9, 4.8e9, 5e9],
        cash_5y=[2e9, 2.2e9, 2.4e9, 2.6e9, 3e9],
        da_5y=[0.5e9, 0.55e9, 0.6e9, 0.65e9, 0.7e9],
        ebitda_5y=[5.5e9, 6.05e9, 6.6e9, 8.15e9, 10.7e9],
        diluted_shares_5y=[580e6, 570e6, 560e6, 550e6, 540e6],
        gross_profit_5y=[7e9, 8e9, 9e9, 11e9, 14e9],  # needed for L4
        invested_capital_5y=[19e9, 21e9, 24e9, 28e9, 33e9],
        dividend_paid_5y=[1e9, 1.2e9, 1.4e9, 1.6e9, 2e9],
        buyback_5y=[0.5e9, 0.6e9, 0.7e9, 0.8e9, 1e9],
        price_current=220.0,
        market_cap_current=128e9,
    )


def _brk_like() -> TickerFinancials:
    """BRK.B — insurance-anchored conglomerate, large investment income."""
    return TickerFinancials(
        ticker="BRK.B",
        industry="40",
        sub_industry="Insurance—Diversified",
        sector_name="Financial Services",
        industry_name="Insurance—Diversified",
        gics_full="Financial Services / Insurance—Diversified",
        premium_earned_5y=[60e9, 65e9, 70e9, 76e9, 83e9],
        losses_incurred_5y=[45e9, 48e9, 52e9, 57e9, 62e9],
        expenses_incurred_5y=[6e9, 6.5e9, 7e9, 7.5e9, 8e9],
        investment_income_fin_5y=[20e9, 22e9, 25e9, 28e9, 32e9],
        net_income_5y=[35e9, 38e9, 42e9, 45e9, 50e9],
        revenue_5y=[250e9, 270e9, 285e9, 302e9, 320e9],
        operating_income_5y=[40e9, 43e9, 47e9, 51e9, 56e9],
        equity_5y=[350e9, 380e9, 410e9, 440e9, 470e9],
        total_debt_5y=[30e9, 32e9, 33e9, 34e9, 35e9],
        cash_5y=[130e9, 140e9, 150e9, 160e9, 170e9],
        da_5y=[8e9, 8.5e9, 9e9, 9.5e9, 10e9],
        ebitda_5y=[48e9, 51.5e9, 56e9, 60.5e9, 66e9],
        diluted_shares_5y=[1.32e9, 1.30e9, 1.28e9, 1.26e9, 1.24e9],
        gross_profit_5y=[120e9, 130e9, 140e9, 150e9, 160e9],  # needed for L4
        invested_capital_5y=[380e9, 412e9, 443e9, 474e9, 505e9],
        dividend_paid_5y=[0, 0, 0, 0, 0],
        buyback_5y=[2e9, 3e9, 4e9, 5e9, 6e9],
        price_current=400.0,
        market_cap_current=520e9,
    )


def _aig_like() -> TickerFinancials:
    """AIG — P&C turnaround, combined ratio compressed, improving."""
    return TickerFinancials(
        ticker="AIG",
        industry="40",
        sub_industry="Insurance—Property & Casualty",
        sector_name="Financial Services",
        industry_name="Insurance—Property & Casualty",
        gics_full="Financial Services / Insurance—Property & Casualty",
        premium_earned_5y=[22e9, 23e9, 24e9, 25e9, 26e9],
        losses_incurred_5y=[17e9, 17.5e9, 17.8e9, 18e9, 18.5e9],
        expenses_incurred_5y=[5e9, 5.2e9, 5.3e9, 5.4e9, 5.5e9],
        investment_income_fin_5y=[3e9, 3.2e9, 3.4e9, 3.6e9, 3.8e9],
        net_income_5y=[3e9, 3.5e9, 4e9, 4.5e9, 5e9],
        revenue_5y=[25e9, 26e9, 27e9, 28e9, 29e9],
        operating_income_5y=[4e9, 4.5e9, 5e9, 5.5e9, 6e9],
        equity_5y=[40e9, 42e9, 44e9, 46e9, 48e9],
        total_debt_5y=[10e9, 9.5e9, 9e9, 8.5e9, 8e9],
        cash_5y=[3e9, 3.2e9, 3.4e9, 3.6e9, 3.8e9],
        da_5y=[0.5e9, 0.52e9, 0.54e9, 0.56e9, 0.58e9],
        ebitda_5y=[4.5e9, 5.02e9, 5.54e9, 6.06e9, 6.58e9],
        diluted_shares_5y=[750e6, 720e6, 690e6, 660e6, 630e6],
        gross_profit_5y=[8e9, 8.5e9, 9e9, 9.6e9, 10.2e9],  # needed for L4
        invested_capital_5y=[50e9, 51.5e9, 53e9, 54.5e9, 56e9],
        dividend_paid_5y=[0.6e9, 0.65e9, 0.7e9, 0.75e9, 0.8e9],
        buyback_5y=[1e9, 1.5e9, 2e9, 2.5e9, 3e9],
        price_current=75.0,
        market_cap_current=47e9,
    )


# ── Layer-level tests ──────────────────────────────────────────────────────

def test_l1_pgr_premium_growth_passes():
    s = _score_l1_insurance(_pgr_like())
    assert s.layer_id == 1
    assert s.verdict == "PASS"
    # CAGR ~16%/y
    assert "premium" in s.rationale.lower() or "cagr" in s.rationale.lower()


def test_l2_pgr_combined_ratio_passes():
    s = _score_l2_insurance(_pgr_like())
    assert s.layer_id == 2
    # PGR combined ratio = (39+7)/55 ≈ 84% → PASS
    assert s.verdict == "PASS"
    assert "combined" in s.rationale.lower()


def test_l2_high_combined_ratio_fails():
    f = _pgr_like()
    # Force combined ratio > 105%
    f.losses_incurred_5y = [32e9, 35e9, 40e9, 48e9, 58e9]
    s = _score_l2_insurance(f)
    assert s.verdict in ("CAUTION", "FAIL")


def test_l3_brk_investment_income_quality():
    s = _score_l3_insurance(_brk_like())
    assert s.layer_id == 3
    # Large investment income → PASS or CAUTION
    assert s.verdict in ("PASS", "CAUTION")


def test_l5_aig_reserve_adequate():
    s = _score_l5_insurance(_aig_like())
    assert s.layer_id == 5
    # equity ~48B / premiums ~26B = 1.85x → PASS
    assert s.verdict == "PASS"


# ── Full score tests ───────────────────────────────────────────────────────

def test_pgr_full_score_not_reject():
    report = score(_pgr_like())
    assert report.quality_verdict != "QUALITY_REJECT"
    assert report.composite_score > 3


def test_brk_full_score_not_reject():
    report = score(_brk_like())
    assert report.quality_verdict != "QUALITY_REJECT"


def test_aig_full_score_not_reject():
    report = score(_aig_like())
    assert report.quality_verdict != "QUALITY_REJECT"


def test_insurance_report_has_7_layers():
    report = score(_pgr_like())
    layer_ids = {v.layer_id for v in report.layers.values()}
    assert layer_ids >= {1, 2, 3, 4, 5, 6, 7}

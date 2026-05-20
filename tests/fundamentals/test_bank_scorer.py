"""Bank scorer tests — golden fixtures for JPM, WFC, MS archetypes."""
import pytest

from tradingview_mcp.core.services.fundamentals.providers.base import TickerFinancials
from tradingview_mcp.core.services.fundamentals.scorers.financial.bank_scorer import (
    score, _score_l1_bank, _score_l2_bank, _score_l3_bank, _score_l5_bank,
)


# ── Helpers ────────────────────────────────────────────────────────────────

def _jpm_like() -> TickerFinancials:
    """Large diversified bank with strong NIM and low efficiency ratio."""
    return TickerFinancials(
        ticker="JPM",
        industry="40",
        sub_industry="Banks—Diversified",
        sector_name="Financial Services",
        industry_name="Banks—Diversified",
        gics_full="Financial Services / Banks—Diversified",
        # Interest income growing ~8%/y
        interest_income_5y=[50e9, 54e9, 58e9, 63e9, 70e9],
        noninterest_income_5y=[20e9, 22e9, 23e9, 25e9, 27e9],
        interest_expense_5y=[5e9, 5.5e9, 6e9, 8e9, 12e9],
        total_loans_5y=[900e9, 950e9, 1000e9, 1050e9, 1100e9],
        total_deposits_5y=[1100e9, 1150e9, 1200e9, 1280e9, 1350e9],
        # Operating income (NII + NONI - noninterest expense)
        operating_income_5y=[30e9, 33e9, 35e9, 38e9, 40e9],
        net_income_5y=[22e9, 25e9, 27e9, 29e9, 32e9],
        gross_profit_5y=[55e9, 60e9, 65e9, 72e9, 80e9],  # needed for L4 Moat
        diluted_shares_5y=[3.0e9, 2.95e9, 2.9e9, 2.85e9, 2.80e9],
        equity_5y=[200e9, 210e9, 220e9, 230e9, 240e9],
        total_debt_5y=[300e9, 310e9, 320e9, 330e9, 340e9],
        cash_5y=[20e9, 22e9, 24e9, 26e9, 28e9],
        da_5y=[3e9, 3.2e9, 3.4e9, 3.6e9, 3.8e9],
        ebitda_5y=[33e9, 36e9, 38e9, 42e9, 44e9],
        dividend_paid_5y=[8e9, 9e9, 10e9, 11e9, 12e9],
        buyback_5y=[6e9, 7e9, 8e9, 9e9, 10e9],
        revenue_5y=[100e9, 108e9, 116e9, 127e9, 140e9],
        invested_capital_5y=[500e9, 520e9, 540e9, 560e9, 580e9],
        price_current=200.0,
        market_cap_current=580e9,
    )


def _wfc_like() -> TickerFinancials:
    """Consumer-heavy bank — adequate NIM, decent efficiency."""
    return TickerFinancials(
        ticker="WFC",
        industry="40",
        sub_industry="Banks—Diversified",
        sector_name="Financial Services",
        industry_name="Banks—Diversified",
        gics_full="Financial Services / Banks—Diversified",
        interest_income_5y=[45e9, 46e9, 47e9, 50e9, 55e9],
        noninterest_income_5y=[14e9, 14.5e9, 15e9, 15.5e9, 16e9],
        interest_expense_5y=[4e9, 4.2e9, 4.5e9, 6e9, 9e9],
        total_loans_5y=[850e9, 870e9, 880e9, 900e9, 920e9],
        total_deposits_5y=[1050e9, 1080e9, 1100e9, 1130e9, 1150e9],
        operating_income_5y=[18e9, 20e9, 22e9, 24e9, 25e9],
        net_income_5y=[12e9, 14e9, 15e9, 16e9, 17e9],
        gross_profit_5y=[35e9, 38e9, 41e9, 45e9, 49e9],  # needed for L4 Moat
        diluted_shares_5y=[4.0e9, 3.9e9, 3.8e9, 3.7e9, 3.6e9],
        equity_5y=[180e9, 185e9, 190e9, 195e9, 200e9],
        total_debt_5y=[250e9, 260e9, 265e9, 270e9, 275e9],
        cash_5y=[15e9, 16e9, 17e9, 18e9, 20e9],
        da_5y=[2.5e9, 2.6e9, 2.7e9, 2.8e9, 2.9e9],
        ebitda_5y=[20.5e9, 22.6e9, 24.7e9, 26.8e9, 27.9e9],
        dividend_paid_5y=[5e9, 5.5e9, 6e9, 6.5e9, 7e9],
        buyback_5y=[3e9, 4e9, 5e9, 6e9, 7e9],
        revenue_5y=[79e9, 82e9, 85e9, 90e9, 96e9],
        invested_capital_5y=[430e9, 445e9, 455e9, 465e9, 475e9],
        price_current=60.0,
        market_cap_current=220e9,
    )


def _ms_like() -> TickerFinancials:
    """Capital-markets-heavy bank — volatile revenues, OK margins."""
    return TickerFinancials(
        ticker="MS",
        industry="40",
        sub_industry="Capital Markets",
        sector_name="Financial Services",
        industry_name="Capital Markets",
        gics_full="Financial Services / Capital Markets",
        interest_income_5y=[10e9, 12e9, 11e9, 14e9, 15e9],
        noninterest_income_5y=[40e9, 45e9, 38e9, 50e9, 52e9],
        interest_expense_5y=[3e9, 3.5e9, 3.2e9, 4e9, 5e9],
        total_loans_5y=[150e9, 160e9, 155e9, 170e9, 180e9],
        total_deposits_5y=[200e9, 210e9, 205e9, 220e9, 230e9],
        operating_income_5y=[14e9, 16e9, 12e9, 18e9, 19e9],
        net_income_5y=[10e9, 12e9, 9e9, 13e9, 14e9],
        gross_profit_5y=[30e9, 34e9, 28e9, 38e9, 40e9],  # needed for L4
        diluted_shares_5y=[1.6e9, 1.58e9, 1.56e9, 1.54e9, 1.52e9],
        equity_5y=[90e9, 95e9, 97e9, 100e9, 105e9],
        total_debt_5y=[200e9, 210e9, 205e9, 215e9, 220e9],
        cash_5y=[18e9, 20e9, 19e9, 22e9, 24e9],
        da_5y=[1e9, 1.1e9, 1.1e9, 1.2e9, 1.2e9],
        ebitda_5y=[15e9, 17.1e9, 13.1e9, 19.2e9, 20.2e9],
        dividend_paid_5y=[2e9, 2.5e9, 3e9, 3.5e9, 4e9],
        buyback_5y=[2e9, 3e9, 2e9, 4e9, 5e9],
        revenue_5y=[54e9, 59e9, 53e9, 64e9, 67e9],
        invested_capital_5y=[290e9, 305e9, 302e9, 315e9, 325e9],
        price_current=100.0,
        market_cap_current=165e9,
    )


# ── Layer-level tests ──────────────────────────────────────────────────────

def test_l1_jpm_strong_growth_passes():
    s = _score_l1_bank(_jpm_like())
    assert s.verdict == "PASS"
    assert s.score >= 7
    assert s.layer_id == 1


def test_l1_flat_growth_caution():
    f = _jpm_like()
    f.interest_income_5y = [50e9, 50.5e9, 51e9, 51.5e9, 52e9]  # ~1%/y
    f.noninterest_income_5y = [20e9, 20.2e9, 20.4e9, 20.6e9, 20.8e9]
    s = _score_l1_bank(f)
    assert s.verdict in ("CAUTION", "FAIL")


def test_l2_nim_jpm_passes():
    s = _score_l2_bank(_jpm_like())
    assert s.layer_id == 2
    assert s.verdict in ("PASS", "CAUTION")
    assert "NIM" in s.rationale.upper() or "nim" in s.rationale.lower()


def test_l2_nim_insufficient_data_returns_caution():
    f = TickerFinancials(ticker="X", industry="40")
    s = _score_l2_bank(f)
    assert s.layer_id == 2
    assert s.verdict == "CAUTION"
    assert s.score == 4


def test_l3_efficiency_jpm_passes():
    s = _score_l3_bank(_jpm_like())
    assert s.layer_id == 3
    assert s.verdict in ("PASS", "CAUTION")


def test_l5_loan_deposit_jpm_good():
    s = _score_l5_bank(_jpm_like())
    assert s.layer_id == 5
    # LtD = 1100/1350 = ~81% → PASS
    assert s.verdict in ("PASS", "CAUTION")
    assert "loan-to-deposit" in s.rationale.lower()


# ── Full score tests ───────────────────────────────────────────────────────

def test_jpm_full_score_not_reject():
    report = score(_jpm_like())
    assert report.quality_verdict != "QUALITY_REJECT"
    assert report.composite_score > 3


def test_wfc_full_score_not_reject():
    report = score(_wfc_like())
    assert report.quality_verdict != "QUALITY_REJECT"
    assert report.composite_score > 3


def test_ms_full_score_uses_bank_scorer():
    """MS capital-markets-heavy — routes to bank scorer, composite > 0 (not a data error)."""
    report = score(_ms_like())
    # Spec: GS/MS may still land in WATCH or REJECT — they're cyclical/compressed NIM.
    # The key is the scorer IS reading real signal (high efficiency ratio), not failing
    # due to dialect mismatch. Verify composite > 4 (actual data, not zero).
    assert report.composite_score > 4
    assert report.ticker == "MS"


def test_bank_report_has_7_layers():
    """All 7 layers (L1-L6 + L7) present in the report."""
    report = score(_jpm_like())
    layer_ids = {v.layer_id for v in report.layers.values()}
    assert layer_ids >= {1, 2, 3, 4, 5, 6, 7}


def test_bank_report_ticker_preserved():
    report = score(_jpm_like())
    assert report.ticker == "JPM"

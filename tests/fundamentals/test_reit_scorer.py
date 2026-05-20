"""REIT scorer tests — PLD, AMT, SPG archetypes."""
import pytest

from tradingview_mcp.core.services.fundamentals.providers.base import TickerFinancials
from tradingview_mcp.core.services.fundamentals.scorers.financial.reit_scorer import (
    score, _score_l1_reit, _score_l2_reit, _score_l3_reit, _score_l5_reit,
)


# ── Fixtures ───────────────────────────────────────────────────────────────

def _pld_like() -> TickerFinancials:
    """Prologis — industrial logistics REIT, strong rental growth, NOI ~75%."""
    return TickerFinancials(
        ticker="PLD",
        industry="60",
        sub_industry="REIT—Industrial",
        sector_name="Real Estate",
        industry_name="REIT—Industrial",
        gics_full="Real Estate / REIT—Industrial",
        rental_income_5y=[3.5e9, 4e9, 4.7e9, 5.6e9, 7e9],
        ffo_5y=[2.5e9, 2.9e9, 3.4e9, 4.1e9, 5.1e9],
        net_income_5y=[1.5e9, 2e9, 2.5e9, 3e9, 3.8e9],
        revenue_5y=[3.5e9, 4e9, 4.7e9, 5.6e9, 7e9],
        gross_profit_5y=[2.6e9, 3e9, 3.5e9, 4.2e9, 5.2e9],  # ~75% NOI margin
        operating_income_5y=[2e9, 2.4e9, 2.8e9, 3.4e9, 4.2e9],
        equity_5y=[20e9, 24e9, 29e9, 35e9, 42e9],
        total_debt_5y=[18e9, 20e9, 22e9, 24e9, 26e9],
        cash_5y=[0.5e9, 0.6e9, 0.7e9, 0.8e9, 1e9],
        da_5y=[1e9, 1.1e9, 1.2e9, 1.3e9, 1.4e9],
        ebitda_5y=[3e9, 3.5e9, 4e9, 4.7e9, 5.6e9],
        diluted_shares_5y=[740e6, 748e6, 756e6, 764e6, 772e6],
        dividend_paid_5y=[1.5e9, 1.7e9, 1.9e9, 2.2e9, 2.7e9],
        buyback_5y=[0, 0, 0, 0, 0],
        price_current=125.0,
        market_cap_current=100e9,
    )


def _amt_like() -> TickerFinancials:
    """American Tower — telecom REIT, steady rental income, higher leverage."""
    return TickerFinancials(
        ticker="AMT",
        industry="60",
        sub_industry="REIT—Office",  # using Office to test variant routing
        sector_name="Real Estate",
        industry_name="REIT—Office",
        gics_full="Real Estate / REIT—Office",
        rental_income_5y=[7e9, 7.6e9, 8.2e9, 8.9e9, 9.5e9],
        ffo_5y=[4.2e9, 4.6e9, 5e9, 5.4e9, 5.8e9],
        net_income_5y=[1.5e9, 1.7e9, 1.9e9, 2.1e9, 2.3e9],
        revenue_5y=[7e9, 7.6e9, 8.2e9, 8.9e9, 9.5e9],
        gross_profit_5y=[5.2e9, 5.7e9, 6.2e9, 6.8e9, 7.2e9],  # ~75% NOI
        operating_income_5y=[2.5e9, 2.8e9, 3.1e9, 3.4e9, 3.7e9],
        equity_5y=[5e9, 6e9, 7e9, 8e9, 9e9],
        total_debt_5y=[40e9, 42e9, 44e9, 46e9, 48e9],
        cash_5y=[1.5e9, 1.6e9, 1.7e9, 1.8e9, 2e9],
        da_5y=[2e9, 2.1e9, 2.2e9, 2.3e9, 2.4e9],
        ebitda_5y=[4.5e9, 4.9e9, 5.3e9, 5.7e9, 6.1e9],
        diluted_shares_5y=[420e6, 428e6, 436e6, 444e6, 452e6],
        dividend_paid_5y=[2.2e9, 2.5e9, 2.8e9, 3e9, 3.2e9],
        buyback_5y=[0, 0, 0, 0, 0],
        price_current=185.0,
        market_cap_current=85e9,
    )


def _spg_like() -> TickerFinancials:
    """Simon Property Group — retail REIT, recovering post-COVID."""
    return TickerFinancials(
        ticker="SPG",
        industry="60",
        sub_industry="REIT—Retail",
        sector_name="Real Estate",
        industry_name="REIT—Retail",
        gics_full="Real Estate / REIT—Retail",
        rental_income_5y=[4.5e9, 4.1e9, 4.4e9, 4.7e9, 5.0e9],  # COVID dip, recovery
        ffo_5y=[3.5e9, 3.2e9, 3.6e9, 3.9e9, 4.2e9],
        net_income_5y=[2e9, 1.8e9, 2.1e9, 2.3e9, 2.5e9],
        revenue_5y=[4.5e9, 4.1e9, 4.4e9, 4.7e9, 5.0e9],
        gross_profit_5y=[3.2e9, 2.9e9, 3.1e9, 3.3e9, 3.5e9],
        operating_income_5y=[2.2e9, 2.0e9, 2.3e9, 2.6e9, 2.8e9],
        equity_5y=[5e9, 4.5e9, 5e9, 5.5e9, 6e9],
        total_debt_5y=[25e9, 26e9, 26.5e9, 27e9, 27.5e9],
        cash_5y=[1.5e9, 1.6e9, 1.7e9, 1.8e9, 2e9],
        da_5y=[0.8e9, 0.85e9, 0.9e9, 0.95e9, 1e9],
        ebitda_5y=[3e9, 2.85e9, 3.2e9, 3.55e9, 3.8e9],
        diluted_shares_5y=[325e6, 320e6, 318e6, 316e6, 314e6],
        dividend_paid_5y=[2e9, 1e9, 1.8e9, 2.1e9, 2.3e9],  # cut then restored
        buyback_5y=[0, 0, 0, 0.2e9, 0.4e9],
        invested_capital_5y=[30e9, 30.5e9, 31.5e9, 32.5e9, 33.5e9],
        price_current=160.0,
        market_cap_current=50e9,
    )


# ── Layer-level tests ──────────────────────────────────────────────────────

def test_l1_pld_rental_growth_passes():
    s = _score_l1_reit(_pld_like())
    assert s.layer_id == 1
    assert s.verdict == "PASS"
    # CAGR ~19%/y from 3.5B to 7B over 5y
    assert s.inputs.get("cagr", 0) > 0.10


def test_l1_flat_rental_caution():
    f = _spg_like()
    # COVID pattern: dip then flat
    f.rental_income_5y = [4.5e9, 4.1e9, 4.0e9, 4.1e9, 4.2e9]
    s = _score_l1_reit(f)
    assert s.verdict in ("CAUTION", "FAIL")


def test_l2_pld_noi_margin_passes():
    s = _score_l2_reit(_pld_like())
    assert s.layer_id == 2
    # NOI margin ~74% → PASS
    assert s.verdict in ("PASS", "CAUTION")
    assert "noi" in s.rationale.lower()


def test_l3_pld_ffo_payout_sustainable():
    s = _score_l3_reit(_pld_like())
    assert s.layer_id == 3
    # Payout = div/FFO = 2.7/5.1 ≈ 53% → PASS
    assert s.verdict in ("PASS", "CAUTION")


def test_l3_unsustainable_payout_fails():
    f = _pld_like()
    # Force dividend > FFO (unsustainable)
    f.dividend_paid_5y = [2e9, 2.5e9, 3e9, 4.5e9, 6e9]  # div > FFO in last year
    s = _score_l3_reit(f)
    assert s.verdict in ("CAUTION", "FAIL")


def test_l5_amt_leverage_check():
    s = _score_l5_reit(_amt_like())
    assert s.layer_id == 5
    # AMT debt/assets ~84% → risky but not instant reject; CAUTION expected
    assert s.verdict in ("CAUTION", "FAIL")


def test_l5_pld_leverage_reasonable():
    s = _score_l5_reit(_pld_like())
    assert s.layer_id == 5
    # PLD: debt 26B, assets ~68B → D/A ~38% → PASS or CAUTION
    assert s.verdict in ("PASS", "CAUTION")


# ── Full score tests ───────────────────────────────────────────────────────

def test_pld_full_score_not_reject():
    report = score(_pld_like())
    assert report.quality_verdict != "QUALITY_REJECT"
    assert report.composite_score > 3


def test_spg_full_score_coherent():
    """SPG has recovering metrics — scorer reads real signal (leverage + slow growth).

    Spec: 'SPG still might be WATCH/REJECT (cyclical compress)'. The key is that
    the composite > 3 (real data, not a dialect-miss zero) even when verdict is REJECT.
    """
    report = score(_spg_like())
    # SPG with COVID-hit rental CAGR and high D/A may get REJECT for real reasons
    # (not because scorer can't read the data). Composite should be > 3.
    assert report.composite_score > 3
    assert report.ticker == "SPG"


def test_reit_report_has_7_layers():
    report = score(_pld_like())
    layer_ids = {v.layer_id for v in report.layers.values()}
    assert layer_ids >= {1, 2, 3, 4, 5, 6, 7}


def test_reit_report_ticker_preserved():
    report = score(_pld_like())
    assert report.ticker == "PLD"

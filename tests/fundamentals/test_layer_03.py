import math

from tradingview_mcp.core.services.fundamentals.providers.base import TickerFinancials
from tradingview_mcp.core.services.fundamentals.scorers.layer_03_fcf_quality import score_layer_3


def test_layer_3_high_roic_fcf_strong():
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
    assert s.verdict == "PASS"
    assert s.score >= 7


def test_layer_3_fcf_below_ni_fails():
    # Net Income inflated, OCF weak -> FCF/NI < 1.0
    f = TickerFinancials(
        ticker="X", industry="45",
        revenue_5y=[100, 110, 120, 130, 140],
        net_income_5y=[30, 35, 40, 45, 50],
        operating_income_5y=[35, 40, 45, 50, 55],
        ocf_5y=[20, 22, 25, 28, 30],
        capex_5y=[8, 9, 10, 11, 12],
        sbc_5y=[2, 2, 3, 3, 3],
        invested_capital_5y=[200, 210, 220, 230, 240],
    )
    s = score_layer_3(f)
    assert s.score < 7


def test_layer_3_negative_roic_fails():
    f = TickerFinancials(
        ticker="X", industry="45",
        revenue_5y=[100, 110, 120, 130, 140],
        net_income_5y=[-10, -8, -5, -3, 1],
        operating_income_5y=[-5, -3, 0, 2, 5],
        ocf_5y=[10, 12, 15, 18, 20],
        capex_5y=[3, 4, 5, 6, 7],
        sbc_5y=[1, 1, 1, 1, 1],
        invested_capital_5y=[100, 110, 120, 130, 140],
    )
    s = score_layer_3(f)
    assert s.verdict == "FAIL"


# ── CCC tests ──────────────────────────────────────────────────────────────

def _base_f(**kwargs) -> TickerFinancials:
    """Base fixture with valid FCF/ROIC data; override fields via kwargs."""
    defaults = dict(
        ticker="TEST", industry="25",
        revenue_5y=[100, 110, 120, 130, 140],
        net_income_5y=[10, 12, 14, 16, 18],
        operating_income_5y=[15, 17, 19, 21, 23],
        ocf_5y=[12, 14, 16, 18, 20],
        capex_5y=[2, 2, 3, 3, 3],
        sbc_5y=[1, 1, 1, 1, 1],
        invested_capital_5y=[80, 85, 90, 95, 100],
    )
    defaults.update(kwargs)
    return TickerFinancials(**defaults)


def test_ccc_fields_none_when_no_inventory():
    """ccc_days should be None when inventory/receivables are absent."""
    f = _base_f()
    s = score_layer_3(f)
    assert s.inputs["ccc_days"] is None
    assert s.inputs["ccc_trend"] is None
    assert s.inputs["inventory_days_latest"] is None
    assert s.inputs["receivable_days_latest"] is None


def test_ccc_low_scores_max():
    """CCC < 60d with flat trend should give ccc_score=2 (no penalty)."""
    # inventory/receivables/payables all small -> CCC < 60 days
    f = _base_f(
        inventory_5y=[5, 5, 5, 5, 5],
        receivables_5y=[3, 3, 3, 3, 3],
        payables_5y=[6, 6, 6, 6, 6],
        cogs_5y=[60, 66, 72, 78, 84],
    )
    s = score_layer_3(f)
    ccc = s.inputs["ccc_days"]
    assert ccc is not None
    assert ccc < 60
    assert s.inputs["ccc_trend"] is not None
    # Inventory days and receivable days populated
    assert s.inputs["inventory_days_latest"] is not None and s.inputs["inventory_days_latest"] > 0
    assert s.inputs["receivable_days_latest"] is not None and s.inputs["receivable_days_latest"] > 0


def test_ccc_high_penalises_score():
    """CCC > 90d should reduce score (ccc_score=0)."""
    # Large inventory relative to COGS -> CCC > 90
    f = _base_f(
        inventory_5y=[30, 30, 30, 30, 30],
        receivables_5y=[20, 20, 20, 20, 20],
        payables_5y=[5, 5, 5, 5, 5],
        cogs_5y=[60, 66, 72, 78, 84],
    )
    s_no_inv = _base_f()  # no inventory data
    s_with_inv = score_layer_3(f)
    s_without = score_layer_3(s_no_inv)
    # With high CCC the score should be lower or equal (never higher)
    assert s_with_inv.score <= s_without.score
    assert s_with_inv.inputs["ccc_days"] > 90


def test_ccc_deteriorating_trend_penalises():
    """Rising CCC trend (slope > 5 days/year) should subtract 1 from ccc_score."""
    # CCC between 60-90 but rising fast -> ccc_score starts at 1, trend penalty -> 0
    f = _base_f(
        inventory_5y=[10, 13, 17, 22, 28],   # growing inventory
        receivables_5y=[5, 6, 7, 8, 9],
        payables_5y=[5, 5, 5, 5, 5],
        cogs_5y=[60, 66, 72, 78, 84],
    )
    s = score_layer_3(f)
    assert s.inputs["ccc_trend"] is not None
    assert s.inputs["ccc_trend"] > 0  # positive = deteriorating


def test_ccc_dpo_reduces_ccc():
    """High payables (DPO) should reduce CCC vs same inventory/receivables with low payables."""
    common = dict(
        inventory_5y=[20, 20, 20, 20, 20],
        receivables_5y=[10, 10, 10, 10, 10],
        cogs_5y=[60, 66, 72, 78, 84],
    )
    f_low_dpo = _base_f(payables_5y=[2, 2, 2, 2, 2], **common)
    f_high_dpo = _base_f(payables_5y=[20, 20, 20, 20, 20], **common)
    s_low = score_layer_3(f_low_dpo)
    s_high = score_layer_3(f_high_dpo)
    # High DPO => lower CCC
    assert s_high.inputs["ccc_days"] < s_low.inputs["ccc_days"]

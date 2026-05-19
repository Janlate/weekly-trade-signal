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

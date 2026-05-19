from tradingview_mcp.core.services.fundamentals.providers.base import TickerFinancials
from tradingview_mcp.core.services.fundamentals.scorers.layer_07_valuation import score_layer_7


def test_layer_7_undervalued_high_mos():
    f = TickerFinancials(
        ticker="X", industry="45",
        revenue_5y=[100, 115, 132, 152, 175],
        operating_income_5y=[25, 30, 36, 43, 52],
        capex_5y=[5, 6, 7, 8, 9],
        net_income_5y=[20, 24, 29, 34, 41],
        diluted_shares_5y=[100, 100, 100, 100, 100],
        total_debt_5y=[10, 10, 10, 10, 10],
        cash_5y=[50, 60, 70, 80, 90],
        price_current=5,   # below DCF fair value (~8.5/share) → MOS > 0
        market_cap_current=500,
        forward_eps_growth_1y=0.15,
    )
    s = score_layer_7(f)
    assert s.inputs["mos_pct"] > 0
    assert "fair_value" in s.inputs


def test_layer_7_overvalued_negative_mos():
    f = TickerFinancials(
        ticker="X", industry="45",
        revenue_5y=[100, 110, 120, 130, 140],
        operating_income_5y=[10, 11, 12, 13, 14],
        capex_5y=[5, 6, 7, 8, 9],
        net_income_5y=[5, 6, 7, 8, 9],
        diluted_shares_5y=[100, 100, 100, 100, 100],
        total_debt_5y=[100, 100, 100, 100, 100],
        cash_5y=[10, 10, 10, 10, 10],
        price_current=200,  # very expensive
        market_cap_current=20000,
        forward_eps_growth_1y=0.05,
    )
    s = score_layer_7(f)
    assert s.inputs["mos_pct"] < 0


def test_layer_7_insufficient_data():
    f = TickerFinancials(ticker="X", industry="45")
    s = score_layer_7(f)
    assert s.verdict == "INSUFFICIENT_DATA"

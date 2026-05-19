from tradingview_mcp.core.services.fundamentals.providers.base import TickerFinancials
from tradingview_mcp.core.services.fundamentals.scorers.layer_06_capital_alloc import score_layer_6


def test_layer_6_strong_buyback_below_current():
    f = TickerFinancials(
        ticker="X", industry="45",
        diluted_shares_5y=[1000, 950, 900, 870, 850],
        buyback_5y=[1000, 1200, 1400, 1600, 1800],
        dividend_paid_5y=[100, 110, 120, 130, 140],
        operating_income_5y=[200, 220, 250, 280, 320],
        invested_capital_5y=[800, 820, 840, 860, 880],
        cash_5y=[100, 120, 140, 160, 180],
        market_cap_current=300e9,
        price_current=420,
    )
    s = score_layer_6(f)
    assert s.score >= 6


def test_layer_6_insufficient_data():
    f = TickerFinancials(ticker="X", industry="45")
    s = score_layer_6(f)
    assert s.verdict == "INSUFFICIENT_DATA"


def test_layer_6_cash_hoarding_penalty():
    # huge cash, no dividend, no buybacks -> cash_penalty applies
    f = TickerFinancials(
        ticker="X", industry="45",
        diluted_shares_5y=[1000, 1000, 1000, 1000, 1000],
        buyback_5y=[0, 0, 0, 0, 0],
        dividend_paid_5y=[0, 0, 0, 0, 0],
        operating_income_5y=[100, 100, 100, 100, 100],
        invested_capital_5y=[500, 500, 500, 500, 500],
        cash_5y=[300, 350, 400, 450, 500],  # 50% of mcap (same unit as cash values)
        market_cap_current=1000,
    )
    s = score_layer_6(f)
    assert s.inputs["cash_penalty"] == 1

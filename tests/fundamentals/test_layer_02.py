from tradingview_mcp.core.services.fundamentals.providers.base import TickerFinancials
from tradingview_mcp.core.services.fundamentals.scorers.layer_02_margin import score_layer_2


def test_layer_2_strong_software_expanding():
    f = TickerFinancials(
        ticker="MSFT", industry="45", sub_industry="Software",
        revenue_5y=[100, 120, 140, 165, 195],
        gross_profit_5y=[68, 82, 98, 116, 138],   # GM 68-71%
        operating_income_5y=[25, 32, 40, 50, 62], # OpM 25-32%
    )
    s = score_layer_2(f)
    assert s.verdict == "PASS"
    assert s.score >= 7


def test_layer_2_below_industry_median():
    f = TickerFinancials(
        ticker="X", industry="45", sub_industry="Software",
        revenue_5y=[100, 110, 120, 130, 140],
        gross_profit_5y=[40, 44, 48, 52, 56],  # GM 40% (well below SW median 70%)
        operating_income_5y=[5, 6, 7, 8, 10],
    )
    s = score_layer_2(f)
    assert s.verdict in ("FAIL", "CAUTION")


def test_layer_2_declining_trend():
    f = TickerFinancials(
        ticker="X", industry="20",
        revenue_5y=[100, 110, 120, 130, 140],
        gross_profit_5y=[40, 41, 38, 35, 32],   # GM contracting
        operating_income_5y=[15, 14, 12, 10, 8],
    )
    s = score_layer_2(f)
    assert s.score < 7

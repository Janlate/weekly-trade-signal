from tradingview_mcp.core.services.fundamentals.providers.base import TickerFinancials
from tradingview_mcp.core.services.fundamentals.scorers.layer_04_moat import score_layer_4


def test_layer_4_phase1_capped_at_7():
    f = TickerFinancials(
        ticker="MSFT", industry="45",
        revenue_5y=[100, 120, 140, 160, 180],
        gross_profit_5y=[70, 84, 98, 112, 126],   # GM stable 70%
        operating_income_5y=[30, 36, 42, 48, 54],
        net_income_5y=[22, 27, 32, 36, 42],
        invested_capital_5y=[60, 65, 70, 75, 80],
        market_cap_current=3e12,
    )
    s = score_layer_4(f)
    assert s.score <= 7.0  # capped Phase 1
    assert s.verdict in ("PASS", "CAUTION")


def test_layer_4_volatile_gm_low_score():
    f = TickerFinancials(
        ticker="X", industry="20",
        revenue_5y=[100, 110, 120, 130, 140],
        gross_profit_5y=[20, 25, 18, 22, 16],  # GM bouncing 15-25%
        operating_income_5y=[5, 8, 4, 6, 3],
        net_income_5y=[3, 5, 2, 4, 1],
        invested_capital_5y=[80, 90, 100, 110, 120],
        market_cap_current=2e9,
    )
    s = score_layer_4(f)
    assert s.score < 5

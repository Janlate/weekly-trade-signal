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


# ── Q18 historical percentile tests ───────────────────────────────────────

def _val_base(**kwargs) -> TickerFinancials:
    defaults = dict(
        ticker="X", industry="45",
        revenue_5y=[100, 115, 132, 152, 175],
        operating_income_5y=[25, 30, 36, 43, 52],
        capex_5y=[5, 6, 7, 8, 9],
        net_income_5y=[20, 24, 29, 34, 41],
        diluted_shares_5y=[100, 100, 100, 100, 100],
        total_debt_5y=[10, 10, 10, 10, 10],
        cash_5y=[50, 60, 70, 80, 90],
        price_current=5.0,
        market_cap_current=500,
        forward_eps_growth_1y=0.15,
    )
    defaults.update(kwargs)
    return TickerFinancials(**defaults)


def test_l7_percentile_none_when_no_history():
    """pe_5y_percentile should be None when historical_pe_5y is absent."""
    f = _val_base()
    s = score_layer_7(f)
    assert s.inputs["pe_5y_percentile"] is None
    assert s.inputs["pe_5y_series"] == []
    assert s.inputs["ev_sales_5y_percentile"] is None
    assert s.inputs["ev_sales_5y_series"] == []


def test_l7_percentile_at_minimum_when_current_cheapest():
    """P/E lower than all historical values -> percentile close to 0."""
    # historical_pe_5y = [25, 30, 35, 40, 45] (oldest->newest)
    # current P/E: market_cap / net_income = 500 / 41 ≈ 12.2 (cheaper than all history)
    f = _val_base(
        historical_pe_5y=[25.0, 30.0, 35.0, 40.0, 45.0],
        market_cap_current=500,   # P/E ~12
        net_income_5y=[20, 24, 29, 34, 41],
    )
    s = score_layer_7(f)
    pctile = s.inputs["pe_5y_percentile"]
    assert pctile is not None
    assert pctile == 0.0  # current below all history


def test_l7_percentile_at_maximum_when_current_priciest():
    """P/E higher than all historical values -> percentile = 1.0."""
    # current P/E: 20000 / 41 ≈ 488 (much higher than history)
    f = _val_base(
        historical_pe_5y=[15.0, 20.0, 25.0, 30.0, 35.0],
        market_cap_current=20000,
        net_income_5y=[20, 24, 29, 34, 41],
        price_current=200.0,
    )
    s = score_layer_7(f)
    pctile = s.inputs["pe_5y_percentile"]
    assert pctile is not None
    assert pctile == 1.0  # current above all history


def test_l7_percentile_midrange():
    """P/E in the middle of history -> percentile around 0.5."""
    # historical: [10, 20, 30, 40, 50]; current P/E: 500/41 ≈ 12 (between 10 and 20)
    f = _val_base(
        historical_pe_5y=[10.0, 20.0, 30.0, 40.0, 50.0],
        market_cap_current=500,   # P/E ~12.2, above 10 only
        net_income_5y=[20, 24, 29, 34, 41],
    )
    s = score_layer_7(f)
    pctile = s.inputs["pe_5y_percentile"]
    assert pctile is not None
    assert 0.0 < pctile < 1.0


def test_l7_percentile_series_preserved():
    """pe_5y_series and ev_sales_5y_series are passed through to inputs."""
    pe_hist = [15.0, 18.0, 22.0, float("nan"), 28.0]
    evs_hist = [3.0, 4.0, 5.0, 6.0, 7.0]
    f = _val_base(
        historical_pe_5y=pe_hist,
        historical_ev_sales_5y=evs_hist,
    )
    s = score_layer_7(f)
    assert s.inputs["pe_5y_series"] == pe_hist
    assert s.inputs["ev_sales_5y_series"] == evs_hist

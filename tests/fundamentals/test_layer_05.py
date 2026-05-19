from tradingview_mcp.core.services.fundamentals.providers.base import TickerFinancials
from tradingview_mcp.core.services.fundamentals.scorers.layer_05_balance_sheet import score_layer_5


def test_layer_5_net_cash_balance_sheet():
    f = TickerFinancials(
        ticker="GOOGL", industry="50",
        total_debt_5y=[10, 12, 14, 14, 14],
        cash_5y=[80, 100, 110, 120, 130],   # huge cash > debt
        ebitda_5y=[60, 70, 80, 95, 110],
        operating_income_5y=[55, 64, 72, 86, 100],
        interest_expense_5y=[1, 1, 1, 1, 1],
        diluted_shares_5y=[700, 690, 680, 670, 660],  # buying back
    )
    s = score_layer_5(f)
    assert s.verdict == "PASS"
    assert s.score >= 8
    assert "net_cash" in s.inputs.get("balance_quality", "")


def test_layer_5_overleveraged_fails():
    f = TickerFinancials(
        ticker="X", industry="20",
        total_debt_5y=[400, 420, 440, 450, 460],
        cash_5y=[20, 25, 22, 18, 15],
        ebitda_5y=[60, 65, 70, 75, 80],
        operating_income_5y=[30, 32, 35, 38, 40],
        interest_expense_5y=[20, 22, 24, 26, 28],
        diluted_shares_5y=[100, 100, 100, 100, 100],
    )
    s = score_layer_5(f)
    assert s.verdict == "FAIL"


def test_layer_5_dilutive_penalty():
    f = TickerFinancials(
        ticker="X", industry="45",
        total_debt_5y=[10, 10, 10, 10, 10],
        cash_5y=[50, 60, 70, 80, 90],
        ebitda_5y=[10, 15, 20, 25, 30],
        operating_income_5y=[5, 8, 12, 16, 22],
        interest_expense_5y=[1, 1, 1, 1, 1],
        diluted_shares_5y=[100, 110, 122, 135, 150],  # +50% over 5y (~8.5%/y)
    )
    s = score_layer_5(f)
    # dilution >5%/y → 0 dilution pts; score capped
    assert s.score <= 7


def test_layer_5_dilution_3to5_band():
    f = TickerFinancials(
        ticker="X", industry="45",
        total_debt_5y=[10, 10, 10, 10, 10],
        cash_5y=[50, 60, 70, 80, 90],
        ebitda_5y=[10, 15, 20, 25, 30],
        operating_income_5y=[5, 8, 12, 16, 22],
        interest_expense_5y=[1, 1, 1, 1, 1],
        diluted_shares_5y=[100, 104, 108, 113, 118],  # ~4%/y
    )
    s = score_layer_5(f)
    # should get 1 pt for dilution band 3-5%
    assert s.inputs["dilution_score"] == 1

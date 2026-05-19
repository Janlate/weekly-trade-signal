from unittest.mock import patch, MagicMock
import pandas as pd

from tradingview_mcp.core.services.fundamentals.providers.yfinance_provider import (
    YfinanceProvider,
)


def _fake_ticker(history_data: dict):
    """Build mock yf.Ticker.

    Note on DataFrame shape: yfinance returns rows=metrics, columns=dates (newest first).
    pd.DataFrame(dict_of_dict) with outer-dict-key as date and inner-dict-key as metric
    naturally produces that shape -- outer keys become columns, inner become index.
    """
    t = MagicMock()
    t.info = {
        "sector": "Technology",
        "industry": "Software—Infrastructure",
        "currentPrice": 420.0,
        "marketCap": 3_100_000_000_000,
        "earningsGrowth": 0.12,
    }
    t.income_stmt = pd.DataFrame(history_data["income_stmt"])
    t.financials = t.income_stmt  # alias for older yfinance versions
    t.balance_sheet = pd.DataFrame(history_data["balance_sheet"])
    t.cashflow = pd.DataFrame(history_data["cashflow"])
    return t


def test_yfinance_provider_msft_minimal():
    # Dict ordered newest -> oldest to match yfinance column order
    fake = _fake_ticker({
        "income_stmt": {
            "2025-06-30": {"Total Revenue": 280000, "Cost Of Revenue": 82000,
                           "Gross Profit": 198000, "Operating Income": 130000,
                           "Net Income": 100000, "Interest Expense": 2000,
                           "Diluted Average Shares": 7440},
            "2024-06-30": {"Total Revenue": 245000, "Cost Of Revenue": 73000,
                           "Gross Profit": 172000, "Operating Income": 109000,
                           "Net Income": 88000, "Interest Expense": 2000,
                           "Diluted Average Shares": 7430},
            "2023-06-30": {"Total Revenue": 211000, "Cost Of Revenue": 65000,
                           "Gross Profit": 146000, "Operating Income": 88000,
                           "Net Income": 73000, "Interest Expense": 2000,
                           "Diluted Average Shares": 7450},
            "2022-06-30": {"Total Revenue": 198000, "Cost Of Revenue": 63000,
                           "Gross Profit": 135000, "Operating Income": 83000,
                           "Net Income": 72000, "Interest Expense": 2000,
                           "Diluted Average Shares": 7500},
            "2021-06-30": {"Total Revenue": 168000, "Cost Of Revenue": 53000,
                           "Gross Profit": 115000, "Operating Income": 70000,
                           "Net Income": 61000, "Interest Expense": 2000,
                           "Diluted Average Shares": 7800},
        },
        "balance_sheet": {
            "2025-06-30": {"Total Debt": 40000, "Cash And Cash Equivalents": 90000,
                           "Stockholders Equity": 280000},
            "2024-06-30": {"Total Debt": 45000, "Cash And Cash Equivalents": 75000,
                           "Stockholders Equity": 240000},
            "2023-06-30": {"Total Debt": 50000, "Cash And Cash Equivalents": 110000,
                           "Stockholders Equity": 200000},
            "2022-06-30": {"Total Debt": 55000, "Cash And Cash Equivalents": 105000,
                           "Stockholders Equity": 170000},
            "2021-06-30": {"Total Debt": 60000, "Cash And Cash Equivalents": 130000,
                           "Stockholders Equity": 145000},
        },
        "cashflow": {
            "2025-06-30": {"Operating Cash Flow": 135000, "Capital Expenditure": -55000,
                           "Reconciled Depreciation": 22000, "Stock Based Compensation": 11000,
                           "Repurchase Of Capital Stock": -16000, "Cash Dividends Paid": -22000},
            "2024-06-30": {"Operating Cash Flow": 119000, "Capital Expenditure": -44000,
                           "Reconciled Depreciation": 20000, "Stock Based Compensation": 10000,
                           "Repurchase Of Capital Stock": -17000, "Cash Dividends Paid": -21000},
            "2023-06-30": {"Operating Cash Flow": 87000, "Capital Expenditure": -28000,
                           "Reconciled Depreciation": 17000, "Stock Based Compensation": 9000,
                           "Repurchase Of Capital Stock": -22000, "Cash Dividends Paid": -19000},
            "2022-06-30": {"Operating Cash Flow": 89000, "Capital Expenditure": -24000,
                           "Reconciled Depreciation": 14000, "Stock Based Compensation": 7000,
                           "Repurchase Of Capital Stock": -28000, "Cash Dividends Paid": -18000},
            "2021-06-30": {"Operating Cash Flow": 76000, "Capital Expenditure": -20000,
                           "Reconciled Depreciation": 12000, "Stock Based Compensation": 6000,
                           "Repurchase Of Capital Stock": -25000, "Cash Dividends Paid": -16000},
        },
    })

    with patch("yfinance.Ticker", return_value=fake):
        provider = YfinanceProvider()
        result = provider.fetch("MSFT")

    assert result is not None
    assert result.ticker == "MSFT"
    assert len(result.revenue_5y) == 5
    assert result.revenue_5y[-1] == 280000  # newest = last
    assert result.price_current == 420.0
    assert "yfinance" in result.source_chain
    # EBITDA = OpInc + D&A -- sanity-check correction not omitted
    assert result.ebitda_5y[-1] == 130000 + 22000
    # Invested capital = Debt + Equity
    assert result.invested_capital_5y[-1] == 40000 + 280000
    # diluted shares pulled from income_stmt (not balance_sheet)
    assert result.diluted_shares_5y[-1] == 7440
    # COGS field populated
    assert result.cogs_5y[-1] == 82000


def test_yfinance_returns_none_on_empty_info():
    fake = MagicMock()
    fake.info = {}
    fake.income_stmt = pd.DataFrame()
    fake.financials = pd.DataFrame()
    fake.balance_sheet = pd.DataFrame()
    fake.cashflow = pd.DataFrame()
    with patch("yfinance.Ticker", return_value=fake):
        provider = YfinanceProvider()
        result = provider.fetch("INVALID")
    assert result is None or result.fetch_errors

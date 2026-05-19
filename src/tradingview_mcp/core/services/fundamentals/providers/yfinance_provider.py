"""yfinance-based financial data provider."""
from __future__ import annotations

from typing import Optional

import yfinance as yf
import pandas as pd

from tradingview_mcp.core.services.fundamentals.providers.base import (
    FinancialProvider, TickerFinancials,
)

# yfinance row label -> standard field name (column = period date)
# Note: yfinance v0.2.x uses `t.income_stmt` (annual). Diluted shares live in income_stmt, not balance_sheet.
_INCOME_FIELDS = {
    "Total Revenue": "revenue_5y",
    "Cost Of Revenue": "cogs_5y",
    "Gross Profit": "gross_profit_5y",
    "Operating Income": "operating_income_5y",
    "Net Income": "net_income_5y",
    "Interest Expense": "interest_expense_5y",
    "Diluted Average Shares": "diluted_shares_5y",
}
_BS_FIELDS = {
    "Total Debt": "total_debt_5y",
    "Cash And Cash Equivalents": "cash_5y",
    "Stockholders Equity": "equity_5y",
    "Inventory": "inventory_5y",
    "Accounts Receivable": "receivables_5y",
    "Accounts Payable": "payables_5y",
}
_CF_FIELDS = {
    "Operating Cash Flow": "ocf_5y",
    "Capital Expenditure": "capex_5y",
    "Stock Based Compensation": "sbc_5y",
    "Reconciled Depreciation": "da_5y",                 # D&A for EBITDA correction
    "Repurchase Of Capital Stock": "buyback_5y",
    "Cash Dividends Paid": "dividend_paid_5y",
}

# Map yfinance sector -> approximate GICS sector code (best-effort; Phase 1 acceptable)
_SECTOR_TO_GICS: dict[str, str] = {
    "Technology": "45",
    "Communication Services": "50",
    "Consumer Cyclical": "25",
    "Consumer Defensive": "30",
    "Energy": "10",
    "Financial Services": "40",
    "Healthcare": "35",
    "Industrials": "20",
    "Basic Materials": "15",
    "Real Estate": "60",
    "Utilities": "55",
}


def _extract_series(df: pd.DataFrame, row_label: str) -> list[float]:
    """Extract a row from a yfinance financials DataFrame, oldest -> newest.

    yfinance shape: rows=metrics (index), columns=dates (newest first).
    Returns up to last 5 years; missing years filled by forward-pad to avoid
    silent zero-poisoning of CAGR/slope calculations.
    """
    if df is None or df.empty or row_label not in df.index:
        return []
    row = df.loc[row_label]
    # columns: newest first -> reverse to oldest -> newest
    reversed_row = row.iloc[::-1]
    # forward-fill from oldest non-NaN; if still NaN at start, drop those entries
    padded = reversed_row.ffill().dropna()
    if padded.empty:
        return []
    series = list(padded.astype(float))
    return series[-5:]  # last 5 years


def _safe_get(t, attr: str) -> pd.DataFrame:
    """Get a yfinance DataFrame attribute safely (empty DF if unavailable)."""
    try:
        df = getattr(t, attr, None)
        return df if isinstance(df, pd.DataFrame) else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


class YfinanceProvider(FinancialProvider):
    name = "yfinance"

    def fetch(self, ticker: str) -> Optional[TickerFinancials]:
        try:
            t = yf.Ticker(ticker)
            info = t.info or {}
        except Exception as e:
            return TickerFinancials(ticker=ticker, fetch_errors=[f"yfinance:Ticker:{e}"])

        if not info or not info.get("currentPrice"):
            return None

        result = TickerFinancials(
            ticker=ticker,
            industry=_SECTOR_TO_GICS.get(info.get("sector", ""), ""),
            sub_industry=info.get("industry", ""),
            gics_full=f'{info.get("sector", "")} / {info.get("industry", "")}',
            price_current=float(info.get("currentPrice") or 0.0),
            market_cap_current=float(info.get("marketCap") or 0.0),
            forward_eps_growth_1y=info.get("earningsGrowth"),
            source_chain=["yfinance"],
        )

        # Annual income statement -- yfinance v0.2.x renamed `financials` -> `income_stmt`
        fin = _safe_get(t, "income_stmt")
        if fin.empty:
            fin = _safe_get(t, "financials")
        for label, attr in _INCOME_FIELDS.items():
            series = _extract_series(fin, label)
            if series:
                if attr == "interest_expense_5y":
                    series = [abs(x) for x in series]
                if attr == "cogs_5y":
                    series = [abs(x) for x in series]
                setattr(result, attr, series)

        # Balance sheet
        bs = _safe_get(t, "balance_sheet")
        for label, attr in _BS_FIELDS.items():
            series = _extract_series(bs, label)
            if series:
                setattr(result, attr, series)

        # Cashflow (capex/buyback/dividends come negative -- flip to positive magnitude)
        cf = _safe_get(t, "cashflow")
        for label, attr in _CF_FIELDS.items():
            series = _extract_series(cf, label)
            if series:
                if attr in {"capex_5y", "buyback_5y", "dividend_paid_5y", "da_5y"}:
                    series = [abs(x) for x in series]
                setattr(result, attr, series)

        # EBITDA = Operating Income + D&A (correct for capital-intensive sectors)
        if result.operating_income_5y and result.da_5y and len(result.da_5y) == len(result.operating_income_5y):
            result.ebitda_5y = [op + da for op, da in zip(result.operating_income_5y, result.da_5y)]
        elif result.operating_income_5y:
            result.ebitda_5y = result.operating_income_5y[:]
            result.fetch_errors.append(
                "yfinance: D&A missing -- EBITDA proxy = OpInc (understated for cap-intensive)"
            )

        # Invested Capital = Total Debt + Equity (correct definition; debt-only overstates ROIC)
        if result.total_debt_5y and result.equity_5y and len(result.total_debt_5y) == len(result.equity_5y):
            result.invested_capital_5y = [d + e for d, e in zip(result.total_debt_5y, result.equity_5y)]
        elif result.equity_5y:
            result.invested_capital_5y = result.equity_5y[:]
        elif result.total_debt_5y:
            result.invested_capital_5y = result.total_debt_5y[:]
            result.fetch_errors.append(
                "yfinance: equity missing -- IC proxy = debt only (ROIC overstated)"
            )

        return result

    def fetch_price_only(self, ticker: str) -> Optional[TickerFinancials]:
        """Lightweight fetch -- current price + forward growth only, no 5y financials.

        Used by weekly entry_signal_scan to avoid re-downloading full statements
        for every ticker in the Quality Universe.
        """
        try:
            t = yf.Ticker(ticker)
            info = t.info or {}
        except Exception as e:
            return TickerFinancials(ticker=ticker, fetch_errors=[f"yfinance:price_only:{e}"])

        if not info or not info.get("currentPrice"):
            return None

        return TickerFinancials(
            ticker=ticker,
            price_current=float(info.get("currentPrice") or 0.0),
            market_cap_current=float(info.get("marketCap") or 0.0),
            forward_eps_growth_1y=info.get("earningsGrowth"),
            source_chain=["yfinance:price_only"],
        )

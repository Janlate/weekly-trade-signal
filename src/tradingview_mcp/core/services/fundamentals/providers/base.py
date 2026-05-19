"""Provider interface for financial data sources."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class TickerFinancials:
    """Standardized financial data for one ticker (5y by default)."""
    ticker: str
    industry: str = ""               # GICS sector code (e.g., "45")
    sub_industry: str = ""           # GICS sub-industry (e.g., "Software")
    gics_full: str = ""              # human-readable
    revenue_5y: list[float] = field(default_factory=list)       # oldest -> newest
    gross_profit_5y: list[float] = field(default_factory=list)
    operating_income_5y: list[float] = field(default_factory=list)
    net_income_5y: list[float] = field(default_factory=list)
    ocf_5y: list[float] = field(default_factory=list)
    capex_5y: list[float] = field(default_factory=list)
    sbc_5y: list[float] = field(default_factory=list)
    da_5y: list[float] = field(default_factory=list)                  # depreciation & amortization
    total_debt_5y: list[float] = field(default_factory=list)
    cash_5y: list[float] = field(default_factory=list)
    equity_5y: list[float] = field(default_factory=list)              # total stockholders' equity
    ebitda_5y: list[float] = field(default_factory=list)
    interest_expense_5y: list[float] = field(default_factory=list)
    invested_capital_5y: list[float] = field(default_factory=list)    # debt + equity
    diluted_shares_5y: list[float] = field(default_factory=list)
    inventory_5y: list[float] = field(default_factory=list)
    receivables_5y: list[float] = field(default_factory=list)
    payables_5y: list[float] = field(default_factory=list)
    cogs_5y: list[float] = field(default_factory=list)
    dividend_paid_5y: list[float] = field(default_factory=list)
    buyback_5y: list[float] = field(default_factory=list)
    # current price / market data
    price_current: float = 0.0
    market_cap_current: float = 0.0
    forward_eps_growth_1y: float | None = None
    # historical valuation series — populated by yfinance provider for L7 Q18
    # list of annual P/E values (oldest -> newest), one per year, max 5 years
    historical_pe_5y: list[float] | None = None
    # list of annual EV/Sales values (oldest -> newest), one per year, max 5 years
    historical_ev_sales_5y: list[float] | None = None
    # provider tracking
    source_chain: list[str] = field(default_factory=list)
    fetch_errors: list[str] = field(default_factory=list)


class FinancialProvider(ABC):
    name: str = "base"

    @abstractmethod
    def fetch(self, ticker: str) -> TickerFinancials | None:
        """Return TickerFinancials or None if ticker not supported."""
        ...

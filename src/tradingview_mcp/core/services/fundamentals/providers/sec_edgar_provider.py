"""SEC EDGAR companyfacts API provider (XBRL standardized financials)."""
from __future__ import annotations

import threading
from typing import Optional

import requests

from tradingview_mcp.core.services.fundamentals.providers.base import (
    FinancialProvider,
    TickerFinancials,
)

TICKER_TO_CIK_URL = "https://www.sec.gov/files/company_tickers.json"
COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

# XBRL concept -> field mapping. Multiple candidates per field -- first match wins.
_CONCEPT_MAP: dict[str, list[str]] = {
    "revenue_5y": [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
    ],
    "gross_profit_5y": ["GrossProfit"],
    "operating_income_5y": ["OperatingIncomeLoss"],
    "net_income_5y": ["NetIncomeLoss"],
    "interest_expense_5y": ["InterestExpense"],
    "cogs_5y": ["CostOfGoodsAndServicesSold", "CostOfRevenue"],
    "da_5y": ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization"],
    "total_debt_5y": ["LongTermDebt", "LongTermDebtNoncurrent"],
    "cash_5y": ["CashAndCashEquivalentsAtCarryingValue"],
    "equity_5y": ["StockholdersEquity"],
    "diluted_shares_5y": ["WeightedAverageNumberOfDilutedSharesOutstanding"],
    "inventory_5y": ["InventoryNet"],
    "receivables_5y": ["AccountsReceivableNetCurrent"],
    "payables_5y": ["AccountsPayableCurrent"],
    "ocf_5y": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex_5y": ["PaymentsToAcquirePropertyPlantAndEquipment"],
    "sbc_5y": ["ShareBasedCompensation"],
    "buyback_5y": ["PaymentsForRepurchaseOfCommonStock"],
    "dividend_paid_5y": ["PaymentsOfDividendsCommonStock", "PaymentsOfDividends"],
    # ── Bank fields (Phase 4) ───────────────────────────────────────────────
    "interest_income_5y": [
        "InterestAndDividendIncomeOperating",
        "InterestIncomeOperating",
    ],
    "noninterest_income_5y": ["NoninterestIncome"],
    "provision_loan_losses_5y": [
        "ProvisionForLoanAndLeaseLosses",
        "ProvisionForLoanLeaseAndOtherLosses",
    ],
    "total_loans_5y": [
        "LoansAndLeasesReceivableNetReportedAmount",
        "LoansAndLeasesReceivableNet",
    ],
    "total_deposits_5y": ["Deposits"],
    # ── Insurance fields (Phase 4) ──────────────────────────────────────────
    "premium_earned_5y": [
        "PremiumsEarnedNet",
        "PremiumsWrittenNet",
    ],
    "losses_incurred_5y": [
        "PolicyholderBenefitsAndClaimsIncurredNet",
        "LiabilityForFuturePolicyBenefitsAndUnpaidClaimsAdjustmentExpense",
        "BenefitsLossesAndExpenses",
    ],
    "expenses_incurred_5y": [
        "OtherUnderwritingExpenseOfInsurer",
        "InsuranceCommissionsAndFees",
    ],
    "investment_income_fin_5y": [
        "NetInvestmentIncome",
        "InvestmentIncomeNet",
    ],
    # ── REIT fields (Phase 4) ────────────────────────────────────────────────
    "rental_income_5y": [
        "OperatingLeasesIncomeStatementLeaseRevenue",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
    ],
}


def _annual_series(units_dict: dict, n_years: int = 5) -> list[float]:
    """Extract last n FY values from XBRL units list, oldest -> newest.

    EDGAR companyfacts returns each annual filing as a separate object.
    We filter FY 10-K rows, deduplicate by (fy, end) to avoid restatements
    causing duplicates, sort by end date, and return the last n entries.
    """
    usd = units_dict.get("USD") or units_dict.get("shares") or []
    fy_only = [
        e for e in usd
        if e.get("fp") == "FY" and e.get("form") in {"10-K", "10-K/A"}
    ]
    seen: set[tuple] = set()
    deduped: list[dict] = []
    for e in sorted(fy_only, key=lambda x: x["end"]):
        key = (e["fy"], e["end"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(e)
    last = deduped[-n_years:]
    return [float(e["val"]) for e in last]


class SecEdgarProvider(FinancialProvider):
    """Primary financial data provider using SEC EDGAR XBRL companyfacts."""

    name = "sec_edgar"

    def __init__(self, user_agent: str = "stock-stack/0.1 (research)"):
        # EDGAR requires a descriptive User-Agent per their fair-use policy
        self.headers = {
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip,deflate",
        }
        self._cik_map: Optional[dict[str, str]] = None
        self._cik_lock = threading.Lock()

    def _load_cik_map(self) -> dict[str, str]:
        """Lazy-load (and cache) the SEC ticker -> CIK mapping.

        Uses double-checked locking so multiple threads racing at startup
        do not issue duplicate HTTP calls. Call prewarm() from main thread
        before parallel usage to avoid the first-call bottleneck.
        """
        if self._cik_map is None:
            with self._cik_lock:
                if self._cik_map is None:  # second check inside lock
                    r = requests.get(TICKER_TO_CIK_URL, headers=self.headers, timeout=15)
                    r.raise_for_status()
                    data = r.json()
                    self._cik_map = {
                        v["ticker"]: f"{int(v['cik_str']):010d}"
                        for v in data.values()
                    }
        return self._cik_map

    def prewarm(self) -> None:
        """Populate CIK cache synchronously from main thread before parallel use."""
        self._load_cik_map()

    def _resolve_cik(self, ticker: str) -> Optional[str]:
        try:
            return self._load_cik_map().get(ticker.upper())
        except Exception:
            return None

    def fetch(self, ticker: str) -> Optional[TickerFinancials]:
        cik = self._resolve_cik(ticker)
        if not cik:
            return None

        try:
            r = requests.get(
                COMPANYFACTS_URL.format(cik=cik),
                headers=self.headers,
                timeout=20,
            )
            r.raise_for_status()
            facts = r.json().get("facts", {}).get("us-gaap", {})
        except Exception as e:
            return TickerFinancials(ticker=ticker, fetch_errors=[f"sec_edgar:{e}"])

        result = TickerFinancials(ticker=ticker, source_chain=["sec_edgar"])

        for field, concepts in _CONCEPT_MAP.items():
            for concept in concepts:
                if concept in facts:
                    series = _annual_series(facts[concept].get("units", {}))
                    if series:
                        setattr(result, field, series)
                        break  # first matching concept wins

        # EBITDA = Operating Income + D&A
        if (
            result.da_5y
            and result.operating_income_5y
            and len(result.da_5y) == len(result.operating_income_5y)
        ):
            result.ebitda_5y = [
                op + d for op, d in zip(result.operating_income_5y, result.da_5y)
            ]
        elif result.operating_income_5y:
            result.ebitda_5y = result.operating_income_5y[:]
            result.fetch_errors.append(
                "sec_edgar: D&A missing -- EBITDA proxy = OpInc"
            )

        # REIT FFO = Net Income + D&A - Gains on property sales
        # EDGAR tag for gains: GainsLossesOnSalesOfRealEstate / GainLossOnSaleOfProperties
        gains_tags = ["GainsLossesOnSalesOfRealEstate", "GainLossOnSaleOfProperties"]
        gains_5y: list[float] = []
        for tag in gains_tags:
            if tag in facts:
                s = _annual_series(facts[tag].get("units", {}))
                if s:
                    gains_5y = s
                    break

        if result.net_income_5y and result.da_5y:
            n = min(len(result.net_income_5y), len(result.da_5y))
            ffo: list[float] = []
            for i in range(n):
                ni_i = result.net_income_5y[-(n - i)]
                da_i = result.da_5y[-(n - i)]
                gain_i = gains_5y[-(n - i)] if len(gains_5y) >= n else 0.0
                ffo.append(ni_i + da_i - gain_i)
            result.ffo_5y = ffo

        # Invested Capital = Total Debt + Equity
        if (
            result.total_debt_5y
            and result.equity_5y
            and len(result.total_debt_5y) == len(result.equity_5y)
        ):
            result.invested_capital_5y = [
                d + e for d, e in zip(result.total_debt_5y, result.equity_5y)
            ]
        elif result.equity_5y:
            result.invested_capital_5y = result.equity_5y[:]

        # Return None if no meaningful financial data was extracted
        if not any([
            result.revenue_5y, result.net_income_5y,
            result.interest_income_5y, result.premium_earned_5y,
            result.rental_income_5y,
        ]):
            return None

        return result

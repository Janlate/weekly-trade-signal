"""Layer 5 — Balance Sheet (kill switch)."""
from __future__ import annotations

from tradingview_mcp.core.services.fundamentals.providers.base import TickerFinancials
from tradingview_mcp.core.services.fundamentals.schemas import LayerScore
from tradingview_mcp.core.services.fundamentals.scorers._utils import (
    cagr, clamp, safe_div,
)


def score_layer_5(f: TickerFinancials) -> LayerScore:
    debt, cash, ebitda, op, interest, shares = (
        f.total_debt_5y, f.cash_5y, f.ebitda_5y,
        f.operating_income_5y, f.interest_expense_5y, f.diluted_shares_5y,
    )
    if not all([debt, cash, ebitda, shares]):
        return LayerScore(
            layer_id=5, name="Balance Sheet", score=0,
            verdict="INSUFFICIENT_DATA",
            rationale="missing balance sheet data",
            inputs={}, data_completeness=0.0,
        )

    net_debt = debt[-1] - cash[-1]
    ebitda_latest = ebitda[-1] if ebitda[-1] > 0 else 1
    nd_ebitda = net_debt / ebitda_latest

    # Net Debt / EBITDA score (max 4)
    balance_quality = "leveraged"
    if net_debt <= 0:
        nd_score = 4
        balance_quality = "net_cash"
    elif nd_ebitda < 2.0:
        nd_score = 4
    elif nd_ebitda < 3.0:
        nd_score = 3
    elif nd_ebitda < 4.0:
        nd_score = 1
    else:
        nd_score = 0

    # Interest coverage (max 3)
    cov = safe_div(op[-1], interest[-1], default=999) if interest and interest[-1] > 0 else 999
    if cov > 5:
        cov_score = 3
    elif cov >= 3:
        cov_score = 2
    elif cov >= 1.5:
        cov_score = 1
    else:
        cov_score = 0

    # Dilution (max 3)
    if len(shares) >= 5:
        sh_cagr = cagr(shares[0], shares[-1], len(shares) - 1)
    else:
        sh_cagr = 0
    if sh_cagr <= 0:
        dil_score = 3
    elif sh_cagr <= 0.03:
        dil_score = 2
    elif sh_cagr <= 0.05:
        dil_score = 1
    else:
        dil_score = 0

    raw = nd_score + cov_score + dil_score
    score = clamp(raw, 0, 10)
    verdict = "PASS" if score >= 7 else ("CAUTION" if score >= 4 else "FAIL")

    rationale = (
        f"Net Debt/EBITDA {nd_ebitda:.2f}x [{balance_quality}]; "
        f"Interest Coverage {cov:.1f}x; "
        f"Shares CAGR {sh_cagr*100:+.1f}%/y"
    )

    return LayerScore(
        layer_id=5, name="Balance Sheet", score=score, verdict=verdict,
        rationale=rationale,
        inputs={"net_debt_ebitda": nd_ebitda, "interest_coverage": cov,
                "shares_cagr": sh_cagr, "balance_quality": balance_quality,
                "nd_score": nd_score, "coverage_score": cov_score, "dilution_score": dil_score},
        data_completeness=1.0,
    )

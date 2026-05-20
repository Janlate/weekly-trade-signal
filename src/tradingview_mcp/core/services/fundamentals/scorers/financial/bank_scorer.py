"""Bank scorer — 8-layer, sector-aware.

L1: Total revenue (interest_income + noninterest_income) 5y CAGR
L2: Net Interest Margin = (interest_income - interest_expense) / total_loans 3y avg
L3: Efficiency ratio = noninterest_expense / (NII + noninterest_income) 3y avg
L4: Reused from generic layer_04_moat
L5: Loan-to-deposit ratio + shares dilution
L6: Reused from generic layer_06_capital_alloc
L7: P/TBV + dividend yield (via generic layer_07_valuation as proxy)
L8: Reused from generic layer_08_position_sizing
"""
from __future__ import annotations

from datetime import date

from tradingview_mcp.core.services.fundamentals.providers.base import TickerFinancials
from tradingview_mcp.core.services.fundamentals.schemas import FundamentalReport, LayerScore
from tradingview_mcp.core.services.fundamentals.composite import score_quality
from tradingview_mcp.core.services.fundamentals.industry_config import is_cyclical
from tradingview_mcp.core.services.fundamentals.scorers._utils import (
    cagr, clamp, safe_div, linear_slope,
)
from tradingview_mcp.core.services.fundamentals.scorers.layer_04_moat import score_layer_4
from tradingview_mcp.core.services.fundamentals.scorers.layer_06_capital_alloc import score_layer_6
from tradingview_mcp.core.services.fundamentals.scorers.layer_07_valuation import score_layer_7


_MIN_YEARS = 3


def _score_l1_bank(f: TickerFinancials) -> LayerScore:
    """L1 — Total revenue growth (NII + non-interest income)."""
    ii = f.interest_income_5y or []
    ni_inc = f.noninterest_income_5y or []
    # Fall back to generic revenue if bank-specific fields absent
    rev = f.revenue_5y or []

    if ii and ni_inc and len(ii) >= _MIN_YEARS and len(ni_inc) >= _MIN_YEARS:
        n = min(len(ii), len(ni_inc))
        total = [ii[i] + ni_inc[i] for i in range(-n, 0)]
        source = "NII+NONI"
    elif rev and len(rev) >= _MIN_YEARS:
        n = len(rev)
        total = rev
        source = "revenue_fallback"
    else:
        return LayerScore(
            layer_id=1, name="Revenue Growth (Bank)",
            score=0, verdict="INSUFFICIENT_DATA",
            rationale="insufficient interest_income / revenue data",
            inputs={}, data_completeness=0.0,
        )

    g = cagr(total[0], total[-1], len(total) - 1)
    import math
    if math.isnan(g):
        return LayerScore(
            layer_id=1, name="Revenue Growth (Bank)",
            score=0, verdict="INSUFFICIENT_DATA",
            rationale="CAGR undefined (non-positive start value)",
            inputs={"source": source}, data_completeness=0.3,
        )

    # Pass band >5%, reject <0%
    if g >= 0.10:
        base = 6
    elif g >= 0.05:
        base = 5
    elif g >= 0.02:
        base = 3
    elif g >= 0:
        base = 2
    else:
        base = 0

    # NIM trend as quality bonus (if data available)
    nim_bonus = 0.0
    ie = f.interest_expense_5y or []
    loans = f.total_loans_5y or []
    if ii and ie and loans and len(ii) >= 3:
        n3 = min(len(ii), len(ie), len(loans))
        nims = []
        for i in range(-n3, 0):
            spread_i = ii[i] - ie[i] if abs(i) <= len(ie) else ii[i]
            loan_i = loans[i] if abs(i) <= len(loans) else 1.0
            if loan_i > 0:
                nims.append(spread_i / loan_i)
        if nims:
            nim_slope = linear_slope(nims)
            nim_bonus = 2.0 if nim_slope > 0 else 0.0

    score = clamp(base + nim_bonus, 0, 10)
    verdict = "PASS" if score >= 7 else ("CAUTION" if score >= 4 else "FAIL")
    return LayerScore(
        layer_id=1, name="Revenue Growth (Bank)",
        score=score, verdict=verdict,
        rationale=f"Total revenue CAGR {g*100:.1f}% ({source}); NIM bonus {nim_bonus:.0f}",
        inputs={"cagr": g, "source": source, "total_revenue_series": total,
                "nim_bonus": nim_bonus, "is_cyclical": False, "tier": "mid"},
        data_completeness=min(1.0, len(total) / 5),
    )


def _score_l2_bank(f: TickerFinancials) -> LayerScore:
    """L2 — Net Interest Margin (NIM) 3y avg. Pass >3%, Reject <2%."""
    ii = f.interest_income_5y or []
    ie = f.interest_expense_5y or []
    loans = f.total_loans_5y or []

    if not (ii and ie and loans) or len(ii) < _MIN_YEARS:
        return LayerScore(
            layer_id=2, name="Margin — NIM (Bank)",
            score=4, verdict="CAUTION",
            rationale="NIM data unavailable — using neutral fallback score 4",
            inputs={}, data_completeness=0.0,
        )

    n = min(len(ii), len(ie), len(loans))
    nims = []
    for i in range(-min(n, 3), 0):
        spread_i = ii[i] - (ie[i] if abs(i) <= len(ie) else 0)
        loan_i = loans[i] if abs(i) <= len(loans) and loans[i] > 0 else None
        if loan_i:
            nims.append(spread_i / loan_i)

    if not nims:
        return LayerScore(
            layer_id=2, name="Margin — NIM (Bank)",
            score=4, verdict="CAUTION",
            rationale="NIM computation yielded no valid data points",
            inputs={}, data_completeness=0.0,
        )

    nim_avg = sum(nims) / len(nims)
    nim_latest = nims[-1]
    nim_slope = linear_slope(nims) if len(nims) >= 2 else 0.0

    # Level score (0-6)
    if nim_avg >= 0.04:
        level = 6
    elif nim_avg >= 0.03:
        level = 5
    elif nim_avg >= 0.025:
        level = 3
    elif nim_avg >= 0.02:
        level = 2
    else:
        level = 0

    # Trend bonus (0-4)
    trend = 2 if nim_slope > 0 else (1 if nim_slope > -0.002 else 0)

    score = clamp(level + trend, 0, 10)
    verdict = "PASS" if score >= 7 else ("CAUTION" if score >= 4 else "FAIL")
    return LayerScore(
        layer_id=2, name="Margin — NIM (Bank)",
        score=score, verdict=verdict,
        rationale=(
            f"NIM 3y avg {nim_avg*100:.2f}% · latest {nim_latest*100:.2f}% · "
            f"slope {nim_slope*100:+.3f}pp/y"
        ),
        inputs={"nim_3y_avg": nim_avg, "nim_latest": nim_latest,
                "nim_slope": nim_slope, "nim_series": nims,
                # expose for Q5 checklist rendering
                "gm_5y": nims, "om_5y": nims,
                "median": {"gross": 0.035, "operating": 0.03}},
        data_completeness=min(1.0, len(nims) / 3),
    )


def _score_l3_bank(f: TickerFinancials) -> LayerScore:
    """L3 — Efficiency ratio = noninterest_expense / (NII + noninterest_income). Gate.

    Pass <55%, Reject >70%. Lower = better (banks spend less per $ of revenue).
    Falls back to ROIC/FCF logic from generic when expense data absent.
    """
    ii = f.interest_income_5y or []
    ie = f.interest_expense_5y or []
    ni_inc = f.noninterest_income_5y or []

    # Noninterest expense = total_expense proxy. yfinance doesn't always have this;
    # approximate as operating_income subtracted from NII+NONI.
    op = f.operating_income_5y or []

    if not (ii and ie and ni_inc and op) or len(ii) < _MIN_YEARS:
        # Fall back to generic L3 ROIC logic
        from tradingview_mcp.core.services.fundamentals.scorers.layer_03_fcf_quality import score_layer_3
        generic = score_layer_3(f)
        # Override name and rationale to signal fallback
        return LayerScore(
            layer_id=3, name="Quality of Growth (Bank, fallback ROIC)",
            score=generic.score, verdict=generic.verdict,
            rationale="[bank: efficiency data unavailable, fallback to ROIC] " + generic.rationale,
            inputs=generic.inputs, data_completeness=generic.data_completeness * 0.7,
        )

    n = min(len(ii), len(ie), len(ni_inc), len(op))
    ratios = []
    for i in range(-min(n, 3), 0):
        nii_i = ii[i] - ie[i]
        total_rev_i = nii_i + ni_inc[i]
        if total_rev_i <= 0:
            continue
        # noninterest expense ≈ total_rev - op_income (approximation)
        nie_i = total_rev_i - op[i]
        if nie_i > 0:
            ratios.append(nie_i / total_rev_i)

    if not ratios:
        return LayerScore(
            layer_id=3, name="Quality of Growth — Efficiency (Bank)",
            score=0, verdict="INSUFFICIENT_DATA",
            rationale="efficiency ratio computation yielded no valid data",
            inputs={}, data_completeness=0.0,
        )

    eff_avg = sum(ratios) / len(ratios)
    eff_slope = linear_slope(ratios) if len(ratios) >= 2 else 0.0

    # Score: <50% = 7, <55% = 6, <60% = 4, <70% = 2, >=70% = 0
    if eff_avg < 0.50:
        base = 7
    elif eff_avg < 0.55:
        base = 6
    elif eff_avg < 0.60:
        base = 4
    elif eff_avg < 0.70:
        base = 2
    else:
        base = 0

    # Improving trend (slope < 0 = efficiency improving)
    trend = 2 if eff_slope < -0.01 else (1 if eff_slope < 0.01 else 0)

    score = clamp(base + trend, 0, 10)
    verdict = "PASS" if score >= 7 else ("CAUTION" if score >= 4 else "FAIL")
    return LayerScore(
        layer_id=3, name="Quality of Growth — Efficiency (Bank)",
        score=score, verdict=verdict,
        rationale=(
            f"Efficiency ratio 3y avg {eff_avg*100:.1f}% (lower=better, pass<55%) · "
            f"slope {eff_slope*100:+.2f}pp/y"
        ),
        inputs={"efficiency_ratio_avg": eff_avg, "efficiency_ratio_series": ratios,
                "efficiency_slope": eff_slope,
                # Standard fields expected by generic composite logic
                "roic": None, "wacc": 0.09, "spread": None,
                "fcf_5y": [], "fcf_ni_ratio_avg": None,
                "sbc_adjusted": False, "historical_loss_penalty": 0,
                "roic_3y_avg": None,
                "ccc_days": None, "ccc_trend": None,
                "inventory_days_latest": None, "receivable_days_latest": None},
        data_completeness=min(1.0, len(ratios) / 3),
    )


def _score_l5_bank(f: TickerFinancials) -> LayerScore:
    """L5 — Loan-to-deposit ratio + share dilution. CET1 = Phase 5."""
    loans = f.total_loans_5y or []
    deposits = f.total_deposits_5y or []
    shares = f.diluted_shares_5y or []

    if not (loans and deposits) or len(loans) < 1:
        # Fall back to generic balance sheet
        from tradingview_mcp.core.services.fundamentals.scorers.layer_05_balance_sheet import score_layer_5
        generic = score_layer_5(f)
        return LayerScore(
            layer_id=5, name="Balance Sheet (Bank, fallback generic)",
            score=generic.score, verdict=generic.verdict,
            rationale="[bank: LtD data unavailable, fallback generic] " + generic.rationale,
            inputs=generic.inputs, data_completeness=generic.data_completeness * 0.7,
        )

    ltd = loans[-1] / deposits[-1] if deposits[-1] > 0 else 99.0

    # Loan-to-deposit ratio score (0-6): <80% excellent, 80-90% good, >100% risky
    if ltd < 0.80:
        ltd_score = 6
    elif ltd < 0.90:
        ltd_score = 5
    elif ltd < 1.00:
        ltd_score = 3
    else:
        ltd_score = 0

    # Dilution score (0-4)
    dil_score = 4
    if len(shares) >= 3:
        from tradingview_mcp.core.services.fundamentals.scorers._utils import cagr as _cagr
        sc = _cagr(shares[0], shares[-1], len(shares) - 1)
        import math
        if not math.isnan(sc):
            if sc <= 0:
                dil_score = 4
            elif sc <= 0.03:
                dil_score = 3
            elif sc <= 0.05:
                dil_score = 2
            else:
                dil_score = 0

    score = clamp(ltd_score + dil_score, 0, 10)
    verdict = "PASS" if score >= 7 else ("CAUTION" if score >= 4 else "FAIL")
    return LayerScore(
        layer_id=5, name="Balance Sheet (Bank)",
        score=score, verdict=verdict,
        rationale=(
            f"Loan-to-deposit {ltd*100:.1f}% (pass<90%) · "
            f"CET1 = Phase 5 (text parsing)"
        ),
        inputs={"loan_to_deposit": ltd, "ltd_score": ltd_score,
                "dilution_score": dil_score,
                # Expose fields checklist20 reads for Q12
                "net_debt_ebitda": ltd,  # proxy for balance-sheet leverage display
                "interest_coverage": 999,
                "shares_cagr": 0.0, "balance_quality": "bank"},
        data_completeness=min(1.0, len(loans) / 5),
    )


def score(fin: TickerFinancials, scan_date: str | None = None) -> FundamentalReport:
    """Run all 8 layers for a bank; return FundamentalReport."""
    scan_date = scan_date or date.today().isoformat()

    l1 = _score_l1_bank(fin)
    l2 = _score_l2_bank(fin)
    l3 = _score_l3_bank(fin)
    l4 = score_layer_4(fin)
    l5 = _score_l5_bank(fin)
    l6 = score_layer_6(fin)
    l7 = score_layer_7(fin)

    layers_quality = {
        f"{l.layer_id}_{l.name.lower().replace(' ', '_').replace('/', '_')}": l
        for l in [l1, l2, l3, l4, l5, l6]
    }

    cyc = is_cyclical(fin.industry, fin.sub_industry)
    industry_label = fin.gics_full or fin.industry_name or fin.industry
    raw_ref = f"stock-reports/data/fundamentals/{fin.ticker}/{scan_date}.json"

    report = score_quality(
        fin.ticker, layers_quality,
        industry=industry_label, is_cyclical=cyc, raw_inputs_ref=raw_ref,
        scan_date=scan_date,
    )

    # Attach L7 to layers dict on the report (score_quality only receives L1-L6)
    l7_key = f"{l7.layer_id}_{l7.name.lower().replace(' ', '_').replace('/', '_')}"
    report.layers[l7_key] = l7

    return report

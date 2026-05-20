"""REIT scorer — 8-layer, sector-aware.

L1: Rental income 5y CAGR  (pass >5%, same-store proxy)
L2: NOI margin = (rental_income - operating_expenses) / rental_income 3y avg
    pass >65%, reject <50%
L3: FFO/AFFO growth + dividend/FFO payout ratio sustainability
    pass payout <80%, reject >100%
L4: Reused generic
L5: Debt/Assets + Debt/EBITDA (pass D/A <50% AND D/EBITDA <7x)
L6: Reused generic
L7: P/FFO proxy (generic DCF used as proxy; rationale tagged)
L8: Reused generic
"""
from __future__ import annotations

import math
from datetime import date

from tradingview_mcp.core.services.fundamentals.providers.base import TickerFinancials
from tradingview_mcp.core.services.fundamentals.schemas import FundamentalReport, LayerScore
from tradingview_mcp.core.services.fundamentals.composite import score_quality
from tradingview_mcp.core.services.fundamentals.industry_config import is_cyclical
from tradingview_mcp.core.services.fundamentals.scorers._utils import (
    cagr, clamp, linear_slope, safe_div,
)
import statistics as _statistics

from tradingview_mcp.core.services.fundamentals.scorers.layer_04_moat import score_layer_4
from tradingview_mcp.core.services.fundamentals.scorers.layer_06_capital_alloc import score_layer_6
from tradingview_mcp.core.services.fundamentals.scorers.layer_07_valuation import score_layer_7


_MIN_YEARS = 3


def _score_l1_reit(f: TickerFinancials) -> LayerScore:
    """L1 — Rental income 5y CAGR. Pass >5%, Reject <0%."""
    rental = f.rental_income_5y or []
    rev = f.revenue_5y or []

    if rental and len(rental) >= _MIN_YEARS:
        series = rental
        source = "rental_income"
    elif rev and len(rev) >= _MIN_YEARS:
        series = rev
        source = "revenue_fallback"
    else:
        return LayerScore(
            layer_id=1, name="Revenue Growth (REIT)",
            score=0, verdict="INSUFFICIENT_DATA",
            rationale="no rental income / revenue data",
            inputs={}, data_completeness=0.0,
        )

    g = cagr(series[0], series[-1], len(series) - 1)
    if math.isnan(g):
        return LayerScore(
            layer_id=1, name="Revenue Growth (REIT)",
            score=0, verdict="INSUFFICIENT_DATA",
            rationale="CAGR undefined (non-positive start value)",
            inputs={"source": source}, data_completeness=0.3,
        )

    if g >= 0.08:
        base = 7
    elif g >= 0.05:
        base = 5
    elif g >= 0.02:
        base = 3
    elif g >= 0:
        base = 2
    else:
        base = 0

    score = clamp(base, 0, 10)
    verdict = "PASS" if score >= 7 else ("CAUTION" if score >= 4 else "FAIL")
    return LayerScore(
        layer_id=1, name="Revenue Growth (REIT)",
        score=score, verdict=verdict,
        rationale=f"Rental income CAGR {g*100:.1f}% ({source})",
        inputs={"cagr": g, "source": source, "rental_series": series,
                "is_cyclical": False, "tier": "mid"},
        data_completeness=min(1.0, len(series) / 5),
    )


def _score_l2_reit(f: TickerFinancials) -> LayerScore:
    """L2 — NOI margin. Pass >65%, Reject <50%.

    NOI = rental_income - operating_expenses ≈ gross_profit proxy.
    """
    rental = f.rental_income_5y or []
    gp = f.gross_profit_5y or []
    rev = f.revenue_5y or []
    op = f.operating_income_5y or []

    if rental and gp and len(rental) >= _MIN_YEARS:
        n = min(len(rental), len(gp))
        margins = [gp[i] / rental[i] if rental[i] > 0 else 0.0
                   for i in range(-min(n, 3), 0)]
        source = "gp/rental"
    elif rev and op and len(rev) >= _MIN_YEARS:
        n = min(len(rev), len(op))
        margins = [op[i] / rev[i] if rev[i] > 0 else 0.0
                   for i in range(-min(n, 3), 0)]
        source = "op_margin_fallback"
    else:
        return LayerScore(
            layer_id=2, name="Margin — NOI (REIT)",
            score=4, verdict="CAUTION",
            rationale="NOI margin data unavailable — neutral fallback",
            inputs={}, data_completeness=0.0,
        )

    noi_avg = sum(margins) / len(margins) if margins else 0.0
    noi_slope = linear_slope(margins) if len(margins) >= 2 else 0.0

    if noi_avg >= 0.70:
        level = 8
    elif noi_avg >= 0.65:
        level = 6
    elif noi_avg >= 0.55:
        level = 4
    elif noi_avg >= 0.50:
        level = 2
    else:
        level = 0

    trend = 2 if noi_slope > 0.01 else (1 if noi_slope > -0.01 else 0)
    score = clamp(level + trend, 0, 10)
    verdict = "PASS" if score >= 7 else ("CAUTION" if score >= 4 else "FAIL")
    return LayerScore(
        layer_id=2, name="Margin — NOI (REIT)",
        score=score, verdict=verdict,
        rationale=(
            f"NOI margin 3y avg {noi_avg*100:.1f}% (pass>65%) · "
            f"slope {noi_slope*100:+.2f}pp/y [{source}]"
        ),
        inputs={"noi_margin_avg": noi_avg, "noi_slope": noi_slope,
                "noi_margin_series": margins,
                "gm_5y": margins, "om_5y": margins,
                "median": {"gross": 0.65, "operating": 0.60}},
        data_completeness=min(1.0, len(margins) / 3),
    )


def _score_l3_reit(f: TickerFinancials) -> LayerScore:
    """L3 — FFO sustainability + payout ratio. Gate.

    Payout = dividend / FFO: pass <80%, reject >100%.
    FFO growth as quality signal.
    """
    ffo = f.ffo_5y or []
    div = f.dividend_paid_5y or []
    ni = f.net_income_5y or []

    # If FFO absent, fall back to net income as rough proxy
    # Note: NI-proxy payout ratio will be inflated for REITs (D&A not added back)
    using_ni_proxy = False
    if not ffo and ni:
        ffo = ni
        ffo_source = "ni_proxy"
        using_ni_proxy = True
    else:
        ffo_source = "ffo"

    if not ffo or len(ffo) < _MIN_YEARS:
        # Fall back to generic L3
        from tradingview_mcp.core.services.fundamentals.scorers.layer_03_fcf_quality import score_layer_3
        generic = score_layer_3(f)
        return LayerScore(
            layer_id=3, name="Quality of Growth (REIT, fallback ROIC)",
            score=generic.score, verdict=generic.verdict,
            rationale="[reit: FFO data absent, fallback ROIC] " + generic.rationale,
            inputs=generic.inputs, data_completeness=generic.data_completeness * 0.7,
        )

    # FFO CAGR
    ffo_g = cagr(ffo[0], ffo[-1], len(ffo) - 1)
    ffo_ok = not math.isnan(ffo_g) and ffo_g >= 0

    # Payout ratio (last 3y avg): dividend / FFO
    payout_ratios = []
    if div and len(div) >= 1:
        n = min(len(div), len(ffo), 3)
        for i in range(-n, 0):
            ffo_i = ffo[i]
            div_i = div[i]
            if ffo_i > 0:
                payout_ratios.append(div_i / ffo_i)

    payout_avg = sum(payout_ratios) / len(payout_ratios) if payout_ratios else 0.80

    # When using NI proxy (no D&A), the payout ratio is overstated.
    # Real FFO = NI + D&A (often 30-50% of NI for industrial/telecom REITs).
    # Apply a correction: adjust effective threshold upward by 40% for NI proxy.
    payout_threshold_pass = 0.80 if not using_ni_proxy else 1.20
    payout_threshold_caution = 1.00 if not using_ni_proxy else 1.50

    # Score: payout vs threshold
    if payout_avg < payout_threshold_pass * 0.75:
        payout_score = 5
    elif payout_avg < payout_threshold_pass:
        payout_score = 4
    elif payout_avg < payout_threshold_caution:
        payout_score = 2
    elif payout_avg < payout_threshold_caution * 1.15:
        payout_score = 1
    else:
        payout_score = 0

    # FFO growth bonus
    ffo_bonus = 0
    if ffo_ok:
        if ffo_g >= 0.05:
            ffo_bonus = 3
        elif ffo_g >= 0.02:
            ffo_bonus = 2
        else:
            ffo_bonus = 1

    score = clamp(payout_score + ffo_bonus, 0, 10)
    verdict = "PASS" if score >= 7 else ("CAUTION" if score >= 4 else "FAIL")
    return LayerScore(
        layer_id=3, name="Quality of Growth — FFO (REIT)",
        score=score, verdict=verdict,
        rationale=(
            f"FFO payout 3y avg {payout_avg*100:.1f}% "
            f"(pass<{payout_threshold_pass*100:.0f}%{'*adj for NI proxy' if using_ni_proxy else ''}) · "
            f"FFO CAGR {ffo_g*100:.1f}% [{ffo_source}]"
        ),
        inputs={"ffo_payout_avg": payout_avg, "ffo_cagr": ffo_g,
                "payout_score": payout_score, "ffo_bonus": ffo_bonus,
                "ffo_source": ffo_source,
                "roic": None, "wacc": 0.08, "spread": None,
                "fcf_5y": ffo, "fcf_ni_ratio_avg": None,
                "sbc_adjusted": False, "historical_loss_penalty": 0,
                "roic_3y_avg": None,
                "ccc_days": None, "ccc_trend": None,
                "inventory_days_latest": None, "receivable_days_latest": None},
        data_completeness=min(1.0, len(ffo) / 5),
    )


def _score_l5_reit(f: TickerFinancials) -> LayerScore:
    """L5 — Debt/Assets + Debt/EBITDA. Pass D/A <50% AND D/EBITDA <7x."""
    debt = f.total_debt_5y or []
    cash = f.cash_5y or []
    ebitda = f.ebitda_5y or []
    equity = f.equity_5y or []

    if not debt:
        from tradingview_mcp.core.services.fundamentals.scorers.layer_05_balance_sheet import score_layer_5
        generic = score_layer_5(f)
        return LayerScore(
            layer_id=5, name="Balance Sheet (REIT, fallback generic)",
            score=generic.score, verdict=generic.verdict,
            rationale="[reit: debt data absent, fallback generic] " + generic.rationale,
            inputs=generic.inputs, data_completeness=generic.data_completeness * 0.7,
        )

    total_assets = (debt[-1] + equity[-1]) if equity else debt[-1] * 2.0  # rough proxy
    da_ratio = debt[-1] / total_assets if total_assets > 0 else 1.0
    net_debt = debt[-1] - (cash[-1] if cash else 0)
    ebitda_latest = ebitda[-1] if ebitda and ebitda[-1] > 0 else 1
    nd_ebitda = net_debt / ebitda_latest

    # D/A score (0-5)
    if da_ratio < 0.35:
        da_score = 5
    elif da_ratio < 0.50:
        da_score = 4
    elif da_ratio < 0.60:
        da_score = 2
    elif da_ratio < 0.65:
        da_score = 1
    else:
        da_score = 0

    # D/EBITDA score (0-5)
    if nd_ebitda < 4:
        de_score = 5
    elif nd_ebitda < 7:
        de_score = 3
    elif nd_ebitda < 10:
        de_score = 1
    else:
        de_score = 0

    score = clamp(da_score + de_score, 0, 10)
    verdict = "PASS" if score >= 7 else ("CAUTION" if score >= 4 else "FAIL")
    return LayerScore(
        layer_id=5, name="Balance Sheet (REIT)",
        score=score, verdict=verdict,
        rationale=(
            f"Debt/Assets {da_ratio*100:.1f}% (pass<50%) · "
            f"Net Debt/EBITDA {nd_ebitda:.1f}x (pass<7x)"
        ),
        inputs={"debt_assets_ratio": da_ratio, "net_debt_ebitda": nd_ebitda,
                "da_score": da_score, "de_score": de_score,
                "interest_coverage": 999,
                "shares_cagr": 0.0, "balance_quality": "reit"},
        data_completeness=min(1.0, len(debt) / 5),
    )


def _score_l4_reit(f: TickerFinancials) -> LayerScore:
    """L4 — REIT moat proxy. Try generic; fall back to rental income stability + scale."""
    l4_generic = score_layer_4(f)
    if l4_generic.verdict != "INSUFFICIENT_DATA":
        return l4_generic

    rental = f.rental_income_5y or []
    ffo = f.ffo_5y or []
    mc = f.market_cap_current

    ref_series = ffo if ffo else rental
    if not ref_series or len(ref_series) < _MIN_YEARS:
        return LayerScore(
            layer_id=4, name="Moat (REIT)", score=4, verdict="CAUTION",
            rationale="[reit: moat data limited] neutral score 4",
            inputs={"moat_override_applied": True, "roic_std": None, "gm_premium": None, "market_cap": mc},
            data_completeness=0.3,
        )

    # FFO/rental income stability
    cv = _statistics.pstdev(ref_series) / abs(sum(ref_series) / len(ref_series)) if sum(ref_series) != 0 else 1.0
    if cv < 0.10:
        consist = 3
    elif cv < 0.20:
        consist = 2
    elif cv < 0.35:
        consist = 1
    else:
        consist = 0

    scale = 2 if mc >= 50e9 else (1 if mc >= 10e9 else 0)

    raw = consist + scale
    score_val = clamp(raw, 0, 7)
    verdict = "PASS" if score_val >= 6 else ("CAUTION" if score_val >= 3 else "FAIL")
    return LayerScore(
        layer_id=4, name="Moat (REIT)", score=score_val, verdict=verdict,
        rationale=f"[reit proxy] income CV {cv:.2f} · market cap ${mc/1e9:.0f}B",
        inputs={"income_cv": cv, "consist": consist, "scale": scale,
                "moat_override_applied": True, "roic_std": None, "gm_premium": None, "market_cap": mc},
        data_completeness=0.6,
    )


def score(fin: TickerFinancials, scan_date: str | None = None) -> FundamentalReport:
    """Run all 8 layers for a REIT; return FundamentalReport."""
    scan_date = scan_date or date.today().isoformat()

    l1 = _score_l1_reit(fin)
    l2 = _score_l2_reit(fin)
    l3 = _score_l3_reit(fin)
    l4 = _score_l4_reit(fin)
    l5 = _score_l5_reit(fin)
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

    l7_key = f"{l7.layer_id}_{l7.name.lower().replace(' ', '_').replace('/', '_')}"
    report.layers[l7_key] = l7
    return report

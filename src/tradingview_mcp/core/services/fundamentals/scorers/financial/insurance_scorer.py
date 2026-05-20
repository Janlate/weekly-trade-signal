"""Insurance scorer — 8-layer, sector-aware.

L1: Premium earned 5y CAGR  (pass >5%, reject <0%)
L2: Combined ratio = (losses + expenses) / premiums 3y avg  (pass <95%, reject >105%)
L3: Investment income / total revenue + stability  (quality-of-earnings gate)
L4: Reused generic
L5: Reserves / written-premium ratio proxy
L6: Reused generic
L7: Generic DCF / valuation (P/Book proxy)
L8: Reused generic
"""
from __future__ import annotations

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


def _score_l1_insurance(f: TickerFinancials) -> LayerScore:
    """L1 — Premium earned 5y CAGR."""
    premiums = f.premium_earned_5y or []
    # Fall back to generic revenue
    rev = f.revenue_5y or []

    if premiums and len(premiums) >= _MIN_YEARS:
        series = premiums
        source = "premium_earned"
    elif rev and len(rev) >= _MIN_YEARS:
        series = rev
        source = "revenue_fallback"
    else:
        return LayerScore(
            layer_id=1, name="Revenue Growth (Insurance)",
            score=0, verdict="INSUFFICIENT_DATA",
            rationale="no premium / revenue data",
            inputs={}, data_completeness=0.0,
        )

    import math
    g = cagr(series[0], series[-1], len(series) - 1)
    if math.isnan(g):
        return LayerScore(
            layer_id=1, name="Revenue Growth (Insurance)",
            score=0, verdict="INSUFFICIENT_DATA",
            rationale="CAGR undefined (non-positive start value)",
            inputs={"source": source}, data_completeness=0.3,
        )

    if g >= 0.10:
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
        layer_id=1, name="Revenue Growth (Insurance)",
        score=score, verdict=verdict,
        rationale=f"Premium CAGR {g*100:.1f}% ({source})",
        inputs={"cagr": g, "source": source, "premium_series": series,
                "is_cyclical": False, "tier": "mid"},
        data_completeness=min(1.0, len(series) / 5),
    )


def _score_l2_insurance(f: TickerFinancials) -> LayerScore:
    """L2 — Combined ratio 3y avg. Pass <95%, Reject >105%."""
    premiums = f.premium_earned_5y or []
    losses = f.losses_incurred_5y or []
    expenses = f.expenses_incurred_5y or []
    rev = f.revenue_5y or []
    op = f.operating_income_5y or []

    if premiums and losses and len(premiums) >= _MIN_YEARS:
        n = min(len(premiums), len(losses),
                len(expenses) if expenses else len(premiums))
        ratios = []
        for i in range(-min(n, 3), 0):
            p = premiums[i]
            if p <= 0:
                continue
            l_i = losses[i]
            e_i = expenses[i] if expenses and abs(i) <= len(expenses) else 0
            ratios.append((l_i + e_i) / p)

        if ratios:
            cr_avg = sum(ratios) / len(ratios)
            cr_slope = linear_slope(ratios) if len(ratios) >= 2 else 0.0
            source = "combined_ratio"
        else:
            cr_avg = 1.0
            cr_slope = 0.0
            source = "combined_ratio_nodata"
    elif rev and op and len(rev) >= _MIN_YEARS:
        # Fall back: invert operating margin as proxy for combined ratio
        cr_series = [(rev[i] - op[i]) / rev[i] if rev[i] > 0 else 1.0
                     for i in range(-min(len(rev), len(op), 3), 0)]
        cr_avg = sum(cr_series) / len(cr_series) if cr_series else 1.0
        cr_slope = linear_slope(cr_series) if len(cr_series) >= 2 else 0.0
        source = "cost_ratio_fallback"
        ratios = cr_series
    else:
        return LayerScore(
            layer_id=2, name="Margin — Combined Ratio (Insurance)",
            score=4, verdict="CAUTION",
            rationale="Combined ratio data unavailable — neutral fallback",
            inputs={}, data_completeness=0.0,
        )

    # Score: <90% = excellent, <95% = pass, <100% = caution, >=105% = reject
    if cr_avg < 0.90:
        level = 8
    elif cr_avg < 0.95:
        level = 6
    elif cr_avg < 1.00:
        level = 4
    elif cr_avg < 1.05:
        level = 2
    else:
        level = 0

    trend = 1 if cr_slope < -0.01 else 0  # improving = bonus

    score = clamp(level + trend, 0, 10)
    verdict = "PASS" if score >= 7 else ("CAUTION" if score >= 4 else "FAIL")
    return LayerScore(
        layer_id=2, name="Margin — Combined Ratio (Insurance)",
        score=score, verdict=verdict,
        rationale=(
            f"Combined ratio 3y avg {cr_avg*100:.1f}% (pass<95%) · "
            f"slope {cr_slope*100:+.2f}pp/y [{source}]"
        ),
        inputs={"combined_ratio_avg": cr_avg,
                "combined_ratio_slope": cr_slope,
                "source": source,
                # Checklist20 Q5 — expose as margin analog
                "gm_5y": [1.0 - r for r in (ratios if ratios else [cr_avg])],
                "om_5y": [1.0 - r for r in (ratios if ratios else [cr_avg])],
                "median": {"gross": 0.05, "operating": 0.05}},
        data_completeness=min(1.0, len(ratios if ratios else []) / 3),
    )


def _score_l3_insurance(f: TickerFinancials) -> LayerScore:
    """L3 — Earnings quality gate for insurers.

    Primary: investment income stability (more relevant for life insurers).
    Secondary: operating income growth + net income trend (works for P&C too).

    P&C insurers (Progressive, Travelers) earn most profit from underwriting,
    so investment income / total revenue can be low (5-10%) — that is NOT a
    quality failure. Gate on sustained profitability instead.
    """
    inv_inc = f.investment_income_fin_5y or []
    premiums = f.premium_earned_5y or []
    rev = f.revenue_5y or []
    op = f.operating_income_5y or []
    ni = f.net_income_5y or []

    # ── Path 1: investment income ratio (life insurers / BRK-type) ────────
    # Only use this as primary signal when inv_income / total_rev >= 15% avg
    inv_score = 0
    inv_ratios: list[float] = []
    if inv_inc and (premiums or rev):
        base_series = premiums if premiums else rev
        n = min(len(inv_inc), len(base_series))
        for i in range(-min(n, 3), 0):
            total_i = base_series[i] + inv_inc[i]
            if total_i > 0:
                inv_ratios.append(inv_inc[i] / total_i)
        if inv_ratios:
            avg_ratio = sum(inv_ratios) / len(inv_ratios)
            inv_slope = linear_slope(inv_ratios) if len(inv_ratios) >= 2 else 0.0
            if avg_ratio >= 0.25:
                inv_score = 4  # life/diversified insurer: high investment income
            elif avg_ratio >= 0.15:
                inv_score = 3
            elif avg_ratio >= 0.08:
                inv_score = 2  # P&C typical range — don't penalise
            else:
                inv_score = 1  # very low but not a failure
            if inv_slope > 0.01:
                inv_score = min(inv_score + 1, 4)

    # ── Path 2: operating income / net income growth (universal signal) ───
    op_score = 0
    if op and len(op) >= _MIN_YEARS:
        op_slope = linear_slope(op[-3:])
        if op_slope > 0:
            op_score = 4
        elif op_slope > -0.05 * max(abs(o) for o in op[-3:] if o != 0):
            op_score = 2
        else:
            op_score = 0

        # Penalise: majority of op-income years negative
        neg_op = sum(1 for o in op if o < 0)
        if neg_op / len(op) >= 0.4:
            op_score = max(0, op_score - 2)

    # ── Path 3: net income trend (ultimate fallback when op_income absent) ─
    ni_score = 0
    ni = f.net_income_5y or []
    if ni and len(ni) >= _MIN_YEARS and op_score == 0:
        ni_slope = linear_slope(ni[-3:])
        neg_ni = sum(1 for n in ni if n < 0)
        if ni_slope > 0 and neg_ni == 0:
            ni_score = 4
        elif ni_slope >= 0 and neg_ni <= 1:
            ni_score = 3
        elif neg_ni / len(ni) < 0.4:
            ni_score = 2
        else:
            ni_score = 0

    # Combine: use best of the three signals + both-good bonus
    combined_base = max(inv_score, op_score, ni_score)
    both_good_bonus = 2 if (max(inv_score, ni_score) >= 2 and max(op_score, ni_score) >= 3) else 0
    score_val = clamp(combined_base + both_good_bonus, 0, 10)
    verdict = "PASS" if score_val >= 7 else ("CAUTION" if score_val >= 4 else "FAIL")

    avg_ratio_str = f"{sum(inv_ratios)/len(inv_ratios)*100:.1f}%" if inv_ratios else "N/A"
    return LayerScore(
        layer_id=3, name="Quality of Growth — Earnings Quality (Insurance)",
        score=score_val, verdict=verdict,
        rationale=(
            f"Inv income ratio 3y avg {avg_ratio_str} · "
            f"Op income trend score {op_score}/4 · combined {score_val:.0f}/10"
        ),
        inputs={"inv_income_ratio_series": inv_ratios,
                "inv_score": inv_score, "op_score": op_score,
                "roic": None, "wacc": 0.09, "spread": None,
                "fcf_5y": [], "fcf_ni_ratio_avg": None,
                "sbc_adjusted": False, "historical_loss_penalty": 0,
                "roic_3y_avg": None,
                "ccc_days": None, "ccc_trend": None,
                "inventory_days_latest": None, "receivable_days_latest": None},
        data_completeness=min(1.0, len(inv_ratios) / 3) if inv_ratios else 0.5,
    )


def _score_l5_insurance(f: TickerFinancials) -> LayerScore:
    """L5 — Reserve adequacy proxy (equity / written premium) + dilution."""
    using_premium = bool(f.premium_earned_5y)
    premiums = f.premium_earned_5y or f.revenue_5y or []  # fallback to revenue
    equity = f.equity_5y or []
    shares = f.diluted_shares_5y or []

    # When using revenue as proxy (includes earned + non-earned), thresholds differ:
    # Pure premium: pass >=1.0x; revenue proxy: pass >=0.25x (revenue > premiums)
    pass_thresh = 1.0 if using_premium else 0.25
    warn_thresh = 0.5 if using_premium else 0.12

    if premiums and equity and len(premiums) >= 1:
        reserve_ratio = equity[-1] / premiums[-1] if premiums[-1] > 0 else 0.0
        if reserve_ratio >= pass_thresh * 1.5:
            res_score = 6
        elif reserve_ratio >= pass_thresh:
            res_score = 5
        elif reserve_ratio >= warn_thresh:
            res_score = 3
        else:
            res_score = 0
    else:
        res_score = 3  # neutral when data absent

    # Dilution score (0-4)
    dil_score = 4
    if len(shares) >= 3:
        sc = cagr(shares[0], shares[-1], len(shares) - 1)
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

    score = clamp(res_score + dil_score, 0, 10)
    verdict = "PASS" if score >= 7 else ("CAUTION" if score >= 4 else "FAIL")
    reserve_ratio_val = equity[-1] / premiums[-1] if (premiums and equity and premiums[-1] > 0) else 0.0
    return LayerScore(
        layer_id=5, name="Balance Sheet (Insurance)",
        score=score, verdict=verdict,
        rationale=f"Equity/Premium ratio {reserve_ratio_val:.2f}x (pass>=1.0x)",
        inputs={"equity_premium_ratio": reserve_ratio_val,
                "reserve_score": res_score, "dilution_score": dil_score,
                "net_debt_ebitda": 1.0 / reserve_ratio_val if reserve_ratio_val > 0 else 99,
                "interest_coverage": 999,
                "shares_cagr": 0.0, "balance_quality": "insurance"},
        data_completeness=min(1.0, len(premiums) / 5) if premiums else 0.3,
    )


def _score_l4_insurance(f: TickerFinancials) -> LayerScore:
    """L4 — Insurance moat proxy. Try generic first; fall back to NI stability + scale."""
    l4_generic = score_layer_4(f)
    if l4_generic.verdict != "INSUFFICIENT_DATA":
        return l4_generic

    ni = f.net_income_5y or []
    premiums = f.premium_earned_5y or []
    mc = f.market_cap_current

    if not ni or len(ni) < _MIN_YEARS:
        return LayerScore(
            layer_id=4, name="Moat (Insurance)", score=4, verdict="CAUTION",
            rationale="[insurance: moat data limited] neutral score 4",
            inputs={"moat_override_applied": True, "roic_std": None, "gm_premium": None, "market_cap": mc},
            data_completeness=0.3,
        )

    # NI stability OR strong upward trend — both are moat indicators
    ni_cv = _statistics.pstdev(ni) / abs(sum(ni) / len(ni)) if sum(ni) != 0 else 1.0
    ni_slope = linear_slope(ni)
    ni_growth = cagr(ni[0], ni[-1], len(ni) - 1) if ni[0] > 0 else 0.0
    if ni_cv < 0.10 or ni_growth >= 0.15:
        consist = 3   # stable OR strongly growing
    elif ni_cv < 0.25 or ni_growth >= 0.05:
        consist = 2
    else:
        consist = 0

    # Premium scale (larger = more stable)
    prem_latest = premiums[-1] if premiums else 0
    if prem_latest >= 50e9 or mc >= 100e9:
        scale = 2
    elif prem_latest >= 10e9 or mc >= 20e9:
        scale = 1
    else:
        scale = 0

    raw = consist + scale
    score_val = clamp(raw, 0, 7)
    verdict = "PASS" if score_val >= 6 else ("CAUTION" if score_val >= 3 else "FAIL")
    return LayerScore(
        layer_id=4, name="Moat (Insurance)", score=score_val, verdict=verdict,
        rationale=f"[insurance proxy] NI CV {ni_cv:.2f} · market cap ${mc/1e9:.0f}B",
        inputs={"ni_cv": ni_cv, "consist": consist, "scale": scale,
                "moat_override_applied": True, "roic_std": None, "gm_premium": None, "market_cap": mc},
        data_completeness=0.6,
    )


def score(fin: TickerFinancials, scan_date: str | None = None) -> FundamentalReport:
    """Run all 8 layers for an insurer; return FundamentalReport."""
    scan_date = scan_date or date.today().isoformat()

    l1 = _score_l1_insurance(fin)
    l2 = _score_l2_insurance(fin)
    l3 = _score_l3_insurance(fin)
    l4 = _score_l4_insurance(fin)
    l5 = _score_l5_insurance(fin)
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

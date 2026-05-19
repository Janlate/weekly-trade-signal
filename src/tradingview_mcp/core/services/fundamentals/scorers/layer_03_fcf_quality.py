"""Layer 3 — Growth Quality / FCF + ROIC — Gate."""
from __future__ import annotations

from tradingview_mcp.core.services.fundamentals.industry_config import get_wacc, is_cyclical
from tradingview_mcp.core.services.fundamentals.providers.base import TickerFinancials
from tradingview_mcp.core.services.fundamentals.schemas import LayerScore
from tradingview_mcp.core.services.fundamentals.scorers._utils import clamp, safe_div

# GICS sectors where SBC is material — adjust FCF
_TECH_GICS = {"45", "50"}


def score_layer_3(f: TickerFinancials) -> LayerScore:
    rev, ni, op, ocf, capex, sbc, ic = (
        f.revenue_5y, f.net_income_5y, f.operating_income_5y,
        f.ocf_5y, f.capex_5y, f.sbc_5y, f.invested_capital_5y,
    )
    if not all([rev, ni, op, ocf, capex, ic]) or len(rev) < 3:
        return LayerScore(
            layer_id=3, name="Growth Quality / FCF", score=0,
            verdict="INSUFFICIENT_DATA",
            rationale="missing income/cashflow/balance data",
            inputs={}, data_completeness=0.0,
        )

    wacc = get_wacc(f.industry)
    cyclical = is_cyclical(f.industry, f.sub_industry)

    # NOPAT ≈ OpInc × (1 - tax_rate) — use 0.21 default US corporate
    tax_rate = 0.21
    nopat_latest = op[-1] * (1 - tax_rate)
    roic = safe_div(nopat_latest, ic[-1], default=-1.0)

    # For cyclicals: compute 3-year average ROIC to avoid single-trough-year distortion.
    # A trough year with depressed op-income should not FAIL the gate alone.
    roic_3y_avg: float | None = None
    if cyclical and len(op) >= 3 and len(ic) >= 3:
        nopat_3y = [op[i] * (1 - tax_rate) for i in range(-3, 0)]
        roic_3y_vals = [
            safe_div(nopat_3y[i], ic[-(3 - i)], default=None)
            for i in range(3)
        ]
        valid_3y = [r for r in roic_3y_vals if r is not None]
        roic_3y_avg = sum(valid_3y) / len(valid_3y) if valid_3y else roic

    # For cyclicals: use 3y-average ROIC for spread scoring so a trough year doesn't FAIL
    roic_for_spread = roic_3y_avg if (cyclical and roic_3y_avg is not None) else roic

    # FCF (adjust SBC for tech)
    is_tech = f.industry in _TECH_GICS
    fcf_5y = []
    for i in range(len(ocf)):
        sbc_i = sbc[i] if (is_tech and i < len(sbc)) else 0
        capex_i = capex[i] if i < len(capex) else 0
        fcf_5y.append(ocf[i] - capex_i - sbc_i)

    # FCF/NI ratio over last 3y
    fcf_ni_ratios = []
    for i in range(-3, 0):
        if ni[i] > 0:
            fcf_ni_ratios.append(fcf_5y[i] / ni[i])
    avg_fcf_ni = sum(fcf_ni_ratios) / len(fcf_ni_ratios) if fcf_ni_ratios else 0

    # ROIC - WACC spread (uses cyclical-adjusted roic_for_spread)
    spread = roic_for_spread - wacc
    if spread >= 0.10:
        spread_score = 5
    elif spread >= 0.05:
        spread_score = 4
    elif spread >= 0.02:
        spread_score = 3
    elif spread >= 0:
        spread_score = 2
    elif spread >= -0.02:
        spread_score = 1
    else:
        spread_score = 0

    # FCF / NI quality
    if avg_fcf_ni >= 1.0:
        fcf_score = 3
    elif avg_fcf_ni >= 0.8:
        fcf_score = 2
    elif avg_fcf_ni >= 0.6:
        fcf_score = 1
    else:
        fcf_score = 0

    # CCC computation — expose detailed metrics for Q10 checklist
    ccc_days: float | None = None
    ccc_trend: float | None = None   # 3y OLS slope of CCC (positive = deteriorating)
    inventory_days_latest: float | None = None
    receivable_days_latest: float | None = None

    ccc_score = 2  # neutral baseline
    if f.inventory_5y and f.receivables_5y and f.cogs_5y:
        def _compute_ccc_for_year(
            inv: float, rec: float, pay: float,
            cogs: float, revenue: float,
        ) -> float:
            """Compute CCC = DIO + DSO - DPO for one year."""
            c = cogs if cogs > 0 else revenue * 0.6
            dio = (inv / c) * 365 if c > 0 else 0.0
            dso = (rec / revenue) * 365 if revenue > 0 else 0.0
            dpo = (pay / c) * 365 if c > 0 else 0.0
            return dio + dso - dpo

        n = min(
            len(f.inventory_5y), len(f.receivables_5y), len(f.cogs_5y),
            len(rev), len(f.payables_5y) if f.payables_5y else 9999,
        )
        pays = f.payables_5y if f.payables_5y else [0.0] * n

        ccc_series: list[float] = []
        for i in range(-n, 0):
            pay_i = pays[i] if abs(i) <= len(pays) else 0.0
            ccc_i = _compute_ccc_for_year(
                f.inventory_5y[i], f.receivables_5y[i], pay_i,
                f.cogs_5y[i], rev[i],
            )
            ccc_series.append(ccc_i)

        ccc_days = ccc_series[-1]

        # Latest-year component breakdown (for evidence)
        cogs_lat = f.cogs_5y[-1] if f.cogs_5y[-1] > 0 else rev[-1] * 0.6
        inventory_days_latest = (f.inventory_5y[-1] / cogs_lat) * 365 if cogs_lat > 0 else 0.0
        receivable_days_latest = (f.receivables_5y[-1] / rev[-1]) * 365 if rev[-1] > 0 else 0.0

        # 3-year CCC trend via OLS slope
        if len(ccc_series) >= 3:
            recent = ccc_series[-3:]
            xs = list(range(len(recent)))
            x_mean = sum(xs) / len(xs)
            y_mean = sum(recent) / len(recent)
            denom = sum((x - x_mean) ** 2 for x in xs)
            ccc_trend = (
                sum((xs[i] - x_mean) * (recent[i] - y_mean) for i in range(len(xs))) / denom
                if denom > 0 else 0.0
            )
        else:
            ccc_trend = 0.0

        # Score: < 60d great; 60–90 OK; > 90 caution; rising trend penalises
        if ccc_days < 60:
            ccc_score = 2
        elif ccc_days < 90:
            ccc_score = 1
        else:
            ccc_score = 0
        # Deteriorating trend (slope > 5 days/year) → subtract 1
        if ccc_trend is not None and ccc_trend > 5:
            ccc_score = max(0, ccc_score - 1)

    # Historical ROIC penalty: if 40%+ of op_income years are negative,
    # the company has a significant track record of capital destruction.
    # Subtract 2 from raw to push CAUTION → FAIL in borderline cases.
    # For cyclicals: only count years where op_income < 0 AND it's not just a trough.
    # Threshold raised to 50% for cyclicals to account for normal cycle troughs.
    negative_op_years = sum(1 for o in op if o < 0)
    loss_threshold = 0.50 if cyclical else 0.40
    historical_loss_penalty = 2 if negative_op_years / len(op) >= loss_threshold else 0

    raw = spread_score + fcf_score + ccc_score - historical_loss_penalty
    score = clamp(raw, 0, 10)
    verdict = "PASS" if score >= 7 else ("CAUTION" if score >= 4 else "FAIL")

    cyclical_note = ""
    if cyclical and roic_3y_avg is not None:
        cyclical_note = f" [cyclical: 3y-avg ROIC {roic_3y_avg*100:.1f}% used for spread]"

    rationale = (
        f"ROIC {roic*100:.1f}% vs WACC {wacc*100:.0f}% (spread {spread*100:+.1f}pp); "
        f"FCF/NI 3y avg {avg_fcf_ni:.2f}"
        + (" [SBC-adjusted]" if is_tech else "")
        + cyclical_note
        + (f" [historical-loss-penalty -{historical_loss_penalty}]" if historical_loss_penalty else "")
    )

    return LayerScore(
        layer_id=3, name="Growth Quality / FCF", score=score, verdict=verdict,
        rationale=rationale,
        inputs={
            "roic": roic,
            "wacc": wacc,
            "spread": spread,
            "fcf_5y": fcf_5y,
            "fcf_ni_ratio_avg": avg_fcf_ni,
            "sbc_adjusted": is_tech,
            "historical_loss_penalty": historical_loss_penalty,
            "roic_3y_avg": roic_3y_avg,       # None for non-cyclicals
            # CCC fields — for Q10 checklist
            "ccc_days": ccc_days,             # latest year's CCC in days (None if data missing)
            "ccc_trend": ccc_trend,           # 3y OLS slope (positive = deteriorating, None if missing)
            "inventory_days_latest": inventory_days_latest,
            "receivable_days_latest": receivable_days_latest,
        },
        data_completeness=1.0,
    )

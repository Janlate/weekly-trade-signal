"""Layer 3 — Growth Quality / FCF + ROIC — Gate."""
from __future__ import annotations

from tradingview_mcp.core.services.fundamentals.industry_config import get_wacc
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

    # NOPAT ≈ OpInc × (1 - tax_rate) — use 0.21 default US corporate
    tax_rate = 0.21
    nopat_latest = op[-1] * (1 - tax_rate)
    roic = safe_div(nopat_latest, ic[-1], default=-1.0)

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

    # ROIC - WACC spread
    spread = roic - wacc
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

    # CCC trend (Phase 1: skip if data incomplete; neutral)
    ccc_score = 2  # neutral baseline; refine when inventory/receivables available
    if f.inventory_5y and f.receivables_5y and f.cogs_5y:
        # CCC = DIO + DSO - DPO; lower is better
        inv_latest, rec_latest = f.inventory_5y[-1], f.receivables_5y[-1]
        cogs_latest = f.cogs_5y[-1] if f.cogs_5y[-1] else rev[-1] * 0.6
        dio = (inv_latest / cogs_latest) * 365 if cogs_latest else 0
        dso = (rec_latest / rev[-1]) * 365 if rev[-1] else 0
        ccc = dio + dso
        # below 60d great, 60-120 OK, 120+ caution
        if ccc < 60:
            ccc_score = 2
        elif ccc < 120:
            ccc_score = 1
        else:
            ccc_score = 0

    # Historical ROIC penalty: if 40%+ of op_income years are negative,
    # the company has a significant track record of capital destruction.
    # Subtract 2 from raw to push CAUTION → FAIL in borderline cases.
    negative_op_years = sum(1 for o in op if o < 0)
    historical_loss_penalty = 2 if negative_op_years / len(op) >= 0.4 else 0

    raw = spread_score + fcf_score + ccc_score - historical_loss_penalty
    score = clamp(raw, 0, 10)
    verdict = "PASS" if score >= 7 else ("CAUTION" if score >= 4 else "FAIL")

    rationale = (
        f"ROIC {roic*100:.1f}% vs WACC {wacc*100:.0f}% (spread {spread*100:+.1f}pp); "
        f"FCF/NI 3y avg {avg_fcf_ni:.2f}"
        + (" [SBC-adjusted]" if is_tech else "")
        + (f" [historical-loss-penalty -{historical_loss_penalty}]" if historical_loss_penalty else "")
    )

    return LayerScore(
        layer_id=3, name="Growth Quality / FCF", score=score, verdict=verdict,
        rationale=rationale,
        inputs={"roic": roic, "wacc": wacc, "spread": spread,
                "fcf_5y": fcf_5y, "fcf_ni_ratio_avg": avg_fcf_ni,
                "sbc_adjusted": is_tech,
                "historical_loss_penalty": historical_loss_penalty},
        data_completeness=1.0,
    )

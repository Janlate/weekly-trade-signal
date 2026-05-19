"""Layer 7 — Valuation: DCF + PEG + EV/Sales."""
from __future__ import annotations

from tradingview_mcp.core.services.fundamentals.industry_config import get_wacc
from tradingview_mcp.core.services.fundamentals.providers.base import TickerFinancials
from tradingview_mcp.core.services.fundamentals.schemas import LayerScore
from tradingview_mcp.core.services.fundamentals.scorers._utils import (
    cagr, clamp, safe_div,
)


def _dcf_value(revenue_growth: float, op_margin: float, capex_pct: float,
               tax_rate: float, wacc: float, terminal_growth: float,
               rev_latest: float, years: int = 5, shares_out: float = 1.0) -> float:
    """Returns intrinsic value per share."""
    pv = 0
    rev = rev_latest
    fcf = 0.0
    for y in range(1, years + 1):
        rev *= (1 + revenue_growth)
        ebit = rev * op_margin
        nopat = ebit * (1 - tax_rate)
        capex = rev * capex_pct
        fcf = nopat - capex
        pv += fcf / ((1 + wacc) ** y)
    terminal_fcf = fcf * (1 + terminal_growth)
    terminal = terminal_fcf / (wacc - terminal_growth) / ((1 + wacc) ** years)
    return (pv + terminal) / shares_out


def score_layer_7(f: TickerFinancials) -> LayerScore:
    if not all([f.revenue_5y, f.operating_income_5y, f.capex_5y, f.diluted_shares_5y,
                f.price_current]):
        return LayerScore(
            layer_id=7, name="Valuation", score=0,
            verdict="INSUFFICIENT_DATA",
            rationale="missing inputs for valuation",
            inputs={}, data_completeness=0.0,
        )

    import math
    wacc = get_wacc(f.industry)
    rev_growth_hist = cagr(f.revenue_5y[0], f.revenue_5y[-1], len(f.revenue_5y) - 1)
    op_margin = f.operating_income_5y[-1] / f.revenue_5y[-1] if f.revenue_5y[-1] else 0
    capex_pct = f.capex_5y[-1] / f.revenue_5y[-1] if f.revenue_5y[-1] else 0.05
    shares = f.diluted_shares_5y[-1]
    rev_latest = f.revenue_5y[-1]

    # 3-scenario DCF — guard against NaN from cagr() (which returns NaN when start <= 0)
    _growth = rev_growth_hist if (rev_growth_hist is not None and not math.isnan(rev_growth_hist)) else 0.08
    base_growth = max(0.03, min(0.30, _growth))
    fair = {
        "bear": _dcf_value(max(0.02, base_growth - 0.05), op_margin * 0.85, capex_pct,
                           0.21, wacc, 0.015, rev_latest, shares_out=shares),
        "base": _dcf_value(base_growth, op_margin, capex_pct,
                           0.21, wacc, 0.025, rev_latest, shares_out=shares),
        "bull": _dcf_value(min(0.35, base_growth + 0.05), op_margin * 1.15, capex_pct,
                           0.21, wacc, 0.035, rev_latest, shares_out=shares),
    }

    # Sensitivity
    fair_wacc_plus = _dcf_value(base_growth, op_margin, capex_pct, 0.21,
                                wacc + 0.01, 0.025, rev_latest, shares_out=shares)
    fair_tg_minus = _dcf_value(base_growth, op_margin, capex_pct, 0.21,
                               wacc, 0.015, rev_latest, shares_out=shares)

    mos = (fair["base"] - f.price_current) / fair["base"] if fair["base"] > 0 else -1

    if mos >= 0.30:
        mos_score = 5
    elif mos >= 0.20:
        mos_score = 4
    elif mos >= 0.10:
        mos_score = 3
    elif mos >= 0:
        mos_score = 2
    else:
        mos_score = 0

    # PEG (1y forward — Phase 1 approximation per spec)
    fwd_growth = f.forward_eps_growth_1y or 0.10
    # Only compute PEG for profitable companies — undefined for losses (spec)
    has_positive_ni = f.net_income_5y and f.net_income_5y[-1] > 0
    if has_positive_ni and f.market_cap_current > 0:
        pe = f.market_cap_current / f.net_income_5y[-1]
        peg = (pe / (fwd_growth * 100)) if fwd_growth > 0 else None
    else:
        pe = None
        peg = None
    if peg is None:
        peg_score = 1   # neutral when not applicable
    elif peg < 1.0:
        peg_score = 3
    elif peg < 1.5:
        peg_score = 2
    elif peg < 2.0:
        peg_score = 1
    else:
        peg_score = 0

    # EV/Sales (current only — Phase 1; historical percentile added below)
    ev = f.market_cap_current + max(f.total_debt_5y[-1] - f.cash_5y[-1], 0) if (
        f.total_debt_5y and f.cash_5y
    ) else f.market_cap_current
    ev_sales = ev / rev_latest if rev_latest else 0
    # Phase 1 simple: just track value, score = 1 (neutral)
    evs_score = 1

    # Q18 — Historical percentile vs own 5y history
    def _percentile_rank(series: list[float], current: float) -> float | None:
        """Return 0.0-1.0 percentile rank of current within series (excl NaN/negative)."""
        valid = [v for v in series if v == v and v > 0]  # exclude NaN (v==v is False for NaN)
        if len(valid) < 2:
            return None
        below = sum(1 for v in valid if v < current)
        return below / len(valid)

    pe_5y_percentile: float | None = None
    pe_5y_series: list[float] = []
    ev_sales_5y_percentile: float | None = None
    ev_sales_5y_series: list[float] = []

    if f.historical_pe_5y:
        pe_5y_series = f.historical_pe_5y
        if pe is not None and pe > 0:
            pe_5y_percentile = _percentile_rank(pe_5y_series, pe)

    if f.historical_ev_sales_5y:
        ev_sales_5y_series = f.historical_ev_sales_5y
        if ev_sales > 0:
            ev_sales_5y_percentile = _percentile_rank(ev_sales_5y_series, ev_sales)

    raw = mos_score + peg_score + evs_score
    score = clamp(raw, 0, 10)

    peg_str = f"PEG {peg:.2f}" if peg else "PEG N/A"
    pe_pctile_str = f" · P/E percentile {pe_5y_percentile*100:.0f}%" if pe_5y_percentile is not None else ""
    rationale = (
        f"Fair (base) ${fair['base']:.2f}, price ${f.price_current:.2f}, MOS {mos*100:+.1f}%; "
        f"{peg_str}; EV/S {ev_sales:.1f}x{pe_pctile_str}"
    )

    return LayerScore(
        layer_id=7, name="Valuation", score=score, verdict="N/A",  # verdict not used at layer 7
        rationale=rationale,
        inputs={
            "fair_value": fair, "mos_pct": mos,
            "sensitivity": {"wacc_plus_1pp": fair_wacc_plus, "tg_minus_1pp": fair_tg_minus},
            "peg": peg, "peg_confidence": "MED", "ev_sales": ev_sales,
            "assumptions": {"rev_growth": base_growth, "op_margin": op_margin,
                            "capex_pct": capex_pct, "wacc": wacc},
            # Q18 historical percentile fields
            "pe_5y_percentile": pe_5y_percentile,
            "pe_5y_series": pe_5y_series,
            "ev_sales_5y_percentile": ev_sales_5y_percentile,
            "ev_sales_5y_series": ev_sales_5y_series,
        },
        data_completeness=1.0,
    )

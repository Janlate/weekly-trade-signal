"""Composite orchestrator: combine layers → verdict."""
from __future__ import annotations

from datetime import date

from tradingview_mcp.core.services.fundamentals.schemas import (
    ConvictionTier, EntrySignal, FundamentalReport, LayerScore,
)

LAYER_WEIGHTS = {1: 1.0, 2: 1.0, 3: 1.5, 4: 1.5, 5: 1.5, 6: 1.0}


def score_quality(
    ticker: str, layers: dict[str, LayerScore], *,
    industry: str, is_cyclical: bool, raw_inputs_ref: str,
    scan_date: str | None = None,
) -> FundamentalReport:
    scan_date = scan_date or date.today().isoformat()

    total_weight = 0
    total_score = 0
    layer_3 = layer_5 = None
    has_fail = False
    has_caution = False

    for key, layer in layers.items():
        weight = LAYER_WEIGHTS.get(layer.layer_id, 1.0)
        total_weight += weight
        total_score += layer.score * weight
        if layer.layer_id == 3:
            layer_3 = layer
        if layer.layer_id == 5:
            layer_5 = layer
        if layer.verdict == "FAIL":
            has_fail = True
        elif layer.verdict == "CAUTION":
            has_caution = True

    composite = (total_score / total_weight) if total_weight else 0
    composite = round(composite, 2)

    _gate_reject_verdicts = {"FAIL", "INSUFFICIENT_DATA"}
    layer3_fail = layer_3 is None or layer_3.verdict in _gate_reject_verdicts
    layer5_fail = layer_5 is None or layer_5.verdict in _gate_reject_verdicts

    if layer3_fail or layer5_fail:
        verdict = "QUALITY_REJECT"
    elif composite < 5:
        verdict = "QUALITY_REJECT"
    elif composite >= 7 and not has_fail:
        verdict = "QUALITY_PASS"
    else:
        verdict = "QUALITY_WATCH"

    return FundamentalReport(
        ticker=ticker, scan_date=scan_date, industry=industry,
        is_cyclical=is_cyclical, composite_score=composite,
        quality_verdict=verdict, layers=layers,
        raw_inputs_ref=raw_inputs_ref,
    )


def score_entry_signal(
    ticker: str, *, price: float, quality_composite: float,
    quality_verdict: str, layer_7: dict, layer_8: dict, moat_score: float,
) -> EntrySignal:
    mos = layer_7.get("mos_pct", -1)
    sens = layer_7.get("sensitivity", {})
    fair_base = layer_7.get("fair_value", {}).get("base", 0)
    wacc_plus = sens.get("wacc_plus_1pp", 0)
    tg_minus = sens.get("tg_minus_1pp", 0)

    sensitivity_ok = wacc_plus > price and tg_minus > price

    if quality_verdict == "QUALITY_REJECT":
        verdict = "SKIP"
        conf = ConvictionTier.LOW
    elif quality_verdict == "QUALITY_PASS" and mos >= 0.20 and sensitivity_ok:
        verdict = "GO"
        conf = ConvictionTier(layer_8.get("conviction_tier", "MED"))
    elif quality_verdict == "QUALITY_PASS":
        verdict = "WAIT"
        conf = ConvictionTier.MED
    elif quality_verdict == "QUALITY_WATCH" and mos < 0:
        verdict = "TRIM"
        conf = ConvictionTier.MED
    else:
        verdict = "WAIT"
        conf = ConvictionTier.LOW

    return EntrySignal(
        ticker=ticker, price=price, quality_composite=quality_composite,
        layer_7=layer_7, layer_8=layer_8, verdict=verdict, confidence=conf,
    )

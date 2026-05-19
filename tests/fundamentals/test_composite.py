from tradingview_mcp.core.services.fundamentals.composite import (
    score_quality, score_entry_signal,
)
from tradingview_mcp.core.services.fundamentals.schemas import LayerScore


def _passing_layer(layer_id: int, score: float = 8.0) -> LayerScore:
    return LayerScore(
        layer_id=layer_id, name=f"L{layer_id}", score=score,
        verdict="PASS", rationale="ok", inputs={}, data_completeness=1.0,
    )


def test_composite_quality_pass():
    layers = {f"{i}_x": _passing_layer(i, 8.5) for i in range(1, 7)}
    report = score_quality("MSFT", layers, industry="45", is_cyclical=False,
                          raw_inputs_ref="path")
    assert report.quality_verdict == "QUALITY_PASS"
    assert report.composite_score >= 7


def test_composite_quality_reject_when_layer3_fails():
    layers = {f"{i}_x": _passing_layer(i, 8.0) for i in range(1, 7)}
    layers["3_x"] = LayerScore(
        layer_id=3, name="L3", score=3.0, verdict="FAIL", rationale="bad ROIC",
        inputs={}, data_completeness=1.0,
    )
    report = score_quality("X", layers, industry="45", is_cyclical=False,
                          raw_inputs_ref="path")
    assert report.quality_verdict == "QUALITY_REJECT"


def test_composite_quality_reject_when_layer5_fails():
    layers = {f"{i}_x": _passing_layer(i, 8.0) for i in range(1, 7)}
    layers["5_x"] = LayerScore(
        layer_id=5, name="L5", score=2.0, verdict="FAIL", rationale="overleveraged",
        inputs={}, data_completeness=1.0,
    )
    report = score_quality("X", layers, industry="45", is_cyclical=False,
                          raw_inputs_ref="path")
    assert report.quality_verdict == "QUALITY_REJECT"


def test_entry_signal_go_when_quality_pass_and_high_mos():
    quality_score = 8.5
    layer_7 = {"mos_pct": 0.25, "sensitivity": {"wacc_plus_1pp": 200, "tg_minus_1pp": 195},
               "fair_value": {"bear": 180, "base": 230, "bull": 280}}
    layer_8 = {"conviction_tier": "HIGH"}
    signal = score_entry_signal("MSFT", price=172, quality_composite=quality_score,
                                quality_verdict="QUALITY_PASS",
                                layer_7=layer_7, layer_8=layer_8, moat_score=7)
    assert signal.verdict == "GO"

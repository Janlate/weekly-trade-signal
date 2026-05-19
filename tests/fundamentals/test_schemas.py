import pytest
from pydantic import ValidationError

from tradingview_mcp.core.services.fundamentals.schemas import (
    LayerScore, FundamentalReport, EntrySignal, ConvictionTier
)


def test_layer_score_valid():
    score = LayerScore(
        layer_id=1, name="Revenue Growth", score=8.5,
        verdict="PASS", rationale="strong cagr", inputs={"cagr_5y": 0.18},
        data_completeness=1.0,
    )
    assert score.score == 8.5
    assert score.verdict == "PASS"


def test_layer_score_clamps_score_field():
    # score > 10 should fail validation (caller must clamp before constructing)
    with pytest.raises(ValidationError):
        LayerScore(
            layer_id=1, name="Revenue Growth", score=12.0,
            verdict="PASS", rationale="x", inputs={}, data_completeness=1.0,
        )


def test_layer_score_negative_fails():
    with pytest.raises(ValidationError):
        LayerScore(
            layer_id=1, name="Revenue Growth", score=-1.0,
            verdict="FAIL", rationale="x", inputs={}, data_completeness=1.0,
        )


def test_layer_score_accepts_na_verdict():
    """Layer 7 (valuation) doesn't gate on PASS/FAIL -- uses "N/A"."""
    score = LayerScore(
        layer_id=7, name="Valuation", score=8.0,
        verdict="N/A", rationale="MOS +27%", inputs={}, data_completeness=1.0,
    )
    assert score.verdict == "N/A"


def test_fundamental_report_minimal():
    report = FundamentalReport(
        ticker="MSFT", scan_date="2026-05-17", industry="Software (GICS 4510)",
        is_cyclical=False, composite_score=9.2,
        quality_verdict="QUALITY_PASS", layers={},
        raw_inputs_ref="stock-reports/data/fundamentals/MSFT/2026-05-17.json",
    )
    assert report.ticker == "MSFT"


def test_entry_signal_minimal():
    sig = EntrySignal(
        ticker="GOOGL", price=172.30, quality_composite=8.5,
        layer_7={"mos_pct": 0.27}, layer_8={"conviction_tier": "HIGH"},
        verdict="GO", confidence=ConvictionTier.HIGH,
    )
    assert sig.verdict == "GO"

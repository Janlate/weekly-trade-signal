from tradingview_mcp.core.services.fundamentals.scorers.layer_08_position_sizing import (
    generate_position_plan,
)


def test_layer_8_high_conviction():
    plan = generate_position_plan(
        composite_score=8.5, mos_pct=0.27, moat_score=7,
        fair_bear=200, fair_base=235, fair_bull=275,
        current_price=172, layer_rationales={},
    )
    assert plan["conviction_tier"] == "HIGH"
    assert plan["suggested_size_pct"] == (0.015, 0.025)
    assert plan["stop_loss"] == 180.0
    assert plan["take_profit"] == [235.0, 275.0, 330.0]
    assert plan["dcf_applicable"] is True
    assert plan["stop_loss_source"] == "dcf_bear"
    assert plan["take_profit_source"] == "dcf"


def test_layer_8_speculative_low_conviction():
    plan = generate_position_plan(
        composite_score=5.0, mos_pct=0.05, moat_score=4,
        fair_bear=50, fair_base=70, fair_bull=90,
        current_price=68, layer_rationales={},
    )
    assert plan["conviction_tier"] == "SPEC"


def test_layer_8_dcf_invalid_falls_back_to_technical():
    """High-capex/utility profile: DCF outputs are negative or zero.
    Stop loss falls back to technical 15% drawdown; take_profit becomes
    price-relative. Both source flags reflect the fallback."""
    plan = generate_position_plan(
        composite_score=7.5, mos_pct=-0.5, moat_score=7,
        fair_bear=-10.0, fair_base=0.0, fair_bull=0.0,
        current_price=200.0, layer_rationales={},
    )
    assert plan["dcf_applicable"] is False
    assert plan["stop_loss"] == 170.0  # 200 * 0.85
    assert plan["stop_loss_source"] == "technical_15pct"
    assert plan["take_profit"] == [230.0, 260.0, 300.0]  # 1.15/1.30/1.50 × price
    assert plan["take_profit_source"] == "price_relative"


# ── Sanity-guard tests ────────────────────────────────────────────────────────

def test_layer_8_stop_within_30pct_no_fallback():
    """price=100, dcf_bear=80 → raw_stop=72, drawdown=28% < 30% → no fallback."""
    plan = generate_position_plan(
        composite_score=7.0, mos_pct=0.20, moat_score=6,
        fair_bear=80.0, fair_base=110.0, fair_bull=140.0,
        current_price=100.0, layer_rationales={},
    )
    assert plan["dcf_applicable"] is True
    # raw_stop = 80 * 0.9 = 72;  drawdown = (100-72)/100 = 28% < 30%
    assert plan["stop_loss"] == 72.0
    assert plan["stop_loss_source"] == "dcf_bear"
    assert plan.get("dcf_bear_unusable") is None or plan.get("dcf_bear_unusable") is False


def test_layer_8_stop_exceeds_30pct_triggers_mechanical_fallback():
    """price=100, dcf_bear=30 → raw_stop=27, drawdown=73% > 30% → mechanical -15%."""
    plan = generate_position_plan(
        composite_score=6.0, mos_pct=-0.70, moat_score=5,
        fair_bear=30.0, fair_base=50.0, fair_bull=80.0,
        current_price=100.0, layer_rationales={},
    )
    assert plan["dcf_applicable"] is True
    assert plan["stop_loss"] == 85.0          # 100 * 0.85
    assert plan["stop_loss_source"] == "mechanical_15pct_fallback"
    assert plan["dcf_bear_unusable"] is True
    assert plan["dcf_bear_reference"] == 27.0  # 30 * 0.9
    # Exit trigger must mention the unusable DCF stop
    assert any("unusable" in t.lower() for t in plan["exit_triggers"])


def test_layer_8_aapl_like_stop_fallback():
    """AAPL-like: price=308.82, fair_bear=70.61 → raw_stop=63.55 (79% drawdown)
    → mechanical fallback to $262.50."""
    plan = generate_position_plan(
        composite_score=5.5, mos_pct=-2.11, moat_score=7,
        fair_bear=70.61, fair_base=99.22, fair_bull=164.60,
        current_price=308.82, layer_rationales={},
    )
    assert plan["dcf_applicable"] is True
    assert plan["stop_loss"] == round(308.82 * 0.85, 2)   # 262.50
    assert plan["stop_loss_source"] == "mechanical_15pct_fallback"
    assert plan["dcf_bear_unusable"] is True
    assert plan["dcf_bear_reference"] == round(70.61 * 0.9, 2)  # 63.55
    assert any("unusable" in t.lower() for t in plan["exit_triggers"])

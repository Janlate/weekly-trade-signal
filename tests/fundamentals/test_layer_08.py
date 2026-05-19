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


def test_layer_8_speculative_low_conviction():
    plan = generate_position_plan(
        composite_score=5.0, mos_pct=0.05, moat_score=4,
        fair_bear=50, fair_base=70, fair_bull=90,
        current_price=68, layer_rationales={},
    )
    assert plan["conviction_tier"] == "SPEC"

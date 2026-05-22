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

"""Layer 8 — Position Sizing + Exit Rules (template, not scored 0-10)."""
from __future__ import annotations

from tradingview_mcp.core.services.fundamentals.schemas import ConvictionTier


def generate_position_plan(
    composite_score: float,
    mos_pct: float,
    moat_score: float,
    fair_bear: float,
    fair_base: float,
    fair_bull: float,
    current_price: float,
    layer_rationales: dict[str, str],
) -> dict:
    """Generate position sizing template + exit triggers."""
    # Conviction tier
    if composite_score >= 8 and mos_pct >= 0.20 and moat_score >= 6:
        tier = ConvictionTier.HIGH
        size = (0.015, 0.025)
    elif composite_score >= 6 and mos_pct >= 0.10:
        tier = ConvictionTier.MED
        size = (0.0075, 0.015)
    else:
        tier = ConvictionTier.SPEC
        size = (0.0025, 0.0075)

    # Stop loss = bear * 0.9 (10% below bear case)
    stop_loss = round(fair_bear * 0.9, 2)
    # Take profit = base, bull, bull*1.2
    take_profit = [round(fair_base, 2), round(fair_bull, 2), round(fair_bull * 1.2, 2)]

    # Exit triggers from rationale clues
    exit_triggers: list[str] = []
    for layer_key, rat in layer_rationales.items():
        # crude extraction — extend in Phase 2
        if "below" in rat.lower() or "contracting" in rat.lower():
            exit_triggers.append(f"Watch: {rat}")
    if not exit_triggers:
        exit_triggers = [
            "Thesis broken: layer 3 (FCF/ROIC) drops to FAIL",
            "Thesis broken: layer 5 (Balance Sheet) drops to FAIL",
            f"Valuation reached: price exceeds bull case ${fair_bull:.2f}",
        ]

    return {
        "conviction_tier": tier.value,
        "suggested_size_pct": size,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "exit_triggers": exit_triggers,
    }

"""Layer 8 — Position Sizing + Exit Rules (template, not scored 0-10)."""
from __future__ import annotations

from tradingview_mcp.core.services.fundamentals.schemas import ConvictionTier

# Maximum practical drawdown for a stop-loss to be considered usable.
# Rationale: 30% is near the average 1-year max drawdown of mega-cap stocks
# (typically 20-30%).  A stop wider than 30% from current price cannot be
# acted on by most position-sizing frameworks (risk-per-trade would exceed
# any sensible 1-2% account risk at normal position sizes).
_MAX_STOP_DRAWDOWN_PCT = 0.30

# Mechanical fallback: -15% from current price, matching the existing
# technical_15pct path used when DCF outputs are fully invalid.
_MECHANICAL_STOP_MULT = 0.85


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
    """Generate position sizing template + exit triggers.

    Defensive rules applied when DCF produces invalid outputs
    (negative fair values, or all targets below current price):
      - stop_loss     -> technical 15% drawdown from current price
      - take_profit   -> price-relative +15%/+30%/+50% targets
      - dcf_applicable flag -> False (UI shows disclaimer)

    Conviction tier when DCF is broken (dcf_applicable=False):
      MOS is unreliable, so tier is determined solely by
      composite_score + moat_score to avoid permanently locking
      every capital-intensive business at SPEC.

    Sanity guard (DCF bear stop too wide):
      When DCF IS valid but the implied stop (fair_bear * 0.9) sits more
      than _MAX_STOP_DRAWDOWN_PCT (30%) below current price the stop is
      replaced by the mechanical -15% fallback.  This prevents unusable
      stops like -79% on overvalued names (e.g. AAPL DCF bear << market
      price).  The original DCF bear value is preserved in
      dcf_bear_reference for debugging; dcf_bear_unusable=True signals
      the fallback was triggered.
    """
    # ── Validate DCF outputs ──────────────────────────────────────────────
    dcf_applicable = fair_base > 0 and fair_bear > 0

    # ── Conviction tier ───────────────────────────────────────────────────
    # Only use MOS from DCF when the DCF result is trustworthy.
    effective_mos = mos_pct if dcf_applicable else -1.0
    if composite_score >= 8 and effective_mos >= 0.20 and moat_score >= 6:
        tier = ConvictionTier.HIGH
        size = (0.015, 0.025)
    elif composite_score >= 7 and moat_score >= 6 and (effective_mos >= 0.10 or not dcf_applicable):
        # MED when fundamentals are strong even if DCF can't price it
        tier = ConvictionTier.MED
        size = (0.0075, 0.015)
    elif composite_score >= 6 and effective_mos >= 0.10:
        tier = ConvictionTier.MED
        size = (0.0075, 0.015)
    else:
        tier = ConvictionTier.SPEC
        size = (0.0025, 0.0075)

    # ── Stop loss calculation ─────────────────────────────────────────────
    dcf_bear_unusable = False
    dcf_bear_reference = None

    if dcf_applicable:
        raw_stop = round(fair_bear * 0.9, 2)
        stop_drawdown_pct = (current_price - raw_stop) / current_price if current_price > 0 else 0.0

        if stop_drawdown_pct > _MAX_STOP_DRAWDOWN_PCT:
            # DCF bear stop is too far from price to be actionable — use
            # mechanical -15% fallback and record the original for reference.
            dcf_bear_unusable = True
            dcf_bear_reference = raw_stop
            stop_loss = round(current_price * _MECHANICAL_STOP_MULT, 2)
            stop_loss_source = "mechanical_15pct_fallback"
        else:
            stop_loss = raw_stop
            stop_loss_source = "dcf_bear"
    else:
        stop_loss = round(current_price * _MECHANICAL_STOP_MULT, 2)  # Defensive 15% technical stop
        stop_loss_source = "technical_15pct"

    # ── Take profit calculation ───────────────────────────────────────────
    if dcf_applicable and fair_bull > current_price:
        take_profit = [round(fair_base, 2), round(fair_bull, 2), round(fair_bull * 1.2, 2)]
        take_profit_source = "dcf"
    else:
        # Price-relative targets if DCF invalid or below market
        take_profit = [
            round(current_price * 1.15, 2),
            round(current_price * 1.30, 2),
            round(current_price * 1.50, 2),
        ]
        take_profit_source = "price_relative"

    # ── Exit triggers from rationale clues ───────────────────────────────
    exit_triggers: list[str] = []
    for layer_key, rat in layer_rationales.items():
        if "below" in rat.lower() or "contracting" in rat.lower():
            exit_triggers.append(f"Watch: {rat}")

    if dcf_bear_unusable and dcf_bear_reference is not None:
        drawdown_pct = int(round((current_price - dcf_bear_reference) / current_price * 100))
        exit_triggers.append(
            f"DCF bear stop (${dcf_bear_reference:.2f}) unusable"
            f" ({drawdown_pct}% drawdown) — using mechanical -15% fallback"
        )

    if not exit_triggers:
        exit_triggers = [
            "Thesis broken: layer 3 (FCF/ROIC) drops to FAIL",
            "Thesis broken: layer 5 (Balance Sheet) drops to FAIL",
            f"Valuation reached: price exceeds target ${max(take_profit):.2f}",
        ]

    result: dict = {
        "conviction_tier": tier.value,
        "dcf_applicable": dcf_applicable,
        "suggested_size_pct": size,
        "stop_loss": stop_loss,
        "stop_loss_source": stop_loss_source,
        "take_profit": take_profit,
        "take_profit_source": take_profit_source,
        "exit_triggers": exit_triggers,
    }

    # Append fallback metadata only when the guard fired — keeps the schema
    # clean for normal cases while remaining backward-compatible (consumers
    # checking for dcf_bear_unusable should treat its absence as False).
    if dcf_bear_unusable:
        result["dcf_bear_unusable"] = True
        result["dcf_bear_reference"] = dcf_bear_reference

    return result

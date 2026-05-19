from tradingview_mcp.core.services.fundamentals.industry_config import (
    WACC_DEFAULTS, INDUSTRY_GROWTH_TIERS, INDUSTRY_MARGIN_MEDIANS,
    CYCLICAL_SECTORS, gics_to_tier, get_wacc, get_margin_median, is_cyclical,
)


def test_wacc_defaults_complete():
    for gics in ["10", "15", "20", "25", "30", "35", "40", "45", "50", "55", "60"]:
        assert gics in WACC_DEFAULTS
        assert 0.05 <= WACC_DEFAULTS[gics] <= 0.12


def test_get_wacc_known_sector():
    assert get_wacc("45") == 0.09  # IT


def test_get_wacc_unknown_defaults_to_avg():
    assert 0.07 <= get_wacc("99") <= 0.10  # fallback


def test_gics_to_tier():
    assert gics_to_tier("30") == "slow"      # Staples
    assert gics_to_tier("45") == "fast"      # IT
    assert gics_to_tier("55") == "slow"      # Utilities


def test_margin_median_for_software():
    median = get_margin_median("45", sub_industry="Software")
    assert median["gross"] == 0.70
    assert median["operating"] == 0.25


def test_is_cyclical():
    assert is_cyclical("10") is True   # Energy
    assert is_cyclical("30") is False  # Staples

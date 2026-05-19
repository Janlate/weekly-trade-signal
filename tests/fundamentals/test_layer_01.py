from tradingview_mcp.core.services.fundamentals.providers.base import TickerFinancials
from tradingview_mcp.core.services.fundamentals.scorers.layer_01_revenue import score_layer_1


def _financials(revenue, **kw) -> TickerFinancials:
    return TickerFinancials(ticker="X", revenue_5y=revenue, **kw)


def test_layer_1_hyper_growth_software():
    # ~35%/y for 5 years
    f = _financials([100, 135, 182, 246, 332], industry="45")
    s = score_layer_1(f)
    assert s.verdict == "PASS"
    assert s.score >= 7
    assert "fast" in s.rationale.lower() or "hyper" in s.rationale.lower()


def test_layer_1_slow_utility():
    # ~5%/y for utility (slow tier)
    f = _financials([100, 105, 110, 116, 122], industry="55")
    s = score_layer_1(f)
    assert s.verdict == "PASS"


def test_layer_1_declining_revenue_fails():
    f = _financials([100, 95, 90, 85, 80], industry="45")
    s = score_layer_1(f)
    assert s.verdict == "FAIL"
    assert s.score < 4


def test_layer_1_volatile_low_consistency():
    # bouncing revenue → low consistency
    f = _financials([100, 200, 90, 250, 110], industry="20")
    s = score_layer_1(f)
    # cv is high → consistency bonus low
    assert s.score < 7  # likely CAUTION


def test_layer_1_insufficient_data():
    f = _financials([100, 110], industry="45")  # only 2 years
    s = score_layer_1(f)
    assert s.verdict == "INSUFFICIENT_DATA"


def test_layer_1_cyclical_uses_longer_window_no_penalty():
    # 10y revenue with cyclical pattern — accepted with tier expectations
    f = _financials([100, 130, 90, 140, 70, 160, 80, 180, 90, 200], industry="10")  # Energy
    s = score_layer_1(f)
    # cyclicals shouldn't be punished for volatility per spec
    assert s.verdict in ("PASS", "CAUTION")

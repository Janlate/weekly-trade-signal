"""Tests for CompositeFinancialProvider — field-level fallback merge."""
from unittest.mock import MagicMock

from tradingview_mcp.core.services.fundamentals.providers.base import TickerFinancials
from tradingview_mcp.core.services.fundamentals.providers.composite_provider import (
    CompositeFinancialProvider,
)


def test_composite_uses_first_provider_when_complete():
    p1 = MagicMock()
    p1.name = "sec_edgar"
    p1.fetch.return_value = TickerFinancials(
        ticker="MSFT", revenue_5y=[100, 110, 120, 130, 140],
        source_chain=["sec_edgar"],
    )
    p2 = MagicMock()
    p2.name = "yfinance"
    p2.fetch.return_value = TickerFinancials(ticker="MSFT", revenue_5y=[1, 1, 1, 1, 1])

    composite = CompositeFinancialProvider([p1, p2])
    result = composite.fetch("MSFT")

    assert result.revenue_5y == [100, 110, 120, 130, 140]
    # composite always tries all providers for field-level merge
    p2.fetch.assert_called_once_with("MSFT")


def test_composite_merges_when_primary_missing_field():
    """When primary returns revenue but no price, fill price from secondary."""
    p1 = MagicMock()
    p1.name = "sec_edgar"
    p1.fetch.return_value = TickerFinancials(
        ticker="MSFT", revenue_5y=[100, 110, 120, 130, 140],
        source_chain=["sec_edgar"],
    )  # no price_current
    p2 = MagicMock()
    p2.name = "yfinance"
    p2.fetch.return_value = TickerFinancials(
        ticker="MSFT", price_current=420.0, market_cap_current=3e12,
        forward_eps_growth_1y=0.12, industry="45",
        source_chain=["yfinance"],
    )

    composite = CompositeFinancialProvider([p1, p2])
    result = composite.fetch("MSFT")

    assert result.revenue_5y == [100, 110, 120, 130, 140]
    assert result.price_current == 420.0
    assert result.industry == "45"
    assert result.source_chain == ["sec_edgar", "yfinance"]


def test_composite_returns_none_when_all_fail():
    p1 = MagicMock()
    p1.fetch.return_value = None
    p2 = MagicMock()
    p2.fetch.return_value = None
    composite = CompositeFinancialProvider([p1, p2])
    assert composite.fetch("INVALID") is None

"""Composite provider — first source wins per field, then merge fallback fields."""
from __future__ import annotations

from dataclasses import fields
from typing import Optional

from tradingview_mcp.core.services.fundamentals.providers.base import (
    FinancialProvider,
    TickerFinancials,
)


def _is_empty(value) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, str)) and not value:
        return True
    if isinstance(value, (int, float)) and value == 0:
        return True
    return False


class CompositeFinancialProvider(FinancialProvider):
    name = "composite"

    def __init__(self, providers: list[FinancialProvider]):
        self.providers = providers

    def fetch(self, ticker: str) -> Optional[TickerFinancials]:
        merged: Optional[TickerFinancials] = None
        for provider in self.providers:
            partial = provider.fetch(ticker)
            if partial is None:
                continue
            if merged is None:
                merged = partial
                continue
            # fill empty fields in merged from partial (first source wins per field)
            for f in fields(TickerFinancials):
                if f.name in ("source_chain", "fetch_errors"):
                    continue
                if _is_empty(getattr(merged, f.name)) and not _is_empty(
                    getattr(partial, f.name)
                ):
                    setattr(merged, f.name, getattr(partial, f.name))
            merged.source_chain.extend(partial.source_chain)
            merged.fetch_errors.extend(partial.fetch_errors)
        return merged

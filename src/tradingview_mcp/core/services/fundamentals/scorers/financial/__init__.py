"""Financial-sector scorer subpackage (Phase 4).

Exports bank_scorer, insurance_scorer, reit_scorer — each with a
score(fin: TickerFinancials) -> FundamentalReport interface identical to the
composite.score_quality path so downstream consumers don't change.
"""
from . import bank_scorer, insurance_scorer, reit_scorer

__all__ = ["bank_scorer", "insurance_scorer", "reit_scorer"]

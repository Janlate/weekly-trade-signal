"""Pydantic models for the 8-layer fundamental scorer."""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class ConvictionTier(str, Enum):
    HIGH = "HIGH"
    MED = "MED"
    SPEC = "SPEC"
    LOW = "LOW"


class LayerScore(BaseModel):
    layer_id: int = Field(..., ge=1, le=8)
    name: str
    score: float = Field(..., ge=0, le=10)
    # "N/A" applies to layers 7-8 (valuation + sizing) which don't gate on PASS/FAIL
    verdict: Literal["PASS", "CAUTION", "FAIL", "INSUFFICIENT_DATA", "N/A"]
    rationale: str
    inputs: dict
    data_completeness: float = Field(..., ge=0, le=1)


class FundamentalReport(BaseModel):
    ticker: str
    scan_date: str  # YYYY-MM-DD
    industry: str
    is_cyclical: bool
    composite_score: float = Field(..., ge=0, le=10)
    quality_verdict: Literal["QUALITY_PASS", "QUALITY_WATCH", "QUALITY_REJECT"]
    layers: dict[str, LayerScore]
    raw_inputs_ref: str


class EntrySignal(BaseModel):
    ticker: str
    price: float
    quality_composite: float
    layer_7: dict
    layer_8: dict
    verdict: Literal["GO", "WAIT", "TRIM", "SKIP"]
    confidence: ConvictionTier

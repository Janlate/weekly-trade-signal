"""GICS sector -> WACC / growth tier / margin medians (Phase 1 hardcoded)."""
from __future__ import annotations

WACC_DEFAULTS: dict[str, float] = {
    "10": 0.09,   # Energy
    "15": 0.09,   # Materials
    "20": 0.08,   # Industrials
    "25": 0.09,   # Consumer Discretionary
    "30": 0.07,   # Consumer Staples
    "35": 0.08,   # Healthcare
    "40": 0.09,   # Financials (banks: ROE-based -- Phase 3)
    "45": 0.09,   # Information Technology
    "50": 0.09,   # Communication Services
    "55": 0.06,   # Utilities
    "60": 0.08,   # Real Estate
}

INDUSTRY_GROWTH_TIERS: dict[str, str] = {
    "10": "cyclical",  # Energy — evaluated by trough-recovery, not CAGR
    "15": "cyclical",  # Materials — same; also cyclical sector per CYCLICAL_SECTORS
    "20": "mid",       # Industrials
    "25": "mid",       # Consumer Discretionary (mature: Retail, Auto Dealers)
    "30": "slow",      # Staples
    "35": "mid",       # Healthcare
    "40": "mid",       # Financials
    "45": "fast",      # IT (growth tech/semis)
    "50": "mid",       # Communication Services — mature platforms (GOOGL, META) grow 8-15%
    "55": "slow",      # Utilities
    "60": "mid",       # REIT
}

GROWTH_BANDS: dict[str, tuple[float, float]] = {
    "slow":     (0.03, 0.08),
    "mid":      (0.08, 0.15),
    "fast":     (0.15, 0.30),
    "hyper":    (0.30, 1.00),
    # "cyclical" has no band — Layer 1 uses trough-recovery logic instead
    "cyclical": (0.00, 1.00),  # sentinel only; not used for base scoring
}

INDUSTRY_MARGIN_MEDIANS: dict[str, dict[str, float]] = {
    "10": {"gross": 0.30, "operating": 0.12},
    "15": {"gross": 0.25, "operating": 0.10},
    "20": {"gross": 0.30, "operating": 0.12},
    "25": {"gross": 0.35, "operating": 0.10},
    "30": {"gross": 0.35, "operating": 0.15},
    "35": {"gross": 0.55, "operating": 0.20},
    "40": {"gross": 0.40, "operating": 0.25},
    "45": {"gross": 0.50, "operating": 0.20},  # default IT
    "50": {"gross": 0.55, "operating": 0.20},
    "55": {"gross": 0.40, "operating": 0.20},
    "60": {"gross": 0.55, "operating": 0.30},
}

SUB_INDUSTRY_MARGIN_OVERRIDES: dict[tuple[str, str], dict[str, float]] = {
    ("45", "Software"):        {"gross": 0.70, "operating": 0.25},
    ("45", "Semiconductors"):  {"gross": 0.45, "operating": 0.20},
    ("45", "Hardware"):        {"gross": 0.40, "operating": 0.15},
}

CYCLICAL_SECTORS: set[str] = {"10", "15"}
CYCLICAL_SUB_INDUSTRIES: set[tuple[str, str]] = {
    ("20", "Airlines"), ("20", "Shipping"), ("20", "Construction Machinery"),
    ("25", "Auto"), ("25", "Homebuilders"),
    ("45", "Memory Semis"),
}


# ─── Financial-sector routing (Phase 4) ──────────────────────────────────────

FINANCIAL_INDUSTRIES: dict[str, list[str]] = {
    "bank": [
        "Banks—Diversified", "Banks—Regional", "Capital Markets",
        "Financial—Credit Services", "Financial Conglomerates",
    ],
    "insurance": [
        "Insurance—Life", "Insurance—Property & Casualty",
        "Insurance—Diversified", "Insurance—Reinsurance",
    ],
    "reit": [
        "REIT—Office", "REIT—Industrial", "REIT—Retail", "REIT—Residential",
        "REIT—Healthcare", "REIT—Diversified", "REIT—Hotel & Motel",
        "REIT—Specialty", "REIT—Mortgage",
        "Real Estate—Diversified", "Real Estate—Services",
    ],
}


def _normalize_industry(s: str) -> str:
    """Normalise industry string for comparison.

    yfinance returns 'Banks - Diversified' (space-dash-space); our spec uses
    'Banks—Diversified' (em-dash). Collapse both to 'banks diversified' for
    substring matching.
    """
    return s.lower().replace("—", " ").replace(" - ", " ").replace("-", " ")


def financial_scorer_for(industry: str) -> str | None:
    """Return 'bank' | 'insurance' | 'reit' | None.

    Visa/Mastercard edge case: sector='Financial Services' but industry=
    'Credit Services' -> returns None (routes to GenericScorer).
    The FINANCIAL_INDUSTRIES list deliberately excludes 'Credit Services'
    (un-prefixed) so that V/MA fall through to None.
    """
    if not industry:
        return None
    low = _normalize_industry(industry)
    for kind, names in FINANCIAL_INDUSTRIES.items():
        if any(_normalize_industry(n) in low for n in names):
            return kind
    return None


def get_wacc(gics_sector: str) -> float:
    return WACC_DEFAULTS.get(gics_sector, 0.085)


def gics_to_tier(gics_sector: str) -> str:
    return INDUSTRY_GROWTH_TIERS.get(gics_sector, "mid")


def get_margin_median(gics_sector: str, sub_industry: str | None = None) -> dict[str, float]:
    if sub_industry:
        key = (gics_sector, sub_industry)
        if key in SUB_INDUSTRY_MARGIN_OVERRIDES:
            return SUB_INDUSTRY_MARGIN_OVERRIDES[key]
    return INDUSTRY_MARGIN_MEDIANS.get(gics_sector, {"gross": 0.40, "operating": 0.15})


def is_cyclical(gics_sector: str, sub_industry: str | None = None) -> bool:
    if gics_sector in CYCLICAL_SECTORS:
        return True
    if sub_industry and (gics_sector, sub_industry) in CYCLICAL_SUB_INDUSTRIES:
        return True
    return False

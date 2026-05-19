"""Math + numeric helpers for scorers (pure functions)."""
from __future__ import annotations

import math
import statistics
from typing import Optional, Sequence


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def safe_div(num: float, denom: float, default: Optional[float] = None) -> Optional[float]:
    if denom == 0 or denom is None:
        return default
    return num / denom


def cagr(start: float, end: float, periods: int) -> float:
    """Compound annual growth rate. Returns NaN if start <= 0 or periods <= 0."""
    if start <= 0 or periods <= 0:
        return float("nan")
    return (end / start) ** (1 / periods) - 1


def linear_slope(series: Sequence[float]) -> float:
    """Slope of best-fit line y = mx + b through points (i, series[i])."""
    n = len(series)
    if n < 2:
        return 0.0
    xs = list(range(n))
    x_mean = sum(xs) / n
    y_mean = sum(series) / n
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, series))
    den = sum((x - x_mean) ** 2 for x in xs)
    return 0.0 if den == 0 else num / den


def coefficient_of_variation(series: Sequence[float]) -> float:
    """std / mean using population stdev. Returns 0 for constant series; NaN if mean is 0."""
    if len(series) < 2:
        return 0.0
    mean = sum(series) / len(series)
    if mean == 0:
        return float("nan")
    std = statistics.pstdev(series)
    return std / abs(mean)


def percentile_rank(value: float, distribution: Sequence[float]) -> float:
    """Fraction of distribution <= value (0..1). Returns 0.5 for empty distribution."""
    if not distribution:
        return 0.5
    leq = sum(1 for x in distribution if x <= value)
    return leq / len(distribution)


def cyclical_trough_recovery_score(
    rev_series: Sequence[float],
) -> tuple[float, str, dict]:
    """Score cyclical revenue by peak-trough-recovery heuristic (0-6).

    Logic (per framework.md §1 cyclical):
    - Does NOT penalise for low CAGR.
    - Rewards: latest revenue >= prior peak × 0.95 (recovered).
    - Rewards: minimum in second half > minimum in first half (rising base).
    - Penalises: latest year still below 70% of series peak (deep trough).

    Returns (score 0-6, rationale_fragment, extra_inputs_dict).
    Minimum 4 data points required; caller must enforce hard-min before calling.
    """
    s = list(rev_series)
    n = len(s)
    if n < 4:
        return 0.0, "insufficient data for trough-recovery", {"trough_recovery": None}

    peak_all = max(s)
    latest = s[-1]
    recovery_ratio = latest / peak_all if peak_all > 0 else 0.0

    # Split series into two halves to detect rising base
    mid = n // 2
    first_half_min = min(s[:mid]) if mid > 0 else s[0]
    second_half_min = min(s[mid:]) if (n - mid) > 0 else s[-1]
    rising_base = second_half_min > first_half_min

    # Score components
    if recovery_ratio >= 0.95:
        recovery_score = 4  # fully recovered to prior peak
    elif recovery_ratio >= 0.80:
        recovery_score = 3  # largely recovered
    elif recovery_ratio >= 0.65:
        recovery_score = 2  # partial recovery
    else:
        recovery_score = 0  # still deep in trough

    base_bonus = 2 if rising_base else 0  # rising trough-floor = structural improvement

    raw = recovery_score + base_bonus
    score = clamp(raw, 0, 6)

    rationale_fragment = (
        f"recovery_ratio={recovery_ratio:.2f} (latest/peak); "
        f"rising_base={'yes' if rising_base else 'no'} "
        f"(trough1={first_half_min:.0f} vs trough2={second_half_min:.0f})"
    )
    extra = {
        "trough_recovery": recovery_ratio,
        "rising_base": rising_base,
        "peak_revenue": peak_all,
        "latest_revenue": latest,
    }
    return score, rationale_fragment, extra

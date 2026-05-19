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

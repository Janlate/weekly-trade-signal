import math
import pytest

from tradingview_mcp.core.services.fundamentals.scorers._utils import (
    clamp, cagr, linear_slope, percentile_rank, safe_div, coefficient_of_variation,
)


def test_clamp():
    assert clamp(5, 0, 10) == 5
    assert clamp(-1, 0, 10) == 0
    assert clamp(11, 0, 10) == 10


def test_cagr_5year_doubling():
    # 100 -> 200 over 4 periods (5 years)
    assert abs(cagr(100, 200, 4) - 0.1892) < 0.001


def test_cagr_decline():
    assert cagr(200, 100, 4) < 0


def test_cagr_zero_start_returns_nan():
    assert math.isnan(cagr(0, 100, 4))


def test_linear_slope():
    # series [1,2,3,4,5] -> slope = 1
    assert abs(linear_slope([1, 2, 3, 4, 5]) - 1.0) < 1e-6


def test_linear_slope_flat():
    assert linear_slope([5, 5, 5, 5, 5]) == 0.0


def test_percentile_rank():
    # value 7 in [1,3,5,7,9]: leq = 4 (1,3,5,7), n=5, 4/5 = 0.8
    assert percentile_rank(7, [1, 3, 5, 7, 9]) == 0.8


def test_safe_div():
    assert safe_div(10, 2) == 5
    assert safe_div(10, 0) is None
    assert safe_div(10, 0, default=0) == 0


def test_coefficient_of_variation():
    # std / mean for [1, 1, 1, 1, 1] is 0
    assert coefficient_of_variation([1, 1, 1, 1, 1]) == 0.0
    # for [1, 2, 3, 4, 5]: mean=3, pstdev~1.414, cv~0.471
    cv = coefficient_of_variation([1, 2, 3, 4, 5])
    assert abs(cv - 0.471) < 0.01

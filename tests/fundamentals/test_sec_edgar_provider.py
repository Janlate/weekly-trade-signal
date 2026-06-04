"""Tests for SEC EDGAR companyfacts provider."""
import responses as responses_lib

from tradingview_mcp.core.services.fundamentals.providers.sec_edgar_provider import (
    SecEdgarProvider,
    TICKER_TO_CIK_URL,
    COMPANYFACTS_URL,
    _annual_series,
)
from tradingview_mcp.core.services.fundamentals.scorers.layer_01_revenue import score_layer_1
from tradingview_mcp.core.services.fundamentals.providers.base import TickerFinancials


@responses_lib.activate
def test_sec_edgar_resolves_cik():
    responses_lib.add(
        responses_lib.GET, TICKER_TO_CIK_URL,
        json={"0": {"cik_str": 789019, "ticker": "MSFT", "title": "MICROSOFT CORP"}},
        status=200,
    )
    responses_lib.add(
        responses_lib.GET, COMPANYFACTS_URL.format(cik="0000789019"),
        json={"entityName": "MICROSOFT CORP", "facts": {"us-gaap": {}}},
        status=200,
    )
    provider = SecEdgarProvider(user_agent="test@example.com")
    cik = provider._resolve_cik("MSFT")
    assert cik == "0000789019"


@responses_lib.activate
def test_sec_edgar_fetch_revenue():
    cik = "0000789019"
    # CIK lookup must be mocked BEFORE fetch -- _load_cik_map() runs lazily on first call
    responses_lib.add(
        responses_lib.GET, TICKER_TO_CIK_URL,
        json={"0": {"cik_str": 789019, "ticker": "MSFT", "title": "MICROSOFT CORP"}},
        status=200,
    )
    facts = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {"USD": [
                        {"end": "2024-06-30", "val": 245000000000, "fy": 2024, "fp": "FY", "form": "10-K"},
                        {"end": "2023-06-30", "val": 211000000000, "fy": 2023, "fp": "FY", "form": "10-K"},
                        {"end": "2022-06-30", "val": 198000000000, "fy": 2022, "fp": "FY", "form": "10-K"},
                        {"end": "2021-06-30", "val": 168000000000, "fy": 2021, "fp": "FY", "form": "10-K"},
                        {"end": "2020-06-30", "val": 143000000000, "fy": 2020, "fp": "FY", "form": "10-K"},
                    ]}
                }
            }
        }
    }
    responses_lib.add(
        responses_lib.GET, COMPANYFACTS_URL.format(cik=cik),
        json=facts, status=200,
    )
    provider = SecEdgarProvider(user_agent="test@example.com")
    result = provider.fetch("MSFT")
    assert result is not None
    assert result.revenue_5y[-1] == 245000000000
    assert "sec_edgar" in result.source_chain


# ─── Cyclical lookback fix (n_years=10 default) ───────────────────────────────

def _make_edgar_units(values: list[float], start_fy: int = 2015) -> list[dict]:
    """Build a minimal EDGAR USD units list with FY 10-K entries."""
    entries = []
    for i, val in enumerate(values):
        fy = start_fy + i
        entries.append({
            "end": f"{fy}-12-31",
            "val": val,
            "fy": fy,
            "fp": "FY",
            "form": "10-K",
        })
    return entries


def test_annual_series_returns_up_to_10_years():
    """_annual_series default must now return up to 10 entries (was 5).

    Regression guard: raising n_years=5 → 10 should allow cyclicals to receive
    a full commodity cycle's worth of data.
    """
    values = list(range(100_000, 100_000 + 10_000 * 11, 10_000))  # 11 years
    units_dict = {"USD": _make_edgar_units(values, start_fy=2014)}
    result = _annual_series(units_dict)
    assert len(result) == 10, f"Expected 10 years, got {len(result)}"
    # Should be the newest 10 (indices 1..10 of 11 total)
    assert result[-1] == values[-1], "Newest year must be last"
    assert result[0] == values[1], "Oldest of 10 must be the 2nd entry"


def test_annual_series_returns_all_when_fewer_than_10():
    """When EDGAR has fewer than 10 FY filings, return all available."""
    values = [100, 110, 120, 125, 130]  # only 5 years
    units_dict = {"USD": _make_edgar_units(values)}
    result = _annual_series(units_dict)
    assert len(result) == 5


def test_cyclical_7y_completeness_reaches_1_with_10y_fetch():
    """End-to-end: when SEC EDGAR returns 7+ years for a cyclical ticker,
    data_completeness should be 1.0 (no permanent penalty).

    Before fix: n_years=5 → actual_years=5 → completeness=5/7≈0.71 forever.
    After fix:  n_years=10 → actual_years=7 → completeness=min(1.0, 7/7)=1.0.
    """
    # 7 years of energy-company revenue (sector 10 = Energy = cyclical)
    rev_7y = [50e9, 80e9, 40e9, 60e9, 75e9, 90e9, 85e9]  # trough at index 2
    f = TickerFinancials(ticker="XOM_SIM", industry="10", revenue_5y=rev_7y)
    result = score_layer_1(f)
    assert result.data_completeness == 1.0, (
        f"Cyclical with 7y data must reach completeness=1.0, got {result.data_completeness:.3f}. "
        "Fix: SEC EDGAR provider now fetches n_years=10 so cyclicals receive 7+ years."
    )


def test_non_cyclical_l1_score_unchanged_with_10y_vs_5y():
    """Regression guard: L1 non-cyclical score must be identical whether the
    provider returns 5y or 10y of data.

    This tests the scorer-level slicing fix: standard path uses only the last
    _PREFERRED_YEARS_STANDARD (5) years, so older data from a 10y EDGAR fetch
    does not alter the CAGR window or CV calculation.
    """
    # 10y series where early years have different growth than recent 5y
    # (chosen so 10y CAGR ≠ 5y CAGR — would flip verdict if not sliced)
    rev10 = [100, 102, 104, 106, 108, 115, 135, 165, 200, 250]  # back-loaded
    rev5  = rev10[-5:]  # last 5 only

    f10 = TickerFinancials(ticker="MSFT_SIM", industry="45", revenue_5y=rev10)
    f5  = TickerFinancials(ticker="MSFT_SIM", industry="45", revenue_5y=rev5)

    s10 = score_layer_1(f10)
    s5  = score_layer_1(f5)

    assert s10.score   == s5.score,   f"Score must not change: 10y={s10.score} vs 5y={s5.score}"
    assert s10.verdict == s5.verdict, f"Verdict must not change: 10y={s10.verdict} vs 5y={s5.verdict}"
    assert abs(s10.inputs["cagr"] - s5.inputs["cagr"]) < 1e-9, (
        f"CAGR must not change: 10y={s10.inputs['cagr']:.6f} vs 5y={s5.inputs['cagr']:.6f}"
    )


@responses_lib.activate
def test_sec_edgar_fetch_returns_up_to_10y_via_provider():
    """Integration: SecEdgarProvider.fetch() should now return 10 years of revenue
    when EDGAR has 10 filings (previously capped at 5).
    """
    cik = "0000320193"  # AAPL CIK (just a placeholder for mock)
    responses_lib.add(
        responses_lib.GET, TICKER_TO_CIK_URL,
        json={"0": {"cik_str": 320193, "ticker": "AAPL", "title": "APPLE INC"}},
        status=200,
    )
    # 10 years of revenue
    revenue_10y = [
        {"end": f"{2015 + i}-09-30", "val": (200 + i * 15) * 1e9,
         "fy": 2015 + i, "fp": "FY", "form": "10-K"}
        for i in range(10)
    ]
    facts = {
        "facts": {
            "us-gaap": {
                "Revenues": {"units": {"USD": revenue_10y}}
            }
        }
    }
    responses_lib.add(
        responses_lib.GET, COMPANYFACTS_URL.format(cik="0000320193"),
        json=facts, status=200,
    )
    provider = SecEdgarProvider(user_agent="test@example.com")
    result = provider.fetch("AAPL")
    assert result is not None
    assert len(result.revenue_5y) == 10, (
        f"Expected 10 years from provider, got {len(result.revenue_5y)}. "
        "SecEdgarProvider must now pass n_years=10 to _annual_series."
    )

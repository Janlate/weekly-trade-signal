"""Tests for SEC EDGAR companyfacts provider."""
import responses as responses_lib

from tradingview_mcp.core.services.fundamentals.providers.sec_edgar_provider import (
    SecEdgarProvider,
    TICKER_TO_CIK_URL,
    COMPANYFACTS_URL,
)


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

"""Tests for financial_scorer_for() routing logic (Phase 4)."""
import pytest

from tradingview_mcp.core.services.fundamentals.industry_config import financial_scorer_for


# ── Routing: bank ──────────────────────────────────────────────────────────

def test_routes_bank_regional():
    assert financial_scorer_for("Banks—Regional") == "bank"


def test_routes_bank_diversified():
    assert financial_scorer_for("Banks—Diversified") == "bank"


def test_routes_capital_markets():
    assert financial_scorer_for("Capital Markets") == "bank"


# ── Routing: insurance ─────────────────────────────────────────────────────

def test_routes_insurance_pc():
    assert financial_scorer_for("Insurance—Property & Casualty") == "insurance"


def test_routes_insurance_life():
    assert financial_scorer_for("Insurance—Life") == "insurance"


def test_routes_insurance_reinsurance():
    assert financial_scorer_for("Insurance—Reinsurance") == "insurance"


# ── Routing: REIT ──────────────────────────────────────────────────────────

def test_routes_reit_industrial():
    assert financial_scorer_for("REIT—Industrial") == "reit"


def test_routes_reit_retail():
    assert financial_scorer_for("REIT—Retail") == "reit"


def test_routes_reit_office():
    assert financial_scorer_for("REIT—Office") == "reit"


# ── Edge cases ─────────────────────────────────────────────────────────────

def test_visa_mastercard_credit_services_returns_none():
    """V and MA have sector=Financial Services but industry=Credit Services.
    They should NOT route to bank scorer — return None for generic.
    """
    assert financial_scorer_for("Credit Services") is None


def test_technology_returns_none():
    assert financial_scorer_for("Software—Application") is None


def test_empty_string_returns_none():
    assert financial_scorer_for("") is None


def test_none_input_returns_none():
    # Should not raise, just return None
    assert financial_scorer_for(None) is None  # type: ignore[arg-type]

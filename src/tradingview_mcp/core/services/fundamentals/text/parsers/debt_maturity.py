from typing import Dict, Any, List

def parse_debt_maturity(facts: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze XBRL company facts to determine debt maturity risk (Q13).
    
    Q13 Rule (Maturity wall in next 1-2 years):
      - Pass: < 15% of total debt due in years 1-2.
      - Warn: 15-30% due in years 1-2.
      - Fail: > 30% due in years 1-2.
    """
    if not facts:
        return {
            "verdict": "na",
            "evidence": "Company facts data not available.",
            "confidence": 0.0
        }

    def _get_latest_fy_value(tag_name: str) -> float:
        tag_data = facts.get(tag_name, {})
        units = tag_data.get("units", {}).get("USD", [])
        if not units:
            return 0.0
        
        # Prefer 10-K FY entries, but fallback to anything if missing
        fy_entries = [u for u in units if u.get("fp") == "FY" and u.get("form") in ("10-K", "10-K/A")]
        if fy_entries:
            latest = sorted(fy_entries, key=lambda x: x["end"])[-1]
            return float(latest.get("val", 0.0))
        
        # Fallback
        latest = sorted(units, key=lambda x: x.get("end", ""))[-1]
        return float(latest.get("val", 0.0))

    # Pull the maturity schedule
    yr1 = _get_latest_fy_value("LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths")
    if yr1 == 0.0:
        yr1 = _get_latest_fy_value("LongTermDebtMaturitiesRepaymentsOfPrincipalInYearOne")
    
    yr2 = _get_latest_fy_value("LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo")
    yr3 = _get_latest_fy_value("LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree")
    yr4 = _get_latest_fy_value("LongTermDebtMaturitiesRepaymentsOfPrincipalInYearFour")
    yr5 = _get_latest_fy_value("LongTermDebtMaturitiesRepaymentsOfPrincipalInYearFive")
    yr5_plus = _get_latest_fy_value("LongTermDebtMaturitiesRepaymentsOfPrincipalAfterYearFive")

    schedule_total = yr1 + yr2 + yr3 + yr4 + yr5 + yr5_plus
    
    # Get total long term debt
    total_ltd = _get_latest_fy_value("LongTermDebt")
    if total_ltd == 0.0:
        total_ltd = _get_latest_fy_value("LongTermDebtNoncurrent")

    # Use the larger of schedule_total or total_ltd to represent total debt base
    total_base = max(schedule_total, total_ltd)
    
    if total_base == 0.0:
        return {
            "verdict": "na",
            "evidence": "No long-term debt or maturity schedule reported in XBRL facts.",
            "confidence": 0.5
        }

    due_1_2_years = yr1 + yr2
    due_pct = (due_1_2_years / total_base) * 100.0

    # Build evidence quote
    evidence = (
        f"Schedule: Y1=${yr1/1e6:.1f}M, Y2=${yr2/1e6:.1f}M, Y3=${yr3/1e6:.1f}M, "
        f"Y4=${yr4/1e6:.1f}M, Y5+=${(yr5 + yr5_plus)/1e6:.1f}M. "
        f"Total Base: ${total_base/1e6:.1f}M. Due in 1-2 years: {due_pct:.1f}%."
    )

    if schedule_total == 0.0:
        return {
            "verdict": "na",
            "evidence": f"No specific maturity schedule found. Total Long-Term Debt: ${total_ltd/1e6:.1f}M.",
            "confidence": 0.2
        }

    verdict = "pass"
    if due_pct > 30.0:
        verdict = "fail"
    elif due_pct >= 15.0:
        verdict = "warn"

    return {
        "verdict": verdict,
        "evidence": evidence,
        "confidence": 0.95
    }

import re
from typing import Dict, Any

def parse_revenue_quality(item1_text: str) -> Dict[str, Any]:
    """Analyze Item 1 (Business) to determine revenue quality and customer concentration (Q4).
    
    Q4 Rule:
      - Pass: Top customer < 10% and recurring revenue > 50%.
      - Warn: Top customer 10-25% or recurring revenue 25-50%.
      - Fail: Top customer > 25% or recurring revenue < 25%.
    """
    if not item1_text:
        return {
            "verdict": "na",
            "evidence": "Item 1 (Business) section was empty or not found.",
            "confidence": 0.0
        }

    sentences = re.split(r'\. (?=[A-Z])|\n', item1_text)
    
    # 1. Look for Customer Concentration
    concentration_sentences = []
    max_customer_pct = 0.0
    no_customer_over_10 = False
    
    # Patterns for customer concentration
    conc_re_1 = re.compile(r'\b(?:customer|client)s?\b.*?\b(\d{1,2}(?:\.\d+)?)\s*%\s+(?:of\s+)?(?:our\s+)?(?:consolidated\s+)?(?:revenue|sales|net\s+sales|revenues)\b', re.IGNORECASE)
    conc_re_2 = re.compile(r'\b(\d{1,2}(?:\.\d+)?)\s*%\s+(?:of\s+)?(?:our\s+)?(?:consolidated\s+)?(?:revenue|sales|net\s+sales|revenues)\b.*?\b(?:customer|client)s?\b', re.IGNORECASE)
    no_conc_re = re.compile(r'\bno\s+(?:single\s+)?(?:customer|client)s?\b.*?\b(?:more\s+than|exceeded|represented|accounted\s+for|greater\s+than)\s+(\d{1,2}(?:\.\d+)?)\s*%\b', re.IGNORECASE)
    no_sig_conc_re = re.compile(r'\bno\s+(?:single\s+)?(?:customer|client)s?\b.*?\b(?:accounted\s+for|represented)\s+(?:a\s+significant|more\s+than|exceeded)\b', re.IGNORECASE)

    for s in sentences:
        s_clean = s.strip()
        if not s_clean:
            continue
        
        # Check no customer > X%
        m = no_conc_re.search(s_clean)
        if m:
            val = float(m.group(1))
            concentration_sentences.append(s_clean)
            if val <= 10.0:
                no_customer_over_10 = True
            if max_customer_pct == 0.0 or val < max_customer_pct:
                max_customer_pct = val
            continue
            
        m = no_sig_conc_re.search(s_clean)
        if m:
            concentration_sentences.append(s_clean)
            no_customer_over_10 = True
            continue

        # Check explicit concentration percent
        m = conc_re_1.search(s_clean) or conc_re_2.search(s_clean)
        if m:
            val = float(m.group(1))
            concentration_sentences.append(s_clean)
            if val > max_customer_pct:
                max_customer_pct = val

    # 2. Look for Recurring Revenue Indications
    recurring_sentences = []
    recurring_pct = -1.0
    
    rec_re_1 = re.compile(r'\b(?:subscription|recurring|saas|arr|annual\s+recurring|membership|memberships)\b.*?\b(\d{1,2}(?:\.\d+)?)\s*%\s+(?:of\s+)?(?:our\s+)?(?:consolidated\s+)?(?:revenue|sales|net\s+sales|revenues)\b', re.IGNORECASE)
    rec_re_2 = re.compile(r'\b(\d{1,2}(?:\.\d+)?)\s*%\s+(?:of\s+)?(?:our\s+)?(?:consolidated\s+)?(?:revenue|sales|net\s+sales|revenues)\b.*?\b(?:subscription|recurring|saas|arr|annual\s+recurring|membership|memberships)\b', re.IGNORECASE)
    
    # Generic recurring keywords to count density
    recurring_keywords = re.compile(r'\b(subscription|subscriptions|recurring|saas|arr|annual\s+recurring|membership|memberships|contract|contracts|multi-year|long-term\s+agreement|maintenance\s+agreement)\b', re.IGNORECASE)
    rec_kw_count = 0

    for s in sentences:
        s_clean = s.strip()
        if not s_clean:
            continue
            
        m = rec_re_1.search(s_clean) or rec_re_2.search(s_clean)
        if m:
            val = float(m.group(1))
            recurring_sentences.append(s_clean)
            if val > recurring_pct:
                recurring_pct = val
        
        matches = recurring_keywords.findall(s_clean)
        if matches:
            rec_kw_count += len(matches)
            if "subscription" in s_clean.lower() or "recurring" in s_clean.lower():
                if len(recurring_sentences) < 3 and s_clean not in recurring_sentences:
                    recurring_sentences.append(s_clean)

    # Heuristic mapping for recurring revenue if not explicitly stated as a percentage:
    # Highly subscription/recurring businesses will have a high density of keywords in Item 1.
    if recurring_pct == -1.0:
        if rec_kw_count > 15:
            recurring_pct = 75.0  # Proxy for SaaS / membership model
        elif rec_kw_count > 5:
            recurring_pct = 40.0  # Proxy for semi-recurring model
        else:
            recurring_pct = 10.0  # Proxy for transactional hardware/products

    # Compile evidence
    ev_parts = []
    if concentration_sentences:
        ev_parts.append("Concentration: " + ". ".join(concentration_sentences[:2]))
    else:
        if no_customer_over_10:
            ev_parts.append("No single customer is material (>10% of sales).")
        else:
            ev_parts.append("No explicit customer concentration figures found.")
            
    if recurring_sentences:
        ev_parts.append("Recurring: " + ". ".join(recurring_sentences[:2]))
    else:
        ev_parts.append(f"Recurring keywords count: {rec_kw_count}.")

    evidence = " | ".join(ev_parts)
    if len(evidence) > 400:
        evidence = evidence[:400] + "..."

    # Determine Verdict
    # Top customer:
    # - Safe: < 10% (or no_customer_over_10)
    # - Warning: 10-25%
    # - Fail: > 25%
    # Recurring:
    # - Safe: > 50%
    # - Warning: 25-50%
    # - Fail: < 25%
    
    conc_verdict = "pass"
    if max_customer_pct > 25.0:
        conc_verdict = "fail"
    elif max_customer_pct > 10.0 or (max_customer_pct == 0.0 and not no_customer_over_10):
        # If no customer info is found, default to warn for customer risk
        conc_verdict = "warn"
        
    rec_verdict = "pass"
    if recurring_pct < 25.0:
        rec_verdict = "fail"
    elif recurring_pct < 50.0:
        rec_verdict = "warn"

    # Combine verdicts (most severe wins)
    verdict_priority = {"fail": 3, "warn": 2, "pass": 1}
    combined_priority = max(verdict_priority[conc_verdict], verdict_priority[rec_verdict])
    
    final_verdict = "pass"
    if combined_priority == 3:
        final_verdict = "fail"
    elif combined_priority == 2:
        final_verdict = "warn"

    confidence = 0.8 if (max_customer_pct > 0.0 or no_customer_over_10) and recurring_pct != -1.0 else 0.5

    return {
        "verdict": final_verdict,
        "evidence": evidence,
        "confidence": confidence
    }

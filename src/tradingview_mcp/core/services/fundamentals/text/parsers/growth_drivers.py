import re
from typing import Dict, Any

def parse_growth_drivers(item7_text: str) -> Dict[str, Any]:
    """Analyze Item 7 (MD&A) to determine growth quality (Q3).
    
    Q3 Rule:
      - Pass: Volume-driven (growth in units, subscribers, or organic).
      - Warn: Price-driven (growth purely due to pricing power or FX).
      - Fail: M&A-driven (growth via acquisitions/mergers > 40% or primary driver).
    """
    if not item7_text:
        return {
            "verdict": "na",
            "evidence": "Item 7 (MD&A) section was empty or not found.",
            "confidence": 0.0
        }

    # Split into sentences
    sentences = re.split(r'\. (?=[A-Z])|\n', item7_text)
    
    growth_sentences = []
    for s in sentences:
        s_clean = s.strip()
        if not s_clean:
            continue
        
        # Look for sentences discussing revenue/sales changes
        has_rev = re.search(r'\b(revenue|sales|net sales)\b', s_clean, re.I)
        has_growth = re.search(r'\b(increase|grew|grow|growth|rose|rise|change|driven|attributable|due to|result of)\b', s_clean, re.I)
        
        if has_rev and has_growth:
            # Check for driver keywords
            has_drivers = re.search(r'\b(volume|price|pricing|asp|average selling price|organic|acquisition|acquisitions|acquired|merger|fx|foreign currency|constant currency)\b', s_clean, re.I)
            if has_drivers:
                growth_sentences.append(s_clean)

    if not growth_sentences:
        return {
            "verdict": "na",
            "evidence": "No clear revenue growth attribution sentences found in Item 7.",
            "confidence": 0.1
        }

    # Score candidates
    vol_score = 0
    price_score = 0
    ma_score = 0
    fx_score = 0
    
    evidence_quotes = []
    
    # Analyze the found growth sentences (limit to top 4 for evidence)
    for s in growth_sentences[:4]:
        evidence_quotes.append(s)
        
        # Word counts in this sentence
        v_matches = len(re.findall(r'\b(volume|volumes|unit|units|subscriber|subscribers|membership|memberships|shipment|shipments|organic|quantity|quantities)\b', s, re.I))
        p_matches = len(re.findall(r'\b(price|prices|pricing|asp|average selling price|tariff|tariffs)\b', s, re.I))
        m_matches = len(re.findall(r'\b(acquisition|acquisitions|acquired|merger|mergers|business combination|business combinations)\b', s, re.I))
        f_matches = len(re.findall(r'\b(fx|foreign currency|exchange rate|exchange rates|constant currency|currency translation)\b', s, re.I))
        
        # Direct phrases boost
        if re.search(r'driven primarily by.*(volume|organic|unit|subscriber|membership)', s, re.I):
            v_matches += 3
        if re.search(r'driven primarily by.*(price|pricing|asp)', s, re.I):
            p_matches += 3
        if re.search(r'driven primarily by.*(acquisition|acquired|merger)', s, re.I):
            m_matches += 3
            
        vol_score += v_matches
        price_score += p_matches
        ma_score += m_matches
        fx_score += f_matches

    evidence = ". ".join(evidence_quotes) + "."
    if len(evidence) > 400:
        evidence = evidence[:400] + "..."

    # Determine verdict based on scores
    if ma_score > vol_score and ma_score > price_score:
        return {
            "verdict": "fail",
            "evidence": f"Growth appears driven primarily by acquisitions. Quotes: {evidence}",
            "confidence": min(0.9, 0.5 + 0.1 * ma_score)
        }
    elif price_score > vol_score:
        return {
            "verdict": "warn",
            "evidence": f"Growth appears driven primarily by price hikes rather than volume. Quotes: {evidence}",
            "confidence": min(0.9, 0.5 + 0.1 * price_score)
        }
    elif vol_score > 0:
        return {
            "verdict": "pass",
            "evidence": f"Growth is organic and volume-driven (unit/subscriber/organic increases). Quotes: {evidence}",
            "confidence": min(0.95, 0.5 + 0.1 * vol_score)
        }
    else:
        # Fallback to na if no drivers could be confidently ranked
        return {
            "verdict": "na",
            "evidence": f"Found growth statements, but could not distinguish the primary driver. Quotes: {evidence}",
            "confidence": 0.3
        }

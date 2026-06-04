import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import yfinance as yf

# stock-reports/data/peers directory path relative to this file
PEERS_DIR = Path(__file__).resolve().parents[8] / "stock-reports" / "data" / "peers"

def _get_peer_metrics(ticker: str) -> Optional[Dict[str, float]]:
    try:
        info = yf.Ticker(ticker).info
        return {
            "trailingPE": info.get("trailingPE"),
            "forwardPE": info.get("forwardPE"),
            "enterpriseToSales": info.get("enterpriseToSales"),
        }
    except Exception:
        return None

def parse_peer_percentile(target_ticker: str, target_gics: str, target_metrics: Dict[str, float]) -> Dict[str, Any]:
    """Analyze peer valuation relative to sector/GICS code (Q18).
    
    Q18 Rule:
      - Pass: Valuation (P/E, EV/Sales) is in the bottom 30% of peers (cheap).
      - Warn: Valuation is in the middle 30-70% of peers.
      - Fail: Valuation is in the top 30% of peers (expensive).
    """
    if not target_gics:
        return {
            "verdict": "na",
            "evidence": "No GICS code or industry mapping provided to identify peers.",
            "confidence": 0.0
        }

    # Normalize GICS or industry string to a filename
    safe_gics = "".join([c if c.isalnum() else "_" for c in target_gics]).lower()
    peer_file = PEERS_DIR / f"{safe_gics}.json"
    
    if not peer_file.exists():
        return {
            "verdict": "na",
            "evidence": f"No static peer list found for {target_gics}.",
            "confidence": 0.1
        }
        
    try:
        peers: List[str] = json.loads(peer_file.read_text())
    except json.JSONDecodeError:
        return {
            "verdict": "na",
            "evidence": "Peer file is corrupted.",
            "confidence": 0.0
        }

    # Make sure we don't compare against ourselves
    peers = [p for p in peers if p.upper() != target_ticker.upper()]
    if not peers:
        return {
            "verdict": "na",
            "evidence": "Not enough peers found in the peer list.",
            "confidence": 0.2
        }

    # Gather peer data
    peer_data = {}
    for p in peers:
        metrics = _get_peer_metrics(p)
        if metrics:
            peer_data[p] = metrics

    if not peer_data:
        return {
            "verdict": "na",
            "evidence": "Could not fetch valuation metrics for any peers.",
            "confidence": 0.3
        }

    # We evaluate Forward P/E as primary, then Trailing P/E, then EV/Sales
    eval_metric = "forwardPE"
    target_val = target_metrics.get(eval_metric)
    
    if not target_val or target_val <= 0:
        eval_metric = "trailingPE"
        target_val = target_metrics.get(eval_metric)
        
    if not target_val or target_val <= 0:
        eval_metric = "enterpriseToSales"
        target_val = target_metrics.get(eval_metric)

    if not target_val or target_val <= 0:
        return {
            "verdict": "na",
            "evidence": "Target has no valid P/E or EV/Sales to compare against peers.",
            "confidence": 0.5
        }

    # Extract valid peer values for the chosen metric
    peer_vals = []
    for p, metrics in peer_data.items():
        val = metrics.get(eval_metric)
        if val and val > 0:
            peer_vals.append(val)

    if len(peer_vals) < 2:
        return {
            "verdict": "na",
            "evidence": f"Not enough peer data for metric {eval_metric}.",
            "confidence": 0.3
        }

    # Calculate rank/percentile
    peer_vals.sort()
    
    # Simple percentile: count how many peers are cheaper (lower metric)
    cheaper_count = sum(1 for v in peer_vals if v < target_val)
    total = len(peer_vals)
    percentile = (cheaper_count / total) * 100.0

    evidence = f"Metric: {eval_metric}. Target: {target_val:.1f}. "
    evidence += f"Peers range: [{peer_vals[0]:.1f} - {peer_vals[-1]:.1f}] across {total} peers. "
    evidence += f"Target is more expensive than {percentile:.0f}% of peers."

    verdict = "pass"
    if percentile > 70.0:
        verdict = "fail"
    elif percentile >= 30.0:
        verdict = "warn"

    return {
        "verdict": verdict,
        "evidence": evidence,
        "confidence": 0.9
    }

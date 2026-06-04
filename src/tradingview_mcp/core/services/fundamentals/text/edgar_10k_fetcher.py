import os
import re
import time
import requests
from pathlib import Path
from bs4 import BeautifulSoup
from typing import Tuple, Optional, Dict

TICKER_TO_CIK_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accno_no_dash}/{doc}"

# SEC EDGAR requires a descriptive User-Agent
DEFAULT_USER_AGENT = "stock-stack/0.1 (research; contact@stock-stack.dev)"

def clean_html_to_text(html_content: str) -> str:
    """Strip HTML tags and return clean text, handling table cell padding and spacing."""
    soup = BeautifulSoup(html_content, "html.parser")
    for script in soup(["script", "style"]):
        script.decompose()
    # Add spacing to table cells to avoid merging text
    for td in soup.find_all("td"):
        td.insert_after(" ")
    text = soup.get_text(separator="\n")
    lines = []
    for line in text.splitlines():
        line = re.sub(r'\s+', ' ', line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)

def extract_sections(text: str) -> Tuple[str, str]:
    """Extract Item 1 (Business) and Item 7 (MD&A) sections from cleaned 10-K text."""
    # Whitespace-flexible regexes to handle layout splits (e.g. B\nUSINESS)
    item1_re = re.compile(r'\bITEM\s+1\b[.:\s\-]+B\s*U\s*S\s*I\s*N\s*E\s*S\s*S\b', re.IGNORECASE)
    item1a_re = re.compile(r'\bITEM\s+1A\b[.:\s\-]+R\s*I\s*S\s*K\s*F\s*A\s*C\s*T\s*O\s*R\s*S\b', re.IGNORECASE)
    item2_re = re.compile(r'\bITEM\s+2\b[.:\s\-]+P\s*R\s*O\s*P\s*E\s*R\s*T\s*I\s*E\s*S\b', re.IGNORECASE)
    
    item7_re = re.compile(r'\bITEM\s+7\b[.:\s\-]+M\s*A\s*N\s*A\s*G\s*E\s*M\s*E\s*N\s*T\s*S?\b[’\'s\s]*D\s*I\s*S\s*C\s*U\s*S\s*S\s*I\s*O\s*N\b', re.IGNORECASE)
    item7a_re = re.compile(r'\bITEM\s+7A\b[.:\s\-]+Q\s*U\s*A\s*N\s*T\s*I\s*T\s*A\s*T\s*I\s*V\s*E\b', re.IGNORECASE)
    item8_re = re.compile(r'\bITEM\s+8\b[.:\s\-]+F\s*I\s*N\s*A\s*N\s*C\s*I\s*A\s*L\s*S\s*T\s*A\s*T\s*E\s*M\s*E\s*N\s*T\s*S\b', re.IGNORECASE)

    item1_text = ""
    item1_matches = list(item1_re.finditer(text))
    for m in item1_matches:
        start_idx = m.start()
        next_m = None
        for end_re in [item1a_re, item2_re]:
            for em in end_re.finditer(text, pos=start_idx):
                if next_m is None or em.start() < next_m.start():
                    next_m = em
        if next_m:
            length = next_m.start() - start_idx
            # Avoid picking up table of contents entries
            if length > 5000:
                item1_text = text[start_idx:next_m.start()]
                break

    item7_text = ""
    item7_matches = list(item7_re.finditer(text))
    for m in item7_matches:
        start_idx = m.start()
        next_m = None
        for end_re in [item7a_re, item8_re]:
            for em in end_re.finditer(text, pos=start_idx):
                if next_m is None or em.start() < next_m.start():
                    next_m = em
        if next_m:
            length = next_m.start() - start_idx
            if length > 5000:
                item7_text = text[start_idx:next_m.start()]
                break

    return item1_text, item7_text

class Edgar10kFetcher:
    def __init__(self, cache_dir: Optional[Path] = None, user_agent: str = DEFAULT_USER_AGENT):
        self.headers = {
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip,deflate",
        }
        if cache_dir is None:
            self.cache_dir = Path.home() / ".cache" / "stock-stack" / "edgar-10k"
        else:
            self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cik_map: Optional[Dict[str, str]] = None

    def _get_cik_map(self) -> Dict[str, str]:
        """Lazy-load the SEC ticker -> CIK mapping."""
        if self._cik_map is None:
            r = requests.get(TICKER_TO_CIK_URL, headers=self.headers, timeout=15)
            r.raise_for_status()
            data = r.json()
            self._cik_map = {
                v["ticker"].upper(): f"{int(v['cik_str']):010d}"
                for v in data.values()
            }
        return self._cik_map

    def _resolve_cik(self, ticker: str) -> Optional[str]:
        try:
            return self._get_cik_map().get(ticker.upper())
        except Exception:
            return None

    def fetch_and_parse_10k(self, ticker: str) -> Tuple[str, str]:
        """Fetches the latest 10-K filing for the ticker, parses and returns (item1, item7)."""
        cik = self._resolve_cik(ticker)
        if not cik:
            return "", ""

        try:
            # Step 1: Fetch recent submissions metadata
            url = SUBMISSIONS_URL.format(cik=cik)
            r = requests.get(url, headers=self.headers, timeout=15)
            r.raise_for_status()
            recent = r.json().get("filings", {}).get("recent", {})
            
            # Step 2: Find the latest 10-K submission
            idx = -1
            for i, form in enumerate(recent.get("form", [])):
                if form == "10-K":
                    idx = i
                    break
            
            if idx == -1:
                return "", ""

            accno = recent["accessionNumber"][idx]
            doc = recent["primaryDocument"][idx]
            accno_no_dash = accno.replace("-", "")
            
            # Check local file cache
            ticker_cache_dir = self.cache_dir / ticker.upper()
            ticker_cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file = ticker_cache_dir / f"{accno_no_dash}.html"
            
            if cache_file.exists():
                html_content = cache_file.read_text(encoding="utf-8", errors="ignore")
            else:
                # Step 3: Fetch the 10-K HTML file from EDGAR archive
                archive_url = ARCHIVE_URL.format(
                    cik=str(int(cik)), accno_no_dash=accno_no_dash, doc=doc
                )
                # Respect SEC rate limits
                time.sleep(0.1)
                res = requests.get(archive_url, headers=self.headers, timeout=30)
                res.raise_for_status()
                html_content = res.text
                
                # Write to local cache
                cache_file.write_text(html_content, encoding="utf-8")
            
            # Step 4: Parse sections
            clean_text = clean_html_to_text(html_content)
            return extract_sections(clean_text)

        except Exception as e:
            # Return empty strings on failure, matching naAnswer behaviour in Astro UI
            return "", ""

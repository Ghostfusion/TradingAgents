"""SEC EDGAR filings vendor (free, no API key).

Fetches a company's most recent SEC filings from the official EDGAR submissions
API (``data.sec.gov``) and summarizes them by form type. This surfaces the
event-risk signals that news-only analysis misses: 8-K (material events: M&A,
guidance, restatements), 10-K/10-Q (annual/quarterly reports), and S-1/S-3
(capital raises / dilution).

EDGAR is public and keyless but requires a descriptive User-Agent (per SEC fair
access policy) and tolerates only ~10 req/s per IP. The ticker -> CIK lookup uses
the SEC's ``company_tickers.json`` (cached in-process). Every network failure
degrades via ``NoMarketDataError`` so the router surfaces "no data" rather than
crashing.
"""
from __future__ import annotations

import json
import logging
import urllib.request
from datetime import datetime

from .errors import NoMarketDataError
from .symbol_utils import normalize_symbol

logger = logging.getLogger(__name__)

# SEC fair-access: a descriptive User-Agent is required; generic tokens are
# throttled/blocked.
_UA = "tradingagents/0.3 (+https://github.com/TauricResearch/TradingAgents)"
_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
_TIMEOUT = 20

# Form types worth surfacing, with a short label for the report.
_FORM_LABELS = {
    "8-K": "8-K (material event / M&A / guidance)",
    "10-K": "10-K (annual report)",
    "10-Q": "10-Q (quarterly report)",
    "S-1": "S-1 (IPO / primary raise)",
    "S-3": "S-3 (shelf / secondary offering)",
    "SC 13D": "SC 13D (activist / 5%+ stake)",
    "SC 13G": "SC 13G (institutional 5%+ stake)",
    "DEF 14A": "DEF 14A (proxy / governance)",
}

_ticker_cik_cache: dict[str, str] | None = None


def _json_get(url: str):
    """GET a JSON document from SEC EDGAR with a descriptive User-Agent."""
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read())


def _ticker_map() -> dict[str, str]:
    """Load (lazily, cached) the SEC ticker -> CIK mapping."""
    global _ticker_cik_cache
    if _ticker_cik_cache is None:
        data = _json_get(_TICKERS_URL)
        _ticker_cik_cache = {
            str(row["ticker"]).upper(): str(row["cik_str"])
            for row in data.values()
        }
    return _ticker_cik_cache


def _cik_for(ticker: str) -> str | None:
    """Resolve a ticker to its CIK, handling exchange-suffixed symbols."""
    base = normalize_symbol(ticker).split(".")[0].upper()
    return _ticker_map().get(base)


def get_sec_filings(ticker: str, limit: int = 10) -> str:
    """Return a formatted summary of the most recent SEC filings for a ticker.

    Args:
        ticker: Ticker symbol (exchange suffixes like ``0700.HK`` are stripped
            for the CIK lookup; non-US tickers typically have no EDGAR record).
        limit: Max filings to summarize (default 10).

    Returns:
        A markdown report of recent filings by form type + date + accession.
    """
    cik = _cik_for(ticker)
    if cik is None:
        raise NoMarketDataError(
            ticker,
            detail="no CIK found on EDGAR (non-US listing, or ticker not registered)",
        )

    try:
        payload = _json_get(_SUBMISSIONS_URL.format(cik=int(cik)))
    except Exception as exc:  # noqa: BLE001
        logger.warning("EDGAR submissions fetch failed for %s (CIK %s): %s", ticker, cik, exc)
        raise NoMarketDataError(ticker, detail=f"EDGAR submissions fetch failed: {exc}") from exc

    recent = payload.get("filings", {}).get("recent", {})
    forms = recent.get("form", []) or []
    dates = recent.get("filingDate", []) or []
    accessions = recent.get("accessionNumber", []) or []
    primary_docs = recent.get("primaryDocument", []) or []

    if not forms:
        raise NoMarketDataError(ticker, detail="no recent EDGAR filings returned")

    shown = 0
    lines = [f"## {ticker.upper()} Recent SEC Filings (EDGAR)", ""]
    for i, form in enumerate(forms):
        if shown >= limit:
            break
        # Only surface forms we have a useful label for; skip the noisy 4/A,
        # EFFECT, S-8, etc. that carry little decision signal.
        if form not in _FORM_LABELS:
            continue
        date = dates[i] if i < len(dates) else "?"
        acc = accessions[i].replace("-", "") if i < len(accessions) else "?"
        doc = primary_docs[i] if i < len(primary_docs) else ""
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{doc}" if acc else ""
        lines.append(f"- **{form}** — {_FORM_LABELS[form]} · filed {date}")
        if url:
            lines.append(f"  {url}")
        shown += 1

    if shown == 0:
        # Recent window had only forms we filtered out — still useful to say so.
        top_forms = sorted(set(forms))[:8]
        lines.append(f"(Recent filings were all in filtered form types: {', '.join(top_forms)})")

    lines.append("")
    lines.append(
        "Interpretation: 8-K filings flag material events (M&A, guidance changes, "
        "restatements); S-1/S-3 filings flag capital raises/dilution; SC 13D/G "
        "flag activist or large institutional positions. Weight event filings "
        "(8-K, S-1) above routine periodic reports."
    )
    return "\n".join(lines)

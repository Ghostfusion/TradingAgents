"""News relevance scoring + admission (DSA research §3.5, pillar 8).

Port of daily_stock_analysis's deterministic news relevance + admission:

- ``score_news_article`` — ticker-in-title +55 / snippet +34 / url +18;
  company-name title +45 (ambiguous names +26); OFFICIAL-source boost +8
  (sec.gov, nasdaq.com, nyse.com + the CN official hosts the fork may later
  consume); macro-term penalty -12; clamp 0..100; <= 5 explainable reasons.
- ``admit_article`` — passes official sources outright; drops app-download /
  spam-like pages by content signal (not domain blacklists).
- ``degrade_triple`` — the honesty contract: all_failed vs empty vs
  unavailable; "no news" NEVER means "search failed".

Pure + hermetic; no network.
"""

from __future__ import annotations

import re

# Official financial sources that get a relevance boost (hosts the fork
# actually consumes; CNT official hosts retained for the future).
OFFICIAL_HOSTS = (
    "sec.gov", "nasdaq.com", "nyse.com", "cninfo.com.cn",
    "sse.com.cn", "szse.cn", "hkexnews.hk",
)

# Content signals that mark a spam/app-download page (content-based, not a
# blacklist — DSA admission rule).
_SPAM_PATTERNS = (
    re.compile(r"\b(install|download|apk|app store|play store)\b", re.I),
    re.compile(r"\b(click here|free vip|recharge|red envelope)\b", re.I),
)

# Macro terms that make an article about the broad market, not this name.
_MACRO_TERMS = ("fed", "fomc", "rate hike", "inflation", "gdp", "recession")


def _host_of(url: str) -> str:
    try:
        from urllib.parse import urlparse

        return (urlparse(url).netloc or "").lower()
    except Exception:  # noqa: BLE001
        return ""


def is_official(url: str) -> bool:
    host = _host_of(url)
    return any(host == h or host.endswith("." + h) for h in OFFICIAL_HOSTS)


def score_news_article(title: str, url: str = "", snippet: str = "",
                       ticker: str = "", company_name: str = "",
                       ambiguous_names: tuple[str, ...] = ()) -> dict:
    """Deterministic relevance score (0-100) + <=5 explainable reasons.

    Mirrors DSA's weights: code-in-title +55, code-snippet +34, code-url +18;
    company-name title +45 (ambiguous +26), snippet +28/+16; official +8;
    macro -12; clamp; reasons capped at 5.
    """
    title_t = str(title or "").lower()
    snip_t = str(snippet or "").lower()
    url_t = str(url or "").lower()
    code = str(ticker or "").upper().strip()
    name = str(company_name or "").strip()
    ambiguous = str(company_name or "").lower() in {str(n).lower() for n in ambiguous_names}

    score = 0.0
    reasons: list[str] = []

    if code and code.lower() in title_t:
        score += 55
        reasons.append("code-in-title")
    if code and code.lower() in snip_t:
        score += 34
        reasons.append("code-in-snippet")
    if code and code.lower() in url_t:
        score += 18
        reasons.append("code-in-url")
    if name and name.lower() in title_t:
        score += 26 if ambiguous else 45
        reasons.append("company-name-title" + ("-ambiguous" if ambiguous else ""))
    elif name and name.lower() in snip_t:
        score += 16 if ambiguous else 28
        reasons.append("company-name-snippet")
    if is_official(url):
        score += 8
        reasons.append("official-source")
    if any(m in title_t for m in _MACRO_TERMS):
        score -= 12
        reasons.append("macro-term")
    score = max(0.0, min(100.0, score))
    return {"score": round(score, 1), "reasons": reasons[:5]}


def admit_article(title: str, url: str = "", content_signals: str = "") -> bool:
    """Admission: official sources pass; spam/app-download signals drop.

    Content-signal regexes (not domain blacklists) — DSA admission rule.
    """
    if is_official(url):
        return True
    hay = f"{title} {content_signals}".lower()
    return not any(p.search(hay) for p in _SPAM_PATTERNS)


def degrade_triple(all_failed: bool, empty: bool, feature_off: bool = False) -> str:
    """The honesty contract for news readouts.

    Returns one of ``all_failed`` / ``empty`` / ``unavailable`` — "no news"
    never means "search failed".
    """
    if feature_off:
        return "unavailable"
    if all_failed:
        return "all_failed"
    if empty:
        return "empty"
    return "unavailable"


__all__ = [
    "score_news_article",
    "admit_article",
    "degrade_triple",
    "is_official",
    "OFFICIAL_HOSTS",
]

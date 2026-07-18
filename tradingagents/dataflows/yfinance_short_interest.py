"""Short-interest / float data from yfinance (free, no API key).

Surfaces the short-squeeze and conviction signals: shares sold short, the
short ratio (days-to-cover), short as a % of float, and the float/insider/
institutional ownership split. High short interest flags squeeze potential and
bearish positioning; very high levels are a contrarian/crowding warning.

Data comes from the same yfinance ``Ticker.info`` blob the identity resolver
already uses, so no key or paid plan is needed. Absent fields (many tickers
report only a subset) are shown as ``n/a`` rather than fabricated; a wholly
empty result raises ``NoMarketDataError`` so the router degrades cleanly.
"""
from __future__ import annotations

import logging

from .errors import NoMarketDataError
from .stockstats_utils import yf_retry
from .symbol_utils import normalize_symbol

logger = logging.getLogger(__name__)


def _num(value):
    """Coerce a value to a human-readable number string, or None."""
    if value is None:
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if n.is_integer():
        return f"{int(n):,}"
    return f"{n:,.4f}"


def get_short_interest_yfinance(ticker: str) -> str:
    """Fetch short interest / ownership data for a ticker from yfinance.

    Returns a markdown report with shares short, days-to-cover, short % of
    float, and float / insider / institutional ownership where available.
    """
    canonical = normalize_symbol(ticker)
    import yfinance as yf

    try:
        info = yf_retry(lambda: yf.Ticker(canonical).info) or {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Short-interest info fetch failed for %s: %s", ticker, exc)
        raise NoMarketDataError(ticker, canonical, "yfinance info fetch failed") from exc

    shares_short = info.get("sharesShort")
    shares_short_prior = info.get("sharesShortPriorMonth")
    short_ratio = info.get("shortRatio")
    short_pct_float = info.get("shortPercentOfFloat")
    float_shares = info.get("floatShares")
    shares_out = info.get("sharesOutstanding")
    insiders = info.get("heldPercentInsiders")
    institutions = info.get("heldPercentInstitutions")

    # Nothing meaningful returned -> honest no-data signal.
    if all(v is None for v in (shares_short, short_ratio, short_pct_float, float_shares)):
        raise NoMarketDataError(
            ticker, canonical, "no short-interest / float data returned"
        )

    lines = [f"## {ticker.upper()} Short Interest & Ownership (yfinance)", ""]
    if shares_short is not None:
        lines.append(f"- Shares short: {_num(shares_short)}")
    if shares_short_prior is not None:
        lines.append(f"- Shares short (prior month): {_num(shares_short_prior)}")
    if short_ratio is not None:
        lines.append(f"- Short ratio (days-to-cover): {_num(short_ratio)}")
    if short_pct_float is not None:
        lines.append(f"- Short % of float: {_num(short_pct_float)}")
    if float_shares is not None:
        lines.append(f"- Float shares: {_num(float_shares)}")
    if shares_out is not None:
        lines.append(f"- Shares outstanding: {_num(shares_out)}")
    if insiders is not None:
        lines.append(f"- Insider ownership: {_num(insiders)}")
    if institutions is not None:
        lines.append(f"- Institutional ownership: {_num(institutions)}")

    lines.append("")
    lines.append(
        "Interpretation: short % of float above ~10% is elevated; above ~20% is a "
        "crowded short (squeeze-prone but also a sign of strong bearish conviction). "
        "Days-to-cover >5 means unwinding would take time. High institutional and "
        "insider ownership is generally supportive; heavy insider selling is a "
        "caution flag."
    )
    return "\n".join(lines)

"""Structured price-target consensus - the half NEWS-6 was missing.

Every analyst-ratings vendor returns rendered ``str``: ``finnhub.py:136``,
``y_finance.py:879``, ``moomoo.py:1355`` and ``benzinga.py:942`` are each typed
``-> str``, and the structured target dict exists only *inside* them, rendered
to markdown immediately (``finnhub.py:160-166``, ``y_finance.py:919-926``). A
persisted PT-revision series needs those numbers as data, so this exposes the
consensus the yfinance chain already fetches as a dict for
``strategies/pt_history.py`` to record.

It adds no vendor call and no dependency: it reads the same
``Ticker.analyst_price_targets`` source ``get_analyst_ratings_yfinance`` reads.
It is a reader only - the store is written by the tool layer, following the
split ``score_history`` already uses.
"""

from __future__ import annotations

import pandas as pd

__all__ = ["price_target_snapshot"]

#: The consensus levels a row keeps, in the vendor's own naming.
_LEVELS = ("mean", "median", "high", "low", "current")


def price_target_snapshot(ticker: str) -> dict:
    """The price-target consensus as data, or an all-``None`` dict on failure.

    Never raises: a missing target set is an absent observation, and the caller's
    store simply records nothing.
    """
    out: dict = dict.fromkeys(_LEVELS)
    out["count"] = None
    out["source"] = None
    try:
        import yfinance as yf

        from tradingagents.dataflows.y_finance import require_symbol, yf_retry

        canonical = require_symbol(ticker)
        targets = yf_retry(lambda: yf.Ticker(canonical).analyst_price_targets)
    except Exception:  # noqa: BLE001 - absent data, not an error
        return out
    if not isinstance(targets, dict) or not targets:
        return out
    for level in _LEVELS:
        value = targets.get(level)
        try:
            if value is None or pd.isna(value):
                continue
            out[level] = float(value)
        except (TypeError, ValueError):
            continue
    if any(out[level] is not None for level in _LEVELS):
        out["source"] = "yfinance:analyst_targets"
    return out

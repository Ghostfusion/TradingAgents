"""The market-wide ``{name: closes}`` panel, built ONCE per run (P0-2).

``strategies/market_breadth.py`` (P0-3) is the producer of market-wide breadth,
and it takes a ``{name: closes}`` map. Nothing built that map, so every consumer
of the breadth read - ``technical_score``'s ``pct_above_50d`` / ``pct_above_200d``
/ ``ad_ratio`` and ``regime_score``'s ``breadth`` - declared the producer and was
never handed a value. `regime_score`'s own component table even records the
caller it did not have ("prerequisite 2 (P0-3); the leaf passes pct_above_50d").

This module is that builder and only that: it takes the S&P 500 constituent list
(``sp500_universe``, disk-cached weekly) and one close series per member through
a **caller-supplied fetcher**, and caches the assembled panel for the process so
a run pays for it once. The fetcher is injected rather than imported because the
run's own OHLCV cache lives in ``agents/utils/analysis_tools`` and a
``dataflows`` module must not import from ``agents``.

The panel is deliberately NOT bounded by default. A breadth read over a sample is
not a breadth read - ``market_breadth``'s own ``min_n`` gate says the same thing
from the other end - and a 40-name sample quoted as "market breadth" is the
"field whose name promises more than it measures" defect this repo keeps fixing.
``limit`` exists for tests and for a caller that has already chosen a smaller
panel, and it is printed in nothing: the panel size travels with the read, via
``market_breadth``'s own ``n``/``basis``.

Every name is passed through, including the ones whose fetch failed. A missing
series must show up in ``market_breadth``'s ``coverage`` (usable / total) rather
than being quietly dropped from the denominator - the same rule
``breadth_with_gate`` applies to a small sample.

Nothing here scores, gates or decides. A failure degrades to an empty map, which
``market_breadth`` turns into ``None`` - never a number from a handful of names.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

#: Assembled panels for this process, keyed by ``limit``. One process is one
#: run, so the first caller pays and every later caller in the same run reads
#: this. Cleared by ``_reset_market_panel_cache``.
_PANEL_CACHE: dict[int | None, dict] = {}


def _reset_market_panel_cache() -> None:
    """Drop the process panel cache (tests, and any caller that changed config)."""
    _PANEL_CACHE.clear()


def _universe_tickers(universe: dict | None = None) -> list[str]:
    """Every constituent in the S&P 500 map, de-duplicated, order preserved.

    ``universe`` is ``sp500_universe.fetch_sp500_universe``'s payload
    (``{"rows": {sector: [ticker, ...]}, ...}``); omit it to fetch. An
    unavailable universe returns ``[]`` - the caller then builds an empty panel
    rather than a partial one.
    """
    rows = None
    if isinstance(universe, dict):
        rows = universe.get("rows")
    if not isinstance(rows, dict):
        try:
            from tradingagents.dataflows.sp500_universe import fetch_sp500_universe

            rows = ((fetch_sp500_universe() or {}).get("rows")) or {}
        except Exception as exc:  # noqa: BLE001 - absence is a finding, not a crash
            logger.warning("sp500 universe unavailable: %s", exc)
            return []
    seen: dict[str, None] = {}
    for sector in sorted(rows):
        for ticker in rows.get(sector) or []:
            code = str(ticker).strip().upper()
            if code:
                seen.setdefault(code, None)
    return list(seen)


def market_closes(fetch_closes, *, universe: dict | None = None,
                  limit: int | None = None) -> dict:
    """``{ticker: [close, ...]}`` over the S&P 500, cached for this process.

    ``fetch_closes(ticker) -> list`` is the run's own close fetcher (the caller
    passes ``lambda t: _ohlcv(t).get("closes") or []``, so every series comes
    from the one OHLCV cache the run already uses - no second price source).

    Returns ``{}`` when the universe is unavailable or ``limit`` is 0. A name
    whose fetcher raised is still in the map with an empty series, so
    ``market_breadth``'s coverage reports it.
    """
    key = None if limit is None else int(limit)
    cached = _PANEL_CACHE.get(key)
    if cached is not None:
        return cached

    tickers = _universe_tickers(universe)
    if limit is not None:
        tickers = tickers[: max(0, int(limit))]
    panel: dict = {}
    for ticker in tickers:
        try:
            series = fetch_closes(ticker)
        except Exception as exc:  # noqa: BLE001 - one name's failure is not the panel's
            logger.warning("market panel: %s close fetch failed: %s", ticker, exc)
            series = None
        panel[ticker] = list(series or [])
    _PANEL_CACHE[key] = panel
    return panel


__all__ = ["market_closes"]

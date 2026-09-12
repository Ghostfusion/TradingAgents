"""The measured book drawdown — one resolver, so one number.

The governor gates on the drawdown of the **configured risk basket**
(``risk_basket_tickers`` / ``risk_basket_weights``) and the report renders that
same number as ``Book drawdown``. The analyst/trader tools used to resolve the
book themselves and silently defaulted to ``{ticker: 1.0}``, so a report could
carry two numbers under one name with no arbiter: NVDA 2026-09-12 showed
``Book drawdown: 7.24%`` (configured 8-name basket — the number the gate used)
beside ``realized book drawdown 20.21%`` (NVDA alone, from
``get_book_tail_risk``/``get_composed_risk_gate`` with default weights), and the
trader then fed 20.2% to ``get_risk_gate`` and reported a REJECT the real gate
never issued.

This module is the single resolver for that computation. It resolves the same
basket the governor uses, converts closes to log returns exactly once, and
returns the drawdown **with a source label** so a caller cannot present a
single-name figure as the book. ``None`` means "unmeasurable" — callers treat
unknown as never-fail, never as zero.
"""

from __future__ import annotations

import math
from collections.abc import Callable

# Minimum return observations for a series to enter the mix (mirrors the
# governor's ``_basket_drawdown``).
MIN_RETURNS = 5


def log_returns(closes) -> list[float]:
    """Log returns from a close series (the one conversion the mix uses)."""
    out: list[float] = []
    for i in range(1, len(closes or [])):
        try:
            prev, cur = float(closes[i - 1]), float(closes[i])
        except (TypeError, ValueError):
            continue
        if prev > 0 and cur > 0:
            out.append(math.log(cur / prev))
    return out


def configured_basket(cfg: dict | None) -> dict[str, float]:
    """The configured risk basket as ``{name: weight}``; ``{}`` when unset.

    Matches the governor exactly: two or more tickers are required (a one-name
    basket is not a book), and a ticker with no configured weight keeps weight
    ``0.0`` so the remaining sleeve stays cash rather than being silently
    equal-weighted.
    """
    tickers = [str(t) for t in ((cfg or {}).get("risk_basket_tickers") or []) if t]
    if len(tickers) < 2:
        return {}
    raw = (cfg or {}).get("risk_basket_weights") or {}
    weights: dict[str, float] = {}
    for name in tickers:
        try:
            weights[name] = float(raw.get(name, 0.0) or 0.0)
        except (TypeError, ValueError):
            weights[name] = 0.0
    return weights


def _resolve(
    weights: dict[str, float],
    closes_for: Callable[[str], list],
    min_returns: int,
    source: str,
) -> tuple[float | None, dict]:
    """Drawdown of one weighted mix, with provenance. A book needs two names."""
    returns_by_name: dict[str, list] = {}
    for name in weights:
        try:
            rets = log_returns(closes_for(name) or [])
        except Exception:  # noqa: BLE001 - a missing name just drops out
            continue
        if len(rets) >= int(min_returns):
            returns_by_name[name] = rets

    meta = {
        "source": source,
        "names": list(weights),
        "weights": dict(weights),
        "resolved": sorted(returns_by_name),
    }
    # A book claim needs two resolved legs, exactly like the governor: one leg
    # is not a portfolio.
    if len(returns_by_name) < (2 if len(weights) > 1 else 1):
        return None, meta
    if not returns_by_name:
        return None, meta
    try:
        from tradingagents.strategies.book_risk import portfolio_drawdown

        usable = {n: w for n, w in weights.items() if n in returns_by_name}
        return portfolio_drawdown(usable, returns_by_name), meta
    except Exception:  # noqa: BLE001 - unmeasurable, never a wrong number
        return None, meta


def measured_book_drawdown(
    cfg: dict | None,
    closes_for: Callable[[str], list],
    *,
    fallback_symbol: str | None = None,
    min_returns: int = MIN_RETURNS,
) -> tuple[float | None, dict]:
    """Measured max drawdown of the weighted book, plus its provenance.

    Resolution order:

    1. the **configured basket** when it resolves (two or more names with a
       usable series) — the same book the governor gates on and the report's
       ``Book drawdown`` line renders (``source="configured_basket"``);
    2. else ``fallback_symbol`` alone, labelled honestly:
       ``source="single_name"`` when no basket is configured, or
       ``source="single_name_fallback"`` when the configured basket could not
       be resolved (the caller must render it as a name-level drawdown);
    3. else ``(None, {"source": ...})``.

    Returns ``(drawdown, meta)`` where ``meta`` carries ``source``, ``names``,
    ``weights``, ``resolved`` and (for a fallback) ``basket`` — so a caller can
    print which book the number came from. ``None`` never fails a gate.
    """
    weights = configured_basket(cfg)
    basket_dd, basket_meta = (None, {"source": "none", "names": [], "weights": {}, "resolved": []})
    if weights:
        basket_dd, basket_meta = _resolve(weights, closes_for, min_returns, "configured_basket")
        if basket_dd is not None:
            return basket_dd, basket_meta

    symbol = str(fallback_symbol or "")
    if not symbol:
        return None, basket_meta
    source = "single_name_fallback" if weights else "single_name"
    dd, meta = _resolve({symbol: 1.0}, closes_for, min_returns, source)
    meta["basket"] = basket_meta
    return dd, meta


def describe_source(meta: dict) -> str:
    """One-line provenance for tool/analysis output ('configured basket (8)'…)."""
    source = str((meta or {}).get("source") or "none")
    names = list((meta or {}).get("names") or [])
    resolved = list((meta or {}).get("resolved") or [])
    if source == "configured_basket":
        return f"configured basket ({len(resolved)}/{len(names)} names)"
    if source == "single_name":
        return f"{names[0] if names else 'n/a'} alone (no basket configured)"
    if source == "single_name_fallback":
        return f"{names[0] if names else 'n/a'} alone (configured basket unresolved)"
    return "unavailable"


__all__ = [
    "MIN_RETURNS",
    "configured_basket",
    "describe_source",
    "log_returns",
    "measured_book_drawdown",
]

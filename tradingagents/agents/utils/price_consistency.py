"""Cross-tool price-scale / staleness consistency guard.

The verified-market snapshot is the designated source of truth for a run's
latest close. Several technical/setup tools compute on their own ``_ohlcv``
series, which — because it uses ``datetime.now()`` as the end date and may
route to a differently-fresh vendor chain — can end one or more sessions
behind the verified source, or land on a corrupted scale entirely. That
produces the stale-price contamination seen on INTU 2026-09-08 (setup tools
anchored to the 9/4 close / a ~677-scale series while the verified close was
314.12).

This module records the verified close once per ticker per run
(``set_verified_close``, called by ``build_verified_market_snapshot``) and
exposes ``ohlcv_scale_warning`` so any OHLCV-based tool can append a warning
to its output when its own latest close disagrees with the verified one by
more than a tolerance. Advisory: never raises; returns "" (no warning) when
no verified close is yet known for the ticker.
"""

from __future__ import annotations

from collections.abc import Sequence

# ticker (upper) -> verified latest close. Populated once per run by the
# verified-market-snapshot builder; read by every _ohlcv-based tool.
_VERIFIED_CLOSE_CACHE: dict[str, float] = {}

# ticker (upper) -> (as-of date, latest close) of the RUN OHLCV series. Single
# producer is analysis_tools._ohlcv (the run-series loader every price-derived
# tool shares), so the basis always describes the series the numbers came from
# — including the one case where it changes a decision: an intraday run whose
# last bar is still FORMING (GOOG 2026-09-11: the fundamentals report compared
# a forming 336.37 close against intrinsic value and a 200-day SMA while the
# market section flagged the same bar provisional; on the prior settled close
# the price was BELOW that SMA, so the sign of the structural read flips).
_PRICE_BASIS_CACHE: dict[str, tuple[str | None, float | None]] = {}

# Relative tolerance for "agrees with the verified close" (1%).
_SCALE_TOLERANCE = 0.01


def set_verified_close(ticker: str, close: float | None) -> None:
    """Record the verified latest close for ``ticker`` (idempotent)."""
    if not ticker or close is None:
        return
    from contextlib import suppress

    with suppress(TypeError, ValueError):
        _VERIFIED_CLOSE_CACHE[str(ticker).upper()] = float(close)


def set_price_basis(ticker: str, close: float | None,
                    as_of: str | None = None) -> None:
    """Record the run OHLCV series' latest (as-of date, close).

    Called by ``analysis_tools._ohlcv`` — the single run-series loader — so the
    basis is recorded exactly once per run and always matches the series the
    price-derived tools computed on. Advisory: never raises.
    """
    if not ticker:
        return
    from contextlib import suppress

    key = str(ticker).upper()
    with suppress(TypeError, ValueError):
        _PRICE_BASIS_CACHE[key] = (
            str(as_of) if as_of else None,
            float(close) if close is not None else None,
        )


def price_basis(ticker: str) -> tuple[str | None, float | None] | None:
    """The run series' (as-of date, latest close), or None when not recorded."""
    return _PRICE_BASIS_CACHE.get(str(ticker).upper())


def price_basis_line(ticker: str, curr_date: str | None = None) -> str:
    """One-line price basis for the analyst evidence block.

    A bar dated the run's analysis date is still FORMING on an intraday run:
    its close, and every figure derived from it (margin of safety,
    DCF-vs-market, PT upside, SMA/EMA distance), is provisional. Rendering the
    basis next to the evidence is what lets a fundamentals/news analyst label
    those numbers honestly — they have no market-snapshot tool of their own.

    Returns "" when the run series was never loaded, so no analyst claims a
    basis it does not have.
    """
    basis = price_basis(ticker)
    if basis is None:
        return ""
    as_of, close = basis
    px = f"{close:,.2f}" if close is not None else "unavailable"
    if as_of and curr_date and as_of == curr_date:
        return (
            f"**Reference price: {px}** ({as_of}, FORMING intraday bar -"
            " provisional: its close and every price-derived figure"
            " (margin of safety, DCF-vs-market, PT upside, SMA/EMA distance)"
            " are provisional until the session closes, and a distance that"
            " is a fraction of a percent may not hold at the settled close)."
        )
    if as_of:
        return f"**Reference price: {px}** ({as_of} settled close)."
    return f"**Reference price: {px}** (as-of date unavailable)."


def clear_verified_close_cache() -> None:
    """Drop the run-level close/price-basis caches (tests / fresh runs)."""
    _VERIFIED_CLOSE_CACHE.clear()
    _PRICE_BASIS_CACHE.clear()


def verified_close(ticker: str) -> float | None:
    """The last verified close for ``ticker``, or None if not yet recorded."""
    return _VERIFIED_CLOSE_CACHE.get(str(ticker).upper())


def ohlcv_scale_warning(ticker: str, close: float | Sequence[float] | None) -> str:
    """Warning line when ``close`` disagrees with the verified close.

    Returns "" (no warning) when the verified close is not yet recorded or
    the tool's close is within tolerance; otherwise a one-line advisory that
    the tool's OHLCV series is stale/scale-mismatched vs the verified source,
    so downstream actionable levels (stops/targets/psych levels) are
    unreliable. ``close`` may be a single latest close or a tuple of
    representative closes (e.g. the price-low scale) — the closest one is
    compared.
    """
    ref = verified_close(ticker)
    if ref is None or close is None:
        return ""
    if isinstance(close, (tuple, list)):
        # Compare against the member closest to the verified close (so e.g.
        # a price-low on a wrong scale is caught). If every member is far
        # from the verified close, the closest gap still drives the warning.
        cands = [c for c in close if isinstance(c, (int, float))]
        if not cands:
            return ""
        closest = min(cands, key=lambda c: abs(c - ref))
    else:
        try:
            closest = float(close)
        except (TypeError, ValueError):
            return ""
    denom = abs(ref)
    if denom == 0:
        return ""
    if abs(closest - ref) / denom <= _SCALE_TOLERANCE:
        return ""
    pct = abs(closest - ref) / denom * 100.0
    return (
        f"PRICE-SCALE WARNING: this tool's latest close ({closest:.2f}) "
        f"differs from the verified-market close ({ref:.2f}) by {pct:.1f}% - "
        "its OHLCV series is stale or on a corrupted scale. Treat any "
        "stop/target/level from this tool as UNRELIABLE until re-run against "
        "the verified snapshot (get_verified_market_snapshot)."
    )

__all__ = [
    "clear_verified_close_cache",
    "ohlcv_scale_warning",
    "price_basis",
    "price_basis_line",
    "set_price_basis",
    "set_verified_close",
    "verified_close",
]

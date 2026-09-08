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

# Relative tolerance for "agrees with the verified close" (1%).
_SCALE_TOLERANCE = 0.01


def set_verified_close(ticker: str, close: float | None) -> None:
    """Record the verified latest close for ``ticker`` (idempotent)."""
    if not ticker or close is None:
        return
    from contextlib import suppress

    with suppress(TypeError, ValueError):
        _VERIFIED_CLOSE_CACHE[str(ticker).upper()] = float(close)


def clear_verified_close_cache() -> None:
    """Drop the run-level verified-close cache (tests / fresh runs)."""
    _VERIFIED_CLOSE_CACHE.clear()


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

__all__ = ["set_verified_close", "ohlcv_scale_warning", "verified_close", "clear_verified_close_cache"]

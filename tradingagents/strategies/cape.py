"""CAPE (Shiller P/E) - the cyclically adjusted price-to-earnings ratio.

The ratio is a real quantity over a real quantity, and deflating both legs to a
common base cancels that base, so CAPE is computable without choosing one:

    CAPE(t) = (P_nom(t) / CPI(t)) / mean_k ( E_nom(k) / CPI(k) )

where the mean runs over the trailing window's annual EPS points. This is the
arithmetic the repository was missing (VALID-16): every input already has a
producer - ``dataflows.fred.get_series_values`` for the deflator,
``statement_parsing.sec_annual_series`` for the EPS history and the run's own
price series - so this module adds no data source and no dependency.

A constant is never returned in place of a measurement: a window that is too
short, or whose mean real EPS is not positive, yields ``cape=None`` **with a
reason**, never a default, a proxy or the nominal P/E.
"""

from __future__ import annotations

#: Trailing window, in fiscal years, that the EPS mean runs over. Shiller's 10.
CAPE_YEARS = 10

#: Below this many usable EPS points no CAPE is reported. Seven of ten is the
#: floor at which the mean still spans a full earnings cycle's worth of the
#: window; under it the "cyclically adjusted" claim is not supported.
CAPE_MIN_YEARS = 7


def _ym(date: str) -> tuple[int, int]:
    """``(year, month)`` from an ISO-ish date. A bare year means December."""
    parts = str(date).replace("/", "-").strip().split("-")
    try:
        year = int(parts[0])
    except (IndexError, ValueError):
        return 0, 0
    if len(parts) == 1:
        return year, 12
    try:
        month = int(parts[1])
    except ValueError:
        return year, 12
    if not 1 <= month <= 12:
        return year, 12
    return year, month


def _cpi_at_or_before(cpi_monthly: list, ym: tuple[int, int]) -> tuple | None:
    """The most recent ``(date, value)`` at or before ``ym``, or ``None``."""
    best = None
    best_key = None
    for date, value in cpi_monthly:
        key = _ym(date)
        if key <= ym and (best_key is None or key > best_key):
            best, best_key = (date, float(value)), key
    return best


def cape_ratio(
    price: float,
    eps_annual,
    cpi_monthly,
    *,
    years: int = CAPE_YEARS,
    min_years: int = CAPE_MIN_YEARS,
) -> dict:
    """CAPE for one name, plus the window and coverage it was computed over.

    Args:
        price: the latest nominal price.
        eps_annual: ``(period_end_date, diluted_eps)`` pairs, nominal, any order.
        cpi_monthly: ``(date, cpi)`` pairs, monthly, any order.
        years: trailing window in years.
        min_years: usable-EPS floor below which no CAPE is reported.

    Returns:
        A dict with ``cape``, ``mean_real_eps``, ``years_used``, ``window``,
        ``cpi_as_of`` and ``reason``. ``cape`` is ``None`` with a populated
        ``reason`` whenever the window does not support one - never a default.
    """
    out = {
        "cape": None, "mean_real_eps": None, "years_used": 0,
        "window": None, "cpi_as_of": None, "reason": None,
    }

    try:
        price = float(price)
    except (TypeError, ValueError):
        out["reason"] = "no price"
        return out
    if price <= 0:
        out["reason"] = f"non-positive price ({price})"
        return out

    cpi_monthly = [(d, float(v)) for d, v in (cpi_monthly or []) if v is not None]
    if not cpi_monthly:
        out["reason"] = "no CPI series"
        return out
    ym_now = max(_ym(d) for d, _v in cpi_monthly)
    cpi_now_pair = _cpi_at_or_before(cpi_monthly, ym_now)
    cpi_now = cpi_now_pair[1] if cpi_now_pair else 0.0
    if cpi_now <= 0:
        out["reason"] = "CPI is non-positive"
        return out
    out["cpi_as_of"] = cpi_now_pair[0]

    pts = []
    for date, value in eps_annual or []:
        try:
            pts.append((date, float(value)))
        except (TypeError, ValueError):
            continue
    if not pts:
        out["reason"] = "no EPS history"
        return out
    pts.sort(key=lambda p: _ym(p[0]))
    window_pts = pts[-years:] if years > 0 else pts

    real = []
    for date, eps in window_pts:
        cpi_k = _cpi_at_or_before(cpi_monthly, _ym(date))
        if cpi_k is None or cpi_k[1] <= 0:
            continue  # no deflator for that period: unusable, not zero
        real.append((date, eps * cpi_now / cpi_k[1]))

    out["years_used"] = len(real)
    if not real:
        out["reason"] = "no EPS period overlaps a CPI observation"
        return out
    out["window"] = (real[0][0], real[-1][0])
    if len(real) < min_years:
        out["reason"] = (
            f"insufficient window: {len(real)} usable EPS year(s), "
            f"floor is {min_years}"
        )
        return out

    mean_real = sum(v for _d, v in real) / len(real)
    out["mean_real_eps"] = round(mean_real, 6)
    if mean_real <= 0:
        out["reason"] = f"non-positive mean real EPS ({mean_real:.4f})"
        return out

    out["cape"] = round(price / mean_real, 2)
    return out


#: Upper bounds of the CAPE bands, ascending. Descriptive only - the read is
#: never a position size, a rating or a gate.
_CAPE_BANDS = ((15.0, "low"), (25.0, "moderate"), (35.0, "elevated"))


def cape_band(cape: float | None) -> str:
    """A descriptive band label for a CAPE, or ``"n/a"`` when unmeasurable."""
    if cape is None:
        return "n/a"
    for bound, label in _CAPE_BANDS:
        if cape < bound:
            return label
    return "stretched"

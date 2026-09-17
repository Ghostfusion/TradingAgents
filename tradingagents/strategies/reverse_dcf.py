"""Reverse DCF (price-implied) — what steady-state FCF / growth a price requires.

Why this module exists
======================
``tradingagents.strategies.dcf.compute_dcf`` projects one free-cash-flow figure
at a single growth rate ``g`` for ``years`` years and then capitalises the last
projected year with a Gordon terminal value at the *same* ``g``::

    EV = sum_{t=1..N} FCF_0 (1+g)^t / (1+wacc)^t
         + [FCF_0 (1+g)^N (1+g) / (wacc-g)] / (1+wacc)^N
    equity = EV + cash - debt
    price  = equity / shares

That sum telescopes algebraically into a single-stage perpetuity. With
``r = (1+g)/(1+wacc)`` the explicit-year PV is
``FCF_0 * (1+g)/(wacc-g) * (1 - r^N)`` and the discounted terminal value is
``FCF_0 * (1+g)/(wacc-g) * r^N``; the two ``r^N`` terms cancel exactly::

    EV == FCF_0 * (1+g) / (wacc-g)      for every N

So the advertised "5-year explicit window" carries no information the growth
rate does not already carry, and it cannot represent a capex regime change.

Concrete incident (MSFT, 2026-09-16). ``compute_dcf`` printed a MSFT fair value
of ``8.85 * 1.025 / 0.075 + 3.84 = $124.80`` per share against a $490.30 market
price, and the write-up dismissed the gap as a "modeling artifact". The inputs
were FY2026 revenue $331.8B, operating cash flow $182.9B, capex $115.9B, FCF
$67.0B and D&A $43.45B — a company mid-AI-buildout whose capex is compressing
reported FCF, i.e. exactly the regime a single ``g`` per unit of FCF cannot
express. The gap is not an artifact: it is the *answer* to a different question.
This module asks that question directly — **what steady-state FCF, or what
perpetual growth, does the observed price imply?** — so the analyst compares the
implied FCF against the company's actual FCF (does a plausible capex
normalisation explain the price?), or reads the implied growth off the curve
(is the growth rate plausible at all?).

Convention (kept identical to ``dcf.py``): enterprise value is the
perpetuity/Gordon form ``FCF*(1+g)/(wacc-g)`` — not ``FCF/(wacc-g)`` — bridged
``EV + cash - debt`` to equity and divided by shares. Inverting the forward
direction for FCF, with ``net_cash = cash - debt``::

    market_price*shares = FCF*(1+g)/(wacc-g) + net_cash
    => implied_fcf = (market_price*shares - net_cash) * (wacc - g) / (1 + g)

Reading ``implied_growth_for_fcf``: the forward value is increasing in ``g`` and
diverges as ``g -> wacc``, so a returned ``g`` sitting near the WACC bound means
the observed price is not explained by any plausible perpetual growth rate of
the supplied FCF — a capex/FCF regime shift upstream is the likelier story.

Pure, deterministic, no I/O, no network. Unusable inputs return an explicit
``{"usable": False, "reason": ...}`` rather than raising, mirroring
``compute_dcf``'s honesty of returning ``None`` instead of fabricating a value.
Every returned leaf carries the full assumption set, so a printed row is
reproducible from itself.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from tradingagents.strategies.dcf import terminal_value_gordon

_BASIS = (
    "perpetuity FCF(1+g)/(wacc-g) + net-cash bridge; "
    "implied = price-equity inverted for FCF"
)


def _num(x, default=None):
    """Coerce ``x`` to a finite float; None/blank/junk -> ``default``.

    Never raises. Non-finite values (``nan``/``inf``) are treated as missing so
    a poisoned provider field cannot leak a NaN into a printed leaf.
    """
    if x is None:
        return default
    try:
        v = float(x)
    except (TypeError, ValueError):
        return default
    return v if math.isfinite(v) else default


def _net_cash(cash, debt) -> float:
    """``cash - debt`` with junk/None treated as zero (never raises)."""
    return (_num(cash, 0.0) or 0.0) - (_num(debt, 0.0) or 0.0)


def reverse_dcf(
    market_price: float | None,
    shares: float | None,
    wacc: float | None,
    *,
    growths: Sequence[float] = (0.02, 0.025, 0.03, 0.04, 0.05, 0.07),
    current_fcf: float | None = None,
    cash: float | None = 0.0,
    debt: float | None = 0.0,
) -> dict:
    """Invert the perpetuity DCF: the steady-state FCF each growth rate implies.

    For every ``g`` in ``growths`` with ``g < wacc`` this solves the forward
    ``dcf.py`` convention for the FCF that would justify ``market_price``::

        implied_fcf = (market_price*shares - net_cash) * (wacc - g) / (1 + g)

    A lower assumed ``g`` pushes more of the value into the FCF term, so
    ``implied_fcf`` strictly decreases as ``g`` rises — the curve is the answer
    set of "steady-state FCF the price requires", indexed by growth.

    Args:
        market_price: observed price per share (>0 to be usable).
        shares: diluted shares outstanding (>0 to be usable).
        wacc: discount rate / cost of capital (>0 to be usable).
        growths: perpetual growth rates to probe; entries ``>= wacc`` (or
            ``<= -100%``) are skipped because the Gordon denominator is
            non-positive there.
        current_fcf: the company's current FCF, used to print the model's own
            forward fair value at each ``g`` (``model_fv_at_current_fcf``); None
            leaves that leaf None.
        cash: cash + equivalents for the EV->equity bridge.
        debt: total debt for the EV->equity bridge.

    Returns:
        dict with keys ``{usable, reason, basis, price, wacc, shares, net_cash,
        current_fcf, rows, crossing_g}``. ``rows`` is a list of
        ``{g, implied_fcf, implied_fcf_per_share, implied_multiple,
        model_fv_at_current_fcf}``; ``implied_multiple`` is None when the
        implied per-share FCF is not positive. ``usable`` is False (with a
        non-empty ``reason`` and empty ``rows``) when price/shares/wacc are
        missing or non-positive, or when no growth survives the ``g < wacc``
        filter. Never raises.
    """
    price = _num(market_price)
    sh = _num(shares)
    w = _num(wacc)
    fcf = _num(current_fcf)
    net_cash = _net_cash(cash, debt)

    out = {
        "usable": False,
        "reason": None,
        "basis": _BASIS,
        "price": price,
        "wacc": w,
        "shares": sh,
        "net_cash": net_cash,
        "current_fcf": fcf,
        "rows": [],
        "crossing_g": None,
    }

    if price is None or price <= 0:
        out["reason"] = "market_price missing or non-positive"
        return out
    if sh is None or sh <= 0:
        out["reason"] = "shares missing or non-positive"
        return out
    if w is None or w <= 0:
        out["reason"] = "wacc missing or non-positive"
        return out

    try:
        growth_seq = list(growths)
    except TypeError:
        growth_seq = []

    equity_req = price * sh
    rows: list[dict] = []
    for g in growth_seq:
        gg = _num(g)
        # Gordon needs wacc-g > 0 and the inversion divides by 1+g.
        if gg is None or gg >= w or 1.0 + gg <= 0.0:
            continue
        implied_fcf = (equity_req - net_cash) * (w - gg) / (1.0 + gg)
        per_share = implied_fcf / sh
        model_fv = None
        if fcf is not None:
            model_fv = (terminal_value_gordon(fcf, w, gg) + net_cash) / sh
        rows.append(
            {
                "g": gg,
                "implied_fcf": implied_fcf,
                "implied_fcf_per_share": per_share,
                "implied_multiple": price / per_share if per_share > 0 else None,
                "model_fv_at_current_fcf": model_fv,
            }
        )

    if not rows:
        out["reason"] = "no growth assumption below wacc (empty or all g >= wacc)"
        return out

    out["usable"] = True
    out["rows"] = rows
    out["crossing_g"] = implied_growth_for_fcf(
        price, sh, w, fcf, cash=cash, debt=debt
    )
    return out


def implied_growth_for_fcf(
    market_price: float | None,
    shares: float | None,
    wacc: float | None,
    fcf: float | None,
    *,
    cash: float | None = 0.0,
    debt: float | None = 0.0,
) -> float | None:
    """Perpetual growth ``g`` at which the forward DCF value equals the price.

    Solves ``FCF*(1+g)/(wacc-g) + net_cash == market_price*shares`` by bisection
    on ``g in (0, wacc - 1e-6)``; the forward value is monotone increasing in
    ``g`` on that interval, so the root is unique when it exists.

    Args:
        market_price: observed price per share.
        shares: diluted shares outstanding.
        wacc: discount rate; the search bound is just below it.
        fcf: the FCF to grow perpetually; must be positive to have a root.
        cash: cash + equivalents for the EV->equity bridge.
        debt: total debt for the EV->equity bridge.

    Returns:
        The crossing growth rate as a fraction, or None when inputs are
        unusable, when the price is already met at ``g = 0`` (no crossing inside
        the interval), or when even ``g -> wacc`` cannot reach the price — i.e.
        the price is unexplained by any plausible perpetual growth of this FCF.
        A returned value close to ``wacc`` is that same warning, softened: the
        required growth is large enough to make the Gordon denominator tiny.
    """
    price = _num(market_price)
    sh = _num(shares)
    w = _num(wacc)
    f = _num(fcf)
    if price is None or price <= 0:
        return None
    if sh is None or sh <= 0:
        return None
    if w is None or w <= 0:
        return None
    if f is None or f <= 0:
        return None

    net_cash = _net_cash(cash, debt)
    target_equity = price * sh

    def gap(g: float) -> float:
        """Forward equity at ``g`` minus the equity the price implies."""
        return terminal_value_gordon(f, w, g) + net_cash - target_equity

    lo, hi = 0.0, w - 1e-6
    if hi <= lo:
        return None
    if gap(hi) < 0.0:
        return None  # unreachable even as the value diverges toward wacc
    if gap(lo) >= 0.0:
        return None  # already met at g = 0: no crossing inside the interval

    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if gap(mid) < 0.0:
            lo = mid
        else:
            hi = mid
        if hi - lo <= 1e-12:
            break
    return 0.5 * (lo + hi)


__all__ = ["reverse_dcf", "implied_growth_for_fcf"]

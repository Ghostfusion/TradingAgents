"""Dealer-gamma (GEX) profile + OPEX calendar reads (derivatives-flow A1+A2, advisory).

A1 — chain gamma profile: aggregate per-strike option gamma (weighted by OI
and notional) to estimate dealer hedging pressure:
- ``gnex_per_strike``: gamma × OI × notional proxy per strike/side.
- ``gamma_regime``: net dealer-gamma sign -> short (momentum/trend risk,
  dealers chase) vs long (mean-reversion, dealers fade) — the write-up's
  most-tested mechanism.
- ``call_wall`` / ``put_wall``: strikes with the largest positive call-side /
  put-side gamma concentration (practitioner market-structure labels).
- ``zero_gamma_level``: spot estimate where the market gamma flips sign.

A2 — OPEX calendar: standard monthly + quarterly option-expiry dates
(third Friday) so a read can flag "in OPEX week" / "post-OPEX unwind".

Everything is None-safe (any missing input degrades, never fabricated) and
advisory — walls/zero-gamma are market-structure heuristics with weak
standalone predictive evidence, never a trade gate.
"""

from __future__ import annotations

from datetime import date, timedelta


def _gamma_contribution(strike: float, spot: float, t_years: float,
                        iv: float, oi: float) -> float | None:
    """OI × notional × Black-76 gamma proxy (advisory magnitude).

    ``gamma = phi(d1) / (F * sig * sqrt(T))``; contribution = gamma × OI ×
    notional (strike × 100). Notional scales OI so a wide-strike book with
    big OI dominates a tight one. None on invalid math.
    """
    try:
        import math

        if not all(v is not None and v > 0 for v in (strike, spot, t_years, iv, oi)):
            return None
        if t_years <= 0 or iv <= 0 or spot <= 0:
            return None
        sig = iv * (t_years ** 0.5)
        if sig <= 0:
            return None
        d1 = (math.log(spot / strike) + (iv * iv / 2.0) * t_years) / sig
        pdf = math.exp(-d1 * d1 / 2.0) / math.sqrt(2.0 * math.pi)
        gamma = pdf / (spot * iv * math.sqrt(t_years))
        return gamma * oi * strike * 100.0
    except Exception:  # noqa: BLE001 - advisory
        return None


def gex_per_strike(
    rows: list[dict], spot: float, t_years: float
) -> dict:
    """Aggregate dealer-gamma exposure across strikes.

    ``rows``: [{strike, iv, oi, side}] (side "call"/"put"). Returns the
    profile dict with per-strike contributions + the aggregate walls:
      {strikes, call_wall, put_wall, net_gamma_sign})
    Mainstream GEX convention (SpotGamma-style): the dealer is assumed short
    the option the public is long, so call OI contributes POSITIVE dealer
    gamma (dealers short calls = long gamma — hedge by buying strength,
    dampening moves) and put OI contributes NEGATIVE (dealers short puts =
    short gamma — amplifying moves). The old code had this inverted.
    """
    contributions: dict[str, list] = {"call": [], "put": []}
    total = 0.0
    for r in rows or []:
        strike = r.get("strike")
        iv = r.get("iv")
        oi = r.get("oi")
        if strike is None or iv is None or oi is None:
            continue
        g = _gamma_contribution(float(strike), spot, t_years, float(iv), float(oi))
        if g is None:
            continue
        side = (r.get("side") or "call").lower()
        # Mainstream sign: call OI => + dealer gamma, put OI => - dealer gamma
        # (dealers are short the public's options; see docstring).
        sign = +1.0 if side == "call" else -1.0
        signed = sign * g
        contributions.setdefault(side, []).append(
            {"strike": float(strike), "gamma": round(g, 2), "signed": round(signed, 2)}
        )
        total += signed
    walls = {}
    for side in ("call", "put"):
        rows_s = contributions.get(side) or []
        if rows_s:
            walls[f"{side}_wall"] = max(
                (x for x in rows_s if x.get("signed", 0) > 0 or True),
                key=lambda x: abs(x.get("signed") or 0.0),
            )["strike"]
        else:
            walls[f"{side}_wall"] = None
    return {
        "contributions": dict(contributions),
        "call_wall": walls.get("call_wall"),
        "put_wall": walls.get("put_wall"),
        "net_gamma": round(total, 2),
        "gamma_regime": "short" if total < 0 else ("long" if total > 0 else "flat"),
    }


def gamma_regime(gamma: float | None) -> str | None:
    """Short vs long dealer-gamma regime (advisory; None when unknown)."""
    if gamma is None:
        return None
    if gamma < 0:
        return "short (dealer hedging chases price: momentum/trend, cascade risk)"
    if gamma > 0:
        return "long (dealer hedging fades price: mean-reversion, pinned/molas-ass regime)"
    return "flat"


def opex_dates(year: int) -> list[date]:
    """Monthly OPEX dates: the third Friday of each month (US options)."""
    out = []
    for month in range(1, 13):
        d = date(year, month, 1)
        while d.weekday() != 4:  # Friday = 4
            d += timedelta(days=1)
        out.append(d + timedelta(days=14))  # +14 = third Friday
    return out


def opex_status(today: date, year: int | None = None) -> dict:
    """OPEX context for ``today``: {next_opex, prev_opex, days_to_next,
    in_opex_week, post_opex_unwind, quarterly}.
    """
    year = year if year is not None else today.year
    dates_all = [d for y in (year - 1, year, year + 1) for d in opex_dates(y)]
    future = [d for d in dates_all if d >= today]
    if not future:
        return {"next_opex": None, "prev_opex": None, "days_to_next": None,
                "in_opex_week": False, "post_opex_unwind": False, "quarterly": False}
    nxt = min(future)
    days = (nxt - today).days
    # Post-OPEX unwind window: the first two TRADING days AFTER the most
    # recent OPEX (Mon/Tue of a fresh week, i.e. the previous OPEX was
    # within the last ~4 days). The weekday gate matters: the weekend after
    # expiry belongs to the OPEX week, and its note would otherwise announce
    # a de-hedging flow that has not started yet.
    past = [d for d in dates_all if d < today]
    prev_opex = max(past) if past else None
    post_window = (
        prev_opex is not None
        and today.weekday() in (0, 1)
        and 1 <= (today - prev_opex).days <= 4
    )
    return {
        "next_opex": nxt.isoformat(),
        "prev_opex": prev_opex.isoformat() if prev_opex else None,
        "days_to_next": days,
        # "OPEX week" = the Mon-Fri week that CONTAINS the expiry, which is
        # exactly ISO (Monday-based) week equality. A 0..6-day countdown also
        # swallows the weekend BEFORE the expiry week: NVDA 2026-09-12 (a
        # Saturday, expiry the following Friday) was reported "in OPEX week".
        "in_opex_week": nxt.isocalendar()[:2] == today.isocalendar()[:2],
        "post_opex_unwind": post_window,
        "quarterly": nxt.month in (3, 6, 9, 12),
    }


def opex_note(status: dict) -> str | None:
    """Advisory one-liner for the OPEX context."""
    if not status or status.get("next_opex") is None:
        return None
    if status.get("in_opex_week"):
        return (
            f"in OPEX week — next expiry {status['next_opex']}; "
            "pinning can damp moves into Friday close; avoid false breakouts"
        )
    if status.get("post_opex_unwind"):
        # The expiry that passed, never the next one: naming `next_opex` here
        # announced "2026-10-16 passed" on 2026-09-21.
        passed = status.get("prev_opex") or "the last expiry"
        return (
            f"post-OPEX unwind window ({passed} passed) — "
            "dealer de-hedging can release a directional move"
        )
    return f"next OPEX {status['next_opex']} in {status['days_to_next']}d"


__all__ = [
    "gex_per_strike",
    "gamma_regime",
    "opex_dates",
    "opex_status",
    "opex_note",
]

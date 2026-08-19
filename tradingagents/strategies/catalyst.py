"""B1 - scheduled-catalyst strategy overlay (Phase-4 PEAD wiring).

A deterministic, config-guarded strategy that sizes positions around scheduled
catalysts the pipeline already fetches but never acted on:

  * earnings  - next scheduled print (calendar), last reported surprise (side),
                and the market-implied move / IV crush history (moomoo F10)
  * macro     - HIGH-importance economic events (CPI, FOMC, payrolls, ...)
                in an upcoming window
  * fed       - next FOMC meeting + market-implied rate probability

``build_catalyst_snapshot`` folds those into one scale (0..1) and a verdict;
``fold_catalyst_into_overlay`` multiplies the base overlay's ``position_scale``
(like ``orderflow.fold_flow_into_overlay`` does) so the position contract and
the risk governor downstream see the catalyst-adjusted size. Built on the
PEAD helpers in ``events.py``, which were written but never wired.

``fetch_catalyst_data`` pulls live moomoo data guarded like
``orderflow.fetch_flow``: any failure returns None and the overlay is skipped
(neutral), never an exception.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from .events import catalyst_risk_penalty, drift_side, surprise_score

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def parse_date(value) -> datetime | None:
    """Parse common date strings; None when unparseable."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()[:10]
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def calendar_days_between(a, b) -> int:
    """Whole calendar days from ``a`` to ``b`` (positive when b is after a)."""
    da, db = parse_date(a), parse_date(b)
    if da is None or db is None:
        return -1
    return (db - da).days


def _num(value, default=None):
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def last_earnings_surprise(rows: list) -> dict | None:
    """Most recent reportable earnings surprise from calendar rows.

    Accepts row dicts with ``eps_actual``/``eps_estimate`` (moomoo) or
    ``actual``/``consensus`` keys. Returns ``{"surprise", "side", "date"}`` or
    None when nothing is quantifiable.
    """
    best = None
    for row in rows or []:
        actual = _num(row.get("eps_actual"), _num(row.get("actual")))
        est = _num(row.get("eps_estimate"), _num(row.get("consensus")))
        surprise = surprise_score(actual, est)
        if surprise is None:
            continue
        date_s = str(row.get("date", "") or "").strip()
        if best is None or date_s > best.get("date", ""):
            best = {"surprise": surprise, "side": drift_side(surprise), "date": date_s}
    return best


def next_earnings(rows: list, trade_date: str, lookahead_days: int = 60) -> dict | None:
    """First earnings entry at/after trade_date within lookahead_days."""
    td = parse_date(trade_date)
    if td is None:
        return None
    best = None
    for row in rows or []:
        d = parse_date(row.get("date"))
        if d is None:
            continue
        days = (d - td).days
        if 0 <= days <= lookahead_days and (best is None or days < best["days_until"]):
            best = {
                "date": d.strftime("%Y-%m-%d"),
                "days_until": days,
                "eps_estimate": _num(row.get("eps_estimate"), _num(row.get("consensus"))),
                "eps_actual": _num(row.get("eps_actual"), _num(row.get("actual"))),
            }
    return best


def implied_move_from_history(history: list) -> float | None:
    """Latest market-implied earnings move (fraction) from the price history.

    ``predict_vola_ratio_newest`` arrives as percent (e.g. 3.9 = 3.9%).
    """
    for row in history or []:
        v = _num(row.get("predict_vola_ratio_newest"))
        if v is not None and v > 0:
            return v / 100.0
    return None


def macro_imminence(events: list, trade_date: str, window_days: int = 3) -> dict:
    """HIGH-importance economic events in the upcoming window."""
    td = parse_date(trade_date)
    if td is None:
        return {"count_high": 0, "min_days": None}
    count = 0
    min_days = None
    for ev in events or []:
        star = str(ev.get("star", "")).strip().upper()
        d = parse_date(ev.get("timestamp") or ev.get("date"))
        if d is None or star != "HIGH":
            continue
        days = (d - td).days
        if 0 <= days <= window_days:
            count += 1
            min_days = days if min_days is None else min(min_days, days)
    return {"count_high": count, "min_days": min_days}


def fed_imminence(fed_rows: list, trade_date: str, window_days: int = 14) -> dict:
    """Next FOMC meeting within the window + modal target-rate probability."""
    td = parse_date(trade_date)
    if td is None:
        return {"days_until": None, "modal_prob": None}
    meetings = {}
    for row in fed_rows or []:
        d = parse_date(row.get("meeting_date"))
        if d is None:
            continue
        days = (d - td).days
        if days < 0:
            continue
        prob = _num(row.get("probability"))
        if prob is not None and days <= window_days:
            meeting = d.strftime("%Y-%m-%d")
            meetings[meeting] = max(meetings.get(meeting, 0.0), prob)
    if not meetings:
        return {"days_until": None, "modal_prob": None}
    meeting = min(meetings, key=lambda m: m)
    md = parse_date(meeting)
    return {"days_until": (md - td).days if md else None, "modal_prob": meetings[meeting]}


# ---------------------------------------------------------------------------
# Snapshot + overlay fold
# ---------------------------------------------------------------------------


def build_catalyst_snapshot(data: dict, trade_date: str, cfg: dict | None = None) -> dict:
    """Combine earnings / macro / fed into one scale (0..1) + verdict.

    ``data`` is the dict from :func:`fetch_catalyst_data` (any section may be
    empty). Pre-event risk dominates: an imminent earnings print scales down by
    the implied move (``events.catalyst_risk_penalty``); macro/Fed catalysts in
    their windows apply their configured multipliers; a recent earnings *miss*
    applies ``catalyst_miss_scale``. Scale is floored at
    ``catalyst_scale_floor`` and never exceeds 1.0.
    """
    cfg = cfg or {}
    window_days = int(_num(cfg.get("catalyst_window_days"), 5) or 5)
    baseline = float(_num(cfg.get("catalyst_baseline_move"), 0.02) or 0.02)
    macro_window = int(_num(cfg.get("catalyst_macro_window_days"), 3) or 3)
    macro_scale = float(_num(cfg.get("catalyst_macro_scale"), 0.6) or 0.6)
    fed_window = int(_num(cfg.get("catalyst_fed_window_days"), 10) or 10)
    fed_scale = float(_num(cfg.get("catalyst_fed_scale"), 0.6) or 0.6)
    miss_scale = float(_num(cfg.get("catalyst_miss_scale"), 0.5) or 0.5)
    floor_scale = float(_num(cfg.get("catalyst_scale_floor"), 0.25) or 0.25)

    data = data or {}
    earnings = next_earnings(data.get("earnings_calendar") or [], trade_date)
    last = last_earnings_surprise(data.get("earnings_calendar") or [])
    implied = implied_move_from_history(data.get("move_history") or [])
    macro = macro_imminence(
        data.get("economic_calendar") or [], trade_date, window_days=macro_window
    )
    fed = fed_imminence(data.get("fed_watch") or [], trade_date, window_days=fed_window)

    scale = 1.0
    verdict = "no-imminent-catalyst"
    reasons: list[str] = []

    if earnings is not None and 0 <= earnings["days_until"] <= window_days:
        penalty = catalyst_risk_penalty(implied, baseline)
        scale *= penalty
        verdict = "earnings-window"
        implied_note = f"implied {implied:.1%}" if implied is not None else "implied n/a"
        reasons.append(
            f"earnings {earnings['date']} in {earnings['days_until']}d ({implied_note}) -> x{penalty:.2f}"
        )
        if last and last["side"] == "miss":
            scale *= miss_scale
            reasons.append(
                f"last earnings miss (surprise {last['surprise']:+.1%}) -> x{miss_scale:.2f}"
            )

    if macro["count_high"] > 0:
        scale *= macro_scale
        if verdict == "no-imminent-catalyst":
            verdict = "macro-catalyst"
        reasons.append(
            f"{macro['count_high']} HIGH macro event(s) within {macro_window}d -> x{macro_scale:.2f}"
        )

    if fed["days_until"] is not None:
        scale *= fed_scale
        if verdict == "no-imminent-catalyst":
            verdict = "fed-catalyst"
        reasons.append(
            f"FOMC {fed['days_until']}d out (modal {fed['modal_prob']:.0%}) -> x{fed_scale:.2f}"
        )

    scale = max(floor_scale, min(1.0, scale))
    return {
        "earnings": earnings,
        "last_surprise": last,
        "implied_move": implied,
        "macro": macro,
        "fed": fed,
        "scale": round(scale, 4),
        "verdict": verdict,
        "reasons": reasons,
    }


def fold_catalyst_into_overlay(overlay: dict | None, snapshot: dict | None) -> dict | None:
    """Multiply the overlay's ``position_scale`` by the catalyst scale.

    Mirrors ``fold_flow_into_overlay``: the catalyst block is stamped on the
    overlay, ``position_scale`` is adjusted, and a context note is appended.
    """
    if not overlay or not snapshot:
        return overlay
    scale = float(snapshot.get("scale", 1.0) or 1.0)
    updated = dict(overlay)
    base = float(overlay.get("position_scale", 1.0) or 1.0)
    updated["position_scale"] = round(max(0.0, min(base * scale, 1.5)), 3)
    updated["catalyst"] = snapshot
    note = f"catalyst {snapshot.get('verdict', '?')}"
    if snapshot.get("reasons"):
        note += ": " + "; ".join(snapshot["reasons"])
    updated["context"] = overlay.get("context", "") + " | " + note
    return updated


def apply_catalyst_scale(size_pct: float | None, snapshot: dict | None) -> float | None:
    """Apply the catalyst scale to a position fraction (for the contract)."""
    if size_pct is None or not snapshot:
        return size_pct
    return round(max(0.0, min(float(size_pct) * float(snapshot.get("scale", 1.0)), 1.0)), 4)


# ---------------------------------------------------------------------------
# Guarded live fetch (mirrors orderflow.fetch_flow)
# ---------------------------------------------------------------------------


def _calendar_window(ctx, market: str, start: str, end: str, chunk_days: int = 6) -> list:
    """moomoo's earnings calendar caps windows at 7 days *inclusive* (begin+6);
    chunk the request so each call spans at most begin..begin+6. Returns
    canonical row dicts for the market (``date``/``eps_estimate``/
    ``eps_actual`` — mapped from moomoo's ``earnings_date``/``eps_predict``/
    ``eps_actual`` with ``N/A`` actuals converted to None).
    """
    from pandas import concat

    parts = []
    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")
    cur = start_dt
    while cur <= end_dt:
        chunk_end = min(cur + timedelta(days=chunk_days), end_dt)
        ret, df = ctx.get_earnings_calendar(
            market=market,
            begin_date=cur.strftime("%Y-%m-%d"),
            end_date=chunk_end.strftime("%Y-%m-%d"),
        )
        if ret == 0 and df is not None and not df.empty:
            parts.append(df)
        cur = chunk_end + timedelta(days=1)
    if not parts:
        return []
    combined = concat(parts, ignore_index=True)

    # Normalize moomoo's names (security / earnings_date / eps_predict) to the
    # canonical keys the pure layer reads; drop whole-market rows that are not
    # the requested security; convert "N/A" actuals to None.
    rows = []
    for r in combined.to_dict("records"):
        actual = r.get("eps_actual")
        if actual is None or (
            isinstance(actual, str) and actual.strip().upper() in ("N/A", "NA", "", "NONE")
        ):
            actual = None
        rows.append(
            {
                "security": str(r.get("security", "") or ""),
                "date": str(r.get("earnings_date") or r.get("date") or "").strip(),
                "eps_estimate": r.get("eps_predict", r.get("eps_estimate")),
                "eps_actual": actual,
            }
        )
    return rows


def _filter_by_security(rows: list, code: str) -> list:
    """Keep calendar rows whose security marker contains the moomoo code."""
    if not code:
        return rows
    needle = code.upper()
    return [r for r in rows or [] if needle in str(r.get("security") or "").upper()]


def fetch_catalyst_data(ticker: str, trade_date: str) -> dict | None:
    """Live catalyst inputs for one ticker; None on any failure (neutral)."""
    try:
        from tradingagents.dataflows.moomoo import _ensure_ctx, _moomoo_code

        code = _moomoo_code(ticker)
        ctx = _ensure_ctx()
        market = code.split(".")[0] if "." in code else "US"
        td = parse_date(trade_date) or datetime.now()
        td_str = td.strftime("%Y-%m-%d")
        past = (td - timedelta(days=35)).strftime("%Y-%m-%d")
        fwd = (td + timedelta(days=95)).strftime("%Y-%m-%d")

        earnings_rows = _filter_by_security(
            _calendar_window(ctx, market, past, fwd), code
        )

        move_history = []
        ret, hist = ctx.get_financials_earnings_price_history(code)
        if ret == 0 and hist is not None and not hist.empty:
            move_history = hist.to_dict("records")

        macro_events = []
        ret, eco, _next_page, _has_more = ctx.get_economic_calendar(
            begin_date=td_str,
            end_date=(td + timedelta(days=14)).strftime("%Y-%m-%d"),
        )
        if ret == 0 and eco is not None and not eco.empty:
            macro_events = eco.to_dict("records")

        fed_rows = []
        ret, fed = ctx.get_fed_watch_target_rate()
        if ret == 0 and fed is not None and not fed.empty:
            fed_rows = fed.to_dict("records")

        return {
            "earnings_calendar": earnings_rows,
            "move_history": move_history,
            "economic_calendar": macro_events,
            "fed_watch": fed_rows,
        }
    except Exception as exc:  # noqa: BLE001 - guarded like orderflow.fetch
        logger.info("catalyst data unavailable for %s: %s", ticker, exc)
        return None


__all__ = [
    "parse_date",
    "calendar_days_between",
    "last_earnings_surprise",
    "next_earnings",
    "implied_move_from_history",
    "macro_imminence",
    "fed_imminence",
    "build_catalyst_snapshot",
    "fold_catalyst_into_overlay",
    "apply_catalyst_scale",
    "fetch_catalyst_data",
]

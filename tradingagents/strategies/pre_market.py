"""Pre-Market Decision Review — deterministic deltas.

Pure, offline-testable functions that turn measured overnight deltas into
the numbers a pre-market reviewer needs (design: ``docs/pre_market_review.md``).
No network, no LLM — these run before the reviewer agent so every verdict it
emits is grounded in recomputed values rather than prose.

Choice (a) placement:
  * **same-night (in-batch)** — catalyst/quality re-check only: no quote, no
    gap; ``catalyst_window_read`` + ``review_decision(catalyst=...)``.
  * **pre-open (standalone script)** — quote + gap + re-anchored tranche plan:
    ``premarket_gap`` + ``reanchor_plan`` + ``review_decision(...)``.

Reuses the existing deterministic building blocks (``strategies/value_dip.py``
tranche plan/risk read, ``strategies/catalyst.py`` snapshot shape).
"""

from __future__ import annotations

from .value_dip import tranche_plan

__all__ = [
    "premarket_gap",
    "catalyst_window_read",
    "reanchor_plan",
    "review_decision",
    "load_prior_state",
    "parse_planned_levels",
    "record_review",
    "resolve_ledger",
    "ledger_track_record",
]


# ---------------------------------------------------------------------------
# Gap read
# ---------------------------------------------------------------------------


def premarket_gap(
    prior_close: float | None,
    open_price: float | None,
    prior_stop: float | None = None,
    entry_price: float | None = None,
    atr: float | None = None,
) -> dict:
    """Read the overnight gap between the prior close and an open/pre-market
    price, plus whether the gap invalidates the prior plan.

    Returns ``{gap_pct, gap_atr, through_stop, vacuum_to_stop, direction}``:

    * ``through_stop`` — the open is beyond the prior stop on the stop's side
      (for a long entry: open < stop). The prior plan would have stopped out;
      this is the strongest REJECT signal.
    * ``vacuum_to_stop`` — the open filled *between* the planned entry and the
      stop on the adverse side (long: entry > open >= stop): the fill is
      immediately underwater and the plan should be REVISEd, not carried over.
    * ``direction`` is inferred from the entry/stop ordering (entry > stop =>
      long; entry < stop => short); None when no stop is provided.

    A missing quote/close renders every sub-field None (never invented).
    """
    if prior_close is None or open_price is None or prior_close <= 0:
        return {
            "gap_pct": None,
            "gap_atr": None,
            "through_stop": None,
            "vacuum_to_stop": None,
            "direction": None,
            "open_price": open_price,
        }
    gap_pct = (float(open_price) - float(prior_close)) / float(prior_close)
    gap_atr = None
    if atr is not None and atr > 0:
        gap_atr = (float(open_price) - float(prior_close)) / float(atr)

    through_stop = False
    vacuum_to_stop = False
    direction = None
    if prior_stop is not None and entry_price is not None:
        long = float(entry_price) > float(prior_stop)
        direction = "long" if long else "short"
        if (long and open_price < prior_stop) or (not long and open_price > prior_stop):
            through_stop = True
        elif (long and open_price < entry_price) or (not long and open_price > entry_price):
            vacuum_to_stop = True

    return {
        "gap_pct": round(gap_pct, 6),
        "gap_atr": round(gap_atr, 4) if gap_atr is not None else None,
        "through_stop": through_stop,
        "vacuum_to_stop": vacuum_to_stop,
        "direction": direction,
        "open_price": float(open_price),
    }


# ---------------------------------------------------------------------------
# Catalyst window re-check (same-night + pre-open path)
# ---------------------------------------------------------------------------


def catalyst_window_read(snapshot: dict | None, cfg: dict | None = None) -> dict:
    """Re-check the B1 catalyst snapshot against the review config.

    ``snapshot`` is the ``build_catalyst_snapshot`` dict
    (``strategies/catalyst.py``): has ``verdict``, ``scale`` (0..1) and a
    ``hard_block`` dict when an earnings print is inside
    ``catalyst_hard_block_days``. Mirrors ``_apply_strategy_overlays``'
    hard-block semantics for the review layer.

    Returns ``{hard_block, days_until, earnings_date, verdict, scale,
    tightened}`` — ``tightened`` True when the scale < 1.0 (window active).
    """
    cfg = cfg or {}
    snap = snapshot or {}
    hard = snap.get("hard_block")
    if hard and isinstance(hard, dict):
        return {
            "hard_block": True,
            "days_until": hard.get("days_until"),
            "earnings_date": hard.get("earnings_date"),
            "verdict": "hard-block",
            "scale": 0.0,
            "tightened": True,
        }
    scale = snap.get("scale")
    verdict = snap.get("verdict") or "no-imminent-catalyst"
    return {
        "hard_block": False,
        "days_until": None,
        "earnings_date": None,
        "verdict": verdict,
        "scale": scale if scale is not None else 1.0,
        "tightened": bool(scale is not None and scale < 1.0),
    }


# ---------------------------------------------------------------------------
# Re-anchored tranche plan (pre-open path only)
# ---------------------------------------------------------------------------


def reanchor_plan(
    open_price: float | None,
    atr_value: float | None,
    weights: tuple = (0.3, 0.3, 0.4),
    stop_mult: float = 1.5,
    risk_pct: float = 0.015,
    account: float = 100_000.0,
    max_position_pct: float = 0.30,
    max_book_position_pct: float = 0.45,
) -> dict:
    """Re-anchor the tranche scale-in plan to a fresh open price.

    Runs the deterministic ``tranche_plan(P1=open_price, ...)`` and returns
    the reviewer-facing summary: ``avg_entry`` (the weighted entry the re-
    anchored contract would use), the composite ``stop``, the
    ``peak_deployed_pct`` (fully-scaled capital exposure vs account) and its
    per-trade / book cap checks. ``valid=False`` when price/ATR are unusable
    (the reviewer falls back to CONFIRM — no data is never a rejection).
    """
    if open_price is None or open_price <= 0 or atr_value is None or atr_value <= 0:
        return {"valid": False, "reason": "no usable open price / ATR"}
    plan = tranche_plan(
        open_price,
        atr_value,
        weights=weights,
        stop_mult=stop_mult,
        account=account,
        risk_pct=risk_pct,
    )
    if not plan.get("valid"):
        return {"valid": False, "reason": plan.get("reason", "invalid tranche inputs")}
    peak = plan.get("peak_deployed_pct")
    cap_ok = peak is not None and peak <= float(max_position_pct)
    book_ok = peak is not None and peak <= float(max_book_position_pct)
    return {
        "valid": True,
        "avg_entry": plan.get("avg_entry"),
        "stop": plan.get("stop"),
        "risk_per_share": plan.get("risk_per_share"),
        "peak_deployed_pct": peak,
        "capital_at_risk_pct": plan.get("capital_at_risk_pct"),
        "cap_ok": cap_ok,
        "book_ok": book_ok,
        "weights": plan.get("weights"),
        "shares": plan.get("shares"),
        "targets": plan.get("targets"),
    }


# ---------------------------------------------------------------------------
# The deterministic verdict arbiter (before any LLM rubber-stamp)
# ---------------------------------------------------------------------------


def review_decision(
    *,
    prior_close: float | None = None,
    open_price: float | None = None,
    prior_stop: float | None = None,
    entry_price: float | None = None,
    atr_value: float | None = None,
    catalyst_snapshot: dict | None = None,
    reanchor: dict | None = None,
    cfg: dict | None = None,
) -> dict:
    """Deterministic CONFIRM / REVISE / REJECT arbiter from measured deltas.

    Same-night path (no quote provided): only the catalyst window is checked;
    a hard block REJECTs, an active window REVISEs (scale down), otherwise
    CONFIRM.

    Pre-open path (quote provided): the gap read runs first —

    * open beyond the prior stop  -> REJECT (would have stopped out)
    * open in the adverse fill zone (vacuum to stop) -> REVISE (re-anchor)
    * any sizable gap (|gap_atr| >= 1.0 default) -> REVISE (re-anchor levels)
    * otherwise (small / favorable gap) -> CONFIRM with refreshed levels

    If ``reanchor`` is provided and its cap checks fail (peak-deployed > the
    per-trade or book cap), the arbiter REJECTs — the re-anchored size would
    breach a limit the governor enforces.

    Returns a dict with ``verdict``, ``reasons`` (measured, never prose),
    ``entry`` / ``stop`` / ``size_pct`` (re-anchored when REVISE) and the
    sub-reads so the report stores the numbers, not just the label.
    """
    cfg = cfg or {}
    gap_atr_threshold = float(cfg.get("pre_market_gap_atr_threshold", 1.0))
    reasons: list[str] = []
    verdict = "CONFIRM"
    entry = None
    stop = None
    size_pct = None

    # Catalyst first (both paths).
    cat = catalyst_window_read(catalyst_snapshot, cfg)
    if cat["hard_block"]:
        verdict = "REJECT"
        reasons.append(
            f"catalyst hard block: earnings {cat.get('earnings_date')} "
            f"in {cat.get('days_until')}d before the open"
        )
    elif cat["tightened"]:
        verdict = "REVISE"
        reasons.append(
            f"catalyst window active: {cat['verdict']} scale {cat['scale']:.2f} "
            "(scale position down / defer)"
        )

    # Pre-open gap path.
    has_quote = prior_close is not None and open_price is not None
    if has_quote:
        gap = premarket_gap(
            prior_close, open_price, prior_stop=prior_stop, entry_price=entry_price, atr=atr_value
        )
        if gap.get("through_stop") is True and verdict != "REJECT":
            verdict = "REJECT"
            reasons.append(
                f"open {open_price} beyond prior stop {prior_stop} "
                "— the prior plan would have stopped out (gap risk realized)"
            )
        elif gap.get("vacuum_to_stop") is True and verdict != "REJECT":
            verdict = "REVISE"
            reasons.append(
                f"open {open_price} filled adversely between entry {entry_price} "
                "and stop — re-anchor levels, do not carry the old plan"
            )
        elif (
            verdict != "REJECT"
            and gap.get("gap_atr") is not None
            and abs(gap["gap_atr"]) >= gap_atr_threshold
        ):
            verdict = "REVISE"
            reasons.append(
                f"overnight gap {gap['gap_pct']:+.1%} "
                f"({gap['gap_atr']:.2f} ATR) — re-anchor entry/stop to the open"
            )

        if verdict == "REVISE" and reanchor and reanchor.get("valid"):
            entry = reanchor.get("avg_entry")
            stop = reanchor.get("stop")
            size_pct = reanchor.get("peak_deployed_pct")
            reasons.append(
                f"re-anchored plan: entry={entry} stop={stop} "
                f"peak_deployed={size_pct:.1%}"
            )

    # Re-anchor cap checks (pre-open path).
    if reanchor and reanchor.get("valid"):
        if reanchor.get("cap_ok") is False:
            verdict = "REJECT"
            reasons.append(
                f"re-anchored peak-deployed {reanchor['peak_deployed_pct']:.1%} "
                "exceeds the per-trade cap"
            )
        elif reanchor.get("book_ok") is False:
            verdict = "REJECT"
            reasons.append(
                f"re-anchored peak-deployed {reanchor['peak_deployed_pct']:.1%} "
                "exceeds the book cap"
            )

    if not reasons:
        reasons.append("no measurable overnight delta invalidating the prior decision")

    return {
        "verdict": verdict,
        "reasons": reasons,
        "entry": entry,
        "stop": stop,
        "size_pct": size_pct,
        "catalyst": cat,
        "gap": (
            premarket_gap(
                prior_close, open_price, prior_stop=prior_stop, entry_price=entry_price, atr=atr_value
            )
            if has_quote
            else None
        ),
        "reanchor": reanchor,
    }


# ---------------------------------------------------------------------------
# Prior-state loader (shared by script + batch integration)
# ---------------------------------------------------------------------------


def load_prior_state(
    report_dir: str, prior_date: str | None = None, results_dir: str | None = None
) -> dict:
    """Load the machine-shaped prior-run state for a report folder.

    ``_log_state`` writes the full state to
    ``<results_dir>/<TICKER>/TradingAgentsStrategy_logs/full_states_log_<date>.json``
    (NOT inside the report folder), so this loader searches both the report
    folder's sibling ``TradingAgentsStrategy_logs`` and a configurable
    ``results_dir`` when given. The ``5_portfolio/decision.md`` (inside the
    report folder) is the human-readable side.

    Returns ``{"state", "decision_md", "ticker", "date", "log_path"}``;
    never raises — a missing folder/log returns None so the caller can fail
    open (design §10).
    """
    import glob
    import json
    import os

    ticker_from_dir = os.path.basename(os.path.normpath(report_dir or "")).split("_")[0]
    candidates = []
    # Search order: 1) <report_dir>/<TICKER>/TradingAgentsStrategy_logs (batch
    # saves reports and logs share the same results_dir), 2) an explicit
    # results_dir argument, 3) the report dir's own name as the ticker folder.
    for logs_base in (report_dir, os.path.dirname(report_dir), ""):
        if logs_base:
            candidates.append(os.path.join(logs_base, ticker_from_dir, "TradingAgentsStrategy_logs"))
        candidates.append(os.path.join(logs_base, "TradingAgentsStrategy_logs"))
    if results_dir:
        candidates.insert(0, os.path.join(results_dir, ticker_from_dir, "TradingAgentsStrategy_logs"))

    def _newest(roots):
        matches = []
        for root in roots:
            if not root or not os.path.isdir(root):
                continue
            matches += glob.glob(os.path.join(root, "full_states_log_*.json"))
        return matches

    path = None
    date = None
    if prior_date is None:
        matches = _newest(candidates)
        if matches:
            path = max(matches, key=os.path.getmtime)
            date = os.path.basename(path).replace("full_states_log_", "").replace(".json", "")
    else:
        for root in candidates:
            p = os.path.join(root, f"full_states_log_{prior_date}.json")
            if os.path.exists(p):
                path = p
                date = prior_date
                break

    state = None
    if path and os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                state = json.load(fh)
        except (OSError, ValueError):
            state = None

    decision_md = ""
    decision_path = os.path.join(report_dir, "5_portfolio", "decision.md")
    if os.path.exists(decision_path):
        try:
            with open(decision_path, encoding="utf-8") as fh:
                decision_md = fh.read()
        except OSError:
            decision_md = ""

    return {
        "state": state,
        "decision_md": decision_md,
        "ticker": ticker_from_dir or (state.get("company_of_interest", "") if state else ""),
        "date": date or (state.get("trade_date", "") if state else ""),
        "log_path": path,
    }


def parse_planned_levels(state: dict | None, decision_md: str = "") -> dict:
    """Extract the prior plan's entry/stop levels for the gap read.

    Reads the TraderProposal markdown stored in ``full_states_log``
    (``trader_investment_decision`` — ``**Entry Price**: X`` / ``**Stop Loss**: Y``),
    then falls back to the PM decision / ``position_contract`` overlay string
    (``stop <n>``) when the trader levels are absent. Returns
    ``{"entry", "stop"}`` (both may be None — the gap read then degrades to
    magnitude-only, never fabricated).
    """
    import re

    def _num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    text = decision_md or ""
    trader = (state or {}).get("trader_investment_decision") or ""
    overlay = (state or {}).get("strategy_overlays") or {}
    contract = overlay.get("position_contract") if isinstance(overlay, dict) else None
    if isinstance(contract, str):
        text = f"{text}\n{contract}"
    elif isinstance(contract, dict):
        text = f"{text}\n{contract.get('text', '')}"
    if trader:
        text = f"{trader}\n{text}"

    entry = None
    m = re.search(r"\*?\*Entry Price\*?\*?[:\s]*([0-9.]+)", text, re.IGNORECASE)
    if m:
        entry = _num(m.group(1))
    stop = None
    m = re.search(r"\*?\*Stop Loss\*?\*?[:\s]*([0-9.]+)", text, re.IGNORECASE)
    if m:
        stop = _num(m.group(1))
    if stop is None:
        m = re.search(r"\bstop[:\s]*([0-9.]+)", text, re.IGNORECASE)
        if m:
            stop = _num(m.group(1))
    return {"entry": entry, "stop": stop}


# ---------------------------------------------------------------------------
# Paper-book ledger (feature 3): measure the reviewer, don't just run it
# ---------------------------------------------------------------------------


def record_review(
    ledger_path: str,
    *,
    ticker: str,
    prior_date: str,
    trade_date: str,
    verdict: str,
    reasons: list[str],
    gap_pct: float | None = None,
    catalyst_verdict: str | None = None,
    prior_close: float | None = None,
) -> None:
    """Append one pre-market review row to the paper-book ledger (JSONL).

    Each row mirrors the memory-log pending pattern: the ``realized_return``
    field starts None and is filled by :func:`resolve_ledger` on a later run
    (measured open vs prior close), so the reviewer's CONFIRM/REVISE/REJECT
    track record is measurable — not a feel-good toggle.
    """
    import json
    import os

    os.makedirs(os.path.dirname(os.path.abspath(ledger_path)), exist_ok=True)
    row = {
        "ticker": ticker,
        "prior_date": prior_date,
        "trade_date": trade_date,
        "verdict": verdict,
        "reasons": reasons or [],
        "gap_pct": gap_pct,
        "prior_close": prior_close,
        "catalyst_verdict": catalyst_verdict,
        "realized_return": None,
    }
    with open(ledger_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def resolve_ledger(ledger_path: str, ticker: str, trade_date: str, open_price: float | None) -> int:
    """Resolve pending reviews for ``ticker`` with a fresh measured price.

    Sets ``realized_return = (open_price - prior_close)/prior_close`` on every
    pending (``realized_return is None``) row for the ticker, rewriting the
    ledger atomically. Returns how many rows were resolved. ``prior_close`` is
    taken from the row's own ``gap_pct`` + stored trade date (we store the
    prior close implicitly via the gap and the review open; the realized return
    is the open move vs the review's prior close). If the row has no ``gap_pct``
    the realized return is None (nothing to measure).

    This is intentionally cheap and side-effect-light — it makes the paper book
    a time series, matching the memory-log's pending→resolve loop.
    """
    import json
    import os

    if not os.path.exists(ledger_path):
        return 0
    rows = []
    with open(ledger_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    n_resolved = 0
    for row in rows:
        if row.get("ticker") != ticker or row.get("realized_return") is not None:
            continue
        if open_price is None:
            continue
        prior_close = row.get("prior_close")
        if prior_close is None and row.get("gap_pct") is not None:
            # Legacy rows (written before prior_close was stored): gap-derived
            # approximation; NEW rows carry the true prior close so the measured
            # open actually moves the realized return (not circular).
            gap = row.get("gap_pct")
            prior_close = open_price / (1.0 + gap) if (1.0 + gap) else None
        if prior_close and float(prior_close) > 0:
            row["realized_return"] = round((open_price - prior_close) / prior_close, 6)
            row["resolved_date"] = trade_date
            n_resolved += 1
    # rewrite atomically
    tmp = ledger_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    os.replace(tmp, ledger_path)
    return n_resolved


def ledger_track_record(
    ledger_path: str,
    direction: str | None = None,
) -> dict:
    """Measured track record of the paper-book reviewer from resolved rows.

    Item 4 (paper-trading ledger): turns the pending→resolved pre-market ledger
    into a measurable win rate / avg return time series, matching how a firm
    would grade a strategy on paper before risking money.

    ``direction`` optionally filters to rows whose verdict matches a directional
    read ('CONFIRM' vs 'REVISE'/'REJECT'); None measures all resolved rows.
    Returns ``{count, resolved, wins, losses, win_rate, avg_realized, sum_realized}``
    where a 'win' is a positive realized return on a CONFIRM (or the absence of
    a through-stop gap), and a negative return is a loss. All None/0 when no
    rows are resolved (never fabricated).
    """
    import json
    import os

    if not os.path.exists(ledger_path):
        return {"count": 0, "resolved": 0, "wins": 0, "losses": 0,
                "win_rate": None, "avg_realized": None, "sum_realized": None}
    rows = []
    with open(ledger_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    realized = []
    for row in rows:
        if row.get("realized_return") is None:
            continue
        if direction and str(row.get("verdict", "")).upper() != direction.upper():
            continue
        realized.append(float(row["realized_return"]))
    if not realized:
        return {"count": len(rows), "resolved": len(realized), "wins": 0, "losses": 0,
                "win_rate": None, "avg_realized": None, "sum_realized": None}
    wins = sum(1 for r in realized if r > 0)
    losses = sum(1 for r in realized if r < 0)
    return {
        "count": len(rows),
        "resolved": len(realized),
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins / len(realized), 4),
        "avg_realized": round(sum(realized) / len(realized), 6),
        "sum_realized": round(sum(realized), 6),
    }

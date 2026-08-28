"""B2 - Trade plan card: pre-written plan for a value-dip / swing entry.

Institutions manage trades off a *written plan made before entry*, not
improvisation: defined risk %, a single unified invalidation/stop, tiered
partial exits at structure/R, a breakeven rule (after confirmation, not too
early), one trailing method, and a journal with plan-adherence scoring.

This module turns the project's existing computed pieces (the value-dip setup
rows, the tranche plan, exits) into ONE markdown "plan card" that the Trader,
Portfolio Manager and the 3 risk debators read pre-decision (injected into
their prompts) and that is appended to the report. It is pure and
deterministic - the LLMs argue over it, never create it.

Everything is advisory: the card reports measured numbers or explicit
'unavailable', and never blocks a decision by itself (hard gating stays in
the risk governor / strict value-dip flags).
"""

from __future__ import annotations


def _pct(v) -> str:
    if v is None:
        return "unavailable"
    try:
        return f"{float(v):.1%}"
    except (TypeError, ValueError):
        return str(v)


def _num(v, nd: int = 2) -> str:
    if v is None:
        return "unavailable"
    try:
        return f"{float(v):.{nd}f}"
    except (TypeError, ValueError):
        return str(v)


def build_trade_plan(
    *,
    ticker: str,
    price: float | None = None,
    setup: dict | None = None,
    tranche: dict | None = None,
    be_rule: dict | None = None,
    targets: dict | None = None,
    trail: dict | None = None,
    config: dict | None = None,
) -> str:
    """Build the markdown plan card from the measured pieces.

    Args (all optional - missing rows render as 'unavailable', never invented):
        ticker   - symbol being planned.
        price    - reference price (last close / signal price).
        setup    - ``value_dip_setup`` result (rows: value_floor,
                   technical_entry, trade_risk, balance_sheet, profitability,
                   regime_gate, re_rating, vdu, ...).
        tranche  - ``tranche_plan`` result (P1/P2/P3, stop, avg_entry, shares,
                   capital_at_risk, targets).
        be_rule  - ``exits.breakeven_after_confirmation`` result.
        targets  - ``swing.targets_rr`` result OR ``tranche_plan['targets']``.
        trail    - ``swing.trail_ema`` / ``chandelier_exit`` result.
        config   - settings (``min_holding_days``, ``max_trades_per_period``,
                   ``stop_never_widen``).
    """
    cfg = config or {}
    stop_never_widen = bool(cfg.get("stop_never_widen", True))
    breakeven_trigger = str(cfg.get("breakeven_trigger", "structure"))
    lines = [f"### Trade plan card: {ticker}", ""]
    lines.append(f"- Reference price: {_num(price)}")
    # Unified stop + invalidation (the single most important line).
    stop = (tranche or {}).get("stop")
    lines.append(
        f"- **Unified stop (invalidation): {_num(stop)}** - never widened "
        f"(policy: {'stop_never_widen=ON' if stop_never_widen else 'off'})"
    )
    # Setup rows (advisory, measured).
    if setup:
        rows = setup.get("rows") or {}
        for key, label in (
            ("value_floor", "Value floor"),
            ("technical_entry", "Technical entry"),
            ("trade_risk", "Trade risk"),
            ("balance_sheet", "Balance sheet"),
            ("profitability", "Profitability"),
            ("regime_gate", "Regime gate"),
            ("re_rating", "Re-rating catalyst"),
            ("vdu", "VDU ladder"),
        ):
            r = rows.get(key) or {}
            if key == "vdu":
                val = "unavailable" if not r else f"candidate={r.get('candidate')}"
                lines.append(f"- {label}: {val}")
            else:
                lines.append(f"- {label}: pass={r.get('pass')}")
    # Tranche execution.
    if tranche:
        t = tranche.get("targets") or {}
        lines.extend(
            [
                "- Tranche execution: "
                f"P1 {_num(tranche.get('p1'))} / P2 {_num(tranche.get('p2'))} / "
                f"P3 {_num(tranche.get('p3'))}; weights {tranche.get('weights')}",
                f"- Weighted avg entry: {_num(tranche.get('avg_entry'))}; "
                f"risk/share {_num(tranche.get('risk_per_share'))}",
                f"- Shares: {tranche.get('total_shares')} "
                f"(n={tranche.get('shares')}); capital-at-risk "
                f"{_pct(tranche.get('capital_at_risk_pct'))} of account, "
                f"peak-deployed {_pct(tranche.get('peak_deployed_pct'))}",
            ]
        )
    else:
        lines.append("- Tranche execution: unavailable")
    # Tiers + BE + trail.
    if targets and targets.get("t1") is not None:
        lines.append(f"- Tiers: T1 {_num(targets.get('t1'))} / T2 {_num(targets.get('t2'))}")
    elif tranche and (tranche.get("targets") or {}).get("t1") is not None:
        t = tranche["targets"]
        lines.append(f"- Tiers: T1 {_num(t.get('t1'))} (1.8R) / T2 {_num(t.get('t2'))} (3.0R)")
    else:
        lines.append("- Tiers: unavailable")
    lines.append(
        f"- Breakeven rule ({breakeven_trigger}): "
        f"price {_num((be_rule or {}).get('price'))} "
        f"(source: {(be_rule or {}).get('source') or 'unavailable'})"
    )
    lines.append(
        "- Trail remainder: EMA(20) close-through exit / chandelier "
        f"{'available' if (trail and trail.get('exit') is not None) else 'unavailable'}"
    )
    # Adherence checklist (the journal score inputs).
    lines.append(
        "- Adherence checklist: (1) entry only at tranche levels; "
        "(2) unified stop NEVER widened; "
        "(3) BE moved only after confirmation; "
        "(4) partial 50% at T1; "
        "(5) trail the remainder; "
        "(6) re-check overnight (pre-market review before acting)."
    )
    return "\n".join(lines)


__all__ = ["build_trade_plan"]

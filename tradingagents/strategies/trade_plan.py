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

import contextlib

from tradingagents.strategies.entry_ceiling import CEILING_SOURCES, entry_ceiling
from tradingagents.strategies.entry_target import ANCHOR_SOURCES, entry_target
from tradingagents.strategies.execution_price import COST_SOURCES, execution_price


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
    valuation_ceiling: float | None = None,
    expected_return_ceiling: float | None = None,
    rr_ceiling: float | None = None,
    valuation_price: float | None = None,
    technical_price: float | None = None,
    tranche_price: float | None = None,
    execution_spread: float | None = None,
    execution_impact: float | None = None,
    execution_slippage: float | None = None,
    liquidity_status: str | None = None,
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
        valuation_ceiling / expected_return_ceiling / rr_ceiling - the entry
                   ceiling sources (advisory): the price above which that
                   construct's economics fail. Whichever is absent simply
                   shrinks the ceiling's coverage; none of them is ever
                   defaulted to the current price.
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
    # Entry ceiling (advisory): the hard maximum price for this long, and the
    # upper bound the unified stop is the lower bound of. A source that could
    # not be measured shrinks coverage rather than being defaulted; with none
    # available the ceiling reads 'unavailable', never the current price.
    ceiling = entry_ceiling(
        price=price,
        valuation_ceiling=valuation_ceiling,
        expected_return_ceiling=expected_return_ceiling,
        rr_ceiling=rr_ceiling,
    )
    coverage = f"{ceiling['coverage']}/{len(CEILING_SOURCES)}"
    if ceiling["value"] is None:
        lines.append(
            f"- Entry ceiling (advisory): unavailable - status "
            f"{ceiling['status']} (coverage {coverage}); {ceiling['reason']}"
        )
    else:
        missing = (
            f"; missing: {', '.join(ceiling['missing_sources'])}"
            if ceiling["missing_sources"]
            else ""
        )
        lines.append(
            f"- Entry ceiling (advisory): {_num(ceiling['value'])} - status "
            f"{ceiling['status']} (binding: {ceiling['binding_source']}; "
            f"coverage {coverage}{missing})"
        )
        lines.append(
            f"- Ceiling headroom: distance {_pct(ceiling['ceiling_distance'])} "
            f"| margin {_pct(ceiling['ceiling_margin'])}"
        )
    # Target entry (advisory): §100's P_entry,target over the PRICE anchors
    # that exist. The score-weighted blend is deliberately NOT implemented -
    # our engines emit 0-100 scores, not prices, and no calibrated
    # score -> price bridge exists (the owner's Phase-2 decision), so the
    # regime/risk adjustment terms stay absent rather than invented.
    target = entry_target(
        valuation_price=valuation_price,
        technical_price=technical_price,
        tranche_price=tranche_price,
    )
    target_coverage = f"{target['coverage']}/{len(ANCHOR_SOURCES)}"
    if target["value"] is None:
        lines.append(
            f"- Target entry (advisory): unavailable - status {target['status']} "
            f"(coverage {target_coverage}); {target['reason']}"
        )
    else:
        lines.append(
            f"- Target entry (advisory): {_num(target['value'])} - status "
            f"{target['status']} (anchors: {', '.join(target['available_sources'])}; "
            f"coverage {target_coverage}; adjustments missing: "
            f"{', '.join(target['adjustments_missing'])})"
        )
    # Execution cost (advisory, §74-§78): rendered only when a caller measured
    # at least one cost term - a price-only card has nothing to say here, and
    # a zero buffer would read as a free trade. Liquidity is the caller's
    # verdict (`liquidity_risk.liquidity_verdict`), never re-derived here.
    if any(v is not None for v in (execution_spread, execution_impact, execution_slippage)):
        execution = execution_price(
            price=price,
            spread=execution_spread,
            impact=execution_impact,
            slippage=execution_slippage,
            liquidity_status=liquidity_status,
        )
        if execution["buffer"] is None:
            lines.append(f"- Execution cost (advisory): unavailable - {execution['reason']}")
        else:
            liquidity_note = (
                f"; liquidity: {execution['liquidity_status']}"
                if execution["liquidity_status"] else ""
            )
            lines.append(
                f"- Execution cost (advisory): buffer {_pct(execution['buffer_fraction'])} "
                f"({_num(execution['buffer'])}) -> execution price "
                f"{_num(execution['execution_price'])} (terms: "
                f"{', '.join(execution['available_sources'])}; coverage "
                f"{execution['coverage']}/{len(COST_SOURCES)}{liquidity_note})"
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


def measured_inputs(closes, config: dict | None = None) -> dict:
    """The plan pieces measurable from the close series alone.

    ``build_trade_plan`` renders whatever it is handed and prints
    "unavailable" for the rest, so call sites that hold prices but no
    statement data were passing nothing and the card degenerated into a wall
    of "unavailable" on every run. This builds what *is* measured - the same
    tranche read the risk fold uses (last close = P1, ATR-14), its targets,
    the breakeven rule off that tranche's stop, and the trailing EMA read -
    from ONE implementation so both call sites agree.

    ``setup`` is deliberately absent: its rows come from the statement /
    valuation path, so a price-only caller leaves them out rather than
    inventing rows. Returns ``{}`` when the tranche read is unusable.
    """
    cfg = config or {}
    if not closes:
        return {}
    from tradingagents.strategies.exits import breakeven_after_confirmation
    from tradingagents.strategies.swing import trail_ema
    from tradingagents.strategies.value_dip import tranche_risk_read

    read = tranche_risk_read(
        closes,
        weights=tuple(cfg.get("tranche_weights") or (0.3, 0.3, 0.4)),
        stop_mult=float(cfg.get("tranche_stop_mult", 1.5)),
        risk_pct=float(cfg.get("tranche_risk_pct", 0.015)),
        account=float(cfg.get("tranche_account", 100_000.0)),
    )
    if not read.get("valid"):
        return {}
    out: dict = {
        "tranche": read,
        "targets": read.get("targets"),
        # §100 price anchor: the tranche's own measured entry.
        "tranche_price": read.get("avg_entry"),
    }
    # Entry-ceiling R:R term: the highest entry at which the tranche's own
    # target still pays the configured minimum R:R given its stop. Solving
    # (T - E) / (E - S) = R for E gives E = (T + R*S) / (1 + R). A row that
    # cannot be measured is simply absent, which shrinks the ceiling's
    # coverage - it never becomes a zero ceiling.
    with contextlib.suppress(Exception):
        stop_px = read.get("stop")
        t1 = (read.get("targets") or {}).get("t1")
        min_rr = float(cfg.get("min_rr", 2.0))
        if stop_px is not None and t1 is not None and min_rr > 0.0:
            s, t = float(stop_px), float(t1)
            if t > s > 0.0:
                out["rr_ceiling"] = (t + min_rr * s) / (1.0 + min_rr)
    # The BE row and the trail are single rows of the card: a failure there
    # must not hide the tranche numbers.
    with contextlib.suppress(Exception):
        out["be_rule"] = breakeven_after_confirmation(
            entry_price=float(read["avg_entry"]),
            stop_price=float(read["stop"]) if read.get("stop") is not None else None,
            trigger=str(cfg.get("breakeven_trigger", "structure")),
        )
    with contextlib.suppress(Exception):
        trail = trail_ema(closes)
        if trail:
            out["trail"] = trail
    return out


__all__ = ["build_trade_plan", "measured_inputs"]

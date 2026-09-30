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

It carries **§103's ENTRY and EXIT blocks whole**: the entry side assembles
``entry_exit_price``'s members (§100's ``final_entry_price`` = the ``min`` over
the ceiling terms actually present, naming the binding one) and the exit side
renders the §101 predicate - every decidable exit evaluated, the first to fire
in ``EXIT_PRECEDENCE``, and the ones that could not be measured named as
absent. So the agents read the entry price AND the exit price from one card
instead of inventing either.

Everything is advisory: the card reports measured numbers or explicit
'unavailable', and never blocks a decision by itself (hard gating stays in
the risk governor / strict value-dip flags).
"""

from __future__ import annotations

import contextlib

from tradingagents.strategies.entry_ceiling import CEILING_SOURCES, entry_ceiling
from tradingagents.strategies.entry_exit_price import entry_exit_price
from tradingagents.strategies.entry_target import ANCHOR_SOURCES, entry_target
from tradingagents.strategies.execution_price import COST_SOURCES, execution_price
from tradingagents.strategies.risk_entry import risk_adjusted_entry
from tradingagents.strategies.stop_mae import mae_stop_distance


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
    max_stop_fraction: float | None = None,
    name_cvar: float | None = None,
    cvar_budget: float | None = None,
    mae_samples=None,
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
                   Its final tier (T2, else T1) is the §103 EXIT block's price
                   target.
        trail    - ``swing.trail_ema`` / ``chandelier_exit`` result. Its own
                   level (``ema`` / ``chandelier``) is the §103 EXIT block's
                   ``trailing_stop``.
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
    # §103 assembly + §100's final = min(target, max) over the terms actually
    # present. Execution is deliberately NOT a member of that min: §102 lists
    # it, but a cost adjustment is not an independent economic ceiling, and
    # §100 itself applies the buffer before the min - inside the min would
    # double-count it.
    # §101's exit inputs that this card can actually MEASURE: the trailing
    # level (the trail read's own price - EMA20 close-through, or the
    # chandelier) and the plan's final tier as the price target. The other four
    # of the six (risk_gate / thesis_break / time_exit / expected_value) are not
    # decidable at plan time and stay ABSENT, which shrinks `coverage` rather
    # than reading as "no exit".
    trail_level = trail_source = None
    if isinstance(trail, dict):
        for _key, _label in (("ema", "EMA20"), ("chandelier", "chandelier")):
            if trail.get(_key) is not None:
                trail_level, trail_source = trail[_key], _label
                break
    _tiers = targets or (tranche or {}).get("targets") or {}
    if _tiers.get("t2") is not None:
        exit_target, exit_target_basis = _tiers["t2"], "T2"
    elif _tiers.get("t1") is not None:
        exit_target, exit_target_basis = _tiers["t1"], "T1"
    else:
        exit_target = exit_target_basis = None

    assembled = entry_exit_price(
        price=price,
        valuation_ceiling=valuation_ceiling,
        expected_return_ceiling=expected_return_ceiling,
        rr_ceiling=rr_ceiling,
        valuation_price=valuation_price,
        technical_price=technical_price,
        tranche_price=tranche_price,
        stop=stop,
        max_stop_fraction=max_stop_fraction,
        name_cvar=name_cvar,
        cvar_budget=cvar_budget,
        execution_spread=execution_spread,
        execution_impact=execution_impact,
        execution_slippage=execution_slippage,
        liquidity_status=liquidity_status,
        trailing_stop=trail_level,
        target=exit_target,
    )
    final_entry = assembled["entry"]
    exit_block = assembled["exit"]
    if final_entry["final_entry_price"] is not None:
        _basis = "; ".join(
            f"{_t}={_num(_v)}"
            for _t, _v in sorted(final_entry["final_entry_basis"].items())
        )
        lines.append(
            f"- **Final entry price (advisory, §100): "
            f"{_num(final_entry['final_entry_price'])}** - min of "
            f"{final_entry['final_entry_binding']} over the §103 terms present "
            f"({_basis})"
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
f"- Execution cost (advisory, §74-§78): buffer {_pct(execution['buffer_fraction'])} "
                f"({_num(execution['buffer'])}) -> execution price "
                f"{_num(execution['execution_price'])} (= §103 "
                f"liquidity_adjusted_entry_price; terms: "
                f"{', '.join(execution['available_sources'])}; coverage "
                f"{execution['coverage']}/{len(COST_SOURCES)}{liquidity_note})"
            )
    # Risk-adjusted max entry (advisory, §68): the highest entry at which the
    # unified stop is still inside `max_stop_fraction` of it. The CVaR half is
    # a STATUS, never a price - a name over the book's budget cannot be
    # entered at any price, and folding that into a number would misstate it.
    if stop is not None and max_stop_fraction is not None:
        risk_entry = risk_adjusted_entry(
            stop=stop,
            max_stop_fraction=max_stop_fraction,
            name_cvar=name_cvar,
            cvar_budget=cvar_budget,
        )
        if risk_entry["value"] is not None:
            lines.append(
                f"- Risk-adjusted max entry (advisory): {_num(risk_entry['value'])} "
                f"(stop within {_pct(risk_entry['stop_fraction'])}; CVaR: "
                f"{risk_entry['cvar_status']})"
            )
    # Measured stop (advisory, §93): the stop distance the MAE distribution of
    # past closed decisions implies. Rendered only when the sample clears the
    # floor - below it the read is a count, not a distance, and a default
    # distance would be a constant standing in for a measurement.
    if mae_samples:
        mae = mae_stop_distance(mae_samples)
        if mae["status"] == "OK":
            lines.append(
                f"- Measured stop (advisory, §93): {_pct(mae['stop_fraction'])} of "
                f"entry at the {_pct(mae['quantile'])} MAE quantile "
                f"(n={mae['sample']}; median MAE {_pct(mae['median'])})"
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
    # §103's EXIT block (§101): the six independent exits, every decidable one
    # evaluated at the reference price, the first to fire in EXIT_PRECEDENCE
    # naming the exit. A condition that could not be evaluated is rendered as
    # ABSENT - never as "no exit" (exits.exit_decision's own contract), so a
    # reader can tell a measured no-exit from an unmeasured one. The Trader and
    # the PM argue the exit from this row.
    _cond = exit_block["conditions"]
    _levels = []
    if stop is not None:
        _levels.append(f"stop_loss {_num(stop)}")
    if trail_level is not None:
        _levels.append(f"trailing_stop {_num(trail_level)} ({trail_source})")
    if exit_target is not None:
        _levels.append(f"target {_num(exit_target)} ({exit_target_basis})")
    if exit_block["exit"] is True:
        _pred = f"FIRES - {exit_block['reason']} at exit price {_num(exit_block['exit_price'])}"
    elif exit_block["exit"] is False:
        _pred = f"no exit condition fired at {_num(price)}"
    else:
        _pred = "no exit condition could be evaluated"
    lines.append(
        f"- §103 exit predicate (advisory, §101): {_pred} - evaluated: "
        + ("; ".join(f"{_k}={_v}" for _k, _v in _cond.items()) if _cond else "none")
        + f" (coverage {exit_block['coverage']}/{len(exit_block['precedence'])})"
    )
    lines.append(
        "- §103 exit levels: "
        + (" / ".join(_levels) if _levels else "unavailable")
        + " (precedence: "
        + " > ".join(exit_block["precedence"])
        + ")"
    )
    _absent = [n for n in exit_block["precedence"] if n not in _cond]
    if _absent:
        lines.append(
            "- §103 exits not measurable at plan time (absent, NOT 'no exit'): "
            + ", ".join(_absent)
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
        # §68 risk rule: the largest per-share risk the sizing will accept, as
        # a fraction of the entry. A config value only - the CVaR half comes
        # from the risk path, not from the closes.
        "max_stop_fraction": cfg.get("max_stop_fraction"),
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

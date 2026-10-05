"""Structured thesis falsification + auto-monitor (W3-7, Gemini falsification
schema).

A decision's bull/bear thesis is bound to EXPLICIT, numeric falsification
conditions: {metric, operator, invalidation_level, current_level,
lookback_window, thesis_impact}. These are stored per decision and then
monitored on subsequent closes: when a condition's current level breaches its
invalidation level, the thesis is marked INVALIDATED and an invalidation row
is appended to the persistent invalidation ledger.

- ``FalsificationCondition`` — a pydantic-ish dataclass with validation.
- ``check_breached`` — evaluate one condition against a current value.
- ``monitor_conditions`` — given a metrics snapshot, return which conditions
  breached (each with its impact).

Deterministic + advisory: it detects and records a thesis invalidation; it
does not by itself cancel anything (the execution layer consumes the breach
as a reference).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FalsificationCondition:
    metric_name: str
    threshold_operator: str          # < | <= | > | >= | outside_band
    invalidation_level: float
    current_level: float | None = None
    lookback_window_days: int = 0
    thesis_impact: str = "soften_to_neutral"  # terminal_exit | soften_to_neutral | reduce_position_size

    def __post_init__(self):
        if self.threshold_operator not in ("<", "<=", ">", ">=", "outside_band"):
            raise ValueError(f"bad operator {self.threshold_operator}")


def check_breached(cond: FalsificationCondition, value: float | None) -> bool:
    """True when ``value`` violates the condition's invalidation level."""
    if value is None:
        return False
    op = cond.threshold_operator
    if op == "<":
        return value < cond.invalidation_level
    if op == "<=":
        return value <= cond.invalidation_level
    if op == ">":
        return value > cond.invalidation_level
    if op == ">=":
        return value >= cond.invalidation_level
    if op == "outside_band":
        return abs(value - cond.invalidation_level) > 0  # band = single level
    return False


def monitor_conditions(conditions: list[FalsificationCondition],
                       metrics: dict,
                       *, ticker: str | None = None,
                       date: str | None = None,
                       results_dir: str | None = None,
                       config: dict | None = None) -> list[dict]:
    """Return the breached conditions against a ``metrics`` snapshot.

    Each result: {metric, operator, invalidation, current, impact, breached}.

    When ``ticker`` and ``date`` are supplied this is the full auto-monitor
    step (W3-7 + W4-7): every breach is RECORDED to the invalidation ledger
    (``record_breaches``) and ALERTED (``monitor.notify``). Both are advisory
    and silent when unconfigured - detection never depends on them.
    """
    out = []
    for c in conditions:
        val = metrics.get(c.metric_name) if isinstance(metrics, dict) else None
        breached = check_breached(c, val)
        out.append({
            "metric": c.metric_name,
            "operator": c.threshold_operator,
            "invalidation_level": c.invalidation_level,
            "current_level": val,
            "impact": c.thesis_impact,
            "breached": breached,
        })
    if ticker and date:
        breached_rows = record_breaches(out, ticker, date, results_dir)
        from tradingagents.strategies.monitor import notify

        for b in breached_rows:
            notify(
                "falsification",
                f"{ticker} {b['metric']} {b['operator']} "
                f"{b['invalidation_level']:g} breached "
                f"(now {b['current_level']:g}) impact={b['impact']}",
                config,
            )
    return out


def evaluate_debate_claims(bull_conditions: list[FalsificationCondition],
                          bear_conditions: list[FalsificationCondition],
                          computed_metrics: dict) -> dict:
    """Judge-side grounding + auto-rejection (W4-3): every falsification
    condition must cite a metric present in the deterministic computed set,
    and a thesis whose CURRENT level already breaches its own condition is
    rejected on arrival (''REJECT_INVALIDATED_THESIS''). Returns a verdict
    dict with per-side analysis — advisory, feeds the judge's scoring."""
    issues: list[str] = []
    for side, conds in (("bull", bull_conditions), ("bear", bear_conditions)):
        if not conds:
            issues.append(f"{side}: no falsification conditions (unfalsifiable thesis)")
        # ONE producer for the breach map: `monitor_conditions` evaluates each
        # condition and the judge reads its rows rather than re-calling
        # `check_breached` here - the two agreed by construction, which is
        # exactly the drift a second call site eventually causes.
        for row in monitor_conditions(list(conds), computed_metrics or {}):
            if row["metric"] not in (computed_metrics or {}):
                issues.append(f"{side}: cites unverified metric '{row['metric']}'")
                continue
            if row["breached"]:
                issues.append(f"{side}: thesis ALREADY invalidated "
                              f"({row['metric']} {row['invalidation_level']:g})")
    return {
        "verdict": "REJECT_INVALIDATED_THESIS" if any(
            "ALREADY invalidated" in i for i in issues) else "PROCEED_TO_SCORING",
        "issues": issues,
        "bull_ok": not any(issues and i.startswith("bull") for i in issues),
        "bear_ok": not any(issues and i.startswith("bear") for i in issues),
    }


def record_breaches(breaches: list[dict], ticker: str, date: str,
                    results_dir: str | None = None) -> list[dict]:
    """Append the breached conditions to the persistent invalidation ledger
    (W3-7 -> invalidation_ledger): an advisory record that this thesis was
    invalidated on a later close. Returns the breached rows."""
    from tradingagents.strategies.invalidation_ledger import append as _append

    for b in breaches:
        if b.get("breached"):
            _append(
                ticker,
                [f"falsification:{b['metric']} {b['operator']} {b['invalidation_level']:g}"
                 f" breached (now {b['current_level']:g}) impact={b['impact']}"],
                date=date,
                note="monitored falsification condition breach (W3-7)",
                source="falsification_monitor",
                results_dir=results_dir,
            )
    return [b for b in breaches if b.get("breached")]


__all__ = ["FalsificationCondition", "check_breached", "monitor_conditions",
           "record_breaches"]

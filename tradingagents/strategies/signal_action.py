"""Security-signal vs portfolio-action split (advisory, pure, deterministic).

SKHY 2026-09-09 review-loop lesson (review #1/#21): a report ending in one
``HOLD`` label collapses two different truths - "the security is bullish"
(NVDA-class price action, momentum, thesis) and "the portfolio says no new
risk" (a drawdown / kill switch / liquidity veto). That buries useful security
signal under a portfolio veto, or lets a gate-blocked stock read as "meh".

``signal_action_split`` keeps the two dimensions separate and derives a
combined action WITHOUT ever letting the gate upgrade a signal: the gate can
only downgrade (or, on a kill switch, force EXIT/NO_TRADE). Advisory - the
composed risk gate keeps its own hard authority elsewhere; this module only
renders the split for humans / decision.json.

Never a hard gate. Every input degrades to an explicit n/a; partial reads
are labeled. The combined action is a *recommendation* for the report/JSON,
never enforced here.
"""

from __future__ import annotations

__all__ = ["signal_action_split", "portfolio_action_from_gate"]

# Security-level signal: what the analysis says the security is doing. This is
# the PRE-portfolio verdict (analyst/debate/PM stance before the gate).
SECURITY_SIGNALS = {
    "STRONG_BUY", "BUY", "BUY_ON_PULLBACK", "OVERWEIGHT", "ACCUMULATE",
    "NEUTRAL", "HOLD", "UNDERWEIGHT", "REDUCE", "SELL", "STRONG_SELL",
}

# Portfolio-level instruction: what the risk layer lets you do.
PORTFOLIO_ACTIONS = {
    "TRADE_ALLOWED",    # gate open; signal intact
    "SCALE_DOWN",        # gate WARN: halve / reduce recommended size
    "HOLD",              # no new risk, keep existing
    "NO_NEW_RISK",       # gate REJECT (portfolio/drawdown): no addition
    "REDUCE",            # gate REJECT (trade/capital): trim existing
    "EXIT",              # kill switch / hard risk: exit held position
    "NO_TRADE",          # kill switch: nothing may open
}

def _has_reason(reasons: list[str] | tuple[str, ...] | None, *needles: str) -> bool:
    joined = " ".join(r.lower() for r in (reasons or ()))
    return any(nd in joined for nd in needles)


def portfolio_action_from_gate(
    verdict: str | None,
    reasons: list[str] | tuple[str, ...] | None = (),
    kill_switch: bool = False,
) -> str:
    """Map a composed-risk-gate verdict (PASS/WARN/REJECT) to the portfolio
    instruction. Priority: kill > portfolio/drawdown > trade/capital >
    liquidity/data > WARN > PASS.
    """
    if kill_switch:
        return "NO_TRADE"
    v = str(verdict or "").upper()
    if v == "REJECT":
        if _has_reason(reasons, "kill", "halt", "hard"):
            return "NO_TRADE" if _has_reason(reasons, "new", "open", "add") else "EXIT"
        if _has_reason(reasons, "portfolio", "drawdown", "book", "hwm", "capital"):
            return "NO_NEW_RISK"
        if _has_reason(reasons, "trade", "tranche", "peak", "position"):
            return "REDUCE"
        if _has_reason(reasons, "liquidity", "illiquid", "data", "stale", "unknown"):
            return "HOLD"
        return "NO_NEW_RISK"  # default REJECT = no new risk
    if v == "WARN":
        return "SCALE_DOWN"
    return "TRADE_ALLOWED"  # PASS or gate-not-run


def _combine(signal: str, action: str, gated: bool) -> str:
    """Derive the human action from signal x action, never upgrading.

    The gate only downgrades: an open gate keeps the signal; any blocked gate
    yields a conservative portfolio action.
    """
    if not gated:
        return signal
    if action in ("EXIT", "NO_TRADE"):
        return "SELL" if signal in ("STRONG_BUY", "BUY", "OVERWEIGHT", "ACCUMULATE", "HOLD", "NEUTRAL") else signal
    if action == "NO_NEW_RISK":
        return "HOLD"
    if action == "REDUCE":
        return "REDUCE" if signal not in ("SELL", "STRONG_SELL") else signal
    if action == "SCALE_DOWN":
        return f"{signal} / SCALE_DOWN"
    if action == "HOLD":
        return "HOLD"
    return signal


def signal_action_split(
    security_signal: str | None,
    gate_verdict: str | None = "PASS",
    gate_reasons: list[str] | tuple[str, ...] | None = (),
    kill_switch: bool = False,
) -> dict:
    """Split a security's signal from the portfolio's gate action.

    Args:
        security_signal: the PRE-portfolio signal (STRONG_BUY..SELL); None when
            the analysis produced no verdict.
        gate_verdict: composed risk gate PASS/WARN/REJECT (None = gate not run).
        gate_reasons: the gate's reason list (for fine-grained mapping).
        kill_switch: True when the kill switch is active.

    Returns ``{security_signal, portfolio_action, combined_action, gated}``.
    ``gated`` = True when the portfolio layer restricts the signal (REJECT /
    kill / WARN).
    """
    sig = str(security_signal or "").upper()
    if sig and sig not in SECURITY_SIGNALS:
        sig = ""
    action = portfolio_action_from_gate(gate_verdict, gate_reasons, kill_switch)
    gated = action != "TRADE_ALLOWED"
    combined = (
        _combine(sig, action, gated) if sig
        else ("HOLD" if gated else None)
    )
    return {
        "security_signal": sig or None,
        "portfolio_action": action,
        "combined_action": combined,
        "gated": gated,
    }

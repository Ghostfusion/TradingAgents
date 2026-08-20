"""V5 - computed debate context builder.

Turns quantified inputs (normalized EBIT, valuation percentile, trap level,
margin of safety) into a compact, auditable snippet the analyst/PM prompts
can adopt - so the LLM argues *from numbers*, not around them.
"""

from __future__ import annotations


def build_computed_context(
    cfg: dict = None,
    *,
    nebit: float | None = None,
    ev_nebit: float | None = None,
    pe_hist_pct: float | None = None,
    trap: dict | None = None,
    margin: float | None = None,
    extra: list | None = None,
) -> str:
    """Render computed value inputs into a prompt snippet; empty when none."""
    cfg = cfg or {}
    parts = []
    if ev_nebit is not None:
        parts.append(f"EV/NEBit (normalized)={ev_nebit:.1f}x")
    if nebit is not None:
        parts.append(f"normalized EBIT={nebit:,.0f}")
    if pe_hist_pct is not None:
        parts.append(f"PE now vs 5y percentile={pe_hist_pct:.0%}")
    if margin is not None:
        parts.append(f"margin_of_safety={margin:+.0%}")
    if trap:
        parts.append(f"trap_risk={trap.get('level', 'n/a')}")
        if trap.get("evidence"):
            parts.append("evidence=" + "; ".join(trap["evidence"]))
    for e in extra or []:
        if e:
            parts.append(str(e))
    if not parts:
        return ""
    return "Computed context: " + " | ".join(parts)


__all__ = ["build_computed_context"]

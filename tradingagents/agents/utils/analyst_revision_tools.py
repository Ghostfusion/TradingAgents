"""Agent-facing tool for the S6 analyst revision index (MSCI recipe).

Docs: ``docs/design_quant_formulas_research_round3.md`` S6,
``docs/implementation_plan_quant_formula_additions_round3.md`` S6.

``get_analyst_revision_index`` wraps ``strategies/analyst_revisions.py`` over
the upgrade/downgrade counts ``dataflows/yfinance_sector.fetch_revision_actions``
already returns. Gated by ``enable_analyst_revision_index`` (default OFF): when
the flag is off the tool returns a clear DISABLED sentinel and never fabricates
a value. Every line names its basis - the weights, the denominator deviation
(``up + down`` vs MSCI's analyst-coverage denominator), the coverage count, and
the explicit ``unavailable`` reason when a leg is missing. Advisory: it informs
the analyst's read, it never gates a decision.
"""

from __future__ import annotations

from typing import Annotated

from langchain_core.tools import tool

__all__ = ["get_analyst_revision_index", "ANALYST_REVISION_TOOLS"]


def _flag(name: str, default: bool = False) -> bool:
    """Read an enable_* flag from the live config (never raises)."""
    try:
        from tradingagents.dataflows.config import get_config

        return bool((get_config() or {}).get(name, default))
    except Exception:  # noqa: BLE001 - a config read must never break a tool
        return default


def _disabled(tool_name: str, flag: str) -> str:
    return (
        f"{tool_name}: DISABLED (set {flag}=true / "
        f"TRADINGAGENTS_{flag.upper()}=true to enable). No value computed."
    )


@tool
def get_analyst_revision_index(
    ticker: Annotated[str, "ticker symbol"],
    current_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"],
) -> str:
    """Weighted, coverage-guarded analyst revision index (MSCI recipe, S6).

    Consumes the upgrade/downgrade action counts the engine already fetches and
    renders the weighted three-period revision ratio (weights 3/2/1, denominator
    ``up + down`` - a stated deviation from MSCI's analyst-coverage
    denominator), the coverage count (fewer than two actions returns
    ``unavailable`` - a single firm's spree must not move a score), and the
    estimate-change leg's explicit ``unavailable`` reason (the engine holds no
    3-4 quarter estimate-level history). The vendor serves one aggregate window,
    so the leading weight applies to it and the shortfall is printed. Cite the
    index before any 'analysts are revising up/down' claim; it informs the read,
    it never gates a decision (MSCI publishes no validation for the recipe).
    """
    if not _flag("enable_analyst_revision_index"):
        return _disabled("get_analyst_revision_index", "enable_analyst_revision_index")

    from tradingagents.strategies.analyst_revisions import revision_index

    try:
        from tradingagents.dataflows.yfinance_sector import fetch_revision_actions

        actions = fetch_revision_actions(ticker)
    except Exception as exc:  # noqa: BLE001
        return f"analyst revision index unavailable for {ticker}: source error ({exc})"

    if not actions:
        return (
            f"analyst revision index unavailable for {ticker}: no upgrade/downgrade "
            "actions returned by the source (yfinance upgrades_downgrades empty or "
            "failed)"
        )

    read = revision_index([actions])
    rr = read["legs"]["revision_ratio"]
    if rr is None:
        reason = (read.get("unavailable") or {}).get("revision_ratio") or "unavailable"
        return f"analyst revision index unavailable for {ticker}: {reason}"

    coverage = read.get("coverage")
    lines = [
        f"analyst revision index {ticker}: {rr:+.4f} (weighted upgrade/downgrade "
        "ratio; informs, never gates)",
        f"  coverage={coverage} action(s) up+down in the vendor window "
        "(>= 2 required - the feed has no per-analyst identity, so one firm's "
        "spree must not move a score)",
        "  denominator=up+down (deviation from MSCI's analyst-coverage "
        "denominator; the feed carries no per-analyst coverage counts)",
    ]
    for name, value in read["legs"].items():
        if value is None:
            lines.append(
                f"  {name}: unavailable ({read['unavailable'].get(name) or 'missing input'})"
            )
        else:
            lines.append(f"  {name}: {value:+.4f}")
    lines.append(
        "  basis: weights revision_ratio=(3, 2, 1) estimate_change=(9, 7, 5, 3); "
        "the vendor serves ONE aggregate window, so the leading weight (3) applies "
        "and the remaining periods are absent, not zero; the estimate-change leg "
        "needs a 3-4 quarter estimate-level history the engine does not hold."
    )
    lines.append(f"  {read['basis']}")
    return "\n".join(lines)


ANALYST_REVISION_TOOLS = [get_analyst_revision_index]

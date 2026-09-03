"""Typed graph state artifacts (W4-2, Gemini).

The research pipeline currently passes plain dicts (analyst reports, tool
dumps) down to Trader/Risk/PM, saturating context and inviting recency bias.
This defines the IMMUTABLE, schema-validated artifacts each layer should
emit, plus a pure ``summarize`` that compresses raw agent output into them.

Advisory + opt-in: nothing re-wires the existing graph; the artifacts exist
so a future typed-state cutover (or the bundle consumers) can hand the next
agent the STRUCTURED summary + computed levels only, never raw history.

Each artifact carries the fields a downstream agent actually needs:
- AnalystSummary: the analyst's conclusion + computed levels + data quality
- ResearchVerdict: bull/bear/judge conclusion + falsification conditions
- TradeProposal: entry/stop/targets/size + the computed reference levels
- RiskVerdict: gate verdict + reasons + CVaR/limits
- Decision: final rating + rationale + invalidation conditions
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AnalystSummary:
    role: str
    conclusion: str = ""
    computed_levels: dict = field(default_factory=dict)   # {metric: value}
    data_quality: str = "unknown"
    missing_fields: list[str] = field(default_factory=list)
    raw_tool_dump: bool = False   # True when the summary still embeds raw output

    def to_compact(self) -> dict:
        """The structure a downstream agent should RECEIVE (no raw text)."""
        return {"role": self.role, "conclusion": self.conclusion[:2000],
                "computed_levels": self.computed_levels,
                "data_quality": self.data_quality}


@dataclass
class ResearchVerdict:
    stance: str = ""                      # bullish | bearish | neutral
    score_bull: float | None = None
    score_bear: float | None = None
    falsification: list[dict] = field(default_factory=list)  # W4-3 conditions
    support_levels: dict = field(default_factory=dict)
    conclusion: str = ""

    def to_compact(self) -> dict:
        return {"stance": self.stance, "score_bull": self.score_bull,
                "score_bear": self.score_bear,
                "falsification": self.falsification,
                "support_levels": self.support_levels}


@dataclass
class TradeProposal:
    direction: str = ""                   # long | short | hold
    entry: float | None = None
    stop: float | None = None
    targets: list[float] = field(default_factory=list)
    position_size: float | None = None
    rationale: str = ""
    computed_levels: dict = field(default_factory=dict)

    def to_compact(self) -> dict:
        return {"direction": self.direction, "entry": self.entry,
                "stop": self.stop, "targets": self.targets,
                "position_size": self.position_size}


@dataclass
class RiskVerdict:
    verdict: str = "PASS"                 # PASS | WARN | REJECT
    reasons: list[str] = field(default_factory=list)
    cvar_pct: float | None = None
    size_cap: float | None = None
    risk_halt: bool = False

    def to_compact(self) -> dict:
        return {"verdict": self.verdict, "reasons": self.reasons,
                "cvar_pct": self.cvar_pct, "size_cap": self.size_cap,
                "risk_halt": self.risk_halt}


@dataclass
class Decision:
    rating: str = ""
    rationale: str = ""
    invalidation_conditions: list[str] = field(default_factory=list)
    data_quality: str = "unknown"
    guardrail_reason: str | None = None

    def to_compact(self) -> dict:
        return {"rating": self.rating, "invalidation_conditions": self.invalidation_conditions,
                "data_quality": self.data_quality, "guardrail_reason": self.guardrail_reason}


def summarize_report(report_text: str, role: str,
                     computed_levels: dict | None = None,
                     data_quality: str = "unknown") -> AnalystSummary:
    """Pure: package an analyst report + computed levels into a summary. The
    raw report is NOT forwarded downstream (only the conclusion head)."""
    conclusion = (report_text or "").strip().splitlines()[0][:500] if report_text else ""
    return AnalystSummary(role=role, conclusion=conclusion,
                          computed_levels=computed_levels or {},
                          data_quality=data_quality)


__all__ = ["AnalystSummary", "ResearchVerdict", "TradeProposal", "RiskVerdict",
           "Decision", "summarize_report"]

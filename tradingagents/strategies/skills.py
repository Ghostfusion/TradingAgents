"""Declarative strategy-skill overlays (DSA research §3.3, pillar 5).

Port of daily_stock_analysis's YAML strategy-skill DSL: a strategy is a
YAML file declaring ``name`` / ``instructions`` (natural language the LLM
can follow) plus optional metadata (``category``, ``core_rules``,
``required_tools``, ``market_regimes``, ``default_priority``,
``score_adjustments``). No code per skill — the loader + regime router are
pure and hermetic.

Regime-from-opinion: the market regime is derived from an EARLIER stage's
structured technical opinion (ma alignment + trend score), NOT a separate
model call — the DSA router pattern. Thresholds: bullish & trend >= 70 ->
"trending_up"; bearish & <= 30 -> "trending_down"; neutral 35..65 ->
"sideways"; undefined -> None (fail-open).

All adjustments are ADVISORY (bounded +/-20, folded behind
``enable_skill_overlays``, default off) — the hard overlay pipeline
(regime -> catalyst -> contract -> governor) is unchanged.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import yaml

_DEFAULT_SKILL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skills")

_ADJUSTMENT_CAP = 20.0


@dataclass
class StrategySkill:
    """One parsed strategy-skill YAML (validation + defaults applied)."""

    name: str
    display_name: str = ""
    description: str = ""
    category: str = "framework"
    core_rules: list[int] = field(default_factory=list)
    required_tools: list[str] = field(default_factory=list)
    market_regimes: list[str] = field(default_factory=list)
    default_priority: int = 100
    default_active: bool = False
    default_router: bool = False
    aliases: list[str] = field(default_factory=list)
    instructions: str = ""
    score_adjustments: dict[str, float] = field(default_factory=dict)

    @property
    def bounded_adjustments(self) -> dict[str, float]:
        """Score adjustments clamped to [-CAP, +CAP] (advisory-only)."""
        return {k: max(-_ADJUSTMENT_CAP, min(_ADJUSTMENT_CAP, float(v)))
                for k, v in self.score_adjustments.items() if isinstance(v, (int, float))}


def parse_skill(data: dict) -> StrategySkill | None:
    """Validate + build a skill from a YAML mapping; None on missing name."""
    name = str((data or {}).get("name") or "").strip()
    if not name:
        return None
    return StrategySkill(
        name=name,
        display_name=str(data.get("display_name") or name),
        description=str(data.get("description") or ""),
        category=str(data.get("category") or "framework"),
        core_rules=[int(r) for r in (data.get("core_rules") or [])],
        required_tools=[str(t) for t in (data.get("required_tools") or [])],
        market_regimes=[str(m) for m in (data.get("market_regimes") or data.get("market-regimes") or [])],
        default_priority=int(data.get("default_priority") or 100),
        default_active=bool(data.get("default_active") or False),
        default_router=bool(data.get("default_router") or False),
        aliases=[str(a) for a in (data.get("aliases") or [])],
        instructions=str(data.get("instructions") or ""),
        score_adjustments={k: float(v) for k, v in (data.get("score_adjustments") or {}).items()
                           if isinstance(v, (int, float))},
    )


def load_skills(skill_dir: str | None = None) -> dict[str, StrategySkill]:
    """Load every ``*.yaml`` in the skill dir (default: package skills/).

    Custom-dir override: when ``skill_dir`` is a real path it replaces the
    default set (DSA: custom overrides builtin by name). Hermetic + pure.
    """
    d = skill_dir or _DEFAULT_SKILL_DIR
    out: dict[str, StrategySkill] = {}
    if not os.path.isdir(d):
        return out
    for fname in sorted(os.listdir(d)):
        if not fname.endswith(".yaml") and not fname.endswith(".yml"):
            continue
        path = os.path.join(d, fname)
        try:
            with open(path, encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
        except (OSError, yaml.YAMLError):
            continue
        skill = parse_skill(data)
        if skill:
            out[skill.name] = skill
    return out


def regime_from_opinion(technical_opinion: dict | None) -> str | None:
    """Regime label from a structured technical opinion (no model call).

    ``technical_opinion`` carries ``ma_alignment`` ("bullish"/"bearish"/...)
    and ``trend_score`` (0-100). DSA thresholds: bullish & >= 70 ->
    trending_up; bearish & <= 30 -> trending_down; 35..65 -> sideways;
    anything unmeasurable -> None (fail-open).
    """
    if not technical_opinion:
        return None
    try:
        ts = technical_opinion.get("trend_score")
        if ts is None:
            return None
        trend = float(ts)
    except (TypeError, ValueError):
        return None
    alignment = str(technical_opinion.get("ma_alignment") or "").lower()
    if "bull" in alignment and trend >= 70:
        return "trending_up"
    if "bear" in alignment and trend <= 30:
        return "trending_down"
    if alignment in ("neutral", "mixed") or 35 <= trend <= 65:
        return "sideways"
    if "bull" in alignment or "bear" in alignment:
        # consistent but not at the extreme band -> moderate trend
        return "trending_up" if "bull" in alignment else "trending_down"
    return None


def select_skills(skills: dict[str, StrategySkill], regime: str | None,
                  requested: list[str] | None = None, max_count: int = 3) -> list[str]:
    """Router precedence (DSA): user-requested -> regime-matched ->
    priority-sorted default; capped at ``max_count``."""
    if not skills:
        return []
    if requested:
        hits = [s.name for s in skills.values() if s.name in requested or
                any(a in requested for a in s.aliases)]
        # plus any requested names that ARE skills
        for name in requested:
            if name in skills and name not in hits:
                hits.append(name)
        return hits[:max_count]
    if regime:
        matched = sorted(
            (s for s in skills.values() if regime in s.market_regimes),
            key=lambda s: (s.default_priority, s.name),
        )
        if matched:
            return [s.name for s in matched[:max_count]]
    defaults = sorted(
        (s for s in skills.values() if s.default_router or s.default_active),
        key=lambda s: (s.default_priority, s.name),
    )
    if not defaults:
        defaults = sorted(skills.values(), key=lambda s: (s.default_priority, s.name))
    return [s.name for s in defaults[:max_count]]


__all__ = [
    "StrategySkill",
    "parse_skill",
    "load_skills",
    "regime_from_opinion",
    "select_skills",
    "_DEFAULT_SKILL_DIR",
    "_ADJUSTMENT_CAP",
]

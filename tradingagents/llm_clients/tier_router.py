"""Hybrid model tier routing (W4-5, advisory).

Local/distilled models handle data-extraction + intermediate analyst work while
frontier models are reserved for synthesis (Research Manager / Risk Judge / PM).
This is a PURE resolver over the config — the live LLM factory keeps its own
hot path unchanged; enabling the tier just makes the router return the right
model per node so a future cutover (or a local proxy) can consume it.

Resolver is deterministic: given a node role and the configured
``llm_tier_map``, return the model + tier. Unconfigured -> None (=> the
factory's default path, bit-identical).
"""

from __future__ import annotations

# Default tier map: synthesis roles -> frontier, everything else -> fast/local.
_DEFAULT_TIER = {
    "frontier": ("research_manager", "risk_judge", "portfolio_manager", "pm"),
    "local": ("market_analyst", "sentiment_analyst", "news_analyst",
              "fundamentals_analyst", "bull_researcher", "bear_researcher",
              "trader", "aggressive", "conservative", "neutral"),
}


def resolve_tier(role: str, config: dict | None = None) -> dict:
    """Return {tier, model} for a node role; None when unconfigured.

    ``config`` may carry ``llm_tier_map`` = {"frontier": [roles...],
    "local": [roles...]} plus ``llm_tier_model`` = {"frontier": "gpt-5.5",
    "local": "deepseek-v4-mini"}. Falls back to the default mapping + a
    generic model ('' when none configured -> factory default).
    """
    cfg = config or {}
    tm = cfg.get("llm_tier_map") or _DEFAULT_TIER
    models = cfg.get("llm_tier_model") or {}
    role_l = str(role or "").lower()
    tier = "local"
    for t, roles in (("frontier", tm.get("frontier") or []),
                     ("local", tm.get("local") or [])):
        if role_l in [str(r).lower() for r in roles]:
            tier = t
            break
    model = models.get(tier)
    return {"tier": tier, "model": model}


__all__ = ["resolve_tier", "_DEFAULT_TIER"]

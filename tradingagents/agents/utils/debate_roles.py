"""P3 — Heterogeneous per-role LLM resolution + tool surfaces for the debate.

``resolve_role_llm`` rides the existing ``create_llm_client`` registry: a
``debate_*_model`` config value of ``"family:id"`` (or ``"provider:model"``)
creates a per-role client with the same tier kwargs as the quick/deep
clients; empty config falls back to the role's default (quick for
bull/bear, deep for judge). The dual-mode adapter handles providers that
cannot bind tools / structured output; ``resolve_role_llm`` itself is pure
enough to unit-test with a factory patch.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from tradingagents.llm_clients.factory import create_llm_client

# Per-role default LLM tier. The risk debators (direction.md parity) reuse
# the research debate keys: aggressive -> TRADINGAGENTS_DEBATE_BULL_MODEL,
# conservative -> TRADINGAGENTS_DEBATE_BEAR_MODEL, neutral -> the fallback
# (quick) tier — no dedicated key, per the user's model-mapping decision.
DEFAULT_TIER = {
    "bull": "quick",
    "bear": "quick",
    "judge": "deep",
    "aggressive": "quick",
    "conservative": "quick",
    "neutral": "quick",
}


def _split_spec(spec: str) -> tuple[str, str] | None:
    """'family:id' -> (family, id); None when not a 2-part spec."""
    if not spec:
        return None
    parts = spec.split(":", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return None
    return parts[0].strip().lower(), parts[1].strip()


def role_fallback_models(config: dict, role: str) -> tuple[str, str]:
    """Default (provider, model) for a role from the config decades."""
    tier = DEFAULT_TIER.get(role, "quick")
    provider = config.get("llm_provider", "")
    model = config.get("deep_think_llm" if tier == "deep" else "quick_think_llm", "")
    return provider, model


def role_model_spec(config: dict, role: str) -> tuple[str, str] | None:
    """The configured per-role (provider, model); None when unset."""
    # direction.md: bull/aggressive share the BULL_MODEL key, bear/conservative
    # share the BEAR_MODEL key, judge (both sections) shares JUDGE_MODEL key.
    # neutral has no key -> None -> falls back to the quick tier.
    key = {
        "bull": "debate_bull_model",
        "bear": "debate_bear_model",
        "judge": "debate_judge_model",
        "aggressive": "debate_bull_model",
        "conservative": "debate_bear_model",
        "neutral": None,
    }.get(role)
    spec = config.get(key) if key else None
    return _split_spec(str(spec)) if spec else None


def build_role_llm_kwargs(
    config: dict, role: str, provider: str, model: str
) -> dict:
    """Per-role kwargs: max_tokens tier + any provider-specific knobs.

    Mirrors TradingAgentsGraph's ``_tier_kwargs`` (max_tokens from
    ``max_output_tokens_quick`` / ``max_output_tokens_deep``) so a role LLM
    respects the same output budgets as the base agents.
    """
    cfg = config or {}
    kwargs: dict[str, Any] = {}
    tier = DEFAULT_TIER.get(role, "quick")
    # Debate roles get their own output budget: the structured payload needs
    # ~500-1500 tokens max, and the quick tier's 8000 let a verbose reasoning
    # model (glm-5.3-flash) write to truncation every call (repair-loop
    # churn + 1-2min turns). Capped at debate_max_output_tokens (2500).
    cap = cfg.get("debate_max_output_tokens") or cfg.get(
        "max_output_tokens_deep" if tier == "deep" else "max_output_tokens_quick"
    )
    cap = cap or cfg.get("max_output_tokens")
    if cap:
        kwargs["max_tokens"] = int(cap)
    # Low sampling temperature for deterministic structured output: high
    # temps invite conversational/free-text drift inside the JSON (deepseek
    # JSON-enforcement note #2). 0.0-0.2 recommended; None = provider default.
    temp = cfg.get("debate_temperature")
    if temp is not None:
        kwargs["temperature"] = float(temp)
    provider_l = (provider or "").lower()
    if provider_l == "google" and cfg.get("google_thinking_level"):
        kwargs["thinking_level"] = cfg["google_thinking_level"]
    elif provider_l == "openai" and cfg.get("openai_reasoning_effort"):
        kwargs["reasoning_effort"] = cfg["openai_reasoning_effort"]
    elif provider_l == "anthropic" and cfg.get("anthropic_effort"):
        kwargs["effort"] = cfg["anthropic_effort"]
    return kwargs


def resolve_role_llm(
    config: dict,
    role: str,
    factory: Callable[..., Any] = create_llm_client,
) -> Any:
    """Return an LLM client for a debate role from config; fallback to the
    role's default tier when no ``debate_*_model`` is set.

    ``factory`` is injectable for tests (patch create_llm_client).
    """
    spec = role_model_spec(config, role)
    if spec is not None:
        provider, model = spec
    else:
        provider, model = role_fallback_models(config, role)
    kwargs = build_role_llm_kwargs(config, role, provider, model)
    base_url = config.get("backend_url")
    client = factory(provider=provider, model=model, base_url=base_url, **kwargs)
    # ``create_llm_client`` returns a BaseLLMClient; ``get_llm()`` unwraps to
    # the raw LangChain-compatible chat model the rest of the graph uses.
    getter = getattr(client, "get_llm", None)
    if getter is not None:
        return getter()
    return client


# Per-role tool surfaces (design §4.1): DIFFERENT tool sets per role.
BULL_TOOLS = (
    "get_swing_set",
    "get_relative_strength",
    "get_growth_metrics",
    "get_insider_activity",
    "get_momentum_scan",
    "get_extended_indicators",
    "get_analyst_verdict",
    "get_earnings_surprise",
    "get_dcf_valuation",
)
BEAR_TOOLS = (
    "get_tail_risk",
    "get_liquidity_risk",
    "get_credit_spread_read",
    "get_short_interest",
    "get_horizon_var",
    "get_book_tail_risk",
    "get_regime_gate_read",
    "get_fixed_income_risk",
    "get_vol_cones",
)
NEUTRAL_EVIDENCE_TOOLS = (
    "get_verified_market_snapshot",
    "get_trade_plan",
    "get_risk_gate",
)


def role_tools(role: str) -> tuple[str, ...]:
    """Tool surface for a role; judge + neutral evidence share the neutral set."""
    if role == "bull":
        return BULL_TOOLS
    if role == "bear":
        return BEAR_TOOLS
    return NEUTRAL_EVIDENCE_TOOLS


__all__ = [
    "DEFAULT_TIER",
    "role_fallback_models",
    "role_model_spec",
    "build_role_llm_kwargs",
    "resolve_role_llm",
    "BULL_TOOLS",
    "BEAR_TOOLS",
    "NEUTRAL_EVIDENCE_TOOLS",
    "role_tools",
]

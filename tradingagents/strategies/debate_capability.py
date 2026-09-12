"""R3 — Config-time capability matrix for structured-debate role routing.

Pure, no network: a startup health check deciding whether a candidate
``(provider, model)`` can meet a debate role's strictness floor. Roles are
routed only to models whose assessed ``context_window``, structured-output
support and tool-binding capability satisfy the role's requirements; a role
that cannot be met fails CLOSED with a clear error rather than silently
degrading.

Role matrix (design §4.1): f(context window, structured-output support,
tool latency). This module keeps the decision pure + testable; the actual
latency probe is a smoke hook called at graph compile time when
``debate_require_capability_matrix`` is enabled.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

DEFAULT_CONTEXT_WINDOW = 128_000
# The gate's message prefixes. ERROR is the fail-closed tier: callers that
# honour ``debate_require_capability_matrix`` raise on these (see
# ``check_debate_capabilities``). Defined once so the caller never re-derives
# what "failed" means.
ERROR_PREFIX = "ERROR: "
WARNING_PREFIX = "WARNING: "


class DebateCapabilityError(RuntimeError):
    """A debate role cannot meet its strictness floor and the matrix is required.

    Raised at graph compile time instead of printing: the flag exists to stop a
    run that cannot produce a verified structured debate, and a printed
    "ERROR:" line let the run continue straight into the legacy fallback
    (2026-09-12: a live run ran the free-form debate with the flag set on).
    """


# Minimum context a debater/judge role needs to hold the analysts' reports +
# computed factsheet + the debate history (advisory floor).
ROLE_FLOORS = {
    "bull": {"context_window": 32_000, "structured": False, "tools": False},
    "bear": {"context_window": 32_000, "structured": False, "tools": False},
    "judge": {"context_window": 16_000, "structured": True, "tools": False},
    # Risk debators (aggressive/conservative/neutral) run a TOOL LOOP
    # (risk_tool_loop.run_tool_loop -> llm.bind_tools) to ground their risk
    # figures before writing prose, so tool binding is required; they emit
    # free-text arguments (not a structured schema), so structured output is
    # not a floor. Same evidence context as the research debators.
    "aggressive": {"context_window": 32_000, "structured": False, "tools": True},
    "conservative": {"context_window": 32_000, "structured": False, "tools": True},
    "neutral": {"context_window": 32_000, "structured": False, "tools": True},
}
_KNOWN_STRUCTURED = {"openai", "anthropic", "google", "azure", "deepseek", "openrouter", "glm", "qwen", "mistral", "minimax"}
_KNOWN_TOOLS = {"openai", "anthropic", "google", "azure", "deepseek", "openrouter", "ollama", "groq", "nvidia", "qwen", "glm", "minimax", "mistral"}


@dataclass
class ModelCapability:
    """Assessed profile of one candidate model."""

    provider: str
    model: str = ""
    context_window: int = DEFAULT_CONTEXT_WINDOW
    structured_output_support: bool = True
    tool_binding_support: bool = True
    tool_latency_ms: float | None = None  # None = not measured (assume OK)

    @property
    def fail_reasons(self) -> list[str]:
        reasons = []
        if self.context_window <= 0:
            reasons.append("context_window<=0")
        return reasons


def assess_model_capability(
    provider: str,
    model: str = "",
    context_window: int | None = None,
    structured_output_support: bool | None = None,
    tool_binding_support: bool | None = None,
) -> ModelCapability:
    """Assess a candidate from configured/provider knowledge.

    Unknown providers default to capability-ON (the capability matrix only
    REFUSES when the matrix is required and evidence says the provider cannot
    meet the floor; unknown is treated as permissive, matching the repo's
    fail-open dual-mode design).
    """
    provider_l = (provider or "").lower()
    return ModelCapability(
        provider=provider_l,
        model=model or "",
        context_window=context_window if context_window is not None else DEFAULT_CONTEXT_WINDOW,
        structured_output_support=(
            structured_output_support
            if structured_output_support is not None
            else provider_l in _KNOWN_STRUCTURED or provider_l == "ollama"
        ),
        tool_binding_support=(
            tool_binding_support
            if tool_binding_support is not None
            else provider_l in _KNOWN_TOOLS
        ),
    )


def can_serve_role(cap: ModelCapability, role: str) -> tuple[bool, list[str]]:
    """Can this model serve this role? Returns (ok, reasons)."""
    floor = ROLE_FLOORS.get(role)
    if floor is None:
        return False, [f"unknown role {role!r}"]
    reasons = []
    if cap.context_window < floor["context_window"]:
        reasons.append(
            f"context {cap.context_window} < floor {floor['context_window']}"
        )
    if floor["structured"] and not cap.structured_output_support:
        reasons.append("role needs structured output but provider lacks it")
    if floor["tools"] and not cap.tool_binding_support:
        reasons.append("role needs tool binding but provider lacks it")
    reasons.extend(cap.fail_reasons)
    return (not reasons), reasons


def capability_gate(
    roles: dict[str, ModelCapability],
    *,
    require: bool = False,
) -> list[str]:
    """Run the matrix over a role→capability map; return config errors.

    When ``require`` is False the matrix is advisory (warnings only). When
    True, a role that cannot meet its floor is a FAIL-CLOSED config error.
    """
    errors: list[str] = []
    for role, cap in roles.items():
        ok, reasons = can_serve_role(cap, role)
        if not ok:
            msg = f"debate role {role!r} (provider={cap.provider}) cannot be served: {'; '.join(reasons)}"
            if require:
                errors.append(f"{ERROR_PREFIX}{msg}")
            else:
                errors.append(f"{WARNING_PREFIX}{msg}")
    return errors


def assess_role_capabilities(
    config: dict, roles: Sequence[str] | None = None
) -> dict[str, ModelCapability]:
    """Role -> capability map from the configured ``debate_*_model`` keys.

    Advisory and best-effort: a role with no configured spec is skipped (the
    matrix refuses only on evidence), and a resolver failure is skipped rather
    than taking down graph construction. The role import is local to keep this
    pure module free of an agents -> strategies import edge.
    """
    from tradingagents.agents.utils.debate_roles import role_model_spec

    caps: dict[str, ModelCapability] = {}
    for role in roles if roles is not None else tuple(ROLE_FLOORS):
        try:
            spec = role_model_spec(config, role)
        except Exception:  # noqa: BLE001 - advisory: an unresolvable role is skipped
            continue
        if spec:
            provider, model = spec
            caps[role] = assess_model_capability(provider, model)
    return caps


def check_debate_capabilities(
    config: dict, roles: Sequence[str] | None = None
) -> list[str]:
    """Enforce the capability matrix at graph compile time (R3).

    Returns the advisory messages the caller should print. When
    ``debate_require_capability_matrix`` is set and any role fails its floor,
    raises :class:`DebateCapabilityError` — fail closed, so a run that cannot
    produce a verified structured debate stops instead of degrading.
    """
    messages = capability_gate(
        assess_role_capabilities(config, roles),
        require=bool((config or {}).get("debate_require_capability_matrix", False)),
    )
    errors = [m for m in messages if m.startswith(ERROR_PREFIX)]
    if errors:
        raise DebateCapabilityError(
            "debate capability matrix: " + "; ".join(errors)
        )
    return messages


__all__ = [
    "DEFAULT_CONTEXT_WINDOW",
    "ERROR_PREFIX",
    "WARNING_PREFIX",
    "ROLE_FLOORS",
    "DebateCapabilityError",
    "ModelCapability",
    "assess_model_capability",
    "assess_role_capabilities",
    "can_serve_role",
    "capability_gate",
    "check_debate_capabilities",
]

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

from dataclasses import dataclass

DEFAULT_CONTEXT_WINDOW = 128_000
# Minimum context a debater/judge role needs to hold the analysts' reports +
# computed factsheet + the debate history (advisory floor).
ROLE_FLOORS = {
    "bull": {"context_window": 32_000, "structured": False, "tools": False},
    "bear": {"context_window": 32_000, "structured": False, "tools": False},
    "judge": {"context_window": 16_000, "structured": True, "tools": False},
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
                errors.append(f"ERROR: {msg}")
            else:
                errors.append(f"WARNING: {msg}")
    return errors


__all__ = [
    "DEFAULT_CONTEXT_WINDOW",
    "ROLE_FLOORS",
    "ModelCapability",
    "assess_model_capability",
    "can_serve_role",
    "capability_gate",
]

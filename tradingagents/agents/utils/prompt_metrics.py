"""Phase 0 decision-context telemetry (docs/design_decision_context.md §13).

**Why this module exists.** Prompts are never persisted today, so the question
the design doc is built around - *"when the PM prompt exceeds 12k tokens, does
the probability of HOLD change?"* - is currently unanswerable without
reconstructing prompts from report trees, which is not possible. This module
records, per run:

- the **prompt size** of every LLM stage (chars + a token estimate);
- the PM model's **structured output before any deterministic transformation**;
- the **deterministic postprocess** applied to it, and the **execution** action;
- the **context mode** (packet version, truncation);
- the **evidence counts** (bullish / bearish / neutral / uncertainty / conflict);
- the **snapshot identity** (hashes that let a paired experiment prove both arms
  consumed the same deterministic evidence).

**Zero behavioural change.** Everything here only measures and returns data.
Nothing reads a value back into a prompt or into a decision. Every function is
total and degrades to an explicit ``None`` / ``"unknown"`` rather than raising -
a telemetry failure must never break a report write.

**The boundary the design doc insists on naming** (§12.4). ``llm_output`` is the
PM model's structured emit, *before* any transformation. It is NOT
``pm_decision``: that state key is captured *after* ``_guardrail_hook`` has
already mutated ``rating`` and ``confidence`` in place, so a value read from it
would silently be a post-guardrail number wearing a "raw" label. The capture
point in ``portfolio_manager._result_hook`` dumps the model BEFORE the guardrail
runs for exactly this reason.
"""

from __future__ import annotations

__all__ = [
    "PROMPT_METRICS_KEY",
    "PM_LLM_OUTPUT_KEY",
    "DIRECTION_BY_RATING",
    "TOKENS_PER_CHAR_DIVISOR",
    "decision_telemetry_block",
    "direction_of",
    "merge_prompt_metrics",
    "record_stage",
    "snapshot_identity",
    "stage_metrics",
    "tokens_est",
]

# State keys. Declared in ``agent_states.AgentState`` - native LangGraph
# SILENTLY DROPS undeclared keys (docs/AGENT_ONBOARDING.md, 2026-08-28).
PROMPT_METRICS_KEY = "prompt_metrics"
PM_LLM_OUTPUT_KEY = "pm_llm_output"

# ~4 chars/token is the divisor the design doc's §3 baseline uses (139,372 chars
# measured as ~34,843 tokens). It is an ESTIMATE and is labelled as one
# everywhere it surfaces; the experiment needs relative size, not billing
# accuracy (``llm_cost_est`` already owns the billing number).
TOKENS_PER_CHAR_DIVISOR = 4

# The coarse directional class of a 5-tier rating. The PM schema has NO
# ``direction`` field - the model emits ``rating`` and ``confidence`` only - so
# this is a deterministic PROJECTION of the rating, recorded alongside it for
# the experiment's readability. It is derived from ``llm_output.rating`` in the
# same expression that records it, so the two can never diverge.
DIRECTION_BY_RATING = {
    "Buy": "bullish",
    "Overweight": "bullish",
    "Hold": "neutral",
    "Underweight": "bearish",
    "Sell": "bearish",
}


def tokens_est(chars: int | None) -> int | None:
    """Estimated tokens for a character count. ``None`` in, ``None`` out."""
    if chars is None:
        return None
    try:
        return int(chars) // TOKENS_PER_CHAR_DIVISOR
    except (TypeError, ValueError):
        return None


def stage_metrics(prompt: object) -> dict:
    """``{"chars": n, "tokens_est": n // 4}`` for one prompt.

    A non-string prompt (a LangChain message list, a template) is measured by
    its ``str()`` - the caller that owns the object knows its real shape, and a
    telemetry call must not raise.
    """
    try:
        text = prompt if isinstance(prompt, str) else str(prompt)
    except Exception:  # noqa: BLE001 - telemetry never raises
        return {"chars": None, "tokens_est": None}
    n = len(text)
    return {"chars": n, "tokens_est": tokens_est(n)}


def record_stage(stage: str, prompt: object, **extra) -> dict:
    """The state fragment one node returns: ``{PROMPT_METRICS_KEY: {stage: ...}}``.

    Usage in a node::

        return {..., **record_stage("pm", prompt)}
    """
    entry = stage_metrics(prompt)
    entry.update(extra)
    return {PROMPT_METRICS_KEY: {stage: entry}}


def merge_prompt_metrics(left: dict | None, right: dict | None) -> dict:
    """LangGraph reducer: merge per-stage dicts.

    Declared as ``Annotated[dict, merge_prompt_metrics]`` in ``AgentState``.
    Without a reducer the default is last-write-wins and every stage but the
    final one would be lost, because each node returns its own fragment.
    """
    out = dict(left or {})
    out.update(right or {})
    return out


def direction_of(rating: str | None) -> str | None:
    """Coarse directional class of a rating: bullish / neutral / bearish.

    ``None`` for an unparseable or absent rating - never a silent "neutral".
    """
    if not rating:
        return None
    return DIRECTION_BY_RATING.get(str(rating).strip().capitalize())


def snapshot_identity(cfg: dict | None, final_state: dict | None) -> dict:
    """Hashes that let a paired experiment prove both arms saw the same evidence.

    The invariant (design doc §12.3): **all arms for a paired observation must
    consume the same deterministic evidence snapshot.** A mismatch invalidates
    the pair. Without this, a market-data refresh or a regenerated engine result
    masquerades as a context effect.

    ``data_snapshot_hash`` is over the ticker / trade date / price caliber
    identity; ``engine_output_hash`` over the run's score snapshot;
    ``model_parameters_hash`` over the sampling-relevant config. Each is
    ``None`` when its input is absent - a named gap, never a hash of nothing.
    """
    import hashlib
    import json as _json

    state = final_state or {}
    out: dict = {"snapshot_id": None, "data_snapshot_hash": None,
                 "engine_output_hash": None, "model_parameters_hash": None}

    ticker = str(state.get("company_of_interest") or "").upper() or None
    trade_date = state.get("trade_date")
    try:
        out["snapshot_id"] = f"{ticker}_{trade_date}" if ticker and trade_date else None
    except Exception:  # noqa: BLE001 - telemetry never raises
        out["snapshot_id"] = None

    def _h(payload) -> str | None:
        try:
            return hashlib.sha256(
                _json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest()[:16]
        except Exception:  # noqa: BLE001
            return None

    # Data identity: what the run believed it was looking at. The price caliber
    # is deliberately included - a "close" and an "adjusted close" are different
    # evidence, and a pair that silently changed basis is not a valid pair.
    if ticker or trade_date:
        out["data_snapshot_hash"] = _h({
            "ticker": ticker,
            "trade_date": trade_date,
            "asset_type": state.get("asset_type"),
            "instrument_context": state.get("instrument_context"),
            "price_caliber": state.get("price_caliber"),
        })

    # Engine identity: the deterministic scores the debate read. Absent when the
    # quant scorecard gate is off - recorded as None, not as an empty hash.
    if state.get("quant_scorecard"):
        out["engine_output_hash"] = _h(state.get("quant_scorecard"))

    # Model identity: sampling-relevant parameters only. The provider rate table
    # and cost keys are excluded - they do not change what the model does.
    _cfg = cfg or {}
    _model_keys = (
        "llm_provider", "deep_think_llm", "quick_think_llm",
        "temperature", "max_tokens", "top_p",
    )
    out["model_parameters_hash"] = _h({k: _cfg.get(k) for k in _model_keys})
    return out


def decision_telemetry_block(
    cfg: dict | None,
    final_state: dict | None,
    *,
    context_mode: str | None = None,
    packet_version: str | None = None,
    packet_truncated: bool | None = None,
    evidence_counts: dict | None = None,
) -> dict:
    """The ``decision_context`` block for ``run_card.json`` (design doc §13).

    Three separate layers, never collapsed:

    - ``llm_output`` - the PM model's structured emit, before ANY transformation;
    - ``deterministic_postprocess`` - the guardrail rating, the risk gate, and
      the security/portfolio action split;
    - ``execution`` - the final action the executor would receive.

    A ``HOLD`` may be ``llm_output.rating = "Buy"`` + a REJECT gate. Collapsing
    the three would make that indistinguishable from the model itself turning
    conservative, which is the single most important distinction the experiment
    depends on.
    """
    state = final_state or {}
    pm = state.get("pm_decision") or {}
    raw = state.get(PM_LLM_OUTPUT_KEY) or {}
    rg = state.get("risk_gate") or {}

    raw_rating = raw.get("rating") if isinstance(raw, dict) else None
    post_rating = pm.get("rating") if isinstance(pm, dict) else None

    # The security/portfolio split is computed by ONE producer
    # (``signal_action_split``), called with the same inputs the execution
    # contract's emitter uses, so the two cannot disagree. It is NOT read from
    # state: nothing writes those keys there, and an earlier draft of this block
    # read them anyway and silently recorded four nulls - a field that does
    # nothing is worse than a named gap.
    try:
        from tradingagents.strategies.signal_action import signal_action_split

        split = signal_action_split(
            str(post_rating) if post_rating else None,
            gate_verdict=rg.get("verdict") if isinstance(rg, dict) else None,
            gate_reasons=(rg.get("reasons") or []) if isinstance(rg, dict) else [],
            kill_switch=bool((state.get("kill_switch_state") or {}).get("active", False)),
        )
    except Exception:  # noqa: BLE001 - telemetry never raises
        split = {"security_signal": None, "portfolio_action": None,
                 "combined_action": None, "gated": None}

    return {
        "llm_output": {
            # The model's own emit. NOT pm_decision, which is captured after the
            # guardrail has already rewritten rating/confidence.
            "rating": raw_rating,
            "direction": direction_of(raw_rating),
            "confidence": raw.get("confidence") if isinstance(raw, dict) else None,
            "captured": bool(raw),
        },
        "deterministic_postprocess": {
            "guardrail_rating": post_rating,
            "guardrail_changed_rating": (
                bool(raw_rating and post_rating and raw_rating != post_rating)
                if (raw_rating or post_rating) else None
            ),
            "guardrail_reason": pm.get("guardrail_reason") if isinstance(pm, dict) else None,
            "risk_cap": pm.get("risk_cap") if isinstance(pm, dict) else None,
            "risk_gate": rg.get("verdict") if isinstance(rg, dict) else None,
            "signal_action": split,
        },
        "execution": {
            # The engine's last action value - what the report and
            # research_decision.json present to the executor. The executor then
            # computes its OWN binding gate; that label is not engine state and
            # is deliberately not fabricated here.
            "final_action": split.get("combined_action"),
            "final_action_source": "signal_action_split.combined_action",
        },
        "context": {
            "context_mode": context_mode,
            "packet_version": packet_version,
            "packet_truncated": packet_truncated,
        },
        "evidence": dict(evidence_counts or {}),
        "snapshot": snapshot_identity(cfg, state),
    }

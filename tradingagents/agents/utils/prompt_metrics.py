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

import hashlib

__all__ = [
    "PROMPT_METRICS_KEY",
    "PM_LLM_OUTPUT_KEY",
    "PROMPT_CONDITION_KEY",
    "PROMPT_VERSION_KEY",
    "CONDITION_MIN_N",
    "DIRECTION_BY_RATING",
    "STANCE_SOURCES",
    "TOKENS_PER_CHAR_DIVISOR",
    "condition_accuracy",
    "condition_descriptor",
    "decision_telemetry_block",
    "direction_of",
    "merge_prompt_metrics",
    "prompt_version",
    "record_condition_run",
    "record_prompt_parts",
    "record_stage",
    "snapshot_identity",
    "stage_metrics",
    "stance_direction_counts",
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


def _messages_chars(messages: object) -> int:
    """Size of a message list AS THE MODEL RECEIVES IT.

    ``len(str(messages))`` is NOT this. A LangChain message's repr carries
    Python scaffolding the provider never sees - ``content=``,
    ``additional_kwargs={}``, ``response_metadata={}``, ``id=`` - which measured
    **9.8% over** on a realistic tool-loop history. That is the same
    mislabelling this module keeps having to fix, so the content and the tool
    calls are summed directly and nothing else is counted.

    A message whose content is a list (multimodal blocks) is measured by its
    rendered parts. Anything unreadable contributes 0 rather than raising.
    """
    try:
        items = list(messages or [])
    except TypeError:
        return 0
    total = 0
    for m in items:
        try:
            content = getattr(m, "content", None)
            if content is None:
                content = m if isinstance(m, str) else ""
            if isinstance(content, str):
                total += len(content)
            else:
                total += len(str(content))
            for tc in (getattr(m, "tool_calls", None) or []):
                total += len(str(tc))
        except Exception:  # noqa: BLE001 - telemetry never raises
            continue
    return total


def record_prompt_parts(stage: str, prefix: str, messages: object, **extra) -> dict:
    """For a node whose prompt is a TEMPLATE plus a growing message history.

    The three tool-loop analysts do not build one string: they render a static
    prefix (boilerplate + system message + evidence block + the bound tool
    catalog) and then append ``MessagesPlaceholder("messages")``, which grows
    with every tool round. Measuring only the prefix would put a number under a
    field named "prompt" that is not the prompt - the same mislabelling this
    module exists to avoid, so the breakdown is recorded explicitly:

    - ``prefix_chars`` - the static part, and the quantity §3 of the design doc
      measures (it is stable across rounds, which is what makes the W4 prefix
      cache work);
    - ``messages_chars`` - the conversation at the final call, measured as the
      model receives it (see ``_messages_chars``);
    - ``chars`` - the two together, which is what the model actually received.

    ``messages_chars`` covers the message CONTENT and tool-call payloads, not
    the provider's own chat-template overhead (role markers, separators), which
    is a few tokens per message and not knowable from here. It is a close proxy,
    and unlike the repr it is not systematically inflated.
    """
    messages_chars = _messages_chars(messages)
    entry = {
        "chars": len(prefix) + messages_chars,
        "tokens_est": tokens_est(len(prefix) + messages_chars),
        "prefix_chars": len(prefix),
        "messages_chars": messages_chars,
    }
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


#: The state keys carrying per-role directional records, in the order they are
#: sampled. The risk trio is sampled after the Trader; the researcher pair
#: before the debate. A caller that holds only the first sees one source.
STANCE_SOURCES: tuple[str, ...] = (
    "researcher_independent_stances",
    "risk_independent_stances",
)


def stance_direction_counts(state: dict | None) -> dict:
    """**The ONE producer** of the directional distribution over stances.

    Two readers consume this - the run card's ``evidence`` block and the
    Decision Packet's ``DIRECTIONAL DISTRIBUTION`` row - and they must not be
    able to disagree about how many stances were bullish (master rule 15).

    The axis is the independent stances because they are the only per-role
    directional records in the state, each carrying a canonical 5-tier rating.
    It is deliberately NOT the engines: the engine band tables are not
    directional (``benign``/``constructive``/``hostile``,
    ``low risk``/``contained``/``severe``, ``high-information``/``stale``), so
    there is no engine-axis sign to count.

    ``sources`` travels with the counts so a reader can see what they are made
    of - a count over three stances is not a count over the whole decision
    context, and must not be read as one. An unreadable rating is counted
    separately, never folded into ``neutral``.
    """
    counts = {"bullish": 0, "bearish": 0, "neutral": 0}
    sources: list[str] = []
    unreadable = 0
    for key in STANCE_SOURCES:
        stances = (state or {}).get(key) or {}
        if not isinstance(stances, dict) or not stances:
            continue
        for _role, payload in stances.items():
            rating = (payload or {}).get("rating") if isinstance(payload, dict) else None
            direction = direction_of(rating)
            if direction is None:
                unreadable += 1
                continue
            counts[direction] += 1
        sources.append(key)
    counts["sources"] = sources
    counts["unreadable"] = unreadable
    return counts


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


# ---------------------------------------------------------------------------
# N5: the prompt-condition A/B harness (OFFLINE - ground rule 8)
# ---------------------------------------------------------------------------
#
# **Adopt the harness, not the framing.** 2606.00061 reports a prompt-framing
# effect that is MODEL-DEPENDENT - one model improves monotonically, another only
# at a 60-month window, a third mostly does not, and the SAME model flips sign
# across context windows - with `n = 72` per cell and no multiple-comparison
# control against a 50% baseline. That is weak evidence for its own framing, so
# nothing here asserts that a framing effect exists. What lands is the harness:
#
# - the prompt becomes a VERSIONED first-class input (`prompt_version`), so two
#   runs whose prompts differ in any byte are distinguishable;
# - the condition is RECORDED PER RUN on the decision ledger, through the
#   ledger's own writer (`strategies.prediction_ledger.log_decision`);
# - accuracy is scored PER CONDITION, on the ledger's own outcomes, so a prompt
#   edit becomes attributable instead of an unrecorded drift.
#
# **The engine's prompt strings do not change.** The harness only labels them.
# It is OFFLINE by construction (ground rule 8): nothing here is reachable from
# `prepare_initial_state`, from `finalize_run`, or from an agent tool, because an
# A/B comparison DOUBLES the LLM spend of every run it touches - it is run on a
# sample, out of band, by an operator.
#
# **A run with no recorded condition is not pooled.** It cannot be attributed to
# an arm, so `condition_accuracy` reports it as unattributed with its count
# rather than folding it into any arm's rate - the same discipline the
# denominator-integrity rule applies to a thin panel (master rule 1).

#: The ledger field carrying the prompt condition one run ran under.
PROMPT_CONDITION_KEY = "prompt_condition"

#: The field carrying the prompt VERSION behind that condition, so a label that
#: silently spans two prompt texts is visible rather than trusted.
PROMPT_VERSION_KEY = "prompt_version"

#: The floor below which an arm's accuracy is NOT reported: a rate over a couple
#: of rows is noise, and quoting it is the very defect this harness exists to
#: avoid. The count is still reported.
CONDITION_MIN_N = 5


def _condition_gate(cfg: dict | None = None) -> bool:
    """Is the N5 harness switched on? (``enable_prompt_condition_harness``)

    The key is read by its literal name so the gate registry's read-site scan
    finds it. Off by default, and an unreadable config leaves it off - a config
    read must never break the read it guards.
    """
    try:
        from tradingagents.dataflows.config import get_config

        gate = get_config() if cfg is None else cfg
    except Exception:  # noqa: BLE001 - a config read must never break the read
        gate = cfg or {}
    return bool((gate or {}).get("enable_prompt_condition_harness", False))


def prompt_version(prompt: object) -> str | None:
    """A deterministic content id for one prompt string - the versioned input.

    ``sha256(text)[:16]``: two runs whose prompts differ in any byte get
    different ids, so a prompt edit is attributable rather than silent. ``None``
    for an unreadable prompt - a named gap, never a hash of nothing.
    """
    try:
        text = prompt if isinstance(prompt, str) else str(prompt)
    except Exception:  # noqa: BLE001 - telemetry never raises
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def condition_descriptor(label: str, prompts: dict | None = None) -> dict:
    """The condition one run ran under: its arm LABEL and its prompt versions.

    ``prompts`` is ``{stage: prompt}`` - the engine's prompt strings, read as
    they are (this function never changes one). Each stage is versioned with
    :func:`prompt_version`, and ``version_id`` folds those versions together, so
    two runs sharing a label but carrying different prompt text are
    distinguishable - the label is the arm's NAME, never its identity.

    Returns ``{"label", "prompt_versions", "version_id", "status",
    "unavailable"}``. An empty label is ``unavailable`` with the reason: a run
    that cannot be named cannot be attributed to an arm.
    """
    name = str(label or "").strip()
    if not name:
        return {
            "label": None,
            "prompt_versions": {},
            "version_id": None,
            "status": "unavailable",
            "unavailable": "no condition label: an unnamed arm is not a condition",
        }
    versions = {
        str(stage): prompt_version(prompt)
        for stage, prompt in sorted((prompts or {}).items())
    }
    version_id = None
    if versions:
        version_id = prompt_version(
            "|".join(f"{k}={v}" for k, v in versions.items())
        )
    return {
        "label": name,
        "prompt_versions": versions,
        "version_id": version_id,
        "status": "ok",
        "unavailable": None,
    }


def record_condition_run(
    condition: dict | None,
    *,
    cfg: dict | None = None,
    **row,
) -> dict:
    """OFFLINE: append ONE decision-ledger row tagged with its prompt condition.

    The WRITER SITE is ``strategies.prediction_ledger.log_decision`` - the
    append-only JSONL writer the run's own finalize path also calls (under
    ``enable_prediction_ledger``). This harness adds the CONDITION column to that
    row and nothing else; it is deliberately reachable from no run path (ground
    rule 8), so running an extra arm is an explicit offline act rather than
    something a graph node can trigger.

    ``row`` carries the ledger fields (``ticker``, ``date``, ``rating``,
    ``entry``, ``confidence``, ``results_dir``, ...). Returns the appended row,
    or - when the gate is off or the condition is unusable - a refusal record
    with the reason, and NOTHING is written.
    """
    if not _condition_gate(cfg):
        return {
            "status": "unavailable",
            "unavailable": (
                "enable_prompt_condition_harness is off (default): the harness "
                "does not run on a gate-off run"
            ),
        }
    label = (condition or {}).get("label") if isinstance(condition, dict) else None
    if not label:
        return {
            "status": "unavailable",
            "unavailable": (
                "no condition label: a run that cannot be named is not written, "
                "because it could only ever be unattributable"
            ),
        }
    from tradingagents.strategies.prediction_ledger import log_decision

    return log_decision(
        prompt_condition=str(label),
        prompt_version=(condition or {}).get("version_id"),
        **row,
    )


def condition_accuracy(
    ledger_rows: list[dict],
    *,
    cfg: dict | None = None,
    min_n: int = CONDITION_MIN_N,
) -> dict:
    """Per-condition accuracy over SCORED decision-ledger rows (N5).

    ``ledger_rows`` is the output of ``prediction_ledger.score_all`` - rows that
    carry an ``outcome.hit``. Each row is grouped by its recorded
    ``prompt_condition`` and each arm reports its hit rate **with its count**. A
    row with NO recorded condition is NOT pooled into any arm, and neither is a
    row whose outcome could not be scored: both are counted under
    ``unattributed`` with their reason, because a run that cannot be attributed
    cannot be compared.

    An arm with fewer than ``min_n`` scored rows reports ``accuracy: None`` (and
    ``below_min_n: True``) rather than a rate from noise. ``version_conflict``
    flags a label that spans more than one prompt version - the case a bare label
    would hide.

    Returns ``{"status", "unavailable", "conditions", "unattributed", "n_rows",
    "n_scored", "min_n", "basis"}``. With the gate off the whole read is
    ``unavailable`` with the reason and no arm is scored.
    """
    if not _condition_gate(cfg):
        return {
            "status": "unavailable",
            "unavailable": (
                "enable_prompt_condition_harness is off (default): no arm is "
                "scored on a gate-off run"
            ),
            "conditions": {},
            "unattributed": {},
            "n_rows": len(list(ledger_rows or [])),
            "n_scored": 0,
            "min_n": int(min_n),
            "basis": "harness off (default)",
        }

    rows = [r for r in (ledger_rows or []) if isinstance(r, dict)]
    arms: dict[str, dict] = {}
    no_condition = 0
    no_outcome = 0
    for row in rows:
        label = row.get(PROMPT_CONDITION_KEY)
        if not label:
            no_condition += 1
            continue
        outcome = row.get("outcome")
        hit = outcome.get("hit") if isinstance(outcome, dict) else None
        if hit is None:
            no_outcome += 1
            continue
        arm = arms.setdefault(
            str(label),
            {"n": 0, "hits": 0, "accuracy": None, "below_min_n": False,
             "versions": set(), "version_conflict": False},
        )
        arm["n"] += 1
        arm["hits"] += int(bool(hit))
        arm["versions"].add(row.get(PROMPT_VERSION_KEY))

    for arm in arms.values():
        arm["below_min_n"] = arm["n"] < int(min_n)
        if not arm["below_min_n"]:
            arm["accuracy"] = round(arm["hits"] / arm["n"], 4)
        versions = sorted(str(v) for v in arm["versions"])
        arm["versions"] = versions
        arm["version_conflict"] = len(versions) > 1

    conditions = {label: arms[label] for label in sorted(arms)}
    n_scored = sum(arm["n"] for arm in conditions.values())
    return {
        "status": "ok",
        "unavailable": None,
        "conditions": conditions,
        "unattributed": {"no_condition": no_condition, "no_outcome": no_outcome},
        "n_rows": len(rows),
        "n_scored": n_scored,
        "min_n": int(min_n),
        "basis": (
            f"per-condition hit rate over {n_scored} scored decision-ledger "
            f"row(s) in {len(conditions)} arm(s); a row with no recorded "
            f"condition ({no_condition}) or no scored outcome ({no_outcome}) is "
            f"NOT pooled - it is unattributed; an arm below min_n={int(min_n)} "
            "reports its count and no rate"
        ),
    }

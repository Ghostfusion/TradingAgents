"""Portfolio Manager: synthesises the risk-analyst debate into the final decision.

Uses LangChain's ``with_structured_output`` so the LLM produces a typed
``PortfolioDecision`` directly, in a single call.  The result is rendered
back to markdown for storage in ``final_trade_decision`` so memory log,
CLI display, and saved reports continue to consume the same shape they do
today.  When a provider does not expose structured output, the agent falls
back gracefully to free-text generation.
"""

from __future__ import annotations

from tradingagents.agents.schemas import PortfolioDecision, render_pm_decision
from tradingagents.agents.utils.agent_utils import (
    get_instrument_context_from_state,
    get_language_instruction,
    get_output_budget,
)
from tradingagents.agents.utils.structured import (
    NO_EXTERNAL_TOOLS,
    bind_structured,
    invoke_structured_or_freetext,
)


def _risk_rows_from_rounds(ds: dict) -> list[dict]:
    """Structured risk factors from the risk-debate rounds, as guardrail rows.

    ``stabilize_decision`` caps at Hold on any row whose severity is high
    (rule 1); the debate's severity vocabulary is LOW/MEDIUM/HIGH/CRITICAL.
    Stored payloads carry ``RiskSeverity`` members - a ``str`` subclass whose
    ``str()`` is ``"RiskSeverity.HIGH"`` - so read ``.value`` before
    normalising.  HIGH and CRITICAL are emitted as the ``"high"`` tier the
    rule compares against, so the documented ``>= high`` threshold holds
    without widening the guardrail's predicate.  Deterministic: rows follow
    round / payload / factor order.
    """
    rows: list[dict] = []
    for record in ds.get("round_records") or []:
        if not isinstance(record, dict):
            continue
        for payload in record.values():
            if not isinstance(payload, dict):
                continue
            for factor in payload.get("risk_factors") or []:
                if not isinstance(factor, dict):
                    continue
                raw = getattr(factor.get("severity"), "value", factor.get("severity"))
                severity = str(raw or "").strip().lower()
                if severity:
                    rows.append(
                        {"severity": "high" if severity in ("high", "critical") else severity}
                    )
    return rows


def create_portfolio_manager(llm, fallback_llm=None, backup_llm=None):
    structured_llm = bind_structured(llm, PortfolioDecision, "Portfolio Manager")

    def portfolio_manager_node(state) -> dict:
        instrument_context = get_instrument_context_from_state(state)

        risk_debate_state = state["risk_debate_state"]

        # Computed risk consensus — the PM must cite it, not reinvent alignment
        # from prose. Option-A hybrid: when the state carries the independent
        # pre-debate vote summary (sampled before any debate cross-talk), use
        # IT — the debate transcript can converge on a wrong answer under
        # conformity pressure, so the dissent flag should come from
        # uncontaminated opinions. Otherwise fall back to parsing the three
        # analysts' last stances from the debate history.
        independent_vote = state.get("computed_independent_vote") or ""
        if independent_vote:
            consensus_line = independent_vote + "\n\n"
        else:
            try:
                from tradingagents.agents.utils.rating import parse_rating
                from tradingagents.strategies.consensus import (
                    agreement_score,
                    consensus_from_score,
                    should_hold,
                    weighted_consensus,
                )
                stances = []
                for key in ("aggressive_history", "conservative_history", "neutral_history"):
                    hist = risk_debate_state.get(key) or []
                    # The graph stores a list of chunks, but a hand-built or
                    # legacy state can carry a plain string - treat that as a
                    # single chunk. Slicing characters out of a string would
                    # otherwise yield garbage "ratings" (masked for a long time
                    # by parse_rating's old implicit Hold default).
                    chunks = [hist] if isinstance(hist, str) else list(hist)
                    for chunk in chunks[-3:]:
                        if isinstance(chunk, str) and chunk.strip():
                            stances.append(parse_rating(chunk))
                score = agreement_score(stances)
                # Weighted stance + threshold-HOLD (advisory, deterministic):
                # weight each risk-role stance equally by default (equal-weight
                # consensus == agreement_score); when enable_calibration is on
                # the caller can pass per-role calibration weights. Below the
                # threshold a divided/weak book is HOLD, not a forced call.
                stance, _ = weighted_consensus([(r, 1.0) for r in stances])
                hold_note = (
                    " Each of them is a STANCE that moves toward HOLD when the "
                    "weighted stance is below threshold (a divided book is not a "
                    "directional call)."
                    if stance is not None and should_hold(stance)
                    else ""
                )
                stance_s = f"{stance:.2f}" if stance is not None else "n/a"
                consensus_line = (
                    f"**Computed risk-consensus** (deterministic): agreement={score:.2f} "
                    f"label={consensus_from_score(score)} weighted_stance={stance_s} "
                    f"(n={len(stances)}) - set your PortfolioDecision.consensus to this "
                    f"level, not a guess.{hold_note}\n\n"
                    if score is not None
                    else "\n"
                )
            except Exception:  # noqa: BLE001 - degrade to no line
                consensus_line = "\n"

        research_plan = state["investment_plan"]
        trader_plan = state["trader_investment_plan"]
        # Computed decision context (regime / plan card / risk snapshot) -
        # advisory hard data compiled by the graph.
        computed_context = state.get("computed_decision_context") or ""

        past_context = state.get("past_context", "")
        lessons_line = (
            f"- Lessons from prior decisions and outcomes:\n{past_context}\n"
            if past_context
            else ""
        )

        # Computed CVaR context: the analyzed name's own daily tail vs the
        # book's tail that actually fed the risk gate (when a risk basket is
        # configured). Grounds the PM's tail-risk / sizing language.
        cvar_line = ""
        try:
            ctx = state.get("risk_context") or {}
            bits = []
            if ctx.get("single_cvar") is not None:
                bits.append(f"analyzed-name daily CVaR {ctx['single_cvar']:.2%}")
            if ctx.get("book_cvar") is not None:
                bits.append(f"portfolio (book) daily CVaR {ctx['book_cvar']:.2%} — fed the gate")
            if bits:
                cvar_line = (
                    "**Computed daily-tail CVaR** (deterministic): "
                    + "; ".join(bits)
                    + ". Ground any tail-risk/sizing language in these numbers; "
                    "do not invent a CVaR.\n\n"
                )
        except Exception:  # noqa: BLE001 - degrade to no line
            cvar_line = ""

        # Computed liquidity / ownership risk (Strategies/risk2.md): the
        # ILLIQ / float-turnover / IWF verdict that fed the risk gate (when
        # enable_liquidity_gate is on). Grounds the PM's liquidity/sizing
        # language; absent when the gate didn't run or had no data.
        liq_line = ""
        try:
            liq = (state.get("risk_context") or {}).get("liquidity") or {}
            if liq.get("verdict"):
                bits = [f"verdict={liq['verdict'].upper()}"]
                if liq.get("illiq") is not None:
                    bits.append(f"ILLIQ={liq['illiq']:.2e}")
                if liq.get("float_turnover") is not None:
                    bits.append(f"float-turnover={liq['float_turnover']:.2%}")
                if liq.get("iwf") is not None:
                    bits.append(f"IWF={liq['iwf']:.2%}")
                if liq.get("dangers"):
                    bits.append("; ".join(liq["dangers"][:3]))
                liq_line = (
                    "**Computed liquidity risk** (deterministic, Strategies/risk2.md): "
                    + "; ".join(bits)
                    + ". Ground any liquidity/slippage/sizing language in these numbers; "
                    "adjust position size down (or to 0%) when the verdict is CAUTION or ILLIQUID.\n\n"
                )
        except Exception:  # noqa: BLE001 - degrade to no line
            liq_line = ""

        # Structured risk-debate judge evidence (direction.md item 5): the L2
        # judge verdict over the three risk candidates + L1 triage feed the PM
        # exactly as the research judge feeds the RM. Advisory — absent when
        # the structured risk path did not run.
        from tradingagents.agents.researchers.structured_debate import (
            SECTION_ROLES,
            render_consumer_debate_matrix,
            render_judge_evidence,
        )

        risk_judge_block = render_judge_evidence(
            state.get("structured_risk_state") or {}
        )
        # P3: replace the raw 3-transcript prose with the tabulated Debate
        # Matrix (direction.md). Reporting keeps the full transcripts.
        rds = state.get("structured_risk_state") or {}
        risk_matrix_block = "\n\n**Risk Debate Matrix (deterministic):**\n" + (
            render_consumer_debate_matrix(rds, SECTION_ROLES["risk"])
            if rds.get("round_records")
            else "  (no structured risk debate rounds)"
        )

        # D1/D2 judge-reliability (soft prompt signal): when the risk-debate
        # judge flipped its winner across ensemble runs or used a free-text/
        # repair fallback, tell the PM to hold down its confidence rather than
        # letting a borderline/unreliable judge ride high.
        _reliability_bits = []
        _judge_flip = bool(rds.get("judge_flip"))
        _judge_fb = bool(rds.get("judge_structured_fallback"))
        _judge_agr = rds.get("judge_agreement")
        if _judge_flip or _judge_fb or (_judge_agr is not None and _judge_agr < 1.0):
            if _judge_flip:
                _reliability_bits.append("judge FLIPPED across ensemble runs")
            if _judge_agr is not None and _judge_agr < 1.0:
                _reliability_bits.append(f"judge agreement={_judge_agr}")
            if _judge_fb:
                _reliability_bits.append("judge used free-text/repair fallback")
        if _reliability_bits:
            judge_reliability_line = (
                "**Risk-debate judge reliability** (deterministic): "
                + "; ".join(_reliability_bits)
                + ". Lower your confidence if the judge disagreed or fell back "
                "to free text — do not let a borderline/unreliable judge ride high.\n\n"
            )
        else:
            judge_reliability_line = ""


        prompt = f"""As the Portfolio Manager, synthesize the risk analysts' debate and deliver the final trading decision.

{instrument_context}

---

**Rating Scale** (use exactly one):
- **Buy**: Strong conviction to enter or add to position
- **Overweight**: Favorable outlook, gradually increase exposure
- **Hold**: Maintain current position, no action needed
- **Underweight**: Reduce exposure, take partial profits
- **Sell**: Exit position or avoid entry

**Context:**
- Research Manager's investment plan: **{research_plan}**
- Trader's transaction proposal: **{trader_plan}**
{lessons_line}
**Risk Analysts Debate Matrix:**
{risk_matrix_block}

{risk_judge_block}

{judge_reliability_line}
{cvar_line}{liq_line}{consensus_line}
**Computed decision context (deterministic, advisory - ground your final
decision in these numbers, never invent your own):**
{computed_context}
---

Be decisive and ground every conclusion in specific evidence from the analysts.

**Risk-adjusted sizing and conviction (required):**
- Set `position_size` explicitly from the risk debate — scale it down (or to `0% — no new position`) when the analysts flag high volatility, thin liquidity, or elevated downside risk; scale up only when the debate converged on a well-evidenced view. This is the final size that supersedes the trader's proposal.
- Set `stop_loss` from the risk debate's volatility/liquidity assessment (e.g. below a key support level or one ATR from entry) when the decision is to enter or hold a position.
- Set `confidence` (0–1) from how strongly the evidence converged and how robust the data was. Set `consensus` to `low` when the aggressive/conservative/neutral analysts materially disagreed (a dissent flag), and `high` when they broadly aligned.
- Prefer a clear `Hold`/`Underweight`/`Sell` (with `position_size` `0%` or a reduction) over an ambiguous call when the debate is split — a decision to do nothing is a decision.

**Label consistency (IREN 2026-09-10 decision.md review):**
- STOP BASIS: when the computed Position contract stop and your narrative Stop Loss differ (e.g. a risk-engine hard stop vs the chandelier trailing stop), state which one governs — never present two different stop values for the same current position without saying they are different mechanisms (contract stop vs trailing chandelier).
- SIZE BASIS: distinguish a computed NEW-ENTRY size from a TARGET BOOK WEIGHT for an existing position being trimmed down. A `0.4%` incremental/new-add size and a `5.0%` residual target weight are different things — label them as such, never let them read as conflicting values of one size.
- GATE HEADER: if the computed risk gate or the risk context reports a portfolio-veto (drawdown over limit → new risk blocked), your header Verdict must not read `PASS`/`TRADE_ALLOWED` while the body says the house gate REJECTs new risk. Reconcile the header with the gate (e.g. `TRADE_ALLOWED` only for exit/trim actions; buys gated) or state the gate status explicitly.
- SPOT PRICE: use ONE spot price throughout the decision and timestamp it (e.g. "at 491.65 (09-10 snapshot)") — never two different spot prices for the same name without stating which is which (MSFT 2026-09-10 decision.md cited 491.65 in the exec summary and 490.50 in the thesis for the DCF comparison).
- SIZE CAP EXPLICITNESS: when the computed Position contract size (e.g. 3.6%) is capped down by the name CVaR / budget (e.g. to 3.0% max), say "contract X capped to Y" — never leave two size numbers on the page without stating the cap (MSFT 2026-09-10: contract `size 3.6%` beside a `3.0% max` ceiling with no explicit downgrade).

{NO_EXTERNAL_TOOLS}{get_language_instruction()}{get_output_budget("portfolio")}"""

        def _guardrail_hook(result):
            """Deterministic post-decision guardrail (DSA phase A).

            Only softens/downgrades with a recorded reason; never upgrades.
            `enable_decision_guardrail` gates the structural rules; the
            score<->rating consistency check + confidence cap on degraded
            data quality run when `enable_decision_guardrail` is on.
            """
            try:
                from tradingagents.dataflows.config import get_config
                from tradingagents.strategies.decision_guardrail import (
                    cap_pm_confidence,
                    cap_pm_confidence_on_judge,
                    stabilize_decision,
                    validate_score_action_agreement,
                )

                if not get_config().get("enable_decision_guardrail"):
                    return
                rating = result.rating.value
                # Risk rows come from the structured risk-debate state - the
                # same source the matrix/judge blocks above consume. The old
                # `risk_matrix_block and [{}] or []` iterable was a non-empty
                # STRING, so it always yielded [{}] (severity "") and rule 1
                # could never fire.
                risk_rows = _risk_rows_from_rounds(rds)
                out = stabilize_decision(rating, risk_rows=risk_rows)
                if out["rating"] != rating:
                    result.rating = type(result.rating)(out["rating"])
                    result.guardrail_reason = "; ".join(
                        o["reason"] for o in (out["overrides"] or [])
                    )
                    result.risk_cap = "Hold" if any(
                        "risk-cap" in o["reason"] for o in (out["overrides"] or [])
                    ) else None
                conf, _ = cap_pm_confidence(result.confidence, result.data_quality)
                if conf != result.confidence:
                    result.confidence = conf
                # D1/D2 judge-reliability gate: if the risk-debate judge
                # flipped its winner across the ensemble runs or used a
                # free-text/repair fallback, cap the PM's confidence — the
                # same evidence produced divergent judge verdicts, so the
                # conviction must not ride high on an unreliable read.
                conf, _jreason = cap_pm_confidence_on_judge(
                    result.confidence,
                    judge_agreement=rds.get("judge_agreement"),
                    judge_flip=rds.get("judge_flip"),
                    judge_structured_fallback=rds.get("judge_structured_fallback"),
                )
                if conf != result.confidence:
                    result.confidence = conf
                    result.guardrail_reason = (
                        (result.guardrail_reason + "; " if result.guardrail_reason else "")
                        + (_jreason or "confidence capped: judge unreliable")
                    )
                # score<->rating agreement advisory note (no score field yet ->
                # recorded when a 0-100 score is present in future iterations)
                validate_score_action_agreement(rating, None)  # no-op today
            except Exception:  # noqa: BLE001 - the guardrail degrades, never raises
                return

        _pm_capture: dict = {}

        def _result_hook(result):
            _guardrail_hook(result)
            try:
                _pm_capture["obj"] = result.model_dump(mode="json")
            except Exception:  # noqa: BLE001 - pm_decision is advisory
                _pm_capture["obj"] = None

        final_trade_decision = invoke_structured_or_freetext(
            structured_llm,
            llm,
            prompt,
            render_pm_decision,
            "Portfolio Manager",
            result_hook=_result_hook,
            fallback_llm=fallback_llm,
            backup_llm=backup_llm,
        )

        new_risk_debate_state = {
            "judge_decision": final_trade_decision,
            "history": risk_debate_state["history"],
            "aggressive_history": risk_debate_state["aggressive_history"],
            "conservative_history": risk_debate_state["conservative_history"],
            "neutral_history": risk_debate_state["neutral_history"],
            "latest_speaker": "Judge",
            "current_aggressive_response": risk_debate_state["current_aggressive_response"],
            "current_conservative_response": risk_debate_state["current_conservative_response"],
            "current_neutral_response": risk_debate_state["current_neutral_response"],
            "count": risk_debate_state["count"],
        }

        return {
            "risk_debate_state": new_risk_debate_state,
            "final_trade_decision": final_trade_decision,
            "pm_decision": _pm_capture.get("obj"),
        }

    return portfolio_manager_node

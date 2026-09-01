# Session Handoff — TradingAgents (2026-09-01)

## 1. Task Objective & Scope
- **Goal:** Operationalize and harden the opt-in structured multi-agent debate (research + risk sections, heterogeneous/mixed LLM roles, bounded context, correct grounding) and extend the quant-formula taxonomy into the codebase.
- **Sub-task in progress:** Quant-formula taxonomy expansion — Tier 1 (Hurst/TWAP/VPIN) and Tier 2 (Fama-French 5-factor, Black-Litterman) are DONE and pushed. Remaining optional item: vanilla BSM equity surface + full Greeks table (skipped — Black-76 + vol-surface Δ exist).

## 2. File Manifest & Modifications
**Modified/Created Files (all committed & pushed to `origin/main` unless noted):**
- `tradingagents/graph/setup.py` — SD family + SD Risk nodes (aggressive/conservative/neutral → L1 → Finalize → PM), legacy no-op placeholders, cfg threaded to debaters.
- `tradingagents/graph/conditional_logic.py` — `should_continue_structured_debate(state, section)` section-aware + round-cycling (depth knob drives both sections).
- `tradingagents/graph/trading_graph.py` — `resolve_role_llm` adds `"neutral"`; `debate_llms` resolved per-role.
- `tradingagents/agents/researchers/structured_debate.py` — `SECTION_ROLES`/`SECTION_CHANNEL`/`SECTION_PROSE`; `build_turn_prompt` (static registry + last-turn delta + active disputes, section-aware 1-shot); `bind_debate_structured` (json_mode); `render_consumer_debate_matrix`; `render_judge_evidence` (UNAVAILABLE-aware); `ground_truth_from_state` harvests analyst computed lines; `active_disputes`; `build_or_get_registry`; degraded-turn fallback (never crashes); `_bounded` context caps; registry/store.
- `tradingagents/agents/arbiters/debate_judge.py` — flat `scores[]` rubric read via `_rubric_dimension_dict`; last-non-degraded-payload selection; directed retry + prose-score fallback (rationale parse → rebuttal proxy → honest UNAVAILABLE); "json" token in judge prompt; `_Judge` fakes/cfg.
- `tradingagents/agents/utils/debate_roles.py` — `role_model_spec` maps neutral→`debate_neutral_model`; `build_role_llm_kwargs` adds `debate_temperature`; `DEFAULT_TIER` includes risk roles.
- `tradingagents/agents/schemas.py` — `RiskStance`/`RiskDebaterTurnPayload` (BULL/BEAR→AGGRESSIVE/CONSERVATIVE coercion); `L2JudgeDimensionedRubric` flat `scores` + alias `dimension_scores` + coercers; `RiskFactor`/`QuantitativeClaim` tolerant defaults; list bounds (25).
- `tradingagents/strategies/debate_claim.py` — `ClaimRecord.status` persists L1 verdicts; `resolve_ground_truth_key` (normalize→alias→difflib fuzzy ≥0.72/≥0.08 margin, token-overlap bonus); `KEY_ALIASES` extended; keeps honest `unverified`.
- `tradingagents/strategies/factors.py` — **NEW** `fama_french_5_factor` (OLS, `FF5_FACTORS`, `_ols5`, `_solve`).
- `tradingagents/strategies/portfolio_optimizer.py` — **NEW** `black_litterman_weights` (implied equilibrium + views → max-Sharpe closed form).
- `tradingagents/strategies/mean_reversion.py` — **NEW** `hurst_exponent` (R/S, clamped [0,1], returns/differences input).
- `tradingagents/strategies/momentum.py` — **NEW** `twap`.
- `tradingagents/strategies/orderflow.py` — **NEW** `vpin`.
- `tradingagents/default_config.py` — `TRADINGAGENTS_RESEARCH_DEPTH` (both round counts), `debate_max_output_tokens=4000`, `debate_temperature=0.1`, `debate_json_mode=true`, `debate_regen_max=2`, `TRADINGAGENTS_DEBATE_NEUTRAL_MODEL`.
- `tradingagents/reporting.py` — structured-debate evidence files stay on disk but NOT appended to `complete_report.md`.
- `cli/main.py` — `_CLI_ENTRY` guard on hard-exit paths (moomoo shutdown-block).
- `.env` (gitignored) — BULL/BEAR/JUDGE/NEUTRAL=openrouter:openai/gpt-5.6-luna; `TRADINGAGENTS_ENABLE_DEBATE=true`.
- Tests: `tests/test_debate_{claim,score,integration,stream_hermetic,risk_parity}.py`; `tests/test_strategies_tier1_formulas.py` (14 tests).

**Key design decisions:** json_mode only on debate path (deepseek `supports_tool_choice=False`); judge prompt MUST contain literal "json" (OpenRouter json_object 400 root cause); flat `scores[]` over enum-keyed dict; prose-fallback over two-pass extractor; NORMALIZE→EXACT→ALIAS→FUZZY→honest-unverified key resolution (never fabricated).

**Untouched Dependencies (read-only):** `evaluate.py` (has `deflated_sharpe` + `probabilistic_sharpe` already), `options_math.py` (Black-76), `statistical.py`/`mean_reversion.py` helpers, `value_dip.py`, `risk_governor.py`, `llm_clients/{capabilities,openai_client,factory}.py`, `graph/agent_states.py`, `cli/utils.py`, `docs/*` (design doc §10/§10.6 + README/CHANGELOG already synced).

## 3. Current State & Validation
**Working/Passing:**
- Debate suite: **103 passed** (`test_debate_*` all green). Full repo earlier: 2053 passed / 2 skipped.
- Tier 1+2 quant tests: 14 passed; related `test_strategies_*` 38 passed; ruff clean repo-wide.
- Live runs (all-luna roles+judge): QCOM 145916, DELL 153305 — 15-file reports, **real judge scores** (research 5.5/5.75, risk 5.25/7.17/5.25), zero degraded turns, PM/RM Underweight/Hold, evidence hidden from complete_report.
- FF5 recovers known synthetic coefficients (mkt 1.20, smb −0.60, R² 0.97); BL no-view=market-cap weights, strong view shifts A 0.59→0.96; Hurst H≈0.5 random-walk / H<0.5 mean-rev / H>0.5 trending; VPIN 0.0 balanced/1.0 one-sided; TWAP exact.

**Failing/Incomplete:**
- `(unused)` claim-ledger rows still nonzero on the last completed run (res 53, risk 123) — alias-router committed AFTER that run; a fresh run should be near-zero. If still high, extend `KEY_ALIASES` with new live labels.
- BSM equity surface + full Greeks table not implemented (skipped — deliberate; Black-76 covers).
- No active failing tests.

**Active Errors/Stack Traces:** None. Prior blockers resolved this session (json_object 400 "must contain json"; empty dimension_scores; ragged enums/booleans; degraded-turn crashes; CLI moomoo shutdown-hang).

## 4. Technical Constraints & Decisions
- `py -3.12` only (bare python = wrong venv). Never commit `.env`.
- All `debate_*` features default OFF; legacy one-shot chain must stay bit-identical when `enable_debate` off.
- Compute-as-tools; keep docs true; commit+push after changes. Working agreement §7: deep web search first for decisions.
- Large inline authoring in bash-heredocs corrupts — build small, verify `py_compile` + `ruff` after each change (git checkout reverts whole files; two corruptions occurred this session).
- Live runs via `hub start qcom-run/dell-run`; worker = child pid (launcher has 1 thread); bash bg jobs cap at 300s → use `sleep 280` windows or direct probes; probe helper `_probe2.ps1 -ProcId N`. Real report files at `~/.tradingagents/logs/qcom/2026-08-31/reports/`; sectioned report at `reports/<SYMBOL>_<ts>/`.
- Judge must get non-empty dimension output: prompt contains "json" token + flat `scores[]` shape; 4000 output cap + `debate_regen_max=2`; schemas tolerant to ragged provider output (never hard-crash turns/schemas).
- Key resolution: normalize → exact → alias → confidence-gated fuzzy (threshold 0.72, margin 0.08, token-overlap bonus); never fabricate - worst case honest `unverified`.
- Financial numbers: deterministic computed values only; rounding convention 4-6 dp per metric; all new strat-éachines pure/stdlib-only (no new deps).
# Gate Registry — every gate, its switch, where it fires, and what proves it

Status: **maintained** (2026-09-11). Companion to
`docs/implementation_plan_quant_formula_additions.md` (round-2 additions) and the
risk sections of `docs/api_reference.md`.

Why this exists: three separate audits found gates that **could not fire** — a
limit compared to itself, a guard reading a dict key off a string, a stop measured
from the wrong entry. Those are invisible in code review and invisible in a run
(nothing errors; the gate just never triggers). This file is the place where each
gate's *claim* is written down next to the thing that proves it.

**How it is kept true.** `tests/test_gate_env_toggles.py` machine-checks this
document on every suite run:

1. the key set in the table equals the registry in the test — the doc cannot drift;
2. every key exists in `DEFAULT_CONFIG` **and** has an `_ENV_OVERRIDES` row;
3. flipping each key through the real loader works in **both** directions
   (`_apply_env_overrides`, the same path `.env` takes);
4. every env var below appears in `.env.example`;
5. the **Status** column is verified against the source: a `wired` gate must be
   read somewhere outside `default_config.py`, and an `inert` gate must be read
   by nothing.

**Flipping a gate.** Put the env var in `.env` (uncommented) and restart — config
is read at import, so a running process does not pick up a change:

```dotenv
TRADINGAGENTS_ENABLE_RISK_GOVERNOR=true
TRADINGAGENTS_RISK_MAX_DRAWDOWN_PCT=0.07
TRADINGAGENTS_ENABLE_LIQUIDITY_GATE=true
```

Unknown names are safe: a row naming a key absent from `DEFAULT_CONFIG` raises at
import (`_validate_env_override_targets`), and a value of the wrong type fails the
same way rather than being stored as a truthy string.

---

## 1. Decision gates — these can stop, shrink or reroute a trade

| Key | Env var | What it can do | Enforced at | Proven by | Status |
| --- | --- | --- | --- | --- | --- |
| `enable_risk_governor` | `TRADINGAGENTS_ENABLE_RISK_GOVERNOR` | PASS / WARN / REJECT verdict; a REJECT sets `risk_halt` | `graph/trading_graph.py` (govern call), `strategies/risk_governor.py::govern` | `test_risk_agent_wiring.py`, `test_risk_context_hoist.py`, `test_risk_governor_measured_drawdown.py` | wired |
| `enable_liquidity_gate` | `TRADINGAGENTS_ENABLE_LIQUIDITY_GATE` | ILLIQUID → REJECT, CAUTION → WARN | `strategies/risk_governor.py::govern` (liquidity branch) | `test_risk_context_hoist.py` | wired |
| `enable_hard_guards` | `TRADINGAGENTS_ENABLE_HARD_GUARDS` | hard-guard labels `max_portfolio_risk` / `data_quality_failure` / `insufficient_liquidity` | `graph/trading_graph.py` (hard-guard tuple) | `test_risk_context_hoist.py` | wired |
| `enable_position_contract` | `TRADINGAGENTS_ENABLE_POSITION_CONTRACT` | the position contract: Kelly × risk/stop × vol-target × agreement, clamped | `strategies/contract.py::build_position_contract` | `test_graph_tool_loop.py` | wired |
| `enable_tranche_risk` | `TRADINGAGENTS_ENABLE_TRANCHE_RISK` | worst-case scale-in capital-at-risk and peak-deployed-capital caps | `graph/trading_graph.py::_tranche_risk_read` | `test_graph_tool_loop.py`, `test_risk_agent_wiring.py` | wired |
| `enable_calibration` | `TRADINGAGENTS_ENABLE_CALIBRATION` | confidence calibration buckets | `strategies/calibration.py` | `test_calibration_wiring.py` | wired |
| `enable_agreement` | `TRADINGAGENTS_ENABLE_AGREEMENT` | consensus / agreement scaling of the size | `strategies/consensus.py` | `test_strategies_value_dip.py`, `test_graph_tool_loop.py` | wired |
| `enable_decision_guardrail` | `TRADINGAGENTS_ENABLE_DECISION_GUARDRAIL` | post-PM downgrade-only stabilizer + confidence cap | `agents/managers/portfolio_manager.py` | `test_decision_guardrail.py` | wired |
| `enable_exits` | `TRADINGAGENTS_ENABLE_EXITS` | exit / stop arithmetic on a held position | `strategies/contract.py` | `test_v2_v5_wiring.py` | wired |
| `enable_kelly_alloc` | `TRADINGAGENTS_ENABLE_KELLY_ALLOC` | portfolio-level fractional-Kelly allocation | `strategies/portfolio.py` | `test_formulas_p3.py` | wired |
| `enable_correlation_penalty` | `TRADINGAGENTS_ENABLE_CORRELATION_PENALTY` | down-weight a name whose average pairwise correlation with the book is high | `strategies/portfolio.py` | `test_strategies_portfolio.py` | wired |
| `enable_pre_market_review` | `TRADINGAGENTS_ENABLE_PRE_MARKET_REVIEW` | same-night pre-market re-check artefact beside the report | `batch.py::_batch_pre_market_check` | `test_batch_pre_market_parity.py` | wired |
| `enable_preopen_depth` | `TRADINGAGENTS_ENABLE_PREOPEN_DEPTH` | pre-open depth read in the run | `graph/trading_graph.py` | `test_risk_agent_wiring.py` | wired |
| `risk_audit_enabled` | `TRADINGAGENTS_RISK_AUDIT_ENABLED` | tamper-evident hash-chained risk audit ledger | `graph/trading_graph.py` | `test_graph_tool_loop.py` | wired |
| `regime_state_enable` | `TRADINGAGENTS_REGIME_STATE_ENABLE` | regime-state size multiplier | `graph/trading_graph.py`, `strategies/regime_state.py` | — (no gate test yet) | wired |
| `vol_cap_enable` | `TRADINGAGENTS_VOL_CAP_ENABLE` | volatility-cap size multiplier | `graph/trading_graph.py` | — (no gate test yet) | wired |
| `enable_sector_multifactor` | `TRADINGAGENTS_ENABLE_SECTOR_MULTIFACTOR` | sector multi-factor ranking read | `agents/utils/analysis_tools.py` | `test_analysis_tools.py` | wired |
| `enable_sector_industry` | `TRADINGAGENTS_ENABLE_SECTOR_INDUSTRY` | parent-gated industry-group ranking | `agents/utils/analysis_tools.py` | `test_analysis_tools.py` | wired |
| `enable_sector_breadth` | `TRADINGAGENTS_ENABLE_SECTOR_BREADTH` | constituent breadth / leadership ratio | `agents/utils/analysis_tools.py` | `test_analysis_tools.py` | wired |
| `enable_sector_eodhd_constituents` | `TRADINGAGENTS_ENABLE_SECTOR_EODHD_CONSTITUENTS` | vendor constituents for the sector table | `agents/utils/analysis_tools.py` | `test_analysis_tools.py` | wired |
| `enable_spread_estimator` | `TRADINGAGENTS_ENABLE_SPREAD_ESTIMATOR` | quote-free spread floor line + `get_spread_estimate` | `agents/utils/quant_formula_tools.py`, `agents/utils/market_position_tools.py` | `test_quant_formula_tools.py`, `test_liquidity_spread.py` | wired |
| `enable_book_risk_sizing` | `TRADINGAGENTS_ENABLE_BOOK_RISK_SIZING` | minimum-CVaR book sizing under the existing budget | `agents/utils/quant_formula_tools.py`, `strategies/book_risk.py` | `test_quant_formula_tools.py`, `test_book_risk_sizing.py` | wired |
| `enable_conformal_bands` | `TRADINGAGENTS_ENABLE_CONFORMAL_BANDS` | calibrated valuation band with realized coverage | `agents/utils/quant_formula_tools.py`, `strategies/conformal.py` | `test_quant_formula_tools.py`, `test_conformal_bands.py` | wired |
| `enable_return_decomposition` | `TRADINGAGENTS_ENABLE_RETURN_DECOMPOSITION` | overnight vs intraday leg decomposition | `agents/utils/quant_formula_tools.py`, `strategies/market_session.py` | `test_quant_formula_tools.py`, `test_return_decomposition.py` | wired |
| `enable_text_factors` | `TRADINGAGENTS_ENABLE_TEXT_FACTORS` | deterministic tone / readability / divergence read | `agents/utils/quant_formula_tools.py`, `strategies/text_factors.py` | `test_quant_formula_tools.py`, `test_text_factors.py` | wired |
| `enable_bocpd` | `TRADINGAGENTS_ENABLE_BOCPD` | calibrated changepoint probability in the shift read | `agents/utils/analysis_tools.py`, `strategies/regime.py` | `test_bocpd.py` | wired |
| `backtest_limit_threshold` | `TRADINGAGENTS_BACKTEST_LIMIT_THRESHOLD` | limit-up/down tradability in backtest fills (0 = off) | `scripts/backtest_strategy.py` | — (no gate test yet) | wired |
| `backtest_volume_participation` | `TRADINGAGENTS_BACKTEST_VOLUME_PARTICIPATION` | fill capped at a share of the day's volume (0 = off) | `scripts/backtest_strategy.py` | — (no gate test yet) | wired |

## 2. Debate-integrity gates — these can stop a run

The structured debate (`enable_debate`) verifies every debater claim against
computed ground truth before the judge scores it. These two flags decide what
happens when that is impossible — and both used to be **decorative**: one
printed an `ERROR:` line and ran on, the other was read by nothing at all (a
live run wrote a legacy free-form debate with the matrix "required").

| Key | Env var | What it can do | Enforced at | Proven by | Status |
| --- | --- | --- | --- | --- | --- |
| `debate_require_capability_matrix` | `TRADINGAGENTS_DEBATE_REQUIRE_CAPABILITY_MATRIX` | **raises** `DebateCapabilityError` at graph compile time when any debate role's model cannot meet its role floor (context / structured output / tool binding) — each role is assessed on the model it actually runs on, its `debate_*_model` or the tier fallback (quick for bull/bear/risk, deep for judge); advisory warning when off | `strategies/debate_capability.py::check_debate_capabilities` (called from `graph/trading_graph.py`) | `test_debate_fail_closed.py::TestCapabilityMatrixFailsClosed` | wired |
| `debate_baseline_fallback` | `TRADINGAGENTS_DEBATE_BASELINE_FALLBACK` | on (default) terminates an unverifiable debate and the pre-debate baseline stances stand; **off raises** `DebateBaselineFallbackError` with the L1 reason instead of writing an unverified debate | `agents/researchers/structured_debate.py::_baseline_termination` (`create_debate_l1`, research + risk) | `test_debate_fail_closed.py::TestBaselineFallbackFailsClosed` | wired |

## 3. Numeric limits the gates read

| Key | Env var | What it bounds | Enforced at | Proven by | Status |
| --- | --- | --- | --- | --- | --- |
| `max_position_pct` | `TRADINGAGENTS_MAX_POSITION_PCT` | single-name position cap (default 30%) | `strategies/risk_governor.py::default_limits` | `test_strategies_risk_governor.py` | wired |
| `risk_max_position_pct` | `TRADINGAGENTS_RISK_MAX_POSITION_PCT` | whole-book position cap (default 45%) | `strategies/risk_governor.py::default_limits` | `test_risk_agent_wiring.py` | wired |
| `sector_cap_limit` | `TRADINGAGENTS_SECTOR_CAP_LIMIT` | sector concentration cap (default 35%) | `strategies/risk_governor.py::default_limits` | `test_formulas_p3.py` | wired |
| `risk_max_drawdown_pct` | `TRADINGAGENTS_RISK_MAX_DRAWDOWN_PCT` | measured book drawdown that blocks new risk (default 10%) | `strategies/book_risk.py::drawdown_gate`, `risk_governor.py` | `test_risk_governor_measured_drawdown.py`, `test_strategies_book_risk.py` | wired |
| `risk_daily_cvar_budget_pct` | `TRADINGAGENTS_RISK_DAILY_CVAR_BUDGET_PCT` | daily book CVaR budget (default 3%) | `strategies/risk_governor.py::govern` | `test_book_risk_sizing.py`, `test_risk_context_hoist.py` | wired |
| `risk_daily_loss_budget_pct` | `TRADINGAGENTS_RISK_DAILY_LOSS_BUDGET_PCT` | daily loss limit (default 3%) | `strategies/risk_governor.py::govern` | — (no gate test yet) | wired |
| `risk_hwm_soft_pct` | `TRADINGAGENTS_RISK_HWM_SOFT_PCT` | high-water-mark drawdown → WARN (default 10%) | `strategies/risk_governor.py::govern` | — (no gate test yet) | wired |
| `risk_hwm_hard_pct` | `TRADINGAGENTS_RISK_HWM_HARD_PCT` | high-water-mark drawdown → REJECT (default 20%) | `strategies/risk_governor.py::govern` | — (no gate test yet) | wired |
| `catalyst_hard_block_days` | `TRADINGAGENTS_CATALYST_HARD_BLOCK_DAYS` | earnings window that forces REJECT regardless of size (default 5) | `strategies/catalyst.py`, `graph/trading_graph.py` | `test_strategies_catalyst.py` | wired |
| `market_stress_vol_cap` | `TRADINGAGENTS_MARKET_STRESS_VOL_CAP` | size cap under market stress (default 0.85) | `strategies/regime.py` | `test_strategies_regime.py` | wired |
| `value_dip_regime_vol_cap` | `TRADINGAGENTS_VALUE_DIP_REGIME_VOL_CAP` | volatility above which a dip entry is refused (default 0.8) | `strategies/regime.py` | — (no gate test yet) | wired |

## 4. Inert flags — declared, read by nothing

These are in `DEFAULT_CONFIG`, appear in older docs as if they were gates, and are
now settable from `.env` — but **no code reads them**, so flipping them changes
nothing. They are listed here so nobody trusts them, and the registry test proves
the `inert` claim on every run (a key that gains a reader will fail the suite and
force this row to be updated).

| Key | Env var | What it was meant to do | Status |
| --- | --- | --- | --- |
| `enable_threshold_gate` | `TRADINGAGENTS_ENABLE_THRESHOLD_GATE` | the PBO / threshold gate from the decision-hardening spec | inert |
| `enable_risk_manager` | `TRADINGAGENTS_ENABLE_RISK_MANAGER` | a separate risk-manager stage | inert |
| `enable_skill_overlays` | `TRADINGAGENTS_ENABLE_SKILL_OVERLAYS` | skill-based overlays | inert |
| `enable_trailing_exit` | `TRADINGAGENTS_ENABLE_TRAILING_EXIT` | trailing-exit arming (the trailing arithmetic itself lives in the exits layer, which is gated by `enable_exits`) | inert |
| `value_dip_regime_gate` | `TRADINGAGENTS_VALUE_DIP_REGIME_GATE` | strict block of dip entries in high-vol / fast-downtrend regimes (the vol cap it was paired with, `value_dip_regime_vol_cap`, *is* read) | inert |
| `volume_share_vol_limit` | `TRADINGAGENTS_VOLUME_SHARE_VOL_LIMIT` | a volume-share volatility limit | inert |
| `enable_regime` | `TRADINGAGENTS_ENABLE_REGIME` | a regime overlay switch | inert |
| `enable_factors` | `TRADINGAGENTS_ENABLE_FACTORS` | a factor overlay switch | inert |

## 5. Always-on checks (no switch)

Not flippable by design — they are integrity checks, not policy:

- **Data quality fails closed for a new position**: `graph/trading_graph.py::_data_quality_blocks_position`
  blocks only when the PM positively reported `stale` / `partial`; an omitted
  field never blocks (`test_schema_contract.py`).
- **Point-in-time fundamentals**: `strategies/data_quality.py::fundamentals_pit_ok`
  (`test_data_quality_falsification.py`).
- **Factor-expression purity**: `strategies/alpha_zoo.py::purity_gate` refuses a
  non-pure expression (`test_alpha_zoo.py`).
- **Report claim checks (advisory, never block delivery)**: the verifier's
  GROUNDED / UNSUPPORTED / CONTRADICTED / INTERNAL_CONFLICT verdicts, including
  `tone_claim_conflict` and `valuation_band_conflict`
  (`test_verifier_formula_checks.py`, `test_report_verify.py`).
- **Debate degradation is recorded and flagged**: `reporting.py::_run_card_debate`
  writes a `debate` block into `run_card.json` (`enabled` / `evidence` /
  `degraded` / `reason`) and prints a named stderr line when `enable_debate` is
  on but `2_research/structured_debate.md` was not written (`test_reporting.py`);
  `report_verifier.py::_debate_degradation` re-checks it tree-level so
  `scripts/report_verify.py` prints `debate DEGRADED` and exits non-zero
  (`test_report_verify.py`). A degraded run is thus auditable from the tree and
  from the verifier, instead of inferred from prose.

## 6. Adding a gate — the rule

A new gate is not done until: (1) it has a key in `DEFAULT_CONFIG`, (2) an
`_ENV_OVERRIDES` row so it is flippable from `.env`, (3) a row in this file with
its enforcement site, (4) a test that **fails when the gate is ignored** (the
mutations in the phase plans are the pattern), and (5) a CHANGELOG entry. The
registry test enforces 1, 2, 3 and 4's existence; only a human can enforce 4's
quality, which is why the "Proven by" column exists.

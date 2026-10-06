# Gate Registry — every registered policy, data-surface and context gate: its switch, where it fires, and what proves it

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
4. every env var below appears in `.env.example` **and** in the live `.env` (created at its
   `DEFAULT_CONFIG` value when the name is absent, never overwritten — owner rule, 2026-09-24);
5. the **Status** column is verified against the source: a `wired` gate must be
   read somewhere outside `default_config.py`, and an `inert` gate must be read
   by nothing.

**What this file covers.** The rows below are every policy, data-surface and
context gate: **all 117 of the 117 `enable_*` keys** in `DEFAULT_CONFIG`, plus
the numeric limits and the always-on checks. R4 stage 2 registered the last six
families — the score-engine gates (§7e), the debate and run-shape flags (§7f),
the factor-model family (§7g), the event family (§7h), the vendor and screener
surfaces (§7i), the score and aggregation flags (§7j) and the remaining odds and
ends (§7k). Four of them are **inert** — declared and settable but read by
nothing — and their rows say so: `enable_factor_model`,
`enable_factor_proposal_loop`, `enable_tuner` and `enable_value_dip`. Every
other newly registered row carries a `Proven by` cell naming the test or the
code path that fires it, verified when the row was added.

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
| `enable_mechanical_volume_discount` | `TRADINGAGENTS_ENABLE_MECHANICAL_VOLUME_DISCOUNT` | the VDU trigger's RVOL is recomputed over the prior window MINUS the OPEX-week / witching sessions, so expiration turnover cannot manufacture a breakout (needs bar dates; unmeasured without them) | `strategies/value_dip.py::trigger_candle` (via `agents/utils/value_dip_tools.py`) | `test_volume_flags.py` | wired |
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
| `risk_max_drawdown_pct` | `TRADINGAGENTS_RISK_MAX_DRAWDOWN_PCT` | measured book drawdown that blocks new risk (default 10%) | `strategies/book_context.py::measured_book_drawdown` (one resolver), `strategies/book_risk.py::drawdown_gate`, `risk_governor.py` | `test_risk_governor_measured_drawdown.py`, `test_strategies_book_risk.py`, `test_book_context.py` | wired |
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
- **The Moomoo SDK cannot hold the interpreter open**: `dataflows/moomoo.py::_daemonise_sdk_threads`
  sets the SDK's `SysConfig.ALL_THREAD_DAEMON` before the first context is constructed, and
  `_close_orphan_executor` stops the executor the SDK installs while closing one
  (`open_context_base._close_callback_executor`). Both exist because a full test run printed its
  summary and then hung ~50 min: MainThread parked in `threading._shutdown` joining two non-daemon
  `callback_executor` threads. `test_moomoo_conn_cap.py`.
- **Debate degradation is recorded and flagged**: `reporting.py::_run_card_debate`
  writes a `debate` block into `run_card.json` (`enabled` / `evidence` /
  `degraded` / `reason`) and prints a named stderr line when `enable_debate` is
  on but `2_research/structured_debate.md` was not written (`test_reporting.py`);
  `report_verifier.py::_debate_degradation` re-checks it tree-level so
  `scripts/report_verify.py` prints `debate DEGRADED` and exits non-zero
  (`test_report_verify.py`). A degraded run is thus auditable from the tree and
  from the verifier, instead of inferred from prose.
- **One producer per measured number**: the book drawdown is resolved only by
  `strategies/book_context.py::measured_book_drawdown` (the configured
  `risk_basket_*` book, one log-return conversion, a labelled source), and the
  governor, the report's `Book drawdown` line and the analyst/trader tools all
  read that one value. A caller-supplied `drawdown_pct` on `get_risk_gate` is a
  labelled what-if and never decides a verdict; the contract stop records the
  ATR and its `h/l` vs `proxy` basis; `research_decision.json` derives
  `data_quality` / `sources_*` / `invalidations` from the tool evidence
  (`test_book_context.py`, `test_research_decision_emission.py`).

## 6. Data-surface gates — these add a source, never a decision

Neither gate can change a rating, a size or a verdict. They decide whether a run
*reads* a data surface at all, and each is off by default, so a gate-off run is
byte-identical to the run before it existed.

| Key | Env var | What it can do | Enforced at | Proven by | Status |
| --- | --- | --- | --- | --- | --- |
| `enable_moomoo_snapshot` | `TRADINGAGENTS_ENABLE_MOOMOO_SNAPSHOT` | reads the live historical-K-line quota before a screener run (warns, and refuses at zero) and enables the batched market-snapshot reader | `scripts/value_screener.py` (pre-flight), `tradingagents/dataflows/moomoo.py::get_market_snapshot_moomoo`, `tradingagents/dataflows/moomoo.py::get_kl_quota_moomoo` | `test_moomoo_snapshot.py` | wired |
| `enable_analyst_estimates` | `TRADINGAGENTS_ENABLE_ANALYST_ESTIMATES` | supplies the estimate-change leg (`RevEC`) from the vendor's 90-day estimate trend, so a leg that was permanently `unavailable` becomes measured | `scripts/value_screener.py` (`--revision-index`), `tradingagents/dataflows/yfinance_sector.py::fetch_estimate_trend` | `test_analyst_estimates_wiring.py` | wired |
| `enable_eodhd_rates` | `TRADINGAGENTS_ENABLE_EODHD_RATES` | reads the EODHD rate/reference surface: TIPS real yields and the nominal-minus-real inflation expectation (so the equity risk premium `dcf.wacc_from_beta` assumes becomes measurable), the Treasury bill **auction** table (discount/coupon, `maturity_date`, `cusip` — a bill curve point is not a note curve point), and FIGI / LEI / CUSIP for the ranked names (the CIK is a labelled cross-check only; `sec_edgar._cik_for` owns that join). Also the market-wide last session (`/eod-bulk-last-day`, batched: one call, the whole exchange — used as a session confirmation and coverage cross-check on the ranked names, **never** as a price contributor), and the news term weights behind the top ranked names (a descriptive reference read, ~40 s per name; `/sentiments` still owns the news-derived number) | `scripts/value_screener.py` (`--rates`), `tradingagents/dataflows/eodhd.py::get_real_yield_rates_eodhd`, `tradingagents/dataflows/eodhd.py::inflation_expectation_eodhd`, `tradingagents/dataflows/eodhd.py::get_bill_auction_rates_eodhd`, `tradingagents/dataflows/eodhd.py::map_identifiers_eodhd`, `tradingagents/dataflows/eodhd.py::bulk_last_day_index_eodhd`, `tradingagents/dataflows/eodhd.py::news_word_weights_eodhd` | `test_eodhd_rates.py` | wired |

## 7. Context gates — these change what the decision model reads

A context gate changes the *representation* of the decision channel, never a
decision, a size or a verdict. It is off by default, so a gate-off run is
byte-identical to the run before it existed.

| Key | Env var | What it can do | Enforced at | Proven by | Status |
| --- | --- | --- | --- | --- | --- |
| `enable_decision_packet` | `TRADINGAGENTS_ENABLE_DECISION_PACKET` | replaces `computed_decision_context` with ONE bounded, deterministic Decision Packet for the decision model, and supplies the §8 uncertainty counters that Phase 0 recorded as `null` | `tradingagents/strategies/decision_packet.py::decision_packet_or_context` (the gate), `::render_decision_packet` (the render), `tradingagents/reporting.py::_run_card_decision_context` (the `packet_chars` measurement) | `test_decision_packet.py` | wired |
| `enable_context_expansion` | `TRADINGAGENTS_ENABLE_CONTEXT_EXPANSION` | §11: attaches the analyst reports, named and bounded, to the decision context when the evidence is DIVIDED; records `context_mode: packet+expanded` so the expansion rate is measurable | `tradingagents/strategies/decision_packet.py::expansion_decision` (the trigger), `::render_expansion` (the render), `::create_decision_packet_node` (the write) | `test_decision_packet.py` | wired |
| `enable_decision_challenge` | `TRADINGAGENTS_ENABLE_DECISION_CHALLENGE` | §10: ONE closed-vocabulary call after the decision that may only DOWNGRADE, and only on one of three grounds, each re-checked mechanically against the packet | `tradingagents/strategies/decision_challenge.py::run_challenge` (the pass), `::adjudicate_challenge` (the decider), `tradingagents/agents/managers/portfolio_manager.py::_challenge_hook` (the site) | `test_decision_challenge.py` | wired |
| `enable_computed_context` | `TRADINGAGENTS_ENABLE_COMPUTED_CONTEXT` | the Phase A-E deterministic block (regime gate / re-rating / trade plan card / risk snapshot / drift hint) injected into the Trader, PM and risk-debator prompts | `tradingagents/graph/trading_graph.py` (`_compiled_decision_context` call) | `test_gate_env_toggles.py` | wired |

## 7b. Data-surface gates — these add a source, never a decision

A data-surface gate adds a *producer*. It never changes a threshold, a size or a
verdict; while it is off its tools return a `DATA_DISABLED` sentinel, so a
gate-off run is byte-identical to the run before the surface existed.

| Key | Env var | What it can do | Enforced at | Proven by | Status |
| --- | --- | --- | --- | --- | --- |
| `enable_options_surface` | `TRADINGAGENTS_ENABLE_OPTIONS_SURFACE` | CBOE delayed options chain: strike / DTE / IV / greeks, exactly as CBOE delivers them | `tradingagents/agents/utils/analysis_tools.py::get_options_surface` (the `_feature_gate` call) | `test_phase3_gate_proofs.py` (the gate fires both ways), `test_cboe.py` (the vendor) | wired |
| `enable_risk_free_curve` | `TRADINGAGENTS_ENABLE_RISK_FREE_CURVE` | NY Fed SOFR history and the Treasury par-yield curve | `tradingagents/agents/utils/analysis_tools.py::get_sofr_curve` / `::get_treasury_curve` (the `_feature_gate` calls) | `test_phase3_gate_proofs.py` (the gate fires both ways), `test_federal_reserve.py` (the vendor) | wired |
| `enable_benzinga_surface` | `TRADINGAGENTS_ENABLE_BENZINGA_SURFACE` | the Benzinga event surface: corporate guidance revisions, FDA/clinical milestones, secondary offerings, individual analyst actions, and news retraction ids | `tradingagents/agents/utils/benzinga_tools.py::get_guidance_revisions` / `::get_fda_calendar` / `::get_offerings_calendar` / `::get_analyst_actions` / `::get_news_removed` (the `_feature_gate` calls) | `test_benzinga_surface.py` | wired |

`enable_benzinga_surface` is one gate for five tools because they are one
vendor's surface with one risk profile and one opt-in: all five read a
registered Benzinga key, all five are additive evidence, and none of them can
change a decision on its own.

**The one context gate that defaults ON.** `enable_computed_context` is `True` in
`DEFAULT_CONFIG`, unlike every other row above. That is deliberate: the block was
built **unconditionally** for its whole life while `.env.example` and the CHANGELOG
documented the variable as the switch, so the variable was inert and the shipped
behaviour was "always on". Defaulting it `False` here would have silently dropped a
shipped prompt block from every run that does not carry `.env` — a behaviour change
disguised as a gate registration. The gate is real now (setting it `false` stops the
injection); only its default is the historical one.

## 7c. Post-run output gates — these add an artefact, never a decision

A post-run output gate runs *after* the report is written and adds an artefact to
the report tree - a new file, or a new `run_card.json` key. It cannot change a
rating, a size, a verdict or anything the model reads: by the time it runs, the
decision is already saved. It is off by default, so a gate-off run produces
exactly the tree it produced before the gate existed.

| Key | Env var | What it can do | Enforced at | Proven by | Status |
| --- | --- | --- | --- | --- | --- |
| `enable_security_context` | `TRADINGAGENTS_ENABLE_SECURITY_CONTEXT` | writes the deterministic classification block: the provider's sector and industry **verbatim with the source that produced them**, the canonical sector, the SPDR key, the SEC SIC when an earlier step already fetched a submissions payload, and the declared theme priority order with its matrix version. It makes **no network call of its own** and adds **zero** decision-context characters - it never enters the decision channel. The prior **cannot gate**: `candidate_themes` is a union, so every registered theme stays a candidate and a wrong cell costs a missed *earlier* check, never a missed theme | `tradingagents/reporting.py`::`_run_card_security_context` (the block), `tradingagents/strategies/security_context.py`::`build_security_context` / `::candidate_themes` / `::theme_priority_order` / `::render_security_context_basis` | `test_security_context.py` (provenance, the widening property, the validator, the gate both ways), `test_gate_env_toggles.py` (the registry) | wired |
| `enable_pplx_decider` | `TRADINGAGENTS_ENABLE_PPLX_DECIDER` | runs a **second** decisions-API judge over the same four analyst reports, **after** `enable_jev_verdict`, and writes `pplx_verdict.json` beside `jev_verdict.json`: Perplexity's `perplexity/pplx-decider-v1-27b` on the same `/api/alpha/decisions` endpoint, the same buy/hold/sell battery and the same position neutralisation. Gated separately so enabling one paid judge cannot silently start a second; one file per decider so the two verdicts sit side by side and neither overwrites the other | `batch.py::post_save_annotations` (the dispatcher), `batch.py::_batch_pplx_decider` (the hook), `tradingagents/jev.py::judge_tree` / `judge_tree_all` (the pass - `DECIDERS[1]`) | `test_jev_verdict_hook.py` (the gate fires both ways and the second file lands beside the first), `test_jev_decide.py` (the recipe) | wired |
| `enable_noul_decider` | `TRADINGAGENTS_ENABLE_NOUL_DECIDER` | runs a **third** decisions-API judge over the same four analyst reports, **after** both others, and writes `noul_verdict.json` beside the other two: Respan's `respan/span-01` on the same `/api/alpha/decisions` endpoint, the same position neutralisation, but a **noul-only battery** (`NOUL_QUESTIONS`) - that model refuses `choice` and `score` with a 400 naming the question and refuses a `criteria` key on a `noul` one, so the shared buy/hold/sell battery cannot be asked of it at all. Its per-stem roll-up lands under `scores`, deliberately not `ratings`. Probed 2026-10-06: its answers are deterministic, report `output_tokens: 0`, `span-01-lite` is byte-identical to `span-01`, and the number does not track the polarity it is asked for (a bullish document scored below a bearish one) - a document statistic, not a rating. Gated separately so a third judge is its own opt-in | `batch.py::post_save_annotations` (the dispatcher), `batch.py::_batch_noul_decider` (the hook), `tradingagents/jev.py::judge_tree` (the recipe dispatch), `tradingagents/jev.py::noul_verdict_for_tree` (the pass - `DECIDERS[2]`) | `test_jev_verdict_hook.py` (the gate fires both ways, the third file lands in the tree, the noul battery carries no `criteria`, the roll-up is `scores` and never `ratings`, and a vendor 400 is recorded rather than raised) | wired |
| `enable_jev_verdict` | `TRADINGAGENTS_ENABLE_JV_VERDICT` | judges the four **analyst** reports with the TypeSafe decisions model, their position language neutralised, and writes `jev_verdict.json` (buy/hold/sell per report) into the report tree | `batch.py::post_save_annotations` (the dispatcher - called by `analyze` after `save_reports`, and by `cli/main.py::save_report_to_disk` for an interactive run), `batch.py::_batch_jev_verdict` (the hook), `tradingagents/jev.py::judge_tree` (the pass) | `test_jev_verdict_hook.py` (the gate fires both ways, the JSON lands in the tree, and the interactive CLI's writer calls the same dispatcher), `test_jev_decide.py` (the recipe) | wired |

`enable_jev_verdict`, `enable_pplx_decider` and `enable_noul_decider` are the
only gates that write an artefact rather than reading a surface, which is why
they are not in §6, §7 or §7b. They are also the only ones whose dependency can
be absent without being an error: the engine does not require
`OPENROUTER_API_KEY`, so the hook skips with a log line rather than failing, and
each is best-effort like `enable_pre_market_review` - a judge that annotates a
finished run must never fail it. The judges' model, endpoint and per-call timeout
are the `.env` keys `TRADINGAGENTS_JEV_MODEL` / `TRADINGAGENTS_JEV_ENDPOINT` /
`TRADINGAGENTS_JEV_TIMEOUT` (defaults `typesafe/jev-1.13`, the alpha decisions
endpoint, 300 s), plus `TRADINGAGENTS_PPLX_DECIDER_MODEL` for the second decider
and `TRADINGAGENTS_NOUL_DECIDER_MODEL` for the third - not code literals. **The
decisions route is `/api/alpha/decisions` for ALL THREE models.** The Perplexity
model is advertised elsewhere as living at `/api/v1/decisions`; that path is a
**404** (probed 2026-10-05), so the second decider uses the same alpha route as
the first and only the `model` differs. The third is on a different **contract**
as well as a different model: Respan's decisions models answer `noul` questions
only - and refuse a `criteria` key on those - so `judge_tree` routes a
`recipe="noul"` decider to `noul_verdict_for_tree` rather than
`verdict_for_tree`. Asking it the shared battery would be a 400, not a worse
answer, and its roll-up is keyed `scores` rather than `ratings` because a
deterministic document statistic is not a buy/hold/sell call.

**Every writer of a finished tree calls `post_save_annotations`, and there are three.**
`batch.py::analyze` (the batch CLI and trading_web's in-process `run_batch`),
`cli/main.py::save_report_to_disk` (the interactive CLI) and `pipeline.py` (which
goes through `analyze`). The interactive CLI was the missing one until
2026-09-28, which is why two trees written that way are 9-entry trees with no
`jev_verdict.json` against 10 for every batch tree. A fourth writer,
`tradingagents/graph/trading_graph.py::save_reports` (documented for ad-hoc
`propagate()` + `save_reports()` calls), still annotates nothing. No observed
tree came from it, and adding the hook there would put a network call inside the
widely-tested tree writer, so it is recorded here rather than changed.

## 7d. Paper-survey instrument gates - these add a diagnostic, never a decision

An instrument gate adds a **read of what is already loaded**: a coverage window, a ledger, an
interval, a proxy. It never changes a threshold, a size, a rating or a verdict, and it is off by
default, so a gate-off run is byte-identical to the run before it existed. Every one of these
reads is a *reader of an existing producer*, never a second authority over that quantity
(inherited ground rule 2), and every one reports its window or returns `unavailable` rather than
a number computed over a padded one (ground rule 4).

| Key | Env var | What it can do | Enforced at | Proven by | Status |
| --- | --- | --- | --- | --- | --- |
| `enable_coverage_window` | `TRADINGAGENTS_ENABLE_COVERAGE_WINDOW` | reports the coverage window a panel statistic was computed over, and refuses the statistic on a padded one (leading missing bars) | `tradingagents/strategies/data_quality.py`::`panel_statistic` (the `padded_days > 0` refusal), `tradingagents/strategies/coverage_window.py`::`coverage_window` (the window read) | `test_coverage_window.py` | wired |
| `enable_rn_skew_proxy` | `TRADINGAGENTS_ENABLE_RN_SKEW_PROXY` | a cross-strike OTM risk-neutral skewness PROXY (>= 5 strikes, else `unavailable`) reported beside the surface read, with the regime cell it was conditioned on | `tradingagents/agents/utils/analysis_tools.py`::`get_vol_surface_shape` (the `_flag` read), `tradingagents/strategies/options_surface.py`::`rn_skew_proxy` (the proxy) | `test_rn_skew_proxy.py` | wired |
| `enable_trend_spectral` | `TRADINGAGENTS_ENABLE_TREND_SPECTRAL` | spectral excess mass and the cost-optimal span reported BESIDE the swing factor (never inside its score), so a trend read states when it deserves weight | `tradingagents/strategies/swing.py`::`_trend_spectral_read` (the guarded read), `tradingagents/strategies/technical_factors.py`::`spectral_excess_mass` / `::cost_optimal_span` | `test_strategies_technical_factors.py` | wired |
| `enable_trial_ledger` | `TRADINGAGENTS_ENABLE_TRIAL_LEDGER` | reads the trial count and the trials' Sharpe dispersion back from the append-only ledger, so a deflated number is deflated by a MEASURED search and not by a caller's assertion | `tradingagents/strategies/evaluate.py`::`_selection_threshold` (the dispersion branch, ignored unless the gate is on), `tradingagents/strategies/trial_ledger.py`::`gate_on` / `::record` / `::trial_stats` | `test_trial_ledger.py` | wired |
| `enable_jump_robust_proxies` | `TRADINGAGENTS_ENABLE_JUMP_ROBUST_PROXIES` | daily-bar bipower and quarticity PROXIES plus the jump share they imply, so a tail read can say whether the tail came in one print or in a diffusion | `tradingagents/strategies/volatility_models.py`::`jump_robust_proxies_enabled` (the read), `tradingagents/strategies/book_risk.py`::`_jump_read` (the tail read that fires it) | `test_volatility_models.py` | wired |
| `enable_mp_lower_spectrum` | `TRADINGAGENTS_ENABLE_MP_LOWER_SPECTRUM` | counts the panel correlation eigenvalues below the Marchenko-Pastur lower bound - a collapse in the effective number of independent bets as a count rather than a story. PRINTED, never scored: `regime_score` attaches it as `printed["mp_lower_spectrum"]` beside R5's block and `get_regime_score` renders it under the component table (a panel-wide eigen-count is a backdrop, not a 0-100 leg). It used to be computed into `market_breadth`'s dict and dropped, with the engine's call site passing no `cfg` at all | `tradingagents/strategies/sector_breadth.py`::`mp_lower_spectrum` (the only reader of the gate; `None` when off), attached by `tradingagents/strategies/market_breadth.py`::`market_breadth` (which `_market_breadth_read` now calls WITH the run's config) and printed by `tradingagents/strategies/regime_score.py`::`_attach_printed_reads` / `_spectrum_printed` | `test_strategies_market_breadth.py`, `test_forward_stress_probability.py` | wired |
| `enable_long_memory` | `TRADINGAGENTS_ENABLE_LONG_MEMORY` | a rolling semiparametric memory parameter (GPH and local Whittle) plus a HAR-family realized-volatility forecast, with d reported BESIDE the forecast rather than instead of it | `tradingagents/strategies/long_memory.py`::`long_memory_enabled` (the read), read by `tradingagents/strategies/mean_reversion.py`::`memory_profile` | `test_long_memory.py` | wired |
| `enable_bootstrap_intervals` | `TRADINGAGENTS_ENABLE_BOOTSTRAP_INTERVALS` | an autocorrelation-aware interval for a claim statistic - a moving-block bootstrap whose block length comes from the series' own ACF decay, checked against an ADF stationarity test - plus the information-gap axis, which says whether a band is wide because it knows something | `tradingagents/strategies/conformal.py`::`_bootstrap_gate` (the read), `::`iid_interval` / `::`block_bootstrap_interval` / `::`information_gap` / `::`block_length` (the estimators), added to `::`rolling_band` beside its realized coverage | `test_bootstrap_intervals.py` | wired |
| `enable_event_iv_lift` | `TRADINGAGENTS_ENABLE_EVENT_IV_LIFT` | the ATM term-structure shape around a scheduled catalyst indexed in EVENT time (days to the meeting, not calendar days to expiry), refusing when the calendar certifies no meeting and valuing nothing past it | `tradingagents/agents/utils/analysis_tools.py`::`get_vol_surface_shape` (the `_flag` read), `tradingagents/strategies/options_surface.py`::`pre_event_iv_lift` (the read) | `test_options_surface.py` | wired |
| `enable_triadic_stress` | `TRADINGAGENTS_ENABLE_TRIADIC_STRESS` | names WHERE a cross-sectional stress is centred - a triadic stress index over the correlation network with a per-node diag(A^3) epicentre - labelled coincident on every read and refused on a thin cross-section | `tradingagents/strategies/triadic_stress.py`::`_gate_on` (the read) / `::`triadic_stress`, registered PRINTED in `tradingagents/strategies/risk_score.py`::COMPONENTS | `test_triadic_stress.py` | wired |
| `enable_refusal_ledger` | `TRADINGAGENTS_ENABLE_REFUSAL_LEDGER` | records candidates the engine REFUSED (risk governor, knife guard, tradability, news admission, value-dip floors) with their reasons, and classifies each against its forward path, so a guardrail's precision becomes measurable instead of assumed | `tradingagents/strategies/refusal_ledger.py`::`gate_on` (the read, consulted at the head of every write), writers in `risk_governor.py` / `knife_guard.py` / `market_tradability.py` / `news_relevance.py` / `value_dip.py`, read by `scripts/refusal_scorecard.py` | `test_refusal_ledger.py` | wired |
| `enable_materiality_verdict` | `TRADINGAGENTS_ENABLE_MATERIALITY_VERDICT` | the three-way verdict vocabulary - SUPPORTED / REFUTED / INCONCLUSIVE - over a pre-declared materiality threshold, plus a family-level FDR and an exposure-time-matched benchmark arm, so an underpowered result is recorded as unresolved instead of as evidence of no edge | `tradingagents/strategies/evaluate.py`::`_materiality_gate_on` / `::`materiality_verdict` / `::`family_materiality` / `::`benchmark_table`, `tradingagents/agents/utils/report_verifier.py`::`_materiality_gate_on` (per-stem verdict and tree-level family emission) | `test_materiality_verdict.py` | wired |
| `enable_accuracy_ceiling` | `TRADINGAGENTS_ENABLE_ACCURACY_CEILING` | the R-squared ceiling and the excess-accuracy read, so an impossible (2DA-1)^2 vs R2_OOS/kappa point above the 45-degree line is FLAGGED - a falsifier, never a validator | `tradingagents/strategies/alpha_eval.py`::`_ceiling_gate` / `::`ceiling_ratio`, `tradingagents/strategies/calibration.py`::`_ceiling_gate` / `::`excess_accuracy`, reported by `tradingagents/graph/trading_graph.py`::`_maybe_report_accuracy_ceiling` | `test_accuracy_ceiling.py` | wired |
| `enable_spectral_null_band` | `TRADINGAGENTS_ENABLE_SPECTRAL_NULL_BAND` | declares a regime change only when a spectral functional's move EXCEEDS its calibrated first-order null band - so a non-rejection reads 'not detectable', never 'no change' | `tradingagents/strategies/regime.py`::`_spectral_band_gate` / `::`spectral_change_read`, declared as the `spectral_change` component by `tradingagents/strategies/regime_score.py`::`_spectral_gate`, numerics in `tradingagents/strategies/covariance_models.py` | `test_spectral_null_band.py` | wired |
| `enable_rnd_recovery` | `TRADINGAGENTS_ENABLE_RND_RECOVERY` | V3: recover a risk-neutral density only when the quotes can identify one; a sparse chain refuses | options_surface.py _rnd_gate, read from expected_move_from_chain | `tests/test_rnd_recovery.py` | wired |
| `enable_eigen_rotation` | `TRADINGAGENTS_ENABLE_EIGEN_ROTATION` | V5: subdominant eigenspace rotation, refused inside the Marchenko-Pastur bulk | covariance_models.py spectral_functionals gated rotation key, reached from regime.spectral_change_read | `tests/test_eigen_rotation.py` | wired |
| `enable_drawdown_envelope` | `TRADINGAGENTS_ENABLE_DRAWDOWN_ENVELOPE` | K2: four drawdown expectations with the Hurst depth rescaling, report-only | book_risk.py drawdown_envelope, read by the strategy-evaluation row in evaluate.py | `tests/test_drawdown_envelope.py` | wired |
| `enable_hmm_heavy_tails` | `TRADINGAGENTS_ENABLE_HMM_HEAVY_TAILS` | R2: heavy-tailed HMM emissions and a regime VaR judged by Kupiec and Christoffersen | regime.py hmm_filtered_regime emission path and regime_conditional_var, consumed by book_risk.py | `tests/test_hmm_heavy_tails.py` | wired |
| `enable_tail_risk_layer` | `TRADINGAGENTS_ENABLE_TAIL_RISK_LAYER` | K1: a tail number carrying its data quality and estimation uncertainty, one-directional | tail_risk.py tail_risk, printed by risk_score.py | `tests/test_tail_risk_layer.py` | wired |
| `enable_factor_availability_gate` | `TRADINGAGENTS_ENABLE_FACTOR_AVAILABILITY_GATE` | H2: registration-time rejection of a forward shift or a field unobservable at the decision date | factor_expressions.py availability_gate, called from scripts/factor_bench.py | `tests/test_factor_availability_gate.py` | wired |
| `enable_forward_stress_probability` | `TRADINGAGENTS_ENABLE_FORWARD_STRESS_PROBABILITY` | R5: a calibrated one-month-ahead forward stress probability from the cross-section | market_breadth.py forward_stress_probability, printed by regime_score.py | `tests/test_forward_stress_probability.py` | wired |
| `enable_prompt_condition_harness` | `TRADINGAGENTS_ENABLE_PROMPT_CONDITION_HARNESS` | N5: prompt versioning with per-condition accuracy on the decision ledger, offline by construction | agents/utils/prompt_metrics.py record_condition_run and condition_accuracy | `tests/test_prompt_condition_harness.py` | wired |

## 7e. Score-engine gates — the report-level research engines (advisory only)

The eight `*_score` engines. Each is a **research-layer calculator**: it can
never set a rating, a size or a gate (the executor's hard gates run downstream),
which is why they are not in §1. Each ships **off**. The engine gates decide
which engines populate the `quant_scorecard` snapshot; the master
`enable_quant_scorecard` (its own row below) decides whether the snapshot reaches the report,
the decision context and the debate at all, and it never implies the engine
gates.

| Key | Env var | What it can do | Enforced at | Proven by | Status |
| --- | --- | --- | --- | --- | --- |
| `enable_fundamental_score` | `TRADINGAGENTS_ENABLE_FUNDAMENTAL_SCORE` | the `get_fundamental_score` leaf: four advisory 0-100 category sub-scores and the panel composite, with coverage and basis | `tradingagents/agents/utils/analysis_tools.py::get_fundamental_score` (`_r3_flag`), `tradingagents/reporting.py::_run_card_fundamental_score` | `test_fundamental_score.py::test_gate_off_makes_the_leaf_say_so`, `::test_run_card_block_is_absent_when_the_gate_is_off` | wired |
| `enable_technical_score` | `TRADINGAGENTS_ENABLE_TECHNICAL_SCORE` | the `get_technical_score` leaf: 0-100 category sub-scores over band-mapped indicators, plus the weighted composite | `tradingagents/agents/utils/analysis_tools.py::get_technical_score` (`_r3_flag`), `tradingagents/reporting.py::_run_card_technical_score` | `test_technical_score.py::test_gate_off_makes_the_leaf_say_so`, `::test_run_card_block_is_absent_when_the_gate_is_off` | wired |
| `enable_momentum_score` | `TRADINGAGENTS_ENABLE_MOMENTUM_SCORE` | the `get_momentum_score` leaf: the eight advisory 0-100 momentum legs (§54: price / relative / trend strength / acceleration / breakout / volume confirmation / quality / risk-adjusted) with the §50-§52 meta reads printed beside the number | `tradingagents/agents/utils/analysis_tools.py::get_momentum_score` (`_r3_flag`) | `test_momentum_score.py::test_the_leaf_is_gated_off_by_default`, `::test_the_gate_ships_off_and_is_registered` | wired |
| `enable_regime_score` | `TRADINGAGENTS_ENABLE_REGIME_SCORE` | the `get_regime_score` leaf: market-level trend / realized-vol / VIX / term-structure / chop reads with the two regime paths printed side by side | `tradingagents/agents/utils/analysis_tools.py::get_regime_score` (`_r3_flag`), `tradingagents/reporting.py::_run_card_regime_score` | `test_regime_score.py::test_the_leaf_says_the_gate_is_off`, `::test_gate_off_writes_no_card_key` | wired |
| `enable_risk_score` | `TRADINGAGENTS_ENABLE_RISK_SCORE` | the `get_risk_score` leaf: eight advisory 0-100 risk category sub-scores (inverted, 100 = low risk) with each raw producer value and sign printed beside its contribution | `tradingagents/agents/utils/analysis_tools.py::get_risk_score` (`_r3_flag`), `tradingagents/reporting.py::_run_card_risk_score` | `test_quant_scorecard.py::test_a_gated_off_engine_is_absent_with_its_gate_named`, `::test_the_missing_engine_reaches_the_composite_as_none_not_zero` | wired |
| `enable_sentiment_score` | `TRADINGAGENTS_ENABLE_SENTIMENT_SCORE` | the `get_sentiment_score` leaf: attention and tone as separate rows (never summed), mixed source scales refused | `tradingagents/agents/utils/analysis_tools.py::get_sentiment_score` (`_r3_flag`), `tradingagents/reporting.py::_run_card_sentiment_score` | `test_quant_scorecard.py::test_a_gated_off_engine_is_absent_with_its_gate_named` (the absence mechanism; the leaf's own gate has no dedicated test) | wired |
| `enable_news_score` | `TRADINGAGENTS_ENABLE_NEWS_SCORE` | the `get_news_score` leaf: relevance and novelty from the news pipeline, the five unsupplied categories printing `NA` with a reason | `tradingagents/agents/utils/analysis_tools.py::get_news_score` (`_r3_flag`), `tradingagents/reporting.py::_run_card_news_score` | `test_quant_scorecard.py::test_a_gated_off_engine_is_absent_with_its_gate_named` (the absence mechanism; the leaf's own gate has no dedicated test) | wired |
| `enable_trade_score` | `TRADINGAGENTS_ENABLE_TRADE_SCORE` | the `get_trade_score` leaf: the advisory composite over four engines, withheld below a two-engine floor; never a gate, a size or an `opportunity_score` | `tradingagents/agents/utils/analysis_tools.py::get_trade_score` (`_r3_flag`), `tradingagents/reporting.py::_run_card_trade_score` | `test_trade_score.py::test_the_leaf_says_the_gate_is_off`, `test_quant_scorecard.py::test_the_composite_is_absent_when_its_gate_is_off_but_the_engines_are_read` | wired |
| `enable_quant_scorecard` | `TRADINGAGENTS_ENABLE_QUANT_SCORECARD` | the master surface gate: decides whether the engine snapshot reaches the report (`run_card`), the computed decision context and the debate block | `tradingagents/graph/trading_graph.py` (`_compiled_decision_context`), `tradingagents/agents/utils/report_hygiene.py::scorecard_context_block`, `tradingagents/reporting.py::_run_card_quant_scorecard` / `::_scorecard_snapshot_for_report` | `test_quant_scorecard.py::test_the_scorecard_gate_exists_and_defaults_off`, `::test_gate_off_leaves_the_context_and_the_card_unchanged` | wired |

## 7f. Debate and run-shape flags

These decide the **shape of a run** — which debate node set is built, which
evidence reaches it, and which advisory artefacts are appended to the finished
decision. They never change a threshold, a size or a rating.

| Key | Env var | What it can do | Enforced at | Proven by | Status |
| --- | --- | --- | --- | --- | --- |
| `enable_debate` | `TRADINGAGENTS_ENABLE_DEBATE` | swaps the legacy one-shot bull/bear chain for the structured, claim-verified debate node set, and resolves the per-role debate LLMs | `tradingagents/graph/setup.py::setup_graph` (node set), `tradingagents/graph/trading_graph.py` (`TradingAgentsGraph.__init__` role-LLM resolution), `tradingagents/reporting.py::_run_card_debate` | `test_debate_stream_hermetic.py::test_structured_debate_graph_compiles_with_stub_llms`, `::test_legacy_path_unchanged_with_flag_off` | wired |
| `enable_reflection` | `TRADINGAGENTS_ENABLE_REFLECTION` | records the run's reflection outcome into the memo overlays | `tradingagents/graph/trading_graph.py::TradingAgentsGraph._maybe_record_reflection_outcome`, `tradingagents/strategies/overlays.py::record_reflection_outcome` | `test_strategies_overlays.py::test_record_reflection_guarded` | wired |
| `enable_independent_vote` | `TRADINGAGENTS_ENABLE_INDEPENDENT_VOTE` | adds the independent researcher stance read and the vote summary to the debate path (the node no-ops when off) | `tradingagents/agents/utils/independent_vote.py::independent_stance_node` | `test_independent_vote.py::test_node_noops_when_flag_off` | wired |
| `enable_evidence_symmetry` | `TRADINGAGENTS_ENABLE_EVIDENCE_SYMMETRY` | adds the S11 evidence-symmetry layer: the macro leaf prefetch and the pre-debate symmetry assertion, changing *how* evidence is gathered, never the decision | `tradingagents/graph/setup.py::setup_graph` (symmetry assertion), `tradingagents/agents/analysts/sentiment_analyst.py::sentiment_analyst_node`, `tradingagents/agents/utils/evidence_gather.py` (the `_flag` reads) | `test_structured_agents.py::test_journals_macro_leaf_only_when_the_gate_is_on`, `test_evidence_symmetry.py` | wired |
| `enable_decision_audit` | `TRADINGAGENTS_ENABLE_DECISION_AUDIT` | appends the computed claim-vs-contract audit note to the PM decision (advisory; never blocks) | `tradingagents/reporting.py::write_report_tree` (decision finalization) | `tradingagents/reporting.py::write_report_tree` (the gate read — no test flips it); `test_reporting.py::test_audit_decision_numbers_flags_mismatch` proves the audit itself | wired |
| `enable_pit_registry` | `TRADINGAGENTS_ENABLE_PIT_REGISTRY` | stores the OHLCV profile snapshot and caches the fitted moments in the point-in-time registry when the factor profile is read | `tradingagents/agents/utils/analysis_tools.py::get_factor_profile` | `tradingagents/agents/utils/analysis_tools.py::get_factor_profile` (the gate read — no test flips it); `test_pit_registry.py` proves the registry itself | wired |
| `enable_prediction_ledger` | `TRADINGAGENTS_ENABLE_PREDICTION_LEDGER` | logs every completed decision as a scorable prediction row (advisory; never gates) | `tradingagents/graph/trading_graph.py::TradingAgentsGraph.finalize_run` | `tradingagents/graph/trading_graph.py::TradingAgentsGraph.finalize_run` (the gate read — no test flips it); `test_prediction_ledger.py` proves the ledger itself | wired |
| `enable_report_attribution` | `TRADINGAGENTS_ENABLE_REPORT_ATTRIBUTION` | appends the Phase D disclosure + invalidation advisory block to the PM decision (computed; never gates) | `tradingagents/reporting.py::write_report_tree` (decision finalization) | `test_reporting.py::test_disclosure_block_does_not_false_mark_truncation`; producers in `test_report_disclosure.py` | wired |
| `enable_report_influence` | `TRADINGAGENTS_ENABLE_REPORT_INFLUENCE` | appends the H9 report-influence / factor-novelty advisory block to the run card: the NNLS thesis-over-reports projection and the factor novelty screen `mean_f max_z \|corr\|`. A **new key**, not an extension of the DSA-2 gate beside it (different read: an NNLS projection vs a sum-100 normalization of engine reads). This repo has no text-embedding provider, so the block carries the named `no_embedding_backend` refusal rather than a fabricated weight (advisory; never gates) | `tradingagents/strategies/report_attribution.py::gate_on` (the read), `tradingagents/reporting.py::_run_card_report_influence` (the card block) | `test_report_attribution.py::test_the_card_gains_the_block_only_when_the_gate_is_on`, `::test_relabelled_factor_flagged` | wired |

## 7g. Factor-model family

The factor-model / quality surfaces. The screener and tool rows are additive
render-only extra columns — when the gate is on they add a computed zone or band,
and the underlying score is byte-identical. Two of the flags are **inert**
(declared and settable, read by nothing): the learned factor model and the
proposal loop are research scripts whose docstrings name their flags, but no
code reads them, so flipping them changes nothing today.

| Key | Env var | What it can do | Enforced at | Proven by | Status |
| --- | --- | --- | --- | --- | --- |
| `enable_factor_model` | `TRADINGAGENTS_ENABLE_FACTOR_MODEL` | **intended**: gate the learned advisory factor-model score (`scripts/factor_model_train.py`) so it never reaches the LLM unless on — **no code reads it** | — (no read site) | `scripts/factor_model_train.py` (L7 docstring names the flag; the read-site scan finds no reader) | inert |
| `enable_factor_profile` | `TRADINGAGENTS_ENABLE_FACTOR_PROFILE` | the `get_factor_profile` leaf: computed momentum / reversal / volatility / value rows off the run's OHLCV cache, or an explicit unavailable when off | `tradingagents/agents/utils/analysis_tools.py::get_factor_profile` | `test_qlib_wiring.py::test_gated_off_returns_unavailable`, `::test_gated_on_returns_computed_rows` | wired |
| `enable_factor_proposal_loop` | `TRADINGAGENTS_ENABLE_FACTOR_PROPOSAL_LOOP` | **intended**: gate the LLM-proposed candidate sheet (`scripts/factor_proposal_loop.py`) so only gated rows reach the factor profile — **no code reads it** | — (no read site) | `scripts/factor_proposal_loop.py` (the script implements the loop; the read-site scan finds no reader) | inert |
| `enable_composite_rank` | `TRADINGAGENTS_ENABLE_COMPOSITE_RANK` | the default ranking mode for `scripts/value_screener.py`: composite when on, value otherwise | `scripts/value_screener.py::main` (rank-mode default) | `scripts/value_screener.py::main` (the gate read; no test flips it) | wired |
| `enable_quality_composite` | `TRADINGAGENTS_ENABLE_QUALITY_COMPOSITE` | adds the quality-composite line to `get_composite_rank` | `tradingagents/agents/utils/analysis_tools.py::get_composite_rank` | `test_round3_wiring.py::test_composite_rank_gate_controls_the_quality_line` | wired |
| `enable_f_score_detail` | `TRADINGAGENTS_ENABLE_F_SCORE_DETAIL` | adds the render-only `f_score_band` extra to the screener row and the earnings-quality tool | `tradingagents/dataflows/statement_parsing.py::screen_ticker`, `tradingagents/agents/utils/quant_formula_tools.py::get_quality_factors` | `test_round3_wiring.py::test_screen_row_carries_the_zone_and_band_when_the_gates_are_on`, `::test_earnings_quality_renders_the_zone_and_band_when_on` | wired |
| `enable_altman_variants` | `TRADINGAGENTS_ENABLE_ALTMAN_VARIANTS` | adds the render-only Altman variant and distress zone (`altman_zone` / `altman_variant`) to the screener row and the earnings-quality tool | `tradingagents/dataflows/statement_parsing.py::screen_ticker`, `tradingagents/agents/utils/quant_formula_tools.py::get_quality_factors` | `test_round3_wiring.py::test_screen_row_carries_the_zone_and_band_when_the_gates_are_on`, `::test_screen_row_has_no_round3_keys_when_the_gates_are_off` | wired |

## 7h. Event family

The event surfaces: a scheduled-catalyst overlay folded into the run, the forward
calendars the event row is measured against, and the `EventScore` leaf. They add
an event read — never a threshold, a size or a rating.

| Key | Env var | What it can do | Enforced at | Proven by | Status |
| --- | --- | --- | --- | --- | --- |
| `enable_events` | `TRADINGAGENTS_ENABLE_EVENTS` | folds the scheduled-catalyst (PEAD) overlay into the run's strategy overlays | `tradingagents/graph/trading_graph.py::_apply_strategy_overlays` | `test_strategies_catalyst.py::test_graph_overlay_wiring_enable_events`, `::test_graph_overlay_wiring_events_disabled` | wired |
| `enable_event_calendars` | `TRADINGAGENTS_ENABLE_EVENT_CALENDARS` | fetches the forward event calendars once for the scorecard's event row and the trade-score calendar answers; off returns `{}` | `tradingagents/reporting.py::_card_event_calendars` / `::_scorecard_snapshot_for_report`, `tradingagents/agents/utils/analysis_tools.py::_event_calendar_answers` | `test_quant_scorecard.py::test_the_card_fetches_the_forward_calendars_once_for_both_readers` (the gate-on fetch; the off path is the `{}` return in `_card_event_calendars`) | wired |
| `enable_event_state` | `TRADINGAGENTS_ENABLE_EVENT_STATE` | the `get_event_state` leaf and the event row in the scorecard snapshot and run card | `tradingagents/agents/utils/analysis_tools.py::get_event_state`, `tradingagents/reporting.py::_run_card_event_state` / `::_scorecard_snapshot_for_report` | `test_event_state.py::test_the_leaf_says_the_gate_is_off`, `::test_the_card_block_reads_the_runs_own_snapshot` | wired |

## 7i. Vendor and screener surfaces

The vendor and screener surfaces. Each adds a data source or a tool; none can
change a rating, a size or a verdict, and the ones backed by `_feature_gate`
return a `DATA_DISABLED` sentinel while off.

| Key | Env var | What it can do | Enforced at | Proven by | Status |
| --- | --- | --- | --- | --- | --- |
| `enable_alpaca` | `TRADINGAGENTS_ENABLE_ALPACA` | Alpaca 1-minute bars as a realtime / OHLCV fallback when the primary vendor path is empty | `scripts/value_screener.py::_fetch_ohlcv`, `tradingagents/graph/trading_graph.py::resolve_instrument_context`, `tradingagents/agents/utils/momentum_tools.py::_momentum_text`, `scripts/action_report.py::_realtime_price`, `scripts/pre_market_review.py::_realtime_price` | `test_alpaca_data.py::test_screener_ohlcv_falls_back_to_alpaca` | wired |
| `enable_massive_flat` | `TRADINGAGENTS_ENABLE_MASSIVE_FLAT` | reads OHLCV from the local flat-file folder when the vendor path is empty; `scripts/validate_massive_flat.py` checks the folder's NOI against it | `scripts/value_screener.py::_fetch_ohlcv`, `scripts/validate_massive_flat.py::main` | `test_massive_flat_noi.py::test_fetch_ohlcv_uses_flat_folder_when_enabled` | wired |
| `enable_market_movers` | `TRADINGAGENTS_ENABLE_MARKET_MOVERS` | the `get_market_movers` tool (top gainers / losers / actives) | `tradingagents/agents/utils/analysis_tools.py::get_market_movers` (the `_feature_gate` read) | `tradingagents/agents/utils/analysis_tools.py::get_market_movers` (the gate read; no test flips it) | wired |
| `enable_market_routing` | `TRADINGAGENTS_ENABLE_MARKET_ROUTING` | routes market-data methods to the configured source-priority chain instead of the fixed default vendor | `tradingagents/dataflows/interface.py::_market_routing_enabled` / `::route_to_vendor` | `test_routing_config_contract.py::test_documented_env_enables_market_routing_branch` | wired |
| `enable_screener` | `TRADINGAGENTS_ENABLE_SCREENER` | the `screen_equities` tool (equity screener) | `tradingagents/agents/utils/analysis_tools.py::screen_equities` (the `_feature_gate` read) | `tradingagents/agents/utils/analysis_tools.py::screen_equities` (the gate read; no test flips it) | wired |
| `enable_etf_engine` | `TRADINGAGENTS_ENABLE_ETF_ENGINE` | classifies an ETF and routes the fundamentals analyst to the ETF toolset | `tradingagents/agents/analysts/fundamentals_analyst.py::fundamentals_analyst_node` | `test_analyst_etf_routing.py::test_etf_classification_uses_etf_toolset` | wired |
| `enable_enhanced_index` | `TRADINGAGENTS_ENABLE_ENHANCED_INDEX` | the enhanced-index allocation path in `allocation_block` | `tradingagents/strategies/portfolio.py::allocation_block` | `test_qlib_wiring.py::test_enhanced_index_flag` | wired |

## 7j. Score and aggregation flags

The score and aggregation flags: the sentiment/analyst-revision reads, the
weighted sentiment aggregation rows, the growth-score block and the
score-evaluation rows. Each is an additive read; none can change a rating, a
size or a verdict.

| Key | Env var | What it can do | Enforced at | Proven by | Status |
| --- | --- | --- | --- | --- | --- |
| `enable_sentiment` | `TRADINGAGENTS_ENABLE_SENTIMENT` | pre-fetches the deterministic social-score line into the sentiment analyst prompt; off leaves the stem exactly as it was | `tradingagents/agents/analysts/sentiment_analyst.py::sentiment_analyst_node` | `test_sentiment_computed.py` (the producer of the line); the gate-off branch is exercised in `test_i18n_coverage.py` | wired |
| `enable_sentiment_factor` | `TRADINGAGENTS_ENABLE_SENTIMENT_FACTOR` | folds the news-sentiment factor read into the run's strategy overlays | `tradingagents/graph/trading_graph.py::_apply_strategy_overlays` / `::_sentiment_factor_read` | `test_strategies_overlays.py::test_graph_sentiment_read_returns_context`, `::test_graph_sentiment_read_off_returns_none` | wired |
| `enable_weighted_sentiment_agg` | `TRADINGAGENTS_ENABLE_WEIGHTED_SENTIMENT_AGG` | appends the weighted sentiment aggregation rows to the sentiment tool | `tradingagents/agents/utils/analysis_tools.py::_sentiment_agg_rows` (the `_sentiment_flag` read) | `test_sentiment_weighted_agg.py::test_news_tool_appends_weighted_rows_only_when_gated` | wired |
| `enable_weighted_sentiment_window` | `TRADINGAGENTS_ENABLE_WEIGHTED_SENTIMENT_WINDOW` | appends the weighted rolling-window row to the sentiment tool | `tradingagents/agents/utils/analysis_tools.py::_sentiment_agg_rows` (the `_sentiment_flag` read) | `test_sentiment_rolling_window.py::test_weighted_window_row_gated_on_the_tool` | wired |
| `enable_news_relevance` | `TRADINGAGENTS_ENABLE_NEWS_RELEVANCE` | engages the news relevance scoring and the official-source boost in the news data tools | `tradingagents/agents/utils/news_data_tools.py::_news_relevance_enabled` | `tradingagents/agents/utils/news_data_tools.py::_news_relevance_enabled` (the gate read; no test flips it) | wired |
| `enable_growth_scores` | `TRADINGAGENTS_ENABLE_GROWTH_SCORES` | adds the growth-score block to `get_quality_factors` | `tradingagents/agents/utils/quant_formula_tools.py::get_quality_factors` | `test_round3_wiring.py::test_quality_tool_compresses_the_median_exclusions_when_no_panel_is_supplied` | wired |
| `enable_score_eval_rows` | `TRADINGAGENTS_ENABLE_SCORE_EVAL_ROWS` | adds the IC / score-evaluation rows to the strategy-quality report | `scripts/strategy_quality_report.py::build_report` | `test_score_eval_rows.py::test_report_gate_off_omits_score_eval`, `::test_report_gate_on_without_ledger_is_unavailable` | wired |
| `enable_analyst_revision_index` | `TRADINGAGENTS_ENABLE_ANALYST_REVISION_INDEX` | adds the analyst-revision index to the sentiment / news component reads and the `get_analyst_revision_index` tool | `tradingagents/agents/utils/analyst_revision_tools.py::get_analyst_revision_index`, `tradingagents/agents/utils/analysis_tools.py::_sentiment_components` / `::_news_components` | `test_analyst_revision_index.py::test_tool_is_a_disabled_sentinel_while_the_flag_is_off`, `::test_tool_renders_the_weighted_index_and_the_estimate_unavailable` | wired |

## 7k. Remaining odds and ends

The last family: the strategy-overlay fold and its sub-reads, the crowd-ratio
band row, the pre-open RVOL lines, the top-k drop allocation path, and two inert
research flags. None can change a rating, a size or a verdict.

| Key | Env var | What it can do | Enforced at | Proven by | Status |
| --- | --- | --- | --- | --- | --- |
| `enable_orderflow` | `TRADINGAGENTS_ENABLE_ORDERFLOW` | folds the order-flow (distribution / VPIN) summary into the strategy overlay | `tradingagents/graph/trading_graph.py::_apply_strategy_overlays` | `tradingagents/graph/trading_graph.py::_apply_strategy_overlays` (the gate read; no test flips it); `test_strategies_overlays.py::test_fold_flow_scales_position_and_warns` proves the fold | wired |
| `enable_crowd_ratio_bands` | `TRADINGAGENTS_ENABLE_CROWD_RATIO_BANDS` | adds the crowd-ratio band row to `get_sentiment_computed` | `tradingagents/agents/utils/analysis_tools.py::get_sentiment_computed` (the `_sentiment_flag` read) | `test_sentiment_crowd_ratio.py::test_crowd_row_gated_on_the_tool` | wired |
| `enable_preopen_rvol` | `TRADINGAGENTS_ENABLE_PREOPEN_RVOL` | adds the pre-open RVOL and gap advisory lines to the computed decision context | `tradingagents/graph/trading_graph.py::_compiled_decision_context` | `tradingagents/graph/trading_graph.py::_compiled_decision_context` (the gate read; the tests set it off) | wired |
| `enable_strategy_overlays` | `TRADINGAGENTS_ENABLE_STRATEGY_OVERLAYS` | builds the regime / sizing overlay and folds it into the run state; off returns the state unchanged | `tradingagents/graph/trading_graph.py::_apply_strategy_overlays`, `tradingagents/strategies/overlays.py::build_strategy_overlays` | `test_strategies_overlays.py::test_overlay_disabled_returns_none`, `::test_overlay_builds_context` | wired |
| `enable_topk_drop` | `TRADINGAGENTS_ENABLE_TOPK_DROP` | the top-k drop allocation path in `allocation_block` | `tradingagents/strategies/portfolio.py::allocation_block` | `test_qlib_wiring.py::test_topk_drop_flag` | wired |
| `enable_metric_authority` | `TRADINGAGENTS_ENABLE_METRIC_AUTHORITY` | a fail-closed PUBLICATION gate — when on, a measured metric with no named, registered producer publishes `unavailable` instead of a value (never a legacy fallback); when off (the shipped default) every read is unchanged | `tradingagents/strategies/metric_authority.py`::`_metric_authority_on` (the read) → `resolve_metric`, wired at `tradingagents/strategies/trade_plan.py`::`_authoritative_ceiling` and `tradingagents/strategies/metric_reconcile.py`::`_metric_authority_enabled` | `test_metric_authority.py::test_the_gate_off_is_unchanged_and_on_fails_closed` | wired |
| `enable_tuner` | `TRADINGAGENTS_ENABLE_TUNER` | **intended**: gate the hyper-parameter grid-search front-end (`scripts/tuner.py`) so the gate still decides — **no code reads it** | — (no read site) | `scripts/tuner.py` (its docstring names the flag; the read-site scan finds no reader) | inert |
| `enable_value_dip` | `TRADINGAGENTS_ENABLE_VALUE_DIP` | **intended**: gate the value-dip screener / tool surface — **no code reads it** (the `--scan value-dip` mode is selected by the CLI flag, not this key) | — (no read site) | `scripts/value_screener.py` (the `value-dip` scan mode; no code reads `enable_value_dip`) | inert |

## 8. Adding a gate — the rule

A new gate is not done until it is registered in **seven** places: (1) a key in
`DEFAULT_CONFIG`, (2) an `_ENV_OVERRIDES` row so it is flippable from `.env`,
(3) a row in this file with its enforcement site, (4) a `REGISTRY` entry in
`tests/test_gate_env_toggles.py`, (5) a test that **fails when the gate is
ignored** (the mutations in the phase plans are the pattern), (6) a line in
`.env.example`, and (7) a row in the `docs/api_reference.md` §1.1 env-var table.
A `CHANGELOG.md` entry is required as well, but it is a documentation obligation
rather than a registration point.

**The live `.env` is required too, and it is an owner rule (2026-09-24):** every
config key the engine ships - gate or value - must have an entry in the `.env`
the run actually reads, created with its `DEFAULT_CONFIG` value when the name is
absent and **never overwritten** when it is already there. An `.env.example`
line alone leaves the switch invisible in the operator's own file. Prove a
top-up by comparing the effective config before and after; the loader runs
`load_dotenv()` **without** `override=`, so a written default cannot mask an
exported variable.

Points 1-4 are machine-enforced: `tests/test_gate_env_toggles.py` checks that
the key, the env row, the doc row and the `REGISTRY` entry all exist and agree,
and `tests/test_api_reference_env_table.py` checks 7 by regenerating the table
from every env var the config reads. Only a human can enforce 5's quality, which
is why the "Proven by" column exists.

**This list said five until 2026-09-22 and six until 2026-09-24.** The 2026-09-22
correction added 7: a new gate with no `api_reference.md` row fails the suite with
*"the table omits 1 env var the config reads"* - found by adding one. The
2026-09-24 correction added the live `.env` (an operator-facing file the contract
had never named) and reconciled the two lists that had drifted apart: this one
had counted a `CHANGELOG.md` entry and omitted `.env.example`, while the adoption
set's ground rules counted `.env.example` and the `REGISTRY` entry and omitted the
CHANGELOG. The list above is the union.

The generator is `scripts/gen_api_reference_table.py --write`.

**Read the key by its literal name.** The read-site scan behind point 4 looks for a *quoted* key
inside an access idiom (`cfg.get("enable_x", False)`, `config["enable_x"]`, `_flag("enable_x")`, a
comparison or a membership test). A gate read through a module constant - `cfg.get(GATE_NAME)` with
`GATE_NAME = "enable_x"` at the top of the file - therefore scans as **read by nothing**, and the
registry can only call a live gate `inert`. Three gates in the 2026-09-23 paper-survey round were
written that way and each one had to be fixed before its item could land, so treat the literal as
part of the gate's contract rather than a style preference: the constant may stay for the messages
it builds, but the read itself names the key.

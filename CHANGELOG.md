# Changelog

All notable changes to TradingAgents are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Breaking changes within the 0.x line are called out explicitly.

### Added
- **Verifier MISQUOTED status + adjudication sweep (AMZN 2026-09-09 loop items
  1+3)** - (1) the deterministic anchor now surfaces MISQUOTED when a claim's
  figures ARE in tool evidence but attached to the wrong label/context (LLM
  reason carries a transposition/attribution cue) instead of silently
  re-grounding it - catching the AMZN composite-rank A/e swap class; the
  internal-conflict metric set gained ATR/T1/T2/macdh/RVOL/Williams/stoch/RSI/
  AWS-growth/HY-OAS with per-metric tolerances (exact price levels at 0.1% so
  T1 265.03 vs 265.97 and ATR 6.47 vs 5.7079 flag); `_float_tokens` now
  collects percent-int figures and unit scales include 1e2 so integer percents
  match fraction leaves. (2) `scripts/verify_sweep.py`: post-verifier
  confirmation workbench over existing verify_flags.json - surfaces N
  CONFIRMED (MISQUOTED/CONTRADICTED/INTERNAL_CONFLICT, needs a fix) vs M
  SUSPECT (UNSUPPORTED, needs adjudication) per tree, `--json`,
  `--confirm-only`; exit 1 when any confirmed/suspect exists. Tests:
  test_report_verify (MISQUOTED anchor, ATR/T1 conflicts, percent-matching),
  test_verify_sweep (counts/absent/CLI ok).
- **News-analyst macro citation hardening (AMZN 2026-09-09 review loop)** -
  uncited macro figures (10Y Treasury "9.78%"/"4.85%" vs actual ~4.78, RRP
  0.626B, "93% no Fed cut" Polymarket) had ZERO tool leaves - the analyst
  recalled them instead of calling get_macro_indicators / get_prediction_markets
  / get_tga_balance (all exist and were bound). The prompt now pins every macro
  class to its tool (MACRO MUSTS) and forbids pasting a recalled macro figure;
  regression test in `tests/test_news_analyst_prompt.py`. Verifier caught all
  of these as UNSUPPORTED/anchored already (rule 8 loop).
- **VDU hard execution gate + ATR(14) labeling (AMZN 2026-09-09 review #19/#14)** -
  (a) `value_dip_setup` gained `require_vdu`: the Step-2 VDU ladder (volume
  dry-up + trigger candle close-above-prior-high + RVOL >= 1.3 + momentum
  confirmation) is promoted to a HARD gate - candidate=False means NO entry
  even if an oscillator looks oversold; measured-only (unknown never fails),
  wired from `TRADINGAGENTS_VALUE_DIP_VDU_ENABLE` / `value_dip_vdu_enable`
  (default off, mirroring the knife/regime/catalyst gates). Tests:
  `tests/test_strategies_value_dip.py` (require_vdu blocks-incomplete /
  confirms / unknown-never-fails). (b) ATR window disclosure - the verified
  market snapshot now labels its stockstats ATR as `atr(14)` and
  `get_swing_set`'s structure-stop renders `1 ATR(14) below swing low,
  ATR(14)=...` so the snapshot's ATR is never confused with a swing/tranche
  ATR of another window (AMZN 6.47 vs 5.7079). Tests: `test_market_data_validator`
  (atr(14) label), `test_analysis_tools` (swing_set ATR(14)).
- **Market-report honesty fixes (AMZN 2026-09-09 review loop)** -
  (a) `build_verified_market_snapshot` now labels a row dated = the requested
  analysis date as a potentially FORMING bar (intraday run) and marks its
  Close + close-derived indicators PROVISIONAL - never a settled close -
  instead of presenting it as a "verified" EOD bar; (b) `get_mean_reversion_quality`
  discloses MIXED evidence when the AR(1) verdict is mean-reverting but the
  long-horizon signatures lean the other way (Hurst > 0.55 persistence and/or
  a significant VR > 1 momentum) - AMZN half-life 10.78d but Hurst 0.6425 /
  VR 1.18, so the read now says "require an explicit trigger/confirmation"
  rather than a clean "dip entries supported". Regression tests:
  `tests/test_market_data_validator.py` (provisional-note + settled control),
  `tests/test_strategies_mean_reversion.py` (mixed + clean paths).
- **CapEx-allocation read (advisory, deterministic)** - `strategies/capex_quality.py`
  + `get_capex_quality` (fundamentals tool loop): separates PRODUCTIVE
  investment from OVERINVESTMENT / DISTRESS for high-capex names - CapEx
  intensity z (vs the name's own history), funding cover OCF/CapEx, CapEx-vs-
  revenue 5y CAGR elasticity, incremental ROIC (3y lag, dNOPAT /
  dInvestedCapital) + economic spread vs WACC, CapEx ROI 3y, payback 3y,
  FCF-recovery gap (to a 3% target yield), a 5-regime label (HARVEST /
  PRODUCTIVE / PRODUCTIVE_INVESTMENT / INVESTMENT_WATCH / OVERINVESTMENT /
  DISTRESS), a 0-100 quality score and advisory valuation penalty. NEVER a
  hard gate; n/a on missing rows; composite renormalizes over measured
  components. Adjudication artifact of the AMZN 2026-09-09 report-review
  loop (rule 8: a negative trailing FCF is reinvestment, not automatically
  value destruction). Tests: `tests/test_capex_quality.py` (8: regimes,
  None-safety, hermetic tool render).
- **FCF value-floor / DCF now anchor on trailing-12M FCF, not latest ANNUAL
  FYxx** - `get_fcf_yield`, `get_value_dip_setup`, `get_dcf_valuation` and the
  scenario-DCF input path all fed the latest annual *free cash flow* into the
  value floors, silently stale in a capex-accelerating quarter (AMZN case:
  FY2025 annual +$7.7B vs trailing-12M -$2.5B; value-floor claimed
  `fcf_positive=True` and DCF $1.56 off a positive stale anchor). New
  `value_dip_tools._ttm_fcf_from_quarterly` sums the newest 4 quarterly FCFs
  (moomoo quarterly markdown or quarterly-CSV, gated on a Q-token shape so an
  annual payload is never summed quarter-style); positive TTM feeds the
  floors/DCF, a NEGATIVE TTM degrades the DCF honestly ("use a
  normalized/forward-FCF model") instead of recycling the stale positive
  annual, and the render shows `basis=ttm` / `basis=annual`. Regression tests:
  TTM preference, negative-TTM DCF degrade, annual fallback. Adjudicated from
  the AMZN 2026-09-09 report-review loop (rule 8).
- **Deterministic forced-tool evidence gathering** (map-reduce; design
  `docs/design_mapreduce_forced_tool_gathering.md`, plan
  `docs/implementation_plan_mapreduce_forced_tool_gathering.md`): when
  `TRADINGAGENTS_ANALYST_FORCED_TOOLS` is set, the runtime gathers that fixed
  tool set deterministically (the "map") before the analyst runs and the
  analyst *reduces* from the merged evidence block — so the analyst's report
  input is fixed in *composition* (which tools were asked) instead of the
  LLM-selected subset. Addresses the analyst-side root cause of run-to-run
  verdict flips (the 2/3 TSM probe). Config: `analyst_forced_tools`,
  `analyst_forced_tools_max_parallel`, `analyst_forced_tools_timeout_s`,
  `analyst_forced_tools_summary_window`. Defaults off — the legacy
  LLM-selected path is bit-identical when unset. Per-tool deadline (default
  30s) records a `timeout` leaf and proceeds (today there is no tool
  deadline at all); a wedged thread drains in the background (Python can't
  preempt it — see design §3.5/tracked TRACKED-1). Evidence is persisted to
  `tool_evidence.json` per run and diffed by `repro_check --evidence` so
  "did every run see the same tools" is answerable from the report tree.
  Scope: the 4 information analysts (market/fundamentals/news/sentiment);
  risk debaters + Trader are a tracked Phase-5 follow-up.
- **Tool pools: gather-pool vs model-pool** (same feature, refined): tools
  whose required args the deterministic context can supply (140 of 180
  registered) are forced-gathered as before; tools needing a
  model-supplied input (40: options quotes, scenario DCF, allocation,
  macro-indicator slugs, etc.) are never auto-attempted — they stay bound
  to the LLM, which owns their inputs, and are listed in the evidence block
  under "Model-supplied tools" so the split is visible. Classification is
  signature-derived at runtime (a future tool needing a model input lands
  in the model pool automatically); `TRADINGAGENTS_ANALYST_TOOLS_MODEL_SUPPLIED`
  is an escape hatch to force extra names into the model pool. Short-circuit
  blocks only gathered (gather-pool) tools; model-pool calls execute for real.
- **Backup LLM for truncation-continuation retries** (`TRADINGAGENTS_BACKUP_LLM`
  in `.env`, config key `backup_llm`): when ANY LLM response is cut at the
  output cap, the continuation retry now runs on the configured backup model
  instead of re-paying the model that kept truncating. Spec format
  `provider:model` (e.g. `openrouter:deepseek/deepseek-chat`) or a bare model
  id using `TRADINGAGENTS_LLM_PROVIDER`; empty = same-model continuations
  (legacy behavior, bit-identical). Wired through every truncation path:
  analyst chain reports (`retry_chain_if_truncated` + cap-forced
  `finalize_messages`), plain researchers / risk debators
  (`retry_llm_if_truncated`), the structured managers / trader / sentiment /
  independent-stance `invoke_structured_or_freetext`, AND the structured
  debate turns + L2 judge (`invoke_structured_turn`: a structured call that
  raised or returned unparseable content — e.g. a max_tokens cut mid-JSON —
  falls back AND repairs on the backup; the plain invoke stays primary when
  the provider lacks structured output). The graph resolves one backup client
  (`provider:model` spec, quick-tier output budget, its own provider's
  kwargs) and threads it into `GraphSetup` + every SD node. Tests:
  `test_truncation_retry.py` +8 backup-swap cases (plain / chain / structured /
  free-text / same-object guard / bounded-give-up / failure-degrade /
  complete-no-touch) + `test_debate_integration.py` +3 (structured-failure
  fallback / repair swap / no-backup same-model) + `test_env_overrides.py` env
  mapping + graph wiring (backup built when set, absent when unset). See
  CHANGELOG / api_reference.
- **Debate-judge ensemble** (`TRADINGAGENTS_DEBATE_JUDGE_ENSEMBLE`, default 1,
  set to 3): the L2 judge runs N times over the SAME transcript and the per-alias
  side scores aggregate (mean-of-means), with `judge_agreement` + `judge_flip`
  written into the debate state so a borderline judge flip is an EXPLICIT
  uncertainty signal instead of a silent swing. `structured.invoke_structured_turn`
  now returns a `mode` ("structured"/"plain"/"repair"); the judge + debater turns
  record `judge_structured_fallback` / per-role `_structured_fallback` when a
  turn fell back to free text (reporting + PM see reduced reliability). The
  RM/PM decision matrix gains a deterministic **field-level consensus** block
  (stance / allocation / judge-score spread) so convergence is measured on the
  typed fields, not just the headline label. New `scripts/repro_check.py` runs a
  symbol N times and prints verdict agreement + config hash for reproducibility
  measurement. Tests: `test_debate_risk_parity.py` (ensemble aggregate + flip /
  fallback flag / consensus lines) + `test_debate_integration.py` (mode contract).
  — A 2×3 TSM reproducibility probe: baseline verdicts (Underweight, Underweight,
  Overweight) vs the ensemble+temp=0.1+judge-luna config (Hold, Overweight, Hold):
  both 2/3 self-agreement — temperature/judge/ensemble=3 reduced but did NOT
  eliminate the borderline flip (judge flips persist even at temp 0.1, per the
  reproducibility literature). Follow-up: `TRADINGAGENTS_DEBATE_JUDGE_ENSEMBLE=5`
  and a deterministic **PM confidence gate** (`decision_guardrail.cap_pm_confidence_on_judge`):
  when the risk-debate judge flipped / agreement<1.0 / used free-text fallback,
  the PM's confidence is capped (default 0.5, never raised) with a recorded
  reason, and the PM prompt carries a "Risk-debate judge reliability" line so
  the model holds down conviction on an unreliable judge — so a borderline
  judge flip now DEGRADES the decision's confidence rather than silently
  swinging it. Tests `test_decision_guardrail.py` +7 + `test_structured_agent_prompts.py` +2.
### Fixed
- **Reasoning-model output-budget starvation** (`TRADINGAGENTS_OPENROUTER_REASONING_EFFORT`
  in `.env`, config `openrouter_reasoning_effort`): a reasoning model
  (deepseek-v4-flash via OpenRouter) spends its WHOLE `max_tokens` on hidden
  reasoning — observed `completion_tokens==reasoning_tokens==4000`, "length
  limit was reached" — so the cap-forced final report turn returns empty and
  the structured-debate judge JSON never parses (both fall back to free text,
  TSM 2026-09-07). The knob forwards `reasoning: {effort: low|medium|high}`
  in the request body for the OpenRouter provider only, so the model's
  reasoning burn stays BELOW the output budget and the report/JSON always has
  room. Off by default (provider default effort). Tests:
  `test_llm_client_timeout.py` +3 (forward / unset-omitted / native-not-affected).
- **Tool-not-found 400 on the cap-forced report retry** (`structured`): a
  strict tool-calling backend (OpenAI / Azure via the OpenRouter relay)
  hard-400s a conversation that contains an unfulfilled tool call — "No
  tool output found for function call <id>" — which the analyst tool loop
  leaves when one assistant reply requests several tools but only the first
  executes. This killed the backup-model retry of empty cap-forced reports
  (TSM 2026-09-07), degrading every such section to the unavailable notice.
  New `_deorphan_tool_calls` strips unfulfilled calls (never fabricating a
  result) before ANY chain re-invoke: `finalize_messages` (terminal turn +
  truncation continuation + backup empty-retry) and
  `retry_chain_if_truncated` / `retry_chain_if_stub`. Regression tests:
  `test_tool_round_cap.py` +3 (backup de-orphan / same-chain de-orphan /
  clean-pass-through).

  (`graph.trading_graph._try_fetch_closes`): a vendor returning OHLCV rows
  NEWEST-first (EODHD) left `closes[-1]` as the OLDEST close, so every
  consumer of `closes[-1]` as 'the latest close' read a stale value — the
  TSM 2026-09-07 trade-plan card pinned a reference price of 288.88 that
  collided with the verified 428.91 bar (bull/bear/Trader/PM flagged an
  'unresolved reference price'; the same stale basis surfaced in
  `get_bollinger_pct_b`/`get_opening_range`/`get_support_structure`).
  The helper now normalizes the vendor output to ASCENDING date order,
  mirroring `analysis_tools._ohlcv` (which had the same ABNB $128.56
  incident). Regression test: `test_graph_tool_loop.py`
  `test_try_fetch_closes_normalizes_newest_first_vendor_rows`.

  (`structured.finalize_messages`): when the MAX_TOOL_ROUNDS terminal turn
  returns empty content (a reasoning model like `deepseek-v4-flash` burned
  its output budget on hidden reasoning — QCOM fundamentals + NXPI
  market lands 2026-09-07 fell through as a bare "report unavailable"
  placeholder), the analyst is re-asked ONCE — on the configured backup
  chain when set, else the same chain — with the completion directive, 
  and only if that still returns empty does it emit an explicit
  `**Report unavailable**` notice (never a silent empty string). Regression
  tests: `test_tool_round_cap.py` +3 (backup-retry / same-chain retry /
  unavailable notice).
 (`get_sector_rotation_screen`):
  the curated-industry branch referenced `_top_note` before assignment
  (`UnboundLocalError`) and the shared constituent block referenced
  `breadth_with_gate` / `leadership_ratio_ewcw` imported only inside the eodhd
  branch — the nxpi batch 2026-09-06 died on the first one. `_top_note` is now
  initialized in the curated branch and the breadth imports are hoisted to the
  function top. Regression test
  `test_sector_rotation_curated_breadth_does_not_crash` renders the constituent
  screens through the exact curated path.
- **Quant-formula audit fixes (independent web-verified pass over ~468 formula
  blocks)** — four material divergences corrected:
  1. **Risk-parity weights** (`portfolio_optimizer.risk_parity_weights`): the
     update `Σ⁻¹·(1/RC_i)` does not converge to equal risk contribution and
     collapsed to a degenerate single-name book on correlated inputs; replaced
     with the converging fixed-point `w ← normalize(b ⊘ Σw)` (equal risk
     budgets), which equalizes marginal risk contributions `wᵢ(Σw)ᵢ`. Non-
     convergence now degrades explicitly to equal-weight with a note.
  2. **Beneish M-Score** (`dataflows.quantitative_scores.beneish_m_score`):
     DEPI denominators were `(PPE − Dep)` instead of canonical `(PPE + Dep)`,
     overstating DEPI ~1.7×; LVGI computed `(CL − LTD)/TA` instead of canonical
     `(CL + LTD)/TA`, flipping the leverage signal for debt-heavy firms (the
     −0.327 weight then pushed M the wrong way). Both fixed to the Beneish
     (1999) forms; None-safe `_add` helper added.
  3. **DCF terminal value** (`strategies.dcf.compute_dcf`): the Gordon TV was
     anchored to the base-year FCF instead of the last projected year
     `F₀(1+g)ⁿ` (docstring already claimed the correct intent), silently
     understating intrinsic value ~7–10%; TV now uses the projected year-N FCF
     and discounts it back from year N.
  4. **Square-root market impact** (`strategies.backtest_models.
     square_root_impact`): `vol_pct` (a percent, e.g. 20.0) was divided by 100
     twice (`(vol_pct or 0.20)/100` → 0.002 for 20% vol), understating impact
     ~100×; now converted once to a fraction (0.20). Regression tests pin the
     exact 0.1·σ·√(Q/V) value.
  Each fix carries a regression test pinning the canonical closed form;
  full-suite green.
- **Agent wiring: every audited calculation reaches its analyst via a tool +
  prompt** — verified the calc→tool→agent-binding→prompt chain for all 17
  audited calculations; closed the 5 that had no agent-tool surface:
  `bsm_equity_surface` → **`get_bsm_option_quote`** (market), 
  `long_short_precision` + `purged_cpcv_splits` (+ `rank_ic`/`icir`) →
  **`get_signal_quality`** (market), `cap_and_redistribute` →
  **`get_constituent_cap_weights`** (fundamentals). Also restored 3 audit
  calcs that were graph-ToolNode-only but never in the LLM's bound list:
  `black76` → `get_options_iv_read`, `taylor_rule` → `get_taylor_read`,
  `alpha158_subset` → `get_factor_profile` — now bound in the market
  analyst's `tools = [...]` (bind_tools) list with prompt guidance. Every
  new/restored tool carries a prompt line (enforced by
  `test_calc_agent_wiring`); Alpaca paper-trading surfaces excluded by
  design.
- **Quant-formula audit pass 2 (13 remaining divergences)** — the 13 lower-
  severity divergences from the same audit, each with a regression test:
  1. **Modified VaR** (`strategies/size.py`): Cornish-Fisher now uses EXCESS
     kurtosis (γ₄−3, normal = 0) instead of the raw standardized kurtosis,
     removing the spurious ~0.7σ tail adjustment at 99% on normal series.
  2. **Capital-income capping** (`strategies/capital_income.py`):
     `cap_and_redistribute` now enforces the documented two-threshold rule
     (3% soft cap / 3.5% exact ceiling): excess redistributed pro-rata to
     names below the soft cap, capped names frozen at the ceiling. The old
     whole-vector renormalization pushed capped names back above 3.5%.
  3. **Downside deviation / semi-deviation** (`strategies/rate_utils.py`):
     divided by ALL observations (canonical, consistent with
     `evaluate.downside_deviation`) instead of the shortfall count (was
     inflated ~√2 on symmetric returns).
  4. **Black-76 rho** (`strategies/options_math.py`): futures-form `−T·V`
     (was BSM spot-form, wrong sign for ITM calls).
  5. **BSM charm** (`strategies/options_math.py`): sign fixed + the dividend
     term `q·e^{−qT}·N(d1)` added; finite-difference verified.
  6. **Zmijewski X-score** (`strategies/normalized.py`): liquidity term uses
     the canonical current ratio CA/CL (was inverted CL/CA).
  7. **Alpha158 `_returns`** (`strategies/factor_expressions.py`): sign-fixed
     to `c/prev − 1` (was `prev/c − 1`, swapping the up/down-vol features).
  8. **Choppiness** (`strategies/regime.py`): now the canonical CHOP index
     (0-100, ATR/range ratio; OHLC); close-only series keep a bounded
     0-1 proxy. Regime threshold retuned to the CHOP 30 trending band.
  9. **Long-short precision** (`strategies/signal_analysis.py`): Qlib
     sign-direction hit rate (was top-quantile set overlap).
  10. **CPCV** (`strategies/evaluate.py`): now Naive-Combinatorial CPCV —
     every (test-group, train-complement) subset, 5×15 paths for 5 groups
     (was single k-fold cut); embargo preserved.
  11. **RSI family** (`strategies/swing.py`, `technical_factors.py`):
     `swing.rsi` + `stoch_rsi` now use Wilder RMA smoothing (was Cutler's
     simple-sum RSI mislabeled "Wilder"); `rsi2` unchanged (n=2 collapse).
  12. **Taylor rule r\*** (`strategies/cycle_tilt.py`): default neutral real
     rate 0.5% → classic Taylor (1993) 2.0%.
  13. **GEX sign** (`strategies/derivatives_gamma.py`): call OI → + dealer
     gamma, put OI → − (mainstream SpotGamma convention; was inverted).

### Changed
- **Wiring audit: prompt guidance for every analyst-bound tool**.
  New AST gates in `tests/test_calc_agent_wiring.py` catch (a) tools bound to
  an analyst's tool list but never explained in its `system_message`, and (b)
  the existing orphan-calc + unbound-tool gates. Closed 28 real gaps: added
  'cite it before any X claim' guidance for 6 fundamentals tools (regime state,
  kalman spread, position risk multiplier, Black-Litterman allocation,
  dividends, Form-4 insider), 16 market tools (indicators, GARCH/vol
  estimators, shift detection, mean-reversion quality, options surface, Merton
  distance, earnings-quality verdict, tail decomposition, universe membership,
  regime/risk-multiplier, stock/crypto data, Alpaca snapshot, cost models,
  momentum scan, debate-claims verdict), 5 news tools (earnings catalyst,
  insider transactions, GDELT sentiment, market breadth, IPOs), and news
  grounding in the sentiment analyst.
### Fixed
- **Vendor outage hardening** (option 1 from the no-data audit;
  `docs/developer/03-dataflow-vendors.md`): the four flow-critical categories
  (`core_stock_apis`, `technical_indicators`, `fundamental_data`, `news_data`)
  joined `OPTIONAL_CATEGORIES`, so a total vendor outage (every vendor in the
  chain raising network/auth/rate-limit errors) returns the `DATA_UNAVAILABLE`
  sentinel instead of re-raising the first error — the graph no longer dies on
  a ToolNode exception when `get_stock_data` / `get_indicators` / the
  statement tools / `get_news` all fail. The analyst proceeds and reports
  "unavailable". Clean no-data and disabled-config sentinels are unchanged;
  per-vendor failures are still logged (never silent); a single vendor failing
  while another can serve it still falls through. The sentinel text now says
  "`<category>` could not be retrieved" (drops the now-wrong "optional" label).
  Tests updated to the new contract (vendor_routing
  `test_core_category_degrades_on_error`, vendor_absence
  `test_typed_wrapper_rate_limited_core_attaches_absence` — the typed wrapper
  now attaches the `rate_limited` envelope instead of raising,
  moomoo_vendor `test_moomoo_alone_and_failing_degrades`).
- **Earnings quality wired to the consensus verdict** (option 1): the
  ticker-based `get_earnings_quality` now fetches canonical statements
  (net income / OCF / total assets / capex) and runs the consensus
  `earnings_quality_verdict` as its evidence layer (cash conversion,
  accrual ratio, FCF = OCF - |capex|, negative-FCF red flag) while keeping
  the forensic trap; the old ad-hoc 6%/2% accrual band (whose
  "low-earnings-quality-risk" label read backwards for high accruals) is
  superseded by the consensus 5%/10% bands. `capex` in the verdict is now
  sign-robust (abs, matching dcf.py) so a GAAP-signed outflow can't
  inflate FCF. Tests: consensus-render assertions + capex red-flag/sign
  cases; wiring gate green; ruff clean.
- **Quant-engine v2 audit** (pre-agent-wiring calculation check): (1) DuPont driver was `argmax |factor|` (= always the biggest leg — mislabeled a normal-leverage firm "leverage-led" and a loss-making firm "equity_multiplier-driven") → replaced with log-DuPont attribution vs the neutral 1.0 benchmark (margin/turnover/leverage/mixed labels; non-positive margin always the story); (2) scenario DCF silently coerced `g_base=0.0` to 3% → respected now; added the design-promised market price → band (below bear / bear-base / base-bull / above bull) + per-scenario margin of safety (and `-0.0` fcf_scale cleanup); (3) earnings-quality returned `LOW` on no inputs (dead `n/a` branch) → level now None (n/a) when nothing is usable, and the render says "concern" so HIGH can't be read as "high quality". Wired the trio into the fundamentals analyst (import + tool list + prompt) — the graph ToolNode already had them. Tests `test_quant_engine_v2.py` (19) + `test_analysis_tools.py` renders (7); wiring gate green; ruff clean.
### Fixed
- **Sector rotation screen: breadth gate + real EW/CW index (review fix)** -
  structural-review fixes: (1) breadth is now **denominator-gated** (sample
  < 20 renders n/a 'not a breadth read' instead of a noisy % from 1-3
  tickers); (2) the EW/CW ratio now uses the **real Invesco RSP* equal-weight
  sector index** per sector (`EW_CW_ETFS`: RSPT/RSPF/RSPH/RSPD/RSPN/RSPM/
  RSPG/RSPU/RSPC/RSPR/RSPS, current 2026-06 tickers) instead of the
  micro-sample reconstruction, **normalized against its own 50d SMA**
  (broadening/narrowing + spread% vs baseline) - unitless return ratio,
  immune to share-price levels; (3) breadth and EW/CW are now **separate
  lines** - a sector can never be called 'broadening' from a 1-ticker sample.
  Live: XLK/RSPT narrowing -53.5% (megacap concentration), XLC/RSPC +3.7%
  broadening, all breadth n/a sample<20. Tests: gate, price-level immunity,
  map completeness (20 screen tests green).
### Added
- **Sector breadth layer (McClellan/MSI/multi-timeframe, review-driven)** -
  `strategies/sector_breadth.py`: (1) multi-timeframe breadth matrix
  (% > 20d/50d/200d, n-gated); (2) per-sector McClellan Oscillator
  (EMA19-EMA39 of the size-normalized daily net A-D, cumulative-sum MSI -
  the correct definition; fixed a steady-state-zero artifact on
  one-directional markets and a negative-slice `_sma` bug that broke the
  whole matrix); (3) RRG heading + constructive/weakening-trap flags
  (`rrg_heading`, standalone); (4) advisory MSI-zone risk-budget note
  (never a gate). Wired into `get_sector_rotation_screen`
  ('## Sector breadth matrix' table: n / 20d / 50d / 200d / MO / slope /
  MSI / RRG). 9 hermetic tests.
- **Sector rotation screen: full S&P-500 universe (review fix 2)** -
  `dataflows/sp500_universe.py` harvests the full S&P-500 constituent table
  (Wikipedia REST wikitext, keyless, disk-cached weekly) and maps GICS
  sector -> SPDR ETF. `get_sector_rotation_screen` with
  `constituent_universe='eodhd'` now uses THIS universe (no alphabetical
  cutoff): every constituent per sector gets its OHLCV through the run cache,
  breadth is computed on the real sector denominator (n=20-60 samples vs the
  previous 1-3), EW/CW stays RSP*-based + own-50d-normalized. Kills the
  'sample truncation' distortion. n_total ~315 constituents, sector n shown.
- **Sector rotation screen: EODHD constituent universe for breadth** -
  the breadth/EW-CW/setup layer can now be driven by the EODHD full-US
  symbol list (`get_exchange_symbols_eodhd`, ~51k symbols, major-exchange
  filtered) instead of the static curated subset: GICS + sub-industry
  sector bucketing (`sector_group_of`, alias map extended for the yfinance
  sub-industry granularity), per-sector cap + classifier budget with an
  early-bail when every lookup fails, in-process lookup cache, and breadth
  rendered for every sector with classified members (n shown - small n is
  noisy, raise eodhd_cap). Tool: `constituent_universe='eodhd'` param or
  `enable_sector_eodhd_constituents` config. Live: 8 sectors breadth/EW-CW
  + Setup A/B states. LLM-facing, advisory, budget-capped for free tiers.
- **Sector rotation screen (P1-P4, design doc)**: new
  `strategies/sector_screener.py` + `get_sector_rotation_screen` tool (market
  analyst): regime (SPY>SMA200+slope) grade cap + multi-factor SPDR rank
  (momentum/RS/trend/risk reusing sector_rank) + RRG quadrant +
  pullback-divergence leader flags + dispersion trend; constituent
  breadth/EW-CW/Setup-A-B behind enable_sector_breadth; P4
  scripts/validate_sector_rotation.py after-cost gate (with-cost rotation
  Sharpe 0.655/IR 1.05 < equal-weight 1.10/1.40 -> screen is context-only,
  no outperformance claim). LLM-facing only (web untouched by design rule).
- **Industry-depth tools (spec rec 1-2)**: `get_edgar_fulltext_search(query,
  forms?, date_range?)` - SEC EDGAR full-text search (efts.sec.gov, keyless):
  fetch the 10-K customer/supplier-concentration footnote ('major customer'),
  peer mentions, thematic scans (filings since 2001); `get_patent_activity(ticker)`
  - USPTO PatentsView granted-patent counts + recent titles (name-based
  assignee match; free PATENTSVIEW_API_KEY; new-API host was unresolvable at
  build, honest degrade otherwise). Both wired to the fundamentals analyst +
  graph ToolNode with prompts; router categories sec_filings (extended) +
  patents (optional, key-gated).
- **Order-flow depth (spec items 1-2, official FINRA keyless)**:
  `get_dark_pool_flow(ticker, weeks?)` - FINRA ATS weekly off-exchange
  share/trade/notional flow (OTC Transparency); `get_short_sale_volume(ticker,
  days?)` - FINRA Reg SHO daily short-sale volume (% short-sale of volume),
  keyless variant beside the Massive-backed get_short_volume. Both render the
  served as-of dates with a staleness gate (FINRA's public consumer tier serves
  a historical window; a free FINRA API key upgrades to the current daily
  file) - never present old data as current. Wired to the market analyst
  (imports + tool list + prompt) + graph ToolNode; router categories
  dark_pool_flow + short_sale_volume (optional, degrade).
- **Macro-strategist depth (spec: liquidity/FX/commodities/global rates)**:
  FRED alias extensions (liquidity: tga/reverse_repo/repo/fed_balance_sheet/effr/sofr;
  commodities: wti/gold/natgas/copper; global policy rates: ecb_rate/boj_rate),
  `get_tga_balance` (US Treasury Fiscal Data API, keyless; daily operating cash
  + net draw/build = reserve injection/drain read), `get_fx_snapshot` (yfinance
  DXY + major pairs, delayed advisory). All wired to the news analyst + graph
  ToolNode with prompts; router category macro_liquidity (optional, degrades).
- **Fundamentals-analyst depth (spec gaps 1-3)**: `get_earnings_transcript`
  (FMP Earnings Transcript API, free tier; date/quarter + excerpt, never
  fabricated quotes), `get_congress_trades` (House + Senate Stock Watcher
  mirrors, keyless; net buys/sells + samples per chamber),
  `get_financial_history` (SEC EDGAR XBRL companyconcept, keyless; annual
  10-K revenue/NI/OCF/capex/assets/liabilities/equity/cash ~10-15y, honest
  pre-XBRL n/a). All wired to the fundamentals analyst + graph ToolNode with
  prompts; router categories earnings_transcripts / congress_trades +
  sec_filings extended; also fixed the SEC User-Agent (the bare project-form
  UA was 403-rejected by EDGAR: 404/403 on every host now returns data).
- **Quant-formula Phase 6** (the research-plan 'medium effort' items;
  `docs/design_quant_formulas_research.md` A6-H2): lottery-tilt screen
  (`strategies/lottery.py`: MAX = largest single-day return over the trailing
  month, IVOL = idiosyncratic residual vol vs the market with a total-vol
  fallback; `get_lottery_factors`, market analyst — a high-octane name with
  high MAX/IVOL is EXPECTED to underperform, a quality penalty),
  Almgren-Chriss optimal execution + TWAP/VWAP/POV benchmarks
  (`strategies/execution_schedule.py` + `get_execution_schedule`: hyperbolic
  front-loaded trajectory with E[IS]/var(IS), advisory scheduling),
  CPPI + vol-target overlay (`portfolio.cppi_exposure` = m * max(P - floor, 0)
  clamped to PV + the existing `size.volatility_target_scale` folded into
  `get_risk_overlay`, market analyst). All advisory, None-safe, wired with
  prompts; wiring gate green; tests p6 (8 lottery + 6 execution + 6 overlay);
  ruff clean.
- **Quant-formula implementation (phases 1-5 of the research plan; `docs/design_quant_formulas_research.md`)** - P1 options: speed/zomma 3rd-order Greeks in `black76` (+ ATM render in `get_options_iv_read`), 25-delta risk-reversal / butterfly / term-structure shape (`options_surface.surface_shape` + `get_vol_surface_shape`, market analyst), put-call parity conversion/reversal screen (`parity_violation` + `get_parity_screen`, market analyst). P2 risk metrics: Cornish-Fisher modified VaR (`size.modified_var` + `get_tail_risk` line), Kappa/LPM (`rate_utils` + `get_downside_read`), Burke/Martin/Pain + gain-to-pain (`evaluate` + `get_strategy_quality` rows), risk-of-ruin + optimal f (`size` + `get_position_sizing` ruin line). P3 statistical: Lo-MacKinlay variance ratio (`mean_reversion.variance_ratio` + MR-quality render), CUSUM/EWMA online shift detection (`regime.cusum/ewma_control` with calib-window anchoring + `get_shift_detection`, market analyst), permutation/approximate/LZ entropy (`complexity.py` + MR-quality render). P4 accounting: Ohlson O-score + Zmijewski X-score (`normalized` + `get_analyst_verdict` rows), Dechow-Dichev accrual quality (`earnings_quality.dechow_dichev_aq`; honest n/a line). P5 macro: Taylor-rule implied rate + deviation + macro stance (`cycle_tilt` + `get_taylor_read`, news analyst). All advisory, None-safe; bound with prompts (market: surface-shape/parity/shift; news: taylor); wiring gate green; tests +quant p1-p5 (12+15+12+9+6 = 54); ruff clean. See the research doc for the ranked gap list.
- **Quant-engine v2** (per the 69-section quant spec + user; `docs/design_quant_engine_v2.md`): DuPont 3/5-factor ROE decomposition (`strategies/dupont.py` + `get_dupont_read` — explains why ROE is high, margin vs turnover vs leverage), scenario DCF (`strategies/scenario_dcf.py` + `get_scenario_dcf` — bear/base/bull value range with growth ±2% + margin shocks), earnings-quality verdict (`strategies/earnings_quality.py` + `get_earnings_quality_verdict` — cash conversion OCF/NI, accrual ratio, negative-FCF red flag, rising-EPS-with-falling-FCF penalty). Tests `test_quant_engine_v2.py` (10) + `test_analysis_tools.py` +4 render; suite green; ruff clean. See the design doc.
- **Quant-engine additions** (per the end-to-end quant spec review; `docs/design_quant_engine_additions.md`): HRP (`strategies/hierarchical_risk_parity.py` + `get_hrp_alloc` — Lopez de Prado single-linkage HRP, robust/no-inversion, equal-weight degrade), 12-1 momentum (`strategies/momentum.momentum_12_1` + `get_momentum_12_1` — Jegadeesh-Titman, skips last month), Omega row in `get_strategy_quality` (via existing `statistical.omega`), industry-neutral z (`cross_section.industry_neutral_z` — winsorize → demean-by-sector → z). Tests `test_quant_engine_additions.py` (10); suite 210 green; ruff clean. See the design doc + api_reference.
- **Option-position breakeven / PMCC advisory read** (per the AVGO PMCC
  sample review + user's "go straight to implementation") —
  `strategies/options_breakeven.py` + `get_option_breakeven` tool (market
  analyst; always-on advisory like `get_cycle_tilt`):
  - `pmcc_breakeven` = long strike + premium paid per share (cost basis held
    to expiry); `short_call_discipline` = the PMCC floor rule (sold strike
    must exceed breakeven, with cushion); `long_leg_time_split` =
    intrinsic vs extrinsic (time) value + ITM flag; `delta_profile` (deep-ITM
    0.75-0.85 long / 0.20-0.30 short advisory bands); `theta_zone` (30-45d
    rent window); `catalyst_window` (earnings imminence -> never hold a
    low-strike short call through it); assignment note on ex-div near-term.
  - Everything None-safe (missing input -> n/a, never fabricated); negative
    inputs -> None; `pmcc_read` combines it all + labels inputs.
  - Bound via the wiring gate (market analyst import + tool list + prompt
    line, graph market ToolNode, agent_utils re-export + `__all__`).
  - Tests: `test_options_breakeven.py` (11: breakeven sum, floor ok/violate/
    None, intrinsic/extrinsic split + OTM-lock, delta bands, theta zones,
    catalyst imminence, combined AVGO sample, partial-input n/a) +
    `test_analysis_tools.py` +3 render tests (full/partial/never-aborts).
    Suite: 151 passed / 2 pre-existing skips; wiring gate green; ruff clean.
  - No execution, no trading_web change (LLM-facing tool).
- **Sector-rotation research actions 1+3+2 implemented** (per the web-research
  findings + user instruction; `strategies/formulas/sector_rotation.md`):
  - **A1 — RRG quadrant** (`strategies/sector_rank.py`): `rrg_quadrant(
    rs_level, rs_momentum)` — the RS-level percentile (ranking) and the
    RS-momentum percentile (RS-ratio acceleration, NEW axis) are kept
    SEPARATE → Leading / Weakening / Improving / Lagging (median split,
    None-aware; not until both axes resolve). The multifactor ranking carries
    a `quadrant` field; `get_sector_rank` emits a rotation line
    ("Leading=…; Improving=…") and an exit line ("Weakening=…") plus a
    cadence note (monthly rebalance, hold top 2-3, trim on Weakening,
    turnover is the main cost risk — A3). Advisory; gated by
    `enable_sector_multifactor`.
  - **A2 — Business-cycle tilt** (`strategies/cycle_tilt.py` + `get_cycle_tilt`
    tool bound to the market analyst): phase = early/mid/late/recession from
    PMI (FRED NAPM alias added) + 10y-2y spread + HY OAS; `TILT_MAP` → favored
    sectors. All inputs None-safe (missing → phase None, tilt [], "n/a" —
    never fabricated). `fred.get_macro_value` returns the latest float
    directly (never raises). Advisory — the regime-gate enhancement.
  - **A4/validation script**: research option, NOT built (per plan).
  - Tests: `test_cycle_tilt.py` (9: phase rules, None-degrade, TILT_MAP);
    `test_sector_rank.py` +5 (quadrant mapping/boundaries/None/carry/field);
    `test_analysis_tools.py` +3 (cycle-tilt render/n-a/never-aborts) + gated
    rotation render. Suite: 212 passed / 2 pre-existing skips; wiring gate
    green (get_cycle_tilt bound); graph import OK; ruff clean.
  - No trading_web change (both tools are LLM-facing).
- **Sector-rotation P1-P3 implemented** (per `strategies/formulas/sector_rotation.md`):
  `strategies/sector_rank.py` gains the multi-factor machinery, additive to
  the legacy single-factor path (byte-identical default):
  - P1 `rank_sectors_multifactor` — tie-aware cross-sectional percentiles
    over momentum (21/63/126/252d composite + acceleration), RS vs the SPY
    benchmark, trend (P/SMA50 + P/SMA200 + MA alignment), risk
    (Sharpe-126 blended with 1 - |MDD-126| percentile); weighted score
    (FACTOR_WEIGHTS .37/.21/.21/.21) with rank + factors; same result shape
    so `sector_standing` consumes it unchanged. None-safe throughout.
  - P2 `rank_industry_group` + `INDUSTRY_ETFS` — industry ETFs (SOXX/IGV/
    HACK/CLOU/SMH/XBI/IBB/KRE/XHB/XAR/XOP/XRT) ranked ONLY inside their
    parent sector (never XLK+SOXX in one pool); single-factor by default,
    multi-factor when a benchmark is supplied.
  - P3 `constituent_breadth` + `leadership_ratio` + `SECTOR_CONSTITUENTS`
    (curated core subset, documented small) — % above SMA50 and the
    EW-vs-CW leadership ratio.
  - `get_sector_rank` renders gated advisory lines when the config keys are
    on: P1 `enable_sector_multifactor`, P2 `enable_sector_industry`, P3
    `enable_sector_breadth` (all default OFF ⇒ legacy output unchanged; any
    unresolvable factor renders n/a).
  - Tests: `test_sector_rank.py` 24 (multifactor ordering/bounds/normalization/
    standing-consumption, industry parent-gating + names, breadth fraction,
    EW/CW ratio + insufficiency, weights sum, documented-constituents);
    `test_analysis_tools.py` gated-render tests (default-off unchanged,
    P1/P2/P3 lines when on). Suite: 210 passed / 2 pre-existing skips.
  - No trading_web change (the read is LLM-facing, not a web capability).
- **Sector-rotation reference** - `strategies/formulas/sector_rotation.md`:
  distilled from two deleted LLM-generated specs (`sector_calc.md`,
  `sector_instruction.md` — removed after distillation, were untracked).
  Single surviving source for the 12-ETF sector-rotation design: staged
  Market→Sector→Industry→Stock→Entry→Sizing→Portfolio-Risk pipeline
  (regime is a gate, not a factor; score ≠ signal), reconciled 8-factor
  100-point sector score (momentum 25 / RS 15 / trend 15 / risk 15 /
  breadth 10 / valuation 10 / flow 5 / fundamentals 5, variant B
  momentum-heavy when breadth/valuation data lacks), cross-sectional
  percentile normalization, grade table + regime cap, two-level universe
  (11 SPDR sectors + industry ETFs like SOXX, never ranked in one pool —
  resolves the spec conflict), and the two genuinely new factors
  (constituent breadth; EW-vs-CW leadership ratio). Maps onto existing
  `strategies/sector_rank.py` (momentum-only today): P1 multi-factor
  extension (RS/trend/risk/acceleration), P2 industry layer, P3
  breadth+EW/CW (fetch-heavy, cached). Rejected outright: the spec's
  "expected return/risk" construction (`evaluate.py` + CPCV/PBO is the
  repo's method). Design only; no code changed.

### Changed
- **LLM client request-timeout fix** (diagnosis: "interactive CLI job stuck
  re-trying truncated output" under provider congestion — DeepSeek US-night
  peak). Two latent bugs: the `timeout` key in the openai-compatible and
  anthropic passthrough lists was NOT a valid constructor arg in the
  installed langchain SDKs (a TypeError at construction), and no default
  timeout was ever set — so a stalled provider stream could hang
  `chain.invoke` and the truncation/stub retry loop indefinitely. Now:
  `timeout` maps to the SDKs' real fields (`request_timeout` /
  `default_request_timeout`), both are valid passthrough args, and every
  request defaults to 300 s (explicit `timeout`/`request_timeout`/
  `default_request_timeout` wins). A wedged provider now raises and
  degrades instead of hanging the job. Tests: `tests/
  test_llm_client_timeout.py` (9: alias mapping, default, explicit-wins, for
  both clients); `test_anthropic_effort.py` `test_other_kwargs_...` updated
  to the corrected mapping (was pinning the latent-broken `timeout` kwarg).
  Docs: api_reference §2 request-timeout note. Suite: 53 client/agent/
  wiring tests + 2 pre-existing skips green; real (un-mocked) deepseek +
  anthropic construction smoke-tested.

### Added
- **myhhub/stock teacher study** - `docs/design_myhhub_stock_integration.md`:
  direct-source study of the Chinese A-share rule-based quant platform
  InStock (`instock/`: MySQL daily-job pipeline, uniform
  `check(...) -> bool` strategy predicates with min-observation self-guards,
  trading-calendar singleton with None fallbacks, declarative web table
  registry, live-trade robot + Eastmoney cookie-triangle fetcher). Adopted
  as 4 advisory, phase-gated, default-off items: P1 managed trading-calendar
  cache (`dataflows/trading_calendar.py` feeding the existing
  `effective_date.non_trading_days` override — serves the yfinance A2/P2
  "exchange closed vs no data" calendar half), P2 session-aware scheduling
  hint (`run_nightly` + web jobs `session=pre|after|any`; skipped mid-session
  jobs), P3 min-obs guard helper (`strategies/obs_guard.py` +
  `require_observations` convention; no migration of existing guards), P4
  env-first credential-priority note (docs). Validation table: fork already
  ahead on backtest metrics (evaluate.py vs rate_stats.py), stepwise jobs,
  web surface; uniform-predicate full layer is deliberately NOT built (the
  ai-hedge-fund mandate AlphaModel is the right shape for typed views).
  Explicit non-goals: live-trade robot (TradingExecution successor), MySQL
  persistence (stateless-per-run + FinceptTerminal P4 plan), chip
  distribution, A-share feeds, GUI. Design only; no code changed.
  Strategies/index row 27.
- **anthropics/financial-services teacher study** - `docs/design_anthropic_financial_services_integration.md`:
  direct-source study of the Anthropic financial-services monorepo (skills
  authored once under `vertical-plugins/*/skills/`, vendored into agent
  bundles with a `check.py` byte-identity drift gate + reference-resolution
  gate; "one source, two wrappers" agent prompts reused by Cowork plugin and
  headless `agent.yaml`; per-subagent `output_schema` enforced harness-side
  by `validate.py`; data-vs-directions guardrails in every agent/skill).
  Adopted as 5 advisory, phase-gated, default-off items: P1 skill-sync drift
  gate (extends `test_calc_agent_wiring` with a parse gate + skill
  reference-resolution gate + drift check — the skill-layer half of the
  fork's permanent wiring discipline), P2 data-vs-directions guardrail
  (news/filings/earnings tool prompt preamble + `disclosure_footers` row),
  P3 declared output shape + harness-side advisory validation (extends
  `structured.py`; `None` still degrades, never blocks), P4 trigger-phrase
  discipline for skill YAMLs, P5 one-source/two-wrappers assessment note.
  Validation table shows the fork already ahead on per-role analysts,
  tool-catalog governance, and disclosure. Explicit non-goals: MCP
  connectors (.mcp.json), Cowork plugins / claude-for-msft, Claude Managed
  Agents deployment, partner plugins, version-bump git hooks, slash
  commands. Design only; no code changed. Strategies/index row 26.
- **yfinance teacher-study phases P1 + P5 implemented** (per user: adopt
  only these two):
  - **P1 typed absence reasons through the read envelope** -
    `dataflows/errors.py` gains `VendorAbsence` (frozen dataclass:
    `reason ∈ no_data | rate_limited | not_configured | error | unknown`,
    `source`, `retryable`, `detail`; `from_error()` taxonomy + JSON-safe
    `to_dict()`). `dataflows/interface.py`: `route_to_vendor` keeps its
    plain-string contract (sentinels unchanged) and carries the chain-end
    reason via a per-call contextvar side channel (`_last_absence`, reset at
    the top of every call and after the typed read — no cross-call/thread
    leak); the reason follows the verdict (NO_DATA → the no-data vendor's
    reason; optional DATA_UNAVAILABLE → the first real error). The typed
    wrapper reads it onto `VendorResult.absence` (new field + `to_dict`).
    `analysis_tools._ohlcv` envelope gains `absence` (via
    `route_to_vendor_typed`), `run_card.json` gains a `data_absence` block
    (null on success), trading_web `/api/ohlcv` returns `absence` on the
    no-history path. CLI period/interval validation was N/A (no such CLI
    exists — all CLIs take dates/bars). Always-on but read-only (new fields
    default null); scripts/* string callers untouched. Tests:
    `tests/test_vendor_absence.py` (15: taxonomy, string-contract guard,
    envelope reasons, verdict-follows-reason, no-leak).
  - **P5 deliberate yfinance pin** - `yfinance>=1.4.1` →
    `yfinance~=1.4` (requirements.txt + pyproject.toml); new
    `tradingagents/dataflows/README.md` vendor notes (guarded quirks
    #986 exclusive-end, #1021 stale frames, unnamed index, statements
    newest-first, `yf_retry` rate-limit backoff) + version-bump checklist.
- **yfinance v1.7.0 teacher study** - `docs/design_yfinance_integration.md`:
  direct-source study of `ranaroussi/yfinance` v1.7.0 (the v2 rewrite:
  `data.py` YfData + Auth cookie/crumb, `_http.py` backend abstraction,
  `cache.py` SQLite KV caches, `base.py` ticker-tz fetch + validation +
  invalidation, `scrapers/history.py` price repair, `multi.py` download
  error grouping, typed `exceptions.py` taxonomy) + full inventory of the
  fork's existing yfinance integration and web grounding on the 1.x line.
  Adopted as 5 advisory, phase-gated, default-off items: P1 typed absence
  reasons through the read envelope (`VendorAbsence(reason, source,
  retryable, yahoo_reason)` + OHLCV `absence` field + CLI period validation
  with valid options), P2 exchange-tz + currency KV cache for OHLCV reads
  (`dataflows/exchange_tz.py`, validated + invalidated + capped; `tz`/
  `currency` on the OHLCV envelope; statement currency prefers the cache
  over the ADR heuristic), P3 100x currency-unit repair (config-gated,
  detected + flagged via tolerance bands, ambiguous refuses, never silent),
  P4 batch error grouping + debug-serialize rule (grouped failure summary +
  debug⇒single-thread), P5 deliberate `yfinance~=1.4` pin + vendor quirk
  notes (#986 exclusive-end, #1021 stale frames, unnamed index). Validation
  table shows the fork already adopted the retry/typed-error/stale-guard/
  statement-currency/sentinel-cache halves. Explicit non-goals: WebSocket
  live pricing (protobuf), login cookies + tier scraping, SQLite persistent
  caches, curl_cffi impersonation, ISIN lookup, typed screener DSL, domain
  objects. Design only; no code changed. Strategies/index row 25.
- **FinceptTerminal v4 teacher study** - `docs/design_fincept_terminal_integration.md`:
  direct-source study of `Fincept-Corporation/FinceptTerminal` v4 (C++20 +
  Qt6 desktop terminal w/ embedded Python 3.11; `src/datahub`, `src/
  services/llm`, `src/trading`, `src/mcp`, `scripts/agents/finagent_core`,
  `scripts/ai_quant_lab`, `docs/DATAHUB_TOPICS.md`, `docs/
  agentic-research/`) + web grounding. Adopted as 6 advisory, phase-gated,
  default-off items: P1 typed topic-registry refresh policy (per-family
  TTL / min-interval / coalesce / force-bypass / freshness fields + a
  `docs/web_TOPICS.md` registry — trading_web REST seam), P2 tool-result
  size budget with park-and-page (`agents/utils/result_store.py` +
  `fetch_result` tool + `max_bytes` envelopes with `truncated`/`result_id`
  — detail on demand, not by default), P3 dual tool-loop budget + visible
  exhaustion (`run_card` + jobs rows gain `tool_rounds_used` /
  `tool_deadline_exhausted` / `exhaustion_note`; web job view shows the
  last probe line), P4 SQLite per-step checkpoints + resume (`jobs.
  checkpoint_json` + `resume_job` capability; crash mid-batch resumes
  un-done symbols), P5 org-as-data governance metadata
  (`consensus.agreement_weighted` + `n_abstained` decision context + PM
  statistical-rigor criteria + persona metadata doc — composes with the
  ai-hedge-fund abstention study), P6 single-source-of-truth capability
  cross-check gate (`test_web_capabilities`: every JSX capability string
  resolves in `backend/capabilities.py`, public capabilities referenced or
  documented API-only). Validation table: fork already ahead on
  multi-provider LLM registry, Qlib teacher study, backtest PIT/fill
  semantics. Explicit non-goals: C++/Qt6 frontend, paper-trading runtime,
  crypto/$FNCPT tokenomics, MCP marketplace, Ollama-default, Qlib
  wholesale wrapper, per-persona SQLite session memory. Design only; no
  code changed. Strategies/index row 24.
- **ai-hedge-fund v2 teacher study** - `docs/design_ai_hedge_fund_integration.md`:
  direct-source study of `virattt/ai-hedge-fund` v2.2.0 (hedge_fund/: data,
  signals, llm, features, fund, strategies, portfolio, risk, brokers,
  pipeline, backtesting, event_study, validation, tui) + web grounding.
  Adopted as 5 advisory, phase-gated, default-off items: P1 declarative
  mandate (fund/strategy/model as YAML data — `strategies/mandate.py` +
  `strategies/mandates/*.yaml` + `pipeline.py --mandate` +
  `scripts/mandate_rebalance.py`), P2 event-study market-model CAR with
  t-test + bootstrap CI significance (`strategies/event_study.py` +
  `pead_car_test` in `events.py` + `get_event_study_read` tool), P3
  abstention-vs-neutral conviction blending (`consensus.agreement_weighted`
  + `n_abstained` in the computed context), P4 per-clamp risk audit events
  (`portfolio.clamp_events` rendered in allocation reads), P5 prompt-level
  provenance vault (exact prompts + responses per decision, keyed to
  `research_decision.json`). Validation table shows the fork is already
  ahead on CPCV/PBO/evaluate metrics/LLM registry. Explicit non-goals:
  live brokers, the TUI, persona voicing, financial-datasets provider,
  market-neutral shorts, per-call prompt caching for cost — the
  no-execution/advisory mandates stand. Design only; no code changed.
  Strategies/index row 23.
- **Hummingbot V2 teacher study** - `docs/design_hummingbot_integration.md`:
  direct-source study of the Hummingbot V2 framework (StrategyV2Base /
  Controllers / Executors / Connectors, backtesting executors-simulators,
  paper-trade connector, budget checker, async notifier, SQLite executor
  ledger) + web grounding. Adopted as 5 advisory, default-off, phase-gated
  items mapped onto existing seams: P1 exit-accounting
  (`exit_cause_frequency` + `close_type` backtest tagging + report block +
  `exit_cause_read`), P2 pre-trade budget as a stateful collateral lock
  (`CollateralLock` + `available()` in `get_pre_trade_read`, sharing the
  backtest envelope), P3 live-book fill-latency paper model
  (`fill_latency_model` / `paper_fill_price`, advisory default-off
  `get_fill_model_read`), P4 unified executor-ledger schema
  (docs-only spec reusing the alpha-ledger row + pnl/fee columns), P5 async
  queue notifier (`monitor.notify` queue-drain). Explicit non-goals: live
  execution/order management, the controller runtime, encrypted keystore,
  per-exchange websocket feeds, MCP/skills — the fork's advisory-only,
  math-decides mandates are unchanged. Design only; no code changed.
  Strategies/index row 22.
- **Calc → agent wiring gates (no more silent gaps)** - the wiring audit is
  now a permanent test, not a one-off find:
  1. `test_calc_agent_wiring` per-fn rule tightened: a public calc counts as
     wired only when referenced OUTSIDE its module, or as an internal helper
     of a module that is itself externally reachable — the old "self-count
     escape" (a fn referenced only by its own module's text) no longer
     passes, and the module-level gate fails any wholly-unreachable module.
  2. NEW `@tool` → agent-surface binding gate: every public LangChain `@tool`
     in `agents/utils/*_tools.py` must appear in the graph ToolNode lists /
     risk-tool loop / analyst bindings, or fail. It immediately caught 4
     tools that were defined and exported but never bound since the
     7-phase risk wiring: `get_pair_risk`, `get_trade_excursions`,
     `get_vif_read`, `get_no_trade_guard_band` — now bound (market /
     fundamentals).
  3. Whitelist purge: the "future work will wire it" entries are gone.
     `prediction_ledger.score_all/score_outcome/outcome_metrics` and
     `regime_performance.stress_grid/macro_regime` are now wired as
     agent tools: `get_prediction_ledger_score` (calibration read),
     `get_trade_outcome_metrics` (MAE/MFE), `get_stress_grid_read`
     (DCF-style scenario grid), `get_macro_regime_read` (cross-asset
     regime) — all bound to the market node + web Value Tools. Remaining
     whitelist entries are permanent classifications (design-reference
     `typed_state` W4-2, dev-ops `complexity_report`, `iv_percentile` needs
     a per-day IV history no vendor ships), each with a stated reason.
- **Formula-catalog additions (six-pillar / master-catalog)** -
  ``strategies/covariance_models.py`` (NEW): Ledoit-Wolf (2004) shrunk
  covariance (scaled-identity / diag targets, ``delta = clip(b2/d2, 0, 1)``,
  web-verified formula) + RiskMetrics EWMA covariance; ``yang_zhang_vol``
  (overnight + range, drift-independent — completes the estimator set;
  ``get_volatility_estimators`` now renders close/Parkinson/GK/**YZ**/EWMA/
  GARCH). ``strategies/portfolio.py``: book-concentration suite
  (``active_share`` / ``weight_hhi`` / ``effective_holdings`` /
  ``weight_entropy``) + multi-asset fractional Kelly
  (``kelly_weights`` = ``f·Σ⁻¹μ``, long-only clip; ``allocation_block``
  switches onto it via ``enable_kelly_alloc``). ``strategies/book_risk.py``:
  EVT/GPD peaks-over-threshold ``extreme_quantile_var`` (extreme-quantile
  VaR + GPD ES, extrapolates beyond the observed worst day). 
  ``strategies/liquidity_risk.py``: ``kyle_lambda`` daily-bar price-impact
  slope (OLS of ΔP on signed volume). New advisory tools bound to the
  market + fundamentals ToolNodes: ``get_covariance_read``,
  ``get_concentration_read``, ``get_tail_extreme_var``, ``get_kyle_lambda``,
  ``get_kelly_alloc`` (+ YZ row in ``get_volatility_estimators``). Config:
  ``covariance_shrinkage_enable`` / ``covariance_shrinkage_target`` /
  ``enable_kelly_alloc`` / ``kelly_alloc_fraction`` (all default off,
  existing runs bit-identical). Tests: ``test_strategies_covariance_models``
  (8), ``test_formulas_p2`` (11), ``test_formulas_p3`` (7) — all hermetic.
  trading_web Value Tools += 5 (capabilities/App/README); docs
  api_reference + Strategies/index synced. See next entry.
- **Value-dip falling-knife velocity-z gate (`--knife-z`) + batch `--probe` tracing** -
  the value screener's value-dip scan can now enforce the falling-knife
  velocity-z guard: ``--knife-z -2.5`` blocks candidates whose 3-day price
  velocity z drops below -2.5 (the unresolved-cascade case the composite
  knife guard warns about), mapping onto the existing
  ``value_dip_setup`` ``require_knife`` / ``knife_velocity_threshold`` seam.
  The knife rows were always displayed; the flag just decides whether they
  gate. Wired for the tickers / eodhd-us / eodhd-losers universes (the
  flagships) via ``_compute_scan_row`` as well as the moomoo movers loop
  (the WIP slice only had the movers path — fixed). Also added
  ``strategies/orderflow.knife_guard_vpin`` (downside-conditioned VPIN
  toxicity filter; the guard only suppresses dip-buys when high VPIN
  coincides with a down move, never blocks up-breakouts). New hermetic
  tests ``tests/test_value_screener.py`` (semantics + CLI seam). Trading-web
  mirrors: ``run_screener`` ``knife_z`` + ``--knife-z``, the Screener form
  gains the field, web README synced. ``batch.py --probe`` writes a
  per-stage trace JSONL (``batch_probe_*.jsonl``: symbol / stage /
  elapsed / error / ``wall_seconds`` / per-worker ``data_vendors``) around
  the graph run — graph_start, graph_done, graph_failed(re-raise) — so a
  hung or failed symbol shows exactly which stage broke;
  ``tests/test_batch_probe.py`` (3, hermetic).
- **Structured PM decision persisted (`pm_decision`)** - `agent_states.AgentState`
  gains `pm_decision`; the Portfolio Manager node captures the structured
  PortfolioDecision (post-guardrail, `model_dump(mode=json)`) and returns it
  in state, so the `research_decision.json` emitter + prediction-ledger log
  read the REAL rating/data_quality/guardrail_reason instead of defaults.
  Legacy runs (pre-fix) keep nulls and are fail-closed by the executor.
- **fix(risk): governor's drawdown stop now uses the measured book drawdown** -
  ``trading_graph`` fed ``drawdown_pct = risk_max_drawdown_pct`` (the config
  limit) into ``govern``, so ``limit > limit`` was always False and the R0/R2
  realized-drawdown stop could never fire. Found via LULU (2026-09-04, CLI):
  the market analyst measured book drawdown 25.6% -> ``drawdown_gate=True``
  (BLOCKED) yet the final Risk Gate said PASS. Fix: ``_basket_drawdown``
  resolves the measured basket drawdown via the new
  ``book_risk.portfolio_drawdown`` (max peak-to-trough of the weighted book
  equity curve), ``govern`` is fed that value, and the risk snapshot exposes
  ``dd=`` so the debate sees it. ``get_book_tail_risk`` now reuses the shared
  helper. Regression tests: governor measured-fed REJECT, graph helper
  returns measured not limit, book_risk pure drawdown. Hermetic; no network.
- **Alpha-health ledger + monitor (market-research material)** -
  ``reporting.write_alpha_ledger`` appends one jsonl row per emitted decision
  (ticker/effective_date/rating/data_quality/guardrail/decision_hash) when
  ``alpha_ledger_enable`` (default off); ``strategies/alpha_health.py``
  aggregates the ledger with joined realized forward returns - score
  distribution, cross-sectional dispersion, rank IC per horizon, ICIR, the
  horizon alpha-decay curve (does edge accrue with horizon?), per-rating win
  rates and opportunity counts (missing ratings are ``n/a``, never UNKNOWN).
  ``scripts/alpha_health.py`` rebuilds the ledger from
  ``reports/*/research_decision.json`` and prints the monitor. Answers the
  material's core question empirically: scorer compression vs market
  efficiency. Hermetic tests (26); wiring gates 33; live smoke on the Sep
  decisions; ruff clean.
- **Agent tools for the quant adds (regime/kalman/multiplier/BL/guard-band)** -
  `agents/utils/quant_adds_tools.py` binds the new calculations to the virtual
  agents so they can cite computed reads:
  `get_regime_state` (multi-axis, Market analyst + node), `get_kalman_spread`
  (Fundamentals), `get_position_risk_multiplier` (Market + Fundamentals),
  `get_allocation_black_litterman` (Fundamentals), plus
  `get_no_trade_guard_band` (guards the wiring gate: `guard_band_halfwidth`/
  `should_trade` were zero-reference). All re-exported via `agent_utils`,
  bound in both analyst tool lists + both ToolNodes; the graph now feeds
  actual `hard_guards` (risk REJECT / stale-or-unknown data / ILLIQUID) into
  `build_position_contract` under `enable_hard_guards` (default off).
  Wiring + structured_agents + calc suites green (33 + 32); ruff clean.
- **Kalman-filter dynamic hedge-ratio spread** - `strategies/statistical_kalman.py`
  `kalman_spread(x, y, Q, R, alpha)` tracks the pair's hedge ratio ONLINE via
  a scalar Kalman filter (`K = P x/(P x^2+R); beta += K(y-alpha-beta x);
  P = (1-Kx)P+Q`) instead of a static rolling-OLS beta — adapts to drifting
  pairs and regime shifts (verified: converges to the true beta; a mid-sample
  1.5->3.0 beta shift is tracked). Outputs the dynamic beta + model spread +
  a mean-reversion signal. Pure, no numpy. 8 tests (Kalman + the already-
  implemented Black-Litterman optimiser: equilibrium with market-cap weights,
  view blending toward Q, equal-weight degrade); Russian/web formula check
  confirmed BL matches the standard Π=λΣw_mkt + posterior precision form.
- **Execution multiplier (soft/hard two-tier)** - `strategies/risk_multiplier.py`
  `RiskMultiplier(soft, hard)` + `combine()` implements the halve-not-block
  philosophy with an explicit soft-vs-hard split: SOFT guards (regime /
  vol_cap / knife / flow) multiply exposure down (catalog-ordered reasons);
  HARD guards (halt / insufficient_liquidity / max_portfolio_risk /
  data_quality_failure / broker_safety) BLOCK the order to 0 regardless of
  any multiplier; unknown hard flags fail SAFE (block). `build_position_contract`
  takes `hard_guards` and runs the terminal execution multiplier (`sized *=
  combine(softs, hard)`; reasons `HARD BLOCK:` / `exec_mult=`). Replaces the
  previous folded 0.x multipliers with one tunable field. Verified: soft
  knife 0.5 halves 0.1125->0.0563, hard halt -> 0.0. 46 tests
  (knife+regime+multiplier); ruff clean.
- **Regime Vol Cap ladder (F_vol)** - `strategies/regime_state.py`
  `vol_cap_factor(atr_ratio, bands)` implements the material's ATR-ratio
  table (<1.2 1.0 / 1.2-1.5 0.75 / 1.5-2.0 0.5 / 2.0-3.0 0.25 / >3.0 0.0
  hard block); `regime_factor` gains `include_vol_leg` so when the standalone
  ladder is enabled F_regime drops its vol dimension (no HIGH 0.5x0.5 double
  count); `regime_state` exposes `vol_ratio`. `build_position_contract`
  composes `vol_cap_factor` in the size chain (`sized *= ... * rf * vcf`,
  reason `vol_cap_scale`); the graph feeds it under `vol_cap_enable` (default
  off, advisory; thresholds are config defaults, not universal). 55 total
  knife+regime+liquidity tests; ruff clean.
- **Multi-axis regime state + F_regime sizing** - `strategies/regime_state.py`
  adds four independent crisp regime dimensions (TrendScore=(EMA20-EMA50)/ATR14
  -> STRONG_BULL/BULL/BEAR/STRONG_BEAR; VolRatio=ATR14/Median(ATR,N) ->
  LOW/NORMAL/HIGH/EXTREME; Relative=R_stock-R_bench vs a benchmark ->
  UNDERPERFORM/NEUTRAL/OUTPERFORM; Drawdown=P/RollingHigh-1 ->
  NORMAL/CORRECTION/BEAR/SEVERE) aggregated by `regime_state()` (multi-axis,
  never a single forced label) with a graduated `regime_factor` (Bull/Normal
  1.0, Bear/Normal 0.5, Bear+High 0.5, Extreme/Severe 0.0; conservative min
  composition). `build_position_contract` accepts `regime_factor` (sized *=
  F_regime * F_knife); graph feeds it when `regime_state_enable` (default
  off); re-exported from `regime.py`. Thresholds are config defaults, not
  universal (calibrate per universe/backtests). Tests: 10 regime tests
  (trend/vol/relative/drawdown axes, factor composition, missing-input
  unknowns, contract scaling) + knife + liquidity = 51 total.
- **Composite knife-guard score + graduated sizing** - `strategies/knife_guard.py`
  adds the weighted composite falling-knife score K (Z_return / Z_volume /
  Z_ATR / Z_drawdown / downside-VPIN legs, weights `[0.25,0.20,0.20,0.20,0.15]`)
  with a graduated `knife_factor` (1.0 <1.5 / 0.5 1.5-2.5 / 0.25 2.5-3.0 / 0.0
  >=3.0) plus the cube-root transaction-cost guard band
  (`guard_band_halfwidth`, `should_trade`). `value_dip_setup` gains a
  `knife_composite` row (display; hard-gates only in the block band under
  `require_knife`); `build_position_contract` accepts `knife_factor` and
  scales sized by it (reason `knife_scale`); graph passes the composite
  factor into the contract when `knife_composite_enable` (default off).
  Directional conditioning everywhere (volume/ATR legs only count while
  falling) - never blocks up-breakouts. Tests: composite calm/crash/borderline/
  directional/guard-band + setup row (22 knife tests, incl. a real bug caught
  - `volume_shock_z` double-divided by the median).
- **Screener column pruning** - `scripts/value_screener.py` `_watchlist_markdown`
  now hides any column where EVERY row is empty / `n/a` / `no` / `-`
  (`prune_empty_columns`; `Rank`/`Ticker` always kept), so a sparse run no
  longer drowns in blank columns. The column legend is filtered to the
  columns actually shown. Verified against real reports (top-losers run:
  64 standard columns -> 44 kept; all-no flag columns + all-n/a vendor
  columns dropped). Tests updated to the pruning contract (all-empty/all-no
  columns absent, populated columns keep real values).
- **`research_decision.json` execution contract emitter** - `reporting.py`
  `write_research_decision()` writes the deterministic, hash-pinned machine
  contract beside `run_card.json` at the end of every report tree: ticker,
  effective_date, PM rating + deterministic stop/target/size from the G1
  position contract, data_quality/guardrail_reason, risk_gate verdict; every
  unproducible field is null (fail closed). This is the ONLY input contract of
  the TradingExecution signal daemon (Phase A) — the executor never reads
  markdown. Advisory; never gates. Hermetic tests
  `tests/test_research_decision_emission.py` (5 cases).
- **Live-print reconciliation guard (AVGO 334.35-vs-357.16 audit)** -
  `dataflows/alpaca.py` `get_intraday` now drops symbols whose returned key
  does NOT match a requested symbol (Alpaca can return a different set
  G/V/A/O when a ticker is misresolved - iterating those leaked a false live
  print into reports). `dataflows/market_data_validator.py` adds
  `live_price_sanity(live, day_low, day_high, buffer)` - flags a live print
  BELOW the verified day-low / ABOVE the day-high as "likely stale feed /
  symbol mismatch - do not reconcile" instead of presenting it as a clean
  quote; exposed as `get_live_price_sanity` tool bound to the market analyst
  + market ToolNode. The AVGO report's discrepancy note was REAL data
  (Alpaca 334.35 still true today, vs EODHD 357.16) - the honest flag stood;
  the guard now makes the conflict verifiable. Tests: sanity below-low /
  inside / above-high / unknown (test_market_data_validator).
- **Pairwise-correlation cluster gate + ATR-adaptive trailing stop** -
  `strategies/portfolio.py` `allocation_block` gains a hard
  `max_pairwise_corr` ceiling (advisory, default off): when the max pairwise
  Pearson corr across the candidate names exceeds the cap, the worst-
  correlated name is dropped (never fabricates - names without a return
  series are kept). `strategies/exits.py` `trailing_stop_exit` gains an
  ATR-multiplied variant (`atr_value` + `atr_mult`): stop distance = atr*mult
  instead of the static `trail_pct`, so high-beta names stop at a
  proportionate width (premature-exit fix); precedence declared in the
  docstring (terminal risk > stop-loss > trailing > min-holding; breakeven
  resets baseline, trailing only ratchets up). Config keys
  `max_pairwise_corr` / `trailing_stop_atr_mult` (env-overridable).
  Tests: test_strategies_portfolio + test_quantlib_lean_enhancements (74
  pass). Gemini review: stale typos already fixed, cvar/drawdown defaults
  present; these two were the genuinely-missing pieces.
- **Market-stress / liquidity / earnings-blackout hardenings (mean-reversion)** -
  `strategies/regime.py` `regime_gate_read` gains a market-level stress leg
  (`index_closes`; config `market_stress_index` e.g. `^SPX` +
  `market_stress_vol_cap` 0.85): when the index latest-21d realized-vol
  percentile exceeds the cap, `market_stress=True` blocks MR entries
  (advisory - stock dips become value traps on a stressed tape).
  `strategies/liquidity_risk.py` `liquidity_verdict` gains optional
  `adv_dollar`/`min_dollar_volume` (20d dollar-volume floor) and
  `spread_bps`/`max_spread_bps` (Roll 1984 spread cap) -> ILLIQUID on a thin
  book / wide spread; the graph's liquidity gate now feeds both. Config
  `catalyst_hard_block_days` default 0 -> 5 (forward-looking earnings
  blackout REJECTs new risk; existing forward logic). Tests:
  test_strategies_liquidity + test_strategies_regime extend (28 pass).
- **Moomoo value-dip screener (`--universe moomoo-screen`)** - `dataflows/moomoo.py`
  adds `screen_value_dip_moomoo()` (Stock Screening V2 against local OpenD: US market,
  PE_TTM / market-cap / ROE value anchors AND 5-day change + RSI dip timing, 52-week-high
  distance, paginated, sorted by 5-day change; unit conventions documented: change/ROE
  decimal, RSI 0-100, price_to_52w_high as (price-high)/high). `scripts/value_screener.py`
  gains the `moomoo-screen` universe: config-default filters (env-overridable via
  `TRADINGAGENTS_MOOMOO_SCREEN_*`) with per-flag overrides (--max-chg5d/--max-rsi/
  --max-debt-assets) + server-side price floor/PB band (--price-min, --pb-min/
  --pb-max) + configurable pullback window (--dip-days, default 5; reference
  recipe 20) + client-side NYSEX/Nasdaq exchange gate (--exchanges, default
  NYSE,NASDAQ, all universes; screen V2's EXCHANGE field is non-functional
  for US, so candidates are checked via get_stock_basicinfo / the EODHD
  symbol-list Exchange column); rows feed mover_meta + the standard results
  loop. Dep guard:
  `protobuf>=5.29,<6` (moomoo SDK needs the pre-6.0 upb API). Tests:
  test_moomoo_value_dip_screen (6 pass) + 2 CLI tests.
- **Remediation W1-5/W3-5/W3-6/W3-8/W4-5/W4-7/W4-8 ops + polish** - `strategies/quant_baseline.py`
  (deterministic quant-only signal + rating for LLM comparison), `strategies/options_surface.py`
  (IV percentile/skew/P-C OI/expected move/VRP), `strategies/integrity_tools.py` (thesis-evidence
  matrix, prompt-injection detection, complexity report), `llm_clients/tier_router.py` (hybrid tier),
  `strategies/monitor.py` (webhook/log notifier, default off).
  Tests: test_phase8_ops (18 pass).

- **Remediation W2-6..10 costs / capacity / actions / survivorship** - `strategies/backtest_models.py`
  (square_root_impact Almgren-Chriss from ADV, turnover, capacity_pct, borrow_cost, quote_adjust
  corporate-action), `pit_registry.universe_membership` (survivorship guard).
  Tests: test_cost_capacity_actions (14 pass).

- **Remediation W1-10/W2-11/W4-6/W1-11 regime + scenario + ablation** - `strategies/regime_performance.py`
  (regime_conditioned_performance per-regime hit/return, stress_grid computed sensitivity rows,
  macro_regime cross-asset label fail-open), `scripts/agent_ablation.py` (drop-one measurement).
  Tests: test_regime_performance (10 pass).

- **Remediation W4 architecture (domain bundles / typed state / falsification schema / factor bridge)** -
  `strategies/domain_bundles.py` (get_market_technicals / get_fundamental_profile /
  get_sentiment_flow_feed / get_factor_profile / get_portfolio_risk_envelope + news_relevance_profile),
  `strategies/typed_state.py` (schema-validated layer artifacts + compact summarizer),
  `falsification.evaluate_debate_claims` (judge grounding + auto-reject already-breached theses).
  Tests: test_phase5_architecture (9 pass).

- **Remediation W1-2/4/6/7 measurement (calibration + scorecard + benchmarks + feedback)** -
  `strategies/calibration.py` (predicted-confidence bins vs actual hit rate; per-agent scorecard),
  `evaluate.benchmark_table` + `strategy_quality_report --benchmark` (market + simple comparators),
  prediction-ledger auto-invalidation on stop-hit outcomes (W1-7).
  Tests: test_calibration_scorecard (7 pass).

- **Remediation W3 data integrity (quality score / disagreement / PIT / falsification)** -
  `strategies/data_quality.py` (aggregate_quality weighted 0-100 + tier, disagreement_flag cross-vendor
  spread, fundamentals_pit_ok fail-closed invariant), `strategies/falsification.py` (numeric thesis
  invalidation conditions auto-monitored into the persistent ledger). Decision disclosure gains the
  quality + falsification lines. Tests: test_data_quality_falsification (14 pass).

- **Remediation W2 validation guards (CPCV / OOS / walk-forward / DSR)** - `strategies/evaluate.py`
  adds `purged_cpcv_splits`+`cpcv_overfit_mask` (W2-2) and `oos_split` (W2-4); `alpha_zoo.bench_zoo` now
  reports OOS rank-IC, walk-forward mean IC (W2-3), CPCV overfit flag, and deflated IC (W2-1);
  `factor_proposal_loop` adopts a factor only when its trailing-OOS IC clears the bar.
  Tests: test_validation_guards (11 pass). Plan: docs/master_implementation_plan.md.

- **Remediation W1 measurement (prediction ledger + cost)** - `strategies/prediction_ledger.py` (W1-1: every
  decision logged as a scorable prediction row; W1-3: MAE/MFE + stop/target outcome scoring against realized
  closes), `strategies/llm_cost.py` (W1-8: provider rate-table cost estimate). Graph wires the ledger behind
  `enable_prediction_ledger`. Tests: test_prediction_ledger (15 pass). Plan: `docs/master_implementation_plan.md`.

- **Vibe-Trading transfer (research + 8 adopted hardening items)** - `docs/design_shadow_account.md`; `VendorResult.price_caliber`/`volume_unit` + `caliber_consistency` mixed-caliber warning; next-bar close fills + lookahead sentinel (`test_next_bar_fill`); `position_target`/`position_filled` in backtest output; persistent invalidation ledger (`--invalidate`, action-report auto-breach); `run_card.json` per report tree; versioned cache keys + no-forming-bar staleness guard; hash-chained `risk_audit` ledger (`--verify-chain`); `alpha_zoo` purity gate + bounded evaluator + `factor_bench` CLI.

- **Fix: false 'Section truncated at the LLM output cap' marker in PM decision** - `reporting.write_report_tree` ran the truncation detector on the decision AFTER appending the computed disclosure block (which ends in lowercase, e.g. `models: n/a`), so a complete decision was flagged as an LLM cut whenever the Phase-D disclosure block was rendered. Truncation detection now runs on the raw LLM text only; audit/disclosure append after. Also tightened `_looks_truncated`'s bold-label exemption to short verdict lines (`**Action**: Buy`) - a long `**Executive Summary**: ...` prose line cut mid-word is now correctly flagged.

- **DSA reporting (phase D)** - `strategies/report_disclosure.py`: computed driver attribution (sum-to-100, never narrated), consensus support/oppose readout, `watch_conditions`/`next_check_time` (fast-path cadence), `invalidation_conditions` (>= 1 per decision: price_stop_loss / price_take_profit_status / data_quality / manual:thesis_reassessment fallback), `disclosure_footers` (sources-used-vs-empty + models). `reporting.write_report_tree` appends the advisory disclosure block to `5_portfolio/decision.md`.

- **DSA polish (phase C)** - `strategies/skills.py` + `strategies/skills/*.yaml` (declarative strategy-skill DSL with regime-from-opinion routing, bounded advisory score adjustments, `enable_skill_overlays` default off); `strategies/news_relevance.py` (deterministic relevance scoring, official-source boost, spam admission, degrade triple); `dataflows/news_cache.py` (owner-wait coalescing TTL cache). Tests: test_skill_overlays + test_news_relevance (25 pass).

- **DSA robustness (phase B)** - `dataflows/market_router.py` (market-for-symbol classifier + per-market `market_source_priority` chains, opt-in, default bit-identical), `dataflows/vendor_breaker.py` (3-fail/300s circuit breaker + half-open probe + negative capability cache, thread-safe), `VendorResult` honesty fields (`fallback_from`/`is_stale`/`stale_seconds`/`data_quality`/`missing_fields` + `to_dict`), `dataflows/effective_date.py` (effective-trading-date rules + all-closed skip, fail-open). Tests: test_market_router + test_effective_date + test_phase_b_wiring (20 pass).

- **DSA decision quality (phase A)** - `tradingagents/strategies/decision_guardrail.py`: post-PM downgrade-only stabilizer (risk-cap at Hold, near-resistance-without-inflow cap, near-support-without-outflow soften) with recorded `guardrail_reason`; versioned 0-100 <-> 5-tier-rating consistency validator; PM confidence capped on degraded `data_quality`; `PortfolioDecision` gains advisory `data_quality`/`guardrail_reason`/`risk_cap`; per-field integrity retry (`structured.retry_structured_missing_fields`) - targeted rebuild, never a blind re-roll. All default-off (`enable_decision_guardrail`). Tests: test_decision_guardrail (179, incl. the never-upgrades property) + test_phase_a_wiring.


- **Qlib Phase-1 pure calculators** (`docs/design_qlib_integration.md` Phase 1,
  all advisory + default-off): `strategies/factor_expressions.py` (Alpha158-style
  operators, expression-string cache, learn/infer fit-apply split with
  train-only moments), `strategies/signal_analysis.py` (rank IC/ICIR,
  quantile long-short, IC-decay half-life, pred-autocorrelation,
  with/without-cost report table), `strategies/portfolio_strategy.py` (Qlib
  Topk-Drop + convex enhanced-index with turnover cap / benchmark-deviation /
  force-hold-sell masks / two-stage fallback; scipy SLSQP + pure-python
  fallback, cvxpy optional), `strategies/market_tradability.py` (limit-up/down
  gates, suspension, volume participation caps, deal-price selector). New
  tools `get_factor_profile` (gated `enable_factor_profile`),
  `get_topk_drop_plan`, `get_enhanced_index_tilt` bound to the market/PM
  ToolNodes + agent_utils + trading_web value tools; `portfolio.allocation_block`
  gains Topk-Drop / enhanced-index strategy options behind
  `enable_topk_drop` / `enable_enhanced_index`; `scripts/backtest_strategy.py`
  fills honour tradability (`--limit-threshold` / `--participation` /
  `--deal-price` + `fill_model` report block); `strategy_quality_report`
  emits the with/without-cost table. Tests: `tests/test_qlib_phase1.py` +
  `tests/test_qlib_wiring.py` (43 pass; §8-1/2/3/6/7/8/9 acceptance).

- **Nightly-review driver `--mode recent`** - `scripts/nightly_review.py
  --mode recent` reviews each symbol's MOST RECENT
  `reports/<TICKER>_<YYYYMMDD>_<HHMMSS>` folder instead of the newest
  `batch_summary_*.jsonl`, so interactive CLI / `propagate()` / `pipeline.py`
  runs (which never write a batch summary) get the scheduled 07:35 pre-open
  review too. Newest-per-symbol is keyed on the folder-name timestamp
  (fixed-width, lexicographic); a folder is skipped with a note when it has no
  `5_portfolio/decision.md` or `full_states_log_*.json` to review; decoy
  entries (`pipeline_*` dirs, batch-summary files) are ignored. Default
  `--mode batch` is unchanged. trading_web `run_nightly` forwards `--mode`
  and the Nightly form gains a "Review source" selector.
  Tests: `test_nightly_review_recent_mode_newest_per_symbol` +
  `test_nightly_review_recent_mode_empty` (hermetic, timed); the existing
  batch-mode driver test is unchanged.
  **Hard-exit guard**: when run as the process entry point the driver now
  flushes and `os._exit()`s after a completed (or failed) run, mirroring the
  CLI's `_CLI_ENTRY` pattern — the moomoo SDK's non-daemon threads no longer
  hang the scheduled task at interpreter exit (a hung task would skip the next
  day's run under Task Scheduler's single-instance default). In-process
  callers (tests import the module) still return/raise normally. The scheduled
  `nightly_review.cmd` now runs `--mode recent --max-symbols 25` (outside the
  repos; ~45-50 min, finishes pre-open).

### Fixed

- **Batch hard-exit guard (moomoo shutdown block)** - `batch.py` now runs the
  same `_CLI_ENTRY` flush + `os._exit()` after a completed (or failed) run
  that the CLI and nightly driver already have. A finished batch (reports +
  `batch_summary_*.jsonl` fully written) previously hung at interpreter exit
  on the moomoo SDK's leaked non-daemon threads — the process stayed "Running"
  indefinitely, and under Task Scheduler's single-instance default that would
  skip the next day's run. The entry block was also moved to the file end so
  `_batch_pre_market_check` is defined before `main()` runs. In-process
  callers (tests) still return/raise normally.
- **Truncation-retry on the structured-output success path** - a structured
  call that parsed into the schema but was cut by `max_tokens` mid-render
  previously skipped `_retry_if_truncated` (only the free-text fallback path
  had it), so the report got the truncation marker with no continuation merge
  (e.g. ADSK 2026-09-02 deep PM run). `invoke_structured_or_freetext` now
  applies the same continuation retry to the rendered structured result.
  Tests:
  `test_invoke_structured_or_freetext_retries_truncated_structured_render` +
  `test_invoke_structured_or_freetext_no_retry_when_structured_render_complete`.
- **`positions_to_basket` treats Fidelity "Pending activity" as cash** - a
  settlement row (Symbol="Pending activity", no Quantity, empty Description,
  e.g. $8,993 on the Sep-02 Account1 export) was parsed as a position and
  emitted a phantom `PENDING_ACTIVITY` weight into the .env basket. The
  blank-Quantity cash branch now also matches settlement/sweep markers in the
  Symbol column (`pending`), same class as the documented blank-symbol / sweep
  rules; the pending dollars fold into the cash sleeve (denominator +41.5% ->
  +43.5%). Test: `test_pending_activity_is_cash`.
- **Analyst report-stub guard (status-turn → full report)** - a model can
  answer a tool loop with a bare *status turn* ("Good progress. Now let me
  gather...") that emits no tool_calls; the analyst router takes that as the
  final turn and the stub landed verbatim in `*_report` (observed: a 217-byte
  NVDA fundamentals report, CLI 2026-09-02 — `_looks_stub` only catches bare
  headers, not short self-interrupting progress notes). New
  `retry_chain_if_stub` (mirrors `_retry_if_stub` for the tool-calling chain)
  + `_looks_report_stub` (degenerate-stub OR short status-announcement
  detection) are wired into the market / news / fundamentals analyst normal
  path: a stubbed report is re-asked once to write the full report from the
  gathered evidence, else an explicit `**Report unavailable**` notice - never
  an empty or one-line report rendered as truth. Tests:
  `tests/test_analyst_report_stub.py` (7 hermetic).
- **Run-config guidance (gitignored `.env`, not committed)** - deep tier
  model separated from quick: `TRADINGAGENTS_DEEP_THINK_LLM=deepseek/
  deepseek-v4-pro-0813` (RM + PM get reliable structured output; quick stays
  flash for speed — NVDA's "Decision: unavailable" stub was flash's
  structured-JSON miss), `TRADINGAGENTS_MAX_OUTPUT_TOKENS_DEEP=4000` (was
  2500 — the deep prompt is the longest and 2500 truncated it mid-sentence),
  `TRADINGAGENTS_LLM_MAX_RETRIES=3` (retry transient failures instead of
  falling to the stub notice).

- **Positions -> risk-basket utility + PM holdings read (Option A/B)** - the
  risk basket now reflects the REAL book:
  - `strategies/book_positions.py` (new, pure/hermetic): broker CSV parse
    (Fidelity-style), cash detection via `**`-suffix / blank-symbol / sweep
    description (the broker's `Type` column is NOT used - Fidelity labels
    equities "Cash"), cross-account merge, `compute_weights` WITH cash in
    the denominator (the <1.0 remainder is the cash sleeve, consistent with
    `portfolio_cvar`'s documented "weights + cash" semantic), exact `.env`
    line render (round-trips through `default_config._coerce`),
    `patch_env_text` (only the two basket lines change), and
    `render_holdings_block` (advisory "Computed book" line for the decision
    agents; `holdings_tickers`/`holdings_weights` when set, else falls back
    to the risk basket).
  - `scripts/positions_to_basket.py` (new): dry-run default (per-account
    cross-check vs the broker's own pct, total/cash, per-symbol weights),
    `--apply` (`.env.bak` backup, rewrite the two basket lines),
    `--min-value` / `--exclude`, `--write-book-json` (gitignored dollar
    book = the Option-C artifact), `--json`.
  - Graph: `_compiled_decision_context` now includes the "Computed book"
    block, so the Trader / PM / risk debators / researchers see the actual
    holdings read - the PM can state "you hold no TSLA -> size 0" instead
    of the conditional "if you hold it, trim".
  - Config: `holdings_tickers` / `holdings_weights` (+
    `TRADINGAGENTS_HOLDINGS_TICKERS` / `TRADINGAGENTS_HOLDINGS_WEIGHTS`) =
    Option B override; empty = Option A (basket is the book). `.env.example`
    mirrors added.
  - Security: the `.gitignore` `profolio/` typo is fixed and `positions/`
    added (the CSV + book JSON are never commit-able).
  Tests: `tests/test_book_positions.py` (24 hermetic, timed): cash
  detection, merge, weights-including-cash, env round-trip, holdings
  fallback, gitignore guard, CLI dry-run/apply/write-book-json.

### Added

- **Parent-repo ports — look-ahead window + debate opening** (ports from
  `TauricResearch/TradingAgents`, no merge):
  - `dataflows/date_window.py` (new): shared half-open UTC window
    `[start, end + 1 day)` for dated content; undated items kept only when the
    window reaches the present. yfinance news migrated to it (same semantics as
    the old private helper).
  - StockTwits (`fetch_stocktwits_messages(..., start_date, end_date)`) and
    Reddit (`fetch_reddit_posts(..., start_date, end_date)`) now trim to the
    run's as-of window via `_within_window` — a historical/backtest run can no
    longer leak post-date chatter (#1220). No window = unchanged live behavior.
  - `agent_utils.opponent_argument_or_opening(text, opponent)`: the opening
    speaker in each of the 5 legacy debates (bull/bear researchers + the 3 risk
    debators) gets the explicit "(The {opponent} has not spoken yet — open the
    debate with your own case.)" marker when the opponent's response is empty,
    instead of interpolating an empty string that made models fabricate the
    other side's position (#1176). Real opponent arguments pass through
    unchanged.
  Tests: `tests/test_parent_ports.py` (12 hermetic, timed); existing
  `test_news_lookahead.py` migrated to the shared module.

### Added

- **Cookbook quant-strategy gap implementation** (`Strategies/cookbook.md`,
  recipes 1-5 + common framework) - the missing portfolio-construction /
  evaluation / options math is now code and bound to the decision agents:
  - **Time-series momentum** (recipe 1): `strategies/momentum.py::ts_momentum_weights`
    - MOP-style `sign(trailing log return) / EWMA vol`, target-vol normalized,
      gross-leverage capped; `factors.momentum_multihorizon` (1/3/6/12m ensemble).
  - **Cross-sectional mean reversion** (recipe 2): new
    `strategies/cross_section.py` - `winsorize`, `cross_sectional_z`,
    `centered_rank` (2.RankPct-1), `quantile_split`, `residualize_returns`
    (market beta residual), `neutralize_book` (dollar + beta + sector-neutral
    via a row-space projection, gross renormalized), `no_trade_band`.
  - **Cointegration pairs** (recipe 3): `statistical.py` - `spread_zscore`
    (rolling beta hedge), `pair_signal` (entry |z|>=2 / exit <=0.5 / stop >=3,
    cointegration + half-life cross-check), `pair_quantities` (dollar-neutral
    G/2 leg split), `ecm_loading` (VECM speed-of-adjustment gamma).
  - **Multifactor portfolios** (recipe 4): `factors.z_composite_alpha`
    (weighted linear z-composite alpha).
  - **Options volatility** (recipe 5): `options_math.py` - `black76` gains
    rho / vanna / vomma / charm (second-order Greeks), new
    `bsm_equity_surface` (vanilla BSM + full Greek set - closes the previously
    skipped vanilla-BSM item), `greek_pnl_response` (delta-gamma-vega-theta
    scenario P&L), `model_free_implied_variance` (Cboe/VIX-style discrete
    formula with the forward-discreteness term). `get_variance_premium` is
    repaired: it now computes a real model-free VRP from the machine options
    chain (strikes/mids to implied variance minus realized), with the IV-
    snapshot degrade when the chain is unavailable.
  - **Common framework**: `evaluate.py` - `turnover` (1/2 sum |dw|),
    `turnover_cost` (sum |dw|*c), `gross_exposure` / `net_exposure`,
    `rolling_sharpe`, `regime_split_performance`.
  - **Risk leaves**: `book_risk.cdar` (Chekhlov drawdown-at-risk tail),
    `portfolio_optimizer.max_diversification_weights` (Choueifaty Sigma^-1 sigma),
    `credit_spread.merton_distance_to_default` (equity-as-a-call fixed-point,
    DtD = d2 + risk-neutral PD), `rate_utils.forward_rate`,
    `market_session.book_depth_read` (microprice + OBI).
- **Agent binding (compute-as-tools)**: new market-analyst tools
  `get_ts_momentum_weights`, `get_pair_trade_signal`, `get_event_pnl_response`,
  `get_book_depth_read`, `get_merton_distance` (bound to the market analyst
  tool list + prompt + the graph market ToolNode + `agent_utils.__all__`),
  Merton also bound to the 3 risk debators' in-node risk loop; `get_tail_risk`
  now reports CDaR/DVaR, `get_risk_parity_alloc` reports max-diversification
  weights, plus a dedicated `get_merton_distance` Merton tool. trading_web
  Value Tools += `variance_premium` + `ts_momentum_weights`.
  Tests: `tests/test_cookbook_gaps.py` (27 hermetic, timed); affected suites
  349 passed.

### Fixed

- **Structured-debate robustness series (QCOM/DELL live runs)** - a
  session-long hardening of the opt-in `enable_debate` pipeline, each
  verified against live runs:
  - Judge json_object 400 root cause: the judge prompt lacked the literal
    "json" token, so OpenRouter's OpenAI/Azure backends rejected
    `response_format=json_object` -> the adapter fell back to a non-json
    call -> the model returned empty/ragged dimensions. The judge prompt
    now says "single JSON object" (also carries the flattened `scores[]`
    shape cue). Verified: real blind scores now appear in both
    `structured_debate.md` files (e.g. research Candidate_Y 6.75, risk
    Candidate_Z 5.75 on DELL).
  - Flattened `L2JudgeDimensionedRubric.dimension_scores` (enum-keyed dict)
    to `scores: [{dimension, score}]` (array of objects is far more
    reliably emitted under json_object); legacy dict shape auto-normalized;
    `_rubric_dimension_dict` back-compat.
  - Tolerant rubric coercion: `entrenchment_detected`/`rebuttal_effectiveness`
    string/object values coerce to bool/float (clamped 0-10) instead of
    failing the whole rubric.
  - Judge empty-dimension fallback: directed retry naming the exact four
    dimensions, then a deterministic prose-score parse (rationale numbers
    per dimension), then `rebuttal_effectiveness` proxy, then honest
    UNAVAILABLE - never a silent 0.0.
  - Registry-key mismatch: debaters humanize the Ground-Truth Key Index
    labels, so L1 marked every claim unverified -> `(unused)` in the
    ledger. `resolve_ground_truth_key` now routes normalize -> extended
    KEY_ALIASES (semantic variants) -> confidence-gated fuzzy (difflib,
    >=0.72 ratio, >=0.08 margin, token-overlap bonus) -> honest unverified
    (never fabricated). Tested against the real run labels.
  - Context-bounded debater prompts (static registry + last-turn delta +
    active disputes instead of full transcripts/reports), 4000-token cap,
    section-aware 1-shot example, risk-stance coercion (BULL/BEAR ->
    AGGRESSIVE/CONSERVATIVE), judge scores last non-degraded round.
  - `TRADINGAGENTS_DEBATE_NEUTRAL_MODEL` key so the neutral risk debater
    resolves its own model (luna), like the other roles.
  - CLI deterministic exit + hard-exit guards behind `_CLI_ENTRY` (moomoo
    shutdown-block can no longer hang or kill pytest).

- **CLI deep-run defect (`--depth` / interactive research depth)** - 'deep'
  mapped to 5 bull + 5 bear debate turns, so a deep run multiplied runtime
  (SKHY 08-31 took >1h vs 30-40m typical) and the later research-debate
  turns degenerated into rambling/empty arguments that poisoned the Research
  Manager (a 300-line garbage bear turn + 3 empty bear turns, then a 0-byte
  `2_research/manager.md`). Now the depth selection maps to the RISK rounds
  only and the bull/bear researchers each run exactly ONCE per analysis; the
  risk debators' aggressive/conservative/neutral rounds still scale with the
  depth selection as before. Also added: an empty-argument retry + honest
  note in both researchers, an explicit "plan unavailable" block in
  `reporting.py` when the Manager produces no usable plan (never a 0-byte
  file), and a 2-tool-round cap on the risk-debator + Trader in-node tool
  loops to bound runtime. Docs/README synced.

### Added

- **Risk-section structured-debate parity** (direction.md) — the structured
  multi-agent debate now mirrors the research section:
  - Risk debators (aggressive/conservative/neutral) emit `RiskDebaterTurnPayload`
    grounded turns into the new `structured_risk_state` channel; legacy
    `risk_debate_state.history` prose keys are still written so reporting and
    the Portfolio Manager consume the same shape.
  - The SAME blind L2 judge is generalized to N candidates
    (`anonymize_and_rotate(turn_by_role, roles)`, Candidate_X/Y/Z) and runs
    over the three risk candidates before the Portfolio Manager when
    `enable_debate` is on.
  - Model keys are shared across sections (direction items 3-5):
    `debate_bull_model` → bull + aggressive, `debate_bear_model` → bear +
    conservative, `debate_judge_model` → both judges; neutral risk analyst
    stays on the quick tier (no dedicated key).
  - **Depth parity** — ONE knob (`TRADINGAGENTS_RESEARCH_DEPTH` env or the
    CLI research-depth selection) drives BOTH the research and risk round
    counts to the same level; explicit per-round env overrides still win.
  - Router fix: `should_continue_structured_debate` no longer hard-stops
    after one round — it cycles to the next round within `max_debate_rounds`
    (the depth knob now actually takes effect on the structured path).
  - RM + PM prompts include the L2 judge verdict evidence block
    (`render_judge_evidence`); `4_risk/structured_risk_debate.md` mirrors the
    research evidence block.
  - All still opt-in via `enable_debate`; with the flag off the legacy risk
    chain is bit-identical (SD Risk nodes are no-op placeholders).
  - Tests: `tests/test_debate_risk_parity.py` (18 cases: model mapping,
    section router + round-cycling, risk turn channels, judge evidence block,
    risk graph edges on/off, depth parity).

- **Structured multi-agent debate implemented (opt-in)** (`docs/design_multi_agent_debate.md`
  P1-P5 + graph wiring): the research debate now runs as a structured subgraph
  when `enable_debate` is on (default OFF — the legacy one-shot chain stays
  bit-identical):
  - **P1 Grounding contract** — `strategies/debate_claim.py`: `ClaimRecord` /
    `ClaimLedger` + `verify_claim` (valid / violated / abstain / unverified /
    qualitative; deceptive-grounding source check against the run ledger).
  - **P2 Scoring + termination + severity** — `strategies/debate_score.py`:
    `debate_score` (evidence × novelty × constraint), `termination_check`
    (plateau / consensus / hard cap), `classify_severity` (R1' severity
    triage: HARD_BREACH → baseline, RETRYABLE → bounded scoped regen,
    SOFT_WARNING → penalty + annotated L2), `entrenchment_index` +
    `divergence_check` + `reweight_to_baseline` (R2' artificial-consensus
    α-reweight toward the empirical base rate).
  - **P3 Heterogeneous models + capability matrix** —
    `strategies/debate_capability.py` (R3 role×model floor check, fail-closed
    when required), `agents/utils/debate_roles.py` (`resolve_role_llm`
    `family:id` per role with quick/deep fallback + per-role tool surfaces),
    `debate_*` config keys + `TRADINGAGENTS_DEBATE_*` env overrides
    (+ `.env.example`).
  - **P4 Schemas + dual-mode adapter + judge** — `agents/schemas.py`:
    `DebaterTurnPayload` / `L1DeterministicResult` / `L2JudgeDimensionedRubric`
    / `L1ExecutionContext` (pydantic mirrors of the source doc's four JSON
    schemas); `agents/utils/debate_structured.py` dual-mode adapter
    (structured-output API + markdown-fence parse + bounded Pydantic repair,
    fail closed); `agents/arbiters/debate_judge.py` blind order-rotated
    dimensioned L2 judge.
  - **P5 A/B harness** — `scripts/debate_ab_harness.py` (Brier score +
    max-unforecasted drawdown), producers injected / `--demo`.
  - **Graph wiring** — `graph/setup.py` SD subgraph (`SD Bull -> SD L1 ->
    SD Bear -> SD L1 -> SD Finalize -> Research Manager`, O-condition
    placeholder nodes registered so targets never raise), the
    `should_continue_structured_debate` router, `debate_state` channel, and
    reporting's `2_research/structured_debate.md` (judge scores + claim
    ledger + L1 verdict, back-compat when absent).
  Tests: `tests/test_debate_claim.py` (12), `test_debate_score.py` (17),
  `test_debate_integration.py` (19), `test_debate_stream_hermetic.py` (2+
  compile) — 56 hermetic. ruff clean.
- **Multi-agent debate design revised for the §7 risk items**
  (`docs/design_multi_agent_debate.md`, revision v3, folding in the 2026-08-31
  update of `Strategies/Multi_Agents_Debate.md`): L1 severity triage
  (HARD_BREACH → baseline fallback, RETRYABLE → one scoped regen, SOFT_WARNING
  → penalty + annotated L2) replaces the binary gate (R1'); an entrenchment
  index `I_entrench` + divergence-floor rule raise an Artificial-Consensus
  Flag that α-reweights `W_final = (1−α)·W_debate + α·W_baseline` toward the
  empirical base rate (R2'); a fourth canonical wire schema
  `l1_execution_context.json` → `L1ExecutionContext` makes the recovery path
  explicit (R5'); FSM transition table + LangGraph mapping updated, new
  `debate_*` config keys (`debate_entrench_thresh`, `debate_divergence_min`,
  `debate_baseline_fallback`), literature + risks + acceptance criteria
  extended. Research/design only — no code changed.
- **Multi-agent debate architecture (research-only design)** (`docs/design_multi_agent_debate.md`) -
  research + design (no code) folding the source doc
  `Strategies/Multi_Agents_Debate.md` onto the existing bull/bear research
  debate: a two-layer judiciary (deterministic L1 gates — claim verifier,
  risk governor, consensus — always precede an L2 blind, order-rotated,
  dimensioned, ensembled LLM judge), heterogeneous per-role models with a
  config-time capability matrix (R3), the FSM transition table + canonical
  wire schemas mapped to pydantic (`DebaterTurnPayload`,
  `L1DeterministicResult`, `L2JudgeDimensionedRubric`), L1 fast-abort /
  single-role regeneration (R1), divergence caps + artificial-consensus
  reweight to baseline (R2), and a matched-compute A/B harness scored with
  Brier + max unforecasted drawdown (R4) before any gate ships. All proposed
  `debate_*` config keys default OFF (bit-identical current behavior);
  phased rollout P0-P6 maps onto existing seams (`independent_vote`,
  `risk_tool_loop`, `conditional_logic`). Companion to
  `docs/design_risk_calculations_agent_wiring.md`.
- **Risk calculations wired into the decision agents** (`docs/design_risk_calculations_agent_wiring.md`,
  7-phase audit implementation): (1) the 18 quant-risk tools that were
  registered in the market ToolNode but unreachable by the LLM are now bound
  to the market analyst (horizon-VaR, downside, trailing exit, risk-parity,
  normality, unit-root, CAPM, rotation, Clenow, omega, correlation,
  scale-out, sentiment-computed, curve surfaces, movers, variance premium);
  (2) 12 new `@tool`s wrap previously-untooled deterministic calculators:
  `get_fixed_risk_size` (commission/tranche-aware sizer), `get_exit_overrides`
  (two-pass drawdown/trail liquidations), `get_pre_trade_read` (notional +
  rate gates), `get_ledger_risk_state` (memory win-rate + paper-reviewer
  record), `get_trade_plan` (the plan card as a callable), `get_fixed_income_risk`
  (preferred YTM/duration/DV01/convexity), `get_pair_risk` (cointegration +
  Granger), `get_vif_read`, `get_vol_cones`, `get_trade_excursions`
  (MAE/MFE/profit-factor), `get_alpha_scoring` (magnitude-scored alpha),
  `get_regime_gate_read` (knife guard); (3) `get_risk_gate` now exposes the
  FULL governor surface (book cap, daily-loss budget, high-water-mark tiers,
  sector cap, tranche capital-at-risk, liquidity verdict, halt); (4) the
  Trader / PM / 3 risk debators' `computed_decision_context` gained a risk
  factsheet (limits registry, vol estimates, tranche peak-deployed +
  capital-at-risk, fixed-risk size); (5) the 3 risk debators run an in-node
  risk-tool loop (`agents/utils/risk_tool_loop.py`, 23 tools, capped at 8
  rounds, degrades to plain invocation when the provider cannot bind tools);
  (6) the Trader runs a 12-tool verification pass after its structured
  proposal; (7) cross-binds: news analyst gets credit-stress + news-sentiment,
  fundamentals gets fixed-income + alpha-scoring, Research Manager + Bull/Bear
  researchers get the computed context. Web: value-tools surface gains
  vol-cones / trade-plan / ledger-risk-state / regime-gate / fixed-income-risk.
  Tests: `tests/test_risk_agent_wiring.py` (22 hermetic).

### Fixed

- **Report truncated after Research Manager (missing Trader / risk / PM)** -
  interactive runs (e.g. SKHY 08-30/08-31) saved only the analysts +
  Bull/Bear/Research Manager and silently dropped `3_trading/trader.md`,
  `4_risk/*`, `5_portfolio/decision.md` — the graph **ended after the
  Research Manager judge**. Root cause: `graph/setup.py` had lost the
  `Research Manager -> Trader` edge (and the Bull/Bear debate conditional
  edges were dropped in the same block), so LangGraph had no path onward
  after the research debate; `write_report_tree` then skipped the sections
  whose state keys were absent. Restored the Bull/Bear -> (Bull | Bear |
  Research Manager) conditional edges AND added the `Research Manager ->
  Trader -> Independent Risk Stances -> Aggressive/Conservative/Neutral ->
  Portfolio Manager -> END` chain. Hermetic full-stream verification (SKHY,
  stub LLM) now emits `trader_investment_plan`, `risk_debate_state` and a PM
  `judge_decision`. Regression test:
  `test_production_setup_research_risk_chain_edges_are_wired` (asserts the
  complete chain is present in the compiled graph).
- **Tool-round cap `KeyError '<Analyst>'` on the interactive CLI** - a run
  whose market/news/fundamentals analyst hit the `MAX_TOOL_ROUNDS` (8) tool
  cap crashed with `KeyError: 'Market Analyst'` wrapped in LangGraph's
  "During task with name ..." note (live symptom: SKHY interactive run). The
  cap routers return the analyst node name, but `setup.py` registered the
  conditional-edge targets as only `[tools, clear]` (sequential) /
  `{tools, clear}` (parallel subgraphs), so LangGraph raised on the cap path.
  Now the analyst node itself is a registered target in both modes (a
  self-loop), and the three analyst nodes short-circuit the cap turn: the
  dangling `tool_calls` on the last message are stripped via
  `structured.finalize_messages` and ONE terminal prose turn writes the
  report — no re-invoke-then-ping-pong, reports are never left empty, the
  loop always terminates. Hermetic end-to-end repro (`SKHY`, stub LLM)
  completes the full graph in both modes. Regression tests:
  `test_production_setup_registers_analyst_cap_self_loop` +
  `test_parallel_subgraph_registers_analyst_cap_self_loop`.

### Added

- **`--value-dip-loose` (value-dip harvest mode) + eodhd-losers equity
  filter** - relaxes the value-dip technical entry from `RSI<=35 AND %b<=0.10`
  to **OR** (either oversold signal suffices) via a new `loose_technical`
  param on `strategies.value_dip.value_dip_setup` (default False: the analyst
  tools / strict AND are unchanged), and appends a ranked **near-miss table**
  (up to 50, distance-to-entry ordered) naming exactly which gate each near
  candidate missed (`value_floor` / `technical_entry` / `trade_risk` /
  `balance_sheet` / `profitability`). The `eodhd-losers` universe now
  **equity-filters** its seed against the EODHD exchange-symbol common-stock
  list (one cached call; warrants/units/leveraged ETFs — which dominate the
  intraday decliners — are dropped; degrades to the unfiltered list if the
  reference call fails). Web Screener gains the Loose dip gate checkbox,
  flags forward through `run_screener`. Tests:
  `test_value_dip_loose_prefilter_or_semantics`,
  `test_eodhd_losers_equity_filter_drops_non_common`,
  `test_eodhd_losers_loose_near_miss_renders` + web
  `--value-dip-loose` forwarding case.
- **`--universe eodhd-losers` value-screener universe** - the EODHD bulk US
  real-time feed (one call, ~18k rows, OpenD-independent) seeds a
  **loss-ordered** scan: the biggest intraday decliners by change% are the
  symbols screened, so value-dip / momentum candidates (RSI/%b oversold,
  stop <= 2%) are harvested from today's actual dips instead of an alphabetical
  `eodhd-us` slice. New `tradingagents/dataflows/eodhd.py::get_top_movers_symbols_eodhd`
  (machine-readable symbol table behind `get_top_movers_eodhd`; `.US` suffix
  stripped, `change_p` kept as percent, optional `min_price` floor).
  `-n/--movers-count` sets the decliner count (moomoo movers cap at 200;
  eodhd-losers accepts up to the whole feed); `--price-min` gates on the
  feed's live close; mcap / PE / ATR gates still run per-symbol afterwards.
  The feed rows carry price + change only (no name/mcap/type), so ETF/ETN rows
  are not name-filtered at seed time - the per-symbol gates handle them.
  Tests: `test_eodhd_losers_universe_seeds_scan` +
  `test_get_top_movers_symbols_eodhd_sorts_strips_caps` (hermetic, mocked
  feed). Docs: `Strategies/scan.md` "Universe sources",
  `docs/developer/06-entrypoints.md` §6.4, `docs/api_reference.md` §6.2/§9.
- **CLI Nerd Font icons** - the interactive TUI's status cells, team column,
  header/welcome titles and workflow-steps line render Nerd Font (nf-fa) glyphs
  when the terminal font supports them (`TRADINGAGENTS_NERDFONT` defaults on;
  set `0`/`false`/`off` for a plain-text fallback). Pure display change, no run
  behavior. (`cli/main.py`, README CLI section.)
- **News/sentiment providers (Phases A-C)** - three additive sources, per the
  free-tier research:
  - `dataflows/gdelt.py` - GDELT DOC 2.0 (keyless, free). `get_news_gdelt`
    (ticker full-text + **native tone**: avg/pos/neg/neutral per article) and
    `get_gdelt_tone_series` (daily avg-tone timeline). New market/news tool
    `get_gdelt_sentiment` (computed sentiment read). Note: GDELT's endpoint is
    network-flaky (connect timeouts), so it is registered but NOT in the default
    `news_data` chain (opt-in via chain config; fail-fast 8s timeout).
  - `dataflows/newsapi.py` - NewsAPI.org free Developer plan (100 req/day),
    key-gated `NEWSAPI_API_KEY`. `get_global_news_newsapi` (macro headlines)
    + `get_news_newsapi` (ticker keyword); wired into `get_news` /
    `get_global_news` default chains (tail).
  - `dataflows/benzinga.py` - Benzinga Basic Financial News API (free tier,
    headline + teaser + link). Key `BENZINGA_API_KEY`; registered but not in the
    default chain (needs a registered key; enable via chain config).
  - `get_gdelt_sentiment` bound to the news analyst (agent_utils, news
    ToolNode, news_analyst prompt already lists `get_massive_news`; the new tool
    joins it). Live-verified: NewsAPI returns global macro headlines with the
    provided key; GDELT endpoint was unreachable from this network (fail-fast
    degrades, no stall).
  Tests: `tests/test_news_sentiment_vendors.py` (15). ruff clean.
- **Extended technical indicators (Phase 1-3 of the indicator-gap plan)** -
  the standard trend/momentum/volume/structure group the project did not yet
  compute locally, all as pure offline calculators in
  `tradingagents/strategies/extended_indicators.py` (no vendor, no quota):
  Ichimoku cloud, golden/death cross, CCI, ROC, momentum oscillator, TRIX,
  Force Index, accumulation/distribution (A-D), VPT, Chaikin Money Flow,
  anchored VWAP, and a candlestick pattern scanner (doji / hammer / shooting
  star / bullish+bearish engulfing / morning+evening star).
  - Exposed as two new market-analyst tools `get_extended_indicators`
    (one combined call, shares the run-level OHLCV cache) and
    `get_candlestick_patterns`, bound in `agent_utils`, the market analyst
    tool list+prompt, and the graph market ToolNode.
  - Twelve Data `/technicals` pull-back deliberately NOT added: the local
    calculators already cover every indicator off any OHLCV source at zero
    API cost (per the deterministic/no-fabrication core).
  Tests: `tests/test_extended_indicators.py` (22) + 6 tool-wiring cases in
  `test_analysis_tools.py`. ruff clean.
- **Twelve Data + StockData.org vendors** - two new free-tier market-data
  sources wired through the vendor contract:
  - `dataflows/twelve_data.py` - `get_stock_data_twelve_data`
    (`/time_series`, 1day, same CSV shape), `get_market_snapshot_twelve_data`
    (`/quote`, realtime), `get_crypto_prices_twelve_data` (`/time_series`
    `BTC/USD`). Free "Basic": 800 credits/day, 8/min; key `TWELVEDATA_API_KEY`.
  - `dataflows/stockdata.py` - `get_stock_data_stockdata` (`/v1/data/eod`,
    newest-first -> oldest-first CSV), `get_market_snapshot_stockdata`
    (`/v1/data/quote`), `get_news_stockdata` (`/v1/news/all`, 2/req). Free
    "$0/mo": 100 requests/day; key `STOCKDATA_API_KEY`.
  - Both registered in `VENDOR_LIST` + `VENDOR_METHODS` (`get_stock_data`,
    `get_news`); `core_stock_apis` = `eodhd,moomoo,yfinance,tiingo,
    twelve_data,stockdata`, `news_data` = `... ,stockdata`; market snapshot
    fallback chain now Massive -> EODHD -> Tiingo -> Twelve Data; crypto
    fallback Tiingo -> Twelve Data. All key-gated (degrade to the next vendor on
    401/403/429/empty, no fabrication). Live-verified: AAPL OHLCV + quote via
    Twelve Data; AAPL EOD (123 rows) + quote + news via StockData.org.
    Tests: `tests/test_twelve_data_vendor.py` (12), `tests/test_stockdata_vendor.py`
    (10), `tests/test_new_provider_wiring.py` (5). ruff clean.

- **Analyst tool-loop edge regression** - the sequential graph lost its
  `ToolNode -> analyst` edge (introduced in the Option-A wiring pass), so a
  run TERMINATED right after the market analyst's first tool round: empty
  analyst reports, no debate / trader / risk / PM chain, and a stub-only
  report folder (reproduced live: interactive CLI `SKHY`, 2026-08-30). The
  edge is restored with a structural regression test (every analyst's tool
  node loops back) + a functional stream test that must complete a tool round
  and reach the debate. Tests: `tests/test_graph_tool_loop.py` (2).
- **Short-closes overlay crash** - `build_strategy_overlays` returns `None`
  for a < 60-bar series (thinly-traded ADR / new listing), and three folds
  called `.get` on the None (order-flow / position contract / risk governor),
  logging "'NoneType' object has no attribute 'get'". The overlay pipeline now
  treats a None overlay as an empty dict and no-ops cleanly with one
  informative log line. Tests: `tests/test_graph_tool_loop.py`
  (short-closes guard).

### Added
- **Independent pre-debate stances (Option-A hybrid)** -
  `enable_independent_vote` (`TRADINGAGENTS_ENABLE_INDEPENDENT_VOTE`, default
  off) — the 3 risk debators + bull/bear researchers each emit ONE independent
  structured stance (rating / confidence / strength / reason) BEFORE the
  debate loop runs, sampled with **no transcript and no opponents' responses**
  (the independence invariant; prompted without `risk_debate_state` /
  `investment_debate_state`). The G3 agreement/consensus math and the G1
  position contract then use the uncontaminated pre-debate agreement
  (`independent_agreement`), and the PM + Research Manager prompts receive the
  independent vote/reads alongside the debate history. The debates run
  unchanged as the risk-surfacing layer — this kills the conformity /
  adversarial-persuasion bias in consensus (FREE-MAD: consensus pressure
  reduces reasoning accuracy; a persuasive agent can drag a group to a wrong
  consensus). When the flag is off, every fallback is byte-for-byte the legacy
  parse-from-history consensus path. New: `agents/utils/independent_vote.py`,
  `IndependentStance` schema + `render_stance`, two graph nodes
  (`Independent Researcher Stances` / `Independent Risk Stances`), three state
  channels. Tests: `test_independent_vote.py` (12) + 3 prompt-injection
  contracts in `test_structured_agent_prompts.py`. ruff clean.
- **CLI one-input mode (`--symbol`)** - `tradingagents analyze --symbol AAPL`
  runs non-interactively: all 4 analysts, deep research (5 debate/5 risk
  rounds), today's date, and the LLM provider + thinking models from
  `TRADINGAGENTS_LLM_PROVIDER` / `TRADINGAGENTS_DEEP_THINK_LLM` /
  `TRADINGAGENTS_QUICK_THINK_LLM` in `.env`; the report auto-saves to
  `reports/<TICKER>_<ts>/` (now anchored to the repo root via
  `resolve_output_path`, not the process CWD). Interactive (no `--symbol`)
  flow unchanged. Tests: `test_cli_symbol_one_input.py` (3, hermetic).
- **Alpha Vantage keyed fallback** - `ALPHA_VANTAGE_API_KEY` set in `.env`;
  `alpha_vantage` added as the key-gated last vendor in the
  `technical_indicators` / `fundamental_data` / `news_data` default chains
  (free tier, 25 req/day - only consulted when the primary vendors fail).
  Live-verified: OVERVIEW returns real fundamentals for AAPL.
- **Provider-endpoint + calc-wiring pass** - audited every data provider's
  endpoint surface (docs + SDKs) and every strategy calculator for agent
  exposure:
  - **Keyless yfinance fallbacks** (new `y_finance.py` functions —
    `get_analyst_ratings_yfinance`, `get_earnings_calendar_yfinance`,
    `get_institution_holdings_yfinance`) registered in `VENDOR_METHODS` and
    the default `data_vendors` chains (`analyst_ratings`/`earnings_calendar`
    = `moomoo,finnhub,yfinance`; `institution_data` = `moomoo,yfinance`) so
    sell-side ratings, earnings dates/EPS surprise and ownership no longer
    depend on the moomoo gateway or a paid key.
  - **New market analyst tools** wiring unwrapped deterministic calculators:
    `get_scaleout_plan` (swing.scaleout_plan tiered profit-taking),
    `get_payoff_asymmetry` (statistical.omega), `get_book_correlation`
    (statistical.correlation_matrix). `get_strategy_quality` now also reports
    Calmar / Ulcer / tail-ratio / expectancy (previously-unwrapped evaluate.*).
  - All bound to the market ToolNode; hermetic tests
    (`test_yfinance_keyless_vendor.py`, new analysis-tool cases). ruff clean.
- **Tiingo data vendor (free Starter tier)** (`dataflows/tiingo.py`) -
  additive market-data source wired through the vendor contract:
  - **EOD OHLCV** - `get_stock_data_tiingo` (`/tiingo/daily/{t}/prices`, 7+
    yrs, `resampleFreq` daily/weekly/monthly/annually) as the yfinance/moomoo
    CSV shape, registered last in `core_stock_apis` (`eodhd,moomoo,yfinance,
    tiingo`).
  - **Fundamental statements** - `get_fundamentals/balance_sheet/cashflow/
    income_statement_tiingo` render Tiingo `dataCode`s as canonical-friendly
    `label : value` blocks that `statement_parsing._canonicalize` maps via
    `_ROW_ALIASES` (a working free fundamentals source; Massive's free-tier
    fundamentals 403). Registered in the `fundamental_data` +
    statements chains (`moomoo,yfinance,tiingo`).
  - **IEX quote** - `get_market_snapshot_tiingo` backs `get_market_snapshot`
    as a third fallback (Massive -> EODHD -> Tiingo).
  - **Crypto OHLCV** - `get_crypto_prices_tiingo` + a `get_crypto_prices`
    tool bound to the market analyst node + prompt (native crypto price
    source; `BTC-USD` -> `btcusd`).
  - **`--vendor tiingo`** preset in batch (`eodhd,moomoo,yfinance,tiingo`).
  - Key `TIINGO_API_KEY` / config `tiingo_api_key`; low free-tier caps
    (~1,000 calls/day, 50/hr, 500 symbols/mo) keep Tiingo last + behind the
    TTL cache; a 429 degrades via `VendorRateLimitError`.
  Tests: `tests/test_tiingo_vendor.py` (17, hermetic). News (403) + intraday
  (404) are not wired. ruff clean.

 (deep-study implementation)** (`docs/design_nautilus_trader_enhancements.md`) -
  design → implemented (3 phases):
  - **Backtest harness (new capability)** - `strategies/backtest_engine.py`
    (order state machine: SUBMITTED/ACCEPTED/PARTIALLY_FILLED/FILLED/CANCELED/
    REJECTED; bar-based limit/stop matching + cash curve) +
    `strategies/backtest_models.py` (fixed + maker/taker fees, adverse-tick
    slippage, fill-probability heuristic) + `scripts/backtest_strategy.py`
    (replays a report's entry/stop/target plan over vendor OHLCV with order-
    honored entry-then-exit, emitting fills + net-of-cost PnL; auto-reads the
    newest `full_states_log` stop). Advisory, never emits orders. Web:
    `run_backtest` capability + Scripts screen option.
  - **Consistent risk sizing** - `strategies/risk_sizing.py` (commission-aware,
    tranche-aware fixed-risk sizer: `risk_points` / `riskable_money` /
    `risk_money` / `risk_quantity`); `value_dip.tranche_plan` now sizes through
    it (commission shrinks the dollar-risk budget). `strategies/risk_checks.py`
    (rolling-window `RateLimiter` + per-symbol notional `pre_trade_check`).
  - **Statistics + config validation** - `strategies/evaluate.py` adds
    `calmar_ratio`, `ulcer_index`, `capture_ratio`, `tail_ratio`,
    `expectancy_stats`; `default_config.py` adds `validate_config()`
    (collects range/fraction/tranche-sum/HWM-monotonic violations - the
    Nautilus ConfigErrorCollector pattern).
  Tests: `tests/test_nautilus_phase{1,2,3}.py` (44) + value-dip/governor/
  contract regression green; ruff clean.

 (`docs/design_openbb_enhancements.md`) -
  design → implemented (Phases 1-4 + cross-cutting):
  - **Strategy depth** - `strategies/statistical.py` (normality, unit_root
    ADF+KPSS, omega, correlation_matrix, cointegration_pair, granger_causality,
    capm_decomposition, ols_factors, variance_inflation_factor) +
    `strategies/rotation.py` (relative_rotation RRG quadrants, clenow_momentum,
    vol_cones). 5 new market @tools (get_normality / get_unit_root /
    get_relative_rotation / get_capm_risk / get_clenow_momentum).
  - **Typed dataflow layer** - `dataflows/schema.py` VendorResult envelope
    (results/provider/warnings/error_kind + to_llm/to_markdown),
    `dataflows/registry.py` (coverage, required_credentials, filter_params,
    command_map), `route_to_vendor_typed()` mapping sentinels -> error_kind.
  - **Free-tier data surfaces** - `dataflows/cboe.py` (options surface ->
    options_math.black_vol_surface), `dataflows/federal_reserve.py` (SOFR +
    Treasury curve for term-structure discounting), `dataflows/screener.py`
    (yfinance universe screener + movers). 4 new config gates default OFF.
  - **Web product (trading_web)** - watchlist, SignalTable grid, TickerChart
    (candlestick/volume/drawdown), run presets, credential manager, job
    timeline + rerun (54 backend tests, vite build clean).
  - **Web user guide screen (trading_web)** - `HelpGuide.jsx` (`/"guide`),
    plain-language documentation for every screen (purpose, sample UI
    selections, likely result) written for non-technical / non-financial
    users; nav entry + route + guide CSS, `npm run build` clean.
  - **QuantLib + Lean enhancements (deep-study implementation)** (`docs/design_quantlib_lean_enhancements.md`) -
  design → implemented (Phases 1-4 + cross-cutting): new pure modules under
  `strategies/`, extended evaluation breadth, 4 new market analyst tools, and
  10 new config keys (all gates default OFF / advisory-only):
  - **New modules** - `options_math.py` (black76, implied_vol_and_greeks,
    black_vol_surface), `rate_utils.py` (discount_factor, compound_factor,
    equivalent_rate, monotone_fill, downside_measures),
    `portfolio_optimizer.py` (risk_parity_weights, min_variance_weights,
    confidence_weights, enforce_sector_exposure, risk_contribution),
    `risk_manager.py` (two-pass `manage_risk` exit override +
    `trailing_stop_targets`; advisory, not wired into the runtime graph yet),
    `alpha_eval.py` (alpha_score, insight_accuracy), `config_robustness.py`.
  - **Extended modules** - `evaluate.py` (skewness, kurtosis,
    downside_deviation, sortino, tracking_error, information_ratio, beta,
    alpha, treynor, rolling_beta, probabilistic_sharpe, underwater_drawdowns),
    `exits.py` (`trailing_stop_exit`, `max_giveback_exit`), `book_risk.py`
    (`return_autocorrelation`, `var_cvar_horizon`), `journal.py`
    (`trade_excursions` MAE/MFE), `liquidity_risk.py` (volume_share_slippage,
    market_impact_slippage).
  - **New analyst tools (market ToolNode)** - `get_downside_read`,
    `get_horizon_var`, `get_trailing_exit`, `get_risk_parity_alloc`;
    `get_strategy_quality` now also emits sortino + psr.
  - **Config keys (+ `TRADINGAGENTS_*` env overrides, gates default OFF)** -
    `psr_benchmark_sharpe` (0.0), `rolling_window` (132), `downside_mar` (0.0),
    `trailing_stop_pct` (0.05), `enable_trailing_exit` (False),
    `risk_parity_enabled` (False), `risk_manager_drawdown_pct` (0.05),
    `enable_risk_manager` (False), `volume_share_vol_limit` (0.1),
    `volume_share_price_impact` (0.025).
  Tests: 62 new + 176 regression green, ruff clean.

- **P1/P2/C3: pre-open + execution-quality advisory rows (Alpaca free IEX)** -
  implemented the measurable slices of the institutional extended-hours
  workflow with the tiers this machine actually has (probed live):
  - **P1 pre-market RVOL** (`dataflows/preopen.py::premarket_rvol`): today's
    pre-open volume / 30-day pre-open average (Alpaca 15-min bars pre 09:30
    ET) - the text's "RVOL > 2.0x institutional" read. Verified live on AAPL.
  - **P1 pre-open gap** (`preopen_gap`): gap anchored to the LIVE pre-open
    price (Alpaca latest trade), not yesterday's close.
  - **P2 live IEX quote-depth** (`preopen_book_depth`): spread_bps, bid/ask
    size imbalance, thin-book flag - the free-tier stand-in for NOII opening
    imbalance (true NOII is plan-gated; documented as a proxy).
  - **C3 alpha-profile** (`postfill_drift` + `strategy_quality_report`):
    post-fill N-day drift vs arrival on the paper ledger - the "did our fill
    leak / adverse selection" test. All advisory, default-ONLY-injected into
    the pre-market reviewer (never gates).
  - Web Pre-Market screen Help updated; config + env keys added
  - **Agent + web sync**: the 5 decision agents (Trader, PM, 3 risk debators)
    now receive the pre-open RVOL / gap / book-depth reads (plus the existing
    regime + re-rating + plan card) via `computed_decision_context`; the
    value-dip analyst tool renders regime_gate + re_rating rows (visible in
    the web Value Tools page), the pre-market reviewer prints them (web
    Pre-Market job output), and the report's `IVa. Computed Decision Context`
    section surfaces the full advisory set.
    (`enable_preopen_rvol` / `enable_preopen_depth` / `enable_alpha_profile`).
  - **Probed data availability** (your tiers): Alpaca free IEX = pre-market
    bars + live quote + news AVAILABLE; EODHD lowest tier = real-time OHLCV
    only (no pre-open volume baseline), Massive free = NOI 404 (plan-gated),
    short-locate/HTB = NOT AVAILABLE (out of scope, analysis-only).
  Tests: `test_preopen.py` (7, hermetic, mocked Alpaca). Full suite green.

- **Institutional workflow for value-dip + swing (Phases A-E, design
  `docs/design_institutional_value_dip_workflow.md`)** - mapped institutional
  practice (value-desk funnel, AQR-style mean reversion, risk-first tranches,
  desk risk policy, TCA, event sizing, regime switching, VCP/SEPA process,
  quant evaluation) onto the stack. ALL new rows are advisory (computed +
  injected into the LLMs); nothing gates by default (opt-in strict flags):
  - **A1 regime gate** (`strategies/regime.py::regime_gate_read`): rolling
    realized-vol percentile + fast-downtrend knife guard + catalyst window;
    new `regime_gate` row in `value_dip_setup`. Strict opt-in:
    `value_dip_regime_gate` (+ vol/downtrend/halve keys).
  - **A2 re-rating catalyst** (`value_dip.py`): `re_rating` row from REAL EPS
    surprise (earnings tool), revisions, institutional accumulation, forward
    PEG - "cheap stays cheap without a catalyst". Strict opt-in:
    `value_dip_require_catalyst`.
  - **B1 daily-loss + high-water-mark gates** (`risk_governor.govern`): new
    `daily_loss_pct` / `hwm_drawdown_pct` inputs; budget + soft/hard tiers
    (`risk_daily_loss_budget_pct`, `risk_hwm_soft/hard_pct`).
  - **B2 trade plan card** (new `strategies/trade_plan.py::build_trade_plan`):
    one markdown plan (unified stop, tranches, tiers, BE rule, trail,
    adherence checklist) compiled per run and injected into ALL 5 decision
    agents (Trader, PM, aggressive/conservative/neutral debators) via
    `graph._compiled_decision_context`, and appended to the report.
  - **B3 BE-after-confirmation** (`exits.py::breakeven_after_confirmation`,
    `breakeven_trigger` = atr|r|structure): move stop to BE only after 1R /
    higher-low - no more too-early BE.
  - **B4 stop-never-widen** (`stop_never_widen`): unified invalidation stop
    flagged in the plan card + trader prompt.
  - **C1 execution/TCA** (`pre_market.py::record_review`): arrival_price /
    fill_price / slippage_bps columns; `strategy_quality_report` gains an
    execution block (avg slippage, fill rate).
  - **C2 turnover guards** (`min_holding_days`, `max_trades_per_period`).
  - **D1 sleeve tagging** (`memory.store_decision(sleeve)` + parse): honest
    per-style attribution in `strategy_quality_report` sleeves block.
  - **D2 drift/alpha-decay monitor** (`strategy_quality_report`): rolling
    4-wk win-rate/Sharpe vs baseline; `drift_threshold`.
  - **Agent data-feeding**: every run seeds `computed_decision_context` into
    state; the 5 decision nodes cite the deterministic numbers (regime /
    re-rating / plan card / risk snapshot / decay hint) instead of inventing.
  - Config keys + env overrides + `.env.example`; web Help text updated.
  Tests: 1503 passed (2 skipped), ruff clean.

- **Value Dip + Swing enhancements (web-researched, matched to practice)** -
  research compared the setup/exit math against established swing-trading
  practice and closed the gaps:
  - **VCP halving progression** (`swing.py::vcp_setup`): the default
    `contraction_tol` is now `0.65` so each pullback must be *successively
    shallower* (reproducing the named 15%->8%->3%; ratios ~0.53/0.38), with a
    `max_final_depth` (default 8%) final-tightness gate and a `pivot` field =
    the highest high of the final contraction (the Minervini breakout buy
    point). Pass `contraction_tol=1.10` for the old permissive rule.
  - **Chandelier true-highs** (`swing.py::chandelier_exit`): accepts a real
    `highs` series so the trailing stop sits below the true 22-bar high
    (was using closes as an upper proxy); threaded through `swing_report` +
    `get_swing_exits`.
  - **Value-dip trend filter** (`value_dip.py::value_dip_setup`): adds a
    `trend` row (price >= 200-SMA and 50-SMA rising) reported when >=200
    closes; gates only when the caller opts in via `require_trend` (a value
    dip is often below its 200-SMA, so it is not a hard default reject).
  - **Stop harmonization** (`value_dip.py`): the `trade_risk` row now also
    reports `plan_stop_pct` / `plan_stop_ok` (the composite plan stop,
    ~3.5 ATR from P1) vs `max_plan_stop_pct` (8%), reconciling the setup's
    <=2% risk screen with the actual wider tranche stop.
  - **Strict-VDU** (`value_dip.py::value_dip_setup`): `strict_vdu=True`
    promotes the Step-2 VDU ladder, valuation-Z and support to hard gates
    (measured only; unknown still never fails).
  - **Configurable tranche ladder** (`value_dip.py::tranche_plan/risk_read`):
    new `steps` (ATR multiples, default 1.0/2.0) and `pct_steps` (fixed
    %-drawdown-from-P1 ladder) options.
  - **R-based breakeven** (`exits.py::stop_to_breakeven_r`): move the stop
    to break-even after `rr` x R in favor (mirrors practice of ~1R-1.5R).
  Tests: `test_strategies_value_dip` (ladder modes, trend, plan-stop),
  `test_strategies_vcp` (halving, final-tight, pivot), `test_strategies_value_style`
  (R-based BE). Docs: README, CHANGELOG.
- **Interactive CLI now applies the strategy overlays (CLI/batch parity)** -
  the interactive CLI built state directly and streamed the graph but NEVER
  called `_apply_strategy_overlays`, so a CLI report omitted the "Risk Gate
  (computed)" block, position contract and computed risk context that the
  `propagate()` (batch/API) path renders - two same-day NVDA runs diverged
  materially (batch 12:02: Hold / PT 323.37 / gate PASS vs CLI 13:48:
  Underweight / PT 188.32 / no gate block), not from LLM variance alone.
  Fix (`cli/main.py`): seed `risk_context` into the initial state BEFORE the
  Portfolio Manager (via `graph._precompute_risk_context`) and apply
  `graph._apply_strategy_overlays(final_state, ticker)` to the merged state
  before saving - the same two hooks `propagate()` uses, so the CLI report
  now carries the same gate/contract/context. Overlay failures degrade
  silently (cannot break saving, matching propagate). Tests:
  `test_cli_no_console` wiring guard (seed-before-stream, overlay-before-save).

### Fixed
- **Two-stage screener gating (no provider calls during the gate)** - the
  main scan loop now runs a **cheap OHLCV-only gate (Stage A)** on the single
  cached price series before any fundamentals fetch, so `value-dip` /
  `trend-pullback` / `breakout` / `momentum` / `swing` / `vcp` all drop
  definitive non-candidates without hitting a provider. Only survivors reach
  the fundamentals stage (Stage B, memoized once per ticker via
  `_fetch_fin_cached` + `_CASHFLOW_CACHE`) and then provider enrichment
  (Stage C: float / sector / revisions / institutions). `value` / `all` have
  no cheap technical signal and fall straight through, as before. This makes
  a large `eodhd-us` slice tractable (was effectively hanging per-name) and
  fixes the duplicate cashflow fetch inside `_value_dip_scan`. Tests:
  `test_cheap_gate_deferred_before_fundamentals` +
  `test_eodhd_cheap_gate_before_fundamentals` (gated-out names never fetch
  fundamentals). ruff clean.
- **Risk gate placement + compact verdict** - the computed `Risk Gate (computed)`
  block was prepended to EVERY analyst report (input evidence, not risk
  output), so it appeared 6+ times; it now lives once in `4_risk/*.md` and
  `5_portfolio/decision.md` (and once in the consolidated report's IV section).
  The compact-mode `4_risk/verdict.md` previously duplicated the PM decision
  almost byte-for-byte; it now contains the risk gate + a pointer to the
  decision. `scripts/rebuild_complete_report.py` gate recovery hardened (scans
  decision/risk/analyst files in order), and `_readable_section` made
  idempotent (re-render no longer doubles `### Round N` headings or stacks
  blank lines). Tests: `test_report_readable.py` (+3), `test_rebuild_gate_recovery.py` (3).
- **Interactive CLI always writes verbose risk-debate files** - the NVDA run
  produced a single `4_risk/verdict.md` instead of `aggressive.md` /
  `conservative.md` / `neutral.md` because an ambient
  `TRADINGAGENTS_RISK_COMPACT_REPORT=true` (shell env / `.env`) flipped the
  compact-report mode on. The interactive CLI now forces
  `risk_compact_report=False` in `_build_run_config`, so a watched run always
  writes the three per-analyst transcripts; `.env` was also reset to `false`.
  Headless/web runs still honor their own config (they keep the compact
  artifact when they opt in).
- **Readable reports everywhere** - debate/research/trader reports are
  generated as conversational prose concatenated with single newlines, so
  they rendered as one unbroken wall. New `reporting._readable_section`
  (deterministic, content-preserving): adds paragraph spacing between plain
  prose lines and promotes repeated round markers (`Bull:`/`Aggressive
  Analyst:`) into `### Round N` headings, applied to research (bull/bear/
  manager), trading (trader) and risk (aggressive/conservative/neutral)
  sections. Tables / headings / lists / code fences are never touched.
  Existing folders re-render via `scripts/rebuild_complete_report.py`.
  Tests: `test_report_readable.py` (3).
- **G2 calibration feedback loop wired** (`decision_hardening_spec.md` G2) -
  previously `record_calibration_entry` had zero call sites and `_calibrated_p`
  always returned `None` (identity), so `enable_calibration` computed buckets
  but never used them. Now: (a) `_maybe_record_calibration` stamps
  `{confidence, won=delta_r>0}` into `calibration_ledger.jsonl` at resolve time
  (confidence parsed from the PM decision's `**Confidence**: X` line);
  (b) `_calibrated_p(decision_text)` returns `calibrated_confidence` (identity
  below `calibration_min_n`); (c) `_compiled_decision_context` injects
  `calibration_table_text` into the Trader/PM/risk-debator prompt when the
  ledger has samples. Tests: `test_calibration_wiring.py` (5, hermetic).
- **`get_ratios` abs(None) crash** - `compute_ratios` called `abs(capex)` when
  `capex` was `None` (OCF present, capex missing) -> `TypeError: bad operand
  type for abs()`, which aborted the `tools_fundamentals` node mid-run (seen
  live on NVDA). Both FCF and dividend_yield now guard the missing operand.
  Regression test added (`test_capex_none_does_not_raise`).
- **Strategies docs kept true** - corrected the audit's doc-misnomers:
  `decision_hardening_spec` (`weighted_score` -> `weighted_sentiment`/
  `decayed_weight`/`computed_sentiment_line`; `evaluate_orderflow.py` ->
  `orderflow_evaluate.py`), `alpaca_data_analysis.md` (ScheduleGate /
  `get_clock_calendar` -> the inline `get_clock()` note in `value_screener.py`;
  `scripts/alpaca_fetch.py` -> inline Alpaca OHLCV fallback; `get_assets` +
  Alpaca corporate actions now marked NOT implemented), and
  `value_dip_swing_prepost_research_plan.md` (ROC/TRIX/Force/A-D explicitly
  marked not implemented).
- **Canonical output root (reports/screener/action_reports)** - every
  relative output path is now anchored to the TradingAgents repo root instead
  of the process CWD, so runs never write into the launch directory. The web
  app (launched from ``TradingNew`` or ``trading_web``) previously caused
  ``batch.analyze`` to drop ``reports/`` into those parent folders; stale
  ``TradingNew/reports`` and ``trading_web/reports`` were migrated into
  ``TradingAgents/reports``. New `repo_root()`/`resolve_output_path()`
  helpers in ``tradingagents/dataflows/utils.py``; wired into
  ``batch.py`` (analyze report_dir + batch_summary), ``pipeline.py``,
  ``value_screener.save_watchlist``, ``action_report`` (--reports-dir /
  --out-dir), ``nightly_review``, ``pre_market_review`` and
  ``rebuild_complete_report``. Absolute / ``~`` paths pass through untouched.
- **Full-set audit (read-before-edit): 14 defects across the deterministic
  calculators, the dataflow/vendor layer, and tool binding — the numbers the
  LLM agents cite are now correct and reachable.**
  Correctness (HIGH — silently-wrong numbers):
  - `strategies/exits.py::exit_check` - profit target was anchored at the
    current close instead of the entry, so `target_hit`/`holding_action` could
    never return `target` (target = close + 4*ATR is always > close). Now
    `target_level(entry, ...)`; the `get_exit_check` tool reports real hits.
  - `strategies/book_risk.py::var_cvar_horizon` - parametric CVaR had a sign
    error and divided by the wrong tail probability (`+0.1085` "gain" instead
    of the true negative tail loss). Now `mu_T - sigma_T*phi(z)/q`.
  - `strategies/momentum.py::first_pullback` - reward was measured to the
    already-passed `recent_high`, so `rr = reward/risk < 1` whenever the
    trigger fired and the 2R gate made the candidate permanently dead. Now the
    target is a measured-move extension beyond the trigger. `get_momentum_detail`
    also printed zero pillars because it indexed `pillars()` with keys
    `("a","m","e","l")` that don't exist — fixed to the real
    `rvol/high_volume/gap/price_band/float`.
  - `dataflows/statement_parsing` - (1) yfinance statement CSV payloads
    (`# Data retrieved on: ...` comment header) were mis-routed to the text
    parser by the `:` check, so every canonical fundamental silently degraded
    to n/a; comment lines are now stripped before dispatch. (2)
    `_parse_csv_statements` took the RIGHTMOST numeric cell as "latest", but
    yfinance columns are newest-first, so the OLDEST fiscal year was returned
    as the current value (the M-Score/Piotroski latest-value regression); now
    takes the first (newest) numeric cell. (3) added `stockholders equity`
    aliases so yfinance's "Stockholders Equity" row maps.
  Correctness (MED):
  - `strategies/evaluate.py::tracking_error` - RMS instead of the standard
    deviation of active returns (mean not demeaned), inflating tracking error
    and understating information ratio — now demeaned.
  - `agents/utils/value_dip_tools.py::_period_multiple` - `ev_ebitda` fell back
    to P/EBITDA; now derives EV = market cap + debt - cash (never P/EBITDA).
  - `strategies/ratios.py` + FCF helpers - capex/dividends may be a negative
    GAAP outflow (yfinance/Tiingo) or a positive magnitude (moomoo); FCF and
    dividend yield now use `abs()` so capital spend is subtracted, not added.
  - `dataflows/alpha_vantage_indicator.py` - a generic exception returned an
    error string that `route_to_vendor` caches as authoritative data; now
    re-raised so the chain falls through. `screen_equities` /
    `get_market_movers` invalid-argument replies are now `DATA_UNAVAILABLE`
    sentinels (not cached). `eodhd.get_exchange_symbols_eodhd` keeps the raw
    list for the screener, and the routed `VENDOR_METHODS` entry now uses a
    string renderer to honour the vendor contract.
  Wiring (compute-as-tools):
  - `get_exit_plan` (new @tool) wraps `exits.breakeven_after_confirmation` +
    `max_giveback_exit` — the trade-management exit arithm is now a callable
    tool, bound to the market node.
  - `get_consensus` and `get_sentiment_computed` were re-exported in
    `agent_utils.__all__` but bound to NO ToolNode (unreachable by any agent);
    now bound (fundamentals / market).
  Config:
  - `batch.py` `--vendor` presets (moomoo/yfinance/eodhd/tiingo) omitted the 4
    OpenBB free-tier data categories (`options_surface`, `risk_free_curve`,
    `equity_screener`, `market_movers`), so a preset silently dropped those
    sources from `data_vendors` (failed
    `test_moomoo_preset_is_moomoo_first_everywhere`). All 4 added to every
    preset, keeping the full 27-key category set.
  Low/robustness:
  - `strategies/value_dip.py::tranche_risk_read` - `book_ok` now includes an
    existing-book fraction (`book` param) per its docstring.
  - `strategies/technical_factors.py::keltner_channel` - EMA midpoint (was an
    SMA, which shifted the channel in trending series).
  Tests: added/updated in `test_analysis_tools.py` (exit_plan /
  sentiment_computed / consensus), `test_statement_parsing.py` (newest-first
  CSV + comment-stripped `_canonicalize`); ruff clean.
- **Per-analyst tool-round cap + empty-report guard (NVDA missing market.md)** - a market/news/fundamentals analyst whose tool loop never terminates (model keeps calling tools, or a slow/hung vendor call keeps the loop spinning) previously left the analyst report empty, which reporting.py silently dropped - the run completed 'normally' with no `1_analysts/market.md` and no error. Now: `ConditionalLogic` forces the terminal report turn after `MAX_TOOL_ROUNDS` (8) tool rounds (routing back to the analyst node instead of the tool node), `structured.finalize_messages` runs that turn with the dangling tool_calls stripped (one final LLM call; truncation-retry + degrade intact), and `reporting.write_report_tree` writes an explicit "report unavailable" block (file + consolidated report) when an analyst report is empty - never a silent gap. Sequential and parallel (`analyst_concurrency>1`) analyst paths both covered. Tests: `tests/test_tool_round_cap.py` (12) + 3 reporting guard tests; ruff clean, 124 regression tests green.
- **Empty final decision after structured-output fallback** - a model that
  misses `with_structured_output` can answer the free-text retry with only a
  section header (live-run symptom: `**Decision` alone landed in
  `5_portfolio/decision.md`). `invoke_structured_or_freetext` now detects a
  degenerate stub, re-invokes once with a completion directive, and if still
  empty returns an explicit "**Decision**: unavailable" notice — never a bare
  header. Covers Trader / Research Manager / Portfolio Manager free-text
  paths. Tests: `test_invoke_structured_stub_freetext_regenerates`,
  `..._still_empty_returns_notice`, `..._retry_exception_returns_notice`.
- **End-to-end advisory-context injection (agent + report)** - the Phase A-E
  decision context (`computed_decision_context` / `risk_context`) was seeded
  onto `AgentState` but the keys were not declared as LangGraph channels, so
  native LangGraph silently dropped them: the Trader / PM / 3 risk debators
  never saw the regime gate / plan card / pre-open rows, and the report's
  `IVa. Computed Decision Context` section never rendered. Declared both keys
  on `AgentState` so they flow to the decision nodes and to `final_state`
  (report now surfaces IVa). Regression tests:
  `test_agent_state_declares_decision_context_channels` +
  `test_agent_state_carries_decision_context_through_graph` (a seeded value
  now reaches a node and the graph output).
- **Pre-market reviewer pre-open rows hidden behind news** - in
  `scripts/pre_market_review.py::_build_summary`, the pre-market RVOL /
  pre-open gap / book-depth lines were indented inside the `if news_titles:`
  block, so they only rendered when overnight headlines existed. They now
  print unconditionally (each still degrades to nothing when its data is
  unavailable), matching the design's independent-delta contract.
- **Audit-driven correctness fixes (data integrity + wiring)** - a repo-wide
  audit surfaced and fixed ~26 defects across strategies, dataflows, graph
  wiring, config, and entry points. All with hermetic regression tests.
  Correctness (HIGH):
  - `quantitative_scores.py`: Piotroski ROA point no longer awarded to
    negative-ROA firms (`if roa or 0 > 0` parsed as `roa or False`).
  - `interface.py`: `VendorRateLimitError` now recorded in `first_error`, so an
    all-throttled optional chain degrades to `DATA_UNAVAILABLE` instead of
    raising a raw `RuntimeError`.
  - `alpha_vantage_common.py`: HTTP 429/5xx / timeout mapped to
    `VendorRateLimitError` (was an untyped crash of the prime price path).
  - `strategies/dcf.py`: projects the LATEST FCF, not the historical max (a
    declining/hump series was overstated ~30-40%).
  - `strategies/technical_factors.py`: OBV bullish-divergence slice fixed
    (was always False).
  - `y_finance.py`: fundamentals/statement/insider functions re-raise instead
    of returning an "Error retrieving..." prose blob that the router cached as
    truth and never fell back from.
  - `default_config.py`: list-typed env overrides (e.g.
    `TRADINGAGENTS_TRANCHE_WEIGHTS`) coerce to the default's element type; a
    numeric list was landing as strings and silently disabling the tranche fold.
  - `market_analyst.py`/`fundamentals_analyst.py`/`news_analyst.py`: bound
    tools the prompts instruct (get_expected_move, get_institution_holdings,
    get_earnings_surprise_history, get_momentum_scan,
    get_market_snapshot_alpaca, get_insider_transactions), closing a
    no-fabrication gap (the model could not fetch those figures).
  Edge/wiring (MEDIUM):
  - `yfinance_short_interest.py` / `y_finance.py`: percent fields scaled x100
    with a `%` marker (was 100x unit drift).
  - `moomoo.py`: `_check_ret` classifies quota/throttle (incl. Chinese
    phrasing) as `VendorRateLimitError` before the permission check;
    `_moomoo_code` raises on forex/futures/non-whitelisted-crypto instead of
    returning a bogus `US.` code.
  - `pre_market.py`: `resolve_ledger` uses a stored `prior_close`
    (non-circular - was recomputing the exact review gap); `record_review` now
    stores it.
  - `size.py` `stop_loss_atr` returns None on insufficient data (was 0.0);
    `market_session.py` `opening_range` emits a target only for a real ORB
    breakout (was a below-stop short target on a flat close).
  - `normalized.py` `trap_verdict` accrual default 0.06 (consistent with
    `value_dip.decline_driver_check`; was 0.02).
  - `pipeline.py`: `_run_batch` caps workers via `batch.effective_workers()`
    (was bypassing the moomoo connection cap).
  - `value_screener.py`: `--rank composite` / `enable_composite_rank` now wired
    (were dead); eodhd-us universe truncation is warned, not silent.
  - `strategy_quality_report.py`: real `--illiq` flag + cost threading (was
    documented but rejected by argparse); `validate_massive_flat.py` returns a
    non-zero code when no CSV is present.
  - `trading_graph.py`: seeds deterministic `risk_context` into the initial
    state so the Portfolio Manager actually receives CVaR/liquidity context
    (was computed only after the graph, never reaching the PM).
  - `regime.py` `realized_vol` returns None on insufficient data
    (`factors.py` guard updated); `parabolic_sar` computes `below`/`exit` when
    a `closes` series is supplied.
  Docs/config truth:
  - `api_reference.md` §1.2/§5 + `.env.example`: strategy-overlay defaults
    aligned to code (only `enable_events`/`enable_reflection`/
    `enable_sentiment`/`enable_strategy_overlays` default True; the rest
    opt-in) - docs previously claimed default True.
  - Documented the two missing `TRADINGAGENTS_ENABLE_DECISION_AUDIT` /
    `TRADINGAGENTS_ENABLE_LIQUIDITY_GATE` overrides; corrected the stale
    `enable_sentiment` "no override / off" comment.
  - `api_reference.md` §9: batch `--vendor` eodhd, `--workers` 1-4,
    pipeline `--universe` top-movers-massive; AGENT_ONBOARDING "~40" tools.
  - `default_config.py`: marked reserved-but-not-yet-wired keys
    (`enable_regime`, `enable_factors`, `enable_threshold_gate`,
    `consensus_seeds`, `calibration_min_n`, `risk_stress_shock_pct_1/2`).
  Web (`TradingNew/trading_web`): `run_strategy_quality` now forwards `--illiq`
  (+ SPA checkbox). Tests: 1490 passed, 2 skipped; ruff clean repo-wide.

### Added
- **EODHD real-time snapshot + top movers (Massive 403 fallback)** - the
  Massive snapshot / top-movers endpoints are 403 on the free plan; EODHD's
  `/api/real-time` works on the EOD plan and now backs them:
  - `get_market_snapshot_eodhd(ticker)` - `/api/real-time/{ticker}`: live
    15-20 min delayed OHLCV + prev close + change% (the market analyst's
    "latest verified bar" + gap read).
  - `get_top_movers_eodhd(direction, count)` - `/api/real-time/{ticker}?ex=US`:
    one call returns ~18k US stocks sorted by change_p (gainers/losers +
    universe replacement).
  - `get_market_snapshot` / `get_top_movers` tools now fall back to EODHD
    when Massive returns an 'unavailable' string (403) or raises.
  - Fixed `_eodhd_get` error detection: a dict with a `code` field but no
    `message` is a normal payload (the real-time response's `code` is the
    ticker symbol), not an error.
  Tests: `test_eodhd_vendor.py` (7 new: snapshot render/no-data, movers
  sort/invalid/no-data, tool fallback x2) + `test_massive_vendor.py`
  failover updated (both-down degrades).
- **Truncation-retry enforcement (max_tokens is a ceiling, not a floor)** -
  when an LLM response is cut at the output cap (ends mid-sentence), the
  agent now re-invokes with a continuation prompt and merges, so reports are
  never truncated. Wired into every agent path:
  - `structured.py::_retry_if_truncated` (free-text fallback of PM/RM/trader/
    sentiment), `retry_chain_if_truncated` (market/news/fundamentals analyst
    tool-calling chains), `retry_llm_if_truncated` (bull/bear researchers +
    aggressive/conservative/neutral risk debators).
  - Up to 2 continuation attempts, each only when a cut was detected; a
    failed continuation degrades to the original text (never raises).
  - Tests: `tests/test_truncation_retry.py` (7).
- **Tool-wiring audit: 4 new market tools + run-level OHLCV cache + computed
  sentiment on** - the audit found strategy functions that were implemented
  but never exposed to the analyst LLMs, and duplicate OHLCV fetches across
  tools. Fixes:
  - `get_technical_factors(ticker)` (market) - ADX / pivots / Aroon / Fisher /
    Chaikin / Elder-Ray / Supertrend / volume-profile in ONE call.
  - `get_book_tail_risk(ticker, weights?)` (market) - portfolio CVaR +
    correlated -10% stress + drawdown gate (book-level tail).
  - `get_liquidation_days(ticker, shares_to_liquidate?)` (market) - days to
    absorb a block at a 15% participation cap.
  - `get_premarket_review(ticker, prior_close?, open_price?, prior_stop?,
    entry_price?)` (market) - deterministic CONFIRM / REVISE / REJECT arbiter.
  - Run-level OHLCV cache (`_RUN_OHLCV_CACHE` in analysis_tools.py): every
    tool shares ONE vendor fetch per (ticker, days) per run - no duplicate
    data / quota burn. Cleared in conftest between tests.
  - `enable_sentiment` now **True** (was False): the computed StockTwits
    score + surprise velocity is injected into the sentiment report (the
    sentiment functions existed but were never delivered).
  Tests: 8 new hermetic tool tests + cache test + market-toolnode guard.
- **Fix market tool-node binding gap + raise quick-tier output cap** -
  the market analyst's prompt lists `get_swing_exits` / `get_dip_technical` /
  `get_mean_reversion_tech` and the 5 market-session tools (`get_opening_range` /
  `get_gap_type` / `get_order_imbalance` / `get_premarket_liquidity` /
  `get_post_close_confirmation`), but they were never registered in the market
  `ToolNode` (a wiring gap from the original value-dip+swing commits) — so every
  run had the LLM call tools that error "not a valid tool" and the chandelier
  trail-stop wiring (`final_state["swing_exits"]`) was dead. All 8 are now bound
  (41 market tools). `max_output_tokens` / `max_output_tokens_quick` raised
  6000 → 8000 after 2026-08-27 WDC analyst reports truncated mid-sentence at
  the 6000 cap. Tests: `test_market_toolnode.py` regression guard (8 tools).
- **EODHD as primary OHLCV vendor + eodhd-us default universe** - the
  `core_stock_apis` chain is now `eodhd,moomoo,yfinance` (EODHD first,
  moomoo/yfinance as fallbacks); `news_data` is `eodhd,moomoo,yfinance` and
  `corporate_actions` is `eodhd,moomoo`. New EODHD endpoints on the EOD plan:
  `get_news_eodhd` (news), `get_corporate_actions_eodhd` (splits +
  dividends), `get_exchange_symbols_eodhd` (full US symbol list, ~18k common
  stocks). The value screener's default `--universe` is now `eodhd-us`
  (EODHD full-US list, no moomoo quota); `top-losers` / `heat-proxy` (moomoo
  movers) stay as the optional intraday-momentum source. Fundamentals /
  technicals / intraday / options are NOT on the EOD plan, so those chains
  keep moomoo/yfinance first. Tests: `test_eodhd_vendor.py` (14) +
  `test_value_screener.py` eodhd-us universe (1).
- **EODHD vendor (daily OHLCV)** - `dataflows/eodhd.py` serves daily bars as
  the same CSV shape yfinance/moomoo produce, registered in the
  `core_stock_apis` chain (`moomoo,eodhd,yfinance` by default) and as a
  `--vendor eodhd` preset (`batch.py`/`pipeline.py`). Key:
  `TRADINGAGENTS_EODHD_API_KEY` (in `.env`). Free tier 20 calls/day; the EOD
  plan ($19.99/mo) is 100k calls/day @ 1000/min with 30+ years history — a
  replacement for the moomoo K-line quota (100 calls/7 days) that the value
  screener exhausts. Tests: `tests/test_eodhd_vendor.py` (8).
- **Moomoo per-call timeout + value-dip gating pre-filter + web screener
  budget** - three fixes for the value-screener web timeouts:
  - `moomoo_call_timeout` (default 5.0s, env `TRADINGAGENTS_MOOMOO_CALL_TIMEOUT`):
    every moomoo SDK call now runs under a wall-clock timeout wrapper
    (`dataflows/moomoo.py::_sdk_call`) instead of the SDK's own 20s
    `ReqInfo.wait()`, so a degraded gateway can't burn 20s per call across
    hundreds of calls.
  - The value-dip gating pass runs a cheap OHLCV-only pre-filter
    (`scripts/value_screener.py::_value_dip_technical_prefilter` — RSI <= 35,
    %b <= 0.10, stop <= 2%) before the heavy fundamentals fetch, dropping the
    per-symbol vendor calls from ~7 to 1 for non-candidates.
  - The web `run_screener` capability budget is raised to 2400s (matching the
    action report's `--llm` budget) and a timed-out capability now kills its
    whole process tree (`taskkill /F /T`) so no orphaned process keeps a
    moomoo context / gateway connection open.
  Tests: `test_moomoo_vendor.py::MoomooSdkCallTimeoutTests` (5),
  `test_value_screener.py` prefilter (3), `test_backend.py` kill-tree (3).
- **Correlation-aware allocation wired into the allocation plan** -
  `portfolio.allocation_block` and the `get_allocation` analyst tool accept
  `returns_by_name` and, when `enable_correlation_penalty` is on (default
  False; `correlation_threshold` 0.6 / `correlation_penalty_frac` 0.3),
  down-weight names whose average pairwise correlation with the rest of the
  book exceeds the threshold before the per-name/per-sector caps. The
  screener's `--alloc` builds return series from the run's OHLCV cache and
  passes them through; names without a measurable series are never penalized.
  Env: `TRADINGAGENTS_ENABLE_CORRELATION_PENALTY` /
  `TRADINGAGENTS_CORRELATION_THRESHOLD` / `TRADINGAGENTS_CORRELATION_PENALTY_FRAC`.
  Tests: portfolio + analysis_tools + value_screener.
- **Industry-practice suggestions implemented (7 items)** -
  - Correlation-aware allocation: `portfolio.correlation_penalty` /
    `mean_correlation` down-weight names highly correlated with the book
    (risk-parity style).
  - Book-level stress: `book_risk.book_correlated_stress` shocks the whole
    basket together; surfaced in the risk snapshot + report risk-gate block.
  - Liquidity-aware costs: `exits.net_of_cost` / `evaluate.net_returns` accept
    an `illiq` (Amihud) param to scale cost for illiquid names.
  - Paper-ledger track record: `pre_market.ledger_track_record` measures the
    reviewer's win rate / avg realized return from resolved rows.
  - Limit-order directive: `pre_market_review.py` appends a thin-liquidity
    "prefer limit orders / reduce size" reason when the book is thin/illiquid.
  - Claim-vs-computed audit: `reporting.audit_decision_numbers` (opt-in via
    `enable_decision_audit` / `TRADINGAGENTS_ENABLE_DECISION_AUDIT`) flags a PM
    decision's Stop Loss far from the computed contract stop.
  - Strategy-quality report: `scripts/strategy_quality_report.py` reads the
    reflection + pre-market ledgers and reports net-of-cost Sharpe / drawdown /
    win rate (wired into the web raw allowlist).
  Tests: portfolio/book_risk/evaluate/pre_market/reporting/value_style.
  Full suite 1427 passed.

### Fixed
- **Moomoo exit-hang** - `dataflows/moomoo.py` had a shadowing duplicate
  `_close_all_ctxs()` (the atexit one called `ctx.close()` directly, which
  can block on the dead receive loop and keep the process alive after
  `main()` returns). Removed the duplicate; the daemon-thread + timeout
  version is the only one. Added `close_context()` to the end of
  `value_screener.py`, `action_report.py`, `capital_income_screener.py` and
  `pre_market_review.py` main() so the moomoo context closes while the
  process is healthy (the graph already did this). A screener run that
  previously hung ~15 min after writing its report (web job timed out) now
  exits cleanly. Regression test: `test_close_all_ctxs_uses_daemon_thread_timeout`.

### Added
- **Value-dip + swing + pre/post-market research implementation** -
  - `technical_factors.py`: 6 new pure factors - `aroon` (trend age),
    `fisher_transform` (normalized reversal), `chaikin_oscillator` (buying
    pressure), `elder_ray` (bull/bear power), `supertrend` (ATR trailing),
    `volume_profile` (POC + value area). All return None on insufficient data.
  - `market_session.py` (new): `opening_range` (ORB breakout + 2R stop/target),
    `gap_type` (common/breakaway/runaway/exhaustion + fill stats),
    `order_imbalance` (buy/sell-heavy from flow nets), `premarket_liquidity`
    (thin-book warning), `post_close_confirmation` (stopped-out/target-hit/hold).
  - 5 new market-analyst tools: `get_opening_range`, `get_gap_type`,
    `get_order_imbalance`, `get_premarket_liquidity`, `get_post_close_confirmation`
    (bound to the market analyst + prompt directives).
  - Screener columns: `Aroon`, `Fisher`, `Supertrend`, `POC` (volume profile).
  - Tests: `test_strategies_market_session.py` (30) + extended
    `test_strategies_technical_factors.py` (17 new).
- **Conditional action report** - `scripts/action_report.py` checks report
  verdicts against the risk basket (`TRADINGAGENTS_RISK_BASKET_WEIGHTS`):
  basket names are kept on their newest Underweight/Sell verdict (reduce/trim),
  non-basket names on their newest Overweight/Buy verdict (add). The report's
  stated condition (re-entry level, trim zone, scale-in confirmation) is
  extracted from Position Size + Executive Summary and checked against live
  OHLCV via the vendor chain — deterministic MET / NOT_MET / UNKNOWN, never
  fabricated. Stop/ATR levels are informational; unmeasurable qualifiers
  (PUC, VDU trigger, stabilization) render UNKNOWN. Optional `--llm` invokes
  a deep-think judge (`ActionConditionVerdict` schema +
  `overrides/action_condition_judge.py`) for UNKNOWN conditions. Output: a
  final action report (ADD/BUY, TRIM/REDUCE, MONITOR) printed + saved
  (keep-only-newest). Tests: `tests/test_action_report.py` (21).
- **Screener: full 11-SPDR sector ranking table** - `_sector_table_markdown`
  renders the whole sector ranking (ETF, name, 1m/3m returns, rank, top-3
  flags) and appends it to the report whenever the ranking is computed
  (`--sector-rank` / `--enrich-sector`). The watchlist previously showed only
  the candidate's SecRank column; now the reader sees the full table the
  framework's "top 3 of 11 SPDR groups" rule is based on. Rows without
  history render n/a and never rank top-3. Tests:
  `test_sector_table_markdown_renders_full_ranking` +
  `test_enrich_sector_populates_without_gating` (asserts the table appears).
- **Report truncation marker** - `reporting._finalize_section` appends a
  visible blockquote marker when a section ends mid-sentence (LLM max_tokens
  cut), so the reader knows the tail is missing at the LLM layer, not a file
  bug. Conservative heuristic: only bare lowercase/digit endings >= 120 chars
  that aren't sentence punctuation, markdown constructs, or bold-label lines
  (`**Consensus**: High`). Applied to every section file + the consolidated
  report. Tests: `test_truncation_marker_appended_to_mid_sentence_sections` +
  `test_finalize_section_roundtrip`.
- **Web: value-dip + swing tools page** - `trading_web` gains a `run_value_tools`
  capability (in-process, read-only) and a "Value tools" SPA page that runs
  `get_value_floors` / `get_swing_exits` / `get_dip_technical` /
  `get_mean_reversion_tech` for one ticker — the same computed numbers the
  analyst LLMs are bound to, inspectable before queueing a full run. Also
  fixed a pre-existing flaky web test: `security._secret()` read the secret
  file back with `.strip()`, which silently dropped a leading/trailing
  whitespace byte from the 32 random bytes and intermittently invalidated
  every session cookie (401s). Tests: `test_value_tools_capability_registered_and_guarded`
  + `test_secret_file_roundtrip_preserves_whitespace_bytes`.
- **Per-role max output tokens + density directives** -
  - Config: `max_output_tokens` (6000), `max_output_tokens_quick` (6000),
    `max_output_tokens_deep` (2500) + env overrides
    `TRADINGAGENTS_MAX_OUTPUT_TOKENS(_QUICK/_DEEP)`.
  - `openai_client._PASSTHROUGH_KWARGS` now forwards `max_tokens` (OpenAI /
    OpenRouter); Anthropic / Bedrock already did. `trading_graph` passes the
    per-tier value (quick vs deep) to each client.
  - `get_output_budget(section)` in `agent_utils`: per-role prompt directive
    (dense, bounded ~250-1400 words by role; tool-call-first: never approximate
    a number that a tool can return). Wired into all 12 agent prompts
    (4 analysts, bull/bear, 3 risk debators, RM, PM, trader).
  - Values grounded in your formula `min(1,048,576, 1,310,720 - input)` +
    measured per-role report maxes (analysts ~5k, RM 1.9k, trader .7k, PM 1.4k).
  Tests: `test_openai_compatible_provider` (max_tokens passthrough + budget
  helper). Docs: api_reference env table, .env.example, README, CHANGELOG.
- **OpenRouter provider-ignore routing** - `TRADINGAGENTS_OPENROUTER_IGNORE_PROVIDERS`
  (.env, comma-separated provider slugs) lets you block slow/unreliable
  OpenRouter endpoints for every request. The list is sent as `provider.ignore`
  in the OpenRouter Chat-Completions body via `extra_body` (nested under the
  `provider` key, per OpenRouter's provider-routing docs). Applied only when
  `llm_provider=openrouter` and the list is non-empty; erased if empty.
  `default_config._ENV_OVERRIDES` coerces the CSV string to a list; default `[]`.
  Tests: `test_openai_compatible_provider` (3: payload present, empty omitted,
  non-openrouter ignored). Docs: api_reference env table, README, CHANGELOG.
- **Free computed ratios (no paid Massive plan)** - `strategies/ratios.py`
  replicates the plan-gated Massive `get_ratios` block from the project's own
  canonical statements: EV, EV/EBIT, EV/EBITDA, EV/Sales, P/E, P/B, P/S,
  P/CF, P/FCF, ROE, ROA, D/E, Current, Quick, cash ratio, dividend yield, FCF,
  market cap. Exposed as `get_ratios` on the fundamentals analyst (computed =
  free; missing inputs render n/a, never fabricated). Adds the `inventory`
  canonical alias so Quick ratio computes. Also fixes a latent double-`@tool`
  decorator bug in `analysis_tools.py` that broke import once the file grew.
  Tests: `test_strategies_ratios` (6 pure) + `test_analysis_tools` (2 tool).
  Docs: api_reference 6.4, developer/04, tests-layout.
- **SEC EDGAR -> Massive insider fallback** - `get_sec_filings` (`agents/utils/
  market_position_tools.py`) now falls back to Massive's `get_form4_insider_massive`
  (Form 4 open-market insider transactions) whenever official SEC EDGAR is
  unavailable: HTTP 403 from SEC fair-access throttling, network failure, or a
  non-US ticker with no EDGAR record (which previously surfaced as
  `NO_DATA_AVAILABLE` / a raised error and degraded the signal). The fallback
  text is explicitly labelled "Massive insider-activity fallback (Form 4 — NOT
  the 8-K/10-K/S-1 set)" so the agent never confuses the datasets; if Massive
  also returns nothing it degrades to an explicit unavailable message (no
  fabrication). Bound to the news analyst's `get_sec_filings` tool + prompt.
  Tests: `test_market_toolnode` (5 fallback cases: EDGAR ok, raise-on-403,
  no-data sentinel, insider body, both-down degrade). Docs: api_reference
  §6.2, data-providers, README, AGENT_ONBOARDING.

- **Web UI (sibling project, not in this repo)** - `TradingNew/trading_web/`
  adds a React SPA + FastAPI web front-end over every TradingAgents capability
  (batch / pipeline / screener / pre-market / nightly / decision-history /
  report viewer / raw read-only), with security-first auth: scrypt password
  hashes, HMAC-SHA256-signed session cookies, CSRF double-submit, login
  lockout, strict path defense on report reads, an allowlisted raw-command
  shell, CSP + security headers, and a JSONL audit log. Serves the SPA from
  the FastAPI backend; 127.0.0.1:8000 by default with `TRADINGAGENTS_WEB_*`
  overrides for a later public deployment. See
  `TradingNew/trading_web/README.md` (not tracked by this repo, per the
  layout rule).

- **Pre-market review (overnight reviewer)** - closes the gap between a
  close-time decision and the next open (design `docs/pre_market_review.md`,
  choice (a)):
  - `strategies/pre_market.py` - deterministic deltas + verdict arbiter:
    `premarket_gap` (gap % / ATR, through-stop / adverse-fill detection),
    `catalyst_window_read` (B1 hard-block / window tighten),
    `reanchor_plan` (tranche re-anchor with per-trade + book caps),
    `review_decision` (CONFIRM / REVISE / REJECT from measured deltas only),
    `load_prior_state` (fail-open loader for `full_states_log_*.json` +
    `5_portfolio/decision.md`).
  - `PreMarketVerdict` schema + `agents/overrides/pre_market_reviewer.py` - a
    deep-think prompt variant (reuses the PM's LLM; no new graph node) that reads
    the prior decision + a number-only deltas summary and emits a structured
    verdict; the deterministic REJECT is never downgraded by the LLM.
  - `scripts/pre_market_review.py` - standalone pre-open path (gap/anchor),
    default = newest report folder, `--prior-date` / `--report-dir` overrides,
    `--skip-llm` (deterministic only) / `--dry-run`.
  - `batch.py` - opt-in same-night step (`enable_pre_market_review`): after each
    symbol's report, a catalyst/quality re-check writes `pre_market_review_<date>.md`
    next to the report; never fails the symbol.
  Config: `enable_pre_market_review` (+ `TRADINGAGENTS_ENABLE_PRE_MARKET_REVIEW`).
  Tests: `test_strategies_pre_market` (pure, 19) + `test_pre_market_review`
  (script + batch, 3). Docs: `docs/pre_market_review.md` status -> implemented.
- **Pre-market review follow-up: defect fixes + 6 features** -
  - Fix 1: the standalone script now extracts the prior plan's entry/stop
    (`parse_planned_levels`) and re-anchors the tranche plan to the measured
    open, so the gap / through-stop / adverse-fill / cap-breach checks in
    `review_decision` actually run (previously the stand-alone passed no
    `prior_stop`/`reanchor` and degenerated to catalyst-only).
  - Fix 2: `batch._batch_pre_market_check` passes `results_dir`, so the
    same-night step finds the full state JSON (not just `decision.md`).
  - Fix 4 (+ feature 1): `_fetch_deltas` prefers a real-time pre-market price
    (Alpaca `get_intraday` when `enable_alpaca`, else yfinance
    `fast_info.last_price`) over the daily close, and adds ATR(14).
  - Feature 2: `scripts/nightly_review.py` drives pre-open reviews from the
    latest `reports/batch_summary_*.jsonl`.
  - Feature 3: paper-book ledger (`data_cache_dir/pre_market_ledger.jsonl`)
    via `record_review` / `resolve_ledger` (pending -> realized return).
  - Feature 4: `scripts/decision_history.py` prints a per-ticker decision
    series from the per-date `full_states_log_*.json` files.
  - Feature 5: guarded overnight-headline context (`_headline_delta`) into the
    reviewer summary (never a hard gate, titles only).
  - Feature 6: scheduler notes (cron / Task Scheduler) in
    `docs/pre_market_review.md` §15.
  Tests: `test_strategies_pre_market` + `test_pre_market_review` extended
  (planned-levels parse, results_dir lookup, headline delta, decision history,
  nightly driver). Full suite green; ruff clean.

### Added

- **Capital-income screener: live `--universe preferred-top` + `--refresh`** -
  the free providers don't expose a validated 500-symbol preferred list, so
  the standalone screener now seeds its universe at runtime from the top
  holdings of the major preferred ETFs (PFF / PFFD / PGF / PGX / PFFV) via
  yfinance `get_funds_data().top_holdings` (no key). Every candidate is
  validated during the run (price + dividendRate); only names that resolve
  are ranked. `--refresh` writes the validated set back to the universe file
  (header preserved), so the curated list stays current without manual edits.
  Tests: `test_capital_income_screener` (universe mode + refresh write-back).
  Full suite 1311 passed / 2 skipped; ruff clean.

- **Standalone preferred-income screener (Strategies/capital_income.md)** -
  a new self-contained screener that does NOT wire into the trading graph or
  any agent. Implements the Global X U.S. High Yield Preferred Index
  methodology: (1) liquidity/quality screen (market cap >= $250M AND 3m ADTV
  >= $1M), (2) indicated-dividend-yield ranking (annualized dividend / price,
  top 50), (3) MV weighting (or equal-weight fallback when per-issue shares
  aren't exposed - preferreds report no per-issue market cap) with the 3% cap
  + pro-rata renormalization.
  - `strategies/capital_income.py` - pure math (annualized dividend, indicated
    yield, ADTV dollar, liquidity gate, top-N, MV/equal weights, cap +
    renormalize). No-fabrication: None on missing input.
  - `scripts/capital_income_screener.py` - standalone CLI (positional/--file
    universe, --top, --min-mcap, --min-adtv, --out-dir, --dry-run, --json);
    pulls price + dividendRate + market cap + OHLCV via yfinance + the vendor
    chain. Uses `info.dividendRate` (pre-annualized) - never the trailing-12m
    sum, which preferreds pollute with special distributions.
  - `Strategies/preferred_universe.txt` - seeded ~24 liquid US preferreds
    (hyphenated Yahoo symbols that resolve with a dividendRate).
  Tests: `test_strategies_capital_income` (10 pure) + `test_capital_income_screener`
  (5 hermetic, mocked yfinance/OHLCV, asserts no graph/agent imports). Full
  suite green; ruff clean.

- **Liquidity gate on by default + surfaced in PM prompt & risk report** -
  `TRADINGAGENTS_ENABLE_LIQUIDITY_GATE=1` is set in `.env` (on by default), so
  the risk governor now REJECTs ILLIQUID names / WARNs on CAUTION ones using
  the risk2.md metrics. The computed liquidity block is surfaced in two places:
  - the **Portfolio Manager prompt** - a `Computed liquidity` line (verdict +
    ILLIQ + float-turnover + IWF + reasons) grounds the PM's liquidity/sizing
    language and instructs scaling size down (or to 0%) on CAUTION/ILLIQUID;
  - the **risk report** (`Risk Gate (computed)` block) - shows `Liquidity
    verdict` + ILLIQ / float-turnover / IWF + reasons when the gate computed it.
  Both degrade gracefully (no line) when the gate didn't run or had no data.
  Tests: `test_reporting` (liquidity block render + PM prompt wiring). Full
  suite 1291 passed / 2 skipped; ruff clean.

- **Liquidity & ownership risk (Strategies/risk2.md)** - implements the five
  institutional risk metrics as a pure, offline module
  (`strategies/liquidity_risk.py`): free-float factor (IWF), float turnover
  (ADV / float), Amihud ILLIQ (price impact per $ traded), days-to-absorb
  (overhang), and ownership HHI (concentration), plus a composite
  LIQUID / CAUTION / ILLIQUID verdict. No-fabrication: every metric returns
  None on missing input.
  - **Risk governor gate (opt-in)**: `govern()` accepts a liquidity verdict;
    ILLIQUID REJECTs, CAUTION WARNs. Enabled via `enable_liquidity_gate`
    (default False - preserves current behavior); the graph computes the
    verdict from vendor OHLCV + float + shares when on.
  - **Analyst tools**: `get_liquidity_risk` (market analyst) and
    `get_ownership_concentration` (fundamentals analyst, HHI best-effort -
    n/a when no per-holder breakdown) + prompt directives.
  - **Screener columns**: `ILLIQ` / `FltTurn` / `IWF` added to the report
    (pure-calculable from OHLCV + float + shares) + legend entries.
  Tests: `test_strategies_liquidity` (16 pure), governor liquidity cases,
  tool cases. Full suite green; ruff clean.

- **Screener: fill the n/a columns (compute + enrich)** - most columns were
  blank because they were gated behind a scan mode or a CLI flag, not because
  the data was missing:
  - **Piotroski F-Score now computes** - added `enrich_screen_ratios` in
    `statement_parsing` which derives the ratio inputs no vendor row provides
    directly (`roa`, `leverage`, `current_ratio`, `gross_margin`,
    `asset_turnover`, `shares_issued`, with prior periods) from the canonical
    statements the chain already fetches, so the F column (previously always
    `n/a`) computes from the moomoo data (- in a live AAPL run F=7, was n/a).
  - **`--scan all` now fills every technical column** - a new
    `_compute_scan_row` helper runs all scan buckets (TrendPB/Breakout/RSI +
    momentum `Pills/Pull/RR` + `Swing/RS/Stp/T2` + `VCP/Brk` +
    `VDip/FCFy/RSI/%b/Stp%`) for every symbol on the default `all` mode, so a
    standard positional run shows these columns instead of `n/a`. Added shared
    run-wide OHLCV/float/benchmark caches (reset per run) so the movers
    gating and the results loop fetch each symbol's OHLCV once. Dedicated
    `--scan <mode>` still filters (now also honoured on the positional path).
  - **New non-gating enrich flags** - `--enrich-sector`, `--enrich-rev`,
    `--enrich-inst` populate `Sec/SecRank`, `RevUp` and `Inst` without the
    filtering that `--sector-rank` / `--revision` / `--inst-accum` apply.
  - `Name` stays mover-metadata-only (classic path shows `n/a`) and
    `L1Px/VWAP1m/1mVol` stay behind `--intraday` (Alpaca cost) by design.
  Tests: F-score derivation, a positional `--scan all` that populates the
  technical columns, and `--enrich-sector` without gating. Full suite 1265
  passed / 2 skipped; ruff clean.

- **Screener FMP 429 rate-limit noise - normalized enrichment now uses the
  vendor chain** - the value screener's ``normalized_score()`` enrichment
  (columns ``nebit_ev_ebit`` / ``pe_pct5`` / ``fmp_ev``) fetched multi-year
  income + enterprise-values straight from FMP, so on the free tier it
  logged ``fmp income-statement: status 429`` / ``fmp enterprise-values:
  status 429`` warnings every run and blanked those columns. ``income_series``
  (new in ``statement_parsing``) now extracts 2+ annual
  ``{year, revenue, ebit, net_income}`` rows from the income statement the
  vendor chain already returns (moomoo markdown period tables or yfinance
  CSV), and ``normalized_score`` computes NEBIT / EV / EV-NEBIT from that +
  canonical fundamentals (market cap, debt, cash), reconstructing the 5y
  P/E percentile best-effort from historical closes x current shares. FMP is
  now only a last-resort fallback when the vendor chain has no income history
  AND an FMP key is set. No more 429s on the default moomoo,yfinance chain;
  the columns compute offline. Tests: `test_fmp` (vendor-chain normalized
  score, fmp_get never called on the default path, no-income degrade, CSV
  income series), `test_statement_parsing` (markdown + CSV income_series).
  Live: AAPL -> ev_nebit 33.96 / pe_pct5 0.75 with no FMP key.

- **Yahoo can't resolve moomoo's dotted US share-class symbols** - moomoo's
  US movers rank returns dotted share classes (`PBR.A`, `MOG.A`, `MOG.B`) but
  Yahoo only resolves the hyphen form (`PBR-A`, `MOG-A`, `MOG-B`, `BRK-B`), so
  yfinance (the second vendor in the default `core_stock_apis=moomoo,yfinance`
  chain) degraded those symbols to "Quote not found / possibly delisted" when
  moomoo couldn't serve them. `normalize_symbol` now converts a dotted
  single-letter US share-class suffix (`.A`/`.B`/`.C`/`.D`/`.K`...) to the
  Yahoo hyphen form, while leaving the `.L` London exchange and all multi-letter
  exchange suffixes (`.SA` Brazil, `.TO`, `.AX`, `.HK`, `.NS`, `.BO`, ...) untouched.
  Because moomoo's `_moomoo_code` doesn't use `normalize_symbol`, moomoo still
  receives the raw dotted form it understands (its own origin format), and the
  yfinance-facing paths hyphenate locally - so both vendors resolve. Also fixes
  manually-typed `BRK.B`/`BF.B` and the graph's `_fetch_cached_history` for
  dotted US share classes.
  Tests: `test_symbol_utils` (share-class dot->hyphen, idempotent hyphen,
  London/multi-letter exchange suffixes kept, plain/US futures unchanged).
  Verified live: `get_stock_data` now returns rows for MOG.A/PBR.A/MOG.B
  through the default chain (was empty). See docs/api_reference §5 symbol table.

- **Installed-CLI import bug: analyst tools could not find `scripts/`** -
  the agent analysis tools imported the vendor-output -> canonical parsing
  helpers from `scripts.value_screener`, but the installed `tradingagents` CLI
  wheel ships only `tradingagents*` and `cli*` (no `scripts/` on `sys.path`),
  so every DCF / fcf-yield / z-score / ratios / earnings-quality call degraded
  to `No module named 'scripts.value_screener'` (DCF) or a bare
  "unavailable ... from the vendor chain". The parsing layer moved to
  `tradingagents/dataflows/statement_parsing.py` (pure parsers + canonical
  aliases + `fetch_ticker`/`screen_ticker`), `scripts/value_screener.py`
  re-exports the same names (backend CLI + tests unchanged), and all 14 tool
  import sites now load from the package module. In a real NVDA run the three
  symptoms became: DCF returns a fair value (WACC from Beta, shares from
  market cap/close), fcf-yield returns a computed yield band, z-score compute
  from 4 real moomoo periods.
- **DCF tool: moomoo-markdown cashflow support** - `_dcf_fcf_series` only
  parsed yfinance-style CSV rows, so with moomoo (the default first vendor)
  serving `get_cashflow` the DCF degraded to "no usable free cash flow"
  series. It now parses moomoo per-period markdown tables too (Free Cash Flow
  row, else OCF - capex, positive-only, chronological), falling back to the
  CSV parser.
- **DCF market-cap / beta / shares resolution** - `get_dcf_valuation` now
  resolves the financial background with the screener-grade `fetch_ticker`
  (fundamentals + balance sheet + income + finnhub gap-fill) instead of a
  single raw `get_fundamentals` call, so market cap / shares resolve even
  when moomoo's statements have no "Market Cap" row; new canonical aliases
  `beta` and `shares` (shares outstanding / diluted / weighted-average) mean
  provider betas are no longer silently dropped to 1.0.
  Tests: `tests/test_statement_parsing.py` (new; imports + parsers + aliases
  + scripts re-export parity), moomoo-markdown DCF case in
  `test_analysis_tools`, hermetic-router updates across the screener/growth/
  scan/v2-v5/alpaca suites (patch `statement_parsing.route_to_vendor`
  alongside `scripts.value_screener`). Full suite 1250 passed / 2 skipped;
  ruff clean.

- **Blank-symbol yfinance hardening** - a whitespace/empty ticker reaching a
  yfinance entry point (e.g. a malformed LLM tool call during
  `batch.py --symbols ...`) used to canonicalize through `normalize_symbol`
  unchanged (`' '` stayed `' '`), hit `yf.Ticker(' ')`, and leak
  `TypeError: 'NoneType' object does not support item assignment` plus noisy
  yfinance HTTP-404/400 ERROR logs. `normalize_symbol` now canonicalizes
  blank/whitespace to `""`, and a new `require_symbol` helper raises the
  typed `NoMarketDataError` (`detail="blank/empty ticker symbol"`) at every
  yfinance entry point (`y_finance` statements/stock/insider,
  `stockstats_utils.load_ohlcv`, `yfinance_options`, `yfinance_short_interest`,
  `yfinance_news`) plus the graph's `_fetch_cached_history`. The router now
  returns one clean `NO_DATA_AVAILABLE: ... blank ticker ...` sentinel the
  agents can report honestly instead of a raw TypeError. Tests:
  `test_symbol_utils` (blank canonicalization + `require_symbol` raises),
  `test_vendor_routing` (blank -> sentinel across the chain).

### Added

- **Value Dip Step-1/Step-2 gap strategies** - five more deterministic
  calculators in `tradingagents/strategies/value_dip.py` close the original
  doc's gaps (`Strategies/Value_Dip_swing.md`):
  - **balance_sheet_health** - D/E < 1.0 OR current ratio > 1.5 (§1 gate),
  - **profitability_quality** - positive FCF AND ROE > 15% (§1 gate),
  - **Step-2 technical ladder** - `macd_divergence` (Daily RSI-14 / MACD-
    histogram bullish divergence or higher-low), `volume_dry_up` (VDU near
    support), `trigger_candle` (RVOL >= 1.3x + close above prior high /
    engulfing), `higher_low_structure`, composed by `vdu_entry_setup`,
  - **support_structure** - multi-month consolidation base low / 200-day SMA
    proximity (200+ closes),
  - **decline_driver_check** - the negative-force screen (clean / caution /
    structural) proxying moat/regulatory red flags with measurable signals
    (trap-HIGH, Sloan accruals > 6%, negative 12-1m momentum, non-positive
    FCF/ROE, severe EPS decline) - a `structural` verdict rejects the dip.
  Exposed as five new analyst `@tool`s: `get_macd_divergence` /
  `get_vdu_entry_setup` / `get_support_structure` (market), `get_balance_sheet_
  health` / `get_decline_driver_check` (fundamentals). `value_dip_setup` and
  the `--scan value-dip` screener now gate on balance-sheet + profitability
  when measured (unknown rows ignored, repo convention). Hermetic tests:
  `test_strategies_value_dip` (new gap cases) + `test_analysis_tools` (5
  tool cases).

- **Tranche risk fold for the risk governor** - the Value Dip + Swing tranche
  plan is now a *control* computation, not just a planning one:
  `strategies/value_dip.py::tranche_risk_read` derives the worst-case measures
  from the measured close (P1) + config-frozen weights / stop multiple / risk
  budget / account (never the LLM), and the governor enforces:
  - **peak-deployed-at-scale-in** (sum of per-tranche capital at full scale-in,
    typically > risk budget because capital is added near the lows) against the
    per-trade cap - the missing check neither the standalone tool nor the
    single-entry governor performed;
  - **capital-at-risk** (sum of per-tranche losses at the hard stop, == the
    risk budget by construction) via `govern()`'s new
    `capital_at_risk_pct`/`risk_cap_pct` check;
  - `build_position_contract` accepts an `entry_price` hook (the weighted
    tranche entry) so the G1 dollar stop/risk matches the tranche execution;
  - the report's `Risk Gate (computed)` block shows `Tranche peak-deployed` /
    `Tranche capital-at-risk` (+ cap-ok) when the fold ran.
  Config: `enable_tranche_risk` (default False), `tranche_weights`,
  `tranche_stop_mult`, `tranche_risk_pct`, `tranche_account` +
  `TRADINGAGENTS_*` env overrides. Tests: `test_strategies_risk_governor` (5),
  `test_strategies_contract` (2), `test_strategies_value_dip` (graph wiring,
  4 + pure 5), `test_reporting` (1).

- **Value Dip + Swing hybrid** - new `tradingagents/strategies/value_dip.py`
  implements the missing calculations from `Strategies/Value_Dip_swing.md` +
  `Value_Dip_swing_Continue.md`: Bollinger %b, historical valuation Z-score
  (vs own trailing P/E / EV/EBITDA / P/FCF), FCF yield, breakeven win rate /
  per-trade expectancy, the 3-tranche scale-in plan (P1/P2/P3 at 1.0/2.0 ATR,
  weighted avg entry, composite stop P3-1.5ATR, capital-at-risk check, 1.8R /
  3.0R targets + blended R:R), and the hybrid allocation matrix
  (`value_dip_setup`). Exposed as six analyst `@tool`s
  (`get_bollinger_pct_b` / `get_tranche_plan` / `get_trade_expectancy` on the
  market node; `get_fcf_yield` / `get_valuation_z_score` / `get_value_dip_setup`
  on the fundamentals node) and as a new `--scan value-dip` screener mode
  (`VDip` / `FCFy` / `RSI` / `%b` / `Stp%` columns). Config: `enable_value_dip`
  (+ `TRADINGAGENTS_ENABLE_VALUE_DIP`). Hermetic tests:
  `tests/test_strategies_value_dip.py` + `tests/test_analysis_tools.py`
  (value-dip cases).

- **Risk basket cash-remainder semantics** - `book_risk.portfolio_cvar` now
  treats a weight sum `< 1.0` as "weights + implicit zero-return cash": the raw
  weights are used (not renormalized), so the mixed daily series is scaled by
  the invested fraction and the portfolio CVaR is diluted by the cash sleeve.
  Weights summing `> 1.0` are still clamped to a valid portfolio. This is what
  makes "include cash as overall portfolio" (e.g. `risk_basket_weights` summing
  to ~0.68 with the rest in SPAXX/cash) actually lower the gate's tail budget.
  Tests: `test_strategies_book_risk` (2: sub-unity dilution + over-allocated
  clamp).

- **Risk Gate renders both CVaRs (analyzed-name + book)** - when a risk basket
  is configured, the report's `Risk Gate (computed)` (and compact verdict mode)
  now shows `Analyzed-name CVaR` (the analyzed ticker's own daily tail) next to
  `Portfolio (book) CVaR — this fed the gate` (the weighted-basket CVaR that is
  actually compared to the budget). The same comparison is computed-injected
  into the Portfolio Manager prompt as `**Computed daily-tail CVaR**`, so the PM
  grounds tail-risk/sizing language in these numbers (no `risk_context` on the
  state → the PM line is omitted, keeping old prompts unchanged). The graph
  writes `final_state["risk_context"] = {single_cvar, book_cvar}` when the
  governor runs. Tests: `test_reporting` (2: both-CVaR block + no-basket
  single-only), `test_structured_agent_prompts` (2: PM prompt injects both,
  omits when absent).

- **True portfolio CVaR for the risk governor (R2)** - the governor's daily-era
  tail budget now uses the *weighted basket's* historical CVaR when configured:
  new config keys `risk_basket_tickers` (list) + `risk_basket_weights` (dict,
  optional) + `TRADINGAGENTS_RISK_BASKET_TICKERS` / `TRADINGAGENTS_RISK_BASKET_WEIGHTS`
  env overrides. `book_risk.portfolio_cvar()` mixes each name's daily log-return
  series (aligned by index, weights normalized) and takes the historical CVaR of
  the weighted book, replacing the single analyzed name's series. Falls back to
  the single-name behavior when the basket is unconfigured or unresolvable (`>2`
  names with `>=5` aligned returns). Env coercion now handles list/dict values
  (comma-split / `k=v` pairs / JSON). Tests: `test_strategies_book_risk` (3),
  `test_env_overrides` (4), `test_strategies_catalyst` (1).

- **Session-discipline & earnings-quality analyst tools** - two more
deterministic strategies exposed as `@tool`s so the analysts cite computed
numbers instead of guessing: `get_session_discipline` (market node; wraps
`momentum.session_flags` + `psych_level` + `past_optimal_window` into an
intraday walk-away read: giveback, max-daily-loss, past the 10:00 ET optimal
window) and `get_earnings_quality` (fundamentals node; wraps
`normalized.accruals_ratio` + `trap_verdict`, surfacing the Sloan accruals
ratio - which `scripts/value_screener.screen_ticker`'s own trap call drops - as
an evidence trigger). Both bound in `_create_tool_nodes` + their analyst's
tool list/prompt, re-exported from `agent_utils`, and hermetic-tested in
  `tests/test_analysis_tools.py` (6 cases). Docs: `api_reference.md` §6.1/6.4
(tool list + table rows), README, CHANGELOG.

- **Docs backfill (missing env keys)** - documented the two `TRADINGAGENTS_*`
  env overrides (`ENABLE_MASSIVE_FLAT`, `MASSIVE_FLAT_DIR`) that were in code
  but absent from `api_reference.md` §1.1's env→config table; synced
  `.env.example` for `TRADINGAGENTS_MASSIVE_API_KEY` and the runtime toggles
  `TRADINGAGENTS_DISABLE_REDDIT` / `TRADINGAGENTS_MOMENTUM_OFFLINE` /
  `TRADINGAGENTS_MOMENTUM_NO_INTRADAY`.

- **Per-test timers (pytest-timeout)** - every test now carries a deadline so
  a hung vendor/network call can never block the whole session indefinitely:
  global 180s per-test default (thread method) + 30-minute session cap in
  `[tool.pytest.ini_options]`, and a 600s module-level `pytestmark` override
  for the modules that legitimately run live vendor calls end-to-end
  (`test_value_screener`, `test_scan_strategies`, `test_growth_screens`,
  `test_structured_agents`; 12-62s/test measured). `pytest-timeout>=2.4` added
  to the `[dev]` extra. Docs: `docs/developer/10-tests-layout.md`.

- **Credit-stress read (FRED ICE BofA OAS)** - `strategies/credit_spread.py`
  (`credit_stress_level`) plus a `get_credit_spread_read(date)` tool bound to
  the market analyst: pulls the three ICE BofA US high-yield option-adjusted
  spreads from FRED (`hy_oas`=BAMLH0A0HYM2, `ccc_oas`=BAMLH0A3HYC,
  `bb_oas`=BAMLH0A1HYBB, new aliases in `dataflows/fred.py::MACRO_SERIES`)
  and flattens them into a deterministic credit-cycle band (low/moderate/
  high/severe) + a 0..1 de-risk scale. Thresholds follow the credit-cycle
  table: HY <3% low / 3.5-4.5% moderate / >5.5% severe; CCC <8% low /
  10-12% moderate / >15% severe. The CCC spread is the leading risk-off
  sentinel. Degrades to an explicit 'unavailable' when FRED_API_KEY is unset
  (no-fabrication). Tests: `tests/test_strategies_credit_spread.py` (7),
  `tests/test_fred.py` (1), `tests/test_analysis_tools.py` (3).

- **Second decision-tool batch (sector/quality/safety/composite/tail)** -
  five more deterministic `strategies/*` functions exposed as analyst
  `@tool`s — `get_sector_rank` (11-SPDR 1m/3m momentum ranking + the
  ticker's sector standing; market node), `get_strategy_quality` (net CAGR,
  annualized vol, Sharpe, max drawdown over the price-derived or provided
  return series; market), `get_margin_of_safety` ((intrinsic - price)/
  intrinsic band, wide/modest/negative; fundamentals), `get_composite_rank`
  (cross-sectional value+momentum composite percentile vs industry peers;
  fundamentals), `get_tail_risk` (historical VaR/CVaR tail budget + -10%
  uniform stress loss; market). Each wraps an existing deterministic
  function, is bound to the market / fundamentals tool nodes and analyst
  prompts, and is hermetic-tested in `tests/test_analysis_tools.py` (12 new
  cases). No config or topology change; all degrade to an explicit
  'unavailable' per the no-fabrication contract.

- **DCF valuation tool** - `strategies/dcf.py` (pragmatic FCF-DCF: WACC via
  CAPM, Gordon terminal value, EV-to-equity bridge) + `get_dcf_valuation`
  tool bound to the fundamentals analyst. Provider-sourced inputs: free cash
  flow (from the cashflow statement chain), 10y Treasury (risk-free), beta,
  shares/cash/debt. growth/ERP are analyst overrides; degrades to
  "unavailable" when there is no usable FCF. Based on
  `Strategies/Discounted_Cash_Flow.md`. Tests in
  `tests/test_strategies_dcf.py` (8) + `tests/test_analysis_tools.py` (2).

- **Massive no-data failover fix** - the direct Massive tool wrappers
  (`get_short_volume`, `get_market_snapshot`, `get_top_movers`,
  `get_massive_news`) now catch `NoMarketDataError` and return an explicit
  "unavailable" string instead of letting the exception abort the analyst node
  and fail the whole batch symbol. Fallback to moomoo/yfinance now happens
  inside the report instead of crashing the run. Regression tests in
  `tests/test_massive_vendor.py::MassiveFailoverTests` (8).

- **Data providers doc (`docs/developer/12-data-providers.md`)** - catalogs
  all **13 data providers** the project uses: the 8 routed vendors
  (`yfinance, fred, polymarket, alpha_vantage, finnhub, sec_edgar, moomoo,
  massive`) plus 5 direct sources (Alpaca, FMP, Reddit, StockTwits,
  float_shares), with per-category `data_vendors` chains, Massive sub-modules,
  and API-key gates.

- **Agent decision-tools (implemented)** - `docs/developer/11-agent-decision-tools.md`
  audits the strategy + dataflow surface and lands six decision-grounding
  `@tool`s the analyst LLMs now cite: `get_exit_check` (stop/target/action),
  `get_allocation` (cap-respecting book), `get_regime_components`
  (vol/trend/chop regime breakdown), `get_consensus` (rating agreement;
  also computed-injected into the PM prompt), `get_momentum_detail`
  (pillars/rvol/vwap/first-pullback), and `get_beat_miss_sizing` (event
  multiplier). Each wraps an existing deterministic `strategies/*` function,
  is bound to the market / fundamentals / news tool nodes (and the PM's
  computed-consensus logic), with hermetic tests in
  `tests/test_analysis_tools.py`. No topology change; the PM keeps its
  NO_EXTERNAL_TOOLS single-structured-call design.

- **Strategies index (`Strategies/index.md`)** - navigation map linking each
  strategy plan doc under `Strategies/` (Math, value_strategy, framework, scan,
  momentum, risk/decision-hardening, enhancement_plan, alpaca_data_analysis) to
  its implementation modules, config gates, scan modes, and consumers. Linked
  from `docs/developer/04-strategies.md` and `docs/api_reference.md` §10.

- **Developer docs set (`docs/developer/`)** - 11 focused guides covering the
  whole project for a joining developer: topology (01), graph topology + run
  (02/02-01), dataflow+vendors (03), strategies (04), agents+tools (05),
  entrypoints (06), persistence (07), development guide (08), Massive
  integration (09), tests layout (10). Linked from `docs/api_reference.md` §10.

- **Massive Flat-File validator** - `scripts/validate_massive_flat.py`
  parses a day-aggregates CSV dropped in the flat folder and reports
  per-ticker close counts, date ranges and usability (>=15 rows) via the
  screener's exact `ohlcv_for_ticker_dir` lookup, so you confirm a genuine
  Massive file (needs Stocks Starter+) before enabling the bulk import.
  Hermetic test in `tests/test_massive_flat_noi.py`.

- **Massive Flat-File screener seam + live run** - the value-screener's
  `_fetch_ohlcv` now reads a configured Massive Flat-File day-aggregates CSV
  first from a Massive day-aggregates folder (`TRADINGAGENTS_MASSIVE_FLAT_DIR`, default `data/massive_flat`) when `enable_massive_flat` is ON (default OFF) for bulk
  ATR / ATR-pct / scan bases, falling back to the per-ticker vendor chain
  otherwise (opt-in, >=15-row gate). Hermetic test in
  `tests/test_massive_flat_noi.py`. A live end-to-end `batch.py` run to AAPL
  (Underweight) validated the new Massive tools end-to-end (see
  `docs/massive_integration.md` §3e).

- **Massive corporate actions, peers & IPOs (row 5)** - `get_company_peers`
  gains a `massive` option (`get_related_companies_massive`, finnhub-format-
  compatible output); `get_dividends_massive` + `get_splits_massive` are
  combined by `get_corporate_actions_massive` registered in the
  `corporate_actions` category; dedicated `get_dividends` (fundamentals
  analyst) and `get_ipos` (news analyst, IPO reference) tools. All row-5
  endpoints are **entitled on the current tier** (probed 200) so these are
  working enrichments, not plan stubs. Tests in `tests/test_massive_vendor.py`.
  Docs: `docs/massive_integration.md` §3f.

- **Massive NOI + Flat Files (item 8)** - `massive_noi.py` is a WebSocket
  Net Order Imbalance streamer (`build_url`/`parse_frame`/`describe`/
  `stream_noi`) wired to `scripts/massive_noi_monitor.py`; `massive_flat.py`
  loads bulk Flat-File day-aggregates into per-ticker OHLCV for the
  value-screener/backtests. Both are **standalone plan-gated utilities**, not
  batch-graph `@tool`s: NOI is a live stream (Imbalances Expansion add-on),
  Flat Files are bulk S3 (Stocks Starter+). Offline tests in
  `tests/test_massive_flat_noi.py`. Docs: `docs/massive_integration.md` §3e.

- **Massive fundamentals/ratios + market snapshots (plan-aware)** - `get_ratios`
  (precomputed EV/EBITDA, EV/Sales, P/E, P/B, ROE/ROA, D/E, FCF, dividend
  yield) registered for `get_fundamentals`/`get_basic_financials` and bound to
  the fundamentals analyst; `get_market_snapshot` (consolidated day/quote) and
  `get_top_movers` bound to the market analyst; new
  `pipeline.py --universe top-movers-massive --movers-direction` universe
  source. These Massive endpoints return 403 NOT_AUTHORIZED on the free Basic
  plan, so each tool degrades with an explicit
  "upgrade at massive.com/pricing" message and activates automatically (no
  code change) once the account's plan includes them. Tests in
  `tests/test_massive_vendor.py`. Docs: `docs/massive_integration.md` §3d.

- **Massive Form-4 insider activity** - `get_form4_insider(ticker, start, end)`
  bound to the fundamentals analyst computes net open-market insider buying from
  SEC Form 4 filings via Massive (`/stocks/filings/vX/form-4`): open-market
  purchases (P) minus sales (S), excluding grant/exercise (A/M) rows. The 13-F
  endpoint is intentionally **not** wired because it has no security (`ticker`)
  filter (only `filer_cik`/`filing_date`) — a per-ticker aggregate would be
  misleading; moomoo `get_institution_holdings` remains the per-ticker
  institutional signal. Tests in `tests/test_massive_vendor.py`. Docs:
  `docs/massive_integration.md` §3c.

- **Massive short interest / short volume** - `get_short_interest_massive`
  registers `massive` in the existing `short_interest` category (FINRA
  two-week settlement: shares short, days-to-cover, avg daily volume, sorted
  newest-first), so the existing `get_short_interest` tool routes to it when
  configured. A dedicated `get_short_volume(ticker, start, end)` tool (daily
  short-sale volume ratio) is bound to the market analyst. Both degrade via
  the error taxonomy (`NoMarketDataError` on empty). Tests in
  `tests/test_massive_vendor.py`. Docs: `docs/massive_integration.md` §3b.

- **Massive macro economy + catalyst OpenD decoupling** - `get_macro_indicators_massive`
  registers `massive` as a `macro_data` vendor (treasury-yields / inflation /
  inflation-expectations / labor-market with FRED-compatible aliases) so macro
  commentary no longer depends on a FRED key or the OpenD gateway. A
  deterministic `fetch_macro_backdrop` (yield-curve inversion / elevated 10y
  breakeven) feeds the B1 catalyst overlay so it keeps de-risking near macro
  stress even when the moomoo event calendar is unavailable; `fetch_catalyst_data`
  now degrades per-section instead of returning `None` on moomoo failure.
  New snapshot verdict `macro-backdrop`; applied only when no forward event
  calendar is present (no double-count with a live moomoo read). Tests in
  `tests/test_massive_vendor.py` + `tests/test_strategies_catalyst.py`. Docs:
  `docs/massive_integration.md` §2/§3a.

- **Massive.com data vendor (news sentiment)** - new `dataflows/massive.py`
  with `get_news_massive` returning per-article structured sentiment
  (positive/negative/neutral + reasoning) from `/v2/reference/news`,
  ticker-filtered so a peer ticker's sentiment never leaks in. Registered as
  a `massive` vendor in the `get_news` chain and `VENDOR_LIST`; a dedicated
  `get_massive_news` LangChain tool is bound to the news/social tool nodes
  and the news analyst prompt. New config key `massive_api_key`
  (`MASSIVE_API_KEY` / `TRADINGAGENTS_MASSIVE_API_KEY`), hermetic offline
  tests in `tests/test_massive_vendor.py`, and `docs/massive_integration.md`.
  US-centric additive vendor (supplements, not replaces, moomoo/yfinance);
  plan-dependent recency/entitlements, FMV/Greeks Business-only (unavailable,
  never invented).

### Fixed

- **README fork-additions highlight (purple border, per-section)** - the fork
  News changelog and EACH fork-additions section (Batch runner, Extended data
  sources, Moomoo OpenAPI vendor, Value watchlist screener, Decision quality,
  Report format, Operational hardening, Decision hardening) is wrapped in its
  own HTML table with a **purple left border** (GitHub's closest rendered
  equivalent to a diff-style added-line mark, since a rendered README cannot
  show the purple bar of the diff view). Each `##` section keeps a real
  heading; upstream sections stay unmarked. The `[!IMPORTANT]` callout stays
  as a GitHub alert.
- **Screener moomoo period-order + prior-period bug (M column always n/a)** -
  moomoo statement payloads list periods newest-first but `_parse_markdown_financials`
  used a last-write-wins dict, so the canonical "latest" was the OLDEST period
  and prior-period values were never captured. Consequently the Beneish
  M-Score - which needs current AND prior - was always `n/a`, and every metric
  (EY, EV/EBIT, F, Z, EpsYoY, ROE) was computed on stale fiscal data. Fixes:
  - `_markdown_period_tables` parses each `### <period>` table and sorts by
    period year (newest first); `_markdown_canonical` scans ALL tables (a
    `get_fundamentals` payload concatenates income+balance+cashflow) and emits
    `{"current", "prior"}` dicts for two-period keys.
  - `_match_row` skips moomoo `-`-prefixed sub-item / contra lines
    (`-Accounts Receivable`, `-Accumulated Depreciation`).
  - depreciation aliases drop the loose `d&a` (normalized to `d a`, it
    substring-matched "Selling and Admin Expenses") and add `depreciation &
    depletion`; `net_receivables` prefers the aggregate `receivables` row.
  - `_latest()` unwraps the dict form at every flat read site (screen_ticker,
    _usd_consistent, fetch_ticker, mover-meta injection).
  - Result: M-Score computes (e.g. MT -2.29, WMT -2.72), F/Z/EY/ROE reflect
    the newest period; NetNet staying `no` on large caps is expected (a
    negative-current-liabilities - current-assets threshold).
- **Regression tests** - tests/test_moomoo_period_fix.py (newest-period,
  prior dicts, dash-skip, d&a alias, M-computes, concatenated-fundamentals).

### Added

- **Finnhub free-tier integration (key: TRADINGAGENTS_FINNHUB_API_KEY)** -
  live-probed the free tier and wired the endpoints that actually work:
  - `get_basic_financials_finnhub` - company_basic_financials metrics
    (epsGrowthQuarterlyYoy / revenueGrowthTTMYoy / roeTTM -> the screener's
    --min-eps-yoy / --min-rev-yoy / --min-roe gates via new canonical aliases
    + a text-router fix so header-prefixed blobs parse); also registered as a
    `get_fundamentals` vendor option
  - `get_insider_activity_finnhub` - stock_insider_sentiment (12m net change
    + mspr + trend, computed)
  - `get_company_peers_finnhub` - comparable peer group
  - `get_profile_finnhub` - profile2 sector (finnhubIndustry -> sector) as
    the second-tier `--sector-rank` fallback (FMP -> Finnhub -> yfinance)
  - bound the three as analyst tools (get_basic_financials / get_insider_activity
    / get_company_peers) to the Fundamentals analyst; all key-gated / guarded
    / no-fabrication
  - docs: api_reference 6.5 table + vendor list
- **Computed-analysis tools - follow-up batch (6 more)** - `analysis_tools.py`
  grows `get_regime_read` (overlays.build_strategy_overlays: regime label +
  position scale + momentum/52w), `get_volatility_contraction` (swing.vcp_setup),
  `get_orderflow_read` (orderflow.summarize on the guarded live fetch),
  `get_analyst_verdict` (screener canonical pipeline -> EY/EV/EBIT/F/M/Z/
  trap-risk/ROE/YoY), `get_earnings_surprise` (standardized surprise % +
  side), and `get_portfolio_weights` (value-proportional + capped weights).
  Bound to the market analyst (regime/VCP/orderflow) and the fundamentals
  analyst (verdict/surprise/portfolio); same no-fabrication contract.
- **Computed-analysis tools for the analyst LLMs** - `agents/utils/analysis_tools.py`
  wraps the deterministic strategy calculators as LangChain tools so the
  agents reason over computed numbers instead of re-deriving (or inventing)
  them from raw vendor output: `get_swing_set` (trend stack + 1-ATR stop +
  2R/3R targets + VCP), `get_relative_strength` (RS line vs benchmark),
  `get_earnings_event_read` (surprise + PEAD setup), `get_catalyst_scale`
  (0..1 B1 scale + verdict), `get_position_sizing` (Kelly + risk budget) and
  `get_risk_gate` (PASS/WARN/REJECT). Bound to the market + news analyst tool
  loops (prompt + graph ToolNodes); all return exact numbers or an explicit
  'unavailable' (no-fabrication contract). Source:
  `tradingagents/strategies/{swing,relative_strength,events,catalyst,size,risk_governor}.py`.
- **Framework Phase-1 screens** - optional screener gates from
  `Strategies/framework.md`: `--min-eps-yoy` / `--min-rev-yoy` (moomoo
  statement YoY columns now parsed - also fixes a latent defect where moomoo
  markdown payloads with `##` headers were never routed to the markdown
  parser), `--min-roe` (net income / total equity via new `total_equity`
  canonical alias), `--max-mcap` ($2B-100B focus), `--sector-rank`
  (`strategies/sector_rank.py`: 11 SPDR ETF groups ranked by 1m/3m momentum,
  ticker sector via FMP profile (key-gated) with guarded
  `dataflows/yfinance_sector.py` fallback),
  `--revision` (net analyst upgrades in 60d as the forward-revisions proxy)
  and `--inst-accum` (two-quarter institutional %-of-float change). New
  EpsYoY/RevYoY/ROE, Sec/Rank, RevUp and Inst table columns; gates apply only
  to measured values (missing data renders n/a).
- **Volatility Contraction Pattern scan (`--scan vcp`)** -
  `strategies/swing.py::vcp_setup` (strict pivot troughs, last-3 pullback depths vs
  the base high must contract 15%->8%->3%-style, deepest pullback within 30%
  of the base, fading volume across troughs; absent volume never fails);
  wired as a screener mode with VCP/Brk columns; `swing_report` carries the
  VCP block as an additional signal. Docs in `Strategies/scan.md`.
- **Techno-fundamental swing scan (`--scan swing`)** - `strategies/swing.py`
  (trend architecture: 20-EMA stacked over rising 50/200-SMA, RSI 45-70 band
  with 40-50 reset, pullback-into-EMA20 on fading volume, 1-ATR swing-low
  stop, 2R/3R two-tier targets, 50% T1 scale-out + 20-EMA trail) and
  `strategies/relative_strength.py` (RS line vs `benchmark_ticker`, 63-day
  established-uptrend slope, new-high/near-high position, negative-divergence
  detection); wired as a new screener mode with ScanC/RS/Stp/T2 columns.
  Source: `Strategies/framework.md`; mode docs in `Strategies/scan.md`.
- **PEAD post-earnings entry helpers** - `events.py` gains
  `gap_up_qualifies` (2.5x-volume gap gate), `consolidation_and_break`
  (opening-range tightening + break trigger) and `post_earnings_play`.
- **Catalyst hard block (G5)** - `catalyst_hard_block_days` config (default
  0 = off; `TRADINGAGENTS_CATALYST_HARD_BLOCK_DAYS` env override): a
  scheduled earnings print inside the window makes the risk governor REJECT
  new risk outright (framework Phase-4 "never initiate" rule) while the
  scale-fold de-risk still applies.
- **Strategy docs** - `Strategies/scan.md` filled (was an empty placeholder)
  with all scan modes including swing.

### Added

- **Momentum day-trading signals (analysis-only)** - `strategies/momentum.py`
  (5-pillar pre-filter, RVOL/EMA9/VWAP, first-pullback pattern with R/R,
  session risk flags); screener `--scan momentum` (+Pills/Pull/RR
  columns); Market Analyst `get_momentum_scan` tool in the graph.
  Source: `Strategies/momentum_day_trading.md`.
- **Alpaca wired into the analyst graph (analysis-only)** -
  `get_market_snapshot_alpaca` tool on the Market Analyst ToolNode;
  `resolve_instrument_context` appends a one-line live 1m snapshot for
  every analyst (one call per run); enabled via `enable_alpaca`.
  Rate-limit aware for the free tier: global pacing (~171 req/min under
  the 200/min cap), batch symbol queries, Retry-After/X-RateLimit-Reset
  backoff on 429.
- **`--intraday` watchlist columns** - with Alpaca keys set, `--intraday`
  appends live **L1Px / VWAP1m / 1mVol** per symbol from the snapshots
  endpoint (latest trade price, 1m-bar VWAP & volume); live-verified
  against Alpaca (AAPL 292.04 / VWAP 309.66 - 2026-08-18).
- **Alpaca smk w/ live keys** - verified against `data.alpaca.markets/v2`
  (bars/batch/snapshots) and `paper-api.alpaca.markets/v2` (calendar/clock);
  free IEX tier limits daily history to the latest bar - screener OHLCV
  fallback now requires >=15 daily bars before use.
- **Alpaca market data (analysis-only)** - `dataflows/alpaca.py` +
  `alpaca_common.py`: signed daily/1m bars (OHLC+vwap), batch bars,
  latest snapshots, trading calendar, market clock; screener falls back
  to Alpaca bars when the vendor CSV is empty (enable_alpaca) and adds a
  market-hours note. No order/position/account endpoints are implemented.
  Plan: `Strategies/alpaca_data_analysis.md`.
- **FMP vendor (optional)** - `dataflows/fmp.py` + `fmp_common.py`: 5+ year
  income/balance/cashflow history, enterprise-values, key metrics TTM,
  earnings surprises, historical OHLCV; `normalized_score` fills the
  V1/V2 gaps (5y median-margin EBIT, EV/NEBIT, 5y PE percentile). Screener
  shows NEV/EBIT + PE5Y columns when `fmp_api_key` is set; register via
  `TRADINGAGENTS_FMP_API_KEY` in `.env`.
- **`--scan` strategies (scan.md)** - trend-pullback (20/50 EMA, RSI 40-55,
  quarter >= +10%, pullback to EMA20) and breakout (>=90% of 52w high,
  above SMA20/50, RVOL >1.5 or <0.75 + Bollinger squeeze) as screener
  modes; `--scan value|trend-pullback|breakout|all` (default all: flags
  ScanA/ScanB columns), combined with the existing value gates.
- **Screener filters updated** - defaults now: market cap >= $10B,
  price >= $15, 30-day avg daily volume >= 1M shares, ATR(14) >= 2%
  of price (new `--min-avg-vol` / `--min-atr-pct` gates computed from
  vendor daily OHLCV; `--min-mcap`/`--price-min` retuned).
- **Deterministic sentiment velocity** - StockTwits counts -> signed
  computed_score (-1..1) + surprise z-score vs a rolling per-ticker
  baseline, injected into the SentimentReport as `computed_score` /
  `computed_velocity` / `sample_size` (rendered **Computed Sentiment**
  line); enabled via `.env` `TRADINGAGENTS_ENABLE_SENTIMENT=true`.
- **Risk report R1b** - the computed risk gate (verdict/snapshot/reasons)
  is injected into every report: prepended to `4_risk/*` and the Risk
  section, mirrored into `5_portfolio/decision.md`; `--risk-compact`
  (`risk_compact_report`, config/.env) replaces 3-analyst transcripts
  with a single `4_risk/verdict.md`.
- **Risk governor R0-R4** - deterministic pre-trade gate
  (`strategies/risk_governor.py`): PASS/WARN/REJECT vs a limits registry;
  book & tail risk (`book_risk.py`): VaR/CVaR, stress shocks, drawdown
  gate; escalation `risk_halt`; `risk_audit.jsonl` + `scripts/risk_report.py`.
  Enabled via .env (`TRADINGAGENTS_ENABLE_RISK_GOVERNOR=true`).
- **V2-V5 value-style wiring** - composite (value+momentum) ranking in the
  screener (`enable_composite_rank`, `--rank composite`), allocation plan
  block (`--alloc`), contract exit levels (ATR breakeven/target via
  `enable_exits`), and computed-debate-context injection
  (`enable_computed_context`). .env defaults enabled.
- **Value-style enhancements (V1-V5)** - normalized earnings (5y median
  margin), historical valuation percentiles, Sloan accruals, trap verdict
  (Trap column in the screener), hard portfolio caps, ATR exits + rebalance
  hints, and computed debate-context snippets. See
  `strategies/value_style_gap_plan.md`.
- **Decision hardening (G1-G5)** - deterministic position/stop contract
  (Kelly x vol x flow x agreement, ATR stop), confidence calibration from
  ledger buckets, computed agreement/consensus, recency-decayed sentiment
  + surprise velocity, and a walk-forward/PBO threshold gate. See
  `strategies/decision_hardening_spec.md`.
- **``$100B market-cap floor``** - `--min-mcap` now defaults to
  $100B for the moomoo rank universes (total cap; float cap <= total so the
  floor satisfies the “cap OR float cap >= $100B” rule); the day-of rank
  cap takes precedence over parsed fundamentals, and `$T` (trillion) values
  parse correctly.
- **``--universe heat-proxy`` refinement** - US-only, stocks only (ETFs/ETNs/
  funds/indices excluded), pipeline is *hot master first (gainers+losers,
  hottest first), losers second*; universe gates now enforce price >= $20 and
  0 < P/E (TTM) <= 40 (`--price-min 20`, `--pe-max 40`, defaults).
- **``--universe heat-proxy``** in the value screener: US-only alias for
  ``top-losers`` that builds the daily universe from moomoo's official intraday
  trade rank as the sanctioned stand-in for the proprietary in-app Heat List
  (composite Trade/Search/News telemetry is not exposed by any moomoo API;
  the web endpoint's signed token is undocumented). Pass the literal app Heat
  List via ``-f list.txt`` to use it directly.
- **Value watchlist screener** — `scripts/value_screener.py` builds a master
  value watchlist by screening tickers through the configured vendor chain
  (`fundamental_data`: `moomoo,yfinance` by default). It normalizes yfinance
  CSV, moomoo markdown/JSON, alpha_vantage JSON, and info text into canonical
  line items, then computes EV/EBIT (Acquirer's Multiple), Earnings Yield, EV,
  Piotroski F-Score, Beneish M-Score, Altman Z and net-net (missing rows ->
  `n/a`, never fabricated). A `--universe top-losers` mode pulls moomoo's
  intraday decliners rank (`get_top_movers_rank`) so the universe changes
daily; output merges name/change columns for picking. See
  `strategies/value_strategy.md`.
- **Quantitative score library** — `tradingagents/dataflows/quantitative_scores.py`
  implements Beneish M-Score, Altman Z-Score, Piotroski F-Score and
  EV / Earnings-Yield / Acquirer's-Multiple helpers, vendor-agnostic over a
  canonical line-item schema (offline unit-tested in
  `tests/test_quantitative_scores.py`).
- **Moomoo top movers vendor call** — `get_top_movers_moomoo()` wraps the SDK's
  intraday gainers/losers rank with the usual error taxonomy (OpenD down /
  permission / rate-limit degrade via `_check_ret`) and converts codes to
  Yahoo-style symbols (`US.AAPL` -> `AAPL`, `HK.00700` -> `00700.HK`).
  Covered by `MoomooTopMoversTests` and `tests/test_value_screener.py`.

### Fixed

- **Value screener refuses mixed currencies.** moomoo reports ADR statements
  in the underlying currency (e.g. JPY) while market cap arrives in USD, which
  produced nonsense EV (e.g. a -62T "EV" for Japan Post's ADR). The screener
  now detects the statement currency (moomoo markdown headers, yfinance
  ``Financial Currency``, alpha_vantage ``reportedCurrency``) plus an
  assets/market-cap >1000x scale heuristic, and gates the USD-only metrics
  (EV / EY / Acquirer's Multiple / Altman Z / net-net) to ``n/a`` when
  currencies would be mixed. A cash > total-assets guard also drops wrong-row
  matches.
- **Moomoo top-movers ``change_ratio`` normalized to a fraction** - the SDK
  returns a ratio in some market sessions and a percent in others for the same
  symbol; the vendor now divides by 100 when \|\|>1.5 so ``DayChg`` formatting
  is always correct.
- **Moomoo fundamentals match the tool signatures.** The moomoo vendor's
  `get_fundamentals`/`get_balance_sheet`/`get_cashflow`/`get_income_statement`
  accepted only the symbol, so the interactive CLI's `curr_date` (and `freq`
  for statements) arguments raised `TypeError` and every call fell back to
  yfinance/alpha_vantage. The vendor now accepts the same arguments as the
  other fundamentals vendors: `freq` selects the annual vs. quarterly report
  type on the moomoo SDK, and `curr_date` filters out statements published
  after the trading day (look-ahead guard, mirroring alpha_vantage).
- **yfinance options chain no longer crashes on `NaN`.** Yahoo chains carry
  `float('nan')` for open interest/volume on many rows; `int(nan)` raised
  `ValueError` and the router logged `Vendor 'yfinance' failed for
  get_options_chain`. The vendor now sums only finite values (missing counts
  contribute 0) and skips non-finite implied-volatility values in the mean,
  so the call degrades to zeroed totals instead of aborting.

### Added
- **Quant-formula calculations** (`Strategies/quants.md` + `quant2.md`
  implementation) - pure deterministic calculators mapped to the repo's gaps:
  - **Volatility estimators**: `strategies/volatility_models.py`
    (Parkinson high-low, Garman-Klass OHLC, EWMA RiskMetrics 0.94, GARCH(1,1)
    pure-NumPy MLE with long-run vol); `volatility_estimator` config
    (close default | ewma | garch) feeds the overlay sizing; tools
    `get_volatility_estimators` + `get_garch_volatility` (market).
  - **Tail decomposition**: `book_risk.incremental_var` + `component_var`
    (normal-covariance MCR, components sum to the book's historical VaR);
    `get_tail_decomposition` market tool.
  - **Mean-reversion quality**: `strategies/mean_reversion.py` (demeaned
    AR(1)/OU half-life with an OLS t-test gate so a random walk is never
    mislabeled; `mean_reversion_verdict`); `get_mean_reversion_quality` tool.
  - **Roll spread**: `liquidity_risk.roll_spread` (effective-spread proxy
    from daily prices), rendered in `get_liquidity_risk`.
  - **Preferred/fixed income**: `strategies/fixed_income.py`
    (indicated_yield, preferred_ytm with honesty for perpetuals,
    macaulay/modified duration, dv01, convexity); `capital_income_screener
    --fi / --fi-horizon` adds YTM/DMod/DV01 columns.
  - **Credit hazard**: `credit_spread.hazard_from_spread` +
    `default_probability` (s ~= lam(1-RR), RR=0.40), rendered in
    `get_credit_spread_read`.
  - **Variance + TCA**: `options_math.variance_swap_strike` (fair variance
    strike from OTM grid) + `get_variance_premium`; `evaluate.implementation_shortfall`
    (decision->arrival->fill) wired into `strategy_quality_report` execution
    block (avg_is_bp).
  Tests: `test_strategies_volatility_models` (8), `test_strategies_tail_decomposition`
  (5), `test_strategies_mean_reversion` (8), `test_strategies_fixed_income`
  (6), `test_quant_phase5` (6). trading_web Value Tools 33->36 tools.

### Added
- **News-sentiment factor** (`News_Sentiment.md` implementation) - the EODHD
  `/sentiments` feed (live-verified, EOD plan) becomes the primary daily
  news-sentiment series:
  - **Feed**: `dataflows/eodhd.get_news_sentiment_eodhd` (daily `normalized`
    centered to -1..1 + 7d SMA + latest innovation + article count),
    `dataflows/alpha_vantage_news.get_news_sentiment_alpha_vantage`
    (parses `ticker_sentiment[]` from the existing `NEWS_SENTIMENT` call,
    post-16:00 ET next-day bucket) and `dataflows/gdelt.get_news_sentiment_gdelt`
    (native tone) — new optional `news_sentiment` category chain
    `eodhd,alpha_vantage,gdelt`.
  - **Analytics**: `strategies/sentiment.py` (`aggregate_daily_sentiment`,
    `daily_sentiment_sma`) + new `strategies/sentiment_research.py`
    (lead/lag, multi-horizon predictive OLS with pure-NumPy Newey-West HAC,
    sector-neutral z + size residualization, rolling IC / IC-IR, IC term
    structure / half-life, quintile long/short backtest).
  - **Tools**: `get_news_sentiment` (routed), `get_news_sentiment_series`,
    `get_sentiment_lead_lag` bound to the market + news analyst ToolNodes and
    prompts.
  - **Eval**: `scripts/sentiment_factor_eval.py` (cross-sectional panel, IC /
    decay / long-short report) + `scripts/value_screener.py --sentiment`
    (`Sent7` / `SentZ` columns).
  - **Overlay (opt-in, OFF)**: `enable_sentiment_factor` folds
    `position_scale * (1 ± max_scale)` only when the name's measured rank IC ≥
    `sentiment_factor_min_ic`, else neutral 1.0 (never blocks).
  - trading_web Value Tools + README (33 tools).
  Tests: `test_strategies_sentiment` (+6), `test_strategies_sentiment_research`
  (12), `test_news_sentiment_series` (13), `test_strategies_overlays` (+5).

### Docs
- **Research-plan + reference sync** - `Strategies/value_dip_swing_prepost_research_plan.md`
  status flipped to implemented; every Part A/B gap marked closed with the
  module that shipped it; the stale "Not doing: ROC/TRIX/Force/A-D" note
  corrected (they shipped in `strategies/extended_indicators.py`); phases
  marked DONE; open questions resolved. `docs/api_reference.md` §6.1 lists
  `get_extended_indicators` / `get_candlestick_patterns` and §6.2's
  `VENDOR_LIST` updated (17 vendors). `docs/developer/12-data-providers.md`
  re-tallied to 22 providers/17 routed vendors, adds the cboe /
  federal_reserve / gdelt / benzinga / newsapi rows, fixes the `news_data`
  chain (…,stockdata,newsapi) and the API-key table.
- **trading_web Value Tools surface** - `run_value_tools` now imports and
  registers `get_extended_indicators` / `get_candlestick_patterns`
  (analysis_tools) + `get_gdelt_sentiment` (news_data_tools) with the matching
  App.jsx options ("Extended indicators", "Candlestick pattern scan", "GDELT
  news-tone sentiment"); README sync table updated to 31 tools; hermetic web
  test added (trading_web commit `db3217d`).

## [0.3.1] — 2026-07-05

Correctness and stability patch: data look-ahead, graph-router crash-safety,
checkpoint identity, crypto sentiment sources, and configurable resilience.

### Fixed

- **Alpha Vantage look-ahead filter now runs.** The fundamentals payload is a
  JSON string, so the dict-only guard skipped filtering and future-dated reports
  leaked into historical runs; parse before filtering. (#1115, @zachthebird)
- **News analyst prompt matches the tool.** The prompt advertised
  `get_news(query, ...)` but the tool takes a ticker; aligned to stop
  hallucinated free-text query calls. (#1116, @shcheuk)
- **Shared debate/risk routers can't crash mid-run.** Both routers return more
  targets than any one edge mapped; every edge now shares the complete path map,
  so a fall-through under prompt/i18n/refactor drift stays routable.
  (#1088, @Fr3ya, @sa7an7, @Sushanth012)
- **Checkpoint resume respects graph shape.** The thread id folds in selected
  analysts, debate/risk depth, and asset mode, so a resume under different
  choices no longer continues the wrong graph. (#1089, @bossjoker1, @Ghraven)
- **Crypto sentiment sources resolve.** StockTwits lists crypto as `<BASE>.X`
  (Yahoo's `BTC-USD` 404s) and Reddit needs the base symbol to match; the social
  path now maps crypto correctly for both. (#1113, @suremadoreai)

### Added

- **Configurable LLM retry budget.** `llm_max_retries` /
  `TRADINGAGENTS_LLM_MAX_RETRIES` is forwarded to every provider, so a transient
  429 burst no longer aborts a run. (#1091, @yanggaome)
- **Bedrock API-key auth.** `AWS_BEARER_TOKEN_BEDROCK` authenticates Amazon
  Bedrock without AWS access keys and takes precedence over an ambient
  `AWS_PROFILE`. (#1103, @praxstack)
- **Latest Claude models.** Added Claude Sonnet 5 (`claude-sonnet-5`) and
  Fable 5 (`claude-fable-5`); effort control now covers the Claude 5 line.

## [0.3.0] — 2026-06-22

Stabilization and extensibility release: a CI gate, a unified verified
data-access contract, a provider and data-vendor registry, and a maintenance
sweep that hardened config precedence, the model catalog, data resilience, and
structured output.

### Added

- **CI gate.** GitHub Actions runs the pytest suite across Python 3.10-3.13,
  strict `ruff`, and a clean-install smoke that imports the package and CLI to
  catch undeclared dependencies. (#994, #197)
- **Provider registry.** OpenAI-compatible providers register as a single spec,
  and a generic `openai_compatible` endpoint covers vLLM, LM Studio, and relays.
  Adds NVIDIA NIM, Kimi, Groq, Mistral, and a native Amazon Bedrock client.
- **Macro and prediction-market vendors.** FRED macro indicators and Polymarket
  event probabilities, surfaced to the news and macro analysts.
- **Programmatic report output.** `TradingAgentsGraph.save_reports()` writes the
  same report tree the CLI produces, for headless and API runs. (#1037)
- **Env-configurable reasoning depth** via `TRADINGAGENTS_OPENAI_REASONING_EFFORT`,
  `TRADINGAGENTS_GOOGLE_THINKING_LEVEL`, and `TRADINGAGENTS_ANTHROPIC_EFFORT`,
  each gated to the models that accept it.

### Changed

- **Verified data-access contract.** Symbol normalization on every vendor path
  (identity, returns, CLI, news); the configured vendor list is the exact
  resolution chain with no silent fallback to unselected vendors; a typed
  `VendorError` taxonomy; look-ahead-safe news windows; stale-OHLCV rejection;
  inclusive yfinance date ranges.
- **Config precedence.** An explicit `TRADINGAGENTS_*` value or CLI flag now wins
  over interactive defaults for debate and risk round counts,
  `--checkpoint / --no-checkpoint`, and the Docker provider profile; invalid
  boolean env values fail loudly. (#975, #976, #977)
- **Current-generation model catalog.** Refreshed provider lineups; retired
  `gpt-4.1`, Claude Sonnet 4.5, and the Gemini 2.5 line.
- **Optional vendors degrade** instead of aborting a run: a failed macro or
  prediction-market lookup returns a no-data sentinel.
- **Analyst prompts lead with the current date** so tool-call date ranges anchor
  to the run date rather than the model's training cutoff. (#836)

### Fixed

- **Instrument identity.** Deterministic ticker-to-company resolution prevents
  wrong-company hallucination, and a verified market-data snapshot grounds price
  and indicator claims. (#814, #830)
- **Social and market data sources.** Reddit RSS-first with 429 backoff,
  StockTwits transport hardening, and Alpha Vantage timeout plus
  key-versus-rate-limit handling.
- **Structured output.** Local OpenAI-compatible servers no longer reject
  object-form `tool_choice`; a thinking model that returns no parsed result falls
  back to free text; null-ish strings in optional price fields coerce to `None`.
  (#1038, #1051, #1057)

### Removed

- The no-op `analyst_concurrency_limit` config knob; parallel analyst execution
  is planned for a later release. (#979)
- The unused committed `uv.lock`. (#1030)

### Contributors

Thanks to everyone who shaped this release through code, design, and reports:

[@CadeYu](https://github.com/CadeYu), [@Zavianx](https://github.com/Zavianx), [@weijianz-opc](https://github.com/weijianz-opc), [@naltun](https://github.com/naltun), [@brahmasky](https://github.com/brahmasky), [@nik2208](https://github.com/nik2208), [@thieucong98](https://github.com/thieucong98), [@Derekko-web](https://github.com/Derekko-web), [@LukiPrince](https://github.com/LukiPrince), [@Eddieargenal](https://github.com/Eddieargenal), [@Ghraven](https://github.com/Ghraven), [@ms32035](https://github.com/ms32035), [@yting27](https://github.com/yting27), [@nyxst4ck](https://github.com/nyxst4ck), [@KenCheung-AIxFinance](https://github.com/KenCheung-AIxFinance), [@yangyusheng2n](https://github.com/yangyusheng2n), [@fareloj](https://github.com/fareloj), [@haosenwang1018](https://github.com/haosenwang1018), [@octo-patch](https://github.com/octo-patch), [@seifenk](https://github.com/seifenk), [@CaoYuhaoCarl](https://github.com/CaoYuhaoCarl), [@mihailnica10](https://github.com/mihailnica10), [@Dado-hash](https://github.com/Dado-hash), [@Handsomemikezzz](https://github.com/Handsomemikezzz), [@ydhawesome](https://github.com/ydhawesome), [@macd2](https://github.com/macd2), [@AyushKar2005](https://github.com/AyushKar2005), [@wildhuman](https://github.com/wildhuman), [@robert23kim](https://github.com/robert23kim), [@bngness](https://github.com/bngness), [@tedix-rodrigo](https://github.com/tedix-rodrigo), [@malaccan](https://github.com/malaccan), [@rfalken78](https://github.com/rfalken78), [@dengli1971-droid](https://github.com/dengli1971-droid), [@proofconcept39](https://github.com/proofconcept39), [@prasta1](https://github.com/prasta1), [@liximin](https://github.com/liximin), [@jeffhuen](https://github.com/jeffhuen), [@mazar](https://github.com/mazar), [@soyangelromero](https://github.com/soyangelromero), [@CNQQC](https://github.com/CNQQC), [@dovetaill](https://github.com/dovetaill), [@fperdigon](https://github.com/fperdigon), [@gyx09212214-prog](https://github.com/gyx09212214-prog), [@RSXLX](https://github.com/RSXLX).

## [0.2.5] — 2026-05-11

### Added

- **Grounded Sentiment Analyst.** The renamed `sentiment_analyst` now reads
  real Yahoo News, StockTwits, and Reddit data before generating its report,
  replacing the prior flow that could fabricate social posts under prompt
  pressure. (#557, #607)
- **MiniMax provider** with the full M2.x catalog (M2.7 / M2.5 / M2.1 / M2
  plus highspeed variants, 204K context). Dual-region: Global
  (`MINIMAX_API_KEY`) and China (`MINIMAX_CN_API_KEY`).
- **Dual-region Qwen and GLM** with separate keys per region — international
  (`DASHSCOPE_API_KEY`, `ZHIPU_API_KEY`) and China (`DASHSCOPE_CN_API_KEY`,
  `ZHIPU_CN_API_KEY`), selectable via a secondary region prompt. (#758)
- **`TRADINGAGENTS_*` env-var configurability for `DEFAULT_CONFIG`.** Override
  `llm_provider`, deep/quick model IDs, `backend_url`, `output_language`,
  debate-round counts, checkpoint flag, and benchmark ticker via `.env` with
  type-aware coercion (string / int / bool). (#602)
- **Interactive API-key detection in the CLI.** When the selected provider's
  key is missing, the CLI prompts for it and persists the value to `.env`
  so the analysis run continues without restart.
- **Remote Ollama support.** `OLLAMA_BASE_URL` points the CLI and the
  programmatic client at a remote `ollama-serve`. The CLI surfaces the
  resolved endpoint and warns on common malformed inputs. Adds a
  `"Custom model ID"` option for models pulled via `ollama pull`. (#648, #768)
- **Configurable news-fetch parameters** in `DEFAULT_CONFIG` — per-ticker
  article limit, macro headline limit, lookback window, and macro search
  queries. (#606, #683)
- **Configurable alpha benchmark** for non-US tickers. Replaces hardcoded
  SPY with regional indices for `.NS` (^NSEI), `.T` (^N225), `.HK` (^HSI),
  `.L` (^FTSE), `.TO` (^GSPTSE), `.AX` (^AXJO), `.BO` (^BSESN); explicit
  `benchmark_ticker` override available. Eliminates FX drift dominating
  alpha for non-USD listings. (#628, #684)
- **Multi-language output covers every user-facing agent** — researchers,
  risk debators, research manager, and trader, ending the previous
  partial-localization reports. (#575)
- **Model catalog refresh.** OpenAI GPT-5.5 frontier, Anthropic Claude Opus
  4.7, Gemini 3.1 Flash-Lite GA, xAI Grok 4.20, Qwen 3.6 line. Versioned IDs
  only; auto-shifting aliases moved to the `"Custom model ID"` option.

### Changed

- **Sentiment Analyst** is now consistently named across the CLI dropdown,
  status panel, and final reports (previously the backend was renamed but
  the CLI still said "Social Analyst"). The `AnalystType.SOCIAL = "social"`
  wire value is kept for saved-config back-compat.

### Fixed

- **Structured output works on DeepSeek V4 / reasoner and MiniMax M2.x.**
  Those providers reject `tool_choice` per their tool-calling docs; the
  binding flow now skips it automatically via a capability table.
- **`pip install .` installations pick up the project `.env`** when running
  the CLI as a console script. (#747)
- **Reports save end-to-end** — streamed chunks were previously dropped from
  `complete_report.md`. (#719, #736)
- **Ticker prompt preserves exchange suffixes** (`.SH`, `.SZ`, `.SS`, `.HK`,
  `.T`, etc.) for A-share, HK, Tokyo, and other non-US flows. (#770)
- **Docker permission errors** no longer block first-run write to
  `~/.tradingagents/`. (#519, #627, #672, #771)
- **Config state no longer leaks between runs** when sub-dicts are mutated;
  `set_config` partial updates preserve sibling defaults. (#788)
- **`max_recur_limit` config actually applies** — previously read but not
  forwarded to the propagator. (#764)
- **Missing-API-key error** names the exact env var to set. (#680)
- **Quieter startup** — suppressed the noisy upstream
  `LangChainPendingDeprecationWarning` from langgraph-checkpoint; will be
  removed once that package ships its fix.

### Security

- **Ticker path-traversal validation** at every filesystem-path site (cache,
  checkpoint database, results) so a malicious ticker cannot escape its
  intended directory. (#618)

## [0.2.4] — 2026-04-25

### Added

- **Structured-output decision agents.** Research Manager, Trader, and Portfolio
  Manager now use `llm.with_structured_output(Schema)` on their primary call
  and return typed Pydantic instances. Each provider's native structured-output
  mode is used (`json_schema` for OpenAI / xAI, `response_schema` for Gemini,
  tool-use for Anthropic, function-calling for OpenAI-compatible providers).
  Render helpers preserve the existing markdown shape so memory log, CLI
  display, and saved reports keep working unchanged. (#434)
- **LangGraph checkpoint resume** — opt-in via `--checkpoint`. State is saved
  after each node so crashed or interrupted runs resume from the last
  successful step. Per-ticker SQLite databases under
  `~/.tradingagents/cache/checkpoints/`. `--clear-checkpoints` resets them. (#594)
- **Persistent decision log** replacing the per-agent BM25 memory. Decisions
  are stored automatically at the end of `propagate()`; the next same-ticker
  run resolves prior pending entries with realised return, alpha vs SPY, and
  a one-paragraph reflection. Override path with `TRADINGAGENTS_MEMORY_LOG_PATH`.
  Optional `memory_log_max_entries` config caps resolved entries; pending
  entries are never pruned. (#578, #563, #564, #579)
- **DeepSeek, Qwen (Alibaba DashScope), GLM (Zhipu), and Azure OpenAI**
  providers, plus dynamic OpenRouter model selection.
- **Docker support** — multi-stage build with separate dev and runtime images.
- **`scripts/smoke_structured_output.py`** — diagnostic that exercises the
  three structured-output agents against any provider so contributors can
  verify their setup with one command.
- **5-tier rating scale** (Buy / Overweight / Hold / Underweight / Sell) used
  consistently by Research Manager, Portfolio Manager, signal processor, and
  the memory log; Trader keeps 3-tier (Buy / Hold / Sell) since transaction
  direction is naturally ternary.
- **Pytest fixtures** — lazy LLM client imports plus placeholder API keys so
  the test suite runs cleanly without credentials. (#588)

### Changed

- **`backend_url` default is now `None`** rather than the OpenAI URL. Each
  provider client falls back to its native default. The previous default
  leaked the OpenAI URL into non-OpenAI clients (e.g. Gemini), producing
  malformed request URLs for Python users who switched providers without
  overriding `backend_url`. The CLI flow is unaffected.
- All file I/O passes explicit `encoding="utf-8"` so Windows users no longer
  hit `UnicodeEncodeError` with the cp1252 default. (#543, #550, #576)
- Cache and log directories moved to `~/.tradingagents/` to resolve Docker
  permission issues. (#519)
- `SignalProcessor` reads the rating from the Portfolio Manager's rendered
  markdown via a deterministic heuristic — no extra LLM call.
- OpenAI structured-output calls default to `method="function_calling"` to
  avoid noisy `PydanticSerializationUnexpectedValue` warnings emitted by
  langchain-openai's Responses-API parse path. Same typed result, no warnings.

### Fixed

- Empty memory no longer triggers fabricated past-lessons in agent prompts;
  the memory-log redesign makes this structurally impossible since only the
  Portfolio Manager consults memory and only when entries exist. (#572)
- Tool-call logging processes every chunk message, not just the last one, and
  memory score normalization handles empty score arrays. (#534, #531)

### Removed

- `FinancialSituationMemory` (the per-agent BM25 system) and the dead
  `reflect_and_remember()` plumbing; subsumed by the persistent decision log.
- Hardcoded Google endpoint that caused 404 when `langchain-google-genai`
  changed its API path. (#493, #496)

### Contributors

Thanks to everyone who shaped this release through code, design, and reports:

- [@claytonbrown](https://github.com/claytonbrown) — checkpoint resume (#594), test fixtures (#588), design feedback on cost tracking (#582) and structured validation (#583)
- [@Bcardo](https://github.com/Bcardo) — memory-log redesign (#579), empty-memory hallucination report (#572), encoding fix proposal (#570)
- [@voidborne-d](https://github.com/voidborne-d) — memory persistence design (#564), portfolio manager state fix (#503)
- [@mannubaveja007](https://github.com/mannubaveja007) — structured-output feature request (#434)
- [@kelder66](https://github.com/kelder66) — RAM-only memory issue (#563)
- [@Gujiassh](https://github.com/Gujiassh) — tool-call logging fix (#534), test stub PR (#533)
- [@iuyup](https://github.com/iuyup) — memory score normalization fix (#531)
- [@kaihg](https://github.com/kaihg) — Google base_url fix (#496)
- [@32ryh98yfe](https://github.com/32ryh98yfe) — Gemini 404 report (#493)
- [@uppb](https://github.com/uppb) — OpenRouter dynamic model selection (#482)
- [@guoz14](https://github.com/guoz14) — OpenRouter limited-model report (#337)
- [@samchenku](https://github.com/samchenku) — indicator name normalization (#490)
- [@JasonOA888](https://github.com/JasonOA888) — y_finance pandas import fix (#488)
- [@tiffanychum](https://github.com/tiffanychum) — stale import cleanup (#499)
- [@zaizou](https://github.com/zaizou) — Docker permission issue (#519)
- [@Stosman123](https://github.com/Stosman123), [@mauropuga](https://github.com/mauropuga), [@hotwind2015](https://github.com/hotwind2015) — Windows encoding bug reports (#543, #550, #576)
- [@nnishad](https://github.com/nnishad), [@atharvajoshi01](https://github.com/atharvajoshi01) — encoding fix proposals (#568, #549)

## [0.2.3] — 2026-03-29

### Added

- **Multi-language output** for analyst reports and final decisions, with a
  CLI selector. Internal agent debate stays in English for reasoning quality. (#472)
- **GPT-5.4 family models** in the default catalog, with deep/quick model split.
- **Unified model catalog** as a single source of truth for CLI options and
  provider validation.

### Changed

- `base_url` is forwarded to Google and Anthropic clients so corporate proxies
  work consistently across providers. (#427)
- Standardised the Google `api_key` parameter to the unified `api_key` form.

### Fixed

- Backtesting fetchers no longer leak look-ahead data when `curr_date` is in
  the middle of a fetched window. (#475)
- Invalid indicator names from the LLM are caught at the tool boundary instead
  of crashing the run. (#429)
- yfinance news fetchers respect the same exponential-backoff retry as price
  fetchers. (#445)

### Contributors

- [@ahmedk20](https://github.com/ahmedk20) — multi-language output (#472)
- [@CadeYu](https://github.com/CadeYu) — model catalog typing (#464)
- [@javierdejesusda](https://github.com/javierdejesusda) — unified Google API key parameter (#453)
- [@voidborne-d](https://github.com/voidborne-d) — yfinance news retry (#445)
- [@kostakost2](https://github.com/kostakost2) — look-ahead bias report (#475)
- [@lu-zhengda](https://github.com/lu-zhengda) — proxy/base_url support request (#427)
- [@VamsiKrishna2021](https://github.com/VamsiKrishna2021) — invalid indicator crash report (#429)

## [0.2.2] — 2026-03-22

### Added

- **Five-tier rating scale** (Buy / Overweight / Hold / Underweight / Sell)
  introduced for the Portfolio Manager.
- **Anthropic effort level** support for Claude models.
- **OpenAI Responses API** path for native OpenAI models.

### Changed

- `risk_manager` renamed to `portfolio_manager` to match the role description
  shown in the CLI display.
- Exchange-qualified tickers (e.g. `7203.T`, `BRK.B`) preserved across all
  agent prompts and tool calls.
- Process-level UTF-8 default attempted for cross-platform consistency
  (note: this approach did not actually take effect; replaced in v0.2.4 with
  explicit per-call `encoding="utf-8"` arguments).

### Fixed

- yfinance rate-limit errors are retried with exponential backoff. (#426)
- HTTP client SSL customisation is supported for environments that need
  custom certificate bundles. (#379)
- Report-section writes handle list-of-string content gracefully.

### Contributors

- [@CadeYu](https://github.com/CadeYu) — exchange-qualified ticker preservation (#413)
- [@yang1002378395-cmyk](https://github.com/yang1002378395-cmyk) — HTTP client SSL customisation (#379)

## [0.2.1] — 2026-03-15

### Security

- Patched `langchain-core` vulnerability (LangGrinch). (#335)
- Removed `chainlit` dependency affected by CVE-2026-22218.

### Added

- `pyproject.toml` build-system configuration; the project now installs via
  modern packaging tooling.

### Removed

- `setup.py` — dependencies consolidated to `pyproject.toml`.

### Fixed

- Risk manager reads the correct fundamental report source. (#341)
- All `open()` calls receive an explicit UTF-8 encoding (initial pass).
- `get_indicators` tool handles comma-separated indicator names from the LLM. (#368)
- `Propagation` initialises every debate-state field so risk debaters never
  see missing keys.
- Stock data parsing tolerates malformed CSVs and NaN values.
- Conditional debate logic respects the configured round count. (#361)

### Contributors

- [@RinZ27](https://github.com/RinZ27) — `langchain-core` security patch (#335)
- [@Ljx-007](https://github.com/Ljx-007) — risk manager fundamental-report fix (#341)
- [@makk9](https://github.com/makk9) — debate-rounds config issue (#361)

## [0.2.0] — 2026-02-04

This is the largest release since the initial public version. The framework
moved from single-provider to a multi-provider architecture and grew several
production-ready surfaces.

### Added

- **Multi-provider LLM support** (OpenAI, Google, Anthropic, xAI, OpenRouter,
  Ollama) via a factory pattern, with provider-specific thinking configurations.
- **Alpha Vantage** integration as a configurable primary data provider, with
  yfinance as a community-stability fallback.
- **Footer statistics** in the CLI: real-time tracking of LLM calls, tool
  calls, and token usage via LangChain callbacks.
- **Post-analysis report saving** — the framework writes per-section markdown
  files (analyst reports, debate transcripts, final decision) when a run
  completes.
- **Announcements panel** — fetches updates from `api.tauric.ai/v1/announcements`
  for the CLI welcome screen.
- **Tool fallbacks** so a single vendor outage does not stop the pipeline.

### Changed

- Risky / Safe risk debaters renamed to **Aggressive / Conservative** for
  consistency with the displayed agent labels.
- Default data vendor switched to balance reliability and quota across
  community deployments.
- Ollama and OpenRouter model lists updated; default endpoints clarified.

### Fixed

- Analyst status tracking and message deduplication in the live display.
- Infinite-loop guard in the agent loop; reflection and logging hardened.
- Various data-vendor implementation bugs and tool-signature mismatches.

### Contributors

This release is the first with substantial outside contributions; many community
PRs from late 2025 also landed here.

- [@luohy15](https://github.com/luohy15) — Alpha Vantage data-vendor integration (#235)
- [@EdwardoSunny](https://github.com/EdwardoSunny) — yfinance fetching optimisations (#245)
- [@Mirza-Samad-Ahmed-Baig](https://github.com/Mirza-Samad-Ahmed-Baig) — infinite-loop guard, reflection, and logging fixes (#89)
- [@ZeroAct](https://github.com/ZeroAct) — saved results path support (#29)
- [@Zhongyi-Lu](https://github.com/Zhongyi-Lu) — `.env` gitignore (#49)
- [@csoboy](https://github.com/csoboy) — local Ollama setup (#53)
- [@chauhang](https://github.com/chauhang) — initial Docker support attempt (#47, later reverted; the merged Docker support shipped in v0.2.4)

## [0.1.1] — 2025-06-07

### Removed

- Static site assets that had been bundled with v0.1.0; the public site now
  lives separately.

## [0.1.0] — 2025-06-05

### Added

- **Initial public release** of the TradingAgents multi-agent trading
  framework: market / sentiment / news / fundamentals analysts; bull and bear
  researchers; trader; aggressive, conservative, and neutral risk debaters;
  portfolio manager. LangGraph orchestration, yfinance data, per-agent
  BM25 memory, single-provider OpenAI integration, interactive CLI.

[0.2.4]: https://github.com/TauricResearch/TradingAgents/compare/v0.2.3...v0.2.4
[0.2.3]: https://github.com/TauricResearch/TradingAgents/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/TauricResearch/TradingAgents/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/TauricResearch/TradingAgents/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/TauricResearch/TradingAgents/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/TauricResearch/TradingAgents/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/TauricResearch/TradingAgents/releases/tag/v0.1.0

### Fixed
- **`get_support_structure` / `get_value_dip_setup` now render the `sma200`
  basis** next to `distance_to_sma200`, so the support distance is anchored
  to its own computed reference value instead of being spliced with a
  different source's 200-day average (QCOM report 2026-09-07 flagged a
  +0.2% distance claim that was actually +0.54% against the printed avg).
- **EPS YoY degenerate-base guard** (`statement_parsing.sane_eps_yoy`, used
  by `get_decline_driver_check` and the analyst-verdict screen): a vendor
  YoY beyond +/-300%, or one whose prior-year EPS base is below $0.01, is a
  denominator artifact, not a decline signal — it now returns n/a instead
  of emitting nonsensical figures like "-2280% EPS YoY" (QCOM 2026-09-07).

### Added
- **Verbatim-citation rule for analyst figures** (market + news system
  prompts and the shared §Tool Evidence block): every figure must be copied
  verbatim from a tool output - never retyped, reformatted, or spliced -
  and when two tools disagree on the same quantity the analyst must quote
  both with tool names instead of reconciling silently. Addresses the QCOM
  2026-09-07 report-garble class (TGA "303.9->944B" for 903.9, "CCC 0.51%"
  for 10.51, an ATR from one tool spliced onto another tool's stop).
- **`repro_check --evidence` analyst-figure cross-check**: flags decimal
  numbers in each analyst report that have no matching value in the run's
  `tool_evidence.json` (tolerance-based: rounded copies of tool values
  pass, digit-garble like 303.9-vs-903.9 fires). Advisory tripwire; the
  prompt rule is the primary guard.

### Added
- **Sentiment analyst journals its pre-fetch into `tool_evidence.json`**:
  the news / StockTwits / Reddit blocks and the deterministic computed score
  are persisted as normal-shaped `sentiment:*` leaves (same args_hash +
  truncation as forced-tool leaves), closing the post-hoc verification gap
  that made the QCOM 2026-09-07 sentiment tallies ("13 Bull vs 1 Bear",
  "velocity -0.82 vs 0.78") uncheckable — `repro_check --evidence` now
  grounds sentiment figures against what the analyst actually saw.

### Added
- **LLM-failure journal** (`tradingagents/agents/utils/llm_failure_journal.py`):
  when a structured-LLM invoke fails with the provider's raw response
  attached (e.g. openai `LengthFinishReasonError` carrying the full
  `ChatCompletion` incl. hidden reasoning tokens), the graph snapshots that
  completion to `<data_cache_dir>/llm_failures/` (or
  `TRADINGAGENTS_LLM_FAILURE_JOURNAL_DIR`). Wired into both structured-
  invoke fallback sites. Advisory — never raises, never breaks the fallback.
  Regression (EIX 2026-09-07): a 9.3k-reasoning-token debate turn was cut at
  the length limit and only the usage line survived; now the full completion
  (prompt-independent) is recoverable.

### Added
- **Per-analyst tool-call log** (`tradingagents/agents/utils/tool_call_log.py`,
  wired into the short-circuit wrapper): one JSONL row per model tool call,
  appended to `<data_cache_dir>/tool_calls/<SYMBOL>_tool_calls.jsonl`
  (config `tool_call_log_dir`, env `TRADINGAGENTS_TOOL_CALL_LOG_DIR`). Each
  row: ts, symbol, trade_date, analyst, tool, event (`executed` vs
  `short_circuit`), `in_model_pool`, args. Answers "which of the ~40
  model-pool tools did the LLM actually invoke" post-run
  (unanswerable from tool_evidence.json, which only lists what was
  gathered). Advisory — never raises, never blocks the graph.

### Added
- **Anti-repetition sampling controls** (`top_p` / `frequency_penalty` /
  `presence_penalty`, env `TRADINGAGENTS_TOP_P` /
  `TRADINGAGENTS_FREQUENCY_PENALTY` / `TRADINGAGENTS_PRESENCE_PENALTY`):
  cross-provider loop-escape levers forwarded to every client that supports
  them (OpenAI-compatible all three; Anthropic/Gemini top_p only). Default
  None = provider default, so run-to-run reproducibility is preserved unless
  a run opts in (recommended: top_p 0.85-0.95, freq/presence 0.2-0.5).
  Range-validated (top_p in [0,1]; penalties in [-2,2]).
- **Repetition-loop guard in the truncation-retry path** (`structured.py`):
  before a continuation prompt, a run of >= 3 identical consecutive lines
  (the max_tokens-padding attractor loop) is trimmed to its first occurrence
  so the loop is never re-fed as context. Conservative: only exact duplicate
  full lines; legitimate repeated structure untouched.

### Fixed
- **`get_analyst_verdict` / `screen_ticker` `revenue_yoy` degenerate guard**
  (`statement_parsing.sane_revenue_yoy`): a vendor revenue-YoY beyond +/-300%
  (or with no safe base) is a units/denominator artifact, not a signal
  (MSFT 2026-09-08: +1779% vs the true +17.79%); it now recomputes from the
  revenue pair or renders n/a - same class as the existing `eps_yoy` guard.
- **`compute_ratios` plausibility + subset-invariant guards**
  (`strategies/ratios.py`): current assets/liabilities can never exceed total
  assets/liabilities (mis-parse produced current 3.74 vs true 1.23 on MSFT
  2026-09-08 -> ratio now nulled); D/E above 10x and dividend yield above 25%
  are units/scaling artifacts, not balance-sheet reads -> n/a. The exact
  MSFT-current-cap (3,659,011,981,312) formula itself was already correct.
- **yfinance fundamentals formatter guards** (`dataflows/y_finance.py`): a
  >25% dividend yield (0.73 = 73% - percent-scaled input) is re-normalized
  to 0.73%; a D/E > 10 renders an explicit "n/a (implausible vendor value
  > 10)" so a unit-scaled 29.118 never reaches the analyst as a real
  leverage read.
- **Combining-diacritic sanitizer in `_finalize_section`**
  (`reporting.py`): stray U+0300-U+036F marks the LLM emits before
  dates/numbers (13x in MSFT market.md 2026-09-08) are stripped before
  any section is persisted, so markdown renders clean.

### Fixed
- **Price-scale/staleness guard** (new `agents/utils/price_consistency.py`,
  wired into 8 OHLCV tools: swing_set / swing_exits / post_close /
  session_discipline / candlestick / bollinger_pct_b / support_structure /
  macd_divergence): the verified-market snapshot now records its authoritative
  close per run, and any setup tool whose own series' close disagrees (>1%)
  appends a PRICE-SCALE WARNING ("UNRELIABLE") to its output — so a stale or
  wrongly-scaled OHLCV (INTU 2026-09-08: setup tools anchored to the 9/4
  close 332.70 / a ~677-scale series while verified was 314.12) can never
  silently produce actionable stops/targets/psych levels off the wrong price.
- **`get_sentiment_lead_lag` strongest-|corr| spans both metrics**: it now
  scans pearson AND spearman and reports lag + metric (INTU 2026-09-08
  claimed 0.206 while a pearson -0.278 was larger).
- **Net-debt sign cross-check** (`y_finance._net_debt_note`): when a yfinance
  balance-sheet's own cash+STI exceeds total debt but the vendor "Net Debt"
  row is positive (INTU 2026-09-08: 8.44B cash vs 6.9B debt, "Net Debt"
  1.48B), the output appends a NET CASH correction note so the analyst never
  quotes a positive debt position that contradicts the sheet.
- **yfinance fundamentals OCF field**: "Operating Cash Flow" now rendered
  separately from "Free Cash Flow", so FCF==OCF aliasing (INTU 2026-09-08:
  6.44B == 6.44B) is visible instead of silently duplicated.
- **`get_ratios` uses a dynamic default date** instead of the hardcoded
  "2026-08-24" (stale quarter could shift current ratio / D/E).

### Fixed
- **`get_composite_rank` surfaces its ranked peer sample** (`peers_ranked:
  <tickers>`) so the "vs N peers" count is auditable against the actual
  tickers (INTU 2026-09-08: "vs 4 peers" while the report listed 10 company
  peers — the two samples come from different sources and are now visible).
- **Distinct labels for the three drawdown measures**: regime `52w_distance`
  is now `52w_distance(drawdown vs 52-wk high)`, `get_book_tail_risk` reads
  `drawdown(book realized)`, `get_strategy_quality` reads `max_dd(backtest)`
  — the unlabeled trio (INTU 2026-09-08: -51.32% / 62.68% / 68.41%) can no
  longer be silently conflated.
- **`live_price_sanity` INSIDE wording clarified**: it reports
  "within the verified day's range [...] (stale-print tolerance +-X%)" so the
  band is not misread as a ±5% band around the live price (INTU 2026-09-08:
  the "[313.13, 327.00] ±5%" label implied ±5% around 314.12, which it is not).

### Fixed
- **`get_credit_spread_read` default-probability 100x error**
  (`analysis_tools.py`): `hazard_from_spread` / `default_probability` expect a
  DECIMAL spread, but the tool passed the FRED percentage (2.68 = 2.68%)
  — producing hazard 4.467 (446.7%) and implied 1y PD 98.9% instead of
  ~4.4% (INTU 2026-09-08 news.md). The tool now converts `hy / 100` before
  computing; a "moderate" credit read no longer renders an absurd 98.9%
  default probability.

### Fixed
- **`sane_revenue_yoy` percent-scaled guard** (`statement_parsing.py`): a
  vendor `revenue_yoy` in (0.3, 3.0] that is percent-scaled (e.g. 1.88 = the
  QCOM 2026-09-08 patch — rendered 188% vs the true +1.9%) now resolves via
  the revenue current/prior pair (ground truth); without a pair, a >100%
  claimed YoY is treated as percent-scaled (1.88 -> 1.88%). The earlier
  |v|>3.0-only guard let the 100x artifact through for values under 300%.

### Fixed
- **`_ohlcv` aligned to the verified-snapshot source (N21 — root cause of the
  price-scale warnings)**: both `analysis_tools._ohlcv` and
  `value_dip_tools._ohlcv` now read from `stockstats_utils.load_ohlcv` — the
  SAME date-aware, look-ahead-filtered source the verified market snapshot
  uses — instead of the vendor-chain CSV that lagged a session or returned a
  corrupted ~2x-scale series (MSTR 2026-09-08: tools at 284.92 / 142.80 vs
  verified 136.68; INTU 2026-09-08: 332.70 vs 314.12). Fixes the stale close
  at the root: the 8 setup tools now compute on the same day's price as the
  verified close, so actionable stops/targets/levels are no longer built on
  yesterday's (or a corrupted) series, and the PRICE-SCALE WARNING advisory
  (6960a03) now correctly stays silent when the sources agree. Also fixed the
  column mapping (load_ohlcv df is `Date,Close,High,Low,Open,Volume`).
- **Test seam `_load_ohlcv_df`** added to both tool modules so the OHLCV
  loader is patchable without bypassing the verified source; the impacted
  `test_analysis_tools.py` data-mocks converted to produce DataFrames.

### Added (advisory LLM report verifier — design docs/design_report_verification_llm.md)
- **LLM report-verification pass**: `tradingagents/agents/utils/report_verifier.py`
  checks every analyst report (1_analysts/*.md) against its `tool_evidence.json`
  leaves and returns per-claim verdicts (`GROUNDED | UNSUPPORTED | CONTRADICTED`)
  + a report-level `PASS/FLAG/UNKNOWN`. It is the qualitative layer the
  deterministic `--evidence` numeric cross-check (`scripts/repro_check.py`)
  cannot provide (causal wording, "never called" phrasing). Advisory: never
  edits reports, never blocks delivery; a provider failure degrades the
  affected report to UNKNOWN (never raises mid-run).
- **Numeric anchoring** (`_anchor_claims`): after the LLM, each claim's decimal
  figures are reconciled against the evidence leaf decimals with the SAME
  <=0.5% tolerance as `repro_check._matches`, so the two gates never disagree
  "about the same number" — a claim the numeric layer would ground is never
  left UNSUPPORTED, and a CONTRADICTED whose figures ARE in evidence drops to
  UNSUPPORTED (no false numeric contradiction).
- **CLI** `scripts/report_verify.py --report-dir <tree> [--model X --provider Y
  --max-calls N]`: offline post-run check, writes `verify_flags.json`, exit 0 =
  all PASS/UNKNOWN, 1 = any FLAG, 2 = missing dir.
- **batch `--verify`**: after each completed symbol, runs the verifier and
  writes `verify_flags.json` (mirrors `_batch_pre_market_check`; best-effort,
  never fails the symbol).
- **Config/`.env.example`**: `TRADINGAGENTS_VERIFY_MODEL` (empty = quick tier)
  and `TRADINGAGENTS_VERIFY_MAX_CALLS` (default 12 per report tree; excess
  stems degrade to UNKNOWN).

### Fixed (report-verifier loop findings, first full pass over MSTR batch6)
- **Unit-scale-blind figure matching** (verifier + `repro_check --evidence`):
  `_matches` now treats raw tool floats and human units as equivalent
  (report `122.4M` matches leaf `122368000.0`, `8.22B` vs `8219628000.0`).
  Deterministic fundamentals suspects on the MSTR tree: 20 -> 0. Canonical
  implementation now lives in `report_verifier._matches`; `repro_check` imports
  it so the two gates share tolerance AND unit handling.
- **Digest hid evidence from the verifier**: `_evidence_digest` capped leaves at
  200 chars, hiding the income-statement revenue row (~4.4k in) and producing
  false "no leaf evidence: truncated" flags. Default is now full-leaf (the
  gatherer already caps at summary_window=12000).
- **Sentiment prompt mandated a fabricated 0-10 score**: `overall_score` was
  produced from nothing (MSTR: "Mildly Bearish 4.0/10" vs deterministic
  computed +0.08). The pipeline now computes deterministic sentiment BEFORE
  the prompt, injects `Deterministic computed sentiment` into the system
  message, and instructs the LLM to anchor the 0-10 verdict as
  `5 + 5 * computed_score` within ±0.5, never contradicting it. The verifier
  now cross-checks the saved report's score against the computed leaf.
- **CLI**: `scripts/report_verify.py --stem <X>` for single-stem / parallel
  per-stem verification (each stem its own bounded job).

### Fixed (adopted from upstream TradingAgents 0.4.0 #1170)
- **Silent-Hold → REVIEW sentinel** (`tradingagents/agents/utils/rating.py):
  an unparseable rating (garbled `Rating: <value>` label — non-tier word,
  fullwidth-colon label, or non-word value like `Rating：⭐⭐⭐`) previously
  degraded to a tradeable Hold; it now returns the `REVIEW_SENTINEL`
  ("REVIEW") so a broken PM decision can never be acted on as Hold. Only the
  tradeable-tier fallback is hardened: callers with an explicit non-tradeable
  default (`"n/a"`) keep it, and ordinary prose that merely mentions "rating"
  without a colon-separated value is untouched. `SignalProcessor` surfaces
  REVIEW too. See docs/review_parent_tauricradingagents.md (review-only, the
  one adoptable item).

### Added (report verifier — internal-consistency pass)
- **Cross-claim internal-conflict detection** (`report_verifier._internal_conflicts`):
  the verifier previously checked each claim against the tool evidence
  individually, so it could not see the same metric asserted at conflicting
  values *within one report* (the TJX 2026-09-08 fundamentals.md: EPV $79.78B
  vs $5.7B, ROE 62.17 vs 53.92, D/E 1.32 vs 1.3, insider net +145,976 vs
  +175k, EPS 5.81 vs 4.79 — every figure "matched some leaf", so per-claim
  anchoring missed the contradiction). Adds an `INTERNAL_CONFLICT` claim class
  (new status) for same-metric/different-value across the report, value
  normalised across K/M/B magnitudes, >1% divergence, values scoped to the
  metric label (no cross-metric misattribution). Advisory, never rewrites.
- **Working-agreement rule 8** (docs/AGENT_ONBOARDING.md): after every
  report-verifier run, verify flagged claims against tool_evidence leaves and
  fix confirmed defects.

### Fixed (market.md audit of TJX 2026-09-08)
- **`get_tranche_plan` avg_entry is size-weighted — now labeled**: the output
  emits `avg_entry(size-weighted)=` instead of ambiguous `avg_entry=`. The
  value was ALREADY correct (weights `[0.3,0.3,0.4]`, w×P = 125.57), but the
  label let readers/below comprehension misread it as an equal-weighted mean
  (simple avg of P1/P2/P3 = 125.88). Disclosing it removes the implied-error
  confusion. Test contract updated to pin `size-weighted`.
- **Market.md remaining conflicts (beta 0.13 vs 0.593, short 1.78% vs 48.1%
  Reg-SHO, put-skew -39.0% vs skew-slope, credit 'moderate' vs 'low') are
  definition-level cross-source issues** — every figure exists in a leaf, so
  they are correctly-unflaggeable-by-value; they are now documented in the
  design doc rather than silently dropped (rule 8).

### Added (composed portfolio>trade risk gate — market.md audit #2/#10)
- **`get_composed_risk_gate(ticker, size_pct?, capital_at_risk_pct?, risk_cap_pct?,
  liquidity_verdict?, weights=...)`**: the ONE-call risk verdict that composes
  the portfolio gate (realized book drawdown from the weighted book, same
  source as `get_book_tail_risk.drawdown_gate`) INTO the risk governor and
  applies the precedence rule **portfolio gate > trade gate** — a blocked
  portfolio drawdown REJECTs a position even when trade-level `risk_ok`
  looks fine (the TJX 2026-09-08 conflict: drawdown_gate=True 23.21% book DD
  vs risk_ok=True). The analyst no longer reconciles the two gates by hand.
  Live proof on TJX: `verdict=REJECT precedence=portfolio-gate>trade-gate
  portfolio_drawdown_block=23.21%`. Wired into the market analyst tool list +
  prompt guidance (+ tests, incl. the disclosure path when book drawdown is
  unavailable — never silently passes). Addresses the external review's
  drawdown-precedence and integration-precedence points.

### Added (quant decision-arbitration — 4 researched phases, all default-off/advisory)
- **P1 Gather-time metric reconciliation** — `strategies/metric_reconcile.py`
  (pure) groups the same metric from multiple tools into ONE canonical bucket
  (e.g. get_fundamentals/get_ratios/get_basic_financials -> market_cap) and
  tags conflicting values at INGEST; `format_evidence_block` appends a
  "VALUES CONFLICT range=... vendors=[...]" line so the analyst sees the
  conflict BEFORE reducing (moves the TJX DCF-80.76-vs-80.60 class from
  post-hoc verifier detection to gather-time prevention). 8 tests.
- **P2 Per-regime calibrated confidence** — `calibration.fit_buckets_by_regime`
  + `calibrated_confidence_by_regime` (per-regime buckets, `_all` fallback) +
  lazy `isotonic_calibrate`; PM `_calibrated_p` now takes the overlay's regime
  label. 6 tests.
- **P3 Weighted + thresholded consensus** — `consensus.weighted_consensus`
  (per-analyst weights, equal=mean) + `should_hold(score, threshold)`; the PM
  consensus line now reports weighted_stance + a HOLD note when below the
  threshold. 7 tests.
- **P4 Hard-gate precedence resolver** — `strategies/risk_hierarchy.py`
  (kill > portfolio > trade > liquidity > regime > data, earliest REJECT
  wins) + `kill_switch_state` emergency tier; `get_composed_risk_gate` now
  resolves the FULL hierarchy (added halt/regime_veto params) and reports
  `blocker=` + the precedence chain. 9 tests.
- **Walk-forward calibration audit** — `scripts/calibration_walkforward.py`
  (pure/offline): fits per-regime buckets IS, evaluates OOS reliability + ECE,
  and shows the calibrated re-map; exit 0/1 by a 0.10 ECE bar. Hermetically
  verified on a synthetic ledger.b

### Added (IT subsector universe + dual-benchmark RS — sector-rotation one level down)
- **IT subsector universe** in `sector_rank.INDUSTRY_ETFS` (parent XLK): CIBR
  Cybersecurity, SKYY Cloud Computing, AIQ AI, BOTZ Robotics, DTCR Data
  Center, NXTG Networking, IYW Tech Hardware, FINX FinTech, XSD Semis (equal-
  weight), VGT Broad IT. Kept INSIDE XLK so the subsectors rank against each
  other within the sector, never vs XLK. VGT is registered as the benchmark —
  excluded from the ranked pool (never circular).
- **Dual-benchmark RS** (`rank_sectors_multifactor` / `rank_industry_group`
  new `bench2_closes`): emits a per-row `rs2` percentile vs a SECOND benchmark
  (the IT pool uses VGT) WITHOUT re-ranking the SPY-relative `rs`. The
  `get_sector_rank` tool now draws VGT as bench2 on the XLK industry pool and
  reports `rs2_vs_vgt` on the top pick — answering "which IT subsector is
  strongest vs IT" separately from "vs the market". Tests: 4 new.

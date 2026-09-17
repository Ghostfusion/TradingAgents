# RiskScore — design

**Part of the score-engine design set: [`README.md`](README.md)** (master).
Siblings: [`FundamentalScore.md`](FundamentalScore.md),
[`TechnicalScore.md`](TechnicalScore.md), [`RegimeScore.md`](RegimeScore.md),
[`NewsScore.md`](NewsScore.md), [`SentimentScore.md`](SentimentScore.md),
[`EventScore.md`](EventScore.md).

**Scope: the risk engine only.** It designs `RiskScore` — *"how much can this
hurt?"* — from the owner's eight categories in
[`../ScoreWeight/market.md`](../ScoreWeight/market.md).

Status: **design (2026-09-17). Not started.** Every one of the eight categories
has at least one real producer, **all of them as components**, and **no 0-100
risk score exists anywhere** (§0.1). This is a new aggregation, not a rename.

---

## 0. What this engine answers, and the three conventions it must fix first

### 0.1 No 0-100 risk score exists — answered by grep, not assumption

Searched `risk_score|RiskScore|risk_grade|risk_rating|risk_band` over
`tradingagents/`, `../TradingExecution/` and the repo root: **zero Python
producers**. Only markdown design documents, and one unrelated string field
(`agents/schemas.py:988 unconditional_risk_rating`). A second search
(`def .*score`) finds only unrelated scorers: `knife_guard.knife_score` (0..~3+,
**risk-increasing**, so not 0-100), `factors.composite_score:115` (0-1 factor
rank), `data_quality.aggregate_quality:40` (data quality, not risk),
`debate_score.debate_score:71`, `alpha_eval.alpha_score:20`, and
`decision_guardrail.score_for_rating:30` (a band lookup, not a producer).

What the executor owns is the **0-100 `opportunity_score` slot** — a different
object, and per the owner's Q1 decision it stays `null` until validation
establishes it (master §7).

### 0.2 Direction: `RiskScore` is inverted, and that is deliberate

`100 = low risk = favourable`, matching every other engine (master §1.2). The
alternative ("high = dangerous") was rejected because a reader comparing
`Fundamental 88 / Technical 61 / Regime 68 / Risk 54` must not have to remember
that one of the four points the other way.

**The consequence is a hard requirement, not a style choice: every component
prints its raw value with units and sign beside its aligned contribution.**
Three incompatible conventions already exist in the tree (§0.3), and a single
aligned score would silently pick one of them.

### 0.3 The three convention conflicts — resolve in code, or the score is ambiguous

| Quantity | Convention 1 | Convention 2 | Convention 3 | Where they collide |
| --- | --- | --- | --- | --- |
| **CVaR / tail loss** | **negative** loss: `book_risk.cvar:18`, `simple_var:9`, `extreme_quantile_var:451` | **positive** magnitude: `book_correlated_stress:128`, `stress_loss:123`, `min_cvar_weights` (`book_risk.py:713`) | **fraction of equity**: the executor's `tail.ESResult.value_pct` (`tail.py:56`) | two producers of one quantity disagree in **sign** (`book_risk.py:18` vs `:713`); consumers `abs()` it inconsistently (`analysis_tools.py:4697`, `trading_graph.py:1640`) |
| **Drawdown** | **positive** magnitude: `evaluate.max_drawdown:108`, `book_risk.portfolio_drawdown:100` | **negative** + labelled band: `regime_state.regime_drawdown:146` (thresholds `regime_state.py:30-32`) | **negative** number: `signald/engine.py:115` → `state.py:75`, emitted at `gate.py:865` | a `regime_drawdown` number and a `measured_book_drawdown` number have **opposite signs for the same market** |
| **Cap family** | **percent of book**: `risk_governor.default_limits:20` (0.30 / 0.45 / 0.35) | **dollar notional**: `mandate.max_notional_per_order_usd:51`, `max_total_exposure_usd:52` | **correlation cluster**: `config.cluster_cap_pct:109` at `gate.py:369` | the owner's "correlation risk 15%" and "concentration risk 10%" each need a **named** cap family; two exist and neither is a correlation coefficient |
| **Semivariance unit** | **squared-return units** — the raw sums `RS⁻ = Σ r²·1[r<0]`, `RS⁺ = Σ r²·1[r>0]` | **return units** — `√RS⁻`, comparable to `regime.realized_vol:29` | **ratio** — `RS⁻/RS⁺` (asymmetry) | one quantity can be a variance, a volatility or a ratio. `RiskScore` pins **`√RS⁻` for the aligned contribution, prints the raw sums beside it**, and treats the ratio as its own component — never one number under three names |

**Design decision: `RiskScore` pins one convention per quantity — positive loss
as a fraction of book equity for tails, positive magnitude for drawdown, and the
correlation-cluster share for correlation — and every component row in the report
prints the raw producer value with its own sign and unit.** Where a producer's
sign differs from the pinned one, the *alignment* is done in the score, visibly,
never by changing the producer (that would break its other readers).

### 0.4 What the evidence says about a risk score's ingredients

- **Expected shortfall is coherent; VaR is not.** The repo's CVaR family is the
  right choice, and it is the one already built (`book_risk.cvar:18`,
  `cdar:174`, `extreme_quantile_var:451`).
- **Volatility targeting improves risk-adjusted outcomes** and tends to reduce
  drawdowns — which is what the engine's sizing path already does
  (`regime_state.vol_cap_factor:169`, `size.composite_position_size:62`). The
  score must not be confused with that multiplier (master §1.4, "score ≠ scale").
- **Correlation alone is not crowding.** Crowding frameworks combine pairwise
  correlation *with* volatility, valuation, short interest and reversal signals;
  crowded positions suffer worse drawdowns in bad states. The repo's
  `cluster_notional` cap is a notional proxy — honest, but it must be labelled a
  proxy.
- **Amihud illiquidity** (|return| per unit volume) is the standard price-impact
  proxy and the repo has it (`liquidity_risk.amihud_illiquidity:71`), along with
  Kyle's lambda (`:262`) and the Corwin-Schultz spread (`:363`).
- **The effective number of bets** (diversification in *independent* risk units,
  not position count) is the right shape for concentration — the repo has
  `hierarchical_risk_parity.hrp_weights:165` and
  `portfolio_optimizer.risk_contribution:246`, but no single concentration
  number.

---

## 1. Component inventory

RiskScore: the owner's staged weights, in one direction (100 = low risk / favourable).

| Component | Weight | Status | Producer (`module.function:line`) | Output key | Direction | Scale/units | Gap |
| --- | --: | --- | --- | --- | --- | --- | --- |
| **Volatility risk** | 15 | SCORABLE | `volatility_models.garch11_fit:226`; `volatility_models.ewma_vol:185`; `volatility_models.parkinson_vol:48`; `volatility_models.garman_klass_vol:78`; `volatility_models.yang_zhang_vol:116` | tool text only (`get_garch_volatility:6995`, `get_volatility_estimators:7188`, `get_vol_cones:8353`) | higher = risk-increasing (vol) | annualized fraction (×√252) | no unified output key; no percentile field except `etf_risk_profile.vol_percentile` |
| — annualized volatility sub-factor | — | SCORABLE | `regime.realized_vol:29`; `volatility_models.*` | `realized_vol` (tool) | risk-increasing | annualized fraction | — |
| — upside / downside semivariance sub-factor | — | **ABSENT** (producer owned by `TechnicalScore.md` §4) | to build in `volatility_models` beside the estimators — `evaluate.downside_deviation:430` is a conditional deviation, not semivariance | `rs_up`, `rs_down`, `rs_ratio` | downside = risk-increasing; the asymmetry ratio risk-increasing above 1 | squared-return units; `√RS⁻` in return units | no producer anywhere (`semivar\|semi_?vol\|upside_vol\|downside_vol` → 0 hits); the **downside** leg is the persistent one (Patton & Sheppard) |
| — expected move sub-factor | — | SCORABLE | `options_surface.implied_move_pct:42`; `options_surface.expected_move_from_chain:50`; `moomoo_extra_tools.get_expected_move:267`; `catalyst.implied_move_from_history:111` | expected move | risk-increasing (wider = riskier) | % / fraction; `implied_move_pct` = 1σ ATM-implied | two producers of "expected move" (event vs options) — naming collision |
| — ATM IV sub-factor | — | SCORABLE | `options_math.implied_vol_and_greeks:119`; `options_math.black_vol_surface:199`; `options_surface.iv_percentile:15` | `atm_iv` / IV percentile | risk-increasing | fraction; `iv_percentile` 0..1 | ATM IV is an input, not a produced score |
| — options walls (dealer gamma/OI) sub-factor | — | PARTIAL | `derivatives_gamma.gex_per_strike:52`; `derivatives_gamma.gamma_regime:105`; `options_surface.put_call_oi_concentration:34` | GEX / regime label / put:call OI | risk-increasing when short-gamma | GEX unnormalized magnitude; label short/long | no strike-level "wall" pinning a price level; no percentile |
| **Tail risk** | 15 | SCORABLE | `book_risk.cvar:18`; `book_risk.simple_var:9`; `book_risk.extreme_quantile_var:451`; `book_risk.var_cvar_horizon:341`; `book_risk.incremental_var:222`; `book_risk.component_var:256`; `book_risk.cdar:174` | tool text (`get_tail_risk:4653`, `get_tail_decomposition:5514`, `get_horizon_var:4022`) | loss (negative) | daily return fraction; EVT/ES negative | sign conventions collide (§3.1); no 0-100 |
| — CVaR sub-factor | — | SCORABLE | `book_risk.cvar:18` | `cvar` | loss | negative return fraction | caller must `abs()` (`analysis_tools.py:4697`) |
| — portfolio CVaR sub-factor | — | SCORABLE | `book_risk.portfolio_cvar:28` (via `portfolio_returns:75`) | `portfolio_cvar` | loss | negative return fraction; cash-diluted when Σw<1 | sign differs from `min_cvar_weights` (positive) |
| — correlated stress sub-factor | — | SCORABLE | `book_risk.book_correlated_stress:128` | `correlated_stress_-10pct` | loss | **positive** magnitude | sign opposite to `cvar` |
| — ES (executor) sub-factor | — | SCORABLE | `tail.es_estimate:145`; `tail.es_historical:97`; `tail.es_parametric:117`; `tail.es_stress:125` | `BookState.es_pct` | loss | **fraction of equity** (ESResult.value_pct) | third unit for the same idea |
| — min-CVaR book sizing sub-factor | — | SCORABLE | `book_risk.min_cvar_weights:628` | `weights`/`cvar` (**positive** at 713) | sizing (advisory) | weights sum 1; cvar positive loss fraction | sign flips vs `cvar:18`; unwired unless `enable_book_risk_sizing` |
| **Liquidity risk** | 10 | SCORABLE | `liquidity_risk.amihud_illiquidity:71`; `float_turnover:53`; `free_float_factor:34`; `days_to_absorb:103`; `spread_estimate:442`; `kyle_lambda:262`; `roll_spread:309` | tool text (`get_liquidity_risk:361`, `get_spread_estimate:73`, `get_liquidation_days:6524`) | risk-increasing (higher = worse; verdict ILLIQUID = bad) | ILLIQ per-$; turnover/day; IWF ratio; days; spread fraction | verdict is 3-valued, not numeric |
| — liquidity caution sub-factor | — | SCORABLE | `liquidity_risk.liquidity_verdict:153` | `verdict` = liquid/caution/illiquid + `dangers` | caution/illiquid = risk-increasing | ordinal label | consumed by `risk_governor.govern` liquidity gate (opt-in) |
| — price-impact / slippage sub-factors | — | SCORABLE | `liquidity_risk.volume_share_slippage:220`; `market_impact_slippage:243` | per-share cost | risk-increasing | price units | — |
| **Gap risk** | 10 | PARTIAL | `market_session.gap_type:137` | `{type, gap_pct, fill_probability, days_to_fill}` | gap = risk-increasing; fill_prob semantics inverted-ish | gap_pct fraction; fill_prob 0..1; days int | **fill_prob/days are hardcoded constants** (§3.2); `type` is a heuristic label |
| — pre-market gap read sub-factor | — | SCORABLE | `pre_market.premarket_gap:40` | `{gap_pct, gap_atr, through_stop, vacuum_to_stop, direction}` | through_stop = strongest reject | fraction; gap_atr in ATR units | **no fill probability / days-to-fill at all** |
| — live pre-open gap sub-factor | — | SCORABLE | `preopen.preopen_gap:129`; `preopen.premarket_rvol:65` | `gap_pct`, `rvol` | risk-increasing | fraction / ratio | separate adapter from `gap_type`; not the same number |
| **Correlation risk** | 15 | SCORABLE | `book_risk.book_correlated_stress:128`; `book_risk.component_var:256`; `covariance_models.ledoit_wolf_shrink:63`; `covariance_models.ewma_covariance:106`; `portfolio_optimizer.risk_contribution:246`; `hierarchical_risk_parity.hrp_weights:165` | tool text | risk-increasing (concentration of co-movement) | covariance matrices / weights / loss fraction | no scalar "correlation risk" number |
| — cluster/notional correlation cap (executor) | — | SCORABLE | `risk/gate._correlation_stress:369` (via `state.cluster_notional:104`; `config.cluster_cap_pct:109`) | `Failure(check="correlation_stress")` | risk-increasing when breached | % of sleeve ceiling × equity | cap is on **notional**, not a correlation coefficient |
| — beta sub-factor | — | PARTIAL | `etf_risk._beta:38` (private, used by `etf_risk.etf_risk_profile`) | `benchmarks[label].beta` | risk-increasing when \|β\| high | ratio | **no book-level net beta** — `BookState.net_beta` has no producer (§3.3) |
| **Concentration risk** | 10 | PARTIAL | `liquidity_risk.ownership_hhi:130`; `portfolio_optimizer.enforce_sector_exposure:169`; `risk/gate._concentration:463`; `state.cluster_notional:104` | HHI / sector weights / Failure | risk-increasing | HHI 0..10000; weights sum 1 | ownership HHI is holder concentration, not portfolio; no single portfolio concentration number |
| — notional/% concentration cap (repo) | — | SCORABLE | `risk_governor.default_limits:20` (`max_position_pct` 0.30, `max_book_position_pct` 0.45, `sector_cap_limit` 0.35) | PASS/WARN/REJECT + numbers | breach = risk-increasing | fraction of book | % of book, not cluster correlation (§3.4) |
| **Portfolio drawdown** | 15 | SCORABLE | `book_risk.portfolio_drawdown:100`; `book_risk.cdar:174`; `book_risk.drawdown_gate:167`; `book_context.measured_book_drawdown:102`; `evaluate.max_drawdown:108`; `evaluate.ulcer_index:621` | tool text (`get_book_tail_risk:5579`) | risk-increasing | **positive** magnitude (0..1) | `drawdown_gate` is boolean, not a level |
| — book drawdown sub-factor | — | SCORABLE | `book_context.measured_book_drawdown:102` (via `book_risk.portfolio_drawdown:100`) | `drawdown` + `source` label | risk-increasing | positive fraction | single resolver shared by governor + tools |
| — labelled-band drawdown sub-factor | — | SCORABLE | `regime_state.regime_drawdown:146` (thresholds `DD_CORRECTION=-0.05:30`, `DD_BEAR=-0.15:31`, `DD_SEVERE=-0.25:32`) | `drawdown` (**negative**) + `label` NORMAL/CORRECTION/BEAR/SEVERE | label drives risk | negative fraction + ordinal label | sign opposite to `portfolio_drawdown` (§3.4) |
| — executor book drawdown sub-factor | — | SCORABLE | `signald/engine.py:115` → `state.BookState.drawdown_pct:75` | `drawdown_pct` | risk-increasing | **negative** fraction, emitted at `gate.py:865` | sign opposite to repo governor |
| — kill switch / ladder sub-factor | — | SCORABLE | `risk_hierarchy.kill_switch_state:81`; `risk/ladder.rung_for:82` | verdict / rung + size_multiplier | risk-increasing | rung 0-4; multiplier | — |
| **Event risk** | 10 | SCORABLE | `catalyst.build_catalyst_snapshot:219`; `catalyst.next_earnings:90`; `catalyst.fed_imminence:142`; `catalyst.macro_imminence:123`; `events.surprise_score:17`; `events.catalyst_risk_penalty:53`; `derivatives_gamma.opex_status:127` | `scale` + `hard_block` | scale<1 / hard_block = risk-increasing | scale in [0.25,1.0]; penalty ≤1; imminence days | occurrence (EventScore's question) vs exposure (RiskScore's) overlap — naming rule needed |
| — position size sub-factor | — | SCORABLE | `size.composite_position_size:62`; `risk_sizing.risk_money:53`; `risk_sizing.risk_quantity:88`; `risk/sizing.size` (executor) | size_pct / qty | sizing (advisory / authoritative in executor) | fraction / shares | score ≠ scale (ground rule 5) |
| — stop distance sub-factor | — | SCORABLE | `risk_sizing.risk_points:20`; `signald/risk/state.py:165` (`RiskRequest.stop_distance`); `Position.open_risk_usd` (state.py:45) | stop distance / open risk | risk-increasing with distance | price units / USD | — |
| — portfolio risk (arbiter) sub-factor | — | SCORABLE | `risk_hierarchy.evaluate_hierarchy:43`; `risk_hierarchy.render_hierarchy:108` | composed verdict | breach = risk-increasing | ordinal KILL>PORTFOLIO>TRADE>LIQUIDITY>REGIME | resolves gates, does not score |

---

## 2. Tool leaves (what the analysts can actually call)

| Leaf (`function:line`) | Toolset binding (`agents/toolsets.py:line`) | What it returns | Wired? |
| --- | --- | --- | --- |
| `get_tail_risk` (analysis_tools.py:4653) | toolsets.py:285 | cvar/var/modified_var/cdar + stress_-10pct | yes |
| `get_book_tail_risk` (analysis_tools.py:5579) | toolsets.py:300 | portfolio_cvar + correlated stress + drawdown + gate | yes |
| `get_tail_decomposition` (analysis_tools.py:5514) | toolsets.py:298 | component VaR table + incremental VaR | yes |
| `get_horizon_var` (analysis_tools.py:4022) | toolsets.py:312 | multi-day VaR/CVaR + scaling_valid | yes |
| `get_downside_read` (analysis_tools.py:3982) | toolsets.py:310 | downside deviation / Sortino | yes |
| `get_credit_spread_read` (analysis_tools.py:4782) | toolsets.py:286 | HY credit band + default prob | yes |
| `get_volatility_estimators` (analysis_tools.py:7188) | toolsets.py:296 | close/Parkinson/GK/EWMA/range vol | yes |
| `get_garch_volatility` (analysis_tools.py:6995) | toolsets.py:297 | GARCH(1,1) omega/alpha/beta + long-run vol | yes |
| `get_vol_cones` (analysis_tools.py:8353) | risk_tool_loop.py:166 (not toolsets) | realized-vol cones percentiles | partial |
| `get_position_sizing` (analysis_tools.py:694) | toolsets.py:264 | Kelly + risk-budget size | yes |
| `get_risk_gate` (analysis_tools.py:810) | toolsets.py:266 | governor PASS/WARN/REJECT + limits | yes |
| `get_composed_risk_gate` (analysis_tools.py:5662) | toolsets.py:301 | risk_hierarchy arbiter verdict | yes |
| `get_book_risk_budget` (quant_formula_tools.py:465) | risk_tool_loop.py:161 (not toolsets) | min-CVaR weights (gated by `enable_book_risk_sizing`) | partial |
| `get_liquidity_risk` (market_position_tools.py:361) | toolsets.py:246 | ILLIQ/turnover/IWF/verdict | yes |
| `get_spread_estimate` (quant_formula_tools.py:73) | toolsets.py:247 | Corwin-Schultz/Abdi-Ranaldo spread floor | yes |
| `get_liquidation_days` (analysis_tools.py:6524) | toolsets.py:302 | days-to-absorb at 15% participation | yes |
| `get_position_risk_multiplier` (quant_adds_tools.py:96) | toolsets.py:265, 434, 457 | soft×hard factor + block list | yes |
| `get_gap_type` (analysis_tools.py:5189) | toolsets.py:259 | gap type + **constant** fill_probability/days_to_fill | yes |
| `get_premarket_review` (analysis_tools.py:6561) | toolsets.py:303 | CONFIRM/REVISE/REJECT from measured gap | yes |
| `get_premarket_liquidity` (analysis_tools.py:5261) | toolsets.py:261 | pre-market volume vs 30d avg | yes |
| `get_expected_move` (moomoo_extra_tools.py:267) | toolsets.py:304 | earnings-implied 1-day move | yes |
| `get_options_chain` (market_position_tools.py:121) | (market analyst) | IV / OI / put-call | yes |
| `get_tranche_plan` (value_dip_tools.py:178) | toolsets.py:288 | tranche caps + re-anchor | yes |
| `get_exit_overrides` (analysis_tools.py:7698) | risk_tool_loop.py:164 | drawdown/trailing overrides | yes |
| `get_ledger_risk_state` (analysis_tools.py:7821) | risk_tool_loop.py:163 | daily-loss/HWM state | yes |

---

## 3. Defects and dead seams

**3.1 CVaR carries three sign/unit conventions.** `book_risk.cvar:18` and `book_risk.simple_var:9` return a **negative** loss; `book_risk.book_correlated_stress:128` and `book_risk.stress_loss:123` return a **positive** magnitude; `book_risk.min_cvar_weights:628` returns `cvar` **positive** (`book_risk.py:713`, `"cvar": round(-cv, 6)`); the executor's `tail.ESResult` (`tail.py:56`) carries `value_pct`, a **fraction of equity**. Consumers must guess: `get_tail_risk` prints `abs(c)` (`analysis_tools.py:4697`) while `risk_governor.govern` compares `cvar_pct > budget` on a positive fraction (`risk_governor.py:106`) and `trading_graph._precompute_risk_context` applies `abs(cv)` (trading_graph.py:1640). Two producers of the same quantity disagree in sign (`book_risk.py:18` vs `book_risk.py:713`), so a caller mixing them silently inverts the tail read. **RiskScore must pin one: positive loss fraction of book equity.**

**3.2 Gap fill probability / days-to-fill are hardcoded constants, not measurements** — **fixed 2026-09-17** (`ba50b5f`): measured over the same-class history with a printed basis; the lookup survives only as the labelled fallback below the minimum sample. `market_session.gap_type:137` assigns literal values per gap class — breakaway `fill_prob = 0.3` / `days = 5` (lines 175/176), exhaustion `0.6` / `3` (179/180), runaway `0.4` / `4` (183/184), common `0.8` / `2` (187/188). `get_gap_type` (`analysis_tools.py:5189`) prints them as if measured (`analysis_tools.py:5206-5212`: `fill_probability={r['fill_probability']:.0%} days_to_fill={r['days_to_fill']}`). `pre_market.premarket_gap:40` has **no** fill statistic at all — it returns only `gap_pct`, `gap_atr`, `through_stop`, `vacuum_to_stop`, `direction`; the design doc's "`pre_market.py` gap statistics" constant claim is over-broad. What a reader sees wrong today: a report citing "fill probability 30%" from a breakaway gap is quoting a constant. A measurement needs historical overnight/premarket bars with a realized fill label (did price trade back through the prior close within N days); the repo already fetches the bars (`agents/utils/analysis_tools._ohlcv`, the vendor chain via `dataflows/interface.route_to_vendor`, and `dataflows/preopen.preopen_gap:129` / `premarket_rvol:65` for live pre-open prints) but never stores the outcome to calibrate against.

**3.3 `BookState.net_beta` has neither a producer nor a reader** — **fixed 2026-09-17** (`a4f8ecf`): it is now `float | None = None`, so unknown is not reported as a flat book. A producer is still absent. Declared at `../TradingExecution/signald/risk/state.py:77` as `net_beta: float = 0.0` on a frozen dataclass. Grep `net_beta` over `TradingAgents` and `../TradingExecution` returns only that line plus design docs (CHANGELOG.md, docs/AGENT_ONBOARDING.md, docs/scores/RiskScore.md). Every construction site omits it — `cli.py:447`, `engine.py:101`, `engine.py:392`, `gates.py:119`, `validation/harness.py:539`, and the test helpers — and a frozen dataclass cannot be assigned post-hoc. The design doc's row 5 ("has a producer and no consumer") is wrong on the producer half: the field is a declared default that is **never populated** (no producer) *and* never read (no consumer = UNWIRED on both sides). The RiskScore's correlation/concentration components therefore cannot use a book beta today; it must be computed, not just consumed.

**3.4 Drawdown has three sign conventions and one labelled band.** `evaluate.max_drawdown:108` and `book_risk.portfolio_drawdown:100` return **positive** magnitudes; `risk_governor.govern` treats `drawdown_pct > risk_max_drawdown_pct` as positive (`risk_governor.py:115`); `regime_state.regime_drawdown:146` returns a **negative** `dd = closes[-1]/high - 1.0` (`regime_state.py:154`) plus a label (thresholds `-0.05/-0.15/-0.25` at lines 30-32); the executor computes `drawdown_pct = -(1.0 - equity/peak)` (positive when equity < peak `signald/engine.py:115`) and emits that **negative** value in the gate snapshot (`signald/risk/gate.py:865`). A number from `regime_drawdown` and a number from `measured_book_drawdown` have opposite signs for the same market; the band labels only exist on the `regime_state` side.

**3.5 Notional-percent cap vs correlation-cluster cap are two different families.** The repo governor caps by **percent of book** (`risk_governor.default_limits:20`: `max_position_pct` 0.30, `max_book_position_pct` 0.45, `sector_cap_limit` 0.35 — a sector is a notional bucket). The executor caps both by **dollar notional** (`mandate.max_notional_per_order_usd:51`, `max_total_exposure_usd:52`) *and* by **correlation cluster** (`config.cluster_cap_pct:109` enforced in `gate._correlation_stress:369` over `state.cluster_notional:104`, plus `max_single_name_pct_swing:106`). RiskScore's "correlation risk 15" and "concentration risk 10" each need a named cap family; today two exist and neither is a correlation coefficient.

**3.6 `get_tail_risk` passes a close-price series as an equity curve to CDaR.** `analysis_tools.py:4690` calls `cdar(closes, ...)` with the raw close series as the "equity proxy" (comment conceded in-line). `cdar` (`book_risk.py:174`) expects a cumulative equity path; using price levels is a defensible proxy but unlabelled, and the printed `cdar`/`dvar` are not the book's CDaR. The tool also has no way to pass the weighted book, so its CDaR and `get_book_tail_risk`'s portfolio numbers are different books under the same name.

**3.7 Duplicated weight-normalisation semantics.** `book_risk.portfolio_cvar:28` and `book_risk.book_correlated_stress:128` re-implement the same cash-sleeve/equal-weight/normalise rules twice (lines ~50-60 and ~150-160). Ground rule 3 (one number, one producer) is violated by construction: a change to the cash-sleeve rule in one leaves the other stale.

---

## 4. What is ABSENT, and the smallest honest producer

**No 0-100 risk score exists (answered explicitly).** Search: regex `risk_score|RiskScore|risk_grade|risk_rating|risk_band` over `tradingagents/`, `../TradingExecution/` and the repo root returns **zero Python producers** — only markdown design/spec files (`CHANGELOG.md`, `docs/AGENT_ONBOARDING.md`, `docs/scores/`, `Strategies/*.md`, `ScoreWeight/*.md`) and the unrelated string field `unconditional_risk_rating: str` at `tradingagents/agents/schemas.py:988`. A second search `def .*score` over `tradingagents/` finds only unrelated scorers: `knife_guard.knife_score` (composite but 0..~3+, **risk-increasing**, not 0-100), `factors.composite_score:115` (0-1 factor rank), `data_quality.aggregate_quality:40` (0-100 data-quality, not risk), `debate_score.debate_score:71`, `alpha_eval.alpha_score:20`, and `decision_guardrail.score_for_rating:30` (a band lookup, not a producer). Conclusion: **RiskScore is a new model**; its inputs are components (CVaR, drawdown, illiquidity, HHI, cluster notional, implied move) and the composite 0-100 producer does not exist.

| ABSENT / PARTIAL piece | Data needed | Already fetched somewhere? | Smallest honest producer |
| --- | --- | --- | --- |
| Composite 0-100 RiskScore | the eight component numbers, direction-aligned (100 = low risk) | all components exist (table §1) | one pure function that z-scores/percentile-maps each component's positive loss/risk form, clips to 0-100, weights the owner's table; NA reduces available weight (never 0) |
| Book net beta (`net_beta`) | per-name beta vs a benchmark + position weights | `etf_risk._beta:38` computes per-name beta; `_ohlcv`/`route_to_vendor` fetch benchmark closes; executor already holds positions + weights | `sum(w_i * beta_i)` in the executor book builder (or a repo helper over the configured basket), stored on `BookState.net_beta` |
| Gap **fill probability** | overnight/premarket gap events labelled by whether price traded back through the prior close within N days | bars are fetched (`_ohlcv`, `route_to_vendor`, `preopen.preopen_gap:129`) but no fill-outcome store | per-gap-class empirical fill rate + mean days from stored historical gaps; until then keep the constant but label it `heuristic` (currently printed as measured) |
| Gap **days-to-fill** | same event sample with realized day count | same as above | empirical mean/median days per gap class from the same sample |
| Pre-market fill statistic in `premarket_gap` | live pre-open print + prior close already available | `preopen.preopen_gap:129`, `premarket_rvol:65` | add a `fill_probability`/`days_to_fill` leg only when a calibrated sample exists; otherwise ABSENT rather than a constant |
| Portfolio correlation-risk scalar | covariance / cluster notionals | `covariance_models.*`, `hrp_weights:165`, `state.cluster_notional:104` all exist | expose one scalar (e.g. largest cluster share of book, or book average pairwise \|ρ\|) with a stated scale |
| Portfolio concentration scalar (portfolio, not holder) | position weights | `enforce_sector_exposure:169`, `risk_contribution:246`, `state.cluster_notional:104` | portfolio HHI over position weights (reuse the HHI formula at `liquidity_risk.ownership_hhi:130`) |
| Options "walls" pinned to price levels | strike-level OI/gamma | `derivatives_gamma.gex_per_strike:52` returns per-strike GEX | return the top strikes by \|GEX\| as explicit levels + distance-to-spot |

**Three conventions the document must resolve (recorded, not fixed):**
1. **CVaR** — negative loss (`book_risk.cvar:18`, `simple_var:9`, `extreme_quantile_var:451`) vs positive magnitude (`book_correlated_stress:128`, `stress_loss:123`, `min_cvar_weights` at `book_risk.py:713`) vs equity fraction (`tail.ESResult` via `tail.py:56`). Consumers abs() it inconsistently (`analysis_tools.py:4697`, `trading_graph.py:1640`).
2. **Drawdown** — positive magnitude (`evaluate.max_drawdown:108`, `portfolio_drawdown:100`) vs labelled band with negative dd (`regime_state.regime_drawdown:146`, thresholds `regime_state.py:30-32`) vs negative number (`signald/engine.py:115` → `state.py:75`, emitted `gate.py:865`).
3. **Cap family** — notional % of book (`risk_governor.default_limits:20`) vs dollar notional (`mandate.py:51-52`) vs correlation-cluster % (`config.cluster_cap_pct:109` at `gate.py:369`).

---

## 5. The composite — how `RiskScore` gets built

1. **A new aggregation over existing components.** One pure function, fed by the
   component values §1 already lists, returning
   `{"score": 0-100, "components": [...], "coverage": {...}}`. No new fetch.
2. **The pinned conventions of §0.3**, applied in the alignment step and printed
   with the raw value.
3. **`NA ≠ 0`.** A missing component reduces the available weight. This matters
   most here: a book with no correlation data must not score as *risky* — it must
   score with less coverage, and say so.
4. **Risk is not an alpha factor.** A high `RiskScore` is not a reason to buy.
   The acceptance case in the master is `F 92 / T 85 / R 78 / K 35` → **NO NEW
   RISK**: the repo already implements this with 17 fail-closed checks in
   `GATE_PRECEDENCE` (`../TradingExecution/signald/contracts.py:42`), a governor
   that never reads a score, and `risk_multiplier.combine` zeroing the soft
   product on a hard flag. **The score is diagnostic.**
5. **Its own band table**, advisory, feeding nothing (master rule 2).
6. **The score never sizes.** `risk/sizing.size` (executor) and
   `size.composite_position_size:62` keep their own paths; the score may be
   *printed beside* a size, never *as* one.
7. **The boundary with `EventScore`** is fixed by question: this engine's event
   leg (10%) measures **exposure** (how dangerous is the event for this
   position), `EventScore` measures **occurrence** (is it happening now). Same
   producers, different questions, and neither may re-derive the other's number
   (master rule 3).

### 5.1 The component map, with the pinned convention

| Owner category | Wt | Reads | Pinned convention |
| --- | --: | --- | --- |
| Volatility risk | 15 | `volatility_models.*`, `regime.realized_vol:29`, `options_surface.implied_move_pct:42` | annualized fraction, **risk-increasing** |
| Tail risk | 15 | `book_risk.cvar:18`, `portfolio_cvar:28`, `cdar:174`, `extreme_quantile_var:451`; executor `tail.ESResult` | **positive loss as a fraction of book equity** |
| Liquidity risk | 10 | `liquidity_risk.amihud_illiquidity:71`, `days_to_absorb:103`, `liquidity_verdict:153`, `kyle_lambda:262` | ILLIQ per $ + days at participation; verdict label printed beside |
| Gap risk | 10 | `market_session.gap_type:137`, `pre_market.premarket_gap:40`, `preopen.preopen_gap:129` | gap as a fraction; **fill statistics labelled a heuristic until §4's calibration exists** |
| Correlation risk | 15 | `book_risk.book_correlated_stress:128`, `covariance_models.ledoit_wolf_shrink:63`, `risk_contribution:246`; executor `gate._correlation_stress:369` | **largest-cluster share of book** (a proxy, labelled) |
| Concentration risk | 10 | `liquidity_risk.ownership_hhi:130` (formula), `enforce_sector_exposure:169`, `state.cluster_notional:104` | portfolio HHI over **position weights** (not holder concentration) |
| Portfolio drawdown | 15 | `book_context.measured_book_drawdown:102` (the single resolver), `cdar:174`, `risk_hierarchy.kill_switch_state:81` | **positive magnitude** |
| Event risk | 10 | `catalyst.build_catalyst_snapshot:219`, `events.catalyst_risk_penalty:53`, `opex_status:127` | `scale ∈ [0.25, 1.0]` + `hard_block` |

---

## 6. Verification requirements

1. **Sign conventions are tested at the boundary**, not assumed: a test feeds a
   known negative CVaR and a known positive `stress_loss` and asserts both align
   to the same favourable direction.
2. **`NA ≠ 0` for every component**: a missing correlation input must *raise*
   coverage-weighted uncertainty, never lower the score.
3. **No-data run returns `None`**, never 50 and never 0.
4. **The score never reaches a gate.** A test asserts the value appears in no
   `GATE_PRECEDENCE` check and no `risk_multiplier` input.
5. **A reproducibility check** — the printed component contributions must
   recompute the printed score.
6. **The drawdown resolver stays single.** A test asserts the score reads
   `book_context.measured_book_drawdown:102` and not `regime_state.regime_drawdown:146`
   (opposite signs).

---

## 7. Open questions

**Status 2026-09-17:** the questions the implementation plan raised are
answered - see [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) §13 (twelve
decisions). The marked ones below are **closed**; the unmarked ones remain open
and are listed in that section's §13.3.


1. **Which cap family does "correlation risk 15%" mean** — the notional cluster
   cap (`config.cluster_cap_pct:109`), a true correlation coefficient, or a new
   scalar (largest cluster share / average pairwise |ρ|)? **Recommendation:** the
   cluster share, labelled a proxy, until Phase C measures whether a correlation
   scalar adds anything.
2. **Does the executor or the engine own the book-level components?** Tail,
   drawdown and cluster notionals are *book* quantities; the engine sees one
   name. The score may therefore need two modes (name-level and book-level) or to
   live in the executor. This is a contract decision, not a modelling one.
3. **Should a `net_beta` producer be added?** §3.3 shows it is neither
   produced nor read; the `0.0` default that made it look flat is gone (it is
   `None` now). Implementing it needs a per-name beta (`etf_risk._beta:38`
   exists, private) times position weights, in the executor's book builder.
4. **Do the two `expected move` producers reconcile?** `options_surface.implied_move_pct:42`
   (ATM-implied) and `catalyst.implied_move_from_history:111` (earnings history)
   are different numbers under one name.
5. **Is `RiskScore` per-name or per-book?** The owner's table mixes both
   (liquidity and volatility are name-level; correlation, concentration and
   drawdown are book-level). The document assumes both are reported and only the
   book-level ones feed the composite. **CLOSED 2026-09-17 (plan §13 Q3): both are reported; only the book-level components feed the composite.**

---

## Appendix — methodology ledger

| Claim | Source | Where it bites |
| --- | --- | --- |
| Expected shortfall is **coherent** (subadditive); VaR is not | the coherent-risk-measure literature | §0.4 — the CVaR family is the right base |
| Volatility targeting improves risk-adjusted returns and tends to reduce drawdowns | vol-targeting studies | §0.4 — and why the score must not be confused with the sizing multiplier |
| Correlation alone does not describe crowding; crowding frameworks combine correlation with volatility, valuation, short interest and reversal, and crowded positions draw down harder in bad states | the crowding literature | §0.3 cap-family row and §7 Q1 — the cluster cap is a proxy, labelled |
| The Amihud ratio (|return| / volume) is the standard price-impact proxy | Amihud (2002) | §1 liquidity row — `amihud_illiquidity:71` is the honest measure |
| The effective number of bets measures diversification in independent risk units, and falls when correlations rise | the ENB / risk-parity literature | §1 concentration row and §7 Q1 |
| Drawdown control is a distinct objective from variance control | the drawdown-control literature | §0.3 — why drawdown has its own 15% and its own resolver |

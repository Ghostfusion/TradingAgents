# RiskScore — design

**Part of the score-engine design set: [`README.md`](README.md)** (master).
Siblings: [`FundamentalScore.md`](FundamentalScore.md),
[`TechnicalScore.md`](TechnicalScore.md), [`RegimeScore.md`](RegimeScore.md),
[`NewsScore.md`](NewsScore.md), [`SentimentScore.md`](SentimentScore.md),
[`EventScore.md`](EventScore.md),
[`MarketScore.md`](MarketScore.md),
[`ValuationScore.md`](ValuationScore.md).

**Scope: the risk engine only.** It designs `RiskScore` — *"how much can this
hurt?"* — from the owner's eight categories in
[`../ScoreWeight/market.md`](../ScoreWeight/market.md).

Status: **built (2026-09-18); gate off by default.** `strategies/risk_score.py` is the engine (eight categories, inverted: 100 = low risk), `get_risk_score` its leaf and `enable_risk_score` its membership switch; it contributes the composite's `K` (master rule 18). The 0-100 aggregation §0.1 said existed nowhere is that module - a new aggregation over the existing components, not a rename. **Unmeasured** (vendor gate).

---

## 0. What this engine answers, and the three conventions it must fix first

### 0.1 No 0-100 risk score exists — answered by grep, not assumption

Searched `risk_score|RiskScore|risk_grade|risk_rating|risk_band` over
`tradingagents/`, `../TradingExecution/` and the repo root: **zero Python
producers**. Only markdown design documents, and one unrelated string field
(`agents/schemas.py:988 unconditional_risk_rating`). A second search
(`def .*score`) finds only unrelated scorers: `knife_guard.knife_score` (0..~3+,
**risk-increasing**, so not 0-100), `factors.composite_score:115` (0-1 factor
rank), `data_quality.aggregate_quality:46` (data quality, not risk),
`debate_score.debate_score:71`, `alpha_eval.alpha_score:229`, and
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
| **CVaR / tail loss** | **negative** loss: `book_risk.cvar:18`, `simple_var:9`, `extreme_quantile_var:451` | **positive** magnitude: `book_correlated_stress:128`, `stress_loss:123`, `min_cvar_weights` (`book_risk.py:713`) | **fraction of equity**: the executor's `tail.ESResult.value_pct` (`tail.py:56`) | two producers of one quantity disagree in **sign** (`book_risk.py:18` vs `:713`); consumers `abs()` it inconsistently (`analysis_tools.py:4715`, `trading_graph.py:1640`) |
| **Drawdown** | **positive** magnitude: `evaluate.max_drawdown:222`, `book_risk.portfolio_drawdown:118` | **negative** + labelled band: `regime_state.regime_drawdown:146` (thresholds `regime_state.py:30-32`) | **negative** number: `signald/engine.py:115` → `state.py:75`, emitted at `gate.py:865` | a `regime_drawdown` number and a `measured_book_drawdown` number have **opposite signs for the same market** |
| **Cap family** | **percent of book**: `risk_governor.default_limits:29` (0.30 / 0.45 / 0.35) | **dollar notional**: `mandate.max_notional_per_order_usd:51`, `max_total_exposure_usd:52` | **correlation cluster**: `config.cluster_cap_pct:109` at `gate.py:369` | the owner's "correlation risk 15%" and "concentration risk 10%" each need a **named** cap family; two exist and neither is a correlation coefficient |
| **Semivariance unit** | **squared-return units** — the raw sums `RS⁻ = Σ r²·1[r<0]`, `RS⁺ = Σ r²·1[r>0]` | **return units** — `√RS⁻`, comparable to `regime.realized_vol:39` | **ratio** — `RS⁻/RS⁺` (asymmetry) | one quantity can be a variance, a volatility or a ratio. `RiskScore` pins **`√RS⁻` for the aligned contribution, prints the raw sums beside it**, and treats the ratio as its own component — never one number under three names |

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
  (`regime_state.vol_cap_factor:169`, `size.composite_position_size:70`). The
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
| **Volatility risk** | 15 | SCORABLE | `volatility_models.garch11_fit:438`; `volatility_models.ewma_vol:397`; `volatility_models.parkinson_vol:155`; `volatility_models.garman_klass_vol:185`; `volatility_models.yang_zhang_vol:288` | tool text only (`get_garch_volatility:6995`, `get_volatility_estimators:7188`, `get_vol_cones:8353`) | higher = risk-increasing (vol) | annualized fraction (×√252) | no unified output key; no percentile field except `etf_risk_profile.vol_percentile` |
| — annualized volatility sub-factor | — | SCORABLE | `regime.realized_vol:39`; `volatility_models.*` | `realized_vol` (tool) | risk-increasing | annualized fraction | — |
| — upside / downside semivariance sub-factor | — | **ABSENT** (producer owned by `TechnicalScore.md` §4) | to build in `volatility_models` beside the estimators — `evaluate.downside_deviation:846` is a conditional deviation, not semivariance | `rs_up`, `rs_down`, `rs_ratio` | downside = risk-increasing; the asymmetry ratio risk-increasing above 1 | squared-return units; `√RS⁻` in return units | no producer anywhere (`semivar\|semi_?vol\|upside_vol\|downside_vol` → 0 hits); the **downside** leg is the persistent one (Patton & Sheppard) |
| — expected move sub-factor | — | SCORABLE | `options_surface.implied_move_pct:42`; `options_surface.expected_move_from_chain:110`; `moomoo_extra_tools.get_expected_move:274`; `catalyst.implied_move_from_history:111` | expected move | risk-increasing (wider = riskier) | % / fraction; `implied_move_pct` = 1σ ATM-implied | two producers of "expected move" (event vs options) — naming collision |
| — ATM IV sub-factor | — | SCORABLE | `options_math.implied_vol_and_greeks:119`; `options_math.black_vol_surface:199`; `options_surface.iv_percentile:15` | `atm_iv` / IV percentile | risk-increasing | fraction; `iv_percentile` 0..1 | ATM IV is an input, not a produced score |
| — options walls (dealer gamma/OI) sub-factor | — | PARTIAL | `derivatives_gamma.gex_per_strike:52`; `derivatives_gamma.gamma_regime:105`; `options_surface.put_call_oi_concentration:34` | GEX / regime label / put:call OI | risk-increasing when short-gamma | GEX unnormalized magnitude; label short/long | no strike-level "wall" pinning a price level; no percentile |
| **Tail risk** | 15 | SCORABLE | `book_risk.cvar:18`; `book_risk.simple_var:9`; `book_risk.extreme_quantile_var:560`; `book_risk.var_cvar_horizon:384`; `book_risk.incremental_var:265`; `book_risk.component_var:299`; `book_risk.cdar:217` | tool text (`get_tail_risk:4653`, `get_tail_decomposition:5514`, `get_horizon_var:4022`) | loss (negative) | daily return fraction; EVT/ES negative | sign conventions collide (§3.1); no 0-100 |
| — CVaR sub-factor | — | SCORABLE | `book_risk.cvar:18` | `cvar` | loss | negative return fraction | caller must `abs()` (`analysis_tools.py:4715`) |
| — portfolio CVaR sub-factor | — | SCORABLE | `book_risk.portfolio_cvar:59` (via `portfolio_returns:75`) | `portfolio_cvar` | loss | negative return fraction; cash-diluted when Σw<1 | sign differs from `min_cvar_weights` (positive) |
| — correlated stress sub-factor | — | SCORABLE | `book_risk.book_correlated_stress:146` | `correlated_stress_-10pct` | loss | **positive** magnitude | sign opposite to `cvar` |
| — ES (executor) sub-factor | — | SCORABLE | `tail.es_estimate:145`; `tail.es_historical:97`; `tail.es_parametric:117`; `tail.es_stress:125` | `BookState.es_pct` | loss | **fraction of equity** (ESResult.value_pct) | third unit for the same idea |
| — min-CVaR book sizing sub-factor | — | SCORABLE | `book_risk.min_cvar_weights:754` | `weights`/`cvar` (**positive** at 713) | sizing (advisory) | weights sum 1; cvar positive loss fraction | sign flips vs `cvar:18`; unwired unless `enable_book_risk_sizing` |
| **Liquidity risk** | 10 | SCORABLE | `liquidity_risk.amihud_illiquidity:71`; `float_turnover:53`; `free_float_factor:34`; `days_to_absorb:103`; `spread_estimate:442`; `kyle_lambda:262`; `roll_spread:309` | tool text (`get_liquidity_risk:361`, `get_spread_estimate:73`, `get_liquidation_days:6524`) | risk-increasing (higher = worse; verdict ILLIQUID = bad) | ILLIQ per-$; turnover/day; IWF ratio; days; spread fraction | verdict is 3-valued, not numeric |
| — liquidity caution sub-factor | — | SCORABLE | `liquidity_risk.liquidity_verdict:153` | `verdict` = liquid/caution/illiquid + `dangers` | caution/illiquid = risk-increasing | ordinal label | consumed by `risk_governor.govern` liquidity gate (opt-in) |
| — price-impact / slippage sub-factors | — | SCORABLE | `liquidity_risk.volume_share_slippage:220`; `market_impact_slippage:243` | per-share cost | risk-increasing | price units | — |
| **Gap risk** | 10 | PARTIAL | `market_session.gap_type:220` | `{type, gap_pct, fill_probability, days_to_fill}` | gap = risk-increasing; fill_prob semantics inverted-ish | gap_pct fraction; fill_prob 0..1; days int | **fill_prob/days are hardcoded constants** (§3.2); `type` is a heuristic label |
| — pre-market gap read sub-factor | — | SCORABLE | `pre_market.premarket_gap:40` | `{gap_pct, gap_atr, through_stop, vacuum_to_stop, direction}` | through_stop = strongest reject | fraction; gap_atr in ATR units | **no fill probability / days-to-fill at all** |
| — live pre-open gap sub-factor | — | SCORABLE | `preopen.preopen_gap:129`; `preopen.premarket_rvol:65` | `gap_pct`, `rvol` | risk-increasing | fraction / ratio | separate adapter from `gap_type`; not the same number |
| **Correlation risk** | 15 | SCORABLE | `book_risk.book_correlated_stress:146`; `book_risk.component_var:299`; `covariance_models.ledoit_wolf_shrink:81`; `covariance_models.ewma_covariance:124`; `portfolio_optimizer.risk_contribution:246`; `hierarchical_risk_parity.hrp_weights:165` | tool text | risk-increasing (concentration of co-movement) | covariance matrices / weights / loss fraction | no scalar "correlation risk" number |
| — cluster/notional correlation cap (executor) | — | SCORABLE | `risk/gate._correlation_stress:369` (via `state.cluster_notional:104`; `config.cluster_cap_pct:109`) | `Failure(check="correlation_stress")` | risk-increasing when breached | % of sleeve ceiling × equity | cap is on **notional**, not a correlation coefficient |
| — beta sub-factor | — | PARTIAL | `etf_risk._beta:39` (private, used by `etf_risk.etf_risk_profile`) | `benchmarks[label].beta` | risk-increasing when \|β\| high | ratio | **no book-level net beta** — `BookState.net_beta` has no producer (§3.3) |
| **Concentration risk** | 10 | PARTIAL | `liquidity_risk.ownership_hhi:130`; `portfolio_optimizer.enforce_sector_exposure:169`; `risk/gate._concentration:463`; `state.cluster_notional:104` | HHI / sector weights / Failure | risk-increasing | HHI 0..10000; weights sum 1 | ownership HHI is holder concentration, not portfolio; no single portfolio concentration number |
| — notional/% concentration cap (repo) | — | SCORABLE | `risk_governor.default_limits:29` (`max_position_pct` 0.30, `max_book_position_pct` 0.45, `sector_cap_limit` 0.35) | PASS/WARN/REJECT + numbers | breach = risk-increasing | fraction of book | % of book, not cluster correlation (§3.4) |
| **Portfolio drawdown** | 15 | SCORABLE | `book_risk.portfolio_drawdown:118`; `book_risk.cdar:217`; `book_risk.drawdown_gate:210`; `book_context.measured_book_drawdown:102`; `evaluate.max_drawdown:222`; `evaluate.ulcer_index:1037` | tool text (`get_book_tail_risk:5579`) | risk-increasing | **positive** magnitude (0..1) | `drawdown_gate` is boolean, not a level |
| — book drawdown sub-factor | — | SCORABLE | `book_context.measured_book_drawdown:102` (via `book_risk.portfolio_drawdown:118`) | `drawdown` + `source` label | risk-increasing | positive fraction | single resolver shared by governor + tools |
| — labelled-band drawdown sub-factor | — | SCORABLE | `regime_state.regime_drawdown:146` (thresholds `DD_CORRECTION=-0.05:30`, `DD_BEAR=-0.15:31`, `DD_SEVERE=-0.25:32`) | `drawdown` (**negative**) + `label` NORMAL/CORRECTION/BEAR/SEVERE | label drives risk | negative fraction + ordinal label | sign opposite to `portfolio_drawdown` (§3.4) |
| — executor book drawdown sub-factor | — | SCORABLE | `signald/engine.py:115` → `state.BookState.drawdown_pct:75` | `drawdown_pct` | risk-increasing | **negative** fraction, emitted at `gate.py:865` | sign opposite to repo governor |
| — kill switch / ladder sub-factor | — | SCORABLE | `risk_hierarchy.kill_switch_state:81`; `risk/ladder.rung_for:82` | verdict / rung + size_multiplier | risk-increasing | rung 0-4; multiplier | — |
| **Event risk** | 10 | SCORABLE | `catalyst.build_catalyst_snapshot:219`; `catalyst.next_earnings:90`; `catalyst.fed_imminence:142`; `catalyst.macro_imminence:123`; `events.surprise_score:17`; `events.catalyst_risk_penalty:63`; `derivatives_gamma.opex_status:166` | `scale` + `hard_block` | scale<1 / hard_block = risk-increasing | scale in [0.25,1.0]; penalty ≤1; imminence days | occurrence (EventScore's question) vs exposure (RiskScore's) overlap — naming rule needed |
| — position size sub-factor | — | SCORABLE | `size.composite_position_size:70`; `risk_sizing.risk_money:53`; `risk_sizing.risk_quantity:88`; `risk/sizing.size` (executor) | size_pct / qty | sizing (advisory / authoritative in executor) | fraction / shares | score ≠ scale (ground rule 5) |
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

**3.1 CVaR carries three sign/unit conventions.** `book_risk.cvar:18` and `book_risk.simple_var:9` return a **negative** loss; `book_risk.book_correlated_stress:146` and `book_risk.stress_loss:141` return a **positive** magnitude; `book_risk.min_cvar_weights:754` returns `cvar` **positive** (`book_risk.py:713`, `"cvar": round(-cv, 6)`); the executor's `tail.ESResult` (`tail.py:56`) carries `value_pct`, a **fraction of equity**. Consumers must guess: `get_tail_risk` prints `abs(c)` (`analysis_tools.py:4715`) while `risk_governor.govern` compares `cvar_pct > budget` on a positive fraction (`risk_governor.py:106`) and `trading_graph._precompute_risk_context` applies `abs(cv)` (trading_graph.py:1640). Two producers of the same quantity disagree in sign (`book_risk.py:18` vs `book_risk.py:713`), so a caller mixing them silently inverts the tail read. **RiskScore must pin one: positive loss fraction of book equity.**

**3.2 Gap fill probability / days-to-fill are hardcoded constants, not measurements** — **fixed 2026-09-17** (`ba50b5f`): measured over the same-class history with a printed basis; the lookup survives only as the labelled fallback below the minimum sample. `market_session.gap_type:220` assigns literal values per gap class — breakaway `fill_prob = 0.3` / `days = 5` (lines 175/176), exhaustion `0.6` / `3` (179/180), runaway `0.4` / `4` (183/184), common `0.8` / `2` (187/188). `get_gap_type` (`analysis_tools.py:5207`) prints them as if measured (`analysis_tools.py:5224-5230`: `fill_probability={r['fill_probability']:.0%} days_to_fill={r['days_to_fill']}`). `pre_market.premarket_gap:40` has **no** fill statistic at all — it returns only `gap_pct`, `gap_atr`, `through_stop`, `vacuum_to_stop`, `direction`; the design doc's "`pre_market.py` gap statistics" constant claim is over-broad. What a reader sees wrong today: a report citing "fill probability 30%" from a breakaway gap is quoting a constant. A measurement needs historical overnight/premarket bars with a realized fill label (did price trade back through the prior close within N days); the repo already fetches the bars (`agents/utils/analysis_tools._ohlcv`, the vendor chain via `dataflows/interface.route_to_vendor`, and `dataflows/preopen.preopen_gap:129` / `premarket_rvol:65` for live pre-open prints) but never stores the outcome to calibrate against.

**3.3 `BookState.net_beta` has neither a producer nor a reader** — **fixed 2026-09-17** (`a4f8ecf`): it is now `float | None = None`, so unknown is not reported as a flat book. A producer is still absent. Declared at `../TradingExecution/signald/risk/state.py:77` as `net_beta: float = 0.0` on a frozen dataclass. Grep `net_beta` over `TradingAgents` and `../TradingExecution` returns only that line plus design docs (CHANGELOG.md, docs/AGENT_ONBOARDING.md, docs/scores/RiskScore.md). Every construction site omits it — `cli.py:447`, `engine.py:101`, `engine.py:392`, `gates.py:119`, `validation/harness.py:539`, and the test helpers — and a frozen dataclass cannot be assigned post-hoc. The design doc's row 5 ("has a producer and no consumer") is wrong on the producer half: the field is a declared default that is **never populated** (no producer) *and* never read (no consumer = UNWIRED on both sides). The RiskScore's correlation/concentration components therefore cannot use a book beta today; it must be computed, not just consumed.

**3.4 Drawdown has three sign conventions and one labelled band.** `evaluate.max_drawdown:222` and `book_risk.portfolio_drawdown:118` return **positive** magnitudes; `risk_governor.govern` treats `drawdown_pct > risk_max_drawdown_pct` as positive (`risk_governor.py:115`); `regime_state.regime_drawdown:146` returns a **negative** `dd = closes[-1]/high - 1.0` (`regime_state.py:154`) plus a label (thresholds `-0.05/-0.15/-0.25` at lines 30-32); the executor computes `drawdown_pct = -(1.0 - equity/peak)` (positive when equity < peak `signald/engine.py:115`) and emits that **negative** value in the gate snapshot (`signald/risk/gate.py:865`). A number from `regime_drawdown` and a number from `measured_book_drawdown` have opposite signs for the same market; the band labels only exist on the `regime_state` side.

**3.5 Notional-percent cap vs correlation-cluster cap are two different families.** The repo governor caps by **percent of book** (`risk_governor.default_limits:29`: `max_position_pct` 0.30, `max_book_position_pct` 0.45, `sector_cap_limit` 0.35 — a sector is a notional bucket). The executor caps both by **dollar notional** (`mandate.max_notional_per_order_usd:51`, `max_total_exposure_usd:52`) *and* by **correlation cluster** (`config.cluster_cap_pct:109` enforced in `gate._correlation_stress:369` over `state.cluster_notional:104`, plus `max_single_name_pct_swing:106`). RiskScore's "correlation risk 15" and "concentration risk 10" each need a named cap family; today two exist and neither is a correlation coefficient.

**3.6 `get_tail_risk` passes a close-price series as an equity curve to CDaR.** `analysis_tools.py:4708` calls `cdar(closes, ...)` with the raw close series as the "equity proxy" (comment conceded in-line). `cdar` (`book_risk.py:174`) expects a cumulative equity path; using price levels is a defensible proxy but unlabelled, and the printed `cdar`/`dvar` are not the book's CDaR. The tool also has no way to pass the weighted book, so its CDaR and `get_book_tail_risk`'s portfolio numbers are different books under the same name.

**3.7 Duplicated weight-normalisation semantics.** `book_risk.portfolio_cvar:59` and `book_risk.book_correlated_stress:146` re-implement the same cash-sleeve/equal-weight/normalise rules twice (lines ~50-60 and ~150-160). Ground rule 3 (one number, one producer) is violated by construction: a change to the cash-sleeve rule in one leaves the other stale.

---

## 4. What is ABSENT, and the smallest honest producer

**No 0-100 risk score exists (answered explicitly).** Search: regex `risk_score|RiskScore|risk_grade|risk_rating|risk_band` over `tradingagents/`, `../TradingExecution/` and the repo root returns **zero Python producers** — only markdown design/spec files (`CHANGELOG.md`, `docs/AGENT_ONBOARDING.md`, `docs/scores/`, `Strategies/*.md`, `ScoreWeight/*.md`) and the unrelated string field `unconditional_risk_rating: str` at `tradingagents/agents/schemas.py:988`. A second search `def .*score` over `tradingagents/` finds only unrelated scorers: `knife_guard.knife_score` (composite but 0..~3+, **risk-increasing**, not 0-100), `factors.composite_score:115` (0-1 factor rank), `data_quality.aggregate_quality:46` (0-100 data-quality, not risk), `debate_score.debate_score:71`, `alpha_eval.alpha_score:229`, and `decision_guardrail.score_for_rating:30` (a band lookup, not a producer). Conclusion: **RiskScore is a new model**; its inputs are components (CVaR, drawdown, illiquidity, HHI, cluster notional, implied move) and the composite 0-100 producer does not exist.

| ABSENT / PARTIAL piece | Data needed | Already fetched somewhere? | Smallest honest producer |
| --- | --- | --- | --- |
| Composite 0-100 RiskScore | the eight component numbers, direction-aligned (100 = low risk) | all components exist (table §1) | one pure function that z-scores/percentile-maps each component's positive loss/risk form, clips to 0-100, weights the owner's table; NA reduces available weight (never 0) |
| Book net beta (`net_beta`) | per-name beta vs a benchmark + position weights | `etf_risk._beta:39` computes per-name beta; `_ohlcv`/`route_to_vendor` fetch benchmark closes; executor already holds positions + weights | `sum(w_i * beta_i)` in the executor book builder (or a repo helper over the configured basket), stored on `BookState.net_beta` |
| Gap **fill probability** | overnight/premarket gap events labelled by whether price traded back through the prior close within N days | bars are fetched (`_ohlcv`, `route_to_vendor`, `preopen.preopen_gap:129`) but no fill-outcome store | per-gap-class empirical fill rate + mean days from stored historical gaps; until then keep the constant but label it `heuristic` (currently printed as measured) |
| Gap **days-to-fill** | same event sample with realized day count | same as above | empirical mean/median days per gap class from the same sample |
| Pre-market fill statistic in `premarket_gap` | live pre-open print + prior close already available | `preopen.preopen_gap:129`, `premarket_rvol:65` | add a `fill_probability`/`days_to_fill` leg only when a calibrated sample exists; otherwise ABSENT rather than a constant |
| Portfolio correlation-risk scalar | covariance / cluster notionals | `covariance_models.*`, `hrp_weights:165`, `state.cluster_notional:104` all exist | expose one scalar (e.g. largest cluster share of book, or book average pairwise \|ρ\|) with a stated scale |
| Portfolio concentration scalar (portfolio, not holder) | position weights | `enforce_sector_exposure:169`, `risk_contribution:246`, `state.cluster_notional:104` | portfolio HHI over position weights (reuse the HHI formula at `liquidity_risk.ownership_hhi:130`) |
| Options "walls" pinned to price levels | strike-level OI/gamma | `derivatives_gamma.gex_per_strike:52` returns per-strike GEX | return the top strikes by \|GEX\| as explicit levels + distance-to-spot |

**Three conventions the document must resolve (recorded, not fixed):**
1. **CVaR** — negative loss (`book_risk.cvar:18`, `simple_var:9`, `extreme_quantile_var:451`) vs positive magnitude (`book_correlated_stress:128`, `stress_loss:123`, `min_cvar_weights` at `book_risk.py:713`) vs equity fraction (`tail.ESResult` via `tail.py:56`). Consumers abs() it inconsistently (`analysis_tools.py:4715`, `trading_graph.py:1640`).
2. **Drawdown** — positive magnitude (`evaluate.max_drawdown:222`, `portfolio_drawdown:100`) vs labelled band with negative dd (`regime_state.regime_drawdown:146`, thresholds `regime_state.py:30-32`) vs negative number (`signald/engine.py:115` → `state.py:75`, emitted `gate.py:865`).
3. **Cap family** — notional % of book (`risk_governor.default_limits:29`) vs dollar notional (`mandate.py:51-52`) vs correlation-cluster % (`config.cluster_cap_pct:109` at `gate.py:369`).

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
   `size.composite_position_size:70` keep their own paths; the score may be
   *printed beside* a size, never *as* one.
7. **The boundary with `EventScore`** is fixed by question: this engine's event
   leg (10%) measures **exposure** (how dangerous is the event for this
   position), `EventScore` measures **occurrence** (is it happening now). Same
   producers, different questions, and neither may re-derive the other's number
   (master rule 3).

### 5.1 The component map, with the pinned convention

| Owner category | Wt | Reads | Pinned convention |
| --- | --: | --- | --- |
| Volatility risk | 15 | `volatility_models.*`, `regime.realized_vol:39`, `options_surface.implied_move_pct:42` | annualized fraction, **risk-increasing** |
| Tail risk | 15 | `book_risk.cvar:18`, `portfolio_cvar:28`, `cdar:174`, `extreme_quantile_var:451`; executor `tail.ESResult` | **positive loss as a fraction of book equity** |
| Liquidity risk | 10 | `liquidity_risk.amihud_illiquidity:71`, `days_to_absorb:103`, `liquidity_verdict:153`, `kyle_lambda:262` | ILLIQ per $ + days at participation; verdict label printed beside |
| Gap risk | 10 | `market_session.gap_type:220`, `pre_market.premarket_gap:40`, `preopen.preopen_gap:129` | gap as a fraction; **fill statistics labelled a heuristic until §4's calibration exists** |
| Correlation risk | 15 | `book_risk.book_correlated_stress:146`, `covariance_models.ledoit_wolf_shrink:81`, `risk_contribution:246`; executor `gate._correlation_stress:369` | **largest-cluster share of book** (a proxy, labelled) |
| Concentration risk | 10 | `liquidity_risk.ownership_hhi:130` (formula), `enforce_sector_exposure:169`, `state.cluster_notional:104` | portfolio HHI over **position weights** (not holder concentration) |
| Portfolio drawdown | 15 | `book_context.measured_book_drawdown:102` (the single resolver), `cdar:174`, `risk_hierarchy.kill_switch_state:81` | **positive magnitude** |
| Event risk | 10 | `catalyst.build_catalyst_snapshot:219`, `events.catalyst_risk_penalty:63`, `opex_status:127` | `scale ∈ [0.25, 1.0]` + `hard_block` |

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

## 7. Decisions (owner, 2026-09-17) - all resolved

**All decided (owner, 2026-09-17).** Each question keeps its text as the record
and carries its decision inline. The architecture decisions are in
[`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) §13; the engine-internal
answers are here.


1. **Which cap family does "correlation risk 15%" mean** — the notional cluster
   cap (`config.cluster_cap_pct:109`), a true correlation coefficient, or a new
   scalar (largest cluster share / average pairwise |ρ|)? **Recommendation:** the
   cluster share, labelled a proxy, until Phase C measures whether a correlation scalar adds anything. **DECIDED
2026-09-17:** keep the cluster/notional concentration **share** as the proxy, renamed
explicitly - `cluster_exposure / portfolio_exposure`. It is **not** a correlation
coefficient and must never be printed as one.
2. **Does the executor or the engine own the book-level components?** Tail,
   drawdown and cluster notionals are *book* quantities; the engine sees one
   name. The score may therefore need two modes (name-level and book-level) or to
   live in the executor. This is a contract decision, not a modelling one. **DECIDED 2026-09-17:** the
executor / portfolio-risk layer **owns** the book-level computations (book CVaR,
drawdown, cluster concentration, portfolio beta, correlated stress). `RiskScore`
owns the **per-security** view and **consumes** the book inputs - book calculations
do not move into the name engine merely because the score displays them.
3. **Should a `net_beta` producer be added?** §3.3 shows it is neither
   produced nor read; the `0.0` default that made it look flat is gone (it is
   `None` now). Implementing it needs a per-name beta (`etf_risk._beta:39`
   exists, private) times position weights, in the executor's book builder. **DECIDED 2026-09-17:** this
is **planned implementation work, not an open design question** - `net_beta` is a
required book-level input and `IMPLEMENTATION_PLAN.md` WP-5 owns the producer.
4. **Do the two `expected move` producers reconcile?** `options_surface.implied_move_pct:42`
   (ATM-implied) and `catalyst.implied_move_from_history:111` (earnings history)
   are different numbers under one name. **DECIDED 2026-09-17:**
`options_surface.implied_move_pct:42` is **canonical** when a valid surface exists;
`catalyst.implied_move_from_history:111` is the **fallback and validation
cross-check**. No reconciliation model - a blended third quantity would need its own
validation. **`EventScore` owns the authoritative field; this engine consumes it**
(see `EventScore.md` §7 Q3 - answered once, there).
5. **Is `RiskScore` per-name or per-book?** The owner's table mixes both
   (liquidity and volatility are name-level; correlation, concentration and
   drawdown are book-level). The document assumes both are reported and only the
   book-level ones feed the composite. **CLOSED 2026-09-17 (plan §13 Q3): both are reported; only the book-level components feed the composite.** **And (engine decision, same day): the book-level *computations* are owned by the executor / portfolio-risk layer** - see Q2 above for the ownership contract.

---

## 8. The owner's formula library (`Strategies/scores/risk_score.md`, 2026-09-26)

**The owner's exhaustive catalogue, ledgered against the engine.** 2,572 lines,
71 numbered top-level sections (§1-§71), 123 `##` sub-headings (98 numbered,
25 named) and 4 `###` sub-headings — **198 headings** — carrying **236 display
formulas**, counted as `$$`-delimited blocks (`grep -c '^\$\$'` = 472 delimiters,
every one paired; §71 carries none) and attributed to the nearest enclosing
numbered section. §1 sits at `##` level; §2-§71 at `#`.

**Its relationship to `../ScoreWeight/market.md`.** `market.md` is the
design-time source of this engine's *eight category weights*, used verbatim in
`risk_score.py::CATEGORY_WEIGHTS:58` and restated in §1 / §5.1 above; the
library is the *arithmetic under those categories* plus **nineteen sections the
engine has no category for** (§14-§16 leverage/distress/Merton, §20
market-regime, §21-§25 systematic/factor/momentum/reversion/volume, §45-§54
short-interest through commodity). Where the two disagree, `market.md` governs
the composite and the library is the backlog: the library's own §70 recommends
"approximately 10 risk factors" including Downside, Systematic, Financial and
Stress, none of which is one of the owner's eight. The library is *not* a second
weight vector — no sub-factor vector is published in either document, which is
why `risk_score.py::category_score:491` runs equal-weight inside each category
and prints that fact.

**The direction rule, confirmed from the code, not from memory.** The library
states risk the usual way — §62's own table is "volatility ↑ → risk ↑, CVaR ↑ →
risk ↑, drawdown ↑ → risk ↑". The engine inverts: `risk_score.py::_align_one:437`
passes every `lower_better` component to `score_engine.py::align:69` with
`direction="lower_better"`, where `frac = (v - lo) / (hi - lo)` then
`frac = 1.0 - frac` (`score_engine.py:109-112`) — so the *low* end of the raw
ramp scores **100** and the high end scores **0**. That is the whole of the
"100 = low risk" convention, and it is the flip every **flip** row below carries.
The three `higher_better` rows in `risk_score.py::COMPONENTS` (`catalyst_scale`,
`catalyst_risk_penalty`, `position_mult_by_side`) are the library's §62
`1 - Normalize` branch and carry **no flip**.

Direction codes in §8.1:

| Code | Meaning | Verified in |
| --- | --- | --- |
| **flip** | library: higher = worse; engine inverts via `align(direction="lower_better")` | `risk_score.py::_align_one:437` → `score_engine.py::align:69` |
| **no flip** | library: higher = safer (§62 `1 - Normalize`); engine reads `higher_better` | `risk_score.py::COMPONENTS` (`catalyst_scale`, `catalyst_risk_penalty`) |
| **neutral** | an input or a normaliser, not a directioned component | §1, §61 |
| **size** | a position size or a stop — never scored (score ≠ scale) | `risk_score.py` docstring rule 6 |

### 8.1 The library's sections against the engine

**One row per library section.** Status vocabulary: **built** (a producer
exists and is exercised), **PARTIAL** (some legs have producers, named legs do
not), **ABSENT** (no producer anywhere — the smallest honest producer is named),
**elsewhere** (produced, but owned by another engine by the anti-double-counting
rule §2.1 of the master, so this engine must *consume*, not re-derive). Every
`module.function:line` was read; where the library's line references have moved
since the doc's §1/§3 were written, the *current* line is cited.

| § | Library section | Form. | Status | Direction | Producer, or the gap (verified) |
| --- | --- | --: | --- | --- | --- |
| 1 | Core return calculations | 5 | built | neutral | `book_context.py::log_returns:31`; `evaluate.py::net_returns:35`, `total_return:53`; excess return exists only as the `risk_free` argument of `evaluate.py::sharpe:94` / `statistical.py::capm_decomposition:328` |
| 2 | Volatility risk | 13 | PARTIAL | flip | `volatility_models.py::garch11_fit:438`, `ewma_vol:397`, `parkinson_vol:155`, `garman_klass_vol:185`, `yang_zhang_vol:288`, `semivariance:68`; `evaluate.py::volatility:84`. **Gap:** §2.4 σ20/σ60 and §2.5 expansion have no producer — `regime_state.py::regime_vol_ratio:92` is market-relative, not a two-window σ ratio |
| 3 | Beta and market risk | 7 | PARTIAL | flip | `evaluate.py::beta:901`, `rolling_beta:939`; `etf_risk.py::_beta:39` (private); `book_risk.py::net_beta:177`. **Gap:** §3.3 downside beta and §3.4 upside beta have no producer |
| 4 | Correlation risk | 5 | PARTIAL | flip | `statistical.py::correlation_matrix:203`; `portfolio.py::mean_correlation:252`; `hierarchical_risk_parity.py::_correlation_distance:50`. **Gap:** §4.5 `CC = Σ_{i≠j} w_i w_j ρ_ij` has no producer — the engine's `cluster_exposure_share` is a **notional share**, see §8.4 |
| 5 | Drawdown risk | 9 | built | flip | `evaluate.py::max_drawdown:222`, `underwater_drawdowns:979`, `ulcer_index:1037`; `book_risk.py::portfolio_drawdown:118`, `cdar:217` |
| 6 | Sharpe-style risk-adjusted measures | 6 | PARTIAL | no flip | `evaluate.py::sharpe:94`, `sortino:860`, `calmar_ratio:1018`; `statistical.py::omega:183`. **Gap:** §6.4 Sterling ratio |
| 7 | Value at Risk | 7 | built | flip | `book_risk.py::simple_var:9` (historical, **negative**), `_book_var:257`, `var_cvar_horizon:384`; `size.py::modified_var:206` is the Cornish-Fisher leg. Note: the parametric-**Gaussian** §7.2 has no producer — `book_risk.py::extreme_quantile_var:560` is EVT/GPD, not Gaussian |
| 8 | Expected Shortfall / CVaR | 3 | built | flip | `book_risk.py::cvar:18`, `portfolio_cvar:59`, `extreme_quantile_var:560` (ES leg); `tail_risk.py::tail_risk:174` |
| 9 | Tail risk | 7 | PARTIAL | flip | `evaluate.py::skewness:818`, `kurtosis:832`, `tail_ratio:1166`; `book_risk.py::copula_scenarios:910` (tail dependence). **Gap:** §9.4 extreme-loss frequency and §9.5 crash frequency as named producers |
| 10 | Downside-risk metrics | 5 | PARTIAL | flip | `evaluate.py::downside_deviation:846`; `volatility_models.py::semivariance:68`. **Gap:** §10.1-§10.4 downside frequency / large-loss frequency / average loss / worst loss |
| 11 | Liquidity risk | 9 | built | flip | `liquidity_risk.py::amihud_illiquidity:71`, `float_turnover:53`, `spread_estimate:442`, `kyle_lambda:262`, `roll_spread:309`, `volume_share_slippage:220` |
| 12 | Gap risk | 4 | built | flip | `market_session.py::gap_type:220` (+ `_gap_fill_stats:167`); `pre_market.py::premarket_gap:40`; `dataflows/preopen.py::preopen_gap:129` |
| 13 | Intraday risk | 5 | built | flip | `size.py::atr:143`; `knife_guard.py::atr_ratio_z:115`; `market_session.py::opening_range:72` |
| 14 | Leverage risk | 8 | **elsewhere** | flip | `ratios.py::compute_ratios:104` (`debt_to_equity`), owned by `fundamental_score.py::risk_subscore:222` (FRS) — `factor_schema.py::SUBSCORE_FACTORS:399` puts `debt_to_equity` in FRS. Not a RiskScore category |
| 15 | Financial distress risk | 7 | **elsewhere** | flip | `dataflows/quantitative_scores.py::altman_z_score:181`; `normalized.py::ohlson_o_score:157`, `zmijewski_score:217`; `credit_spread.py::default_probability:185` — `z`/`o`/`zmijewski_x` are FRS's (`SUBSCORE_FACTORS:399`) |
| 16 | Merton structural credit risk | 1 | built | flip | `credit_spread.py::merton_distance_to_default:104` |
| 17 | Credit-spread risk | 3 | built | flip | `credit_spread.py::credit_stress_level:44`, `hazard_from_spread:84`; `statistical.py::spread_zscore:393` |
| 18 | Earnings/event risk | 5 | built | flip | `catalyst.py::build_catalyst_snapshot:219`, `implied_move_from_history:111`; `events.py::surprise_score:17`, `catalyst_risk_penalty:63` |
| 19 | Options-implied risk | 8 | built | flip | `options_surface.py::iv_percentile:15`, `iv_skew:25`, `volatility_risk_premium:140`, `put_call_oi_concentration:34`, `implied_move_pct:42`; `options_math.py::implied_vol_and_greeks:119` |
| 20 | Market-regime risk | 4 | **elsewhere** | flip | **RegimeScore owns it**: `regime_score.py::RAMPS:91` (`vix_percentile`, `vix_term_structure`, `realized_vol_percentile`), leaf `analysis_tools.py::_vix_percentile_read:8857`; `regime_score.py::vix_term_structure:408`; `regime_state.py::regime_vol_ratio:92`. Library §20.4 itself says it "should feed RegimeScore and RiskScore separately" |
| 21 | Systematic risk | 4 | built | flip | `statistical.py::capm_decomposition:328`; `evaluate.py::alpha:920`, `tracking_error:869`, `information_ratio:892` |
| 22 | Factor risk | 4 | built | flip | `factors.py::fama_french_5_factor:518`; `statistical.py::ols_factors:353`, `variance_inflation_factor:570` |
| 23 | Momentum crash risk | 2 | PARTIAL | flip | `factors.py::momentum:24`; `momentum.py::momentum_12_1:358`; `knife_guard.py::momentum_return_z:78`, `drawdown_3d_z:135`. **Gap:** the §23 reversal `R_short - R_long` leg |
| 24 | Mean-reversion / overextension risk | 3 | built | flip | `value_dip.py::bollinger_pct_b:77`; `factors.py::high_distance:35`, `z_score:68` |
| 25 | Volume risk | 3 | built | flip | `knife_guard.py::volume_shock_z:93`; `momentum.py::rvol:25`; `volume_flags.py::rvol_ex_mechanical:90` |
| 26 | Concentration risk | 5 | built | flip | `liquidity_risk.py::ownership_hhi:130` (the HHI formula); `portfolio_optimizer.py::enforce_sector_exposure:169`; `hierarchical_risk_parity.py::hrp_weights:165`; engine rows `portfolio_hhi` / `top_position_share` / `sector_max_share` (`risk_score.py::COMPONENTS`) |
| 27 | Portfolio volatility | 1 | built | flip | `covariance_models.py::ledoit_wolf_shrink:81`, `ewma_covariance:124`; `portfolio_optimizer.py::_covariance_matrix:19` |
| 28 | Marginal risk contribution | 2 | built | flip | `portfolio_optimizer.py::risk_contribution:246` |
| 29 | Component risk contribution | 2 | built | flip | `portfolio_optimizer.py::risk_contribution:246` (RC and PRC legs) |
| 30 | Portfolio VaR | 1 | built | flip | `book_risk.py::_book_var:257`; `book_risk.py::var_cvar_horizon:384` |
| 31 | Portfolio CVaR | 1 | built | flip | `book_risk.py::portfolio_cvar:59` |
| 32 | Stress testing | 2 | built | flip | `book_risk.py::stress_loss:141`, `book_correlated_stress:146`; executor `signald/risk/tail.py::StressGrid:41` |
| 33 | Monte Carlo risk | 2 | built | flip | `book_risk.py::copula_scenarios:910`; `conformal.py::block_bootstrap_interval:409`. **Gap:** §33's probability-of-hitting-stop and expected-terminal-loss legs |
| 34 | Probability of loss | 2 | PARTIAL | flip | `evaluate.py::expectancy_stats:1185` (`win_rate`); `size.py::risk_of_ruin:240`. **Gap:** a return-series `P(R<0)` producer |
| 35 | Expected loss | 1 | built | flip | `evaluate.py::expectancy_stats:1185` (`expectancy`, `avg_loss`) |
| 36 | Expected downside | 1 | built | flip | `volatility_models.py::semivariance:68`; `evaluate.py::expectancy_stats:1185` |
| 37 | Risk/reward | 1 | built | flip | `evaluate.py::expectancy_stats:1185` (`profit_factor`, `tail_ratio`) |
| 38 | Expected value | 2 | built | flip | `evaluate.py::expectancy_stats:1185` (expectancy); `size.py::optimal_f:273` |
| 39 | Kelly risk | 4 | built | **size** | `size.py::kelly_fraction:14`, `position_size_kelly:24`, `risk_of_ruin:240`; `portfolio.py::kelly_weights:452` |
| 40 | Position sizing risk | 3 | built | **size** | `risk_sizing.py::risk_money:53`, `risk_quantity:88`; `size.py::composite_position_size:70` |
| 41 | Stop-loss risk | 2 | built | **size** | `risk_sizing.py::risk_points:20`; `size.py::stop_loss_atr:162` |
| 42 | Liquidity-adjusted position risk | 1 | built | flip | `liquidity_risk.py::days_to_absorb:103` |
| 43 | Market-impact-adjusted risk | 2 | built | flip | `liquidity_risk.py::market_impact_slippage:243`; `evaluate.py::implementation_shortfall:1367` |
| 44 | Slippage risk | 3 | built | flip | `liquidity_risk.py::volume_share_slippage:220`, `spread_estimate:442`; `evaluate.py::implementation_shortfall:1367` |
| 45 | Short-interest risk | 2 | built | flip | `short_interest.py::short_interest_percentile:35`; `dataflows/massive.py::get_short_interest_massive:485` |
| 46 | Insider / ownership concentration risk | 2 | built | flip | `liquidity_risk.py::ownership_hhi:130` (holder HHI, 0-10000); `liquidity_risk.py::free_float_factor:34` |
| 47 | Bankruptcy / solvency risk | 3 | **elsewhere** | flip | `ratios.py::compute_ratios:104` (`current`, `quick`), owned by FRS (`SUBSCORE_FACTORS:399`). RiskScore's `portfolio_hhi` is position concentration, not solvency |
| 48 | Cash-burn risk | 2 | **ABSENT** | flip | zero hits for `cash_runway` / `cash_burn`; **smallest honest producer**: an FCF leg in `ratios.py::compute_ratios:104` |
| 49 | Earnings-quality risk | 1 | **elsewhere** | flip | `normalized.py::accruals_ratio:62`; `earnings_quality.py::dechow_dichev_aq:118`. `accruals` is FQS's (`SUBSCORE_FACTORS:399`) — FundamentalScore owns it |
| 50 | Revenue concentration risk | 1 | **ABSENT** | flip | zero hits for `revenue_share`; no segment-revenue store; **smallest honest producer**: an HHI over segment revenue in `ratios.py` |
| 51 | Geographic concentration | 1 | **ABSENT** | flip | zero hits; the same missing segment store |
| 52 | Currency risk | 2 | **ABSENT** | flip | no FX-exposure or FX-VaR producer. `dataflows/fx.py::get_fx_snapshot:24` is a **data source** (`agents/utils/analysis_tools.py::get_fx_snapshot:11426`), not an exposure producer |
| 53 | Interest-rate risk | 3 | PARTIAL | flip | `fixed_income.py::macaulay_duration:69`, `modified_duration:103`, `bond_convexity:141` — bond duration, **not** an equity rate beta |
| 54 | Commodity/input-cost risk | 1 | **ABSENT** | flip | no commodity-beta producer; `sector_drivers.py:53` maps sectors to commodity drivers; **smallest honest producer**: `statistical.py::ols_factors:353` with a commodity series |
| 55 | Event concentration | 1 | built | flip | `catalyst.py::build_catalyst_snapshot:219`; `events.py::position_mult_by_side:37`; engine rows `catalyst_scale` / `event_hard_block` (`risk_score.py::COMPONENTS`) |
| 56 | Risk-adjusted momentum | 2 | built | no flip | `factors.py::vol_adjusted_momentum:46`; `factors.py::momentum:24` |
| 57 | Volatility-adjusted return | 1 | built | no flip | `factors.py::vol_adjusted_momentum:46` |
| 58 | Tail-adjusted return | 1 | **ABSENT** | no flip | no `ExpectedReturn / CVaR` producer; **smallest honest producer**: `evaluate.py::total_return:53` over `book_risk.py::cvar:18` |
| 59 | Drawdown-adjusted return | 1 | built | no flip | `evaluate.py::calmar_ratio:1018` (annualized return / MDD) |
| 60 | Composite risk score | 11 | built | flip | `risk_score.py::risk_score:516` — the library's own `100 × (1 - RiskRaw)` **is** the engine's inversion. Its eight normalised components are not the owner's eight categories (§8.3 d6) |
| 61 | Recommended normalization methods | 5 | built | neutral | `factors.py::percentile_rank:59`, `z_score:68`; `normalized.py::percentile_hist:53`; `score_engine.py::align:69` |
| 62 | Risk-direction transformation | 2 | built | flip | `score_engine.py::align:69` (`direction="lower_better"` → `1 - frac`, `score_engine.py:109-112`); `risk_score.py::_pin:418` (`PIN_NEGATE` / `PIN_ABS`) |
| 63 | Nonlinear risk penalties | 3 | **ABSENT** | flip | no `x ** γ` producer — `grep -E "def .*penalt"` returns only `events.py::catalyst_risk_penalty:63` and `portfolio.py::correlation_penalty:274`, neither a power. **smallest honest producer**: a `gamma` exponent inside `score_engine.py::align:69` |
| 64 | Threshold risk penalty | 1 | built | flip | `score_engine.py::align:69`'s clamped ramp is the same `max(0, (x - T)/(U - T))` shape (`lo` → 0, `hi` → 100, clamped) |
| 65 | Hard risk gate | 1 | built | flip | `risk_governor.py::govern:40`; `book_risk.py::drawdown_gate:210`; `GATE_PRECEDENCE` (`../TradingExecution/signald/contracts.py:42`) |
| 66 | Risk regime multiplier | 3 | built | flip | `regime_state.py::vol_cap_factor:169`, `regime_factor:191`; `risk_multiplier.py::combine:37`; `credit_spread.py::credit_stress_level:44` (`scale`) |
| 67 | Correlation-adjusted risk | 1 | PARTIAL | flip | `covariance_models.py::ledoit_wolf_shrink:81`; `portfolio.py::correlation_penalty:274`. **Gap:** the `λ Σ_{i≠j} w_i w_j ρ_ij σ_i σ_j` term |
| 68 | Liquidity-adjusted CVaR | 1 | **ABSENT** | flip | zero hits for `cvar_adj` / `liquidity_adjusted`; **smallest honest producer**: `book_risk.py::cvar:18` + `liquidity_risk.py::market_impact_slippage:243` summed in the tail leg |
| 69 | Total economic risk | 7 | PARTIAL | flip | `risk_score.py::risk_score:516` is the composite — over the owner's **eight** categories, not the library's six-bucket sum; the library's own §61 forbids the raw sum (§8.3 d7) |
| 70 | Suggested architecture for your RiskScore engine | 2 | PARTIAL | flip | the library recommends ~10 factors; the engine ships the owner's eight (`risk_score.py::CATEGORY_WEIGHTS:58`) with equal weights inside each category (`category_score:491`) |
| 71 | The most important distinction for your system | 0 | built | neutral | score ≠ gate: `risk_score.py::STATUS_ADVISORY:328`; `risk_governor.py::govern:40`; `GATE_PRECEDENCE` (`contracts.py:42`); the engine never imports `SCORE_BANDS` (`risk_score.py` docstring rule 6) |

**Counts: 46 built, 12 PARTIAL, 8 ABSENT, 5 elsewhere** (71 rows).

### 8.2 Not built — the backlog the library names

**Every ABSENT row, with the smallest honest producer.** None of these is a
defect in the engine; each is a quantity the library specifies and no module
computes.

| Library section | Quantity | Smallest honest producer |
| --- | --- | --- |
| §2.4-§2.5 | σ20/σ60 volatility ratio; `(σ_short - σ_long)/σ_long` expansion | a two-window ratio over `volatility_models.py::ewma_vol:397` or `evaluate.py::volatility:84`, in `volatility_models.py` |
| §3.3-§3.4 | downside / upside beta | `evaluate.py::beta:901` conditioned on `R_m < 0` / `> 0` |
| §4.5 | `CC = Σ_{i≠j} w_i w_j ρ_ij` correlation concentration | `covariance_models.py::ledoit_wolf_shrink:81` × position weights in `portfolio_optimizer.py` |
| §6.4 | Sterling ratio (return / average MDD) | the `evaluate.py::calmar_ratio:1018` shape over `evaluate.py::underwater_drawdowns:979` |
| §9.4-§9.5 | extreme-loss and crash frequency | a count over the `book_risk.py::simple_var:9` threshold |
| §10.1-§10.4 | downside frequency, large-loss frequency, average loss, worst loss | a counter beside `evaluate.py::downside_deviation:846` |
| §23 | momentum reversal `R_short - R_long` | `momentum.py::momentum_12_1:358` at two horizons |
| §33 | probability of hitting a stop; expected terminal loss | `book_risk.py::copula_scenarios:910` + a stop-path check |
| §34 | return-series `P(R < 0)` | a count in `evaluate.py` beside `downside_deviation:846` |
| §48 | cash runway; cash-flow deterioration | an FCF leg in `ratios.py::compute_ratios:104` |
| §50-§51 | revenue and geographic concentration (HHI over segment revenue) | the `liquidity_risk.py::ownership_hhi:130` formula over a segment-revenue store that does not exist |
| §52 | FX exposure / FX VaR | `dataflows/fx.py::get_fx_snapshot:24` fetches; nothing converts it to an exposure |
| §54 | commodity beta | `statistical.py::ols_factors:353` with a commodity series |
| §58 | tail-adjusted return (`ExpectedReturn / CVaR`) | `evaluate.py::total_return:53` over `book_risk.py::cvar:18` |
| §63 | nonlinear penalty `x ** γ`, γ > 1 | a `gamma` exponent inside `score_engine.py::align:69` |
| §68 | liquidity-adjusted CVaR (`CVaR + ExecutionCost_tail`) | `book_risk.py::cvar:18` + `liquidity_risk.py::market_impact_slippage:243` |

**Five sections are not this engine's to build.** §14 leverage, §15 distress,
§47 solvency and §49 accruals are `FundamentalScore`'s — FRS owns
`z`/`o`/`zmijewski_x`/`debt_to_equity`/`current`/`quick` and FQS owns `accruals`
(`factor_schema.py::SUBSCORE_FACTORS:399`, consumed by
`fundamental_score.py::risk_subscore:222`). §20 market-regime is `RegimeScore`'s
(`regime_score.py::RAMPS:91`). Re-deriving any of them inside `RiskScore` would
put one quantity into two engines, which master §2.1 forbids.

### 8.3 Library-internal defects

**Verified against the library text only — no code involved.** Each is a
contradiction or a mislabel *inside* `Strategies/scores/risk_score.md`.

**d1 — §5.2 carries two mutually exclusive drawdown definitions, and §5.3 is
false under one of them.** §5.2 offers both `DD_t = (P_t - M_t)/M_t` (≤ 0 below
the peak) and `DD_t = 1 - P_t/M_t` (≥ 0 below the peak), then §5.3 defines
`MDD = max_t DD_t`. Under the *first* convention every `DD_t ≤ 0` with
`DD_0 = 0`, so `max_t DD_t = 0` **always** — the maximum drawdown formula
returns "no drawdown" for any series. The second convention is the one that
works, and it is the one the code implements (`evaluate.py::max_drawdown:222`:
`dd = (peak - value)/peak`).

**d2 — §8.1 and §8.2 define one quantity twice, and the library says so.** §8.1
`ES_c = -E[R | R < Q_{1-c}(R)]`; §8.2 `CVaR_c = E[L | L > VaR_c]` — the text
itself concedes "often used interchangeably with ES". One number under two names,
both stated as a **positive** loss, yet the repo ships them as *different*
producers with the *opposite* sign (`book_risk.py::cvar:18` vs
`tail_risk.py::tail_risk:174`, both negative = loss) and the engine scores both.

**d3 — §2.2's `σ_down` is a semivariance, and §2.3 then promotes the ratio the
code explicitly warns against.** §2.2 is
`σ_down = sqrt((1/N) Σ min(R_t, 0)²)` — exactly
`volatility_models.py::semivariance:68`'s `RS⁻ = Σ min(r,0)²/n`, so its square is
the raw squared-return sum, not a variance of demeaned returns (note §2.1 uses
`1/(N-1)` while §2.2 uses `1/N`; the library never says why). §2.3's
`UDVR = σ_up/σ_down` is then `sqrt(RS⁺)/sqrt(RS⁻)` = the producer's
`asymmetry`, whose own docstring calls it "confounded with drift and partly
re-measures momentum" and names `rs_minus` as the persistent leg. The library's
§2.3 headline ("a lower downside component … indicates a more favorable
distribution") promotes the leg the producer says not to score.

**d4 — §26's HHI and the code's HHI are two scales under one name.** §26 gives
`HHI = Σ w_i²` over weights (0..1), while
`liquidity_risk.py::ownership_hhi:130` is documented "over ownership
percentages (0-10000)" and `risk_score.py::RAMPS` puts `portfolio_hhi` on
`(0.05, 0.50)`. The engine's row reads the *formula* over position weights and
labels it "HHI over position weights (sum w², 0..1)" — so a reader moving
between §26 and `ownership_hhi:130` changes scale by 10⁴ with no warning in
either.

**d5 — §20.4's stress composite contradicts §20's own opening rule.** §20.4
sums `Stress = w₁·VIX_Z + w₂·CreditSpread_Z + w₃·Corr_Z + w₄·Vol_Z` and then
says it "should probably feed your RegimeScore and RiskScore separately, rather
than duplicating the same metric" — the formula and the instruction cannot both
hold, and the code resolves it the second way (RegimeScore owns the VIX legs,
`regime_score.py::RAMPS:91`).

**d6 — §60's and §70's component lists are not the owner's eight categories.**
§60 names `R_vol, R_down, R_tail, R_liq, R_leverage, R_drawdown,
R_concentration, R_systemic`; §70 names ten factors adding Financial and Stress.
The engine ships the `market.md` eight — `volatility, tail, liquidity, gap,
correlation, concentration, drawdown, event`
(`risk_score.py::CATEGORY_WEIGHTS:58`) — so §60's list would drop `gap` and
`event` and add `leverage` and `systemic`, i.e. it is a different engine's
weight vector.

**d7 — §69's additive total contradicts §61.** §69 defines
`TotalRisk = MarketRisk + TailRisk + LiquidityRisk + FinancialRisk + EventRisk +
PortfolioRisk` over raw sub-sums, while §61 states "Do **not** directly average
raw volatility, beta, CVaR, drawdown, etc. Their scales are incompatible." The
library forbids in §61 what §69 does.

### 8.4 Contradictions between the library and the code

**The three conventions §0.3 records are the library's own, not the code's
invention.** Checked one at a time; each row names the library symbol and the
code symbol that disagree.

| Quantity | Library (`Strategies/scores/risk_score.md`) | Code | Mismatch |
| --- | --- | --- | --- |
| **CVaR / ES** | §7.1 `VaR_c = -Q_{1-c}(R)` and §8.1-§8.2 `ES_c = -E[R \| R<Q]`, `CVaR_c = E[L \| L>VaR_c]` — a **positive loss magnitude** | four producers, three conventions: `book_risk.py::cvar:18` **negative** ("negative = loss"), `book_risk.py::portfolio_cvar:59` negative via `cvar:18`, `book_risk.py::stress_loss:141` **positive**, `book_risk.py::min_cvar_weights:754` returns `"cvar": round(-cv, 6)` at `book_risk.py:839` **positive**, executor `signald/risk/tail.py::ESResult:56` a **fraction of equity** | §62's rule "CVaR ↑ → risk ↑" holds for the positive producers and **inverts** for `cvar:18`/`portfolio_cvar:59`: there a *less negative* CVaR is *more* risk. The engine pins the library's convention — `PIN_NEGATE` on `cvar`, `portfolio_cvar`, `extreme_quantile_es` (`risk_score.py::COMPONENTS`) |
| **Drawdown** | §5.2 both `(P_t - M_t)/M_t` (**negative**) and `1 - P_t/M_t` (**positive**); §5.3 `MDD = max_t DD_t`; §5.7 `CDD_q = E[DD \| DD > q]` (positive form only) | `evaluate.py::max_drawdown:222` and `book_risk.py::portfolio_drawdown:118` **positive**; `book_risk.py::cdar:217` positive (`D_t = (M_t - P_t)/M_t`); `regime_state.py::regime_drawdown:146` **negative** (`dd = closes[-1]/high - 1.0`, thresholds `DD_CORRECTION`/`DD_BEAR`/`DD_SEVERE`); executor `signald/engine.py:115` **negative** (`-(1.0 - equity/peak)`), emitted at `signald/risk/gate.py:865` | the library supplies both signs in one section; the code splits them across modules. `RiskScore` pins positive and reads **only** `book_context.py::measured_book_drawdown:102` (`PIN_DRAWDOWN`, `risk_score.py::COMPONENTS`) — the `regime_drawdown:146` number has the opposite sign for the same market |
| **Correlation cluster** | §4.5 `CC = Σ_{i≠j} w_i w_j ρ_ij`; §67 `Risk_corr = Σ w_i σ_i + λ Σ_{i≠j} w_i w_j ρ_ij σ_i σ_j` — a **ρ-weighted double sum**; §4.4 `ρ̄ = 2/(N(N-1)) Σ_{i<j} ρ_ij` | the engine's pinned quantity is `cluster_exposure_share` = `cluster_notional / portfolio_exposure` — `signald/risk/state.py::cluster_notional:109`, enforced at `signald/risk/gate.py::_correlation_stress:369` with `config.py::cluster_cap_pct:115`; the repo's nearest ρ producers are `portfolio.py::mean_correlation:252` (one name vs peers) and `hierarchical_risk_parity.py::_correlation_distance:50` | the library's quantity needs ρ; the code's has **no ρ term** and is a **notional share**. `PIN_CORRELATION` (`risk_score.py:52`) forbids printing it as a correlation coefficient; §4.4's exact all-pairs average has no producer either |
| **Semivariance unit** | §2.2 squared-return units (`1/N Σ min(R,0)²`); §2.3 the ratio `σ_up/σ_down` | `volatility_models.py::semivariance:68` returns `rs_minus`/`rs_plus`/`rv` (squared-return units) **and** `sqrt_rs_minus` (return units, comparable to `regime.py::realized_vol:39`) **and** `asymmetry` (the ratio) | one quantity as a variance, a volatility and a ratio; the engine scores `sqrt(RS⁻)` only, prints the raw sums beside it, and **fails** on a triple that violates `RS⁻ + RS⁺ = RV` (`risk_score.py::semivariance_leg:345`) |

**Two consequences for this document.** (a) The library's line references have
moved since §1/§3 were written: `book_risk.py::book_correlated_stress` is now
`:146` (was `:128`), `stress_loss:141` (was `:123`), `cdar:217` (was `:174`),
`extreme_quantile_var:560` (was `:451`), `min_cvar_weights:754` (was `:628`,
returning at `:839`), `portfolio_drawdown:118` (was `:100`),
`var_cvar_horizon:384` (was `:341`), and the `volatility_models` estimators are
now `garch11_fit:438` / `ewma_vol:397` / `parkinson_vol:155` /
`garman_klass_vol:185` / `yang_zhang_vol:288` (was `:226` / `:185` / `:48` /
`:78` / `:116`). The rows in §8.1 cite the current lines; §1 and §3 above are
left as written. (b) §3.3 records that `BookState.net_beta` has no producer —
still true for the executor field (`signald/risk/state.py:75` documents it as
unpopulated), but the repo now carries `book_risk.py::net_beta:177`, so the
smallest honest producer §4 asks for is a call to that function from the
executor's book builder rather than a new formula.

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

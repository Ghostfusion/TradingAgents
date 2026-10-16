# Momentum Screener — Design

Status: **designed, not built.** This pass changes no code. Every read the
screener consumes is built and green today — the eight-leg score
(`strategies/momentum_score.py`), the cross-sectional book
(`strategies/cross_section.py::momentum_book`), the liquidity gate
(`capital_income.passes_liq_screen`), the tail leg
(`graph/trading_graph.py::_precompute_risk_context`) and the measurement harness
(`scripts/score_panel.py`). What this document decides is the **screen stage**
over an eligible universe: the fields it publishes, the producer behind each one,
the gates it may apply, and — explicitly — the four things the source brief asks
for that this repo must not build. It follows the shape of its sibling
`docs/design_sector_rotation_screener.md`.

Source: the owner's pasted brief (2026-10-16, *"Momentum trading strategies:
formulas, screening rules, and Python implementation"*); the **owner-owned**
formula library `docs/scores/momentum_score.md` (§§1–§54); the engine's own
record `docs/scores/MomentumScore.md`; the measured panel evidence in
`docs/scores/MEASUREMENT_FINDINGS.md`; and the primary literature cited in §9.

**Owner-owned here — quoted, never edited:** `docs/scores/momentum_score.md`,
`docs/scores/MEASUREMENT_FINDINGS.md`, `docs/scores/ScoreUniverse.md`
(declared at `docs/MASTER_DESIGN.md:1034-1036`).

---

## 1. The one-paragraph takeaway

The momentum screener is a **screen stage over the momentum score this repo
already owns** — not a second momentum model. It builds an eligible universe
(size, liquidity, history, data quality), computes each name's `MomentumScore`
through the existing eight-leg engine **with a supplied reference cross-section**
(the engine's own §48 path, which until now only its tests exercised), ranks the
eligible names by that one composite, and publishes four fields per name beside
the components and the exclusion reason: `momentum_score`, `momentum_eligible`,
`momentum_regime`, `momentum_risk_flags`. It adds **no** weight vector, **no**
momentum producer, **no** tail estimator and **no** gate. Its status starts
`RESEARCH_ONLY`, exactly as the engine's does, and the ladder out of that status
is the existing WP-10 measurement (§7).

## 2. The brief, checked line by line

The brief is a vendor/pasted hypothesis, so it is a lead. Each load-bearing item
was checked against this repo's own producers and against primary sources
(§9); the verdicts are what the screener is allowed to use.

| Claim in the brief | Verdict | Why (evidence) |
| --- | --- | --- |
| Momentum is a *family* of measurable signals; keep raw signals separate from the final score | **ADOPT** | The engine already emits `components`, `legs` and `meta` beside `score`, and the meta is never folded in (MOM-3) — `strategies/momentum_score.py:644` |
| Cross-sectional vs time-series momentum are different questions | **ADOPT** | Both exist: `cross_section.momentum_book:398` (cross-sectional book) and `momentum.ts_momentum_weights:135` (MOP-style time-series weights) |
| 12−1 momentum = `P_(t−21)/P_(t−252) − 1` | **ADOPT**, convention pinned | Our one 12−1 producer is `momentum.momentum_12_1:395` (skip 21, window 252). The convention is Kenneth French's own — prior **(2-12)** return, "a price for the end of month t-13 and a good return for t-2" — i.e. the *formation window is 231 sessions (11 months)*, and the "12" is the reference point, not the length |
| "Document whether you use 252 versus 253 observations and whether prices are adjusted" | **ADOPT** | §5.6 pins it: `min_history = 253` sessions, the realized count printed, and the price basis named |
| The §4 composite: `0.30·Rank(12−1) + 0.25·Rank(6M) + 0.20·Rank(3M) + 0.15·Rank(MOM_adj) + 0.10·Rank(RS_6M)` | **DECLINE — it would be a third momentum weight vector** | `LEG_WEIGHTS` is owner-ratified (2026-09-27; `momentum_score.py:89`, `MomentumScore.md` §2.1) and `technical_score.CATEGORY_WEIGHTS` is the second, which MOM-4 declined to re-point. The brief's own §4 calls its weights "an illustrative baseline" that "should be tested for redundancy" |
| Tail risk as `cvar_95_daily_252 ≤ 4 %` | **DECLINE — a second tail estimator, and the brief agrees** | Its own §7: *"If your existing risk engine uses 320 bars and the 15 worst returns, that is a different estimator and should remain separately identified rather than being silently substituted."* Ours is `book_risk.cvar` over `_pit_closes` simple returns — magnitude in `single_cvar`, window in `single_cvar_n`, 250-observation floor (`graph/trading_graph.py:2081`) |
| Liquidity: 20-day average dollar volume ≥ $10 M | **DECLINE the second window** | `capital_income.adtv_dollar:74` is the repo's one ADTV producer (63-session "3-month" default) and `passes_liq_screen:93` its one comparator. The floors stay parameters printed in the basis line; the declared constants (`MIN_MARKET_CAP = 250e6`, `MIN_ADTV_DOLLARS = 1e6`, `capital_income.py:23`) are left untouched |
| RSI(14) prefer 50–75, "use as a feature, not a rule" | **DECLINE — nothing to build** | The engine deliberately scores no RSI: MOM-5 records RSI as §53's *Overextension* group, not one of the eight §54 legs, and the panel measured the oscillator cluster's redundancy (`rsi|stoch_k` 0.816 — `MEASUREMENT_FINDINGS.md` §2). RSI already belongs to `TechnicalScore` |
| Relative volume: "report it; optionally require above 0.8" | **ADOPT the report, DECLINE the gate** | `rvol` is already the V leg's own member (`momentum.rvol:57`); gating on it would score one reading twice, and volume as *unconditional* confirmation is not supported — high-volume winners subsequently underperform (Lee & Swaminathan 2000) |
| "Compare within sectors as well as across the market" | **DECLINE the neutral rank; ADOPT the sector read** | `cross_section.industry_neutral_z:111` demeans a cross-section by a caller-supplied group and is wired to no RS read; the engine declined it in writing (MOM-6, `DECLINED_SUB_ITEMS["industry_relative"]`), and the sector read it wants already exists as the R leg's member `relative_strength.relative_strength_vs_sector:276`. Sector *concentration* is reported (§5.5), never silently neutralised |
| A composite score must not override a hard risk gate or a missing-data condition | **ADOPT** | Master rule 17, and `score_engine.align` returns `None` — never a neutral 50 — for an absent input (`strategies/score_engine.py:69`) |
| Test each feature's incremental value; backtest the complete rule with costs | **ADOPT** | §7: the WP-10 panel already computes IC / rank IC / ICIR / decile spread / turnover plus purged CPCV, DSR, PBO, Reality Check and SPA |

Two defects in the brief's own code, recorded because we build the same field and
must not copy them (a pasted implementation is a hypothesis too):

1. `df[col].rank(pct=True, ascending=True) * 100` carries the comment *"A
   percentile rank of 1 is best"*. `pct=True` is 0–1, and the `× 100` makes
   **100** best. The screener's rank column is produced by
   `factors.percentile_rank:59` (the repo's tie-aware percentile producer, the
   same one the screener's `Qual` column already reads).
2. `rank_momentum_universe`'s prose says *"Missing indicators remain missing
   rather than silently receiving a zero score"*, while its code does
   `df[col].fillna(0)` and divides by `available_weight` — publishing a score for
   an incomplete row. We take the prose: a member that could not be measured
   leaves its leg's denominator, and a name whose required components are absent
   is **ineligible with its reason**, never renormalised into a comparable score.

## 3. Where it maps onto the existing repo (reuse, don't rebuild)

Rule 11(c) runs first: check for the producer. Every stage of the brief's §3
architecture already has one.

| Stage (brief §3) | Existing surface | What the screener does with it |
| --- | --- | --- |
| 1. Universe | `scripts/value_screener.py --universe` modes (`tickers`, `eodhd-us`, `moomoo-screen`, `top-losers`, `heat-proxy`); `dataflows/sp500_universe.py::fetch_sp500_universe:120` for the GICS→sector map | Calls nothing new: the screener is a **`--scan` mode inside that script**, so it inherits the universe plumbing and the market-cap fields it already reads |
| 1. Data quality | `graph/trading_graph.py::_pit_closes:1566` → `analysis_tools._ohlcv:229` → `dataflows/stockstats_utils.py::load_ohlcv:274` (PIT-filtered, per-`(ticker, days)` cached) | The screener's bars are the same series the engine's leaf uses — no second fetch path |
| 2. Raw features | `strategies/momentum_score.py::COMPONENTS` — 41 members, each naming its `strategies/*` producer and its library section | **Read, never re-derived.** The screener assembles the member vector through the engine's own component builder |
| 3. Eligibility | `capital_income.passes_liq_screen:93` + `adtv_dollar:74`; the T leg's `sma_stack` / `ma_distance` members | §5.3 — thresholds are parameters, printed |
| 4. Ranking | `factors.percentile_rank:59`; `momentum_score.normalize_component:477` (§48 z / §49 percentile) | §5.4 — one rank column over the eligible cross-section |
| 5. Outputs | `scripts/value_screener.py`'s row renderer and two-stage gate (`_compute_scan_row:586`) | One row per name, the brief's four fields beside the components |
| Cross-sectional book (advisory) | `cross_section.momentum_book:398`, reachable as the `get_cross_section_momentum` tool (`agents/utils/analysis_tools.py:6056`, bound to the market analyst at `agents/toolsets.py:54`) | Left alone: it is a risk-adjusted long/short **book** over the names you hand it, not a screen with eligibility |
| Tail risk | `book_risk.cvar:18` via `_precompute_risk_context`; window keys published since `execution_contract.py:57` | Read as `single_cvar` / `single_cvar_n` |
| Measurement | `scripts/score_panel.py` (WP-10 panel + factor statistics + redundancy matrix), `scripts/score_panel_eval.py`, `alpha_health.score_evaluation_rows` | §7 — the promotion evidence, not a new harness |

## 4. Scope

```
universe ──► data quality ──► member vector ──► eligibility ──► rank ──► row
 (value_screener   (_pit_closes,     (momentum_score      (size/liquidity/   (percentile   (score,
  --universe)       PIT filter)       COMPONENTS, 41)      history/D-leg)     rank)        eligibility,
                                                                                          regime, flags)
```

**Non-goals, stated so they are not quietly added later:**

- It never places, sizes or blocks an order. It is not a gate, and nothing in it
  enters `TradeScore` (`MomentumScore` is deliberately outside `COMPOSITE_ENGINES`
  — `MomentumScore.md` §5).
- It is not market breadth, and its `n` is not the market: the panel is whatever
  the caller could see, and `n` travels with every read (the precedent is
  `momentum_book`'s own docstring).
- It declares no threshold, window or limit that the owner already set: the tail
  limit read is the configured `risk_standalone_cvar_limit_pct`.
- It is off by default, behind the engine's own `enable_momentum_score`
  (`default_config.py::SHIPPED_DEFAULTS`, shipped `False`) — no new gate key.

## 5. The screener spec

### 5.1 The published fields (one row per name)

| Field | Meaning | Producer | Absent when |
| --- | --- | --- | --- |
| `momentum_score` | the 0–100 composite, the engine's `score` | `momentum_score.momentum_score:644` over `LEG_WEIGHTS` | the composite is below `COMPOSITE_MIN_COVERAGE = 3` legs — withheld with its reason, never 0 |
| `momentum_eligible` | whether every §5.3 rule passed | this stage (booleans only, from §5.3's producers) | never — it is a verdict, and its reason list is published beside it |
| `momentum_regime` | `positive` / `mixed` / `negative`, per name | the T leg's own members `ma_distance` + `sma_stack` (§5.3) | `mixed` when either member is absent — *not* `positive` (fail closed) |
| `momentum_risk_flags` | the closed set in §5.5 | existing readings, named per flag | a flag whose reading is absent is reported as `unmeasured`, never omitted |
| `momentum_rank` | tie-aware percentile of `momentum_score` over the **eligible** set | `factors.percentile_rank:59` | the name is ineligible (rank is `None`, not 0) |
| `momentum_exclusion` | the first failed §5.3 rule, named | this stage | the name is eligible |
| the 41 members, the eight leg scores, `coverage`, the §§50–52 meta | component-level audit trail | the engine's own `components` / `legs` / `meta` | a member that could not measure is listed in `absent` |

The four names the brief proposes (`momentum_score`, `momentum_eligible`,
`momentum_regime`, `momentum_risk_flags`) are kept as written; `momentum_rank`
and `momentum_exclusion` are added because the brief's `screen_rank` is the
screen stage's own output, not the engine's.

### 5.2 The score: one producer, and the population it standardises over

The engine is per-name and, with no universe, maps members through their own
declared bands and ramps (`score_engine.align`). The library's §48/§49 forms are
both **cross-sectional** (`normalize_component`'s own docstring says so), and the
engine already exposes the hook: `momentum_score(values, reference={member:
cross_section})` normalises a member by §48 over the supplied population and
takes **the last entry as the name under test**.

**Decision: the screener is the reference path's first production consumer.** It
passes, for each member, the column of that member's values across the eligible
universe with the name appended. Consequences, all of them fail-closed:

- A reference column with fewer than two finite values, or with zero spread,
  yields `None` for that member (`normalize_component` — **never 50**), so the
  member leaves its leg's denominator and the leg's coverage says so.
- A member the screener has no cross-section for falls back to its declared
  ramp, and the row records **which basis each member used**. A leg mixing
  reference-normalised and ramp-mapped members is then visible in the output
  rather than silent.
- The bar-level extraction stays one function: the 41-member vector is assembled
  by the builder the engine's leaf already calls
  (`agents/utils/analysis_tools.py::_momentum_components:6676`), refactored to a
  series-taking core with the ticker-fetching leaf as its caller. Two assemblies
  of the same members would be the second producer this design exists to avoid.

### 5.3 Eligibility (the brief's stage 3), rule by rule

Every rule reads a producer that already exists; a missing input **fails the
rule** and names itself.

| # | Rule | Producer | Missing value |
| --- | --- | --- | --- |
| 1 | size ≥ `--min-market-cap` (default 1e9) | the dated market-cap field the screener already reads (`scripts/value_screener.py:800`) | ineligible, reason `market_cap_unmeasured` |
| 2 | ADTV ≥ `--min-adtv` (default 1e7) over the producer's own 63-session window | `capital_income.adtv_dollar:74` compared by `passes_liq_screen:93` | ineligible, reason `adtv_unmeasured` |
| 3 | history ≥ 253 sessions of PIT bars | `_pit_closes` → `load_ohlcv:274` | ineligible, reason `insufficient_history` |
| 4 | the 12−1 return is positive (the time-series direction overlay) | `momentum.momentum_12_1:395` | ineligible, reason `mom_12_1_unmeasured` |
| 5 | trend: `ma_distance > 0` **and** `sma_stack == 1` — the brief's `P > SMA50 > SMA200`, expressed through the engine's own two T members | `technical_factors.sma_legs:1050`, `swing.trend_architecture:76` (via the T leg) | ineligible, reason `trend_unmeasured` |
| 6 | the composite cleared its floor and every component rules 1–5 read is present in `components` | the engine's `withheld` / `absent` | ineligible, reason `components_incomplete` |
| 7 | `single_cvar ≤ risk_standalone_cvar_limit_pct` (the owner's configured limit) | `graph/trading_graph.py:2081`, window in `single_cvar_n` | ineligible, reason `tail_unmeasured` |

Two rules the brief asks for are deliberately **not** here, each with its
falsifier:

- **`mom_6m > 0` is not a second gate.** It is a nested window of the same
  quantity rule 4 already reads, and the brief's own §7.6 asks for each feature's
  *incremental* value. It is published as a member; it becomes a gate only if the
  panel measures that adding it widens the forward-return spread (§7).
- **`rvol ≥ 0.8` is not a gate** — §2.
- **No sector-neutral rank** — §2; sector concentration is reported instead
  (§5.5).

Rule 5 is deliberately expressible as `momentum_regime == "positive"`: the gate
is a projection of a published field, so a screened row can never disagree with
the regime it prints.

### 5.4 The rank

One rank column, over the **eligible** cross-section only, from
`factors.percentile_rank` (0–100, tie-aware, the screener's existing `Qual`
convention). Ineligible names carry `None`, never a rank from a lower population:
two runs with different universes are then not silently comparable, and `n` is
printed in the basis line so a rank over nine names cannot be read as a decile of
the market.

### 5.5 Risk flags (the brief's `momentum_risk_flags`)

| Flag | Reading | Threshold |
| --- | --- | --- |
| `tail_over_limit` | `single_cvar` / `single_cvar_n` | > the configured standalone CVaR limit |
| `vol_high` | the D leg's `realized_vol` member | above the engine's own declared ramp edge (`RAMPS["realized_vol"]`, `0.15 → 0.80`) |
| `extended` | the B leg's `dist_from_high` member | within the engine's declared near-high ramp — *reported, never a gate* (the brief itself says a strong trend can stay extended) |
| `sector_concentration` | the sector counts of the **eligible** set, from `sp500_universe.fetch_sp500_universe`'s GICS map | the largest sector above a printed share — the anti-concentration read that replaces the declined neutral rank |
| `thin_history` | the realized session count | < 2× the 12−1 requirement, i.e. the name passes rule 3 but not by much |

### 5.6 The basis line

Every row (and the run header) prints: the gate that let the mode run
(`enable_momentum_score`), the pinned floors actually used (`--min-market-cap`,
`--min-adtv`), the ADTV window (63 sessions), `min_history = 253`, the price
basis the bars came from, the CVaR limit read, the normalization method per
member, the universe source and `n`, and the engine's `status`
(`RESEARCH_ONLY`). The brief's "data freshness" output is this line plus the last
bar's date, which `_pit_closes` already fixes to the run's own trade date.

## 6. Data feasibility, and the four corners

- **Bars.** The screener reuses `_pit_closes` (320 bars, PIT-filtered,
  per-`(ticker, days)` cached) so a name's return series is the same one its
  CVaR was measured over. The 250-observation floor on the tail leg
  (`_cvar_min_observations:1545`) is stricter than rule 3's 253-session history
  rule, so a rule-3-eligible name is never tail-ineligible by construction — the
  two floors are stated in the basis line so the relationship is visible.
- **Market capitalisation** comes from a dated fundamentals snapshot (rule 1's
  producer), never from a share count times today's price: the brief's own §6
  warns about that, and the repo's fail-closed rule agrees — an unmeasured cap is
  a refusal, not a guess.
- **Adjustment basis.** The bars are one consistent close series per name; the
  repo's own caliber read is `dataflows/market_router.py::price_caliber_for:112`.
  A total-return vs price-return distinction is *not* re-derived here: if the two
  bases must ever be compared, that is a `definition_mismatch`, not a
  subtraction.
- **Named gap — survivorship.** The panel and the universe both see the names
  that are listable *now*; a delisted name's history is missing unless the
  EODHD delisted feed is bought (a standing owner item). Every rank this screener
  prints inherits that bias, and the basis line says so.

## 7. Verification: what would falsify this design

Nothing here is promoted out of `RESEARCH_ONLY` by argument. The ladder is the
WP-10 one the engines already use, and the harness exists
(`scripts/score_panel.py` — one cross-sectional snapshot per date under
`data_cache_dir/panels/`, SEC EDGAR XBRL fundamentals read point-in-time, the
technical leg from each name's own bars; `score_panel_eval.py` for the
statistics).

1. **Forward-return test.** `MomentumScore`'s rank IC / ICIR / decile spread /
   turnover against forward 21-, 63- and 126-session returns, with the
   multiple-testing machinery already wired (`evaluate.purged_cpcv_splits`,
   `deflated_sharpe`, `pbo_flag`, `reality_check`, `spa`).
2. **Incremental-value ladder** (the brief's §7.6, and the repo is part-way
   there): 12−1 alone → + trend → + relative strength → + volatility adjustment
   → the full composite, one addition at a time.
3. **The two gating falsifiers.** If `mom_6m > 0` widens the spread, add it; if
   the sector-neutral rank beats the market-wide rank on the panel, revisit §2's
   decline — both are measurements, not opinions.
4. **The reuse falsifier.** If the reference-normalised path does not beat the
   ramp-mapped path on the same panel, the screener falls back to the declared
   ramps and §5.2's decision is recorded as refuted.

## 8. Honest disagreements with the source brief

| The brief says | This repo says |
| --- | --- |
| Build a five-component percentile composite with weights 0.30/0.25/0.20/0.15/0.10 | The repo's vector is owner-ratified and the brief's own text calls its weights illustrative; a third momentum vector would break master rule 3 and rule 8 (one producer, one number) |
| Measure `cvar_95_daily_252` at a 4 % threshold | The brief's §7 itself warns against substituting an estimator; ours publishes its window (`single_cvar_n`) beside the value and gates at the configured limit |
| Require 20-day ADV ≥ $10 M | The repo's one ADTV producer is 63-session; a second window would be a second producer for one number |
| Neutralise ranks within sectors | The sector read already exists as the R leg's member; neutralising the *rank* silently changes the population a rank is defined over, so concentration is reported instead |
| The brief's citations | Its own links are `images.openai.com` static image paths, not sources — no claim was taken on their authority. Every load-bearing claim above was re-grounded on the primary sources in §9 or on this repo's measured panel |

## 9. Sources

Primary literature, checked before any of it was written into a decision
(`[verified]` = the DOI/abstract or the publisher's own construction page was
read; `[reported]` = title and venue seen only inside a third party's reference
list, so treated as a lead, not a fact):

- Jegadeesh, N. & Titman, S. (1993). *Returns to Buying Winners and Selling
  Losers: Implications for Stock Market Efficiency.* Journal of Finance 48(1),
  65–91. doi:10.1111/j.1540-6261.1993.tb04702.x `[verified]` — the formation
  horizon and the ranking-by-past-return construction.
- Jegadeesh, N. (1990). *Evidence of Predictable Behavior of Security Returns.*
  Journal of Finance 45(3). doi:10.1111/j.1540-6261.1990.tb05110.x `[verified]` —
  the short-horizon reversal result the skip-month exists for. Companion:
  Lehmann (1990), *Fads, Martingales, and Market Efficiency*, QJE `[reported]`.
- French, K. R. *Detail for Monthly Momentum Factor (Mom)*, Data Library
  construction page `[verified]` — the 12−1 convention in the publisher's own
  words: a prior **(2-12)** return, formed at the end of t-1, requiring a price at
  the end of t-13 and a good return for t-2.
- Moskowitz, T., Ooi, Y. H. & Pedersen, L. H. (2012). *Time series momentum.*
  Journal of Financial Economics 104(2), 228–250.
  doi:10.1016/j.jfineco.2011.11.003 `[verified]` — the time-series sign overlay
  behind §5.3 rule 4.
- Barroso, P. & Santa-Clara, P. (2015). *Momentum has its moments.* Journal of
  Financial Economics 116(1), 111–120 (SSRN 2041429) `[verified]` — realised
  volatility as the thing that scales momentum's risk.
- Daniel, K. & Moskowitz, T. (2016). *Momentum crashes.* Journal of Financial
  Economics 122(2), 221–247. doi:10.1016/j.jfineco.2015.12.002 `[verified]` — why
  a momentum screen needs its tail leg rather than only its ranking.
- Blitz, D., Huij, J. & Martens, M. (2011). *Residual momentum.* Journal of
  Empirical Finance 18(3), 506–521. doi:10.1016/j.jempfin.2011.01.003 `[verified]`
  — the residual/β-adjusted variant; relevant here only as the reason
  `cross_section.residualize_returns:223` exists and is *not* promoted into the
  screen (it needs a market model per name, a different design).
- Lee, C. M. C. & Swaminathan, B. (2000). *Price Momentum and Trading Volume.*
  Journal of Finance 55(5), 2017–2069. doi:10.1111/0022-1082.00280 `[verified]` —
  volume is not unconditional confirmation (§2).
- Moreira, A. & Muir, T. (2017). *Volatility-Managed Portfolios.* Journal of
  Finance 72(4), 1611–1644. doi:10.1111/jofi.12513 `[verified]` — the
  vol-scaling result behind treating the volatility-adjusted leg as a *score*
  input rather than a sizing rule.
- Moskowitz, T. & Grinblatt, M. (1999). *Do Industries Explain Momentum?*
  Journal of Finance 54(4), 1249–1290 `[reported]` — industry momentum; the
  reason §5.5 reports sector concentration instead of ignoring it.
- Sullivan, R., Timmermann, A. & White, H. (1999). *Data-Snooping, Technical
  Trading Rule Performance, and the Bootstrap.* Journal of Finance 54(5),
  1647–1691 `[verified]`; and Brock, W., Lakonishok, J. & LeBaron, B. (1992),
  Journal of Finance 47(5), 1731–1764 `[reported]` — the reason a
  moving-average/trend rule is a *filter hypothesis* here, tested on the panel,
  never adopted on its chart reputation.
- Wilder, J. W. (1978). *New Concepts in Technical Trading Systems* `[reported]` —
  RSI's original definition; cited only to record that the screener does not
  score it (§2).
- *Momentum: what do we know 30 years after Jegadeesh and Titman's seminal
  paper?* Financial Markets and Portfolio Management 37(1) (2023).
  doi:10.1007/s11408-022-00417-8 `[verified]` — the survey used to check that
  12−1 and the cross-sectional/time-series split are the current consensus, not a
  single paper's idiosyncrasy.
- Faber, M. (2007). *A Quantitative Approach to Tactical Asset Allocation*
  `[reported]` — the trend-filter tradition; recorded, not adopted as a gate.

Repo sources of record, read for this document: `docs/scores/momentum_score.md`
(owner library, §§1–54), `docs/scores/MomentumScore.md` (the engine's own record:
legs, weights, normalization, the MOM-5 redundancy audit, the written declines),
`docs/scores/MEASUREMENT_FINDINGS.md` (the measured panel IC/redundancy tables),
`docs/scores/ScoreUniverse.md` (§8 Q6 ownership split), `Strategies/scan.md` and
`Strategies/momentum_day_trading.md` (the day-trade `--scan momentum` mode this
design must not be confused with), `docs/design_sector_rotation_screener.md` (the
sibling screen), and `docs/design_metric_authority_registry.md` (one canonical
producer per measured metric).

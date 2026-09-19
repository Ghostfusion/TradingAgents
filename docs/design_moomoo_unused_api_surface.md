# Design + implementation: the unused moomoo OpenAPI surface

State 2026-09-18. Sources: the installed `moomoo` SDK (**v10.10.7008**, introspected
directly — every signature and docstring read from the package, not from a web page), and
**live calls against OpenD** on `127.0.0.1:11111` on 2026-09-18. **No code changed by this
document.**

Companion to `docs/design_webull_data_provider.md` (the same shape: a vendor capability read
mapped onto the repo's existing seams, with a phased plan and the constraints that decide it).

---

## Verdict

The repo uses **31 of `OpenQuoteContext`'s 166 public callables**. Of the **103 unused data
methods**, four are worth taking and one of those is worth taking first:

| | Method | Why it wins |
|---|---|---|
| **P0** | `get_history_kl_quota` | The repo documents the K-line quota as *"the screener's bottleneck"*; this is the live read that lets a run warn or refuse **before** exhausting it. Smallest possible change, purely protective. |
| **P1** | `get_market_snapshot` | **142 columns for a whole batch of symbols in one call**, including the valuation block, the pre/after/overnight session families, short-interest fields and ETF NAV/premium. The repo assembles this from four-plus vendors, one symbol at a time. |
| **P2** | `get_option_underlying_overview` + `get_option_underlying_his_volatility` | Batch **IV rank / IV percentile / HV**, and a 251-row **IV-and-HV time series**. Turns the variance risk premium from *"asserted, not quantified"* into a measurement. |
| **P3** | `get_valuation_detail` + `get_research_morningstar_report` | A **valuation percentile**, a **peer/industry distribution**, and an **independent fair value**. The docs currently record that no peer-multiple table exists. |

Everything else in the unused surface is either out of scope (trade contexts, warrants, sports
event contracts), already correct as documented (the buyback limitation), or gated behind a
subscription rather than absent (order book, ticker, RT data).

---

## What the scan covered

| Measure | Count |
|---|---|
| Public callables on `OpenQuoteContext` | **166** |
| Called by this repo | **31** |
| Lifecycle / infrastructure (subscribe, close, handlers, connection ids) | **32** |
| **Unused data methods** | **103** |
| Read individually (signature + docstring) | 103 / 103 |
| Live-probed against OpenD | ~35 |

The used set was extracted from the tree, not from memory: every `ctx.<name>` reference across
the 78 files that mention moomoo. The single SDK seam is
`tradingagents/dataflows/moomoo.py`; the other files are its tests.

Out of scope by construction: `OpenSecTradeContext`, `OpenCryptoTradeContext`,
`OpenFutureTradeContext`. This project is analysis-only with an external executor
(`TradingExecution`), so no order, account or position endpoint is applicable.

---

## Verified live against OpenD (2026-09-18)

Every number below came back from a real call. Where a method failed, the failure is recorded
with its exact message, because an entitlement wall and an absent feature close differently.

### Tier 1 — fills a real gap

#### 1. `get_market_snapshot(code_list)` — a 142-column batch quote

```python
ret, snap = ctx.get_market_snapshot(['US.AAPL', 'US.MSFT'])   # shape (2, 142)
```

One call returns, per symbol:

| family | fields |
|---|---|
| valuation | `pe_ratio`, `pe_ttm_ratio`, `pb_ratio`, `ey_ratio`, `net_profit`, `net_asset`, `earning_per_share`, `net_asset_per_share` |
| shares / cap | `issued_shares`, `outstanding_shares`, `total_market_val`, `circular_market_val` |
| dividends | `dividend_ttm`, `dividend_ratio_ttm`, `dividend_lfy`, `dividend_lfy_ratio` |
| **pre / after / overnight** | `pre_price`, `pre_change_rate`, `pre_volume`, `pre_turnover`, `after_price`, `after_change_rate`, `overnight_price`, `overnight_change_rate` |
| liquidity | `turnover_rate`, `volume_ratio`, `bid_ask_ratio`, `amplitude`, `avg_price`, `price_spread` |
| 52w / history | `highest52weeks_price`, `lowest52weeks_price`, `highest_history_price`, `lowest_history_price` |
| short | `enable_short_sell`, `short_sell_rate`, `short_available_volume`, `mortgage_ratio` |
| ETF | `trust_netAssetValue`, `trust_premium`, `trust_aum`, `trust_dividend_yield`, `trust_assetClass` |
| option greeks | `option_implied_volatility`, `option_delta` / `gamma` / `vega` / `theta` / `rho`, `option_open_interest` |
| index / plate breadth | `index_raise_count`, `index_fall_count`, `plate_raise_count`, `plate_fall_count` |

Measured values (2026-09-18):

```
US.AAPL  last 336.13  pe_ttm 38.547  pb 45.626  ey_ratio 1.183  dividend_ratio_ttm 0.31
         pre_price 337.97  after_price 334.875  overnight_price 337.19
         total_market_val 4,905,541,723,400  issued_shares 14,594,180,000
US.SPY   trust_netAssetValue 769.35  trust_premium -0.995
```

**Batching is real**: 50 and 120 distinct symbols returned in one call each, all rows populated.

**⚠ The call is all-or-nothing.** A single unknown, renamed or OTC symbol fails the *entire*
call, and the error names only the first offender:

```
requested 100 -> ret=-1  "Unknown stock. SQ"          # Block renamed SQ -> XYZ
requested  50 -> ret=-1  "US OTC market quote is not available for SSLZY"
```

Both were hit live. Any caller must pre-validate and chunk; the repo already owns both
mechanisms (`get_code_change` for renames, the NYSE/Nasdaq exchange gate for OTC —
`get_exchange_moomoo`, `moomoo.py:2206`).

#### 2. `get_option_underlying_overview(code_list)` — batch IV rank, up to 500 symbols

```
code      iv      iv_rank  iv_percentile  hv_30d  hv_30d_percentile  call_volume  put_volume
US.AAPL  24.466   33.837        14.285    22.447       39.285           939,497     583,410
US.NVDA  34.691    0.591         0.396    44.643       89.285         1,807,630     928,926
US.TSLA  45.062   15.414        11.507    48.229       58.333         2,234,591   1,527,499
```

plus `call_open_interest` / `put_open_interest`. IV rank and IV percentile for a **batch**,
where `strategies/options_surface.py::iv_percentile` (`:15`) computes it per name from a
chain. And `iv − hv_30d` **is** the variance risk premium that
`strategies/options_surface.py::volatility_risk_premium` (`:65`) already knows how to consume.

#### 3. `get_option_underlying_his_volatility(code)` — 251 rows of IV **and** HV history

Columns `time`, `timestamp`, `iv`, `hv`, `underlying_price`; 251 rows returned. A genuine
**time series**, so IV rank over any window, the VRP series, and an event-vol study around
earnings all become measurable. The repo has no IV history source at all.

#### 4. `get_research_morningstar_report(code)` — an independent fair value

```
star_rating 2   fair_value 290.0   economic_moat Wide   uncertainty Medium
rating_type QUALITATIVE
```

AAPL traded 336.13 against Morningstar's 290. This is the external anchor the recorded DCF
debate never had — plus `economic_moat_label` and `uncertainty_label`, two qualitative
dimensions with no current source.

#### 5. `get_valuation_detail(code)` — valuation vs its own history, the market, and its industry

```
valuation_type PE
trend:              current 38.547  average 35.955  avg-1sd 33.693  avg+1sd 38.216
                    valuation_percentile 86.454   forward 36.141
market_distribution: histogram over PE bands
plate_distribution:  plate_average_value 38.544  plate_ranking 3
profit_growth_rate:  financial_ttm_multiple 1.361  market_cap_multiple 1.753
                     "Slightly Overvalued: 5-year market cap growth slightly outpaced net income"
```

A **valuation percentile** and a **peer/industry distribution** — the two things the changelog
records as missing (*"no peer-multiple table, so no 'cheap vs peers' claim can be evidenced
from a comp set"*).

#### 6. `get_rating_change(market)` / `get_research_rating_summary(code)` — direct revisions

`get_rating_change` (US) returned 10 rows of `rating`, `last_rating`, `target_price`,
`last_target_price`, `change_type`, `institution_name`, `recommendation_date`.
`get_research_rating_summary` returns `{next_key, inst_rating_summary_list}`.
`strategies/analyst_revisions.py` uses yfinance upgrades/downgrades as a **proxy**; this is
the direct source, with target prices.

#### 7. `get_daily_short_volume(code)` — US/HK daily short volume

`total_shares_short`, **`nasdaq_shares_short`** / **`nyse_shares_short`** (the exchange split),
`short_percent`, `volume`, `close_price`, `daily_trade_avg_ratio`. The repo sources this from
FINRA via Massive today.

#### 8. Ownership depth

| method | verified payload |
|---|---|
| `get_shareholders_overview(code)` | `main_holder` + `holder_type` + `holding_period` in one request (`period_id=0`) |
| `get_insider_holder_list(code)` | `holder_quantity`, `holder_pct`, `name`, `title`, `insider_total_count`, **`insider_bought_count`**, **`insider_sold_count`** |
| `get_institution_list(market)` | `institution_id`, `institution_name`, `position_value`, `position_value_change`, `position_count`, `disclosure_date` |

#### 9. Fundamentals extras

- **`get_company_operational_efficiency(code)`** — per-fiscal-year `item_list` including
  **`employee_number`**: a per-employee efficiency dimension the repo has nowhere.
- `get_company_profile(code)` — 18 name/value rows.
- `get_company_executives(code)` — 15 rows: `position_name`, `begin_date`, `leader_age`,
  `highest_education`, `annual_salary`.

#### 10. Whole-market rank feeds

| method | live size | notable columns |
|---|---|---|
| `get_earnings_beat_rank(market, beat_type)` | **1,455** (EPS) | `industry`, `market_cap`, `pe_ttm`, `dividends_ttm` |
| `get_period_change_rank(market, period_type)` | **6,447** | `change_rate_5min` / `_5d` / `_10d` — a whole-market momentum rank |
| `get_us_pre_market_rank()` | **18,108** | `pre_market_price`, `pre_market_change_ratio` |
| `get_dividend_rank(market, rank_type)` | 4 (HIGH_YIELD) | **`dividend_grow_year`**, `avg_dividend_yield_5y`, `distribution_frequency` |
| `get_ipo_list(market)` | 100 (US) | `ipo_price`, `industry_pe_rate` |

`dividend_grow_year` + `avg_dividend_yield_5y` is dividend **growth** — what
`strategies/capital_income.py`'s preferred-income index needs and does not have.

#### 11. Classification, corporate actions, operations

- **`get_plate_list(US, ALL)` → 348 plates**; `get_owner_plate(['US.AAPL'])` → **41 plates**
  with `plate_code` / `plate_name` / `plate_type`. A finer industry taxonomy than the 11 SPDR
  sectors — the reference set `strategies/peer_universe.py::resolve_peer_universe` (`:174`)
  and `cross_section.industry_neutral_z` both need.
- **`get_rehab(code)`** → 62 rows of raw `split_ratio`, `per_cash_div`, `special_dividend`,
  `bonus_*`. The **adjustment table** behind vendor-adjusted bars — an audit trail for the
  price-scale/staleness guard.
- **`get_history_kl_quota(get_detail=True)`** → `(26, 74, [{code, name, request_time}, …])`:
  quota used / remaining **plus the recent request log**.
- **`get_market_state(code_list)`** → authoritative `market_state` per code.
- **`get_code_change(code_list)`** → ticker renames. Not hypothetical: the probe hit a real one
  (SQ → XYZ).
- **`get_fed_watch_dot_plot()`** → 12 rows: `year`, `rate`, `vote_count`, `is_median`,
  `median_rate`, `current_rate`. The FOMC path behind the target-rate read already in use.
- **`get_macro_indicator_list(region)`** → 24 US entries: the catalogue behind
  `get_macro_indicator_history` (already used).
- **`get_cur_kline(code, num, ktype, autype)`** → up to 1,000 bars with an explicit adjustment
  type; the real-time sibling of `request_history_kline`.

### Tier 2 — gated behind a subscription, **not** absent

Each returned an explicit instruction, so these are plumbing rather than entitlement walls:

| method | exact error | what it gives |
|---|---|---|
| `get_order_book(code, num)` | *"Before calling the Get Real-time Order Book interface, please subscribe to OrderBook data first."* | LV2 depth, 10 levels (40 for SF) |
| `get_rt_ticker(code, num)` | *"Before calling the Get Real-time Tick-by-Tick Data interface, please subscribe to Ticker data first."* | up to 1,000 ticks — the **microstructure feed** for `liquidity_risk.kyle_lambda` (`:262`) and `roll_spread` (`:309`), which currently run on bars as a proxy |
| `get_rt_data(code)` | *"Before calling the Get Real-time Intraday Data interface, please subscribe to RT data first."* | intraday minute series |

### Tier 3 — checked and **not** usable

- **`get_corporate_actions_buybacks` is HK/A-share only.** Exact error: *"Only HK and A-share
  stocks and funds are supported; other markets or security types are not supported."*
  **This confirms an existing correct claim** rather than discovering one —
  `moomoo.py:1911` already says *"Dividend history + stock splits (buybacks are HK/A-share
  only)."* Recorded here so the `share_buybacks` gap (a canonical key with no reader) is not
  re-probed against moomoo for US names. It needs a different source.
- **`get_technical_unusual` / `get_financial_unusual` / `get_derivative_unusual`** are
  `SkillWrapAPI` endpoints returning **LLM-generated prose**, not numbers. My call returned
  *"Unknown stock. AAPL"* (they take a name or a differently-formatted code). Even when they
  answer, this is the class of source this repo refuses to cite as a computed value.
- `get_option_volatility(code)` needs an **option** code, not a stock — my probe's failure, not
  the API's.
- `get_holding_change_list` rejects `holder_type=None`; it needs a real holder type.
- `filter_competition` is sports-event filtering. Irrelevant.

---

## Fit against the repo (grounded, not inferred)

| Capability | What it replaces or fills | Existing seam |
|---|---|---|
| `get_market_snapshot` batch quote | one-symbol-at-a-time vendor fetches | `scripts/value_screener.py::_fetch_ohlcv` (`:449`), `scripts/score_panel.py::PriceProvider` (`:531`) |
| pre / after / overnight families | Alpaca free-IEX pre-market reads | `strategies/market_session.py::premarket_liquidity` (`:309`), `::post_close_confirmation` (`:328`), `::decompose_returns` (`:354`) |
| `iv_rank` / `iv_percentile` batch | per-name chain computation | `strategies/options_surface.py::iv_percentile` (`:15`) |
| `iv` vs `hv_30d` | *"asserted, not quantified"* | `strategies/options_surface.py::volatility_risk_premium` (`:65`) |
| `get_valuation_detail` percentile + plate distribution | the missing peer-multiple table | `strategies/peer_universe.py::resolve_peer_universe` (`:174`), `::resolve_growth_medians` (`:304`) |
| `get_rating_change` | yfinance upgrades/downgrades **proxy** | `strategies/analyst_revisions.py::revision_index` (`:279`) |
| `get_daily_short_volume` | FINRA via Massive | `dataflows/massive.py` short-volume family |
| `get_shareholders_overview` / `get_insider_holder_list` | ownership concentration | `strategies/liquidity_risk.py::ownership_hhi` (`:130`) |
| `get_dividend_rank` growth fields | missing dividend-growth input | `strategies/capital_income.py` |
| `get_plate_list` / `get_owner_plate` | 11-SPDR-only sector map | `strategies/cross_section.py::industry_neutral_z` (`:89`) |
| `get_rehab` | no raw adjustment audit trail | the price-scale/staleness guard |
| `get_history_kl_quota` | the documented K-line bottleneck | `scripts/value_screener.py` universe fetch |
| `get_market_state` | hardcoded session logic | `strategies/market_session.py` |

---

## Constraints

1. **Batch calls are all-or-nothing.** Verified twice. A caller must pre-validate symbols and
   chunk. The failure names one offender, so recovery means iterating — cheap for a panel
   build, unacceptable in a per-symbol hot path.
2. **OpenD is a hard dependency**, and its supervision is currently a known gap: the daemon
   died mid-session on 2026-09-18 and nothing restarts it. A factor that reads moomoo inherits
   that fragility. This is a reason to keep every new consumer behind a gate with a
   `unavailable` degrade path, not a reason to abstain.
3. **Rule 15 — one producer.** `get_market_snapshot`'s `pe_ttm_ratio`, `pb_ratio` and
   `total_market_val` **overlap** what `statement_parsing` computes and what the SEC XBRL leg
   derives (`sec_edgar.annual_facts`). Adopting the snapshot does not delete the other
   producers; the choice of which is authoritative must be made explicitly, per metric, and
   recorded. A second contributor to one quantity is exactly what rule 15 forbids.
4. **Gate-off byte-identity.** Every consumer lands behind a new gate, default `False`, and a
   gate-off run must be byte-identical to today's — the established protocol
   (`docs/gate_registry.md`, machine-checked by `tests/test_gate_env_toggles.py`).
5. **US-centric.** The snapshot and the option analytics are US-first. Non-US symbols must
   raise a typed `NoMarketDataError` and fall through, as `_moomoo_code` (`moomoo.py:663`)
   already does.
6. **The SDK is pinned by version.** Every fact here is from `moomoo` **10.10.7008**. A
   signature or field change is a silent break, so the field sets the code depends on should be
   asserted in tests rather than assumed.

---

## Design

### Gate

**`enable_moomoo_snapshot`** — new, never used (verified absent from the tree). Default
`False`, with an `_ENV_OVERRIDES` row and a `.env.example` line, and a `docs/gate_registry.md`
row. The individual capabilities sit underneath as separate gates only if they ship separately;
the block gate is what the registry documents.

### Module layout

Mirrors `moomoo.py`, which is this repo's template for a gated vendor — reuse its plumbing
rather than re-implementing it:

```
tradingagents/dataflows/moomoo.py          existing seam; add the new readers here
   _ensure_ctx          (:303)             thread-local context, already bounded
   _sdk_call            (:484)             wall-clock timeout, already bounded
   _check_ret           (:563)             typed errors from the SDK return code
   _moomoo_code         (:663)             Yahoo ticker <-> US.AAPL, typed on unknown market
   _RET_OK              (:559)
   MoomooNotConfiguredError (:69)
```

New readers, one function each, all returning rendered text in the existing house style and
degrading to an explicit `unavailable` rather than raising:

```
get_market_snapshot_moomoo(symbols: list[str]) -> str        # batched, chunked, pre-validated
get_option_iv_overview_moomoo(symbols: list[str]) -> str     # iv / iv_rank / iv_percentile / hv
get_option_iv_history_moomoo(symbol: str) -> str             # the iv/hv series
get_valuation_detail_moomoo(symbol: str) -> str              # percentile + plate distribution
get_rating_changes_moomoo(limit: int) -> str                 # the US rating-change feed
get_kl_quota_moomoo() -> str                                 # the operational guard
```

### The batching helper (the one piece that must be right)

Because the call is all-or-nothing, a `_batched_snapshot(codes, chunk=…)` helper owns three
rules in one place:

1. **Pre-validate** each symbol through the existing exchange gate; drop OTC and non-equity.
2. **Chunk**, and on `Unknown stock. <X>` **bisect** — drop `<X>`, retry the chunk, and record
   the dropped symbol in the coverage line rather than silently losing it.
3. **Never fabricate**: a chunk that still fails contributes `None` with its reason, and the
   rendered output names how many symbols were requested versus returned.

This is the same coverage-travels-with-the-number rule the score engines already follow.

### What each reader must print

Per the house convention, every number travels with its basis:

- the **request time** (these are live snapshots, not dated closes — a snapshot read at 21:00
  is an after-hours read, and the output must say so);
- the **session** the price belongs to (`last` vs `pre` vs `after` vs `overnight`);
- the **chunking outcome** (requested / returned / dropped);
- for the IV family, that `iv_rank` is the vendor's own percentile, not a locally computed one.

---

## Implementation plan

| Phase | Work | Acceptance |
|---|---|---|
| **P0** | `get_kl_quota_moomoo()` + a pre-flight warning in the screener's universe fetch | The screener prints remaining quota before a run and refuses cleanly at zero; gate off ⇒ byte-identical |
| **P1** | `get_market_snapshot_moomoo` + `_batched_snapshot` | A 100-symbol batch returns 100 rows in one call; an injected bad symbol is dropped, named in the coverage line, and the batch still succeeds; gate off ⇒ byte-identical |
| **P2** | `get_option_iv_overview_moomoo` + `get_option_iv_history_moomoo` | Live `iv_rank` matches the vendor for 3 names; the IV history feeds `options_surface.volatility_risk_premium` with a real series; gate off ⇒ byte-identical |
| **P3** | `get_valuation_detail_moomoo` + the Morningstar anchor | A rendered valuation percentile and plate distribution; the Morningstar fair value is printed **as a third-party figure with its own attribution**, never merged into the repo's DCF |
| **P4** | `get_rating_changes_moomoo` as an alternative leg in `analyst_revisions` | Same rendered shape as today's proxy path; the source is named in the basis line |
| **P5** | Deferred: the subscription-gated reads (`get_order_book`, `get_rt_ticker`) | Only if a subscription is purchased; the error text is the trigger |

Each phase lands alone, gate off by default, with its own failing-first test and a
`CHANGELOG` entry.

---

## Open questions

1. **Which producer wins for P/E, P/B and market cap?** `get_market_snapshot` carries them,
   `statement_parsing` computes them, and the SEC XBRL leg derives market cap from close ×
   cover-page shares. Rule 15 forbids two contributors. Close by measuring all three on the
   same 20 names and recording the disagreement before choosing — not by preference.
2. **Is the snapshot's `pe_ttm_ratio` genuinely TTM?** The field name says TTM; the repo's
   hard-won lesson (the AMZN basis drift) is that a field name is not a basis. Close with the
   vendor's own definition, and print `(vendor TTM, unverified)` until then.
3. **Do the Tier-2 reads need a purchase, or only a `subscribe` call?** Close with one
   `subscribe(OrderBook)` attempt on a name with an existing LV2 entitlement.
4. **Does `get_market_snapshot` carry a per-symbol rate cost against the K-line quota?** Close
   with `get_history_kl_quota` before and after a 100-symbol batch.
5. **Is `average_heat`'s equal weighting stable across sessions?** Measured once
   (2026-09-18, 400 rows, exact to within integer rounding). A second session confirms it.

---

## Recommendation

Take **P0 and P1**. P1 is the whole point of the scan: it collapses a per-symbol, multi-vendor
assembly into one batched call and carries three families — session reads, short interest, ETF
NAV/premium — that no current source supplies together. P0 is nearly free and protects the
quota the screener is documented to exhaust.

P2 is the strongest *analytical* addition, because it converts a recorded "asserted, not
quantified" into a measurement in a single batch call.

Do **not** adopt anything from Tier 2 or Tier 3, and do not adopt `get_market_snapshot`'s
valuation fields until open question 1 is settled — that is precisely the two-producers
mistake the master rule exists to prevent.

---

## Appendix A — the 103 unused data methods, categorised

Harvested by introspecting `OpenQuoteContext` on the installed SDK and diffing against every
`ctx.<name>` reference in the tree. "Tier" refers to the sections above; `—` means not
individually assessed because it is out of scope for this project.

### Batch / cross-sectional

| Method | Tier |
|---|---|
| `get_market_snapshot` | **1** |
| `get_market_state` | 1 |
| `get_option_underlying_overview` | **1** |
| `get_period_change_rank` | 1 |
| `get_us_pre_market_rank` | 1 |
| `get_us_after_hours_rank` | 1 |
| `get_us_overnight_rank` | 1 |

### Options

| Method | Tier |
|---|---|
| `get_option_underlying_his_volatility` | **1** |
| `get_option_volatility` | 3 (needs an option code) |
| `get_option_exercise_probability` | 3 (needs an option code) |
| `get_option_quote` | — |
| `get_option_rank` | — |
| `get_option_screen` | — |
| `get_option_market_statistic` | — |
| `get_option_earnings_screener` | — |
| `get_option_seller_screener` | — |
| `get_option_strategy` | — |
| `get_option_strategy_analysis` | — |
| `get_option_strategy_spread` | — |
| `get_option_underlying_his_statistic` | — |
| `get_option_underlying_rank` | — |
| `get_option_event` | — |
| `get_option_event_alert` | — |
| `set_option_event_alert` | — |
| `get_option_zero_dte_contract` | — |
| `get_option_zero_dte_screener` | — |

### Fundamentals, valuation, ratings

| Method | Tier |
|---|---|
| `get_valuation_detail` | **1** |
| `get_valuation_plate_stock_list` | 1 (same family) |
| `get_research_morningstar_report` | **1** |
| `get_research_rating_summary` | **1** |
| `get_rating_change` | **1** |
| `get_company_operational_efficiency` | 1 |
| `get_company_profile` | 1 |
| `get_company_executives` | 1 |
| `get_company_executive_background` | 1 |
| `get_earnings_beat_rank` | 1 |
| `get_financials_earnings_price_move` | 1 |
| `get_financial_unusual` | 3 (LLM prose) |
| `get_technical_unusual` | 3 (LLM prose) |
| `get_derivative_unusual` | 3 (LLM prose) |

### Ownership, flow, short

| Method | Tier |
|---|---|
| `get_shareholders_overview` | **1** |
| `get_shareholders_holder_detail` | 1 |
| `get_shareholders_holding_changes` | 1 |
| `get_insider_holder_list` | **1** |
| `get_holding_change_list` | 1 (needs a holder type) |
| `get_institution_list` | **1** |
| `get_institution_profile` | 1 |
| `get_institution_holding_list` | 1 |
| `get_institution_holding_change` | 1 |
| `get_institution_distribution` | 1 |
| `get_daily_short_volume` | **1** |
| `get_short_selling_rank` | 1 |
| `get_top_ten_buy_sell_brokers` | 1 (HK-centric) |
| `get_broker_queue` | 1 (HK-centric) |

### Income, dividends, corporate actions

| Method | Tier |
|---|---|
| `get_dividend_rank` | **1** |
| `get_dividend_calendar` | **1** |
| `get_corporate_actions_buybacks` | **3 — HK/A-share only** |
| `get_rehab` | **1** |
| `get_high_dividend_soe_rank` | — (HK SOE screen) |
| `get_ipo_list` | 1 |
| `get_code_change` | 1 |

### Classification / taxonomy

| Method | Tier |
|---|---|
| `get_plate_list` | **1** |
| `get_owner_plate` | **1** |
| `get_plate_stock` | 1 |
| `get_industrial_chain_list` | 1 |
| `get_industrial_chain_detail` | 1 |
| `get_industrial_chain_by_plate` | 1 |
| `get_industrial_plate_info` | 1 |
| `get_industrial_plate_stock` | 1 |
| `get_referencestock_list` | 1 (related securities) |

### Market data / microstructure

| Method | Tier |
|---|---|
| `get_order_book` | **2 — needs a subscription** |
| `get_rt_ticker` | **2 — needs a subscription** |
| `get_rt_data` | **2 — needs a subscription** |
| `get_cur_kline` | 1 |
| `get_history_kl_quota` | **1** |
| `get_market_snapshot` | (listed above) |
| `get_stock_quote` | 2 (needs a subscription) |
| `get_delay_statistics` | — (connection telemetry) |
| `get_stock_filter` | 1 (the other screener) |
| `get_search_quote` | — (symbol search) |
| `get_security_firm` | — |

### Macro, Fed, events

| Method | Tier |
|---|---|
| `get_fed_watch_dot_plot` | **1** |
| `get_macro_indicator_list` | **1** |
| `get_event_contract_kline` | — |
| `request_history_event_contract_kline` | — |
| `get_event_contract_milestone_list` | — |
| `get_event_contract_order_book` | — |
| `get_event_contract_ticker` | — |
| `subscribe_event_contract` | — |
| `unsubscribe_event_contract` | — |
| `unsubscribe_all_event_contract` | — |
| `filter_competition` | **3 — sports** |

### Reminders, combos, misc

| Method | Tier |
|---|---|
| `get_price_reminder` | — |
| `set_price_reminder` | — |
| `request_combo_quotes` | — |
| `request_indicator_calc_async` | — |
| `get_indicator_list` | — (indicator catalogue) |
| `get_future_info` | — |
| `get_warrant` | — |
| `get_warrant_screen` | — |
| `get_ark_fund_holding` | 1 |
| `get_ark_active_transaction` | 1 |
| `handle_push` | — (dispatch hook) |

**Also unused and noted:** `get_hot_list` — the Heat List. It is not in this table's "take it"
column because the finding is already recorded separately (the five corrected false claims,
TradingAgents `4acc555`); the method works and its composite is the equal-weighted mean of
`search_heat` / `trade_heat` / `news_heat`.

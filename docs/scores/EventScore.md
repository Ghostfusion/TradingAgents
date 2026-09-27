# EventScore — design

**Part of the score-engine design set: [`README.md`](README.md)** (master).
Siblings: [`FundamentalScore.md`](FundamentalScore.md),
[`TechnicalScore.md`](TechnicalScore.md), [`RegimeScore.md`](RegimeScore.md),
[`NewsScore.md`](NewsScore.md), [`SentimentScore.md`](SentimentScore.md),
[`RiskScore.md`](RiskScore.md), [`MarketScore.md`](MarketScore.md),
[`ValuationScore.md`](ValuationScore.md).

**Scope: the event engine only.** The owner recommends it as the **seventh**
engine, and gives it no weight table. Its question is *"is a high-impact event
happening right now?"* — **occurrence and imminence** — as distinct from
`NewsScore` (*information flow*) and from `RiskScore`'s event leg (*the exposure
the event creates*).

His reason for adding it is explicit and is this document's governing constraint:
it should exist **before `NewsScore` is allowed to influence
`opportunity_score`**.

Status: **built (2026-09-18); gate off by default.** `strategies/event_state.py` is the engine (`imminence`, `event_components`, `forward_calendar`), `get_event_state` its leaf and `enable_event_state` its membership switch. Occurrence producers exist for **4 of 7** event families (§1); the hard block exists and is the engine's only event-triggered fail-closed path (§0.3). **Unmeasured** (vendor gate).

---

## 0. What this engine answers, and the two things it must not do

### 0.1 No weight table — and that is not an omission to fill in

The owner gives NewsScore nine weights, SentimentScore ten, and EventScore
**none**. The inventory explains why that is coherent: **every existing event
producer is a multiplier, a day-count or a boolean** — not a normalised factor.
There is nothing to weight yet.

So this document does **not** invent weights (master rule 6). It specifies:

1. the **occurrence/imminence scalars** that would have to exist first (§4),
2. the **overlap split** against `RiskScore`'s event leg (§0.2),
3. the **hard block**, which is EventScore's most important output and already
   exists (§0.3),
4. the four defects found in the live wiring (§3).

### 0.2 The overlap with `RiskScore`'s event leg — resolved by question

Same producers, two different questions. **No function currently separates
them**: `build_catalyst_snapshot.scale` and `events.catalyst_risk_penalty` each
carry both meanings today.

| Same producer | `EventScore` reads it as | `RiskScore`'s event leg reads it as |
| --- | --- | --- |
| `catalyst.build_catalyst_snapshot:219` → `scale` | **occurrence**: is an event inside the window | **exposure**: `contract.build_position_contract`'s `catalyst_scale` (`contract.py:115`, applied `:208-212`); `fold_catalyst_into_overlay:362`; `pre_market.catalyst_window_read:103` |
| `events.catalyst_risk_penalty:63` | (invoked inside the snapshot, `catalyst.py:266`) | the exposure multiplier itself — implied move vs baseline |
| `catalyst.implied_move_from_history:111` → `implied_move` | event sizing context | intended `contract.build_position_contract`'s `implied_move_pct` (`contract.py:118`, `:262-267`) — **never populated** (§3 D1) |
| `events.position_mult_by_side:37` | the side label via `drift_side:26` | `get_beat_miss_sizing:2252`'s position multiplier |
| `book_risk.book_correlated_stress:146` | — | macro-event correlated tail loss |
| `regime.regime_gate_read:850`'s `catalyst_window` | an event-regime veto input | an entry veto — **deliberately not fed** (owner decision 2026-09-18; §3 D3, closed) |

**The design rule**: `EventScore`'s components are the **occurrence** measures
(imminence day-counts, window flags, the hard block); `RiskScore`'s event leg
keeps the **exposure** measures (implied move, the risk penalty, the size
multiplier). Neither may re-derive the other's number (master rule 3). Where one
producer serves both, the producing engine is named in both tables.

### 0.3 The hard block — already the engine's only event fail-closed path

`build_catalyst_snapshot:219` sets `hard_block` (`catalyst.py:284-288`, key
`:358`) **only** when `earnings.days_until <= catalyst_hard_block_days` (default
5, `default_config.py:799`). **Macro, Fed and OPEX never set it.** It then exits
through three places:

1. `graph/trading_graph.py:1061-1070` — REJECT `risk_gate` ("forced REJECT
   regardless of size").
2. `pre_market.catalyst_window_read:103` → `{hard_block: True, scale: 0.0}`;
   `review_decision:198` (branch `:240-245`) → REJECT — **unreachable from its
   own leaf** (§3 D2).
3. `regime.regime_gate_read:850` — advisory, and deliberately unfed (§3 D3, closed 2026-09-18).

The executor's 17 fail-closed checks (`../TradingExecution/signald/contracts.py:42`)
contain **no event check at all** — so the engine's `hard_block` is the
authoritative signal and the split must not route it through a score.

### 0.4 What the evidence says about event windows

- **Scheduled events carry a risk premium and an implied move**, and implied
  volatility **rises into the event and drops after it** (vol crush). The
  engine's `implied_move_from_history:111` and `get_earnings_catalyst:206` are
  this family.
- **Pre-FOMC drift exists in the literature but weakened after 2015**, and it is
  a *drift*, not a rule: `fed_imminence:142` should be an **imminence** input,
  never a directional bias.
- **OPEX weeks show abnormal returns and a volatility rise-then-fall around the
  third Friday** — `opex_status:127`'s `in_opex_week` / `post_opex_unwind` are
  the right shape.
- **Expected move rule of thumb**: annualized IV / ~16 for a one-day move, or the
  ATM straddle price directly. Worth pinning, because the engine has **two
  producers of "expected move"** under one name (§7 Q3).

---

## 1. Component ledger

EventScore has no weight table in code; every producer is a multiplier, a day-count, or a boolean. Status column per the shared vocabulary.

| Event family | Producer (`module.function:line`) | Lead time / horizon | Scale returned | Hard block? | Direction | Status |
| --- | --- | --- | --- | --- | --- | --- |
| Earnings — next print (imminence) | `catalyst.next_earnings` (`tradingagents/strategies/catalyst.py:90`) | entries at/after trade_date, `lookahead_days=60` | dict `{date, days_until:int, eps_estimate, eps_actual}` | no | higher `days_until` = farther = safer | SCORABLE |
| Earnings — snapshot leg | `catalyst.build_catalyst_snapshot` (`catalyst.py:219`, earnings branch `:265`) | `catalyst_window_days` default 5 (`default_config.py:791`) | multiplies `scale` by `catalyst_risk_penalty` | YES at `:284` | lower scale = risk-increasing | SCORABLE |
| Earnings — last surprise / side | `catalyst.last_earnings_surprise` (`catalyst.py:70`); `events.surprise_score` (`events.py:17`); `events.drift_side` (`events.py:26`) | most recent report in calendar | `{surprise: ratio, side: 'beat' \| 'miss', date}`; surprise = (act-est)/\|est\| | no | beat = favourable | SCORABLE |
| Earnings — implied move (exposure) | `catalyst.implied_move_from_history` (`catalyst.py:111`) | latest history row | fraction (`predict_vola_ratio_newest/100`) | no | larger = more risk | SCORABLE |
| Earnings — risk multiplier | `events.catalyst_risk_penalty` (`events.py:53`) | none (implied vs baseline) | multiplier <=1 (0.5 when unknown; `1/(1+3r)`) | no | lower = more risk | SCORABLE |
| Earnings — PEAD entry | `events.post_earnings_play` (`events.py:112`); `events.gap_up_qualifies` (`:63`) | print + 4 bars | verdict `setup/consolidating/no-gap/no-data` | no | setup = favourable | SCORABLE |
| Earnings — position mult by side | `events.position_mult_by_side` (`events.py:37`) | none | 1.0 beat / 0.5 miss / 0.0 flat, cap 1.5 | no | higher = favourable | PARTIAL (catalyst arg inert, see §3 D4) |
| Macro (CPI/FOMC/payrolls) imminence | `catalyst.macro_imminence` (`catalyst.py:123`) | `window_days=3`; `star=='HIGH'` filter | `{count_high:int, min_days:int \| None}` | no | imminent = risk-increasing | SCORABLE |
| Fed — next FOMC | `catalyst.fed_imminence` (`catalyst.py:142`) | `window_days=14` default; snapshot passes `catalyst_fed_window_days`=10 | `{days_until:int, modal_prob:%, modal_range:str}` | no | modal hike = risk-increasing | SCORABLE |
| Fed — direction label | `catalyst.fed_direction` (`catalyst.py:184`) | none | `HOLD`/`HIKE`/`CUT`/`n/a` | no | hike = risk-increasing | SCORABLE |
| Macro backdrop (fallback) | `massive.fetch_macro_backdrop` (`tradingagents/dataflows/massive.py:398`) | 90d look-back; only when both fed+econ calendars absent | 0..1 de-risk mult (0.7 inversion x0.75 breakeven), `verdict` | no | lower = risk-increasing | SCORABLE (constant thresholds `_INVERSION_SCALE=0.7`, `_BREAKEVEN_SCALE=0.75`, `massive.py:392-395`) |
| OPEX / expiry | `derivatives_gamma.opex_status` (`derivatives_gamma.py:127`); `opex_dates` (`:116`); `opex_note` (`:165`) | third-Friday monthly cycle; `days_to_next`; OPEX week = ISO-week equality; post-OPEX unwind = Mon/Tue within 1-4d of prev expiry | `{next_opex, prev_opex, days_to_next:int, in_opex_week:bool, post_opex_unwind:bool, quarterly:bool}` | no | OPEX-week/unwind = structure risk, not favourable | SCORABLE (booleans, no 0-1) |
| Product launch / clinical / FDA | `event_calendars.fda_calendar_rows` (`tradingagents/dataflows/event_calendars.py`, pdufa.bio `/api/v1/events`, keyless) | the event's own announced day; family horizon `HORIZONS['product_clinical']=90` (declared) | `{date, name, type, status, indication, source, source_url, url}` | no | an imminent decision = risk-increasing | **SCORABLE (built 2026-09-18)**; announced-day rows only |
| Court decision | `event_calendars.court_calendar_rows` — **returns `None`** | — | — | — | — | **ABSENT**: the chosen source cannot carry a forward date (`COURT_REASON`) |
| Investor day | — | — | — | — | — | **ABSENT — DROPPED by decision 2026-09-18** (no free source; `INVESTOR_DAY_REASON`) |
| Gap risk (event-adjacent exposure) | `market_session.gap_type` (`market_session.py:137`); `pre_market.premarket_gap` (`pre_market.py:40`) | last bar / overnight | gap type + fill prob; `{gap_pct, gap_atr, through_stop, vacuum_to_stop}` | `through_stop` -> REJECT at `pre_market.py:255` | gap-through-stop = risk | SCORABLE |

**`build_catalyst_snapshot` return contract** (`catalyst.py:219`; return dict `catalyst.py:350-359`):

```python
{
    "earnings": earnings,        # next_earnings(...) or None
    "last_surprise": last,       # last_earnings_surprise(...) or None
    "implied_move": implied,     # fraction or None  (catalyst.py:352)
    "macro": macro,              # {count_high, min_days}
    "fed": fed,                  # {days_until, modal_prob, modal_range}
    "scale": round(scale, 4),    # 0..1, floored at catalyst_scale_floor (0.25), never > 1.0
    "verdict": verdict,          # no-imminent-catalyst | earnings-window | earnings-hard-block
                                 # | macro-catalyst | fed-catalyst | macro-backdrop | catalyst-unassessed
    "reasons": reasons,          # list[str]
    "hard_block": hard_block,    # None, or {days_until, window_days, earnings_date}
}
```

- `scale` range: `max(catalyst_scale_floor, min(1.0, scale))` at `catalyst.py:349`; floor default 0.25 (`default_config.py:798`).
- `hard_block` triggers only when `block_days > 0 and earnings.days_until <= block_days` (`catalyst.py:280-288`), `block_days = catalyst_hard_block_days` default 5 (`default_config.py:799`). Macro/Fed/OPEX never set it.
- Surfaced by leaf `get_catalyst_scale` (`analysis_tools.py:617`), bound to the **news analyst** toolset (`agents/toolsets.py`, `news_tools()` list line 370). Also folded live at `graph/trading_graph.py:836-839`.

**Overlap with RiskScore's event leg (function-by-function; the exposure side):**

| Same producer | Read by EventScore as | Read by RiskScore's event-exposure leg as |
| --- | --- | --- |
| `catalyst.build_catalyst_snapshot` (`catalyst.py:219`) `scale` | occurrence/imminence folded scalar | `contract.build_position_contract` `catalyst_scale` param (`contract.py:115`, applied `:208-212`); `catalyst.fold_catalyst_into_overlay` (`catalyst.py:362`); `pre_market.catalyst_window_read` (`pre_market.py:103`) |
| `events.catalyst_risk_penalty` (`events.py:53`) | (invoked inside snapshot, `catalyst.py:266`) | the exposure multiplier itself — implied move vs baseline |
| `catalyst.implied_move_from_history` (`catalyst.py:111`) -> `implied_move` | event sizing context | intended `contract.build_position_contract` `implied_move_pct` (`contract.py:118`, `:262-267`) — **never populated** (see §3 D1) |
| `events.position_mult_by_side` (`events.py:37`) | side label via `drift_side` | `get_beat_miss_sizing` (`analysis_tools.py:2270`) position multiplier |
| `book_risk.book_correlated_stress` (`book_risk.py:128`) | — | macro-event correlated tail loss ("a macro event moves every position at once") |
| `regime.regime_gate_read` `catalyst_window` (`regime.py:178`) | event-regime veto input | entry veto; **deliberately not fed** (see §3 D3, closed 2026-09-18) |

No single function currently separates occurrence from exposure: `scale` and `catalyst_risk_penalty` each carry both meanings.

#

---

## 2. Tool leaves (what the analysts can actually call)

| Leaf (`function:line`) | Toolset binding (`agents/toolsets.py:line`) | What it returns | Wired? |
| --- | --- | --- | --- |
| `get_catalyst_scale` (`analysis_tools.py:617`) | news `:370` | scale 0..1 + verdict + per-factor reasons | YES (`catalyst.build_catalyst_snapshot`) |
| `get_earnings_event_read` (`analysis_tools.py:535`) | news `:371` | last surprise/side + PEAD verdict | YES |
| `get_earnings_catalyst` (`moomoo_extra_tools.py:206`) | news `:369` | historical earnings implied move / IV crush (backward) | YES (vendor) |
| `get_expected_move` (`moomoo_extra_tools.py:267`) | market `:304` | 1-sigma expected move % + band for upcoming print | YES (vendor) |
| `get_economic_calendar` (`moomoo_extra_tools.py:60`) | news `:365` | upcoming CPI/FOMC/payrolls, look_days default 14 | YES |
| `get_fed_watch` (`moomoo_extra_tools.py:84`) | news `:367` | market-implied FOMC target-rate probabilities | YES |
| `get_earnings_calendar` (`analyst_data_tools.py:30`) | news `:359` | next earnings date + EPS surprise, default 30d | YES |
| `get_opex_read` (`analysis_tools.py:3126`) | market `:241` | next expiry, OPEX-week flag, post-OPEX unwind | YES |
| `get_derivatives_flow` (`analysis_tools.py:3160`) | market `:240` | gamma + OPEX + IV combined | YES |
| `get_premarket_review` (`analysis_tools.py:6657`) | market `:303` | CONFIRM/REVISE/REJECT from gap + re-anchor | PARTIAL — no catalyst_snapshot passed (§3 D2) |
| `get_beat_miss_sizing` (`analysis_tools.py:2270`) | news `:372` | position multiplier by side | YES |
| `get_regime_gate_read` (`analysis_tools.py:10170`) | market (via `market_tools()`), leaf arg `catalyst_window` default `None` = measured from the ticker's catalyst snapshot | knife-guard verdict | YES — measures the snapshot when the caller supplies none |
| `get_ipos` (`moomoo_extra_tools.py:178`) | news `:363` | pending IPOs | YES (universe/event input) |
| `get_earnings_surprise_history` (`moomoo_extra_tools.py:246`) | fundamentals `:394` | historical surprises + implied moves | YES |
| `get_earnings_surprise` (`analysis_tools.py:1492`) | fundamentals `:392` | computed surprise | YES |
| `get_event_pnl_response` (`analysis_tools.py:8198`) | market `:331` | delta-gamma-vega-theta P&L per option unit | YES |
| `get_option_breakeven` (`analysis_tools.py:2965` args; `strategies/options_breakeven.catalyst_window:105`) | market `:235` | earnings-window flag on the sold call | PARTIAL — `days_to_earnings` caller-supplied |
| `get_session_discipline` (`analysis_tools.py:4889`) | market `:278` | walk-away / psych levels (not event) | YES (non-event) |

#

---

## 3. Defects and dead seams

- **D1 — dead `implied_move_pct` key (exposure never scaled) — **FIXED 2026-09-17, `2c05701`**.** `graph/trading_graph.py:966` reads `(catalyst_snapshot or {}).get("implied_move_pct")`, but the producer emits `"implied_move"` (`strategies/catalyst.py:352`) and never `implied_move_pct`. So `contract.build_position_contract`'s `(1 - implied_move_pct)` de-risk (`strategies/contract.py:262-267`) is unreachable. Reader sees a report whose implied-move sizing is documented but never applied; only the `scale` fold moves size.
- **D2 — premarket hard block unreachable from its leaf — **FIXED 2026-09-17, `2c05701`**.** `analysis_tools.py:6682-6689` calls `pre_market.review_decision(...)` without `catalyst_snapshot=`, while `strategies/pre_market.py:239` reads it to raise the earnings-window REJECT (and `:246` the REVISE). The leaf therefore can only REJECT/REVISE on gap and re-anchor caps, never on an open earnings window.
- **D3 — `regime_gate_read.catalyst_window` always False — **FIXED 2026-09-18 (owner decision; master §3.5 D-11, `ResearchLayerWiring.md` §6.6)**.** `strategies/regime.py:261` blocks when `catalyst_window` is set. The `2c05701` change fed it from `state["strategy_overlays"]["catalyst"]` inside `_compiled_decision_context`, but that function is called with `init_agent_state` *before* `graph.invoke` (`graph/trading_graph.py:645-647`) while the overlay is stamped *after* the graph (`:686`) — so the key was always absent and the derived flag always `False`. **Resolved as row 2 of §6.4, NOT by feeding the flag:** the axis is now **tri-state** (`catalyst_window: bool | None = None`) — `None` means the caller supplied no event fact and is reported **unmeasured** rather than coerced to `False`; the gate neither vetoes nor claims "no catalyst", and its trailer reads "volatility contained + no fast downtrend (catalyst window not measured)". `_compiled_decision_context` supplies **none** and prints `catalyst_window=unavailable_pre_graph`; `value_dip_tools.get_value_dip_setup`, which passed an explicit `False` it never measured, now supplies none too. The veto is **deliberately not fed** — event authority is `EventScore`'s — so this is now a *recorded decision* rather than a dead wire, and the axis can no longer read as a measured clear. Failing-first: both new tests in `tests/test_strategies_regime.py` reproduce the exact false string against the pre-fix code.
- **D4 — `events.position_mult_by_side` catalyst arg inert.** `events.py:42` uses `event_scale = catalyst if catalyst > 1 else 1.0`, but the only caller documents `catalyst` as `0..1` (`analysis_tools.py:2272` "catalyst scale 0..1") and `get_catalyst_scale` supplies <=1. `event_scale` is therefore always 1.0; the multiplier is only 1.0 (beat) / 0.5 (miss).
- **D5 — `get_earnings_calendar` param named backward for a forward query.** The leaf arg is `look_back_days` "Days to look back" (`analyst_data_tools.py:33`), but the finnhub adapter queries `[curr_date, curr_date + look_back_days]` forward (`dataflows/finnhub.py:195-196`). A caller setting it small truncates the forward window.

#

---

## 4. What is ABSENT, and the smallest honest producer

| Component | Data needed | Engine already fetches? | Smallest honest producer |
| --- | --- | --- | --- |
| FDA / clinical decisions | a forward PDUFA / trial-readout calendar | **YES as of 2026-09-18** — `dataflows/event_calendars.py::fda_calendar_rows` (pdufa.bio `/api/v1/events`, free and keyless) | **BUILT**: `forward_calendar('product' \| 'clinical')`, announced-day rows only |
| Court decisions | a litigation/docket calendar | **NO — the chosen source cannot answer.** CourtListener is a filing archive: its docket endpoints need a token and its anonymous search exposes only `dateArgued`/`dateFiled`/`dateTerminated`, all backward-looking (`event_calendars.COURT_REASON`) | none; the family answers **MISSING**, never `not_applicable` |
| Investor day / product launch | a company-events calendar | **NO — DROPPED by owner decision 2026-09-18**: no free source exists, and the one priced source was declined (`event_calendars.INVESTOR_DAY_REASON`) | none; the nearest producers are `get_corporate_actions` (dividends/splits) and `get_ipos` (`moomoo_extra_tools.py:178`) |
| Earnings imminence > 60d | horizon beyond `next_earnings.lookahead_days=60` (`catalyst.py:90`), fetch window +95d (`catalyst.py:493`) | YES (fetch is wider than the read) | raise `lookahead_days`; no new adapter |
| Scalar 0-1 imminence | normalization of existing day-counts | YES — raw counts already returned | pure `clamp(1 - days_until/horizon, 0, 1)` over `next_earnings.days_until` / `macro_imminence.min_days` / `fed_imminence.days_until` / `opex_status.days_to_next`; no new fetch |
| Hard block for macro/Fed/OPEX | a rule to close on imminent non-earnings events | YES (calendar fetched) | extend `build_catalyst_snapshot` (`catalyst.py:280`) to set `hard_block` from `macro_imminence.min_days` / `fed_imminence.days_until` against a configured window |
| Weights / composite | any EventScore band or weight structure | NO — every producer is a multiplier or gate; no 0-100 score anywhere | needs (a) per-family imminence 0-1, (b) per-family impact/severity, (c) NA!=0 handling; nothing exists to reuse |

**PROBED 2026-09-17 (P0-9) — the moomoo economic calendar does NOT carry them.**
The probe is the answer this row was waiting for: `get_economic_calendar_moomoo`
over the next 14 days returned **50 rows, every one a MACRO release** (Fed interest-rate
projections, TIC capital flows, jobless claims, housing starts, bill/TIPS auctions,
Philly Fed sub-indices, GDPNow, natural-gas storage). **Zero rows matched
FDA / clinical / trial / phase / court / litigation / ruling / investor day /
analyst day / drug / approval.** The moomoo adapter supplies the *pattern*
(a windowed reader with a typed no-data error) and **not** the data, which is what
made the sourcing decision below necessary rather than optional.

**RESOLVED 2026-09-18 — the vendor decision, and what it bought.**
`dataflows/event_calendars.py` is the module. Each family was decided on its own,
because the cheapest honest answer differs per family:

| Family | Source chosen | Cost | Outcome |
| --- | --- | --- | --- |
| FDA / clinical | **pdufa.bio** `/api/v1/events` | **$0**, keyless (1,000 req/day anonymous) | **MEASURABLE.** Live 2026-09-18: 456 catalysts tracked, **120 carrying an announced day** |
| Court | **CourtListener** (owner's pick) | $0 | **STILL ABSENT** — see below |
| Investor day | none | — | **DROPPED** — no free source exists |

**Two things the decision did not buy, both recorded rather than papered over.**

1. **CourtListener cannot answer this family's question.** It is a filing archive,
   not a forward calendar: `/api/rest/v4/dockets/` and `/docket-entries/` require a
   token even for `OPTIONS`, and the anonymously accessible `/search/?type=r`
   endpoint exposes exactly three date fields — `dateArgued`, `dateFiled`,
   `dateTerminated` — **all backward-looking**. Probed live 2026-09-18 across three
   result sets (144,748 / 4,563 / 61,937,018 matches): **zero rows carried a future
   date.** The adapter is therefore bound and returns `None`, which makes the family
   `missing` — **not** `not_applicable`, because "this source cannot carry a forward
   date" is not the claim "no court event is scheduled", and only the second one
   would be a false assertion. `event_calendars.court_probe` keeps the finding
   re-verifiable as a callable rather than as prose that could quietly go stale.
2. **The investor-day family is dropped by decision, not by omission.** Wall Street
   Horizon via Interactive Brokers ($49/mo retail) was the only priced source and
   was declined; EODHD's Corporate Events Calendar ($19.99/mo) does not carry
   investor days at all — its own page scopes it to earnings, IPOs, splits,
   dividends and news. The design permits dropping it: the families are independent
   and coverage prints per family.

**The announced-day rule is load-bearing, not a filter detail.** pdufa.bio changed
`date` on 2026-09-09 to mean *an announced day, or `null`*: for `month`, `quarter`
and `year` precision the field is null and only `date_month` holds the granularity,
because the site used to serve a month midpoint as if a sponsor had announced it
(~7 rows in 10). **Only `date_precision == "day"` rows become forward events here.**
A month midpoint turned into a day-count would be exactly the fabrication this set
refuses, and it would land in a scored imminence. The undated rows are counted, not
discarded: `event_calendars.calendar_coverage` reports `rows_held` beside
`rows_with_announced_day`, so a family that measures nothing says *"of 6 rows, 5
undated"* rather than reading as an absence of catalysts.

**Gate.** `enable_event_calendars` (default **False**, `default_config.py:1094`),
**separate** from `enable_event_state`: this is the one part of the state that
leaves the machine, and enabling the engine must not silently acquire a
third-party fetch. With it off, every family keeps the answer it had before the
adapters existed.

**Hard-block inventory (every fail-closed-on-an-event site in either repo):**

Engine (TradingAgents):
1. `catalyst.build_catalyst_snapshot` sets `hard_block` (`catalyst.py:284-288`, key `:358`) when `earnings.days_until <= catalyst_hard_block_days` (default 5) — the sole event-triggered hard block.
2. `graph/trading_graph.py:1061-1070` — REJECT `risk_gate` on `hard_block` ("forced REJECT regardless of size").
3. `pre_market.catalyst_window_read` (`pre_market.py:103`) -> `{hard_block: True, scale: 0.0}`; `pre_market.review_decision` (`:198`, branch `:240-245`) -> REJECT.
4. `pre_market.review_decision` gap branch -> REJECT on `through_stop` (`pre_market.py:255`) and on re-anchor cap breach (`:290`).
5. `regime.regime_gate_read` (`regime.py:261`) `catalyst_window` OR `vol` OR `fast_downtrend` -> `pass=False` (advisory; hard only via `require_regime`, `value_dip.py:1411`).
6. `book_risk.drawdown_gate` (`book_risk.py:167`) -> new risk blocked.
7. `risk_hierarchy.evaluate_hierarchy` (`risk_hierarchy.py:43`) / `kill_switch_state` (`:81`), precedence `GATE_ORDER` (`:24`, 6 gates: kill_switch > portfolio > trade > liquidity > regime > data_quality).
8. `risk_governor.govern` (`risk_governor.py:37`) -> REJECT on halt, size cap, book cap, cvar, capital-at-risk, drawdown, daily-loss, HWM hard tier, ILLIQUID.
9. `risk_multiplier.combine` (`risk_multiplier.py:37`), `HARD_NAMES` (`:22`: halt, insufficient_liquidity, max_portfolio_risk, data_quality_failure, broker_safety) -> `factor=0.0, blocked=True`.

Executor (TradingExecution):
10. `signald/contracts.py:42` `GATE_PRECEDENCE` — 17 fail-closed check names: mandate, sleeve_capital, house_drawdown, house_cvar, correlation_stress, vol_regime, market_regime, knife_guard, concentration, liquidity, cost, wash, shortability, data, time, halt, approval. **No event/earnings/catalyst check exists.**
11. `signald/risk/gate.py:805` `CHECKS` (17 phases) and `evaluate` (`:825`); a check exception becomes `Failure(name, "block", "check_error")` — fail-closed.
12. `signald/gates.py:210` `to_gate_result` -> `blocked` tuple; `signald/processor.py:187-204` quarantines and returns `ProcessResult("blocked")`.
13. `signald/order/halts.py:184` — `allow_entries=False` during halted/limit/reopening/cooldown.
14. `signald/risk/sizing.py:101` — fail-closed `RiskDecision(ok=False, qty=0)`.
15. `signald/alpaca_ref.py:50` `complete_for_gates` -> fail-closed when cash/asset state missing.
16. `signald/schema.py:149` — fail-closed when neither direction nor rating resolves an action.
17. `signald/processor.py:121` future `effective_date` -> blocked; `:139` reference unavailable -> blocked; `:157` sleeve routing refused -> blocked.
18. `signald/marketdata/clock.py:78` — fail-closed outside `CALENDAR_YEARS`.

Sibling `../trading_web`: no `hard_block` / `fail_closed` / `do_not_trade` / `blocked` producers.

Consequence for the design: EventScore's most important output (the earnings blackout) currently exits only through engine items 1-3; the executor re-derives nothing event-specific, so the split must keep the engine's `hard_block` as the authoritative fail-closed signal and must not route it through a score.

---

## 5. How `EventScore` should be built (no weights yet)

The owner gave no weights, so the deliverable here is the **structure**, not a
table. Three layers, in this order:

### 5.1 Layer 1 — imminence scalars (mechanical, no new data)

Every family already returns a day-count. A single pure function

```
imminence(days_until, horizon) -> clamp(1 - days_until / horizon, 0, 1)
```

over `next_earnings.days_until`, `macro_imminence.min_days`,
`fed_imminence.days_until` and `opex_status.days_to_next` gives the engine a
comparable 0-1 occurrence input **without a single new fetch**. `NA ≠ 0`: a
family with no calendar data contributes nothing and reduces coverage.

### 5.2 Layer 2 — the window flags and the block (already exist)

`hard_block` (earnings, ≤5 days) stays exactly as it is and stays
**authoritative**; the window flags (`in_opex_week`, `post_opex_unwind`,
`catalyst_window`) are printed. **No score may gate on itself**: the block fires
from the snapshot, not from `EventScore`.

### 5.3 Layer 3 — the score, only if the owner wants one

If a 0-100 `EventScore` is wanted, it needs two things that do not exist: a
per-family **impact/severity** weight (an FDA decision is not a payrolls print)
and a **normalisation** of the multipliers. Until then the honest output is a
**structured event state**:

```
{ "families": {earnings: {...}, macro: {...}, fed: {...}, opex: {...}},
  "imminence": {...}, "hard_block": {...}|None, "coverage": 4/7 }
```

— which is what the owner's own framing needs ("is there a high-impact event
occurring right now"), and which cannot be mistaken for a signal.

### 5.4 What it must never do

| May | May not |
| --- | --- |
| print the event state and the hard block | override or duplicate the hard block |
| feed `NewsScore`'s materiality category (master §3.2, NewsScore §7 Q2) | become a second `RiskScore` event leg |
| veto through the existing `hard_block` path | introduce a directional bias from a scheduled event (no pre-FOMC drift trade) |
| reduce coverage when a family is unknown | substitute 0 for an unknown family |

---

## 6. Verification requirements

1. **`hard_block` fires only on earnings** and the test pins that (a macro-only
   window must not block) — until §4's extension is decided.
2. **The imminence scalar is monotone and bounded**: 0 days → 1, ≥ horizon → 0,
   and `None` → `None` (never 0).
3. **`NA ≠ 0`**: with one family absent, coverage drops by that family and the
   state still renders.
4. **No event path reaches `GATE_PRECEDENCE`** through a score; the executor's
   check list is unchanged.
5. **The overlap test**: a test asserts `EventScore`'s components and
   `RiskScore`'s event components are disjoint sets of keys (no key produced by
   both).

---

## 7. Decisions (owner, 2026-09-17) - all resolved

**All decided (owner, 2026-09-17).** Each question keeps its text as the record
and carries its decision inline. The architecture decisions are in
[`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) §13; the engine-internal
answers are here.


1. **Does the owner want a 0-100 `EventScore`, or the structured event state of
   §5.3?** The staged spec recommends the engine *before* NewsScore is allowed to
   influence `opportunity_score` — a gate-shaped role, which the state satisfies and a score does not. **CLOSED 2026-09-17 (plan §13 Q7): the structured state is the deliverable** — no 0-100 `EventScore`.
2. **Should macro/Fed/OPEX be able to hard-block?** Today only earnings can
   (`catalyst.py:280-288`). Extending it is a **fail-closed behaviour change**
   that would start rejecting trades the engine currently takes; it needs the owner's explicit decision, not a default. **CLOSED 2026-09-17 (plan §13 Q7): not extended** — only earnings may hard-block, and a test pins it.
3. **The two "expected move" producers**: `options_surface.implied_move_pct:42`
   (ATM-implied, live) vs `catalyst.implied_move_from_history:111` (earnings
   history). Which is canonical for sizing? (Same question as
   [`RiskScore.md`](RiskScore.md) §7 Q4 — it must be answered once.) **DECIDED 2026-09-17:** `options_surface.implied_move_pct:42`
is **canonical** when a valid surface exists; `catalyst.implied_move_from_history:111`
is the **fallback and validation cross-check**; no reconciliation model. **`EventScore`
owns the authoritative field and `RiskScore` consumes it** - the same decision as
`RiskScore.md` §7 Q4, answered once, here.
4. **Is `EventScore` per-name or market-level?** Earnings and OPEX are name-level;
   CPI/FOMC are market-level. The owner's framing ("a high-impact event occurring right now") spans both. **DECIDED 2026-09-17:**
**both, with explicit scope** - `EventScope = NAME` (earnings, product, clinical,
litigation, investor day) and `EventScope = MARKET` (FOMC, CPI, payrolls, OPEX). A
stock report shows its name events plus the relevant market events, and each
underlying event keeps its own scope. **Market events do not become hard blockers**
(plan §13 Q7).
5. **Do product/clinical, court and investor-day calendars get built?** They are
   ABSENT, and the smallest honest producer is a forward-calendar adapter
   modelled on `moomoo.get_economic_calendar_moomoo:1813` + `catalyst._calendar_window:394`.
**DECIDED 2026-09-17:** this is **implementation coverage, not an architecture
question**. Define the four calendar interfaces (product, clinical, court, investor
day) each returning `available | missing | not_applicable`, and **never convert
missing calendar data to `score = 0`** - unknown is not "no event exists" and
certainly not "a negative event".

---

## 8. Outside the score set - intraday event-risk sizing vs latency (OPEN)

**This is the one event question the score set does not answer, and until
2026-09-17 it had no document home.** It is recorded here because `EventScore`
owns the event risk; it is **not** an engine-internal question and it does not
change any decision above.

**The question.** When an event lands *during* the session (a print, a headline, a
halt), may that fresh information **modify sizing** - and under what latency and
data-quality conditions? Today the answer is implicit: the daily score does not
move intraday (rule 9 / §13.2's metric-horizon contract), the hard block reads the
earnings window, and the governor never reads a score. What is undecided is the
path *between* those: a **separately authorised sizing input** fed by intraday
event information (the ledger statements of §13.1 allow exactly that - "potentially
separately authorised sizing mechanisms"), or nothing at all.

**Why it is not merely a vendor integration question.** A paid licensed feed (the
FinancialJuice class) would supply the events, but the feed is the easy half. The
hard half is the contract:

- **Latency.** What is the maximum age at which an intraday event may still change
  a size? A headline read 40 seconds late is a different instrument from one read
  4 seconds late, and the answer cannot be "as fresh as possible".
- **Data quality.** The event must arrive with a provenance and a confidence the
  sizing path can act on - an unconfirmed headline is not a print.
- **Idempotence and re-entry.** A size changed intraday must not be re-applied on
  every refresh, and the executor's idempotency key (`signals/` dedup) is the
  existing mechanism that would have to cover it.
- **The daily contract must not move.** Rule 9 (master) / §13.2 rule 9 (plan):
  daily is canonical, and an intraday metric joins the daily score only by
  explicit per-metric promotion. This question is about a **separate sizing
  authorisation**, never a silent second `TradeScore` input (master rule 17).
- **Fail-closed.** If the feed is stale or down, the existing behaviour must stand
  - no size change - rather than a size computed from partial data.

**Status: OPEN.** Not decided, not scoped, not started; it needs a feed decision
and a latency contract before any code. Recorded so that the next pass over the
event work finds it in a document rather than in a conversation.

## 9. The owner's formula library (`Strategies/scores/event_score.md`, 2026-09-26)

The owner's quantitative EventScore library was refreshed 2026-09-26 (17:41) and is
newer than this document. It is **2,126 lines, 120 numbered top-level sections and
28 `## N.M` subsection headings (148 headings), carrying 199 display equations.**
The count is mechanical: sections are the `^# ` headings, subsections the `^## `
headings, and formulas the `$$ … $$` display blocks (each pair counted once; inline
`\(…\)` and `$…$` math is not counted). It is the design-time companion to §1's
ledger, not its replacement: §1 lists the *occurrence* producers the engine reads;
the library enumerates the full quantitative surface an EventScore could measure, of
which §1 supplies the timing/occurrence axis alone. Against the code the 120 sections
resolve into **4 BUILT, 17 PARTIAL, 7 'elsewhere', 92 ABSENT** (§9.1).

**Delta against §1's ledger.** §1 and the Status line print producers for **4 of 7**
event families; the engine's own availability table marks **5 of 7 `SCORABLE`**
(`strategies/event_state.py::FAMILY_AVAILABILITY:107`, `product_clinical` gained a
producer — `dataflows/event_calendars.py::fda_calendar_rows:171` — on 2026-09-18), and
§1's own table already carries that row as `SCORABLE`. The library adds **no family**
— its taxonomy (line 1: M&A, management changes, capital actions, geopolitical events)
is broader still and maps onto none of the seven — so the 4-vs-5 count is a
doc-internal drift, ledgered here rather than silently rewritten.

**Delta against §5.3.** §5.3's Layer 3 ("the score, only if the owner wants one") and
§7 Q1 (CLOSED: "no 0-100 `EventScore`") are now behind the code: `event_state` at
`strategies/event_state.py::event_state:586` returns a 0-100 `score` (equal weights,
`EVENT_BANDS`, `RESEARCH_ONLY`). The library's §119/§120 supply exactly the Layer-3
architecture §5.3 deferred — the product form, `50 + 50·tanh(k·ES_raw)`, and weight
vectors — and the code adopts **none** of it (§9.4).

**The ten-part framing (`Strategies/scores/event_score.md:1-19`)** — the dimensions the
library says an EventScore should measure — checked against the code:

| # | Dimension | Producer? | Symbol / why not |
| --- | --- | --- | --- |
| 1 | Magnitude | **no** | no economic-magnitude producer; `strategies/catalyst.py::implied_move_from_history:111` is event *sizing*, not magnitude |
| 2 | Surprise | **partly** | `strategies/events.py::surprise_score:17` (relative `(act-est)/abs(est)`), `strategies/catalyst.py::last_earnings_surprise:70` |
| 3 | Direction | **partly** | `strategies/events.py::drift_side:26` (`beat`/`miss`/`flat`), `strategies/catalyst.py::fed_direction:184` (`HOLD`/`HIKE`/`CUT`) — labels, not a signed scalar |
| 4 | Probability | **no** | `strategies/catalyst.py::fed_imminence:142` `modal_prob` is a rate-path probability, not an event probability |
| 5 | Timing | **yes** | `strategies/event_state.py::imminence:349`, `::HORIZONS:66` |
| 6 | Persistence | **partly** | `strategies/events.py::expected_drift_after:56`, printed as `post_event_drift` (`agents/utils/analysis_tools.py:734`) |
| 7 | Market reaction | **partly** | `agents/utils/analysis_tools.py::get_earnings_event_read:660` print-day return + `volume_ratio` (a leaf read, not a scored component) |
| 8 | Credibility | **no** | `dataflows/event_calendars.py::ATTRIBUTION:68` is provenance, not a reliability score |
| 9 | Second-order effects | **no** | none |
| 10 | Event interaction | **no** | none |

### 9.1 The library's sections against the engine

One row per numbered library section: its formula count (display `$$` blocks) and its
status against the code. `BUILT` = the engine or its leaves emit the quantity;
`PARTIAL` = a producer covers part of it; `elsewhere` = a real producer exists outside
EventScore (RiskScore's leg, the options module) and is not read here; `ABSENT` = no
producer anywhere, with the nearest honest symbol where one exists.

| § | Title | Formulas | Status | Evidence (`path::symbol` / nearest) |
| --: | --- | --: | --- | --- |
| 1 | Core Event Representation | 3 | PARTIAL | `strategies/event_state.py::COMPONENTS:205` / `::FAMILY_COMPONENTS:299` (family imminence + flags, not a `(D,T,P,M,S,C,Q,H,X)` tuple) |
| 2 | Event Direction | 7 | PARTIAL | `events.drift_side:26`, `catalyst.fed_direction:184` (labels, not a signed scalar) |
| 3 | Event Magnitude | 7 | ABSENT | no economic-magnitude producer; `catalyst.implied_move_from_history:111` is sizing |
| 4 | Event Surprise | 3 | PARTIAL | `events.surprise_score:17` relative surprise only |
| 5 | Earnings Surprise | 6 | PARTIAL | EPS surprise via `events.surprise_score:17`; no revenue/EBITDA/margin/FCF leg |
| 6 | Earnings Surprise Composite | 3 | ABSENT | none |
| 7 | Guidance Surprise | 4 | ABSENT | none |
| 8 | Guidance Change | 3 | ABSENT | none |
| 9 | Analyst Estimate Revision | 4 | ABSENT | none |
| 10 | Estimate Dispersion | 2 | ABSENT | none |
| 11 | Consensus Confidence | 2 | ABSENT | none |
| 12 | Probability-Weighted Event Value | 3 | ABSENT | none |
| 13 | Expected Event Value | 2 | ABSENT | none |
| 14 | Expected Return From Event | 1 | ABSENT | none |
| 15 | Expected Loss | 1 | ABSENT | none |
| 16 | Event Asymmetry | 2 | ABSENT | none |
| 17 | Risk-Adjusted Event Value | 2 | ABSENT | none |
| 18 | Event Volatility | 2 | ABSENT | none |
| 19 | Event Sharpe | 1 | ABSENT | none |
| 20 | Event Information Ratio | 1 | ABSENT | none |
| 21 | Abnormal Return | 3 | PARTIAL | `get_earnings_event_read:660` print-day return (leaf read, not scored) |
| 22 | Market-Adjusted Abnormal Return | 1 | ABSENT | none |
| 23 | Cumulative Abnormal Return | 1 | ABSENT | none |
| 24 | Buy-and-Hold Abnormal Return | 1 | ABSENT | none |
| 25 | Event Reaction Strength | 2 | ABSENT | none |
| 26 | Volume Reaction | 2 | PARTIAL | `get_earnings_event_read:660` `volume_ratio` |
| 27 | Abnormal Volume | 1 | PARTIAL | `get_earnings_event_read:660` `volume_ratio` vs its 20d mean |
| 28 | Price × Volume Event Strength | 2 | ABSENT | none |
| 29 | Volatility Shock | 2 | ABSENT | none |
| 30 | Implied Volatility Event Signal | 1 | elsewhere | `catalyst.implied_move_from_history:111` |
| 31 | IV Skew Event Signal | 2 | elsewhere | `options_surface.iv_skew:25` |
| 32 | Options-Implied Event Move | 2 | elsewhere | `options_surface.implied_move_pct:42`; `moomoo_extra_tools.get_expected_move:274` |
| 33 | Event Surprise vs Market Move | 1 | ABSENT | none |
| 34 | Price Reaction Residual | 2 | ABSENT | none |
| 35 | Event Drift | 1 | PARTIAL | `events.expected_drift_after:56` -> `get_earnings_event_read:660` `post_event_drift` |
| 36 | Post-Earnings Announcement Drift | 2 | PARTIAL | `events.post_earnings_play:122`; drift printed as `post_event_drift` |
| 37 | Event Persistence | 2 | ABSENT | none |
| 38 | Event Decay | 2 | ABSENT | none |
| 39 | Time-Decay Weight | 2 | ABSENT | none |
| 40 | Event Recency Score | 1 | ABSENT | none |
| 41 | Catalyst Proximity | 2 | BUILT | `event_state.imminence:349` (linear clamp, not `e^-ld`/`1/(1+d)`) |
| 42 | Event Horizon Score | 1 | PARTIAL | `event_state.HORIZONS:60` per family (declared for 3 families) |
| 43 | Event Duration | 1 | ABSENT | none |
| 44 | Event Conviction | 1 | ABSENT | none |
| 45 | Source Reliability | 2 | ABSENT | nearest: `event_calendars.ATTRIBUTION:68` (provenance string, not a score) |
| 46 | Source Agreement | 1 | ABSENT | none |
| 47 | Evidence Breadth | 1 | ABSENT | none |
| 48 | Evidence Concentration | 1 | ABSENT | none |
| 49 | Information Confidence | 1 | ABSENT | none |
| 50 | Event Novelty | 2 | ABSENT | none |
| 51 | Information Surprise | 1 | ABSENT | none |
| 52 | Bayesian Event Update | 4 | ABSENT | none |
| 53 | Bayesian Surprise | 2 | ABSENT | none |
| 54 | Event Probability Revision | 2 | ABSENT | none |
| 55 | Hazard Rate | 1 | ABSENT | none |
| 56 | Survival Probability | 1 | ABSENT | none |
| 57 | Event Timing Probability | 1 | PARTIAL | `event_state.imminence:349` is a timing measure, not a probability |
| 58 | Event Clustering | 1 | ABSENT | none |
| 59 | Event Density | 1 | ABSENT | none |
| 60 | Event Overload | 1 | ABSENT | none |
| 61 | Event Correlation | 1 | ABSENT | none |
| 62 | Event Interaction | 3 | ABSENT | none |
| 63 | Event Synergy | 1 | ABSENT | none |
| 64 | Event Conflict | 1 | ABSENT | none |
| 65 | Net Event Exposure | 1 | ABSENT | none |
| 66 | EventScore Raw | 1 | PARTIAL | `event_state.event_state:586` equal-weight combine, not the library's product |
| 67 | EventScore Normalization | 2 | PARTIAL | `event_state.event_state:586` `combine`/`align` to 0-100, inverted; not tanh |
| 68 | Cross-Sectional EventScore | 2 | ABSENT | none |
| 69 | Sector-Relative EventScore | 1 | ABSENT | none |
| 70 | Market-Relative EventScore | 1 | ABSENT | none |
| 71 | Event Alpha | 2 | ABSENT | none |
| 72 | Event Beta | 1 | ABSENT | none |
| 73 | Event-to-Price Elasticity | 2 | ABSENT | none |
| 74 | Event-to-Valuation Elasticity | 1 | ABSENT | none |
| 75 | Event-to-Earnings Elasticity | 1 | ABSENT | none |
| 76 | Event Materiality | 1 | ABSENT | none |
| 77 | Market-Cap Materiality | 1 | ABSENT | none |
| 78 | Valuation Gap Created by Event | 3 | ABSENT | none |
| 79 | DCF Event Impact | 2 | ABSENT | none |
| 80 | Event-Implied Fair Value | 2 | ABSENT | none |
| 81 | Catalyst Risk/Reward | 1 | ABSENT | none |
| 82 | Event Expected Value | 1 | ABSENT | none |
| 83 | Event Risk | 1 | elsewhere | `events.catalyst_risk_penalty:63` (RiskScore's leg, `EventScore.md` sec 0.2) |
| 84 | Tail Event Risk | 1 | elsewhere | `book_risk.book_correlated_stress:146` |
| 85 | Event CVaR | 1 | elsewhere | `book_risk.cvar:18` |
| 86 | Event VaR | 1 | elsewhere | `book_risk.cvar:18` |
| 87 | Event Risk-Adjusted Score | 1 | ABSENT | none |
| 88 | Event Quality Score | 1 | ABSENT | none |
| 89 | Catalyst Strength | 1 | ABSENT | none |
| 90 | Catalyst Conviction | 1 | ABSENT | none |
| 91 | Catalyst-to-Risk Ratio | 1 | ABSENT | none |
| 92 | Event Momentum | 1 | ABSENT | none |
| 93 | Event Momentum Acceleration | 1 | ABSENT | none |
| 94 | Event Trend | 2 | ABSENT | none |
| 95 | Event Regime | 1 | ABSENT | none |
| 96 | Event Volatility | 1 | ABSENT | none |
| 97 | Event Stability | 1 | ABSENT | none |
| 98 | Event Confidence Interval | 1 | ABSENT | none |
| 99 | Bootstrap Event Confidence | 1 | ABSENT | none |
| 100 | Historical Event Hit Rate | 1 | ABSENT | none |
| 101 | Conditional Hit Rate | 2 | ABSENT | none |
| 102 | Historical Event Return | 1 | ABSENT | none |
| 103 | Conditional Event Return | 1 | ABSENT | none |
| 104 | Event-Type Alpha | 1 | ABSENT | none |
| 105 | Event-Type Sharpe | 1 | ABSENT | none |
| 106 | Bayesian Historical Event Model | 1 | ABSENT | none |
| 107 | Sample-Size Confidence | 1 | PARTIAL | `event_state.EVENT_MIN_COVERAGE:333` + `score_engine.coverage_floor` |
| 108 | Data Coverage Score | 1 | BUILT | `event_state.event_state:586` coverage; `event_calendars.calendar_coverage:269` |
| 109 | EventScore Coverage Adjustment | 1 | BUILT | `event_state.event_state:586` (NA lowers coverage, never the score) |
| 110 | Missing-Data Penalty | 1 | PARTIAL | NA!=0 lowers coverage; withheld below `EVENT_MIN_COVERAGE` (`event_state.py:333`) |
| 111 | Event Confidence Adjustment | 1 | ABSENT | none |
| 112 | Event Conflict Adjustment | 1 | ABSENT | none |
| 113 | Event Overlap Adjustment | 2 | ABSENT | none |
| 114 | Event Independence Adjustment | 1 | ABSENT | none |
| 115 | Event Evidence Score | 1 | ABSENT | none |
| 116 | Event Confidence Composite | 1 | ABSENT | none |
| 117 | Event Impact Composite | 1 | ABSENT | none |
| 118 | Event Timing Composite | 1 | BUILT | `event_state.event_state:586` equal-weight composite over imminence |
| 119 | Final EventScore Architecture | 4 | PARTIAL | `event_state.event_state:586`; equal-weight/inverted, not the library's product form |
| 120 | Recommended EventScore Sub-Engines | 4 | PARTIAL | only the Timing/Coverage sub-engines exist (`event_state.py`) |

### 9.2 Not built — the backlog the library names

The 92 `ABSENT` rows are the library's backlog for this engine, and they cluster into
the dimensions above that have no producer: magnitude (§3), probability and the hazard/
Bayesian family (§12-13, §52-57), the market-reaction battery (§21-34), persistence and
decay (§37-40), credibility/evidence (§45-51), the normalisation and cross-sectional
axis (§67-71), materiality/valuation (§76-80), the risk split (§81-87), momentum/regime
(§92-97), historical base rates (§100-107), and the confidence/quality composites
(§111-117). **The library's own answer is the Layer-3 composite (§119-120)**, which the
code delivers only in its narrowest form (§9.4). §4's engine backlog is unchanged and
still the shortest honest path: court and investor-day calendars have no source, the 0-1
imminence scalar is unbuilt beyond `imminence:349`, and no non-earnings event may
hard-block.

### 9.3 Library-internal defects (verified)

- **Duplicate and near-duplicate section titles.** `# 18. Event Volatility` (`Var(R)=Σ P_i(R_i-E[R])²`) and `# 96. Event Volatility` (`EventVol = Std(EventScore_t)`) share a title for two different quantities. `# 13. Expected Event Value` vs `# 82. Event Expected Value`; `# 16. Event Asymmetry` (`P_up·R_up / P_down·|R_down|`) vs `# 81. Catalyst Risk/Reward` (`ExpectedUpside/ExpectedDownside`) — the same ratio under two names; `# 44. Event Conviction` vs `# 90. Catalyst Conviction`; `# 3. Event Magnitude` (the "Fundamental impact score") vs `# 117. Event Impact Composite`.
- **Three mutually inconsistent "raw" composites.** `# 1` defines `EI = D·P·M·S·C`; `# 66` defines `ES_raw = Σ_i D_i·P_i·M_i·S_i·C_i·Q_i·W_i` (a *sum* of products, adding source quality Q and time decay W); `# 119` defines `ES_raw = Direction·Impact·Probability·Surprise·Confidence·Timing·Novelty` (a single product, adding Timing and Novelty, dropping Q). They cannot all be the engine's `ES_raw`.
- **Repeated normalisation.** `50 + 50·tanh(k·raw)` appears at `# 1`, `# 13`, `# 67` and `# 119`, with `k` folded differently each time; `# 67` also offers `100·Φ(Z)` as an alternative with no reconciliation.
- **Sign-inconsistent expected value.** `# 12`/`# 14` add the neutral outcome (`+P_neutral·Impact_neutral`); `# 82` subtracts one (`EV = P_up·U − P_down·D − P_neutral·C`).
- **Linear, non-unique numbering.** 120 top-level sections plus 28 unnumbered `## N.M` subsections (148 headings); topics recur across non-adjacent numbers (volatility at 18 and 96, expected value at 13 and 82), so the numbering is a catalogue, not a taxonomy.

### 9.4 Contradictions between the library and the code

- **§0.2 (the RiskScore event-leg overlap).** The library states the right principle in
  words — EventScore "doesn't have to become a disguised risk score" (`:2111`) — but then
  places the exposure measures *inside* the EventScore library: `# 83. Event Risk`, `# 84.
  Tail Event Risk`, `# 85. Event CVaR`, `# 86. Event VaR`. §0.2 assigns those to
  RiskScore's event leg, and the code agrees with §0.2, not the library:
  `strategies/events.py::catalyst_risk_penalty:63` (the exposure multiplier),
  `strategies/book_risk.py::book_correlated_stress:146`, `::cvar:18`. `event_state.py`
  declares no event-risk component and never imports the sizing or risk path — so the
  library's risk sections must not be read as EventScore output.
- **§0.3 (the hard block is the only fail-closed event path).** The library contains **no
  gate or block formula** (the only occurrence of "block"/"gate" in 2,126 lines is the
  `:2111` prose sentence). Its surprise (§4-6) and probability (§12-13, §52-57) formulas
  are **measurement** formulas: `strategies/events.py::surprise_score:17` feeds
  `last_earnings_surprise:70`'s label, and `catalyst.build_catalyst_snapshot:219`'s
  `hard_block` is set only on `earnings.days_until <= catalyst_hard_block_days`. Neither
  the library's surprise nor its probability formulas gate anything, and no score here
  reaches `GATE_PRECEDENCE`.
- **§0.1 ("no weight table — and that is not an omission to fill in").** The library
  *does* publish weight vectors — `# 117` `w1..w5`, `# 118` `w1..w4`, `# 88` `w1..w5`, and
  the Impact/Confidence composites of `# 119` — and `# 120` proposes a 25-way sub-engine
  split. The code adopts none of them: `strategies/event_state.py::event_state:586` runs
  `weights=None`, takes equal weights (1.0 per family) and **prints that no vector is
  published** ("no weight vector is published for this engine (EventScore.md section
  0.1)"). The library supplies the architecture §0.1 declines to invent; the machine
  still has no measured vector, so §0.1's point stands even though the library now
  contains the fill-in.
- **Direction of the 0-100 scale.** The library's "Suggested 0-100 interpretation"
  (`:2113-2126`) is **directional** (90-100 = "extremely strong positive event evidence",
  0-9 = "extremely strong negative"). The engine's scale is **inverted and
  direction-neutral**: `EVENT_BANDS` at `strategies/event_state.py:322` is
  `event-window`/`imminent`/`approaching`/`quiet`/`clear`, and the `basis` string states
  "SCALE IS INVERTED RELATIVE TO THE OTHER ENGINES - 100 means an event is on top of us".
  The library's band table must not be read onto the engine's score.

---

## Appendix — methodology ledger

| Claim | Source | Where it bites |
| --- | --- | --- |
| Pre-FOMC announcement drift: large average excess returns in the 24h before scheduled FOMC announcements — **but the effect has weakened or disappeared in recent years** | Lucca & Moench (2015) and later work | §0.4 — `fed_imminence:142` is an imminence input, never a directional bias |
| An **earnings announcement risk premium** exists (~13bp average) and implied volatility rises before the release then drops discontinuously after (vol crush) | the earnings-options literature | §0.4 and §1's implied-move rows |
| Option-expiration weeks show abnormal returns and pricing patterns; non-expiring IVs rise before and fall after the third Friday | the OPEX literature | §1's OPEX row — `opex_status:127`'s flags are the right shape |
| Expected move ≈ annualized IV / 16 for one day, or the ATM straddle price directly | practitioner standard | §0.4 and §7 Q3 — pins which producer is canonical |
| Scheduled-event windows concentrate risk: the position can be gapped through a stop on a print | the event-risk literature | §0.3 — why the hard block is the engine's authoritative event signal |

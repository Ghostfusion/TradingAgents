# EventScore — design

**Part of the score-engine design set: [`README.md`](README.md)** (master).
Siblings: [`FundamentalScore.md`](FundamentalScore.md),
[`TechnicalScore.md`](TechnicalScore.md), [`RegimeScore.md`](RegimeScore.md),
[`NewsScore.md`](NewsScore.md), [`SentimentScore.md`](SentimentScore.md),
[`RiskScore.md`](RiskScore.md).

**Scope: the event engine only.** The owner recommends it as the **seventh**
engine, and gives it no weight table. Its question is *"is a high-impact event
happening right now?"* — **occurrence and imminence** — as distinct from
`NewsScore` (*information flow*) and from `RiskScore`'s event leg (*the exposure
the event creates*).

His reason for adding it is explicit and is this document's governing constraint:
it should exist **before `NewsScore` is allowed to influence
`opportunity_score`**.

Status: **design (2026-09-17). Not started.** Occurrence producers exist for
**4 of 7** event families (§1); the hard block exists and is the engine's only
event-triggered fail-closed path (§0.3).

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
| `events.catalyst_risk_penalty:53` | (invoked inside the snapshot, `catalyst.py:266`) | the exposure multiplier itself — implied move vs baseline |
| `catalyst.implied_move_from_history:111` → `implied_move` | event sizing context | intended `contract.build_position_contract`'s `implied_move_pct` (`contract.py:118`, `:262-267`) — **never populated** (§3 D1) |
| `events.position_mult_by_side:37` | the side label via `drift_side:26` | `get_beat_miss_sizing:2252`'s position multiplier |
| `book_risk.book_correlated_stress:128` | — | macro-event correlated tail loss |
| `regime.regime_gate_read:178`'s `catalyst_window` | an event-regime veto input | an entry veto — **never fed** (§3 D3) |

**The design rule**: `EventScore`'s components are the **occurrence** measures
(imminence day-counts, window flags, the hard block); `RiskScore`'s event leg
keeps the **exposure** measures (implied move, the risk penalty, the size
multiplier). Neither may re-derive the other's number (master rule 3). Where one
producer serves both, the producing engine is named in both tables.

### 0.3 The hard block — already the engine's only event fail-closed path

`build_catalyst_snapshot:219` sets `hard_block` (`catalyst.py:284-288`, key
`:358`) **only** when `earnings.days_until <= catalyst_hard_block_days` (default
5, `default_config.py:793`). **Macro, Fed and OPEX never set it.** It then exits
through three places:

1. `graph/trading_graph.py:1061-1070` — REJECT `risk_gate` ("forced REJECT
   regardless of size").
2. `pre_market.catalyst_window_read:103` → `{hard_block: True, scale: 0.0}`;
   `review_decision:198` (branch `:240-245`) → REJECT — **unreachable from its
   own leaf** (§3 D2).
3. `regime.regime_gate_read:261` — advisory, and inert (§3 D3).

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
| Earnings — snapshot leg | `catalyst.build_catalyst_snapshot` (`catalyst.py:219`, earnings branch `:265`) | `catalyst_window_days` default 5 (`default_config.py:785`) | multiplies `scale` by `catalyst_risk_penalty` | YES at `:284` | lower scale = risk-increasing | SCORABLE |
| Earnings — last surprise / side | `catalyst.last_earnings_surprise` (`catalyst.py:70`); `events.surprise_score` (`events.py:17`); `events.drift_side` (`events.py:26`) | most recent report in calendar | `{surprise: ratio, side: 'beat'|'miss', date}`; surprise = (act-est)/|est| | no | beat = favourable | SCORABLE |
| Earnings — implied move (exposure) | `catalyst.implied_move_from_history` (`catalyst.py:111`) | latest history row | fraction (`predict_vola_ratio_newest/100`) | no | larger = more risk | SCORABLE |
| Earnings — risk multiplier | `events.catalyst_risk_penalty` (`events.py:53`) | none (implied vs baseline) | multiplier <=1 (0.5 when unknown; `1/(1+3r)`) | no | lower = more risk | SCORABLE |
| Earnings — PEAD entry | `events.post_earnings_play` (`events.py:112`); `events.gap_up_qualifies` (`:63`) | print + 4 bars | verdict `setup/consolidating/no-gap/no-data` | no | setup = favourable | SCORABLE |
| Earnings — position mult by side | `events.position_mult_by_side` (`events.py:37`) | none | 1.0 beat / 0.5 miss / 0.0 flat, cap 1.5 | no | higher = favourable | PARTIAL (catalyst arg inert, see §3 D4) |
| Macro (CPI/FOMC/payrolls) imminence | `catalyst.macro_imminence` (`catalyst.py:123`) | `window_days=3`; `star=='HIGH'` filter | `{count_high:int, min_days:int|None}` | no | imminent = risk-increasing | SCORABLE |
| Fed — next FOMC | `catalyst.fed_imminence` (`catalyst.py:142`) | `window_days=14` default; snapshot passes `catalyst_fed_window_days`=10 | `{days_until:int, modal_prob:%, modal_range:str}` | no | modal hike = risk-increasing | SCORABLE |
| Fed — direction label | `catalyst.fed_direction` (`catalyst.py:184`) | none | `HOLD`/`HIKE`/`CUT`/`n/a` | no | hike = risk-increasing | SCORABLE |
| Macro backdrop (fallback) | `massive.fetch_macro_backdrop` (`tradingagents/dataflows/massive.py:398`) | 90d look-back; only when both fed+econ calendars absent | 0..1 de-risk mult (0.7 inversion x0.75 breakeven), `verdict` | no | lower = risk-increasing | SCORABLE (constant thresholds `_INVERSION_SCALE=0.7`, `_BREAKEVEN_SCALE=0.75`, `massive.py:392-395`) |
| OPEX / expiry | `derivatives_gamma.opex_status` (`derivatives_gamma.py:127`); `opex_dates` (`:116`); `opex_note` (`:165`) | third-Friday monthly cycle; `days_to_next`; OPEX week = ISO-week equality; post-OPEX unwind = Mon/Tue within 1-4d of prev expiry | `{next_opex, prev_opex, days_to_next:int, in_opex_week:bool, post_opex_unwind:bool, quarterly:bool}` | no | OPEX-week/unwind = structure risk, not favourable | SCORABLE (booleans, no 0-1) |
| Product launch / clinical / FDA | — | — | — | — | — | ABSENT |
| Court decision | — (only LM litigation lexicon, `strategies/text_factors.py:104-109`, news tone) | — | — | — | — | ABSENT |
| Investor day | — | — | — | — | — | ABSENT |
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

- `scale` range: `max(catalyst_scale_floor, min(1.0, scale))` at `catalyst.py:349`; floor default 0.25 (`default_config.py:792`).
- `hard_block` triggers only when `block_days > 0 and earnings.days_until <= block_days` (`catalyst.py:280-288`), `block_days = catalyst_hard_block_days` default 5 (`default_config.py:793`). Macro/Fed/OPEX never set it.
- Surfaced by leaf `get_catalyst_scale` (`analysis_tools.py:617`), bound to the **news analyst** toolset (`agents/toolsets.py`, `news_tools()` list line 370). Also folded live at `graph/trading_graph.py:836-839`.

**Overlap with RiskScore's event leg (function-by-function; the exposure side):**

| Same producer | Read by EventScore as | Read by RiskScore's event-exposure leg as |
| --- | --- | --- |
| `catalyst.build_catalyst_snapshot` (`catalyst.py:219`) `scale` | occurrence/imminence folded scalar | `contract.build_position_contract` `catalyst_scale` param (`contract.py:115`, applied `:208-212`); `catalyst.fold_catalyst_into_overlay` (`catalyst.py:362`); `pre_market.catalyst_window_read` (`pre_market.py:103`) |
| `events.catalyst_risk_penalty` (`events.py:53`) | (invoked inside snapshot, `catalyst.py:266`) | the exposure multiplier itself — implied move vs baseline |
| `catalyst.implied_move_from_history` (`catalyst.py:111`) -> `implied_move` | event sizing context | intended `contract.build_position_contract` `implied_move_pct` (`contract.py:118`, `:262-267`) — **never populated** (see §3 D1) |
| `events.position_mult_by_side` (`events.py:37`) | side label via `drift_side` | `get_beat_miss_sizing` (`analysis_tools.py:2252`) position multiplier |
| `book_risk.book_correlated_stress` (`book_risk.py:128`) | — | macro-event correlated tail loss ("a macro event moves every position at once") |
| `regime.regime_gate_read` `catalyst_window` (`regime.py:178`) | event-regime veto input | entry veto; **never fed** (see §3 D3) |

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
| `get_opex_read` (`analysis_tools.py:3108`) | market `:241` | next expiry, OPEX-week flag, post-OPEX unwind | YES |
| `get_derivatives_flow` (`analysis_tools.py:3142`) | market `:240` | gamma + OPEX + IV combined | YES |
| `get_premarket_review` (`analysis_tools.py:6561`) | market `:303` | CONFIRM/REVISE/REJECT from gap + re-anchor | PARTIAL — no catalyst_snapshot passed (§3 D2) |
| `get_beat_miss_sizing` (`analysis_tools.py:2252`) | news `:372` | position multiplier by side | YES |
| `get_regime_gate_read` (`analysis_tools.py:8467`) | market (via `market_tools()`), leaf arg `catalyst_window` default False | knife-guard verdict | PARTIAL — caller-supplied bool, no producer (`:8496`) |
| `get_ipos` (`moomoo_extra_tools.py:178`) | news `:363` | pending IPOs | YES (universe/event input) |
| `get_earnings_surprise_history` (`moomoo_extra_tools.py:246`) | fundamentals `:394` | historical surprises + implied moves | YES |
| `get_earnings_surprise` (`analysis_tools.py:1474`) | fundamentals `:392` | computed surprise | YES |
| `get_event_pnl_response` (`analysis_tools.py:8102`) | market `:331` | delta-gamma-vega-theta P&L per option unit | YES |
| `get_option_breakeven` (`analysis_tools.py:2947` args; `strategies/options_breakeven.catalyst_window:105`) | market `:235` | earnings-window flag on the sold call | PARTIAL — `days_to_earnings` caller-supplied |
| `get_session_discipline` (`analysis_tools.py:4871`) | market `:278` | walk-away / psych levels (not event) | YES (non-event) |

#

---

## 3. Defects and dead seams

- **D1 — dead `implied_move_pct` key (exposure never scaled) — **FIXED 2026-09-17, `2c05701`**.** `graph/trading_graph.py:966` reads `(catalyst_snapshot or {}).get("implied_move_pct")`, but the producer emits `"implied_move"` (`strategies/catalyst.py:352`) and never `implied_move_pct`. So `contract.build_position_contract`'s `(1 - implied_move_pct)` de-risk (`strategies/contract.py:262-267`) is unreachable. Reader sees a report whose implied-move sizing is documented but never applied; only the `scale` fold moves size.
- **D2 — premarket hard block unreachable from its leaf — **FIXED 2026-09-17, `2c05701`**.** `analysis_tools.py:6586-6593` calls `pre_market.review_decision(...)` without `catalyst_snapshot=`, while `strategies/pre_market.py:239` reads it to raise the earnings-window REJECT (and `:246` the REVISE). The leaf therefore can only REJECT/REVISE on gap and re-anchor caps, never on an open earnings window.
- **D3 — `regime_gate_read.catalyst_window` always False — **FIXED 2026-09-17, `2c05701`**.** `strategies/regime.py:261` blocks when `catalyst_window` is set; callers pass `False` (`trading_graph.py:1267`; `value_dip_tools.py:738`) or a caller-defaulted param never fed from the snapshot (`value_dip.py:1005/1137`). No producer maps `build_catalyst_snapshot` imminence -> `True`. The RegimeScore "event regime" veto and the `catalyst-window` verdict are dead in the live graph.
- **D4 — `events.position_mult_by_side` catalyst arg inert.** `events.py:42` uses `event_scale = catalyst if catalyst > 1 else 1.0`, but the only caller documents `catalyst` as `0..1` (`analysis_tools.py:2254` "catalyst scale 0..1") and `get_catalyst_scale` supplies <=1. `event_scale` is therefore always 1.0; the multiplier is only 1.0 (beat) / 0.5 (miss).
- **D5 — `get_earnings_calendar` param named backward for a forward query.** The leaf arg is `look_back_days` "Days to look back" (`analyst_data_tools.py:33`), but the finnhub adapter queries `[curr_date, curr_date + look_back_days]` forward (`dataflows/finnhub.py:195-196`). A caller setting it small truncates the forward window.

#

---

## 4. What is ABSENT, and the smallest honest producer

| Component | Data needed | Engine already fetches? | Smallest honest producer |
| --- | --- | --- | --- |
| FDA / clinical decisions | a forward PDUFA / trial-readout calendar | NO — no vendor category in `dataflows/interface.py` `VENDOR_METHODS`; `patents` is a backward metric (`patentsview.py:57`) | new forward-calendar adapter modelled on `moomoo.get_economic_calendar_moomoo` (`dataflows/moomoo.py:1758`) + the chunked window reader `catalyst._calendar_window` (`catalyst.py:394`) |
| Court decisions | a litigation/docket calendar | NO — only the LM litigation lexicon scoring news tone (`text_factors.py:104-109`) | same forward-calendar pattern; none exists |
| Investor day / product launch | a company-events calendar | NO — nearest are `get_corporate_actions` (dividends/splits) and `get_ipos` (`moomoo_extra_tools.py:178`) | forward company-events calendar; none exists |
| Earnings imminence > 60d | horizon beyond `next_earnings.lookahead_days=60` (`catalyst.py:90`), fetch window +95d (`catalyst.py:493`) | YES (fetch is wider than the read) | raise `lookahead_days`; no new adapter |
| Scalar 0-1 imminence | normalization of existing day-counts | YES — raw counts already returned | pure `clamp(1 - days_until/horizon, 0, 1)` over `next_earnings.days_until` / `macro_imminence.min_days` / `fed_imminence.days_until` / `opex_status.days_to_next`; no new fetch |
| Hard block for macro/Fed/OPEX | a rule to close on imminent non-earnings events | YES (calendar fetched) | extend `build_catalyst_snapshot` (`catalyst.py:280`) to set `hard_block` from `macro_imminence.min_days` / `fed_imminence.days_until` against a configured window |
| Weights / composite | any EventScore band or weight structure | NO — every producer is a multiplier or gate; no 0-100 score anywhere | needs (a) per-family imminence 0-1, (b) per-family impact/severity, (c) NA!=0 handling; nothing exists to reuse |

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
   modelled on `moomoo.get_economic_calendar_moomoo:1758` + `catalyst._calendar_window:394`.
**DECIDED 2026-09-17:** this is **implementation coverage, not an architecture
question**. Define the four calendar interfaces (product, clinical, court, investor
day) each returning `available | missing | not_applicable`, and **never convert
missing calendar data to `score = 0`** - unknown is not "no event exists" and
certainly not "a negative event".

---

## Appendix — methodology ledger

| Claim | Source | Where it bites |
| --- | --- | --- |
| Pre-FOMC announcement drift: large average excess returns in the 24h before scheduled FOMC announcements — **but the effect has weakened or disappeared in recent years** | Lucca & Moench (2015) and later work | §0.4 — `fed_imminence:142` is an imminence input, never a directional bias |
| An **earnings announcement risk premium** exists (~13bp average) and implied volatility rises before the release then drops discontinuously after (vol crush) | the earnings-options literature | §0.4 and §1's implied-move rows |
| Option-expiration weeks show abnormal returns and pricing patterns; non-expiring IVs rise before and fall after the third Friday | the OPEX literature | §1's OPEX row — `opex_status:127`'s flags are the right shape |
| Expected move ≈ annualized IV / 16 for one day, or the ATM straddle price directly | practitioner standard | §0.4 and §7 Q3 — pins which producer is canonical |
| Scheduled-event windows concentrate risk: the position can be gapped through a stop on a print | the event-risk literature | §0.3 — why the hard block is the engine's authoritative event signal |

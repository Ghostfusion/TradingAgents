# Design — the exit engine: five mechanisms, one decision

**Status: landed 2026-10-16.** `tradingagents/strategies/exit_engine.py` (the engine),
`scripts/exit_engine.py` (the operator report), the `get_exit_engine` tool (bound to the
market analyst), the gate `enable_exit_engine` (ships **off**), and
`tests/test_exit_engine.py` (17 tests).

**Brief.** A pasted "how to build a proper exit system for a momentum trading strategy"
(§1 five mechanisms, §2 a priority order, §3 five formulas, §4 a sample Python engine,
§5 a worked trade, §6 an `ExitEngine`/`ExitScore` shape with a five-value output, §7 a
validation ladder). A pasted brief is a **LEAD** (rule 11), so every load-bearing claim
was re-grounded on a primary source and the tree was checked *before* anything was built.
Two of the brief's parameter claims were confirmed, two of its rules were measured to be
weak, one sample function does not exist, and most of its architecture was already here.

**Takeaway.** The tree already had four of the five mechanisms as producers, so this is a
**composition** module (one ATR convention, the existing ladder, the existing chandelier,
the existing §58 horizon) plus exactly four things nothing answered: a *confirmed* trend
break, momentum deterioration as *persistence*, the opportunity-cost stall, and a
point-in-time walk that publishes one action from the five. It re-implements nothing, and
every parameter it defines traces to a source that was read.

---

## 1. What already existed, and was not rebuilt

| Brief's mechanism | The producer already in the tree |
|---|---|
| initial protective stop | `size.atr(high, low, close, window)` — a **simple mean of the last `window` true ranges** — and `size.stop_loss_atr(..., atr_mult=2.0)`; `contract.atr_with_source` names the basis (`"h/l"` vs a close-to-close `"proxy"`); `contract.build_position_contract(atr_mult=2.0)` sizes off the same stop |
| trailing stop | `swing.chandelier_exit(closes, atr, window=22, k=3.0, highs=...)` — "highest high in window − k × ATR" — already printed by the `get_swing_exits` tool; `exits.trailing_stop_exit(entry, peak, current, atr_value, atr_mult)` is the stateless peak-trail variant; `risk_manager.trailing_stop_targets` is the Lean L4 override pass |
| risk / thesis-break exit | `exits.EXIT_PRECEDENCE` (`risk_gate, stop, trailing_stop, target, thesis_break, time_exit, expected_value`) and `exits.exit_decision(...)`, which already implements §101's truth table with fail-closed conditions; `risk_manager.manage_risk` (the Lean L1 second pass); `risk_governor` for the gate verdict |
| time exit | `exits.time_exit(days_held, max_holding_days, min_holding_days)` — §58 — with `None` (not `False`) when the horizon is unknown |
| the priority order | §101's own ladder, already a tuple in `exits.py` |
| cost netting | `exits.net_of_cost(gross, cost_bps, illiq)` |

Tools already bound for exits: `get_swing_exits`, `get_trailing_exit`, `get_exit_check`,
`get_exit_plan`, `get_scaleout_plan` (market analyst + trader + the risk debators). Gates
already present: `enable_exits` (wired), `enable_trailing_exit` and `enable_risk_manager`
(inert). The owner's own spec is `Strategies/entry_exit.md` — §101 (the composite
`ExitPrice` and the exit truth table), §58 (time exit), §68 (the per-share risk the entry
carries), §103 (the price families) — and the engine obeys it rather than replacing it.

## 2. The brief, line by line

| The brief says | Verdict | Why |
|---|---|---|
| 2.5 × ATR initial stop | **ADOPT** | LeBeau: "my favorite initial stop is placed 2 or 3 ATRs below my entry point". Alvarez's 10-year R-multiple study: the **2.5 × ATR max loss evaluated at the close** was the best of every stop type tested (776 total R vs 164 with no stop). |
| 3 × ATR trailing from the high-water mark since entry | **ADOPT with a caveat** | LeBeau's chandelier is exactly this ("3 ATRs below the highest high … since the trade was entered"). But Alvarez measured the trailing stop as the one type that did **not** add value on a medium-term breakout (~200-250 total R, negative at tight multiples), so it is a switch and `compare_exit_variants` ships to measure it here. |
| "the stop never moves down" (`max(Stop_{t-1}, HH_t − k·ATR_t)`) | **ADOPT** | A stop that can fall is not a trailing stop. `trailing_stop_level` is that `max`, and a test pins monotonicity. |
| test **today's low** against the stop | **DECLINE as the default** | Alvarez: end-of-day evaluation beat intraday by ~30 % on identical stops (776 vs 607 total R). `stop_evaluation='close'` is the default, `'intraday'` is available. |
| "calculate the stop from information available before the current bar … update the high-water mark only after the current bar has been evaluated" | **ADOPT, and it is the point** | This is the walk's contract; `test_the_stop_in_force_ignores_the_bar_it_is_tested_on` pins it with a spike bar (the exit must land on the bar *after* the spike). |
| a confirmed MA50 breakdown (two consecutive closes) | **ADOPT** | LeBeau: "exit using moving averages … 30 to 50 days works well for stocks". Confirmation is what costs the "be patient" advice. |
| momentum exit at `M < 35` for 3 sessions | **ADOPT the shape, CHANGE the number** | The composite's own `MOMENTUM_BANDS` edges are 90/75/60/**40**/25/10: 35 sits *inside* the first band below "neutral", so the default is the **band edge 40** — a threshold is the producer's number (the same rule the momentum screener obeys). |
| time/stall exit: `D ≥ 20 ∧ R ≤ 0 ∧ RS deteriorating` | **BUILD, SHIP OFF** | Alvarez measured this exact rule on a momentum breakout: CAR and maximum drawdown essentially unchanged, win rate and average P/L materially lower, trade count higher; a practitioner in the same thread ("stale exits remove the first movers … diluted returns"). Available, default-off, until a run here measures it improving something. |
| "Shares = floor(RiskBudget / (entry − stop))" | **ALREADY BUILT** | `contract.build_position_contract` (risk-per-trade, Kelly, volatility target, the price cap) and the sizing tools. The engine deliberately does not re-derive size. |
| `ExitEngine` / `ExitScore` with `HOLD / REDUCE / EXIT / RISK_EXIT / UNAVAILABLE` | **ADOPT** | `EXIT_ACTIONS` + `classify_exit`. The vocabulary is the brief's; the ladder behind it is the repo's. |
| §4's sample code | **CANNOT RUN AS PASTED** | It calls `evaluate_long_exit(...)`, which the brief never defines (only `add_exit_indicators` is given); its LaTeX has been mangled by the HTML paste (`|H_t − C_{t-1}|` renders as `\|H_t-C\_{t-1}|`); and it assumes a per-bar `momentum_score` column, which this repo's composite does not have (the score-history store holds **one row per scored run date**, not a bar series). |
| §7 "backtest at least four variants on identical entries" | **ADOPT** | `compare_exit_variants` runs the four (initial only; +trailing; +trend; +momentum/stall) over one entry and reports the outcome, the rule that fired, net return, holding days, the peak gain and the share of it surrendered. |

## 3. The spec as built

### 3.1 `ExitConfig`

`atr_period=14`, `initial_atr_multiple=2.5`, `trailing_atr_multiple=3.0`,
`trailing_window=22`, `trend_ma_period=50`, `trend_confirm_bars=2`,
`momentum_exit_threshold=40.0` (the band edge), `momentum_confirm_bars=3`,
`max_stalled_bars=20`, `max_holding_days=None`, `min_holding_days=None`,
`enable_trailing/enable_trend/enable_momentum=True`, `enable_stall_exit=False`,
`stop_evaluation="close"`, `reduce_within_atr=1.0`, `cost_bps=10.0`.
`ExitConfig.resolved()` repairs incoherent input **visibly** (an unknown
`stop_evaluation` becomes `"close"`, a zero period becomes 2) rather than at the
call site. The `enable_*` fields are the four-variant switches; the *global* gate is
`enable_exit_engine`.

### 3.2 The walk's point-in-time contract

For each bar `t` after the entry bar:

1. the ATR, the high-water mark and the chandelier are computed from bars **through
   `t−1`** — the stop being tested on `t` is the one that existed when `t` opened;
2. the price rules are tested against `t` (the close under `"close"`, the low under
   `"intraday"`);
3. the trend/momentum rules are evaluated on the series **through `t`** (a signal known
   at `t`'s close);
4. **only then** may `t`'s high raise the high-water mark and set the next bar's stop.

Fills are never invented. `"close"`: the signal is known at the close, so the fill is the
**next bar's open** (else its next close, else the last close) — a gap-down therefore
fills *worse* than the stop, which is what the brief's own caveat asks for.
`"intraday"`: the stop is tested against the low and fills at the stop, or at that bar's
**open** when the bar gapped through it. The walk stops at the first firing bar: once an
exit has fired the position is flat, and `action` is that exit's action.

### 3.3 The four rules this module adds

* `sma_break_confirmed(closes, period=50, confirm_bars=2)` → `{break, ma, below, bars_below}`.
  `break` is `None` when the history cannot decide it (needs `period + confirm_bars − 1`
  closes). Its SMA is pinned by test to `technical_factors.sma_legs`' `sma_fast` — the
  series exists only because a *confirmation* is about consecutive closes, which no
  scalar producer answers.
* `momentum_deterioration(scores, threshold=40.0, confirm_bars=3)` → persistence, not
  level. A `None` inside the window makes the rule **unmeasurable** (`None`), never "no
  deterioration".
* `stall_exit(days_held, unrealized_return=, rs_deteriorating=, max_stalled_bars=20)` →
  all three inputs must be measured for the rule to fire *or not fire*.
* `evaluate_long_exit(...)` / `compare_exit_variants(...)` → the walk and the A/B.

### 3.4 The published vocabulary, and what `REDUCE` means

`classify_exit` maps the ladder to the action: a fired `risk_gate` slot is `RISK_EXIT`;
any other fired slot is `EXIT`; nothing fired **and** a deterioration read present is
`REDUCE`; nothing fired is `HOLD`; and a position whose **protective layer could not be
measured** is `UNAVAILABLE` — the one verdict that must never be a reassuring `HOLD`.
`REDUCE` is deterministic and documented: (a) the price is below the trend MA but the
confirmation count is not met, or (b) the composite is below its edge on the last scored
session without the confirmation count, or (c) the price is within `reduce_within_atr`
ATRs of the live stop.

The thesis slot carries two independent mechanisms (trend break, momentum
deterioration), so it is measurable when **either** is; the unmeasured peer is named in
`absent`, and the **tool prints `absent`**, so weaker evidence is visible rather than
silent. `absent` is a dict of rule → reason, not a bare list.

## 4. Parameter provenance

| Parameter | Source, read not remembered |
|---|---|
| 2.5 × ATR initial | LeBeau, *Exit Strategies for Stocks and Futures* (TradeStationWorld, 2005): "2 or 3 ATRs below my entry point". Alvarez's 10-year study of a 52-week-high breakout, R-multiples: **2.5 × ATR at the close = 776 total R** (best of every type), 3 × ATR intraday = 607, no stop = 164. |
| 3 × ATR trailing from the highest high since entry | LeBeau: "the stop is set 3 (?) ATRs below the highest high (or highest close) since the trade was entered … the stop moves upward whenever a new high is made"; "we usually start new trades with the default ATR of 3", tightened to 2 after 4 ATRs of profit. |
| close-evaluated stops | Alvarez: end-of-day evaluation improved total R by ~30 % over intraday on the same stops; also "a simple max loss stop evaluated at the close outperformed every other stop type tested". |
| 50-day MA | LeBeau: "exit using moving averages. 10 or 20 days works in futures while 30 to 50 days works well for stocks". |
| the 20-session stall, off | Alvarez 2014 (DTAYS weekly breakout, Russell 3000, 2004-2014): adding "exit if under the entry price after N weeks" left CAR and MDD "basically unchanged" while `% winners` and `Avg. % P/L` "drop dramatically"; his own closing note is that one may still want it for psychology. |
| the momentum threshold | the composite's own `MOMENTUM_BANDS` neutral floor (40.0), never the brief's 35. |

## 5. Open items, and the falsifiers that would change the design

* **The momentum rule has no series in production yet.** `evaluate_long_exit` takes
  `momentum_scores`; the tool feeds `score_history.read_history(ticker)` (one row per
  scored run date). That store has **no writer in the tree today**, so in practice the
  rule is named absent — visible in the report's census, never assumed safe. It goes live
  when a run records scores; the falsifier is three recorded rows for a name.
* **The trailing stop is the weakest leg on the evidence** (Alvarez). `compare_exit_variants`
  is the instrument; if the trailing variant never improves net return or give-back on the
  names at hand, `ExitConfig(enable_trailing=False)` is a one-word change and the engine
  should say so.
* **No opens-only series can model a queue.** With closes/opens the walk can price a gap at
  the open; it cannot say what a limit order would have done.
* **The stall rule stays off** until a run here measures it adding something. The
  falsifier is a variant comparison where `plus_momentum_and_stall` beats `plus_trend` on
  net return without a worse drawdown.
* **`REDUCE` is a judgement call this doc defines**, not a measured optimum: it is a
  deterministic restatement of "momentum is weakening, but a full exit is not yet
  justified" (the brief's own §6 wording), and it is deliberately published with its
  inputs so a later run can move it.

## 6. Sources

* Charles LeBeau, *Exit Strategies for Stocks and Futures*, TradeStationWorld conference
  2005 (PDF, read): initial stops 2-3 ATR; the chandelier's definition and its ATR-3
  default; MA lengths for stocks; the four-step exit priority; the time exit as "good for
  testing entries".
* Cesar Alvarez, *DTAYS Weekly Breakout Strategy With Time Stops*, 2014-09-22 (read): the
  N-week stall rule's measured effect on CAR, MDD, win rate and trade count.
* Cesar Alvarez's stop-loss study (2005-2015, Russell 1000, R-multiples), as reported by
  Better System Trader episode 037 (read): the ranking of percentage, ATR, trailing and
  stop-plus-target types, intraday vs end-of-day, and the 4:1-5:1 reward:risk finding.
* This repo: `Strategies/entry_exit.md` §58, §68, §101, §103 (the owner's spec);
  `strategies/exits.py`, `strategies/size.py`, `strategies/swing.py`,
  `strategies/contract.py`, `strategies/risk_manager.py`,
  `strategies/relative_strength.py`, `strategies/score_history.py`.

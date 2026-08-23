# Pre-Market Decision Review (Overnight Reviewer) — Design

**Status:** design sketch → **implemented** (choice (a): same-night in-batch
catalyst/quality re-check + standalone pre-open gap/anchor script). Build map
in §12; entry points: `scripts/pre_market_review.py`, `scripts/nightly_review.py`
(driver), `scripts/decision_history.py` (series), and the opt-in `batch.py`
same-night step (`enable_pre_market_review`). Follow-up fixes & features
shipped 2026-08-22: real-time pre-market quote (defect-4 fix), planned-entry/
stop extraction + tranche re-anchor in the standalone path (defect-1 fix),
batch `results_dir` wiring (defect-2), a paper-book ledger
(`pre_market_ledger.jsonl`, feature 3), guarded overnight-headline context for
the reviewer (feature 5), and scheduler notes (§15, feature 6).

---

## 1. The problem this solves

The pipeline runs **after market close** and emits a structured decision
(`final_trade_decision` from the Portfolio Manager) with overlay-adjusted
entry/stop/size (`position_contract`, `risk_gate`, `tranche_context`). That
decision is priced at **T close**.

By **T+1 open** three things may have changed that can invalidate a
close-based plan:

1. **Gap risk** — the open gaps through the planned entry (or through the
   stop). The entry/stop anchors were computed on yesterday's close.
2. **Catalyst window tightened** — the B1 earnings window (`catalyst_window_days`)
   or `catalyst_hard_block_days` are now *closer* to the print; the de-risk
   math that was neutral at close may no longer be.
3. **Overnight information** — material filings (SEC), analyst
   upgrades/downgrades, macro moves (FRED credit spreads), news/sentiment,
   pre-market quote.

A perfectly-formed 4pm decision can be wrong at 9:30am. The purpose of the
pre-market reviewer is a **delta-driven CONFIRM / REVISE / REJECT** — not a
full re-run of the graph (re-debating bull/bear overnight is expensive and
ignores the prior report).

> Real trading desks implement this exact layer ("pre-market review /
> overnight risk override"). It is the *design* closing the gap between
> "the report said Buy" and "the order that actually fills".

---

## 2. Goals & non-goals

**Goals**

- Re-validate a prior close-time decision against **measured** overnight
  deltas.
- Re-anchor entry/stop/size when the open differs from yesterday's close.
- Prioritize the two highest-value checks: **catalyst-window tightening** and
  **gap risk**.
- Emit one deterministic verdict: `CONFIRM` / `REVISE` / `REJECT` with
  tool-sourced reasons (the repo's no-fabrication contract).

**Non-goals**

- Not a full re-run of the LangGraph pipeline (no new bull/bear debate).
- Not a "review of the review" chain — one reviewer consuming the on-disk
  report + deltas is enough.
- Not an execution layer. This repo is **analysis-only**; a REJECT has
  paper-book semantics (skip the plan). If an execution layer is ever added,
  the reviewer's verdict becomes the gate between decision and order (§9).

---

## 3. Where it slots in (placement)

```
T-close run (existing):
  propagate() -> _apply_strategy_overlays -> portfolio_manager decision
  -> 5_portfolio/decision.md + <results>/<ticker>/full_states_log_<date>.json
  -> memory_log.store_decision (pending entry)

T+1 pre-market (proposed):
  ---- NEW: pre_market_review(ticker, prior_date, prior_state) ----
  1. load prior report artifacts (decision.md / full_states_log)
  2. fetch measured deltas (pre-market quote, overnight news/filings/ratings,
     macro, catalyst calendar)
  3. re-anchor the deterministic folds with today's price/date
     (catalyst window, tranche_plan, position_contract, risk governor)
  4. one review LLM reads prior decision + computed deltas
     -> CONFIRM | REVISE(new entry/stop/size) | REJECT(reasons)
  5. write pre_market_review_<date>.md next to the report; append a paper-
     book line

Later same-ticker run (existing loop untouched):
  propagate() -> _resolve_pending_entries() resolves the prior entry's
  realized return vs benchmark and reflects (the reviewer sits *earlier*
  in this loop; it does not break it)
```

The reviewer runs **before the open** (pre-market / opening-auction window),
not after — otherwise it degenerates into a second close-analysis.

---

## 4. Prior-report inputs (already on disk)

| Artifact | Source | What the reviewer reads |
| --- | --- | --- |
| `5_portfolio/decision.md` | `reporting.write_report_tree` | PM decision, `Risk Gate (computed)` block, `Position contract`, tranche lines (`tranche_context`) |
| `full_states_log_<date>.json` | `graph/trading_graph.py::_log_state` | `final_trade_decision`, `strategy_overlays`, `risk_gate`, `position_contract`, `risk_context`, `tranche_context` |
| Pending memory entry | `agents/utils/memory.py` | the prior decision's original rating line (for later realized-return reflection) |
| `data_cache_dir/vendor_cache` | TTL disk cache | avoids re-fetching unchanged vendors |

The reviewer should prefer `_log_state`'s JSON (machine-shaped) over parsing
the markdown, and degrade gracefully when the folder/JSON is missing (e.g. a
report written by `rebuild_complete_report.py` re-render).

---

## 5. Overnight delta sources (all existing vendors/tools)

| Delta | Tool/vendor endpoint | Consumer |
| --- | --- | --- |
| Pre-market / opening quote + gap % | `route_to_vendor("get_stock_data", ...)` (moomoo `get_stock_data_moomoo` first, yfinance fallback) + `get_market_snapshot` | re-anchor entry/stop; gap risk |
| Earnings window now closer | `get_earnings_calendar` (+ `get_expected_move`), B1 `fetch_catalyst_data` → `build_catalyst_snapshot` | catalyst-window check |
| Overnight news / sentiment | `get_news` chain incl. `get_massive_news` (structured sentiment) | material-change context (never a hard veto by itself) |
| Material filings | `get_sec_filings` | purpose-specific (8-K over a weekend) → can flag REVISE |
| Analyst action | `get_analyst_ratings` / `get_insider_activity` / `get_form4_insider` | standalone upgrades / insider prints |
| Macro stress | `get_credit_spread_read(date)` (FRED HY/CCC OAS) + `_apply_strategy_overlays` macro backdrop | risk-off re-evaluation |
| Prior-close realized context | memory log `resolve` helper | feeds the reflection loop, not the review |

Every delta is **measured**; a missing vendor degrades to `DATA_UNAVAILABLE`
(outside `data_vendors` opt-outs) exactly as it does today, and the reviewer
treats "no delta data" as a reason to **default to CONFIRM**, never to invent.

---

## 6. Deterministic re-anchoring (the numbers, not prose)

The reviewer's decisions must be grounded in these recomputed values rather
than LLM narrative:

1. **Gap read** — `premarket_gap% = (open - prior_close)/prior_close`.
   - `|gap|` within ATR tolerance → re-anchor entry = open, keep stop distance,
     usually CONFIRM (stop adjusted).
   - Gap through the planned entry toward the stop → REVISE with re-anchored
     levels from `tranche_plan(P1=open, atr, weights, ...)`.
   - Gap through the stop → REJECT (gap risk realized; the prior plan's
     invalidation is moot — the trade would have stopped out).
2. **Catalyst window re-check** — re-run `fetch_catalyst_data(ticker, T+1)`
   → `build_catalyst_snapshot`; if the print is now inside
   `catalyst_window_days` / `catalyst_hard_block_days` (→ risk governor
   REJECT per §5 of `docs/api_reference.md`), demote CONFIRM→REVISE (scale
   down) or REJECT (hard block).
3. **Tranche / contract re-anchor** — `tranche_risk_read` (config-frozen
   weights/stop/risk; measured close = open) → `peak_deployed_pct`,
   `capital_at_risk_pct`, `peak_ok`/`book_ok`; then
   `build_position_contract(entry_price=weighted_avg_entry, ...)` so the
   dollar stop/BE/target match the new entry. If the re-anchored
   capital-at-risk or peak-deployed exceeds its cap → REVISE (smaller size)
   or REJECT.
4. **Governor re-run** — `govern(peak_deployed_pct, cfg, cvar_pct=...,
   capital_at_risk_pct=..., risk_cap_pct=...)` → PASS/WARN/REJECT on the new
   numbers. REJECT here is the strongest signal, exactly as in
   `_apply_strategy_overlays`.

These four are **pure functions + one `route_to_vendor` call per delta**; no
graph invoke, no LLM until step 4 below.

---

## 7. The reviewer agent (verdict contract)

A single LLM reviewer — either the existing **Portfolio Manager** (deep-think)
with a dedicated pre-market prompt, or a new thin node — reads:

```
Prior decision      (from full_states_log / decision.md)
Computed deltas     (gap%, catalyst snapshot + hard-block, re-anchored
                     tranche plan, governor verdict, news/filing/rating delta)
Config              (output_language, catalyst_*, tranche_*, risk_*)
```

And emits a **structured verdict** (mirroring the repo's pydantic pattern in
`agents/schemas.py`):

```python
class PreMarketVerdict(BaseModel):
    verdict: Literal["CONFIRM", "REVISE", "REJECT"]
    entry_price: float | None      # re-anchored (usually = open) if REVISE
    stop_loss: float | None        # re-anchored
    position_size: float | None    # re-anchored (governor-bounded) if REVISE
    reasons: list[str]             # every reason must cite a measured delta
    catalyst_days_to_print: int | None
```

**No-fabrication contract** (same as every analyst tool): a REVISE/REJECT must
quote at least one recomputed number or a tool-sourced delta. The default
answer when nothing measurable changed is **CONFIRM**. A "sentiment feels
worse" line without a delta is not a reason.

---

## 8. Verdict semantics for an analysis-only repo

| Verdict | Meaning today (paper book) | Meaning if an execution layer is ever added |
| --- | --- | --- |
| `CONFIRM` | plan stands; record as-is in the paper log | plan stands; arrive at open with the original plan |
| `REVISE` | plan updated with new entry/stop/size + reasons | submit revised order (entry = open / re-anchored) |
| `REJECT` | plan skipped; `risk_halt`-style paper skip; note in log | no order; do not chase |

The repo already has `risk_halt=True` semantics in `_apply_strategy_overlays`
(REJECT → "no position"); the reviewer's REJECT reuses that mental model at
the pre-market layer without touching the graph.

---

## 9. Future: execution-layer gate (one paragraph, not now)

If real orders are ever added (out of scope today), the pre-market verdict
becomes the **mandatory gate** between the prior decision and order
submission: an order may only be placed for a plan whose verdict is CONFIRM
or REVISE (with the revised levels actually turned into the order), and REJECT
hard-blocks the order. The reviewer stays deterministic-first so the gate is
never an opaque LLM decision.

---

## 10. Sequencing / practical edges

- **Run pre-market, not post-open**: the opening auction / pre-market quote is
  the freshest usable price before the decision is acted on.
- **No trading day** (weekend/holiday): skip the review cleanly (no quote, no
  calendar), do not fabricate a pass.
- **No delta data** → default CONFIRM (never invent).
- **Prior report missing/partial** → fail open with a logged note (the report
  writer `reporting.py` has a re-render path; re-rendered folders carry the
  same JSON/dir layout).
- **Multiple decisions per ticker** (batch): review each pending entry
  independently (the batch runner `batch.py` already isolates per-symbol
  memory).

---

## 11. Cost & failure modes (honest)

- **Cost**: one pre-market quote fetch + calendar/catalyst fetch + one LLM
  call per pending plan. Far cheaper than a full graph re-run.
- **False REJECT**: a reviewer that over-reacts to a gap without re-anchoring
  math would kill good plans. Guard: REJECT requires a *measured* breach
  (gap through stop, hard-block, governor REJECT), not a "felt" one.
- **False CONFIRM on stale catalysts**: if the calendar vendor 429s, the
  catalyst window check degrades to unknown → CONFIRM. Acceptable (matches
  existing degrade-to-neutral behavior of the B1 overlay).
- **Anchor drift**: re-anchoring entry to the open is only sound while the
  stop distance (ATR-based) stays meaningful; after a several-ATR gap the
  tranche ladder should be recomputed from the open, not shifted.

---

## 12. Reuse map (build-from-here checklist)

| Need | Existing seam |
| --- | --- |
| Load prior decision | `_log_state` JSON (`graph/trading_graph.py`), `reporting.py` |
| Pre-market price / gap | `route_to_vendor("get_stock_data", ...)` + `get_market_snapshot` |
| Catalyst window | `strategies/catalyst.py::fetch_catalyst_data/build_catalyst_snapshot` |
| Tranche re-anchor | `strategies/value_dip.py::tranche_plan/tranche_risk_read` (measured P1, config-frozen params) |
| Contract re-anchor | `strategies/contract.py::build_position_contract(entry_price=...)` |
| Governor gate | `strategies/risk_governor.py::govern(... capital_at_risk_pct=..., risk_cap_pct=...)` |
| Overnight news/filings/ratings | news chain + `get_massive_news`, `get_sec_filings`, `get_analyst_ratings` (headline context via `_headline_delta`, feature 5) |
| Real-time pre-market price | Alpaca `get_intraday` (when enabled) else yfinance `fast_info.last_price` else daily close (`_realtime_price`) |
| Pre-open batch driver | `scripts/nightly_review.py` (reads `reports/batch_summary_*.jsonl`; feature 2) |
| Paper-book ledger | `strategies/pre_market.py::record_review/resolve_ledger` → `data_cache_dir/pre_market_ledger.jsonl` (feature 3) |
| Decision history series | `scripts/decision_history.py` (reads per-ticker `full_states_log_*.json`; feature 4) |
| Macro stress | `get_credit_spread_read` (FRED) |
| Structured verdict | `agents/schemas.py` pydantic pattern + free-text fallback |
| Memory loop | `memory.py` pending→resolve (`_resolve_pending_entries`) |

**Suggested entry point** if built: a script
`scripts/pre_market_review.py <ticker> --prior-date YYYY-MM-DD` (or a mode in
`pipeline.py`), reusing `scripts/value_screener.py`-style
`importlib.util.spec_from_file_location` loading conventions and `py -3.12`
everywhere. Hermetic tests would mock `route_to_vendor`; every test inherits
the `pytest-timeout` deadline (180 s/test, 30-min session) per
`docs/developer/10-tests-layout.md`.

---

## 13. Open questions (decide before building)

1. **Reviewer identity**: reuse the Portfolio Manager (deep-think) with a
   pre-market system prompt, or add a new `agents/` node? (Repo pattern favors
   reuse + a prompt variant.)
    answer: reuse + prompt variant, but allow a new node for future separation
2. **`--prior-date` discovery**: default = "the last report folder for this
   ticker" vs an explicit flag.
    answer: default to last report folder, but allow explicit override,
3. **Batch integration**: per-symbol review in `batch.py`'s existing loop vs a
   standalone script invoked after the nightly batch.
    answer: per-symbol review in batch.py, but allow standalone script for manual runs
4. **Verdict storage**: one `pre_market_review_<date>.md` beside the report
   (like `5_portfolio/decision.md`) vs appending to the memory log.
    answer: one `pre_market_review_<date>.md` next to the report
5. **Config gate**: an `enable_pre_market_review` flag + `TRADINGAGENTS_*`
   override, mirroring every other feature's opt-in convention.
    answer: yes, confirmed.


---

## 14. Bottom line

Feasible, financially motivated, and low-risk to build because every building
block already exists. The two highest-value checks are **catalyst-window
tightening** and **gap risk**, both fully deterministic. The one thing that
must stay true is the guardrail: **REVISE/REJECT only on measured deltas,
CONFIRM by default** — otherwise the reviewer becomes opinion drift instead of
a risk control.
## 15. Operationalizing the two-point-in-time design (feature 6 — schedulers)

Choice (a) is a **two-step daily cadence**: a close-time batch + a pre-open
review. Wire it with a scheduler:

**Linux cron (crontab)**
```cron
# 17:35 after US close on weekdays -> nightly close-time batch (example)
35 17 * * 1-5  cd /path/to/TradingAgents && py -3.12 batch.py --symbols "$(cat universe.txt)" --depth deep
# 07:35 before the open -> pre-open review of the whole batch
35 7  * * 1-5  cd /path/to/TradingAgents && py -3.12 scripts/nightly_review.py
```

**Windows Task Scheduler**
- Task 1: `py -3.12 batch.py --symbols ... --depth deep` at 17:35 weekday.
- Task 2: `py -3.12 scripts/nightly_review.py` at 07:35 weekday (uses the
  latest `reports/batch_summary_*.jsonl`, so it needs no args).

Notes
- Skip review on weekends/holidays via the *weekday* (`1-5`) schedule; the
  script itself also degrades to CONFIRM when there is no quote.
- `nightly_review.py` reads the latest batch summary; run it **before the
  open** so the gap read reflects the pre-market price (see §10).
- All runs are `py -3.12` (the environment with pytest/deps; bare `python` is
  the wrong venv on this machine — `docs/AGENT_ONBOARDING.md` §1).

# Calculation → agent binding: audit findings & implementation plan

**Criterion (as requested):** if a calculation's result can be used by a virtual agent, that agent must be
able to obtain it **by tool** *and* be told **by prompt** when it matters. Deliverable of this document:
the decisions and the ordered work. **No code has been changed.**

Audited at `acfd15c` (main, clean). Method: a mechanical chain map (706 public calcs in
`tradingagents/strategies/*`; 208 `@tool` functions; 192 callable by an agent) plus three read-only
semantic audits (unbound tools, prompt guidance, the non-tool context channel). Every claim below carries
a file:line and was reproduced by the main thread where it is load-bearing.

**Drafting correction (2026-09-10), recorded before any code changed.** An intermediate check suggested that
`892ade2` (S1, the single-source refactor) had silently unbound live tools, because the 16 tools under audit
appear in the pre-S1 `_create_tool_nodes` ToolNode lists and on no surface after it. That reading was wrong
and is retracted. At `48d1bc5` every analyst carried its **own** LLM-facing `tools = [...]` literal
(`market_analyst.py:130` = 111 entries, news 25, fundamentals 48, social 0) and **none of the 16 appears in
any of them**, so no model could call them; they were dead executor entries, and S1's removal of them (and
of 6 more such entries) was correct. The audit's original conclusion stands: the 16 are genuinely unbound.
The detour produced one durable result, now W1's bidirectional gate — see §3.E.

---

## 1. The three channels (what "bound" means here)

| channel | who uses it | binding requirement |
|---|---|---|
| **Analyst toolset** (`agents/toolsets.py` → node `bind_tools` + graph ToolNode) | market, news, fundamentals (company/ETF variants) | tool in the toolset **and** a "cite it before any X claim" line in that analyst's prompt |
| **In-node tool loop** (`agents/utils/risk_tool_loop.py`: `RISK_DEBATOR_TOOLS` 27, `TRADER_TOOLS` 13) | 3 risk debators, trader | tool in the list **and** the debator risk-tool line / trader verify prompt |
| **Always-on context block** (`computed_decision_context`, `risk_context`, `computed_independent_vote`) | bull/bear researchers, RM, judge, PM, debators | the value must actually be **written before** the agent runs, and labelled so the model can cite it |

Agents that bind **no** tools by design: sentiment analyst (prefetch-only), bull/bear researchers,
debate judge, research manager, portfolio manager (`NO_EXTERNAL_TOOLS`). For these the context channel is
the only one — which is where the deepest gaps are.

## 2. Numbers

- 706 public calcs; **255** referenced directly by a bound tool, **450** reachable through another calc,
  **1** unreachable (`factor_expressions.clear_expr_cache` — a cache utility, see W5).
- 208 `@tool` functions; 192 callable by an agent (in the agent's `bind_tools` set **and** dispatchable by
  its executor); **16 in no callable surface** (13 on no surface at all, 3 reachable only from the debator
  loop). See §3.E: "bound" is two conditions, and only the single-source toolset guarantees both.
- Prompt guidance: market 100 guided / 10 listed-only; news 18 / 7; fundamentals 35 / 9 (+ETF 8 / 4);
  risk debators 23 named / **4 absent**; trader 12 / 1. **35 tools have no trigger sentence** (5 of them
  carry a usable trigger in their own docstring, 30 do not).
- Context channel: **3 PM prompt rules reference numbers that are never injected**, 1 always-`unavailable`
  card, 1 judge prompt reduced to counts, 2 blocks built-and-never-read, 1 guard that can never fire.

---

## 3. Findings

### A. The 16 unbound `@tool` functions → 4 bind / 6 already-covered / 6 not agent-facing

Verified pre-S1: none of the 16 was present in any analyst's LLM-facing `tools = [...]` list at `48d1bc5`,
so none was ever model-callable. Their earlier presence in the hand-maintained ToolNode lists is the
false-positive the old gate counted as "bound" (§3.E), not a binding that was later lost.

**A1 — bind (4).** Each already has the claim class in some agent's prompt; only the tool + line are missing.

| tool | target | why | proposed prompt line |
|---|---|---|---|
| `get_pair_risk` | market | Granger x→y with per-lag p-values is returned by **no** bound tool (`get_pair_trade_signal` gives only cointegration/β/half-life) | slot after the `get_pair_trade_signal` bullet: "`get_pair_risk(x, y)` … cite `granger(x→y)` with its p-values before calling either name the leader" |
| `get_macro_regime_read` | news | composite Risk-On / Liquidity-Contraction / Stagflation label from the 5 inputs news already cites; no bound tool produces the composite | after the `get_credit_spread_read` sentence: "…folds the same fed/curve/credit/DXY/vol markers into ONE cross-asset label — cite it before any 'the tape is risk-on / liquidity crunch / stagflation' claim" |
| `get_vif_read` | market | no bound tool measures regressor collinearity; the prompt already demands non-redundant indicators (`market_analyst.py:55`) | **prerequisite (W2.0):** make the tool take `ticker` + indicator names and fetch/compute the series itself. Then, after that instruction: "`get_vif_read(ticker, indicators=[…])` … call it before presenting two like measures as independent evidence" |
| `get_trade_outcome_metrics` | risk debators (`RISK_DEBATOR_TOOLS`) | entry-anchored MAE/MFE + stop/target hits for the plan the debators are arguing; the market-bound `get_post_close_confirmation` gives only a stopped-out/target-hit verdict from the newest decision.md | append to the shared debator risk-tool line: "`get_trade_outcome_metrics(ticker, entry, stop?, target?)` — the measured MAE/MFE + stop/target hits for the plan entry" |

**A2 — already covered (6)** — declare with the covering tool named, do **not** bind:
`get_consensus` (PM already receives the computed agreement number; both managers are `NO_EXTERNAL_TOOLS`),
`get_kyle_lambda` (`get_liquidity_risk` returns ILLIQ/float-turnover/IWF/verdict; the tool's own docstring
forbids per-ticker use), `get_prediction_ledger_score` (`get_ledger_risk_state` covers win-rate; the
unique stops/targets half moves to `get_trade_outcome_metrics`), `get_stress_grid_read` (`get_scenario_dcf`
is the modelled version; the grid never receives its sensitivity axis and says so), `get_thesis_evidence_matrix`
(**deleted in W5**, per §4.4 — `get_debate_claims_verdict` + the in-node deterministic HARD BREACH + the
report-level grounded-claim gate already cover it, and it takes model-authored JSON),
`get_kelly_alloc` (`get_allocation_black_litterman` / `get_position_sizing` / `get_hrp_alloc`).

**A3 — not agent-facing (6)** — declare, and record the real consumer:
`get_trade_excursions` (journal rows; the CLI/batch QA path), `get_topk_drop_plan` and
`get_enhanced_index_tilt` (universe-level portfolio construction; the screener alloc block; the PM that
docs say should own them runs `NO_EXTERNAL_TOOLS`), `get_no_trade_guard_band` (needs a current book weight
no agent surface carries), `get_prompt_injection_read` (a guard whose value is *pre*-context — by the time
an LLM can call it the text is already in context; the real home is the ingestion layer),
`screen_equities` (CLI screener, `enable_screener=False`; breadth is covered by bound `get_market_movers`).

### B. Prompt-guidance gaps (35 tools, 30 without any trigger)

`listed-only` = the tool name and usually its return shape appear in the prompt, but the prompt never says
which claim depends on it. Market 10 (`get_market_snapshot`, `get_top_movers`, `get_options_chain`,
`get_short_interest`, `get_short_volume`, `get_short_sale_volume`, `get_capital_flow`,
`get_market_snapshot_alpaca`, `get_dupont_read`, `get_payoff_asymmetry`, `get_market_movers`), news 7
(`get_news`, `get_global_news`, `get_share_buyback_authorization`, `get_news_sentiment`,
`get_economic_calendar`, `get_fed_watch`, `get_gdelt_sentiment`), fundamentals 9 (+ETF 4)
(`get_fundamentals`, `get_balance_sheet`, `get_cashflow`, `get_income_statement`, `get_analyst_ratings`,
`get_smart_money`, `get_revenue_breakdown`, `get_corporate_actions`, `get_earnings_surprise_history`,
`get_institution_holdings`, `get_patent_activity`, `get_company_peers`, `get_kalman_spread`), plus
`get_tail_extreme_var` / `get_covariance_read` / `get_concentration_read` / `get_merton_distance` (absent
from the debator line) and `get_composite_sizing` (absent from the trader prompt). Five of these already
carry the trigger in their own tool docstring (which is what the model reads), so the prompt gap is a
consistency issue rather than a missing instruction — the plan treats those separately from the 30 real gaps.

Extra finds: `news_analyst` says "three computed-analysis tools" and lists four; `fundamentals_analyst`
emits the ETF/FUND TOOLING paragraph unconditionally (so a company run is told about ETF tools).

### C. Context-channel holes (the deepest class: prompt rules with no backing number)

1. **PM "computed risk gate"** — `portfolio_manager.py:270` orders the model to reconcile with "the computed
   risk gate or the risk context … portfolio-veto (drawdown over limit)". `risk_gate` and
   `risk_context[book_drawdown/drawdown_limit]` are written only inside `_apply_strategy_overlays`
   (`trading_graph.py:1160-1165`), which runs **after** the graph. The PM is told to reconcile with a number
   it never receives. Same for `position_contract` (rule at `:268`, `:272`; written at `trading_graph.py:968`).
2. **PM liquidity line is dead** — `portfolio_manager.py:162` reads `risk_context['liquidity']`, written only
   at `trading_graph.py:1123` (post-graph) → `liq_line` is always `""`, so the sizing rule that depends on it
   silently does nothing.
3. **Trade-plan card is always "unavailable"** — both callers pass only ticker+price+config
   (`trading_graph.py:1386`, `analysis_tools.py:6839`), so `trade_plan.build_trade_plan` renders
   `Unified stop / Tranche execution / Tiers / Trail remainder = unavailable` on every run, including the
   copy injected into `computed_decision_context` (which the trader, PM, RM and debaters read).
4. **Debate judge gets counts, not claims** — it loads the full `ClaimLedger` (`debate_judge.py:193`) but
   injects only `valid=2 violated=0 …` (`:86`, `:234-238`), while its prompt demands it score empirical
   grounding and distrust unverifiable numbers.
5. **Dead / broken blocks**: `final_state['computed_context']` written (`trading_graph.py:1215`) and read by
   nobody (and its V5 inputs are never supplied outside tests); the `insufficient_liquidity` hard-guard read
   at `trading_graph.py:903` is a dict-key read on a string written later, so it can never fire.

### D. Docs assert bindings that do not exist

`CHANGELOG.md:994-1005` ("now bound (market / fundamentals)"), `README.md:180-187` ("No more silent gaps"),
and `docs/api_reference.md:628-634` (a `surface` column naming market / market+fundamentals) all claim
bindings that the audit disproves for all 16 tools. Cause (now proven, not inferred): the 2026-09-04 wiring
gate defined "bound" as *appearing in a ToolNode list*, and at `cdddd85` these 16 were added to the market /
fundamentals / news ToolNode lists — but never to those analysts' `bind_tools` sets, so no model could emit
the call. The docs recorded the gate's definition rather than the tool's reachability; they were wrong when
written, not falsified later. Correction per doc type: `README.md` (current-state) is fixed in place; the
`api_reference` surface column becomes machine-checked (W1); the `CHANGELOG.md` entry is a historical record
and is **kept**, with a dated correction appended rather than rewritten.

### E. Gate integrity issue (must be fixed before the binds, or the plan can be faked)

`tests/test_calc_agent_wiring.py` decides "bound" by searching the **raw text** of the binding domains
(`TOOL_BINDING_BLOB`, :216-243). Adding only a prompt sentence would silence the binding gate while the tool
stays uncallable (the prompt-guidance gate only checks tools that are *already* in a toolset). Two holes:
the blob-scan, and `TOOL_LEGACY_BINDING` as the escape hatch for exactly the 16 tools under audit.

There is also a **second dimension the gate never checked, and it cuts both ways**: a tool is callable only
if (i) its name is in the agent's `bind_tools` set — the model has to know the schema to emit the call — and
(ii) its name is dispatchable by that agent's executor (the ToolNode / `run_tool_loop` list). Two production
instances prove the halves are independently breakable:

- **bind-only**: the 5 `get_etf_*` tools were in the fundamentals `bind_tools` set with no ToolNode entry,
  so langgraph rejected every ETF-path call as "not a valid tool" (fixed in `892ade2`, P0-4).
- **execute-only**: these 16 were in ToolNode lists and in no `bind_tools` set, so the model could never
  emit the call and the entry was dead weight (removed in `892ade2`; the docs outlived the truth).

W1's gate must therefore check both directions for every agent: `bind_tools` ⊆ executor, and executor ⊆
`bind_tools`. The single-source `toolsets.py` makes that invariant structural for the analysts; the gate
exists so a future refactor cannot silently break it again.

---

## 4. Decisions I need from you (product calls, not defects)

1. **RESOLVED (2026-09-10): accept the 4 binds, with `get_vif_read` made self-sufficient first (option b).**
   The other three are bound as-is. `get_vif_read` must not be bound in its current shape: its input is a dict
   of raw indicator series, and no tool hands the model those numbers as data (`get_indicators` returns a
   rendered table), so a call would require re-typing ~60-90 digits — a confident wrong answer if any value
   is dropped, rounded or invented, which is exactly what the suite's never-fabricate rule forbids. Instead:
   change the tool to take `ticker` + indicator names, fetch/compute the series internally (run OHLCV cache +
   the existing indicator path), and only then bind it to the market analyst. See W2.0.
2. **RESOLVED: bind both.** `get_pair_risk` → market (its Granger lead-lag half is returned by no bound tool;
   the cointegration half does overlap `get_pair_trade_signal`, and the prompt line will say so).
   `get_trade_outcome_metrics` → risk debators (entry-anchored MAE/MFE + stop/target hits for the plan they are
   arguing; `get_post_close_confirmation` only reads a verdict off the newest decision.md).
3. **RESOLVED: accept the 6 as declared**, each naming its covering tool. No upgrades to binds now; the stated
   leftover unique fields are recorded in §3/A2 so a later review can promote one with a single prompt line.
4. **RESOLVED: declare `get_prompt_injection_read`, delete `get_thesis_evidence_matrix`.** The injection scan is
   a real guard whose home is the ingestion layer (an LLM that can call it has already ingested the text), so it
   stays declared rather than deleted. The thesis-evidence matrix duplicates live machinery (`get_debate_claims_verdict`,
   the in-node deterministic HARD BREACH, the report-level grounded-claim gate) and takes model-authored JSON — it
   is removed in W5.
5. **RESOLVED: hoist the pre-decision inputs; soften only what is inherently post-decision.** The PM gets the
   values it can act on *before* it decides — book drawdown vs `risk_max_drawdown_pct`, the liquidity verdict, and
   the position-contract size/stop where they are computable pre-graph (all of these come from data the pre-graph
   precompute already loads next to `_precompute_risk_context`). Any rule whose number is inherently a verdict on
   the PM's *own* final size stays post-decision, so that rule's wording changes to reference the pre-graph limits
   instead of a verdict it cannot have. The point is that no prompt may reference a number that is absent from the
   rendered prompt (enforced by W4's acceptance test).
6. **RESOLVED: fill all 30 real gaps** in one batch — each is a one-line append in the house style, and W1's
   trigger-phrase gate then keeps them from regressing.

---

## 5. Work plan

Each phase: fix → regression gate → `ruff` → targeted tests → full suite → CHANGELOG → commit. No phase
starts before its predecessor's gate is green.

### W1 — Make the gates honest + fix the doc drift (must be first)

- Add a `@tool` → binding gate that checks the **toolset/loop objects** (`toolsets.analyst_toolset(key)`,
  `risk_tool_loop.RISK_DEBATOR_TOOLS/TRADER_TOOLS`), not raw text, and delete the blob loophole.
- Extend the prompt-guidance gate to require a **trigger phrase** (not just a name) for every bound tool, so
  B's list becomes enforceable rather than advisory; allow the docstring-trigger exemption explicitly.
- Correct `CHANGELOG.md:994-1005`, `README.md:180-187`, `docs/api_reference.md:628-634` to the real state
  (and note the historical cause). Docs are the contract the next reader trusts.

- Add the **bidirectional callability gate**: for every analyst/debator/trader surface, the `bind_tools`
  set and the executor list must be equal (both directions, per §3.E). It fails today for any surface that
  still holds an execute-only entry, and it is the gate that would have caught both P0-4 and the 16.

**Acceptance:** the new gates fail on the current tree (proving teeth), including the bidirectional gate
against a synthetic execute-only and a synthetic bind-only entry; and the doc lines no longer claim a
binding that does not exist.

### W2 — The binds (A1)

**W2.0 (prerequisite for `get_vif_read` only):** make the tool self-sufficient before binding it. New shape:
`get_vif_read(ticker, indicators=[...])` — resolve each requested indicator to its series internally using the
run OHLCV cache (`_ohlcv`) plus the existing indicator computation the vendor path already uses, then run the
existing `variance_inflation_factor` calc. Keep the series-dict form as an internal/advanced path if a caller
needs it, but the LLM-facing arg must be names, not numbers. Regression test: a call with indicator names on a
stubbed OHLCV seam returns the VIF table and never asks the model for data; a missing/unknown indicator name
degrades to an explicit 'unavailable' rather than a fabricated column. Only after this lands does the market
prompt line reference `get_vif_read(ticker, indicators=[…])`.

Per tool (the other three — `get_macro_regime_read` → news, `get_pair_risk` → market,
`get_trade_outcome_metrics` → `RISK_DEBATOR_TOOLS`): add to the toolset/loop → add the prompt line → extend the
gate test that the tool is bound *and* guided. Four files for toolsets/prompts + `risk_tool_loop.py` + the debator prompts; remove the
`TOOL_LEGACY_BINDING` entries for the bound names.

**Acceptance:** each new tool is in the toolset, mentioned with a trigger, executed by its ToolNode (an
end-to-end call with a stubbed vendor seam), and the binding gate is green without the whitelist entry.

### W3 — Prompt guidance for the remaining gap list (B)

All **30 real gaps** (the 5 whose trigger already lives in the tool docstring are checked, not rewritten): one
line per tool, in the house style ("cite it before any <claim>"), in the owning analyst prompt; fix the
"three tools / four listed" miscount and the unconditional ETF paragraph (emit it only on the ETF path).
Re-run the S2 advertised-signature gate (the new lines must not advertise wrong arities) and the prompt-token
budget check.

**Acceptance:** the trigger-phrase gate is green for all bound tools; a negative test proves a name-only
mention fails it.

### W4 — Context-channel fixes (C)

1. PM (per §4.5): hoist the pre-decision inputs into the pre-graph precompute next to `_precompute_risk_context`
   — book drawdown vs `risk_max_drawdown_pct`, the liquidity verdict, and the position-contract size/stop where
   computable — and render them in the PM's context list. Then soften the wording of any rule whose number is a
   verdict on the PM's own final size, so no rule references a number the render cannot contain.
2. Pass the measured inputs into both `build_trade_plan` callers (tranche/value-dip setup, BE rule, targets,
   trail) so the shared card stops rendering `unavailable`.
3. Judge prompt: inject the per-claim ledger rows (metric, asserted value, ground-truth key, true value,
   status) instead of only per-role counts.
4. Delete or wire the dead blocks (`computed_context`) and fix the `insufficient_liquidity` guard (it reads a
   string as a dict).

**Acceptance:** one test per fix asserting the value the agent now sees (not the injection mechanics); the
trader/PM/debater prompts contain no reference to a number that is absent from the rendered prompt.

### W5 — Declarations, deletions, and the calc tail

- Rewrite `TOOL_LEGACY_BINDING` to contain only the A2/A3 declarations, each with the covering tool or the
  real consumer named (no more "no code/test consumer").
- `factor_expressions.clear_expr_cache`: classify in `LEGACY_WHITELIST` (cache utility, not a calc).
- Decision §4.4: **delete `get_thesis_evidence_matrix`** (tool + its calc export + the tests that only pin its
  existence); keep `get_prompt_injection_read` declared with the ingestion-layer rationale.
- Optional cleanups found en route: `get_topk_drop_plan`/`get_enhanced_index_tilt` doc references to a PM
  toolset that cannot exist (PM is `NO_EXTERNAL_TOOLS`).

**Acceptance:** every exemption line states a real consumer/cover; the gate refuses a new unbound tool.

### W6 — Verification

- Full suite (baseline 3639 passed) + `ruff` clean.
- Live smoke per touched surface: one ETF run path (`get_etf_mechanics`, `classify_security`), one company
  path, one debator loop call over a pair, one PM prompt render showing the gate/contract/liquidity numbers
  present.
- Prompt-budget check on the three analyst prompts after the added lines.

## 6. Sequencing & dependencies

`W1 → W2 → W3` are strictly ordered (the gate must be honest before binds, and binds before guidance can be
enforced). `W4` is independent of W2/W3 in files but uses the same PM/prompt test harness, so run it after W2
to avoid churn in the same prompts. `W5` closes what W2/W4 changed. `W6` last.

## 7. Risks

- **Prompt bloat**: the market prompt already carries ~100 guided tools; four more lines plus 11 trigger
  phrases is real token weight. W3 includes the budget check, and the house style is one clause per tool.
- **Binding a tool the model can't drive**: `get_pair_risk` needs the model to supply two price series; the
  mitigation is the prompt naming the exact call, as the already-bound `get_book_correlation` / `get_hrp_alloc` /
  `get_pair_trade_signal` do. For `get_vif_read` the mitigation is structural instead — W2.0 removes the series
  argument from the LLM-facing signature, so there is nothing left to transcribe.
- **PM pre-graph gating changes what the decision can act on.** Resolved as "hoist" in §4.5, so this is the one
  change in the plan that can alter a trading decision: the PM will now see a drawdown-vs-limit / liquidity /
  contract read it previously never received, and may veto or shrink trades it used to pass. Two residual risks
  follow. (a) **Two numbers for one quantity:** the hoisted value and the post-graph overlay must come from the
  same calc, or the PM argues against one number while the system applies another — so the pre-graph precompute
  calls the existing functions, it does not re-derive them. (b) **A gate that cannot precede the decision:**
  only the inputs can be hoisted; a verdict on the PM's *own* final size is inherently post-decision, so those
  rules are reworded to cite the limits, not a verdict. Mitigation: single-source calc, the post-graph overlays
  unchanged, and the W6 PM-render smoke asserting the numbers are present in what the model reads.
- **Docs are load-bearing here**: correcting them is part of the deliverable, because the false claims are
  what let this gap persist. The correction must state the real cause — the 2026-09-04 gate counted
  executor-list membership as "bound", so the docs (and the gate) asserted callability for 16 tools no model
  could call. `README.md` is fixed in place, the `api_reference` surface column becomes machine-checked, and
  the `CHANGELOG.md` entry is kept as history with a dated correction appended rather than rewritten.

## 8. What this plan does NOT do

- It does not give the tool-less agents (sentiment, researchers, RM, judge, PM) a general tool loop — that is
  a design change; it fills the specific holes where their prompts already demand a number.
- It does not re-audit the ~450 calcs that are reachable through another calc; those inherit their parent's
  binding, and W1's gate keeps that true.
- It does not change any vendor adapter or calc arithmetic.

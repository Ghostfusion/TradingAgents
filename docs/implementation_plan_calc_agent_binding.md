# Calculation → agent binding: audit findings & implementation plan

**Criterion (as requested):** if a calculation's result can be used by a virtual agent, that agent must be
able to obtain it **by tool** *and* be told **by prompt** when it matters. Deliverable of this document:
the decisions and the ordered work. **No code has been changed.**

Audited at `acfd15c` (main, clean). Method: a mechanical chain map (706 public calcs in
`tradingagents/strategies/*`; 208 `@tool` functions; 192 bound to an agent surface) plus three read-only
semantic audits (unbound tools, prompt guidance, the non-tool context channel). Every claim below carries
a file:line and was reproduced by the main thread where it is load-bearing.

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
- 208 `@tool` functions; 192 bound; **16 bound to nothing**.
- Prompt guidance: market 100 guided / 10 listed-only; news 18 / 7; fundamentals 35 / 9 (+ETF 8 / 4);
  risk debators 23 named / **4 absent**; trader 12 / 1. **35 tools have no trigger sentence** (5 of them
  carry a usable trigger in their own docstring, 30 do not).
- Context channel: **3 PM prompt rules reference numbers that are never injected**, 1 always-`unavailable`
  card, 1 judge prompt reduced to counts, 2 blocks built-and-never-read, 1 guard that can never fire.

---

## 3. Findings

### A. The 16 unbound `@tool` functions → 4 bind / 6 already-covered / 6 not agent-facing

**A1 — bind (4).** Each already has the claim class in some agent's prompt; only the tool + line are missing.

| tool | target | why | proposed prompt line |
|---|---|---|---|
| `get_pair_risk` | market | Granger x→y with per-lag p-values is returned by **no** bound tool (`get_pair_trade_signal` gives only cointegration/β/half-life) | slot after the `get_pair_trade_signal` bullet: "`get_pair_risk(x, y)` … cite `granger(x→y)` with its p-values before calling either name the leader" |
| `get_macro_regime_read` | news | composite Risk-On / Liquidity-Contraction / Stagflation label from the 5 inputs news already cites; no bound tool produces the composite | after the `get_credit_spread_read` sentence: "…folds the same fed/curve/credit/DXY/vol markers into ONE cross-asset label — cite it before any 'the tape is risk-on / liquidity crunch / stagflation' claim" |
| `get_vif_read` | market | no bound tool measures regressor collinearity; the prompt already demands non-redundant indicators (`market_analyst.py:55`) | after that instruction: "`get_vif_read({rsi: [...], stochrsi: [...]})` … call it before presenting two like measures as independent evidence" |
| `get_trade_outcome_metrics` | risk debators (`RISK_DEBATOR_TOOLS`) | entry-anchored MAE/MFE + stop/target hits for the plan the debators are arguing; the market-bound `get_post_close_confirmation` gives only a stopped-out/target-hit verdict from the newest decision.md | append to the shared debator risk-tool line: "`get_trade_outcome_metrics(ticker, entry, stop?, target?)` — the measured MAE/MFE + stop/target hits for the plan entry" |

**A2 — already covered (6)** — declare with the covering tool named, do **not** bind:
`get_consensus` (PM already receives the computed agreement number; both managers are `NO_EXTERNAL_TOOLS`),
`get_kyle_lambda` (`get_liquidity_risk` returns ILLIQ/float-turnover/IWF/verdict; the tool's own docstring
forbids per-ticker use), `get_prediction_ledger_score` (`get_ledger_risk_state` covers win-rate; the
unique stops/targets half moves to `get_trade_outcome_metrics`), `get_stress_grid_read` (`get_scenario_dcf`
is the modelled version; the grid never receives its sensitivity axis and says so), `get_thesis_evidence_matrix`
(`get_debate_claims_verdict` + the in-node deterministic HARD BREACH + the report-level grounded-claim gate),
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
bindings that my scan disproves for all 16 tools. The likely cause: those docs were written while the tools
sat in the hand-maintained ToolNode lists, which the binding gate counted as "bound"; S1 removed those lists
and exposed the truth. The plan must correct the docs to reality.

### E. Gate integrity issue (must be fixed before the binds, or the plan can be faked)

`tests/test_calc_agent_wiring.py` decides "bound" by searching the **raw text** of the binding domains
(`TOOL_BINDING_BLOB`, :216-243). Adding only a prompt sentence would silence the binding gate while the tool
stays uncallable (the prompt-guidance gate only checks tools that are *already* in a toolset). Two holes:
the blob-scan, and `TOOL_LEGACY_BINDING` as the escape hatch for exactly the 16 tools under audit.

---

## 4. Decisions I need from you (product calls, not defects)

1. **Accept the 4 binds** (A1)? All four add a new LLM-callable read. `get_vif_read` is the weakest: it needs
   the model to transcribe indicator series into the call. Alternative: declare it a factor-modelling QA read.
2. **`get_pair_risk` / `get_trade_outcome_metrics`**: bind (my recommendation) or declare, given each has a
   partial overlap with a bound tool (`get_pair_trade_signal`, `get_post_close_confirmation`)?
3. **The 6 already-covered**: accept as declared (recommended), or upgrade any to a real bind (each has a
   stated leftover unique field)?
4. **The 2 zero-consumer tools** (`get_prompt_injection_read`, `get_thesis_evidence_matrix`): declare, or delete?
5. **PM gating** (C1/C2): should the PM receive a **pre-graph** computed risk gate / position contract /
   liquidity read (a genuine pre-decision gate), or should those prompt rules be softened to "if the context
   reports…"? This changes what the PM can act on, so it is your call.
6. **Prompt-guidance scope**: fill all 30 real gaps now, or only the claim classes you consider load-bearing
   (my recommendation: all, in one batch, since each is a one-line append and the gate can enforce it).

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

**Acceptance:** the new gates fail on the current tree (proving teeth), and the doc lines no longer claim a
binding that does not exist.

### W2 — The binds (A1)

Per tool: add to the toolset/loop → add the prompt line → extend the gate test that the tool is bound *and*
guided. Four files for toolsets/prompts + `risk_tool_loop.py` + the debator prompts; remove the
`TOOL_LEGACY_BINDING` entries for the bound names.

**Acceptance:** each new tool is in the toolset, mentioned with a trigger, executed by its ToolNode (an
end-to-end call with a stubbed vendor seam), and the binding gate is green without the whitelist entry.

### W3 — Prompt guidance for the remaining gap list (B)

One line per tool, in the house style ("cite it before any <claim>"), in the owning analyst prompt; fix the
"three tools / four listed" miscount and the unconditional ETF paragraph (emit it only on the ETF path).
Re-run the S2 advertised-signature gate (the new lines must not advertise wrong arities) and the prompt-token
budget check.

**Acceptance:** the trigger-phrase gate is green for all bound tools; a negative test proves a name-only
mention fails it.

### W4 — Context-channel fixes (C)

1. PM: inject the computed risk gate / position contract / liquidity into the PM prompt (pre-graph precompute
   alongside `_precompute_risk_context`), per your decision in §4.5 — and if any rule cannot be backed, soften
   the prompt instead of leaving a rule that references a phantom number.
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
- Decision §4.4: delete the two zero-consumer tools or keep them declared.
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
- **Binding a tool the model can't drive**: `get_vif_read`/`get_pair_risk` need the model to supply series;
  the mitigation is the prompt naming the exact call (as `get_book_correlation`/`get_hrp_alloc` already do).
- **PM pre-graph gating** changes what the decision can act on; if you choose "soften the prompt" instead,
  the PM keeps its current behaviour and only the honesty of the instruction changes.
- **Docs are load-bearing here**: correcting them is part of the deliverable, because the false claims are
  what let this gap persist.

## 8. What this plan does NOT do

- It does not give the tool-less agents (sentiment, researchers, RM, judge, PM) a general tool loop — that is
  a design change; it fills the specific holes where their prompts already demand a number.
- It does not re-audit the ~450 calcs that are reachable through another calc; those inherit their parent's
  binding, and W1's gate keeps that true.
- It does not change any vendor adapter or calc arithmetic.

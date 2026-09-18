# Changelog

All notable changes to TradingAgents are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Breaking changes within the 0.x line are called out explicitly.

**Cross-repo rule (the sibling web app).** `trading_web` consumes this repo's tools, CLI flags and JSON
shapes. A change that removes, renames or reshapes something the app uses **must state its web impact in its
entry here** — e.g. "web impact: the app's `GET /api/history/ohlcv` reads `ohlcv['opens']`". The registry of
what depends on what is `trading_web/docs/web_TOPICS.md`; the app's contract tests (`tests/test_engine_contract.py`,
`tests/test_doc_claims.py`) fail when this surface drifts, and this rule is what the engine side owes them.

### Fixed

**D-7 - the leaf scored the wall clock, the card scored the run date (2026-09-18).** Found while designing the research-layer wiring (`docs/scores/ResearchLayerWiring.md`), by executing both paths to the same number with different dates - the same technique that found D-6.
- **The defect.** `_trade_score_engines` called `fundamental_score_for_ticker(ticker)` with no date, and `fundamental_score_for_ticker` falls back to `datetime.now()` (`strategies/fundamental_score.py:550`) - one of only two legs that scores *as of a date*. `_run_card_fundamental_score` (`reporting.py:881-882`) passes `pm_decision.trade_date`. On the documented `batch.py --date 2026-07-22` invocation (`batch.py:5`) those are different panels.
- **Measured, on MSFT:** leaf **`66.25`**, card **`62.50`** - same basis string, same `panel_n=9`. One vector, two numbers on two surfaces, and **the leaf was the wrong one**: it scored a July decision against September's peer panel.
- **Fixed** by giving `_trade_score_engines` a `current_date` and threading it to that one engine, and by adding `current_date` to `get_trade_score` - mirroring the sibling `get_fundamental_score(ticker, current_date)`, which has taken the date all along. Two regression tests in `tests/test_trade_score.py` fail before the fix (`TypeError: _trade_score_engines() takes 1 positional argument but 2 were given`; `assert None == '2026-07-22'`) and pass after. The date-less call still works, so the tool's schema stays backward compatible.
- **Why it survived:** the assembler's existing test pinned the returned dict but never what the function passed *in*. A test that asserts an output without asserting its arguments cannot see this class.

Tests: `tests/test_trade_score.py` **50 passed** (48 + 2).

**Web impact**: none - an optional parameter on an advisory tool leaf, defaulting to `None`. `get_trade_score` is not a web-surface capability.

**D-6 - the leaf's `TradeScore` never read `RiskScore` (2026-09-18).** Found by walking a live example of the score pipeline end to end, not by reading the set: `_trade_score_engines` carried three engine blocks (fundamental, technical, regime) and returned behind a stale *"WP-5 fills `risk` in through its own public entry point ... until it lands the engine is absent"* comment - but WP-5 had landed (`strategies/risk_score.py`, `1260329`) and the sibling leaf `get_risk_score` had read it ever since.
- **The consequence was a different vector on two surfaces.** The leaf's `K` was `None` unconditionally, so `get_trade_score` never applied the owner's published `K = 0.20` and its coverage was capped at **80%**, while `_run_card_trade_score` - which reads all four engine blocks - applied all four. Measured on MSFT: the leaf printed `67.65` at 80% coverage; with the engine wired it prints `70.00` at 100%.
- **Found by executing the path, not by reading it.** The four engines called directly returned `fundamental 66.25`, `technical 62.61`, `regime 79.78`, **`risk null`** - while `_risk_components('MSFT')` returned 13 real components and `risk_score` scored them **79.39**. Components present, score withheld, and the assembler's own test already patched `_risk_components` as if it were in the path.
- **Fixed** by mirroring the other three blocks (`_risk_components` -> `risk_score`), with a regression test that fails before the fix (`assert None == 74.0`) and passes after.
- **This is the third instance of one failure shape** (after the sibling repo's ingest boundary, 2026-09-18 (e), and the `ba50b5f` / `2c05701` defect sets): a producer exists, a reader exists, and the wire between them was never run. A defect ledger built by reading documents cannot see it; only executing the path can. Recorded as **§3.4** in the master's ledger, with the two paths named in the plan's §8.
- **The doc set's status lines were stale and are corrected in the same pass.** All seven engine documents and the master still read *"design (2026-09-17) ... Not started"* / *"Nothing here is implemented"*, and the plan read *"Nothing implemented. No code has been written for any engine"* - while that same plan's §9 carried an **Exit - MET** block for every phase. Each status line now names the module, the leaf, the gate and the measurement state (`docs/scores/README.md`, `IMPLEMENTATION_PLAN.md`, and the seven engine documents).

Tests: engine suite **4770 passed / 5 skipped** (the 4769 baseline plus the one new test).

**Web impact**: none - no wire contract, no report field, no score output shape. The change is inside an advisory tool leaf, and `get_trade_score` is not a web-surface capability.

**All five §14 defects are fixed, and two of them turned out to be code (2026-09-17).** The implementation plan's defect section said "none is a code defect; all are documentation or hygiene" - D-3 and D-4 are code, and that claim was wrong until they were repaired.
- **D-3 - the SEC `User-Agent` carried a non-deliverable placeholder.** `sec_edgar.py` sent `contact: research@example.com` against a published fair-access policy that asks for a reachable contact (10 requests/second per IP; 403s already seen under parallel batch load). `_UA` now carries the owner's real address (`sec_edgar.py:33`). **The same defect class was found next door**: `sp500_universe.py:122` sent `contact@example.com` to the Wikimedia API, which asks for the same thing - replaced with the identical string, and both sites name each other in a comment so a future change is one edit in two known places.
- **D-4 - 11 requests where one would do.** `get_financial_history` looped `_TAG_MAP` calling `companyconcept` once per tag. It now reads every us-gaap tag from a single `companyfacts` payload (`_us_gaap_facts`, `_COMPANYFACTS_URL:74`), which is what makes the P0-1 tag extension cheap. The per-tag loop is **kept as the fallback**: a multi-MB payload can fail or truncate where a small one would not, and losing every tag at once is a worse failure than losing one. `_annual_rows` holds the shared 10-K FY row filter (full-year flow rows only, instant concepts matched on form/fp) so both paths use one rule. Two tests: `test_xbrl_history_costs_one_request_for_every_tag` asserts a single fetch renders the whole table, `test_xbrl_history_falls_back_to_per_tag_when_the_facts_payload_fails` asserts the fallback - **both fail against the pre-change module**. Live smoke test the same day: MSFT rendered 6 annual periods from **2 requests** (the ticker map + one `companyfacts`) where the pre-change path issued 12, and the new UA was accepted by data.sec.gov with no 403.
- **D-1 - the master's §4/§5 stubs.** Re-verified: no stub text remains, and §4 names the cheap path (a tool leaf) against the expensive path (a number on the wire).
- **D-2 - dead cross-references.** Re-verified by a headings-vs-references scan of all nine documents: the dead section names appear only inside the D-2 record row.
- **D-5 - `enable_factor_model` is not a free name.** `design_qlib_integration.md`, `design_finrl_integration.md` and `implementation_plan_finrl.md` all now state, in the body **and** in the seam-table row, that the flag gates the **learned** advisory model only and is not a generic score switch - naming `scripts/factor_model_train.py:7`, `default_config.py:899` and `.env.example:227`. The deterministic composite's gates are separate names for exactly this reason.
- The plan's §14 and the master's §3.3 are now **status tables** (a fifth column per defect); the plan's P0-1 text, which described both changes as still to make, is corrected to past tense in the same pass.
Tests: engine suite **4406 passed / 5 skipped** (the two new XBRL tests), executor **1105**, web **149**.
**Web impact**: none - no wire contract, no report field, no score output. The SEC/Wikimedia UA is a request header only.

### Changed

**D3 reversed: the composite's printed `basis` contract is preserved, not rewritten (owner, 2026-09-18).** The owner re-answered the third research-layer question in the opposite direction, and the first answer's implementation (`02145fe`) is **reverted** in this pass.
- **What was reverted.** `strategies/trade_score.py` — the framing sentence is back to *"Advisory only: never a gate, never a size, never an `opportunity_score`. The hard gates operate downstream and block regardless of this number."*, and the `basis` field's tail is back to *"…; advisory only - never a gate, never a size, never an `opportunity_score`"*. The rendered block is **byte-identical to `6047071`**. `tests/test_trade_score.py::test_the_printed_block_carries_weights_status_and_coverage` again pins the negative clause, now with a comment recording that the wording is a *preserved contract* rather than an oversight.
- **Why.** *"Changing it alters every generated report"* is precisely why a contract change must not ride along with the scorecard rollout. The owner's principle: *"Enablement can be incremental; measurement cannot be pretend. And existing report contracts should not be changed merely to introduce the new scorecard."*
- **The rule this leaves behind.** The scorecard's explanatory text goes in **new** fields — `scorecard_basis`, and `basis_constraints` if the constraints need enumerating — never as a rewrite of a shipped string. So with the gate off, `run_card.json` stays byte-identical to a pre-scorecard tree.
- **D1 and D2 are unchanged** by the reversal and are consistent with both answers: one `enable_quant_scorecard` block gate with the individual engine gates underneath, and deltas held until the vector is measured, validated and promoted.
- **The state machine is reconciled to the owner's simpler ladder** (`docs/scores/ResearchLayerWiring.md` §4.6): enablement and measurement are now **two separate printed axes** — `DISABLED / PARTIAL / COMPLETE` for which engines are active, and `RESEARCH_ONLY -> ACTIVE` for the vector — with the hard invariant **no validated vector → no delta → no movement**. Research calculations may still be logged internally for diagnostics; what is withheld is their presentation as movement.
- **`02145fe`'s reversal is recorded rather than quietly corrected** (`ResearchLayerWiring.md` §9.1): the first answer was implemented and pushed before the second arrived, and both are now on the record.

Tests: engine suite **4772 passed / 5 skipped**; `tests/test_trade_score.py` 50 passed; `trading_web` 149 passed.

**Web impact**: none — this pass restores the strings `02145fe` had changed, so every downstream surface returns to its pre-`02145fe` value.

**The three research-layer questions are answered, and the composite's printed block now leads with its purpose (owner, 2026-09-18).** Decisions recorded in `docs/scores/ResearchLayerWiring.md` §9; **D3 is implemented**, D1 and D2 are design decisions for `WP-12` (not yet built). **See the entry above: D3 was answered again in the opposite direction and is reverted.**
- **D1 — the scorecard's gate.** `enable_quant_scorecard` is the single top-level gate, and the individual engine gates determine which engine rows are populated. The master gate must **not** imply all eight: a partial scorecard is useful during dark launch, because it shows exactly which pieces are active without silently activating every engine. The safeguard is to make the partial state **explicit**, so the block carries a status and names the enabled and disabled engines — the scorecard state machine is now specified in §4.6 (enablement `DISABLED / PARTIAL / COMPLETE` and measurement `RESEARCH_ONLY -> ACTIVE` as **two printed axes**, with `Scorecard status` / `Vector status` / `Movement`).
- **D2 — movement is held until vector validation.** A delta such as `Δ5D: +4.2` implicitly claims both observations are legitimate, and until the vector is measured and promoted that claim is not grounded. The reason is **vector validity, not `RESEARCH_ONLY`** — once a vector is validated, movement is appropriate in a research-only system and is expected to be valuable for the manual review and the debate. A movement field must not be manufactured merely because the current score exists.
- **D3 — the composite's printed block, corrected. [REVERTED — see the entry above; the contract is preserved.]** The owner's principle: *"the report should say what the number is, not primarily what it isn't."* The composite is not useless because it cannot trade — it is the quantitative summary the human reviewer and the LLM debate consume during research. Treated as a **report-contract change** rather than leaving outdated wording in place to avoid touching tests. In `strategies/trade_score.py`: the framing sentence went from *"Advisory only: never a gate, never a size, never an `opportunity_score`"* to *"Purpose: the highest-level quantitative evidence summary, for human research review - not an order, not a position size and not a gate"*, and the `basis` field's duplicate restatement was dropped so the constraint is stated **once** in the block. `tests/test_trade_score.py::test_the_printed_block_carries_weights_status_and_coverage` now pins **both halves** — the purpose and the constraints — so removing either fails it.
- **The rendered block now reads:** `Four-engine decision composite 0.4F + 0.25T + 0.15R + 0.2K. Purpose: the highest-level quantitative evidence summary, for human research review - not an order, not a position size and not a gate. The hard gates operate downstream and block regardless of this number.`
- **Reported, not decided:** the seven engine renderers (`agents/utils/analysis_tools.py:5053`, `:5261`, `:5849`, `:6008`) and the engines' own `basis` tails each end with their own negative-only line (*"advisory only - never a gate, never a size, never a forecast"*). The same reasoning applies, but the owner's decision named the **composite**; changing seven more outputs is a separate call and is not inferred here.

Tests: engine suite **4772 passed / 5 skipped**; `tests/test_trade_score.py` 50 passed.

**Web impact**: the `run_card.json` `trade_score.basis` string changes when the gate is on, and the leaf's tool text changes. `trading_web` reads only `*.md` and no run_card, and no report renders the composite yet (`IVa` carries no scores until WP-12), so **no web surface moves**.

**The research-layer wiring is designed, and the seam is mapped (2026-09-18).** New design document: `docs/scores/ResearchLayerWiring.md`, part of the score-engine set and referenced from the master's §3.5 and §4. Documentation plus the D-7 fix above; no other behaviour changes.
- **The question it answers:** should the scores be exposed in the other research-layer reports and fed to the LLM debate as structured evidence rather than an instruction (owner, 2026-09-18). The answer is yes, and the repository is already shaped to do it at one seam.
- **The finding that motivates it.** The eight engine scores reach exactly two surfaces - a gated tool leaf and `run_card.json` - and `run_card.json` has **no reader in the research layer at all**: the executor explicitly ignores it (`TradingExecution/signald/watch.py:6-8`), the web UI reads only `*.md` (`trading_web/backend/capabilities.py:1699`), and `complete_report.md` is built from state keys alone (`reporting.py:1788`). Meanwhile `computed_decision_context` - one deterministic string built once at `graph/trading_graph.py:649` - already reaches **ten** prompt sites, is text-parsed into the L1 verifiable-claim registry (`structured_debate.py::ground_truth_from_state:298`), and is rendered as report section `IVa` (`reporting.py:1644-1646`). **One producer, three readers, already wired; the scores are simply not in it.**
- **The design:** one snapshot, three readers. A single `quant_scorecard` producer, built pre-graph, read by the rendered context block, by the `run_card` blocks and by the leaf - never computed a third time. One new gate, `enable_quant_scorecard`, default `False`; an engine entry appears iff that engine's own gate is on, which is the rule `_run_card_trade_score` already applies and which is what resolves D-8. The block goes **first** in the context, because `structured_debate.py:216` bounds the whole context to 3000 chars and a tail-appended block would be silently truncated on the one path that verifies claims.
- **What the block must carry, and why:** the four drivers beside the composite (a bare `76.75` reads very differently from `76.75 because F 92 / T 85 / R 78 / K 35`), coverage per engine and on the composite, the absent list, and the **positive purpose** - not only the negative constraint the printed blocks carry today. Score movement (5D delta) is designed with a refusal rule: no prior row means no delta keys, and a delta across a changed weight vector is refused, because a delta across a weight change is not a delta.
- **The boundary is explicit:** the LLM interprets and never recomputes or overrides; a quant/LLM disagreement is surfaced as a deterministic **flag** for the human, never as an override of the measurement.
- **Three further defects recorded, and two stale docs corrected in the same pass.** D-8 (the D-6 class is not closed: the leaf and the card disagree whenever a sub-gate is off), D-9 (a gate-on `enable_sentiment_score` is unreachable by any agent - no sentiment ToolNode is built, `trading_graph.py:343-345`, and a test pins that set; deliberate, but it bounds the design), and D-10 (the structured debate's consensus exit is dead - `structured_debate.py:644` reads a key nothing writes; pre-existing, already on the books at `docs/implementation_plan_defect_audit.md:51` with drifted line numbers). The stale claims: `agents/utils/agent_states.py` said `computed_decision_context` reached "the Trader, Portfolio Manager and the 3 risk debators" when it reaches ten sites; `docs/design_risk_calculations_agent_wiring.md` §3 recorded the bull/bear researchers as having *"no computed context"* and the Research Manager as *"none"*, both false.

Tests: `tests/test_trade_score.py` **50 passed**; `tradingagents/agents/utils/agent_states.py` is a docstring change only.

**Web impact**: none - a new document, a docstring, and (in the D-7 fix above) an optional parameter on an advisory tool leaf. No report field, no JSON shape, no `run_card.json` key.

**The composite's purpose is stated, and the verdict attribution corrected (owner, 2026-09-18).** Documentation and a docstring only - no behaviour, no printed output, no wire contract.
- **What was wrong with the framing.** The set stated only the *negative* constraint (`TradeScore` reaches no gate, no size, no `opportunity_score`) and nowhere stated what the composite is *for*. Worse, master §1.4 and the plan's §8 attributed the acceptance case's verdict to the composite - `F 92 / T 85 / R 78 / K 35 -> NO NEW RISK` read as though the score concluded it. It does not: that is the downstream gate's verdict.
- **The owner's framing, now recorded at both definition sites.** `TradeScore` is the **highest-level quantitative evidence summary**; its consumer is a human reviewer, not an order path. `RESEARCH_ONLY` does **not** mean "do nothing" - it means the evidence is summarised and the conversion to an action is deliberately not this object's job. `F92/T85/R78/K35` is the system saying *"the quantitative evidence is favourable overall, but the application is not authorised to convert that evidence into a trade automatically"*, and the reviewer's job is to ask why risk is the low leg, inspect the underlying metrics, valuation, catalysts, price action and portfolio context, and decide. "I agree, no trade" and "I disagree, that risk reading is temporary" are both legitimate outcomes - supporting exactly that judgment is what the platform is for.
- **Coverage travels with the number**, because a human makes the decision: `72` at `coverage 68%` means **72 over 68% of the intended evidence**, with the missing components named - never "the system has reasonably strong evidence". This is why the printed block carries coverage and the absent list beside the score, and why the floor withholds the number rather than reporting a partial one as whole.
- **Nothing functional changed, and nothing needed to.** The separation is already implemented and correct: no score is pushed into `opportunity_score` (owner Q1 keeps it `null`), position sizing or the risk gate, and the gates operate downstream. This is a **research-only quant system with human-in-the-loop execution**, and that separation is what makes it one - not what makes the score inert.
- Corrected in `docs/scores/README.md` §1.4 (a new *What the composite is for* beside *What the composite may not do*), `IMPLEMENTATION_PLAN.md` §8 and its R10 mitigation, and `strategies/trade_score.py`'s module docstring.

Tests: engine suite **4770 passed / 5 skipped** (re-run over the touched module's file).

**Web impact**: none.

**Dark launch recorded, both directions (2026-09-18).** Phase A's last clause, with every part the environment allowed and the one it did not named.
- **Gate off, live:** `reports/MSFT_20260918_005500` carries **no engine key** in `run_card.json` (12 keys, evidence mode `forced`).
- **Gate on, through the same functions a run uses:** the four toolsets gain **exactly eight tools and remove none**, and the card gains its eight engine keys with live numbers — `fundamental 64.58` (4/4 sub-scores), `technical 61.36`, `regime 72.49`, `risk 79.41`, `sentiment 84.20`, plus `event_state` and `news_score` present with their honest `unavailable` reasons. The composite reads those blocks and **recomputes from its parts**: `0.40(64.58) + 0.25(61.36) + 0.15(72.49) + 0.20(79.41) = 67.92` against the printed `67.93`.
- **Each of the eight gates individually moves `repro_check`'s config hash** (off `42b9a914a36f` → on `e6f00bd36202`) — a dark-launch flip is provably same-input-different-config.
- **The clause not met:** `report_verify.py` / `verify_sweep.py` exiting 0 on `CONFIRMED` — the sweep returned 1 CONFIRMED and 1 SUSPECT, and the CONFIRMED one was a **real defect** (`rvol` at two windows under one name), fixed in the previous commit. A fresh tree is needed to show the sweep clean; the gate-on run producing one was still crawling after 70 minutes under today's vendor conditions, and the `report_verify` LLM pass itself timed out at 600 s.
Tests: none (a measurement record).
**Web impact**: none.

### Fixed

**One metric, one label: `rvol` now carries its window (2026-09-18).** `verify_sweep.py` on a fresh tree (`reports/MSFT_20260918_005500`) returned a **CONFIRMED** internal conflict — *"'rvol' cited at conflicting values: 0.61; 0.8830"* — and the cause is two producers of one name with no label: `momentum.rvol(volumes, window=50)` and `value_dip.trigger_candle`'s own `rvol` at `window=20`, both printed as a bare `rvol=`. The reader (and the model) had no way to tell which window it was looking at. Both print sites now name their window (`rvol(50d)=`, `rvol(20d)=`), and the leaf-shape assertion is re-pointed at the label, since the label *is* the change.
Tests: 31 passed across the rvol/vdu/trigger/momentum-detail selection.
**Web impact**: tool-card text only — two rendered labels gain their window; no JSON shape, prompt, flag or report row changes.

### Added

**WP-10 measured live — the panel, the statistics and the written findings (2026-09-18).** Phase C's harness was not just built, it was **run**: 30 dates (2026-08-06…2026-09-17) under `~/.tradingagents/cache/panels/`, 149 of 150 NASDAQ common stocks, 154,188 metric cells, cost and fetch timestamp recorded per file, and a second invocation that made **0 network calls** (30 cache hits).
- **The vendor gate is recorded, not hidden.** The EODHD key returns 200 on `/eod` and `/exchange-symbol-list` but **403 on `/bulk-fundamentals` and `/fundamentals`** — Extended Fundamentals is support-gated — so each panel's `_meta.vendor_gate` carries the 403 and the build continues on the price leg instead of crashing or caching an empty panel.
- **Measured for 36 of `TechnicalScore`'s 40 components**: rank IC, ICIR, decile spread `D10−D1`, monotonicity (ordered adjacent pairs / 9), turnover, persistence, the OOS split, deflated Sharpe, the purged-CPCV overfit mask and the family PBO/White/Hansen checks. The **redundancy matrix** covers 136 pairs in the 50% trend+momentum+RS block (mean |ρ| 0.36, max 1.00, 8 pairs ≥ 0.80 — `rsi|stoch_k` 0.816, `di_spread|rsi` 0.819, `roc20|rsi` 0.805 over 4,326 obs), with thin-coverage pairs printing their `n`; the FCF-yield cluster reports all five members **MISSING** behind the same 403. `INSUFFICIENT_CROSS_SECTION` is tested both ways (a thin panel is labelled with the failed floor named and produces **no** vector).
- **`docs/scores/MEASUREMENT_FINDINGS.md`** carries the finding per engine with every line labelled MEASURED / UNMEASURED / DECLARED, plus an explicit `UNMEASURED` section — the document never claims a measurement the vendor gate prevented.
- **Two defects found while measuring, fixed failing-first**: `evaluate.cagr` returned a **complex number** when a series compounds to ≤ −100% (a decile long-short spread does exactly that), and `alpha_health` printed `nan` as a factor's rank IC instead of withholding it.
Tests: `tests/test_score_panel.py` **+32**, plus the harness contract suites (`test_score_eval_rows.py`, `test_alpha_health.py`) at 68 passed together.
**Web impact**: none — a measurement script and a findings document; no tool, card, prompt, flag or report row changes.

### Added

**WP-4 through WP-11 — the remaining six engines, their leaves and the composite (2026-09-18).** Phases B, D and E of `docs/scores/IMPLEMENTATION_PLAN.md`, every one default-off behind its own gate, plus the measurement layer's harness.
- **`RegimeScore` (WP-4).** `strategies/regime_score.py` over the market level, not the name: the benchmark's trend, the benchmark's realized-vol percentile, the VIX percentile, the VIX9D/VIX3M term structure (Cboe's own levels) and the chop unit. **The two regime paths are printed, never reconciled** — live on 2026-09-18 Path A said `neutral` while Path B said `BULL/NORMAL/NEUTRAL`, and the output carries `disagree=True` with the reason. **Two defects fixed on sight**: `regime.vol_percentile` returned a **fabricated `0.5`** when it could not rank (master rule 1's exact prohibition) — it now returns `None` with `vol_percentile_read` carrying the reason — and the caller that would have broken, `get_regime_components`, called `regime_label(vol_pct, ...)` undefended and formatted the value outside its `try` (a 30-41-bar ticker would have raised `TypeError`).
- **`RiskScore` (WP-5).** `strategies/risk_score.py`, **inverted (100 = low risk)**, over the owner's eight categories. The three incompatible conventions the tree already ships (a negative CVaR, a positive stress loss, an opposite-sign regime drawdown) are aligned **in the score, visibly** — every row prints raw → pinned → aligned with units and sign — never by changing a producer. `net_beta(weights, betas)` lands in `book_risk.py` as the producer the executor's book builder calls. The semivariance leg consumes `√RS⁻` with the raw sums printed, and **a fixture where `RS⁻ + RS⁺ ≠ RV` raises**.
- **`EventScore` state (WP-8).** `strategies/event_state.py` (the plan's own module name): one `imminence(days, horizon) = clamp(1 - days/horizon, 0, 1)` for all seven families, monotone and bounded, `None` for an absent day-count. **The hard block stays earnings-only** — driven through the real `catalyst.build_catalyst_snapshot`, with a macro-only window leaving it `None` and the module holding no block window of its own. The three company-level calendars print their **ABSENT-with-evidence** text (the P0-9 probe: 50 macro rows, zero company events). Live: OPEX `imminence=1.000` in an OPEX week.
- **`SentimentScore` (WP-7) and `NewsScore` (WP-6).** The sentiment **scale is pinned first and printed** (EODHD/AV −1..1, GDELT −100..100); a read that mixes two tone sources is **REFUSED with the reason**, never averaged; the confirmation quadrant produces four distinct labels. NewsScore prints its five unsupplied categories as **`NA` with a reason**, never 0, and takes materiality from `EventScore` (owner Q6) rather than building a second estimate. Live sentiment: quadrant `confirm-up`, 6 of 18 components, composite 84.6 at 50% coverage.
- **`TradeScore` (WP-11), the composite.** `strategies/trade_score.py` over `{engine: score}` numbers only — it imports no engine. It prints its weights, its status and its coverage, reaches **no gate, no size and no `opportunity_score`** (AST-guarded), reads **no configuration at all** (so a gate flip cannot promote it), and its hard-gate test drives the executor's 17-check `GATE_PRECEDENCE`: the acceptance case `F 92 / T 85 / R 78 / K 35` → 76.75 with the gate at `BLOCK` changes nothing. The promotion ladder is data with one required-evidence record per rung, and a `status=` request is clamped down to the evidenced rung. The vector is the owner's `0.40/0.25/0.15/0.20` (master §1.4/§1.5, rule 18) and the six-engine research allocation stays a separate object it never reads (rule 17).
- **Every engine gate is a toolset membership switch, not just an inert body**: with the gates off, `market_tools()`, `news_tools()`, `sentiment_tools()` and `fundamentals_company_tools()` are byte-identical to before and no engine `run_card.json` key is written; with a gate on, exactly that one tool and that one card block appear. Eight gates: `enable_fundamental_score`, `enable_technical_score`, `enable_regime_score`, `enable_risk_score`, `enable_sentiment_score`, `enable_news_score`, `enable_event_state`, `enable_trade_score` — all default `False`, all in `.env.example`, all in `repro_check`'s config hash.
- **`scripts/score_panel.py`** (WP-10 harness): the cross-sectional panel with per-date caching, 500-symbol chunking, a recorded cost/coverage line, the `INSUFFICIENT_CROSS_SECTION` label below the floors, and the IC/rank-IC/ICIR/decile-spread/monotonicity/turnover/persistence statistics with the redundancy matrix.
Tests: `tests/test_regime_score.py`, `test_risk_score.py`, `test_event_state.py`, `test_sentiment_score.py`, `test_news_score.py`, `test_trade_score.py`, `test_score_panel.py` — every acceptance clause one test, and the four engines' mutations verified to fail the suite that guards them.
**Web impact**: additive and off by default — seven new gated tool cards and, only when a gate is on, one new `run_card.json` key each. No existing card, JSON shape, prompt, CLI flag or report row changes.

### Added

**WP-3 — the `TechnicalScore` engine: nine advisory category sub-scores over the run's own bars (2026-09-17).** `docs/scores/IMPLEMENTATION_PLAN.md` §5.2, gated `enable_technical_score` (default off).
- **One pure function over existing inputs.** `strategies/technical_score.py` takes a flat `{component: raw value}` dict — 40 components across the owner's nine categories (trend 20, momentum 18, relative strength 12, price structure 12, volume 10, breakout 10, mean reversion 8, volatility 5, breadth 5) — and returns the sub-scores, their coverage and a composite renormalised over the categories that could be measured. No fetch, no new formula, no vendor call lives in the module.
- **The direction problem is solved first, which is the whole point of this engine.** Nine inputs are non-monotonic (RSI, stochastic K, StochRSI, RSI2, Williams %R, Bollinger %b, MFI, the Elder thermometer, Keltner %b) and are **band-mapped over the bands their own consumers already read** — RSI 45-70 (`strong`) scores 85 while >70 (`hot`) scores 45, because `hot` is where the producer's consumers stop adding. A naive ramp inverts all nine; a table-driven test asserts each one's favourable end scores higher than its unfavourable end. **A first draft had five of those tables inverted** and the smoke test caught it.
- **`NA` is not `0`.** A component with no value leaves the denominator; the category prints its coverage and the composite prints the weight share actually measured. Below the floor a category is withheld **with its reason** (and a count floor is capped at the category's own size, the lesson from WP-2's FGS).
- **Two producer-side corrections.** (1) The RS **level** (`relative_strength.rs_series`, a stock/benchmark *price ratio*) is scale-dependent and is therefore **not** a component — the scale-free `rs_trend.above_sma` takes its place, and the same reasoning dropped a ramp that would have scored a 0.05 ratio as "maximally lagging". (2) `regime.vol_percentile` **returns `0.5` when it cannot measure** — a fabricated neutral, master rule 1's exact prohibition — so the leaf does not consume it and the defect is recorded with its home in WP-4.
- **`volatility_models.semivariance`** lands as the volatility category's persistent leg: `RS⁻ + RS⁺ = RV` **exactly** (the full-sample decomposition, not the conditional `sum(r²)/n_down`, and not the drift-confounded `σ_up/σ_down`), `None` below `min_obs` with the reason, the score consuming `√RS⁻`.
- **Surface**: leaf `get_technical_score` (bound to the fundamentals toolset only when the gate is on) and a `run_card.json` block carrying the categories with their weights/bands/coverage plus the aligned components. Both card keys (`fundamental_score`, `technical_score`) are now written **only when their own gate is on**, so a run with the engines off writes a card byte-identical to a pre-engine tree.
- **Live (MSFT, NVDA, 2026-09-17):** 35 of 40 components measured, composites `61.25` and `55.34` (both `neutral`) at `coverage 0.95`; the absent five are the fresh-cross-only `golden_cross`, the defective `vol_percentile`, and the three breadth components (a single-name call has no market panel).
- **Phase 0 exit recorded** in the plan §9: all nine prerequisites landed except P0-2 (vendor-gated), the five §14 defects are fixed failing-first, the kernel's five acceptance tests pass with their mutations, and the counts at this commit are engine **4454 passed / 5 skipped**, executor **1105**, web **149**.
Tests: `tests/test_technical_score.py` **+30** (the band tables at their producers' edges, the ramps' ordering, the coverage arithmetic, the recompute-from-attribution property, the sizing-path AST guard, the leaf's assembly on synthetic bars, the gate both ways, the card block and its degrade path, and the semivariance identity). 72 passed across the technical/fundamental/gate suites.
**Web impact**: additive and off by default — a new gated tool card (`get_technical_score`) and, only when gated on, one new `run_card.json` key. No existing card, JSON shape, prompt, CLI flag or report row changes.

### Added

**WP-2 — the `FundamentalScore` engine: four advisory category sub-scores, one `RESEARCH_ONLY` composite (2026-09-17).** `docs/scores/IMPLEMENTATION_PLAN.md` §5.1, gated `enable_fundamental_score` (default off).
- **The four sub-scores are thin wrappers, not four copies.** `factors.category_scores` (the round-3 quality composite renamed in the previous commit) is the one body: winsorise 0.01/0.99 → cross-sectional z → direction sign → coverage-gated weighted mean → tie-aware percentile ×100. `strategies/fundamental_score.py` adds `FQS` (quality/profitability), `FGS` (growth), `VS` (valuation) and `FRS` (financial risk), each with its own band table, its own factor set and its own floor.
- **`strategies/factor_schema.py` is the Q3 record** — `factor / category / formula / direction / base_weight / sector_scope / normalization_method / supplier / availability` for every factor the engine consumes, with `validate_schema()` asserting one identity per measure, ±1 directions, and that **no factor enters two sub-scores**. `base_weight` is `None` everywhere: this repo publishes no per-factor vector, so the engine runs equal-weight and prints that fact rather than inventing coefficients.
- **`NA` is not `0`.** A factor with no supplier on the panel path is named in the output (`rev_cagr5` for FGS; `fcf_yield`, `val_z` for VS) and dropped; a name below the floor is withheld **with its reason**, never scored on what it lacks. Coverage is stated over the sub-score's **own** factor set (a name carrying 3 of FQS's 7 reads `3/7`, not `3/24`).
- **`dcf_confidence` scales the DCF upside (§3.4).** Four measured legs — payload basis + conflict, beta assumed-or-measured with its sensitivity width, the annual-FCF coefficient of variation, the terminal share of fair value — product into a 0-1 confidence, capped at a documented `INCOMPLETE_CAP = 0.6` when a leg could not be read. The caller supplies `dcf_upside` already scaled, so a DCF nobody could verify contributes less with no prose claiming it is an artifact.
- **Two defects found while building, fixed on sight.** (1) `factors.category_scores` **raised `KeyError` on any partial weight vector** — the renormalisation indexed `w[m]` for metrics the caller had not weighted; a metric with no supplied weight is now dropped with its reason. (2) The design's `min_coverage=3` default **withheld every name from FGS forever** (it has two factors with a supplier), an off switch wearing a floor's name; a count floor is now capped at the sub-score's own factor count. Also recorded: the design's §3.1 table listed the Ohlson O in **both** FQS and FRS — one distress probability in two categories of one composite, which master rule 15 forbids; FRS owns it.
- **The peer panel gained an opt-in extension** (`resolve_peer_universe(..., include_score_metrics=True)`): the `ratios.compute_ratios` valuation block, `screen_ticker`'s earnings-yield/growth legs and the Zmijewski X. Opt-in because the round-3 quality composite's published coverage and droplist are computed over the panel's key set — its row must not move, and a test asserts the default panel is unchanged.
- **Surface**: leaf `get_fundamental_score` (bound to the fundamentals toolset **only when the gate is on**, so a gate-off toolset is byte-identical), and a `run_card.json` block carrying the four sub-scores with their bands/coverage plus the composite, so the card holds the numbers and their attribution rather than a quote of the tool's prose. `repro_check`'s config hash gained the new gate.
- **Live (MSFT, 2026-09-17, peer panel of 9):** `FQS 75.0 (7/7)`, `FGS 33.3 (2/2)`, `VS 62.5 (9/10)`, `FRS 87.5 (6/6)`, composite `64.6` over 4/4 sub-scores, 0 withheld.
Tests: `tests/test_fundamental_score.py` **+36** (the schema invariants; the plan's five acceptance criteria; the coverage floor and its cap; the `NA ≠ 0` convention; the band tables against `SCORE_BANDS`; the DCF legs and the scaling; the gate's toolset membership both ways; the run-card block, including its degrade path; the opt-in panel extension). 93 passed across the score/schema/wiring suites.
**Web impact**: additive and off by default — a new gated tool card (`get_fundamental_score`) and one new `run_card.json` key (`fundamental_score`). No existing card, JSON shape, prompt, CLI flag or report row changes; with the gate off the toolset and the card are byte-identical.

### Changed

**WP-2 step 1 — the shared cross-sectional core is renamed, not forked (2026-09-17).** `factors.quality_composite` becomes `factors.category_scores`: one body, many callers, and the caller owns the metric set, the directions, the weights and the band table. The only thing that crosses into the printed `basis` is a `label`.
- **Why the rename is the first step, alone.** The `FundamentalScore` design (`docs/scores/FundamentalScore.md` §3.1) needs four category sub-scores over the same winsorise → z → direction-sign → coverage-gated mean → tie-aware percentile chain. Ground rule 2 says one implementation per computation, so the four sub-scores are thin wrappers over this body rather than four copies of it — and the rename lands before any of them so the diff is unambiguous.
- **Clean cutover, no alias.** The old name is gone rather than wrapped: the two callers (`scripts/value_screener.py:2367`, `analysis_tools._quality_composite_row:4594`) now call `category_scores(..., label="quality composite")` and print the identical `basis` string they printed before. `QUALITY_DIRECTIONS`, `QUALITY_BANDS`, `quality_band` and the `enable_quality_composite` gate are untouched — they are the quality composite's own, not the core's.
- **Tests**: `tests/test_quality_composite.py` → `tests/test_category_scores.py`, 12 tests re-pointed, all passing unchanged. Live docs re-pointed (`docs/api_reference.md`, `docs/developer/04-strategies.md`, `docs/AGENT_ONBOARDING.md`, `docs/scores/{FundamentalScore,TechnicalScore,IMPLEMENTATION_PLAN}.md`).
Tests: 44 passed across `test_category_scores.py` + `test_round3_wiring.py`.
**Web impact**: none — no tool card, JSON shape, prompt or CLI flag changes; the printed quality-composite row is byte-identical.

### Added

**P0-9 — both vendor-capability probes answered (2026-09-17).** Recorded answers, not code; a probe that finds nothing is a result.
- **EODHD `/sentiments` coverage is complete for this universe.** `trading_graph._sentiment_factor_read` hardcodes `source="eodhd"` and returns `None` rather than falling back, while the leaf (`get_sentiment_lead_lag`) does fall back — the probe asked what that costs. **26 of 26 names returned a non-empty series**: 16 large caps at 73-151 daily points over a 150-day window, four ETFs (SPY 151, QQQ 146, IEI 46, VTV 73), a foreign listing (0700.HK 102), an OTC name (SKHY 83), plus BRK.B 43, RIVN 143, ARM 128, CART 84. No empty result, no error. **Answered: mirror the leaf's EODHD → Alpha Vantage → GDELT chain if a gap ever appears, and change nothing now** — a fallback that never fires is untested code on a path nothing can currently exercise.
- **The forward event calendars are ABSENT with evidence.** The moomoo economic-calendar adapter returned **50 rows over the next 14 days, every one a macro release** (Fed rate projections, TIC capital flows, jobless claims, housing starts, bill/TIPS auctions, Philly Fed sub-indices, GDPNow, natural-gas storage) and **zero** rows matching FDA / clinical / trial / phase / court / litigation / ruling / investor day / analyst day / drug / approval. So the adapter supplies the *pattern* (a windowed reader with a typed no-data error), **not** the data, and the three company-level calendars need a company-events source of their own — a vendor decision that does not ride on the economic calendar.
- Both answers live where the item lives: `SentimentScore.md` §3 and `EventScore.md` §4, with the counts and the names, and `IMPLEMENTATION_PLAN.md` §3.9 records the outcome.
Tests: none (probes only). Engine suite **4454 passed / 5 skipped**, executor **1105**, web **149**.
**Web impact**: none.

### Added

**WP-1 — the shared score kernel (2026-09-17).** Seven engines need the same three operations; seven copies would be a defect by construction (ground rule 2, master rule 3). `strategies/score_engine.py` is **three functions and no framework** — no registry, no plugin table, no engine import, no ticker, no I/O, and no weight table (weights are each engine's own, master rule 6).
- **`align(value, *, direction, band=None, lo=None, hi=None)`** maps a raw value to a 0-100 *favourable* contribution: a `lo`→0 / `hi`→100 ramp (inverted for `lower_better`), or a **band table over the producer's own edges** for the inputs whose relationship is not monotone (`NON_MONOTONIC_INPUTS` names RSI, MFI, stochastic, StochRSI, RSI2, Williams %R, Bollinger %b and the Elder thermometer so an engine cannot quietly treat one as monotone). `None` in → `None` out, and an unusable input is `None` too — **never a neutral 50**, which would enter the denominator as if it had been measured. A direction typo **raises** rather than silently flipping a component.
- **`combine(components, *, weights, min_coverage=3, bands=None)`** renormalises over the **present** components (`sum(w·v)/sum(w present)`), reports `coverage` as the fraction of the engine's own weight that was measured, and **withholds below the floor with the reason** — `score` is `None`, never 0 and never 50. `basis` names the weight vector actually used and the components that were absent, so the number cannot drift from its own description.
- **`band_label(score, bands)`** walks the engine's own table top-down; the table is a **required argument**, so there is no default that could be the decision guardrail's contract bands.
- **The two semantics were extracted, not re-derived**: `factors._coverage_floor` and `factors.quality_band` now delegate to the kernel, and the 13 quality-composite tests pass unchanged.
- Eighteen acceptance tests, including the plan's five with their mutations: the absent-component case (a zero-fill scores materially lower), nothing-present (never 0/50), every non-monotonic input alignable and **not** monotone, the basis tracking the weights actually used, and the withholding floor from both sides.
Tests: engine suite **4454 passed / 5 skipped**, executor **1105**, web **149**.
**Web impact**: none — a pure module with no caller yet; each engine's gate lands with that engine.

### Added

**P0-5 — the VIX term structure, from Cboe's own index levels (2026-09-17).** `RegimeScore.md` §1 and §4 forbid substituting the equity-IV slope (`options_surface.term_structure_slope`, one name's option chain) for a VIX term structure, and VIX9D is not on FRED — FRED carries `VXVCLS` for the 3-month and its discontinued 3-month series is `VXOCLS`.
- **`dataflows/cboe.py::vix_term_structure()`** returns `{vix9d, vix3m, slope, state, as_of, basis, reason}` from the two Cboe CDN history CSVs, on the **shared slope convention** (long minus short) so the number is comparable with the equity-IV slope while the basis line says which object it is.
- **The module already existed** as the CBOE delayed options-chain vendor, so the function was **added** to it rather than created beside it — one vendor, one module — and a test pins that the routed `get_options_surface` is untouched.
- **A flat curve is `contango`, not stress**; only a negative slope is `backwardation`. An unreachable CSV leaves the keys `None` with the reason printed and the basis saying the read is unavailable — never the equity-IV slope under a VIX name, never a defaulted state.
- **Cached under `data_cache_dir`, one fetch per day** (the files are end-of-day): a second call is served from disk without touching the network.
- **Live 2026-09-17:** `vix9d=13.39, vix3m=18.55, slope=5.16, state=contango`, `as_of=09/17/2026`. Cboe writes `MM/DD/YYYY`, passed through rather than silently re-formatted — the first draft of the docstring claimed ISO and was corrected against the observed payload.
- Six tests: the two state fixtures, the unreachable reason, the zero-slope case, the daily cache, and the untouched options vendor.
Tests: engine suite **4436 passed / 5 skipped**, executor **1105**, web **149**.
**Web impact**: none — a strategy-facing producer, not registered in `VENDOR_METHODS`; no wire field, no gate.

### Added

**P0-6 — the short-interest percentile over a name's own settlement series (2026-09-17).** `SentimentScore.md` §1 marks short interest PARTIAL: the settlement series was already fetched and only the raw level printed, so a number could not be read at all — 12% short is crowded for one name and ordinary for another.
- **`strategies/short_interest.py::short_interest_percentile(series, *, min_obs=4)`** returns the percentile of the latest settlement within the name's own history, beside the raw value, the prior settlement, the period-over-period change, the series length and the **direction** sentence: *high short interest is bearish positioning with a squeeze RISK, not a bullish signal*. The sign is stated so the percentile cannot be quoted as a squeeze thesis by itself.
- `min_obs` is counted in **settlements, not days** — FINRA settles twice a month (published on the 7th business day after), so four is about two months of history.
- Below `min_obs` the percentile is `None` **with the reason** ("1 settlement(s) held, 4 needed"), never a fabricated 0.5; an empty series is `None`, never 0.
- **Wired into `massive.get_short_interest_massive`**, which carried the series and printed only raw settlements: it now prints `Latest settlement vs its own history: latest of 5 settlements, 100% percentile of this name's own history, +14.3% vs prior settlement` plus the direction line.
- Four tests: the 6-settlement known percentile and change, the mid-range rank, the single-settlement reason, the empty series, and the wired rendering.
Tests: engine suite **4431 passed / 5 skipped**, executor **1105**, web **149**.
**Web impact**: none — an added advisory line inside an existing leaf; no wire field, no gate.

### Added

**P0-3 — market-wide breadth from the panel the run already fetched (2026-09-17).** `RegimeScore.md` §1 marks market-wide advance/decline, new highs/lows and percent-above-MA as ABSENT; this is the smallest honest producer, and it needs **no new vendor**.
- **`strategies/market_breadth.py::market_breadth(closes_by_name, *, windows=(20, 50, 200), min_n=20)`** returns `{pct_above_<w>, n, coverage, advance_decline, advancers, decliners, new_highs, new_lows, small_sample, basis}` or `None` for an empty panel. The percent-above columns come from the shared `sector_breadth.multi_breadth`; the A/D, high/low and coverage counts are computed from the **same map**, so the numbers cannot describe different panels (one implementation, two scopes).
- **The denominator-integrity gate is the shared one** (`sector_screener.breadth_with_gate`): below `min_n` the percentages render `None` with the reason, never a noisy rate over a handful of names — while the counts still travel, because a count is not a rate.
- **The high/low counts are measured against the window the caller supplied, and the basis line says which window that was** — a 60-bar panel cannot be quoted as a 52-week figure. `None` for an absent read, never 0.
- **Real run:** over 22 names drawn from the in-repo S&P map (315 constituents) it returned `n=22, coverage=1.0, pct_above_20d=45.5, pct_above_50d=54.5, pct_above_200d=40.9, A/D=-2, new_highs=1, new_lows=1, small_sample=False`, with the panel size in the basis line.
- Five tests: the known-answer panel, the gate at its default, a panel over the floor with its panel size, the empty/unusable cases, and the window-provenance rule.
Tests: engine suite **4427 passed / 5 skipped**, executor **1105**, web **149**.
**Web impact**: none — a pure strategy module with no caller yet; the engines that consume it (WP-3, WP-4) land behind their own gates.

### Fixed

**P0-8 — the five recorded defects, and two of them were real bugs (2026-09-17).**
- **P0-8a — the catalyst argument was inert, so every event position sized the same.** `position_mult_by_side` tested `catalyst > 1` while the only caller documents `catalyst` as 0..1 and `get_catalyst_scale` floors at `catalyst_scale_floor` and never exceeds 1.0 — so `event_scale` was **always 1.0** and a beat sized identically with or without a print in front of it. It now reads `0 < catalyst <= 1` (1.0 stays the no-catalyst case, anything outside the range is treated as no catalyst rather than extrapolated), so a beat at a 0.25 catalyst scale sizes 0.25.
- **P0-8b — `get_earnings_calendar`'s `look_back_days` named the opposite direction to the one it queries.** All three vendors query `[curr_date, curr_date + N]`. Renamed to `look_ahead_days` on finnhub, moomoo and yfinance and on the tool; a test asserts the forward `to` date and that a small value truncates the forward window.
- **P0-8c — `get_tail_risk` fed a close series to a function that wants an equity curve, then printed it as `cdar=`.** The book's CDaR (`book_risk.solve_weights`) is fed the weighted portfolio, so one quantity appeared to have two producers (master rule 15). The proxy stays — it is a legitimate drawdown read on a 1-unit buy-and-hold — but it is **labelled** (`price_path_dd_tail_mean`, `price_path_dd_var`, `price_path_max_dd`, with "not the book CDaR" printed beside it) and the name is refused: no bare `cdar=` token remains.
- **P0-8d — the cash-sleeve rule had two implementations.** `portfolio_cvar` and `book_correlated_stress` each carried their own copy of the equal-weight / over-allocation / cash-sleeve normalisation, so a change could land in one path and miss the other. Both now read `normalize_book_weights`, and a test replaces that ONE rule and shows both paths move.
- **P0-8e — `get_macro_regime_read` demanded five caller-supplied markers while the run's own leaves held them.** In practice they arrived empty and the label was almost always `n/a`. `_derive_macro_markers` now fills all five: the 10y-2y slope and HY OAS from FRED, the policy-rate and dollar changes over their own windows from the FRED series, and the vol percentile from the VIX's trailing rank. **A supplied value always wins**, an unmeasurable one stays `None` (never a default), and the leaf prints which markers it derived and which it could not measure.

### Added

**P0-4 — the VIX percentile, and the FRED read on the market surface (2026-09-17).**
- The VIX existed in this repo only as a raw FRED level on the NEWS surface, never as a regime input. `analysis_tools._vix_percentile_read` now ranks the latest `VIXCLS` close within its own trailing year and prints its basis (`VIXCLS 18.42 at the 62% percentile of its trailing 252d (n=251)`), returning `None` with the reason when the history is too short.
- It is built on **`fred.get_series_values`** (a new series accessor: time-ordered `(date, value)` observations over a window, never raising, `"."` rows dropped rather than zero-filled) and **`normalized.percentile_hist_or_none`** — the honest-contract sibling of the four rank helpers that returned a neutral 0.5 for an unmeasurable rank. One implementation, and `None` below `min_obs` rather than a fabricated mid-range.
- The percentile feeds the market-level regime path as `get_macro_regime_read`'s derived `vol_percentile` marker, and `get_macro_indicators` is now bound to `market_tools()` as well as `news_tools()`.

### Changed

**P0-7 — the four mis-homed toolset bindings (2026-09-17).** All in one commit, per the toolsets collision rule.
- **`sentiment_tools()` exists** (Q5): 11 leaves, registered as the `sentiment` analyst key so `analyst_toolset("sentiment")` stops raising `KeyError`. The sentiment **analyst** still binds no tools — that is its documented design (its data is pre-fetched into the prompt from turn 0), so the surface is addressable for the engine without changing the analyst's contract.
- **`get_institution_holdings`** (P0-7a) is on the sentiment surface: institutional sentiment is 15% of that engine and the leaf was bound only to `fundamentals_company_tools`.
- **`get_analyst_revision_index`** (P0-7b) is on `news_tools()`: NewsScore's analyst category (5%) reads it.
- **`get_market_breadth`** (P0-7c) is on `market_tools()`: it is a market read, and it was reachable only from the news analyst.
- The market prompt gained the two trigger lines its new leaves require — `test_prompt_trigger_contract` is the gate (a bound tool must be given a "use before any X claim" sentence). Budget pins held: 79 of 95 bullets, well under the 50,000-char ceiling.
Tests: engine suite **4422 passed / 5 skipped**, executor **1105**, web **149**. Fifteen new tests across the three items; **11 of them fail without the source changes** (verified by stashing the sources), and the twelfth is an import error by construction.
**Web impact**: none — no wire contract, no report field. `get_macro_regime_read` gains an optional `current_date` and prints a `markers:` clause; the other leaves print the same numbers under honest names.

### Added

**P0-1 — the structured SEC XBRL series, and the consumer that needed it (2026-09-17).** The first Phase-0 prerequisite: the 5-period legs (Mohanram G4/G5, the CAGR family, Dechow-Dichev's 8-period accrual window) printed "5-year ROA series unavailable (n=0)" wherever the data existed upstream, because the vendor statements carry ~4-5 annual periods and nothing consumed the free source that goes deeper.
- **`sec_edgar.financial_history_series(ticker, years=15)`** is now the structured producer: `{"series": {label: {fiscal_end: value}}, "span": [first, last], "years"}`. `get_financial_history` renders from it, so the table and any consumer of the series cannot disagree (one implementation, two readers).
- **`_TAG_MAP` grew from 8 to 12 rows**: `EarningsPerShareDiluted`, `OperatingIncomeLoss`, `DepreciationDepletionAndAmortization`, `GrossProfit` join revenue / net income / OCF / capex / assets / liabilities / equity / cash. The row reader now accepts the units the SEC actually files per-share concepts under (`USD/shares`), which a hardcoded `USD` lookup silently dropped.
- **EBITDA and FCF are derived, never fetched**: neither has a us-gaap tag, so `sec_annual_series` computes `operating_income + d_and_a` and `operating_cashflow - capex` and marks them `derived: true`.
- **`statement_parsing.sec_annual_series`** maps the labels to the canonical series keys, keeps only the **longest run of consecutive fiscal years** per key (the readers index these arrays positionally, so a hole would misalign them), and calls the same `_add_roa` the vendor path calls — the ROA series is derived once, on beginning-of-year assets, for both sources.
- **The merge is opt-in** (`fetch_ticker(..., with_sec_series=True)`), wired at the two leaves that need the depth: `get_quality_factors` (G4/G5) and `get_earnings_quality` (Dechow-Dichev). One EDGAR request plus an as-reported USD basis is a cost the default vendor path must not pay, and a test asserts the default call **never touches EDGAR**. When asked, the longer series wins **per key** — never spliced across bases — and the provenance row names `source: "sec_xbrl"`.
- **Four new tests** (all failing against the pre-change source): the label mapping with derived EBITDA/FCF and the ROA alignment, the empty result for a non-US ticker, the longest-unbroken-run rule, and the opt-in merge with its provenance. Three existing test doubles needed `**kw` for the new parameter — the changed contract, not a regression.
Tests: engine suite **4410 passed / 5 skipped**, executor **1105**, web **149**.
**Web impact**: none — the series is additive to `fetch_ticker`'s return and reaches no wire contract; the two leaves that opt in print the same rows with more depth.

### Added

**The poisoned-tree regeneration landed six fresh trees, all verified clean, before the run was stopped (2026-09-17).** No code change: the corpus half of the previous pass's decision.
- **Six of the fifteen affected tickers were regenerated** (shallow depth, `--verify`, production env with `TRADINGAGENTS_ANALYST_FORCED_TOOLS` popped): `AMKR_20260917_174353`, `AMZN_20260917_172613`, `ASML_20260917_181308`, `HPE_20260917_180506`, `IBM_20260917_184255`, `JCI_20260917_185054`. The run was stopped on the owner's instruction; the remaining nine tickers keep their `POISONED_LEAF.md` markers and are regenerated on demand.
- **All six verify clean by the same scan that found the poison** - each fresh tree's `get_balance_sheet_health` leaf reports a `current_assets` that matches a `Current Assets` row of that tree's own `get_balance_sheet` leaf and no non-current row. That is the fixed reader confirmed end to end on a fresh vendor payload, not only on its unit tests. The poison value is visible beside it: the poisoned AMZN leaves read `588,959,000,000` (the 2025-12-31 non-current row) where the fresh tree reads `229,080,000,000` from the current-assets row.
- **Every fresh tree carries the `evidence` block in `run_card.json`** (`{"mode": "forced", "forced_tools": ["ALL"], "analysts": [...], "rendered_blocks": 3}`), the mechanism added after the legacy-mode trees made their gather-off downgrade invisible - so a tree now states which mode built it.
- **All six carry `verify_flags.json`** - two from the batch's own `--verify` pass (`ASML`, `HPE`), four generated with `scripts/report_verify.py` in the same shape, so no new tree joins the "without `verify_flags.json`" list.
Tests: none (corpus only). Engine suite **4404 passed / 5 skipped**, executor **1105**, web **149** - unchanged, no code touched.
**Web impact**: none.

### Added

**The six items outside the score set are decided, and the one without a document home now has one (2026-09-17).** One code change (the weighting exemption), one corpus regeneration, and the rest documentation.

- **The three legacy-mode trees -> kept as the documented gather-off downgrade example, explicitly labelled.** `MSFT_20260916_174952`, `VTV_20260916_175407` and `IEI_20260916_175246` each carry `LEGACY_GATHER_OFF.md` in the tree root: the leaked `TRADINGAGENTS_ANALYST_FORCED_TOOLS` value, the absent `_rendered_block`/`_model_pool`, the empty digest lines, and the fact that their `run_card.json` has no `evidence` block (it predates the writer at `tradingagents/reporting.py:1445`). Regenerate any tree that is to represent current production verification - their status is no longer ambiguous.
- **The 25 poisoned trees -> correct/regenerate, and the list is re-verified independently.** A balance-sheet leaf reading current assets from non-current assets is a **source/data-binding defect, not a legitimate scenario**; since no stored gate outcome changed, this is a **verification-artifact integrity** issue. Scanning each tree's own `get_balance_sheet` leaf for a `Current Assets` / `Total Non-Current Assets` row whose value equals the health leaf's `current_assets` - over **every column**, since the health tool merges the latest as-reported period per line item - reproduces **exactly the 25 of 37** already recorded (AMKR, AMZN ×4, ASML, HPE, IBM, JCI, LULU, MSFT ×5, NFLX ×2, NVDA 09-15 14:19, SIMO, SMCI, TSM ×2, VST ×2, WDC 09-14), with AMAT, LRCX, MSFT `20260916_231406`, NVDA `20260915_223229` and WDC `20260915_120300` clean by the same test. Each of the 25 now carries `POISONED_LEAF.md` with the mis-bound value, the true current-assets value from the same tree, and the decision; and a **fresh tree is regenerated per affected ticker** (15 tickers, shallow depth, verify on) - that run is **in flight at this commit**; the markers are what close the integrity issue now, and the regenerated trees are verified in the next pass.
- **The DISCLOSED-vendor-pair tradeoff -> keep both survivors flagged until a reproducer is run**, then decide whether `_disclosed_pair` needs broader cues. **Do not weaken the detector merely to eliminate the flags.**
- **The weighting-decision UNSUPPORTED family -> the explicit exemption, implemented.** A stated analyst weighting is a **methodological judgment, not a factual claim about the external world**, provided the weighting is explicitly stated in the synthesis itself. Implemented deterministically rather than by prompt hope in `tradingagents/agents/utils/report_verifier.py`: `_is_weighting_statement` (narrow cue - the weighting verb must take one of the analyst's **own signals** as its object **and** sit beside a comparative or explanatory token; "risk" is deliberately excluded so "risk-weighted assets are higher" and "the index is cap-weighted toward tech" are untouched), an `_anchor_claims` branch that grounds an UNSUPPORTED weighting claim **only when it carries no decimal figure** ("the statement, never the figures it cites"), and a `_VERIFY_INSTRUCTIONS` bullet so the flag is not raised in the first place. Tests: `test_a_stated_weighting_is_not_a_claim_about_the_world` and `test_a_world_claim_that_merely_says_weighted_is_not_exempted` - both fail against the pre-change module.
- **The sentiment-score anchor -> leave open until a live case occurs**, then choose between a statement-based anchor and a source-derived band from what the pipeline actually produces. No pre-commitment on a hypothetical.
- **Intraday event-risk sizing vs latency -> recorded, with a document home** (`EventScore.md` §8). It is **not merely a FinancialJuice integration question**: it decides **whether fresh intraday event information may modify sizing, and under what latency and data-quality conditions**. The section names the four contract halves that make it hard (latency, data quality, idempotence/re-entry, fail-closed), and pins that the daily contract must not move (master rule 9/17) - any such path is a **separately authorised sizing input**, never a silent second `TradeScore` input.
- `IMPLEMENTATION_PLAN.md` §13.4 is now a **decision record** (six rows, each with the class the owner gave it and the decision) instead of an open-items list; the master's §7 points at it; and the verifier document's own "Open items" section carries each decision inline with its evidence.
Tests: engine suite **4404 passed / 5 skipped** (the two new verifier tests), executor **1105**, web **149**.
**Web impact**: none - no wire contract, no report field, no score output changes. The verifier's exemption is advisory-only and never edits a report.

### Added

**The owner confirms both diagram completions, and the two ledger statements are recorded as binding rules (2026-09-17).** Documentation only: no code, no gate, no test.
- **`RiskScore` is a `TradeScore` engine, not a risk gate.** The owner confirms the flagged addition: `RiskScore` contributes the `R` component of the four-engine `TradeScore = 0.40F + 0.25T + 0.15R + 0.20K`, while the hard gates operate **downstream** of `TradeScore` and can hard-block a proposed action **regardless of the composite score**. The distinction is `RiskScore != Risk Gate`; drawing them as one object hides the producer of one of the four numbers. The caveat marking it as the assistant's addition is gone - now confirmed and kept.
- **The six-engine research allocation and the four-engine `TradeScore` are separate objects.** Fundamental, Technical, Regime and Risk feed `TradeScore`; News and Sentiment participate in the research allocation for attribution and do **not** directly contribute to `TradeScore`. The owner's earlier diagram, which routed News and Sentiment straight into `TradeScore`, would have turned a four-input decision composite into a six-input one and contradicted decision Q2 - corrected.
- **Both statements are recorded verbatim as ledger statements** in `IMPLEMENTATION_PLAN.md` §13.1 and `README.md` §1.4, and as **binding rules**: master **rule 17** / plan rule 11 (*no engine enters the decision composite by adjacency* - an engine joins only by an explicit decision, never by being drawn next to the others) and master **rule 18** / plan rule 12 (*`RiskScore` is a `TradeScore` engine, not a risk gate*).
- **The owner's implication is recorded:** `NewsScore` and `SentimentScore` can still be highly informative without being direct decision-score inputs - their information may affect research attribution, diagnostics, explanations and *potentially separately authorised sizing mechanisms* - but must not silently become a fifth/sixth `TradeScore` factor. "Separately authorised" is the operative word: a sizing path that consumes them is its own decision with its own contract, not an adjacency in the diagram.
- **Two stale flags retired in the same pass (rule 9).** §1.4's "two conflicts inside the owner's own diagrams, flagged not resolved" is now a **resolution** - gate order settled by decision Q8 (gates before sizing) and which composite governs settled by decision Q2 plus this confirmation - and §1.5's note that the four-score vector was "withdrawn as a production score" is corrected: the withdrawal was of the four-score version as *the whole* score, not of `TradeScore` as the decision object, which the owner re-affirmed. §2.1's heading no longer says "seven" invariants (it carries rules 8-18).
Tests: none (documentation only). Engine suite **4402 passed / 5 skipped**, executor **1105**, web **149** - unchanged, no code touched.
**Web impact**: none.

### Added

**The architecture diagram is corrected: `FundamentalScore` was omitted by oversight, not by design (2026-09-17).** Documentation only: no code, no test. The owner confirms the omission, so `IMPLEMENTATION_PLAN.md` §13.1's flow diagram now carries `FundamentalScore` with its **own data root** - statements and filings, not market data - feeding `TradeScore` directly.
- **Two completions named alongside it, so the drawing and the contracts agree.** First, **`RiskScore` is drawn as an engine** rather than only as "Risk Gates": it is one of the four `TradeScore` inputs (`0.40F + 0.25T + 0.15R + 0.20K`) and a composite never overrides a hard gate (master §1.4), so conflating the score with the gate would hide the engine that produces one of the four numbers. That one is **my addition, flagged for confirmation**, not the owner's. Second, the **two arrows out of the engine row are separate objects** (decision Q2): the six engines feed the **research allocation** (attribution only), while the four - Fundamental, Technical, Regime, Risk - feed **`TradeScore`**, which is what reaches the gates. `NewsScore` and `SentimentScore` are in the six and not in the four, so they reach the decision only through the research layer, never directly.
- The "flagged, not resolved" caveat this replaces is gone; the fuller engine map above the flow diagram is unchanged.
Tests: none (documentation only). Engine suite **4402 passed / 5 skipped**, executor **1105**, web **149** - unchanged, no code touched.
**Web impact**: none.

### Added

**All 28 engine-document questions are answered - the score set has no open design question left (2026-09-17).** Documentation only: no code, no gate, no test. The owner resolved the 18 that were still open; they join the 10 closed earlier, so every question in the six engine documents' §7 now carries its decision inline and each §7 is retitled "Decisions (owner, 2026-09-17) - all resolved".
- **RegimeScore:** the standalone **event category is removed** when `EventScore` ships (the same producer feeds both, so a second factor double-counts one catalyst - Regime = environment, Event = catalyst); the **variance ratio is the canonical persistence producer** with Hurst demoted to a diagnostic; a regime **change** is a **separate state/flag** (CUSUM / EWMA control / BOCPD), not another weighted category.
- **RiskScore:** "correlation risk 15%" is the **cluster/notional concentration share**, renamed explicitly (`cluster_exposure / portfolio_exposure`) and never printed as a correlation coefficient; the **executor / portfolio-risk layer owns the book-level computations** while `RiskScore` owns the per-security view and consumes them; `net_beta` is **planned WP-5 work, not an open question**; and the two expected-move producers are resolved - `options_surface.implied_move_pct:42` **canonical**, `catalyst.implied_move_from_history:111` **fallback and validation cross-check**, no reconciliation model.
- **TechnicalScore:** a **score composed from state/metric leaves** (`raw metric -> state -> normalised contribution -> score`); the **sector ETF is the primary** relative-strength benchmark with SPY/QQQ as contextual diagnostics (one canonical `relative_strength_vs_sector`); and the volatility category does **not** mechanically invert - it is non-monotonic/contextual, with the directional reading from the canonical semivariance method.
- **NewsScore:** **primarily per-name** (market-wide news belongs to `RegimeScore` or `EventScore`); per-article relevance is **retained internally** with the **aggregate as the primary output** plus a concise highest-impact-articles section.
- **SentimentScore:** the **period-over-period change** in institutional holdings is canonical (the level stays contextual, the orderflow proxy stays a separate diagnostic); the **regression slope** is the canonical velocity measure (no second 20-day delta); crowd bands become **percentile-based** with the 40/60 constants as the fallback and the thresholds as configuration.
- **EventScore:** `options_surface.implied_move_pct:42` canonical and history as fallback/validation with **`EventScore` owning the authoritative field** (the same decision as `RiskScore.md` §7 Q4, answered once); events carry an explicit **`EventScope = NAME | MARKET`**; and the four missing calendars are **implementation coverage** - interfaces returning `available | missing | not_applicable`, never `score = 0`.
- **Two new invariants and one contract, recorded in the master's §2.1 (rules 15-16) and the plan's §13.2 (rules 8-10):** **no derived quantity may have two independent authoritative producers** - a secondary implementation may be a fallback, a validation cross-check or a diagnostic, but must not independently contribute to the same composite (this one rule covers expected move, materiality, volatility, sentiment velocity, institutional sentiment and relative strength); **daily is the canonical horizon** with intraday metrics requiring explicit per-metric promotion (`RSI_daily` vs `RSI_intraday` are separate fields), carried as a full metric-class table; and **missing data is `unavailable`, never zero** - including a missing calendar, which is *unknown*, not "no event exists". Master rule 1 gained that last form.
- **The `verify_flags.json` contract is recorded** in `docs/design_report_verification_llm.md`: a missing file is a **contract/implementation gap, not evidence of `false`**, and a tree states `status = VERIFIED | PARTIAL | UNAVAILABLE | NOT_APPLICABLE` rather than inferring it from absence. The dangerous ambiguity removed is that `false` could mean either "verified not to hold" or "no verification data".
- **The owner's second architecture diagram is recorded in the plan's §13.1 and flagged, not resolved:** it does not show `FundamentalScore` (nor `RiskScore` as its own node - it appears only as "Risk Gates") while the first diagram does. Read together, the second describes the **decision flow to execution**, not the full engine set; if the omission is deliberate, it is a contract change worth stating because `FundamentalScore` carries the largest research weight.
- **Six items remain open and are listed in the plan's new §13.4** - explicitly **not** covered by this answer set: the three legacy-mode trees (regenerate or keep as the documented downgrade example), the 25 poisoned trees, the DISCLOSED-vendor-pair tradeoff, the weighting-decision UNSUPPORTED family, the sentiment-score anchor when the computed block is absent, and the intraday event-risk latency question, which still has no document home.
Tests: none (documentation only). Engine suite **4402 passed / 5 skipped**, executor **1105**, web **149** - unchanged, no code touched.
**Web impact**: none.

### Added

**The twelve architecture decisions are recorded and propagated - the implementation plan's §13 is now a decision record, not a question list (2026-09-17).** Documentation only: no code, no gate, no test. The owner answered all eleven open questions and added a twelfth (the semivariance measure, already specified in `8535da2`). Every row keeps the **recommendation that was on record** beside the **decision that now governs**, so the reasoning stays visible where the two differ.
- **The decisions:** Q1 the canonical regime path is **C** (market-level, reusing B's four-axis vocabulary); Q2 `TradeScore` and the six-engine object are **separate objects with separate names** (decision composite vs research allocation); Q3 `RiskScore` is **both** name- and book-level, with only the book-level components feeding the composite; Q4 the mis-homed leaves **move** (the category weights are preserved, never silently redistributed); Q5 the **sentiment toolset exists** and needs binding repair; Q6 **`EventScore` owns materiality and the expected move** and `NewsScore` consumes it; Q7 the **structured event state** is the deliverable and macro/Fed/OPEX may **not** hard-block; Q8 **gates before sizing**; Q9 the **neglected-firm sign** for coverage; Q10 the score **informs only**; Q11 the score's horizon is **daily**; Q12 **semivariance, not the conditional-σ ratio**.
- **Seven anti-double-counting invariants are now binding** and recorded in the master's new §2.1 as rules 8-14: one quantity to one authoritative producer; EventScore owns materiality; book risk to the composite and name risk to reporting; score and sizing multiplier never merged; market regime at market level and security regime as a name-level diagnostic; daily `TradeScore` takes daily inputs with intraday indicators staying leaves; and directional volatility uses the semivariance ratio, not `σ_up/σ_down` - the rule that stops the volatility factor quietly becoming a second momentum factor through drift contamination.
- **The plan's §13 also carries the architecture the decisions produce** and a §13.3 that states what is **still open**, so the record cannot be read as "everything is decided": the engine documents' remaining questions (the regime event category, the cap family, the two expected-move producers, score-vs-state, the benchmark, the institutional measure, the absent calendars) are listed there by document and number.
- **Ten engine-document questions are closed in place.** Each resolved question in `RegimeScore.md`, `RiskScore.md`, `TechnicalScore.md`, `NewsScore.md`, `SentimentScore.md` and `EventScore.md` now carries a `**CLOSED 2026-09-17 (plan §13 Qn)**` line with the decision, and each §7 opens with a status note pointing at the record. The unmarked questions stay open. **One distinction is kept explicit:** Q6 assigns *ownership* of materiality to `EventScore`; it does not choose between the two producers (`options_surface.implied_move_pct:42` vs `catalyst.implied_move_from_history:111`), so `EventScore.md` §7 Q3 stays open as a producer question.
- **The plan's own inline references were updated with it**: P0-7's two bindings are "move" rather than "decide", WP-4's prerequisite 5 becomes "Path C, decided", WP-5's book-mode, WP-6's materiality source, WP-8's layer 3 and its hard-block note, WP-11's names and its gate-order paragraph, and §11.2's event-block bullet. No `§13 Qn` reference in the plan is left dangling.
Tests: none (documentation only). Engine suite **4402 passed / 5 skipped**, executor **1105**, web **149** - unchanged, no code touched.
**Web impact**: none.

### Added

**Signed semivariance is specified in the score-engine design set - the one addition from the volatility-factor review that survived scrutiny (2026-09-17).** Documentation only: no code, no gate, no test. The measure is **owned by `docs/scores/TechnicalScore.md`** (§1's volatility ledger, §4's producer spec, the methodology appendix) and **read by `docs/scores/RiskScore.md`**'s volatility leg as a named dependency, with the build row in `IMPLEMENTATION_PLAN.md` §5.2 and the acceptance in §5.4.
- **The producer is specified as `volatility_models.semivariance(returns, *, min_obs=20) -> {"rs_up", "rs_down", "rs_total", "rs_ratio", "n"}`**, beside the existing estimators, with `RS⁻ = Σ r²·1[r<0]`, `RS⁺ = Σ r²·1[r>0]` and the identity `RS⁻ + RS⁺ = RV` holding **exactly** (Patton & Sheppard 2015). `None` below `min_obs`, never `0`; the score consumes `√RS⁻` (return units, comparable to `regime.realized_vol:29`) and the ratio, with the raw sums printed beside them.
- **Why not the conditional standard deviation.** The review that prompted this proposed `σ_up = StdDev(r | r>0)`; that is a *conditional* std, which does not decompose - `evaluate.downside_deviation:430` and `rate_utils.downside_measures:149` are the same object and are not semivariance. The ledger rows say so explicitly, and the identity is the test.
- **The asymmetry ratio is specified as `RS⁻/RS⁺`, not `σ_up/σ_down`**, because a ratio of conditional stds is **confounded with drift** - it moves with the mean return, so it partly re-measures the momentum it is meant to complement.
- **The direction is pinned from the evidence, not from intuition:** downside semivariance is the more persistent and more forecast-relevant leg, so the **downside** leg carries the risk weight; and the ledger's methodology appendix now carries the counter-evidence the review omitted - the **IVOL puzzle** (Ang, Hodrick, Xing & Zhang 2006) and the **low-volatility anomaly** (Baker, Bradley & Wurgler 2011), plus the **MAX / lottery effect** (Bali, Cakici & Whitelaw 2011), which the repo already screens from the other side (`get_lottery_factors:8739` → `strategies/lottery.py:88 lottery_verdict`, bound at `toolsets.py:282`). Volatility stays **risk-increasing** in every row; it is never a favourable score on its own.
- **`RiskScore.md` §0.3 gains a fourth pinned convention** (semivariance unit): one quantity that can be a variance, a volatility or a ratio is pinned to `√RS⁻` for the aligned contribution with the raw sums printed - the same defect class (one quantity, three conventions) that section already resolves for CVaR, drawdown and the cap families.
- **The master's rule 3 names the coupling**, so the shared producer has one owner on the record.
Tests: none (documentation only). Engine suite **4402 passed / 5 skipped**, executor **1105**, web **149** - unchanged, no code touched.
**Web impact**: none.

### Added

**The score-engine design set gets an implementation plan, and the five documentation defects found while writing it are recorded (2026-09-17).** `docs/scores/IMPLEMENTATION_PLAN.md` (new, ~74 KB) is built from the eight design documents read end to end: the data and wiring prerequisites, the shared score kernel, the seven engine workstreams, the advisory surface, the measurement layer, the composite boundary, six phases with entry and exit criteria, the parallelism and file-collision map, a consolidated verification checklist, a ten-item risk register, the eleven decisions the owner still has to make, and the external sources the plan depends on with their endpoints and limits. **Documentation only - no code, no gate, no test.**
- **WP-0 names the prerequisites that block everything else**, with the source checked rather than assumed: the SEC XBRL series (`sec_edgar.get_financial_history:173` loops `_TAG_MAP:56-65` calling `companyconcept` **once per tag** and returns a rendered string, discarding its own structured `by_tag` dict - so the CAGR path cannot consume it; `companyfacts` returns every tag in one call against a published 10 req/s ceiling); the EODHD US panel (bulk fundamentals is stocks-only, needs the Extended Fundamentals plan, costs 100 calls per exchange request and 100+N with a symbol list, caps at 500 symbols per request, paid plans 100,000 calls/day); market-wide breadth computed from the S&P map the sector screens already fetch (no new vendor); the VIX percentile from FRED `VIXCLS`; the VIX term structure from the Cboe CDN CSVs (`VIX9D_History.csv`/`VIX3M_History.csv` - VIX9D is not on FRED, and FRED's discontinued 3-month series is `VXOCLS`, not `VXVCLS`); the short-interest percentile over FINRA's bi-monthly settlement series; the three toolset bindings on the wrong surface; and the five recorded defects still open (the inert `position_mult_by_side` catalyst argument first, because it is a real sizing bug).
- **WP-1 is the shared kernel** - `align` / `combine` / `band_label` in one module, because seven engines need the same three operations and ground rule 2 makes seven copies a defect. Its non-goals are stated so they are not added later: no registry, no plugin table, no weights, no engine imports.
- **Each engine workstream carries its own prerequisite order, its own acceptance and its own decision.** The plan does not invent a weight anywhere (master rule 6) and does not resolve a conflict the owner left open (the gate order, the canonical regime path, whether macro/Fed/OPEX may hard-block).
- **The phase plan is Phase 0 → E**, each default-off behind its own gate and each flipped one at a time under the dark-launch protocol. **The gate names were checked against `default_config.py` before being proposed**: `enable_factor_model` already means the *learned* advisory model (`scripts/factor_model_train.py:7`), `enable_factors` and `enable_regime` are documented inert (`.env.example:470-471`, asserted by `tests/test_gate_env_toggles.py:87`), and `enable_score_eval_rows` already gates the IC harness - so the six engine gates are new names and Phase C reuses the existing measurement switch.
- **Five documentation and hygiene defects found while writing it, recorded in the master's new §3.3:** (D-1) the master's §4 and §5 were **stubs** - the restructure of `68931f3` left the wiring contract as two sentences and the phase plan as one paragraph that stopped mid-sentence; (D-2) both the master and `FundamentalScore.md` cited sections that no longer exist (§3.7.x, §3.8.x, §4.2, §5.1-§5.3, §6 Phases A-E, §8, §8.3) - every reference is now repointed at the live section, and the D-2 row keeps the dead names deliberately, as the record; (D-3) `dataflows/sec_edgar.py:30` sends a `User-Agent` whose contact is the non-deliverable `research@example.com` while the SEC's fair-access policy asks for a reachable one; (D-4) the per-tag fetch pattern is 11 requests where one `companyfacts` call would do; (D-5) `enable_factor_model` is not a free name - three design documents describe it as "the score" gate while `scripts/factor_model_train.py` consumes it for the learned model.
- **The master's §4 and §5 are repointed rather than deleted**: §4 now names the cheap path (a tool leaf) against the expensive path (a number on the wire) and records the two couplings the wiring must respect; §5 points at the plan's §9 and lists the gate collisions. The header carries the plan as the build order.
Tests: none (documentation only). Engine suite **4402 passed / 5 skipped**, executor **1105**, web **149** - unchanged, no code touched.
**Web impact**: none. No key, flag, tool, JSON shape or rendered card changed; the plan is a document, and the only contract it fixes in place is the existing one (nothing new reaches the wire).

### Added

**The twelve remaining inventory defects are fixed - three NA-as-zero substitutions, two unreachable fail-closed paths, two model-supplied numbers presented as computed, and five producers no reader could reach (2026-09-17).** Recorded in `docs/scores/README.md` §3.2, fixed with a regression test each. **10 of the 11 new tests fail before the fix and pass after** (the eleventh pins a producer key the graph was misreading).
- **`size.atr` returned `0.0` on a missing or mismatched series**, so a caller testing `is not None` read "unknown volatility" as "zero volatility". It returns `None` now, the same contract `stop_loss_atr` and `etf_risk._atr` already had. Four call sites that would have raised on `None` were fixed with it (`stop_loss_atr`, `contract._atr_with_source`, `value_screener`'s ATR floor, and the `_atr_or_proxy` leaf path).
- **A missing drawdown percentile was scored as the WORST one.** `rank_sectors_multifactor`'s risk leg substituted `0.0` for an absent leg - the floor of a higher-is-better percentile - so an unmeasurable drawdown actively penalised the sector. It renormalises over the legs that exist (the same pattern the composite `score` right below it already used); the best sector on the available leg now scores 100 there instead of 60.
- **`support_structure`'s primary branch was unreachable.** The leaf never passed `atr_value`, so "within 1.5 ATR of the base low" - and therefore the `multi-month-base-support` verdict - could never be emitted. The leaf now measures ATR(14) and passes it.
- **The premarket hard block was dead.** `get_premarket_review` never passed `catalyst_snapshot` to `pre_market.review_decision`, so its earnings-window REJECT/REVISE branch could not fire: a fail-closed path that only the gap leg could reach. A new shared `_catalyst_snapshot(ticker)` producer (one implementation, both callers) feeds it, and the rendered line now carries `catalyst=<verdict> scale=<scale> hard_block=<bool>`.
- **The regime gate's catalyst veto was inert.** `catalyst_window` defaulted to `False` with no producer anywhere, so the veto `regime_gate_read` advertises could never fire. It is now `bool | None = None`: omitted, the ticker's catalyst snapshot is read and an open earnings window (or a hard block) sets it; an explicit value still overrides. The graph's compiled-decision-context line derives it from the snapshot the overlay already carries (`fold_catalyst_into_overlay` stamps it under `catalyst`) and prints `catalyst_window=` beside the verdict.
- **A dead `implied_move_pct` key.** The graph read `implied_move_pct` from the catalyst snapshot while the producer emits `implied_move`, so the position contract's implied-move de-risk never applied. One key, one name; the producer contract is now pinned by a test so reader and producer cannot drift apart again.
- **`knife_factor` was a model-supplied number.** `get_position_risk_multiplier` took all three factors from the LLM - a "computed execution multiplier" fed an invented factor, where 0.0 (block) and 1.0 (no reduction) both looked measured. All three are now **measured from the ticker's own series** by default (`knife_guard.knife_score` -> `factor`, `regime_state.regime_state` -> `F_regime`, `regime_state.vol_cap_factor` over the ATR ratio); an explicit override is labelled `caller-supplied` in the output and an unmeasurable leg reads 1.0 (no reduction) and says so. Live: `execution multiplier MSFT: factor=0.75 (regime 0.75 (measured), vol_cap 1.0 (measured), knife 1.0 (measured))`.
- **`trend_score` was a model-supplied number.** `get_skill_read` is regime-from-opinion by design, so both `trend_score` and `baseline_score` are caller inputs - but they were printed bare, so a report could quote "trend_score=72" or "Fold 60 + 12 = 72.0/100" as if computed. Every number now carries its provenance: `[trend_score 72 (caller-supplied opinion, not measured)]` and `60 (caller-supplied baseline) + +29.00 (YAML skill adjustments)`.
- **`volume_profile`'s value-area accumulator carried a dead incremental add** (the accumulator was recomputed from the bins on the next line, so the statement never affected the result) and the band it produced could legitimately span the whole price range for a bimodal distribution - the AMAT 2026-09-14 read (`va_low == poc == 169.56`, `va_high == 424.64`) could not be told apart from a broken accumulator. The loop is now the band recomputation alone, and a new `value_area_pct` reports the coverage it actually holds, printed by the leaf (`va_pct=0.7463` on MSFT).
- **Unbounded Chaikin was labelled a verdict.** The leaf printed `chaikin=<raw A/D units> (positive=buying pressure)`, so a magnitude that is not comparable across names read as a strength score (AMAT: `869687.156` beside `di- > di+`). It now prints the unit and what the sign means: `(A/D units; sign = net accumulation vs distribution, magnitude not comparable across names)`.
- **`momentum_multihorizon` was built and unreachable** (whitelisted as legacy) and **`rule_signal_macd_hist_rising`** - the only MACD-histogram-slope producer in the repo - had a script as its only reader. Both are now surfaced by `get_momentum_detail`: `momentum_mh: 21d=+3.2%, 63d=+31.2%, 126d=+27.2%, 252d=-1.7% ensemble=+15.0%` and `macd_hist_rising=True`. The wiring gate's whitelist entry is gone with it, so the audit now proves the reachability rather than exempting it.
Tests: `test_analysis_tools.py` **+7** (the multi-horizon vector and the MACD rule through the leaf; the three risk factors measured and the override labelled; the skill read's provenance; the Chaikin unit note; `multi-month-base-support` reachable; the premarket REJECT on a hard block; the regime gate's measured catalyst window), `test_strategies_technical_factors.py` **+1** (the value-area coverage, including the bimodal case), `test_strategies_size.py` **+1** (`atr` None on every unmeasurable shape), `test_sector_rank.py` **+1** (a missing leg is not the worst rank), `test_strategies_catalyst.py` **+1** (the snapshot's implied-move key), and `test_calc_agent_wiring.py` loses one whitelist entry and one exempted case because the function is now reachable. Engine suite **4402 passed / 5 skipped**; executor **1105 passed**; web **149 passed** (unchanged).
**Web impact**: text-only, on tool cards the app renders - the risk-multiplier card names each factor's source, the skill read names its inputs' provenance, `get_momentum_detail` gains two lines, `get_technical_factors`' volume-profile line gains `va_pct=`, the Chaikin suffix changed, and `get_premarket_review` / `get_regime_gate_read` gain a catalyst line. No key, CLI flag, JSON shape, gate or score changed; `size.atr`'s return type is internal to the engine.

### Added

**The six defects the score-engine inventories found are fixed - a dead regime branch, a two-scale choppiness, three unreachable flags and one constant table (2026-09-17).** Recorded in `docs/scores/README.md` §3.1, fixed with a regression test each. No score semantics changed; every fix is a value that was previously unreachable or a claim that was previously false.
- **The regime label was trend-blind on the default path.** `overlays.build_strategy_overlays` called `regime_label(vol_pct, trend, 0.4)` while the default `chop_threshold` was `0.30`, so the choppiness branch could never fire; with the common `vol_pct == 0.5` the label was `neutral` whatever the trend was. Proven before the fix on a real series: a monotone **uptrend** and a monotone **downtrend** both returned `regime=neutral`. The overlay now passes a **measured** choppiness, and the label moves with the trend (`bull` / `bear`).
- **Choppiness was passed on two incompatible scales.** The producer returns 0-100 (canonical Dreiss CHOP) but fell back to a 0-1 log-return dispersion on closes alone (`~8e-07` on a clean trend), while `overlays` compared a literal `0.4` against `0.30` and `get_regime_components` compared the real value against `30.0`. **One scale now: 0-100 in both branches** - the close-only branch is `100 x (1 - Kaufman efficiency ratio)`, same axis and same direction as CHOP - with a single exported `CHOP_TREND_THRESHOLD = 30.0` that both callers use. An unmeasurable chop is `None` (never a fabricated neutral) and `regime_label` treats it as "cannot tell", not as "trending".
- **Donchian breakout flags were unreachable.** `donchian_channel` returned `breakout_up/breakout_dn = None` by construction ("closes not passed; caller derives") and no caller derived them. It now takes `closes`, and the flags compare the latest close against the **prior** N-bar channel - the only definition that can be true, since a close cannot exceed the high of its own bar - with the reference levels returned beside them. Every caller passes `closes` (the `get_mean_reversion_tech` leaf, `value_dip.value_dip_setup`, `scripts/value_screener.py`).
- **`parabolic_sar`'s exit flag was unreachable.** The only leaf called it without `closes`, so `below`/`exit` were always `None`; the leaf now passes the close series and prints `below=`/`exit=` beside the SAR level.
- **`BookState.net_beta` was a declared field with no producer.** It defaulted to `0.0` while every construction site omitted it, so a reader could not tell "flat book" from "not measured" - an `NA`-as-zero defect. It is now `float | None = None`: unknown until something computes it (per-name beta x weight). No producer is added here; the field no longer lies.
- **Gap fill statistics were a constant table printed as a measurement.** `market_session.gap_type` assigned literal `fill_probability`/`days_to_fill` per class (0.3/0.6/0.4/0.8 and 5/3/4/2) and the leaf rendered them as a measured read. They are now **measured** over the same-class gaps in the history the caller already passes (10 bars to fill, median days among those that did, the current bar excluded), with the lookup table kept only as a fallback below `GAP_FILL_MIN_SAMPLE = 8` same-class gaps. A new `fill_basis` field is printed with every read (`measured (280 historical common gaps)` / `heuristic (3 ... < 8)`), so a heuristic can no longer be quoted as a measurement; a measured 0% is now reachable, which the constant table could never produce.
- **Prompt dose**: the market analyst's `get_gap_type` line now asks for the basis to be quoted. No other prompt text changed.
Tests: `test_strategies_regime.py` **+3** (close-only chop on the 0-100 scale and its `None` case, the label moving with the trend through the real overlay path, and the threshold sitting on the producer's own scale in both directions), `test_strategies_market_session.py` **+2** (the measured statistics matching a constructed 6-of-19 fill history with a measured 0% edge case, and the heuristic fallback being labelled), `test_strategies_fundamental_floors.py` **+2** (Donchian flags reachable in all three states with the reference levels, PSAR `below`/`exit` needing closes), TradingExecution `test_sleeves.py` **+1** (`net_beta` unknown, not zero). Engine suite **4392 passed / 5 skipped** (baseline 4385 + 7); executor **1105 passed** (baseline 1104 + 1); web **149 passed**.
**Web impact**: text-only, on tool cards the app renders - the regime leaf's `chop` token is now 0-100 or `n/a (insufficient history)`, `get_mean_reversion_tech` gains `breakout_up/breakout_dn` and `psar below/exit`, and `get_gap_type` gains a `[measured ...]` / `[heuristic ...]` basis. No key, CLI flag, JSON shape or gate changed.

### Added

**The score-engine design is split into a master document and one document per engine (2026-09-17; design only, `docs/scores/`).** Design only - no code changed in this commit. The owner asked for the design to be restructured: `docs/design_fundamental_factor_weight_model.md` was scoped to **FundamentalScore only** and moved to `docs/scores/FundamentalScore.md`, and six new documents were written beside it, under a master that carries the architecture and the cross-engine rules.

- **The set.** `docs/scores/README.md` (master: the seven engines, the direction convention, the engine map, the composite and its gate-order conflict, the cross-engine rules, the **code-defect ledger**, the wiring contracts, the phase plan, the verification requirements, the decision record and the open questions), plus `FundamentalScore.md`, `TechnicalScore.md`, `RegimeScore.md`, `NewsScore.md`, `SentimentScore.md`, `EventScore.md`, `RiskScore.md`. Nothing was dropped in the move: the fundamental document keeps its method, its 106-factor ledger, its four sub-scores and its source appendices; the other engines' material moved into their own documents, where it is expanded with a per-engine component ledger, tool-leaf map, defect list, build order and methodology ledger.
- **Every engine was re-inventoried against the code by a read-only scout, and every row carries a verified `module.function:file:line`.** The findings that decide each document:
- **`TechnicalScore`**: **no composite technical score exists anywhere in the three repos** (re-verified by grep; the only 0-100 "trend score" is an LLM-supplied argument at `analysis_tools.py:9247`). Five of the nine categories are fully scorable today; the holes are EMA slope, RSI slope, ATR percentile, 5D momentum, a public MACD histogram, an OBV value, and market-wide numeric breadth. **Six of the owner's named inputs are non-monotonic** (RSI's 45-70 band, MFI, stochastic, StochRSI, RSI2, Williams %R, Bollinger %b, Elder thermometer) - so the composite band-maps them and prints the raw value, rather than ramping them.
- **`RegimeScore`**: the reported "regime conflict" is a **name collision between two independent paths** that share no inputs, no scales and no label vocabulary - `get_regime_read` → `overlays.build_strategy_overlays` (a 3-valued vol proxy, `enable_strategy_overlays` default **True**) vs `get_regime_state` → `regime_state.regime_state` (four axes + `F_regime`, `regime_state_enable` default **False**) - and both are bound to the market analyst. The volatility-regime evidence is that the **sign** of predictability is regime-dependent, so a `RegimeScore` describes environment and never direction; breadth is a participation/confirmation measure, not an established leading indicator; and the formal persistence tests (`variance_ratio:216`, `hurst_exponent:112`) exist and are unwired.
- **`RiskScore`**: **no 0-100 risk score exists anywhere** (grep `risk_score|RiskScore|risk_grade|risk_rating|risk_band` → zero Python producers in either repo). All eight categories have components, at **three incompatible sign/unit conventions** - CVaR as a negative loss (`book_risk.cvar:18`) vs a positive magnitude (`book_correlated_stress:128`) vs an equity fraction (the executor's `tail.ESResult`); drawdown positive (`portfolio_drawdown:100`) vs negative-with-label (`regime_state.regime_drawdown:146`) vs negative (`signald/engine.py:115`); and two cap families (percent-of-book vs dollar notional vs correlation cluster). The document pins one convention per quantity and requires every component to print its raw value beside its aligned contribution.
- **`NewsScore` ships last and partial**: **5 of its 9 categories are ABSENT** and the largest weight (20%, fundamental impact) has no producer at all. `news_relevance.score_news_article:53` scores **relevance, not materiality** (quoted from its docstring and its lexical point table), so the two are printed as separate rows and materiality stays `NA`. The duplicate-of-SentimentScore question is **not settled by construction** (four couplings), so the separation is a build-time naming rule. Novelty is the highest-value build: Tetlock's staleness measure has a known recipe and a known sign, and the primitives (timestamps + `sentiment._normalise_headline:604`) are already there.
- **`SentimentScore`** is mostly buildable with four holes (20-day momentum, acceleration, per-source breadth, institutional sentiment - the last bound to the *fundamentals* toolset at `toolsets.py:395`). **Sentiment × Price Confirmation is PARTIAL**: `sentiment_lead_lag:65` gives `Corr(dSentiment, dPrice)`, but the owner's `Sign(dSentiment) × Sign(abnormal return)` quadrant and a market-adjusted return do not exist - and the wired fold is a **single-name self-correlation** used as a sizing sign gate, gated off by default. The news-sentiment route also carries **two scales behind one name** (EODHD/AV -1..1 vs GDELT -100..100, unnormalised).
- **`EventScore`** (the owner's seventh engine, no weights given - and that is coherent, because every event producer is a multiplier, a day-count or a boolean, not a normalised factor). Occurrence producers exist for **4 of 7** families; `build_catalyst_snapshot:219`'s return contract is quoted in full; the **only event-triggered hard block is the earnings blackout** (`catalyst.py:280-288`, ≤5 days), and the executor's 17 `GATE_PRECEDENCE` checks contain **no event check** - so the engine's `hard_block` stays authoritative and must not be routed through a score. The overlap with `RiskScore`'s event leg is resolved by question (occurrence vs exposure), function by function.
- **The master's §3 is the defect ledger**: the six defects the owner asked to have fixed (§3.1), plus **twelve more found by these inventories** (§3.2) - a dead value-area accumulator, an unreachable `support_structure` branch, `size.atr` returning `0.0` on failure, an `NA → 0` substitution in `rank_sectors_multifactor`, two LLM-supplied numbers presented as computed (`knife_factor`, `trend_score`), an unbounded Chaikin labelled as a verdict, a dead `implied_move_pct` key, an unreachable premarket hard block, an inert `catalyst_window` veto, an unread MACD-slope producer, and a built-but-unreachable multi-horizon momentum vector.
- **References updated for the move**: `scripts/value_screener.py`, `tradingagents/strategies/factors.py`, `docs/design_quant_formulas_research_round3.md`. The CHANGELOG's and the onboarding log's earlier entries keep their original paths, because they are dated records of what was true then; this entry is the pointer for the move.
Tests: none (no code changed). Doc contract tests: 16 passed, 1 skipped.
**Web impact**: none - documentation only.

### Added

**The staged score spec is folded in: six engines plus a recommended seventh, with the superseded weights kept on the record (2026-09-17; design only, `docs/design_fundamental_factor_weight_model.md` §3.7-§3.8).** Design only - no code changed. The owner staged `docs/ScoreWeight/{fundamental,market,news_sentiment}.md`, which refine the earlier four-score version: **six engines** (Fundamental, Technical, Regime, News, Sentiment, Risk) **plus a recommended EventScore**, four factor catalogs targeting ~250-300 factors in total, and a research allocation of **35 / 20 / 15 / 7.5 / 7.5 / 15** (EventScore's weight still open).
- **Where the staged weights differ from the pasted-text version, the staged version governs** and the superseded numbers stay in the tables for the record. TechnicalScore: trend 20 / momentum 18 / RS 12 / price-structure 12 / volume 10 / breakout-pullback 10 / mean-reversion 8 / **volatility-ATR 5** / **breadth-participation 5** (was 25/20/20/12/10/8/5). RegimeScore: market trend 20 / volatility 20 / momentum 15 / **breadth 15** / choppiness 10 / sector rotation 10 / **macro-credit 5** / event 5 (was 20/20/15/15/10/10/10, relative-regime dropped). RiskScore: volatility 15 / tail 15 / liquidity 10 / **gap 10** / correlation 15 / **concentration 10** (split out) / **portfolio drawdown 15** / event 10 (was portfolio 20 / tail 15 / vol 15 / liquidity 10 / concentration-correlation 15 / drawdown 10 / event 10 / gap 5).
- **The two new engines are grounded, not assumed.** NewsScore: **5 of its 9 categories are ABSENT** (novelty, materiality, fundamental impact, guidance change, corporate events, persistence) and only relevance (`news_relevance.score_news_article:53` - relevance, *not* materiality), the earnings-surprise/PEAD leg (`events.surprise_score:17`, `drift_side:26`), analyst revisions and the macro reads are computed - so it can only ship as a **partial** engine that prints its coverage. SentimentScore: buildable from existing leaves for news level, retail/social, analyst, options, dispersion and raw short interest, with four holes (momentum exists only as a 7-day innovation, acceleration ABSENT, no per-source positive-share breadth, institutional sentiment bound to the *fundamentals* toolset).
- **The duplicate question is NOT settled by construction.** Four couplings already feed one number to both engines: `sentiment.py:589 _weighted_basis` uses the news path's relevance/100 as the sentiment aggregation's confidence weight; `get_news_sentiment_series` is bound to both `news_tools()` and `market_tools()`; the sentiment analyst pre-fetches the news analyst's `get_news` leaf (`sentiment_analyst.py:88`); and `domain_bundles.get_sentiment_flow_feed:93` bundles the two feeds. The owner's "don't let NewsScore become a duplicate of SentimentScore" is therefore a **build-time naming rule**, not an emergent property.
- **Sentiment × Price Confirmation is PARTIAL.** `sentiment_research.sentiment_lead_lag:65` (innovations) computes `Corr(dSentiment, dPrice)` and `sentiment_factor_scale:570` uses sign-agreement against the measured historical IC direction, but the owner's actual output shape - a `Sign(dSentiment) × Sign(abnormal return)` **quadrant label** with a market-adjusted return - does not exist.
- **EventScore is recommended by the staged spec as the gate between NewsScore and `opportunity_score`**, and its producers are the same family RiskScore's event leg reads (`catalyst.build_catalyst_snapshot:219` with `scale` + `hard_block`, `next_earnings`, `fed_imminence`, `macro_imminence`). The doc resolves the overlap by question: EventScore answers *occurrence* ("is a high-impact event happening now"), RiskScore's event leg answers *exposure* ("how dangerous is it for this position"), and neither may re-derive the other's number.
- **Two conflicts in the owner's own diagrams are flagged, not silently resolved (§8.3).** (1) Gate order: the pasted pipeline puts the hard gates *before* sizing, the staged diagram puts them *after* - the engine implements gates-before-sizing (the gate verdict feeds `risk/sizing.size:144`), so the doc keeps that and records the inversion as an open question, because a gate after sizing must unwind a size it already authorised. (2) Which composite governs: the 4-score `TradeScore` or the 6-engine allocation - the staged one is newer and governs, with the first iteration recorded.
- **The literature added to the ledger (Appendix C.2, rows 25-28)**: Tetlock (media pessimism → next-day decline then reversal within days; extremes → volume; a price→tone feedback loop), Baker-Wurgler (high sentiment → lower subsequent returns in hard-to-value names), Barber-Odean and the limited-attention PEAD reading (novelty/attention drive immediate incorporation, stale information drifts), and Da-Engelberg-Gao/StockTwits (**attention** spikes predict negative next-day returns while **bullish sentiment** predicts positive ones - different signals with opposite short-horizon signs, so the two must not be merged).
Tests: none (no code changed). Doc contract tests: 16 passed, 1 skipped.
**Web impact**: none - this is a doc.

### Added

**The four-score architecture is specified, and grounding it found six code defects (2026-09-17; design only, `docs/design_fundamental_factor_weight_model.md` §3.7).** Design only - no code, tool, gate, prompt or schema changed. Four **separate** 0-100 scores, one per dimension, and only then a combination; the owner's governing sentence is *"do not mix them into one score too early"*, and the evidence backs it: value and momentum are ≈ −0.60 correlated and separate sleeves historically beat merging signals into one ranking (Asness-Moskowitz-Pedersen), and composite-indicator practice keeps dimensions separate for root-cause attribution and to avoid a **misleading cancellation**. The MSFT case in the brief is that case - strong long-term trend with deteriorating MACD, RSI fallen, price below the 10/20 EMA and swing setup NO.
- **One direction for all four: 100 = favourable.** `FundamentalScore` (the ten categories already specified, plus the owner's band table: 80-100 exceptional / 65-79 strong / 50-64 average / 35-49 weak / 0-34 poor - and **a high score does not mean Buy**), `TechnicalScore` (Trend 25 / Momentum 20 / Setup 20 / RS 12 / Volume 10 / Breakout 8 / Mean-reversion 5), `RegimeScore` (market trend 20 / vol 20 / momentum 15 / choppiness-persistence 15 / sector 10 / relative 10 / event-macro 10), `RiskScore` (**inverted: 100 = low risk**; portfolio 20 / tail 15 / vol 15 / liquidity 10 / concentration-correlation 15 / drawdown 10 / event 10 / gap 5). Every component prints the **raw** value with its units and sign beside the aligned contribution - which is what resolves three currently inconsistent conventions in the tree (CVaR negative-loss vs positive-magnitude vs equity-fraction; drawdown negative vs labelled band; notional cap vs correlation cap).
- **Readiness measured, not assumed.** `TechnicalScore`: no composite technical score exists anywhere (nearest are the unwired `quant_baseline.quant_signal`, the sector-level `rank_sectors_multifactor`, `get_composite_rank`'s peer percentile and the higher-is-**worse** `knife_guard.knife_score`), but five of seven components are scorable today from existing leaves; **five existing consumers read the opposite polarity** from a naive higher-is-better score (RSI band, MFI oversold, stochastic oversold, the elder thermometer's "quiet dip", and `support_structure`'s near-the-200-SMA-is-good against `swing`'s above-the-200-SMA-is-good) and each component must declare its polarity. `RegimeScore`: no market-level regime score exists (only categorical states, sizing multipliers and raw numerics; the only 0-100 numbers are cross-sectional *sector* percentiles); five of seven components scorable, two partial. `RiskScore`: **no 0-100 risk score exists anywhere** (grep over both repos returns zero hits) so it is a new model - but all eight components have producers, six existing numbers already sit in the favourable direction (`F_regime`, `F_vol`, `knife_factor`, `risk_multiplier.combine`, the catalyst scale, the executor's vol scalar), and the blockers are aggregation recipes and sign conventions rather than missing inputs.
- **The reported MSFT regime conflict is a name collision, not a contradiction.** `get_regime_read` → `overlays.build_strategy_overlays` classifies with a **3-valued** vol proxy and a hardcoded `chop=0.4`, returning `neutral` + a sizing scale (0.47x); `get_regime_state` → `regime_state.regime_state` uses OHLC ATR14/EMA20/EMA50/benchmark/252-bar high and returns four axis labels plus `F_regime` = the **worst** of three legs. No shared call path, independently gated, and **both bound to the same analyst** - so they disagree inside one prompt. A RegimeScore may not average them: it names one producer per component or applies a stored arbitration rule. The score/scale/state/confidence separation (`RegimeScore 68`, `RegimeScale 0.47x`, `RegimeState STRONG_BULL`, `RegimeConfidence 0.75`) is kept explicit, because sizing is not conviction (vol targeting sizes inversely to volatility; fractional Kelly discounts for estimation error).
- **`TradeScore = 0.40F + 0.25T + 0.15R + 0.20K`, and it never overrides a hard gate.** That matches the repo's existing precedence: the repo governor never reads a score and turns `risk_context` into PASS/WARN/REJECT after the contract; the executor evaluates **17 fail-closed checks** in `GATE_PRECEDENCE` order before sizing, and its docstring states the research risk context *"can never move a verdict, and it is never read as a number"*; `risk_multiplier.combine` already zeroes the soft product when a hard flag is live. The weights ship as a hypothesis learned empirically later (Phase D's ladder), which is also how the earlier withdrawal of `TradeScore = 40/25/15/20` *as a production score* is satisfied: it exists as the interaction layer, printed with its attribution, and is not a measurement until validated.
- **Six code defects found while grounding the scores, recorded and NOT fixed (the pass was design-only):** (1) `overlays.build_strategy_overlays` passes a hardcoded `chop=0.4` against `regime_label`'s default `chop_threshold=0.30`, so the chop branch is **dead** and with the common `vol_pct == 0.5` the label is `neutral` **regardless of trend** - a quoted `regime=neutral` may carry no information today; (2) the same quantity is passed on **two incompatible scales** (`chop_threshold=30.0` at `analysis_tools.py:2176` vs the hardcoded `0.4`); (3) `donchian_channel` returns `breakout_up/dn = None` by construction and no caller derives them; (4) `parabolic_sar` is called without `closes`, so its `below/exit` flag is unreachable; (5) `BookState.net_beta` has a producer and **no reader**; (6) gap fill probability / days-to-fill are constants. All six are listed in §1.5 with their evidence and consequences.
Tests: none (no code changed). Doc contract tests re-run: 16 passed, 1 skipped.
**Web impact**: none - this is a doc. The design document gains §1.5 (the six defects), §3.7 (the four-score architecture, its readiness tables and the direction policy), §6 Phase E (the implementation order, arbitration first), §7's six new verification requirements, §8.1/§8.2 updates and Appendix C.2 (the evidence ledger).

### Added

**The 106-factor weight model's five open questions are decided, and the design now enforces the separation they create (2026-09-17; `docs/design_fundamental_factor_weight_model.md` §8).** Design only - no code, no tool, no gate, no schema. The decisions close the document's question list and change its architecture in five places.
- **Q1 - the composite never reaches `opportunity_score`.** It stays a tool-leaf / `run_card` advisory metric, and the executor-facing slot keeps its deliberate `null`. The owner's reason is the distinction this document exists to protect: a deterministic `FundamentalScore = 84` does not imply `Opportunity = 84` (a name can show `FundamentalScore 92 / TechnicalScore 61 / RegimeScore 68 / RiskScore 54 / ValuationScore 37` - outstanding fundamentals, poor current opportunity). What changes is that the `null` gains a **producer-owned `opportunity_score_reason`** so a reader knows the absence is a decision, not a missing value; that is an envelope change, so it carries the same `artifact_sha256`/`decision_hash` consequences and is **designed, not scheduled**.
- **Q2 - learned weights are in scope, as a research layer.** Not inside the deterministic production score, and never promoted because they improved in-sample: the ladder is `RESEARCH_ONLY → VALIDATED → CONTRACT_MIGRATION → PRODUCTION`, and the comparison against the deterministic baseline is on IC, decile monotonicity, spread and stability. The repo's precedents for the shape are `enable_tuner` and `enable_factor_proposal_loop`.
- **Q3 - sector overlays: architecture now, suppliers deferred.** Every factor carries `factor / category / formula / direction / base_weight / sector_scope / normalization_method / supplier / availability`, so a bank or REIT overlay is a data event rather than a code fork. Until a supplier exists the metrics are `NA`, and **`NA ≠ 0` is a hard rule**: missing data reduces the *available* weight instead of punishing the name, and a missing metric is never manufactured from a generic factor (a bank scored on `ev_ebit` is not a bank score). The convention is already implemented - `quality_composite`'s coverage floor and `withheld`, `growth_metrics`' omit-don't-zero, `capex_quality_read`'s renormalisation, `signal_summary`'s refusal to print a partial sum under the full denominator - so the design extends it rather than inventing it.
- **Q4 - the full EODHD US panel is the official validation universe.** The named basket stays a dev/diagnostic set and is labelled `VALIDATION_STATUS = INSUFFICIENT_CROSS_SECTION`: it may never produce authoritative factor weights. Phase C now specifies the statistics (`IC_i,t = Corr(Factor_i,t, Return_t+H)`, `MeanIC`, `ICIR`, `DecileSpread = Return(D10) − Return(D1)`, `Monotonicity = correctly ordered adjacent decile pairs / 9`) and names a **gap to close first**: `alpha_health.score_evaluation_rows` is the ready-made harness, but its floors (`min_names=4`, `min_obs=5`) are a smoke floor and it emits no insufficiency status - it does already declare its rows are "inputs to the DSR/PBO multiple-testing check, never a standalone verdict", so nothing reads it as one today.
- **Q5 - no `factor_score=NN` in prose.** Scores reach the reader through structured output (`fundamental_score`, `fundamental_score_status`, `fundamental_score_confidence`); narrative states quality in words. The decision also **closes** a coupling the document had flagged as a hazard: `structured_debate.ground_truth_from_state` harvests `key=value` numbers out of the fundamentals prose into debate ground truth, so a score printed into the report would have become a debated claim automatically. The prompt may state what the *factors* show, never the score.
- **The owner also withdrew his own earlier `TradeScore = 40/25/15/20`** for the same reason he withdrew the source's `0.35/0.25/0.25/0.15`: an unvalidated combination is a research composite, not a measurement. The four category sub-scores are therefore the advisory output, the composite ships as `RESEARCH_ONLY` behind a status vocabulary, and `OpportunityScore` stays separate and `null`.
**Web impact**: none - no key, CLI flag, tool, JSON shape or prompt changed; this is a doc. The design document's §8 is now a decision record with rationale, and its remaining open items are data questions (overlay suppliers, the EODHD fetch plan, the measured IC table), not design questions.

**The factor-model inventory's four defects are fixed - the series readers get a producer, and two labels stop lying (2026-09-17).** Found by the 106-factor inventory (`docs/design_fundamental_factor_weight_model.md` §1.4) and fixed on sight. No score semantics changed; every fix is a value that was previously unreachable or a claim that was previously false.
- **`roa_series` / `revenue_series` had no producer.** The Mohanram G-Score's G4/G5 legs read them (`quantitative_scores.growth_metrics`) and nothing in the tree ever wrote them, so `var_roa` / `var_sales_growth` were structurally absent and the G-Score printed "5-year ROA series unavailable (n=0)" for every name. New `statement_parsing.annual_series` (+ `_period_canonicals`, `_period_token`) stacks **one canonical dict per fiscal year** through `_flat_canonical` - the same row matcher the merged payload uses, so a series value cannot disagree with the newest-period value for the same key. It merges a moomoo `get_fundamentals` payload's per-statement tables **by year** (12 tables = 4 periods, not 12 half-empty ones), derives `roa_series` on **beginning-of-year** total assets - the convention `growth_metrics` uses for the ROA level, so the level and the variance cannot disagree - **aligned by fiscal year** rather than by position (the income and balance statements arrive as separate payloads on the yfinance path, exactly as the level ROA already joins them), and never splices one key's values across payloads (a vendor switch mid-series would join periods that need not share a scale or currency). `fetch_ticker` attaches `revenue_series` / `net_income_series` / `total_assets_series` / `operating_cashflow_series` only when a payload carries two complete periods, with provenance naming the period span and re-using `_period_kind` - so a series built from a quarterly payload under an annual request flags `basis_conflict` instead of printing as a clean annual series. A key missing in any period is omitted, never zero-filled; a year with no prior-year balance sheet is skipped, never re-indexed. **Live smoke** (`fetch_ticker` + `growth_metrics`, 2026-09-17): MSFT and AAPL each carry **5 series keys over 4 annual periods** (FY2023-FY2026 / FY2022-FY2025, `roa_series` n=3), all `observed_kind=annual`, no conflicts - so the G-Score's variance legs are still EXCLUDED on today's vendor history, now reporting the honest `n=4`/`n=3` instead of `n=0`, and they compute the moment a 5-period payload arrives (the 6-period case is pinned by test). Wiring `sec_edgar.get_financial_history` (up to 15 annual years, US filers, already a tool at `analysis_tools.py:8783`) into the producer is the unlock and is listed in `design_fundamental_factor_weight_model.md` §3.6.
- **The Dechow-Dichev caller could never fire, and would have fabricated a number if it had.** It required `operating_cashflow` to be a **dict of ≥6 keys** - a shape the canonical merge never produces (a float or `{current, prior}`) - and, had it ever fired, fed `dechow_dichev_aq` an **all-zero accruals list**, i.e. a residual std computed from a series no statement supports. It now reads the series above with accruals on the Sloan proxy the repo already defines, `(net income − CFO) / total assets`, and prints the substitution beside the value (`dd_aq=… (accruals=(NI-CFO)/total assets over N periods)`) rather than substituting silently. **Live**: MSFT `dd_aq=n/a (needs 8+ annual periods)` on the current chain (4-period statements) - the branch is correct and unfired rather than dead and fabricating, and it fires automatically once the series is long enough. The n/a text now names the real bar. `earnings_quality.DD_MIN_PERIODS = 8` is that bar, defined once and used by both the function and the caller: the regressor rows are `[cfo_{t-1}, cfo_t, cfo_{t+1}]` for t in 1..n-2, so 6 residual rows need 8 periods - the docstring previously said ">= 6", which a caller could satisfy and still get `None` with no reason.
- **`QUALITY_BANDS`' 50 band was labelled "sector median" while the percentile is taken across the scored peer set.** `industry_neutral_z` demeans the z by sector, but the percentile that produces the 0-100 score stays peer-wide, so the label claimed a reference set the number does not use. Renamed to **"peer median"**, with the source table's label quoted in the comment and the reason it does not apply. A within-sector percentile remains a design item (`design_fundamental_factor_weight_model.md` §3.2), not a silent semantic change here.
- **`scripts/value_screener.py`'s docstring advertised two screens that do not exist.** "Return on Capital (EBIT / invested capital)" and "Shareholder Yield (dividends + buybacks + net debt reduction / market cap)" have no implementing symbol anywhere in the tree (`share_buybacks` and `debt_repayment` are canonical keys with no reader; no invested-capital denominator is built on that path). The docstring now marks both as **not implemented**, names the missing inputs, and points at the design doc's ranked wiring list. The screens themselves are features, not doc defects, and stay unbuilt - the dividend leg alone would print a wrong number under that name.
Tests: `test_statement_parsing.py` **+7** (the moomoo per-year table merge, the cross-payload fiscal-year join, the gap rule, the incomplete-key rule, the two-period floor, the provenance record, and the producer→G-Score integration that proves `var_roa`/`var_sales_growth` compute and no "series unavailable" deviation remains), `test_analysis_tools.py` **+3** (a perfect-fit DD value with its printed basis, the 7-period refusal, and a regression guard that a multi-key cash-flow dict no longer produces any DD number), `test_quant_p4_accounting.py` **+1** (the 8-period bar, mutation-provable), `test_quality_composite.py` re-pointed to the new band label. Engine suite **4385 passed / 5 skipped**.
**Web impact**: text-only, on tool cards the app renders - the earnings-quality leaf's `dd_aq` token gains a basis parenthetical or a named requirement, and the quality-composite band label reads "peer median". No key, CLI flag, JSON shape or prompt changed; the new canonical series keys are internal to the evidence leaves.

**A 106-factor fundamental weight model is designed, not adopted - and the inventory says why (2026-09-17; `docs/design_fundamental_factor_weight_model.md`).** An external weight table (ten categories, 106 factors, "starting production weights") was read against the tree factor by factor before any of it was accepted. The design document maps every factor to its existing implementation, and the map is the finding: **36 of the 106 factors are already computed here (42.15 points of the proposed weight), 26 are partial (20.35), and 44 are absent (41.50)** - and the absences are concentrated exactly where the source puts its weight. Valuation, the largest category at 20%, is the *most* complete (13.25 of 20 already computed); Cash Flow, at 17%, is the largest single hole (11.00 absent); Balance Sheet is 6.75 of 10 absent. Four of the source's own categories do not sum to their stated totals - the per-factor weights add to **104.00%**, not 100% - so the numbers are recorded as hypotheses and the document adopts equal weights plus a named, printed table, per the round-3 rule "no weight vector is invented".
- **What is adopted:** the four sub-score decomposition (quality/growth/valuation/risk) rather than one master number, because the recurring defect this repo fixes is a report *cancelling* two facts against each other ("DCF says \$125, analyst says \$573, so the DCF is an artifact"); an `EffectiveWeight` chain whose every multiplier reads an existing measured surface (`data_quality.aggregate_quality` + `disagreement_flag`, the coverage floor, basis conflicts, one tie-aware percentile) rather than a hand-assigned grade; a derived A/B/C/D confidence table; a `dcf_confidence` score over four legs the DCF family **already prints** (`terminal_share`, `beta_sensitivity`, the basis registry, cycle-FCF dispersion) so a low-confidence DCF loses weight instead of being argued about in prose; and the existing `capex_quality_read` score as the capex direction source, since it already carries the AMZN review's lesson plus the new `defensive_capex_share`/`maintenance_fcf` counterweights.
- **What is refused, with evidence:** shipping unmeasured "production weights" (DeMiguel-Garlappi-Uppal: estimated weights usually lose to `1/N` out of sample; the repo's own rule 2 already forbids inventing a weight vector); walk-forward learned weights as a default (McLean-Pontiff: ~26% out-of-sample and ~58% post-publication decay; ground rule 1's deterministic-auditable requirement); regime-conditional weights (Asness et al., "Contrarian Factor Timing is Deceptively Difficult"); bank/REIT overlays (right in structure, but NIM/CET1/ROTCE/FFO/AFFO/NAV/occupancy are absent from the canonical vocabulary - a data-supplier project, not a scoring change); the literal `1/(1+Σ|Corr|)` redundancy constant (structure yes, untested constant no); and wiring a composite into `opportunity_score` (declared 0-100, deliberately `null` at `execution_contract.py:240-252` "would dress an estimate up as a measurement" - that is an owner decision, not a side effect).
- **The wiring gap beats the missing formulas.** The dominant pattern found is values the engine already computes and never exposes: level ROIC (invested capital is built and used only as a ΔIC denominator), gross margin (stored, consumed by three scores, never rendered), interest coverage (`interest_expense` exists with no reader), working capital, numeric debt/asset growth, receivables/inventory days (booleans inside Beneish), buyback and total shareholder yield (`share_buybacks` exists with no reader), and EV/FCF. Two structural defects are recorded: `roa_series`/`revenue_series` are read by the G-Score's G4/G5 but **no producer populates them** (those legs are dead and always report "series unavailable"), and `industry_neutral_z` demeans by sector while the final percentile is taken across the whole peer set - so `QUALITY_BANDS`' 50 band says "sector median" and does not mean it.
- **Also recorded (found, not fixed - the owner asked for no code changes this pass):** `scripts/value_screener.py`'s docstring advertises "Magic Formula Return on Capital" and "Shareholder Yield" with no implementing symbol anywhere in the tree.
**Web impact**: none - no key, CLI flag, tool, JSON shape or prompt changed; this is a doc. The four-phase plan it proposes is designed, not started, and every phase is default-off behind a new gate under the existing dark-launch protocol.

**The DCF family now says what a price REQUIRES and what capex normalization does, and the net-debt basis is disclosed instead of relabelled an error (2026-09-16; the MSFT fundamentals review).** A reviewer pushed back on the MSFT report's "the DCF is a modeling artifact, not a value signal": every number he quoted checked out against the tree and the FY2026 release, and his diagnosis was sharper than the report's - the model is not *nearly* a current-FCF perpetuity, it **is** one, algebraically. Verified by reproduction: `compute_dcf`'s N-year window projected at `g` and Gordon-discounted at the same `g` telescopes into a single stage, so 66.98bn / 7.567bn shares = 8.85/share, x1.025/0.075 = 120.96, plus the 3.84 net-cash bridge = **124.80** - the printed leaf to the cent. Chasing his point about net-debt terminology then exposed a false claim our own producer was emitting.
- **`y_finance._net_debt_note` no longer declares a vendor error.** It fired whenever cash + ST investments exceeded total debt and told the model the row "is net-CASH ... do not quote it". MSFT's vendor row reconciles exactly on a narrower, standard basis - financial debt excluding capital-lease obligations less cash and equivalents: 31,067 + 9,227 - 20,935 = **19,359** - and the report repeated the note as "the vendor 'Net Debt' row is mis-signed". The note now reconciles the row against four standard bases first and DISCLOSES: the basis that reproduces it, the widest basis (cash + ST investments less total debt including leases = **+19,825m NET CASH**), and one instruction not to call the difference a sign error. Only a row no basis can reproduce (AMAT, WDC) is reported as unreproducible, with no imperative; a row whose sign agrees with the widest basis (AMZN: its net debt excludes operating-lease liabilities) stays silent as before. **Measured over the 20 stored payloads that carry a Net Debt row: the note fired on 8 before and still fires on 8 - but 6 of those 8 (all the MSFT and NVDA trees) were the false vendor-error claim, now disclosures.** Exact-label row reads were added because a substring reader cannot separate `Long Term Debt` from `Long Term Debt And Capital Lease Obligation`, and the wider row is listed first.
- **The canonical `total_debt` bound the long-term leg alone.** moomoo's balance sheet carries "Long Term Debt and Capital Lease Obligation" (47.60bn) and "Short-Term Debt and Capital Lease Obligation" (9.23bn) and NO total row, so the alias scan stopped at the long-term row and the DCF bridge charged 47.60bn against 56.83bn. `_total_debt_match` completes the total from the two legs when no dedicated row exists, which reproduces the vendor's own Total Debt exactly: 47,599 + 9,227 = **56,826**; when a payload does carry `Total Debt` (yfinance) it still wins, so nothing is double counted. The markdown path also re-matches a key in the prior-period table when the label is synthesized, so Piotroski's deleveraging and Beneish's LVGI still get `{current, prior}` (live MSFT: `{56.83bn, 60.59bn}` - the prior matches the vendor's own 60.588bn).
- **The DCF's cash leg now has a named, payload-independent basis.** New canonical `cash_and_investments` (yfinance 76,651m / moomoo 76,650m on MSFT) is preferred over the narrower `cash` row (yfinance 20,935m), and `get_dcf_valuation` prints the bridge it used: `cash= debt= net_debt= bridge=(<cash basis> - <debt basis>) equity=`, so `fair_value = equity / shares` is reproducible from the leaf. Before this the same ticker printed a net-cash bridge of +29.05bn (the printed leaf), +19.83bn (the balance sheet's own total debt) or -35.89bn (yfinance's cash-and-equivalents row) depending on which payload the merge saw - an 8.58/share swing on identical FCF and WACC, invisible to the reader.
- **`beta` is no longer assumed when a configured vendor carries it.** `fetch_ticker` gap-fills beta from Finnhub's basic financials (1.0626 for MSFT) alongside the existing growth/ROE/market-cap gaps; before, the canonical merge had no beta at all in this environment (moomoo's fundamentals payload has no beta row) so every DCF ran `beta=1.00 ... (assumed)`. Live MSFT before/after: WACC 10.00% -> 10.31%, fair value **124.80 -> 118.73** (bridge and beta together, -6.07/share). When beta is still assumed the leaf now prints `beta_sensitivity=(0.8-> .. 0.9-> .. 1.1-> .. 1.2-> ..)`, because that assumption is worth ~5-8% of the fair value per 0.1 of beta.
- **New `get_reverse_dcf(ticker, current_date, growths=?)` - the answer to "the model cannot explain the price".** It inverts the engine's own convention for the market price and reports the steady-state FCF the price implies at each growth rate, plus `implied_growth_for_current_fcf`. Live MSFT (490.30, WACC 10.31%): the price implies **281.3bn** of steady-state FCF at 2.5% perpetual growth, 186.7bn at 5%, 114.3bn at 7% - or **8.35%/yr perpetual growth** on today's 66.98bn. That converts a useless "artifact" verdict into two separate findings: the model's limitation, and what the market is assuming.
- **New `get_normalized_fcf_dcf(ticker, current_date, revenue_growth=?, defensive_capex_share=?, years=?)` - the capex-fade basis, with the maintenance floor in the same leaf.** Revenue-driven: capex intensity fades linearly from today's level toward depreciation (steady state: capex tracks D&A), OCF from a cash margin, Gordon terminal at 2.5%, the shared bridge. `defensive_capex_share` is the honest counterweight - the share of today's excess capex intensity treated as permanently required (1.0 = no normalization). `maintenance_fcf` (OCF - D&A, with reported FCF and growth capex beside it) and a `maintenance_basis_fair_value` are printed for the same ticker. Live MSFT FY2026 (revenue 331.84bn, OCF 182.94bn, capex 115.95bn [moomoo "Net PPE Purchase and Sale", a new `capex` alias], D&A 38.53bn, growth 17.79% provider YoY): **437.55** capex-faded, **217.94** with defensive capex, **252.97** maintenance floor, against the run-rate DCF's **118.73** - the three bases the report should have been arguing between.
- **Both new tools are bound to the fundamentals analyst** (`fundamentals_company_tools`), advertised in its prompt with exact arities, and carry trigger sentences; `DCF PLAUSIBILITY CHECK` now REQUIRES (1) labeling the consensus comparison a basis mismatch - a 12-month price target is not an intrinsic-value estimate and can never override a DCF, and the DCF may not be dismissed as "an artifact"; (2) asking what the price requires via `get_reverse_dcf` and, on a capex-heavy name, `get_normalized_fcf_dcf`, quoting the implied FCF/growth, the capex-faded value and the maintenance floor, and saying which basis is weighted; (3) stating a valuation conclusion (elevated / unresolved) rather than a model verdict, with the DCF leaf's own bridge cited. Two more rules landed with it: `NET-DEBT BASIS` (name the basis; never write that a vendor row is "mis-signed" unless its formula can be shown impossible) and `INSIDER WEIGHTING` (Form 4 flow is a secondary flag - say whether sales look discretionary or compensation-driven before weighting them).
Tests: `test_reverse_dcf.py` **+19**, `test_normalized_fcf.py` **+12** (both new modules - the forward-perpetuity telescoping identity asserted to 1e-9, the fade/floor/defensive ordering, JSON-able leaves, degradation without exceptions), `test_analysis_tools.py` **+6** (the implied-FCF grid and its monotonicity, a percent-style grid, a bad grid, the fade above the run-rate and below the floor, the provider-YoY default, the named missing capex leg), `test_render_honesty.py` **+3** (the bridge reproduces the printed fair value; the narrow-cash fallback names its basis; the beta sensitivity straddles the point value), `test_yfinance_keyless_vendor.py` re-pointed from "the vendor is wrong" to the basis contract. Engine suite **4374 passed / 5 skipped**.
**Web impact**: additive - two new tool names in the fundamentals toolset (the app does not call analyst tools), and existing evidence-line values change on the correct side (`fair_value` for every ticker whose bridge or beta was wrong, `total_debt` where a payload carried only aggregate legs).

**Prompt budget: the market ceiling is set to 50,000, the sentiment verbatim-counts item is pinned, and the budget helper was blind to f-strings (2026-09-16; owner's call).**
- **`MARKET_CEILING` 42_050 -> 50_000**, on the owner's instruction: standing headroom so the next rule additions do not each need a budget decision. The market prompt's measured size is unaffected (41,999, so 8,001 of slack), and the bullet ceiling (95) plus the longest-bullet pin (523) are untouched and still bind - growth cannot hide in a reflow, and the other prompt modules stay bounded by the same constant.
- **The sentiment verbatim-counts item is now pinned.** `test_report_verify.py::test_sentiment_prompt_requires_verbatim_counts` renders the real prompt through `_build_system_message`, locates the item by its **lead** (not its number, so renumbering the list is free) and asserts inside that item alone: the three figures it governs (message counts, upvote/comment totals, computed-block values), the prohibition on rounding or estimating, and the obligation itself ("quoted exactly as given"). Teeth verified by mutation - dropping any one class, the prohibition, the lead or the item's body each fails it, and a regex that matches nothing cannot pass it. The score half of the same class already has a deterministic backstop (`_anchor_claims` rescales and checks `computed_score`); a rounded or half-read **count** has none, which is exactly why the prompt is the whole control here.
- **`prompt_literal_text` was blind to every f-string** (defect fixed on sight). It excluded each `Constant` inside an `ast.JoinedStr` in the name of "counted once", but `ast.walk` already visits an f-string's segments exactly once - the exclusion was a hole, not a dedup. Measured old -> new: news **13,160 -> 15,337**, sentiment **1,406 -> 7,105** (the sentiment system message is one f-string, so that prompt was effectively unmeasured by the ceiling gate), market 41,999 and fundamentals 27,617 unchanged. `test_other_analyst_prompts_stay_bounded` now covers sentiment as well, so all four prompt modules are size-checked.
Tests: `test_report_verify.py` **+1** (199 in that module); the five other prompt gates 30 passed / 1 skipped. Engine suite **4330 passed / 5 skipped** (was 4328).
**Web impact**: none - test and prompt-budget contracts only; no runtime code, key, CLI flag or report shape changed.

**The analyst rule prose is consolidated into named sections, with one new rule per prompt class and one name per rule pipeline-wide (2026-09-16; the MSFT DCF-vs-consensus round).** The three largest prompts had accumulated rule prose in fragments - the same principle stated two or three times under different headers, and two failure modes that no rule covered. Nothing was dropped: every tool name, parameter and historical citation is preserved, verified mechanically - after the whitespace restore below, **all 79 market tool bullets and the whole indicator/tool block are byte-identical to the previous revision**.
- **Fundamentals:** the four scattered basis rules (`SAME METRIC IN TWO BLOCKS`, `RATIO BASIS`, `DUPONT BASIS`, `MARGIN-OF-SAFETY BASIS`) are now one **`BASIS DISCIPLINE`** rule with four numbered sub-cases, so one habit replaces four instructions to satisfy separately; new **`DCF PLAUSIBILITY CHECK`** (before citing a DCF fair value, sanction it against `get_analyst_ratings` consensus and the quality screens - a fair value that collapses to current FCF-per-share ÷ (WACC − g) while a multi-year terminal share is claimed is a low-growth capitalization, not a forecast; the MSFT 2026-09-16 case is the worked example); new **`SIGNAL SYNTHESIS`** (name the conflict, state what was weighted more heavily and why - never average conflicting screens silently, and never let a screen its own sanity check queried carry equal weight).
- **Market:** six rules became **`QUOTE-TYPE & SESSION INTEGRITY`** (close-vs-high labeling, forming-vs-closed bars, confirmed-vs-provisional language, the price/timestamp gate, gap-vs-session, intraday claims vs OHLC - all instances of "don't misstate what kind of price this is or when it was true", with the orphaned DELL example folded back onto its rule), seven became **`CANONICAL VALUE DISCIPLINE`** (one sourced value per metric, body and table agreeing, each former rule a labeled sub-case) and three became **`ATR & STOP MECHANICS`**; new **`INTRINSIC-VALUE PLAUSIBILITY`** (sanction `get_scenario_dcf` against the options-implied read and the trend/regime tools before treating an extreme gap as a directional call) and new **`SIGNAL SYNTHESIS`**, which routes `get_vif_read`-flagged redundant signals away from being restated as independent confirmations and funnels tool-vs-tool pricing disputes into `get_debate_claims_verdict`.
- **News:** `FOMC DIRECTION` + `CATALYST LABEL` → **`FED-EVENT LABELING`**; `MACRO MUSTS` + `10Y FRED ID` + `DAY COUNTS` → **`MACRO DATA PROVENANCE`** (every macro class still pinned to its tool, source by source); index-inclusion + SEC 8-K + insider-10b5-1 → **`EVENT-SIGNAL RESTRAINT`**; `EARNINGS DATE` + `TOOL-STATED CAVEAT` → **`CONFIDENCE & CAVEAT CARRYING`**; three rules → **`CANONICAL VALUE DISCIPLINE`**; new **`PREDICTION-MARKET VS SENTIMENT DIVERGENCE`** (name a sharp divergence between market-implied odds and narrative sentiment rather than quoting whichever supports the framing) and new **`SIGNAL SYNTHESIS`** (catalyst scale vs macro regime vs credit band vs sentiment - say which was weighted).
- **One name per rule.** The sentiment analyst's macro pin carried `MACRO MUSTS (10-year)` for the same macro-leaf rule the news analyst now calls `MACRO DATA PROVENANCE`; it is renamed to match, and `tests/test_news_analyst_prompt.py` now asserts the two modules agree, so one rename cannot land without the other. The `_macro_authority_gate` docstring (the gate that enforces these pins against tool leaves) names the current header.
- **Sentiment (same pass):** the source-conflict instruction now requires naming **which source was weighted** when the reads disagree, `overall_band: Mixed` must name the sources in conflict (a finding to explain, not a way to avoid resolving it), a new item 9 requires counts and quotes copied **verbatim** from the blocks, and `overall_score` states its fallback when no computed block is present.
- **Whitespace.** The market prompt's indicator/tool block had been re-indented four spaces into its triple-quoted string - 456 chars of padding that broke the longest-bullet pin for a whitespace-only reason (`527` vs the recorded `523`); it is flush-left again, so the longest bullet is back to 523 and the block's interior is byte-identical to the previous revision. A fragment boundary in the news macro section was merged so `MUST come from <tool>` stays greppable per macro class - that pin is the AMZN 2026-09-09 uncited-10Y guard.
- **Prompt budget.** The market prompt measures **41,999** chars (the new rules' prose), over the 40,300 ceiling, so `test_prompt_budget_contract.MARKET_CEILING` is raised to **42,050** with the measured reason and a 51-char slack in the same comment; the other two prompts stay under it (fundamentals 27,617 / news 13,160 - the news figure came from a helper that dropped f-string text and is corrected to 15,337 in the entry above, which also raises this ceiling to 50,000 the same day). Bullet count 79/95, unchanged.
Tests: `test_analyst_evidence_wiring.py` re-pointed to `BASIS DISCIPLINE` / `SAME METRIC, TWO BLOCKS` (its other three pins - `basis unstated`, `IMPLIED SHARE COUNT`, `10.79B vs 10.88B` - were already satisfied); `test_news_analyst_prompt.py` re-pointed to `MACRO DATA PROVENANCE` **+1** (the cross-analyst header-drift test); `test_report_verify.py` and `test_structured_agents.py` re-pointed to the renamed sentiment pin; `test_prompt_budget_contract.py` ceiling raised as above. Engine suite **4324 passed / 5 skipped**; verified end to end by rendering all four system messages and asserting every new section header reaches the model.
**Web impact**: none - prompt text only; no key, CLI flag or JSON shape changed, and the app never reads an analyst prompt.

**The buy-and-hold cost bleed in `get_strategy_quality`, a verifier-scale information ratio, and three IEI report defects (2026-09-16; `reports/IEI_20260916_175246` re-verification).** The latest IEI tree was re-verified stem-by-stem against `tool_evidence.json`, adjudicating every non-GROUNDED claim instead of counting them: three report-text defects, one mis-attributed tool citation, and two producer defects the report itself had flagged as "not reconcilable".
- **`get_strategy_quality` charged 10 bp to every one of the 319 daily returns of a price-derived series.** The cost is per TRADE, and a price-derived series is buy-and-hold: one entry, one exit. The per-day bleed fabricated net_cagr **-21.10%**, sharpe -7.01 and a 26.15% "backtest" drawdown for IEI from a price path whose raw CAGR is +1.53% with a 3.32% max drawdown - and the report spent a paragraph telling the reader to ignore it. The round trip is now charged once (one way on the entry period, one way on the exit); an explicit strategy series keeps the per-period convention (`signal_analysis` rebalances per period and its tests pin it). Same IEI series after the fix: net_cagr **+1.37%**, sharpe 0.45, max_dd 3.42%.
- **`tracking_error` reported floating-point noise as a tracking error.** A constant difference series - perfect tracking, or the flat cost offset above - leaves ~1e-18 residuals whose std annualizes to a TE ~7e-18, and `information_ratio` then divided into **-2.9e17**, which reached the analyst's evidence as `info_ratio=-293012267876759360.00`. A spread within float precision of the values themselves is now 0.0 (so the ratio is `unavailable`); a genuinely divergent series still measures.
- **`run_card.json` now records which evidence mode built the tree.** The deterministic gather freezes each analyst's first render under `_rendered_block`; the legacy LLM-selected path never writes that key, and a tree built that way carries no prompt-level identity / reference-price line, so its venue / mandate claims cannot be re-verified post-hoc. That mode was reachable by accident - an empty `analyst_forced_tools` (e.g. the `" "` value the test suite exports) silently disables the gather for a whole batch - and was inferable only from a missing reserved key: the three trees regenerated the same evening (MSFT/VTV/IEI `20260916_174952/175407/175246`) were all built that way. The card gains `evidence: {mode, forced_tools, analysts, rendered_blocks}`, and the block can never cost the card.
- **Report-text corrections in the latest IEI tree** (local artifacts: `reports/` is gitignored, so these are not commits). The summary table's "6th straight lower close" contradicted the body's "Eighth" *and* the verified close series (09-04 115.66 → 09-16 114.22 is the eighth); the multicollinearity bullet attributed StochRSI and %b to `get_vif_read`, whose factors are rsi 9.6 / mom 3.6 / vol 3.1 / zscore 6.9 / range 2.8 (the conclusion - one oversold signal counted three times, not three confirmations - stands); and `fundamentals.md` plus its `complete_report.md` section split the QQQ relative-strength row across a line break ("+1.79%, +1" then ".79%, +1.49%"), which reads as five values for four windows - repaired to the leaf's four. The strategy-quality paragraph now records that the print was a tool defect and names the corrected values.
Tests: `test_analysis_tools.py` +1 (a flat 300-close path must not report a double-digit negative net CAGR from transaction costs - it was -22.3%), `test_strategies_evaluate.py` +1 (a constant-offset series is zero TE with no information ratio - it was 7.4e-18 and a huge IR), `test_reporting.py` +3 (the mode classifier over a forced and a legacy state, a hostile state cannot cost the card, and the block reaches a real card). Engine suite **4314 passed / 5 skipped**; web **149 passed**.
**Web impact**: additive - `run_card.json` gains one `evidence` object (the app and the executor's `watch.py` read `research_decision.json`, not the card), and two evidence-line values change on the correct side (`net_cagr`, `info_ratio`) inside existing per-analyst leaves.

**Report degeneracy is caught before it ships, and the day's verifier false positives are gone (2026-09-16; the four-symbol batch, `reports/{AMZN,MSFT,IEI,VTV}_20260916_*`).** Verifying the batch (16 stems) produced real defects *and*, on adjudication, five verifier bugs the same run had created. Everything confirmed was fixed in the same task under working-agreement rule 10 - added to `docs/AGENT_ONBOARDING.md` §0 with this round as its first application (a confirmed defect is fixed on sight; ask only when a fix is destructive to user data or rewrites a decision contract the owner set).
- **A cascade or a self-halted generation is no longer shipped as a report.** `structured.py` gains `_looks_like_degenerate_loop` (the longest run of an immediately repeated 3/4/5-word block, **or** a non-trivial line repeated 4+ times) and `_looks_like_generation_self_halt` (the vocabulary of a generation narrating its own failure), behind one `_degenerate_body_kind` classifier used by all three guard sites: the analyst chain (`retry_chain_if_stub`), the cap-forced terminal turn (`finalize_messages`) and the free-text decision path (`_retry_if_monologue`). MSFT news.md had shipped "speaking broadly overall generally" x20 then `[HARD STOP]`; VTV news.md shipped every figure spelled out in words then "(Report truncated here deliberately ... reproducing known degeneration patterns)". Both were non-empty, so emptiness, shortness, end-char, monologue-vocabulary and *line-level* repetition guards all passed them. Thresholds are measured, not guessed: over the 493 markdown files under `reports/` the longest adjacent 3/4/5-word repeat is 2 in every clean file and 5+ in every degenerate one; over the 502 agent stems the longest repeat of one non-trivial line is 2 clean vs 12+ degenerate; the self-halt vocabulary matches exactly this batch's 5 artifact files and no clean one.
- **Leaked tool-call markup is stripped from analyst reports.** `risk_tool_loop._final_prose` guarded the risk/trader path only, so VTV sentiment.md shipped `</invoke>`/`</parameter>`. `retry_chain_if_stub` (the last call in every analyst node) and `finalize_messages` now strip with the shared `tool_call_markup` vocabulary, log + journal the strip, and let a markup-only report degrade to the explicit unavailable notice instead of a transcript. Live the same hour: the re-runs logged 40+ strips.
- **The statement payloads state their scale.** `y_finance.get_balance_sheet` / `get_cashflow` / `get_income_statement` print absolute vendor integers with no units line, so MSFT 2026-09-16 quoted FCF/capex/operating-cash-flow/deferred-tax/revenue as "N x10^6" - a 10x mis-scale on five rows, invented (`no leaf prints an x10^6 header`). Each header now carries `# Values are raw vendor figures (unscaled): absolute units, so 19639000000.0 = $19.639bn (NOT 196,390 x10^6).`, matching what `get_financial_trends` already said. `get_fundamentals` also gains an **Exchange** line, so a report naming its venue quotes a leaf instead of the prompt.
- **The resolved instrument identity is evidence in every stem.** `build_instrument_context` puts "Resolved identity: Company: X; Exchange: Y" into every analyst's system message; `evidence_gather` now prepends it to the evidence block beside the reference price, and the verifier digest lists it as `instrument_identity [ok]`. IEI 2026-09-16 and VTV 2026-09-16 both had a true venue ("exchange NGM", "on PCX") flagged as fabrication because the fact lived in the prompt and no leaf carried it - the same drift the reference-price line closed on 2026-09-15.
- **One report-hygiene rule for every analyst.** The self-correction ban (`corrected:` / `correction -` caveats) existed only in the news prompt, the restart ban in three, and neither in sentiment - so VTV market.md shipped "Corrected positioning bullet:" plus four loop-error notes from a prompt that forbade only the restart form. Both clauses now live in `agents/utils/report_hygiene.py::REPORT_HYGIENE_RULES`, appended by all four analyst nodes, with `tests/test_report_hygiene.py` gating the wiring (one convention; the per-analyst variants are gone).
- **Verifier: digit placeholders are reported as the defect they are.** IEI market.md carried 146 masked digits (`rsi=23._15` for the leaf's 23.15, `pct_b=_0219`, `GARCH cond **_._**04%` for 3.04%) and VTV sentiment.md a dot/ellipsis variant (`+0..85`, `≈9..25/10`, `-026-09-15`). The extractors read the surviving fragments ("23" out of "23._15", "91" out of "_._91", "04" out of "_.04%") and invented three INTERNAL_CONFLICT rows - now a line whose digits are masked yields no quotable value, and one `digit_obfuscation` claim names the corruption (ISO date ranges such as `2026-09-07..2026-09-14` are excluded, and tool names like `close_50_sma` are not matches).
- **Verifier: the 0-10 sentiment score is anchored in code.** The sentiment prompt mandates `5 + 5 * computed_score` +/-0.5; the LLM verifier applied that inconsistently in this run (AMZN's 9.5/10 and IEI's ~0/10 flagged UNSUPPORTED while MSFT's and VTV's were accepted), contradicting its own documented precedent. `_anchor_claims` now grounds a score claim whose stated figures sit inside the band around the anchor read from the stem's `computed_score` leaf, and the instructions state the rule.
- **Verifier: two EPS estimates are only comparable within one earnings date.** AMZN news.md quotes 1.83 for the already-reported 2026-07-30 print beside 2.03 (Zacks, upcoming) and 1.95 (calendar, 2026-10-29) - three estimates, two dates, each labelled; the label-keyed same-metric pass paired 1.83 with 2.03. The generic `eps estimate` metric is removed; the date-scoped `_eps_estimate_duals` (same date, two values) owns the metric and is unchanged.
- **Verifier: a 200-SMA distance that prints identically twice is not a conflict.** AMZN market.md states +2.44% and 2.4%; both render "+2.4%" and the claim read "+2.4% / +2.4%". The comparison now runs at the precision the claim prints.
- **Artifacts.** The masked/cascaded trees were regenerated (`reports/{IEI,MSFT,VTV}_20260916_{175246,174952,175407}` - all 12 stems clean on every defect class, verified) and the localized defects in the four original trees were corrected leaf-by-leaf (AMZN news' spliced sentiment-series peak, AMZN sentiment's unsupported "tape skews distinctly negative", MSFT sentiment's transposed 37.5%/62.5% labeled share, IEI fundamentals' fabricated venue attribution, MSFT fundamentals' "sits between 50-day and 200-day" when the price is above both, MSFT news' "41 shares valued about twenty million dollars" for 41,674 shares / $20,764,845, VTV fundamentals' misattributed wrapper line + distribution window + malformed rows, and the two stems whose tails had degenerated into a repeated line, truncated with an explicit marker). The original trees are kept as evidence of the classes.
Tests: `test_degenerate_report_guard.py` new (9: cascade, repeated line, self-halt, per-kind classification, cascade/self-halt repair on the analyst chain, markup strip + markup-only degradation, cap-turn repair, cap-turn degradation), `test_report_hygiene.py` new (3: both clauses present, all four analyst modules wired to the one constant with no per-analyst variant left, the built sentiment message carries it), `test_report_verify.py` +4 (identical 200-SMA values, masked digits + no value from a masked line, the sentiment band in three directions, cross-date EPS estimates replacing the generic pin), `test_evidence_gather.py` +1 (the identity line is prepended; a ticker-only context adds none), `test_quantitative_scores.py` +3 (Tobin's Q unit), `test_tool_round_cap.py` (the padded-repetition fixture is now a realistic truncated report, since the padding is itself a degenerate body). Engine suite **4309 passed / 5 skipped**; web **149 passed**.
**Web impact**: none - no key, CLI flag or JSON shape changed. `verify_flags.json` gains one possible claim (`digit_obfuscation`) and one digest row (`instrument_identity`), both inside existing per-stem arrays; `trading_web`'s `_run_report_verify` counts `overall == "FLAG"` and never switches on claim text.

**Tobin's Q lands in the value screens; precedent transactions are documented as out of reach (2026-09-16; a valuation-method coverage scan).** The classic multiples were already computed here (EV/EBITDA, EV/EBIT, EV/Sales, P/E, P/B, P/S, P/CF, P/FCF, dividend yield) and the Graham/NCAV/EPV floors shipped with the value-dip work, but the firm-level market-vs-book read and the deal-comps pair were absent.
- **`tobins_q`** (`dataflows/quantitative_scores.py`): `Q = (market_cap + total_liabilities) / total_assets` — the market value of the firm's assets over their book value, which stands in for replacement cost. The canonical has no market price for the debt and no appraisal of the asset base, so the legs are stated rather than implied: equity at market, liabilities and assets at book. Returns `{value, basis, classification}`; `None` when any leg is missing, when the market cap is non-positive or total assets are non-positive. A missing `total_liabilities` is `None`, never the equity-only ratio: dropping the liabilities leg would silently print the P/B reading (0.5 instead of 0.75 on the unit fixture) as a cheap firm-level multiple.
- **Wired end to end.** `screen_ticker` carries `tobins_q` + `tobins_q_classification` behind the same USD-consistency gate as the EV family — Q mixes a USD market cap with a JPY balance sheet exactly as EV does, so a foreign-statement ADR must not print a 0.10x "cheap" multiple (live JPPHY: `currency=non_usd` -> n/a). `get_analyst_verdict` prints the line after EV/EBIT, and its basis line now names `total_liabilities` among the screen inputs. The watchlist renders a `TobinQ` column beside EV. It is an **informational row only** — no score, ranking or filter reads it, the same contract GP/A and NOA shipped under.
- **Live smoke** (`fetch_ticker` + `screen_ticker`, 2026-09-16): AAPL **14.255** (4.836e12 + 2.855e11 over 3.592e11), MSFT **5.309**, AMZN **3.782** — each matches the canonical legs recomputed by hand; VTV (a fund, no balance-sheet legs) and JPPHY (currency mix) both degrade to n/a rather than to a number.
- **Not implemented, deliberately: precedent transactions.** A transaction comp set needs deal value, target earnings/assets and deal date from a deal database; no free source carries one and this repo does not scrape. The nearest existing read is `acquirers_multiple` (EV/EBIT) — the multiple acquirers pay, but not a comp set. No stub tool is shipped: a tool whose only answer is "unavailable" is weight, and `docs/design_institutional_value_dip_workflow.md` §4 now names what the valuation row actually covers.
- **Peer comps stay partial by design**: `get_company_peers` (Finnhub peer tickers) plus the cross-sectional percentile ranks in `strategies/factors.py` give peer *standing*; there is still no peer-multiple table, so no "cheap vs peers" claim can be evidenced from a comp set.
Tests: `test_quantitative_scores.py` +3 (the liabilities leg is priced at book and the equity-only reading is rejected; a missing liabilities line yields `None`; non-positive cap or asset base yields `None`), `test_quality_factors.py` +1 (the screen row carries the value and its classification), `test_value_screener.py` (the currency gate now also asserts `tobins_q is None`), `test_analysis_tools.py` +1 (the verdict prints the row's Q). Engine suite **4292 passed / 5 skipped**.
**Web impact**: additive — the verdict text gains one line and the watchlist one column; no key, CLI flag or JSON shape changed.

**Statement bases are labelled from the payload, not asserted - and the merge records an annual/quarterly conflict (2026-09-16; the AMZN 2026-09-14 statement-basis drift).** `statement_parsing.fetch_ticker` asked both statement vendors for `annual` and stamped a flat `annual` on whatever came back, so FY-annual rows could be merged with TTM quarters (AMZN: EV/EBIT 32.79 -> -30551.06) with nothing in the record showing the disagreement. Each provenance entry now carries the payload's own period kind beside the requested basis: `{source, basis, period, observed_kind, basis_conflict}`. `observed_kind` is `annual`/`quarterly`/`ttm`/`unstated`, classified from the period token the payload actually prints (`2025/FY`, `### Income Statement (2026/Q2)`, `TTM ...`), and `basis_conflict` is True only when an explicit label contradicts the request. A bare date header (yfinance's column layout) states no kind, so it stays `unstated` and is never a conflict - diffing period tokens blindly would flag intraday movement as loudly as a mislabelled statement. A conflict is logged at WARNING and named on the verdict tool's basis line, which until now could not print at all: `analysis_tools._screen_basis_line` called `re.sub` with no module-level `re` import, so **any non-empty provenance raised `NameError`** - the basis line every value verdict opens with was dead code (verified live: AAPL 2026-09-12 now prints `basis: cash/total_assets/total_debt/total_equity 2025/FY (FY 2025, currency: USD) (get_balance_sheet); ...`). Supersedes the three-key record the 2026-09-12 D1 entry below describes.
Tests: `test_statement_parsing.py` +14 (an AMZN-shaped quarterly payload under an annual request flags its income keys while the annual balance keys stay clean; a kindless date header never flags; `_period_kind` over 11 vendor labels; the conflict truth table, including that the fundamentals pull's `info` basis can never conflict) and `test_analysis_tools.py` +2 (the basis line names a conflicted key; no marker when the bases agree). Engine suite 4287 passed / 5 skipped. Live smoke: `fetch_ticker` for AAPL/AMZN/LULU/LRCX/MSFT records `observed_kind=annual` with zero conflicts on today's chain - the honest label is in place, and the conflict path did not reproduce against the live vendors today.
**Web impact**: none - no key, CLI flag or JSON shape changed; the verdict tool's basis line is text and only grows when a conflict is detected (verified: no web test or contract pins that line).

**The verification payload gains a typed basis registry, and a verdict that says what actually ran (2026-09-16; a 4-symbol deep batch, `reports/{IEI,IBM,MSFT,AMZN}_20260916_*`).** Two gaps the batch exposed.
- **The registry.** Each stem in `verify_flags.json` now carries the typed triples the deterministic layer had already extracted: `basis: [{metric, value, basis, source}]`. `basis` is the period token the report itself prints beside the value (`ttm:ttm`, `date:2026-06-30`, `period:annualized`) or, when it states none, the metric's unit class (`level`/`percent`/`multiple`/`ratio`) — deliberately not a fraction-vs-percent dichotomy, because a ratio above 1 is ordinary here (P/E 135.94). `source` is `evidence` when the value resolves to a tool leaf within the metric's tolerance, else `report`. The point is comparability: two runs of one ticker can be diffed mechanically, because a basis change leaves no prose trace to diff — the same `(AMZN, 2026-09-14)` calls resolved FY-annual flows at 22:5xZ and TTM quarters at 19:08Z (EV/EBIT 32.79 -> -30551.06), and one metric is quoted at two values across runs (LULU `ev/ebit` 5.50 vs 4.40, MSFT `rvol` 0.30 vs 0.4220, LRCX diluted EPS 1.81 vs 5.76). Measured on the trees themselves: 25 triples in MSFT fundamentals, 23 in market, 1 in news.
- **`NUMERIC_ONLY`.** A stem whose LLM half failed (provider error, unparsed verdict) but whose figures WERE extracted and found consistent no longer reports the uninformative `UNKNOWN`: it reports `NUMERIC_ONLY`, and `UNKNOWN` is reserved for a stem with nothing to check. On the batch's MSFT tree re-verified with the provider stubbed out: fundamentals/market FLAG (3/1 claims), news `NUMERIC_ONLY` (1 triple), sentiment `UNKNOWN` (0 triples). `scripts/report_verify.py`'s exit code is unchanged — 0 for PASS/NUMERIC_ONLY/UNKNOWN, 1 for FLAG — because a `NUMERIC_ONLY` stem carries no flag by construction.
- A first cross-run experiment on the only same-day pairs in `reports/` (NVDA and NFLX, 2026-09-15) shows why the *comparison policy* is a separate step: a naive value diff flags intraday movement (`atr` 2.2293 -> 2.3115, `rsi` 50.15 -> 49.33) just as loudly as the fundamentals that moved within one day (`dcf fair value` 25.92 -> 34.59). The registry ships; the discriminator (which classes may move intraday, which may not) does not.
Tests: `test_report_verify.py` +10 — `_basis_of` prefers a stated period and falls back to the unit class; the registry dedupes identical triples and marks a value no leaf carries `report`; two labelled quarters stay two bases; `_stem_overall` is pinned in three directions (NUMERIC_ONLY when the figures were checked, UNKNOWN when not, FLAG on a deterministic claim); the real payload carries the triples. The provider-failure test was updated to the refined contract (NUMERIC_ONLY with figures, UNKNOWN without), and the module + CLI docstrings now state it.
**Web impact**: additive — `verify_flags.json` gains a per-stem `basis` array and one new `overall` value. `trading_web/backend/capabilities.py::_run_report_verify` counts `overall == "FLAG"`, so `verify_flags_count` is unchanged by a `NUMERIC_ONLY` stem, and the app never switches on the verdict vocabulary; its docstring claim that a provider failure "degrades to an UNKNOWN entry" was corrected in the same pass.

**OpenRouter large-prompt request shaping,### Added

**Webull OpenAPI provider study (design only, 2026-09-16; `docs/design_webull_data_provider.md`).** A direct-source read of Webull's Market Data API (HTTP Data API + MQTT streaming) mapped onto the existing `data_vendors` categories, with a phased implementation plan and the constraints that decide it. No code, no chain, no preset - chains are unchanged by construction.
- **Why it is worth considering:** its income/cashflow/balance rows are natively basis-tagged (`fiscal_year`, `fiscal_period` 0=FY/1..4=Q, `end_date`, `publish_date`), which is the upstream half of the 2026-09-14 statement-basis drift (AMZN FY-annual at 22:5xZ vs TTM quarters at 19:08Z) and the counterpart of the report-side `basis` registry added earlier today. `publish_date` also gives point-in-time selection instead of run-date guessing. 300 req/min and 20 symbols per bars call is more headroom than the chains currently have (the batch worker cap of 4 exists for moomoo limits).
- **The three constraints:** US-only categories (`US_STOCK`/`US_ETF` - non-US symbols must raise a typed `NoMarketDataError` and fall through, exactly like `moomoo.py`); real-time requires a separately-purchased Nasdaq Basic/Totalview **non-display** subscription (app/QT subscriptions do not count, and only one device may use L1/L2 at a time); production tokens go `INVALID` after 15 consecutive idle days, with a 5-minute in-app SMS verification window - sandbox tokens need no 2FA, which is the sane default for tests.
- **Not a replacement for anything:** its news endpoint is an LLM-generated SSE summary over a watchlist (not a headline feed, and circular inside an LLM pipeline); the Display Solution families are the wrong product for non-display analytics; options have no chain summary or greeks; EODHD and moomoo keep their roles. Recommended scope is P0-P3 (auth + bars + fundamentals + ratings/calendar/capital-flow), with streaming and NOII/footprint as separate later decisions.
- The go/no-go experiment is stated first: the docs imply non-display usage needs the Nasdaq entitlement while the sandbox is documented as 15-minute delayed by default - one sandbox bars call answers whether the integration is viable before any code is written.
**Web impact**: none - no key, CLI flag or JSON shape changed; this is a doc.

**OpenRouter large-prompt request shaping,### Added

**OpenRouter large-prompt request shaping, and the prefix-cache defect under it (2026-09-14; plan `docs/implementation_plan_openrouter_large_prompt_ttft.md`).** A 40-60k-token prompt spends a long time in prefill with nothing on the wire, which is what the one recorded provider timeout looks like from here (`FailureLog/llm_failure_20260914_161016_16527.json`: `structured/Trader`,
`code 504`, `metadata.error_type="timeout"` — OpenRouter's typed "the provider did not respond within the allowed time"). Auditing the cache path first turned up the real defect: **the analyst system message was rebuilt on every tool round**, so the prompt prefix moved at token 0 and an implicit prefix cache (OpenRouter/DeepSeek) was dead for the whole tool loop. `evidence_gather.gather_for_analyst_node` renders the forced-evidence block into `messages[0]`; a re-entry re-rendered it from state that had since grown (the tool node journals a leaf for every tool the model calls itself) and dropped the first render's S11b "declared-default tools moved" notes. It now freezes the first render under the reserved `_rendered_block` key and re-serves those exact bytes on every later entry — the leaves stay in `tool_evidence` for the verifier and reports (they are in the transcript as tool messages anyway), and the reserved rows are list-shaped rows without a `tool` key, so `reporting._evidence_sources` and `repro_check --evidence` (which skips `_`-prefixed keys) are unaffected. **Measured live, same client, same prompt:** turn 1 `cache_read: 0 / 6043` input tokens, turn 2 `cache_read: 5888 / 6043` (~97%) — the cache hits now, at DeepSeek's 0.1x cache-read rate.
Alongside it, three request-shaping knobs on the OpenRouter client (all opt-in, all default-off so an unconfigured body is byte-identical): `TRADINGAGENTS_OPENROUTER_STREAMING` (stream responses — langchain aggregates chunks, so `invoke()`/tool loops are unchanged, and a streamed `invoke()` still reports `usage_metadata`, verified live; the deprecated `stream_options.include_usage` is never sent), `TRADINGAGENTS_OPENROUTER_SESSION_ID` (`auto` = one sticky-routing id per client, i.e. per symbol run — OpenRouter pins the session to the host holding the warmed cache; a literal pins a named session, max 256 chars), and the `provider` object's `sort` / `preferred_max_latency` / `preferred_min_throughput` / `require_parameters` / `allow_fallbacks`. **`provider.order` is never sent** — OpenRouter disables sticky routing when a manual order is set, which would cancel the session. Telemetry: the CLI footer now appends `(cache N)` when the provider reports cache reads, and `StatsCallbackHandler` sums `input_token_details` cache reads/writes including the service-tier-prefixed keys (`priority_cache_read` / `flex_cache_read`) that langchain emits for priority/flex routes; the failure journal now records typed provider fields (`error_type`, `error_code`, `status_code`, `provider_code`), token/cache counters and `provider`/`session_id`, so a 504 is distinguishable from a parse failure without reading the message text. `strategies/llm_cost.estimate_cost` takes `cached_input_tokens` and prices them at the model's cache-read share (0.1x for DeepSeek; unknown model -> full input rate, an over-estimate by design).
Also in `.env`: the slow-host blocklist is populated (13 slugs, verified against the live provider list on 2026-09-14 — `openinference` from the old `.env.example` line no longer exists), with `STREAMING=true` and `SESSION_ID=auto`; `PROVIDER_SORT` is deliberately left empty because sorting by throughput/latency disables OpenRouter's price-based balancing and can route the same model to pricier hosts.
Tests: `test_llm_client_timeout.py` +8 (defaults untouched / streaming+session / stability per client / explicit id + 256-char bound / provider-object merge / fallbacks only when disabled / bad sort and bad latency raise / native providers untouched), `test_evidence_gather.py` +2 (re-entry byte-identical after a journaled leaf; reserved rows invisible to the evidence walkers) — the re-entry test fails against the previous code (verified: the old re-render differs and leaks the new leaf). `scripts/repro_check.py::_config_hash` now folds in every request-body key (the new ones plus `openrouter_ignore_providers`, which was missing), so two runs that differ only in routing are no longer reported as provably same-input.
**Web impact**: none structurally — no key, CLI flag or JSON shape changed. The footer string gains an optional `(cache N)` suffix, and `tool_evidence.json` gains one `_rendered_block` key (already skipped by `repro_check --evidence` and by the report walkers).

**End-to-end A/B on SKHY, same day, same command** (`batch.py --symbols SKHY --depth shallow`): before this change the symbol died with `code 504 / error_type=timeout` (and all six symbols of that afternoon's two batches failed the same way); after it the run completed with a full report tree, `decision.verdict=PASS`, `debate.degraded=false`, and **zero entries in the failure journal during the whole 1785 s run**. The after run's `tool_evidence.json` carries the new `_rendered_block` rows (market/news/fundamentals) — i.e. the freeze is live in production, and the frozen prefix each analyst re-serves is 34-59 kB. Wall time is dominated by the deterministic gather (87 tools, `max_parallel=1`), not prefill: it is a timeout fix, not a speed fix.

Two follow-up experiments closed the same day (numbers in the plan's §9; raw rows in the gitignored `reports/experiments_20260914/`). **(1)** `openrouter_reasoning_effort` does **not** move time-to-first-response: first-chunk medians 0.89 s (high) / 1.09 s (low) / 1.91 s (medium) at 13.5k input tokens, and a 53.7k-token prompt at `high` still produced its first delta in 1.8-4.3 s — prefill is not what makes the connection silent, and hidden reasoning (79-92% of output at every effort) is what moves time-to-first-**content**. The knob keeps its documented output-budget rationale, not a timeout one; nothing argues for changing `.env`'s `high`. **(2)** A recall-preserving digest of the analyst reports for the five debate-stage prompts (bull/bear + 3 risk debators — the terminal stages only take `investment_plan` + computed context, correcting the plan's wording) cut prompt input tokens 45% (8,204 → 4,530 median) on a paired 16-item harness with **no** fabrication penalty (fabricated figures 21 → 10; worse in 3 pairs, better in 9) but **29% fewer** distinct figures cited. Viable, not free, and not needed for the timeout fix: not shipped, and explicitly deprioritised behind the analyst-side prefix (W5 items 1-3).

**Fundamentals basis disclosure, a period-aware conflict scan, and the verdict tool's missing basis (2026-09-14; an AMZN review of `reports/AMZN_20260914_192119/1_analysts/fundamentals.md`).** The review found the report quoting ROE at 30.56% (feed) / 22.10% (DuPont) / 22.09% (ratios) / 18.89% (verdict) and EV/EBIT at 35.02 (verdict) vs 32.79 (ratios) side by side with no reconciliation, plus a market cap against an EPS whose implied share counts differ by ~1% (10.79B vs 10.88B) unstated. Root cause on the report side: `get_analyst_verdict` — unlike `get_ratios` and `get_dupont_read` — printed **no basis**, so the analyst had no period to quote for its screens; it now prints one line built from `fetch_ticker(..., with_provenance=True)` naming the period and source behind every value-screen input (e.g. `basis: net_income/operating_income/revenue 2025/FY (get_income_statement); market_cap vendor TTM/annual (finnhub basic financials)`). The fundamentals prompt gains two rules, both citing this run: **SAME METRIC IN TWO BLOCKS** (quote both values with the block that produced each and state the basis difference; a block printing no basis is quoted as `basis unstated` — never present one as *the* value) and **IMPLIED SHARE COUNT** (market cap / price vs net income / EPS must agree; when they do not, state both implied counts and the gap).

Detection side: the same-metric scan in `report_verifier` flagged the ROE and EV/EBIT pairs correctly but also cried wolf on **disclosed** basis differences (AMZN's diluted EPS 2.78 for 2026-03-31 beside 5.75 for 2026-06-30 — two labelled quarters), so it now exempts a metric only when every value cluster carries its own period/basis tag and no two clusters share a tag. Measured over all 277 archived analyst reports: 137 flags -> 131 (files with findings unchanged at 70), the six suppressed rows all values that carry their own period/expiry label, with the AMZN ROE/EV-EBIT flags retained. Also de-flaked the envelope fixture in `tests/test_report_verify.py`: a hard-coded `effective=2026-09-12` against a wall-clock `produced_at` made all four envelope tests fail from 2026-09-15T00:00Z (`invalid_timestamp`, then `expired`) with no product change. Tests: `test_report_verify.py` +2, `test_analyst_evidence_wiring.py` +1. Web impact: none (a tool's text gains a basis line; no key, flag or JSON shape changed).

**Not fixed, and worth its own investigation — the same (ticker, date) resolved a different statement basis three hours later.** Re-running the same tool calls with the same arguments on AMZN 2026-09-14 at 22:5xZ returned FY2025-annual flows where the 19:08Z run had TTM-quarter flows ending 2026-03-31, moving ratios ROE 22.09% -> 18.90%, P/E 30.12 -> 35.41, current ratio 3.12 -> 1.05, EV/EBIT 32.79 -> -30551.06 (near-zero-EBIT artifact) and FCF -2,472,000,000 -> n/a, plus the verdict's EY 2.86% -> -0.00% (ARTIFACT). That is the data layer, not the prose: `fetch_ticker` merges up to four vendor payloads last-writer-wins, so which vendor answers decides the period. The new basis line makes the drift visible on every future run; making a run's basis *stable* (or refusing a silent basis switch) is not addressed here.

### Fixed

**The prompt round's own smoke run flagged two correct MSFT sentences; both were deterministic-reader bugs (2026-09-16; `reports/MSFT_20260916_231406`).** The live smoke after the rule consolidation (1 symbol, shallow, forced evidence mode) produced two INTERNAL_CONFLICT rows - and both were the deterministic half misreading prose that is correct.
- **The chandelier stop reader walked into the next metric's assignment.** `_chandelier_identity`'s "=" pattern (`chandelier[^=\n]*=`) crossed the "3x ATR below the 22-bar high" parenthetical and grabbed the assignment that followed it, so `... chandelier 485.9179 (3x ATR below the 22-bar high), 1R=4.3821` read the 1R as a second chandelier stop, and `chandelier 486.7536 (= 3x10.3422 below the 22-bar anchor high 517.78)` read the ATR multiple's `3` as one (MSFT 13:04). The reader now: takes an optional "stop" between label and value (so `chandelier stop 486.3121` - invisible to the old space form, which demanded a digit straight after the word - is read again), rejects an "=" gap that ends in another label's token (a label beside a figure carries a digit: `1R`, `t1`, `t2`; prose does not: `high`, `stop`), and rejects a value followed by an `x`/`×`/`ATR` operator in both forms. **Measured over all 37 stored market stems:** the checker's flag set goes 2 -> 0 (both flags were the bogus grabs), two real stops that were previously *unreadable* come back (486.3121 on MSFT 09-15 14:02, which the wrong grab had replaced with a `t1` value; 234.4857 on SIMO), no other stem's value set changes, and the four existing chandelier fixtures behave exactly as before.
- **The net-debt identity read a vendor row the report quotes in order to correct it.** MSFT 2026-09-16 fundamentals.md wrote 'the vendor "Net Debt 19,359,000,000" row is mis-signed and I do not quote it as debt' beside its own **+19,825,000,000 net cash**, and `_net_debt_identity` took the quoted row as the report's net figure and flagged it against the balance-sheet legs (19.83 vs 19.36). A quoted net row whose line names it as wrong (`mis-signed` / `wrong sign` / `not quoted` / `do not use` / `unreliable` / `mislabel` / `stale`) is now ineligible as the report's own figure. **Measured over the 37 fundamentals stems:** 2 bogus flags suppressed (MSFT 23:14 and MSFT 11:30, the same "vendor row is net-CASH per the feed's own note" shape), AMAT unaffected, and the NVDA R2 sign-flip fixture still flags.
Tests: `test_report_verify.py` **+4** (a neighbouring metric's assignment is not the stop; the stop after the word "stop" is read; the `(n x ATR)` leg is not a stop; a rejected vendor row is ignored - with the same row unflagged-but-quoted as the positive control); engine suite **4328 passed / 5 skipped** (was 4324). Re-running the verifier on the smoke tree: the market stem returns to **PASS** (70 claims) and both deterministic flags are gone (`_chandelier_identity` and `_net_debt_identity` return `[]` directly); the two FLAGs that remain on that tree are the LLM half's per-run variance (a different claim set than the first pass on the same unchanged stems), which is the documented open item.
**Web impact**: none - the verifier is advisory and its output shape is unchanged (`verify_flags.json` still carries per-claim statuses; only the false positives stop appearing).

**The canonical reader bound three line items to the wrong rows, and the whole MSFT valuation + forensic block read them (2026-09-16; `reports/MSFT_20260916_174952` adjudication).** Re-verifying the latest MSFT fundamentals stem against `tool_evidence.json` (every non-GROUNDED claim read against its leaf, the external check's claims adjudicated one by one) surfaced a producer defect under the report's own numbers: `statement_parsing._match_row`'s alias scan stopped at the first row whose LABEL CONTAINED the alias, and a label that *negates* the item contains it too.
- **`current_assets` / `current_liabilities` bound the NON-current rows whenever yfinance served the balance sheet.** yfinance labels its current rows `Current Assets` / `Current Liabilities` (no "Total" prefix) and lists `Total Non Current Assets` / `Total Non Current Liabilities Net Minority Interest` first, so the `current assets` fallback alias landed on the non-current line. Reproduced byte-exactly from the run's `get_balance_sheet_health` leaf (`current_assets=550,666M` = total non-current assets, `current_liabilities=147,164M` = total non-current liabilities) and from a live yfinance payload: current ratio **3.7419 vs 1.23**, working capital **403.50bn vs 38.89bn** - and Altman Z (X1), Ohlson O, Zmijewski, the net-net test, the Piotroski F-Score and the value-dip gate's balance-sheet leg all read that working capital. The same five bindings were wrong on the AMZN/NVDA/JPM balance sheets (JPM, a bank with no current-asset rows, is unaffected).
- **`operating_income` bound moomoo's `Other Non-Operating Income (Expenses)`** ($4.72bn) on the annual income statement, because "other non operating income expenses" contains the `operating income` alias and the sheet has no row carrying that exact phrase (the real row is `Operating Profit`, $155.24bn). That fed EV/EBIT **779 vs 23.71**, EV/EBITDA **85.12 vs 19.00** (which is why the report saw a "wide basis gap" against Finnhub's 19.61 - the gap was the bug), the earnings yield **0.13% vs 4.22%** and the earnings-power value floor **EPV $49.48bn vs $1,724.89bn** (conclusion `earnings-power-weak` -> `earnings-power-floor`).
- **`retained_earnings` bound yfinance's AOCI row** (`Gains Losses Not Affecting Retained Earnings`, -3.28bn vs +328.26bn) - Altman X2; **`depreciation` bound `Accumulated Depreciation`** (-118.69bn, a contra-asset where the reader wants the period expense, which poisons EV/EBITDA and Beneish's depreciation/gross-PPE leg); **`revenue` bound `Non Current Deferred Revenue`** (a liability).
- **The fix is structural, not a list.** `_match_row` now scans twice: negated labels (`non ` / `not ` / `excluding ` before the alias, unless the alias itself carries the token) are skipped in the first pass and only allowed if nothing plain matches - some items are only ever reported negated (moomoo's `Non-Operating Interest Expense` IS MSFT's interest expense row, and the retry preserves it). `_ROW_LABEL_EXCLUDES` gains the cases negation cannot express: `not affecting` (AOCI), `accumulated` (contra-asset), and `deferred`/`unearned` for revenue. Measured before landing, per the repo's convention: across MSFT/AMZN/NVDA/JPM/VTV/IEI balance sheets and income/cash-flow payloads, **every changed binding was a wrong-row correction** and no correct binding moved (the yfinance IS/CF payloads and the moomoo balance sheet were unchanged; the moomoo income statement changed only `operating_income`).
Tests: `test_statement_parsing_aliases.py` +9 (current assets/liabilities prefer the current row over the non-current one; the AOCI row is not retained earnings; a balance sheet states no period depreciation; a deferred-revenue liability is not revenue; the canonical dict from a yfinance-shaped payload carries the current rows; `operating_income` prefers `Operating Profit` over `Other Non-Operating Income (Expenses)`; a negated-only row still matches on the retry; the moomoo markdown form reads `Operating Profit`). Engine suite **4323 passed / 5 skipped** (was 4314).
**Report-text corrections in the same tree** (local artifacts: `reports/` is gitignored, so these are not commits): the fundamentals stem and its `complete_report.md` section now carry a correction note and the corrected figures (`was`), replace the "current ratio is a basis conflict" paragraph with the wrong-row cause (one ratio, three sources, all 1.23: statements, ratios, Finnhub `currentRatioAnnual`), state which DCF inputs are **not** provider data (growth/ERP are overrides, shares derived; the five explicit years grow at the same 2.5% as the terminal rate, so 69% of the value is the terminal perpetuity of a capex-suppressed FCF), name both market caps the feed carries (the "$9.3bn EV-bridge gap" is cap-dependent: $9.3bn against the ratios cap, $20.7bn against the price-consistent one), and move the dividend schedule to `get_corporate_actions` (EODHD), the leaf that actually carries it - `get_dividends` returned a stale, unsorted pre-2024 sample.
**Web impact**: none - no key, CLI flag or JSON shape changed. The corrected values reach the app only through the existing per-analyst leaves, on the correct side.

**The tool loop stops a round it has already run (2026-09-16; a 4-symbol deep batch, `reports/*_20260916_*`).** `risk_tool_loop.run_tool_loop` bounded a turn only by its round cap, so a model that re-asked for evidence it already held spent the remaining rounds on the same calls and paid a provider call for each. Prose-based guards cannot see this loop: the text is new every turn while the *question* is identical — the reports' own failure mode is a silent basis change, not a repeated sentence.
- Rounds are now fingerprinted (tool name + canonical args, sorted, so a key or call reordering is still the same round) and the **third** appearance stops the loop **before** executing it: every result that round asks for is already in the conversation, so the cap's existing terminal turn answers from them, and the transcript records `[cycle] the same tool call(s) came back 3x (...); terminal turn forced`. Two repeats are allowed, so a legitimate re-read of a moving value is not cut short, and an `A -> B -> A -> B` cycle stops too — the counter, not adjacency, is what trips.
Tests: `test_risk_agent_wiring.py` +4 — a repeated round executes exactly twice then trips; a two-call cycle stops after four executions; three DISTINCT rounds still consume all three rounds and never trip (the false-positive guard); the fingerprint is stable under key and call reordering.
**Web impact**: none — no key, CLI flag or JSON shape changed.

**Two argument contracts the trader's verification pass got wrong: a `*_pct` argument is a FRACTION, and a market level must be measured (2026-09-16; the live verification turn on NVDA 2026-09-15).** Both were found by running the trader's own verify prompt against the production provider after the tool-call-markup fix — the loop dispatched the calls, and the *arguments* were then wrong in two ways that produce numbers nobody computed.
- **The unit trap.** Every sizing/risk argument in `analysis_tools` is a fraction of capital (`0.01` = 1%) while its name ends in `_pct`, so a caller reading the name passes the percent number and the tool answers on an input nobody proposed: `get_risk_gate(size_pct=1.0)` for a **1%** proposal came back as `size 100.0% > cap 30.0% -> REJECT` — a REJECT the desk never issued, which the report then cited. The same trap silently capped `risk_per_trade` (1.5 = 150% → size pinned to the cap) and collapsed `stop_dist_pct` (8.371 vs 0.08371 → a 0.12% size). New `analysis_tools._fraction_errors` refuses the value with the corrected form (fail closed, never coerce — the project's rule) and produces no verdict from it: `size_pct`, `risk_per_trade`, `risk_frac` and `stop_dist_pct` are refused from `1.0` up (exactly `1.0` is the ambiguous value: 100% of capital, above every cap, and the shape of "1%" written as a percent), while rate-like arguments (drawdown, CVaR, book/sector exposure, a cap) are refused only above `1.0`, where `1.0` stays a legitimate boundary. Wired into `get_position_sizing`, `get_composite_sizing`, `get_risk_gate`, `get_composed_risk_gate` and `get_fixed_risk_size` (which used to answer a `risk_frac=1.5` with "equity/risk/price must be positive").
- **The invented level.** `get_exit_check(entry, close, atr)` took all three levels from the caller, so the pass supplied `atr=7.0` — a value no tool in that conversation had returned — and the arithmetic printed it as a computed check (the target 128.00 was 4× the invented ATR off the entry). Both exit tools now take an optional `ticker` and MEASURE the current price and 14-day ATR from the run's own daily series (`analysis_tools._measured_levels`), a measured value WINS over a conflicting caller one (`caller atr=7.00 ignored`), and without a ticker the output labels its levels `CALLER-SUPPLIED ... not measured` — so an invented number can never be read as a computed one. `close`/`atr`/`current` become optional; `ticker` is appended last so no existing positional call changes meaning. The trader's verify prompt now names `ticker=<symbol>`, the loop's system directive states both contracts for every tool-bound role (trader + 3 risk debators), and the market analyst's tool-guidance lines state the fraction convention and the measured-level rule.
Tests: `test_analysis_tools.py` +7 (the gate refuses `1.0`/`1.5`/`40` with no verdict issued and still gates `0.01`; a rate argument at `1.0` stays valid; both sizing tools refuse percent arguments; `get_fixed_risk_size` names the unit; the exit tools measure from the series and report an ignored caller ATR; without a ticker they label the levels caller-supplied) — the gate case is the reproduction (the pre-fix tool answered `REJECT; size=100.0%`). `tests/test_prompt_budget_contract.py`'s market ceiling was raised deliberately, 40 000 -> 40 300, for the four guidance lines that now carry both contracts (wording trimmed to +245 chars; the longest tool bullet stays at its recorded 523). No report-tree correction was needed: scanning all 11 repaired trees, the only surviving `REJECT` claims in trader prose are CVaR-budget rejects that were computed on a correct fraction.
**Web impact**: none — no key, CLI flag or JSON shape changed, and none of the four tools appears in `trading_web/docs/web_TOPICS.md`'s value-tool registry (`capabilities.VALUE_TOOL_SPECS`), so the app calls none of them.

**The Trader's "Computed verification" block could be a raw tool-call transcript — the loop only read structured `tool_calls` (2026-09-16; `reports/NFLX_20260915_152207/3_trading/trader.md`, `reports/NVDA_20260915_223229/3_trading/trader.md`).** 11 of the 22 archived `trader.md` files (and the same section of their `complete_report.md`) ended with the provider's tool-call markup instead of a computed spec. Root cause: `risk_tool_loop.run_tool_loop` read `result.tool_calls` only, so when a relay answers a tool-bound turn with its native markup inside `content` and an EMPTY `tool_calls` list, `pending == []`, the `while` never ran, and that markup was returned as the model's "final prose" — which the trader then appended under a heading claiming deterministic verification. **No tool had run in any of those trees**: the sizing / gate / exit calls the block names were never dispatched, so the report claimed a check that produced nothing. Same provider and model as a clean run three hours earlier (`openrouter` + `deepseek/deepseek-v4.1-flash`: NVDA 14:19 clean, NVDA 22:32 leaking) — intermittent emission, not configuration. Upstream this is the documented provider/parser mismatch: the gateway does not normalize its own markup into `tool_calls`, and LangChain does not parse it either.
Three layers, one vocabulary:
- **Parser (the recommended mitigation for a provider that leaks its tool syntax as text).** New `agents/utils/tool_call_markup.py` owns `TOOL_CALL_MARKUP_RE` (every spelling that reached the reports: single- and double-wrapped `U+FF5C DSML U+FF5C`, plus the variant whose block word lost its `tool_` prefix), `parse_text_tool_calls` (invoke blocks and their parameter name/value pairs, values coerced from the markup's own `string="true|false"` flag — a tool whose schema wants a float rejects the text `"1.5"`), `has_tool_call_markup` and `strip_tool_call_markup`.
- **Execution and guard.** `run_tool_loop` dispatches markup turns (`_turn_calls`): the parsed calls run through the same `ToolExecutor`, and the turn is replaced by a well-formed function-call message so a strict backend accepts the ToolMessages that follow — and so the model stops re-reading its own markup in the history as a format to imitate. `_final_prose` then guarantees the loop never returns markup: one tool-less turn asking for the prose (the tool results are already in the conversation), else whatever prose the strip left, else an explicit `unavailable:` notice. The system directive now names the function-calling interface and forbids writing a call as text.
- **Detector.** `trader._verification_is_stub` rejects a markup reply outright, so the block can never be appended under that heading, and `report_verifier._TOOL_CALL_MARKUP` is now the shared regex — it could not match the `tool_`-less spelling the reports actually carried.
Tests: `test_risk_agent_wiring.py` +3 (the parser recovers names/args and the types the schemas require, for both wrapper widths; a markup turn is dispatched and the returned prose carries no markup; a model that only answers with markup yields no markup and an `unavailable` notice), `test_structured_agents.py` +1 (a markup reply is not appended under the heading and is re-asked once), `test_report_verify.py` (the detector matches the `tool_`-less spelling). Verified against the previous code, which returns the markup as prose with `transcript == []` — the reproduction.
Artifacts: all 11 leaking trees repaired in place — the block, heading included, removed from `3_trading/trader.md` and from the same section of `complete_report.md` (1700 lines, 1308 tags; backup outside the repo at `%TEMP%/tradingagents_dsml_backup_20260915_234914`), and no file under `reports/` carries markup now. The block is dropped rather than annotated because the fixed code never appends one for this failure (the same guard drops a stub), so its absence is the honest state: the run produced no computed verification.
**Web impact**: none — no key, CLI flag or JSON shape changed; `trading_web` serves report files verbatim and parses no part of the trader block (it has no row in `trading_web/docs/web_TOPICS.md`), so a repaired or absent block is only ever rendered as text.

**Documentation brought back in line with the code (2026-09-16; a three-repo doc audit).** An audit of every human-facing doc found drift in all three repos; the fixes:
- `docs/design_report_verification_llm.md` (7 corrections): the 2026-09-08 conclusion "NO open code defect - journaling mechanics proven hermetic" is marked **falsified by 2026-09-13** (the short-circuit guard matched nothing, so 0 of 38 archived runs carried a journaled leaf, and the ROST "fabricated call" attribution rests on that broken journal); the verdict list now names all five statuses (the doc said three, while the numeric anchor emits MISQUOTED and the same-metric scan INTERNAL_CONFLICT, and the decision rule keys on all four non-GROUNDED); the invented `NO_LEAF_CATEGORY` class name is replaced by the real "no leaf evidence" wording; the "latency-orphaned tools" problem statement is past tense with all four tools re-bound; `vrp` moved from "residual, accepted" to closed (the unit-scoped exemption); and the open-items list was re-measured against the current code - it keeps LULU `ev/ebit` + `scenario dcf base/bull`, LRCX `diluted eps`/`altman z`, AMZN `ev/ebit` and MSFT `rvol`, and records that the per-segment scoping **closed** SKHY's `t1`/`t2` and WDC's `scenario dcf` pair.
- `.env.example`: 248 `TRADINGAGENTS_*` names documented (was 209) - every key the code reads now has a line, with defaults traced to `default_config.py` (three apparent gaps were not keys: `TRADINGAGENTS_HOME` is a module constant, and two were f-string fragments).
- `README.md`: the "raw files stay byte-identical" claim was wrong (the debate/trader/risk sections go through the readable pass - paragraph spacing plus `### Round N` - and any section can carry a truncation marker) and the run card's absence key is `data_absence`, not `absence`.
- `docs/api_reference.md`: `analyst_consistency` now names `report_verifier._valuation_identity_checks` (the valuation quartet was missing from the stated family); batch's `--vendor` presets include `eodhd|tiingo`.
- `docs/AGENT_ONBOARDING.md`: rule 8 now lists all four non-GROUNDED statuses (a MISQUOTED/INTERNAL_CONFLICT row is a capture-or-citation defect, not noise) and the worklog carries this round.
- `scripts/verify_sweep.py`: the docstring advertised `report_verify.py --verify`, a flag that does not exist (`--report-dir`).
- Sibling repos: `trading_web` (the report-verifier pointer named the CLI instead of the in-process `verify_report_dir`; the Raw screen's entry-point list omitted two allowlisted scripts; the signals hint predated the RTH scan window; the claim-status enumeration missed two statuses) and `TradingExecution` (the scan window, `mandate-add`/`mandate-remove`, the candidate card, mandate hot-reload and the held-name exit exemption were undocumented).
Also corrected in place: this session's own `2_research` round-separator entry carried a wrong web-impact reason (the app serves every `*.md` of a tree verbatim; the registry has no row for the report tree, so the note was not required at all).
**Still open by decision**: `trading_web/docs/web_TOPICS.md` records only the subprocess symbols, tool attributes and raw allowlist, so the in-process surfaces the app actually consumes (`verify_report_dir`'s payload, the report-tree markdown, `default_config.DEFAULT_CONFIG`, `value_screener._fetch_ohlcv`, the execution signal feed, `moomoo.close_all_contexts`) have no registry row and no shape test - the audit supplied the exact rows.
**Web impact**: none - documentation only; no key, CLI flag or JSON shape changed.

**The bull/bear transcripts never separated their rounds - the research section did not use the risk section's format (2026-09-16; `reports/IEI_20260915_210623/2_research/bull.md`).** `write_report_tree` promotes repeated speaker turns into `### Round N` headings, but the research branch passed `role=name.split()[0]` - **"Bull"** - while the debate state labels every turn `"Bull Analyst:"` (`bull_researcher.py:82`, `bear_researcher.py:80`). The occurrence count was therefore 0, promotion never fired, and a two-round `bull.md`/`bear.md` rendered as one unbroken wall with no marker between rounds. The 4_risk branch has always passed its speaker (`"Aggressive Analyst"`) and has always read separated, which is exactly why the two sections looked different; the research branch now passes the same speaker token and renders identically. The duplicated `_readable_section` call on that path is also hoisted, so the file and the consolidated report render from one pass instead of two.
The reviewed tree was re-rendered in place with the same transform (content-preserving and idempotent - `_readable_section(_collapse_repeated_tables(text), role="Bull Analyst")`): `2_research/bull.md` and `bear.md` plus their embedded copies in `complete_report.md`, nothing else in the tree. **`scripts/rebuild_complete_report.py` was NOT used for this**: rehearsed on a copy of the tree it strips 6 lines from each of `4_risk/{aggressive,conservative,neutral}.md` and `5_portfolio/decision.md` (the recovered `### Risk Gate (computed)` block re-prepends differently), so a repo-wide re-render is a separate decision.
Tests: `test_report_readable.py` +1 (a two-round bull/bear history through `write_report_tree` must carry both round headings in order, each round's prose under its own heading) - it fails against the old role token (verified: `_readable_section(text, role="Bull").count("### Round") == 0` vs `role="Bull Analyst"` == 2).
**Web impact**: none - no key, CLI flag or JSON shape changed; `trading_web` serves every `*.md` of a report folder verbatim (`backend/capabilities.py::read_report_tree`, rendered raw in the report view), so the added headings render as text. (Corrected 2026-09-16: the registry at `trading_web/docs/web_TOPICS.md` has no row for the report tree, so its rule did not require this note at all - and the reason first given here, that the app merely names the folder, was wrong.)

**IEI 2026-09-15 verification: one real defect fixed in a live report, five false-positive classes fixed in the verifier (2026-09-16; `reports/IEI_20260915_210623`).** The advisory pass over the newest tree returned FLAG on `market` and `sentiment` - 13 non-GROUNDED claims, each adjudicated against `tool_evidence.json`:
- **Real, report-side:** market.md counted `get_capital_flow` as "negative in 7 of the last 8 weeks"; its own weekly table shows **6 of 8** (2026-07-27 +0.1B and 2026-08-03 +0.7B are positive). Corrected in the body and the summary row, in the stem **and** the tree's `complete_report.md`. Two further analyst-side recall defects: sentiment.md asserted "hedge-fund **basis-trade unwind** risk, a mechanical seller of the belly of the curve" where no leaf carries "basis trade" (the headline's supplied snippet stops mid-sentence at "the main systemic th"), and sentiment.md + news.md both quoted "IEI's **~4-5 year duration**" while the same tree's fundamentals section had correctly withheld a duration figure (`get_fixed_income_risk` = n/a). Both now name the fund's 3-7 year maturity band and say no duration figure is in the evidence.
- **False positive 1 - a word boundary.** `_PRIMARY_PRICE` had none, so the alternation matched the "**at**" INSIDE an ordinary word: market.md's caveat `... "do not reconcile as a true print."* Treat 114.33 as unverified.` made the disowned Alpaca print the report's spot price, and the swing-set summary row's 2R/3R targets were then re-derived off the day low plus ATR (114.33 + 2*0.2939 = 114.92 vs the quoted 115.2778) - two verbatim `get_swing_set` targets flagged. "Treat" is not "at"; the boundary is now pinned by a test.
- **False positive 2 - multi-producer scoping.** `t1`/`t2` values were grouped by the FIRST tool named on a line and by nothing at all on a tool-less line, so `get_tranche_plan`'s T1 115.40 and `get_swing_set`'s T1 115.2778 landed in one scope (on the line naming both tools) and flagged each other, twice. Scoping is now per **segment** - each value binds to the producer named nearest before it - with a framework-label fallback (`swing set` / `tranche plan` / `chandelier` / `ema20`) for tool-less summary rows, so a row pair that quotes two frameworks by design no longer pairs up.
- **False positive 3 - a foreign percent in the 200-SMA window.** The 60-char window after the label reached a different metric's percent: "no short thesis at 200-SMA support with **4.8-4.9%** 5-7y yields" (a yield) and the Bollinger "**%b -6.22%**" two clauses later produced "200-SMA distance cited at different values: +4.9% / +6.2%" for a report that states one distance. A percent is now skipped when another metric's label introduces it, or when it is the second leg of a range.
- **False positive 4 - a dated series is not a dual value.** "10 EMA 116.1043 -> **115.0450**" (moomoo, 08-17 to 09-15) beside the verified "10 EMA 115.20" read as two competing readings; both legs of a series are now skipped.
- **False positive 5 - the meeting is not a market-implied figure.** The macro-authority gate held a line naming the **FOMC meeting** to `get_fed_watch`/`get_prediction_markets`, though the sentiment analyst's own news leaf carries the Fed decision (UBS: "expects the Federal Reserve to raise its policy rate by 25 basis points on September 16"; Apollo: "Federal Open Market Committee ... at its mid-September meeting"). The bare "fomc" trigger moved to its own group, satisfied by a leaf carrying the central bank's own names; **probability/pricing** claims ("hike probability", "no rate cuts", "fed watch", "Polymarket") keep the strict pinned-tool requirement.
Post-fix re-run: all four analyst sections PASS (0 non-GROUNDED claims) and `verify_flags.json` is rewritten in the tree. One claim was checked and *kept*: sentiment's headline "Score: 0.2/10" against `computed_score=-1.00` is inside the prompt's own anchor (`5 + 5*computed_score` = 0.0, +/-0.5 allowed).
Tests: `test_report_verify.py` 180 passed (+1: the word-boundary regression, which fails against the previous regex) and `test_report_readable.py` +1 (the round separators); full suite 4246 passed, 5 skipped (the same five as before).
**Web impact**: none - no key, CLI flag or JSON shape changed; `verify_flags.json` keeps its `claims`/`overall` shape and simply carries fewer false claims.

**The post-PM decision guardrail is switched on in `.env` (2026-09-15), with the A/B that shows what it does and does not cost.** `TRADINGAGENTS_ENABLE_DECISION_GUARDRAIL=true` activates `strategies/decision_guardrail.py` in the PM result hook (`managers/portfolio_manager.py::_guardrail_hook`, before the card renders): (1) a **risk-cap** - any Buy/Overweight becomes **Hold** when a structured risk-debate row is HIGH or CRITICAL, recorded as `risk_cap="Hold"` plus `guardrail_reason="risk-cap: ..."`; (2) `cap_pm_confidence` - confidence capped at **0.70** when the PM's `data_quality` is not fresh; (3) `cap_pm_confidence_on_judge` - confidence capped at **0.50** when the risk-debate judge flipped its winner across the ensemble or fell back to free-text/repair. It is downgrade-only by construction (property-tested: never upgrades, never flips a sign except to exactly zero, so risk can cap at Hold but never force a Sell), it costs no provider calls, and a failure inside the hook is swallowed so it cannot break a run. Two rules are dormant as wired: the near-resistance/flow softening (the hook passes only `risk_rows`) and `validate_score_action_agreement` (the PM has no 0-100 score field yet).

Measured before enabling, because the concern was lost opportunities: across the **21 report trees in `reports/` the cap would have changed 0 ratings** - 17 Underweight, 2 Hold, 0 Buy/Overweight - even though **21 of 21** trees carry 4-9 HIGH/CRITICAL risk rows (`name_cvar_exceeds_budget`, `vol_regime_gate_fail`, `event_catalyst_fomc_volatility`, ...). The trigger is routine; its precondition (a POSITIVE PM rating) is what never occurred, because those same HIGH rows already make the deterministic gate block new risk. A same-day A/B on NFLX (`NFLX_20260915_152207` with the guardrail on vs `NFLX_20260915_140346` with it off, same depth/config) confirms it: rating Underweight and confidence 0.55 in both, `guardrail_reason = None` - nothing fired, since 0.55 is already below both caps. Driven with that run's own risk ledger, the rules do bite: `stabilize_decision("Buy", <its 5 HIGH factors>) -> Hold` ("risk-cap: high-severity risk caps recommendation at Hold"), `Overweight -> Hold`, `Underweight -> Underweight` (bearish untouched), `cap_pm_confidence(0.90, "partial") -> 0.70`, `cap_pm_confidence_on_judge(0.90, judge_flip=True) -> 0.50`. If it proves too blunt once positive ratings return, the dials are: cap on CRITICAL only, convert the rating cap into a size haircut, or A/B it against `scripts/alpha_health.py`'s ledger.

Side finding from the same run: `NFLX_20260915_152207` is the **first report tree in this repo carrying `research_decision.json`** - the emitter fix above, live in production (`schema_version 1.1.0`, `expires_at 2026-09-17T00:00Z`, 158 sources used / 1 empty, and it validates against the executor's published contract).
**Web impact**: none - no key, CLI flag or JSON shape changed; `trading_web` does not read these fields.

**Second batch of the day (NFLX/LULU/MSFT/NVDA, 4 workers, shallow) - a live report degenerated into restart markers and synonym loops, and the tree still recorded PASS (2026-09-15).** All four symbols completed (`batch_summary_20260915_134620.jsonl`, all Underweight). `reports/NVDA_20260915_141952/1_analysts/market.md` is not a report: it opens by announcing that a previous turn suffered "an unrecoverable generation fault mid-draft (an internal repetition loop)" and must be discarded, then runs a synonym-chain loop inside that same sentence; its citation bullets lost their separators so digits run together (`ATR(14)=6733273738700908`, `RSI450308`); it carries "*(Generation fault again detected mid-sentence.)*" and "*(Terminating.)*" lines; and it ends in two whitespace-free dumps (4,903 and 5,870 chars) that close with synonym chains. The HPE 2026-09-14 shape, recurring in production - and again the tree recorded `decision.verdict=PASS` with `analyst_consistency: null`, i.e. the debate, trader and portfolio stages consumed it as the market read. What worked this time is the detector: `_self_correction_artifacts` flagged it (degeneration markers + whitespace-free runs), the stem was replaced with an inventory note (stem and `complete_report.md`), and the verifier now reports such stems as unusable instead of judging the note's own sentences - the previous behaviour spent a provider call and returned six UNSUPPORTED flags per note (`_unusable_note`, sentinel `SECTION UNUSABLE`).

Report defects from the batch, corrected in place in the stem **and** the tree's `complete_report.md`: LULU fundamentals called FY2026 "the first down-year in the series" while its own `get_financial_history` leaf shows a 1.0B to 0.9B decline two years earlier and a 0.3B to 0.2B decline in FY2015; MSFT sentiment invented an "8.4/10" headline score ("+0.69 ... which maps to 8.45/10"), invoked a "~70/30 moderately bullish reference band" and a ">=90/10 over-extension zone" that no tool defines, and called n=30 "labeled messages" when 13 are labeled; NFLX sentiment invented an "8.7/10" score and the same n=30 labeling error (16 labeled); NVDA sentiment invented "4.0/10" and "thirty labeled messages" (12 labeled of 30, an exact 6/6 tie); MSFT sentiment claimed the Mag-7 P/E comparison was "repeated across two separate headlines" when one headline carries the figures.

Five checker classes fixed. **200-SMA distance**: a table row pairs its labels and values by ORDINAL (MSFT 2026-09-15 market.md writes `| 50-SMA / 200-SMA | 457.68 / 429.95 | Stacked, rising; +8.9% / +15.9% above |`), so the 50-SMA figure is no longer read as a second 200-SMA distance. **Disclosure scope**: prose stays paragraph-scoped - a reconciliation clause names its figures first and the basis at the end of a long sentence - but inside a TABLE the marker must share the ROW with the value, because a summary table is one paragraph and a current-ratio note was exempting the ROE quartet printed two rows later (the ROE quartet is correctly flagged now: "quote all four; no reconciliation offered"). **Marker vocabulary**: `mislabelled`, `non-current`, `wrong row`, and `two|three|four|five|six bases` (reports write "five bases"); the bare *instruction* "quote all" is deliberately NOT a marker, since the same sentence said no reconciliation was offered. **Foreign-context values**: a metric's number sitting inside another metric's list is not a reading - `get_vif_read`'s "rsi 5.4 HIGH>5" (a VIF SCORE) is no longer an RSI reading beside the real RSI 50.71 (SMCI); `\bvif\b` cannot match inside `get_vif_read`, the same trap `_VIF_MARKER_RE` documents. **Net-debt identity**: the net leg is bound by slash-cell ordinal (`| Total Debt / Net Debt | 14,309,306,000 / 5,210,074,000 |` was handing the TOTAL DEBT to the net leg), and the cash+STI gap may not bridge into another noun phrase ("a -25.7% QoQ drop in cash + ST investments and a 4,714,403,000 buyback quarter" handed the BUYBACK to the cash leg) - both false positives cleared (NFLX, SIMO) while the pinned R2 sign-flip test still bites.

**Web impact**: none - no key, CLI flag or JSON shape changed; `verify_flags.json` carries fewer INTERNAL_CONFLICT claims. **Still open** (unchanged family): the slashed-label-cell bindings for `t1`/`t2` (SKHY), `scenario dcf base/bull` (LULU, WDC) and `ev/ebit` (LULU), and the single-line two-period cluster (LULU's D/E row labels 2026-01-31 and 2026-07-31 side by side; the period-tag model is line-level by design - a per-value variant was tried and reverted because it re-flagged a correctly exempted AMZN ROE pair).

**The execution layer's only input contract was never written - a silently swallowed `AttributeError` (2026-09-15; found while tracing the research-to-Discord path).** `write_research_decision` crashed on every run that gathered tool evidence. `reporting._evidence_sources` walked **every** value of `state["tool_evidence"]` as a leaf list, but the gatherer stores its run-level records in that same mapping, and `_model_pool` is a **dict of tool-name lists** - so its name strings reached `(leaf or {}).get(...)` as `AttributeError: 'str' object has no attribute 'get'` (`reporting.py:505`). The call site is wrapped in `write_report_tree`'s `with suppress(Exception)` ("advisory; never breaks the report"), so the failure was invisible: every tree got a `run_card.json` and **no** `research_decision.json`. Verified: 0 artifacts across every tree in `reports/` and under `~/.tradingagents/logs`, TradingExecution's `audit/audit.jsonl` holding a single `kill_switch` row (no `accepted`, no signal), and no `signals/signals.jsonl` - i.e. the signal daemon has never had anything to ingest, let alone notify Discord about.

The walk now matches on **shape** - `isinstance(value, list)` and `isinstance(leaf, dict)` - not on the four analyst names: the key set follows the selected analysts (the same reason a name allow-list would silently drop a real analyst's leaves and misreport `data_quality`), the reserved keys are skipped wholesale, and rows without a `tool` key stay skipped as before. Verified against the real `reports/AMZN_20260915_113032/tool_evidence.json`: 156 sources used, 1 empty (`get_analyst_verdict`), `data_quality=partial`, and the emitted 6.2 kB artifact validates against the executor's published `TradingExecution/contracts/research_decision.v1.schema.json`; `write_report_tree` now lands `research_decision.json` beside `run_card.json` (checked at the real call site, wrapper included). Also corrected the two stale contracts in `evidence_gather.py` that asserted a dict value "would raise there". Test: `test_emitter_survives_the_gatherers_run_level_evidence_keys` - fails pre-fix with the attribute error.
**Web impact**: none - `trading_web` never references `research_decision.json` (checked), and no key, CLI flag or JSON shape changed. Note for the execution layer: trees written before this fix carry no artifact, and the emitter deliberately refuses to invent one from a markdown-only rebuild, so the contract appears from the next full run onward.

**Same-day batch (AMKR/JCI/VST/SIMO) surfaced a second round of verifier false positives plus one more capture class (2026-09-14).** The 2R/3R R-multiple identity fired on *every* tree that quoted a tranche plan, for two reasons now fixed: `_STOP_RE`'s 12-char gap let "stop: swing_low **134.9000**, structure_stop **129.9781**" bind the swing LOW as the stop (VST: the report's own correct T1(2R) 162.2338 was reported 6.8% wrong), and when a line stated its own multiple but no entry the check fell back to the report-wide spot price, which is not a tranche plan's basis (AMKR: "T1 55.27 (1.8R)" flagged against the quote; TSM's summary row "| Tranche plan | stop 382.56; T1 450.62; R:R 2.40 |" likewise). A stop candidate whose gap names another metric (swing low/high, entry, avg, target, base) is now rejected, a line stating its own multiplier - or quoting a scale-in ladder - never gets the spot fallback, and an implied multiple within 3% of a clean tenth is accepted (1.798 is the tool's own 1.8R rounding, which the previous 1% test rejected). Same-metric scan: values read after a peer-comparison marker are dropped for the comparison metrics ("vs NVMI forward P/E 32.93, PEG **1.88**" is the PEER's PEG, not AMKR's - 2026-09-14 news.md), a dropped magnitude suffix no longer splits one figure into two ("market cap $87.8B" beside "87.8", JCI sentiment.md), and the disclosure markers gained "separate ... basis", "conflicting bases" and "as printed"/"history" (AMKR's four-year FY series beside its latest quarter, JCI's three-basis ROE row and its disclosed ATR pair). Measured over the 14 trees now in `reports/`: **86 -> 18 deterministic flags** (11 conflicts + 7 identities), 167 verifier tests green. Real defects found in the new batch were reconciled in place: VST fundamentals now states its three current-ratio bases (0.973 / 1.31 / 1.3145) and its three ROA bases (2.27 / 5.89 / 5.34 DuPont-implied), propagated into that tree's `complete_report.md`.
**Still open, same family:** `t1`/`t2` on SKHY (a slashed label list inside one paragraph), the WDC `scenario dcf base/bull` row binding, the AMZN news day-count (the fitting date sits on a neighbouring line), the SIMO net-cash identity (a wrong `$0.00B` cash capture - the report's own $12.5M net cash is correct), and the `mean price target` metric still collecting option-IV means (AMZN 102.8/91.3).

Four more false-positive classes came out of the LLM pass over those trees and are fixed: a claim that *asserts a series is unavailable* is now grounded (its absence is the support - the prompt REQUIRES saying "unavailable" rather than quoting a recalled value, so "the effective fed funds rate / RRP series returned no fresh evidence this run" was flagged UNSUPPORTED for having no EFFR/RRP leaf); the `%` guard on `_PRICE_TARGET` keeps "call IV mean 151.3%, put IV mean 184.7%" from reading as two conflicting mean PTs (JCI - and the guard refuses to backtrack into a partial capture); a statistical mean is no longer a price target ("current 1.2770 vs mean 1.9691, std 0.5373" - TSM); and `_expected_band_identity` no longer fires on a line that DISCLAIMS the zero band ("dollar band unavailable, not +-$0.00" - SIMO). Report defects from the batch, corrected in place in both the stem and the tree's `complete_report.md`: AMKR market "VWMA has fallen 20 of the last 21 sessions" vs the leaf's 14 declines in 19 transitions; AMKR news "Reference price 47.12 ... below all 2026 insider sale prints" vs five prints below it (47.00 on 2026-07-30, 44.54 on 2026-03-16, 45.89/46.03/46.92 on 2026-02-17); and JCI fundamentals "buybacks materially reduced versus the prior-year quarter" vs the leaf's FY25 Q3 -310,000,000 against FY26 Q3 -635,000,000 (they ROSE ~2x).

Third provider-side safety rejection in a row on dense fundamentals text ("Upstream error from Alibaba: Output data may contain inappropriate content") leaves those stems UNKNOWN - a verifier-model choice (`TRADINGAGENTS_VERIFY_MODEL`), not a report defect.
**Web impact**: none - `verify_flags.json` simply carries fewer INTERNAL_CONFLICT claims; no key, CLI flag or JSON shape changed.

**Second batch of the same day (AMZN/VST/TSM/WDC, 4 workers, shallow) - the reference price was never evidence, and eight capture classes fell out with it (2026-09-15).** Three of the four symbols completed (`batch_summary_20260915_110651.jsonl`: AMZN, VST, TSM, all Underweight); **WDC died on the provider's own output filter** (`APIError: Upstream error from Alibaba: Output data may contain inappropriate content.`) - the same upstream rejection class that has now hit the verifier three times, so it is a provider/model choice, not a report defect. Its re-run was stopped on operator instruction; `reports/WDC_20260915_120300` is the partial tree that run left behind (flat files, no `1_analysts/`, no `verify_flags.json`) and was deliberately not regenerated.

The structural find: **the run's reference price is part of every analyst's prompt but was not part of the verifier's evidence.** `evidence_gather._render_evidence` PREPENDS `**Reference price: X (date, FORMING intraday bar - provisional)**` to all four stems and freezes it in `tool_evidence.json` under `_rendered_block`; the verifier's digest was built from the leaves alone, so TSM news.md ("the reference price is 413.23") and AMZN news.md (which named its own source as "prompt") were flagged as fabrication every run. `_evidence_digest` now renders that line as a `reference_price [ok]` row and `_evidence_decimals` includes its figure for the anchor layer; both stems re-verified PASS.

Seven more capture bugs, each with the row that produced it: **`_primary_price` read the prior close** (TSM market.md opens "Verified OHLCV ... C 413.23" then quotes "Prev close 418.01", which the R-multiple fallback bound as the entry - now `(?<!prev\s)(?<!previous\s)(?<!prior\s)`); **a parenthesized multiple is a stated basis** ("targets T1(2R) 444.2039, T2(3R) 459.6909" off the swing set's own swing-low/ATR - new `_RMULT_STATED_LABEL_RE`, parenthesized only so a bare "2R/3R targets" phrase still is not); **a stop candidate can wear another metric's parenthetical** ("puts 386.51 (structure stop) and 381.68 (200-SMA) in play" bound the 200-SMA and flagged a correct 2R - new `_STOP_TAIL_REJECT`); **a magnitude suffix swallowed the next word's first letter** ("fcf=2,255,000,000, market_cap=47,133,249,536" read the m of market_cap as MILLIONS, turning a 2.255B FCF into 2,255,000B and inventing a unit slip - `(?![A-Za-z])` added to eight patterns); **`_SUM_LINE`'s total group could not read commas** ("= $2,592,000,000" parsed as 2) and a unit-scaled sum is not a slip (addends in millions, total in dollars - WDC); **one stop printed at two precisions is one stop** (LRCX chandelier 306.033 vs 306.0336, a 0.0002% drift - new shared `_cluster_value_tokens`, now also used by the EMA-trail and GARCH identities); and **a VRP in percentage points is not a VRP ratio** (AMZN market.md: +2.10pp from `get_options_iv_read` beside +0.0490 from `get_variance_premium` - new `_UNIT_SCOPED_METRICS`/`_unit_after` guard).

Two identity checks were reading disclosed differences as contradictions, and the disclosure policy now reaches them: **`_roa_consistency` compares within ONE paragraph** (TSM/VST print the quoted ROA bullets away from the DuPont inputs), is exempt when the block states a basis, and fires only when the margin x turnover product is not also one of the report's own quoted ROAs (AMZN prints 6.59/15.21/11.10 and the product IS `get_ratios`' 11.10; the pinned NVDA R1 case quotes a single ROA the decomposition does not produce, and still flags); **`_dupont_identity` checks only the ROE attached to the decomposition** (SKHY prints "ROE 134.2% ... net_margin 0.8562, asset_turnover 1.0742, equity_multiplier 1.4595 ... This conflicts with get_ratios ROE 35.57%" - reading the disclosed comparison value was a second failure). `_DISCLOSURE_MARKERS` gained "conflicts with" and the generalized "two|three|four bases"; `_PERIOD_TAG_RES` gained the prose period words `quarterly`/`annual` (AMZN D/E 0.37 against a 2025-12-31 balance sheet beside a *quarterly* 0.2816).

Report defects from the batch, corrected in place in the stem **and** the tree's `complete_report.md`: TSM news attached the last print's 3.9% implied move to the 2026-10-14 print (the `get_earnings_catalyst` leaf has one row, 2026-07-16); TSM sentiment attributed a "forward P/E of 19" to TSMC twice when the headline leaf gives it to Broadcom; VST fundamentals asserted the run-rate DCF's EV (24.25B) was "below the EPV floor" when the floor leaf's epv is 15.6B (the DCF clears it in EV terms - what fails is the 4.78% FCF yield against the 6% threshold). The HPE degeneration note was also paraphrased: it quoted the detector's own marker phrases, so the note re-flagged itself.

Also fixed the one suite failure this round surfaced, which was not new: the market analyst prompt sat **169 chars over its 40,000-char budget** (`tests/test_prompt_budget_contract.py`) since the NEVER-RESTART rule landed on 2026-09-14. Trimmed the rule's wording (same markers, same citation) and the duplicated "organized ... organized" table sentence; the prompt is now 39,972 chars (28 under) and the contract test passes.

Measured over `reports/`: **18 -> 7 deterministic flags** (the seven are the known open capture items). `tests/test_report_verify.py`: 178 (+10: prior-close price, reference-price evidence, parenthesized multiple, stop tail, VRP units, unit-scaled sum, chandelier reprints, DuPont disclosure, ROA paragraph scope, period-tag disclosure).
**Web impact**: none - no key, CLI flag or JSON shape changed; `verify_flags.json` carries fewer INTERNAL_CONFLICT claims.

**A whole analyst report was shipped mid-degeneration, and the verifier had no check that noticed (2026-09-14; found by running the verifier over every tree in `reports/`).** `reports/HPE_20260914_213213/1_analysts/fundamentals.md` is not a report: it opens with a `FINAL TRANSACTION PROPOSAL` line, then "Wait correction needed", "Correction: ... Stop.", "This is degenerating", a line repeated twelve times (`Inventory series:** ``635200`. **`), the model's own admission ("I am stuck repeating myself due an internal glitch. Please disregard this draft attempt entirely. I will restart cleanly below."), and finally a SECOND copy of the report with spaces, underscores and decimal points stripped (`DCFFairValue194EV440527404343terminalshare64WACC121beta144...`), so its figures are unreadable and unreconcilable. The deterministic pass flagged none of that - it only produced bogus figure conflicts read out of the mangled digits - and the tree went on to record `decision.verdict=PASS`, i.e. the research/risk/portfolio sections consumed it as the fundamentals read. Three fixes. (1) The verifier now detects the class: `_self_correction_artifacts` gained degeneration markers (restart/disregard/glitch/degenerating), a repetition-loop check (a non-trivial line repeated 4+ times), a degenerate-run check (200+ chars with no whitespace), a conflicting-`FINAL TRANSACTION PROPOSAL`-verdict check (two *identical* proposal lines are a style habit and stay silent) and an unexecuted-tool-call-markup check (`<invoke name=...>, and a raw float leaked into the prompt and from there into prose (2026-09-14; AMZN `news.md` fact-check).** The fact-check recomputed (5.75−1.83)/1.83 = 214.21% against the quoted `surprise_pct=215.02` and flagged a 0.8pp gap. Its guess — rounded inputs — is correct, and the tool *already states it*: `get_earnings_calendar`'s header carries "surprise_pct is the vendor's own figure (from unrounded EPS), so it need not equal (reported-estimate)/estimate on the 2dp values shown". The report dropped that caveat when quoting the three numbers, so a faithful transcription read as an internal inconsistency. Two fixes: the news analyst prompt gains a **TOOL-STATED CAVEAT** rule (carry a tool-printed basis/caveat with its figure — same for any vendor ratio quoted beside its rounded inputs), and the report states the reconciliation inline. Separately, `get_news_sentiment_series` printed a computed score's raw repr — `latest score 0.23340000000000005` — beside a table rounding the same value to `+0.23`; since the analysts copy tool numbers **verbatim** by rule, the 17-digit float reached that report's verdict line, its sentiment bullet and its summary table. The EODHD, Alpha Vantage and GDELT renderers now format the latest score/tone and 7d SMA to 4dp at the source (the `n/a` path is untouched, so a missing value still reads `n/a`). Test: `test_sentiment_summary_line_formats_the_score` — fails against the previous template, where the raw repr trips both the no-long-float assertion and the 4dp match. Report corrections also carry two data-quality items invisible from the prose: the buyback figure is the **statement's** ordinary-share count (vendor basis unstated — not the market-cap-implied ~10.786B, nor the NI ÷ EPS-implied ~10.883B), and the vendor breadth table's bucket labels are self-contradictory and overlapping (`7% … 0%` beside a separate `0% … 0%` row, with `0% … -7%` overlapping `-3% … 0%`), so the buckets must not be summed.
**Web impact**: none structurally — the sentiment leaf's rendered *text* is now 4dp-formatted; no key, CLI flag or JSON shape changed. Baseline: every other figure the fact-check checked matches its leaf exactly (10Y 4.96 from 4.72 = +5.08%, TGA net draw 21.5B, FOMC 92.4% + 7.6%, the 45-day countdown, the 8.2% implied move shared with `market.md`, insider sales 260.33-260.45 against the 254.77 automatic disposition), as do the ones it did not (credit 2.65/10.76/1.50% + 4.3% default prob, catalyst scale 0.9 / mult 1.00, FX, prediction markets 94%/10%, SEC filings, TGA dates).

**A report that quoted the tranche tool verbatim was reported as self-inconsistent, and the checker that should have caught a real R-multiple error could not read the tool's own spelling (2026-09-14; AMZN `market.md` fact-check).** The fact-check read the tranche plan's `shares=109, risk/share=13.74, capital_at_risk=$1,486` as irreconcilable (109 × 13.74 = $1,497.66) and concluded the dollar figure and the share count disagreed by 0.8%. They agree: capital-at-risk is the **per-tranche** sum `Σ n_i×(P_i−stop)` = 32×20.04 + 32×14.31 + 45×8.59 = **$1,485.64 → $1,486**, because each tranche carries only the distance from *its own* fill to the composite stop; multiplying `total_shares` by the *weighted-average* risk/share applies the P1 distance to the cheaper P2/P3 fills and overstates the risk by $12. Nothing was wrong with the number — the tool's line was unreadable and the report had dropped the weights. So `get_tranche_plan` now names the measure and the account it was sized against (`capital_at_risk=$N (=sum n_i*(P_i-stop), not shares*risk/share) vs max $M risk_ok=… (account $A x R% risk)`) — the `$1,500` cap is that tool's **default** $100,000 × 1.5% and was previously invisible to the reader — and `reports/AMZN_20260914_192119/1_analysts/market.md` was corrected to quote the weights (`w=[0.3, 0.3, 0.4]`, `n=[32, 32, 45]`), the per-tranche decomposition, and the account basis, and to stop attributing the tranche risk check to `get_composed_risk_gate` (that gate was called with `ticker` only, so its PASS rests on `portfolio_drawdown=5.33%` alone and never evaluated the tranche capital-at-risk).

Verifier side, and the reason this matters beyond one report: `report_verifier._ENTRY_AVG_RE` could not match `avg_entry=` — the tool's own stdout spelling — because the optional entry qualifier demanded whitespace (`(?:\s+entry)?`) and `\bentry\b` cannot match inside the underscore-joined token. The reader therefore fell back to the report-wide spot price, paired the *close* (253.54) with the composite stop (233.50), computed risk 20.04 instead of 13.74, and flagged `get_tranche_plan`'s own correct 1.8R/3.0R targets (T1 271.97 / T2 288.46) as two INTERNAL_CONFLICTs — a report quoting the tool verbatim could not verify clean. The spelling is now read; measured over all 277 archived analyst reports: reports with R-multiple flags 10 -> 9, total flags 26 -> 23, 0 regressions, the AMZN tree the single report fixed. Test: `test_r_multiple_identity_reads_avg_entry_underscore_spelling` (fails against the previous pattern with exactly those two flags).

**Not fixed, same check:** `_STOP_RE` binds the *swing low* instead of the stop when `structure_stop` is immediately followed by `swing_low=<value>` — the optional `struct(?:ure)?[\s_]*` prefix is consumed, then the first float within the 12-char gap is the low, so `structure_stop swing_low=249.5800, stop=243.8550; targets entry=253.5400, T1(2R)=272.9100` (un-bolded) resolves risk 3.96 and raises two spurious flags. The 23 remaining flags across 9 reports are this class (mixed with whatever genuine errors they contain) and need their own adjudication before the pattern is tightened.
**Web impact**: none structurally — a tool's text gains its account basis and the measure it applies, and `verify_flags.json` carries fewer INTERNAL_CONFLICT claims; no key, CLI flag or JSON shape changed.

**The report verifier's deterministic scan cried wolf: half of its same-metric conflicts were capture artifacts (2026-09-14; found running it over the
MU/SNDK/DELL/SKHY batch).** Adjudicating a 4-tree run (727 claims: 639 GROUNDED, 78 INTERNAL_CONFLICT, 6 UNSUPPORTED, 4 MISQUOTED, 0 CONTRADICTED) showed the
CONFLICT rows were dominated by the extractor, not the reports: `'diluted eps'` "conflicting" at `rice (919.97; **$24.67; +1368.5; | $28` (the raw string carried a
6-char slice of surrounding prose), `'scenario dcf bear' 71.38; 171.38` and `94.96; 194.96` (the label regex consumed the value's leading digit), `'market cap'
**1` (a fragment of `$1,166,000,000,000` — the figure regex stopped at the first comma, so `$28,243,000,000` read as 28), `'stochastic' … rsi **0.0` (`stoch`
matched `stochrsi`), `'rsi' … : 5.8` (a VIF row reusing the label), `'rvol' … ≥ 1.3` (a threshold read as a value), `'insider net' 12; 12m` (a 12-month window
read as 12 million), `'diluted eps' 6.34; 5.24; 1.70` (three quarters, each labelled as such), and `metric_errors: valuation_identity: could not convert string
to float: '1.5286.'` (a `[\d.]+` capture swallowing a sentence-ending period, which silently killed the whole DuPont check). Two identity families were binding
*across producers*: the R-multiple check crossed one tool's `entry` with another's `stop` (the quoted targets are verbatim tool output — `get_swing_set` scales
2R/3R off the structure stop, `get_swing_exits` off the chandelier, `get_tranche_plan` off an averaged entry at 1.8R/3.0R), and the valuation-band check demanded
realized coverage from a band that has none by design (get_expected_move's option-implied ±1σ band; the conformal `get_valuation_band` prints its own coverage).
Now: comma-grouped figures (plus a `T` unit), unit-boundary and R-suffix-aware capture, label-prefix / VIF / threshold / growth-percent / 12-month-window /
period-qualifier guards, table-cell and slash-list pair binding (`| Net Income / Diluted EPS | $28,243,000,000 / $24.67 |` binds 24.67), per-tool scoping for
`t1`/`t2`, a conformal-context gate on the band check, a line-local (spot-price-anchored, multiplier-aware) R-multiple binding, and hardened float captures.
Measured over all 45 archived trees (185 analyst reports): same-metric conflict rows 409 -> 186, metric errors > 0 -> 0, and 0 R-multiple/band claims on the four
2026-09-14 trees (12 before). Every pinned verifier test still passes (10 new cases pin the classes above); the advisory contract is unchanged — the verifier
still never edits a report.
**Web impact**: none structurally — `verify_flags.json` simply carries fewer INTERNAL_CONFLICT claims and no `metric_errors` entries; no key or CLI flag changed.

**The sentiment stem could cite a macro level with no evidence behind it (2026-09-14; SKHY review).** The news analyst gets a deterministic 10-year FRED leaf from
`gather_for_analyst_node` (S11b's declared default under `enable_evidence_symmetry`), but the sentiment analyst binds no tools and pre-fetches a fixed source set,
so it had only recalled macro levels out of headlines: the SKHY 2026-09-14 stem wrote "US 10-year above 5%" with no macro leaf anywhere in its evidence and the
verifier flagged the line UNSUPPORTED (the class pinned by the SKHY 2026-09-09 review loop). Under the same gate the node now fetches
`get_macro_indicators(indicator=10y_treasury, look_back_days=30)` once, journals it as a `get_macro_indicators` leaf under `tool_evidence.sentiment` (same leaf
shape/args_hash as a gatherer leaf, `no_data` when the vendor returns a placeholder), adds it to the prompt as the only quotable macro level, and pins the rule:
a headline that disagrees with the leaf must be reported as disagreeing rather than repeated as fact. Gate off (or a fetch failure) leaves the stem byte-identical
to before.
**Web impact**: additive only — with the gate on, `tool_evidence.json` gains one `get_macro_indicators` leaf under the `sentiment` key (array append), and the
rendered `sentiment.md` may quote the 10-year level with its date. No key, flag or CLI change.

**S11c's mirrored discretionary budget had no operator path (2026-09-13; found measuring the S11 gate).** The
behaviour was implemented in `evidence_gather._journal_executed` but read its allowance from
`config["evidence_symmetry_pairs"]` - a key that was **not declared in `default_config.py` and not env-mappable** -
so the mirror could never activate: nothing was suppressed, and the plan's "S11c" row described a behaviour no run
could reach (the standalone `mirror_discretionary_budget` API was tested but had no caller). Now: the key is declared
(`[]` = inert) and reaches `.env` via `TRADINGAGENTS_EVIDENCE_SYMMETRY_PAIRS`, a JSON list of `{roles, budget}`
specs (any list-valued key accepts a JSON list; malformed JSON raises at startup); the live path and the pair API
share one split rule (`_split_discretionary`) and one suppression-journal helper, so they cannot drift; a pair may
declare an explicit `budget` or leave it out to mirror the smallest discretionary count an already-run partner
recorded; and a forced (S11b) leaf is never suppressed (and no longer consumes the allowance). Measured on the real
path with real journaling: budget 1 -> the surplus calls are dropped from the evidence and written to the tool-call
log as `suppressed` with their args; derived allowance -> mirrors the partner's observed count; gate on with no pair
declared -> byte-identical to a gate-off run; the deterministic gather is unaffected (fundamentals 48 leaves, same
pool, same block with the gate on and a pair declared). Caveat measured: the mirror drops the evidence **leaf** after
the call already executed, so the transcript still carries that result - keep budgets at or above a pair's natural
counts, or the report verifier will flag claims based on a result the evidence file no longer holds.
**Web impact**: none - no JSON shape or CLI flag changes; a suppressed call simply appears as a `suppressed` row in
the per-symbol tool-call log instead of an evidence leaf.

**A launcher's `TRADINGAGENTS_*` environment was silently replaced by `.env` (2026-09-13; found while trying to flip a
gate per run).** `tradingagents/__init__.py` reloaded the whole `.env` with `override=True` to force the three
output-token cap keys (commit `0a0ba1c`) and then restored the caller's values for those three keys only - so every
other key the file declares (~190) was rewritten in `os.environ` at import. Reproduced: exporting
`TRADINGAGENTS_ENABLE_GROWTH_SCORES=false` (or `TRADINGAGENTS_TEMPERATURE=0.99`) left both `os.environ` and
`DEFAULT_CONFIG` holding `.env`'s value, although that block's own comment promised "all other caller exports are
untouched". Why it matters: (a) the round-3 gates were documented as env-flippable, but the only working operator
path was editing `.env`, so a rule-10 flip could not be scoped to one run or one process; (b) any launcher, script or
CI job that exports engine settings had them ignored whenever `.env` also declared them. The force-set is now scoped:
the three cap keys are read out of the files with `dotenv_values` and applied directly (unchanged intent - a low
launcher cap must not starve report turns), every other caller export survives, and a gate can be flipped per run
(`TRADINGAGENTS_ENABLE_X=true py -3.12 batch.py ...`) as well as through `.env`. Tests:
`tests/test_env_overrides.py` (+3; two of them fail against the old block).
**Web impact**: the app spawns the engine with the repo's `.env` in place, so its behaviour is unchanged; a launcher
that exports `TRADINGAGENTS_*` (or a future per-job override) now takes effect instead of being overridden.

**A drafting monologue shipped as the Research Manager's investment plan (2026-09-13; found reviewing
`reports/MU_20260913_220057`).** The RM's structured call missed (`structured output returned no parsed result`), the
free-text fallback returned the model's *private* drafting monologue - 5.6 KB of "why does my decimal become
asterisks" self-correction that re-drafted the same header twice - and `2_research/manager.md` opened with that
monologue ahead of the real plan. It reached every consumer, because the same text is the state's
`investment_plan`: the Trader and Portfolio Manager prompts, the report tree and the memory log all read it as the
plan. None of the existing guards could see it: it is not a stub (5.6 KB of prose), not a truncation
(`_looks_truncated` needs a mid-sentence ending) and not a repetition loop. New in `agents/utils/structured.py`:
`_looks_like_drafting_monologue` flags it, `_salvage_final_draft` keeps the monologue's own final draft when there is
one (free - it recovered the real plan from that same response, so the run's plan was never lost),
`_retry_if_monologue` otherwise re-asks once on the backup model (never the model that just monologued) and finally
emits the explicit "**Decision**: unavailable" notice. Wired into all three free-text chokepoints -
`invoke_structured_or_freetext` (RM / trader / PM), `retry_chain_if_stub` (analyst reports) and
`retry_llm_if_truncated` (bull/bear researchers and the three risk debators) - each writing a
`monologue/<agent>` journal note so the event is diagnosable. The detector thresholds are measured, not guessed:
across the 599 markdown files under `reports/` (2026-09-13) the composition vocabulary matches ONLY that leaked
monologue (31 hits) and the narrow self-correction set never exceeds 1 hit in a clean report.
**Web impact**: none - the guard runs inside the engine before the report tree is written; the app's
`2_research/manager.md` / `tool_evidence.json` readers see the same shapes, except that a monologue run now yields
the real plan (or an explicit unavailable notice) instead of self-talk.

**`scripts/repro_check.py` could not be run as documented (2026-09-13; found while reproducing a report run for
the rule-10 launch).** `py -3.12 scripts/repro_check.py --symbol tsm --runs 3 --workers 1` - its own docstring's
`Usage:` line, and the script the round-3 plan's rule 10 and `docs/AGENT_ONBOARDING.md` both point at for the
gate-flip evidence - died immediately with `ModuleNotFoundError: No module named 'batch'`. The script runs with
`scripts/` as `sys.path[0]` while `batch.py` lives at the repo root, so `from batch import analyze` only resolved
when something else had already put the root on the path (e.g. `py -3.12 -m scripts.repro_check`, or
`PYTHONPATH=.`). It now takes the same
`sys.path.insert(0, str(Path(__file__).resolve().parents[1]))` bootstrap 19 other scripts in `scripts/` already
use. Why it matters: rule 10's gate-flip evidence (the off-run/on-run tree diff) is produced by this script, so
the documented launch command failing at import is the difference between a measured flip and a claimed one -
and it was one reason the earlier report-level attempts produced no tree at all.
**Web impact**: none - `trading_web` does not invoke anything under `scripts/`.

**`get_composite_rank` ranked against the characters of a string, not against peers (2026-09-13;
found while dark-launching the round-3 gates).** `get_company_peers_finnhub` returns TEXT
(`"Peers: NVDA, AVGO, AMD, ..."`) because it is routed through the vendor layer, and the tool did
`peers = [ticker] + list(peer_list)[:8]` - so its peer set was the first eight CHARACTERS of that sentence:
`['P','e','e','r','s',':',' ','N']`. Consequences, measured live on MU 2026-09-11: it ranked the name against
the letters `e/P/r/s` (`peers_ranked: P, e, r, s`, composite 60.00%), and it fetched statements for the
"symbol" `N` (Tiingo 400s in the run log). New `finnhub.peer_symbols()` parses the rendered string (or accepts
already-split iterables, which is what the tests pass), and the tool excludes its own ticker. Measured after the
fix: `peers_ranked: ADI, AMD, AVGO, INTC, MRVL, NVDA, QCOM, TXN`, composite 77.78%, and the S3 quality row it
now feeds renders `quality composite MU: 86/100 (elite); metrics used: accruals, f, gp_a, m, noa, o, z;
coverage 7/7; peers scored 8 of 9` (before the fix that row could only answer `peer set below the floor
(5 < 8 names)` - it burned 9s to do it). A test pins the production shape: a rendered-peer-string monkeypatch
must produce real symbols and must never fetch a single-character ticker.
**Web impact**: the `get_composite_rank` tool card's `peers_ranked` list and `score` change (real peers instead
of characters) - an additive-honesty fix to an existing surface, not a shape change.

**The ten round-3 gates could not be flipped from `.env` (2026-09-13; found while dark-launching them).**
`_apply_env_overrides` only reads names present in `_ENV_OVERRIDES`, and the ten round-3 gates were not in it -
so `TRADINGAGENTS_ENABLE_ALTMAN_VARIANTS=true` was silently ignored, the rule-10 launch procedure had no operator
path, and the `.env.example` block shipped for this round documented ten environment variables that did nothing.
All ten are now mapped (with a test asserting the mapping covers every round-3 gate, that a mapped value flips its
key, and that a typo raises rather than being swallowed). Verified live: `.env` -> `DEFAULT_CONFIG`, one gate at a
time. The round-3 gate-default tests were also environment-coupled - they read the in-process `DEFAULT_CONFIG`,
which is built from the operator's `.env`, so the very dark launch they exist to support failed them; the shipped-
default check now runs in a clean interpreter with no `.env` and no `TRADINGAGENTS_*`, and the mapping test clears
the ambient gate variables first.

**The forced-tool short-circuit never wrapped the real tool node: no journal, no model-pool leaves
(2026-09-13; the QQQI news review).** `evidence_gather.make_short_circuit_tool_node` guarded on
`callable(tool_node)` and returned the node untouched when that was False. LangGraph's `ToolNode` is a Runnable and
NOT callable, so **every production node** came back unwrapped while the unit tests - which pass plain-function
doubles - stayed green. In every run since the feature landed:

- the short-circuit never fired (a re-requested gathered tool could re-hit the vendor);
- `tool_call_log` recorded no calls (there is no `QQQI_tool_calls.jsonl` for the QQQI run);
- `_journal_executed` appended no model-pool leaf - **0 of the 38 archived runs** carries one, although the QQQI news
  analyst demonstrably called `get_macro_indicators` (`10y_treasury` / `fed_funds_rate` / `reverse_repo` / `vix` /
  `cpi`), `get_prediction_markets` (`Fed rate cut`, `recession 2026`) and `get_news_relevance_read`, and the report
  quotes their real outputs verbatim (DGS10 4.95 / 4.68, RRP 5.255B, CPI 334.131, Polymarket 94%).

Cost of the defect: the deterministic macro-authority gate (`report_verifier._macro_authority_gate`) holds every
"10Y / RRP / Polymarket" line to a matching tool leaf, so the QQQI news report's **five** correct,
tool-grounded lines were flagged UNSUPPORTED - the exact false-positive class the recorder was written to kill (the
JPM/GS 2026-09-08 macro block). Adding just those two leaves takes the same report to zero flags.

Fix: a callable node keeps the plain-function wrapper; a Runnable node now gets a `RunnableLambda` that forwards the
config LangGraph injects (a bare `ToolNode.invoke(state)` raises "Missing required config key" outside a graph), and
that wrapper is a `RunnableLambda` SUBCLASS delegating unknown attributes to the ToolNode - LangGraph rejects a plain
proxy object, and the tool-binding contract (one producer per number: four test files read
`graph.tool_nodes[key].tools_by_name`) must keep answering. A node that is neither callable nor a Runnable is still
returned untouched, but that disable is now logged loudly - the silent return is what hid this. Model-pool leaves
also carry the call args (they were empty), so `repro_check --evidence` can diff them.

Verified against the live wiring: the run's own news tool node, driven in a graph with a
`get_macro_indicators(indicator="cpi")` call, executes against FRED, journals `executed / in_model_pool=True` and
appends the leaf with its args.

**`get_catalyst_scale` printed the modal probability 100x too large (2026-09-13).** The fed-watch feed's probability
is already a percent number (86.5) and the reason line formatted it with `:.0%`, so the QQQI leaf read
"modal 8650%". It renders "modal 86.5%" now; the sibling `modal_prob=86.5000` field was always right.

Tests: a real `ToolNode` regression (wrapped, both the short-circuit and executed paths, leaf carries its args), a
loud-disable test, and a catalyst reason assertion that fails on the doubled scale. Web impact: none (no JSON shape,
CLI flag or tool name changed; the web app's Value-tools screen calls the tools directly, outside this node).

**Options horizons read from the wrong label: doubled variance + a moved gamma wall (2026-09-13; the QQQI
market review).** Every yfinance-chain reader parsed an expiry as a 6-digit contract stamp
(`strptime(expiry, "%y%m%d")`), but `Ticker.options` returns ISO dates (`"2026-11-20"`), so the parse failed
silently and all five readers priced the chain at the 30-day default `T = 30/365`:

**(1) `get_variance_premium`** priced a 68-day chain at 30 days. Variance scales ~1/T, so `implied_var` came out
**0.1034** instead of **0.0458** (implied vol 32.2% instead of 21.6%) and the premium read **+0.0928** instead of
**+0.0358** - a 2.6x overstatement of the "rich IV" edge that a report would have quoted as a cheap-vol call. The
leaf now prints the implied/realized VOL beside the variances (the figures are variance, which is why a 21% chain
read as "32% vol"), names the expiry and its day count, and says the ATM-IV tool reads a different expiry.

**(2) `get_gamma_profile` / `get_derivatives_flow`** fed that T to `gex_per_strike`. On the QQQI chain the same
rows give net dealer gamma 3,488,951 with a **55.0** call wall at T=30/365 and 3,355,519 with a **56.0** call wall
at the true 68-day horizon - i.e. the report's headline "doji/shooting-star into the 55.0 call wall" was a T
artifact (the gamma *regime* stayed "long", but walls are strike-ranking reads and a per-strike IV spread makes the
ranking T-sensitive). Both leaves now name the chain and horizon they measured.

**(3) `get_options_iv_read`** labelled its expected move "30d" while multiplying a 68-day ATM IV by sqrt(30/365):
2.7% instead of that chain's 4.1% over 67 days. Its "OI ratio convention" note also claimed the put/call and
call/put ratios were "reciprocals of the same OI universe" - they are not: 0.73 put/call comes from the 2026-11-20
chain while the chain snapshot's 2.51 (call/put 0.40) comes from the nearest 2026-09-18 expiry, so a report that
quoted both was comparing two different books. The note now names each tool's expiry, and the chain snapshot states
that its IVs are strike MEANS (thin wings included) and cannot be compared with an ATM-IV of another expiry.

**(4) `get_parity_screen`** discounted 30 days on a 4-day expiry - the numbers were unaffected only because the
caller passes `r=0`, so the leaf now states the assumption (`r=0, q=0`, last traded prices, no American early
exercise) instead of leaving it implicit; `get_vol_surface_shape` carried the same wrong T with no effect on its
IV-difference outputs.

Root fix: one pure `options_math.expiry_days(label)` that reads ISO dates, 6-digit stamps and 8-digit basic ISO and
returns None (never a guess) for an unreadable label. All five readers take the horizon from it and print the
expiry they used.

Tests: `expiry_days` shapes (ISO / stamp / basic ISO / today / garbage) + an ISO-expiry regression that prices a
flat-25%-vol strip on a 67-day label and fails if a reader returns the 30-day default (correct var 0.0362 vs the
inflated 0.0805) and that every leaf names its expiry + horizon. Web impact: none (leaf text only; no JSON shape,
CLI flag or tool name changed).

**Label-anchored metric values + fund-yield cross-checks (2026-09-13; the QQQI fund review).** A fund run
(`QQQI_20260913_125516`) shipped two numbers that were not numbers, and neither was analyst arithmetic:

**(1) `market_cap: VALUES CONFLICT range=10 .. 2026` was a parsing artifact.** `strategies/metric_reconcile.py`
read the FIRST number in each leaf, so it took the note date (`# Data retrieved on: 2026-09-13`) as
`get_fundamentals`' market cap and the `10DayAverageTradingVolume` label of `get_basic_financials` as 10 - in a
leaf set that carries no market cap at all. The report then quoted that phantom range as its AUM evidence ("I do
not state a single AUM figure"). Values now come from the line that NAMES the metric (`TOOL_VALUE_RE`, per tool:
`Market Cap:` / `- Market cap:` / `marketCapitalization:` / `fair_value=` / `- Last:` / `| Close |`), a tool with
no scalar label (the statement CSVs) contributes nothing, and a multi-vendor metric whose vendors are all silent
renders `NO VALUE IN EVIDENCE ... report it unavailable` instead of a range. The same defect had been
fabricating `market_snapshot` conflicts on stock runs (MU `range=1028 .. 2026`, NXPI `range=223.3 .. 2026`, HPE)
- those are gone, while real vendor conflicts are unchanged (ADBE market cap 99.1B vs 102.26B, MU 1.148T vs
1.161T, ARM D/E 5.62 vs 0.055).

**(2) `Dividend yield: 9.00%` stood five lines above a distribution table paying ~14%.** The vendor field
(yfinance `info['dividendYield'] = 0.09`) is unreconcilable with the SAME vendor's payment record: the trailing
twelve monthly prints sum to 7.649 = 14.02% at the 54.56 reference price, and every rolling 12-payment window
since inception is 13.4-14.0%. Three changes. `report_verifier._dividend_yield_sanity` now also parses fund
**distribution lists** when no "dividend per share" sentence exists, inferring cadence from the printed dates
(26-33 day median gap = monthly, 80-100 = quarterly; an undated list only with an explicit monthly/quarterly
word), and flags an **understated** quote (implied > 1.4x quoted) as well as the existing overstated one (>5x).
`dataflows/y_finance.py::get_fundamentals` cross-checks the field against `Ticker.dividends` TTM and appends a
correction NOTE when the two disagree by >25% (QQQI: 9.00% vs 14.02%). The yield sanity check refuses to emit a
claim whose implied rate exceeds 60% - that is a mis-parsed price, not a yield, and a claim carrying an absurd
number costs more than the missed flag.

Tests: `test_metric_reconcile` +3 (label-anchored extraction, the QQQI ETF no-value case, the MU date-vs-price
case), `test_report_verify` +3 (understated fund yield, cadence inference incl. a quarterly payer NOT annualized
x12, undated monthly list), `test_yfinance_keyless_vendor` +3 (cross-check fires / silent when the record agrees
/ absent without a payment record). Sweeping all 157 analyst reports in `reports/` yields exactly two yield
sanity claims: the pre-existing MU one and the new QQQI one - no false positives. Web impact: none (the
reconcile dict is rendered into the evidence text only; the `tool_evidence.json` shape is unchanged).

**Basket-pinned tests unpinned (2026-09-13).** `test_analysis_tools.py::test_book_tail_risk_computes` and
`test_book_context.py::test_book_tail_risk_reports_which_book_it_measured` asserted `configured basket (8/8
names)` against the live `.env` portfolio, so the Sep-13 basket recalc (8 -> 6 names: SPY, GLD, GOOG, NVDA, NLR,
BAC) failed both for a reason that had nothing to do with the code under test. They now inject their own basket
(3 names / 2 names) like their siblings `test_book_tail_risk_no_series` and the single-name half of the
book-context test - the property under test (the mix names the configured book, not the analyzed ticker) is
unchanged.

**Honest degradation for tools a caller has no position for (2026-09-13; the web app's all-tools run).** The
app's Value tools screen runs any of the 56 value tools on a bare ticker. One such run (`run_value_tools("AAPL",
tools=<all 56>)`, `ok=true`, 42s) produced five answers that were not answers: a pydantic schema dump
(`unavailable: 3 validation errors for get_trailing_exit | entry | Input should be a valid number`), a raw
arithmetic error (`risk-parity alloc unavailable: float division by zero`), a repr'd Python error (`memory
ledger: unavailable ('str' object has no attribute 'get')`), a full stress grid headed `base 0.00` with every
cell `+/-0.00`, and `trade outcome metrics unavailable for AAPL: no valid closes` for a ticker whose close
series was 319 bars long. Each one is a missing input reported as if it were a result, and four of them leaked
implementation text into a user-facing line. All six are fixed at the tool - the absent input now names itself:

**(1) `get_trailing_exit`** took `entry`/`peak`/`current` as required floats, so a caller with no position died
inside the schema. All three are optional now and answer `trailing exit unavailable for X: need entry, peak,
current (...)` naming only the ones actually missing.

**(2) `get_risk_parity_alloc`** divided by a covariance that did not exist. It now filters the book to series
with >= 2 points and refuses fewer than two names: `need return series for 2+ names (got 0 of 0 usable)`.
Together with the web-side book building below, the two-name case computes again.

**(3) `get_ledger_risk_state`** built `TradingMemoryLog(cfg.get("memory_log_path"))` - a *path* where the
constructor takes the config **dict** - so the memory-ledger half of the read always failed with an
AttributeError string. It passes `cfg` now, and the real win-rate/`resolved` line appears.

**(4) `get_stress_grid_read`** rendered a 20-cell table of zeros for a zero base - a computed-looking, entirely
meaningless "robust to a -10% revenue cut" grid. A non-positive or absent base is refused:
`base value missing - pass the base read the revenue/discount shifts act on`.

**(5) `get_prompt_injection_read`** answered `none detected (n=0)` for empty text: a clean bill of health for a
document that was never supplied. Empty text now says `nothing to scan (no text supplied).` - detection itself
is unchanged.

**(6) `get_trade_outcome_metrics`** required an `entry`, and 0 (what the app sent) divided by zero, so the
excursions were discarded and the message blamed the closes ("no valid closes"). The entry is optional and a
missing or non-positive one is named: `need the entry price (MAE/MFE are measured from it; 0 or absent is not a
price)`.

**Web impact (sibling app).** `trading_web` calls all six with empty inputs from its Value tools screen: it now
sends `entry=None`/`base_value=None` instead of `0.0`, and builds `returns_by_name` for `risk_parity_alloc` from
the Ticker box's comma-separated names (`backend/capabilities.py::_returns_by_name`), so the book case computes.
The screen's per-tool "needs ..." markers were reworded to match these messages, and
`trading_web/tests/test_backend.py` pins both the book-building and the None sentinels. No JSON shape or
argument *name* changed: the only wire difference is that a caller may now omit `entry`/`base_value`, and
`get_trailing_exit` accepts omitting all three prices. Six tools still need inputs the screen has no field for
(name=weight pairs, expected excess returns, macro levels, an entry price, text to scan, the
`enable_factor_profile` switch) - they say so in one line instead of failing obscurely, and the app labels them.

**News-report day-count and basis integrity (2026-09-12; NVDA `news.md` review).** An external reviewer validated
`reports/NVDA_20260912_160416/1_analysts/news.md` and found one real error: the report calls the next print
(2026-11-17) "**83 days away**" - twice, prose and summary table - where the analysis date (2026-09-12) is 66
days out. 83 is the gap from the PRIOR print (2026-08-26 -> 2026-11-17), i.e. a right number on the wrong base.
No tool printed it: `get_earnings_calendar` showed the date and estimate with no countdown, `get_catalyst_scale`
prints `fomc Nd out` but only covers the Fed, so the model computed it and nothing checked it. Fixed in both
directions - the number now has a producer, and the class now has a write-time detector.

**(1) The countdown is produced, not computed.** All three earnings-calendar vendors now render the days to the
next print from `curr_date`: `2026-11-17 estimate=2.47 (in 66d)` (yfinance), `| Days out: 66` (Finnhub),
`(in 66d)` (moomoo). Historical prints carry no countdown - they are not catalysts. The news-analyst prompt
gained the matching rule with this precedent.

**(2) The surprise percent states its basis.** NVDA 2026-08-26 shows `estimate=2.09; reported=2.22;
surprise_pct=6.16`, while (2.22-2.09)/2.09 = 6.22%: the percent is the *vendor's*, computed from EPS it does not
expose at full precision, so it cannot reconcile with the 2dp pair printed beside it (every row in that table
shows the same gap). The yfinance calendar header now says so, so a reader does not read a vendor convention as
a slip.

**(3) Detection: a date-count identity at write time.** `report_verifier._days_countdown_identity` recomputes a
day count stated on a line that carries both an ISO date and an explicit `N days out|away|ago|until` and flags a
mismatch beyond +/-1 day (tolerance for the run date vs the prior close). It runs only with an anchor -
`_report_as_of` reads the run date from the report directory name - and returns nothing without one, because a
guessed anchor manufactures findings. `_text_metrics`/`_valuation_identity_checks` take the anchor through, so
`write_report_tree` now records it in `run_card.json["analyst_consistency"]`; replaying the reviewed tree records
`news.md: day count does not follow from its own dates: '83 days out' for 2026-11-17 is 66 days from 2026-09-12`.
Deliberately narrow: a bare "in N days" is NOT matched, because "worst in 30 days" is a lookback - reading it as
a countdown flagged the clean TSM 2026-09-09 tree, and a swept corpus of all 48 report trees yields exactly one
finding (this NVDA one).

Tests: 13 new (6 `test_report_verify.py`, 3 `test_yfinance_keyless_vendor.py`, 2 `test_moomoo_vendor.py`, 1
`test_news_window_contract.py`, 1 `test_reporting.py`) and one extended (the identity fan-out registration now
covers the anchored check). **3981 passed, 5 skipped** on the full suite; ruff clean. Eleven mutations were run against the new
gates and every one bit, each file restored byte-identical (sha256), no-op control green.
Web impact: none - additive text in three vendor strings plus one new advisory run-card key.

**Market-report number, scale and OPEX-label integrity (2026-09-12; NVDA `market.md` review).** An external
reviewer re-derived the arithmetic in `reports/NVDA_20260912_160416/1_analysts/market.md` and found no error in
it; re-deriving the same figures from the run's own logged OHLCV (92 bars) plus the vendor series the tools use
confirmed every one - and exposed four defects that the review could not see, because they live in the tools
rather than in the report's arithmetic. Each is fixed at the source with a regression test.

**(1) A date one week early labelled "in OPEX week" - in the reviewed run itself.** `opex_status` used
`0 <= days_to_expiry <= 6`, which swallows the weekend *before* the expiry week: the run's
`get_opex_read(current_date=2026-09-12)` - a Saturday whose expiry was Friday 2026-09-18 - returned
`in_opex_week: True`, and the market report relayed that label in prose, in the body and in the summary table.
"OPEX week" is the Mon-Fri week that *contains* the expiry, i.e. ISO-week equality. The same weekend leak is
fixed in `post_opex_unwind` (its docstring says Mon/Tue of the fresh week; the code also fired on Sat/Sun), and
the unwind note now names the expiry that *passed* instead of the next one - it read "post-OPEX unwind window
(2026-10-16 passed)" on 2026-09-21.

**(2) A GARCH "long-run vol" of 1,355,146% - two tools, and the sizing path.** `garch11_fit` only guarded
`alpha + beta >= 1.0`, but the NVDA fit landed at `alpha + beta = 1 - 2.7e-13`: under the guard, so
`omega / max(1e-12, 1 - alpha - beta)` turned a floating-point residual into ~7.3e5 and the tool published
`sqrt(VL x 252)` = 1,355,146% annualized. `get_volatility_estimators` printed it a second time, and
`overlays.build_strategy_overlays` consumes that same field as the `volatility_estimator: garch` override, where
the `scale <= 0 -> 1.0` guard would silently *maximise* position size rather than de-risk. An IGARCH fit
(`alpha + beta >= 0.999`) now reports `long_run_vol: None`; both tools render
`n/a (IGARCH fit: alpha+beta=1.000000 >= 0.999, no finite long-run variance)` and keep the conditional vol
(41.06%), and the sizing override falls back to the close-based estimator.

**(3) `var` rendered as a raw fraction beside percents.** `get_tail_risk` printed
`cvar=4.53% var=0.03732170883628583 modified_var=3.42% ...`: a 17-digit fraction on a line whose every sibling is
a percent, i.e. a 100x reading error for anyone comparing them.

**(4) One word, two units in one tool; an unnamed R reference across two.** `get_swing_set` printed
`risk=0.0508` (a fraction of the close) in the structure-stop line and `risk=11.0976` (price units) in the next
line's targets - the report had to convert 0.0508 into 5.08% itself. It now prints `risk=5.08% of close`.
`get_swing_exits` prints 2R/3R targets whose R is measured to the **chandelier** (NVDA: 1R=6.7941), not to
`get_swing_set`'s structure stop (1R=11.0976), and named neither; it now renders
`(R vs chandelier stop 211.4959: 1R=6.7941)` so a report can state which R it quotes. Also labelled: the two ATR
bases are the vendor's Wilder `atr(14)` (6.8421) vs `strategies.size.atr` (simple mean of TR, 7.6672), and the two
Bollinger band pairs differ by SD convention (`get_bollinger_pct_b` = population SD; the vendor pair = sample SD,
sqrt(20/19)=1.026x wider) - the report flagged both discrepancies without being able to name the difference.

Independent re-derivation against the run's own data (all reproduced the tools' printed values): SMA50 212.3562,
close_10_ema 221.3927, EMA20 219.7151, RSI(14) 49.94, MACD 2.6048/3.1119/-0.5071, pivots 219.48/216.96/220.81,
ATR(14) 6.8421 (Wilder) and 7.6672 (simple mean), chandelier 211.4959 = 22-bar high 234.4975 - 3xATR, structure
stop 207.1924 = 10-bar low 214.8596 - 1xATR, 52w distance -7.19% (versus the 52-week high *close* 235.20; the
week's high 236.00 would give -7.50%), mom60 +6.79% (`closes[-60] -> closes[-1]`) and the 0.37 position scale
(target vol 15% / 60d vol 40.28%). The reviewer's 19 arithmetic checks re-derive exactly.

Tests: 10 new (3 `test_derivatives_gamma.py`, 3 `test_strategies_volatility_models.py`, 4
`test_analysis_tools.py`). **3968 passed, 5 skipped** on the full suite; ruff clean. Twelve mutations were run against the new
gates, every one bit, each file restored byte-identical (sha256) and a no-op control stayed green.
Web impact: none - one label flips to False on the 2 calendar days before an expiry week, one value becomes
`None`/`n/a` on an IGARCH fit, and the rest is additive basis text inside tool strings.

**Fundamentals number and label integrity (2026-09-12; NVDA report review).** An external reviewer re-derived
the disputed figures from two NVDA trees (`reports/NVDA_20260912_160416` = R1, `reports/NVDA_20260912_005957`
= R2) against live market data. Seven defects, all fixed at the source, each with a regression test.

**(1) A P/E on annual earnings presented as a current multiple (R1: `P/E 43.90`).**
`strategies/ratios.py::price_to_earnings` divided the current market cap by the **FY2026 ANNUAL** net income
(120.07B → 43.90x) while the same run's TTM basis was 27.63x (Finnhub `epsTTM` 7.9108). The merge that fed it
(`statement_parsing.fetch_ticker`) overwrote up to four vendor payloads per key without recording which period
or vendor won. `fetch_ticker(..., with_provenance=True)` now returns `{key: {source, basis, period}}`,
`statement_parsing.trailing_twelve_months()` is the single producer of a TTM window (full coverage required -
a key with three quarters is reported absent, never as a year), `compute_ratios` prefers the TTM flows, and the
rendered block leads with `- basis: flows TTM (4 quarters ending 2026-07-31); balance sheet 2026-07-31`. The
dead `price` parameter is now the labelled `price / reported EPS` fallback.

**(2) A current ratio that did not match the report's own inputs (R1: `4.6808` beside `$197.41B / $43.02B` =
4.588).** `get_balance_sheet_health` divided the canonical merge's own pair without printing it, so a reader
could not reconcile the tool's number with the statement rows the same report quoted (the run carried three
different current ratios). It now prints all four rows it used plus the basis
(`current_assets=… current_liabilities=… total_debt=… total_equity=…; basis: canonical merged rows`).

**(3) An ROA that contradicted its own DuPont inputs (R1: `ROA TTM 81.41%` vs `0.637 x 0.946` = 60.3%).**
The figure was a verbatim Finnhub passthrough printed beside computed ratios with no basis. Every metric line
in `get_basic_financials_finnhub` now carries its basis and source derived from the vendor key suffix
(`roaTTM (TTM, Finnhub): 81.41%`; an unrecognised key renders `(vendor, basis unknown)` and is never dropped),
and when the payload's own TTM margin and asset turnover imply a materially different ROA an advisory
`# NOTE:` line names both numbers and the implied value.

**(4) A DuPont decomposition labelled "on the latest quarter" over a mixed basis (R1).**
`get_dupont_read` took three bare floats and emitted no period, so the label was prose over a TTM margin and
quarter-end turnover/leverage. `get_dupont_read(ticker, curr_date)` now derives all three legs from ONE
payload and states the period it used; the raw-number form labels the legs caller-supplied and unverified
unless `period=` is passed.

**(5) One period labelled two ways in one report (R2: `2025-07-31` as `Q1 FY26` in the income/balance tables
and `Q2 FY26` in the cash-flow table - the second is right).** Quarter names were LLM-authored because
yfinance emits date-only columns. The new `get_financial_trends(ticker, curr_date)` prints the labelled
quarter-series table (`| Item | <date (FYq)> | … | YoY | QoQ |`), deriving fiscal labels from the vendor's own
annual period ends (and stating so when it cannot), and the prompt requires quoting its cells.

**(6) An inventory "+47% YoY" that was a two-quarter move (R2; the true YoY was +111%).**
Same tool: every delta is rendered as `+47.6% (Q4 FY26 -> Q2 FY27)`, naming both periods, so a six-month change
cannot be read as a year; the prompt pin states the rule and the NVDA case.

**(7) "net debt of $10.9B" that contradicted its own balance sheet (R2: cash+STI 62.47B - total debt 38.35B =
24.12B net CASH).** The number is yfinance's own `Net Debt` row surfaced verbatim, and the guard written for
exactly this case (`y_finance._net_debt_note`, INTU 2026-09-08) **had no test**; its note is absent from every
logged NVDA payload although the call site is present at the run's recorded commit and the function returns
the correction when run on the run's own payload. Mechanism NOT proven - the run card's `commit` field is
itself unreliable after the 2026-09-12 rebuild - so the fix does not depend on the note surviving: four
regression tests now cover the guard (including that the note is the last text in the delivered payload), and
the arithmetic is enforced independently by the verifier check below.

**Detection, not just repair.** The identity family in `agents/utils/report_verifier.py` gains
`_net_debt_identity`, `_current_ratio_identity`, `_roa_consistency` and `_quarter_label_consistency`, and the
family now runs at **write time**: `run_card.json` carries `analyst_consistency`
(`{stem: [{status, claim}]}`), so a tree records its own contradictions instead of depending on the opt-in
`report_verify` pass (neither NVDA tree had a `verify_flags.json`, so nothing checked them at all).
Deliberately the identity family only, not the same-metric-at-two-values scan, which still false-positives on
ordinary prose. Replayed over the two real trees the checks report exactly the reviewer's findings and nothing
else: R2 gets the net-debt sign flip plus both quarter-label defects, R1 the current-ratio and ROA
contradictions.

Tests: 45 new (14 `test_financial_trends.py`, 9 `test_report_verify.py`, 7 `test_finnhub_basis.py`,
4 `test_analysis_tools.py`, 3 `test_reporting.py`, 2 `test_strategies_ratios.py`,
2 `test_statement_parsing.py`, 4 `test_yfinance_keyless_vendor.py`) and one updated where it pinned the
replaced behaviour (the ratio block's no-fabrication sweep now iterates the ratio keys, since `basis` is
metadata). **3958 passed, 5 skipped** on the full suite. Twelve mutations were run against the new gates and every one bit
(including a registration probe: dropping a check from the verifier fan-out leaves its unit test green, so the
fan-out is tested directly); each file was restored byte-identical and a no-op control stayed green.

Web impact: none - the app reads tool names, CLI flags and JSON shapes, and these changes are additive labels
plus one new tool and one new run-card key.

### Fixed

**Number and label integrity in the decision path (2026-09-12; NVDA report comparison).** Comparing the two
NVDA trees for the same session (`reports/NVDA_20260912_005957` vs `NVDA_20260912_160416`) surfaced five
defects where a report or artifact carried a number under a name that did not mean what a reader (or the
downstream execution layer) would assume. All five are fixed at the source, not in the renderer.

**(1) Two numbers called "book drawdown".** The rendered block said `Book drawdown: 7.24% (limit 10.00%)` —
the configured 8-name `risk_basket_*` book, which is what the governor gated on — while
`get_book_tail_risk`/`get_composed_risk_gate` silently defaulted to `weights={ticker: 1.0}` and computed
NVDA's **own** 20.21%, printed as "realized book drawdown". The trader copied that number into its
verification and called `get_risk_gate(dd=20.2%)`, producing a REJECT the composed gate never issued (and
the trader's own tool allow-list could not reach the composed gate to check). Now: one resolver,
`strategies/book_context.py::measured_book_drawdown` (configured basket, one log-return conversion, a
labelled source), used by the graph's governor feed, both tools and the report; the composed gate and the
tail-risk tool print `source=configured basket (n/m names)` or `… alone (no basket configured / configured
basket unresolved)`; the trader can call `get_composed_risk_gate`/`get_book_tail_risk`; the pre-decision
context now carries the measured book drawdown so it need not be invented.

**(2) A caller-supplied state value could decide a gate.** `get_risk_gate` passed the model's
`drawdown_pct` straight into `govern`, so a hypothetical became a house verdict (the 20.2% above). The
drawdown check is no longer a caller input: a `drawdown_pct` is echoed as
`drawdown_whatif=… -> VERDICT (hypothetical, NOT the house verdict)` and never moves the verdict; the
docstring/annotation say so, and the market-analyst guidance points drawdown claims at
`get_composed_risk_gate`.

**(3) Three stops, two ATR bases, one report.** The decision printed `Stop Loss: 207.19` (the trader's
structural stop) while `research_decision.json` and the `Position contract` line carried `207.8845` — and
that contract stop was built from a **close-to-close ATR proxy (5.20)** because the contract call site
never passed the highs/lows that were already in state, while the swing tools used the true ATR (7.6672).
`build_position_contract` now receives the state's real H/L, `PositionContract` records `atr` +
`atr_source` (`h/l` vs `proxy`) and prints them (`stop 207.8845 (from entry 218.29, atr 7.67 (h/l))`), and
`audit_decision_numbers` reconciles the decision's stop with the contract stop at any real difference
(0.05%) instead of 15% — naming both numbers.

**(4) A risk-driven trim read as a setup call.** The action was trim-only because the analyzed name's CVaR
(4.83%) exceeded the 3% budget, yet the trader's own verification said the structure tools (`swing_set
verdict=NO`, trailing exit hold) pointed the other way, and nothing in the artifact said which constraint
bound it. `reporting.py::_binding_constraint` (renamed in
the entry below) now derives `binding_constraint` / `action_basis` (`risk_reduction` vs `setup`) /
`binding_reason` from `risk_context` and `risk_gate` only — never prose — writes them into
`research_decision.json`, and the `Risk Gate (computed)` block renders
`Basis: **risk reduction** (binding: analyzed_name_cvar - 4.83% > 3.00%)`.

**(5) A rebuild could null a real decision.** `scripts/rebuild_complete_report.py` reconstructs state from
markdown and never has `pm_decision`, so it rewrote `research_decision.json` (rating/thesis/rationale →
null) and `run_card.json` (today's config on an old run) — the 2026-09-12 web rebuild did exactly that
across 544 files. `write_report_tree(..., emit_run_artifacts=False)` (used by the rebuild) now leaves the
run-scoped JSON untouched and prints `[rebuild] … preserved …`; `write_research_decision` additionally
refuses to write when there is no `pm_decision` and a contract already exists.

Also in the same pass: the artifact's `data_quality` / `disclosure.sources_used` / `sources_empty` /
`invalidations` are derived from the forced-tool evidence (`ok` vs `error|no_data|timeout` leaves) and the
contract levels by one owner (`reporting.py::_evidence_sources` / `_evidence_data_quality`), replacing
hardcoded `[]`/`"unknown"` placeholders and a regex over the decision prose; `price_caliber` stays null
(no producer reaches report-tree state) with a comment saying so. New fields `binding_gate`,
`action_basis`, `binding_reason` are additive — old artifacts parse unchanged.

Tests: 10 new in `test_book_context.py`, 6 in `test_reporting.py`, 3 in
`test_research_decision_emission.py`, 2 in `test_rebuild_gate_recovery.py`, 1 in
`test_strategies_contract.py` (22 total, 3889 passed on the full suite); 4 existing tests updated where they pinned the replaced behaviour (the 15%
claim-audit tolerance, the book-tail-risk label, and two book-tail-risk fixtures that relied on the
single-name default). Web impact: none — no tool name, CLI flag or JSON key was removed or renamed
(`research_decision.json` gains keys only), and `run_rebuild_report` now re-renders markdown without
touching the JSON contracts.

The engine test suite could no longer exit (2026-09-12; `dataflows/moomoo.py`). A full run printed
`3856 passed … in 512.38s` and then the process sat for ~50 minutes until an external timeout killed
it — a green run that wastes an hour, and a CI job that reads as a failure. An exit probe (a plugin
that dumps all thread stacks if the interpreter is still alive 30s after `pytest_sessionfinish`) named
it exactly: `MainThread` parked in `threading._shutdown`, joining **two non-daemon
`CallbackExecutor` threads** from the Moomoo SDK, both idling in `queue.get()` on the receive loop.

Two SDK facts combine into the leak:

- `CallbackExecutor.__init__` starts its thread with `daemon = SysConfig.ALL_THREAD_DAEMON`, and that
  class default is **False**;
- `open_context_base._close_callback_executor` installs a **fresh** executor *while* closing the old
  one when auto-reconnect is on, so a closed context leaves a thread behind that nothing will stop —
  the two orphaned threads match the two `on_disconnect … reason=CallClose` events in the run log.

`_ensure_ctx` now calls `_daemonise_sdk_threads()` (the SDK's own `SysConfig.set_all_thread_daemon(True)`)
immediately before the first `OpenQuoteContext` is constructed — the flag is read when a thread starts,
so this is the only place it can take effect — and every close path additionally stops the orphaned
executor (`_close_orphan_executor`, best-effort, so a long-lived process does not accumulate one thread
and queue per closed context). `_ensure_ctx` is the only construction site in the repo, so no path
escapes it. Nothing about the connection or the call path changes; daemon threads are simply reaped at
interpreter exit.

Mutation proof: dropping the orphan cleanup from `_bounded_close` -> `test_bounded_close_stops_the_orphan_executor`
fails. Tests: 3 new. No web impact.

### Added

**Round-3 scoring & sentiment formulas land (2026-09-13; S1-S11, every gate default-off).** Ten additive,
deterministic-first computations, each printing its basis and degrading to "unavailable" instead of fabricating a
value: S1 the Altman Z'/Z''/Z''-EM variants plus the distress zones they label (book-equity X4 with the
proxy named, funds and financials unavailable); S2 the Piotroski F-Score's paper basis (the accrual test in ratio
form, LTD+current portion over *average* assets), its published 0-1/8-9 bands and a `deviations` list recording
every substitution; S10 Mohanram's G-Score and Montier's C-Score (a **risk screen**) with industry medians from
the resolved peer universe; S4 a weighted/unweighted news aggregation whose equal-weight default reproduces the
unweighted mean exactly and which dedupes syndicated headlines; S5 the crowd bull/bear ratio + dispersion with
display-only bands; S6 an MSCI-style weighted revision ratio (coverage-guarded, denominator deviation printed,
estimate-change leg says why it is unavailable); S3 a 0-100 winsorised-z composite quality score with stated
coverage and its own quality bands (never `SCORE_BANDS`); S8 score IC/decile/coverage/stability rows; S7 an
exponentially weighted rolling sentiment window with a warm-up guard; S11 paired-role evidence symmetry (a
measured symmetry row, deterministic default args, a mirrored discretionary budget, and a gated argument-plan
call that falls back to the legacy loop with the reason).

New modules `strategies/analyst_revisions.py`, `strategies/peer_universe.py` (ONE resolver for the screener scan
universe, shared by S3 and S10) and `agents/utils/analyst_revision_tools.py`; new rows on the existing
`get_quality_factors`, `get_composite_rank`, `get_news_sentiment_series` / `get_sentiment_computed` tools; new
screener columns G / C / Qual / RevIdx behind `--growth-scores`, `--quality-score`, `--revision-index`.

Also closed while landing: S11b's declared-default table was falling back to itself when a caller omitted it, so
`classify_tool_pools` / `gather_evidence` moved a model-pool tool into the deterministic gather even with the gate
off. Both now default to NO table (gate-on callers pass it), and the ungated split is byte-identical to before
(the re-measurement is what caught it: news 23/4 ungated vs 24/3 gated). S9 (reduced BW-style market sentiment
index) stays unscheduled per the plan's Appendix A - it is annual, one-year-lagged and five of its six proxies are
unavailable, and no market-level consumer with a decision path exists.

A partial G/C sum is **never printed over its full denominator**: with the peer medians absent (the tool
path) or a 5-year series missing, `growth_score` sums only the computable signals, so `1/8` read as Mohanram's
G = 1 when one signal was computable. `signal_summary` now prints `<score> of <k> computed signal(s)
(<n> excluded, not scored 0)` and reserves `x/8` / `x/6` for the complete case (the one that also carries a
band); the tool also collapses the repeated "industry median unavailable" lines into one line naming the
excluded metrics (26 lines -> 20 for a median-less call). `signal_summary` is the single implementation, shared
by the tool row and the screener columns.

The S1/S2 **consumers the plan names** are wired, not just the calculators: `statement_parsing.screen_ticker` now
computes the gated Altman variant + zone and the F-Score band, feeds them into `trap_verdict` as render-only extras
(never changing the severity) and exposes them on the row; `get_earnings_quality` renders `altman_zone=` /
`f_score_band=` when they are present, and the screener's `Trap` column shows the zone beside the level. With the
gates off, the row, the trap verdict and the column are byte-identical to before.

**Web impact**: additive tool-card lines only - `tool_evidence.json` gains the S11 `_symmetry` list (the existing
evidence readers skip a list-valued key) and the tool rows above; no JSON key is removed, renamed or reshaped, and
no CLI flag changes meaning. The screener's new columns are additive table columns.

**The research→execution artifact now declares the executor's v1.1.0 envelope (2026-09-12; plan R1–R5).**
`research_decision.json` was a loose blob the execution layer had to read as 1.0.0, so nothing on the far side
could check provenance, expiry or the body hash. `write_research_decision` now emits
`schema_version: "1.1.0"` with `produced_at`/`expires_at` (the close of the session following
`effective_date`, 20:00 ET, always UTC-offset — a naive stamp is rejected there as `naive_timestamp`), a
`producer` stanza whose `run_id` is the report directory name (stable across a rebuild, so the executor's
inbox key `service:run_id:artifact_sha256` cannot turn a re-emit into a second signal), a UUIDv4
`idempotency_key`, and two self-excluding hashes (`artifact_sha256` over the body, `decision_hash` over the
body minus itself). Field ownership is explicit: this repo sets **no** executor-owned key, and the advisory
label formerly emitted as `binding_gate` is now `binding_constraint` — the executor reserves `binding_gate`
for the label its own gate computes, and the two vocabularies collided on `halt` while a `book_drawdown`
value would have been dead-lettered. `opportunity_score` ships `null`: this repo has no deterministic
producer for it, and an absent score is honest where a stochastic debate mean dressed as a measurement is
not. `risk_context` is an allow-listed advisory passthrough (governor numbers + the gate verdict) that the
executor records and never reads as data. The rules live in one module,
`tradingagents/execution_contract.py`, shared by the emitter and the verifier: `verify_flags.json` gains an
`envelope` block (missing expiry, naive/expired stamps, a body that no longer hashes, a reserved field, an
out-of-range score) counted in the CLI exit code, while legacy 1.0.0 trees stay exempt so no historical tree
is flagged. The executor's published schema is vendored byte-identical at
`contracts/research_decision.v1.schema.json`, and a test diffs it against the sibling repo when that repo is
present — drift fails a test, not a live run. Contract note and acceptance tests T1–T9:
`docs/execution_v1_emitter_plan.md`.
Web impact: none — the artifact's JSON keys are not part of the app's contract, and `binding_gate` was
introduced in this same unpublished batch, so nothing had ever read it.

Tests: 14 new in `test_execution_contract.py` (validation against the vendored contract, both hash recipes,
the session/expiry policy, run-id stability, the reserved-key and allow-list rules, the null score) and 10 in
`test_report_verify.py` (each verifier flag, the legacy exemption, an unreadable artifact, the CLI exit code);
**3913 passed, 5 skipped** on the full suite. Eight mutations were run against the new gates (dropped required
key, naive stamp, constant idempotency key, fabricated score, re-added reserved key, neutered verifier,
removed legacy exemption, file-name run id) — every one bit and every file was restored byte-identical; the
no-op control passed.

Two follow-ups on the debate flags above (2026-09-12; `strategies/debate_capability.py`,
`agents/utils/report_verifier.py`, `scripts/report_verify.py`):

**The matrix now assesses the tier fallback, not only explicit models.** It read only the roles with a
`debate_*_model`, so a role that inherits the quick tier (the `neutral` risk debator always does) was
never checked — a gate with a blind spot for exactly the models it exists to vet. `assess_role_capabilities`
now assesses every requested role on the model it actually runs on: its `debate_*_model`, else
`role_fallback_models` (quick for bull/bear/aggressive/conservative/neutral, deep for judge). An
unresolvable role is still skipped.

**`report_verify.py` flags a degraded tree.** `report_verifier.py::_debate_degradation` re-checks
`run_card.json` + `2_research/structured_debate.md` at tree level (no config, no LLM, no live run), the
payload gains a `debate` block, and the CLI prints `debate DEGRADED` with the reason and returns
non-zero — so a silent fallback is a named failure in `verify_flags.json`, not something to notice in
the prose. `enabled` is null for a tree written before the block existed, and unknown is NOT a
degradation: only a tree that positively claims the structured debate while lacking its evidence is
flagged. Mutation proofs: dropping the fallback branch in `assess_role_capabilities` -> the two
fallback-coverage tests fail; forcing `"degraded": False` in `_debate_degradation` -> the degraded-tree
tests fail; forcing it True -> the disabled-tree test fails. Tests: 8 new (2 capability, 6 verifier).
No web impact (the app does not run the verifier).

Two debate flags that could not do anything now stop the run, and a degraded debate is recorded
(2026-09-12; `strategies/debate_capability.py`, `agents/researchers/structured_debate.py`,
`reporting.py`). A live NVDA run wrote a legacy free-form debate while the config said the structured
one was required, and nothing on disk said so — both flags were decorative:

**`debate_require_capability_matrix` could not fail.** `capability_gate(require=True)` returned
`"ERROR: ..."` strings and the call site *printed* them, inside a bare `except Exception: pass` that
would have swallowed a raise anyway. The module docstring promised "fails CLOSED with a clear error
rather than silently degrading". The decision now lives in
`strategies/debate_capability.py::check_debate_capabilities` (pure, unit-testable): it builds the
role→capability map, stays advisory about unresolvable roles, and raises `DebateCapabilityError` on any
error-tier role. `graph/trading_graph.py` calls it outside any swallowing `try`, so the refusal cannot
be eaten.

**`debate_baseline_fallback` was read by nothing.** It existed in `DEFAULT_CONFIG` and in
`_ENV_OVERRIDES` while no code read it, so flipping it changed nothing. It is now honoured at the three
baseline-fallback sites in `create_debate_l1` (no turns / schema hard breach / L1 hard breach, shared
by the research and risk sections) through one helper, `_baseline_termination`: on (default) keeps the
established R1' degradation to the pre-debate stances; off raises `DebateBaselineFallbackError` naming
the L1 reason.

**A degraded debate is now auditable.** `reporting.py::_run_card_debate` writes a `debate` block into
`run_card.json` (`enabled` / `baseline_fallback` / `require_capability_matrix` / `evidence` /
`degraded` / `terminated` / `reason`) and prints a named stderr line when `enable_debate` is on but
`2_research/structured_debate.md` was not written. It reads the artifacts the run actually wrote rather
than re-deriving the condition, so the record cannot disagree with the tree; `degraded` stays false
when the SD debate was never asked for (the legacy path is not a degradation by default).

Registry rows for both flags (new section 2, later sections renumbered); `.env.example` and
`docs/api_reference.md` now state what flipping each one does. Mutation proofs: `errors = []` in the
helper -> the require test fails; `if False:` in `_baseline_termination` -> 4 fail-closed tests fail;
`"degraded": False` -> the run-card degradation test fails; `research = False` -> the positive run-card
test fails; the old swallow restored at the call site -> the graph-refusal test fails; narrowing the
advisory `except` -> the card-survival test fails. Tests: 14 new (4 capability / 5 fallback in `test_debate_fail_closed.py`, 4 run-card in
`test_reporting.py`, 1 call-site refusal in `test_debate_stream_hermetic.py`). No web impact (the app
never reads `run_card.json`; the new block is additive).

Screener tests are actually offline now (2026-09-12; `tests/test_value_screener.py`). The file's
docstring promised "nothing hits the network" while `vs.main` reached EODHD, Tiingo, Alpha Vantage and
Finnhub for real. It surfaced as a full-suite run that stalled for 35 minutes with no CPU and no
failure; a `faulthandler` dump landed inside `fmp_common.fmp_get`. Three causes stacked:

**A router patch that missed a binding.** `route_to_vendor` is imported *by name* into three modules.
The fixture patched `vs` and `statement_parsing`, but `fmp.normalized_score` imports it inside the
function, so it read the unpatched interface attribute and went live - 18 of 39 tests reached a vendor
(and `statement_parsing.fetch_ticker` calls Finnhub the same way, swallowing the failure, so nothing
said so). All three bindings are now patched from one shared list; dropping any one of them is proven
to fail the suite. The FMP and Finnhub HTTP seams are mocked explicitly.

**No guard, so it could not be noticed.** A non-loopback socket connect is now refused *and recorded*.
Refusing alone is not enough - the vendors degrade via `except Exception`, which would swallow the
guard's error and let a live seam pass quietly (mutation proved it), so the autouse fixture asserts the
record is empty at teardown and names the offending host:port.

**A 600s marker where a hang should have failed.** `pytestmark = pytest.mark.timeout(600)` was there
for "15-60s per test under a slow network"; the thread-based timeout cannot interrupt a blocking socket
read, so the stall simply sat there. With every seam mocked the marker is pure hang-safety: 120s.

Also fixed while gating it: all six run-level screener caches are cleared per test (`_FIN_CACHE`,
`_CASHFLOW_CACHE`, `_RUN_OHLCV_CACHE`, `_RUN_FLOAT_CACHE`, `_BENCHMARK_CACHE`, `_SECTOR_RANK_CACHE`).
`main()` clears these itself, but a direct `_value_dip_scan` call does not, and a stale `(AAPL, date)`
entry was passing one test on live data rather than its own fake.

**A mock that outlived its test.** `_patch_all_routes` patched those same three attributes through
`monkeypatch`, whose teardown runs *after* the autouse fixture's - so it restored the fixture's mock
rather than the real function, and the router stayed patched for every later test. That leak had been
invisible because it never touched `interface` (the binding the vendor-routing tests read); patching
`interface` exposed it as 7 failures in `tests/test_vendor_routing.py`. Both call sites now use the
context-managed helper, which unwinds inside the test, and the duplicate helper is gone.

Numbers: the file 295.93s -> 13.71s, the previously hung test 56.46s -> 2.43s, 39 passed, zero live
hosts. Mutation proofs: dropping the interface binding -> 8 teardown errors naming the hosts; dropping
`statement_parsing`'s -> 2; removing the record -> the guard's own gate test fails. No web impact
(tests only).

Gate registry, and every gate flippable from `.env` (2026-09-11; `docs/gate_registry.md`,
`tests/test_gate_env_toggles.py`). Three audits had found gates that could not fire - a limit compared
to itself, a guard reading a dict key off a string, a stop measured from the wrong entry - and none of
those is visible in code review or in a run. The registry writes each gate's claim down next to the
thing that proves it: switch, what it can block, enforcement site, the test that fires it, and a
Status column.

**The `.env` gap (fixed).** Five gate keys had **no** `_ENV_OVERRIDES` row, so they could not be set
from `.env` at all - including three the governor reads on every decision: `max_position_pct` (the
per-name cap), `risk_max_position_pct` (the book cap) and `sector_cap_limit` (the sector cap), plus
`risk_audit_enabled` and `enable_threshold_gate`. Seven overlay flags (`enable_regime`,
`enable_factors`, `enable_preopen_depth`, the four `enable_sector_*`) had the same gap. All now have
rows; the registry test flips each of the 47 registry keys through the real loader
(`_apply_env_overrides`, the same path `.env` takes) in **both** directions, and asserts unsetting the
variable leaves the default untouched. Five duplicate rows introduced while adding them were removed
(a duplicate key in the dict literal is silently collapsed, so it would have looked fine).

**Eight flags are declared and read by nothing** (`enable_threshold_gate`, `enable_risk_manager`,
`enable_skill_overlays`, `enable_trailing_exit`, `value_dip_regime_gate`, `volume_share_vol_limit`,
`enable_regime`, `enable_factors`). They are now documented as **inert** rather than presented as
gates - `enable_threshold_gate` in particular is named in the decision-hardening spec as if the
PBO/threshold gate were wired, and it is not. `enable_skill_overlays` appears in two docstrings and
nowhere else. The registry test machine-checks the claim in both directions: a `wired` gate must have
a real read site, an `inert` one must have none, so the day one of them gains a reader the suite fails
and forces the row to be corrected. Not fixed here (out of scope): wiring them is a feature decision,
not a documentation one.

**Documentation.** `docs/gate_registry.md` (decision gates, the numeric limits they read, the inert
flags, the always-on integrity checks, and the rule for adding a gate);
`docs/api_reference.md` §1.1 now carries the missing rows and points at the registry; `.env.example`
gains a gate block - 25 entries that were undocumented there - marking the inert ones in place so an
operator does not trust a switch that does nothing. 5 gates, 4 mutations.

### Added

Round-2 quant formula additions: eight deterministic reads, their agent tools, and the prompt
rules that make the agents cite them (2026-09-11; `docs/design_quant_formulas_research_round2.md`,
plan `docs/implementation_plan_quant_formula_additions.md`). The round-1 scan
(`docs/design_quant_formulas_research.md`, 2026-09-05) had largely landed since - variance ratio,
CUSUM/EWMA, permutation entropy, Ohlson/Zmijewski, Dechow-Dichev, Taylor rule, MAX/IVOL,
Almgren-Chriss + TWAP/VWAP/POV, vol-target scaling, Cornish-Fisher/Kappa/Burke/ruin - so this round
first records that ledger and then adds only what was still absent and fit the book's style
(value-dip swing on daily bars, a gated CVaR/drawdown book, an LLM path whose claims must be
checkable). Every flag defaults to **False** and every tool returns a DISABLED sentinel when off,
so a run's artefacts cannot change silently. **Web impact:** the screener row gains two
informational keys (`gp_a`, `noa`, plus their `*_classification`) - additive, and the watchlist
markdown gains the matching columns; the app's `run_screener` result envelope passes rows through,
so nothing it reads is reshaped. Tool JSON shapes it consumes are untouched.

**Q1 quote-free spread floor** (N1). `strategies/liquidity_risk.py`: `corwin_schultz`,
`abdi_ranaldo`, `spread_estimate` (median of both, `basis` names which survived) over the daily
high/low the engine already fetches - the usable estimate where no quoted spread exists (mid-caps,
HK names, sparse bars). The published negative-correction case returns `None` (never clamped to 0).
`strategies/execution_schedule.py`: `default_temp_impact(price, spread)` = half-spread in price
units normalised by the documented 1e6-share reference clip, used by `almgren_chriss` **only** when
the caller passed no `temp_impact` (explicit inputs still win). Folded into `get_liquidity_risk` as
a `spread_estimate=` line (labelled a FLOOR, not a quote) and exposed as `get_spread_estimate`
(market). 12 gates, 3 mutations.

**Q2 book sizing under the budget** (N5, absorbing round-1 C4). `strategies/book_risk.py`:
`min_cvar_weights` (Rockafellar-Uryasev sample-average LP, fully-invested long-only with the
per-name cap and a `max_delta` bound against the current book, `binding` names the constraint that
binds) and `copula_scenarios` (t/Clayton/Gaussian/independent joint-tail scenarios in place of the
single fixed -10% shock, deterministic from a seed). `risk_governor.govern`/`build_risk_snapshot`
take an optional, purely additive `sizing` mapping; the PASS/WARN/REJECT logic is untouched in
every branch and existing callers get byte-identical output. The gate could previously only say
REJECT; this is the sizing remedy. Exposed as `get_book_risk_budget` (risk debators). 16 gates,
4 mutations. The LP is infeasible when `cap * names < 1` and says so (`None`) rather than
producing weights.

**Q3 conformal valuation bands** (N2). New `strategies/conformal.py`: `calibrate`,
`quantile_band`, `rolling_band` (proper-training/calibration split, `realized_coverage` computed
on the calibration window, `min_n` floor). The guarantee is marginal and only under
exchangeability, so the realized coverage is always rendered beside the nominal level; a band
without it is a defect, not a display choice. Exposed as `get_valuation_band` (fundamentals),
which names its prerequisite (model-vs-realized pairs at
`<results_dir>/<TICKER>/valuation_pairs.jsonl`) and leaves a point value unbanded rather than
inventing an interval. 17 gates, 5 mutations.

**Q4 gross profitability + net operating assets** (N3/N4). `dataflows/quantitative_scores.py`:
`gross_profitability` (GP/A, Novy-Marx 2013) and `net_operating_assets` (NOA, Hirshleifer et al.
2004), both `None` when COGS or the prior-year balance sheet is missing - never substituted.
Screen rows carry the values beside `piotroski_f_score` and the screener renders the columns; no
existing score, rank or filter reads them (proven by a gate). Exposed as `get_quality_factors`
(fundamentals, no flag - informational). 8 gates, 2 mutations.

**Q5 overnight-vs-intraday decomposition** (N8). `strategies/market_session.py`:
`decompose_returns` (intraday `ln(C/O)`, overnight `ln(O/C_prev)`, intraday share of variance) plus
a text renderer. Says WHICH leg carried a move, never why; ragged/missing opens and zero variance
return `None`. Exposed as `get_return_decomposition` (market). 8 gates, 3 mutations.

**Q6 disclosure text factors** (N6). New `strategies/text_factors.py`: `lm_tone` (reduced
Loughran-McDonald-style dictionary, version-tagged, counts always reported; a zero-hit passage is
`zero_hits` with `tone=None`, never neutral), `readability` (Flesch ease / FK grade / fog) and
`divergence` (tone and complexity gaps kept separate because the 2025 evidence treats their
persistence differently). Exposed as `get_disclosure_tone` (news). The report verifier gains a
matching text-only family `tone_claim_conflict`: a disclosure written up as confident over a
negative cited tone (or over a zero-hit read) is an INTERNAL_CONFLICT. 6 + 5 gates, 4 + 4
mutations.

**Q7 White Reality Check / Hansen SPA** (N7). `strategies/evaluate.py`: `reality_check` and `spa`
over a candidate universe, stationary block bootstrap, deterministic from a seed; `None` below the
sample floors. `alpha_zoo.bench_zoo` gains keyword-only `reality_check=False` adding exactly one
row key when enabled - the default record's key set is unchanged (asserted). No agent surface:
this scores a factor universe, not a symbol view. 12 gates, 4 mutations.

**Q8 Bayesian online changepoint detection** (N9). `strategies/regime.py`: `bocpd`
(Adams-Mackay run-length posterior, Normal-Inverse-Gamma conjugate, standardized causally on the
warmup window, `shift = zero_run_prob >= BOCPD_SHIFT_THRESHOLD`), an OPTIONAL complement to the
landed CUSUM/EWMA read - its docstring records that a `shift=True` read invalidates the
window-based statistics (Hurst / variance-ratio / half-life) for the NEXT read. Appended as an
opt-in line inside `get_shift_detection` (market); the existing CUSUM/EWMA outputs are pinned
unchanged in the tests. 10 gates, 3 mutations.

**Verifier (Q3 + Q6 hooks).** Two text-only families joined `_text_metrics`, each isolated so a
parser bug cannot erase the payload: `valuation_band_conflict` (a band quoted without realized
coverage, coverage far below nominal, or an INSIDE/OUTSIDE verdict that contradicts the band
bounds) and `tone_claim_conflict`.

**Wiring.** Six tools live in `agents/utils/quant_formula_tools.py`; `get_spread_estimate` and
`get_return_decomposition` bind to the market analyst, `get_quality_factors` and
`get_valuation_band` to fundamentals, `get_disclosure_tone` to news, `get_book_risk_budget` to the
risk debators. Each analyst prompt gained the matching "cite before the claim" rule, and
`docs/api_reference.md` records the tools and the six config keys; the tool table is
machine-checked (`tests/test_doc_binding_claims.py`).

### Fixed

Batch pre-market re-check moved into `analyze()`, so the CLI and the web app write the same artefacts (2026-09-11; audit `docs/implementation_plan_web_app_defects.md` W-P2-18). The opt-in same-night step (`_batch_pre_market_check`, which writes `pre_market_review_<trade_date>.md` next to the report) lived in `batch.main()`'s `as_completed` loop. **Web impact:** `trading_web`'s `run_batch` calls `batch.analyze` in-process and never goes through `main()`, so with `enable_pre_market_review` on the CLI wrote `pre_market_review_<date>.md` for every symbol while the web job wrote none — the same job produced different artefacts depending on which entry point ran it, and a web-run symbol read as reviewed with no review file behind it. The call now sits in `analyze()` immediately after `ta.save_reports(...)`, under the same `DEFAULT_CONFIG.get("enable_pre_market_review")` guard and with the same best-effort semantics; the `main()` copy is gone so exactly **one** call site remains (leaving both would have written the review twice per symbol). CLI-visible behaviour is otherwise unchanged — identical argument values (`symbol`, `report_dir`, and `analyze`'s own `trade_date`, which is `args.date` on the CLI path). Tests: `tests/test_batch_pre_market_parity.py` +3 (analyze calls the re-check once with `(symbol, report_dir, trade_date)`; flag off → zero calls; `main()` with `analyze` stubbed → zero calls, proving the loop no longer runs it).

The moomoo SDK's two unbounded interactions are now bounded, and every close path is bounded too (2026-09-11; prompted by the web app's 70 h zombie job). **Web impact:** `trading_web`'s `run_batch`/`run_value_tools` run in-process, so an unbounded SDK wait parks a pool worker and the job row stays `running` with no error — the live row had no error text, no audit row and no frame at all. **(1) Context creation**: `_ensure_ctx` now runs `OpenQuoteContext(...)` on a daemon thread joined with `moomoo_init_timeout` (default 5 s) and raises the typed `MoomooNotConfiguredError` when the handshake never completes — a reachable-but-wedged OpenD used to freeze the caller for the life of the process. **(2) The timeout path**: `_sdk_call`'s expiry branch used to call `_close_ctx()` → `ctx.close()`, which joins the SDK's receive loop and can block forever *precisely when that loop is dead*, so the call never raised and nothing recorded an error — the exact signature of the 70 h row; it now uses the bounded close. **(3)** `_close_ctx`, the connection-cap eviction and `_close_all_ctxs` all go through one `_bounded_close` helper, and the eviction closes its victims **outside** `_ctx_lock` (holding the registry lock across a blocking close froze every other thread's context work). Field evidence from the client log on the zombie's day (`%APPDATA%/com.moomoo.OpenD/Log/py_2026_09_08.log`): 858 `on_connect` vs 717 `on_disconnect` across 29 processes — i.e. 141 contexts opened and never closed, while no `KeepAlive`/`Lock expired`/`refused` line appears, so the freeze signature is the missing close, not a wedged OpenD. Tests: `tests/test_moomoo_conn_cap.py` +4 (a blocking constructor still raises on time, the timeout path returns despite a hung close, `_close_ctx` is bounded and forgets the handle, eviction does not hold the registry lock), `tests/test_moomoo_vendor.py::MoomooSdkCallTimeoutTests::test_timeout_closes_context` re-pointed at the context (it asserted the old helper call). Each proven failing under a targeted mutation (4).


Two seams the sibling web app (`trading_web`) consumes, with the **web impact stated** (the cross-repo rule: an engine change that removes, renames or reshapes something the app consumes must say so here). **(1)** `scripts/value_screener.py::_fetch_ohlcv` parsed `Open` out of the vendor CSV and then dropped it from the returned payload, so no consumer of `ohlcv["opens"]` ever got one — while the alpaca branch returned them, i.e. the two paths disagreed on the shape of the same seam. **Web impact:** `GET /api/history/ohlcv` builds its bars from `ohlcv["opens"]`, so the price chart drew a candle with no open for every bar; the app now also labels a genuinely missing column (`fields_unavailable: ["open"]`) instead of emitting a silent null. Test: `tests/test_v2_v5_wiring.py::test_fetch_ohlcv_returns_opens_from_the_vendor_chain` (Open deliberately differs from Close, so it cannot pass by accident). **(2)** `dataflows/moomoo.py::close_all_contexts(timeout=3.0)` is now public — the daemon-thread close `_close_all_ctxs` already implemented, exposed rather than duplicated. **Web impact:** the SDK's receive-loop threads are non-daemon and end only through its own close or a hard timeout, so a server that ran an in-process capability (`run_batch` / `run_value_tools`) could not exit, and anything reading its stdout waited for a timeout instead of the real end of the run; `trading_web` now calls it from `jobs.shutdown()` and from its test suite's session-end fixture. Test: `tests/test_moomoo_conn_cap.py::test_public_close_all_contexts_delegates`.

Decision-block honesty: which CVaR leg blocks, and the entry a contract stop is measured from (2026-09-11; GOOG risk/decision fact-check). The engine renders a `### Risk Gate (computed)` block into `4_risk/*.md`, `5_portfolio/decision.md` and `complete_report.md` (`reporting.py::_risk_gate_block`). Two defects in it, both visible in the 2026-09-11 GOOG tree: **(1)** `Portfolio (book) CVaR: 1.21% — this fed the gate` was emitted **unconditionally**, so the book leg (1.21% against a 3.00% budget) read as the operative constraint while the **name** leg (4.12% against the same budget) was what actually blocked new risk — the Portfolio Manager had to contradict the header in prose ("so it is the name-level gate, not the book, doing the blocking"); each leg now carries its budget and only a breaching leg claims the gate (`— over budget: blocks NEW risk in this name` / `— funds the portfolio gate`), and neither claims anything when no budget is configured. The drawdown line received exactly this treatment after the IREN 2026-09-10 review — CVaR was the unfixed sibling. **(2)** `Position contract: size 1.4%, stop 323.5084` printed a stop with **no anchor**, so it could not be reconciled with the trader's own `Stop Loss: 335.1665` or the report's spot 336.25 — a document with two unexplained stops; the contract was anchored on the 330.39 close (`stop = entry × (1 − risk_per_trade / risk_part) = 330.39 × (1 − 0.01/0.480) = 323.5084`, exact), and `PositionContract` now carries `entry_price` and renders `stop 323.5084 (from entry 330.39)` through a single `summary()`. Tests: `tests/test_reporting.py` +1 and its both-cvars test corrected to the new contract (the old assertion pinned the misattribution), `tests/test_strategies_contract.py` +1, each proven failing under a targeted mutation.
The report verifier could not run at all — fixed, and made non-fatal (2026-09-11; GOOG news.md fact-check). Running `scripts/report_verify.py` against a real tree raised `ValueError: could not convert string to float: ''` out of `_pe_basis_conflict` (`report_verifier.py:787`) and **lost the entire payload**: `sentiment.md` writes "sub-30 **P/E,** cheap vs Costco/Meta", the number-capture family `([\d,]+…)` matches a **comma-only** capture, `float(",".replace(",", ""))` is `float("")`, and the exception escaped `verify_report_dir` — so `verify_flags.json` was never written. Impact, measured: **5 of 35 report trees have a `verify_flags.json`, all from 2026-09-08/09**; every later tree (including the GOOG one) had none, and both `batch.py`'s `--verify` step and the web app's VERIFY capability degraded to "no flags" (the web app reports `verify_error`) instead of failing loudly. Fix: every `[\d,]+`-family capture across the verifier (17) and `strategies/metric_reconcile.py` (1) now requires a digit (`(\d[\d,]*…)`), and the metric layer is isolated in a new `_text_metrics(report_text) -> (claims, errors)` used by `verify_report_dir`, which runs each family in its own try/except and records failures in the payload's ``metric_errors`` (logged at WARNING) — one parser bug can no longer delete the whole gate, and it cannot do it silently. Re-run on the GOOG tree: all four sections verified, `verify_flags.json` written for the first time. Tests: `tests/test_report_verify.py` +3 (the comma-only capture parses to nothing, a report tree containing that prose still yields a payload, a deliberately failing metric is recorded while the section entry survives), each proven failing under a targeted mutation. **Known limit left in place (see below):** the flags it now produces include false positives, because model-called tool results are not recorded in `tool_evidence.json`.
One base, two readings — each with its own name (2026-09-11; GOOG market.md fact-check). `strategies/value_dip.py::support_structure` computed `dist_base = (price - base_low)/price` (drawdown to the base) and `dist_sma = (price - sma200)/sma200` (% above the level) **in the same dict, under one field family** (`distance_to_base_pct` / `distance_to_sma200_pct`). So the exported "distance to base" did not reproduce from the convention every sibling field uses — 19.4% vs 24.0% above the 271.1956 base low on GOOG — and the verdict prose rendered it as "close 19.4% above the multi-month base low", which is a **wrong sentence** (the price was 24.0% above it). It also propagated: the market note's `distance_to_base=19.4%` is harvested as a debate **ground-truth registry key**, so `bear.md`/the risk debators quoted "Distance to base (%) = 19.4". Fix: each name now carries exactly one convention — ``distance_to_base_pct = (price - base_low)/base_low`` (how far ABOVE the base low, matching `distance_to_sma200_pct` and the tool's own prose) and a newly exported ``base_depth_pct = (price - base_low)/price`` (room DOWN to the base — the reading the verdict's `<15%` depth test has always used, i.e. the old number, now named for what it is). Both are rendered in the `get_support_structure` leaf (`distance_to_base=… base_depth=…`) so an analyst or debater can cite the reading it means instead of reverse-engineering the denominator, and the prose is formatted from the rounded export so the sentence and the field can never disagree by a rounding step. **Semantics change to note:** the registry key `distance_to_base` now carries the level reading (GOOG: 24.0%, not 19.4%) and the downside reading has its own key `base_depth`; no test or doc pinned the old value. Test: `tests/test_strategies_value_dip.py::test_support_structure_separates_base_distance_from_base_depth` (both formulas, the two readings differ, the prose matches `distance_to_base_pct`), proven failing under three targeted mutations (revert to the depth formula, drop the export, drop the rounding).
Forming-bar price basis now reaches every analyst (2026-09-11; GOOG fact-check follow-up). The fundamentals report compared a **forming intraday close** ($336.37, 2026-09-11) against intrinsic value, a PT upside and a 200-day SMA (+0.4%) and never said it was provisional — while the market section of the *same report* flagged that bar provisional. It could not know: `get_verified_market_snapshot` is a market-toolset tool, so the fundamentals evidence has no snapshot leaf at all. The stakes are not cosmetic — on the prior settled close ($330.39) the price sat **below** that SMA (−1.4%), so the structural read flips sign at the close, and the two options were "label the basis" or "use the last settled close". Chosen: **label it** — using a stale close would fork the price across sections (market/regime/value-dip/tranche all compute on the run snapshot) and manufacture exactly the dual-value conflict this repo's validators exist to catch. **Fix:** the run-OHLCV loader (`analysis_tools._ohlcv`, the one series every price-derived tool shares) is now the single producer of the run's `(as-of date, latest close)` (`price_consistency.set_price_basis`), and `evidence_gather._render_evidence` renders it as a **Reference price** line above the evidence leaves — `336.37 (2026-09-11, FORMING intraday bar - provisional: its close and every price-derived figure (margin of safety, DCF-vs-market, PT upside, SMA/EMA distance) are provisional until the session closes…)`, or `(… settled close)`, or nothing at all when the series never loaded (no analyst claims a basis it does not have). The fundamentals prompt gains a REFERENCE-PRICE BASIS rule: state the basis on every price-derived line, treat a forming-bar ratio as provisional, and say "basis unavailable" rather than assuming a settled close. No extra vendor call — the loader already fetches the series. Tests: `tests/test_price_consistency.py` +6 (set/read, forming label, settled label, unknown → "", cache clear, the loader records it), `tests/test_evidence_gather.py` +1 (the block carries the line, and claims none when no basis is recorded), `tests/test_analyst_evidence_wiring.py` +1 (the rule reaches the rendered prompt) — each proven failing under a targeted mutation of the fix.
Cap-forced terminal turn, corrected: the model was re-calling tools, not burning its budget (2026-09-11; correction to the entry below). The journal added by the entry below caught the real mechanism on its first two production hits (13:43:59 and 13:44:59, both `finalize_messages/News Analyst`): `finish_reason="tool_calls"` with 467/391 output tokens and 45/90 reasoning tokens — nowhere near the cap. The forced terminal turn was answered with **another tool call**, whose content is empty, so "the model burned its output budget before writing" (the reader-facing notice, and this file's own root-cause claim) was wrong for every production occurrence; the measured burn (16k cap → `finish_reason="length"` at exactly 16000, 32k → natural finish) is real but was not what happened. `tool_choice="none"` is **not** honored by the OpenRouter relay (measured: the model still returned `tool_calls`), so the fix is structural: the market/news/fundamentals nodes and the risk-debator loop now build a **tool-less twin** (`prompt | llm`, degrading to None when the model object is not runnable) and `finalize_messages` runs the terminal turn — and both repair attempts, backup first — on it, so the model cannot answer with tools at all. The notice is now **cause-aware** (`_EMPTY_TURN_REASONS`): `tool_calls` → "kept requesting tools instead of writing", `length` → "burned its output budget before writing", anything else → "produced no report text". Tests: `tests/test_tool_round_cap.py` +3 (terminal turn runs on the tool-less chain, repairs prefer the plain pair, the notice names the reported cause), each proven failing under a targeted mutation; the market-node cap test now models `prompt | llm` (`llm.return_value`). Both production hits were repaired by the doubled-cap repair loop (repair `finish_reason="stop"`, 5509/4227 output tokens), so no report was lost.

Fact-check rules for two GOOG 2026-09-11 claims (2026-09-11; user-verified against public coverage). **Non-operating gain substance:** the feed's `Gain On Sale Of Security` row ($98.839B) is the vendor's *name* for what coverage describes as an **unrealized mark-to-market** on equity stakes — the report's label implied a cash-realizing sale the leaves never evidence, while the quality-of-earnings read hinged on it being non-cash. The fundamentals prompt now has a NON-OPERATING GAIN SUBSTANCE rule: state the amount and that the vendor flags it unusual, say whether the feed establishes realized vs unrealized (and when it does not, say so), never write "proceeds"/"sold"/"cashed in" that no leaf evidences. **Normalized-EPS provenance:** the feed's `Normalized Income` ($32,232,249,000 → ~$2.62 EPS, the pretax gain tax-effected at ~19%) is the vendor's normalization, not the Street's adjusted basis (~$2.85 against a $2.8991 consensus), so the report's "roughly in-line/slightly below" compared across bases. The prompt now has a NORMALIZED-EPS PROVENANCE rule: label the figure as the vendor's normalization, give the add-back and implied tax treatment when the leaves allow, and mark any vendor-normalized-vs-consensus comparison as cross-basis. Gate: `tests/test_analyst_evidence_wiring.py::test_fundamentals_prompt_states_gain_substance_and_normalized_provenance` asserts both rules reach the rendered prompt (proven failing when either rule text is removed).

Empty cap-forced terminal turn: repaired with a doubled output budget, and journaled (2026-09-11). A live GOOG news run replaced the news report with `**Report unavailable** - the analyst's cap-forced terminal turn returned empty content (the model burned its output budget before writing)`, and nothing else was recorded anywhere: the empty turn raises nothing, so no failure-journal entry existed, and the analyst's own report path only logged two bare warnings. **Root cause class:** reasoning tokens share `max_tokens`, so a reasoning model can spend the entire output budget on hidden reasoning and emit no text — and the old repair re-asked the *same* question with the *same* cap on the *same* chain, so a deterministic burn reproduced. Measured on the live config (deepseek-v4.1-flash, `reasoning_effort=high`, the 44k-token GOOG evidence context): at the configured 16000 cap the terminal turn stopped at exactly 16000 output tokens with `finish_reason="length"`; the same input at 32000 finished naturally (19696 output tokens, 6691 of them reasoning). **Fix:** `finalize_messages` now repairs an empty terminal turn on the **backup chain first, then the primary**, granting the repair `2 × max_output_tokens_quick` (`_terminal_turn_max_tokens`) through a per-call `max_tokens` override, and only then emits the notice; an exception from the backup (e.g. a model that rejects a tool-bearing history) no longer loses the repair. `finalize_messages` takes `agent_name` (wired from the market/news/fundamentals nodes and the risk-debator loop) for the log lines and the new entry. **Forensics:** new `journal_llm_note` in `llm_failure_journal` writes a completion-less entry — stage `finalize_messages/<role>`, `finish_reason`, the output/reasoning/input token split, the raised cap and every repair outcome — so the next notice names its model and token split. **Defect class fixed with it:** every response-content extraction in `structured.py` (six sites) went through `hasattr(x, "content")` and passed the result to `.strip()`, so a relay returning content as typed blocks raised inside the retry path and degraded a real report to the notice; all of them now use the single `llm_clients.base_client.content_to_text`, which `normalize_content` also delegates to. **Test hygiene:** `FailureLog/` held 381 entries written by the *test suite* (fake `_LLM` doubles, the `structured/t` stage) because the journal and tool-call-log dirs resolve from the developer's `.env`; `conftest` now redirects both to a per-test tmp dir, so the one forensic trail a live failure is diagnosed from is no longer polluted by tests. Tests: `tests/test_tool_round_cap.py` +6 (raised-cap kwarg, primary fallback, backup exception, forensic entry fields, block-shaped content, cap helper), each proven failing under a targeted mutation of the fix, and the pre-existing still-empty case updated to the two-attempt contract.

Documents synced to the code (2026-09-11). `docs/api_reference.md` and `docs/design_risk_calculations_agent_wiring.md` now show the **reshaped signatures** (`get_pair_risk(ticker_x, ticker_y, window?, maxlag?)`, `get_vif_read(ticker, factors, window?)`), and the wiring design doc's four false surface cells are corrected (`get_fixed_risk_size` → risk debators / trader, `get_vol_cones` and `get_regime_gate_read` → risk debators, `get_trade_excursions` → declared) with a note that the machine-checked contract is the api_reference table; `tests/test_doc_binding_claims.py` now also fails when a hand-kept table names a tool that no longer exists. The tree docs learn `agents/toolsets.py` (the single source of bound toolsets, bind == execute) and `agents/arbiters/`, and drop the deleted `strategies/debate_context.py`; `docs/developer/02-graph-workflow.md` repairs the dangling computed-context item and documents the **pre-graph precompute** (the single producer the Portfolio Manager reads before deciding), with `04-strategies.md` gaining the same in its strategies→graph section. README, `Strategies/index.md` and the V5 plan record that the computed-context snippets were removed, and the binding plan's §2 counts are now 207 `@tool` functions / 196 callable / 11 declared.

Context A/B harness, and what it measured (2026-09-11). New `scripts/context_ab.py` answers "does sending more computed context make the agent more accurate?" with two paired experiments scored per item and reported with an exact McNemar test plus the cost side (tools presented / characters of context): **(1) tool selection** with the full surface vs a shortlist, where the items are (claim, tool) pairs drawn from the tools' own schema text and the question never names the answer; **(2) read ablation**, where the injected block is a real render (`trade_plan.measured_inputs` + `build_trade_plan`, `build_risk_snapshot`) and every expected number is parsed back out of that render, so the harness cannot drift from the card the agents read. Producers are injected (hermetic by default, same shape as `scripts/debate_ab_harness.py`); `--demo` checks the plumbing and `--live` runs the repo's own LLM client, recording failed calls instead of scoring them as misses. Hermetic tests: `tests/test_context_ab.py`. **Measured live** (openrouter/deepseek-v4.1-flash, 12 tool items / 11 read items): the injected computed block raised answer accuracy from **0.000 to 0.909** (b=10, c=0, p=0.0020), with 2 answers inventing figures when it was absent — a computed number the model cannot derive is decisive. Tool selection did **not** degrade with the larger surface on this sample: full surface 1.000 vs shortlist 0.917 (b=0, c=1, p=1.000, n=12 — underpowered, and a same-surface shortlist is a harder discrimination task than the full list), so tool-count overload is, at this scale, a cost/latency question rather than a demonstrated accuracy one.

Declarations rewritten and the last dead tool deleted (2026-09-11; plan: `docs/implementation_plan_calc_agent_binding.md`, W5). **`TOOL_LEGACY_BINDING` now holds 11 entries, each naming either the bound tool that covers the same claim or the real consumer of the read** — the "no code/test consumer" entries are gone, so a declared tool states what it is for. **`get_thesis_evidence_matrix` is deleted** (the tool plus its `agent_utils` export and its `api_reference` row): it duplicated live machinery — `get_debate_claims_verdict`, the in-node deterministic HARD BREACH and the report-level grounded-claim gate — and asked the model to author the JSON it then checked, which is the wrong shape for a guard. The underlying `strategies/integrity_tools.thesis_evidence_matrix` calc stays (its behaviour tests are the only coverage of the matrix logic) and it is no longer reachable from any agent surface. `get_prompt_injection_read` stays declared: by the time an LLM can call it the text is already in context, so its home is the ingestion layer, not a tool.

Prompt guidance completed, and the debt list is empty (2026-09-11; plan: `docs/implementation_plan_calc_agent_binding.md`, W3). **All 28 audited trigger gaps are closed** (10 market, 8 news, 9 fundamentals, 1 debator): every bound tool now carries a clause saying when it applies ("Cite ... before any ... claim"), including a single clause that covers the six news source tools they shared a sentence with and the `get_merton_distance` / `get_trade_outcome_metrics` additions to the shared risk-debator line. The trigger gate's `PENDING` map is now empty, and it still fails if a bound tool loses its trigger, so this cannot quietly regress. **Two prompt defects fixed:** the news prompt said "three computed-analysis tools" while listing more (now "several"), and the fundamentals prompt no longer emits the ETF tooling paragraph on a company run — that text only applies to the ETF path, which already carries `_ETF_SYSTEM_TAIL` containing the same guidance. The market prompt grew by ~14 short clauses and stays inside the budget gate's ceilings.

Tool binds the model can actually drive (2026-09-11; plan: `docs/implementation_plan_calc_agent_binding.md`, W2 — the four binds from §4 plus one latent defect). **`get_vif_read`** no longer takes a dict of indicator series (a call meant re-typing 60-90 digits, and one dropped value produced a confident wrong VIF): it takes `ticker` + `factors=[...]` and builds each column itself from the run OHLCV through the live `strategies.factor_expressions` primitives (rsi / mom / bias / zscore / std / vol / range), trimming the common warm-up prefix; an unknown factor or too few usable columns degrades to an explicit `unavailable`, never a fabricated column. Found while reshaping it: the read was also **broken for every well-formed input** — it looked for a `{"columns": ...}` wrapper that `statistical.variance_inflation_factor` never returns, so it answered `singular fit / no result` even with valid data; the envelope read is fixed and a success-path test now pins it. **`get_pair_risk`** takes `ticker_x` / `ticker_y` and fetches both close series itself (the series-level computation stays as a private helper for batch QA). Both are bound to the market analyst with trigger lines. **`get_macro_regime_read`** is bound to the news analyst (the composite label over the same fed/curve/credit/DXY/vol markers news already cites) and **`get_trade_outcome_metrics`** to the three risk debators (entry-anchored MAE/MFE + stop/target hits for the plan they are arguing), each with its own trigger sentence. The four leave `TOOL_LEGACY_BINDING` (the declarations list now only shrinks), `docs/api_reference.md` names their real surface, and the argument-shape gate records `get_vif_read` as names-only.

Context channel: the pre-decision numbers are now real (2026-09-11; plan: `docs/implementation_plan_calc_agent_binding.md`, W4). **PM prompt:** `_precompute_risk_context` (already called before the graph runs) is now the single producer of the PM's pre-decision inputs — CVaR plus the liquidity verdict, the measured book drawdown against `risk_max_drawdown_pct`, the per-trade size cap and the daily CVaR budget — and the post-graph governor block consumes those values instead of recomputing them (one producer per number; a call-count test pins `_basket_drawdown` at exactly one call). The PM renders a limits line, and its stop / gate / size-cap rules now cite pre-decision sources instead of a Position contract that is written only after the decision. **Latent bug found en route:** the old post-graph liquidity read pulled `final_state['closes']` / `['volumes']`, which nothing ever writes, so the liquidity gate always saw empty series; the pre-graph read now measures what it can (IWF, Roll spread) and reports `unknown` — never a fabricated figure — where volumes are unavailable. **Hard guard:** the `insufficient_liquidity` guard called `.get('liquidity_verdict')` on `risk_snapshot`, which `build_risk_snapshot` returns as a **str**, so it raised inside a broad except and could never fire; it now reads the risk context and fires on a genuine ILLIQUID verdict. **Trade-plan card:** both callers (`trading_graph` and the `get_trade_plan` tool) pass the measured pieces (`trade_plan.measured_inputs`: tranche levels, unified stop, targets, BE rule, trail — from the same read the risk fold uses), so the card no longer renders a wall of `unavailable`. **Debate judge:** the L1 scorecard carries one row per claim (metric, asserted value, ground-truth key, true value, status), capped at 15 per role with an explicit omission note, instead of only per-role counts. **Removed:** the write-only `computed_context` chain — `strategies/debate_context.py::build_computed_context`, the `enable_computed_context` config key + env var (and the stale key in seven test configs) — read by no agent, its V5 inputs never supplied.

Binding-instruction gates (2026-09-11; plan: `docs/implementation_plan_calc_agent_binding.md`). **Correction to the 2026-09-04 wiring entry above:** that gate defined "bound" as appearing in a ToolNode list, so 16 `@tool` functions were documented (this file, README, `docs/api_reference.md`) as agent-callable while no `bind_tools` set carried them — a model can only emit calls for tools it was bound, so those were dead executor entries and the docs recorded the gate's definition instead of the capability. The `api_reference` rows now name the real surface (`risk debators` for the three the debator loop carries, `declared` for the rest) and the label is machine-checked. **New gates:** the tool-binding gate reads the toolset OBJECTS rather than file text (a prompt sentence can no longer fake a binding) and fails on a stale declaration; a bidirectional callability gate (per surface, the `bind_tools` set and the executor list must agree — the invariant behind both the ETF bind-without-executor bug and the 16 execute-without-bind orphans); a prompt-trigger gate (every bound tool needs a "cite it before any X claim" sentence; the 28 audited gaps are listed and being filled); a prompt-budget gate (market prompt measured at 37,527 chars / 77 forced-tool bullets / 523-char longest bullet, with ceilings so guidance growth is deliberate); an argument-shape gate (a bound tool may not advertise a list/object argument without a recorded decision — 11 currently do, and `get_vif_read` / `get_pair_risk` are reshaped to take names in this plan); and a doc-claim gate over the `api_reference` table.

Defect-audit remediation, part 2 (2026-09-10; plan: `docs/implementation_plan_defect_audit.md`). **Rendering honesty:** unmeasured risk metrics (semi-deviation, shortfall probability, horizon VaR, Jarque-Bera/Shapiro p) rendered as hard zeros now render `n/a` — a fabricated "no downside risk"/"normality decisively rejected" becomes an explicit unknown; a DCF with no provider beta/cash/debt labels the assumption (`beta=1.00 (assumed, no provider beta)`) instead of printing the substitute as "provider-derived"; the beat-streak identity shares one word→count map (two..ten), so "seven straight >40% beats" is verified instead of silently skipped. **Contracts:** `data_quality` has one meaning — `stale`/`partial` is a degraded read (confidence cap + hard guard), omitted/`unknown` is "not reported" and must not block a position; previously a reported `unknown` was coerced to `None` (so the documented confidence cap never applied) while an *omitted* field raised the `data_quality_failure` guard. The dead `L1Verdict`/`L1DeterministicResult` mirror (never emitted; the pipeline writes `severity_tier`/`l1_action`) is deleted and the emitted vocabulary documented as canonical. **Config/routing:** `enable_market_routing` + `market_source_priority` are real keys with env overrides (the documented `MARKET_SOURCE_PRIORITY` knob previously did nothing); `resolve_market_priority` filters to vendors registered for the method (a priority list naming an unregistered vendor raised an uncaught KeyError inside the router); `validate_config` now runs at config load and raises on violations (it had no production caller); `VENDOR_LIST` is derived from `VENDOR_METHODS` and the provider docs are corrected. **Dead weight:** the unreachable social ToolNode and its conditional branch are gone (the sentiment analyst binds no tools), the undeclared `security_type` state return is gone, the never-read `sender` channel is gone, the per-field integrity retry is wired into the decision agents, and the EMA is one shared implementation (three byte-identical copies fed the verifier's EMA identity pins). **Data integrity:** the Alpha Vantage OVERVIEW path kept only `Sector` from the flat camelCase payload, so `market_cap`/`shares`/`beta` were never parsed when AV served (EV, earnings yield, Altman and the net-net test all degraded to n/a) — single-level numeric fields are now parsed and camelCase/snake_case keys are split into the word boundaries the alias matcher expects. **Test gates:** new test-quality gate (no unfalsifiable assertions, source pins, or skip-inside-except) and prompt-*text* assertions replacing `inspect.getsource` pins.

Defect-audit remediation (2026-09-10; plan: `docs/implementation_plan_defect_audit.md`). **Reproduced-broken tools:** `get_regime_gate_read` returned "not callable" on every call (the private helper `_cfg_idx` carried a stray `@tool`, so the internal call raised TypeError) and `get_etf_mechanics` rendered "Distributions: n/a" on every call (a `@tool` object called as a function) — both fixed, with a new repo-wide gate that no `@tool`-decorated function is ever called as a plain function; `render_action_condition_verdict` was restored to `schemas.py` (deleted by an earlier refactor, so `action_condition_judge` raised ImportError and the `--llm` judge could never run). **Decisions:** the PM risk-cap guardrail now reads the structured risk factors (its old comprehension was always `[{}]`, leaving rule 1 unreachable) and the cap predicate implements its documented `>= high` threshold (CRITICAL now caps); the PM consensus line accepts both history shapes (a string-valued history was sliced into characters, yielding garbage stances that the old implicit Hold default silently turned into a fabricated consensus); `parse_rating` no longer defaults an unavailable decision to the tradeable `Hold` (it returns REVIEW and the memory log stores nothing, so reflection cannot resolve a failed decision). **Caching/config:** `_ohlcv` no longer caches a failed fetch (one transient error degraded every OHLCV tool for the process); `TRADINGAGENTS_ENABLE_*` overrides naming keys absent from `DEFAULT_CONFIG` stored the raw string, making `'false'` truthy — six keys defined plus an import-time validator, so env `false` is a real `False`. **Data integrity:** statement aliases no longer report Operating Income as revenue, EBITDA as operating income, or "Total Liabilities And Equity" as total liabilities; five dead vendor-chain entries fixed (Tiingo fundamentals/statements took the router contract; a real `get_global_news_gdelt` replaced the signature-mismatched one); `volume_dry_up`'s "20-day" baseline was a 5-bar slice and `price_velocity_z` measured the oldest bars instead of the trailing window; `get_fixed_income_risk` passed a 100×-too-small yield; `classify_security` called JPM/GS/MS/BLK/SCHW/NTRS/STT ETFs (swapping the fundamentals toolset for operating companies) — fund evidence now requires a wrapper token. **Look-ahead:** Finnhub global news ignored `curr_date`/`look_back_days`/`limit` and its earnings calendar queried a purely backward window; the insider window used `datetime.now()`; stockdata and moomoo news ignored the requested window; stockstats back-filled before the as-of filter; `date_window` admitted undated items for a window ending yesterday; Massive turned 429/timeouts into an "upgrade your plan" string; stockdata/newsapi/benzinga classified the body before the HTTP status; moomoo's empty financials returned a placeholder that blocked the whole vendor chain; `y_finance` returned blank indicator rows as a success string. **Verifier:** the 10-EMA identity missed "10-EMA = x", `t1`/`t2` read the `3` of `3R`, and the EPS-estimate metric required "eps actual". **Wiring:** registry credential map completed (five key-gated vendors) and `method_requires_credentials` is config-aware; `_run_signature` folds in the debate mode and checkpoint threads are run-scoped (concurrent same-ticker runs no longer share/delete each other's checkpoints); the parallel analyst merge carries `tool_evidence` (so `tool_evidence.json` exists when `analyst_concurrency>1`). **Dead code:** deprecated `social_media_analyst` shim + alias deleted, phantom `get_growth_metrics` tool surface deleted, dead state/misc unreachable code removed, `value_dip_tools` reuses the shared cached `_ohlcv`. **Test hygiene:** ~25 tests that could not fail (`or True`, `in (True, None, False)`, `is not None or … is None`, `assert True`, `inspect.getsource` pins, wall-clock bounds, global `os.chdir`, `except Exception -> pytest.skip`) were rewritten to assert observable behaviour, and five assertions that pinned the removed `Hold` fallback were re-pinned to the corrected contract. New gates: advertised-prompt-signature contract, vendor-signature contract, config contract, tool-callable contract.

Agent tool binding has one source of truth (S1; audit 2026-09-10): new `tradingagents/agents/toolsets.py` owns each analyst's bound toolset and `TradingAgentsGraph._create_tool_nodes` now derives every ToolNode from it, so the bound list and its executor can no longer drift. Fixes the ETF gap: the fundamentals analyst bound `get_etf_valuation` / `get_etf_decline_driver` / `get_etf_relative_strength` / `get_etf_risk` / `get_etf_mechanics` that no ToolNode could execute, so langgraph rejected every ETF-path call as "not a valid tool" (the fundamentals node is now the union of the company and ETF toolsets). Removes 22 hand-maintained ToolNode entries no analyst could bind (market 14, fundamentals 5, news 1, social 2 incl. the unreachable social node); the nodes now carry exactly what their analyst binds (market 125->111, news 26->25, social 2->0, fundamentals 53 unchanged). 16 `@tool` functions with no agent surface are declared in `TOOL_LEGACY_BINDING` with their real consumers (two are bind-or-delete candidates). Three source-text-pinning wiring tests were converted to behavioural checks over the toolset objects. Tests: `tests/test_tool_binding_single_source.py` +4.

DELL fundamentals review-loop fixes (2026-09-10): negative-equity D/E gate fails-open fix; scenario-DCF dual-bear conflict metric; beat-streak identity (table or inline; words or digits).

DELL market.md review-loop fixes (2026-09-10): close_200_sma dual-value flag (258.98 vs 238.98); ema20 trail dual-value flag (481.74 vs 503.74); T1 tolerance tightened to 0.05% (611.43 vs.611.85); ATR excludes dash-multiplier forms (1-ATR); market prompt pins close-vs-high label rule.

DELL news.md review-loop fixes (2026-09-10): EPS-actual dual-value flag (7.04 vs 7.00, both Finnhub); EPS-estimate dual-value flag (5.012 vs  .,5.03; news prompt pins summary-table figures must match body figures exactly (AI-orders $61B row was lost as $2B in the summary).

MU fundamentals review-loop fixes (2026-09-10): ev/ebit + ev/ebitda internal-conflict metrics (report quoted 65.2/66.65 vs leaves 113.91/113.80); dividend-yield sanity check flags a quoted yield >5x the same report's dividend-per-share x4 / price implication (MU 4.91% vs 0.061% - stale/unit-scaled vendor field); bare 'TTM yield' label covered without capturing 'earnings yield'.

MU market review-loop fixes (2026-09-10): pcr-oi internal-conflict metric (put/call 3.99 vs 3.39); VRP sign-label check flags a negative quoted VRP (-5.24pp) labeled 'positive' (unicode-minus tolerant); market prompt pins forming-bar wording (no 'closed' on an intraday session) and real-scale trigger labels (1,010 is never 400-area).

MU news.md review-loop fixes (2026-09-10): double-digit-beat-streak identity (claim must match the calendar's >=10% consecutive surprise run - the 'fifth' vs actual 3); insider sold-shares x price vs value identity (summary 30,000/8.8M vs leaf 40,000/38,756,162); scenario-dcf-bear regex scoped to kill the 'Bear-side' prose false positive.

SNDK fundamentals review-loop fixes (2026-09-10): beta internal-conflict metric (Finnhub 3.868 vs risk 1.87); scenario-DCF-base metric (1,388.45 vs 1,476.2); cash-conversion metric (OCF/NI 1.6 vs 1.032/1.28); SMA200-distance identity flags a direction/basis flip (65% below price vs true 39.6%; 65.5% is price ABOVE sma); fundamentals prompt pins fiscal-period labels (SNDK fiscal Q4 2026, not Q2 2026).

SNDK market review-loop fixes (2026-09-10): market prompt pins - never call a forming-bar intraday move CONFIRMED (gap-down/close/fill); label trailing stops by their own basis (20-day-true-range trail is not a 20-EMA - SNDK renamed 1586.04).

SNDK news review-loop fixes (2026-09-10): news prompt pins - index-inclusion catalyst wording (no assumed rebalance-buying window), insider rows calibrated to 10b5-1 (scheduled <> discretionary), and one-timestamp-per-series macro levels (HY OAS 2.71 vs 2.59 replication slip). The HY-OAS dual-value is already flagged by the existing verifier hy-oas metric.

SNDK review-loop follow-up: new get_share_buyback_authorization tool - trailing-4Q repurchase spend + ordinary-share-count trend from vendor statement rows (honest unavailable when rows absent), and it never quotes a remaining-AUTHORIZATION number (company-disclosure item). Wired into the news analyst prompt + tools and the news ToolNode; +3 tests.

WDC fundamentals review-loop fixes (2026-09-10): current-ratio internal-conflict metric (balance-sheet-health 10.87 vs vendored 1.329 in one report); scenario-DCF-base metric widened to $- and slash-forms (base 93.05 vs band 57.28/80.18/156.55); FCF unit-slip identity flags an M-vs-B typo in one report ($4.1B vs $3.10M; real FY26 FCF $3.51B); fundamentals prompt pins GAAP-vs-normalized labeling and one-unit-scale FCF discipline.

WDC market review-loop fixes (2026-09-10): 200-day-SMA conflict metric hardened against paired-label rows ('close_50_sma / close_200_sma | 497.72 / 377.47' false positive eliminated; paren-form value extraction fixed); MACD dual-value flagged via macd-histogram metric (body -9.32/+8.37 vs summary -0.32/+0.25); _DOLLAR_RE eased to accept paren-prefixed figures; market prompt pins PRICE/TIMESTAMP gate (>1% gap = DATA-INTEGRITY, no final SELL on the unverified figure), SELL-vs-REDUCE wording, and one canonical MACD record per report.

Verifier precision pass (found on the MSFT/TSM/ADBE/HPE batch sweep): eps-ttm conflict metric now requires the literal 'ttm' label (kills ~30 bare-eps / growth-row false flags); FCF unit-slip parser rejects non-money contexts (yield %, sum fragments, multiples) and zero values (kills the 0.0M-vs-B false positives).

MSFT fundamentals review-loop fixes (2026-09-10): new scenario-dcf-bull conflict metric (body 231.62 vs summary $201 - a 13% contradiction; bear/base rounding pairs also surfaced); new diluted-eps conflict metric (4.81 vs 4.84 label duals); fundamentals prompt pins MARGIN-OF-SAFETY denominator basis ((FV-P)/FV -333.7% vs (FV-P)/P -76.9% for MSFT) and exact restatement of key figures in the summary table.

Methodology extensions (from review-loop recommendations): (1) get_margin_of_safety now reports BOTH the FV-basis MoS and the price-basis MoS plus price/intrinsic - no more denominator ambiguity (MSFT -333.7% FV vs -76.9% price); (2) Finnhub peer-ticker aliases normalize malformed/international ids (3NDK->SNDK, 3QP->HPQ, QINFQ->INFQ ...) so peer sets stop corrupting valuation screens (SNDK 2026-09-10 review); (3) FCF-yield value-floor is configurable via TRADINGAGENTS_FCF_YIELD_FLOOR (default 6%; a strategy parameter, not a finance law - WDC review); (4) NEW get_normalized_cycle_dcf - median-of-annual-FCF perpetuity for cyclical reporters (MU/SNDK/WDC/TSM), independent of the run-rate DCF, wired into the fundamentals analyst + ToolNode; live WDC median=9.82/shr vs run-rate DCF 77.57, the normalized-cycle anchor the review asked for.

Fix(1) in margin_of_safety_bases: the price-basis MoS was computed as -(P/IV - 1), which is algebraically identical to the FV-basis - the tool printed the same number for both conventions (caught live on MSFT: -335.4% FV and -335.4% price). Corrected to (IV - P)/P, so MSFT reads -333.7% FV-basis vs -76.9% price-basis, exactly the two conventions the review asked to separate; +regression test.

MSFT market.md review-loop fixes (2026-09-10): new expected-band identity check flags a '+/-$0.00' dollar band next to a stated expected-move % (a fabrication - the vendor leaf gave [458, 523]; MSFT reported 6.6% as +/-$0.00); market prompt pins 'quote the vendor band or write unavailable, never $0.00'.

MSFT news.md review-loop (2026-09-10): new eps-estimate-per-date identity check flags two different EPS estimates anchored to the same earnings date (2026-10-28 cited as est 4.72 in headline/table but est 4.16 in the forward calendar - leaf says 4.72); news-agent pins: vendor- estimated next earnings date wording, routine-8-K classification instead of 'unknown material event', and one-estimate-per-date.

TSM fundamentals review-loop (2026-09-10): get_dcf_valuation now hard-gates unit/share-basis-inconsistent fair values - fair_value/price >5x returns DATA-QUALITY FAIL and excludes the DCF from composite valuation (TSM: 2933.52 vs 429.55 = 6.8x); fundamentals prompt pins ADR-vs-common-share basis on every EPS/normalized-EPS figure (TSM vendor diluted EPS 136.25 TWD is per-ADR = NT$27.25/common; the report quoted it as if common).

TSM market.md review-loop (2026-09-10): new bollinger-band identity check flags two unlabeled band sets in one report (body 438.16/405.14 vs table wide 438.59/404.71 - %b matches only the body pair); new sector-rank identity check flags conflicting numeric ranks for one sector (XLK rank 4 in both tools vs rank5 in the table); market prompt pins one canonical band set and one canonical sector rank.

HPE news.md review-loop (2026-09-10): new self-correction-artifact identity check flags inline (corrected: / correction -) retype leaks in a final report (HPE leaked '9.87 ... corrected: 4.8' and '172.346 ... correction - 154.3360'); news-agent prompt pins: clean rewrites only, catalyst modal_prob must name the modal outcome/date (never bare 'modal 73.4%'), and the 10Y FRED id must be DGS10 (a transient 9.87 print was the wrong series id - DGS1 - not a market move).

HPE fundamentals.md review-loop (2026-09-10): new mean-price-target identity check flags three distinct consensus means (leaf 69.38 vs table 58.38/58.97); self-correction detector now also catches money-ellipsis retype leaks ('Total debt $8.22B... verbatim'); fundamentals prompt pins: Total Revenue row verbatim per quarter, one analyst-consensus mean-PT, and signed gain/loss rows only (the report's $344M gain matched neither the -$444M cashflow row nor the +$373M IS unusual-items row; the leaf revenue was $12,213M while the report said $12.45B/$12.30B).

HPE market.md review-loop (2026-09-10): three new level-identity checks - 200-SMA distance (body +64.7% vs table +184.7%; 55.46/33.68-1=64.7%), GARCH conditional (58.90% body vs 65.90% table), and chandelier stop (54.11 vs 58.2/58.11); market prompt pins: gap-vs-session labeling (HPE open gap -1.9% / close -5.8% were mislabeled -5.4% gap), one canonical value per labeled level, and expected-move event reference (Q3 already printed 09-02; the +/-10.9% move is not a pending event).

ADBE fundamentals loop (2026-09-10, first live browser-fed chatgpt.com audit): new sum-identity verifier flags quoted additive sums whose arithmetic is wrong (report wrote TTM OCF 2.165+2.958+3.160+2.198 = $10.62B; the addends sum to 10.481B); fundamentals prompt pins an N-quarter series must list N entries (report labeled a four-quarter uptrend with five values) and DATA AS-OF must state the latest vendor-surfaced fiscal period (Q3 not in feed at report time).

HPE market.md re-verify (2026-09-10, second pass on the same report): new 10-EMA identity (trend section 54.66 vs summary graph 55.54) and EMA-trail identity (body 53.91 vs summary 59.02) checks - the stop/ level duals a trader acts on must be single-valued; market prompt pins ratio conventions (Call/Put vol 2.41 vs call activity 4.2x), one call-wall per report, ATR as unsigned magnitude, and intraday cross-under claims vs OHLC (HPE said price printed under the 10-EMA 54.66 intraday while the day low was 55.21).

IREN fundamentals fix batch (2026-09-10; synthesized from 4 model reviews - ChatGPT/Claude/Gemini/DeepSeek): earnings-surprise basis caveat when actual EPS is negative (GAAP actual vs adjusted consensus mix - IREN Q4 act -2.16 vs est -0.6058 was a beat on adjusted); EV/EBIT ARTIFACT guard in get_analyst_verdict (huge positive multiple next to negative EBIT = near-zero-slice artifact; 270,761 vs -18.29); cash-conversion sign handling for negative NI (the <0.8 warning bands assume positive income - IREN -2.99 read is a sign-inverted flag, not the old warning); fundamentals prompt pins: surprise basis, EV/EBIT sign sanity, parent/sub-item charge sums (IREN -779.76M vs components 729.94M), and EV/net-debt bridge conventions.

IREN market.md fix batch (2026-09-10; 4-model review - ChatGPT/Claude/Gemini/DeepSeek): ema20 verifier tightened so it cannot attribute a value across a table row (IREN 'Chandelier / EMA20 trail | 39.83 / 41.73' had mis-grabbed the chandelier 39.83 as an EMA20 value - a false positive; EMA20 is 41.73); market prompt pins: STOP BASIS (structure stop uses the tool's ATR snapshot, which can differ from the headline ATR(14) - IREN 31.6567 = 1x 3.1533 below 34.81, not 1x 3.38) and CHANDELIER BASIS (highest-high - multiplier x ATR, never close - multiplier x ATR).

IREN news.md fix (2026-09-10; 4-model review - ChatGPT/Claude/Gemini/DeepSeek): FOMC modal direction made deterministic. get_catalyst_scale (and fed_imminence) now surface the modal target range, and a new fed_direction(current_rate, modal_range) helper classifies the modal outcome HIKE/HOLD/CUT by 25bp-bucketing the current effective rate - IREN labeled 'hold at 3.75-4.00%' but with effective 3.63 (band 3.50-3.75) the modal 3.75-4.00% is a HIKE. get_catalyst_scale accepts an optional current_rate to render the direction; news prompt pins pass the effective rate and never call a 25bp modal move a hold without checking the current band.

IREN decision.md review fixes (2026-09-10, Claude feedback): the risk gate block now surfaces the book drawdown that drives the portfolio veto, with the configured limit, and flags a verdict/label mismatch when a PASS header sits beside drawdown over the limit (IREN: 61.64% vs 10% limit read PASS while the body said the house gate REJECTs); the graph fold records book_drawdown + drawdown_limit into risk_context; portfolio-manager prompt pins: stop-basis (contract hard stop vs chandelier trail must be labeled), size-basis (new-entry size vs target book weight are different figures), and gate-header consistency (no PASS/TRADE_ALLOWED header beside a portfolio veto).

MSFT decision.md review fix (2026-09-10, Claude feedback): the 200-SMA-distance verifier now catches a % mislabeled as the 200-SMA distance when the same line carries the 50-SMA value - it proves the stated % is actually the 50-SMA distance (MSFT decision.md +8.8% above the 200-SMA 429.51 at ~490.50 is +14.2% on the 200-SMA and +8.8% on the 50-SMA 450.83). Type-1 cross-value conflicts are now deduplicated (equal values no longer flag). PM prompt pins: one timestamped spot price per decision, and explicit 'contract size X capped to Y' labeling when a CVaR budget downsizes the contract.

NEW data source: Seeking Alpha keyless RSS commentary channel (user request 2026-09-10). New `dataflows/seekingalpha.py` fetches the public per-ticker feed (`/api/sa/combined/{TICKER}.xml`, browser UA, 15s timeout, typed NoMarketDataError/VendorRateLimitError) and renders contributor title/author/date/link with an OPINION CHANNEL pin (single- author commentary, no summaries - never a fact basis). Registered as the TAIL of the `get_news` chain in `interface.py`, so it serves only when every newswire vendor above fails; transcripts/quant-grades are intentionally skipped (FMP + in-house scores already own them). Hermetic tests in `tests/test_seekingalpha_vendor.py` (9; mock the urlopen seam); live probe confirmed the feed and the opinion render.

Agent-surface wiring audit fixes (13 failures -> 0; full suite 3441 pass): (1) retry-contract tests re-pinned to the 661d879 design - analyst stub-completion and structured missing-field repairs run only on the BACKUP LLM, never the flaky original; new tests pin the no-backup -> explicit-unavailable path and the never-repay invariant; (2) news analyst prompt regains the MACRO MUSTS header + explicit get_macro_indicators pin (the verifier already documented the header); (3) fundamentals analyst declares its company toolset as a canonical `tools = [...]` list and the base system message now carries ETF/FUND TOOLING guidance naming get_etf_valuation / get_etf_decline_driver / get_etf_relative_strength / get_etf_risk / get_etf_mechanics (the guidance previously lived only in the conditional ETF tail, invisible to the prompt-guidance audit); (4) get_composed_risk_gate is now bound in the market analyst's ToolNode (it was in the analyst tool list and prompt but missing from trading_graph's node); (5) get_composite_sizing is bound into the Trader sizing toolset in risk_tool_loop (was defined @tool but unreachable by any agent).
- **SOXX fundamentals review-loop fixes (2026-09-09)** - (1) the SOXX
  fundamentals.md asserted "NAV ~$532 is at ~39% below its 52-week high"
  (true drawdown 18.9%; price 532 / high 655.95) - a stale mid-sentence
  draft artifact. report_verifier gained `_drawdown_identity`: any "X%
  below 52-week high" claim must match price/high - 1 (>20% mismatch ->
  INTERNAL_CONFLICT). (2) SOXX's announced Nov-2026 forward split (iShares
  filed 2026-08-21; record 11-03, effective 11-04, adjusted trading 11-05)
  was absent from the corporate-actions vendor feed; the EODHD renderer now
  discloses announced-but-pending splits from a watchlist. Tests: +2
  (report_verify, eodhd_vendor).
- **Fed-cuts contradiction check (IGV 2026-09-09 review loop)** - the
  IGV news.md asserted the same "Fed rate cuts in 2026" Polymarket event at
  "Yes 0%" (body) and "Yes 93%" (summary table) with no prediction-market
  leaf anywhere in the tree. report_verifier gained a deterministic
  `_fed_cuts_contradiction`: any report citing that event at two materially
  different probabilities (<=2% vs >=50%) is INTERNAL_CONFLICT, resolved to
  one tool-sourced value. Tests: tests/test_report_verify.py (+2).
- **ETF sector identity fix (IGV 2026-09-09 review loop)** - the IGV/SOXX/
  SKYY/CIBR market reports mapped the tech ETFs to "Financial Services" via
  provider equity-sector metadata (yfinance/FMP return that for every ETF,
  including XLK). fetch_sector now canonicalizes known ETFs from the repo
  universe lists FIRST (SPDR_SECTORS / INDUSTRY_ETFS -> GICS label; no
  vendor call) so an ETF's sector comes from the issuer mapping, never the
  provider's wrong equity-sector field; company tickers are untouched.
  get_vol_surface_shape now renders the term-structure convention explicitly
  (TS = IV(long)-IV(short); >0 contango, <0 backwardation) so a report cannot
  mislabel -0.019 as "contango"; market-analyst prompt pins RSI >70 =
  OVERBOUGHT / <30 = OVERSOLD (the IGV report wrote ">70 oversold"). Tests:
  tests/test_yfinance_sector.py (+1).
- **ETF-specific fundamental engine (IGV 2026-09-09 review loop)** -
  the IGV fundamentals.md collapsed to "no DCF -> no BUY" because
  company statement tools correctly returned unavailable for a fund. Shipped
  docs/design_etf_fundamental_valuation.md end-to-end (default-off via
  TRADINGAGENTS_ENABLE_ETF_ENGINE): (P0) security_type.py classifies
  ETF/company (quote_type, universe lists, fund-issuer names; UNKNOWN keeps
  today's path); (P1) etf_valuation.py weighted constituent valuation (harmonic
  P/E, fwd P/E, earnings/FCF yield, val percentile, vs SPY/XLK, top-N) +
  SECTOR_CONSTITUENTS extended to IGV/CIBR/SKYY/AIQ/BOTZ/DTCR/NXTG/IYW/
  FINX/XSD; (P2) etf_decline_driver.py MARKET/SECTOR/ETF_SPECIFIC/
  CONSTITUENT_DRIVEN/UNKNOWN (replaces company "clean"); (P3) etf_risk.py
  relative strength with both legs + beta/capture/vol%/ATR%/maxDD; (P4)
  get_etf_mechanics NAV premium + distributions; (P5) fundamentals analyst
  routes to the ETF toolset + ETF prompt when classified, stamps
  security_type on state. Tests: 29 new (security_type, valuation, decline,
  risk, mechanics, analyst gating).
- **All retries route to TRADINGAGENTS_BACKUP_LLM (2026-09-09 review loop)**
  - the SOXX/IGV/CIBR/SKYY batch showed a ~20-call back-to-back burst of
  tencent/hy4-preview with no interleaved quick calls: the RM/PM
  structured->free-text stub path re-invoked the SAME (deep) model up to
  _MAX_TRUNCATION_RETRIES times, re-paying the flaky model for the repair.
  structured.py now routes EVERY retry to the backup model: _retry_if_stub
  (remaining budget on backup_llm, never plain_llm), retry_chain_if_stub
  (backup_chain), retry_structured_missing_fields (backup_llm); the three
  analyst nodes pass their backup_chain. Without a distinct backup there is
  NO same-model retry - the honest 'unavailable' notice is emitted instead
  (no infinite loop). Tests: tests/test_structured_agents.py (4 updated to
  the backup-routing contract).
- **Options/liquidity metric transparency (NXPI 2026-09-09 review loop)** -
  (1) get_options_iv_read now names the VRP realized-vol basis ("ATM IV
  50.45% - 20d realized 20.58%: +29.87pp, 20d log-close basis") instead of
  the ambiguous "ATM IV - realized vol" the review could not reconcile
  against the 60d/YZ/garch vols also listed. (2) get_liquidation_days
  renders the 15% participation figure separately from the ADV ("X/day
  (15% of ADV Y/day)") - the old label printed the ADV as if it were the
  15% participation, making 445.6 days look internally inconsistent (math
  was correct). (3) options-chain tools (moomoo + yfinance) relabel the OI
  ratio: call_oi/put_oi is now "Call/Put OI/volume ratio" with the put/call
  reciprocal, not the contradictory "Put/Call OI ratio (call/put)". Tests:
  tests/test_moomoo_vendor.py, tests/test_analysis_tools.py.
- **Valuation-data hardening (NXPI 2026-09-09 review loop)** - (1)
  get_ratios_massive now annotates >100x EV/EBITDA or EV/EBIT as
  "DATA-QUALITY: vendor-multiple anomaly (contaminated EBITDA denominator),
  do not use as valuation evidence" instead of handing 474.72x / 3119.61x to
  the analyst as a real multiple. (2) DuPont identity fixed: the product is
  compared against the ROE on the SAME line as the decomposition inputs, not
  the first ROE in the report (NXPI 26.1% on-line product matched; a
  different analyst-screen 19.34% was a false positive). Tests:
  tests/test_massive_vendor.py (+2), tests/test_report_verify.py (+1).
- **Catalyst-scale honest degradation (MU 2026-09-09 review loop)** - when
  fed_watch AND economic_calendar both return NO_DATA (vendor down), the
  snapshot reported "scale=1.0 no-imminent-catalyst" — a false clean bill
  with FOMC 09-15 six days out (SKHY-sized the same window 0.60 when its
  feed was live). build_catalyst_snapshot now reports
  verdict=catalyst-unassessed with the "FOMC proximity unevaluable" reason
  and a configurable x0.90 de-risk (catalyst_unassessed_scale) instead of
  claiming a confirmed clean window; LIVE feeds with no event in window
  still yield no-imminent-catalyst scale 1.0. Tests:
  tests/test_strategies_catalyst.py (+1, 2 updated to honest contract).
- **R-multiple (2R/3R target) identity check (MU 2026-09-09 review loop)**
  - the market.md quoted "2R/3R targets 1357.69 / 1521.68" vs get_swing_set
  (evidence) 2R 1357.69 / 3R 1522.65 — a 0.06% transcription typo, and the
  review's #1 arithmetic find. report_verifier gained determinisic
  `_r_multiple_identity`: each 2R/3R must resolve as entry+N*(entry-stop)
  from the entry/stop PAIR on its own line (structure stop 862.81 vs
  chandelier stop 910.16 are separate frameworks, never crossed); 4-digit
  "/" pairs ("1357.69 / 1521.68") parse correctly. Tests:
  tests/test_report_verify.py (+4).
- **Valuation-identity checks (MU 2026-09-09 review loop)** - the
  fundamentals.md mixed basis and broke identities the same report asserted:
  get_ratios P/E 135.94 (annual FY25 EPS basis) vs "TTM EPS $44.17" at
  price $1,027.77 (=> 23.3); ROE ~35% decomposed from net_margin 0.5591 x
  asset_turnover 0.8929 x equity_multiplier 1.3315 (=> 66.5%); EV
  $1.166T > market cap $1.16T while asserting net cash $19.65B. report_verifier
  gained deterministic `_valuation_identity_checks` (DuPont product vs ROE,
  P/E basis vs price/TTM-EPS, EV>mcap-with-net-cash) plus an `altman z`
  internal-conflict metric (MU body 24.60 vs summary/evidence 25.70). Runs in
  verify_report_dir regardless of the LLM pass; live on MU_20260909_171033
  flags 3 identity + 2 internal conflicts. Tests: tests/test_report_verify.py
  (+7).
- **Macro-authority gate (SKHY 2026-09-09 review loop)** - the news.md
  quoted market-implied figures ("Polymarket: no Fed rate cuts in 2026 =
  Yes 93%", "recession 8%", "10Y at 4.78 FRED print", "RRP at 0.432B")
  with NO get_prediction_markets / get_macro_indicators leaf in the tree -
  the MACRO MUSTS prompt pin is not enforced. report_verifier gained a
  deterministic `_macro_authority_gate`: any line citing a pinned macro
  authority (polymarket/prediction market/fed-cut/10Y/RRP/WTI) is
  UNSUPPORTED unless that analyst's evidence holds the matching tool leaf
  or a leaf whose content carries the term (TGA leaf cannot satisfy an RRP
  claim). Runs in verify_report_dir regardless of the LLM verdict; live on
  SKHY_20260909_155623 flags 7 lines. Tests: tests/test_report_verify.py
  (+4).
- **Quant decision stack P1-P3 (SKHY 2026-09-09 review loop)** -
  (P1) security-signal/portfolio-action split: `strategies/signal_action.py`
  renders "Security signal: **BUY** | Portfolio action: **NO_NEW_RISK**
  (gated)" in the Risk Gate block and adds `security_signal` /
  `portfolio_action` / `combined_action` / `gated` to research_decision.json
  (additive; the gate can downgrade but never upgrade a signal). (P2)
  composite position sizing: `strategies/size.composite_position_size` +
  `get_composite_sizing` tool - size = min(quarter-Kelly, risk/stop, cap) x
  vol-scale x liquidity x uncertainty, clamped to 0 by any blocking portfolio
  action and halved on SCALE_DOWN. (P3) per-rule forward-return evaluation:
  `strategies/rule_eval.py` + `scripts/rule_eval.py` - measures fwd
  1/5/10/20d return, hit rate, MAE/MFE, Sharpe, profit factor per rule with
  an n>=30 INSUFFICIENT guard (live AMZN: rsi_oversold fwd5 +0.71% PF 1.37 /
  macd_hist_rising fwd20 +1.39% PF 1.45 vs rsi_overbought fwd20 -1.31% PF
  0.68 - the indicator set now has evidence). Tests:
  `tests/test_signal_action_sizing_ruleeval.py` (12).
- **Data-quality annotations (SKHY 2026-09-09 review loop, P0)** -
  (a) `build_verified_market_snapshot` now flags indicators whose history is
  shorter than the methodology window: stockstats SILENTLY substituted a
  truncated-window mean for a 200-SMA on 43 bars (identical to the 50-SMA,
  i.e. a full-series mean) - the snapshot now renders
  "(insufficient history: 43/200)" per indicator (10-EMA/50-SMA/200-SMA/
  RSI/bands/MACD/ATR registry), so a fallback is never read as a genuine
  long-window statistic; (b) options OI convention disclosure - the IV-read
  tool (put/call) and the options-chain snapshot (call/put) now each print
  the reciprocal + a convention note, killing the "1.24 vs 3.37" conflicting-
  ratio class. Tests: insufficient-history annotation, IV-read convention +
  reciprocal, pure put/call reciprocal.
- **Fix overnight-gap mislabel (SKHY 2026-09-09 review loop)** -
  `gap_type` computed the gap as (close_t - close_t-1) - i.e. the DAY'S return
  labelled an "overnight gap" - because it proxied today's open with the
  close. SKHY: +7.32% session move was labeled an "exhaustion gap" when the
  real open gap was ~+1%. `gap_type(closes, opens, highs, lows, volumes)`
  now takes the real open series (tool passes it; close fallback only when
  no opens exist) and `get_gap_type` renders the true open gap. Tests:
  breakaway via real +2% open gap, SKHY regression (flat open + big close
  move classifies common, never exhaustion).
- **FCF-yield currency-neutral render + P/E/PEG conflict net (SKHY 2026-09-09
  review loop)** - `get_fcf_yield` rendered vendor-raw values with a "$" prefix
  even for non-USD reporters (SKHY KRW: a correctly-computed 7.77% yield got
  prose'd as "$228.4B FCF / $26.3B mcap" - pure unit corruption). The render
  now drops the "$" and labels "raw vendor units" so the analyst never
  relabels KRW as USD; the verifier's internal-conflict metric set gained
  `forward peg` + `ttm p/e` (SKHY table 'PEG 0.08' vs body '2.08285', 'P/E
  1.91' vs '2.1822'). Tests: fcf-yield no-$ render, PEG/PE conflict.
- **Complete TRADINGAGENTS_BACKUP_LLM coverage (khy 2026-09-09 stall)** - the
  report verifier, the `--verify` batch pass, the Action-Condition judge and
  the Pre-Market reviewer did NOT plumb the backup LLM: their truncation
  continuation retried on the SAME truncated model. `verify_report_dir` now
  builds a backup client from `backup_llm`/`TRADINGAGENTS_BACKUP_LLM` and
  forwards it into `invoke_structured_or_freetext`; both overrides accept
  `backup_llm` and their scripts (`action_report.py --llm`,
  `pre_market_review.py`) build it from config. Every LLM truncation path now
  falls back to the configured backup model. Regression test:
  `test_verify_report_dir_builds_backup_from_config`.
- **Fix VRP double-percent render (ARM 2026-09-09 review-loop)** -
  `get_options_iv_read` rendered `volatility_risk_premium`'s PERCENTAGE-POINTS
  value with a "%" format, multiplying by 100 twice: ARM (ATM IV 67.97% - RV
  ~50.4%) = +17.63pp printed as "+1763%". Now renders "VRP (ATM IV - realized
  vol): +17.63pp (percentage points)". `volatility_risk_premium` itself
  (pure, returns pp) is unchanged - tests pin its API; regression test added
  for the tool render (hermetic yfinance chain, asserts pp + sane <100
  magnitude).
- **DCF WACC decomposition + gather-time D/E reconcile (ARM 2026-09-09 loop)** -
  (a) `get_dcf_valuation` now exposes `rf=` / `beta=` / `erp=` with
  "wacc = CAPM rf + beta*erp" so an extreme WACC (ARM 24.23% on beta 3.89) is
  auditable instead of a black-box output; (b) `metric_reconcile` gained a
  debt/equity lane: get_fundamentals raw "Debt to Equity 5.62" vs get_ratios
  computed 0.06 vs get_balance_sheet_health d_e=0.0552 now surfaces as a
  gather-time VALUES CONFLICT (the ARM loop flagged the 5.62 as a likely bad
  vendor field - debt 464M / equity 8.63B = 0.054). Tests:
  `test_metric_reconcile` (extract_de_value shapes + reconcile flag).
- **Verifier MISQUOTED status + adjudication sweep (AMZN 2026-09-09 loop items
  1+3)** - (1) the deterministic anchor now surfaces MISQUOTED when a claim's
  figures ARE in tool evidence but attached to the wrong label/context (LLM
  reason carries a transposition/attribution cue) instead of silently
  re-grounding it - catching the AMZN composite-rank A/e swap class; the
  internal-conflict metric set gained ATR/T1/T2/macdh/RVOL/Williams/stoch/RSI/
  AWS-growth/HY-OAS with per-metric tolerances (exact price levels at 0.1% so
  T1 265.03 vs 265.97 and ATR 6.47 vs 5.7079 flag); `_float_tokens` now
  collects percent-int figures and unit scales include 1e2 so integer percents
  match fraction leaves. (2) `scripts/verify_sweep.py`: post-verifier
  confirmation workbench over existing verify_flags.json - surfaces N
  CONFIRMED (MISQUOTED/CONTRADICTED/INTERNAL_CONFLICT, needs a fix) vs M
  SUSPECT (UNSUPPORTED, needs adjudication) per tree, `--json`,
  `--confirm-only`; exit 1 when any confirmed/suspect exists. Tests:
  test_report_verify (MISQUOTED anchor, ATR/T1 conflicts, percent-matching),
  test_verify_sweep (counts/absent/CLI ok).
- **News-analyst macro citation hardening (AMZN 2026-09-09 review loop)** -
  uncited macro figures (10Y Treasury "9.78%"/"4.85%" vs actual ~4.78, RRP
  0.626B, "93% no Fed cut" Polymarket) had ZERO tool leaves - the analyst
  recalled them instead of calling get_macro_indicators / get_prediction_markets
  / get_tga_balance (all exist and were bound). The prompt now pins every macro
  class to its tool (MACRO MUSTS) and forbids pasting a recalled macro figure;
  regression test in `tests/test_news_analyst_prompt.py`. Verifier caught all
  of these as UNSUPPORTED/anchored already (rule 8 loop).
- **VDU hard execution gate + ATR(14) labeling (AMZN 2026-09-09 review #19/#14)** -
  (a) `value_dip_setup` gained `require_vdu`: the Step-2 VDU ladder (volume
  dry-up + trigger candle close-above-prior-high + RVOL >= 1.3 + momentum
  confirmation) is promoted to a HARD gate - candidate=False means NO entry
  even if an oscillator looks oversold; measured-only (unknown never fails),
  wired from `TRADINGAGENTS_VALUE_DIP_VDU_ENABLE` / `value_dip_vdu_enable`
  (default off, mirroring the knife/regime/catalyst gates). Tests:
  `tests/test_strategies_value_dip.py` (require_vdu blocks-incomplete /
  confirms / unknown-never-fails). (b) ATR window disclosure - the verified
  market snapshot now labels its stockstats ATR as `atr(14)` and
  `get_swing_set`'s structure-stop renders `1 ATR(14) below swing low,
  ATR(14)=...` so the snapshot's ATR is never confused with a swing/tranche
  ATR of another window (AMZN 6.47 vs 5.7079). Tests: `test_market_data_validator`
  (atr(14) label), `test_analysis_tools` (swing_set ATR(14)).
- **Market-report honesty fixes (AMZN 2026-09-09 review loop)** -
  (a) `build_verified_market_snapshot` now labels a row dated = the requested
  analysis date as a potentially FORMING bar (intraday run) and marks its
  Close + close-derived indicators PROVISIONAL - never a settled close -
  instead of presenting it as a "verified" EOD bar; (b) `get_mean_reversion_quality`
  discloses MIXED evidence when the AR(1) verdict is mean-reverting but the
  long-horizon signatures lean the other way (Hurst > 0.55 persistence and/or
  a significant VR > 1 momentum) - AMZN half-life 10.78d but Hurst 0.6425 /
  VR 1.18, so the read now says "require an explicit trigger/confirmation"
  rather than a clean "dip entries supported". Regression tests:
  `tests/test_market_data_validator.py` (provisional-note + settled control),
  `tests/test_strategies_mean_reversion.py` (mixed + clean paths).
- **CapEx-allocation read (advisory, deterministic)** - `strategies/capex_quality.py`
  + `get_capex_quality` (fundamentals tool loop): separates PRODUCTIVE
  investment from OVERINVESTMENT / DISTRESS for high-capex names - CapEx
  intensity z (vs the name's own history), funding cover OCF/CapEx, CapEx-vs-
  revenue 5y CAGR elasticity, incremental ROIC (3y lag, dNOPAT /
  dInvestedCapital) + economic spread vs WACC, CapEx ROI 3y, payback 3y,
  FCF-recovery gap (to a 3% target yield), a 5-regime label (HARVEST /
  PRODUCTIVE / PRODUCTIVE_INVESTMENT / INVESTMENT_WATCH / OVERINVESTMENT /
  DISTRESS), a 0-100 quality score and advisory valuation penalty. NEVER a
  hard gate; n/a on missing rows; composite renormalizes over measured
  components. Adjudication artifact of the AMZN 2026-09-09 report-review
  loop (rule 8: a negative trailing FCF is reinvestment, not automatically
  value destruction). Tests: `tests/test_capex_quality.py` (8: regimes,
  None-safety, hermetic tool render).
- **FCF value-floor / DCF now anchor on trailing-12M FCF, not latest ANNUAL
  FYxx** - `get_fcf_yield`, `get_value_dip_setup`, `get_dcf_valuation` and the
  scenario-DCF input path all fed the latest annual *free cash flow* into the
  value floors, silently stale in a capex-accelerating quarter (AMZN case:
  FY2025 annual +$7.7B vs trailing-12M -$2.5B; value-floor claimed
  `fcf_positive=True` and DCF $1.56 off a positive stale anchor). New
  `value_dip_tools._ttm_fcf_from_quarterly` sums the newest 4 quarterly FCFs
  (moomoo quarterly markdown or quarterly-CSV, gated on a Q-token shape so an
  annual payload is never summed quarter-style); positive TTM feeds the
  floors/DCF, a NEGATIVE TTM degrades the DCF honestly ("use a
  normalized/forward-FCF model") instead of recycling the stale positive
  annual, and the render shows `basis=ttm` / `basis=annual`. Regression tests:
  TTM preference, negative-TTM DCF degrade, annual fallback. Adjudicated from
  the AMZN 2026-09-09 report-review loop (rule 8).
- **Deterministic forced-tool evidence gathering** (map-reduce; design
  `docs/design_mapreduce_forced_tool_gathering.md`, plan
  `docs/implementation_plan_mapreduce_forced_tool_gathering.md`): when
  `TRADINGAGENTS_ANALYST_FORCED_TOOLS` is set, the runtime gathers that fixed
  tool set deterministically (the "map") before the analyst runs and the
  analyst *reduces* from the merged evidence block — so the analyst's report
  input is fixed in *composition* (which tools were asked) instead of the
  LLM-selected subset. Addresses the analyst-side root cause of run-to-run
  verdict flips (the 2/3 TSM probe). Config: `analyst_forced_tools`,
  `analyst_forced_tools_max_parallel`, `analyst_forced_tools_timeout_s`,
  `analyst_forced_tools_summary_window`. Defaults off — the legacy
  LLM-selected path is bit-identical when unset. Per-tool deadline (default
  30s) records a `timeout` leaf and proceeds (today there is no tool
  deadline at all); a wedged thread drains in the background (Python can't
  preempt it — see design §3.5/tracked TRACKED-1). Evidence is persisted to
  `tool_evidence.json` per run and diffed by `repro_check --evidence` so
  "did every run see the same tools" is answerable from the report tree.
  Scope: the 4 information analysts (market/fundamentals/news/sentiment);
  risk debaters + Trader are a tracked Phase-5 follow-up.
- **Tool pools: gather-pool vs model-pool** (same feature, refined): tools
  whose required args the deterministic context can supply (140 of 180
  registered) are forced-gathered as before; tools needing a
  model-supplied input (40: options quotes, scenario DCF, allocation,
  macro-indicator slugs, etc.) are never auto-attempted — they stay bound
  to the LLM, which owns their inputs, and are listed in the evidence block
  under "Model-supplied tools" so the split is visible. Classification is
  signature-derived at runtime (a future tool needing a model input lands
  in the model pool automatically); `TRADINGAGENTS_ANALYST_TOOLS_MODEL_SUPPLIED`
  is an escape hatch to force extra names into the model pool. Short-circuit
  blocks only gathered (gather-pool) tools; model-pool calls execute for real.
- **Backup LLM for truncation-continuation retries** (`TRADINGAGENTS_BACKUP_LLM`
  in `.env`, config key `backup_llm`): when ANY LLM response is cut at the
  output cap, the continuation retry now runs on the configured backup model
  instead of re-paying the model that kept truncating. Spec format
  `provider:model` (e.g. `openrouter:deepseek/deepseek-chat`) or a bare model
  id using `TRADINGAGENTS_LLM_PROVIDER`; empty = same-model continuations
  (legacy behavior, bit-identical). Wired through every truncation path:
  analyst chain reports (`retry_chain_if_truncated` + cap-forced
  `finalize_messages`), plain researchers / risk debators
  (`retry_llm_if_truncated`), the structured managers / trader / sentiment /
  independent-stance `invoke_structured_or_freetext`, AND the structured
  debate turns + L2 judge (`invoke_structured_turn`: a structured call that
  raised or returned unparseable content — e.g. a max_tokens cut mid-JSON —
  falls back AND repairs on the backup; the plain invoke stays primary when
  the provider lacks structured output). The graph resolves one backup client
  (`provider:model` spec, quick-tier output budget, its own provider's
  kwargs) and threads it into `GraphSetup` + every SD node. Tests:
  `test_truncation_retry.py` +8 backup-swap cases (plain / chain / structured /
  free-text / same-object guard / bounded-give-up / failure-degrade /
  complete-no-touch) + `test_debate_integration.py` +3 (structured-failure
  fallback / repair swap / no-backup same-model) + `test_env_overrides.py` env
  mapping + graph wiring (backup built when set, absent when unset). See
  CHANGELOG / api_reference.
- **Debate-judge ensemble** (`TRADINGAGENTS_DEBATE_JUDGE_ENSEMBLE`, default 1,
  set to 3): the L2 judge runs N times over the SAME transcript and the per-alias
  side scores aggregate (mean-of-means), with `judge_agreement` + `judge_flip`
  written into the debate state so a borderline judge flip is an EXPLICIT
  uncertainty signal instead of a silent swing. `structured.invoke_structured_turn`
  now returns a `mode` ("structured"/"plain"/"repair"); the judge + debater turns
  record `judge_structured_fallback` / per-role `_structured_fallback` when a
  turn fell back to free text (reporting + PM see reduced reliability). The
  RM/PM decision matrix gains a deterministic **field-level consensus** block
  (stance / allocation / judge-score spread) so convergence is measured on the
  typed fields, not just the headline label. New `scripts/repro_check.py` runs a
  symbol N times and prints verdict agreement + config hash for reproducibility
  measurement. Tests: `test_debate_risk_parity.py` (ensemble aggregate + flip /
  fallback flag / consensus lines) + `test_debate_integration.py` (mode contract).
  — A 2×3 TSM reproducibility probe: baseline verdicts (Underweight, Underweight,
  Overweight) vs the ensemble+temp=0.1+judge-luna config (Hold, Overweight, Hold):
  both 2/3 self-agreement — temperature/judge/ensemble=3 reduced but did NOT
  eliminate the borderline flip (judge flips persist even at temp 0.1, per the
  reproducibility literature). Follow-up: `TRADINGAGENTS_DEBATE_JUDGE_ENSEMBLE=5`
  and a deterministic **PM confidence gate** (`decision_guardrail.cap_pm_confidence_on_judge`):
  when the risk-debate judge flipped / agreement<1.0 / used free-text fallback,
  the PM's confidence is capped (default 0.5, never raised) with a recorded
  reason, and the PM prompt carries a "Risk-debate judge reliability" line so
  the model holds down conviction on an unreliable judge — so a borderline
  judge flip now DEGRADES the decision's confidence rather than silently
  swinging it. Tests `test_decision_guardrail.py` +7 + `test_structured_agent_prompts.py` +2.
### Fixed
- **Reasoning-model output-budget starvation** (`TRADINGAGENTS_OPENROUTER_REASONING_EFFORT`
  in `.env`, config `openrouter_reasoning_effort`): a reasoning model
  (deepseek-v4-flash via OpenRouter) spends its WHOLE `max_tokens` on hidden
  reasoning — observed `completion_tokens==reasoning_tokens==4000`, "length
  limit was reached" — so the cap-forced final report turn returns empty and
  the structured-debate judge JSON never parses (both fall back to free text,
  TSM 2026-09-07). The knob forwards `reasoning: {effort: low|medium|high}`
  in the request body for the OpenRouter provider only, so the model's
  reasoning burn stays BELOW the output budget and the report/JSON always has
  room. Off by default (provider default effort). Tests:
  `test_llm_client_timeout.py` +3 (forward / unset-omitted / native-not-affected).
- **Tool-not-found 400 on the cap-forced report retry** (`structured`): a
  strict tool-calling backend (OpenAI / Azure via the OpenRouter relay)
  hard-400s a conversation that contains an unfulfilled tool call — "No
  tool output found for function call <id>" — which the analyst tool loop
  leaves when one assistant reply requests several tools but only the first
  executes. This killed the backup-model retry of empty cap-forced reports
  (TSM 2026-09-07), degrading every such section to the unavailable notice.
  New `_deorphan_tool_calls` strips unfulfilled calls (never fabricating a
  result) before ANY chain re-invoke: `finalize_messages` (terminal turn +
  truncation continuation + backup empty-retry) and
  `retry_chain_if_truncated` / `retry_chain_if_stub`. Regression tests:
  `test_tool_round_cap.py` +3 (backup de-orphan / same-chain de-orphan /
  clean-pass-through).

  (`graph.trading_graph._try_fetch_closes`): a vendor returning OHLCV rows
  NEWEST-first (EODHD) left `closes[-1]` as the OLDEST close, so every
  consumer of `closes[-1]` as 'the latest close' read a stale value — the
  TSM 2026-09-07 trade-plan card pinned a reference price of 288.88 that
  collided with the verified 428.91 bar (bull/bear/Trader/PM flagged an
  'unresolved reference price'; the same stale basis surfaced in
  `get_bollinger_pct_b`/`get_opening_range`/`get_support_structure`).
  The helper now normalizes the vendor output to ASCENDING date order,
  mirroring `analysis_tools._ohlcv` (which had the same ABNB $128.56
  incident). Regression test: `test_graph_tool_loop.py`
  `test_try_fetch_closes_normalizes_newest_first_vendor_rows`.

  (`structured.finalize_messages`): when the MAX_TOOL_ROUNDS terminal turn
  returns empty content (a reasoning model like `deepseek-v4-flash` burned
  its output budget on hidden reasoning — QCOM fundamentals + NXPI
  market lands 2026-09-07 fell through as a bare "report unavailable"
  placeholder), the analyst is re-asked ONCE — on the configured backup
  chain when set, else the same chain — with the completion directive, 
  and only if that still returns empty does it emit an explicit
  `**Report unavailable**` notice (never a silent empty string). Regression
  tests: `test_tool_round_cap.py` +3 (backup-retry / same-chain retry /
  unavailable notice).
 (`get_sector_rotation_screen`):
  the curated-industry branch referenced `_top_note` before assignment
  (`UnboundLocalError`) and the shared constituent block referenced
  `breadth_with_gate` / `leadership_ratio_ewcw` imported only inside the eodhd
  branch — the nxpi batch 2026-09-06 died on the first one. `_top_note` is now
  initialized in the curated branch and the breadth imports are hoisted to the
  function top. Regression test
  `test_sector_rotation_curated_breadth_does_not_crash` renders the constituent
  screens through the exact curated path.
- **Quant-formula audit fixes (independent web-verified pass over ~468 formula
  blocks)** — four material divergences corrected:
  1. **Risk-parity weights** (`portfolio_optimizer.risk_parity_weights`): the
     update `Σ⁻¹·(1/RC_i)` does not converge to equal risk contribution and
     collapsed to a degenerate single-name book on correlated inputs; replaced
     with the converging fixed-point `w ← normalize(b ⊘ Σw)` (equal risk
     budgets), which equalizes marginal risk contributions `wᵢ(Σw)ᵢ`. Non-
     convergence now degrades explicitly to equal-weight with a note.
  2. **Beneish M-Score** (`dataflows.quantitative_scores.beneish_m_score`):
     DEPI denominators were `(PPE − Dep)` instead of canonical `(PPE + Dep)`,
     overstating DEPI ~1.7×; LVGI computed `(CL − LTD)/TA` instead of canonical
     `(CL + LTD)/TA`, flipping the leverage signal for debt-heavy firms (the
     −0.327 weight then pushed M the wrong way). Both fixed to the Beneish
     (1999) forms; None-safe `_add` helper added.
  3. **DCF terminal value** (`strategies.dcf.compute_dcf`): the Gordon TV was
     anchored to the base-year FCF instead of the last projected year
     `F₀(1+g)ⁿ` (docstring already claimed the correct intent), silently
     understating intrinsic value ~7–10%; TV now uses the projected year-N FCF
     and discounts it back from year N.
  4. **Square-root market impact** (`strategies.backtest_models.
     square_root_impact`): `vol_pct` (a percent, e.g. 20.0) was divided by 100
     twice (`(vol_pct or 0.20)/100` → 0.002 for 20% vol), understating impact
     ~100×; now converted once to a fraction (0.20). Regression tests pin the
     exact 0.1·σ·√(Q/V) value.
  Each fix carries a regression test pinning the canonical closed form;
  full-suite green.
- **Agent wiring: every audited calculation reaches its analyst via a tool +
  prompt** — verified the calc→tool→agent-binding→prompt chain for all 17
  audited calculations; closed the 5 that had no agent-tool surface:
  `bsm_equity_surface` → **`get_bsm_option_quote`** (market), 
  `long_short_precision` + `purged_cpcv_splits` (+ `rank_ic`/`icir`) →
  **`get_signal_quality`** (market), `cap_and_redistribute` →
  **`get_constituent_cap_weights`** (fundamentals). Also restored 3 audit
  calcs that were graph-ToolNode-only but never in the LLM's bound list:
  `black76` → `get_options_iv_read`, `taylor_rule` → `get_taylor_read`,
  `alpha158_subset` → `get_factor_profile` — now bound in the market
  analyst's `tools = [...]` (bind_tools) list with prompt guidance. Every
  new/restored tool carries a prompt line (enforced by
  `test_calc_agent_wiring`); Alpaca paper-trading surfaces excluded by
  design.
- **Quant-formula audit pass 2 (13 remaining divergences)** — the 13 lower-
  severity divergences from the same audit, each with a regression test:
  1. **Modified VaR** (`strategies/size.py`): Cornish-Fisher now uses EXCESS
     kurtosis (γ₄−3, normal = 0) instead of the raw standardized kurtosis,
     removing the spurious ~0.7σ tail adjustment at 99% on normal series.
  2. **Capital-income capping** (`strategies/capital_income.py`):
     `cap_and_redistribute` now enforces the documented two-threshold rule
     (3% soft cap / 3.5% exact ceiling): excess redistributed pro-rata to
     names below the soft cap, capped names frozen at the ceiling. The old
     whole-vector renormalization pushed capped names back above 3.5%.
  3. **Downside deviation / semi-deviation** (`strategies/rate_utils.py`):
     divided by ALL observations (canonical, consistent with
     `evaluate.downside_deviation`) instead of the shortfall count (was
     inflated ~√2 on symmetric returns).
  4. **Black-76 rho** (`strategies/options_math.py`): futures-form `−T·V`
     (was BSM spot-form, wrong sign for ITM calls).
  5. **BSM charm** (`strategies/options_math.py`): sign fixed + the dividend
     term `q·e^{−qT}·N(d1)` added; finite-difference verified.
  6. **Zmijewski X-score** (`strategies/normalized.py`): liquidity term uses
     the canonical current ratio CA/CL (was inverted CL/CA).
  7. **Alpha158 `_returns`** (`strategies/factor_expressions.py`): sign-fixed
     to `c/prev − 1` (was `prev/c − 1`, swapping the up/down-vol features).
  8. **Choppiness** (`strategies/regime.py`): now the canonical CHOP index
     (0-100, ATR/range ratio; OHLC); close-only series keep a bounded
     0-1 proxy. Regime threshold retuned to the CHOP 30 trending band.
  9. **Long-short precision** (`strategies/signal_analysis.py`): Qlib
     sign-direction hit rate (was top-quantile set overlap).
  10. **CPCV** (`strategies/evaluate.py`): now Naive-Combinatorial CPCV —
     every (test-group, train-complement) subset, 5×15 paths for 5 groups
     (was single k-fold cut); embargo preserved.
  11. **RSI family** (`strategies/swing.py`, `technical_factors.py`):
     `swing.rsi` + `stoch_rsi` now use Wilder RMA smoothing (was Cutler's
     simple-sum RSI mislabeled "Wilder"); `rsi2` unchanged (n=2 collapse).
  12. **Taylor rule r\*** (`strategies/cycle_tilt.py`): default neutral real
     rate 0.5% → classic Taylor (1993) 2.0%.
  13. **GEX sign** (`strategies/derivatives_gamma.py`): call OI → + dealer
     gamma, put OI → − (mainstream SpotGamma convention; was inverted).

### Changed
- **Wiring audit: prompt guidance for every analyst-bound tool**.
  New AST gates in `tests/test_calc_agent_wiring.py` catch (a) tools bound to
  an analyst's tool list but never explained in its `system_message`, and (b)
  the existing orphan-calc + unbound-tool gates. Closed 28 real gaps: added
  'cite it before any X claim' guidance for 6 fundamentals tools (regime state,
  kalman spread, position risk multiplier, Black-Litterman allocation,
  dividends, Form-4 insider), 16 market tools (indicators, GARCH/vol
  estimators, shift detection, mean-reversion quality, options surface, Merton
  distance, earnings-quality verdict, tail decomposition, universe membership,
  regime/risk-multiplier, stock/crypto data, Alpaca snapshot, cost models,
  momentum scan, debate-claims verdict), 5 news tools (earnings catalyst,
  insider transactions, GDELT sentiment, market breadth, IPOs), and news
  grounding in the sentiment analyst.
### Fixed
- **Vendor outage hardening** (option 1 from the no-data audit;
  `docs/developer/03-dataflow-vendors.md`): the four flow-critical categories
  (`core_stock_apis`, `technical_indicators`, `fundamental_data`, `news_data`)
  joined `OPTIONAL_CATEGORIES`, so a total vendor outage (every vendor in the
  chain raising network/auth/rate-limit errors) returns the `DATA_UNAVAILABLE`
  sentinel instead of re-raising the first error — the graph no longer dies on
  a ToolNode exception when `get_stock_data` / `get_indicators` / the
  statement tools / `get_news` all fail. The analyst proceeds and reports
  "unavailable". Clean no-data and disabled-config sentinels are unchanged;
  per-vendor failures are still logged (never silent); a single vendor failing
  while another can serve it still falls through. The sentinel text now says
  "`<category>` could not be retrieved" (drops the now-wrong "optional" label).
  Tests updated to the new contract (vendor_routing
  `test_core_category_degrades_on_error`, vendor_absence
  `test_typed_wrapper_rate_limited_core_attaches_absence` — the typed wrapper
  now attaches the `rate_limited` envelope instead of raising,
  moomoo_vendor `test_moomoo_alone_and_failing_degrades`).
- **Earnings quality wired to the consensus verdict** (option 1): the
  ticker-based `get_earnings_quality` now fetches canonical statements
  (net income / OCF / total assets / capex) and runs the consensus
  `earnings_quality_verdict` as its evidence layer (cash conversion,
  accrual ratio, FCF = OCF - |capex|, negative-FCF red flag) while keeping
  the forensic trap; the old ad-hoc 6%/2% accrual band (whose
  "low-earnings-quality-risk" label read backwards for high accruals) is
  superseded by the consensus 5%/10% bands. `capex` in the verdict is now
  sign-robust (abs, matching dcf.py) so a GAAP-signed outflow can't
  inflate FCF. Tests: consensus-render assertions + capex red-flag/sign
  cases; wiring gate green; ruff clean.
- **Quant-engine v2 audit** (pre-agent-wiring calculation check): (1) DuPont driver was `argmax |factor|` (= always the biggest leg — mislabeled a normal-leverage firm "leverage-led" and a loss-making firm "equity_multiplier-driven") → replaced with log-DuPont attribution vs the neutral 1.0 benchmark (margin/turnover/leverage/mixed labels; non-positive margin always the story); (2) scenario DCF silently coerced `g_base=0.0` to 3% → respected now; added the design-promised market price → band (below bear / bear-base / base-bull / above bull) + per-scenario margin of safety (and `-0.0` fcf_scale cleanup); (3) earnings-quality returned `LOW` on no inputs (dead `n/a` branch) → level now None (n/a) when nothing is usable, and the render says "concern" so HIGH can't be read as "high quality". Wired the trio into the fundamentals analyst (import + tool list + prompt) — the graph ToolNode already had them. Tests `test_quant_engine_v2.py` (19) + `test_analysis_tools.py` renders (7); wiring gate green; ruff clean.
### Fixed
- **Sector rotation screen: breadth gate + real EW/CW index (review fix)** -
  structural-review fixes: (1) breadth is now **denominator-gated** (sample
  < 20 renders n/a 'not a breadth read' instead of a noisy % from 1-3
  tickers); (2) the EW/CW ratio now uses the **real Invesco RSP* equal-weight
  sector index** per sector (`EW_CW_ETFS`: RSPT/RSPF/RSPH/RSPD/RSPN/RSPM/
  RSPG/RSPU/RSPC/RSPR/RSPS, current 2026-06 tickers) instead of the
  micro-sample reconstruction, **normalized against its own 50d SMA**
  (broadening/narrowing + spread% vs baseline) - unitless return ratio,
  immune to share-price levels; (3) breadth and EW/CW are now **separate
  lines** - a sector can never be called 'broadening' from a 1-ticker sample.
  Live: XLK/RSPT narrowing -53.5% (megacap concentration), XLC/RSPC +3.7%
  broadening, all breadth n/a sample<20. Tests: gate, price-level immunity,
  map completeness (20 screen tests green).
### Added
- **Sector breadth layer (McClellan/MSI/multi-timeframe, review-driven)** -
  `strategies/sector_breadth.py`: (1) multi-timeframe breadth matrix
  (% > 20d/50d/200d, n-gated); (2) per-sector McClellan Oscillator
  (EMA19-EMA39 of the size-normalized daily net A-D, cumulative-sum MSI -
  the correct definition; fixed a steady-state-zero artifact on
  one-directional markets and a negative-slice `_sma` bug that broke the
  whole matrix); (3) RRG heading + constructive/weakening-trap flags
  (`rrg_heading`, standalone); (4) advisory MSI-zone risk-budget note
  (never a gate). Wired into `get_sector_rotation_screen`
  ('## Sector breadth matrix' table: n / 20d / 50d / 200d / MO / slope /
  MSI / RRG). 9 hermetic tests.
- **Sector rotation screen: full S&P-500 universe (review fix 2)** -
  `dataflows/sp500_universe.py` harvests the full S&P-500 constituent table
  (Wikipedia REST wikitext, keyless, disk-cached weekly) and maps GICS
  sector -> SPDR ETF. `get_sector_rotation_screen` with
  `constituent_universe='eodhd'` now uses THIS universe (no alphabetical
  cutoff): every constituent per sector gets its OHLCV through the run cache,
  breadth is computed on the real sector denominator (n=20-60 samples vs the
  previous 1-3), EW/CW stays RSP*-based + own-50d-normalized. Kills the
  'sample truncation' distortion. n_total ~315 constituents, sector n shown.
- **Sector rotation screen: EODHD constituent universe for breadth** -
  the breadth/EW-CW/setup layer can now be driven by the EODHD full-US
  symbol list (`get_exchange_symbols_eodhd`, ~51k symbols, major-exchange
  filtered) instead of the static curated subset: GICS + sub-industry
  sector bucketing (`sector_group_of`, alias map extended for the yfinance
  sub-industry granularity), per-sector cap + classifier budget with an
  early-bail when every lookup fails, in-process lookup cache, and breadth
  rendered for every sector with classified members (n shown - small n is
  noisy, raise eodhd_cap). Tool: `constituent_universe='eodhd'` param or
  `enable_sector_eodhd_constituents` config. Live: 8 sectors breadth/EW-CW
  + Setup A/B states. LLM-facing, advisory, budget-capped for free tiers.
- **Sector rotation screen (P1-P4, design doc)**: new
  `strategies/sector_screener.py` + `get_sector_rotation_screen` tool (market
  analyst): regime (SPY>SMA200+slope) grade cap + multi-factor SPDR rank
  (momentum/RS/trend/risk reusing sector_rank) + RRG quadrant +
  pullback-divergence leader flags + dispersion trend; constituent
  breadth/EW-CW/Setup-A-B behind enable_sector_breadth; P4
  scripts/validate_sector_rotation.py after-cost gate (with-cost rotation
  Sharpe 0.655/IR 1.05 < equal-weight 1.10/1.40 -> screen is context-only,
  no outperformance claim). LLM-facing only (web untouched by design rule).
- **Industry-depth tools (spec rec 1-2)**: `get_edgar_fulltext_search(query,
  forms?, date_range?)` - SEC EDGAR full-text search (efts.sec.gov, keyless):
  fetch the 10-K customer/supplier-concentration footnote ('major customer'),
  peer mentions, thematic scans (filings since 2001); `get_patent_activity(ticker)`
  - USPTO PatentsView granted-patent counts + recent titles (name-based
  assignee match; free PATENTSVIEW_API_KEY; new-API host was unresolvable at
  build, honest degrade otherwise). Both wired to the fundamentals analyst +
  graph ToolNode with prompts; router categories sec_filings (extended) +
  patents (optional, key-gated).
- **Order-flow depth (spec items 1-2, official FINRA keyless)**:
  `get_dark_pool_flow(ticker, weeks?)` - FINRA ATS weekly off-exchange
  share/trade/notional flow (OTC Transparency); `get_short_sale_volume(ticker,
  days?)` - FINRA Reg SHO daily short-sale volume (% short-sale of volume),
  keyless variant beside the Massive-backed get_short_volume. Both render the
  served as-of dates with a staleness gate (FINRA's public consumer tier serves
  a historical window; a free FINRA API key upgrades to the current daily
  file) - never present old data as current. Wired to the market analyst
  (imports + tool list + prompt) + graph ToolNode; router categories
  dark_pool_flow + short_sale_volume (optional, degrade).
- **Macro-strategist depth (spec: liquidity/FX/commodities/global rates)**:
  FRED alias extensions (liquidity: tga/reverse_repo/repo/fed_balance_sheet/effr/sofr;
  commodities: wti/gold/natgas/copper; global policy rates: ecb_rate/boj_rate),
  `get_tga_balance` (US Treasury Fiscal Data API, keyless; daily operating cash
  + net draw/build = reserve injection/drain read), `get_fx_snapshot` (yfinance
  DXY + major pairs, delayed advisory). All wired to the news analyst + graph
  ToolNode with prompts; router category macro_liquidity (optional, degrades).
- **Fundamentals-analyst depth (spec gaps 1-3)**: `get_earnings_transcript`
  (FMP Earnings Transcript API, free tier; date/quarter + excerpt, never
  fabricated quotes), `get_congress_trades` (House + Senate Stock Watcher
  mirrors, keyless; net buys/sells + samples per chamber),
  `get_financial_history` (SEC EDGAR XBRL companyconcept, keyless; annual
  10-K revenue/NI/OCF/capex/assets/liabilities/equity/cash ~10-15y, honest
  pre-XBRL n/a). All wired to the fundamentals analyst + graph ToolNode with
  prompts; router categories earnings_transcripts / congress_trades +
  sec_filings extended; also fixed the SEC User-Agent (the bare project-form
  UA was 403-rejected by EDGAR: 404/403 on every host now returns data).
- **Quant-formula Phase 6** (the research-plan 'medium effort' items;
  `docs/design_quant_formulas_research.md` A6-H2): lottery-tilt screen
  (`strategies/lottery.py`: MAX = largest single-day return over the trailing
  month, IVOL = idiosyncratic residual vol vs the market with a total-vol
  fallback; `get_lottery_factors`, market analyst — a high-octane name with
  high MAX/IVOL is EXPECTED to underperform, a quality penalty),
  Almgren-Chriss optimal execution + TWAP/VWAP/POV benchmarks
  (`strategies/execution_schedule.py` + `get_execution_schedule`: hyperbolic
  front-loaded trajectory with E[IS]/var(IS), advisory scheduling),
  CPPI + vol-target overlay (`portfolio.cppi_exposure` = m * max(P - floor, 0)
  clamped to PV + the existing `size.volatility_target_scale` folded into
  `get_risk_overlay`, market analyst). All advisory, None-safe, wired with
  prompts; wiring gate green; tests p6 (8 lottery + 6 execution + 6 overlay);
  ruff clean.
- **Quant-formula implementation (phases 1-5 of the research plan; `docs/design_quant_formulas_research.md`)** - P1 options: speed/zomma 3rd-order Greeks in `black76` (+ ATM render in `get_options_iv_read`), 25-delta risk-reversal / butterfly / term-structure shape (`options_surface.surface_shape` + `get_vol_surface_shape`, market analyst), put-call parity conversion/reversal screen (`parity_violation` + `get_parity_screen`, market analyst). P2 risk metrics: Cornish-Fisher modified VaR (`size.modified_var` + `get_tail_risk` line), Kappa/LPM (`rate_utils` + `get_downside_read`), Burke/Martin/Pain + gain-to-pain (`evaluate` + `get_strategy_quality` rows), risk-of-ruin + optimal f (`size` + `get_position_sizing` ruin line). P3 statistical: Lo-MacKinlay variance ratio (`mean_reversion.variance_ratio` + MR-quality render), CUSUM/EWMA online shift detection (`regime.cusum/ewma_control` with calib-window anchoring + `get_shift_detection`, market analyst), permutation/approximate/LZ entropy (`complexity.py` + MR-quality render). P4 accounting: Ohlson O-score + Zmijewski X-score (`normalized` + `get_analyst_verdict` rows), Dechow-Dichev accrual quality (`earnings_quality.dechow_dichev_aq`; honest n/a line). P5 macro: Taylor-rule implied rate + deviation + macro stance (`cycle_tilt` + `get_taylor_read`, news analyst). All advisory, None-safe; bound with prompts (market: surface-shape/parity/shift; news: taylor); wiring gate green; tests +quant p1-p5 (12+15+12+9+6 = 54); ruff clean. See the research doc for the ranked gap list.
- **Quant-engine v2** (per the 69-section quant spec + user; `docs/design_quant_engine_v2.md`): DuPont 3/5-factor ROE decomposition (`strategies/dupont.py` + `get_dupont_read` — explains why ROE is high, margin vs turnover vs leverage), scenario DCF (`strategies/scenario_dcf.py` + `get_scenario_dcf` — bear/base/bull value range with growth ±2% + margin shocks), earnings-quality verdict (`strategies/earnings_quality.py` + `get_earnings_quality_verdict` — cash conversion OCF/NI, accrual ratio, negative-FCF red flag, rising-EPS-with-falling-FCF penalty). Tests `test_quant_engine_v2.py` (10) + `test_analysis_tools.py` +4 render; suite green; ruff clean. See the design doc.
- **Quant-engine additions** (per the end-to-end quant spec review; `docs/design_quant_engine_additions.md`): HRP (`strategies/hierarchical_risk_parity.py` + `get_hrp_alloc` — Lopez de Prado single-linkage HRP, robust/no-inversion, equal-weight degrade), 12-1 momentum (`strategies/momentum.momentum_12_1` + `get_momentum_12_1` — Jegadeesh-Titman, skips last month), Omega row in `get_strategy_quality` (via existing `statistical.omega`), industry-neutral z (`cross_section.industry_neutral_z` — winsorize → demean-by-sector → z). Tests `test_quant_engine_additions.py` (10); suite 210 green; ruff clean. See the design doc + api_reference.
- **Option-position breakeven / PMCC advisory read** (per the AVGO PMCC
  sample review + user's "go straight to implementation") —
  `strategies/options_breakeven.py` + `get_option_breakeven` tool (market
  analyst; always-on advisory like `get_cycle_tilt`):
  - `pmcc_breakeven` = long strike + premium paid per share (cost basis held
    to expiry); `short_call_discipline` = the PMCC floor rule (sold strike
    must exceed breakeven, with cushion); `long_leg_time_split` =
    intrinsic vs extrinsic (time) value + ITM flag; `delta_profile` (deep-ITM
    0.75-0.85 long / 0.20-0.30 short advisory bands); `theta_zone` (30-45d
    rent window); `catalyst_window` (earnings imminence -> never hold a
    low-strike short call through it); assignment note on ex-div near-term.
  - Everything None-safe (missing input -> n/a, never fabricated); negative
    inputs -> None; `pmcc_read` combines it all + labels inputs.
  - Bound via the wiring gate (market analyst import + tool list + prompt
    line, graph market ToolNode, agent_utils re-export + `__all__`).
  - Tests: `test_options_breakeven.py` (11: breakeven sum, floor ok/violate/
    None, intrinsic/extrinsic split + OTM-lock, delta bands, theta zones,
    catalyst imminence, combined AVGO sample, partial-input n/a) +
    `test_analysis_tools.py` +3 render tests (full/partial/never-aborts).
    Suite: 151 passed / 2 pre-existing skips; wiring gate green; ruff clean.
  - No execution, no trading_web change (LLM-facing tool).
- **Sector-rotation research actions 1+3+2 implemented** (per the web-research
  findings + user instruction; `strategies/formulas/sector_rotation.md`):
  - **A1 — RRG quadrant** (`strategies/sector_rank.py`): `rrg_quadrant(
    rs_level, rs_momentum)` — the RS-level percentile (ranking) and the
    RS-momentum percentile (RS-ratio acceleration, NEW axis) are kept
    SEPARATE → Leading / Weakening / Improving / Lagging (median split,
    None-aware; not until both axes resolve). The multifactor ranking carries
    a `quadrant` field; `get_sector_rank` emits a rotation line
    ("Leading=…; Improving=…") and an exit line ("Weakening=…") plus a
    cadence note (monthly rebalance, hold top 2-3, trim on Weakening,
    turnover is the main cost risk — A3). Advisory; gated by
    `enable_sector_multifactor`.
  - **A2 — Business-cycle tilt** (`strategies/cycle_tilt.py` + `get_cycle_tilt`
    tool bound to the market analyst): phase = early/mid/late/recession from
    PMI (FRED NAPM alias added) + 10y-2y spread + HY OAS; `TILT_MAP` → favored
    sectors. All inputs None-safe (missing → phase None, tilt [], "n/a" —
    never fabricated). `fred.get_macro_value` returns the latest float
    directly (never raises). Advisory — the regime-gate enhancement.
  - **A4/validation script**: research option, NOT built (per plan).
  - Tests: `test_cycle_tilt.py` (9: phase rules, None-degrade, TILT_MAP);
    `test_sector_rank.py` +5 (quadrant mapping/boundaries/None/carry/field);
    `test_analysis_tools.py` +3 (cycle-tilt render/n-a/never-aborts) + gated
    rotation render. Suite: 212 passed / 2 pre-existing skips; wiring gate
    green (get_cycle_tilt bound); graph import OK; ruff clean.
  - No trading_web change (both tools are LLM-facing).
- **Sector-rotation P1-P3 implemented** (per `strategies/formulas/sector_rotation.md`):
  `strategies/sector_rank.py` gains the multi-factor machinery, additive to
  the legacy single-factor path (byte-identical default):
  - P1 `rank_sectors_multifactor` — tie-aware cross-sectional percentiles
    over momentum (21/63/126/252d composite + acceleration), RS vs the SPY
    benchmark, trend (P/SMA50 + P/SMA200 + MA alignment), risk
    (Sharpe-126 blended with 1 - |MDD-126| percentile); weighted score
    (FACTOR_WEIGHTS .37/.21/.21/.21) with rank + factors; same result shape
    so `sector_standing` consumes it unchanged. None-safe throughout.
  - P2 `rank_industry_group` + `INDUSTRY_ETFS` — industry ETFs (SOXX/IGV/
    HACK/CLOU/SMH/XBI/IBB/KRE/XHB/XAR/XOP/XRT) ranked ONLY inside their
    parent sector (never XLK+SOXX in one pool); single-factor by default,
    multi-factor when a benchmark is supplied.
  - P3 `constituent_breadth` + `leadership_ratio` + `SECTOR_CONSTITUENTS`
    (curated core subset, documented small) — % above SMA50 and the
    EW-vs-CW leadership ratio.
  - `get_sector_rank` renders gated advisory lines when the config keys are
    on: P1 `enable_sector_multifactor`, P2 `enable_sector_industry`, P3
    `enable_sector_breadth` (all default OFF ⇒ legacy output unchanged; any
    unresolvable factor renders n/a).
  - Tests: `test_sector_rank.py` 24 (multifactor ordering/bounds/normalization/
    standing-consumption, industry parent-gating + names, breadth fraction,
    EW/CW ratio + insufficiency, weights sum, documented-constituents);
    `test_analysis_tools.py` gated-render tests (default-off unchanged,
    P1/P2/P3 lines when on). Suite: 210 passed / 2 pre-existing skips.
  - No trading_web change (the read is LLM-facing, not a web capability).
- **Sector-rotation reference** - `strategies/formulas/sector_rotation.md`:
  distilled from two deleted LLM-generated specs (`sector_calc.md`,
  `sector_instruction.md` — removed after distillation, were untracked).
  Single surviving source for the 12-ETF sector-rotation design: staged
  Market→Sector→Industry→Stock→Entry→Sizing→Portfolio-Risk pipeline
  (regime is a gate, not a factor; score ≠ signal), reconciled 8-factor
  100-point sector score (momentum 25 / RS 15 / trend 15 / risk 15 /
  breadth 10 / valuation 10 / flow 5 / fundamentals 5, variant B
  momentum-heavy when breadth/valuation data lacks), cross-sectional
  percentile normalization, grade table + regime cap, two-level universe
  (11 SPDR sectors + industry ETFs like SOXX, never ranked in one pool —
  resolves the spec conflict), and the two genuinely new factors
  (constituent breadth; EW-vs-CW leadership ratio). Maps onto existing
  `strategies/sector_rank.py` (momentum-only today): P1 multi-factor
  extension (RS/trend/risk/acceleration), P2 industry layer, P3
  breadth+EW/CW (fetch-heavy, cached). Rejected outright: the spec's
  "expected return/risk" construction (`evaluate.py` + CPCV/PBO is the
  repo's method). Design only; no code changed.

### Changed
- **LLM client request-timeout fix** (diagnosis: "interactive CLI job stuck
  re-trying truncated output" under provider congestion — DeepSeek US-night
  peak). Two latent bugs: the `timeout` key in the openai-compatible and
  anthropic passthrough lists was NOT a valid constructor arg in the
  installed langchain SDKs (a TypeError at construction), and no default
  timeout was ever set — so a stalled provider stream could hang
  `chain.invoke` and the truncation/stub retry loop indefinitely. Now:
  `timeout` maps to the SDKs' real fields (`request_timeout` /
  `default_request_timeout`), both are valid passthrough args, and every
  request defaults to 300 s (explicit `timeout`/`request_timeout`/
  `default_request_timeout` wins). A wedged provider now raises and
  degrades instead of hanging the job. Tests: `tests/
  test_llm_client_timeout.py` (9: alias mapping, default, explicit-wins, for
  both clients); `test_anthropic_effort.py` `test_other_kwargs_...` updated
  to the corrected mapping (was pinning the latent-broken `timeout` kwarg).
  Docs: api_reference §2 request-timeout note. Suite: 53 client/agent/
  wiring tests + 2 pre-existing skips green; real (un-mocked) deepseek +
  anthropic construction smoke-tested.

### Added
- **myhhub/stock teacher study** - `docs/design_myhhub_stock_integration.md`:
  direct-source study of the Chinese A-share rule-based quant platform
  InStock (`instock/`: MySQL daily-job pipeline, uniform
  `check(...) -> bool` strategy predicates with min-observation self-guards,
  trading-calendar singleton with None fallbacks, declarative web table
  registry, live-trade robot + Eastmoney cookie-triangle fetcher). Adopted
  as 4 advisory, phase-gated, default-off items: P1 managed trading-calendar
  cache (`dataflows/trading_calendar.py` feeding the existing
  `effective_date.non_trading_days` override — serves the yfinance A2/P2
  "exchange closed vs no data" calendar half), P2 session-aware scheduling
  hint (`run_nightly` + web jobs `session=pre|after|any`; skipped mid-session
  jobs), P3 min-obs guard helper (`strategies/obs_guard.py` +
  `require_observations` convention; no migration of existing guards), P4
  env-first credential-priority note (docs). Validation table: fork already
  ahead on backtest metrics (evaluate.py vs rate_stats.py), stepwise jobs,
  web surface; uniform-predicate full layer is deliberately NOT built (the
  ai-hedge-fund mandate AlphaModel is the right shape for typed views).
  Explicit non-goals: live-trade robot (TradingExecution successor), MySQL
  persistence (stateless-per-run + FinceptTerminal P4 plan), chip
  distribution, A-share feeds, GUI. Design only; no code changed.
  Strategies/index row 27.
- **anthropics/financial-services teacher study** - `docs/design_anthropic_financial_services_integration.md`:
  direct-source study of the Anthropic financial-services monorepo (skills
  authored once under `vertical-plugins/*/skills/`, vendored into agent
  bundles with a `check.py` byte-identity drift gate + reference-resolution
  gate; "one source, two wrappers" agent prompts reused by Cowork plugin and
  headless `agent.yaml`; per-subagent `output_schema` enforced harness-side
  by `validate.py`; data-vs-directions guardrails in every agent/skill).
  Adopted as 5 advisory, phase-gated, default-off items: P1 skill-sync drift
  gate (extends `test_calc_agent_wiring` with a parse gate + skill
  reference-resolution gate + drift check — the skill-layer half of the
  fork's permanent wiring discipline), P2 data-vs-directions guardrail
  (news/filings/earnings tool prompt preamble + `disclosure_footers` row),
  P3 declared output shape + harness-side advisory validation (extends
  `structured.py`; `None` still degrades, never blocks), P4 trigger-phrase
  discipline for skill YAMLs, P5 one-source/two-wrappers assessment note.
  Validation table shows the fork already ahead on per-role analysts,
  tool-catalog governance, and disclosure. Explicit non-goals: MCP
  connectors (.mcp.json), Cowork plugins / claude-for-msft, Claude Managed
  Agents deployment, partner plugins, version-bump git hooks, slash
  commands. Design only; no code changed. Strategies/index row 26.
- **yfinance teacher-study phases P1 + P5 implemented** (per user: adopt
  only these two):
  - **P1 typed absence reasons through the read envelope** -
    `dataflows/errors.py` gains `VendorAbsence` (frozen dataclass:
    `reason ∈ no_data | rate_limited | not_configured | error | unknown`,
    `source`, `retryable`, `detail`; `from_error()` taxonomy + JSON-safe
    `to_dict()`). `dataflows/interface.py`: `route_to_vendor` keeps its
    plain-string contract (sentinels unchanged) and carries the chain-end
    reason via a per-call contextvar side channel (`_last_absence`, reset at
    the top of every call and after the typed read — no cross-call/thread
    leak); the reason follows the verdict (NO_DATA → the no-data vendor's
    reason; optional DATA_UNAVAILABLE → the first real error). The typed
    wrapper reads it onto `VendorResult.absence` (new field + `to_dict`).
    `analysis_tools._ohlcv` envelope gains `absence` (via
    `route_to_vendor_typed`), `run_card.json` gains a `data_absence` block
    (null on success), trading_web `/api/ohlcv` returns `absence` on the
    no-history path. CLI period/interval validation was N/A (no such CLI
    exists — all CLIs take dates/bars). Always-on but read-only (new fields
    default null); scripts/* string callers untouched. Tests:
    `tests/test_vendor_absence.py` (15: taxonomy, string-contract guard,
    envelope reasons, verdict-follows-reason, no-leak).
  - **P5 deliberate yfinance pin** - `yfinance>=1.4.1` →
    `yfinance~=1.4` (requirements.txt + pyproject.toml); new
    `tradingagents/dataflows/README.md` vendor notes (guarded quirks
    #986 exclusive-end, #1021 stale frames, unnamed index, statements
    newest-first, `yf_retry` rate-limit backoff) + version-bump checklist.
- **yfinance v1.7.0 teacher study** - `docs/design_yfinance_integration.md`:
  direct-source study of `ranaroussi/yfinance` v1.7.0 (the v2 rewrite:
  `data.py` YfData + Auth cookie/crumb, `_http.py` backend abstraction,
  `cache.py` SQLite KV caches, `base.py` ticker-tz fetch + validation +
  invalidation, `scrapers/history.py` price repair, `multi.py` download
  error grouping, typed `exceptions.py` taxonomy) + full inventory of the
  fork's existing yfinance integration and web grounding on the 1.x line.
  Adopted as 5 advisory, phase-gated, default-off items: P1 typed absence
  reasons through the read envelope (`VendorAbsence(reason, source,
  retryable, yahoo_reason)` + OHLCV `absence` field + CLI period validation
  with valid options), P2 exchange-tz + currency KV cache for OHLCV reads
  (`dataflows/exchange_tz.py`, validated + invalidated + capped; `tz`/
  `currency` on the OHLCV envelope; statement currency prefers the cache
  over the ADR heuristic), P3 100x currency-unit repair (config-gated,
  detected + flagged via tolerance bands, ambiguous refuses, never silent),
  P4 batch error grouping + debug-serialize rule (grouped failure summary +
  debug⇒single-thread), P5 deliberate `yfinance~=1.4` pin + vendor quirk
  notes (#986 exclusive-end, #1021 stale frames, unnamed index). Validation
  table shows the fork already adopted the retry/typed-error/stale-guard/
  statement-currency/sentinel-cache halves. Explicit non-goals: WebSocket
  live pricing (protobuf), login cookies + tier scraping, SQLite persistent
  caches, curl_cffi impersonation, ISIN lookup, typed screener DSL, domain
  objects. Design only; no code changed. Strategies/index row 25.
- **FinceptTerminal v4 teacher study** - `docs/design_fincept_terminal_integration.md`:
  direct-source study of `Fincept-Corporation/FinceptTerminal` v4 (C++20 +
  Qt6 desktop terminal w/ embedded Python 3.11; `src/datahub`, `src/
  services/llm`, `src/trading`, `src/mcp`, `scripts/agents/finagent_core`,
  `scripts/ai_quant_lab`, `docs/DATAHUB_TOPICS.md`, `docs/
  agentic-research/`) + web grounding. Adopted as 6 advisory, phase-gated,
  default-off items: P1 typed topic-registry refresh policy (per-family
  TTL / min-interval / coalesce / force-bypass / freshness fields + a
  `docs/web_TOPICS.md` registry — trading_web REST seam), P2 tool-result
  size budget with park-and-page (`agents/utils/result_store.py` +
  `fetch_result` tool + `max_bytes` envelopes with `truncated`/`result_id`
  — detail on demand, not by default), P3 dual tool-loop budget + visible
  exhaustion (`run_card` + jobs rows gain `tool_rounds_used` /
  `tool_deadline_exhausted` / `exhaustion_note`; web job view shows the
  last probe line), P4 SQLite per-step checkpoints + resume (`jobs.
  checkpoint_json` + `resume_job` capability; crash mid-batch resumes
  un-done symbols), P5 org-as-data governance metadata
  (`consensus.agreement_weighted` + `n_abstained` decision context + PM
  statistical-rigor criteria + persona metadata doc — composes with the
  ai-hedge-fund abstention study), P6 single-source-of-truth capability
  cross-check gate (`test_web_capabilities`: every JSX capability string
  resolves in `backend/capabilities.py`, public capabilities referenced or
  documented API-only). Validation table: fork already ahead on
  multi-provider LLM registry, Qlib teacher study, backtest PIT/fill
  semantics. Explicit non-goals: C++/Qt6 frontend, paper-trading runtime,
  crypto/$FNCPT tokenomics, MCP marketplace, Ollama-default, Qlib
  wholesale wrapper, per-persona SQLite session memory. Design only; no
  code changed. Strategies/index row 24.
- **ai-hedge-fund v2 teacher study** - `docs/design_ai_hedge_fund_integration.md`:
  direct-source study of `virattt/ai-hedge-fund` v2.2.0 (hedge_fund/: data,
  signals, llm, features, fund, strategies, portfolio, risk, brokers,
  pipeline, backtesting, event_study, validation, tui) + web grounding.
  Adopted as 5 advisory, phase-gated, default-off items: P1 declarative
  mandate (fund/strategy/model as YAML data — `strategies/mandate.py` +
  `strategies/mandates/*.yaml` + `pipeline.py --mandate` +
  `scripts/mandate_rebalance.py`), P2 event-study market-model CAR with
  t-test + bootstrap CI significance (`strategies/event_study.py` +
  `pead_car_test` in `events.py` + `get_event_study_read` tool), P3
  abstention-vs-neutral conviction blending (`consensus.agreement_weighted`
  + `n_abstained` in the computed context), P4 per-clamp risk audit events
  (`portfolio.clamp_events` rendered in allocation reads), P5 prompt-level
  provenance vault (exact prompts + responses per decision, keyed to
  `research_decision.json`). Validation table shows the fork is already
  ahead on CPCV/PBO/evaluate metrics/LLM registry. Explicit non-goals:
  live brokers, the TUI, persona voicing, financial-datasets provider,
  market-neutral shorts, per-call prompt caching for cost — the
  no-execution/advisory mandates stand. Design only; no code changed.
  Strategies/index row 23.
- **Hummingbot V2 teacher study** - `docs/design_hummingbot_integration.md`:
  direct-source study of the Hummingbot V2 framework (StrategyV2Base /
  Controllers / Executors / Connectors, backtesting executors-simulators,
  paper-trade connector, budget checker, async notifier, SQLite executor
  ledger) + web grounding. Adopted as 5 advisory, default-off, phase-gated
  items mapped onto existing seams: P1 exit-accounting
  (`exit_cause_frequency` + `close_type` backtest tagging + report block +
  `exit_cause_read`), P2 pre-trade budget as a stateful collateral lock
  (`CollateralLock` + `available()` in `get_pre_trade_read`, sharing the
  backtest envelope), P3 live-book fill-latency paper model
  (`fill_latency_model` / `paper_fill_price`, advisory default-off
  `get_fill_model_read`), P4 unified executor-ledger schema
  (docs-only spec reusing the alpha-ledger row + pnl/fee columns), P5 async
  queue notifier (`monitor.notify` queue-drain). Explicit non-goals: live
  execution/order management, the controller runtime, encrypted keystore,
  per-exchange websocket feeds, MCP/skills — the fork's advisory-only,
  math-decides mandates are unchanged. Design only; no code changed.
  Strategies/index row 22.
- **Calc → agent wiring gates (no more silent gaps)** - the wiring audit is
  now a permanent test, not a one-off find:
  1. `test_calc_agent_wiring` per-fn rule tightened: a public calc counts as
     wired only when referenced OUTSIDE its module, or as an internal helper
     of a module that is itself externally reachable — the old "self-count
     escape" (a fn referenced only by its own module's text) no longer
     passes, and the module-level gate fails any wholly-unreachable module.
  2. NEW `@tool` → agent-surface binding gate: every public LangChain `@tool`
     in `agents/utils/*_tools.py` must appear in the graph ToolNode lists /
     risk-tool loop / analyst bindings, or fail. It immediately caught 4
     tools that were defined and exported but never bound since the
     7-phase risk wiring: `get_pair_risk`, `get_trade_excursions`,
     `get_vif_read`, `get_no_trade_guard_band` — now bound (market /
     fundamentals).
  3. Whitelist purge: the "future work will wire it" entries are gone.
     `prediction_ledger.score_all/score_outcome/outcome_metrics` and
     `regime_performance.stress_grid/macro_regime` are now wired as
     agent tools: `get_prediction_ledger_score` (calibration read),
     `get_trade_outcome_metrics` (MAE/MFE), `get_stress_grid_read`
     (DCF-style scenario grid), `get_macro_regime_read` (cross-asset
     regime) — all bound to the market node + web Value Tools. Remaining
     whitelist entries are permanent classifications (design-reference
     `typed_state` W4-2, dev-ops `complexity_report`, `iv_percentile` needs
     a per-day IV history no vendor ships), each with a stated reason.
- **Formula-catalog additions (six-pillar / master-catalog)** -
  ``strategies/covariance_models.py`` (NEW): Ledoit-Wolf (2004) shrunk
  covariance (scaled-identity / diag targets, ``delta = clip(b2/d2, 0, 1)``,
  web-verified formula) + RiskMetrics EWMA covariance; ``yang_zhang_vol``
  (overnight + range, drift-independent — completes the estimator set;
  ``get_volatility_estimators`` now renders close/Parkinson/GK/**YZ**/EWMA/
  GARCH). ``strategies/portfolio.py``: book-concentration suite
  (``active_share`` / ``weight_hhi`` / ``effective_holdings`` /
  ``weight_entropy``) + multi-asset fractional Kelly
  (``kelly_weights`` = ``f·Σ⁻¹μ``, long-only clip; ``allocation_block``
  switches onto it via ``enable_kelly_alloc``). ``strategies/book_risk.py``:
  EVT/GPD peaks-over-threshold ``extreme_quantile_var`` (extreme-quantile
  VaR + GPD ES, extrapolates beyond the observed worst day). 
  ``strategies/liquidity_risk.py``: ``kyle_lambda`` daily-bar price-impact
  slope (OLS of ΔP on signed volume). New advisory tools bound to the
  market + fundamentals ToolNodes: ``get_covariance_read``,
  ``get_concentration_read``, ``get_tail_extreme_var``, ``get_kyle_lambda``,
  ``get_kelly_alloc`` (+ YZ row in ``get_volatility_estimators``). Config:
  ``covariance_shrinkage_enable`` / ``covariance_shrinkage_target`` /
  ``enable_kelly_alloc`` / ``kelly_alloc_fraction`` (all default off,
  existing runs bit-identical). Tests: ``test_strategies_covariance_models``
  (8), ``test_formulas_p2`` (11), ``test_formulas_p3`` (7) — all hermetic.
  trading_web Value Tools += 5 (capabilities/App/README); docs
  api_reference + Strategies/index synced. See next entry.
- **Value-dip falling-knife velocity-z gate (`--knife-z`) + batch `--probe` tracing** -
  the value screener's value-dip scan can now enforce the falling-knife
  velocity-z guard: ``--knife-z -2.5`` blocks candidates whose 3-day price
  velocity z drops below -2.5 (the unresolved-cascade case the composite
  knife guard warns about), mapping onto the existing
  ``value_dip_setup`` ``require_knife`` / ``knife_velocity_threshold`` seam.
  The knife rows were always displayed; the flag just decides whether they
  gate. Wired for the tickers / eodhd-us / eodhd-losers universes (the
  flagships) via ``_compute_scan_row`` as well as the moomoo movers loop
  (the WIP slice only had the movers path — fixed). Also added
  ``strategies/orderflow.knife_guard_vpin`` (downside-conditioned VPIN
  toxicity filter; the guard only suppresses dip-buys when high VPIN
  coincides with a down move, never blocks up-breakouts). New hermetic
  tests ``tests/test_value_screener.py`` (semantics + CLI seam). Trading-web
  mirrors: ``run_screener`` ``knife_z`` + ``--knife-z``, the Screener form
  gains the field, web README synced. ``batch.py --probe`` writes a
  per-stage trace JSONL (``batch_probe_*.jsonl``: symbol / stage /
  elapsed / error / ``wall_seconds`` / per-worker ``data_vendors``) around
  the graph run — graph_start, graph_done, graph_failed(re-raise) — so a
  hung or failed symbol shows exactly which stage broke;
  ``tests/test_batch_probe.py`` (3, hermetic).
- **Structured PM decision persisted (`pm_decision`)** - `agent_states.AgentState`
  gains `pm_decision`; the Portfolio Manager node captures the structured
  PortfolioDecision (post-guardrail, `model_dump(mode=json)`) and returns it
  in state, so the `research_decision.json` emitter + prediction-ledger log
  read the REAL rating/data_quality/guardrail_reason instead of defaults.
  Legacy runs (pre-fix) keep nulls and are fail-closed by the executor.
- **fix(risk): governor's drawdown stop now uses the measured book drawdown** -
  ``trading_graph`` fed ``drawdown_pct = risk_max_drawdown_pct`` (the config
  limit) into ``govern``, so ``limit > limit`` was always False and the R0/R2
  realized-drawdown stop could never fire. Found via LULU (2026-09-04, CLI):
  the market analyst measured book drawdown 25.6% -> ``drawdown_gate=True``
  (BLOCKED) yet the final Risk Gate said PASS. Fix: ``_basket_drawdown``
  resolves the measured basket drawdown via the new
  ``book_risk.portfolio_drawdown`` (max peak-to-trough of the weighted book
  equity curve), ``govern`` is fed that value, and the risk snapshot exposes
  ``dd=`` so the debate sees it. ``get_book_tail_risk`` now reuses the shared
  helper. Regression tests: governor measured-fed REJECT, graph helper
  returns measured not limit, book_risk pure drawdown. Hermetic; no network.
- **Alpha-health ledger + monitor (market-research material)** -
  ``reporting.write_alpha_ledger`` appends one jsonl row per emitted decision
  (ticker/effective_date/rating/data_quality/guardrail/decision_hash) when
  ``alpha_ledger_enable`` (default off); ``strategies/alpha_health.py``
  aggregates the ledger with joined realized forward returns - score
  distribution, cross-sectional dispersion, rank IC per horizon, ICIR, the
  horizon alpha-decay curve (does edge accrue with horizon?), per-rating win
  rates and opportunity counts (missing ratings are ``n/a``, never UNKNOWN).
  ``scripts/alpha_health.py`` rebuilds the ledger from
  ``reports/*/research_decision.json`` and prints the monitor. Answers the
  material's core question empirically: scorer compression vs market
  efficiency. Hermetic tests (26); wiring gates 33; live smoke on the Sep
  decisions; ruff clean.
- **Agent tools for the quant adds (regime/kalman/multiplier/BL/guard-band)** -
  `agents/utils/quant_adds_tools.py` binds the new calculations to the virtual
  agents so they can cite computed reads:
  `get_regime_state` (multi-axis, Market analyst + node), `get_kalman_spread`
  (Fundamentals), `get_position_risk_multiplier` (Market + Fundamentals),
  `get_allocation_black_litterman` (Fundamentals), plus
  `get_no_trade_guard_band` (guards the wiring gate: `guard_band_halfwidth`/
  `should_trade` were zero-reference). All re-exported via `agent_utils`,
  bound in both analyst tool lists + both ToolNodes; the graph now feeds
  actual `hard_guards` (risk REJECT / stale-or-unknown data / ILLIQUID) into
  `build_position_contract` under `enable_hard_guards` (default off).
  Wiring + structured_agents + calc suites green (33 + 32); ruff clean.
- **Kalman-filter dynamic hedge-ratio spread** - `strategies/statistical_kalman.py`
  `kalman_spread(x, y, Q, R, alpha)` tracks the pair's hedge ratio ONLINE via
  a scalar Kalman filter (`K = P x/(P x^2+R); beta += K(y-alpha-beta x);
  P = (1-Kx)P+Q`) instead of a static rolling-OLS beta — adapts to drifting
  pairs and regime shifts (verified: converges to the true beta; a mid-sample
  1.5->3.0 beta shift is tracked). Outputs the dynamic beta + model spread +
  a mean-reversion signal. Pure, no numpy. 8 tests (Kalman + the already-
  implemented Black-Litterman optimiser: equilibrium with market-cap weights,
  view blending toward Q, equal-weight degrade); Russian/web formula check
  confirmed BL matches the standard Π=λΣw_mkt + posterior precision form.
- **Execution multiplier (soft/hard two-tier)** - `strategies/risk_multiplier.py`
  `RiskMultiplier(soft, hard)` + `combine()` implements the halve-not-block
  philosophy with an explicit soft-vs-hard split: SOFT guards (regime /
  vol_cap / knife / flow) multiply exposure down (catalog-ordered reasons);
  HARD guards (halt / insufficient_liquidity / max_portfolio_risk /
  data_quality_failure / broker_safety) BLOCK the order to 0 regardless of
  any multiplier; unknown hard flags fail SAFE (block). `build_position_contract`
  takes `hard_guards` and runs the terminal execution multiplier (`sized *=
  combine(softs, hard)`; reasons `HARD BLOCK:` / `exec_mult=`). Replaces the
  previous folded 0.x multipliers with one tunable field. Verified: soft
  knife 0.5 halves 0.1125->0.0563, hard halt -> 0.0. 46 tests
  (knife+regime+multiplier); ruff clean.
- **Regime Vol Cap ladder (F_vol)** - `strategies/regime_state.py`
  `vol_cap_factor(atr_ratio, bands)` implements the material's ATR-ratio
  table (<1.2 1.0 / 1.2-1.5 0.75 / 1.5-2.0 0.5 / 2.0-3.0 0.25 / >3.0 0.0
  hard block); `regime_factor` gains `include_vol_leg` so when the standalone
  ladder is enabled F_regime drops its vol dimension (no HIGH 0.5x0.5 double
  count); `regime_state` exposes `vol_ratio`. `build_position_contract`
  composes `vol_cap_factor` in the size chain (`sized *= ... * rf * vcf`,
  reason `vol_cap_scale`); the graph feeds it under `vol_cap_enable` (default
  off, advisory; thresholds are config defaults, not universal). 55 total
  knife+regime+liquidity tests; ruff clean.
- **Multi-axis regime state + F_regime sizing** - `strategies/regime_state.py`
  adds four independent crisp regime dimensions (TrendScore=(EMA20-EMA50)/ATR14
  -> STRONG_BULL/BULL/BEAR/STRONG_BEAR; VolRatio=ATR14/Median(ATR,N) ->
  LOW/NORMAL/HIGH/EXTREME; Relative=R_stock-R_bench vs a benchmark ->
  UNDERPERFORM/NEUTRAL/OUTPERFORM; Drawdown=P/RollingHigh-1 ->
  NORMAL/CORRECTION/BEAR/SEVERE) aggregated by `regime_state()` (multi-axis,
  never a single forced label) with a graduated `regime_factor` (Bull/Normal
  1.0, Bear/Normal 0.5, Bear+High 0.5, Extreme/Severe 0.0; conservative min
  composition). `build_position_contract` accepts `regime_factor` (sized *=
  F_regime * F_knife); graph feeds it when `regime_state_enable` (default
  off); re-exported from `regime.py`. Thresholds are config defaults, not
  universal (calibrate per universe/backtests). Tests: 10 regime tests
  (trend/vol/relative/drawdown axes, factor composition, missing-input
  unknowns, contract scaling) + knife + liquidity = 51 total.
- **Composite knife-guard score + graduated sizing** - `strategies/knife_guard.py`
  adds the weighted composite falling-knife score K (Z_return / Z_volume /
  Z_ATR / Z_drawdown / downside-VPIN legs, weights `[0.25,0.20,0.20,0.20,0.15]`)
  with a graduated `knife_factor` (1.0 <1.5 / 0.5 1.5-2.5 / 0.25 2.5-3.0 / 0.0
  >=3.0) plus the cube-root transaction-cost guard band
  (`guard_band_halfwidth`, `should_trade`). `value_dip_setup` gains a
  `knife_composite` row (display; hard-gates only in the block band under
  `require_knife`); `build_position_contract` accepts `knife_factor` and
  scales sized by it (reason `knife_scale`); graph passes the composite
  factor into the contract when `knife_composite_enable` (default off).
  Directional conditioning everywhere (volume/ATR legs only count while
  falling) - never blocks up-breakouts. Tests: composite calm/crash/borderline/
  directional/guard-band + setup row (22 knife tests, incl. a real bug caught
  - `volume_shock_z` double-divided by the median).
- **Screener column pruning** - `scripts/value_screener.py` `_watchlist_markdown`
  now hides any column where EVERY row is empty / `n/a` / `no` / `-`
  (`prune_empty_columns`; `Rank`/`Ticker` always kept), so a sparse run no
  longer drowns in blank columns. The column legend is filtered to the
  columns actually shown. Verified against real reports (top-losers run:
  64 standard columns -> 44 kept; all-no flag columns + all-n/a vendor
  columns dropped). Tests updated to the pruning contract (all-empty/all-no
  columns absent, populated columns keep real values).
- **`research_decision.json` execution contract emitter** - `reporting.py`
  `write_research_decision()` writes the deterministic, hash-pinned machine
  contract beside `run_card.json` at the end of every report tree: ticker,
  effective_date, PM rating + deterministic stop/target/size from the G1
  position contract, data_quality/guardrail_reason, risk_gate verdict; every
  unproducible field is null (fail closed). This is the ONLY input contract of
  the TradingExecution signal daemon (Phase A) — the executor never reads
  markdown. Advisory; never gates. Hermetic tests
  `tests/test_research_decision_emission.py` (5 cases).
- **Live-print reconciliation guard (AVGO 334.35-vs-357.16 audit)** -
  `dataflows/alpaca.py` `get_intraday` now drops symbols whose returned key
  does NOT match a requested symbol (Alpaca can return a different set
  G/V/A/O when a ticker is misresolved - iterating those leaked a false live
  print into reports). `dataflows/market_data_validator.py` adds
  `live_price_sanity(live, day_low, day_high, buffer)` - flags a live print
  BELOW the verified day-low / ABOVE the day-high as "likely stale feed /
  symbol mismatch - do not reconcile" instead of presenting it as a clean
  quote; exposed as `get_live_price_sanity` tool bound to the market analyst
  + market ToolNode. The AVGO report's discrepancy note was REAL data
  (Alpaca 334.35 still true today, vs EODHD 357.16) - the honest flag stood;
  the guard now makes the conflict verifiable. Tests: sanity below-low /
  inside / above-high / unknown (test_market_data_validator).
- **Pairwise-correlation cluster gate + ATR-adaptive trailing stop** -
  `strategies/portfolio.py` `allocation_block` gains a hard
  `max_pairwise_corr` ceiling (advisory, default off): when the max pairwise
  Pearson corr across the candidate names exceeds the cap, the worst-
  correlated name is dropped (never fabricates - names without a return
  series are kept). `strategies/exits.py` `trailing_stop_exit` gains an
  ATR-multiplied variant (`atr_value` + `atr_mult`): stop distance = atr*mult
  instead of the static `trail_pct`, so high-beta names stop at a
  proportionate width (premature-exit fix); precedence declared in the
  docstring (terminal risk > stop-loss > trailing > min-holding; breakeven
  resets baseline, trailing only ratchets up). Config keys
  `max_pairwise_corr` / `trailing_stop_atr_mult` (env-overridable).
  Tests: test_strategies_portfolio + test_quantlib_lean_enhancements (74
  pass). Gemini review: stale typos already fixed, cvar/drawdown defaults
  present; these two were the genuinely-missing pieces.
- **Market-stress / liquidity / earnings-blackout hardenings (mean-reversion)** -
  `strategies/regime.py` `regime_gate_read` gains a market-level stress leg
  (`index_closes`; config `market_stress_index` e.g. `^SPX` +
  `market_stress_vol_cap` 0.85): when the index latest-21d realized-vol
  percentile exceeds the cap, `market_stress=True` blocks MR entries
  (advisory - stock dips become value traps on a stressed tape).
  `strategies/liquidity_risk.py` `liquidity_verdict` gains optional
  `adv_dollar`/`min_dollar_volume` (20d dollar-volume floor) and
  `spread_bps`/`max_spread_bps` (Roll 1984 spread cap) -> ILLIQUID on a thin
  book / wide spread; the graph's liquidity gate now feeds both. Config
  `catalyst_hard_block_days` default 0 -> 5 (forward-looking earnings
  blackout REJECTs new risk; existing forward logic). Tests:
  test_strategies_liquidity + test_strategies_regime extend (28 pass).
- **Moomoo value-dip screener (`--universe moomoo-screen`)** - `dataflows/moomoo.py`
  adds `screen_value_dip_moomoo()` (Stock Screening V2 against local OpenD: US market,
  PE_TTM / market-cap / ROE value anchors AND 5-day change + RSI dip timing, 52-week-high
  distance, paginated, sorted by 5-day change; unit conventions documented: change/ROE
  decimal, RSI 0-100, price_to_52w_high as (price-high)/high). `scripts/value_screener.py`
  gains the `moomoo-screen` universe: config-default filters (env-overridable via
  `TRADINGAGENTS_MOOMOO_SCREEN_*`) with per-flag overrides (--max-chg5d/--max-rsi/
  --max-debt-assets) + server-side price floor/PB band (--price-min, --pb-min/
  --pb-max) + configurable pullback window (--dip-days, default 5; reference
  recipe 20) + client-side NYSEX/Nasdaq exchange gate (--exchanges, default
  NYSE,NASDAQ, all universes; screen V2's EXCHANGE field is non-functional
  for US, so candidates are checked via get_stock_basicinfo / the EODHD
  symbol-list Exchange column); rows feed mover_meta + the standard results
  loop. Dep guard:
  `protobuf>=5.29,<6` (moomoo SDK needs the pre-6.0 upb API). Tests:
  test_moomoo_value_dip_screen (6 pass) + 2 CLI tests.
- **Remediation W1-5/W3-5/W3-6/W3-8/W4-5/W4-7/W4-8 ops + polish** - `strategies/quant_baseline.py`
  (deterministic quant-only signal + rating for LLM comparison), `strategies/options_surface.py`
  (IV percentile/skew/P-C OI/expected move/VRP), `strategies/integrity_tools.py` (thesis-evidence
  matrix, prompt-injection detection, complexity report), `llm_clients/tier_router.py` (hybrid tier),
  `strategies/monitor.py` (webhook/log notifier, default off).
  Tests: test_phase8_ops (18 pass).

- **Remediation W2-6..10 costs / capacity / actions / survivorship** - `strategies/backtest_models.py`
  (square_root_impact Almgren-Chriss from ADV, turnover, capacity_pct, borrow_cost, quote_adjust
  corporate-action), `pit_registry.universe_membership` (survivorship guard).
  Tests: test_cost_capacity_actions (14 pass).

- **Remediation W1-10/W2-11/W4-6/W1-11 regime + scenario + ablation** - `strategies/regime_performance.py`
  (regime_conditioned_performance per-regime hit/return, stress_grid computed sensitivity rows,
  macro_regime cross-asset label fail-open), `scripts/agent_ablation.py` (drop-one measurement).
  Tests: test_regime_performance (10 pass).

- **Remediation W4 architecture (domain bundles / typed state / falsification schema / factor bridge)** -
  `strategies/domain_bundles.py` (get_market_technicals / get_fundamental_profile /
  get_sentiment_flow_feed / get_factor_profile / get_portfolio_risk_envelope + news_relevance_profile),
  `strategies/typed_state.py` (schema-validated layer artifacts + compact summarizer),
  `falsification.evaluate_debate_claims` (judge grounding + auto-reject already-breached theses).
  Tests: test_phase5_architecture (9 pass).

- **Remediation W1-2/4/6/7 measurement (calibration + scorecard + benchmarks + feedback)** -
  `strategies/calibration.py` (predicted-confidence bins vs actual hit rate; per-agent scorecard),
  `evaluate.benchmark_table` + `strategy_quality_report --benchmark` (market + simple comparators),
  prediction-ledger auto-invalidation on stop-hit outcomes (W1-7).
  Tests: test_calibration_scorecard (7 pass).

- **Remediation W3 data integrity (quality score / disagreement / PIT / falsification)** -
  `strategies/data_quality.py` (aggregate_quality weighted 0-100 + tier, disagreement_flag cross-vendor
  spread, fundamentals_pit_ok fail-closed invariant), `strategies/falsification.py` (numeric thesis
  invalidation conditions auto-monitored into the persistent ledger). Decision disclosure gains the
  quality + falsification lines. Tests: test_data_quality_falsification (14 pass).

- **Remediation W2 validation guards (CPCV / OOS / walk-forward / DSR)** - `strategies/evaluate.py`
  adds `purged_cpcv_splits`+`cpcv_overfit_mask` (W2-2) and `oos_split` (W2-4); `alpha_zoo.bench_zoo` now
  reports OOS rank-IC, walk-forward mean IC (W2-3), CPCV overfit flag, and deflated IC (W2-1);
  `factor_proposal_loop` adopts a factor only when its trailing-OOS IC clears the bar.
  Tests: test_validation_guards (11 pass). Plan: docs/master_implementation_plan.md.

- **Remediation W1 measurement (prediction ledger + cost)** - `strategies/prediction_ledger.py` (W1-1: every
  decision logged as a scorable prediction row; W1-3: MAE/MFE + stop/target outcome scoring against realized
  closes), `strategies/llm_cost.py` (W1-8: provider rate-table cost estimate). Graph wires the ledger behind
  `enable_prediction_ledger`. Tests: test_prediction_ledger (15 pass). Plan: `docs/master_implementation_plan.md`.

- **Vibe-Trading transfer (research + 8 adopted hardening items)** - `docs/design_shadow_account.md`; `VendorResult.price_caliber`/`volume_unit` + `caliber_consistency` mixed-caliber warning; next-bar close fills + lookahead sentinel (`test_next_bar_fill`); `position_target`/`position_filled` in backtest output; persistent invalidation ledger (`--invalidate`, action-report auto-breach); `run_card.json` per report tree; versioned cache keys + no-forming-bar staleness guard; hash-chained `risk_audit` ledger (`--verify-chain`); `alpha_zoo` purity gate + bounded evaluator + `factor_bench` CLI.

- **Fix: false 'Section truncated at the LLM output cap' marker in PM decision** - `reporting.write_report_tree` ran the truncation detector on the decision AFTER appending the computed disclosure block (which ends in lowercase, e.g. `models: n/a`), so a complete decision was flagged as an LLM cut whenever the Phase-D disclosure block was rendered. Truncation detection now runs on the raw LLM text only; audit/disclosure append after. Also tightened `_looks_truncated`'s bold-label exemption to short verdict lines (`**Action**: Buy`) - a long `**Executive Summary**: ...` prose line cut mid-word is now correctly flagged.

- **DSA reporting (phase D)** - `strategies/report_disclosure.py`: computed driver attribution (sum-to-100, never narrated), consensus support/oppose readout, `watch_conditions`/`next_check_time` (fast-path cadence), `invalidation_conditions` (>= 1 per decision: price_stop_loss / price_take_profit_status / data_quality / manual:thesis_reassessment fallback), `disclosure_footers` (sources-used-vs-empty + models). `reporting.write_report_tree` appends the advisory disclosure block to `5_portfolio/decision.md`.

- **DSA polish (phase C)** - `strategies/skills.py` + `strategies/skills/*.yaml` (declarative strategy-skill DSL with regime-from-opinion routing, bounded advisory score adjustments, `enable_skill_overlays` default off); `strategies/news_relevance.py` (deterministic relevance scoring, official-source boost, spam admission, degrade triple); `dataflows/news_cache.py` (owner-wait coalescing TTL cache). Tests: test_skill_overlays + test_news_relevance (25 pass).

- **DSA robustness (phase B)** - `dataflows/market_router.py` (market-for-symbol classifier + per-market `market_source_priority` chains, opt-in, default bit-identical), `dataflows/vendor_breaker.py` (3-fail/300s circuit breaker + half-open probe + negative capability cache, thread-safe), `VendorResult` honesty fields (`fallback_from`/`is_stale`/`stale_seconds`/`data_quality`/`missing_fields` + `to_dict`), `dataflows/effective_date.py` (effective-trading-date rules + all-closed skip, fail-open). Tests: test_market_router + test_effective_date + test_phase_b_wiring (20 pass).

- **DSA decision quality (phase A)** - `tradingagents/strategies/decision_guardrail.py`: post-PM downgrade-only stabilizer (risk-cap at Hold, near-resistance-without-inflow cap, near-support-without-outflow soften) with recorded `guardrail_reason`; versioned 0-100 <-> 5-tier-rating consistency validator; PM confidence capped on degraded `data_quality`; `PortfolioDecision` gains advisory `data_quality`/`guardrail_reason`/`risk_cap`; per-field integrity retry (`structured.retry_structured_missing_fields`) - targeted rebuild, never a blind re-roll. All default-off (`enable_decision_guardrail`). Tests: test_decision_guardrail (179, incl. the never-upgrades property) + test_phase_a_wiring.


- **Qlib Phase-1 pure calculators** (`docs/design_qlib_integration.md` Phase 1,
  all advisory + default-off): `strategies/factor_expressions.py` (Alpha158-style
  operators, expression-string cache, learn/infer fit-apply split with
  train-only moments), `strategies/signal_analysis.py` (rank IC/ICIR,
  quantile long-short, IC-decay half-life, pred-autocorrelation,
  with/without-cost report table), `strategies/portfolio_strategy.py` (Qlib
  Topk-Drop + convex enhanced-index with turnover cap / benchmark-deviation /
  force-hold-sell masks / two-stage fallback; scipy SLSQP + pure-python
  fallback, cvxpy optional), `strategies/market_tradability.py` (limit-up/down
  gates, suspension, volume participation caps, deal-price selector). New
  tools `get_factor_profile` (gated `enable_factor_profile`),
  `get_topk_drop_plan`, `get_enhanced_index_tilt` bound to the market/PM
  ToolNodes + agent_utils + trading_web value tools; `portfolio.allocation_block`
  gains Topk-Drop / enhanced-index strategy options behind
  `enable_topk_drop` / `enable_enhanced_index`; `scripts/backtest_strategy.py`
  fills honour tradability (`--limit-threshold` / `--participation` /
  `--deal-price` + `fill_model` report block); `strategy_quality_report`
  emits the with/without-cost table. Tests: `tests/test_qlib_phase1.py` +
  `tests/test_qlib_wiring.py` (43 pass; §8-1/2/3/6/7/8/9 acceptance).

- **Nightly-review driver `--mode recent`** - `scripts/nightly_review.py
  --mode recent` reviews each symbol's MOST RECENT
  `reports/<TICKER>_<YYYYMMDD>_<HHMMSS>` folder instead of the newest
  `batch_summary_*.jsonl`, so interactive CLI / `propagate()` / `pipeline.py`
  runs (which never write a batch summary) get the scheduled 07:35 pre-open
  review too. Newest-per-symbol is keyed on the folder-name timestamp
  (fixed-width, lexicographic); a folder is skipped with a note when it has no
  `5_portfolio/decision.md` or `full_states_log_*.json` to review; decoy
  entries (`pipeline_*` dirs, batch-summary files) are ignored. Default
  `--mode batch` is unchanged. trading_web `run_nightly` forwards `--mode`
  and the Nightly form gains a "Review source" selector.
  Tests: `test_nightly_review_recent_mode_newest_per_symbol` +
  `test_nightly_review_recent_mode_empty` (hermetic, timed); the existing
  batch-mode driver test is unchanged.
  **Hard-exit guard**: when run as the process entry point the driver now
  flushes and `os._exit()`s after a completed (or failed) run, mirroring the
  CLI's `_CLI_ENTRY` pattern — the moomoo SDK's non-daemon threads no longer
  hang the scheduled task at interpreter exit (a hung task would skip the next
  day's run under Task Scheduler's single-instance default). In-process
  callers (tests import the module) still return/raise normally. The scheduled
  `nightly_review.cmd` now runs `--mode recent --max-symbols 25` (outside the
  repos; ~45-50 min, finishes pre-open).

### Fixed

- **Batch hard-exit guard (moomoo shutdown block)** - `batch.py` now runs the
  same `_CLI_ENTRY` flush + `os._exit()` after a completed (or failed) run
  that the CLI and nightly driver already have. A finished batch (reports +
  `batch_summary_*.jsonl` fully written) previously hung at interpreter exit
  on the moomoo SDK's leaked non-daemon threads — the process stayed "Running"
  indefinitely, and under Task Scheduler's single-instance default that would
  skip the next day's run. The entry block was also moved to the file end so
  `_batch_pre_market_check` is defined before `main()` runs. In-process
  callers (tests) still return/raise normally.
- **Truncation-retry on the structured-output success path** - a structured
  call that parsed into the schema but was cut by `max_tokens` mid-render
  previously skipped `_retry_if_truncated` (only the free-text fallback path
  had it), so the report got the truncation marker with no continuation merge
  (e.g. ADSK 2026-09-02 deep PM run). `invoke_structured_or_freetext` now
  applies the same continuation retry to the rendered structured result.
  Tests:
  `test_invoke_structured_or_freetext_retries_truncated_structured_render` +
  `test_invoke_structured_or_freetext_no_retry_when_structured_render_complete`.
- **`positions_to_basket` treats Fidelity "Pending activity" as cash** - a
  settlement row (Symbol="Pending activity", no Quantity, empty Description,
  e.g. $8,993 on the Sep-02 Account1 export) was parsed as a position and
  emitted a phantom `PENDING_ACTIVITY` weight into the .env basket. The
  blank-Quantity cash branch now also matches settlement/sweep markers in the
  Symbol column (`pending`), same class as the documented blank-symbol / sweep
  rules; the pending dollars fold into the cash sleeve (denominator +41.5% ->
  +43.5%). Test: `test_pending_activity_is_cash`.
- **Analyst report-stub guard (status-turn → full report)** - a model can
  answer a tool loop with a bare *status turn* ("Good progress. Now let me
  gather...") that emits no tool_calls; the analyst router takes that as the
  final turn and the stub landed verbatim in `*_report` (observed: a 217-byte
  NVDA fundamentals report, CLI 2026-09-02 — `_looks_stub` only catches bare
  headers, not short self-interrupting progress notes). New
  `retry_chain_if_stub` (mirrors `_retry_if_stub` for the tool-calling chain)
  + `_looks_report_stub` (degenerate-stub OR short status-announcement
  detection) are wired into the market / news / fundamentals analyst normal
  path: a stubbed report is re-asked once to write the full report from the
  gathered evidence, else an explicit `**Report unavailable**` notice - never
  an empty or one-line report rendered as truth. Tests:
  `tests/test_analyst_report_stub.py` (7 hermetic).
- **Run-config guidance (gitignored `.env`, not committed)** - deep tier
  model separated from quick: `TRADINGAGENTS_DEEP_THINK_LLM=deepseek/
  deepseek-v4-pro-0813` (RM + PM get reliable structured output; quick stays
  flash for speed — NVDA's "Decision: unavailable" stub was flash's
  structured-JSON miss), `TRADINGAGENTS_MAX_OUTPUT_TOKENS_DEEP=4000` (was
  2500 — the deep prompt is the longest and 2500 truncated it mid-sentence),
  `TRADINGAGENTS_LLM_MAX_RETRIES=3` (retry transient failures instead of
  falling to the stub notice).

- **Positions -> risk-basket utility + PM holdings read (Option A/B)** - the
  risk basket now reflects the REAL book:
  - `strategies/book_positions.py` (new, pure/hermetic): broker CSV parse
    (Fidelity-style), cash detection via `**`-suffix / blank-symbol / sweep
    description (the broker's `Type` column is NOT used - Fidelity labels
    equities "Cash"), cross-account merge, `compute_weights` WITH cash in
    the denominator (the <1.0 remainder is the cash sleeve, consistent with
    `portfolio_cvar`'s documented "weights + cash" semantic), exact `.env`
    line render (round-trips through `default_config._coerce`),
    `patch_env_text` (only the two basket lines change), and
    `render_holdings_block` (advisory "Computed book" line for the decision
    agents; `holdings_tickers`/`holdings_weights` when set, else falls back
    to the risk basket).
  - `scripts/positions_to_basket.py` (new): dry-run default (per-account
    cross-check vs the broker's own pct, total/cash, per-symbol weights),
    `--apply` (`.env.bak` backup, rewrite the two basket lines),
    `--min-value` / `--exclude`, `--write-book-json` (gitignored dollar
    book = the Option-C artifact), `--json`.
  - Graph: `_compiled_decision_context` now includes the "Computed book"
    block, so the Trader / PM / risk debators / researchers see the actual
    holdings read - the PM can state "you hold no TSLA -> size 0" instead
    of the conditional "if you hold it, trim".
  - Config: `holdings_tickers` / `holdings_weights` (+
    `TRADINGAGENTS_HOLDINGS_TICKERS` / `TRADINGAGENTS_HOLDINGS_WEIGHTS`) =
    Option B override; empty = Option A (basket is the book). `.env.example`
    mirrors added.
  - Security: the `.gitignore` `profolio/` typo is fixed and `positions/`
    added (the CSV + book JSON are never commit-able).
  Tests: `tests/test_book_positions.py` (24 hermetic, timed): cash
  detection, merge, weights-including-cash, env round-trip, holdings
  fallback, gitignore guard, CLI dry-run/apply/write-book-json.

### Added

- **Parent-repo ports — look-ahead window + debate opening** (ports from
  `TauricResearch/TradingAgents`, no merge):
  - `dataflows/date_window.py` (new): shared half-open UTC window
    `[start, end + 1 day)` for dated content; undated items kept only when the
    window reaches the present. yfinance news migrated to it (same semantics as
    the old private helper).
  - StockTwits (`fetch_stocktwits_messages(..., start_date, end_date)`) and
    Reddit (`fetch_reddit_posts(..., start_date, end_date)`) now trim to the
    run's as-of window via `_within_window` — a historical/backtest run can no
    longer leak post-date chatter (#1220). No window = unchanged live behavior.
  - `agent_utils.opponent_argument_or_opening(text, opponent)`: the opening
    speaker in each of the 5 legacy debates (bull/bear researchers + the 3 risk
    debators) gets the explicit "(The {opponent} has not spoken yet — open the
    debate with your own case.)" marker when the opponent's response is empty,
    instead of interpolating an empty string that made models fabricate the
    other side's position (#1176). Real opponent arguments pass through
    unchanged.
  Tests: `tests/test_parent_ports.py` (12 hermetic, timed); existing
  `test_news_lookahead.py` migrated to the shared module.

### Added

- **Cookbook quant-strategy gap implementation** (`Strategies/cookbook.md`,
  recipes 1-5 + common framework) - the missing portfolio-construction /
  evaluation / options math is now code and bound to the decision agents:
  - **Time-series momentum** (recipe 1): `strategies/momentum.py::ts_momentum_weights`
    - MOP-style `sign(trailing log return) / EWMA vol`, target-vol normalized,
      gross-leverage capped; `factors.momentum_multihorizon` (1/3/6/12m ensemble).
  - **Cross-sectional mean reversion** (recipe 2): new
    `strategies/cross_section.py` - `winsorize`, `cross_sectional_z`,
    `centered_rank` (2.RankPct-1), `quantile_split`, `residualize_returns`
    (market beta residual), `neutralize_book` (dollar + beta + sector-neutral
    via a row-space projection, gross renormalized), `no_trade_band`.
  - **Cointegration pairs** (recipe 3): `statistical.py` - `spread_zscore`
    (rolling beta hedge), `pair_signal` (entry |z|>=2 / exit <=0.5 / stop >=3,
    cointegration + half-life cross-check), `pair_quantities` (dollar-neutral
    G/2 leg split), `ecm_loading` (VECM speed-of-adjustment gamma).
  - **Multifactor portfolios** (recipe 4): `factors.z_composite_alpha`
    (weighted linear z-composite alpha).
  - **Options volatility** (recipe 5): `options_math.py` - `black76` gains
    rho / vanna / vomma / charm (second-order Greeks), new
    `bsm_equity_surface` (vanilla BSM + full Greek set - closes the previously
    skipped vanilla-BSM item), `greek_pnl_response` (delta-gamma-vega-theta
    scenario P&L), `model_free_implied_variance` (Cboe/VIX-style discrete
    formula with the forward-discreteness term). `get_variance_premium` is
    repaired: it now computes a real model-free VRP from the machine options
    chain (strikes/mids to implied variance minus realized), with the IV-
    snapshot degrade when the chain is unavailable.
  - **Common framework**: `evaluate.py` - `turnover` (1/2 sum |dw|),
    `turnover_cost` (sum |dw|*c), `gross_exposure` / `net_exposure`,
    `rolling_sharpe`, `regime_split_performance`.
  - **Risk leaves**: `book_risk.cdar` (Chekhlov drawdown-at-risk tail),
    `portfolio_optimizer.max_diversification_weights` (Choueifaty Sigma^-1 sigma),
    `credit_spread.merton_distance_to_default` (equity-as-a-call fixed-point,
    DtD = d2 + risk-neutral PD), `rate_utils.forward_rate`,
    `market_session.book_depth_read` (microprice + OBI).
- **Agent binding (compute-as-tools)**: new market-analyst tools
  `get_ts_momentum_weights`, `get_pair_trade_signal`, `get_event_pnl_response`,
  `get_book_depth_read`, `get_merton_distance` (bound to the market analyst
  tool list + prompt + the graph market ToolNode + `agent_utils.__all__`),
  Merton also bound to the 3 risk debators' in-node risk loop; `get_tail_risk`
  now reports CDaR/DVaR, `get_risk_parity_alloc` reports max-diversification
  weights, plus a dedicated `get_merton_distance` Merton tool. trading_web
  Value Tools += `variance_premium` + `ts_momentum_weights`.
  Tests: `tests/test_cookbook_gaps.py` (27 hermetic, timed); affected suites
  349 passed.

### Fixed

- **Structured-debate robustness series (QCOM/DELL live runs)** - a
  session-long hardening of the opt-in `enable_debate` pipeline, each
  verified against live runs:
  - Judge json_object 400 root cause: the judge prompt lacked the literal
    "json" token, so OpenRouter's OpenAI/Azure backends rejected
    `response_format=json_object` -> the adapter fell back to a non-json
    call -> the model returned empty/ragged dimensions. The judge prompt
    now says "single JSON object" (also carries the flattened `scores[]`
    shape cue). Verified: real blind scores now appear in both
    `structured_debate.md` files (e.g. research Candidate_Y 6.75, risk
    Candidate_Z 5.75 on DELL).
  - Flattened `L2JudgeDimensionedRubric.dimension_scores` (enum-keyed dict)
    to `scores: [{dimension, score}]` (array of objects is far more
    reliably emitted under json_object); legacy dict shape auto-normalized;
    `_rubric_dimension_dict` back-compat.
  - Tolerant rubric coercion: `entrenchment_detected`/`rebuttal_effectiveness`
    string/object values coerce to bool/float (clamped 0-10) instead of
    failing the whole rubric.
  - Judge empty-dimension fallback: directed retry naming the exact four
    dimensions, then a deterministic prose-score parse (rationale numbers
    per dimension), then `rebuttal_effectiveness` proxy, then honest
    UNAVAILABLE - never a silent 0.0.
  - Registry-key mismatch: debaters humanize the Ground-Truth Key Index
    labels, so L1 marked every claim unverified -> `(unused)` in the
    ledger. `resolve_ground_truth_key` now routes normalize -> extended
    KEY_ALIASES (semantic variants) -> confidence-gated fuzzy (difflib,
    >=0.72 ratio, >=0.08 margin, token-overlap bonus) -> honest unverified
    (never fabricated). Tested against the real run labels.
  - Context-bounded debater prompts (static registry + last-turn delta +
    active disputes instead of full transcripts/reports), 4000-token cap,
    section-aware 1-shot example, risk-stance coercion (BULL/BEAR ->
    AGGRESSIVE/CONSERVATIVE), judge scores last non-degraded round.
  - `TRADINGAGENTS_DEBATE_NEUTRAL_MODEL` key so the neutral risk debater
    resolves its own model (luna), like the other roles.
  - CLI deterministic exit + hard-exit guards behind `_CLI_ENTRY` (moomoo
    shutdown-block can no longer hang or kill pytest).

- **CLI deep-run defect (`--depth` / interactive research depth)** - 'deep'
  mapped to 5 bull + 5 bear debate turns, so a deep run multiplied runtime
  (SKHY 08-31 took >1h vs 30-40m typical) and the later research-debate
  turns degenerated into rambling/empty arguments that poisoned the Research
  Manager (a 300-line garbage bear turn + 3 empty bear turns, then a 0-byte
  `2_research/manager.md`). Now the depth selection maps to the RISK rounds
  only and the bull/bear researchers each run exactly ONCE per analysis; the
  risk debators' aggressive/conservative/neutral rounds still scale with the
  depth selection as before. Also added: an empty-argument retry + honest
  note in both researchers, an explicit "plan unavailable" block in
  `reporting.py` when the Manager produces no usable plan (never a 0-byte
  file), and a 2-tool-round cap on the risk-debator + Trader in-node tool
  loops to bound runtime. Docs/README synced.

### Added

- **Risk-section structured-debate parity** (direction.md) — the structured
  multi-agent debate now mirrors the research section:
  - Risk debators (aggressive/conservative/neutral) emit `RiskDebaterTurnPayload`
    grounded turns into the new `structured_risk_state` channel; legacy
    `risk_debate_state.history` prose keys are still written so reporting and
    the Portfolio Manager consume the same shape.
  - The SAME blind L2 judge is generalized to N candidates
    (`anonymize_and_rotate(turn_by_role, roles)`, Candidate_X/Y/Z) and runs
    over the three risk candidates before the Portfolio Manager when
    `enable_debate` is on.
  - Model keys are shared across sections (direction items 3-5):
    `debate_bull_model` → bull + aggressive, `debate_bear_model` → bear +
    conservative, `debate_judge_model` → both judges; neutral risk analyst
    stays on the quick tier (no dedicated key).
  - **Depth parity** — ONE knob (`TRADINGAGENTS_RESEARCH_DEPTH` env or the
    CLI research-depth selection) drives BOTH the research and risk round
    counts to the same level; explicit per-round env overrides still win.
  - Router fix: `should_continue_structured_debate` no longer hard-stops
    after one round — it cycles to the next round within `max_debate_rounds`
    (the depth knob now actually takes effect on the structured path).
  - RM + PM prompts include the L2 judge verdict evidence block
    (`render_judge_evidence`); `4_risk/structured_risk_debate.md` mirrors the
    research evidence block.
  - All still opt-in via `enable_debate`; with the flag off the legacy risk
    chain is bit-identical (SD Risk nodes are no-op placeholders).
  - Tests: `tests/test_debate_risk_parity.py` (18 cases: model mapping,
    section router + round-cycling, risk turn channels, judge evidence block,
    risk graph edges on/off, depth parity).

- **Structured multi-agent debate implemented (opt-in)** (`docs/design_multi_agent_debate.md`
  P1-P5 + graph wiring): the research debate now runs as a structured subgraph
  when `enable_debate` is on (default OFF — the legacy one-shot chain stays
  bit-identical):
  - **P1 Grounding contract** — `strategies/debate_claim.py`: `ClaimRecord` /
    `ClaimLedger` + `verify_claim` (valid / violated / abstain / unverified /
    qualitative; deceptive-grounding source check against the run ledger).
  - **P2 Scoring + termination + severity** — `strategies/debate_score.py`:
    `debate_score` (evidence × novelty × constraint), `termination_check`
    (plateau / consensus / hard cap), `classify_severity` (R1' severity
    triage: HARD_BREACH → baseline, RETRYABLE → bounded scoped regen,
    SOFT_WARNING → penalty + annotated L2), `entrenchment_index` +
    `divergence_check` + `reweight_to_baseline` (R2' artificial-consensus
    α-reweight toward the empirical base rate).
  - **P3 Heterogeneous models + capability matrix** —
    `strategies/debate_capability.py` (R3 role×model floor check, fail-closed
    when required), `agents/utils/debate_roles.py` (`resolve_role_llm`
    `family:id` per role with quick/deep fallback + per-role tool surfaces),
    `debate_*` config keys + `TRADINGAGENTS_DEBATE_*` env overrides
    (+ `.env.example`).
  - **P4 Schemas + dual-mode adapter + judge** — `agents/schemas.py`:
    `DebaterTurnPayload` / `L1DeterministicResult` / `L2JudgeDimensionedRubric`
    / `L1ExecutionContext` (pydantic mirrors of the source doc's four JSON
    schemas); `agents/utils/debate_structured.py` dual-mode adapter
    (structured-output API + markdown-fence parse + bounded Pydantic repair,
    fail closed); `agents/arbiters/debate_judge.py` blind order-rotated
    dimensioned L2 judge.
  - **P5 A/B harness** — `scripts/debate_ab_harness.py` (Brier score +
    max-unforecasted drawdown), producers injected / `--demo`.
  - **Graph wiring** — `graph/setup.py` SD subgraph (`SD Bull -> SD L1 ->
    SD Bear -> SD L1 -> SD Finalize -> Research Manager`, O-condition
    placeholder nodes registered so targets never raise), the
    `should_continue_structured_debate` router, `debate_state` channel, and
    reporting's `2_research/structured_debate.md` (judge scores + claim
    ledger + L1 verdict, back-compat when absent).
  Tests: `tests/test_debate_claim.py` (12), `test_debate_score.py` (17),
  `test_debate_integration.py` (19), `test_debate_stream_hermetic.py` (2+
  compile) — 56 hermetic. ruff clean.
- **Multi-agent debate design revised for the §7 risk items**
  (`docs/design_multi_agent_debate.md`, revision v3, folding in the 2026-08-31
  update of `Strategies/Multi_Agents_Debate.md`): L1 severity triage
  (HARD_BREACH → baseline fallback, RETRYABLE → one scoped regen, SOFT_WARNING
  → penalty + annotated L2) replaces the binary gate (R1'); an entrenchment
  index `I_entrench` + divergence-floor rule raise an Artificial-Consensus
  Flag that α-reweights `W_final = (1−α)·W_debate + α·W_baseline` toward the
  empirical base rate (R2'); a fourth canonical wire schema
  `l1_execution_context.json` → `L1ExecutionContext` makes the recovery path
  explicit (R5'); FSM transition table + LangGraph mapping updated, new
  `debate_*` config keys (`debate_entrench_thresh`, `debate_divergence_min`,
  `debate_baseline_fallback`), literature + risks + acceptance criteria
  extended. Research/design only — no code changed.
- **Multi-agent debate architecture (research-only design)** (`docs/design_multi_agent_debate.md`) -
  research + design (no code) folding the source doc
  `Strategies/Multi_Agents_Debate.md` onto the existing bull/bear research
  debate: a two-layer judiciary (deterministic L1 gates — claim verifier,
  risk governor, consensus — always precede an L2 blind, order-rotated,
  dimensioned, ensembled LLM judge), heterogeneous per-role models with a
  config-time capability matrix (R3), the FSM transition table + canonical
  wire schemas mapped to pydantic (`DebaterTurnPayload`,
  `L1DeterministicResult`, `L2JudgeDimensionedRubric`), L1 fast-abort /
  single-role regeneration (R1), divergence caps + artificial-consensus
  reweight to baseline (R2), and a matched-compute A/B harness scored with
  Brier + max unforecasted drawdown (R4) before any gate ships. All proposed
  `debate_*` config keys default OFF (bit-identical current behavior);
  phased rollout P0-P6 maps onto existing seams (`independent_vote`,
  `risk_tool_loop`, `conditional_logic`). Companion to
  `docs/design_risk_calculations_agent_wiring.md`.
- **Risk calculations wired into the decision agents** (`docs/design_risk_calculations_agent_wiring.md`,
  7-phase audit implementation): (1) the 18 quant-risk tools that were
  registered in the market ToolNode but unreachable by the LLM are now bound
  to the market analyst (horizon-VaR, downside, trailing exit, risk-parity,
  normality, unit-root, CAPM, rotation, Clenow, omega, correlation,
  scale-out, sentiment-computed, curve surfaces, movers, variance premium);
  (2) 12 new `@tool`s wrap previously-untooled deterministic calculators:
  `get_fixed_risk_size` (commission/tranche-aware sizer), `get_exit_overrides`
  (two-pass drawdown/trail liquidations), `get_pre_trade_read` (notional +
  rate gates), `get_ledger_risk_state` (memory win-rate + paper-reviewer
  record), `get_trade_plan` (the plan card as a callable), `get_fixed_income_risk`
  (preferred YTM/duration/DV01/convexity), `get_pair_risk` (cointegration +
  Granger), `get_vif_read`, `get_vol_cones`, `get_trade_excursions`
  (MAE/MFE/profit-factor), `get_alpha_scoring` (magnitude-scored alpha),
  `get_regime_gate_read` (knife guard); (3) `get_risk_gate` now exposes the
  FULL governor surface (book cap, daily-loss budget, high-water-mark tiers,
  sector cap, tranche capital-at-risk, liquidity verdict, halt); (4) the
  Trader / PM / 3 risk debators' `computed_decision_context` gained a risk
  factsheet (limits registry, vol estimates, tranche peak-deployed +
  capital-at-risk, fixed-risk size); (5) the 3 risk debators run an in-node
  risk-tool loop (`agents/utils/risk_tool_loop.py`, 23 tools, capped at 8
  rounds, degrades to plain invocation when the provider cannot bind tools);
  (6) the Trader runs a 12-tool verification pass after its structured
  proposal; (7) cross-binds: news analyst gets credit-stress + news-sentiment,
  fundamentals gets fixed-income + alpha-scoring, Research Manager + Bull/Bear
  researchers get the computed context. Web: value-tools surface gains
  vol-cones / trade-plan / ledger-risk-state / regime-gate / fixed-income-risk.
  Tests: `tests/test_risk_agent_wiring.py` (22 hermetic).

### Fixed

- **Report truncated after Research Manager (missing Trader / risk / PM)** -
  interactive runs (e.g. SKHY 08-30/08-31) saved only the analysts +
  Bull/Bear/Research Manager and silently dropped `3_trading/trader.md`,
  `4_risk/*`, `5_portfolio/decision.md` — the graph **ended after the
  Research Manager judge**. Root cause: `graph/setup.py` had lost the
  `Research Manager -> Trader` edge (and the Bull/Bear debate conditional
  edges were dropped in the same block), so LangGraph had no path onward
  after the research debate; `write_report_tree` then skipped the sections
  whose state keys were absent. Restored the Bull/Bear -> (Bull | Bear |
  Research Manager) conditional edges AND added the `Research Manager ->
  Trader -> Independent Risk Stances -> Aggressive/Conservative/Neutral ->
  Portfolio Manager -> END` chain. Hermetic full-stream verification (SKHY,
  stub LLM) now emits `trader_investment_plan`, `risk_debate_state` and a PM
  `judge_decision`. Regression test:
  `test_production_setup_research_risk_chain_edges_are_wired` (asserts the
  complete chain is present in the compiled graph).
- **Tool-round cap `KeyError '<Analyst>'` on the interactive CLI** - a run
  whose market/news/fundamentals analyst hit the `MAX_TOOL_ROUNDS` (8) tool
  cap crashed with `KeyError: 'Market Analyst'` wrapped in LangGraph's
  "During task with name ..." note (live symptom: SKHY interactive run). The
  cap routers return the analyst node name, but `setup.py` registered the
  conditional-edge targets as only `[tools, clear]` (sequential) /
  `{tools, clear}` (parallel subgraphs), so LangGraph raised on the cap path.
  Now the analyst node itself is a registered target in both modes (a
  self-loop), and the three analyst nodes short-circuit the cap turn: the
  dangling `tool_calls` on the last message are stripped via
  `structured.finalize_messages` and ONE terminal prose turn writes the
  report — no re-invoke-then-ping-pong, reports are never left empty, the
  loop always terminates. Hermetic end-to-end repro (`SKHY`, stub LLM)
  completes the full graph in both modes. Regression tests:
  `test_production_setup_registers_analyst_cap_self_loop` +
  `test_parallel_subgraph_registers_analyst_cap_self_loop`.

### Added

- **`--value-dip-loose` (value-dip harvest mode) + eodhd-losers equity
  filter** - relaxes the value-dip technical entry from `RSI<=35 AND %b<=0.10`
  to **OR** (either oversold signal suffices) via a new `loose_technical`
  param on `strategies.value_dip.value_dip_setup` (default False: the analyst
  tools / strict AND are unchanged), and appends a ranked **near-miss table**
  (up to 50, distance-to-entry ordered) naming exactly which gate each near
  candidate missed (`value_floor` / `technical_entry` / `trade_risk` /
  `balance_sheet` / `profitability`). The `eodhd-losers` universe now
  **equity-filters** its seed against the EODHD exchange-symbol common-stock
  list (one cached call; warrants/units/leveraged ETFs — which dominate the
  intraday decliners — are dropped; degrades to the unfiltered list if the
  reference call fails). Web Screener gains the Loose dip gate checkbox,
  flags forward through `run_screener`. Tests:
  `test_value_dip_loose_prefilter_or_semantics`,
  `test_eodhd_losers_equity_filter_drops_non_common`,
  `test_eodhd_losers_loose_near_miss_renders` + web
  `--value-dip-loose` forwarding case.
- **`--universe eodhd-losers` value-screener universe** - the EODHD bulk US
  real-time feed (one call, ~18k rows, OpenD-independent) seeds a
  **loss-ordered** scan: the biggest intraday decliners by change% are the
  symbols screened, so value-dip / momentum candidates (RSI/%b oversold,
  stop <= 2%) are harvested from today's actual dips instead of an alphabetical
  `eodhd-us` slice. New `tradingagents/dataflows/eodhd.py::get_top_movers_symbols_eodhd`
  (machine-readable symbol table behind `get_top_movers_eodhd`; `.US` suffix
  stripped, `change_p` kept as percent, optional `min_price` floor).
  `-n/--movers-count` sets the decliner count (moomoo movers cap at 200;
  eodhd-losers accepts up to the whole feed); `--price-min` gates on the
  feed's live close; mcap / PE / ATR gates still run per-symbol afterwards.
  The feed rows carry price + change only (no name/mcap/type), so ETF/ETN rows
  are not name-filtered at seed time - the per-symbol gates handle them.
  Tests: `test_eodhd_losers_universe_seeds_scan` +
  `test_get_top_movers_symbols_eodhd_sorts_strips_caps` (hermetic, mocked
  feed). Docs: `Strategies/scan.md` "Universe sources",
  `docs/developer/06-entrypoints.md` §6.4, `docs/api_reference.md` §6.2/§9.
- **CLI Nerd Font icons** - the interactive TUI's status cells, team column,
  header/welcome titles and workflow-steps line render Nerd Font (nf-fa) glyphs
  when the terminal font supports them (`TRADINGAGENTS_NERDFONT` defaults on;
  set `0`/`false`/`off` for a plain-text fallback). Pure display change, no run
  behavior. (`cli/main.py`, README CLI section.)
- **News/sentiment providers (Phases A-C)** - three additive sources, per the
  free-tier research:
  - `dataflows/gdelt.py` - GDELT DOC 2.0 (keyless, free). `get_news_gdelt`
    (ticker full-text + **native tone**: avg/pos/neg/neutral per article) and
    `get_gdelt_tone_series` (daily avg-tone timeline). New market/news tool
    `get_gdelt_sentiment` (computed sentiment read). Note: GDELT's endpoint is
    network-flaky (connect timeouts), so it is registered but NOT in the default
    `news_data` chain (opt-in via chain config; fail-fast 8s timeout).
  - `dataflows/newsapi.py` - NewsAPI.org free Developer plan (100 req/day),
    key-gated `NEWSAPI_API_KEY`. `get_global_news_newsapi` (macro headlines)
    + `get_news_newsapi` (ticker keyword); wired into `get_news` /
    `get_global_news` default chains (tail).
  - `dataflows/benzinga.py` - Benzinga Basic Financial News API (free tier,
    headline + teaser + link). Key `BENZINGA_API_KEY`; registered but not in the
    default chain (needs a registered key; enable via chain config).
  - `get_gdelt_sentiment` bound to the news analyst (agent_utils, news
    ToolNode, news_analyst prompt already lists `get_massive_news`; the new tool
    joins it). Live-verified: NewsAPI returns global macro headlines with the
    provided key; GDELT endpoint was unreachable from this network (fail-fast
    degrades, no stall).
  Tests: `tests/test_news_sentiment_vendors.py` (15). ruff clean.
- **Extended technical indicators (Phase 1-3 of the indicator-gap plan)** -
  the standard trend/momentum/volume/structure group the project did not yet
  compute locally, all as pure offline calculators in
  `tradingagents/strategies/extended_indicators.py` (no vendor, no quota):
  Ichimoku cloud, golden/death cross, CCI, ROC, momentum oscillator, TRIX,
  Force Index, accumulation/distribution (A-D), VPT, Chaikin Money Flow,
  anchored VWAP, and a candlestick pattern scanner (doji / hammer / shooting
  star / bullish+bearish engulfing / morning+evening star).
  - Exposed as two new market-analyst tools `get_extended_indicators`
    (one combined call, shares the run-level OHLCV cache) and
    `get_candlestick_patterns`, bound in `agent_utils`, the market analyst
    tool list+prompt, and the graph market ToolNode.
  - Twelve Data `/technicals` pull-back deliberately NOT added: the local
    calculators already cover every indicator off any OHLCV source at zero
    API cost (per the deterministic/no-fabrication core).
  Tests: `tests/test_extended_indicators.py` (22) + 6 tool-wiring cases in
  `test_analysis_tools.py`. ruff clean.
- **Twelve Data + StockData.org vendors** - two new free-tier market-data
  sources wired through the vendor contract:
  - `dataflows/twelve_data.py` - `get_stock_data_twelve_data`
    (`/time_series`, 1day, same CSV shape), `get_market_snapshot_twelve_data`
    (`/quote`, realtime), `get_crypto_prices_twelve_data` (`/time_series`
    `BTC/USD`). Free "Basic": 800 credits/day, 8/min; key `TWELVEDATA_API_KEY`.
  - `dataflows/stockdata.py` - `get_stock_data_stockdata` (`/v1/data/eod`,
    newest-first -> oldest-first CSV), `get_market_snapshot_stockdata`
    (`/v1/data/quote`), `get_news_stockdata` (`/v1/news/all`, 2/req). Free
    "$0/mo": 100 requests/day; key `STOCKDATA_API_KEY`.
  - Both registered in `VENDOR_LIST` + `VENDOR_METHODS` (`get_stock_data`,
    `get_news`); `core_stock_apis` = `eodhd,moomoo,yfinance,tiingo,
    twelve_data,stockdata`, `news_data` = `... ,stockdata`; market snapshot
    fallback chain now Massive -> EODHD -> Tiingo -> Twelve Data; crypto
    fallback Tiingo -> Twelve Data. All key-gated (degrade to the next vendor on
    401/403/429/empty, no fabrication). Live-verified: AAPL OHLCV + quote via
    Twelve Data; AAPL EOD (123 rows) + quote + news via StockData.org.
    Tests: `tests/test_twelve_data_vendor.py` (12), `tests/test_stockdata_vendor.py`
    (10), `tests/test_new_provider_wiring.py` (5). ruff clean.

- **Analyst tool-loop edge regression** - the sequential graph lost its
  `ToolNode -> analyst` edge (introduced in the Option-A wiring pass), so a
  run TERMINATED right after the market analyst's first tool round: empty
  analyst reports, no debate / trader / risk / PM chain, and a stub-only
  report folder (reproduced live: interactive CLI `SKHY`, 2026-08-30). The
  edge is restored with a structural regression test (every analyst's tool
  node loops back) + a functional stream test that must complete a tool round
  and reach the debate. Tests: `tests/test_graph_tool_loop.py` (2).
- **Short-closes overlay crash** - `build_strategy_overlays` returns `None`
  for a < 60-bar series (thinly-traded ADR / new listing), and three folds
  called `.get` on the None (order-flow / position contract / risk governor),
  logging "'NoneType' object has no attribute 'get'". The overlay pipeline now
  treats a None overlay as an empty dict and no-ops cleanly with one
  informative log line. Tests: `tests/test_graph_tool_loop.py`
  (short-closes guard).

### Added
- **Independent pre-debate stances (Option-A hybrid)** -
  `enable_independent_vote` (`TRADINGAGENTS_ENABLE_INDEPENDENT_VOTE`, default
  off) — the 3 risk debators + bull/bear researchers each emit ONE independent
  structured stance (rating / confidence / strength / reason) BEFORE the
  debate loop runs, sampled with **no transcript and no opponents' responses**
  (the independence invariant; prompted without `risk_debate_state` /
  `investment_debate_state`). The G3 agreement/consensus math and the G1
  position contract then use the uncontaminated pre-debate agreement
  (`independent_agreement`), and the PM + Research Manager prompts receive the
  independent vote/reads alongside the debate history. The debates run
  unchanged as the risk-surfacing layer — this kills the conformity /
  adversarial-persuasion bias in consensus (FREE-MAD: consensus pressure
  reduces reasoning accuracy; a persuasive agent can drag a group to a wrong
  consensus). When the flag is off, every fallback is byte-for-byte the legacy
  parse-from-history consensus path. New: `agents/utils/independent_vote.py`,
  `IndependentStance` schema + `render_stance`, two graph nodes
  (`Independent Researcher Stances` / `Independent Risk Stances`), three state
  channels. Tests: `test_independent_vote.py` (12) + 3 prompt-injection
  contracts in `test_structured_agent_prompts.py`. ruff clean.
- **CLI one-input mode (`--symbol`)** - `tradingagents analyze --symbol AAPL`
  runs non-interactively: all 4 analysts, deep research (5 debate/5 risk
  rounds), today's date, and the LLM provider + thinking models from
  `TRADINGAGENTS_LLM_PROVIDER` / `TRADINGAGENTS_DEEP_THINK_LLM` /
  `TRADINGAGENTS_QUICK_THINK_LLM` in `.env`; the report auto-saves to
  `reports/<TICKER>_<ts>/` (now anchored to the repo root via
  `resolve_output_path`, not the process CWD). Interactive (no `--symbol`)
  flow unchanged. Tests: `test_cli_symbol_one_input.py` (3, hermetic).
- **Alpha Vantage keyed fallback** - `ALPHA_VANTAGE_API_KEY` set in `.env`;
  `alpha_vantage` added as the key-gated last vendor in the
  `technical_indicators` / `fundamental_data` / `news_data` default chains
  (free tier, 25 req/day - only consulted when the primary vendors fail).
  Live-verified: OVERVIEW returns real fundamentals for AAPL.
- **Provider-endpoint + calc-wiring pass** - audited every data provider's
  endpoint surface (docs + SDKs) and every strategy calculator for agent
  exposure:
  - **Keyless yfinance fallbacks** (new `y_finance.py` functions —
    `get_analyst_ratings_yfinance`, `get_earnings_calendar_yfinance`,
    `get_institution_holdings_yfinance`) registered in `VENDOR_METHODS` and
    the default `data_vendors` chains (`analyst_ratings`/`earnings_calendar`
    = `moomoo,finnhub,yfinance`; `institution_data` = `moomoo,yfinance`) so
    sell-side ratings, earnings dates/EPS surprise and ownership no longer
    depend on the moomoo gateway or a paid key.
  - **New market analyst tools** wiring unwrapped deterministic calculators:
    `get_scaleout_plan` (swing.scaleout_plan tiered profit-taking),
    `get_payoff_asymmetry` (statistical.omega), `get_book_correlation`
    (statistical.correlation_matrix). `get_strategy_quality` now also reports
    Calmar / Ulcer / tail-ratio / expectancy (previously-unwrapped evaluate.*).
  - All bound to the market ToolNode; hermetic tests
    (`test_yfinance_keyless_vendor.py`, new analysis-tool cases). ruff clean.
- **Tiingo data vendor (free Starter tier)** (`dataflows/tiingo.py`) -
  additive market-data source wired through the vendor contract:
  - **EOD OHLCV** - `get_stock_data_tiingo` (`/tiingo/daily/{t}/prices`, 7+
    yrs, `resampleFreq` daily/weekly/monthly/annually) as the yfinance/moomoo
    CSV shape, registered last in `core_stock_apis` (`eodhd,moomoo,yfinance,
    tiingo`).
  - **Fundamental statements** - `get_fundamentals/balance_sheet/cashflow/
    income_statement_tiingo` render Tiingo `dataCode`s as canonical-friendly
    `label : value` blocks that `statement_parsing._canonicalize` maps via
    `_ROW_ALIASES` (a working free fundamentals source; Massive's free-tier
    fundamentals 403). Registered in the `fundamental_data` +
    statements chains (`moomoo,yfinance,tiingo`).
  - **IEX quote** - `get_market_snapshot_tiingo` backs `get_market_snapshot`
    as a third fallback (Massive -> EODHD -> Tiingo).
  - **Crypto OHLCV** - `get_crypto_prices_tiingo` + a `get_crypto_prices`
    tool bound to the market analyst node + prompt (native crypto price
    source; `BTC-USD` -> `btcusd`).
  - **`--vendor tiingo`** preset in batch (`eodhd,moomoo,yfinance,tiingo`).
  - Key `TIINGO_API_KEY` / config `tiingo_api_key`; low free-tier caps
    (~1,000 calls/day, 50/hr, 500 symbols/mo) keep Tiingo last + behind the
    TTL cache; a 429 degrades via `VendorRateLimitError`.
  Tests: `tests/test_tiingo_vendor.py` (17, hermetic). News (403) + intraday
  (404) are not wired. ruff clean.

 (deep-study implementation)** (`docs/design_nautilus_trader_enhancements.md`) -
  design → implemented (3 phases):
  - **Backtest harness (new capability)** - `strategies/backtest_engine.py`
    (order state machine: SUBMITTED/ACCEPTED/PARTIALLY_FILLED/FILLED/CANCELED/
    REJECTED; bar-based limit/stop matching + cash curve) +
    `strategies/backtest_models.py` (fixed + maker/taker fees, adverse-tick
    slippage, fill-probability heuristic) + `scripts/backtest_strategy.py`
    (replays a report's entry/stop/target plan over vendor OHLCV with order-
    honored entry-then-exit, emitting fills + net-of-cost PnL; auto-reads the
    newest `full_states_log` stop). Advisory, never emits orders. Web:
    `run_backtest` capability + Scripts screen option.
  - **Consistent risk sizing** - `strategies/risk_sizing.py` (commission-aware,
    tranche-aware fixed-risk sizer: `risk_points` / `riskable_money` /
    `risk_money` / `risk_quantity`); `value_dip.tranche_plan` now sizes through
    it (commission shrinks the dollar-risk budget). `strategies/risk_checks.py`
    (rolling-window `RateLimiter` + per-symbol notional `pre_trade_check`).
  - **Statistics + config validation** - `strategies/evaluate.py` adds
    `calmar_ratio`, `ulcer_index`, `capture_ratio`, `tail_ratio`,
    `expectancy_stats`; `default_config.py` adds `validate_config()`
    (collects range/fraction/tranche-sum/HWM-monotonic violations - the
    Nautilus ConfigErrorCollector pattern).
  Tests: `tests/test_nautilus_phase{1,2,3}.py` (44) + value-dip/governor/
  contract regression green; ruff clean.

 (`docs/design_openbb_enhancements.md`) -
  design → implemented (Phases 1-4 + cross-cutting):
  - **Strategy depth** - `strategies/statistical.py` (normality, unit_root
    ADF+KPSS, omega, correlation_matrix, cointegration_pair, granger_causality,
    capm_decomposition, ols_factors, variance_inflation_factor) +
    `strategies/rotation.py` (relative_rotation RRG quadrants, clenow_momentum,
    vol_cones). 5 new market @tools (get_normality / get_unit_root /
    get_relative_rotation / get_capm_risk / get_clenow_momentum).
  - **Typed dataflow layer** - `dataflows/schema.py` VendorResult envelope
    (results/provider/warnings/error_kind + to_llm/to_markdown),
    `dataflows/registry.py` (coverage, required_credentials, filter_params,
    command_map), `route_to_vendor_typed()` mapping sentinels -> error_kind.
  - **Free-tier data surfaces** - `dataflows/cboe.py` (options surface ->
    options_math.black_vol_surface), `dataflows/federal_reserve.py` (SOFR +
    Treasury curve for term-structure discounting), `dataflows/screener.py`
    (yfinance universe screener + movers). 4 new config gates default OFF.
  - **Web product (trading_web)** - watchlist, SignalTable grid, TickerChart
    (candlestick/volume/drawdown), run presets, credential manager, job
    timeline + rerun (54 backend tests, vite build clean).
  - **Web user guide screen (trading_web)** - `HelpGuide.jsx` (`/"guide`),
    plain-language documentation for every screen (purpose, sample UI
    selections, likely result) written for non-technical / non-financial
    users; nav entry + route + guide CSS, `npm run build` clean.
  - **QuantLib + Lean enhancements (deep-study implementation)** (`docs/design_quantlib_lean_enhancements.md`) -
  design → implemented (Phases 1-4 + cross-cutting): new pure modules under
  `strategies/`, extended evaluation breadth, 4 new market analyst tools, and
  10 new config keys (all gates default OFF / advisory-only):
  - **New modules** - `options_math.py` (black76, implied_vol_and_greeks,
    black_vol_surface), `rate_utils.py` (discount_factor, compound_factor,
    equivalent_rate, monotone_fill, downside_measures),
    `portfolio_optimizer.py` (risk_parity_weights, min_variance_weights,
    confidence_weights, enforce_sector_exposure, risk_contribution),
    `risk_manager.py` (two-pass `manage_risk` exit override +
    `trailing_stop_targets`; advisory, not wired into the runtime graph yet),
    `alpha_eval.py` (alpha_score, insight_accuracy), `config_robustness.py`.
  - **Extended modules** - `evaluate.py` (skewness, kurtosis,
    downside_deviation, sortino, tracking_error, information_ratio, beta,
    alpha, treynor, rolling_beta, probabilistic_sharpe, underwater_drawdowns),
    `exits.py` (`trailing_stop_exit`, `max_giveback_exit`), `book_risk.py`
    (`return_autocorrelation`, `var_cvar_horizon`), `journal.py`
    (`trade_excursions` MAE/MFE), `liquidity_risk.py` (volume_share_slippage,
    market_impact_slippage).
  - **New analyst tools (market ToolNode)** - `get_downside_read`,
    `get_horizon_var`, `get_trailing_exit`, `get_risk_parity_alloc`;
    `get_strategy_quality` now also emits sortino + psr.
  - **Config keys (+ `TRADINGAGENTS_*` env overrides, gates default OFF)** -
    `psr_benchmark_sharpe` (0.0), `rolling_window` (132), `downside_mar` (0.0),
    `trailing_stop_pct` (0.05), `enable_trailing_exit` (False),
    `risk_parity_enabled` (False), `risk_manager_drawdown_pct` (0.05),
    `enable_risk_manager` (False), `volume_share_vol_limit` (0.1),
    `volume_share_price_impact` (0.025).
  Tests: 62 new + 176 regression green, ruff clean.

- **P1/P2/C3: pre-open + execution-quality advisory rows (Alpaca free IEX)** -
  implemented the measurable slices of the institutional extended-hours
  workflow with the tiers this machine actually has (probed live):
  - **P1 pre-market RVOL** (`dataflows/preopen.py::premarket_rvol`): today's
    pre-open volume / 30-day pre-open average (Alpaca 15-min bars pre 09:30
    ET) - the text's "RVOL > 2.0x institutional" read. Verified live on AAPL.
  - **P1 pre-open gap** (`preopen_gap`): gap anchored to the LIVE pre-open
    price (Alpaca latest trade), not yesterday's close.
  - **P2 live IEX quote-depth** (`preopen_book_depth`): spread_bps, bid/ask
    size imbalance, thin-book flag - the free-tier stand-in for NOII opening
    imbalance (true NOII is plan-gated; documented as a proxy).
  - **C3 alpha-profile** (`postfill_drift` + `strategy_quality_report`):
    post-fill N-day drift vs arrival on the paper ledger - the "did our fill
    leak / adverse selection" test. All advisory, default-ONLY-injected into
    the pre-market reviewer (never gates).
  - Web Pre-Market screen Help updated; config + env keys added
  - **Agent + web sync**: the 5 decision agents (Trader, PM, 3 risk debators)
    now receive the pre-open RVOL / gap / book-depth reads (plus the existing
    regime + re-rating + plan card) via `computed_decision_context`; the
    value-dip analyst tool renders regime_gate + re_rating rows (visible in
    the web Value Tools page), the pre-market reviewer prints them (web
    Pre-Market job output), and the report's `IVa. Computed Decision Context`
    section surfaces the full advisory set.
    (`enable_preopen_rvol` / `enable_preopen_depth` / `enable_alpha_profile`).
  - **Probed data availability** (your tiers): Alpaca free IEX = pre-market
    bars + live quote + news AVAILABLE; EODHD lowest tier = real-time OHLCV
    only (no pre-open volume baseline), Massive free = NOI 404 (plan-gated),
    short-locate/HTB = NOT AVAILABLE (out of scope, analysis-only).
  Tests: `test_preopen.py` (7, hermetic, mocked Alpaca). Full suite green.

- **Institutional workflow for value-dip + swing (Phases A-E, design
  `docs/design_institutional_value_dip_workflow.md`)** - mapped institutional
  practice (value-desk funnel, AQR-style mean reversion, risk-first tranches,
  desk risk policy, TCA, event sizing, regime switching, VCP/SEPA process,
  quant evaluation) onto the stack. ALL new rows are advisory (computed +
  injected into the LLMs); nothing gates by default (opt-in strict flags):
  - **A1 regime gate** (`strategies/regime.py::regime_gate_read`): rolling
    realized-vol percentile + fast-downtrend knife guard + catalyst window;
    new `regime_gate` row in `value_dip_setup`. Strict opt-in:
    `value_dip_regime_gate` (+ vol/downtrend/halve keys).
  - **A2 re-rating catalyst** (`value_dip.py`): `re_rating` row from REAL EPS
    surprise (earnings tool), revisions, institutional accumulation, forward
    PEG - "cheap stays cheap without a catalyst". Strict opt-in:
    `value_dip_require_catalyst`.
  - **B1 daily-loss + high-water-mark gates** (`risk_governor.govern`): new
    `daily_loss_pct` / `hwm_drawdown_pct` inputs; budget + soft/hard tiers
    (`risk_daily_loss_budget_pct`, `risk_hwm_soft/hard_pct`).
  - **B2 trade plan card** (new `strategies/trade_plan.py::build_trade_plan`):
    one markdown plan (unified stop, tranches, tiers, BE rule, trail,
    adherence checklist) compiled per run and injected into ALL 5 decision
    agents (Trader, PM, aggressive/conservative/neutral debators) via
    `graph._compiled_decision_context`, and appended to the report.
  - **B3 BE-after-confirmation** (`exits.py::breakeven_after_confirmation`,
    `breakeven_trigger` = atr|r|structure): move stop to BE only after 1R /
    higher-low - no more too-early BE.
  - **B4 stop-never-widen** (`stop_never_widen`): unified invalidation stop
    flagged in the plan card + trader prompt.
  - **C1 execution/TCA** (`pre_market.py::record_review`): arrival_price /
    fill_price / slippage_bps columns; `strategy_quality_report` gains an
    execution block (avg slippage, fill rate).
  - **C2 turnover guards** (`min_holding_days`, `max_trades_per_period`).
  - **D1 sleeve tagging** (`memory.store_decision(sleeve)` + parse): honest
    per-style attribution in `strategy_quality_report` sleeves block.
  - **D2 drift/alpha-decay monitor** (`strategy_quality_report`): rolling
    4-wk win-rate/Sharpe vs baseline; `drift_threshold`.
  - **Agent data-feeding**: every run seeds `computed_decision_context` into
    state; the 5 decision nodes cite the deterministic numbers (regime /
    re-rating / plan card / risk snapshot / decay hint) instead of inventing.
  - Config keys + env overrides + `.env.example`; web Help text updated.
  Tests: 1503 passed (2 skipped), ruff clean.

- **Value Dip + Swing enhancements (web-researched, matched to practice)** -
  research compared the setup/exit math against established swing-trading
  practice and closed the gaps:
  - **VCP halving progression** (`swing.py::vcp_setup`): the default
    `contraction_tol` is now `0.65` so each pullback must be *successively
    shallower* (reproducing the named 15%->8%->3%; ratios ~0.53/0.38), with a
    `max_final_depth` (default 8%) final-tightness gate and a `pivot` field =
    the highest high of the final contraction (the Minervini breakout buy
    point). Pass `contraction_tol=1.10` for the old permissive rule.
  - **Chandelier true-highs** (`swing.py::chandelier_exit`): accepts a real
    `highs` series so the trailing stop sits below the true 22-bar high
    (was using closes as an upper proxy); threaded through `swing_report` +
    `get_swing_exits`.
  - **Value-dip trend filter** (`value_dip.py::value_dip_setup`): adds a
    `trend` row (price >= 200-SMA and 50-SMA rising) reported when >=200
    closes; gates only when the caller opts in via `require_trend` (a value
    dip is often below its 200-SMA, so it is not a hard default reject).
  - **Stop harmonization** (`value_dip.py`): the `trade_risk` row now also
    reports `plan_stop_pct` / `plan_stop_ok` (the composite plan stop,
    ~3.5 ATR from P1) vs `max_plan_stop_pct` (8%), reconciling the setup's
    <=2% risk screen with the actual wider tranche stop.
  - **Strict-VDU** (`value_dip.py::value_dip_setup`): `strict_vdu=True`
    promotes the Step-2 VDU ladder, valuation-Z and support to hard gates
    (measured only; unknown still never fails).
  - **Configurable tranche ladder** (`value_dip.py::tranche_plan/risk_read`):
    new `steps` (ATR multiples, default 1.0/2.0) and `pct_steps` (fixed
    %-drawdown-from-P1 ladder) options.
  - **R-based breakeven** (`exits.py::stop_to_breakeven_r`): move the stop
    to break-even after `rr` x R in favor (mirrors practice of ~1R-1.5R).
  Tests: `test_strategies_value_dip` (ladder modes, trend, plan-stop),
  `test_strategies_vcp` (halving, final-tight, pivot), `test_strategies_value_style`
  (R-based BE). Docs: README, CHANGELOG.
- **Interactive CLI now applies the strategy overlays (CLI/batch parity)** -
  the interactive CLI built state directly and streamed the graph but NEVER
  called `_apply_strategy_overlays`, so a CLI report omitted the "Risk Gate
  (computed)" block, position contract and computed risk context that the
  `propagate()` (batch/API) path renders - two same-day NVDA runs diverged
  materially (batch 12:02: Hold / PT 323.37 / gate PASS vs CLI 13:48:
  Underweight / PT 188.32 / no gate block), not from LLM variance alone.
  Fix (`cli/main.py`): seed `risk_context` into the initial state BEFORE the
  Portfolio Manager (via `graph._precompute_risk_context`) and apply
  `graph._apply_strategy_overlays(final_state, ticker)` to the merged state
  before saving - the same two hooks `propagate()` uses, so the CLI report
  now carries the same gate/contract/context. Overlay failures degrade
  silently (cannot break saving, matching propagate). Tests:
  `test_cli_no_console` wiring guard (seed-before-stream, overlay-before-save).

### Fixed
- **Two-stage screener gating (no provider calls during the gate)** - the
  main scan loop now runs a **cheap OHLCV-only gate (Stage A)** on the single
  cached price series before any fundamentals fetch, so `value-dip` /
  `trend-pullback` / `breakout` / `momentum` / `swing` / `vcp` all drop
  definitive non-candidates without hitting a provider. Only survivors reach
  the fundamentals stage (Stage B, memoized once per ticker via
  `_fetch_fin_cached` + `_CASHFLOW_CACHE`) and then provider enrichment
  (Stage C: float / sector / revisions / institutions). `value` / `all` have
  no cheap technical signal and fall straight through, as before. This makes
  a large `eodhd-us` slice tractable (was effectively hanging per-name) and
  fixes the duplicate cashflow fetch inside `_value_dip_scan`. Tests:
  `test_cheap_gate_deferred_before_fundamentals` +
  `test_eodhd_cheap_gate_before_fundamentals` (gated-out names never fetch
  fundamentals). ruff clean.
- **Risk gate placement + compact verdict** - the computed `Risk Gate (computed)`
  block was prepended to EVERY analyst report (input evidence, not risk
  output), so it appeared 6+ times; it now lives once in `4_risk/*.md` and
  `5_portfolio/decision.md` (and once in the consolidated report's IV section).
  The compact-mode `4_risk/verdict.md` previously duplicated the PM decision
  almost byte-for-byte; it now contains the risk gate + a pointer to the
  decision. `scripts/rebuild_complete_report.py` gate recovery hardened (scans
  decision/risk/analyst files in order), and `_readable_section` made
  idempotent (re-render no longer doubles `### Round N` headings or stacks
  blank lines). Tests: `test_report_readable.py` (+3), `test_rebuild_gate_recovery.py` (3).
- **Interactive CLI always writes verbose risk-debate files** - the NVDA run
  produced a single `4_risk/verdict.md` instead of `aggressive.md` /
  `conservative.md` / `neutral.md` because an ambient
  `TRADINGAGENTS_RISK_COMPACT_REPORT=true` (shell env / `.env`) flipped the
  compact-report mode on. The interactive CLI now forces
  `risk_compact_report=False` in `_build_run_config`, so a watched run always
  writes the three per-analyst transcripts; `.env` was also reset to `false`.
  Headless/web runs still honor their own config (they keep the compact
  artifact when they opt in).
- **Readable reports everywhere** - debate/research/trader reports are
  generated as conversational prose concatenated with single newlines, so
  they rendered as one unbroken wall. New `reporting._readable_section`
  (deterministic, content-preserving): adds paragraph spacing between plain
  prose lines and promotes repeated round markers (`Bull Analyst:`/`Aggressive
  Analyst:`) into `### Round N` headings, applied to research (bull/bear/
  manager), trading (trader) and risk (aggressive/conservative/neutral)
  sections. **Corrected 2026-09-16:** the research branch passed the display
  name's first token (`Bull`), which matched nothing, so bull/bear never
  promoted a heading until then. Tables / headings / lists / code fences are never touched.
  Existing folders re-render via `scripts/rebuild_complete_report.py`.
  Tests: `test_report_readable.py` (3).
- **G2 calibration feedback loop wired** (`decision_hardening_spec.md` G2) -
  previously `record_calibration_entry` had zero call sites and `_calibrated_p`
  always returned `None` (identity), so `enable_calibration` computed buckets
  but never used them. Now: (a) `_maybe_record_calibration` stamps
  `{confidence, won=delta_r>0}` into `calibration_ledger.jsonl` at resolve time
  (confidence parsed from the PM decision's `**Confidence**: X` line);
  (b) `_calibrated_p(decision_text)` returns `calibrated_confidence` (identity
  below `calibration_min_n`); (c) `_compiled_decision_context` injects
  `calibration_table_text` into the Trader/PM/risk-debator prompt when the
  ledger has samples. Tests: `test_calibration_wiring.py` (5, hermetic).
- **`get_ratios` abs(None) crash** - `compute_ratios` called `abs(capex)` when
  `capex` was `None` (OCF present, capex missing) -> `TypeError: bad operand
  type for abs()`, which aborted the `tools_fundamentals` node mid-run (seen
  live on NVDA). Both FCF and dividend_yield now guard the missing operand.
  Regression test added (`test_capex_none_does_not_raise`).
- **Strategies docs kept true** - corrected the audit's doc-misnomers:
  `decision_hardening_spec` (`weighted_score` -> `weighted_sentiment`/
  `decayed_weight`/`computed_sentiment_line`; `evaluate_orderflow.py` ->
  `orderflow_evaluate.py`), `alpaca_data_analysis.md` (ScheduleGate /
  `get_clock_calendar` -> the inline `get_clock()` note in `value_screener.py`;
  `scripts/alpaca_fetch.py` -> inline Alpaca OHLCV fallback; `get_assets` +
  Alpaca corporate actions now marked NOT implemented), and
  `value_dip_swing_prepost_research_plan.md` (ROC/TRIX/Force/A-D explicitly
  marked not implemented).
- **Canonical output root (reports/screener/action_reports)** - every
  relative output path is now anchored to the TradingAgents repo root instead
  of the process CWD, so runs never write into the launch directory. The web
  app (launched from ``TradingNew`` or ``trading_web``) previously caused
  ``batch.analyze`` to drop ``reports/`` into those parent folders; stale
  ``TradingNew/reports`` and ``trading_web/reports`` were migrated into
  ``TradingAgents/reports``. New `repo_root()`/`resolve_output_path()`
  helpers in ``tradingagents/dataflows/utils.py``; wired into
  ``batch.py`` (analyze report_dir + batch_summary), ``pipeline.py``,
  ``value_screener.save_watchlist``, ``action_report`` (--reports-dir /
  --out-dir), ``nightly_review``, ``pre_market_review`` and
  ``rebuild_complete_report``. Absolute / ``~`` paths pass through untouched.
- **Full-set audit (read-before-edit): 14 defects across the deterministic
  calculators, the dataflow/vendor layer, and tool binding — the numbers the
  LLM agents cite are now correct and reachable.**
  Correctness (HIGH — silently-wrong numbers):
  - `strategies/exits.py::exit_check` - profit target was anchored at the
    current close instead of the entry, so `target_hit`/`holding_action` could
    never return `target` (target = close + 4*ATR is always > close). Now
    `target_level(entry, ...)`; the `get_exit_check` tool reports real hits.
  - `strategies/book_risk.py::var_cvar_horizon` - parametric CVaR had a sign
    error and divided by the wrong tail probability (`+0.1085` "gain" instead
    of the true negative tail loss). Now `mu_T - sigma_T*phi(z)/q`.
  - `strategies/momentum.py::first_pullback` - reward was measured to the
    already-passed `recent_high`, so `rr = reward/risk < 1` whenever the
    trigger fired and the 2R gate made the candidate permanently dead. Now the
    target is a measured-move extension beyond the trigger. `get_momentum_detail`
    also printed zero pillars because it indexed `pillars()` with keys
    `("a","m","e","l")` that don't exist — fixed to the real
    `rvol/high_volume/gap/price_band/float`.
  - `dataflows/statement_parsing` - (1) yfinance statement CSV payloads
    (`# Data retrieved on: ...` comment header) were mis-routed to the text
    parser by the `:` check, so every canonical fundamental silently degraded
    to n/a; comment lines are now stripped before dispatch. (2)
    `_parse_csv_statements` took the RIGHTMOST numeric cell as "latest", but
    yfinance columns are newest-first, so the OLDEST fiscal year was returned
    as the current value (the M-Score/Piotroski latest-value regression); now
    takes the first (newest) numeric cell. (3) added `stockholders equity`
    aliases so yfinance's "Stockholders Equity" row maps.
  Correctness (MED):
  - `strategies/evaluate.py::tracking_error` - RMS instead of the standard
    deviation of active returns (mean not demeaned), inflating tracking error
    and understating information ratio — now demeaned.
  - `agents/utils/value_dip_tools.py::_period_multiple` - `ev_ebitda` fell back
    to P/EBITDA; now derives EV = market cap + debt - cash (never P/EBITDA).
  - `strategies/ratios.py` + FCF helpers - capex/dividends may be a negative
    GAAP outflow (yfinance/Tiingo) or a positive magnitude (moomoo); FCF and
    dividend yield now use `abs()` so capital spend is subtracted, not added.
  - `dataflows/alpha_vantage_indicator.py` - a generic exception returned an
    error string that `route_to_vendor` caches as authoritative data; now
    re-raised so the chain falls through. `screen_equities` /
    `get_market_movers` invalid-argument replies are now `DATA_UNAVAILABLE`
    sentinels (not cached). `eodhd.get_exchange_symbols_eodhd` keeps the raw
    list for the screener, and the routed `VENDOR_METHODS` entry now uses a
    string renderer to honour the vendor contract.
  Wiring (compute-as-tools):
  - `get_exit_plan` (new @tool) wraps `exits.breakeven_after_confirmation` +
    `max_giveback_exit` — the trade-management exit arithm is now a callable
    tool, bound to the market node.
  - `get_consensus` and `get_sentiment_computed` were re-exported in
    `agent_utils.__all__` but bound to NO ToolNode (unreachable by any agent);
    now bound (fundamentals / market).
  Config:
  - `batch.py` `--vendor` presets (moomoo/yfinance/eodhd/tiingo) omitted the 4
    OpenBB free-tier data categories (`options_surface`, `risk_free_curve`,
    `equity_screener`, `market_movers`), so a preset silently dropped those
    sources from `data_vendors` (failed
    `test_moomoo_preset_is_moomoo_first_everywhere`). All 4 added to every
    preset, keeping the full 27-key category set.
  Low/robustness:
  - `strategies/value_dip.py::tranche_risk_read` - `book_ok` now includes an
    existing-book fraction (`book` param) per its docstring.
  - `strategies/technical_factors.py::keltner_channel` - EMA midpoint (was an
    SMA, which shifted the channel in trending series).
  Tests: added/updated in `test_analysis_tools.py` (exit_plan /
  sentiment_computed / consensus), `test_statement_parsing.py` (newest-first
  CSV + comment-stripped `_canonicalize`); ruff clean.
- **Per-analyst tool-round cap + empty-report guard (NVDA missing market.md)** - a market/news/fundamentals analyst whose tool loop never terminates (model keeps calling tools, or a slow/hung vendor call keeps the loop spinning) previously left the analyst report empty, which reporting.py silently dropped - the run completed 'normally' with no `1_analysts/market.md` and no error. Now: `ConditionalLogic` forces the terminal report turn after `MAX_TOOL_ROUNDS` (8) tool rounds (routing back to the analyst node instead of the tool node), `structured.finalize_messages` runs that turn with the dangling tool_calls stripped (one final LLM call; truncation-retry + degrade intact), and `reporting.write_report_tree` writes an explicit "report unavailable" block (file + consolidated report) when an analyst report is empty - never a silent gap. Sequential and parallel (`analyst_concurrency>1`) analyst paths both covered. Tests: `tests/test_tool_round_cap.py` (12) + 3 reporting guard tests; ruff clean, 124 regression tests green.
- **Empty final decision after structured-output fallback** - a model that
  misses `with_structured_output` can answer the free-text retry with only a
  section header (live-run symptom: `**Decision` alone landed in
  `5_portfolio/decision.md`). `invoke_structured_or_freetext` now detects a
  degenerate stub, re-invokes once with a completion directive, and if still
  empty returns an explicit "**Decision**: unavailable" notice — never a bare
  header. Covers Trader / Research Manager / Portfolio Manager free-text
  paths. Tests: `test_invoke_structured_stub_freetext_regenerates`,
  `..._still_empty_returns_notice`, `..._retry_exception_returns_notice`.
- **End-to-end advisory-context injection (agent + report)** - the Phase A-E
  decision context (`computed_decision_context` / `risk_context`) was seeded
  onto `AgentState` but the keys were not declared as LangGraph channels, so
  native LangGraph silently dropped them: the Trader / PM / 3 risk debators
  never saw the regime gate / plan card / pre-open rows, and the report's
  `IVa. Computed Decision Context` section never rendered. Declared both keys
  on `AgentState` so they flow to the decision nodes and to `final_state`
  (report now surfaces IVa). Regression tests:
  `test_agent_state_declares_decision_context_channels` +
  `test_agent_state_carries_decision_context_through_graph` (a seeded value
  now reaches a node and the graph output).
- **Pre-market reviewer pre-open rows hidden behind news** - in
  `scripts/pre_market_review.py::_build_summary`, the pre-market RVOL /
  pre-open gap / book-depth lines were indented inside the `if news_titles:`
  block, so they only rendered when overnight headlines existed. They now
  print unconditionally (each still degrades to nothing when its data is
  unavailable), matching the design's independent-delta contract.
- **Audit-driven correctness fixes (data integrity + wiring)** - a repo-wide
  audit surfaced and fixed ~26 defects across strategies, dataflows, graph
  wiring, config, and entry points. All with hermetic regression tests.
  Correctness (HIGH):
  - `quantitative_scores.py`: Piotroski ROA point no longer awarded to
    negative-ROA firms (`if roa or 0 > 0` parsed as `roa or False`).
  - `interface.py`: `VendorRateLimitError` now recorded in `first_error`, so an
    all-throttled optional chain degrades to `DATA_UNAVAILABLE` instead of
    raising a raw `RuntimeError`.
  - `alpha_vantage_common.py`: HTTP 429/5xx / timeout mapped to
    `VendorRateLimitError` (was an untyped crash of the prime price path).
  - `strategies/dcf.py`: projects the LATEST FCF, not the historical max (a
    declining/hump series was overstated ~30-40%).
  - `strategies/technical_factors.py`: OBV bullish-divergence slice fixed
    (was always False).
  - `y_finance.py`: fundamentals/statement/insider functions re-raise instead
    of returning an "Error retrieving..." prose blob that the router cached as
    truth and never fell back from.
  - `default_config.py`: list-typed env overrides (e.g.
    `TRADINGAGENTS_TRANCHE_WEIGHTS`) coerce to the default's element type; a
    numeric list was landing as strings and silently disabling the tranche fold.
  - `market_analyst.py`/`fundamentals_analyst.py`/`news_analyst.py`: bound
    tools the prompts instruct (get_expected_move, get_institution_holdings,
    get_earnings_surprise_history, get_momentum_scan,
    get_market_snapshot_alpaca, get_insider_transactions), closing a
    no-fabrication gap (the model could not fetch those figures).
  Edge/wiring (MEDIUM):
  - `yfinance_short_interest.py` / `y_finance.py`: percent fields scaled x100
    with a `%` marker (was 100x unit drift).
  - `moomoo.py`: `_check_ret` classifies quota/throttle (incl. Chinese
    phrasing) as `VendorRateLimitError` before the permission check;
    `_moomoo_code` raises on forex/futures/non-whitelisted-crypto instead of
    returning a bogus `US.` code.
  - `pre_market.py`: `resolve_ledger` uses a stored `prior_close`
    (non-circular - was recomputing the exact review gap); `record_review` now
    stores it.
  - `size.py` `stop_loss_atr` returns None on insufficient data (was 0.0);
    `market_session.py` `opening_range` emits a target only for a real ORB
    breakout (was a below-stop short target on a flat close).
  - `normalized.py` `trap_verdict` accrual default 0.06 (consistent with
    `value_dip.decline_driver_check`; was 0.02).
  - `pipeline.py`: `_run_batch` caps workers via `batch.effective_workers()`
    (was bypassing the moomoo connection cap).
  - `value_screener.py`: `--rank composite` / `enable_composite_rank` now wired
    (were dead); eodhd-us universe truncation is warned, not silent.
  - `strategy_quality_report.py`: real `--illiq` flag + cost threading (was
    documented but rejected by argparse); `validate_massive_flat.py` returns a
    non-zero code when no CSV is present.
  - `trading_graph.py`: seeds deterministic `risk_context` into the initial
    state so the Portfolio Manager actually receives CVaR/liquidity context
    (was computed only after the graph, never reaching the PM).
  - `regime.py` `realized_vol` returns None on insufficient data
    (`factors.py` guard updated); `parabolic_sar` computes `below`/`exit` when
    a `closes` series is supplied.
  Docs/config truth:
  - `api_reference.md` §1.2/§5 + `.env.example`: strategy-overlay defaults
    aligned to code (only `enable_events`/`enable_reflection`/
    `enable_sentiment`/`enable_strategy_overlays` default True; the rest
    opt-in) - docs previously claimed default True.
  - Documented the two missing `TRADINGAGENTS_ENABLE_DECISION_AUDIT` /
    `TRADINGAGENTS_ENABLE_LIQUIDITY_GATE` overrides; corrected the stale
    `enable_sentiment` "no override / off" comment.
  - `api_reference.md` §9: batch `--vendor` eodhd, `--workers` 1-4,
    pipeline `--universe` top-movers-massive; AGENT_ONBOARDING "~40" tools.
  - `default_config.py`: marked reserved-but-not-yet-wired keys
    (`enable_regime`, `enable_factors`, `enable_threshold_gate`,
    `consensus_seeds`, `calibration_min_n`, `risk_stress_shock_pct_1/2`).
  Web (`TradingNew/trading_web`): `run_strategy_quality` now forwards `--illiq`
  (+ SPA checkbox). Tests: 1490 passed, 2 skipped; ruff clean repo-wide.

### Added
- **EODHD real-time snapshot + top movers (Massive 403 fallback)** - the
  Massive snapshot / top-movers endpoints are 403 on the free plan; EODHD's
  `/api/real-time` works on the EOD plan and now backs them:
  - `get_market_snapshot_eodhd(ticker)` - `/api/real-time/{ticker}`: live
    15-20 min delayed OHLCV + prev close + change% (the market analyst's
    "latest verified bar" + gap read).
  - `get_top_movers_eodhd(direction, count)` - `/api/real-time/{ticker}?ex=US`:
    one call returns ~18k US stocks sorted by change_p (gainers/losers +
    universe replacement).
  - `get_market_snapshot` / `get_top_movers` tools now fall back to EODHD
    when Massive returns an 'unavailable' string (403) or raises.
  - Fixed `_eodhd_get` error detection: a dict with a `code` field but no
    `message` is a normal payload (the real-time response's `code` is the
    ticker symbol), not an error.
  Tests: `test_eodhd_vendor.py` (7 new: snapshot render/no-data, movers
  sort/invalid/no-data, tool fallback x2) + `test_massive_vendor.py`
  failover updated (both-down degrades).
- **Truncation-retry enforcement (max_tokens is a ceiling, not a floor)** -
  when an LLM response is cut at the output cap (ends mid-sentence), the
  agent now re-invokes with a continuation prompt and merges, so reports are
  never truncated. Wired into every agent path:
  - `structured.py::_retry_if_truncated` (free-text fallback of PM/RM/trader/
    sentiment), `retry_chain_if_truncated` (market/news/fundamentals analyst
    tool-calling chains), `retry_llm_if_truncated` (bull/bear researchers +
    aggressive/conservative/neutral risk debators).
  - Up to 2 continuation attempts, each only when a cut was detected; a
    failed continuation degrades to the original text (never raises).
  - Tests: `tests/test_truncation_retry.py` (7).
- **Tool-wiring audit: 4 new market tools + run-level OHLCV cache + computed
  sentiment on** - the audit found strategy functions that were implemented
  but never exposed to the analyst LLMs, and duplicate OHLCV fetches across
  tools. Fixes:
  - `get_technical_factors(ticker)` (market) - ADX / pivots / Aroon / Fisher /
    Chaikin / Elder-Ray / Supertrend / volume-profile in ONE call.
  - `get_book_tail_risk(ticker, weights?)` (market) - portfolio CVaR +
    correlated -10% stress + drawdown gate (book-level tail).
  - `get_liquidation_days(ticker, shares_to_liquidate?)` (market) - days to
    absorb a block at a 15% participation cap.
  - `get_premarket_review(ticker, prior_close?, open_price?, prior_stop?,
    entry_price?)` (market) - deterministic CONFIRM / REVISE / REJECT arbiter.
  - Run-level OHLCV cache (`_RUN_OHLCV_CACHE` in analysis_tools.py): every
    tool shares ONE vendor fetch per (ticker, days) per run - no duplicate
    data / quota burn. Cleared in conftest between tests.
  - `enable_sentiment` now **True** (was False): the computed StockTwits
    score + surprise velocity is injected into the sentiment report (the
    sentiment functions existed but were never delivered).
  Tests: 8 new hermetic tool tests + cache test + market-toolnode guard.
- **Fix market tool-node binding gap + raise quick-tier output cap** -
  the market analyst's prompt lists `get_swing_exits` / `get_dip_technical` /
  `get_mean_reversion_tech` and the 5 market-session tools (`get_opening_range` /
  `get_gap_type` / `get_order_imbalance` / `get_premarket_liquidity` /
  `get_post_close_confirmation`), but they were never registered in the market
  `ToolNode` (a wiring gap from the original value-dip+swing commits) — so every
  run had the LLM call tools that error "not a valid tool" and the chandelier
  trail-stop wiring (`final_state["swing_exits"]`) was dead. All 8 are now bound
  (41 market tools). `max_output_tokens` / `max_output_tokens_quick` raised
  6000 → 8000 after 2026-08-27 WDC analyst reports truncated mid-sentence at
  the 6000 cap. Tests: `test_market_toolnode.py` regression guard (8 tools).
- **EODHD as primary OHLCV vendor + eodhd-us default universe** - the
  `core_stock_apis` chain is now `eodhd,moomoo,yfinance` (EODHD first,
  moomoo/yfinance as fallbacks); `news_data` is `eodhd,moomoo,yfinance` and
  `corporate_actions` is `eodhd,moomoo`. New EODHD endpoints on the EOD plan:
  `get_news_eodhd` (news), `get_corporate_actions_eodhd` (splits +
  dividends), `get_exchange_symbols_eodhd` (full US symbol list, ~18k common
  stocks). The value screener's default `--universe` is now `eodhd-us`
  (EODHD full-US list, no moomoo quota); `top-losers` / `heat-proxy` (moomoo
  movers) stay as the optional intraday-momentum source. Fundamentals /
  technicals / intraday / options are NOT on the EOD plan, so those chains
  keep moomoo/yfinance first. Tests: `test_eodhd_vendor.py` (14) +
  `test_value_screener.py` eodhd-us universe (1).
- **EODHD vendor (daily OHLCV)** - `dataflows/eodhd.py` serves daily bars as
  the same CSV shape yfinance/moomoo produce, registered in the
  `core_stock_apis` chain (`moomoo,eodhd,yfinance` by default) and as a
  `--vendor eodhd` preset (`batch.py`/`pipeline.py`). Key:
  `TRADINGAGENTS_EODHD_API_KEY` (in `.env`). Free tier 20 calls/day; the EOD
  plan ($19.99/mo) is 100k calls/day @ 1000/min with 30+ years history — a
  replacement for the moomoo K-line quota (100 calls/7 days) that the value
  screener exhausts. Tests: `tests/test_eodhd_vendor.py` (8).
- **Moomoo per-call timeout + value-dip gating pre-filter + web screener
  budget** - three fixes for the value-screener web timeouts:
  - `moomoo_call_timeout` (default 5.0s, env `TRADINGAGENTS_MOOMOO_CALL_TIMEOUT`):
    every moomoo SDK call now runs under a wall-clock timeout wrapper
    (`dataflows/moomoo.py::_sdk_call`) instead of the SDK's own 20s
    `ReqInfo.wait()`, so a degraded gateway can't burn 20s per call across
    hundreds of calls.
  - The value-dip gating pass runs a cheap OHLCV-only pre-filter
    (`scripts/value_screener.py::_value_dip_technical_prefilter` — RSI <= 35,
    %b <= 0.10, stop <= 2%) before the heavy fundamentals fetch, dropping the
    per-symbol vendor calls from ~7 to 1 for non-candidates.
  - The web `run_screener` capability budget is raised to 2400s (matching the
    action report's `--llm` budget) and a timed-out capability now kills its
    whole process tree (`taskkill /F /T`) so no orphaned process keeps a
    moomoo context / gateway connection open.
  Tests: `test_moomoo_vendor.py::MoomooSdkCallTimeoutTests` (5),
  `test_value_screener.py` prefilter (3), `test_backend.py` kill-tree (3).
- **Correlation-aware allocation wired into the allocation plan** -
  `portfolio.allocation_block` and the `get_allocation` analyst tool accept
  `returns_by_name` and, when `enable_correlation_penalty` is on (default
  False; `correlation_threshold` 0.6 / `correlation_penalty_frac` 0.3),
  down-weight names whose average pairwise correlation with the rest of the
  book exceeds the threshold before the per-name/per-sector caps. The
  screener's `--alloc` builds return series from the run's OHLCV cache and
  passes them through; names without a measurable series are never penalized.
  Env: `TRADINGAGENTS_ENABLE_CORRELATION_PENALTY` /
  `TRADINGAGENTS_CORRELATION_THRESHOLD` / `TRADINGAGENTS_CORRELATION_PENALTY_FRAC`.
  Tests: portfolio + analysis_tools + value_screener.
- **Industry-practice suggestions implemented (7 items)** -
  - Correlation-aware allocation: `portfolio.correlation_penalty` /
    `mean_correlation` down-weight names highly correlated with the book
    (risk-parity style).
  - Book-level stress: `book_risk.book_correlated_stress` shocks the whole
    basket together; surfaced in the risk snapshot + report risk-gate block.
  - Liquidity-aware costs: `exits.net_of_cost` / `evaluate.net_returns` accept
    an `illiq` (Amihud) param to scale cost for illiquid names.
  - Paper-ledger track record: `pre_market.ledger_track_record` measures the
    reviewer's win rate / avg realized return from resolved rows.
  - Limit-order directive: `pre_market_review.py` appends a thin-liquidity
    "prefer limit orders / reduce size" reason when the book is thin/illiquid.
  - Claim-vs-computed audit: `reporting.audit_decision_numbers` (opt-in via
    `enable_decision_audit` / `TRADINGAGENTS_ENABLE_DECISION_AUDIT`) flags a PM
    decision's Stop Loss far from the computed contract stop.
  - Strategy-quality report: `scripts/strategy_quality_report.py` reads the
    reflection + pre-market ledgers and reports net-of-cost Sharpe / drawdown /
    win rate (wired into the web raw allowlist).
  Tests: portfolio/book_risk/evaluate/pre_market/reporting/value_style.
  Full suite 1427 passed.

### Fixed
- **Moomoo exit-hang** - `dataflows/moomoo.py` had a shadowing duplicate
  `_close_all_ctxs()` (the atexit one called `ctx.close()` directly, which
  can block on the dead receive loop and keep the process alive after
  `main()` returns). Removed the duplicate; the daemon-thread + timeout
  version is the only one. Added `close_context()` to the end of
  `value_screener.py`, `action_report.py`, `capital_income_screener.py` and
  `pre_market_review.py` main() so the moomoo context closes while the
  process is healthy (the graph already did this). A screener run that
  previously hung ~15 min after writing its report (web job timed out) now
  exits cleanly. Regression test: `test_close_all_ctxs_uses_daemon_thread_timeout`.

### Added
- **Value-dip + swing + pre/post-market research implementation** -
  - `technical_factors.py`: 6 new pure factors - `aroon` (trend age),
    `fisher_transform` (normalized reversal), `chaikin_oscillator` (buying
    pressure), `elder_ray` (bull/bear power), `supertrend` (ATR trailing),
    `volume_profile` (POC + value area). All return None on insufficient data.
  - `market_session.py` (new): `opening_range` (ORB breakout + 2R stop/target),
    `gap_type` (common/breakaway/runaway/exhaustion + fill stats),
    `order_imbalance` (buy/sell-heavy from flow nets), `premarket_liquidity`
    (thin-book warning), `post_close_confirmation` (stopped-out/target-hit/hold).
  - 5 new market-analyst tools: `get_opening_range`, `get_gap_type`,
    `get_order_imbalance`, `get_premarket_liquidity`, `get_post_close_confirmation`
    (bound to the market analyst + prompt directives).
  - Screener columns: `Aroon`, `Fisher`, `Supertrend`, `POC` (volume profile).
  - Tests: `test_strategies_market_session.py` (30) + extended
    `test_strategies_technical_factors.py` (17 new).
- **Conditional action report** - `scripts/action_report.py` checks report
  verdicts against the risk basket (`TRADINGAGENTS_RISK_BASKET_WEIGHTS`):
  basket names are kept on their newest Underweight/Sell verdict (reduce/trim),
  non-basket names on their newest Overweight/Buy verdict (add). The report's
  stated condition (re-entry level, trim zone, scale-in confirmation) is
  extracted from Position Size + Executive Summary and checked against live
  OHLCV via the vendor chain — deterministic MET / NOT_MET / UNKNOWN, never
  fabricated. Stop/ATR levels are informational; unmeasurable qualifiers
  (PUC, VDU trigger, stabilization) render UNKNOWN. Optional `--llm` invokes
  a deep-think judge (`ActionConditionVerdict` schema +
  `overrides/action_condition_judge.py`) for UNKNOWN conditions. Output: a
  final action report (ADD/BUY, TRIM/REDUCE, MONITOR) printed + saved
  (keep-only-newest). Tests: `tests/test_action_report.py` (21).
- **Screener: full 11-SPDR sector ranking table** - `_sector_table_markdown`
  renders the whole sector ranking (ETF, name, 1m/3m returns, rank, top-3
  flags) and appends it to the report whenever the ranking is computed
  (`--sector-rank` / `--enrich-sector`). The watchlist previously showed only
  the candidate's SecRank column; now the reader sees the full table the
  framework's "top 3 of 11 SPDR groups" rule is based on. Rows without
  history render n/a and never rank top-3. Tests:
  `test_sector_table_markdown_renders_full_ranking` +
  `test_enrich_sector_populates_without_gating` (asserts the table appears).
- **Report truncation marker** - `reporting._finalize_section` appends a
  visible blockquote marker when a section ends mid-sentence (LLM max_tokens
  cut), so the reader knows the tail is missing at the LLM layer, not a file
  bug. Conservative heuristic: only bare lowercase/digit endings >= 120 chars
  that aren't sentence punctuation, markdown constructs, or bold-label lines
  (`**Consensus**: High`). Applied to every section file + the consolidated
  report. Tests: `test_truncation_marker_appended_to_mid_sentence_sections` +
  `test_finalize_section_roundtrip`.
- **Web: value-dip + swing tools page** - `trading_web` gains a `run_value_tools`
  capability (in-process, read-only) and a "Value tools" SPA page that runs
  `get_value_floors` / `get_swing_exits` / `get_dip_technical` /
  `get_mean_reversion_tech` for one ticker — the same computed numbers the
  analyst LLMs are bound to, inspectable before queueing a full run. Also
  fixed a pre-existing flaky web test: `security._secret()` read the secret
  file back with `.strip()`, which silently dropped a leading/trailing
  whitespace byte from the 32 random bytes and intermittently invalidated
  every session cookie (401s). Tests: `test_value_tools_capability_registered_and_guarded`
  + `test_secret_file_roundtrip_preserves_whitespace_bytes`.
- **Per-role max output tokens + density directives** -
  - Config: `max_output_tokens` (6000), `max_output_tokens_quick` (6000),
    `max_output_tokens_deep` (2500) + env overrides
    `TRADINGAGENTS_MAX_OUTPUT_TOKENS(_QUICK/_DEEP)`.
  - `openai_client._PASSTHROUGH_KWARGS` now forwards `max_tokens` (OpenAI /
    OpenRouter); Anthropic / Bedrock already did. `trading_graph` passes the
    per-tier value (quick vs deep) to each client.
  - `get_output_budget(section)` in `agent_utils`: per-role prompt directive
    (dense, bounded ~250-1400 words by role; tool-call-first: never approximate
    a number that a tool can return). Wired into all 12 agent prompts
    (4 analysts, bull/bear, 3 risk debators, RM, PM, trader).
  - Values grounded in your formula `min(1,048,576, 1,310,720 - input)` +
    measured per-role report maxes (analysts ~5k, RM 1.9k, trader .7k, PM 1.4k).
  Tests: `test_openai_compatible_provider` (max_tokens passthrough + budget
  helper). Docs: api_reference env table, .env.example, README, CHANGELOG.
- **OpenRouter provider-ignore routing** - `TRADINGAGENTS_OPENROUTER_IGNORE_PROVIDERS`
  (.env, comma-separated provider slugs) lets you block slow/unreliable
  OpenRouter endpoints for every request. The list is sent as `provider.ignore`
  in the OpenRouter Chat-Completions body via `extra_body` (nested under the
  `provider` key, per OpenRouter's provider-routing docs). Applied only when
  `llm_provider=openrouter` and the list is non-empty; erased if empty.
  `default_config._ENV_OVERRIDES` coerces the CSV string to a list; default `[]`.
  Tests: `test_openai_compatible_provider` (3: payload present, empty omitted,
  non-openrouter ignored). Docs: api_reference env table, README, CHANGELOG.
- **Free computed ratios (no paid Massive plan)** - `strategies/ratios.py`
  replicates the plan-gated Massive `get_ratios` block from the project's own
  canonical statements: EV, EV/EBIT, EV/EBITDA, EV/Sales, P/E, P/B, P/S,
  P/CF, P/FCF, ROE, ROA, D/E, Current, Quick, cash ratio, dividend yield, FCF,
  market cap. Exposed as `get_ratios` on the fundamentals analyst (computed =
  free; missing inputs render n/a, never fabricated). Adds the `inventory`
  canonical alias so Quick ratio computes. Also fixes a latent double-`@tool`
  decorator bug in `analysis_tools.py` that broke import once the file grew.
  Tests: `test_strategies_ratios` (6 pure) + `test_analysis_tools` (2 tool).
  Docs: api_reference 6.4, developer/04, tests-layout.
- **SEC EDGAR -> Massive insider fallback** - `get_sec_filings` (`agents/utils/
  market_position_tools.py`) now falls back to Massive's `get_form4_insider_massive`
  (Form 4 open-market insider transactions) whenever official SEC EDGAR is
  unavailable: HTTP 403 from SEC fair-access throttling, network failure, or a
  non-US ticker with no EDGAR record (which previously surfaced as
  `NO_DATA_AVAILABLE` / a raised error and degraded the signal). The fallback
  text is explicitly labelled "Massive insider-activity fallback (Form 4 — NOT
  the 8-K/10-K/S-1 set)" so the agent never confuses the datasets; if Massive
  also returns nothing it degrades to an explicit unavailable message (no
  fabrication). Bound to the news analyst's `get_sec_filings` tool + prompt.
  Tests: `test_market_toolnode` (5 fallback cases: EDGAR ok, raise-on-403,
  no-data sentinel, insider body, both-down degrade). Docs: api_reference
  §6.2, data-providers, README, AGENT_ONBOARDING.

- **Web UI (sibling project, not in this repo)** - `TradingNew/trading_web/`
  adds a React SPA + FastAPI web front-end over every TradingAgents capability
  (batch / pipeline / screener / pre-market / nightly / decision-history /
  report viewer / raw read-only), with security-first auth: scrypt password
  hashes, HMAC-SHA256-signed session cookies, CSRF double-submit, login
  lockout, strict path defense on report reads, an allowlisted raw-command
  shell, CSP + security headers, and a JSONL audit log. Serves the SPA from
  the FastAPI backend; 127.0.0.1:8000 by default with `TRADINGAGENTS_WEB_*`
  overrides for a later public deployment. See
  `TradingNew/trading_web/README.md` (not tracked by this repo, per the
  layout rule).

- **Pre-market review (overnight reviewer)** - closes the gap between a
  close-time decision and the next open (design `docs/pre_market_review.md`,
  choice (a)):
  - `strategies/pre_market.py` - deterministic deltas + verdict arbiter:
    `premarket_gap` (gap % / ATR, through-stop / adverse-fill detection),
    `catalyst_window_read` (B1 hard-block / window tighten),
    `reanchor_plan` (tranche re-anchor with per-trade + book caps),
    `review_decision` (CONFIRM / REVISE / REJECT from measured deltas only),
    `load_prior_state` (fail-open loader for `full_states_log_*.json` +
    `5_portfolio/decision.md`).
  - `PreMarketVerdict` schema + `agents/overrides/pre_market_reviewer.py` - a
    deep-think prompt variant (reuses the PM's LLM; no new graph node) that reads
    the prior decision + a number-only deltas summary and emits a structured
    verdict; the deterministic REJECT is never downgraded by the LLM.
  - `scripts/pre_market_review.py` - standalone pre-open path (gap/anchor),
    default = newest report folder, `--prior-date` / `--report-dir` overrides,
    `--skip-llm` (deterministic only) / `--dry-run`.
  - `batch.py` - opt-in same-night step (`enable_pre_market_review`): after each
    symbol's report, a catalyst/quality re-check writes `pre_market_review_<date>.md`
    next to the report; never fails the symbol.
  Config: `enable_pre_market_review` (+ `TRADINGAGENTS_ENABLE_PRE_MARKET_REVIEW`).
  Tests: `test_strategies_pre_market` (pure, 19) + `test_pre_market_review`
  (script + batch, 3). Docs: `docs/pre_market_review.md` status -> implemented.
- **Pre-market review follow-up: defect fixes + 6 features** -
  - Fix 1: the standalone script now extracts the prior plan's entry/stop
    (`parse_planned_levels`) and re-anchors the tranche plan to the measured
    open, so the gap / through-stop / adverse-fill / cap-breach checks in
    `review_decision` actually run (previously the stand-alone passed no
    `prior_stop`/`reanchor` and degenerated to catalyst-only).
  - Fix 2: `batch._batch_pre_market_check` passes `results_dir`, so the
    same-night step finds the full state JSON (not just `decision.md`).
  - Fix 4 (+ feature 1): `_fetch_deltas` prefers a real-time pre-market price
    (Alpaca `get_intraday` when `enable_alpaca`, else yfinance
    `fast_info.last_price`) over the daily close, and adds ATR(14).
  - Feature 2: `scripts/nightly_review.py` drives pre-open reviews from the
    latest `reports/batch_summary_*.jsonl`.
  - Feature 3: paper-book ledger (`data_cache_dir/pre_market_ledger.jsonl`)
    via `record_review` / `resolve_ledger` (pending -> realized return).
  - Feature 4: `scripts/decision_history.py` prints a per-ticker decision
    series from the per-date `full_states_log_*.json` files.
  - Feature 5: guarded overnight-headline context (`_headline_delta`) into the
    reviewer summary (never a hard gate, titles only).
  - Feature 6: scheduler notes (cron / Task Scheduler) in
    `docs/pre_market_review.md` §15.
  Tests: `test_strategies_pre_market` + `test_pre_market_review` extended
  (planned-levels parse, results_dir lookup, headline delta, decision history,
  nightly driver). Full suite green; ruff clean.

### Added

- **Capital-income screener: live `--universe preferred-top` + `--refresh`** -
  the free providers don't expose a validated 500-symbol preferred list, so
  the standalone screener now seeds its universe at runtime from the top
  holdings of the major preferred ETFs (PFF / PFFD / PGF / PGX / PFFV) via
  yfinance `get_funds_data().top_holdings` (no key). Every candidate is
  validated during the run (price + dividendRate); only names that resolve
  are ranked. `--refresh` writes the validated set back to the universe file
  (header preserved), so the curated list stays current without manual edits.
  Tests: `test_capital_income_screener` (universe mode + refresh write-back).
  Full suite 1311 passed / 2 skipped; ruff clean.

- **Standalone preferred-income screener (Strategies/capital_income.md)** -
  a new self-contained screener that does NOT wire into the trading graph or
  any agent. Implements the Global X U.S. High Yield Preferred Index
  methodology: (1) liquidity/quality screen (market cap >= $250M AND 3m ADTV
  >= $1M), (2) indicated-dividend-yield ranking (annualized dividend / price,
  top 50), (3) MV weighting (or equal-weight fallback when per-issue shares
  aren't exposed - preferreds report no per-issue market cap) with the 3% cap
  + pro-rata renormalization.
  - `strategies/capital_income.py` - pure math (annualized dividend, indicated
    yield, ADTV dollar, liquidity gate, top-N, MV/equal weights, cap +
    renormalize). No-fabrication: None on missing input.
  - `scripts/capital_income_screener.py` - standalone CLI (positional/--file
    universe, --top, --min-mcap, --min-adtv, --out-dir, --dry-run, --json);
    pulls price + dividendRate + market cap + OHLCV via yfinance + the vendor
    chain. Uses `info.dividendRate` (pre-annualized) - never the trailing-12m
    sum, which preferreds pollute with special distributions.
  - `Strategies/preferred_universe.txt` - seeded ~24 liquid US preferreds
    (hyphenated Yahoo symbols that resolve with a dividendRate).
  Tests: `test_strategies_capital_income` (10 pure) + `test_capital_income_screener`
  (5 hermetic, mocked yfinance/OHLCV, asserts no graph/agent imports). Full
  suite green; ruff clean.

- **Liquidity gate on by default + surfaced in PM prompt & risk report** -
  `TRADINGAGENTS_ENABLE_LIQUIDITY_GATE=1` is set in `.env` (on by default), so
  the risk governor now REJECTs ILLIQUID names / WARNs on CAUTION ones using
  the risk2.md metrics. The computed liquidity block is surfaced in two places:
  - the **Portfolio Manager prompt** - a `Computed liquidity` line (verdict +
    ILLIQ + float-turnover + IWF + reasons) grounds the PM's liquidity/sizing
    language and instructs scaling size down (or to 0%) on CAUTION/ILLIQUID;
  - the **risk report** (`Risk Gate (computed)` block) - shows `Liquidity
    verdict` + ILLIQ / float-turnover / IWF + reasons when the gate computed it.
  Both degrade gracefully (no line) when the gate didn't run or had no data.
  Tests: `test_reporting` (liquidity block render + PM prompt wiring). Full
  suite 1291 passed / 2 skipped; ruff clean.

- **Liquidity & ownership risk (Strategies/risk2.md)** - implements the five
  institutional risk metrics as a pure, offline module
  (`strategies/liquidity_risk.py`): free-float factor (IWF), float turnover
  (ADV / float), Amihud ILLIQ (price impact per $ traded), days-to-absorb
  (overhang), and ownership HHI (concentration), plus a composite
  LIQUID / CAUTION / ILLIQUID verdict. No-fabrication: every metric returns
  None on missing input.
  - **Risk governor gate (opt-in)**: `govern()` accepts a liquidity verdict;
    ILLIQUID REJECTs, CAUTION WARNs. Enabled via `enable_liquidity_gate`
    (default False - preserves current behavior); the graph computes the
    verdict from vendor OHLCV + float + shares when on.
  - **Analyst tools**: `get_liquidity_risk` (market analyst) and
    `get_ownership_concentration` (fundamentals analyst, HHI best-effort -
    n/a when no per-holder breakdown) + prompt directives.
  - **Screener columns**: `ILLIQ` / `FltTurn` / `IWF` added to the report
    (pure-calculable from OHLCV + float + shares) + legend entries.
  Tests: `test_strategies_liquidity` (16 pure), governor liquidity cases,
  tool cases. Full suite green; ruff clean.

- **Screener: fill the n/a columns (compute + enrich)** - most columns were
  blank because they were gated behind a scan mode or a CLI flag, not because
  the data was missing:
  - **Piotroski F-Score now computes** - added `enrich_screen_ratios` in
    `statement_parsing` which derives the ratio inputs no vendor row provides
    directly (`roa`, `leverage`, `current_ratio`, `gross_margin`,
    `asset_turnover`, `shares_issued`, with prior periods) from the canonical
    statements the chain already fetches, so the F column (previously always
    `n/a`) computes from the moomoo data (- in a live AAPL run F=7, was n/a).
  - **`--scan all` now fills every technical column** - a new
    `_compute_scan_row` helper runs all scan buckets (TrendPB/Breakout/RSI +
    momentum `Pills/Pull/RR` + `Swing/RS/Stp/T2` + `VCP/Brk` +
    `VDip/FCFy/RSI/%b/Stp%`) for every symbol on the default `all` mode, so a
    standard positional run shows these columns instead of `n/a`. Added shared
    run-wide OHLCV/float/benchmark caches (reset per run) so the movers
    gating and the results loop fetch each symbol's OHLCV once. Dedicated
    `--scan <mode>` still filters (now also honoured on the positional path).
  - **New non-gating enrich flags** - `--enrich-sector`, `--enrich-rev`,
    `--enrich-inst` populate `Sec/SecRank`, `RevUp` and `Inst` without the
    filtering that `--sector-rank` / `--revision` / `--inst-accum` apply.
  - `Name` stays mover-metadata-only (classic path shows `n/a`) and
    `L1Px/VWAP1m/1mVol` stay behind `--intraday` (Alpaca cost) by design.
  Tests: F-score derivation, a positional `--scan all` that populates the
  technical columns, and `--enrich-sector` without gating. Full suite 1265
  passed / 2 skipped; ruff clean.

- **Screener FMP 429 rate-limit noise - normalized enrichment now uses the
  vendor chain** - the value screener's ``normalized_score()`` enrichment
  (columns ``nebit_ev_ebit`` / ``pe_pct5`` / ``fmp_ev``) fetched multi-year
  income + enterprise-values straight from FMP, so on the free tier it
  logged ``fmp income-statement: status 429`` / ``fmp enterprise-values:
  status 429`` warnings every run and blanked those columns. ``income_series``
  (new in ``statement_parsing``) now extracts 2+ annual
  ``{year, revenue, ebit, net_income}`` rows from the income statement the
  vendor chain already returns (moomoo markdown period tables or yfinance
  CSV), and ``normalized_score`` computes NEBIT / EV / EV-NEBIT from that +
  canonical fundamentals (market cap, debt, cash), reconstructing the 5y
  P/E percentile best-effort from historical closes x current shares. FMP is
  now only a last-resort fallback when the vendor chain has no income history
  AND an FMP key is set. No more 429s on the default moomoo,yfinance chain;
  the columns compute offline. Tests: `test_fmp` (vendor-chain normalized
  score, fmp_get never called on the default path, no-income degrade, CSV
  income series), `test_statement_parsing` (markdown + CSV income_series).
  Live: AAPL -> ev_nebit 33.96 / pe_pct5 0.75 with no FMP key.

- **Yahoo can't resolve moomoo's dotted US share-class symbols** - moomoo's
  US movers rank returns dotted share classes (`PBR.A`, `MOG.A`, `MOG.B`) but
  Yahoo only resolves the hyphen form (`PBR-A`, `MOG-A`, `MOG-B`, `BRK-B`), so
  yfinance (the second vendor in the default `core_stock_apis=moomoo,yfinance`
  chain) degraded those symbols to "Quote not found / possibly delisted" when
  moomoo couldn't serve them. `normalize_symbol` now converts a dotted
  single-letter US share-class suffix (`.A`/`.B`/`.C`/`.D`/`.K`...) to the
  Yahoo hyphen form, while leaving the `.L` London exchange and all multi-letter
  exchange suffixes (`.SA` Brazil, `.TO`, `.AX`, `.HK`, `.NS`, `.BO`, ...) untouched.
  Because moomoo's `_moomoo_code` doesn't use `normalize_symbol`, moomoo still
  receives the raw dotted form it understands (its own origin format), and the
  yfinance-facing paths hyphenate locally - so both vendors resolve. Also fixes
  manually-typed `BRK.B`/`BF.B` and the graph's `_fetch_cached_history` for
  dotted US share classes.
  Tests: `test_symbol_utils` (share-class dot->hyphen, idempotent hyphen,
  London/multi-letter exchange suffixes kept, plain/US futures unchanged).
  Verified live: `get_stock_data` now returns rows for MOG.A/PBR.A/MOG.B
  through the default chain (was empty). See docs/api_reference §5 symbol table.

- **Installed-CLI import bug: analyst tools could not find `scripts/`** -
  the agent analysis tools imported the vendor-output -> canonical parsing
  helpers from `scripts.value_screener`, but the installed `tradingagents` CLI
  wheel ships only `tradingagents*` and `cli*` (no `scripts/` on `sys.path`),
  so every DCF / fcf-yield / z-score / ratios / earnings-quality call degraded
  to `No module named 'scripts.value_screener'` (DCF) or a bare
  "unavailable ... from the vendor chain". The parsing layer moved to
  `tradingagents/dataflows/statement_parsing.py` (pure parsers + canonical
  aliases + `fetch_ticker`/`screen_ticker`), `scripts/value_screener.py`
  re-exports the same names (backend CLI + tests unchanged), and all 14 tool
  import sites now load from the package module. In a real NVDA run the three
  symptoms became: DCF returns a fair value (WACC from Beta, shares from
  market cap/close), fcf-yield returns a computed yield band, z-score compute
  from 4 real moomoo periods.
- **DCF tool: moomoo-markdown cashflow support** - `_dcf_fcf_series` only
  parsed yfinance-style CSV rows, so with moomoo (the default first vendor)
  serving `get_cashflow` the DCF degraded to "no usable free cash flow"
  series. It now parses moomoo per-period markdown tables too (Free Cash Flow
  row, else OCF - capex, positive-only, chronological), falling back to the
  CSV parser.
- **DCF market-cap / beta / shares resolution** - `get_dcf_valuation` now
  resolves the financial background with the screener-grade `fetch_ticker`
  (fundamentals + balance sheet + income + finnhub gap-fill) instead of a
  single raw `get_fundamentals` call, so market cap / shares resolve even
  when moomoo's statements have no "Market Cap" row; new canonical aliases
  `beta` and `shares` (shares outstanding / diluted / weighted-average) mean
  provider betas are no longer silently dropped to 1.0.
  Tests: `tests/test_statement_parsing.py` (new; imports + parsers + aliases
  + scripts re-export parity), moomoo-markdown DCF case in
  `test_analysis_tools`, hermetic-router updates across the screener/growth/
  scan/v2-v5/alpaca suites (patch `statement_parsing.route_to_vendor`
  alongside `scripts.value_screener`). Full suite 1250 passed / 2 skipped;
  ruff clean.

- **Blank-symbol yfinance hardening** - a whitespace/empty ticker reaching a
  yfinance entry point (e.g. a malformed LLM tool call during
  `batch.py --symbols ...`) used to canonicalize through `normalize_symbol`
  unchanged (`' '` stayed `' '`), hit `yf.Ticker(' ')`, and leak
  `TypeError: 'NoneType' object does not support item assignment` plus noisy
  yfinance HTTP-404/400 ERROR logs. `normalize_symbol` now canonicalizes
  blank/whitespace to `""`, and a new `require_symbol` helper raises the
  typed `NoMarketDataError` (`detail="blank/empty ticker symbol"`) at every
  yfinance entry point (`y_finance` statements/stock/insider,
  `stockstats_utils.load_ohlcv`, `yfinance_options`, `yfinance_short_interest`,
  `yfinance_news`) plus the graph's `_fetch_cached_history`. The router now
  returns one clean `NO_DATA_AVAILABLE: ... blank ticker ...` sentinel the
  agents can report honestly instead of a raw TypeError. Tests:
  `test_symbol_utils` (blank canonicalization + `require_symbol` raises),
  `test_vendor_routing` (blank -> sentinel across the chain).

### Added

- **Value Dip Step-1/Step-2 gap strategies** - five more deterministic
  calculators in `tradingagents/strategies/value_dip.py` close the original
  doc's gaps (`Strategies/Value_Dip_swing.md`):
  - **balance_sheet_health** - D/E < 1.0 OR current ratio > 1.5 (§1 gate),
  - **profitability_quality** - positive FCF AND ROE > 15% (§1 gate),
  - **Step-2 technical ladder** - `macd_divergence` (Daily RSI-14 / MACD-
    histogram bullish divergence or higher-low), `volume_dry_up` (VDU near
    support), `trigger_candle` (RVOL >= 1.3x + close above prior high /
    engulfing), `higher_low_structure`, composed by `vdu_entry_setup`,
  - **support_structure** - multi-month consolidation base low / 200-day SMA
    proximity (200+ closes),
  - **decline_driver_check** - the negative-force screen (clean / caution /
    structural) proxying moat/regulatory red flags with measurable signals
    (trap-HIGH, Sloan accruals > 6%, negative 12-1m momentum, non-positive
    FCF/ROE, severe EPS decline) - a `structural` verdict rejects the dip.
  Exposed as five new analyst `@tool`s: `get_macd_divergence` /
  `get_vdu_entry_setup` / `get_support_structure` (market), `get_balance_sheet_
  health` / `get_decline_driver_check` (fundamentals). `value_dip_setup` and
  the `--scan value-dip` screener now gate on balance-sheet + profitability
  when measured (unknown rows ignored, repo convention). Hermetic tests:
  `test_strategies_value_dip` (new gap cases) + `test_analysis_tools` (5
  tool cases).

- **Tranche risk fold for the risk governor** - the Value Dip + Swing tranche
  plan is now a *control* computation, not just a planning one:
  `strategies/value_dip.py::tranche_risk_read` derives the worst-case measures
  from the measured close (P1) + config-frozen weights / stop multiple / risk
  budget / account (never the LLM), and the governor enforces:
  - **peak-deployed-at-scale-in** (sum of per-tranche capital at full scale-in,
    typically > risk budget because capital is added near the lows) against the
    per-trade cap - the missing check neither the standalone tool nor the
    single-entry governor performed;
  - **capital-at-risk** (sum of per-tranche losses at the hard stop, == the
    risk budget by construction) via `govern()`'s new
    `capital_at_risk_pct`/`risk_cap_pct` check;
  - `build_position_contract` accepts an `entry_price` hook (the weighted
    tranche entry) so the G1 dollar stop/risk matches the tranche execution;
  - the report's `Risk Gate (computed)` block shows `Tranche peak-deployed` /
    `Tranche capital-at-risk` (+ cap-ok) when the fold ran.
  Config: `enable_tranche_risk` (default False), `tranche_weights`,
  `tranche_stop_mult`, `tranche_risk_pct`, `tranche_account` +
  `TRADINGAGENTS_*` env overrides. Tests: `test_strategies_risk_governor` (5),
  `test_strategies_contract` (2), `test_strategies_value_dip` (graph wiring,
  4 + pure 5), `test_reporting` (1).

- **Value Dip + Swing hybrid** - new `tradingagents/strategies/value_dip.py`
  implements the missing calculations from `Strategies/Value_Dip_swing.md` +
  `Value_Dip_swing_Continue.md`: Bollinger %b, historical valuation Z-score
  (vs own trailing P/E / EV/EBITDA / P/FCF), FCF yield, breakeven win rate /
  per-trade expectancy, the 3-tranche scale-in plan (P1/P2/P3 at 1.0/2.0 ATR,
  weighted avg entry, composite stop P3-1.5ATR, capital-at-risk check, 1.8R /
  3.0R targets + blended R:R), and the hybrid allocation matrix
  (`value_dip_setup`). Exposed as six analyst `@tool`s
  (`get_bollinger_pct_b` / `get_tranche_plan` / `get_trade_expectancy` on the
  market node; `get_fcf_yield` / `get_valuation_z_score` / `get_value_dip_setup`
  on the fundamentals node) and as a new `--scan value-dip` screener mode
  (`VDip` / `FCFy` / `RSI` / `%b` / `Stp%` columns). Config: `enable_value_dip`
  (+ `TRADINGAGENTS_ENABLE_VALUE_DIP`). Hermetic tests:
  `tests/test_strategies_value_dip.py` + `tests/test_analysis_tools.py`
  (value-dip cases).

- **Risk basket cash-remainder semantics** - `book_risk.portfolio_cvar` now
  treats a weight sum `< 1.0` as "weights + implicit zero-return cash": the raw
  weights are used (not renormalized), so the mixed daily series is scaled by
  the invested fraction and the portfolio CVaR is diluted by the cash sleeve.
  Weights summing `> 1.0` are still clamped to a valid portfolio. This is what
  makes "include cash as overall portfolio" (e.g. `risk_basket_weights` summing
  to ~0.68 with the rest in SPAXX/cash) actually lower the gate's tail budget.
  Tests: `test_strategies_book_risk` (2: sub-unity dilution + over-allocated
  clamp).

- **Risk Gate renders both CVaRs (analyzed-name + book)** - when a risk basket
  is configured, the report's `Risk Gate (computed)` (and compact verdict mode)
  now shows `Analyzed-name CVaR` (the analyzed ticker's own daily tail) next to
  `Portfolio (book) CVaR — this fed the gate` (the weighted-basket CVaR that is
  actually compared to the budget). The same comparison is computed-injected
  into the Portfolio Manager prompt as `**Computed daily-tail CVaR**`, so the PM
  grounds tail-risk/sizing language in these numbers (no `risk_context` on the
  state → the PM line is omitted, keeping old prompts unchanged). The graph
  writes `final_state["risk_context"] = {single_cvar, book_cvar}` when the
  governor runs. Tests: `test_reporting` (2: both-CVaR block + no-basket
  single-only), `test_structured_agent_prompts` (2: PM prompt injects both,
  omits when absent).

- **True portfolio CVaR for the risk governor (R2)** - the governor's daily-era
  tail budget now uses the *weighted basket's* historical CVaR when configured:
  new config keys `risk_basket_tickers` (list) + `risk_basket_weights` (dict,
  optional) + `TRADINGAGENTS_RISK_BASKET_TICKERS` / `TRADINGAGENTS_RISK_BASKET_WEIGHTS`
  env overrides. `book_risk.portfolio_cvar()` mixes each name's daily log-return
  series (aligned by index, weights normalized) and takes the historical CVaR of
  the weighted book, replacing the single analyzed name's series. Falls back to
  the single-name behavior when the basket is unconfigured or unresolvable (`>2`
  names with `>=5` aligned returns). Env coercion now handles list/dict values
  (comma-split / `k=v` pairs / JSON). Tests: `test_strategies_book_risk` (3),
  `test_env_overrides` (4), `test_strategies_catalyst` (1).

- **Session-discipline & earnings-quality analyst tools** - two more
deterministic strategies exposed as `@tool`s so the analysts cite computed
numbers instead of guessing: `get_session_discipline` (market node; wraps
`momentum.session_flags` + `psych_level` + `past_optimal_window` into an
intraday walk-away read: giveback, max-daily-loss, past the 10:00 ET optimal
window) and `get_earnings_quality` (fundamentals node; wraps
`normalized.accruals_ratio` + `trap_verdict`, surfacing the Sloan accruals
ratio - which `scripts/value_screener.screen_ticker`'s own trap call drops - as
an evidence trigger). Both bound in `_create_tool_nodes` + their analyst's
tool list/prompt, re-exported from `agent_utils`, and hermetic-tested in
  `tests/test_analysis_tools.py` (6 cases). Docs: `api_reference.md` §6.1/6.4
(tool list + table rows), README, CHANGELOG.

- **Docs backfill (missing env keys)** - documented the two `TRADINGAGENTS_*`
  env overrides (`ENABLE_MASSIVE_FLAT`, `MASSIVE_FLAT_DIR`) that were in code
  but absent from `api_reference.md` §1.1's env→config table; synced
  `.env.example` for `TRADINGAGENTS_MASSIVE_API_KEY` and the runtime toggles
  `TRADINGAGENTS_DISABLE_REDDIT` / `TRADINGAGENTS_MOMENTUM_OFFLINE` /
  `TRADINGAGENTS_MOMENTUM_NO_INTRADAY`.

- **Per-test timers (pytest-timeout)** - every test now carries a deadline so
  a hung vendor/network call can never block the whole session indefinitely:
  global 180s per-test default (thread method) + 30-minute session cap in
  `[tool.pytest.ini_options]`, and a 600s module-level `pytestmark` override
  for the modules that legitimately run live vendor calls end-to-end
  (`test_value_screener`, `test_scan_strategies`, `test_growth_screens`,
  `test_structured_agents`; 12-62s/test measured). `pytest-timeout>=2.4` added
  to the `[dev]` extra. Docs: `docs/developer/10-tests-layout.md`.

- **Credit-stress read (FRED ICE BofA OAS)** - `strategies/credit_spread.py`
  (`credit_stress_level`) plus a `get_credit_spread_read(date)` tool bound to
  the market analyst: pulls the three ICE BofA US high-yield option-adjusted
  spreads from FRED (`hy_oas`=BAMLH0A0HYM2, `ccc_oas`=BAMLH0A3HYC,
  `bb_oas`=BAMLH0A1HYBB, new aliases in `dataflows/fred.py::MACRO_SERIES`)
  and flattens them into a deterministic credit-cycle band (low/moderate/
  high/severe) + a 0..1 de-risk scale. Thresholds follow the credit-cycle
  table: HY <3% low / 3.5-4.5% moderate / >5.5% severe; CCC <8% low /
  10-12% moderate / >15% severe. The CCC spread is the leading risk-off
  sentinel. Degrades to an explicit 'unavailable' when FRED_API_KEY is unset
  (no-fabrication). Tests: `tests/test_strategies_credit_spread.py` (7),
  `tests/test_fred.py` (1), `tests/test_analysis_tools.py` (3).

- **Second decision-tool batch (sector/quality/safety/composite/tail)** -
  five more deterministic `strategies/*` functions exposed as analyst
  `@tool`s — `get_sector_rank` (11-SPDR 1m/3m momentum ranking + the
  ticker's sector standing; market node), `get_strategy_quality` (net CAGR,
  annualized vol, Sharpe, max drawdown over the price-derived or provided
  return series; market), `get_margin_of_safety` ((intrinsic - price)/
  intrinsic band, wide/modest/negative; fundamentals), `get_composite_rank`
  (cross-sectional value+momentum composite percentile vs industry peers;
  fundamentals), `get_tail_risk` (historical VaR/CVaR tail budget + -10%
  uniform stress loss; market). Each wraps an existing deterministic
  function, is bound to the market / fundamentals tool nodes and analyst
  prompts, and is hermetic-tested in `tests/test_analysis_tools.py` (12 new
  cases). No config or topology change; all degrade to an explicit
  'unavailable' per the no-fabrication contract.

- **DCF valuation tool** - `strategies/dcf.py` (pragmatic FCF-DCF: WACC via
  CAPM, Gordon terminal value, EV-to-equity bridge) + `get_dcf_valuation`
  tool bound to the fundamentals analyst. Provider-sourced inputs: free cash
  flow (from the cashflow statement chain), 10y Treasury (risk-free), beta,
  shares/cash/debt. growth/ERP are analyst overrides; degrades to
  "unavailable" when there is no usable FCF. Based on
  `Strategies/Discounted_Cash_Flow.md`. Tests in
  `tests/test_strategies_dcf.py` (8) + `tests/test_analysis_tools.py` (2).

- **Massive no-data failover fix** - the direct Massive tool wrappers
  (`get_short_volume`, `get_market_snapshot`, `get_top_movers`,
  `get_massive_news`) now catch `NoMarketDataError` and return an explicit
  "unavailable" string instead of letting the exception abort the analyst node
  and fail the whole batch symbol. Fallback to moomoo/yfinance now happens
  inside the report instead of crashing the run. Regression tests in
  `tests/test_massive_vendor.py::MassiveFailoverTests` (8).

- **Data providers doc (`docs/developer/12-data-providers.md`)** - catalogs
  all **13 data providers** the project uses: the 8 routed vendors
  (`yfinance, fred, polymarket, alpha_vantage, finnhub, sec_edgar, moomoo,
  massive`) plus 5 direct sources (Alpaca, FMP, Reddit, StockTwits,
  float_shares), with per-category `data_vendors` chains, Massive sub-modules,
  and API-key gates.

- **Agent decision-tools (implemented)** - `docs/developer/11-agent-decision-tools.md`
  audits the strategy + dataflow surface and lands six decision-grounding
  `@tool`s the analyst LLMs now cite: `get_exit_check` (stop/target/action),
  `get_allocation` (cap-respecting book), `get_regime_components`
  (vol/trend/chop regime breakdown), `get_consensus` (rating agreement;
  also computed-injected into the PM prompt), `get_momentum_detail`
  (pillars/rvol/vwap/first-pullback), and `get_beat_miss_sizing` (event
  multiplier). Each wraps an existing deterministic `strategies/*` function,
  is bound to the market / fundamentals / news tool nodes (and the PM's
  computed-consensus logic), with hermetic tests in
  `tests/test_analysis_tools.py`. No topology change; the PM keeps its
  NO_EXTERNAL_TOOLS single-structured-call design.

- **Strategies index (`Strategies/index.md`)** - navigation map linking each
  strategy plan doc under `Strategies/` (Math, value_strategy, framework, scan,
  momentum, risk/decision-hardening, enhancement_plan, alpaca_data_analysis) to
  its implementation modules, config gates, scan modes, and consumers. Linked
  from `docs/developer/04-strategies.md` and `docs/api_reference.md` §10.

- **Developer docs set (`docs/developer/`)** - 11 focused guides covering the
  whole project for a joining developer: topology (01), graph topology + run
  (02/02-01), dataflow+vendors (03), strategies (04), agents+tools (05),
  entrypoints (06), persistence (07), development guide (08), Massive
  integration (09), tests layout (10). Linked from `docs/api_reference.md` §10.

- **Massive Flat-File validator** - `scripts/validate_massive_flat.py`
  parses a day-aggregates CSV dropped in the flat folder and reports
  per-ticker close counts, date ranges and usability (>=15 rows) via the
  screener's exact `ohlcv_for_ticker_dir` lookup, so you confirm a genuine
  Massive file (needs Stocks Starter+) before enabling the bulk import.
  Hermetic test in `tests/test_massive_flat_noi.py`.

- **Massive Flat-File screener seam + live run** - the value-screener's
  `_fetch_ohlcv` now reads a configured Massive Flat-File day-aggregates CSV
  first from a Massive day-aggregates folder (`TRADINGAGENTS_MASSIVE_FLAT_DIR`, default `data/massive_flat`) when `enable_massive_flat` is ON (default OFF) for bulk
  ATR / ATR-pct / scan bases, falling back to the per-ticker vendor chain
  otherwise (opt-in, >=15-row gate). Hermetic test in
  `tests/test_massive_flat_noi.py`. A live end-to-end `batch.py` run to AAPL
  (Underweight) validated the new Massive tools end-to-end (see
  `docs/massive_integration.md` §3e).

- **Massive corporate actions, peers & IPOs (row 5)** - `get_company_peers`
  gains a `massive` option (`get_related_companies_massive`, finnhub-format-
  compatible output); `get_dividends_massive` + `get_splits_massive` are
  combined by `get_corporate_actions_massive` registered in the
  `corporate_actions` category; dedicated `get_dividends` (fundamentals
  analyst) and `get_ipos` (news analyst, IPO reference) tools. All row-5
  endpoints are **entitled on the current tier** (probed 200) so these are
  working enrichments, not plan stubs. Tests in `tests/test_massive_vendor.py`.
  Docs: `docs/massive_integration.md` §3f.

- **Massive NOI + Flat Files (item 8)** - `massive_noi.py` is a WebSocket
  Net Order Imbalance streamer (`build_url`/`parse_frame`/`describe`/
  `stream_noi`) wired to `scripts/massive_noi_monitor.py`; `massive_flat.py`
  loads bulk Flat-File day-aggregates into per-ticker OHLCV for the
  value-screener/backtests. Both are **standalone plan-gated utilities**, not
  batch-graph `@tool`s: NOI is a live stream (Imbalances Expansion add-on),
  Flat Files are bulk S3 (Stocks Starter+). Offline tests in
  `tests/test_massive_flat_noi.py`. Docs: `docs/massive_integration.md` §3e.

- **Massive fundamentals/ratios + market snapshots (plan-aware)** - `get_ratios`
  (precomputed EV/EBITDA, EV/Sales, P/E, P/B, ROE/ROA, D/E, FCF, dividend
  yield) registered for `get_fundamentals`/`get_basic_financials` and bound to
  the fundamentals analyst; `get_market_snapshot` (consolidated day/quote) and
  `get_top_movers` bound to the market analyst; new
  `pipeline.py --universe top-movers-massive --movers-direction` universe
  source. These Massive endpoints return 403 NOT_AUTHORIZED on the free Basic
  plan, so each tool degrades with an explicit
  "upgrade at massive.com/pricing" message and activates automatically (no
  code change) once the account's plan includes them. Tests in
  `tests/test_massive_vendor.py`. Docs: `docs/massive_integration.md` §3d.

- **Massive Form-4 insider activity** - `get_form4_insider(ticker, start, end)`
  bound to the fundamentals analyst computes net open-market insider buying from
  SEC Form 4 filings via Massive (`/stocks/filings/vX/form-4`): open-market
  purchases (P) minus sales (S), excluding grant/exercise (A/M) rows. The 13-F
  endpoint is intentionally **not** wired because it has no security (`ticker`)
  filter (only `filer_cik`/`filing_date`) — a per-ticker aggregate would be
  misleading; moomoo `get_institution_holdings` remains the per-ticker
  institutional signal. Tests in `tests/test_massive_vendor.py`. Docs:
  `docs/massive_integration.md` §3c.

- **Massive short interest / short volume** - `get_short_interest_massive`
  registers `massive` in the existing `short_interest` category (FINRA
  two-week settlement: shares short, days-to-cover, avg daily volume, sorted
  newest-first), so the existing `get_short_interest` tool routes to it when
  configured. A dedicated `get_short_volume(ticker, start, end)` tool (daily
  short-sale volume ratio) is bound to the market analyst. Both degrade via
  the error taxonomy (`NoMarketDataError` on empty). Tests in
  `tests/test_massive_vendor.py`. Docs: `docs/massive_integration.md` §3b.

- **Massive macro economy + catalyst OpenD decoupling** - `get_macro_indicators_massive`
  registers `massive` as a `macro_data` vendor (treasury-yields / inflation /
  inflation-expectations / labor-market with FRED-compatible aliases) so macro
  commentary no longer depends on a FRED key or the OpenD gateway. A
  deterministic `fetch_macro_backdrop` (yield-curve inversion / elevated 10y
  breakeven) feeds the B1 catalyst overlay so it keeps de-risking near macro
  stress even when the moomoo event calendar is unavailable; `fetch_catalyst_data`
  now degrades per-section instead of returning `None` on moomoo failure.
  New snapshot verdict `macro-backdrop`; applied only when no forward event
  calendar is present (no double-count with a live moomoo read). Tests in
  `tests/test_massive_vendor.py` + `tests/test_strategies_catalyst.py`. Docs:
  `docs/massive_integration.md` §2/§3a.

- **Massive.com data vendor (news sentiment)** - new `dataflows/massive.py`
  with `get_news_massive` returning per-article structured sentiment
  (positive/negative/neutral + reasoning) from `/v2/reference/news`,
  ticker-filtered so a peer ticker's sentiment never leaks in. Registered as
  a `massive` vendor in the `get_news` chain and `VENDOR_LIST`; a dedicated
  `get_massive_news` LangChain tool is bound to the news/social tool nodes
  and the news analyst prompt. New config key `massive_api_key`
  (`MASSIVE_API_KEY` / `TRADINGAGENTS_MASSIVE_API_KEY`), hermetic offline
  tests in `tests/test_massive_vendor.py`, and `docs/massive_integration.md`.
  US-centric additive vendor (supplements, not replaces, moomoo/yfinance);
  plan-dependent recency/entitlements, FMV/Greeks Business-only (unavailable,
  never invented).

### Fixed

- **README fork-additions highlight (purple border, per-section)** - the fork
  News changelog and EACH fork-additions section (Batch runner, Extended data
  sources, Moomoo OpenAPI vendor, Value watchlist screener, Decision quality,
  Report format, Operational hardening, Decision hardening) is wrapped in its
  own HTML table with a **purple left border** (GitHub's closest rendered
  equivalent to a diff-style added-line mark, since a rendered README cannot
  show the purple bar of the diff view). Each `##` section keeps a real
  heading; upstream sections stay unmarked. The `[!IMPORTANT]` callout stays
  as a GitHub alert.
- **Screener moomoo period-order + prior-period bug (M column always n/a)** -
  moomoo statement payloads list periods newest-first but `_parse_markdown_financials`
  used a last-write-wins dict, so the canonical "latest" was the OLDEST period
  and prior-period values were never captured. Consequently the Beneish
  M-Score - which needs current AND prior - was always `n/a`, and every metric
  (EY, EV/EBIT, F, Z, EpsYoY, ROE) was computed on stale fiscal data. Fixes:
  - `_markdown_period_tables` parses each `### <period>` table and sorts by
    period year (newest first); `_markdown_canonical` scans ALL tables (a
    `get_fundamentals` payload concatenates income+balance+cashflow) and emits
    `{"current", "prior"}` dicts for two-period keys.
  - `_match_row` skips moomoo `-`-prefixed sub-item / contra lines
    (`-Accounts Receivable`, `-Accumulated Depreciation`).
  - depreciation aliases drop the loose `d&a` (normalized to `d a`, it
    substring-matched "Selling and Admin Expenses") and add `depreciation &
    depletion`; `net_receivables` prefers the aggregate `receivables` row.
  - `_latest()` unwraps the dict form at every flat read site (screen_ticker,
    _usd_consistent, fetch_ticker, mover-meta injection).
  - Result: M-Score computes (e.g. MT -2.29, WMT -2.72), F/Z/EY/ROE reflect
    the newest period; NetNet staying `no` on large caps is expected (a
    negative-current-liabilities - current-assets threshold).
- **Regression tests** - tests/test_moomoo_period_fix.py (newest-period,
  prior dicts, dash-skip, d&a alias, M-computes, concatenated-fundamentals).

### Added

- **Finnhub free-tier integration (key: TRADINGAGENTS_FINNHUB_API_KEY)** -
  live-probed the free tier and wired the endpoints that actually work:
  - `get_basic_financials_finnhub` - company_basic_financials metrics
    (epsGrowthQuarterlyYoy / revenueGrowthTTMYoy / roeTTM -> the screener's
    --min-eps-yoy / --min-rev-yoy / --min-roe gates via new canonical aliases
    + a text-router fix so header-prefixed blobs parse); also registered as a
    `get_fundamentals` vendor option
  - `get_insider_activity_finnhub` - stock_insider_sentiment (12m net change
    + mspr + trend, computed)
  - `get_company_peers_finnhub` - comparable peer group
  - `get_profile_finnhub` - profile2 sector (finnhubIndustry -> sector) as
    the second-tier `--sector-rank` fallback (FMP -> Finnhub -> yfinance)
  - bound the three as analyst tools (get_basic_financials / get_insider_activity
    / get_company_peers) to the Fundamentals analyst; all key-gated / guarded
    / no-fabrication
  - docs: api_reference 6.5 table + vendor list
- **Computed-analysis tools - follow-up batch (6 more)** - `analysis_tools.py`
  grows `get_regime_read` (overlays.build_strategy_overlays: regime label +
  position scale + momentum/52w), `get_volatility_contraction` (swing.vcp_setup),
  `get_orderflow_read` (orderflow.summarize on the guarded live fetch),
  `get_analyst_verdict` (screener canonical pipeline -> EY/EV/EBIT/F/M/Z/
  trap-risk/ROE/YoY), `get_earnings_surprise` (standardized surprise % +
  side), and `get_portfolio_weights` (value-proportional + capped weights).
  Bound to the market analyst (regime/VCP/orderflow) and the fundamentals
  analyst (verdict/surprise/portfolio); same no-fabrication contract.
- **Computed-analysis tools for the analyst LLMs** - `agents/utils/analysis_tools.py`
  wraps the deterministic strategy calculators as LangChain tools so the
  agents reason over computed numbers instead of re-deriving (or inventing)
  them from raw vendor output: `get_swing_set` (trend stack + 1-ATR stop +
  2R/3R targets + VCP), `get_relative_strength` (RS line vs benchmark),
  `get_earnings_event_read` (surprise + PEAD setup), `get_catalyst_scale`
  (0..1 B1 scale + verdict), `get_position_sizing` (Kelly + risk budget) and
  `get_risk_gate` (PASS/WARN/REJECT). Bound to the market + news analyst tool
  loops (prompt + graph ToolNodes); all return exact numbers or an explicit
  'unavailable' (no-fabrication contract). Source:
  `tradingagents/strategies/{swing,relative_strength,events,catalyst,size,risk_governor}.py`.
- **Framework Phase-1 screens** - optional screener gates from
  `Strategies/framework.md`: `--min-eps-yoy` / `--min-rev-yoy` (moomoo
  statement YoY columns now parsed - also fixes a latent defect where moomoo
  markdown payloads with `##` headers were never routed to the markdown
  parser), `--min-roe` (net income / total equity via new `total_equity`
  canonical alias), `--max-mcap` ($2B-100B focus), `--sector-rank`
  (`strategies/sector_rank.py`: 11 SPDR ETF groups ranked by 1m/3m momentum,
  ticker sector via FMP profile (key-gated) with guarded
  `dataflows/yfinance_sector.py` fallback),
  `--revision` (net analyst upgrades in 60d as the forward-revisions proxy)
  and `--inst-accum` (two-quarter institutional %-of-float change). New
  EpsYoY/RevYoY/ROE, Sec/Rank, RevUp and Inst table columns; gates apply only
  to measured values (missing data renders n/a).
- **Volatility Contraction Pattern scan (`--scan vcp`)** -
  `strategies/swing.py::vcp_setup` (strict pivot troughs, last-3 pullback depths vs
  the base high must contract 15%->8%->3%-style, deepest pullback within 30%
  of the base, fading volume across troughs; absent volume never fails);
  wired as a screener mode with VCP/Brk columns; `swing_report` carries the
  VCP block as an additional signal. Docs in `Strategies/scan.md`.
- **Techno-fundamental swing scan (`--scan swing`)** - `strategies/swing.py`
  (trend architecture: 20-EMA stacked over rising 50/200-SMA, RSI 45-70 band
  with 40-50 reset, pullback-into-EMA20 on fading volume, 1-ATR swing-low
  stop, 2R/3R two-tier targets, 50% T1 scale-out + 20-EMA trail) and
  `strategies/relative_strength.py` (RS line vs `benchmark_ticker`, 63-day
  established-uptrend slope, new-high/near-high position, negative-divergence
  detection); wired as a new screener mode with ScanC/RS/Stp/T2 columns.
  Source: `Strategies/framework.md`; mode docs in `Strategies/scan.md`.
- **PEAD post-earnings entry helpers** - `events.py` gains
  `gap_up_qualifies` (2.5x-volume gap gate), `consolidation_and_break`
  (opening-range tightening + break trigger) and `post_earnings_play`.
- **Catalyst hard block (G5)** - `catalyst_hard_block_days` config (default
  0 = off; `TRADINGAGENTS_CATALYST_HARD_BLOCK_DAYS` env override): a
  scheduled earnings print inside the window makes the risk governor REJECT
  new risk outright (framework Phase-4 "never initiate" rule) while the
  scale-fold de-risk still applies.
- **Strategy docs** - `Strategies/scan.md` filled (was an empty placeholder)
  with all scan modes including swing.

### Added

- **Momentum day-trading signals (analysis-only)** - `strategies/momentum.py`
  (5-pillar pre-filter, RVOL/EMA9/VWAP, first-pullback pattern with R/R,
  session risk flags); screener `--scan momentum` (+Pills/Pull/RR
  columns); Market Analyst `get_momentum_scan` tool in the graph.
  Source: `Strategies/momentum_day_trading.md`.
- **Alpaca wired into the analyst graph (analysis-only)** -
  `get_market_snapshot_alpaca` tool on the Market Analyst ToolNode;
  `resolve_instrument_context` appends a one-line live 1m snapshot for
  every analyst (one call per run); enabled via `enable_alpaca`.
  Rate-limit aware for the free tier: global pacing (~171 req/min under
  the 200/min cap), batch symbol queries, Retry-After/X-RateLimit-Reset
  backoff on 429.
- **`--intraday` watchlist columns** - with Alpaca keys set, `--intraday`
  appends live **L1Px / VWAP1m / 1mVol** per symbol from the snapshots
  endpoint (latest trade price, 1m-bar VWAP & volume); live-verified
  against Alpaca (AAPL 292.04 / VWAP 309.66 - 2026-08-18).
- **Alpaca smk w/ live keys** - verified against `data.alpaca.markets/v2`
  (bars/batch/snapshots) and `paper-api.alpaca.markets/v2` (calendar/clock);
  free IEX tier limits daily history to the latest bar - screener OHLCV
  fallback now requires >=15 daily bars before use.
- **Alpaca market data (analysis-only)** - `dataflows/alpaca.py` +
  `alpaca_common.py`: signed daily/1m bars (OHLC+vwap), batch bars,
  latest snapshots, trading calendar, market clock; screener falls back
  to Alpaca bars when the vendor CSV is empty (enable_alpaca) and adds a
  market-hours note. No order/position/account endpoints are implemented.
  Plan: `Strategies/alpaca_data_analysis.md`.
- **FMP vendor (optional)** - `dataflows/fmp.py` + `fmp_common.py`: 5+ year
  income/balance/cashflow history, enterprise-values, key metrics TTM,
  earnings surprises, historical OHLCV; `normalized_score` fills the
  V1/V2 gaps (5y median-margin EBIT, EV/NEBIT, 5y PE percentile). Screener
  shows NEV/EBIT + PE5Y columns when `fmp_api_key` is set; register via
  `TRADINGAGENTS_FMP_API_KEY` in `.env`.
- **`--scan` strategies (scan.md)** - trend-pullback (20/50 EMA, RSI 40-55,
  quarter >= +10%, pullback to EMA20) and breakout (>=90% of 52w high,
  above SMA20/50, RVOL >1.5 or <0.75 + Bollinger squeeze) as screener
  modes; `--scan value|trend-pullback|breakout|all` (default all: flags
  ScanA/ScanB columns), combined with the existing value gates.
- **Screener filters updated** - defaults now: market cap >= $10B,
  price >= $15, 30-day avg daily volume >= 1M shares, ATR(14) >= 2%
  of price (new `--min-avg-vol` / `--min-atr-pct` gates computed from
  vendor daily OHLCV; `--min-mcap`/`--price-min` retuned).
- **Deterministic sentiment velocity** - StockTwits counts -> signed
  computed_score (-1..1) + surprise z-score vs a rolling per-ticker
  baseline, injected into the SentimentReport as `computed_score` /
  `computed_velocity` / `sample_size` (rendered **Computed Sentiment**
  line); enabled via `.env` `TRADINGAGENTS_ENABLE_SENTIMENT=true`.
- **Risk report R1b** - the computed risk gate (verdict/snapshot/reasons)
  is injected into every report: prepended to `4_risk/*` and the Risk
  section, mirrored into `5_portfolio/decision.md`; `--risk-compact`
  (`risk_compact_report`, config/.env) replaces 3-analyst transcripts
  with a single `4_risk/verdict.md`.
- **Risk governor R0-R4** - deterministic pre-trade gate
  (`strategies/risk_governor.py`): PASS/WARN/REJECT vs a limits registry;
  book & tail risk (`book_risk.py`): VaR/CVaR, stress shocks, drawdown
  gate; escalation `risk_halt`; `risk_audit.jsonl` + `scripts/risk_report.py`.
  Enabled via .env (`TRADINGAGENTS_ENABLE_RISK_GOVERNOR=true`).
- **V2-V5 value-style wiring** - composite (value+momentum) ranking in the
  screener (`enable_composite_rank`, `--rank composite`), allocation plan
  block (`--alloc`), contract exit levels (ATR breakeven/target via
  `enable_exits`), and computed-debate-context injection
  (`enable_computed_context`). .env defaults enabled.
- **Value-style enhancements (V1-V5)** - normalized earnings (5y median
  margin), historical valuation percentiles, Sloan accruals, trap verdict
  (Trap column in the screener), hard portfolio caps, ATR exits + rebalance
  hints, and computed debate-context snippets. See
  `strategies/value_style_gap_plan.md`.
- **Decision hardening (G1-G5)** - deterministic position/stop contract
  (Kelly x vol x flow x agreement, ATR stop), confidence calibration from
  ledger buckets, computed agreement/consensus, recency-decayed sentiment
  + surprise velocity, and a walk-forward/PBO threshold gate. See
  `strategies/decision_hardening_spec.md`.
- **``$100B market-cap floor``** - `--min-mcap` now defaults to
  $100B for the moomoo rank universes (total cap; float cap <= total so the
  floor satisfies the “cap OR float cap >= $100B” rule); the day-of rank
  cap takes precedence over parsed fundamentals, and `$T` (trillion) values
  parse correctly.
- **``--universe heat-proxy`` refinement** - US-only, stocks only (ETFs/ETNs/
  funds/indices excluded), pipeline is *hot master first (gainers+losers,
  hottest first), losers second*; universe gates now enforce price >= $20 and
  0 < P/E (TTM) <= 40 (`--price-min 20`, `--pe-max 40`, defaults).
- **``--universe heat-proxy``** in the value screener: US-only alias for
  ``top-losers`` that builds the daily universe from moomoo's official intraday
  trade rank as the sanctioned stand-in for the proprietary in-app Heat List
  (composite Trade/Search/News telemetry is not exposed by any moomoo API;
  the web endpoint's signed token is undocumented). Pass the literal app Heat
  List via ``-f list.txt`` to use it directly.
- **Value watchlist screener** — `scripts/value_screener.py` builds a master
  value watchlist by screening tickers through the configured vendor chain
  (`fundamental_data`: `moomoo,yfinance` by default). It normalizes yfinance
  CSV, moomoo markdown/JSON, alpha_vantage JSON, and info text into canonical
  line items, then computes EV/EBIT (Acquirer's Multiple), Earnings Yield, EV,
  Piotroski F-Score, Beneish M-Score, Altman Z and net-net (missing rows ->
  `n/a`, never fabricated). A `--universe top-losers` mode pulls moomoo's
  intraday decliners rank (`get_top_movers_rank`) so the universe changes
daily; output merges name/change columns for picking. See
  `strategies/value_strategy.md`.
- **Quantitative score library** — `tradingagents/dataflows/quantitative_scores.py`
  implements Beneish M-Score, Altman Z-Score, Piotroski F-Score and
  EV / Earnings-Yield / Acquirer's-Multiple helpers, vendor-agnostic over a
  canonical line-item schema (offline unit-tested in
  `tests/test_quantitative_scores.py`).
- **Moomoo top movers vendor call** — `get_top_movers_moomoo()` wraps the SDK's
  intraday gainers/losers rank with the usual error taxonomy (OpenD down /
  permission / rate-limit degrade via `_check_ret`) and converts codes to
  Yahoo-style symbols (`US.AAPL` -> `AAPL`, `HK.00700` -> `00700.HK`).
  Covered by `MoomooTopMoversTests` and `tests/test_value_screener.py`.

### Fixed

- **Value screener refuses mixed currencies.** moomoo reports ADR statements
  in the underlying currency (e.g. JPY) while market cap arrives in USD, which
  produced nonsense EV (e.g. a -62T "EV" for Japan Post's ADR). The screener
  now detects the statement currency (moomoo markdown headers, yfinance
  ``Financial Currency``, alpha_vantage ``reportedCurrency``) plus an
  assets/market-cap >1000x scale heuristic, and gates the USD-only metrics
  (EV / EY / Acquirer's Multiple / Altman Z / net-net) to ``n/a`` when
  currencies would be mixed. A cash > total-assets guard also drops wrong-row
  matches.
- **Moomoo top-movers ``change_ratio`` normalized to a fraction** - the SDK
  returns a ratio in some market sessions and a percent in others for the same
  symbol; the vendor now divides by 100 when \|\|>1.5 so ``DayChg`` formatting
  is always correct.
- **Moomoo fundamentals match the tool signatures.** The moomoo vendor's
  `get_fundamentals`/`get_balance_sheet`/`get_cashflow`/`get_income_statement`
  accepted only the symbol, so the interactive CLI's `curr_date` (and `freq`
  for statements) arguments raised `TypeError` and every call fell back to
  yfinance/alpha_vantage. The vendor now accepts the same arguments as the
  other fundamentals vendors: `freq` selects the annual vs. quarterly report
  type on the moomoo SDK, and `curr_date` filters out statements published
  after the trading day (look-ahead guard, mirroring alpha_vantage).
- **yfinance options chain no longer crashes on `NaN`.** Yahoo chains carry
  `float('nan')` for open interest/volume on many rows; `int(nan)` raised
  `ValueError` and the router logged `Vendor 'yfinance' failed for
  get_options_chain`. The vendor now sums only finite values (missing counts
  contribute 0) and skips non-finite implied-volatility values in the mean,
  so the call degrades to zeroed totals instead of aborting.

### Added
- **Quant-formula calculations** (`Strategies/quants.md` + `quant2.md`
  implementation) - pure deterministic calculators mapped to the repo's gaps:
  - **Volatility estimators**: `strategies/volatility_models.py`
    (Parkinson high-low, Garman-Klass OHLC, EWMA RiskMetrics 0.94, GARCH(1,1)
    pure-NumPy MLE with long-run vol); `volatility_estimator` config
    (close default | ewma | garch) feeds the overlay sizing; tools
    `get_volatility_estimators` + `get_garch_volatility` (market).
  - **Tail decomposition**: `book_risk.incremental_var` + `component_var`
    (normal-covariance MCR, components sum to the book's historical VaR);
    `get_tail_decomposition` market tool.
  - **Mean-reversion quality**: `strategies/mean_reversion.py` (demeaned
    AR(1)/OU half-life with an OLS t-test gate so a random walk is never
    mislabeled; `mean_reversion_verdict`); `get_mean_reversion_quality` tool.
  - **Roll spread**: `liquidity_risk.roll_spread` (effective-spread proxy
    from daily prices), rendered in `get_liquidity_risk`.
  - **Preferred/fixed income**: `strategies/fixed_income.py`
    (indicated_yield, preferred_ytm with honesty for perpetuals,
    macaulay/modified duration, dv01, convexity); `capital_income_screener
    --fi / --fi-horizon` adds YTM/DMod/DV01 columns.
  - **Credit hazard**: `credit_spread.hazard_from_spread` +
    `default_probability` (s ~= lam(1-RR), RR=0.40), rendered in
    `get_credit_spread_read`.
  - **Variance + TCA**: `options_math.variance_swap_strike` (fair variance
    strike from OTM grid) + `get_variance_premium`; `evaluate.implementation_shortfall`
    (decision->arrival->fill) wired into `strategy_quality_report` execution
    block (avg_is_bp).
  Tests: `test_strategies_volatility_models` (8), `test_strategies_tail_decomposition`
  (5), `test_strategies_mean_reversion` (8), `test_strategies_fixed_income`
  (6), `test_quant_phase5` (6). trading_web Value Tools 33->36 tools.

### Added
- **News-sentiment factor** (`News_Sentiment.md` implementation) - the EODHD
  `/sentiments` feed (live-verified, EOD plan) becomes the primary daily
  news-sentiment series:
  - **Feed**: `dataflows/eodhd.get_news_sentiment_eodhd` (daily `normalized`
    centered to -1..1 + 7d SMA + latest innovation + article count),
    `dataflows/alpha_vantage_news.get_news_sentiment_alpha_vantage`
    (parses `ticker_sentiment[]` from the existing `NEWS_SENTIMENT` call,
    post-16:00 ET next-day bucket) and `dataflows/gdelt.get_news_sentiment_gdelt`
    (native tone) — new optional `news_sentiment` category chain
    `eodhd,alpha_vantage,gdelt`.
  - **Analytics**: `strategies/sentiment.py` (`aggregate_daily_sentiment`,
    `daily_sentiment_sma`) + new `strategies/sentiment_research.py`
    (lead/lag, multi-horizon predictive OLS with pure-NumPy Newey-West HAC,
    sector-neutral z + size residualization, rolling IC / IC-IR, IC term
    structure / half-life, quintile long/short backtest).
  - **Tools**: `get_news_sentiment` (routed), `get_news_sentiment_series`,
    `get_sentiment_lead_lag` bound to the market + news analyst ToolNodes and
    prompts.
  - **Eval**: `scripts/sentiment_factor_eval.py` (cross-sectional panel, IC /
    decay / long-short report) + `scripts/value_screener.py --sentiment`
    (`Sent7` / `SentZ` columns).
  - **Overlay (opt-in, OFF)**: `enable_sentiment_factor` folds
    `position_scale * (1 ± max_scale)` only when the name's measured rank IC ≥
    `sentiment_factor_min_ic`, else neutral 1.0 (never blocks).
  - trading_web Value Tools + README (33 tools).
  Tests: `test_strategies_sentiment` (+6), `test_strategies_sentiment_research`
  (12), `test_news_sentiment_series` (13), `test_strategies_overlays` (+5).

### Docs
- **Research-plan + reference sync** - `Strategies/value_dip_swing_prepost_research_plan.md`
  status flipped to implemented; every Part A/B gap marked closed with the
  module that shipped it; the stale "Not doing: ROC/TRIX/Force/A-D" note
  corrected (they shipped in `strategies/extended_indicators.py`); phases
  marked DONE; open questions resolved. `docs/api_reference.md` §6.1 lists
  `get_extended_indicators` / `get_candlestick_patterns` and §6.2's
  `VENDOR_LIST` updated (17 vendors). `docs/developer/12-data-providers.md`
  re-tallied to 22 providers/17 routed vendors, adds the cboe /
  federal_reserve / gdelt / benzinga / newsapi rows, fixes the `news_data`
  chain (…,stockdata,newsapi) and the API-key table.
- **trading_web Value Tools surface** - `run_value_tools` now imports and
  registers `get_extended_indicators` / `get_candlestick_patterns`
  (analysis_tools) + `get_gdelt_sentiment` (news_data_tools) with the matching
  App.jsx options ("Extended indicators", "Candlestick pattern scan", "GDELT
  news-tone sentiment"); README sync table updated to 31 tools; hermetic web
  test added (trading_web commit `db3217d`).

## [0.3.1] — 2026-07-05

Correctness and stability patch: data look-ahead, graph-router crash-safety,
checkpoint identity, crypto sentiment sources, and configurable resilience.

### Fixed

- **Alpha Vantage look-ahead filter now runs.** The fundamentals payload is a
  JSON string, so the dict-only guard skipped filtering and future-dated reports
  leaked into historical runs; parse before filtering. (#1115, @zachthebird)
- **News analyst prompt matches the tool.** The prompt advertised
  `get_news(query, ...)` but the tool takes a ticker; aligned to stop
  hallucinated free-text query calls. (#1116, @shcheuk)
- **Shared debate/risk routers can't crash mid-run.** Both routers return more
  targets than any one edge mapped; every edge now shares the complete path map,
  so a fall-through under prompt/i18n/refactor drift stays routable.
  (#1088, @Fr3ya, @sa7an7, @Sushanth012)
- **Checkpoint resume respects graph shape.** The thread id folds in selected
  analysts, debate/risk depth, and asset mode, so a resume under different
  choices no longer continues the wrong graph. (#1089, @bossjoker1, @Ghraven)
- **Crypto sentiment sources resolve.** StockTwits lists crypto as `<BASE>.X`
  (Yahoo's `BTC-USD` 404s) and Reddit needs the base symbol to match; the social
  path now maps crypto correctly for both. (#1113, @suremadoreai)

### Added

- **Configurable LLM retry budget.** `llm_max_retries` /
  `TRADINGAGENTS_LLM_MAX_RETRIES` is forwarded to every provider, so a transient
  429 burst no longer aborts a run. (#1091, @yanggaome)
- **Bedrock API-key auth.** `AWS_BEARER_TOKEN_BEDROCK` authenticates Amazon
  Bedrock without AWS access keys and takes precedence over an ambient
  `AWS_PROFILE`. (#1103, @praxstack)
- **Latest Claude models.** Added Claude Sonnet 5 (`claude-sonnet-5`) and
  Fable 5 (`claude-fable-5`); effort control now covers the Claude 5 line.

## [0.3.0] — 2026-06-22

Stabilization and extensibility release: a CI gate, a unified verified
data-access contract, a provider and data-vendor registry, and a maintenance
sweep that hardened config precedence, the model catalog, data resilience, and
structured output.

### Added

- **CI gate.** GitHub Actions runs the pytest suite across Python 3.10-3.13,
  strict `ruff`, and a clean-install smoke that imports the package and CLI to
  catch undeclared dependencies. (#994, #197)
- **Provider registry.** OpenAI-compatible providers register as a single spec,
  and a generic `openai_compatible` endpoint covers vLLM, LM Studio, and relays.
  Adds NVIDIA NIM, Kimi, Groq, Mistral, and a native Amazon Bedrock client.
- **Macro and prediction-market vendors.** FRED macro indicators and Polymarket
  event probabilities, surfaced to the news and macro analysts.
- **Programmatic report output.** `TradingAgentsGraph.save_reports()` writes the
  same report tree the CLI produces, for headless and API runs. (#1037)
- **Env-configurable reasoning depth** via `TRADINGAGENTS_OPENAI_REASONING_EFFORT`,
  `TRADINGAGENTS_GOOGLE_THINKING_LEVEL`, and `TRADINGAGENTS_ANTHROPIC_EFFORT`,
  each gated to the models that accept it.

### Changed

- **Verified data-access contract.** Symbol normalization on every vendor path
  (identity, returns, CLI, news); the configured vendor list is the exact
  resolution chain with no silent fallback to unselected vendors; a typed
  `VendorError` taxonomy; look-ahead-safe news windows; stale-OHLCV rejection;
  inclusive yfinance date ranges.
- **Config precedence.** An explicit `TRADINGAGENTS_*` value or CLI flag now wins
  over interactive defaults for debate and risk round counts,
  `--checkpoint / --no-checkpoint`, and the Docker provider profile; invalid
  boolean env values fail loudly. (#975, #976, #977)
- **Current-generation model catalog.** Refreshed provider lineups; retired
  `gpt-4.1`, Claude Sonnet 4.5, and the Gemini 2.5 line.
- **Optional vendors degrade** instead of aborting a run: a failed macro or
  prediction-market lookup returns a no-data sentinel.
- **Analyst prompts lead with the current date** so tool-call date ranges anchor
  to the run date rather than the model's training cutoff. (#836)

### Fixed

- **Instrument identity.** Deterministic ticker-to-company resolution prevents
  wrong-company hallucination, and a verified market-data snapshot grounds price
  and indicator claims. (#814, #830)
- **Social and market data sources.** Reddit RSS-first with 429 backoff,
  StockTwits transport hardening, and Alpha Vantage timeout plus
  key-versus-rate-limit handling.
- **Structured output.** Local OpenAI-compatible servers no longer reject
  object-form `tool_choice`; a thinking model that returns no parsed result falls
  back to free text; null-ish strings in optional price fields coerce to `None`.
  (#1038, #1051, #1057)

### Removed

- The no-op `analyst_concurrency_limit` config knob; parallel analyst execution
  is planned for a later release. (#979)
- The unused committed `uv.lock`. (#1030)

### Contributors

Thanks to everyone who shaped this release through code, design, and reports:

[@CadeYu](https://github.com/CadeYu), [@Zavianx](https://github.com/Zavianx), [@weijianz-opc](https://github.com/weijianz-opc), [@naltun](https://github.com/naltun), [@brahmasky](https://github.com/brahmasky), [@nik2208](https://github.com/nik2208), [@thieucong98](https://github.com/thieucong98), [@Derekko-web](https://github.com/Derekko-web), [@LukiPrince](https://github.com/LukiPrince), [@Eddieargenal](https://github.com/Eddieargenal), [@Ghraven](https://github.com/Ghraven), [@ms32035](https://github.com/ms32035), [@yting27](https://github.com/yting27), [@nyxst4ck](https://github.com/nyxst4ck), [@KenCheung-AIxFinance](https://github.com/KenCheung-AIxFinance), [@yangyusheng2n](https://github.com/yangyusheng2n), [@fareloj](https://github.com/fareloj), [@haosenwang1018](https://github.com/haosenwang1018), [@octo-patch](https://github.com/octo-patch), [@seifenk](https://github.com/seifenk), [@CaoYuhaoCarl](https://github.com/CaoYuhaoCarl), [@mihailnica10](https://github.com/mihailnica10), [@Dado-hash](https://github.com/Dado-hash), [@Handsomemikezzz](https://github.com/Handsomemikezzz), [@ydhawesome](https://github.com/ydhawesome), [@macd2](https://github.com/macd2), [@AyushKar2005](https://github.com/AyushKar2005), [@wildhuman](https://github.com/wildhuman), [@robert23kim](https://github.com/robert23kim), [@bngness](https://github.com/bngness), [@tedix-rodrigo](https://github.com/tedix-rodrigo), [@malaccan](https://github.com/malaccan), [@rfalken78](https://github.com/rfalken78), [@dengli1971-droid](https://github.com/dengli1971-droid), [@proofconcept39](https://github.com/proofconcept39), [@prasta1](https://github.com/prasta1), [@liximin](https://github.com/liximin), [@jeffhuen](https://github.com/jeffhuen), [@mazar](https://github.com/mazar), [@soyangelromero](https://github.com/soyangelromero), [@CNQQC](https://github.com/CNQQC), [@dovetaill](https://github.com/dovetaill), [@fperdigon](https://github.com/fperdigon), [@gyx09212214-prog](https://github.com/gyx09212214-prog), [@RSXLX](https://github.com/RSXLX).

## [0.2.5] — 2026-05-11

### Added

- **Grounded Sentiment Analyst.** The renamed `sentiment_analyst` now reads
  real Yahoo News, StockTwits, and Reddit data before generating its report,
  replacing the prior flow that could fabricate social posts under prompt
  pressure. (#557, #607)
- **MiniMax provider** with the full M2.x catalog (M2.7 / M2.5 / M2.1 / M2
  plus highspeed variants, 204K context). Dual-region: Global
  (`MINIMAX_API_KEY`) and China (`MINIMAX_CN_API_KEY`).
- **Dual-region Qwen and GLM** with separate keys per region — international
  (`DASHSCOPE_API_KEY`, `ZHIPU_API_KEY`) and China (`DASHSCOPE_CN_API_KEY`,
  `ZHIPU_CN_API_KEY`), selectable via a secondary region prompt. (#758)
- **`TRADINGAGENTS_*` env-var configurability for `DEFAULT_CONFIG`.** Override
  `llm_provider`, deep/quick model IDs, `backend_url`, `output_language`,
  debate-round counts, checkpoint flag, and benchmark ticker via `.env` with
  type-aware coercion (string / int / bool). (#602)
- **Interactive API-key detection in the CLI.** When the selected provider's
  key is missing, the CLI prompts for it and persists the value to `.env`
  so the analysis run continues without restart.
- **Remote Ollama support.** `OLLAMA_BASE_URL` points the CLI and the
  programmatic client at a remote `ollama-serve`. The CLI surfaces the
  resolved endpoint and warns on common malformed inputs. Adds a
  `"Custom model ID"` option for models pulled via `ollama pull`. (#648, #768)
- **Configurable news-fetch parameters** in `DEFAULT_CONFIG` — per-ticker
  article limit, macro headline limit, lookback window, and macro search
  queries. (#606, #683)
- **Configurable alpha benchmark** for non-US tickers. Replaces hardcoded
  SPY with regional indices for `.NS` (^NSEI), `.T` (^N225), `.HK` (^HSI),
  `.L` (^FTSE), `.TO` (^GSPTSE), `.AX` (^AXJO), `.BO` (^BSESN); explicit
  `benchmark_ticker` override available. Eliminates FX drift dominating
  alpha for non-USD listings. (#628, #684)
- **Multi-language output covers every user-facing agent** — researchers,
  risk debators, research manager, and trader, ending the previous
  partial-localization reports. (#575)
- **Model catalog refresh.** OpenAI GPT-5.5 frontier, Anthropic Claude Opus
  4.7, Gemini 3.1 Flash-Lite GA, xAI Grok 4.20, Qwen 3.6 line. Versioned IDs
  only; auto-shifting aliases moved to the `"Custom model ID"` option.

### Changed

- **Sentiment Analyst** is now consistently named across the CLI dropdown,
  status panel, and final reports (previously the backend was renamed but
  the CLI still said "Social Analyst"). The `AnalystType.SOCIAL = "social"`
  wire value is kept for saved-config back-compat.

### Fixed

- **Structured output works on DeepSeek V4 / reasoner and MiniMax M2.x.**
  Those providers reject `tool_choice` per their tool-calling docs; the
  binding flow now skips it automatically via a capability table.
- **`pip install .` installations pick up the project `.env`** when running
  the CLI as a console script. (#747)
- **Reports save end-to-end** — streamed chunks were previously dropped from
  `complete_report.md`. (#719, #736)
- **Ticker prompt preserves exchange suffixes** (`.SH`, `.SZ`, `.SS`, `.HK`,
  `.T`, etc.) for A-share, HK, Tokyo, and other non-US flows. (#770)
- **Docker permission errors** no longer block first-run write to
  `~/.tradingagents/`. (#519, #627, #672, #771)
- **Config state no longer leaks between runs** when sub-dicts are mutated;
  `set_config` partial updates preserve sibling defaults. (#788)
- **`max_recur_limit` config actually applies** — previously read but not
  forwarded to the propagator. (#764)
- **Missing-API-key error** names the exact env var to set. (#680)
- **Quieter startup** — suppressed the noisy upstream
  `LangChainPendingDeprecationWarning` from langgraph-checkpoint; will be
  removed once that package ships its fix.

### Security

- **Ticker path-traversal validation** at every filesystem-path site (cache,
  checkpoint database, results) so a malicious ticker cannot escape its
  intended directory. (#618)

## [0.2.4] — 2026-04-25

### Added

- **Structured-output decision agents.** Research Manager, Trader, and Portfolio
  Manager now use `llm.with_structured_output(Schema)` on their primary call
  and return typed Pydantic instances. Each provider's native structured-output
  mode is used (`json_schema` for OpenAI / xAI, `response_schema` for Gemini,
  tool-use for Anthropic, function-calling for OpenAI-compatible providers).
  Render helpers preserve the existing markdown shape so memory log, CLI
  display, and saved reports keep working unchanged. (#434)
- **LangGraph checkpoint resume** — opt-in via `--checkpoint`. State is saved
  after each node so crashed or interrupted runs resume from the last
  successful step. Per-ticker SQLite databases under
  `~/.tradingagents/cache/checkpoints/`. `--clear-checkpoints` resets them. (#594)
- **Persistent decision log** replacing the per-agent BM25 memory. Decisions
  are stored automatically at the end of `propagate()`; the next same-ticker
  run resolves prior pending entries with realised return, alpha vs SPY, and
  a one-paragraph reflection. Override path with `TRADINGAGENTS_MEMORY_LOG_PATH`.
  Optional `memory_log_max_entries` config caps resolved entries; pending
  entries are never pruned. (#578, #563, #564, #579)
- **DeepSeek, Qwen (Alibaba DashScope), GLM (Zhipu), and Azure OpenAI**
  providers, plus dynamic OpenRouter model selection.
- **Docker support** — multi-stage build with separate dev and runtime images.
- **`scripts/smoke_structured_output.py`** — diagnostic that exercises the
  three structured-output agents against any provider so contributors can
  verify their setup with one command.
- **5-tier rating scale** (Buy / Overweight / Hold / Underweight / Sell) used
  consistently by Research Manager, Portfolio Manager, signal processor, and
  the memory log; Trader keeps 3-tier (Buy / Hold / Sell) since transaction
  direction is naturally ternary.
- **Pytest fixtures** — lazy LLM client imports plus placeholder API keys so
  the test suite runs cleanly without credentials. (#588)

### Changed

- **`backend_url` default is now `None`** rather than the OpenAI URL. Each
  provider client falls back to its native default. The previous default
  leaked the OpenAI URL into non-OpenAI clients (e.g. Gemini), producing
  malformed request URLs for Python users who switched providers without
  overriding `backend_url`. The CLI flow is unaffected.
- All file I/O passes explicit `encoding="utf-8"` so Windows users no longer
  hit `UnicodeEncodeError` with the cp1252 default. (#543, #550, #576)
- Cache and log directories moved to `~/.tradingagents/` to resolve Docker
  permission issues. (#519)
- `SignalProcessor` reads the rating from the Portfolio Manager's rendered
  markdown via a deterministic heuristic — no extra LLM call.
- OpenAI structured-output calls default to `method="function_calling"` to
  avoid noisy `PydanticSerializationUnexpectedValue` warnings emitted by
  langchain-openai's Responses-API parse path. Same typed result, no warnings.

### Fixed

- Empty memory no longer triggers fabricated past-lessons in agent prompts;
  the memory-log redesign makes this structurally impossible since only the
  Portfolio Manager consults memory and only when entries exist. (#572)
- Tool-call logging processes every chunk message, not just the last one, and
  memory score normalization handles empty score arrays. (#534, #531)

### Removed

- `FinancialSituationMemory` (the per-agent BM25 system) and the dead
  `reflect_and_remember()` plumbing; subsumed by the persistent decision log.
- Hardcoded Google endpoint that caused 404 when `langchain-google-genai`
  changed its API path. (#493, #496)

### Contributors

Thanks to everyone who shaped this release through code, design, and reports:

- [@claytonbrown](https://github.com/claytonbrown) — checkpoint resume (#594), test fixtures (#588), design feedback on cost tracking (#582) and structured validation (#583)
- [@Bcardo](https://github.com/Bcardo) — memory-log redesign (#579), empty-memory hallucination report (#572), encoding fix proposal (#570)
- [@voidborne-d](https://github.com/voidborne-d) — memory persistence design (#564), portfolio manager state fix (#503)
- [@mannubaveja007](https://github.com/mannubaveja007) — structured-output feature request (#434)
- [@kelder66](https://github.com/kelder66) — RAM-only memory issue (#563)
- [@Gujiassh](https://github.com/Gujiassh) — tool-call logging fix (#534), test stub PR (#533)
- [@iuyup](https://github.com/iuyup) — memory score normalization fix (#531)
- [@kaihg](https://github.com/kaihg) — Google base_url fix (#496)
- [@32ryh98yfe](https://github.com/32ryh98yfe) — Gemini 404 report (#493)
- [@uppb](https://github.com/uppb) — OpenRouter dynamic model selection (#482)
- [@guoz14](https://github.com/guoz14) — OpenRouter limited-model report (#337)
- [@samchenku](https://github.com/samchenku) — indicator name normalization (#490)
- [@JasonOA888](https://github.com/JasonOA888) — y_finance pandas import fix (#488)
- [@tiffanychum](https://github.com/tiffanychum) — stale import cleanup (#499)
- [@zaizou](https://github.com/zaizou) — Docker permission issue (#519)
- [@Stosman123](https://github.com/Stosman123), [@mauropuga](https://github.com/mauropuga), [@hotwind2015](https://github.com/hotwind2015) — Windows encoding bug reports (#543, #550, #576)
- [@nnishad](https://github.com/nnishad), [@atharvajoshi01](https://github.com/atharvajoshi01) — encoding fix proposals (#568, #549)

## [0.2.3] — 2026-03-29

### Added

- **Multi-language output** for analyst reports and final decisions, with a
  CLI selector. Internal agent debate stays in English for reasoning quality. (#472)
- **GPT-5.4 family models** in the default catalog, with deep/quick model split.
- **Unified model catalog** as a single source of truth for CLI options and
  provider validation.

### Changed

- `base_url` is forwarded to Google and Anthropic clients so corporate proxies
  work consistently across providers. (#427)
- Standardised the Google `api_key` parameter to the unified `api_key` form.

### Fixed

- Backtesting fetchers no longer leak look-ahead data when `curr_date` is in
  the middle of a fetched window. (#475)
- Invalid indicator names from the LLM are caught at the tool boundary instead
  of crashing the run. (#429)
- yfinance news fetchers respect the same exponential-backoff retry as price
  fetchers. (#445)

### Contributors

- [@ahmedk20](https://github.com/ahmedk20) — multi-language output (#472)
- [@CadeYu](https://github.com/CadeYu) — model catalog typing (#464)
- [@javierdejesusda](https://github.com/javierdejesusda) — unified Google API key parameter (#453)
- [@voidborne-d](https://github.com/voidborne-d) — yfinance news retry (#445)
- [@kostakost2](https://github.com/kostakost2) — look-ahead bias report (#475)
- [@lu-zhengda](https://github.com/lu-zhengda) — proxy/base_url support request (#427)
- [@VamsiKrishna2021](https://github.com/VamsiKrishna2021) — invalid indicator crash report (#429)

## [0.2.2] — 2026-03-22

### Added

- **Five-tier rating scale** (Buy / Overweight / Hold / Underweight / Sell)
  introduced for the Portfolio Manager.
- **Anthropic effort level** support for Claude models.
- **OpenAI Responses API** path for native OpenAI models.

### Changed

- `risk_manager` renamed to `portfolio_manager` to match the role description
  shown in the CLI display.
- Exchange-qualified tickers (e.g. `7203.T`, `BRK.B`) preserved across all
  agent prompts and tool calls.
- Process-level UTF-8 default attempted for cross-platform consistency
  (note: this approach did not actually take effect; replaced in v0.2.4 with
  explicit per-call `encoding="utf-8"` arguments).

### Fixed

- yfinance rate-limit errors are retried with exponential backoff. (#426)
- HTTP client SSL customisation is supported for environments that need
  custom certificate bundles. (#379)
- Report-section writes handle list-of-string content gracefully.

### Contributors

- [@CadeYu](https://github.com/CadeYu) — exchange-qualified ticker preservation (#413)
- [@yang1002378395-cmyk](https://github.com/yang1002378395-cmyk) — HTTP client SSL customisation (#379)

## [0.2.1] — 2026-03-15

### Security

- Patched `langchain-core` vulnerability (LangGrinch). (#335)
- Removed `chainlit` dependency affected by CVE-2026-22218.

### Added

- `pyproject.toml` build-system configuration; the project now installs via
  modern packaging tooling.

### Removed

- `setup.py` — dependencies consolidated to `pyproject.toml`.

### Fixed

- Risk manager reads the correct fundamental report source. (#341)
- All `open()` calls receive an explicit UTF-8 encoding (initial pass).
- `get_indicators` tool handles comma-separated indicator names from the LLM. (#368)
- `Propagation` initialises every debate-state field so risk debaters never
  see missing keys.
- Stock data parsing tolerates malformed CSVs and NaN values.
- Conditional debate logic respects the configured round count. (#361)

### Contributors

- [@RinZ27](https://github.com/RinZ27) — `langchain-core` security patch (#335)
- [@Ljx-007](https://github.com/Ljx-007) — risk manager fundamental-report fix (#341)
- [@makk9](https://github.com/makk9) — debate-rounds config issue (#361)

## [0.2.0] — 2026-02-04

This is the largest release since the initial public version. The framework
moved from single-provider to a multi-provider architecture and grew several
production-ready surfaces.

### Added

- **Multi-provider LLM support** (OpenAI, Google, Anthropic, xAI, OpenRouter,
  Ollama) via a factory pattern, with provider-specific thinking configurations.
- **Alpha Vantage** integration as a configurable primary data provider, with
  yfinance as a community-stability fallback.
- **Footer statistics** in the CLI: real-time tracking of LLM calls, tool
  calls, and token usage via LangChain callbacks.
- **Post-analysis report saving** — the framework writes per-section markdown
  files (analyst reports, debate transcripts, final decision) when a run
  completes.
- **Announcements panel** — fetches updates from `api.tauric.ai/v1/announcements`
  for the CLI welcome screen.
- **Tool fallbacks** so a single vendor outage does not stop the pipeline.

### Changed

- Risky / Safe risk debaters renamed to **Aggressive / Conservative** for
  consistency with the displayed agent labels.
- Default data vendor switched to balance reliability and quota across
  community deployments.
- Ollama and OpenRouter model lists updated; default endpoints clarified.

### Fixed

- Analyst status tracking and message deduplication in the live display.
- Infinite-loop guard in the agent loop; reflection and logging hardened.
- Various data-vendor implementation bugs and tool-signature mismatches.

### Contributors

This release is the first with substantial outside contributions; many community
PRs from late 2025 also landed here.

- [@luohy15](https://github.com/luohy15) — Alpha Vantage data-vendor integration (#235)
- [@EdwardoSunny](https://github.com/EdwardoSunny) — yfinance fetching optimisations (#245)
- [@Mirza-Samad-Ahmed-Baig](https://github.com/Mirza-Samad-Ahmed-Baig) — infinite-loop guard, reflection, and logging fixes (#89)
- [@ZeroAct](https://github.com/ZeroAct) — saved results path support (#29)
- [@Zhongyi-Lu](https://github.com/Zhongyi-Lu) — `.env` gitignore (#49)
- [@csoboy](https://github.com/csoboy) — local Ollama setup (#53)
- [@chauhang](https://github.com/chauhang) — initial Docker support attempt (#47, later reverted; the merged Docker support shipped in v0.2.4)

## [0.1.1] — 2025-06-07

### Removed

- Static site assets that had been bundled with v0.1.0; the public site now
  lives separately.

## [0.1.0] — 2025-06-05

### Added

- **Initial public release** of the TradingAgents multi-agent trading
  framework: market / sentiment / news / fundamentals analysts; bull and bear
  researchers; trader; aggressive, conservative, and neutral risk debaters;
  portfolio manager. LangGraph orchestration, yfinance data, per-agent
  BM25 memory, single-provider OpenAI integration, interactive CLI.

[0.2.4]: https://github.com/TauricResearch/TradingAgents/compare/v0.2.3...v0.2.4
[0.2.3]: https://github.com/TauricResearch/TradingAgents/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/TauricResearch/TradingAgents/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/TauricResearch/TradingAgents/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/TauricResearch/TradingAgents/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/TauricResearch/TradingAgents/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/TauricResearch/TradingAgents/releases/tag/v0.1.0

### Fixed
- **`get_support_structure` / `get_value_dip_setup` now render the `sma200`
  basis** next to `distance_to_sma200`, so the support distance is anchored
  to its own computed reference value instead of being spliced with a
  different source's 200-day average (QCOM report 2026-09-07 flagged a
  +0.2% distance claim that was actually +0.54% against the printed avg).
- **EPS YoY degenerate-base guard** (`statement_parsing.sane_eps_yoy`, used
  by `get_decline_driver_check` and the analyst-verdict screen): a vendor
  YoY beyond +/-300%, or one whose prior-year EPS base is below $0.01, is a
  denominator artifact, not a decline signal — it now returns n/a instead
  of emitting nonsensical figures like "-2280% EPS YoY" (QCOM 2026-09-07).

### Added
- **Verbatim-citation rule for analyst figures** (market + news system
  prompts and the shared §Tool Evidence block): every figure must be copied
  verbatim from a tool output - never retyped, reformatted, or spliced -
  and when two tools disagree on the same quantity the analyst must quote
  both with tool names instead of reconciling silently. Addresses the QCOM
  2026-09-07 report-garble class (TGA "303.9->944B" for 903.9, "CCC 0.51%"
  for 10.51, an ATR from one tool spliced onto another tool's stop).
- **`repro_check --evidence` analyst-figure cross-check**: flags decimal
  numbers in each analyst report that have no matching value in the run's
  `tool_evidence.json` (tolerance-based: rounded copies of tool values
  pass, digit-garble like 303.9-vs-903.9 fires). Advisory tripwire; the
  prompt rule is the primary guard.

### Added
- **Sentiment analyst journals its pre-fetch into `tool_evidence.json`**:
  the news / StockTwits / Reddit blocks and the deterministic computed score
  are persisted as normal-shaped `sentiment:*` leaves (same args_hash +
  truncation as forced-tool leaves), closing the post-hoc verification gap
  that made the QCOM 2026-09-07 sentiment tallies ("13 Bull vs 1 Bear",
  "velocity -0.82 vs 0.78") uncheckable — `repro_check --evidence` now
  grounds sentiment figures against what the analyst actually saw.

### Added
- **LLM-failure journal** (`tradingagents/agents/utils/llm_failure_journal.py`):
  when a structured-LLM invoke fails with the provider's raw response
  attached (e.g. openai `LengthFinishReasonError` carrying the full
  `ChatCompletion` incl. hidden reasoning tokens), the graph snapshots that
  completion to `<data_cache_dir>/llm_failures/` (or
  `TRADINGAGENTS_LLM_FAILURE_JOURNAL_DIR`). Wired into both structured-
  invoke fallback sites. Advisory — never raises, never breaks the fallback.
  Regression (EIX 2026-09-07): a 9.3k-reasoning-token debate turn was cut at
  the length limit and only the usage line survived; now the full completion
  (prompt-independent) is recoverable.

### Added
- **Per-analyst tool-call log** (`tradingagents/agents/utils/tool_call_log.py`,
  wired into the short-circuit wrapper): one JSONL row per model tool call,
  appended to `<data_cache_dir>/tool_calls/<SYMBOL>_tool_calls.jsonl`
  (config `tool_call_log_dir`, env `TRADINGAGENTS_TOOL_CALL_LOG_DIR`). Each
  row: ts, symbol, trade_date, analyst, tool, event (`executed` vs
  `short_circuit`), `in_model_pool`, args. Answers "which of the ~40
  model-pool tools did the LLM actually invoke" post-run
  (unanswerable from tool_evidence.json, which only lists what was
  gathered). Advisory — never raises, never blocks the graph.

### Added
- **Anti-repetition sampling controls** (`top_p` / `frequency_penalty` /
  `presence_penalty`, env `TRADINGAGENTS_TOP_P` /
  `TRADINGAGENTS_FREQUENCY_PENALTY` / `TRADINGAGENTS_PRESENCE_PENALTY`):
  cross-provider loop-escape levers forwarded to every client that supports
  them (OpenAI-compatible all three; Anthropic/Gemini top_p only). Default
  None = provider default, so run-to-run reproducibility is preserved unless
  a run opts in (recommended: top_p 0.85-0.95, freq/presence 0.2-0.5).
  Range-validated (top_p in [0,1]; penalties in [-2,2]).
- **Repetition-loop guard in the truncation-retry path** (`structured.py`):
  before a continuation prompt, a run of >= 3 identical consecutive lines
  (the max_tokens-padding attractor loop) is trimmed to its first occurrence
  so the loop is never re-fed as context. Conservative: only exact duplicate
  full lines; legitimate repeated structure untouched.

### Fixed
- **`get_analyst_verdict` / `screen_ticker` `revenue_yoy` degenerate guard**
  (`statement_parsing.sane_revenue_yoy`): a vendor revenue-YoY beyond +/-300%
  (or with no safe base) is a units/denominator artifact, not a signal
  (MSFT 2026-09-08: +1779% vs the true +17.79%); it now recomputes from the
  revenue pair or renders n/a - same class as the existing `eps_yoy` guard.
- **`compute_ratios` plausibility + subset-invariant guards**
  (`strategies/ratios.py`): current assets/liabilities can never exceed total
  assets/liabilities (mis-parse produced current 3.74 vs true 1.23 on MSFT
  2026-09-08 -> ratio now nulled); D/E above 10x and dividend yield above 25%
  are units/scaling artifacts, not balance-sheet reads -> n/a. The exact
  MSFT-current-cap (3,659,011,981,312) formula itself was already correct.
- **yfinance fundamentals formatter guards** (`dataflows/y_finance.py`): a
  >25% dividend yield (0.73 = 73% - percent-scaled input) is re-normalized
  to 0.73%; a D/E > 10 renders an explicit "n/a (implausible vendor value
  > 10)" so a unit-scaled 29.118 never reaches the analyst as a real
  leverage read.
- **Combining-diacritic sanitizer in `_finalize_section`**
  (`reporting.py`): stray U+0300-U+036F marks the LLM emits before
  dates/numbers (13x in MSFT market.md 2026-09-08) are stripped before
  any section is persisted, so markdown renders clean.

### Fixed
- **Price-scale/staleness guard** (new `agents/utils/price_consistency.py`,
  wired into 8 OHLCV tools: swing_set / swing_exits / post_close /
  session_discipline / candlestick / bollinger_pct_b / support_structure /
  macd_divergence): the verified-market snapshot now records its authoritative
  close per run, and any setup tool whose own series' close disagrees (>1%)
  appends a PRICE-SCALE WARNING ("UNRELIABLE") to its output — so a stale or
  wrongly-scaled OHLCV (INTU 2026-09-08: setup tools anchored to the 9/4
  close 332.70 / a ~677-scale series while verified was 314.12) can never
  silently produce actionable stops/targets/psych levels off the wrong price.
- **`get_sentiment_lead_lag` strongest-|corr| spans both metrics**: it now
  scans pearson AND spearman and reports lag + metric (INTU 2026-09-08
  claimed 0.206 while a pearson -0.278 was larger).
- **Net-debt sign cross-check** (`y_finance._net_debt_note`): when a yfinance
  balance-sheet's own cash+STI exceeds total debt but the vendor "Net Debt"
  row is positive (INTU 2026-09-08: 8.44B cash vs 6.9B debt, "Net Debt"
  1.48B), the output appends a NET CASH correction note so the analyst never
  quotes a positive debt position that contradicts the sheet.
- **yfinance fundamentals OCF field**: "Operating Cash Flow" now rendered
  separately from "Free Cash Flow", so FCF==OCF aliasing (INTU 2026-09-08:
  6.44B == 6.44B) is visible instead of silently duplicated.
- **`get_ratios` uses a dynamic default date** instead of the hardcoded
  "2026-08-24" (stale quarter could shift current ratio / D/E).

### Fixed
- **`get_composite_rank` surfaces its ranked peer sample** (`peers_ranked:
  <tickers>`) so the "vs N peers" count is auditable against the actual
  tickers (INTU 2026-09-08: "vs 4 peers" while the report listed 10 company
  peers — the two samples come from different sources and are now visible).
- **Distinct labels for the three drawdown measures**: regime `52w_distance`
  is now `52w_distance(drawdown vs 52-wk high)`, `get_book_tail_risk` reads
  `drawdown(book realized)`, `get_strategy_quality` reads `max_dd(backtest)`
  — the unlabeled trio (INTU 2026-09-08: -51.32% / 62.68% / 68.41%) can no
  longer be silently conflated.
- **`live_price_sanity` INSIDE wording clarified**: it reports
  "within the verified day's range [...] (stale-print tolerance +-X%)" so the
  band is not misread as a ±5% band around the live price (INTU 2026-09-08:
  the "[313.13, 327.00] ±5%" label implied ±5% around 314.12, which it is not).

### Fixed
- **`get_credit_spread_read` default-probability 100x error**
  (`analysis_tools.py`): `hazard_from_spread` / `default_probability` expect a
  DECIMAL spread, but the tool passed the FRED percentage (2.68 = 2.68%)
  — producing hazard 4.467 (446.7%) and implied 1y PD 98.9% instead of
  ~4.4% (INTU 2026-09-08 news.md). The tool now converts `hy / 100` before
  computing; a "moderate" credit read no longer renders an absurd 98.9%
  default probability.

### Fixed
- **`sane_revenue_yoy` percent-scaled guard** (`statement_parsing.py`): a
  vendor `revenue_yoy` in (0.3, 3.0] that is percent-scaled (e.g. 1.88 = the
  QCOM 2026-09-08 patch — rendered 188% vs the true +1.9%) now resolves via
  the revenue current/prior pair (ground truth); without a pair, a >100%
  claimed YoY is treated as percent-scaled (1.88 -> 1.88%). The earlier
  |v|>3.0-only guard let the 100x artifact through for values under 300%.

### Fixed
- **`_ohlcv` aligned to the verified-snapshot source (N21 — root cause of the
  price-scale warnings)**: both `analysis_tools._ohlcv` and
  `value_dip_tools._ohlcv` now read from `stockstats_utils.load_ohlcv` — the
  SAME date-aware, look-ahead-filtered source the verified market snapshot
  uses — instead of the vendor-chain CSV that lagged a session or returned a
  corrupted ~2x-scale series (MSTR 2026-09-08: tools at 284.92 / 142.80 vs
  verified 136.68; INTU 2026-09-08: 332.70 vs 314.12). Fixes the stale close
  at the root: the 8 setup tools now compute on the same day's price as the
  verified close, so actionable stops/targets/levels are no longer built on
  yesterday's (or a corrupted) series, and the PRICE-SCALE WARNING advisory
  (6960a03) now correctly stays silent when the sources agree. Also fixed the
  column mapping (load_ohlcv df is `Date,Close,High,Low,Open,Volume`).
- **Test seam `_load_ohlcv_df`** added to both tool modules so the OHLCV
  loader is patchable without bypassing the verified source; the impacted
  `test_analysis_tools.py` data-mocks converted to produce DataFrames.

### Added (advisory LLM report verifier — design docs/design_report_verification_llm.md)
- **LLM report-verification pass**: `tradingagents/agents/utils/report_verifier.py`
  checks every analyst report (1_analysts/*.md) against its `tool_evidence.json`
  leaves and returns per-claim verdicts (`GROUNDED | UNSUPPORTED | CONTRADICTED`)
  + a report-level `PASS/FLAG/UNKNOWN`. It is the qualitative layer the
  deterministic `--evidence` numeric cross-check (`scripts/repro_check.py`)
  cannot provide (causal wording, "never called" phrasing). Advisory: never
  edits reports, never blocks delivery; a provider failure degrades the
  affected report to UNKNOWN (never raises mid-run).
- **Numeric anchoring** (`_anchor_claims`): after the LLM, each claim's decimal
  figures are reconciled against the evidence leaf decimals with the SAME
  <=0.5% tolerance as `repro_check._matches`, so the two gates never disagree
  "about the same number" — a claim the numeric layer would ground is never
  left UNSUPPORTED, and a CONTRADICTED whose figures ARE in evidence drops to
  UNSUPPORTED (no false numeric contradiction).
- **CLI** `scripts/report_verify.py --report-dir <tree> [--model X --provider Y
  --max-calls N]`: offline post-run check, writes `verify_flags.json`, exit 0 =
  all PASS/UNKNOWN, 1 = any FLAG, 2 = missing dir.
- **batch `--verify`**: after each completed symbol, runs the verifier and
  writes `verify_flags.json` (mirrors `_batch_pre_market_check`; best-effort,
  never fails the symbol).
- **Config/`.env.example`**: `TRADINGAGENTS_VERIFY_MODEL` (empty = quick tier)
  and `TRADINGAGENTS_VERIFY_MAX_CALLS` (default 12 per report tree; excess
  stems degrade to UNKNOWN).

### Fixed (report-verifier loop findings, first full pass over MSTR batch6)
- **Unit-scale-blind figure matching** (verifier + `repro_check --evidence`):
  `_matches` now treats raw tool floats and human units as equivalent
  (report `122.4M` matches leaf `122368000.0`, `8.22B` vs `8219628000.0`).
  Deterministic fundamentals suspects on the MSTR tree: 20 -> 0. Canonical
  implementation now lives in `report_verifier._matches`; `repro_check` imports
  it so the two gates share tolerance AND unit handling.
- **Digest hid evidence from the verifier**: `_evidence_digest` capped leaves at
  200 chars, hiding the income-statement revenue row (~4.4k in) and producing
  false "no leaf evidence: truncated" flags. Default is now full-leaf (the
  gatherer already caps at summary_window=12000).
- **Sentiment prompt mandated a fabricated 0-10 score**: `overall_score` was
  produced from nothing (MSTR: "Mildly Bearish 4.0/10" vs deterministic
  computed +0.08). The pipeline now computes deterministic sentiment BEFORE
  the prompt, injects `Deterministic computed sentiment` into the system
  message, and instructs the LLM to anchor the 0-10 verdict as
  `5 + 5 * computed_score` within ±0.5, never contradicting it. The verifier
  now cross-checks the saved report's score against the computed leaf.
- **CLI**: `scripts/report_verify.py --stem <X>` for single-stem / parallel
  per-stem verification (each stem its own bounded job).

### Fixed (adopted from upstream TradingAgents 0.4.0 #1170)
- **Silent-Hold → REVIEW sentinel** (`tradingagents/agents/utils/rating.py):
  an unparseable rating (garbled `Rating: <value>` label — non-tier word,
  fullwidth-colon label, or non-word value like `Rating：⭐⭐⭐`) previously
  degraded to a tradeable Hold; it now returns the `REVIEW_SENTINEL`
  ("REVIEW") so a broken PM decision can never be acted on as Hold. Only the
  tradeable-tier fallback is hardened: callers with an explicit non-tradeable
  default (`"n/a"`) keep it, and ordinary prose that merely mentions "rating"
  without a colon-separated value is untouched. `SignalProcessor` surfaces
  REVIEW too. See docs/review_parent_tauricradingagents.md (review-only, the
  one adoptable item).

### Added (report verifier — internal-consistency pass)
- **Cross-claim internal-conflict detection** (`report_verifier._internal_conflicts`):
  the verifier previously checked each claim against the tool evidence
  individually, so it could not see the same metric asserted at conflicting
  values *within one report* (the TJX 2026-09-08 fundamentals.md: EPV $79.78B
  vs $5.7B, ROE 62.17 vs 53.92, D/E 1.32 vs 1.3, insider net +145,976 vs
  +175k, EPS 5.81 vs 4.79 — every figure "matched some leaf", so per-claim
  anchoring missed the contradiction). Adds an `INTERNAL_CONFLICT` claim class
  (new status) for same-metric/different-value across the report, value
  normalised across K/M/B magnitudes, >1% divergence, values scoped to the
  metric label (no cross-metric misattribution). Advisory, never rewrites.
- **Working-agreement rule 8** (docs/AGENT_ONBOARDING.md): after every
  report-verifier run, verify flagged claims against tool_evidence leaves and
  fix confirmed defects.

### Fixed (market.md audit of TJX 2026-09-08)
- **`get_tranche_plan` avg_entry is size-weighted — now labeled**: the output
  emits `avg_entry(size-weighted)=` instead of ambiguous `avg_entry=`. The
  value was ALREADY correct (weights `[0.3,0.3,0.4]`, w×P = 125.57), but the
  label let readers/below comprehension misread it as an equal-weighted mean
  (simple avg of P1/P2/P3 = 125.88). Disclosing it removes the implied-error
  confusion. Test contract updated to pin `size-weighted`.
- **Market.md remaining conflicts (beta 0.13 vs 0.593, short 1.78% vs 48.1%
  Reg-SHO, put-skew -39.0% vs skew-slope, credit 'moderate' vs 'low') are
  definition-level cross-source issues** — every figure exists in a leaf, so
  they are correctly-unflaggeable-by-value; they are now documented in the
  design doc rather than silently dropped (rule 8).

### Added (composed portfolio>trade risk gate — market.md audit #2/#10)
- **`get_composed_risk_gate(ticker, size_pct?, capital_at_risk_pct?, risk_cap_pct?,
  liquidity_verdict?, weights=...)`**: the ONE-call risk verdict that composes
  the portfolio gate (realized book drawdown from the weighted book, same
  source as `get_book_tail_risk.drawdown_gate`) INTO the risk governor and
  applies the precedence rule **portfolio gate > trade gate** — a blocked
  portfolio drawdown REJECTs a position even when trade-level `risk_ok`
  looks fine (the TJX 2026-09-08 conflict: drawdown_gate=True 23.21% book DD
  vs risk_ok=True). The analyst no longer reconciles the two gates by hand.
  Live proof on TJX: `verdict=REJECT precedence=portfolio-gate>trade-gate
  portfolio_drawdown_block=23.21%`. Wired into the market analyst tool list +
  prompt guidance (+ tests, incl. the disclosure path when book drawdown is
  unavailable — never silently passes). Addresses the external review's
  drawdown-precedence and integration-precedence points.

### Added (quant decision-arbitration — 4 researched phases, all default-off/advisory)
- **P1 Gather-time metric reconciliation** — `strategies/metric_reconcile.py`
  (pure) groups the same metric from multiple tools into ONE canonical bucket
  (e.g. get_fundamentals/get_ratios/get_basic_financials -> market_cap) and
  tags conflicting values at INGEST; `format_evidence_block` appends a
  "VALUES CONFLICT range=... vendors=[...]" line so the analyst sees the
  conflict BEFORE reducing (moves the TJX DCF-80.76-vs-80.60 class from
  post-hoc verifier detection to gather-time prevention). 8 tests.
- **P2 Per-regime calibrated confidence** — `calibration.fit_buckets_by_regime`
  + `calibrated_confidence_by_regime` (per-regime buckets, `_all` fallback) +
  lazy `isotonic_calibrate`; PM `_calibrated_p` now takes the overlay's regime
  label. 6 tests.
- **P3 Weighted + thresholded consensus** — `consensus.weighted_consensus`
  (per-analyst weights, equal=mean) + `should_hold(score, threshold)`; the PM
  consensus line now reports weighted_stance + a HOLD note when below the
  threshold. 7 tests.
- **P4 Hard-gate precedence resolver** — `strategies/risk_hierarchy.py`
  (kill > portfolio > trade > liquidity > regime > data, earliest REJECT
  wins) + `kill_switch_state` emergency tier; `get_composed_risk_gate` now
  resolves the FULL hierarchy (added halt/regime_veto params) and reports
  `blocker=` + the precedence chain. 9 tests.
- **Walk-forward calibration audit** — `scripts/calibration_walkforward.py`
  (pure/offline): fits per-regime buckets IS, evaluates OOS reliability + ECE,
  and shows the calibrated re-map; exit 0/1 by a 0.10 ECE bar. Hermetically
  verified on a synthetic ledger.b

### Added (IT subsector universe + dual-benchmark RS — sector-rotation one level down)
- **IT subsector universe** in `sector_rank.INDUSTRY_ETFS` (parent XLK): CIBR
  Cybersecurity, SKYY Cloud Computing, AIQ AI, BOTZ Robotics, DTCR Data
  Center, NXTG Networking, IYW Tech Hardware, FINX FinTech, XSD Semis (equal-
  weight), VGT Broad IT. Kept INSIDE XLK so the subsectors rank against each
  other within the sector, never vs XLK. VGT is registered as the benchmark —
  excluded from the ranked pool (never circular).
- **Dual-benchmark RS** (`rank_sectors_multifactor` / `rank_industry_group`
  new `bench2_closes`): emits a per-row `rs2` percentile vs a SECOND benchmark
  (the IT pool uses VGT) WITHOUT re-ranking the SPY-relative `rs`. The
  `get_sector_rank` tool now draws VGT as bench2 on the XLK industry pool and
  reports `rs2_vs_vgt` on the top pick — answering "which IT subsector is
  strongest vs IT" separately from "vs the market". Tests: 4 new.

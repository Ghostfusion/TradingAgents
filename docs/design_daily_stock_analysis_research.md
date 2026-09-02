# Design: What TradingAgents can learn from `ZhuLinsen/daily_stock_analysis` (DSA)

**Status:** research + design only — no code changed.
**Date:** 2026-09-02.
**Source study (source-verified this session):** clone of
`https://github.com/ZhuLinsen/daily_stock_analysis` (master, commit at read
time — ~1,150 files). Read directly: README, AGENTS.md, SKILL.md,
`strategies/README.md` + `strategies/*.yaml` (15 strategy skills),
`docs/screening-engine.md`, `docs/research-artifact.md`, `templates/report_markdown.j2`
(+ `_macros.j2`). Sub-agent deep reads (file:line transcription): `main.py`
(orchestrator), `src/scheduler.py`, `src/core/trading_calendar.py`,
`src/core/pipeline.py`, `src/core/market_review_lock.py`,
`api/app.py` + `api/v1/*` (REST surface), `bot/dispatcher.py`,
`src/notification.py` (+14 channel senders), `data_provider/*` (multi-market
routing), `src/search_service.py` (7-provider news search),
`src/analyzer.py`, `src/agent/` (skills/router/agents/orchestrator/runner/
llm_adapter), `src/schemas/{decision_scale,decision_action}.py`. Paper:
**arXiv 2608.26990 "DSA: Evidence-Aware LLM-Agent Orchestration for
Multi-Market Stock Research"** (Linsen Zhu, Yi Shi; 2026-08-27 — abstract
read directly). Web search (2026-09-02): repo context/positioning.

**Object:** absorb DSA's transferable lessons into this fork without
violating its contracts: **compute-as-tools, no-fabrication, advisory-first,
deterministic hard gates, walk-forward/PBO before any gate ships,
analysis-only (no execution layer).**

Companion docs: `design_qlib_integration.md`, `design_finrl_integration.md`,
`design_market_refresh_fastpath.md`, `design_*_enhancements.md`.

---

## 1. What DSA is (one paragraph)

DSA is a popular (TrendShift #1-Python-repo-of-the-day at read time,
arXiv 2608.26990) **AI-LLM daily stock-analysis system** for A/HK/US/JP/KR/TW
watchlists: every trading day it fetches multi-market data, runs an
evidence-aware LLM-agent analysis (context pack → technical → intel → risk →
decision, plus optional Strategy-Skill reasoning), emits a structured
"decision dashboard" per name (core conclusion, data perspective,
intelligence, battle plan, phase decision, signal attribution, strategy
synthesis), aggregates a market review, and pushes reports to 14 channels
(WeChat Work/Feishu/Telegram/Discord/Slack/email). It is deployed via GitHub
Actions, Docker, a FastAPI service, a Web workbench and a desktop app. Its
worldview: **evidence → structured context → model-routed analysis → report,
with every opinion traceable and every unavailable surface disclosed**. Its
paper's own claim is scoped: the 1,457-portable-contract-test manifest
"establishes implementation conformance for the tested software contracts,
not superior report quality, forecasting accuracy, or investment returns."

The fork's worldview is complementary: **LLM deliberation over deterministic
computed numbers**, single-name-first, US-focused, committees + deterministic
overlays, no execution. The two share DNA: `pipeline.py` (screen→rank→top-N),
pre-market review, `strategy_quality_report`, the debate/consensus machinery,
the T0/T1/T2 fast-path design.

---

## 2. DSA pillars → fork gaps → transferable lessons

| DSA pillar (source-verified) | What it does | Fork gap today | Transferable lesson (adoptable) |
| --- | --- | --- | --- |
| **1. Post-LLM deterministic guardrail layer** (`analyzer.py:1000-1175, 1376-1390`) | After the model returns, deterministic overrides apply in order: fill missing price/chip fields → `stabilize_decision_with_structure` (downgrade a buy without capital inflow near resistance; a sell without outflow near support; hold/watch score re-bounded to 45–59) → phase guardrail → daily-market-context softening → 8-state action realignment, **each with a recorded `guardrail_reason`; can only soften/downgrade, never upgrade** | The analyst→trader→PM chain has computed rows but no post-decision deterministic correction pass; `enable_decision_audit` records PM claim-vs-computed but never adjusts | **A pure `decision_guardrail` stabilizer after the PM decision**: only softens/downgrades with a recorded reason, never upgrades; reuses the existing regime/flow/technical reads + ledger stop-adherence |
| **2. Canonical score↔action contract in the prompt + versioned scale** (`schemas/decision_scale.py:17-45`) | One 0–100 scale → 8-state action / 3-state decision table (80–100 strong_buy, 60–79 buy, 40–59 watch/hold, 20–39 reduce, 0–19 sell); the consistency rule (score≥60 yet hold/watch, or score<40 yet watch/hold → MUST emit `guardrail_reason`) is embedded in the system prompt AND re-validated post-hoc | `PortfolioDecision` + `bind_structured` let the PM free-form a rating/size; score↔action agreement is not enforced | **Versioned decision-scale table + `guardrail_reason` field in the PM schema**, post-hoc validator raising a documented inconsistency (advisory, never a silent fix) |
| **3. Negative-override risk weighting** (`agent/agents/decision_agent.py:63-77`) | Risk agent is ~30% of the signal blend AND a hard cap: any high-severity risk caps the final signal at hold regardless of bullish inputs | Risk debators advise; the governor can REJECT (hard), but the advisory decision card has no "risk cap at hold" tier | **A `risk_cap` field in the decision card**: high-severity advisory risk rows cap the displayed recommendation at hold (never sell-forced by risk alone); the governor stays the only hard gate |
| **4. Confidence gated by data quality + integrity retry** (`analyzer.py:2091, 3896-3930`; prompt rule) | `confidence_level` must not be 高 when ANY data slice is stale/fallback/missing/partial/estimated; missing mandatory fields trigger a **targeted integrity retry** (rebuild prompt = original + previous response + per-field spec), not a blind re-roll; final text-fallback parse keeps a report | `structured.py` has NO_EXTERNAL_TOOLS + truncation retry (test_truncation_retry) but no data-quality→confidence gate and no per-field integrity rebuild | **Bind a `data_quality` flag into structured outputs; gate PM confidence on it; add a per-field integrity retry** (reuse the provider fabric, no blind re-roll) |
| **5. Strategy-skill YAML DSL + regime router** (`strategies/*.yaml`, `agent/skills/router.py:29-84`) | Strategies declared in YAML: `name/instructions` (natural language), `category`, `core_rules`, `required_tools`, `default_active/default_router/default_priority`, `market_regimes`, numeric score adjustments (e.g. `volume_breakout: sentiment_score +12`). Router precedence: user-requested → manual config → **regime detected from an EARLIER stage's structured technical opinion** (ma_alignment + trend_score: ≥70 trending_up / ≤30 trending_down / 35–65 sideways) → priority-sorted fallback. Zero new code per strategy | Overlays are code (regime.py, overlays.py), not declarative; no per-strategy instruction+leverage YAML; regime is not derived from a structured opinion, it is computed separately | **A declarative skill-YAML layer + regime-from-opinion routing**: numeric score adjustments as pure fold inputs (advisory, gated as today); regime derived from the trend-analysis opinion, not a new model call |
| **6. Multi-market code classification + per-market source chains** (`data_provider/base.py:71-152, 619-641`) | Classify a symbol's market FIRST, then consult that market's own source whitelist in config-string priority; unconfigured sources are not instantiated; credentials auto-boost a source up the chain; env can re-prioritize; first-success primary returns early, `_SUPPLEMENT_FIELDS` gap-fill from secondary | `route_to_vendor` is a single global chain (eodhd/tiingo/yfinance/moomoo) with no market classifier and no per-market priority config | **Market-classified routing + per-market source priorities** (US/CA winding first); quote contract gains `fallback_from`, `is_stale/stale_seconds`, `data_quality`, `missing_fields` (extends `market_data_validator`) |
| **7. Layered data-source health** (`data_provider/realtime_types.py:394-409`, `base.py:822-856`) | Circuit breaker (3 fails / 300 s cooldown / half-open probe; chip 2/600 s), per-(market,fetcher) health keys, long-connect cooldowns (futu/pytdx 15 s), capability negative caches (TTL 900 s), fail-open fundamentals with per-block status ok/partial/failed + `source_chain` | `vendor_cache` has TTL but no breaker/cooldown/half-open; fundamentals falsify per-call, not per-block with a source chain | **Breaker + negative-cache semantics on the vendor layer**; per-block fundamental bundles with `status`/`source_chain` (feeds the report honesty footer) |
| **8. News search: deterministic relevance scoring + official-source boost + spam admission + degrade triple** (`search_service.py`) | 7 providers (Anspire→Bocha→Tavily→Brave→SerpAPI→MiniMax→SearXNG) with per-source timeout; relevance score: code-in-title +55 / snippet +34 / url +18, company-name title +45 (+26 ambiguous), **official source +8** (sec.gov, nasdaq.com, sse/szse/hkex), macro override −12, clamp 0..100, max 5 explainable reasons; spam/app-download pages dropped by content signals unless official; degrade triple: all-failed→`success=False`, filtered-empty→`success=True provider=Filtered`, per-path `NoUsableNews` diagnostics | News pipeline has per-source tools but no unified relevance score, no official-source boost, no spam admission pass, and reports "no news" without distinguishing empty-vs-failed | **Deterministic relevance scoring + official-source boost + admission filter over the news tools**; degrade triple semantics in the news readouts ("no news" ≠ "search failed") |
| **9. Owner-wait request coalescing + TTL result cache** (`search_service.py:2707-2775`) | Per-(query,target,days) in-memory cache (TTL 600 s, cap 500); concurrent identical requests coalesce: first caller = owner, waiters wait on an event (cap 30 s) and re-compete if the owner failed; only successes cached; hits attributed `provider=SearchCache` | `_RUN_OHLCV_CACHE` is run-level only; parallel analyst loops could fire duplicate identical news searches within a run | **Coalescing + TTL cache for heavy read surfaces** (news search, macro fetches) so a run's parallel analysts share one fetch |
| **10. Checkpoint/resume as data idempotency** (`core/pipeline.py:385-414`) | Never persist "step N of batch": key analysis by `(symbol, effective_trading_date)`; skip when data+report exist (`has_today_data`); re-running resumes naturally; per-run **frozen reference time** so a long batch never straddles a close boundary | Batch reports overwrite/accumulate per timestamp; failed reruns redo whole batches; no effective-trading-date keying | **Resume via (symbol, effective_date) idempotency + frozen run reference time** in `batch.py`/nightly; natural crash-resume |
| **11. Trading-day calendar, fail-open, per-market TZ** (`core/trading_calendar.py`) | exchange-calendars optional; `MARKET_EXCHANGE` map; "today" per market's own tz; `get_effective_trading_date`: non-trading day→previous session, before close→previous, after close→current, fail-open to local date; all-closed→skip with log (`--force-run` escape hatch); market-review run uses its own region filter | Nightly/pre-market assume US calendar; no effective-date logic, no all-closed skip | **Effective-trading-date helper + fail-open calendar** for nightly/pre-market/fast-path (region param), `--force-run` bypass |
| **12. Phase-decision schedule** (`phase_decision` 7 fields + `_macros.j2`) | Per-stock `action_window` / `immediate_action` / `watch_conditions` / `next_check_time` / `confidence_reason` / `data_limitations` structured decision follow-up | Pre-market CONFIRM/REVISE/REJECT lacks structured watch-conditions + next-check-time | **`watch_conditions` + `next_check_time` in the PM decision card** → feeds the fast-path T1/T2 cadence ("why HOLD and when to re-check") |
| **13. Strategy synthesis + signal attribution + disclosure footers** (`report_markdown.j2` blocks) | Per decision: `strategy_synthesis` (final_signal, consensus_level, conflict_severity + count, supporting/opposing skills with confidence, invalid-opinion count, top-3 conflicts), `signal_attribution` (4 weights summing 100 + strongest bull/bear signal), and report footers: **data_sources used/empty, models_used, generated_at, history-comparison table** (prior score/action/trend per name) | Reports have decision audit + memory log but no per-decision attribution weights, no supporting/opposing consensus readout at the skill level, no models-used footer, no per-name history-comparison table in the report | **Attribution + consensus + disclosure blocks** in `action_report`: which driver weights, which sources contributed (vs empty), which model, prior-decision delta |
| **14. ResearchArtifact: thesis + evidence + invalidation conditions** (`docs/research-artifact.md`, schema v1) | Structured per-report artifact: `thesis` (direction/confidence/action/reasons/risks), `evidence[]` each with `freshness` (fresh/stale/unknown) + `quality_level` (good/…/poor), **`invalidation_conditions` (≥1 mandatory)**: stop-loss breach, take-profit review, data-quality limits, missing disclosure, else `manual:thesis_reassessment` fallback; enables "What Changed" thesis diffs | Decisions are prose/`full_states_log`; no explicit invalidation contract; the fast-path HOLD/UPDATE/ESCALATE lacks a rule telling when a prior thesis dies | **Invalidation conditions on the stored decision** (stop breach / TP review / data staleness thresholds) — the missing "when does the last thesis stop being true" rule for the fast path |
| **15. Per-symbol failure isolation + output-gate** (`core/pipeline.py:3531-3606`, `main.py:1099-1106`) | Thread pool per symbol; each future's exception is caught independently; batch continues; whole-run failure ONLY when zero outputs; distinct failure reasons (`empty_stock_list`/`no_report`/`report_save_failed`/`runtime_error`) mapped to exit codes for cron vs API | Batch isolates per-symbol already (batch_summary rows), but no explicit "output gate" (fail only when zero reports) with distinct reasons | **Output-gate + distinct failure reasons** so nightly/cron semantics are explicit |
| **16. Async surface: queue + poll + SSE + DB fallback** (`api/v1`) | POST analyze → 202 {task_id}; GET status/{id} with DB fallback (completed tasks survive restart; task_id==query_id); SSE stream with 30 s heartbeat; per-task flow snapshot; tasks cap 100, dedupe → 409 | trading_web has jobs but no persisted task-id fallback / flow snapshot | **Note only** — web surface is a separate repo; adopt the persisted-status + flow-snapshot idea when wiring the web jobs screen |
| **17. Dev/AI-governance process** (AGENTS.md) | Single AI-gov source (AGENTS.md =唯一真源, CLAUDE.md symlink); screenshots/evidence live in PR/issues, never committed; review bans patch-stacking; changelog Unreleased in flat lines to cut merge conflicts; "docs-only: say tests not run"; deliverables state changed/why/verified/unverified/risk/rollback | The fork's working agreement already covers docs-true, explicit staging, no fabrication | **Adopt the flat Unreleased changelog convention** (merge-friendly) + "docs-only → say tests not run" delivery note. Nothing else new |

---

## 3. Proposed adoptions for this fork (concrete, advisory, default-off)

### 3.1 `tradingagents/strategies/decision_guardrail.py` (new; pillar 1–3)
- `stabilize_decision(decision, risk_rows, technical_read, flow_read, ledger_state) -> {decision', overrides: [reason, direction]}` — pure; **only softens/downgrades** (buy→hold etc.), never upgrades; each override records a `guardrail_reason`. Rules: buy without confirmed capital inflow near resistance → hold; sell near support without outflow → hold; high-severity risk row → `risk_cap` sets displayed action ≤ hold; hold/watch score bounds.
- `validate_score_action_agreement(score, action, scale_version)` — the versioned scale table (0–100 → 8-state) as a pure validator; mismatch → advisory `guardrail_reason`, never a silent fix.
- Wire: after the PM decision is assembled (`action_report` render path), advisory `guardrail` block; config `enable_decision_guardrail` (False) + `decision_guardrail_*`.
- Tests `tests/test_decision_guardrail.py`: downgrade-only invariant (property-style: any input → never upgrades); risk-cap ≤ hold; score-action validator flags documented mismatches; no-fabrication None paths.

### 3.2 PM schema + confidence gate (extends `agents/schemas.py`; pillar 4)
- `PortfolioDecision` gains optional `guardrail_reason`, `data_quality` flag, `risk_cap`; confidence levels mapped from data quality (stale/fallback/missing → cannot assert high confidence).
- Integrity retry: `structured.py` bind path gains a targeted rebuild on missing mandatory fields (original prompt + prior response + per-field spec) before a fallback — reuse the existing truncation-retry fabric; add a per-field variant.
- Tests `tests/test_pm_decision_schema.py`.

### 3.3 Skill-YAML overlays + regime-from-opinion (new declarative layer; pillar 5)
- `skill://`-style YAML under `strategies/skills/*.yaml` (name/instructions/required_tools/category/core_rules/market_regimes/default_priority + numeric score adjustments) loaded at config time (pure, hermetic, no code per skill).
- Regime derivation from the trend-analysis structured opinion (ma alignment + trend score thresholds) — no new model call — feeds the skill router + the existing regime fold.
- Config `enable_skill_overlays` (False), `skill_dir`; numeric adjustments become advisory fold inputs behind the existing hard gates.
- Tests `tests/test_skill_overlays.py`: YAML parse; regime-from-opinion thresholds; adjustments bounded; unknown skill → explicit unavailable.

### 3.4 Vendor-layer upgrades (extend `dataflows/interface.py` + `vendor_cache.py`; pillars 6–7)
- `market_for_symbol(symbol)` classifier (US buckets; extend for CA/exchange suffixes when relevant) → per-market source priority (config-string, e.g. `US_MARKET_SOURCE_PRIORITY: eodhd,tiingo,yfinance,moomoo`); unconfigured sources skipped; first-success early return + `_SUPPLEMENT_FIELDS` gap-fill.
- Quote/bar result contract gains `fallback_from`, `is_stale`, `stale_seconds`, `data_quality`, `missing_fields` (extends `market_data_validator.py`); report honesty footer consumes it.
- Circuit breaker per (market, vendor): 3 fails / 300 s cooldown / half-open probe + capability negative cache; fail-open semantics.
- Config: `market_source_priority` maps + `vendor_breaker_*`; default behavior unchanged.
- Tests `tests/test_vendor_routing.py`: market classification; priority honoring; breaker tripping/half-open; gap-fill merge.

### 3.5 News relevance + admission + degrade semantics (extend the news tools; pillars 8–9)
- `strategies/news_relevance.py` (pure): score = code-in-title/snippet/url, company-name, **official-source boost list** (sec.gov/nasdaq/nyse — the sources the fork already consumes), macro negative, clamp, max-5 reasons; admission filter drops app-download/spam pages by content signal unless official.
- Owner-wait coalescing + TTL cache (600 s) for identical (query,target,days) news searches; hits attributed `provider=SearchCache`.
- Degrade triple in news tool outputs: `all_failed` vs `empty` vs `unavailable` — "no news" never means "search failed".
- Config `enable_news_relevance` (False) (routing default off; degrade triple always-on honesty in the tool string).
- Tests `tests/test_news_relevance.py`: planted items scored + admission; official-source boost; coalescing hit/miss; degrade triple.

### 3.6 Effective-trading-date + resume idempotency (extend `scripts/nightly_review.py` / `batch.py`; pillars 10–11)
- `dataflows/effective_date.py` (pure): `effective_trading_date(region, ref_utc, calendar=optional-fail-open)` — non-trading day→previous session; before close→previous; after close→current; `--force-run` bypass + all-closed skip-with-log.
- Resume keying: nightly/batch decide-report rows keyed by `(symbol, effective_date)`; rerun skips completed, finishes missing; per-run frozen reference time.
- Config `region` (US default), `force_run` flag; default behavior unchanged.
- Tests `tests/test_effective_date.py`: weekend/holiday/pre-close/post-close cases with a planted calendar.

### 3.7 Report disclosure + attribution + invalidation (extend `action_report` / reports; pillars 12–14)
- `action_report` gains advisory blocks: `signal_attribution` (driver weights from the composite/regime/flow reads — computed, not narrated), `consensus` (supporting/opposing from the existing debate + skill overlays), footers: `data_sources` (which sources contributed; which empty), `models_used`.
- Decision rows gain `watch_conditions` + `next_check_time` (feeds the fast-path cadence) and **`invalidation_conditions`** (stop breach / TP review / staleness thresholds / else `manual:thesis_reassessment`) stored with `full_states_log`; the fast-path T1/T2 uses them ("when does the prior HOLD die").
- All pure/advisory; `enable_report_attribution` (False) + always-on honesty footers.
- Tests `tests/test_report_disclosure.py` + `tests/test_invalidation_conditions.py`.

---

## 4. Non-goals / risks (honest)

- **No execution layer.** DSA ships trade tools (`src/agent/tools/execution.py`) and broker holdings integration; the fork is analysis-only — keep it that way (matches every prior design's non-goal).
- **No A-share data pipeline.** DSA's crown jewels are A/HK-centric (Tushare/AkShare/TickFlow/Longbridge chains); the fork is US-first. Adopt the *routing/health/resume patterns*, not the sources; JP/KR/TW support would be a separate effort.
- **LLM-score-driven decisions vs compute-as-tools.** DSA's action comes from an LLM sentiment score with deterministic stabilizers; the fork's hard gates stay the authority. The guardrail/stabilizer is adopted as an *advisory* fold (enable_decision_guardrail False default) — it never replaces the governor.
- **Chinese UI/report localization** — out of scope (the fork has its own language knob).
- **Web/desktop app + 14 push channels** — out of scope (separate trading_web repo; no push infra). The async queue+poll+SSE pattern is noted for the web jobs screen only.
- **Screening engine (AlphaSift-derived)** — the fork's `value_screener` already covers its niche; DSA's per-source TTL cache + rotation are heavier machinery than needed. Adopted: source-health + honesty, not the full engine.
- **Single-LOC monolith style** (search_service.py ~194 KB, storage.py ~171 KB) — an anti-pattern on DSA's own AGENTS.md quality bar; the fork keeps small pure modules.
- **Paper claims are conformance, not alpha.** arXiv 2608.26990 explicitly says its test manifest proves contract conformance, not performance or returns — same honesty bar the fork's own docs apply to RD-Agent/FinRL claims.

## 5. Quick-wins verdict

1. **Effective-trading-date + resume idempotency** — correctness for nightly/pre-market/fast-path, ~pure helpers, no new deps.
2. **Decision guardrail (downgrade-only + risk-cap + score↔action validator)** — the highest-leverage decision-quality fix; pure, advisory, default-off.
3. **Confidence gated by data quality + per-field integrity retry** — makes every PM assert honest about its inputs.
4. **News relevance scoring + official-source boost + degrade triple** — zero new vendors, honest news readouts.
5. **Skill-YAML overlays + regime-from-opinion** — declarative strategies with numeric adjustments; advisory folds only.
6. **Vendor routing: market-classified priority chains + breakers + stale/fallback contract** — robustness + report honesty; larger, touches the vendor layer (test carefully, behavior unchanged by default).
7. **Report disclosure/attribution/invalidation** — the report becomes a decision artifact with a "when does this stop being true" rule (fast-path prerequisite).
8. **Async queue/poll/SSE (web jobs)** — note only; separate repo.

## 6. Acceptance (evidence checklist)

1. `stabilize_decision` never upgrades (property test), records `guardrail_reason` per override; risk-cap ≤ hold; score↔action validator flags documented mismatches.
2. PM confidence is capped when `data_quality` is stale/fallback/missing; integrity retry rebuilds per missing field (no blind re-roll).
3. Skill YAML loads hermetic; regime-from-opinion thresholds (≥70/≤30/35–65) derive without a model call; adjustments bounded + advisory.
4. Vendor router classifies market first, honors per-market priority string, first-success early return + gap-fill; breaker trips 3-fails/300 s and half-open probes; quote contract carries `fallback_from/stale/data_quality/missing_fields`.
5. News relevance scores planted items, boosts official sources, drops spam; coalescing dedups concurrent identical searches; degrade triple distinguishes failed vs empty.
6. `effective_trading_date` handles weekend/holiday/pre-close/post-close; nightly/batch resume via `(symbol, date)`; `--force-run` bypass; all-closed skip-with-log.
7. Report renders attribution weights + consensus + data_sources/models footers; decisions carry `watch_conditions`/`next_check_time`/`invalidation_conditions` (stop-breach, TP-review, staleness; `manual:thesis_reassessment` fallback).
8. Full suite hermetic (timers), ruff clean, docs/README/CHANGELOG true, trading_web mirrored, committed + pushed.

## 7. References

- Repo: https://github.com/ZhuLinsen/daily_stock_analysis (master, read 2026-09-02; README, AGENTS.md, SKILL.md, strategies/, docs/screening-engine.md, docs/research-artifact.md, templates/, plus sub-agent file:line reads of main/scheduler/trading_calendar/pipeline/api/notification/data_provider/search_service/analyzer/agent)
- Paper: arXiv 2608.26990 (Zhu & Shi, 2026-08-27) — "DSA: Evidence-Aware LLM-Agent Orchestration for Multi-Market Stock Research" (abstract read)
- Related: AlphaSift (screening reference), AlphaEvo (strategy backtest/evolution) — noted, not deep-read
- Web (2026-09-02): repo positioning/features context

---

## 8. Relationship to the merged Qlib+FinRL roadmap

This research is a **third teacher** on the same roadmap: the Qlib doc owns
PIT/factors/workflow, the FinRL doc owns stress/stop/contract/benchmark, DSA
owns **decision-quality mechanics** (post-decision guardrails, canonical
score↔action contract, confidence↔data-quality, report disclosure/
invalidation) and **operational robustness** (resume idempotency,
effective-date calendar, vendor health, news coalescing). None of it rewires
the graph topology or the overlay order; every adoption is default-off and
advisory, gated by the existing walk-forward/PBO policy where anything
learned is involved. Any implementation phase follows §3 module by module,
each with hermetic tests + docs-true + commit/push per the working agreement.
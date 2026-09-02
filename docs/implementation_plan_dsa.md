# Implementation Plan — DSA Research Adoptions (companion to `docs/design_daily_stock_analysis_research.md`)

**Status:** plan only — no code changed.
**Date:** 2026-09-02.
**Source:** `docs/design_daily_stock_analysis_research.md` (deep-research of `ZhuLinsen/daily_stock_analysis`, arXiv 2608.26990).
**Scope:** concrete, reviewable tasks for the §3 adoptions (decision guardrail + score↔action contract, confidence↔data-quality + integrity retry, skill-YAML overlays + regime-from-opinion, vendor routing/health, news relevance/coalescing/degrade, effective-date + resume idempotency, report disclosure/invalidation). Each task names exact files, function signatures, verified seams, tests, config keys, and the design §6 acceptance item it evidences. Everything advisory + default-off; no graph-topology or overlay-order change.

## 1. Ground rules (verified repo facts)

- Repo package `tradingagents/`; root `batch.py`/`pipeline.py`/`cli/main.py`; dev tools `scripts/*.py`. Tests `tests/test_*.py` with `pytest.mark.timeout` (hermetic).
- `py -3.12` only; no heredocs on Windows — `write`/`eval` for file edits (the edit tool has intermittently injected corrupt bytes; repair via byte-level `eval` when it does).
- Conventional Commits; **explicit `git add <paths>` only** — never `git add -A`.
- Config: `tradingagents/default_config.py` `DEFAULT_CONFIG` + env map + `.env.example` mirror for every new key. Web mirror: `trading_web/backend/capabilities.py`.
- Docs-true set (same commit): `docs/api_reference.md` §5/§6, `docs/developer/04-strategies.md`, `docs/AGENT_ONBOARDING.md`, `README.md`, `CHANGELOG.md`.
- Every new tool: `analysis_tools.py`/`news_data_tools.py` `__all__` → `agent_utils.py` re-export → graph ToolNode → web allowlist → docs.
- No-fabrication: `float | None`, explicit `"unavailable"`, min-obs guards.

## 2. Verified seams (checked against the repo this session)

| Seam | Verified anchor | DSA adoption |
| --- | --- | --- |
| PM structured output | `agents/schemas.py:188` `PortfolioDecision` (rating: `PortfolioRating` 5-tier enum :44; `confidence: float|None` ge0 le1 :224; `dissent` note :252) + render at :271 | add `guardrail_reason` (markdown render must keep headers); `data_quality` + `risk_cap` advisory fields |
| Rating scale | same file `PortfolioRating` (Buy/Overweight/Hold/Underweight/Sell) + `TraderAction` 3-tier :54 | versioned 0–100 ↔ rating scale table + validator (no new enum needed — validate against existing) |
| Confidence source | `SentimentReport.confidence` `Literal["low","medium","high"]` :419 (existing data-quality language) | PM confidence capped when data quality stale/fallback/missing; reuse vocabulary |
| Structured bind | `agents/utils/structured.py` `bind_structured` + `NO_EXTERNAL_TOOLS` (onboarding §structured) + truncation retry (tests/test_truncation_retry.py) | per-field integrity retry follows the same rebuild fabric |
| Vendor router | `dataflows/interface.py:535` `route_to_vendor` (category→vendor, fallback), `:662` `route_to_vendor_typed` `VendorResult`, `get_category_for_method` :511 | market classifier + per-market priority + `fallback_from/stale/data_quality` fields on the typed result |
| Vendor cache | `dataflows/vendor_cache.py` (TTL) | breaker + negative-cache semantics per (market, vendor) |
| Quote validator | `dataflows/market_data_validator.py` `build_verified_market_snapshot` :62 | honesty fields feed the snapshot/report footer |
| Report render | `reporting.py:393` `write_report_tree` + `:204` `audit_decision_numbers` (claim-vs-computed) | attribution/consensus/disclosure blocks land next to the existing audit note |
| Nightly | `scripts/nightly_review.py:99` `main` (--mode batch/recent, --prior-date, --skip-llm) | effective-trading-date + (symbol,date) resume keying + `--force-run` |
| Batch cadence | `batch.py` (thread-pool per symbol, batch_summary rows) | output-gate + distinct failure reasons (already partially there) |
| News tools | `agents/utils/news_data_tools.py` `get_news` :9 / `get_news_sentiment` :27 / `get_global_news` :43 | relevance scoring is a NEW pure module consumed by existing tools' render (degrade triple in the string) |
| Overlays | `strategies/overlays.py` `build_strategy_overlays` :20 / `fold_*` :96-165 / `apply_overlay_to_state` :167 | skill-YAML loads → numeric score adjustments become advisory fold inputs; regime-from-opinion derives from the trend-analysis structured read |
| Regime | `strategies/regime.py` `regime_gate_read` (vol percentile/trend label) | regime-from-opinion input (ma alignment + trend score from the technical opinion), no new model call |
| Structured context | `graph/trading_graph.py:1388` `_compiled_decision_context` | watch_conditions/next_check_time/invalidation lines injected (advisory) |

## 3. Dependencies (build order)

```
Phase A (decision quality — independent of the rest):
  decision_guardrail.py + PM-schema guardrail_reason/data_quality/risk_cap
   + score↔action validator + PM confidence gate + per-field integrity retry
Phase B (operational robustness — independent):
  vendor routing/health (market classifier + priority + breaker + stale fields)
   + effective-trading-date + resume idempotency (nightly/batch)
Phase C (analysis-layer polish — depends on a working bind + overlays):
  skill-YAML overlays + regime-from-opinion
   + news relevance/admission + coalescing-cache + degrade triple
Phase D (reporting — depends on A/B/C products):
  attribution/consensus/data_sources disclosure + watch_conditions/
  next_check_time + invalidation_conditions stored with the decision
Phases A-D are independent slices (parallelizable); each ships as its own
commit after its own approval.
```

## 4. Phase A — decision quality (design §3.1–§3.2; acceptance §6-1/2)

### 4.1 `tradingagents/strategies/decision_guardrail.py` (new)
- `stabilize_decision(decision: dict, risk_rows: list[dict], technical_read: dict, flow_read: dict | None, ledger_state: dict | None) -> dict` — pure; **only softens/downgrades, never upgrades** (the invariant); each applied override appended to `decision["overrides"]` as `{reason, direction}`. Rules (DSA `stabilize_decision_with_structure` + risk-cap): (a) a `risk_rows` item with severity ≥ high → displayed action capped at hold (`risk_cap`), (b) buy/overweight near resistance without confirmed inflow → downgrade to hold, (c) sell/underweight near support without outflow → hold, (d) hold/watch score candidates re-bounded to a sane band (advisory). Returns the modified decision dict (copy, never mutate input).
- `validate_score_action_agreement(rating_value: str, score: float | None, scale_version="v1") -> {ok, expected, issue} | None` — the versioned 0–100 ↔ 5-tier `PortfolioRating` table; mismatch → advisory issue (never a silent fix). Scale: 80–100 Buy, 60–79 Overweight, 40–59 Hold, 20–39 Underweight, 0–19 Sell (documented; the actual bands validated against repo convention).
- Wire: in `action_report` render path after the PM decision is assembled (advisory `guardrail` block); config `enable_decision_guardrail` (False) + `decision_guardrail_scale_version` ("v1").
- Tests `tests/test_decision_guardrail.py`: **property/invariant test — for any planted decision+risk+technical inputs, the output rating is never more bullish than the input**; risk-cap ≤ hold; near-resistance-no-flow downgrade; near-support-no-outflow → hold; validator flags documented mismatches and passes matching pairs; None/degenerate inputs → decision unchanged with no fabricated override (design §6-1).
- Acceptance: §6-1.

### 4.2 PM schema + confidence/data-quality gate (extends `agents/schemas.py`; `structured.py`)
- `PortfolioDecision` gains optional fields: `data_quality: Literal["fresh","stale","partial","unknown"] | None = None`, `guardrail_reason: str | None = None`, `risk_cap: str | None = None` — all advisory, render preserves the exact markdown headers (the render at :271 must keep `**Rating**` etc. for downstream parsers).
- PM confidence gate: `confidence` is capped (e.g. ≤0.7) when `data_quality` is not fresh AND a computed `data_quality` flag from the market snapshot is stale/fallback/missing — a deterministic post-hoc check in the render path, plus the prompt gains the DSA "confidence must not be high when any slice is stale/fallback/missing" rule.
- Integrity retry: `structured.py` bind path gains a per-field targeted rebuild on missing mandatory fields (original prompt + prior response + per-field spec) before truncation-retry fallback — reuse the existing `test_truncation_retry` fabric (add `tests/test_integrity_retry_per_field.py`).
- Tests `tests/test_pm_decision_schema.py`: schema accepts the new optional fields (back-compat: old decisions without them still render); confidence cap triggers on planted stale data quality; per-field retry rebuilds exactly the missing field spec (design §6-2).
- Acceptance: §6-2.

## 5. Phase B — vendor routing + health + calendar/resume (design §3.4 + §3.6; acceptance §6-4/6)

### 5.1 `tradingagents/dataflows/market_router.py` (new; extends `interface.py`)
- `market_for_symbol(symbol: str) -> str` — pure classifier (US ticker patterns: straight alphanumerics/^prefix indices etc.; CA suffix `.TO/.V`; exchange-suffix `.L/.PA` etc. as the fork actually supports) — default "US" for anything unrecognized (fail-open).
- Per-market priority: config string `MARKET_SOURCE_PRIORITY` (dict market → comma vendor list, default `{"US": "eodhd,tiingo,yfinance,moomoo"}`) read by `route_to_vendor` when set; unconfigured sources skipped; **first-success early return + `_SUPPLEMENT_FIELDS` gap-fill** (missing fields filled from the next source in priority, e.g. moomoo fills volume_ratio after eodhd price).
- `VendorResult` (`route_to_vendor_typed`) gains `fallback_from`, `is_stale`, `stale_seconds`, `data_quality`, `missing_fields` (extend the existing typed wrapper; `market_data_validator.build_verified_market_snapshot` consumes them for the honesty footer).
- Config: `market_source_priority` + `vendor_breaker_max_failures` (3) / `vendor_breaker_cooldown_seconds` (300) / `vendor_breaker_half_open` (True) + `vendor_negative_cache_ttl` (900). Default behavior unchanged (route falls back to the current global chain when no priority configured).
- Breaker: `strategies/`-place pure breaker state module `dataflows/vendor_breaker.py` (per (market, vendor): fails/cooled-until/half-open probe) — thread-safe, in-process.
- Tests `tests/test_market_router.py`: classification (US/CA/exchange-suffix/unknown→US); priority honoring (config order + skip-unconfigured); first-success early return + gap-fill merge (planted vendors: primary returns partial, secondary fills the gap); breaker trips at 3 fails, half-open probe passes/fails, cooldown expiry (design §6-4).
- Acceptance: §6-4.

### 5.2 `tradingagents/dataflows/effective_date.py` (new)
- `effective_trading_date(region="US", ref_utc=None, force_run=False) -> str` — pure: non-trading day → previous session; before market close → previous session; after close → current session; **fail-open** to the market-local calendar date when no calendar source is available; `force_run=True` returns ref date. Uses a provided minimal holiday/session table for the region (no new dependency; exchange-calendar lib optional — mirror DSA's optional import gate).
- `should_skip_all_closed(regions) -> bool` — all relevant markets closed → True (skip with log).
- Wire: `scripts/nightly_review.py` + `scripts/pre_market_review.py` key decisions by `(symbol, effective_date)`; rerun skips completed symbols (`has_today_report` check), finishes missing; per-run **frozen reference time** (captured once at run start). `--force-run` flag bypasses the calendar skip (documented escape hatch).
- Tests `tests/test_effective_date.py`: weekend/holiday/pre-close/post-close cases with a planted session table; fail-open with no table; all-closed skip; force-run bypass; resume idempotency — a rerun with one completed symbol runs only the missing one (design §6-6).
- Acceptance: §6-6.

## 6. Phase C — analysis polish (design §3.3 + §3.5; acceptance §6-3/5)

### 6.1 Skill-YAML overlays + regime-from-opinion
- `tradingagents/strategies/skills.py` (new) + `data/skills/*.yaml` (bundled example skills `ma_bull_trend.yaml`, `volume_breakout.yaml`, `shrink_pullback.yaml` — DSA-style): loader (pure, hermetic) verifying `name/instructions`, optional `category/core_rules/required_tools/market_regimes/default_priority`, and optional `score_adjustments` (numeric, e.g. `{entry: +12, sector_resonance: +5}` — **bounded ±20, advisory only**). YAML via `pyyaml` (already a dep).
- `regime_from_opinion(technical_opinion: dict) -> str` — pure thresholds on the trend-analysis structured read: ma bullish & trend_score ≥ 70 → "trending_up"; bearish & ≤ 30 → "trending_down"; 35–65 → "sideways" (DSA defaults.py/router.py thresholds); unknown → None (fail-open).
- Router: `select_skills(skills, regime, requested: list[str] | None, default_priority) -> list[str]` — precedence user-requested → regime-matched → priority-sorted default; cap ~3.
- Fold: numeric adjustments become advisory fold inputs into `overlays.fold_*` behind `enable_skill_overlays` (False) + `skill_dir`; the hard gates stay the authority.
- Tool `get_skill_read(skill_id, ticker)` (market) → renders the skill's instructions + its computed adjustments (advisory); web value-tools mirror.
- Tests `tests/test_skill_overlays.py`: YAML load + schema reject on missing name; regime thresholds (≥70/≤30/35–65, unknown); router precedence + cap; adjustments bounded; unknown skill → explicit unavailable (design §6-3).
- Acceptance: §6-3.

### 6.2 News relevance + admission + coalescing + degrade triple
- `tradingagents/strategies/news_relevance.py` (new, pure): `score_news_article(title, url, snippet, ticker, company_name) -> {score, reasons[]}` — ticker-in-title +55 / snippet +34 / url +18; company-name title +45 (ambiguous names +26); **official-source boost +8** (sec.gov, nasdaq.com, nyse.com — the sources the fork already consumes; plus the CN official hosts irrelevant here); macro-term −12; clamp 0–100; max 5 explainable reasons. `admit_article(title, url, content_signals, is_official) -> bool` — drops app-download/spam-like pages unless official.
- Coalescing cache `dataflows/news_cache.py`: `{key: (ts, result)}` TTL 600 s cap 500; owner-wait event coalescing (first caller owns, waiters wait ≤30 s, only successes cached, hits attributed `provider=SearchCache`). Key = `(query, target, days)`.
- Degrade triple in the news tool strings (`get_news`/`get_global_news`): `all_failed` (explicit "news search failed") vs `empty` ("no news found in window" — a valid result) vs `unavailable` (feature off / no sources) — **"no news" never means "search failed"**.
- Config `enable_news_relevance` (False) — default OFF for scoring; the degrade-triple honesty is ALWAYS on (tool-string change, no gate).
- Tests `tests/test_news_relevance.py`: planted items scored + admission (official URL passes, app-download spam dropped); boost exactness; coalescing dedupes concurrent identical searches (threaded test); degrade triple across planted provider results (design §6-5).
- Acceptance: §6-5.

## 7. Phase D — report disclosure + invalidation (design §3.7; acceptance §6-7)

- `reporting.py` `write_report_tree` + `action_report` gains advisory blocks:
  - `signal_attribution` — computed driver weights (from the composite-regime-flow reads: technical/news/fundamental/market — pure sum-to-100, never narrated) + strongest bull/bear computed signals.
  - `consensus` — supporting/opposing readout from the existing debate + skill overlays (the debate already computes agreement; render a per-side list).
  - Disclosure footers: `data_sources` (which sources contributed vs empty) fed by `VendorResult.data_quality`/`_SUPPLEMENT_FIELDS` (Phase B), `models_used`.
  - `watch_conditions` + `next_check_time` from the PM decision → feeds the fast-path T1/T2 cadence ("why HOLD / when to re-check").
- **`invalidation_conditions`** — stored with the decision (`full_states_log`): stop-loss breach (from the stop), take-profit review (from the target), data-staleness thresholds (from `data_quality`), else `manual:thesis_reassessment` fallback. Consumed by the fast-path HOLD/UPDATE/ESCALATE ("when does the prior HOLD die") + pre-market review.
- Config `enable_report_attribution` (False) + always-on honesty footers (sources/models — no gate).
- Tests `tests/test_report_disclosure.py` (attribution sums 100; sources/models footers present; watch_conditions render) + `tests/test_invalidation_conditions.py` (each decision carries ≥1 invalidation; stop-breach generates a price condition; staleness generates a data-quality condition; `manual:thesis_reassessment` fallback) (design §6-7).
- Acceptance: §6-7.

## 8. Definition of done (per phase + final)

- Per phase: hermetic tests named above green (`py -3.12 -m pytest tests/test_<module>.py -q`), ruff clean, config mirrors (`default_config.py` + `.env.example`), tools bound + re-exported + web-mirrored, docs-true set updated in the same commit, explicit `git add` of touched paths, Conventional Commit, push.
- Final gate (design §6-8): full suite hermetic, ruff clean, docs/README/CHANGELOG true, trading_web mirrored, pushed. Acceptance §6-1…§6-8 evidenced by the named tests.

## 9. Risks & sequencing notes

- **Guardrail must never upgrade** — property-tested invariant; the code path only ever maps to a strictly weaker rating/action; if a new rule would upgrade, it is rejected at review. Never touches the governor (hard gate unchanged).
- **Vendor router is the riskiest slice** — default behavior MUST be bit-identical when `market_source_priority` is unconfigured (regression test against the current chain); the priority feature is opt-in config only. Breaker state is in-process (ok for one batch run; note multi-process behavior like DSA's own doc).
- **Skill-YAML adjustments are advisory folds** — bounded ±20, default-off; the hard overlay pipeline (regime→catalyst→contract→governor) stays the authority and is unchanged.
- **Degrade triple changes tool strings** — audit the news tool callers/tests (`test_news_lookahead` etc.) so the new vocabulary doesn't break existing assertions; always-on honesty is part of this phase.
- **Confidence cap touches the PM prompt** — prompt change must keep the structured schema back-compatible (optional fields only) and the render headers identical (downstream report parsers).
- **Parallelization**: Phases A–D are independent slices — safe to fan out to subagents with one integration owner for tests+docs+web; the guardrail + PM-schema slice (A) and the vendor slice (B) are the sharpest — do them with full context.
- **No execution, no A-share sources, no push/web app** (design §4): only the *patterns* transfer; anything learned stays behind the existing walk-forward/PBO gate.
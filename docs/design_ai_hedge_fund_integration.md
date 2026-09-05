# ai-hedge-fund (virattt) — Teacher Study for TradingAgents

Status: **design study only — no code changes.** Direct-source study of
`github.com/virattt/ai-hedge-fund` v2.2.0 (`hedge_fund/`: `data/`,
`signals/`, `llm/`, `features/`, `fund/`, `strategies/`, `portfolio/`,
`risk/`, `brokers/`, `pipeline/`, `backtesting/`, `event_study/`,
`validation/`, `tui/`), plus web grounding on the current multi-agent state.
Everything here is **advisory and opt-in**; the fork's "no execution,
advisory-first, deterministic-over-LLM" mandates are unchanged. Where the
study validates existing fork work, that is stated explicitly (a few places
the fork is already ahead).

---

## 1. The one-paragraph takeaway

ai-hedge-fund v2 rebuilds itself around three ideas the fork already shares:
the **LLM never touches the trade** (agents form views; deterministic code
sizes and places; risk limits are hard gates — identical to the fork's
no-execution mandate and advisory-analyst design), **same-code-path
truthfulness** (a backtest is the live cycle looped over history — only the
clock and broker change; identical to the fork's backtest reusing the live
fill/tradability layer), and **typed views** (every analyst — persona LLM or
quant model — implements one `AlphaModel.predict → Signal` interface:
conviction in [-1,1] + reasoning + components + metadata, with **abstention
recorded distinctly from neutral**). The most transferable surface is the
declarative **mandate**: a fund is data — a YAML spec binding strategies ×
models × blend policy × risk limits × capital × rebalance cadence ×
benchmark — so the same pipeline can run one cycle, a backtest, or a
recurring fund, pointed at any tickers.

## 2. What ai-hedge-fund does that the fork already implements (validated)

| ai-hedge-fund mechanism | Fork equivalent | Verdict |
| --- | --- | --- |
| Validation plans (`validation/` CPCV + PBO are "planned" in their roadmap) | `strategies/evaluate.py`: `purged_cpcv_splits` + `cpcv_overfit_mask` + `oos_split` + `walk_forward_splits` + `pbo_flag` + `deflated_sharpe`, gated by `scripts/evaluate_config_gate.py` | **fork is ahead** — the entire validation roadmap slot is already shipped + gated |
| `AlphaModel.predict → Signal` (conviction -1..1) | `consensus.rating_to_number` + `agreement_score` + G3 consensus + `strategies/quant_baseline.py` (deterministic quant rating) | partial — the abstention-vs-neutral semantics (§3.3) is the new nugget |
| Risk limits: per-position cap + gross-exposure clamp, clamped exposure **stays in cash** (not redistributed) | `portfolio.capped_weights` (excess to cash), `risk_governor.govern` PASS/WARN/REJECT, book position caps, sector caps | already adopted; the per-clamp **audit event** (§3.4) is new |
| Point-in-time by construction (data filtered on **filing date**; PEAD drops stale filings; the prompt says "treat the filing date as today") | `effective_date`, PIT snapshots, `data_quality.fundamentals_pit_ok` fail-closed, `date_window` content window | validates; the prompt-level PIT instruction is a cheap extra (§3.2 note) |
| `CachedDataClient` disk cache (only successes cached, errors propagate, refresh override) | `vendor_cache` disk TTL (successes only, sentinels never cached) + `_RUN_OHLCV_CACHE` | already adopted; warm-offline reruns are implicit in the fork's 6h TTL |
| Multi-LLM provider registry (`llm/registry.py` + `api_models.json`) | `llm_clients/` provider registry (14 providers, capability matrix) | fork is ahead |
| Backtest metrics: total/annualized return, Sharpe, max drawdown, win rate | `evaluate.py` (Sharpe/Sortino/Calmar/PSR/IC/decay/walk-forward + benchmark hierarchy + with/without-cost) | fork is far richer |
| Same-code-path backtest vs live (only clock + broker change) | `scripts/backtest_strategy.py` reuses `market_tradability` fills; the fast-path T1 design reuses prior reports | already the fork's philosophy |

## 3. Adoptable lessons (phase-gated, advisory-first)

### 3.1 — A declarative mandate: fund/strategy/model as data (A1, the flagship)

**What:** `fund/spec.py` + `strategies/*.yaml` + `FundSpec` define a whole
desk as YAML data, pydantic-validated with `extra="forbid"` (typos fail
loudly): fund = capital slices over strategies; strategy = a `BlendPolicy`
(conviction-weighted, optional market-neutral) over weighted models; plus
`risk` limits, `capital`, `rebalance` cadence, `benchmark`. The mandate
carries **no tickers** — it is a desk; tickers are a run-time input, and
every run records what it traded. The same spec drives one cycle or a
backtest at the rebalance cadence.

**Gap in the fork:** the closest analogue is the DSA-3 YAML strategy skills
(`strategies/skills/*.yaml`) — but those are single-strategy overlays, not a
composable funding of strategies with capital slices, blend policy, a
rebalance cadence and a benchmark. `pipeline.py` hard-codes its
universe→screen→rank→top-N→batch flow; the nightly/batch cadence is fixed by
schedulers, not by the mandate.

**Adopt (Phase-A1, advisory, default-off):**
- `strategies/mandate.py`: `MandateSpec` (pydantic, `extra="forbid"`) —
  `name`, `strategies: [{name, weight, models: [{name, weight}], blend}]`,
  `risk: {max_position_pct, max_gross_exposure}`, `capital`, `rebalance:
  daily|weekly|monthly`, `benchmark`. `load_mandate(path)` + a
  `strategies/mandates/` library (deep-value, earnings-drift, momentum-tilt).
- `pipeline.py --mandate file.yaml`: the mandate drives the flow — the
  screener/rank reads are the "models", the rebalance cadence is when it
  runs, weights become the allocator's capital slices. Same CLI output.
- A `scripts/mandate_rebalance.py` helper that renders "what this mandate
  wants today" (the target book), advisory.
- The mandate can name the fork's own deterministic reads (regime / knife /
  composite-rank / analyst-verdict) as models — its blend maps to the
  repo's composite-rank + consensus machinery.

### 3.2 — Event-study module: market-model CAR with significance (A2)

**What:** `event_study/` is a pure quant engine: fit the market model
(`R_stock = alpha + beta * R_market`) by OLS, abnormal returns
`AR_t = R_stock,t - (alpha + beta * R_market,t)`, cumulative abnormal return
over a window, one-sample t-test on the CARs and a percentile **bootstrap
CI** (is mean CAR != 0?). The repo uses it to research the earnings-drift
strategy.

**Gap in the fork:** `events.py` (`drift_side`, `post_earnings_play`,
`surprise_score`) and `catalyst.py` read the earnings move but never measure
the **significance of the post-announcement drift** vs a market model — the
drift read is asserted from the surprise sign, not validated against the
benchmark-relative pattern.

**Adopt (Phase-A2):**
- New `strategies/event_study.py` (pure, numpy): `market_model_fit`,
  `abnormal_returns`, `cumulative_abnormal_return(start, end)`,
  `car_ttest`, `car_bootstrap_ci` — all `float|None`-safe, min-obs guarded.
- Wire into the drift reads: `strategies/events.py` gains
  `pead_car_test(closes, bench_closes, surprise, drift_window=5)` returning
  `{car, t_stat, p_value, ci, significant}`; render in
  `get_earnings_event_read` ("the post-print drift is/isn't significant vs
  the benchmark"). New tool `get_event_study_read(ticker, window_days?)`
  (market + news analysts). Advisory; significance never gates.

### 3.3 — Abstention ≠ neutral, formalized (A3)

**What:** in `blend_signals`, an **abstained** signal
(`metadata.abstained = true` — LLM parse failure or insufficient data) is
excluded from numerator AND denominator of the conviction blend: "no
opinion" must not masquerade as "opinion: neutral". A real 0.0 (e.g. PEAD
outside its window) is a true neutral vote and dilutes. Every signal records
its abstained flag so the outer loop can skip. Data-layer errors PROPAGATE
(fail loud — a broken snapshot must never become a fake neutral view); only
LLM parse failures abstain.

**Gap in the fork:** the fork's convention is "unknown inputs render a row
n/a and never fail a gate" — close, but analysts produce prose and the
difference between "no opinion" and "neutral opinion" is not carried in the
computed context that feeds the manager/debate.

**Adopt (Phase-A3, small):** `consensus.py` adds
`agreement_weighted(views)` where a view = `{value: float | None,
abstained: bool}` — None/abstained rows are excluded from the mean and
counted as `n_abstained` (recorded, never treated as 0.0); expose
`n_abstained` in the computed decision context so "the desk had no view" is
distinguishable from "the desk is neutral". Default-off advisory row.

### 3.4 — Per-clamp risk audit events (A4)

**What:** `apply_limits` returns a `RiskResult` with
`ClampEvent(limit, ticker, before, after)` per clamp — every limit that
fired is explainable; the order is fixed (per-position cap first, then
proportional gross scaling; the scaling only shrinks, so it can never
re-violate the per-position cap) and the pair is idempotent.

**Gap in the fork:** the risk governor records a verdict + reasons and the
`risk_audit` ledger is hash-chained; but the individual clamps fired by
`portfolio.capped_weights` / `adjust_for_caps` / the size chain are not
emitted per-name with before/after values.

**Adopt (Phase-A4, small):** a pure `portfolio.clamp_events(weights, caps,
gross_cap) -> list[ClampEvent]` (+ `ClampEvent` dataclass) that
`allocation_block` / `get_allocation` render ("clamped AAPL 0.34 → 0.25;
gross 1.12 → 1.00, the excess stays cash") so every allocation read
explains its clamps the way the Governor's reasons already do. Default-off
advisory text.

### 3.5 — Prompt-level provenance vault (A5)

**What:** `llm/cache.py::PromptCache` is deliberately three things in one
(their locked design decision): a cache (re-running an agent over an
unchanged snapshot costs zero), the **audit persistence record** of the
exact system + user prompt and the exact response behind every Signal, and a
debug trail for parse failures. Keyed by `sha256(agent|model|system|user)`.

**Gap in the fork:** the fork's audit chain pins decision OUTPUTS
(`research_decision.json` hash, risk audit, alpha ledger, run_card with
provider/model) but never preserves the exact prompts + raw responses that
produced them — so a disputed decision cannot be replayed prompt-for-prompt.

**Adopt (Phase-A5, default-off, disk-gated):** `strategies/prompt_vault.py`
— `prompt_vault_append(section, agent, model, system, user, response,
parse_ok)` appends one JSONL row per run under `results_dir` (config
`enable_prompt_vault`), keyed with the run's `decision_hash` so the vault
rows link to `research_decision.json`. Advisory; never gates. A natural
complement to the `llm_cost` run-card estimates and hallucination forensics.

### 3.6 — Live-view streaming JSON decode (A6, optional small)

`llm/watch.py::ThesisStream` decodes an agent's half-written JSON answer
field-by-field so a live view can show signal/confidence the moment they
land and let the prose type itself out — read-only by construction, the real
parse always wins. Adopt (optional): a thin JS stream-decoder in
trading_web's job view. Lowest priority.

## 4. Explicit non-goals (reasons)

| ai-hedge-fund surface | Why not adopt |
| --- | --- |
| Live/paper brokers + order placement (Broker protocol, SimBroker) | the fork is explicitly **advisory-only**; TradingExecution is the phase-gated successor and a broker protocol belongs there, not in research |
| The TUI (textual fund builder + live backtest board) | the fork ships trading_web already; a TUI adds a second interactive surface |
| Persona LLM agents (Buffett / Graham voicing) | the fork already has priced analyst personas + structured debate; the lesson is the one-typed-`predict` *interface*, adopted in A1/A3 |
| Financial-Datasets data provider | the fork has its own vendor chains (moomoo / finnhub / eodhd / alpaca...); the lesson is the DataClient protocol seam, which `route_to_vendor` already is |
| Market-neutral / dollar-neutral short books | the fork is long-only advisory; the `market_neutral` blend flag stays a documented future knob, never adopted now |
| Per-call prompt **caching for cost** | risk of stale answers; adopt the *audit* half (§3.5), not the replay-for-cost half |

## 5. Phases (dependency-ordered, all advisory + default-off)

1. **P1 — Mandate spec (A1)**: `strategies/mandate.py` + `strategies/
   mandates/*.yaml` + `pipeline.py --mandate` + `scripts/mandate_rebalance.py`.
   Tests: mandate validation (extra-forbid typo rejection, strategy/model
   weight handling, unknown rebalance rejected), target-book rendering.
2. **P2 — Event study (A2)**: `strategies/event_study.py` + `pead_car_test`
   in `events.py` + `get_event_study_read` tool (+ trading_web Value Tools).
   Tests: market-model recovery on synthetic data, CAR window sum, t-test
   significance, bootstrap-CI sanity, min-obs → None.
3. **P3 — Abstention semantics (A3)**: `consensus.agreement_weightd` +
   `n_abstained` in the computed decision context. Tests: abstained-excluded
   vs true-neutral dilution, all-abstain → "no opinion" (not 0).
4. **P4 — Clamp events (A4)**: `portfolio.clamp_events` + render in
   `get_allocation` / `allocation_block`. Tests: per-name clamp, gross-scale
   idempotence, before/after values.
5. **P5 — Prompt vault (A5)**: `strategies/prompt_vault.py` (default off) +
   `run_card` link. Tests: row links to decision_hash; off ⇒ no writes.
6. **P6 — Web + docs**: trading_web mirror for the new tools/flag;
   api_reference / Strategies-index / AGENT_ONBOARDING.changelog /
   CHANGELOG / README synced per phase.

## 6. Honest limits

- **Persona creativity not adopted**: the study adopts the *interface* and
  the mandate/abstention/audit discipline, not novel anthropomorphic
  personas — the fork's debate + analyst personas already cover role
  diversity.
- **Market-neutral shorts not adopted now**: the blend policy adopts the
  long-biased variants only; the `market_neutral` flag is a documented
  future knob.
- **Model vocabulary is the fork's**: a mandate names the fork's own reads
  (regime / knife / composite-rank / analyst verdict), not the repo's
  PEAD/persona list; the mapping lives in the mandate docs.
- **No lookahead regression**: any `pipeline.py --mandate` wiring must reuse
  the fork's `effective_date` / PIT / sentinel gates — the mandate is a
  composition layer, never a bypass of the data gates.
- **Bootstrap CI cost**: the event-study bootstrap is bounded (fixed
  resamples) so it stays fast on the daily-bar frequency.

## 7. Validation & sequencing

Per phase: hermetic tests (`pytest-timeout`), `ruff` clean, affected suite
green, commit + push, docs true, trading_web mirrored where a tool/flag is
added. No behavior change when the mandate/event-study/abstention/clamp/
vault config keys are off (defaults off). Live smokes: P1
`py -3.12 pipeline.py --mandate strategies/mandates/deep-value.yaml --tickers AAPL --dry-run`
renders the target book; P2 `get_event_study_read('AAPL')` returns CAR +
p-value vs the benchmark.

Mapping: **A1 → P1**, **A2 → P2**, **A3 → P3**, **A4 → P4**, **A5 → P5**,
web/docs → P6. P2/P3/P4 are independent (batch where sensible); P1 is the
largest and lands first; P5 depends on the decision hash already shipping.
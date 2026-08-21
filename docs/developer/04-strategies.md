# 4. Strategies — the deterministic calculators

`tradingagents/strategies/*.py` are **pure, offline, deterministic functions**
that back the analyst tool loops and the post-graph overlays. No LLM is
involved. This is the "compute, don't narrate" core.

> **Plan specs** live in [`Strategies/`](../../Strategies/) — see
> [`Strategies/index.md`](../../Strategies/index.md) to map each plan doc to
> its implementation modules, config flags, and consumers.

## 4.1 Value & screening calculators

- `swing.py` — `swing_report`, `vcp_setup`: trend stack, RSI band, 1-ATR stop,
  2R/3R targets, volatility contraction.
- `relative_strength.py` — `relative_strength_report`: leading/uptrend/lagging
  vs SPY.
- `momentum.py` — pillars, first-pullback, RVOL, session flags (intraday).
- `regime.py` — regime gate (vol percentile / trend label).
- `sector_rank.py` — `--sector-rank` logic (SPDR top-3 by momentum).
- `size.py` — Kelly / vol-target / position sizing (position_sizing).
- `portfolio.py` — `value_ratio_weights`, cap adjustments (watchlist alloc).
- `normalized.py` — 5y median-margin EBIT + EV/EBIT + 5y PE percentile.
- `factors.py` — composite rank (EY + momentum + 52w).
- `dcf.py` — pragmatic FCF-DCF intrinsic valuation (WACC via CAPM, Gordon TV,
  EV->equity bridge) powering `get_dcf_valuation`.
- `journal.py` — `--journal` alloc/journal.

## 4.2 Overlays

- `overlays.py` — `build_strategy_overlays(config, closes)`, `fold_flow*`,
  `apply_overlay_to_state`, `record_reflection_outcome`.
- `size.py` — ATR/vol targets / Kelly sizing (`atr`, `kelly_fraction`).
- `book_risk.py` — `cvar` (tail budget).
- `catalyst.py` — `build_catalyst_snapshot`, `fetch_catalyst_data`
  (earnings/macro/Fed scale 0..1), `fold_catalyst_into_overlay`,
  hard-block (REJECT inside window).
- `events.py` — `post_earnings_play`, `surprise_score`, `drift_side`.
- `risk_governor.py` — `govern()` -> PASS/WARN/REJECT; `build_risk_snapshot`.
- `contract.py` — `build_position_contract` (size + stop from min(Kelly,
  risk/stop)*vol*flow*agree*catalyst).
- `calibration.py` — `fit_buckets` (ledger win-rate -> calibrated P).
- `consensus.py` — `agreement_score` (debate stances -> agreement).
- `debate_context.py` — `build_computed_context` (numbers into debate).
- `exits.py` — stop/BE/targets.
- `reflection.py` — ledger, analyst hit-rates.
- `orderflow.py` — `fetch_flow`, `summarize`, divergence/alignment/exhaustion.
- `sentiment.py` — `compute_social_scores`, `computed_sentiment_line`.

## 4.3 Evaluation

- `evaluate.py` — walk-forward splits, Sharpe, deflated Sharpe, PBO flag
  (used by `scripts/evaluate_config_gate.py` G5).

## 4.4 How strategies feed the graph

- **Pre-graph**: the analyst tool loops call `get_*` tools that wrap a strategy
  function (e.g. `get_swing_set` -> `swing.swing_report`).
- **Post-graph**: `_apply_strategy_overlays` calls several of these in an
  order (see `02-graph-workflow.md` §2.6).

## 4.5 Config flags that gate them

`enable_regime` / `enable_factors` / `enable_sentiment` / `enable_threshold_gate`
default OFF; all `enable_*` overlays default ON except those four. Catalyst
keys: `catalyst_*`. Risk: `risk_*`. Sizing: `position_sizing`, `target_vol`,
`risk_per_trade`, `atr_mult`, `kelly_fraction`.

## 4.6 Adding a new strategy

1. Create `strategies/<name>.py` with pure functions.
2. Add a unit test `tests/test_strategies_<name>.py`.
3. Optionally expose it as an analyst tool via `analysis_tools.get_<x>` and
   bind it in the applicable analyst's tool node + prompt.
4. Optionally fold it into the overlay pipeline in `_apply_strategy_overlays`.
5. Add the config flag + `.env.example` override.
6. Update README/CHANGELOG/docs.

Continue to [`05-agents-tools.md`](05-agents-tools.md).
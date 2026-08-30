# Decision Hardening Spec — compute, don't narrate

Audit findings (validated against the codebase) converted into an
implementation-ready spec. **Status: spec only — no code changed.**
Related: `strategies/enhancement_plan.md`, `tradingagents/agents/schemas.py`,
`tradingagents/strategies/*`.

## G1 — Deterministic position & stop contract

**Problem:** `PortfolioDecision.position_size` is free text ("5% of portfolio"),
`stop_loss` is an LLM-picked price (`agents/schemas.py`). Overlays compute
`position_scale` but never bind the numbers the user acts on.

**Goal:** the LLM argues the *thesis*; the pipeline computes *size, stop,
target*.

**Formula (contract = capped product of independent budgets):**

```
p_cal     = calibrated_confidence(decision.confidence)   # G2, identity when off
kelly     = position_size_kelly(p_cal, odds=1.0, fraction=0.25)     # size.py
stop      = close - atr_mult * ATR(high, low, close); stop_pct = 2*ATR/close
risk_size = risk_per_trade / stop_pct
vol_t     = clamp(volatility_target_scale(log_returns, target_vol), 0.0, 1.5)
flow_s    = 1 - distribution_score                              # orderflow.py
agree_s   = agreement_score(risk_team_stances)                  # G3 (1.0 when off)

size_pct  = min(kelly_min, risk_size) * risk_t * flow_s * agree_s
size_pct  = clamp(size_pct, 0.0, max_position_pct)
stop      = close * (1 - stop_pct)   # = 2*ATR stop
```

**API**

```python
# tradingagents/strategies/contract.py
@dataclass
class PositionContract:
    size_pct: float          # authoritative
    stop_loss: float | None  # absolute price
    stop_pct: float
    reason_parts: list[str]  # which budgets bound it (audit trail)

def build_position_contract(decision, cfg, ohlcv, flow_summary=None,
                            agreement=1.0, calibrated_p=None) -> PositionContract
```

**Integration:** a post-PM node in `trading_graph.py` runs the contract when
`enable_position_contract` is true; it (a) stores contract in
`final_state["position_contract"]`, (b) renders a
`**Position Contract**` block appended to `final_trade_decision` (LLM prose
kept above as rationale), (c) memory log stores `size_pct` + `stop_loss`
for later review. No hard veto — the contract is the *stated* number, the
LLM can only argue against it in `final_trade_decision`.

**Config** (`default_config.py`):
`enable_position_contract=false`, `risk_per_trade=0.01`,
`max_position_pct=0.30`, `atr_mult=2.0`, `target_vol=0.15`,
`position_odds=1.0`, `kelly_fraction=0.25`.

**Acceptance / tests (unit):**
- size ≤ min(kelly, risk/stop) budgets, bounded [0, max_position_pct]
- stop_speed-aware example: ATR=2 on close 100 → stop 96 → risk_size ≤ 25%
- distribution 0.79 → flow_s 0.21 (UNH live values)
- agreement 0.6 → size × 0.6
- cfg-off == pass-through (current behavior preserved)

## G2 — Confidence calibration

**Problem:** `confidence` is LLM self-feeling; no mapping to realized outcomes.

**Goal:** convert ledger outcomes into a per-bucket win-rate table; the PM
sees its own calibration and numbers are dampened by it.

**New module `strategies/calibration.py`**

```python
BUCKETS = [(0.00,0.50),(0.50,0.60),(0.60,0.70),(0.70,0.80),(0.80,1.01)]
def fit_buckets(entries) -> {bucket: {"n": int, "win_rate": float|None}}
def calibrated_confidence(p, table, min_n=5) -> float   # bucket win_rate; identity fallback
def calibration_table_text(table) -> str                # for the PM prompt
```

**Data flow:** extend decision-time stamping — when a decision resolves in
the memory-log/reflection path (`_update_memory_returns`), write
`{confidence, delta_r>` into `strategy_ledger.jsonl` (new `confidence`
field added to `record_reflection_outcome`; backward compatible).

**Wiring:** with `enable_calibration`, the PM prompt receives
`calibration_table_text` ("your 0.6–0.7 calls resolved 52%...") and Kelly
sizing (G1) uses `calibrated_confidence`.

**Config:** `enable_calibration=false`, `calibration_min_n=5`,
`calibration_buckets` (list of bounds).

**Acceptance:** monotone-ish table on synthetic data; fallback to identity
when n<min per bucket; no behavior change when disabled.

## G3 — Measured disagreement instead of binary consensus

**Problem:** `consensus: Literal["high","low"]` is a narrative flag.

**Solution:** compute `agreement_score` from the risk-team stances already in
`risk_debate_state` (aggressive/conservative/neutral ratings history) — e.g.
normalized range score:

```
arms = rating2num(stance) in {Buy:1, Overweight:0.5, ... Sell:-1}
agree = 1 - (max(ratings)-min(ratings))  # unit-stretch to [0,1]
consensus = "high" if agree >= 0.7 else "low"
```

**New `strategies/consensus.py`:** `agreement_score(ratings: list)` and
`consensus_from_score(score, high_at=0.7)`; reuse the rating vocabulary
(`agents/utils/rating.py` → `1/) in a shared `rating_to_number()` helper.

**Wiring:** when `enable_agreement`, the computed consensus replaces the LLM's
`consensus` field; `agreement` feeds the G1 size multiply.

**Acceptance:** exact on lists of extreme stances; disagreement (Buy vs Sell)
→ consensus "low" and size × ~0.

## G4 — Sentiment decay/velocity

**Problem:** `stocktwits.py` aggregates plain bull/bear counts; no freshness
weight, no author weight, no surprise vs baseline.

**Fix (`strategies/sentiment.py` additions):**

```
weighted_sentiment(messages)     # each msg: weight = 0.5^(age/half_life) * credibility factor
surprise_velocity(series)       # (current - 30d mean) / 30d std  (z-score)
decayed_weight(age_days, half_life=7.0)  # recency weight for a single post
```
`enable_sentiment` gates a `computed_sentiment_line` enrichment appended to the
news analyst's social tool output, and only when timestamps are present (RSS path
adds `None` → falls back to equal weights). Baseline window from the same
ticker's prior social fetches (persisted small rolling buffer in cache dir).

**Acceptance:** recency test — old contrarian post → negligible weight;
shock test — current z >> baseline → flagged.

## G5 — Threshold governance

**Rule:** every tunable threshold lives in `default_config.py` with a type,
a unit, and a unit test. Tuning must go through `strategies/evaluate.py`:
walk-forward split + `deflated_sharpe`/`pbo_flag` gate (`enable_threshold_gate=true`
before accepting any new default).

**Deliverables:** move ad-hoc constants to config keys;
`scripts/orderflow_evaluate.py` (ledger win-rate/alpha) and a new
`scripts/evaluate_config_gate.py` report, in any threshold proposal, the
mis-fit risk.

**Acceptance:** config schema test enumerates thresholds; `pbo_flag` false
for any default we ship.

## Sequencing & gates

1. G1 contract (module+unit → graph node → regression)
2. G2 calibration (module tests → stamping migration → PM prompt → regression)
3. G4 (consensus + sentiment, module tests → wiring → regression)
4. G5 (configification + gate script → regression)

All toggled off by default; each phase: unit tests per step, full pytest
with `timeout`, README/CHANGELOG, commit/push — same flow as prior phases.

## Out of scope (deliberately)

- Replacing `parse_rating` (deterministic already)
- Changing analyst prompts wholesale
- Real brokerage/DarkPool data (moomoo flow is intraday buckets)
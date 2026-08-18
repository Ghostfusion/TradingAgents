# TradingAgents Enhancement Plan (researched)

Phase-by-phase implementation plan for 8 researched trading-method threads.
Status fields track implementation; all phases are config-gated and off by
default so existing behavior is unchanged. Run per-phase unit tests offline.

Sources: arXiv (FinMem 2311.13743; Reflexion 2303.11366; MAR 2512.20845;
TradingGroup 2508.17565; HMM bull/bear 2007.14874; HMM+NN 2407.19858; PEAD
2009.03094; media tone 2110.10800; claims 2402.11728; vol-target smoothing
2212.07288; CVaR-RL 2109.14438; backtest overfitting 1408.1159, 1905.05023,
2209.05559; LLM news sentiment 2602.00086; WSB 2101.12110; StockTwits
2004.11686; FinMM 2402.18485; F2-Agent 2608.05668; FLAG-Trader 2502.11433) plus
classics: Hamilton 1989, Kelly 1956, Asness-Moskowitz-Pedersen 2009.

## Phase 0 - Evaluation harness (tradingagents/strategies/evaluate.py)
Cost-adjusted metrics: net returns, drawdown, CAGR, Sharpe, deflated Sharpe
(trial-count penalty), walk-forward splits, PBO-lite overfit flag.
Config: `evaluate_cost_bps` (default 10).

## Phase 1 - Market regime gate (tradingagents/strategies/regime.py)
Features: realized vol (21d percentile), 200-SMA trend; optional 2-3 state HMM
label when hmmlearn is installed. Gate scales position and flips analyst lens.
Config: `enable_regime` (default False).

## Phase 2 - Money management (tradingagents/strategies/sizing.py)
Quarter-Kelly from confidence; volatility targeting with smoothing; CVaR budget
across a book; ATR-based stops.
Config: `position_sizing` (kelly|vol_target|flat), `target_vol`.

## Phase 3 - Value + momentum composite (tradingagents/strategies/factors.py)
Cross-sectional momentum (12-1m), 52w-high distance, vol-adjusted; composite
rank folds value screens from scripts/value_screener.py.
Config: `enable_factors` (default False).

## Phase 4 - Event-driven earnings (tradingagents/strategies/events.py)
Surprise from calendar consensus; PEAD drift rules; catalyst-risk sizing.
Config: `enable_events` (default False).

## Phase 5 - Memory & reflection (tradingagents/strategies/reflection.py)
Post-trade ledger (debit/credit per analyst), score decay, episodic recall.
Config: `enable_reflection` (default False).

## Phase 6 - Alt data & multimodality (tradingagents/strategies/sentiment.py)
Sentiment velocity from social text + volume; ensemble consensus of N seeds.
Config: `consensus_seeds` (default 1), `enable_sentiment` (default False).

Wiring notes per phase are documented in this file's modules' doctrings; graph
node integration is done via small guarded hooks once a phase is validated in
the Phase-0 harness.

## Implementation status

- P0 evaluate.py (tests/test_strategies_evaluate.py) - 9 passing
- P1 regime.py (tests/test_strategies_regime.py) - 6 passing
- P2 size.py (tests/test_strategies_size.py) - 7 passing
- P3 factors.py (tests/test_strategies_factors.py) - 7 passing
- P4 events.py (tests/test_strategies_events.py) - 6 passing
- P5 reflection.py (tests/test_strategies_reflection.py) - 5 passing
- P6 sentiment.py (tests/test_strategies_sentiment.py) - 7 passing
- Config gates added to default_config.py (all off by default).
- Graph node wiring is intentionally deferred until full regression passes.

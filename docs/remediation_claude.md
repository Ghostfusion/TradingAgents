This is a well-architected system — the safety invariants (advisory-only, no-fabrication, downgrade-only guardrails, PIT discipline, hash-chained audit) are the right ones to have hardened first, and testing them as properties rather than just unit cases is a mature choice. Here's where I'd push on it.

## Research validity — the biggest gap

The system is very rigorous about *individual* computations (factor IC, rank-IC bench) but I don't see anything validating the **end-to-end agent pipeline's output quality** — i.e., does a "Buy" rating from the full analyst→debate→PM chain actually correlate with subsequent returns, net of the LLM's added noise? Things worth adding:

- **Closed-loop forward tracking**: log every decision, then automatically score it against realized price action N days/weeks later (rating calibration, not just factor IC). This is the natural, safe way to prove the system's advisory value without ever touching execution.
- **Multiple-testing / overfitting controls** for the factor research loop (`factor_proposal_loop.py`, `alpha_zoo.py`) — deflated Sharpe ratio, IC decay across time-splits, out-of-sample holdout enforcement. With 69 strategy modules and an automated factor-proposal loop, silent overfitting is a real risk.
- **Survivorship bias** in universe construction (pipeline top-movers/top-losers) — are delisted/halted tickers retained in backtests?

## Data integrity — one likely blind spot

PIT discipline is enforced for price/news (`pit_registry.py`, lookahead sentinel tests), but I don't see the same treatment for **fundamentals restatements**. Restated financials are one of the most common silent lookahead-bias sources in quant research — a 10-Q that later gets restated shouldn't leak the restated number into a historical analysis date. Worth confirming `fundamentals` reads are versioned/point-in-time the same way price data is.

## Backtesting realism

`backtest_strategy` does next-bar fills (good — avoids the obvious lookahead bug), but the doc doesn't mention:
- Transaction costs / slippage / market impact modeling
- Corporate actions (splits, dividends, spinoffs) reconciliation
- Borrow cost/availability for any short-side strategies
- Capacity constraints (does a signal still work at size, given liquidity?)

## Operational maturity

- **LLM cost/latency governance**: `run_card.json` logs which LLM was used, but no mention of token-spend budgets, per-run cost caps, or latency SLAs for the nightly driver.
- **Monitoring/alerting**: circuit breaker trips, stale-data thresholds, and invalidation-ledger events seem to be logged but not clearly *alerted* on. A production nightly system usually wants a push notification path, not just a JSONL you have to go read.
- **Prompt injection surface**: news/social text flows into LLM analyst prompts. Given real financial news APIs are public and unmoderated, an explicit test for prompt-injection resistance in ingested text (not just spam/relevance filtering) would be a reasonable hardening step.

## Feature ideas that fit the existing architecture

- **Uncertainty bands**, not just point estimates, on computed valuation/technical reads — a DCF fair value with a range is more honest than a single number, and fits the "no fabrication" ethos.
- **Portfolio-level aggregation view** across multiple single-ticker runs — sector/factor exposure and correlation when several reports are generated in one session, since `book_risk.py` already does CVaR at the book level.
- **Scenario/stress testing** (rate shock, sector rotation, vol spike) applied against a current basket, reusing the existing risk-debate framing.
- **Benchmark-relative framing** in the report card (vs. sector/index), since ratings currently read as absolute.

## Minor structural note

56 dataflow modules + 69 strategy modules + 146 tools is a lot of surface area for one repo. The `test_calc_agent_wiring` reachability gate is a good guardrail against dead code, but at this scale I'd also want a periodically-run **dependency/complexity report** (unused exports, circular imports) so the module count doesn't quietly become a maintenance tax — especially since docs (`api_reference.md`, `developer/04-strategies.md`, etc.) are kept in sync manually rather than generated.

If you want, I can go deeper on any one of these — the forward-tracking/calibration piece seems like the highest-leverage addition given how much rigor already exists everywhere else in the pipeline.
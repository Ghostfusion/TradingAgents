# Industry Practice Comparison & Suggestions

Research pass comparing the project's practices against (a) the TradingAgents
paper (arXiv 2412.20138) and (b) general trading-firm / hedge-fund practice
(Investopedia: risk management, VaR, Kelly, MPT, risk parity, diversification,
slippage, position sizing). Each section: what firms do → what the project has
→ suggestion.

---

## 1. Multi-agent LLM trading framework (TradingAgents paper)

**What the paper does:** LLM agents in specialized roles (fundamental /
sentiment / technical analysts, bull & bear researchers, risk team, trader),
a debate loop, and a risk-management team monitoring exposure. Claims
improvements in cumulative returns, Sharpe, and max drawdown vs baselines.

**What the project has:** the same architecture — 4 analysts, bull/bear
researchers, 3 risk debators, PM, trader, debate rounds, risk governor,
position contract, catalyst overlay. **Already aligned.**

**Suggestion:** the paper's key differentiator is the **debate + risk-team
synthesis**. The project already has this. The gap is **evaluation**: the paper
reports Sharpe/drawdown on a backtest; the project has `evaluate.py`
(walk-forward, deflated Sharpe) but it's not wired into a **scheduled
self-evaluation** of the agent's own decisions. Suggest a periodic
"strategy-quality report" that runs `evaluate.py` on the decision ledger and
feeds the result back into the PM prompt (the memory log already stores
decisions; add a computed quality line).

---

## 2. Risk management (hedge-fund practice)

**What firms do:**
- **VaR / CVaR** — estimate tail loss at a confidence level; CVaR (expected
  shortfall) is preferred because VaR understates extreme events.
- **Kelly criterion** — optimal bet size from win probability + win/loss
  ratio; not standalone (ignores diversification).
- **Position sizing** — risk-budget-based (risk per trade × account / stop
  distance), not just % of account.
- **Drawdown governor** — stop new risk when realized drawdown exceeds a limit.

**What the project has:**
- `book_risk.py`: `simple_var`, `cvar`, `portfolio_cvar`, `stress_loss`,
  `drawdown_gate` ✅
- `risk_governor.py`: PASS/WARN/REJECT on CVaR budget + drawdown + liquidity ✅
- `contract.py`: Kelly × risk/stop × vol × flow × catalyst × agreement,
  clamped to caps ✅
- `size.py`: `kelly_fraction`, `position_size_kelly`, `volatility_target_scale` ✅

**Suggestion:** the project is **strong here**. The one gap vs practice: firms
**stress-test the whole book** (correlated shock across positions), not just
single-name CVaR. `book_risk.stress_loss` exists but is only used for a single
name. Suggest wiring a **book-level stress test** (all open positions shocked
together) into the risk governor's snapshot, so the PM sees "if the basket
drops 10% together, the book loses X%".

---

## 3. Backtesting / overfitting prevention

**What firms do:**
- **Walk-forward analysis** — train on one window, test on the next, roll
  forward; the honest way to validate a strategy.
- **Deflated Sharpe** — penalize the Sharpe for the number of trials tried
  (Lopez de Prado), so a lucky backtest isn't mistaken for skill.
- **Paper trading** — run live signals without real money before committing.

**What the project has:**
- `evaluate.py`: `walk_forward_splits`, `deflated_sharpe`, `sharpe`, `cagr`,
  `max_drawdown`, `equity_curve` ✅
- `scripts/evaluate_config_gate.py` (G5 walk-forward/PBO) ✅
- `scripts/orderflow_evaluate.py` (ledger win-rate/alpha) ✅

**Suggestion:** the project is **strong here too**. The gap: **paper-trading
mode** — the web has `--dry-run` on pre-market/nightly, but there's no
"paper book" that records what the system *would have* done and compares it to
the real market over time. The pre-market ledger (`resolve_ledger`) is close;
suggest extending it into a **full paper-trading ledger** (record every
proposed entry/exit, mark to market daily, report realized-vs-paper P&L).

---

## 4. Execution / transaction costs

**What firms do:**
- **Slippage** — the difference between expected and actual fill; worse in
  volatile/low-liquidity markets; reduced with limit orders.
- **Transaction costs** — commissions + spread + market impact; must be netted
  from returns or a backtest is fiction.
- **Implementation shortfall** — the gap between the decision price and the
  actual execution price.

**What the project has:**
- `exits.net_of_cost(gross_return, cost_bps=10)` — nets 10bps from returns ✅
- `evaluate.net_returns(returns, cost_bps=10)` — nets costs in backtests ✅
- `liquidity_risk.py` — Amihud ILLIQ, float turnover, IWF (slippage proxy) ✅

**Suggestion:** the project **nets a flat 10bps** but doesn't **scale costs by
liquidity**. Firms charge more for illiquid names. Suggest: make the cost
model **liquidity-aware** — `cost_bps = base + k × ILLIQ` (or a function of
float turnover), so an illiquid name's backtest and position sizing reflect
its true execution cost. This is a small change to `exits.net_of_cost` /
`evaluate.net_returns` (accept an `illiq` param).

---

## 5. Pre-market / after-hours practice

**What firms do:**
- Pre-market (4am–9:30am) and after-hours (4pm–8pm) have **low liquidity,
  wide spreads** — institutional-dominated, retail order restrictions.
- **Opening range** — first ~15 min high/low; ORB breakout strategy.
- **Gap risk** — close-to-open discontinuity; plan for it with stops.

**What the project has:**
- `pre_market.py`: `premarket_gap`, `catalyst_window_read`, `reanchor_plan`,
  `review_decision` (CONFIRM/REVISE/REJECT) ✅
- `market_session.py` (new): `opening_range`, `gap_type`, `order_imbalance`,
  `premarket_liquidity`, `post_close_confirmation` ✅
- `pre_market_review.py` + `nightly_review.py` scripts ✅

**Suggestion:** the project is **now well-covered** after the market-session
module. The one practice gap: firms **don't trade the pre-market open with
market orders** (wide spreads). The project's `premarket_liquidity` flags thin
books, but the **pre-market reviewer doesn't yet suggest limit orders** when
liquidity is thin. Suggest: in `pre_market_review.py`, when
`premarket_liquidity` returns "thin"/"illiquid", append a "use limit orders /
reduce size" directive to the verdict reasons.

---

## 6. Portfolio construction

**What firms do:**
- **MPT** — maximize return for a given risk via diversification (correlation
  matters).
- **Risk parity** — allocate so each asset contributes equal risk (AQR,
  Bridgewater style).
- **Diversification** — measured by the correlation coefficient between
  assets.

**What the project has:**
- `portfolio.py`: `value_ratio_weights`, `capped_weights` (per-name + per-sector
  caps) ✅
- `book_risk.portfolio_cvar` — basket CVaR from the risk basket ✅
- `factors.composite_score` — value+momentum composite ✅

**Suggestion:** the project has **per-name and per-sector caps** but no
**correlation-aware allocation** (MPT/risk-parity). The risk basket
(`TRADINGAGENTS_RISK_BASKET_WEIGHTS`) is a fixed list, not optimized. Suggest:
add a **correlation-aware weight adjustment** — compute the pairwise
correlation of the basket names from their return series (the project already
fetches closes for `_basket_cvar`), and down-weight names that are highly
correlated with the rest of the book (a simple "correlation penalty" on the
weight). This is the highest-value portfolio-construction gap.

**Status: implemented + wired.** `portfolio.correlation_penalty` /
`mean_correlation` (commit 0cb22e3) compute the average pairwise correlation
of each name vs the rest of the book and down-weight names above the
threshold. The allocation plan now consumes it: `portfolio.allocation_block`
and the `get_allocation` analyst tool accept `returns_by_name` and apply the
penalty before the caps when `enable_correlation_penalty` is on (default
False; `correlation_threshold` 0.6 / `correlation_penalty_frac` 0.3); the
screener's `--alloc` builds return series from the run's OHLCV cache and passes
them through. Names without a measurable return series are never penalized
(no fabrication).

---

## 7. LLM hallucination / no-fabrication

**What firms do:** AI in finance is only trusted when outputs are **grounded in
computed numbers** — a model that invents a price or a ratio is unusable.

**What the project has:** the **no-fabrication contract** is central: every
analyst tool returns exact numbers or explicit "unavailable", the pre-market
arbiter is deterministic, and the LLM judge is advisory-only. **Already a
strength.**

**Suggestion:** the one hardening step firms would add: **a post-hoc
verification pass** — after the PM produces a decision, a deterministic checker
re-verifies every numeric claim in the decision against the tool outputs (the
project's `reporting._finalize_section` already flags truncation; extend the
idea to flag any number in the PM decision that doesn't match a computed
value). This is a "claim-vs-computed" audit.

---

## Summary — highest-value suggestions (ranked)

| # | Suggestion | Area | Effort |
|---|---|---|---|
| 1 | **Correlation-aware allocation** (down-weight names correlated with the book) | Portfolio | Medium |
| 2 | **Book-level stress test** (all positions shocked together in the risk snapshot) | Risk | Small |
| 3 | **Liquidity-aware cost model** (cost_bps scales with ILLIQ) | Execution | Small |
| 4 | **Paper-trading ledger** (record proposed trades, mark to market, compare) | Backtest | Medium |
| 5 | **Limit-order directive in pre-market review** when liquidity is thin | Pre-market | Small |
| 6 | **Claim-vs-computed audit** (verify PM decision numbers against tool outputs) | LLM safety | Medium |
| 7 | **Scheduled strategy-quality report** (run evaluate.py on the ledger, feed PM) | Evaluation | Small |

All 7 fit the project's deterministic-first, no-fabrication philosophy. Items
2, 3, 5, 7 are small; 1, 4, 6 are medium.

**Implementation status (all 7 shipped):**

| # | Suggestion | Status |
|---|---|---|
| 1 | Correlation-aware allocation | ✅ `portfolio.correlation_penalty` + wired into `allocation_block` / `get_allocation` / screener `--alloc` (opt-in `enable_correlation_penalty`) |
| 2 | Book-level stress test | ✅ `book_risk.book_correlated_stress`, surfaced in the risk snapshot + report risk-gate block |
| 3 | Liquidity-aware cost model | ✅ `exits.net_of_cost` / `evaluate.net_returns` accept `illiq` (Amihud) |
| 4 | Paper-trading ledger | ✅ `pre_market.ledger_track_record` (win rate / avg realized) + `scripts/strategy_quality_report.py` reads it |
| 5 | Limit-order directive in pre-market review | ✅ `pre_market_review.py` thin-liquidity directive |
| 6 | Claim-vs-computed audit | ✅ `reporting.audit_decision_numbers` (opt-in `enable_decision_audit`) |
| 7 | Scheduled strategy-quality report | ✅ `scripts/strategy_quality_report.py` (net-of-cost Sharpe / drawdown / win rate) |

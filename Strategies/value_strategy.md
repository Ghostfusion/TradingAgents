# Value Strategy: Master Watchlist -> Screened Candidates -> Analyst Pipeline

**Status:** plan + reference implementation (see below)
**Related:** [`Strategies/Math.md`](./Math.md) (source playbook) · [`tradingagents/dataflows/quantitative_scores.py`](../tradingagents/dataflows/quantitative_scores.py) · [`scripts/value_screener.py`](../scripts/value_screener.py)

This document turns the screening playbook in `Math.md` into an executable
strategy layered on top of TradingAgents' existing vendor pipeline
(`route_to_vendor`), so a generated watchlist feeds straight into the analyst
teams without writing a new data layer.

---

## 1. Objective

Produce a **master watchlist** of 30-50 value candidates per rebalance (Greenblatt
target), pre-filtered for cheapness *and* solvency, before any LLM analyst
prompts are spent on deep-dive analysis. The watchlist is the input universe;
the agents are the second stage.

**Pipeline:** universe -> screens (this doc) -> ranked watchlist -> `get_fundamentals` /
`get_income_statement` / `get_balance_sheet` deep dives -> agent debate.

---

## 2. Screen definitions (implemented in `quantitative_scores.py`)

All inputs are *canonical* line items mapped by the vendor layer
(yfinance CSV, moomoo markdown/JSON, alpha_vantage JSON). Missing items degrade
a screen to `n/a` — never a fabricated number.

### 2.1 Valuation

| Screen | Formula | Threshold / rule |
| --- | --- | --- |
| Earnings Yield (Magic Formula) | EBIT / EV | top decile within universe |
| Acquirer's Multiple | EV / EBIT | lowest first; hard cap < 8-10x |
| EV | MarketCap + TotalDebt - Cash | - |
| P/B (used with F-Score) | Price / Book | bottom 20-30% of universe |

### 2.2 Quality / solvency

| Screen | Basis | Threshold |
| --- | --- | --- |
| Piotroski F-Score | 9 binary signals | >= 7 (improving margins, liquidity, leverage) |
| Altman Z-Score | 1.2X1+1.4X2+3.3X3+0.6X4+1.0X5 | > 2.99 safe, < 1.81 distress |
| Beneish M-Score | 8 manipulation indices | M < -2.22 clean, > -1.78 suspect |
| Net-Net | MarketCap vs 2/3 x (CA - Liab) | MarketCap < 2/3 x net current assets |
| Shareholder Yield | (Div + Buyback + NetDebtRepay) / MarketCap | top quartile + FCF > NI |

### 2.3 Combination rule

Combine **one valuation filter + one quality filter** (per `Math.md` §2):

| Screen | Valuation | Quality |
| --- | --- | --- |
| Magic Formula | EBIT/EV top decile | ROIC > 20% (or F >= 7 fallback) |
| Acquirer's Multiple | EV/EBIT < 10x | Debt/Equity < 1.0 |
| Piotroski Quality Value | low P/B | F-Score >= 7 |
| Shareholder Yield | top quartile yield | FCF/NI > 1.0 |
| Net-Net | 2/3 x (CA - Liab) | positive operating cash flow |

---

## 3. Reference implementation

- `tradingagents/dataflows/quantitative_scores.py` — pure scoring functions:
  `beneish_m_score`, `altman_z_score`, `piotroski_f_score`, `enterprise_value`,
  `earnings_yield`, `acquirers_multiple`. Offline-tested in
  `tests/test_quantitative_scores.py` (synthetic canonical input; 4 passing tests).
- `scripts/value_screener.py` — watchlist CLI:
  ```
  python scripts/value_screener.py AAPL MSFT GOOG -d 2026-06-30
  python scripts/value_screener.py -f universe.txt -d 2026-06-30 -l 100
  ```
  It pulls each ticker through the **configured vendor chain**
  (`fundamental_data` defaults to `moomoo,yfinance`), translates vendor output
  (CSV / markdown / JSON / text) into canonical items, computes the screens
  above, ranks by earnings yield then EV/EBIT, and prints the ranked table.
  Missing rows -> `n/a` (the vendor chain is left to decide fallbacks; the
  screener itself never guesses).

---

## 4. Operating plan

1. **Universe:** start from a broad equity list (e.g. SP 500 constituents or a
   yfinance/Finviz export); feed `-f universe.txt`.
2. **Rebalance cadence:** monthly watchlist refresh, hold ~1 year per Carlisle's
   rules (sell losers early for tax-loss harvesting, winners long-term).
3. **Sizing:** equal-weight the top N (30-50); smaller caps -> higher expected
   return but more volatility (Carlisle).
4. **Two-stage analysis:** watchlist rows with non-`n/a` screens are promoted to
   the interactive CLI deep dive (`get_fundamentals` etc.), so analyst LLM budget
   is spent on screened names only.
5. **Risk gates:** drop names with Beneish M > -1.78 (manipulation risk) and
   Altman Z < 1.81 (distress) before promotion, regardless of cheapness.

## 5. Limitations & next steps

- `total_debt` vs `total_liabilities` row aliasing can overstate EV when a
  vendor omits the dedicated debt row; refine alias scoring (prefer exact row
  label, fall back to longest substring) in the screener.
- Prior-period canonical items are required for M-Score and F-Score deltas;
  the current screener fetches the annual statement once — a follow-up can
  request both periods from yfinance's `filter_financials_by_date` or moomoo's
  `num=8` window.
- Validation: backtest the ranked watchlist against the memory-log realized
  returns (moomoo trading-day calendar) over the last N rebalances.

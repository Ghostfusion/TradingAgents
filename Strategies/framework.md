## Techno-Fundamental Swing Trading Framework

This guide provides end-to-end operational instructions for executing multi-day to multi-week swing trades by combining technical market structure, momentum screening, fundamental quality filters, and event catalysts.

---

### Phase 1: Fundamental Screening & Universe Selection

Filter a universe of thousands of equities down to a high-conviction watchlist of institutional-grade stocks.

1. **Liquidity Thresholds:**
* Average Daily Volume (50-day SMA): $\ge 1,000,000$ shares.
* Share Price: $\ge \$15$ (eliminates micro-cap volatility and bid-ask slippage).


2. **Earnings & Sales Growth:**
* Quarterly EPS Growth (YoY): $\ge 20\%$.
* Quarterly Revenue Growth (YoY): $\ge 15\%$.
* Positive forward earnings revisions over the past 30–60 days.


3. **Institutional Sponsorship:**
* Positive net accumulation by institutional funds over the last 1–2 quarters.
* Return on Equity (ROE): $\ge 15\%$.


4. **Market Capitalization:**
* Focus on mid-to-large-cap names ($\$2\text{B} - \$100\text{B}$) with sufficient float to move on volume without extreme, illiquid gaps.



---

### Phase 2: Momentum & Relative Strength Filtering

Identify stocks demonstrating leadership against the broader market index (e.g., S&P 500 / SPY).

1. **Relative Strength (RS) Line Calculation:**
* Plot the ratio $\frac{\text{Stock Price}}{\text{SPY Price}}$ on a daily chart.
* **Rule:** The RS line must be in an established uptrend, making new highs before or simultaneously with the stock price.


2. **Market Correlation & Divergence:**
* When the broader market pulls back or consolidates, look for candidate stocks that hold sideways above major moving averages (indicating institutional accumulation).


3. **Sector & Industry Group Confirmation:**
* Confirm that the stock belongs to a top-performing sector (e.g., top 3 of 11 SPDR sectors) and industry sub-group over a rolling 1-month and 3-month window.



---

### Phase 3: Technical Analysis & Setup Identification

Evaluate price action, trend alignments, and volatility contractions on daily ($D1$) and 4-hour ($H4$) charts.

```
       Resistance / Pivot High ------------------ [ENTRY TRIGGER] (Breakout on 1.5x Vol)
                                 \  Pullback  /
                                  \  to EMA  /
       Rising 20-day EMA --------- \________/ --- [STOP LOSS] (Placed 1 ATR below swing low)

```

1. **Trend Architecture:**
* Stock price must trade above the rising 50-day and 200-day Simple Moving Averages (SMA).
* 20-day Exponential Moving Average (EMA) must be stacked above the 50-day SMA.


2. **High-Probability Entry Patterns:**
* **Moving Average Pullback:** Price orderly pulls back into the rising 20-day EMA or 50-day SMA on declining volume, followed by a bullish reversal candle (hammer, engulfing, or inside-bar breakout).
* **Volatility Contraction Pattern (VCP):** Successive price swings contract in depth (e.g., $15\% \rightarrow 8\% \rightarrow 3\%$) with diminishing volume before a breakout.
* **Breakout & Retest:** Price breaks out past a major horizontal resistance level on above-average volume, pulls back lightly to test previous resistance as support, and holds.


3. **Indicator Confirmation:**
* **RSI (14-period):** Operates between 45 and 70. Look for pullbacks where RSI resets to 40–50 during an uptrend without breaking below 40.
* **Volume Signature:** Breakout days must register at least $1.5\times$ the 50-day average volume. Pullback days must print below-average volume.



---

### Phase 4: Catalyst & Event-Driven Alignment

Ensure scheduled news events act as tailwinds rather than unmanaged gap risk.

1. **Earnings Calendar Check:**
* **Rule:** Never initiate a standard swing trade within 5 to 7 trading days prior to a scheduled earnings report to avoid binary overnight gap risk.


2. **Post-Earnings Announcement Drift (PEAD):**
* If a stock beats revenue and EPS expectations and gaps up on exceptional volume ($2.5\times+$ average), wait 3–5 trading days for an opening range consolidation, then enter on a break above the consolidation high.


3. **Macro / Regulatory Milestones:**
* Track scheduled macroeconomic releases (CPI, FOMC rate decisions) and sector-specific milestones (FDA advisory panels, key product keynotes). Ensure stops account for expected macro volatility windows.



---

### Phase 5: Trade Execution, Sizing & Risk Management

Apply strict mathematical limits to risk, stop placement, and profit realization.

| Metric / Rule | Specification | Execution Detail |
| --- | --- | --- |
| **Account Risk ($R$)** | $0.5\% - 1.0\%$ of total capital | The maximum dollar loss tolerated if the hard stop is hit. |
| **Stop-Loss Placement** | Structural invalidation | Set stop-loss 1 ATR ($14$) below the most recent swing low or moving average support level. |
| **Position Sizing** | $\text{Shares} = \frac{\text{Account Capital} \times \text{Risk \%}}{\text{Entry Price} - \text{Stop Price}}$ | Adjust share count dynamically based on the stop distance, not arbitrary dollar amounts. |
| **Target Asymmetry** | Minimum $2:1$ or $3:1$ $R:R$ | First profit target ($T1$) set at $2R$; second target ($T2$) set at $3R$ or trailed. |
| **Profit Taking & Trailing** | Scale-out + Trailing Stop | Sell $50\%$ of position at $T1$ ($2R$) and move the stop-loss on the remaining $50\%$ to break-even ($Entry$). Trail remaining shares behind the rising 20-day EMA until a daily close below it occurs. |
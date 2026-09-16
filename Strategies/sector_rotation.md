When market breadth fractures and dispersion between sectors widens, index-level trend following breaks down while **sector rotation, relative strength (RS), and mean-reversion models** thrive.

Rather than forecasting macro direction, quantitative and swing strategies exploit capital flow velocity, lead-lag relationships, and structural dispersion.

---

### Quantitative Architecture

Quant frameworks quantify cross-sectional momentum and mean reversion across sector ETFs (e.g., SPDR sectors) and their liquid constituents.

| Strategy Layer | Quant Signal / Metric | Execution Mechanics |
| --- | --- | --- |
| **Cross-Sectional RS Ranking** | 20-to-60-day relative return vs. $SPY$, normalized by 20-day ATR or rolling volatility ($z$-score). | Long top quintile sectors; short bottom quintile (or hedge via index delta). Rebalanced weekly/bi-weekly. |
| **Dispersion Trading** | Realized inter-sector correlation ($\rho_{sector}$) vs. index implied volatility ($VIX$). | Long single-stock/sector volatility while short index volatility when cross-asset correlation collapses. |
| **Lead-Lag Factor Modeling** | Vector Autoregression (VAR) or Granger causality on macro drivers (e.g., US10Y yield, DXY, crude oil). | Example: When 10Y yields spike, systematic triggers short Utilities/Real Estate and allocate long into Regional Banks or Energy before momentum fully prints. |
| **Ornstein-Uhlenbeck (OU) Mean Reversion** | Sector pair spreads (e.g., $XLE / XOM$, or cyclical vs. defensive ratios like $XLI / XLU$). | Calculate rolling cointegration ($ADF$ test). Enter mean-reversion trades when spread exceeds $\pm 2.0\ \sigma$. |

---

### Swing Trading Playbook

For discretionary or techno-fundamental swing traders operating on 3-day to 3-week horizons, sector-driven tape requires tracking **capital migration** rather than chasing late breakouts.

* **Tracking the Rotation Clock:**
* **Risk-On Expansion:** Outperformance concentrates in Technology ($XLK$), Consumer Discretionary ($XLY$), and Industrials ($XLI$).
* **Late-Cycle / Inflationary:** Energy ($XLE$) and Basic Materials ($XLB$) absorb capital flows.
* **Defensive Flight:** Capital rotates into Utilities ($XLU$), Consumer Staples ($XLP$), and Healthcare ($XLV$).


* **Relative Strength Divergence Setup:**
* When the broad index makes a lower low on a daily chart, scan for the sector making a higher low or holding above its 20-day EMA. The first sector to stop falling during an index pullback is almost always the prime driver of the subsequent rally.


* **Volume & Order Flow Confirmation:**
* Track cumulative volume delta (CVD) and institutional dark-pool prints on sector ETFs. If a sector drops on declining volume while absorbing large block bids at multi-week support, it indicates institutional accumulation during sector re-allocations.


* **The "Laggard Catch-Up" Trap:**
* Avoid buying bottom-tier sectors simply because they look "cheap." Strong sectors tend to persist longer than expected due to institutional rebalancing cycles, while weak sectors often become funding legs for new allocations.



---

### Risk Management & Portfolio Construction

* **Beta-Neutral Pairs:** Run dollar-neutral books within correlated sectors (e.g., Long the strongest semiconductor name vs. Short the weakest software name) to isolate alpha and eliminate index drawdown risk.
* **Factor Exposure Caps:** Set a hard ceiling on net sector exposure (e.g., no single sector exceeding 25%–30% of gross capital).
* **Cross-Asset Volatility Gates:** When overall sector dispersion spikes into a liquidity crunch (correlation abruptly shifts toward 1.0 across all assets), immediately scale down leverage and widen stop bands.

Are you looking to model this quantitatively (e.g., backtesting relative strength cross-sectional momentum) or establish discretionary swing scanning rules?

To build a reliable discretionary swing scanning framework for sector-driven markets, filter top-down: first isolate the dominant sector, identify institutional accumulation, and drill into leaders offering high reward-to-risk pullbacks.

---

### Step 1: Sector Universe & Relative Strength Filter

Run this scan daily at market close across the major sector ETFs ($XLK$, $XLC$, $XLY$, $XLI$, $XLE$, $XLF$, $XLV$, $XLP$, $XLU$, $XLB$, $XLRE$).

* **Relative Strength (RS) Line:** Plot `Sector / SPY` on a daily chart.
* **Rule:** The RS line must be sloped upward over the 20-day and 50-day windows.
* **Benchmark Trend Alignment:** Sector ETF must trade above its rising 20-day EMA and 50-day SMA.


* **Pullback Divergence Check:**
* When $SPY$ closes down 2+ consecutive sessions or undercuts a recent swing low, flag sectors closing green or holding above their prior day's high. These are your target rotation leaders.



---

### Step 2: Liquid Stock Universe Screener

Filter for constituent liquid equities within the top 2–3 outperforming sectors identified in Step 1.

| Filter Parameter | Threshold / Setting | Purpose |
| --- | --- | --- |
| **Market Cap & Liquidity** | Market Cap $\ge$ $2B$, 20-day Avg Vol $\ge$ 1.5M shares | Filters out low-liquidity slippage and manipulation. |
| **Trend Architecture** | Price $>$ 20-day EMA $>$ 50-day SMA $>$ 200-day SMA | Ensures strong multi-timeframe structural alignment. |
| **Relative Outperformance** | 20-day Performance vs. Sector ETF $\ge$ +2% | Isolates sector leaders rather than beta-riders. |
| **ADX / Trend Strength** | 14-period ADX $\ge$ 25 with $+DI > -DI$ | Confirms actionable trend velocity over choppy consolidation. |

---

### Step 3: Actionable Swing Setups

Do not chase stocks extended $>5\%$ above their 20-day EMA. Scan strictly for two entry conditions:

**Setup A: The RS Shelf / High Tight Consolidation (Breakout)**

* **Conditions:** Stock consolidates sideways for 5–15 sessions within $3\%–6\%$ of 52-week highs while its sector or the broader index pulls back.
* **Volume Footprint:** Daily volume contracts during the base ($\le 75\%$ of 20-day average volume).
* **Trigger:** Daily close or intraday clearance above the shelf high accompanied by at least $1.5\times$ average daily volume.

**Setup B: First Pullback to Rising 20-day EMA (Mean Reversion)**

* **Conditions:** A proven momentum leader retraces to test its rising 20-day EMA or a prior structural resistance-turned-support level.
* **Candle Confirmation:** A reversal signal at the moving average (hammer, bullish engulfing, or inside-day upward break).
* **Trigger:** Buy stop set 1 tick above the high of the reversal day.

---

### Step 4: Execution & Invalidation Rules

* **Stop-Loss Anchoring:** Anchor initial stops to market structure rather than arbitrary percentages. Set the stop directly below the swing low of the consolidation shelf or 1 ATR below the 20-day EMA entry pivot. Risk should rarely exceed $3\%–5\%$ of position equity.
* **Take-Profit Scaling:**
* **T1 ($1.5R$ to $2R$):** Sell $33\%–50\%$ of the position to lock in gains and finance the trade risk. Move the stop-loss on the balance to breakeven.
* **Runner:** Trail the remaining shares using a close below the daily 20-day EMA or a breakdown of the prior 3-day low.


* **Sector Kill-Switch:** If the parent sector ETF violates its 20-day EMA on heavy distribution volume, tighten stops immediately on all individual long positions within that sector regardless of their individual chart strength.

In fast-moving sector rotation cycles, standard fixed-percentage or wide moving-average trailing stops fail: they either get chopped out during normal intraday rebalancing or surrender too much open profit when institutional capital abruptly rotates out.

Effective rotation trailing frameworks must be **asymmetric**—loosely tracking price during the structural accumulation phase, then aggressively ratcheting tighter as momentum accelerates or relative strength peaks.

---

### Framework 1: Two-Tier Structural Ratchet (R-Multiple & EMA)

This framework shifts the trailing anchor based on trade maturity, ensuring you give the setup room to develop early while protecting capital once the trade achieves initial targets.

| Trade Phase | Trigger / Milestone | Trailing Anchor | Invalidation Logic |
| --- | --- | --- | --- |
| **Phase 1: Inception** | Entry to $< 1.5R$ | Prior swing low or entry-bar low $- 1.0 \times \text{ATR}_{14}$ | Structural breakdown of the base. |
| **Phase 2: Transition** | Price reaches $+1.5R$ to $+2.0R$ | Breakeven $+ 0.2R$ (or rising 10-day EMA) | Scale out $33\%–50\%$; trade becomes risk-free. |
| **Phase 3: Mature Trend** | Price $> +2.0R$ | Rising 10-day EMA (Daily close) | Daily close below 10-day EMA triggers full exit. |
| **Phase 4: Climax / Extension** | Price $> 2.5 \times \text{ATR}_{14}$ above 20-day EMA | Prior session low (trailing daily) | Locks in parabolic blow-off moves before rotation. |

---

### Framework 2: Relative Strength (RS) Exhaustion Exit

During sector rotations, an individual stock's nominal price often lags the underlying rotation signal. Monitoring the stock’s relative strength ratio against the benchmark ($Stock / SPY$) provides an earlier exit than nominal price action alone.

* **Relative Strength Ratio:** Compute $RS_t = \frac{\text{Close}_{\text{Stock}}}{\text{Close}_{SPY}}$.
* **RS Moving Average Envelope:** Plot a 10-period and 20-period EMA of the $RS$ line.
* **Systematic Trailing Rules:**
* **Warning Signal:** $RS$ ratio prints a lower high while nominal price prints a higher high (Bearish Relative Divergence). Tighten stops from the 10-day EMA to the low of the prior session.
* **Hard Stop Trigger:** Daily close of $RS_t$ crossing below its 20-period EMA. Exit $100\%$ of the position at the next market open, regardless of nominal chart support.



---

### Framework 3: Volatility-Adjusted Chandelier / ATR Step

A traditional Chandelier stop can be refined for rotation velocity by dynamically ratcheting the ATR multiplier downward as momentum increases:

$$\text{Stop Level} = \text{Highest High}(N) - (k \times \text{ATR}_{14})$$

```
Base multiplier:  k = 3.0  (While 14-period RSI < 60)
Trend tier:       k = 2.0  (When 14-period RSI is between 60 and 70)
Climax tier:      k = 1.2  (When 14-period RSI > 70 or sector ETF enters top decile extension)

```

* **One-Way Ratchet Rule:** The stop price can only move upward. If the formula yields a value lower than the previous bar's stop level, retain the previous value: $\text{Stop}_t = \max(\text{Stop}_t, \text{Stop}_{t-1})$.

---

### Framework 4: Sector Breadth Kill-Switch (Top-Down Override)

In rotation tape, individual stock setups are subordinate to sector-level liquidity drains. When institutional allocators liquidate a sector ETF, single-stock trailing stops are often gapped down.

* **Trigger Conditions:**
* Sector ETF breaks below its 20-day EMA on volume $\ge 125\%$ of its 50-day average.
* More than $60\%$ of constituents within the sector ETF fall below their 10-day EMAs on a daily close.


* **Execution:** Overrides all individual stock trailing stops. Immediately market-sell $50\%$ of all open positions in that sector and raise trailing stops on the remaining balance to the immediate prior session low.

The friction between intraday and end-of-day (EOD) trailing stops comes down to a direct trade-off: **noise filtering vs. catastrophic tail-risk protection**.

In fast sector rotations, institutional reallocations frequently trigger sharp intraday liquidity sweeps that reclaim key levels by 4:00 PM, while genuine sector liquidations can cascade several percentage points lower before the closing bell.

---

### Core Trade-Offs

| Execution Dimension | Intraday Hard Trigger (Stop-Market / Stop-Limit) | End-of-Day Close Confirmation (MOC / 3:45 PM Check) |
| --- | --- | --- |
| **Whipsaw & Shakeout Risk** | **High.** Vulnerable to morning algorithmic stop-hunts, bid tests, and intraday mean-reversion wicks. | **Low.** Effectively filters out intraday noise and false breakdowns that institutional dip-buyers absorb. |
| **Max Drawdown / Tail Risk** | **Capped.** Losses are strictly bounded to your predefined execution level, regardless of session momentum. | **Unbounded.** A high-volume distribution day or flash rotation can turn a planned $1R$ loss into a $-2.5R$ loss by the close. |
| **Execution Quality & Slippage** | Slippage spikes during fast sell programs as market stops trigger into thin intraday books. | High liquidity at the market close (closing cross / MOC) provides cleaner fills, but often at worse absolute prices. |
| **Psychological Friction** | **High regret from seller's remorse** when a stock wicks your stop by cents and finishes green. | **High stress during liquidation** watching an open position bleed throughout the trading day without intervening. |
| **System Automation** | $100\%$ hands-off; native broker stop orders handle execution without screen time. | Requires active monitoring near the close or scheduled automation running programmatic conditional orders. |

---

### Failure Modes in Fast Rotations

* **The Intraday "Stop Sweep" Trap:** Institutional desks executing dark-pool sector rebalancing routinely probe liquidity below obvious technical levels (e.g., 10-day EMA or prior day low) between 9:45 AM and 11:30 AM. Intraday triggers exit at the absolute low of the day, right before bids absorb the move and push price back above the trendline.
* **The EOD "Waterfall" Trap:** When institutional rotation out of a sector is broad and urgent (e.g., tech selloff into utilities), buyers step aside completely. A stock breaking its 20-day EMA at 11:00 AM may drop another $4\%–7\%$ before the closing auction, destroying trade expectancy.

---

### Hybrid Frameworks for Fast Rotations

Rather than adopting a pure binary approach, active swing systems combine elements of both:

**1. The Two-Anchor Structure (Catastrophe Stop + Soft Trend Stop)**

* **Intraday Hard Stop:** Kept wide at a disaster level (e.g., prior major structural pivot or $-2.5 \times \text{ATR}_{14}$). This protects against earnings blowups, sector-wide downgrades, or flash cascades.
* **EOD Trailing Trigger:** Key technical levels (10-day EMA or 20-day EMA) are monitored strictly on a **daily close basis**. If price closes below the level at 3:55 PM, exit via Market-on-Close (MOC) or on the next session open.

**2. The 30-Minute / Time-of-Day Rule**

* Ignore breaches during peak morning volatility (9:30 AM – 10:30 AM).
* Only honor an intraday stop if the price breaks the trailing level **and remains below it for 30 consecutive minutes** after 11:00 AM, confirming sustained distribution rather than an algorithmic sweep.

**3. Volatility-Buffered Intraday Triggers**

* Instead of placing hard stops directly at the moving average or pivot level, offset the intraday trigger by a fractional ATR buffer:

$$\text{Trigger Level} = \text{EMA}_{10} - (0.35 \times \text{ATR}_{14})$$


* This gives market makers room to sweep immediate chart stops without triggering your exit, while still cutting the position if genuine momentum selling takes over.

To mathematically optimize an ATR offset buffer $k$, frame the problem as an objective function that balances **trade retention** (avoiding premature shakeouts on false breaches) against **loss severity** (limiting catastrophic drawdowns on true breakdowns).

---

### Step 1: Formalize the Objective Function

Define the trailing stop price for an anchor level $L_t$ (e.g., rising 10-day EMA or structural shelf) as:

$$\text{Stop}_t(k) = L_t - k \cdot \text{ATR}_{14, t}$$

Where $k \ge 0$ is the buffer multiplier to calibrate.

For every historical trade $i \in \{1, \dots, N\}$, a breach event occurs at bar $\tau$ when $\text{Low}_\tau \le \text{Stop}_\tau(k)$. We segment outcomes into two distinct classes:

* **Type I Error (False Breakdown / Premature Shakeout):** The intraday low breaches $\text{Stop}_\tau(k)$, but the stock subsequently recovers to close back above $L_t$ and reaches profit target $T$. The lost opportunity cost is $P_{\text{target}} - P_{\text{breach}}$.
* **Type II Error (True Liquidation Slippage):** The stock suffers a genuine breakdown. Because the buffer $k$ delayed execution, the loss is larger by $k \cdot \text{ATR}_{14}$ compared to exiting directly at $L_t$.

Optimize $k$ by maximizing trade expectancy $\mathbb{E}[R(k)]$ or a penalized Sharpe/Sortino ratio:

$$k^* = \arg\max_k \left( \frac{\mu_{R(k)}}{\sigma_{R(k)}} - \lambda \cdot \text{CVaR}_{\alpha}(k) \right)$$

* $\mu_{R(k)}$: Mean trade return (in $R$-multiples) using buffer $k$.
* $\sigma_{R(k)}$: Standard deviation of trade returns.
* $\text{CVaR}_{\alpha}(k)$: Conditional Value at Risk (Expected Shortfall) at the $\alpha = 95\%$ or $99\%$ tail, penalizing catastrophic runaway losses.
* $\lambda$: Risk-aversion penalty parameter (typically $0.5 \le \lambda \le 1.5$).

---

### Step 2: Extract Empirical Intraday Breach Distributions

Rather than running a brute-force parameter sweep that risks overfitting, model the empirical distribution of intraday maximum adverse excursions below $L_t$.

For each session $t$ where an asset touches or undercuts $L_t$:

1. Measure the **Normalized Undercut Depth ($D_t$)**:

$$D_t = \frac{L_t - \text{Low}_t}{\text{ATR}_{14, t}} \quad \text{for } \text{Low}_t < L_t$$


2. Split the events into two empirical probability density functions:
* $f_{\text{reclaim}}(D)$: Distribution of maximum excursion for sessions that closed back above $L_t$ (noise/sweeps).
* $f_{\text{cascade}}(D)$: Distribution of maximum excursion for sessions that closed below $L_t$ and continued down $\ge 2.0R$ (structural failure).



Plotting these two distributions reveals the overlap:

```
Probability Density
  ^
  |      f_reclaim(D) [Sweeps]
  |       /\
  |      /  \        f_cascade(D) [True Liquidations]
  |     /    \            /\
  |    /      \          /  \
  |   /        \        /    \
  +--+----------\------/------\--------> Undercut Depth D (in ATR)
     0          k*    1.0    2.0

```

The optimal structural buffer $k^*$ lies at the **Neyman-Pearson decision boundary**—the threshold where the marginal cost of taking a larger loss on a true cascade equals the marginal benefit of staying in a winning trade:

$$\frac{f_{\text{cascade}}(k^*)}{f_{\text{reclaim}}(k^*)} = \frac{C_{\text{Type I}}}{C_{\text{Type II}}} = \frac{\mathbb{E}[\text{Gain if retained}]}{\mathbb{E}[\text{Excess loss on cascade}]}$$

---

### Step 3: High-Beta Dynamic Adjustments

In high-beta sectors ($XLY$, $XLK$, $XBI$), a static $k$ underperforms because intraday noise scales non-linearly with volatility regimes and market-open liquidity. Scale $k$ dynamically:

**1. Normalized Realized Volatility Ratio ($NVR$)**
When short-term implied or realized volatility decouples from longer-term ATR, expand the buffer:


$$k_t = k_{\text{base}} \cdot \left( \frac{\sigma_{5\text{d}}}{\sigma_{20\text{d}}} \right)^\gamma$$


*(Set $\gamma \approx 0.5$ to prevent excessive stop widening during panic spikes).*

**2. Intraday U-Shaped Volatility Smile ($VOD$)**
Between 9:30 AM and 10:30 AM EST, market makers sweep resting book liquidity. Incorporate a time-of-day decay factor:


$$k(t) = k_{\text{base}} \cdot \left( 1 + \delta \cdot e^{-\beta \cdot t_{\text{mins}}} \right)$$

* At the open ($t=0$), the buffer is widest (e.g., $1.5 \times k_{\text{base}}$).
* By mid-day ($t \ge 90\text{ min}$), the multiplier converges to $k_{\text{base}}$.

---

### Step 4: Python Implementation & Cross-Validation

Run a rolling walk-forward test (e.g., 6-month train, 2-month out-of-sample test) to avoid curve-fitting:

```python
import numpy as np
import pandas as pd

def optimize_atr_buffer(trades_df, k_range=np.linspace(0.1, 1.5, 29), alpha=0.05, lam=1.0):
    """
    trades_df columns:
      - 'undercut_atr': max depth below anchor level normalized by ATR
      - 'recovered': bool, True if price closed back above anchor and hit T1
      - 'cascade_loss_atr': total subsequent drop in ATR if trade cascaded
      - 'potential_win_r': R-gain if trade was not shaken out
    """
    results = []

    for k in k_range:
        returns = []
        for _, row in trades_df.iterrows():
            breached = row['undercut_atr'] >= k
            
            if breached:
                if row['recovered']:
                    # Type I error: Premature exit on a winner
                    returns.append(-k)  # Loss capped at the buffer exit
                else:
                    # Correct exit on true cascade (avoided deeper waterfall)
                    returns.append(-k)
            else:
                if row['recovered']:
                    # Successfully held winner
                    returns.append(row['potential_win_r'])
                else:
                    # Type II error: Held through cascade; exited at EOD/cascade stop
                    returns.append(-row['cascade_loss_atr'])

        r = np.array(returns)
        mean_r = np.mean(r)
        std_r = np.std(r) + 1e-6
        sharpe = mean_r / std_r
        
        # Calculate CVaR at 95% confidence
        cutoff = np.percentile(r, alpha * 100)
        cvar = np.abs(np.mean(r[r <= cutoff]))
        
        # Penalized objective function
        score = sharpe - (lam * cvar)
        results.append({"k": k, "score": score, "sharpe": sharpe, "cvar": cvar})

    res_df = pd.DataFrame(results)
    best_k = res_df.loc[res_df['score'].idxmax()]['k']
    return best_k, res_df

```

---

### Practical Rules of Thumb for High-Beta Names

* **Tight Consolidation Anchors:** When a stock forms a 10-day shelf, empirical optimization typically clusters $k^*$ around **$0.35$ to $0.50 \times \text{ATR}_{14}$**. Setting $k < 0.25$ triggers excessive stop-outs on standard quote spreads.
* **Extended Momentum Names:** When the stock is extended $> 2.0 \times \text{ATR}$ above its 20-day EMA, optimal $k^*$ compresses toward **$0.20 \times \text{ATR}_{14}$** or shifts directly to a trailing 1-session low. At high extensions, the priority shifts from trade retention to immediate capital preservation.

When a dynamic ATR buffer is added to a structural stop level, the stop distance is no longer a static chart coordinate—it becomes an **expanding or contracting stochastic variable**.

If position size is calculated using only the nominal chart pivot while the exit executes at the dynamic buffer, the realized loss will systematically exceed the target risk budget ($1R$). Sizing models must explicitly absorb this buffer into the unit risk calculation and account for fat-tailed execution slippage.

---

### Fixed Fractional Model with Dynamic Buffer

In a standard fixed fractional framework, dollar risk is capped at a fixed percentage of total portfolio equity $E$ (e.g., $f_{\text{risk}} = 1.0\%$).

Define the dynamic stop distance $\Delta P_{\text{stop}}(t)$:

$$\Delta P_{\text{stop}}(t) = (P_{\text{entry}} - L_{\text{anchor}}) + k_t \cdot \text{ATR}_{14, t} + \mathcal{S}_{\text{slip}}$$

* $P_{\text{entry}}$: Intended fill price.
* $L_{\text{anchor}}$: Structural anchor (e.g., rising 10-day EMA or consolidation shelf low).
* $k_t \cdot \text{ATR}_{14, t}$: Time-varying volatility buffer.
* $\mathcal{S}_{\text{slip}}$: High-beta adverse execution allowance (typically modeled as $0.10 \text{ to } 0.20 \times \text{ATR}_{14}$ to cover liquidity gap fills on stop triggers).

The position size in shares $N_{\text{shares}}$ is calculated dynamically as:

$$N_{\text{shares}} = \left\lfloor \frac{E \cdot f_{\text{risk}}}{(P_{\text{entry}} - L_{\text{anchor}}) + k_t \cdot \text{ATR}_{14, t} + \mathcal{S}_{\text{slip}}} \right\rfloor$$

```
Example: High-Beta Tech Stock
Portfolio Equity (E)       = $100,000
Risk Budget (f_risk)       = 1.0% ($1,000)
Entry Price (P_entry)      = $150.00
Anchor Level (L_anchor)    = $146.00 (Structural base)
ATR_14                     = $4.00
Dynamic Buffer (k_t)       = 0.40  -->  0.40 * $4.00 = $1.60
Slippage Allowance         = 0.10 * $4.00 = $0.40

Total Stop Distance        = ($150 - $146) + $1.60 + $0.40 = $6.00
Position Size              = floor($1,000 / $6.00) = 166 shares ($24,900 gross exposure)
(Note: Ignoring the buffer would have sized based on $4.00 risk, yielding 250 shares 
and resulting in a $1,500 loss on stop-out—a 50% risk overshoot).

```

---

### Adjusting the Continuous Kelly Criterion

Standard discrete Kelly assumes fixed binary payouts ($b = \frac{\text{Win Size}}{\text{Loss Size}}$). With dynamic ATR stops, trade returns follow an empirical distribution with negative skew due to gap opens and buffer expansion.

Use the continuous generalized Kelly approximation:

$$f^* = \frac{\mu}{\sigma^2}$$

* $\mu = \mathbb{E}[R_i]$: Expected return per trade normalized by nominal trade risk.
* $\sigma^2 = \text{Var}(R_i)$: Variance of normalized returns.

Because the dynamic buffer $k$ alters both the win rate $p$ (by filtering out stop sweeps) and the loss size on true failures, evaluate $\mu(k)$ and $\sigma^2(k)$ as functions of buffer width $k$:

1. **Trade Expectancy:**

$$\mu(k) = p(k) \cdot \bar{W}(k) - (1 - p(k)) \cdot \bar{L}(k)$$


* $\bar{W}(k)$: Average winning payout in $R$ (stays relatively flat or slightly increases as trade retention improves).
* $\bar{L}(k)$: Average loss. As buffer $k$ increases, $\bar{L}(k)$ expands from $1.0R$ to $1.0 + k \cdot \left(\frac{\text{ATR}}{\Delta P_{\text{anchor}}}\right)$.


2. **Fractional Kelly Scaling (Defensive Dampening):**
Full Kelly generates excessive drawdown volatility in high-beta equity regimes. Implement a **Fractional Kelly multiplier** ($\kappa \in [0.25, 0.50]$) combined with a tail-risk penalty:
$$f_{\text{allocated}}^* = \kappa \cdot \left( \frac{\mu(k)}{\sigma^2(k)} \right) \cdot \left( 1 - \frac{\text{ES}_{0.99}(k)}{\text{Max Allowed Loss}} \right)$$



---

### Volatility-Targeted Dynamic Sizing Architecture

In sector rotation strategies, capital moves between low-volatility sectors (e.g., $XLU$, $\text{ATR}\% \approx 0.8\%$) and high-volatility sectors (e.g., $XBI$, $\text{ATR}\% \approx 3.5\%$). To equalize risk across rotational candidates, size via **volatility parity**:

$$\text{Position Value} = \frac{E \cdot \text{Target Volatility per Position}}{\sigma_{\text{asset}, t} + \lambda_k \cdot \text{ATR}\%_{14, t}}$$

| Variable / Parameter | Adjustment Rule | Rationale |
| --- | --- | --- |
| **High Realized Vol ($\frac{\sigma_{5d}}{\sigma_{20d}} > 1.3$)** | $k_t$ widens $\to$ Sizing shrinks automatically. | Prevents overexposure during regime shifts when wide sweeps occur. |
| **Compression ($\frac{\text{ATR}_{14}}{\text{SMA}_{20}(\text{ATR}_{14})} < 0.75$)** | $k_t$ narrows $\to$ Base distance tightens $\to$ Sizing expands. | Takes advantage of volatility contraction shelves prior to explosive rotational expansion. |
| **Gross Exposure Cap** | Hard ceiling at $\le 20\%–25\%$ of portfolio equity per name. | Prevents math models from concentrating excessive capital into ultratight micro-bases with tiny ATRs. |

---

### Order Routing & Execution Safeguards

* **Recalculate at Fill, Not at Signal:** Because ATR and intraday price fluctuate between order staging and fill time, dynamic stops must compute the share quantity using the real-time $\text{ATR}_{14}$ at the instant of order placement.
* **The "Zero-Distance" Guard:** In extremely tight consolidations, $(P_{\text{entry}} - L_{\text{anchor}})$ can approach zero. Always enforce a hard mathematical floor on the denominator:

$$\Delta P_{\text{stop}} \ge 1.0 \times \text{ATR}_{14, t}$$



This prevents the sizing formula from allocating excessive leverage to an artificially tight base that lacks true structural support.

A cross-sectional risk-parity weighting model for rotating sector ETFs balances total portfolio risk by equalizing the **marginal risk contribution (MRC)** of each selected sector, rather than allocating capital on a nominal dollar-weighted basis.

When coupled with a rotation filter, the model first selects the top $N$ relative strength (RS) sectors, then dynamically sizes them using an Equal Risk Contribution (ERC) formulation driven by a rolling covariance matrix.

---

### Step 1: Universe Selection & Momentum Filtering

Rather than allocating across all 11 SPDR sectors (which dilutes momentum), filter down to the top $N$ outperforming sectors (typically $N \in [3, 5]$) before computing risk parity weights:

1. Calculate the 60-day relative return of each sector ETF vs. $SPY$, adjusted for 20-day realized volatility:

$$z_i(t) = \frac{R_{i, t}^{60\text{d}} - R_{SPY, t}^{60\text{d}}}{\sigma_{i, t}^{20\text{d}}}$$


2. Select the subset $\mathcal{S}_t = \{i \mid \text{rank}(z_i(t)) \le N\}$.
3. Apply a trend filter: ETF must trade above its 50-day SMA ($P_{i, t} > \text{SMA}_{50}(P_{i, t})$). If fewer than $N$ sectors pass, the unallocated weight routes to short-term Treasuries ($BIL$ or $SHY$).

---

### Step 2: Rolling Covariance Estimation

For the active subset $\mathcal{S}_t$, construct the rolling covariance matrix $\Sigma_t \in \mathbb{R}^{N \times N}$ over a lookback window $\tau$ (typically 40 to 60 trading days):

$$\Sigma_t = \mathcal{D}_t \cdot \mathcal{C}_t \cdot \mathcal{D}_t$$

* $\mathcal{D}_t = \text{diag}(\sigma_{1, t}, \dots, \sigma_{N, t})$: Diagonal matrix of rolling exponential or sample volatilities.
* $\mathcal{C}_t$: Rolling correlation matrix across the active sectors.
* **Shrinkage Regularization:** To prevent inversion instability when cross-sector correlation spikes, apply Ledoit-Wolf shrinkage toward a constant-correlation target $\mathcal{F}$:

$$\hat{\Sigma}_t = (1 - \alpha) \Sigma_t + \alpha \mathcal{F}$$



---

### Step 3: Equal Risk Contribution (ERC) Formulation

Portfolio volatility is given by:

$$\sigma_p(w) = \sqrt{w^T \hat{\Sigma}_t w}$$

The marginal risk contribution ($\text{MRC}_i$) of sector $i$ and its total risk contribution ($\text{TRC}_i$) are:

$$\text{MRC}_i = \frac{(\hat{\Sigma}_t w)_i}{\sigma_p(w)}, \quad \text{TRC}_i = w_i \cdot \text{MRC}_i = \frac{w_i (\hat{\Sigma}_t w)_i}{\sigma_p(w)}$$

Risk parity requires that each active sector contributes an identical share of total portfolio volatility:

$$\text{TRC}_i = \frac{\sigma_p(w)}{N} \quad \forall i \in \mathcal{S}_t$$

Solve the convex optimization problem under standard long-only, fully invested constraints:

$$\min_w \sum_{i=1}^N \sum_{j=1}^N \left( w_i (\hat{\Sigma}_t w)_i - w_j (\hat{\Sigma}_t w)_j \right)^2 \quad \text{s.t.} \quad \sum_{i=1}^N w_i = 1, \quad w_i \ge 0$$

*(Note: If off-diagonal correlations are assumed zero, this collapses to simple **Inverse-Volatility Weighting**: $w_i \propto \frac{1}{\sigma_i}$. However, true ERC is critical during sector rotations because correlations between defensive and cyclical sectors are highly asymmetric).*

---

### Step 4: Python Implementation (Rolling ERC Engine)

```python
import numpy as np
import pandas as pd
from scipy.optimize import minimize

def get_erc_weights(cov_matrix: np.ndarray) -> np.ndarray:
    """
    Computes Equal Risk Contribution (ERC) weights for a covariance matrix.
    """
    n = cov_matrix.shape[0]
    
    def objective(w):
        # w in R^n, calculate TRC for each asset
        sigma_p = np.sqrt(w @ cov_matrix @ w)
        mrc = (cov_matrix @ w) / (sigma_p + 1e-12)
        trc = w * mrc
        # Minimize the sum of squared differences between TRC pairs
        diffs = trc[:, None] - trc[None, :]
        return np.sum(diffs ** 2)

    bounds = [(0.05, 0.45) for _ in range(n)]  # Cap individual sectors at 45%, min 5%
    constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0}]
    w0 = np.ones(n) / n

    res = minimize(objective, w0, method='SLSQP', bounds=bounds, constraints=constraints)
    return res.x if res.success else w0

def run_rotation_risk_parity(daily_returns: pd.DataFrame, top_n: int = 4, lookback: int = 60):
    """
    daily_returns: DataFrame of sector ETF returns (e.g., XLK, XLE, XLV, etc.)
    """
    # 1. Momentum scoring: 60-day return / 20-day realized volatility
    ret_60d = daily_returns.rolling(lookback).apply(lambda x: np.prod(1 + x) - 1)
    vol_20d = daily_returns.rolling(20).std() * np.sqrt(252)
    momentum_scores = ret_60d / (vol_20d + 1e-6)

    # 2. Rebalance monthly (or bi-weekly)
    rebalance_dates = daily_returns.resample('M').last().index
    allocation_history = {}

    for date in rebalance_dates:
        if date not in momentum_scores.index or momentum_scores.loc[:date].shape[0] < lookback:
            continue

        scores = momentum_scores.loc[date].dropna()
        selected_sectors = scores.nlargest(top_n).index.tolist()

        # 3. Rolling covariance on active sectors
        cov = daily_returns.loc[:date, selected_sectors].tail(lookback).cov().values * 252
        weights = get_erc_weights(cov)
        
        allocation_history[date] = pd.Series(weights, index=selected_sectors)

    return pd.DataFrame(allocation_history).T.fillna(0.0)

```

---

### Step 5: Turnover Dampening & Volatility Targeting

Pure re-optimization every bar leads to excessive friction. Implement two overlay guards:

* **Rebalance Bands (No-Trade Buffer):** Do not re-optimize unless a constituent’s current weight deviates from its target ERC weight by more than $\pm 15\%$ relative (e.g., target is $25\%$, band is $21.25\% - 28.75\%$).
* **Portfolio-Level Volatility Targeting:** Scale total gross leverage $L_t$ to hit a constant annual portfolio volatility $\sigma_{\text{target}}$ (e.g., $12\%$):

$$L_t = \min\left(1.0, \frac{\sigma_{\text{target}}}{\sigma_p(w_t)}\right)$$



When macro dispersion spikes and correlations converge toward 1.0, the model scales back gross equity exposure and parks excess capital in cash/short-duration yields.

A standard fixed-volatility target ($\sigma_{\text{target}}$) fails during macro regime transitions: it forces the portfolio to over-lever into low-volatility traps (which precede sharp volatility expansions) and forces massive liquidations at the absolute bottom of market selloffs.

A **Markov-Switching Autoregressive (MS-AR) model** detects the latent probability of market regimes—typically **Low-Vol Expansion**, **Rotational/Transitional Churn**, and **High-Vol Liquidation**—allowing you to dynamically throttle $\sigma_{\text{target}}(t)$ before realized covariance spikes trigger trailing stops.

---

### Step 1: Formalize the Latent Regime State Space

Let $S_t \in \{1, 2, \dots, K\}$ denote an unobserved discrete Markov chain representing the market regime at time $t$ (typically $K=3$ for sector-rotation dynamics).

The transition between regimes follows a first-order Markov process governed by transition matrix $\mathbf{P}$:

$$P_{ij} = \mathbb{P}(S_t = j \mid S_{t-1} = i), \quad \sum_{j=1}^K P_{ij} = 1$$

To capture both index-level turbulence and sector dispersion, model an observable multivariate vector $Y_t$:

$$Y_t = \begin{bmatrix} r_{\text{SPY}, t} \\ \text{Cross-Sectional Dispersion}_t \\ \Delta \log(VIX_t) \end{bmatrix}$$

Where **Cross-Sectional Sector Dispersion** is defined as the cross-sectional standard deviation of returns across all $M=11$ sector ETFs:

$$\mathcal{D}_t = \sqrt{\frac{1}{M-1} \sum_{m=1}^M \left( r_{m, t} - \bar{r}_t \right)^2}$$

Conditional on regime $S_t = s$, the observation vector follows a state-dependent Gaussian distribution:

$$Y_t \mid (S_t = s) \sim \mathcal{N}(\mu_s, \mathbf{\Omega}_s)$$

| State ($S_t$) | Economic Regime | Typical Dynamics | Dispersion & Correlation |
| --- | --- | --- | --- |
| **State 1** | **Low-Vol Expansion** | High return, low vol, low index-sector correlation. | Low-to-moderate dispersion; steady sector trending. |
| **State 2** | **Rotational / Churn** | Muted benchmark returns, elevated inter-sector dispersion. | **High dispersion**; rapid capital rotation without market breakdown. |
| **State 3** | **Liquidation / Contagion** | Negative returns, high vol, correlations collapse to 1.0. | Low-to-moderate dispersion; indiscriminate selling. |

---

### Step 2: Extract Real-Time Filtered Probabilities

To avoid lookahead bias, do not use smoothed probabilities (which condition on future data). Instead, use the **Hamilton Filter** forward recursion to compute the **filtered state probability** $\xi_{t \mid t} \in \mathbb{R}^K$:

$$\xi_{t \mid t-1} = \mathbf{P}^T \xi_{t-1 \mid t-1}$$

$$\xi_{t \mid t, s} = \frac{\xi_{t \mid t-1, s} \cdot f(Y_t \mid S_t = s; \hat{\theta})}{\sum_{j=1}^K \xi_{t \mid t-1, j} \cdot f(Y_t \mid S_t = j; \hat{\theta})}$$

Where $f(\cdot)$ is the multivariate normal density function evaluated under parameter set $\hat{\theta} = \{\mu_s, \mathbf{\Omega}_s, \mathbf{P}\}$.

---

### Step 3: Dynamic Target Volatility & Gross Leverage Throttling

Define a baseline target volatility for each regime:

$$\sigma_{\text{base}} = [\sigma_1, \sigma_2, \sigma_3]^T = [15\%, 10\%, 5\%]^T$$

At each rebalancing timestamp $t$, calculate the expected regime target volatility $\sigma_{\text{target}}(t)$ as the probability-weighted expectation:

$$\sigma_{\text{target}}(t) = \sum_{s=1}^K \xi_{t \mid t, s} \cdot \sigma_s = \xi_{t \mid t}^T \mathbf{\sigma}_{\text{base}}$$

This output smoothly scales the portfolio's gross exposure without binary whipsawing:

1. **In State 1 (Expansion, $\xi_{1} \to 1.0$):** Target volatility expands to $15\%$. Risk parity runs near or above full capacity ($L_t \approx 1.0 - 1.2$), compounding sector trend momentum.
2. **In State 2 (Sector Rotation, $\xi_{2} \to 1.0$):** Target volatility compresses moderately to $10\%$. Cross-sectional ERC reallocates aggressively into high-RS sectors, but total risk is clipped to account for whipsaw and factor churn.
3. **In State 3 (Liquidation, $\xi_{3} \to 1.0$):** Target volatility drops to $5\%$. Gross leverage collapses ($L_t \approx 0.3 - 0.4$), routing capital into cash or short Treasuries ($BIL$) before stop cascades trigger.

$$L_t = \min \left( L_{\max}, \frac{\sigma_{\text{target}}(t)}{\sqrt{w_t^T \hat{\Sigma}_t w_t}} \right)$$

---

### Step 4: Python Implementation (Hamilton Filter & Dynamic Sizing)

```python
import numpy as np
import pandas as pd
from statsmodels.tsa.regimes.markov_autoregression import MarkovAutoregression

def estimate_regime_probabilities(spy_returns: pd.Series, sector_returns: pd.DataFrame) -> pd.DataFrame:
    """
    Fits a 3-state Markov Switching model on SPY returns and sector dispersion.
    Returns daily filtered probabilities (no lookahead bias).
    """
    # 1. Calculate sector cross-sectional dispersion
    dispersion = sector_returns.std(axis=1)
    
    # 2. Construct standardized feature: SPY Return / Dispersion Ratio
    feature = (spy_returns / (dispersion + 1e-5)).dropna()

    # 3. Fit 3-regime Markov model (switching variance and mean)
    model = MarkovAutoregression(
        endog=feature,
        k_regimes=3,
        order=0,
        switching_variance=True
    )
    res = model.fit(disp=False)

    # 4. Extract filtered probabilities (P(S_t = s | Y_1, ..., Y_t))
    filtered_probs = res.filtered_marginal_probabilities

    # Sort regimes by variance: State 0 = Lowest Vol, State 2 = Highest Vol
    var_order = np.argsort(res.params[['sigma2[0]', 'sigma2[1]', 'sigma2[2]']].values)
    filtered_probs.columns = [f'State_{i}' for i in range(3)]
    
    # Re-order columns so State_0 is always Low-Vol, State_1 is Medium, State_2 is High
    ordered_probs = filtered_probs[[f'State_{var_order[0]}', 
                                    f'State_{var_order[1]}', 
                                    f'State_{var_order[2]}']]
    ordered_probs.columns = ['P_LowVol', 'P_Rotational', 'P_Liquidation']
    return ordered_probs

def compute_dynamic_target_vol(filtered_probs: pd.DataFrame, 
                               base_vols: list = [0.15, 0.10, 0.05]) -> pd.Series:
    """
    Computes real-time target volatility:
    target_vol_t = P_LowVol * 15% + P_Rotational * 10% + P_Liquidation * 5%
    """
    weights = np.array(base_vols)
    dynamic_vol = filtered_probs.dot(weights)
    return dynamic_vol

```

---

### Key Operational Nuances

* **Filtering Lookback Calibration:** Re-fit the Markov parameters ($\hat{\theta}$) using a rolling window of 252 to 504 days. Do not update $\hat{\theta}$ daily (which causes regime label flipping); re-estimate parameter matrices monthly, while updating filtered probabilities $\xi_{t \mid t}$ on every daily close.
* **Asymmetric Transitions:** Empirical transition matrices in sector markets are asymmetric: $P_{\text{Exp} \to \text{Liq}}$ is typically small, but $P_{\text{Rot} \to \text{Liq}}$ is significantly higher. Transitions usually move sequentially: $\text{Expansion} \to \text{Sector Dispersion/Churn} \to \text{Liquidation}$. Detecting the expansion of State 2 provides an early warning gate before macro drawdowns accelerate.
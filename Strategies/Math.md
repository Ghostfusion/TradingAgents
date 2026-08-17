Here are the most effective books, quantitative frameworks, and screening resources specifically focused on **systematically generating a master watchlist of value stocks** before running in-depth analysis.

---

### 1. Essential Books for Systematic & Formulaic Value Screening

* ***The Little Book That Still Beats the Market* by Joel Greenblatt**
* **Core Concept:** The **"Magic Formula"**—a two-factor quantitative screen that ranks companies by **Earnings Yield** ($EBIT / EV$) and **Return on Capital** ($EBIT / (Net\ Working\ Capital + Net\ Fixed\ Assets)$).
* **Why it fits:** It is designed specifically to produce a pre-filtered list of ~30–50 companies that are fundamentally cheap relative to their profitability.


* ***Quantitative Value: A Practitioner's Guide to Automating Intelligent Investment* by Wesley Gray & Tobias Carlisle**
* **Core Concept:** Builds an algorithmic, end-to-end framework starting with forensic accounting filters to eliminate fraud/bankruptcy risk (Beneish M-Score, Altman Z-Score, Piotroski F-Score), followed by valuation and quality ranking.
* **Why it fits:** Essential if you plan to build a programmatic screener or automated pipeline to avoid "value traps."


* ***The Acquirer's Multiple* by Tobias Carlisle**
* **Core Concept:** Compares various valuation multiples and demonstrates why **Enterprise Value to Operating Earnings ($EV / EBIT$)** consistently outperforms traditional metrics like $P/E$ or $P/B$ across market cycles.
* **Why it fits:** A fast, high-signal filter to rank the entire universe of public equities.


* ***What Works on Wall Street* by James O'Shaughnessy**
* **Core Concept:** Decades of backtested empirical data on valuation metrics (Price-to-Sales, EV/EBITDA, Shareholder Yield, Free Cash Flow Yield).
* **Why it fits:** Highlights the statistical win-rate of single-factor and multi-factor value filters across large-cap and small-cap universes.



---

### 2. High-Yield Screening Formulas for Your Master List

When setting up your initial filters to quickly populate a master list, combine one **Valuation filter** with one **Financial Health / Quality filter**:

| Screen Type | Primary Valuation Filter | Quality / Solvency Filter | Typical Output Profile |
| --- | --- | --- | --- |
| **Magic Formula / ROIC** | Top decile: $EBIT / EV$ | Top decile: $ROIC$ or $ROC > 20\%$ | Profitable businesses trading at a temporary discount |
| **Acquirer's Multiple** | Lowest $EV / EBIT$ ($< 8–10\times$) | Debt-to-Equity $< 1.0$ or Interest Coverage $> 4\times$ | Mispriced cash generators, potential buyouts |
| **Piotroski Quality Value** | Low $P/B$ (bottom 20–30%) or low $EV/EBITDA$ | **Piotroski F-Score $\ge 7$** (improving margins, liquidity, leverage) | Turnaround candidates with improving fundamentals |
| **Shareholder Yield** | Top quartile: Dividends + Net Buybacks + Debt Reduction | Positive Free Cash Flow ($FCF / Net\ Income > 1.0$) | Mature, capital-disciplined cash cows |
| **Net-Net / Deep Value** | Market Cap $< \frac{2}{3} \times (Current\ Assets - Total\ Liabilities)$ | Low Cash Burn / Positive Operating Cash Flow | Micro-cap deep value / liquidation margin of safety |

---

### 3. Practical Data Sources & Pre-Built Screening Resources

* **Free Algorithmic Screeners:**
* **[Magic Formula Investing](https://www.magicformulainvesting.com/):** Joel Greenblatt’s official tool to generate 30- to 50-stock lists filtered by minimum market cap.
* **[The Acquirer's Multiple Screener](https://acquirersmultiple.com/):** Free and paid screening lists ranking stocks by EV/EBIT.
* **[Finviz Screener](https://finviz.com/screener.ashx):** Excellent for multi-criteria visual filtering (e.g., Forward P/E $< 15$, PEG $< 1$, Debt/Eq $< 0.5$, positive insider buying).


* **Programmatic / API Pipelines (for custom scripts):**
* **OpenBB Terminal / SDK:** Open-source Python environment for querying equity fundamentals, screeners, and macro datasets.
* **Financial Modeling Prep (FMP) API / SEC EDGAR:** Useful for batch-downloading balance sheet and cash flow statements to compute composite F-Scores or custom enterprise multiples.
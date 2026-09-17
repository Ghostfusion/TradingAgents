Yes. I would make **NewsScore** and **SentimentScore** separate engines rather than burying them inside TechnicalScore or FundamentalScore.

For your quant application, the architecture can become:

```text
FundamentalScore
TechnicalScore
RegimeScore
RiskScore
NewsScore
SentimentScore
        │
        ▼
 Decision / Opportunity Engine
```

The key distinction is that **news is information/event flow**, while **sentiment is the market's interpretation/positioning around that information**.

## Recommended initial weights

### NewsScore — 100%

| Category                     |   Weight |
| ---------------------------- | -------: |
| News relevance / materiality |  **20%** |
| News novelty                 |  **15%** |
| Fundamental impact           |  **20%** |
| Earnings / guidance news     |  **15%** |
| Corporate events             |  **10%** |
| Regulatory / legal news      |   **5%** |
| Analyst / rating changes     |   **5%** |
| Macro / industry news        |   **5%** |
| News persistence             |   **5%** |
| **Total**                    | **100%** |

Potential factors:

* headline sentiment
* headline relevance
* novelty score
* materiality
* earnings surprise
* guidance change
* revenue-impact estimate
* margin-impact estimate
* product announcement
* M&A
* partnership
* contract/win
* lawsuit
* regulatory action
* analyst upgrade/downgrade
* price-target revision
* management change
* dividend/buyback announcement
* bankruptcy/distress
* industry shock
* macro sensitivity
* news volume acceleration
* repeated-news decay

I'd particularly emphasize **novelty + materiality + fundamental impact**, rather than simply counting positive/negative headlines.

---

# SentimentScore — 100%

| Category                     |   Weight |
| ---------------------------- | -------: |
| News sentiment               |  **15%** |
| Sentiment momentum           |  **15%** |
| Sentiment breadth            |  **10%** |
| Institutional sentiment      |  **15%** |
| Analyst sentiment            |  **10%** |
| Retail/social sentiment      |  **10%** |
| Options sentiment            |  **10%** |
| Short-interest sentiment     |   **5%** |
| Sentiment dispersion         |   **5%** |
| Sentiment extreme / crowding |   **5%** |
| **Total**                    | **100%** |

For example:

### Sentiment level

$$
SentimentLevel =
\frac{Positive-News-Negative-News}
{Total-News}
$$

### Sentiment momentum

$$
SentimentMomentum =
Sentiment_{today}-Sentiment_{20d}
$$

### Sentiment acceleration

$$
SentimentAcceleration =
\Delta SentimentMomentum
$$

### Sentiment breadth

Percentage of sources/articles expressing positive sentiment.

### Sentiment dispersion

$$
Dispersion = Std(Sentiment_i)
$$

This is useful because:

```text
90% positive + low dispersion
```

means something very different from:

```text
50% extremely positive + 50% extremely negative
```

---

# I would add one particularly important factor

### Sentiment × Price Confirmation

Don't assume positive sentiment is bullish.

Calculate whether sentiment is being **confirmed by price/volume**.

For example:

$$
SPC =
Corr(\Delta Sentiment,\Delta Price)
$$

or a more useful event-window measure:

$$
SentimentConfirmation =
Sign(\Delta Sentiment)
\times
Sign(\text{abnormal return})
$$

This creates four very different situations:

| Sentiment | Price   | Interpretation     |
| --------- | ------- | ------------------ |
| Positive  | Rising  | Confirmed positive |
| Positive  | Falling | **Divergence**     |
| Negative  | Falling | Confirmed negative |
| Negative  | Rising  | **Divergence**     |

That is much more useful than simply:

```text
Sentiment = +0.72
```

---

# Don't let NewsScore become a duplicate of SentimentScore

This is important.

For example:

```text
NewsScore
```

should answer:

> **What new information has arrived, and how materially could it affect the company?**

while:

```text
SentimentScore
```

answers:

> **How are investors/analysts/media/markets currently positioned or reacting to the information?**

So:

```text
NVIDIA announces major new AI contract
        ↓
NewsScore ↑↑
        ↓
Analysts become more positive
        ↓
SentimentScore ↑
        ↓
Stock +8%, volume 3× normal
        ↓
TechnicalScore ↑
```

Those are **three separate observations**, not three votes for the same thing.

---

# Your complete architecture is now getting very clean

I'd use:

```text
┌───────────────────────────────┐
│       FUNDAMENTAL ENGINE      │
│       FundamentalScore        │
└───────────────┬───────────────┘
                │
┌───────────────▼───────────────┐
│        TECHNICAL ENGINE       │
│        TechnicalScore         │
└───────────────┬───────────────┘
                │
┌───────────────▼───────────────┐
│         REGIME ENGINE         │
│         RegimeScore           │
└───────────────┬───────────────┘
                │
┌───────────────▼───────────────┐
│          NEWS ENGINE           │
│          NewsScore             │
└───────────────┬───────────────┘
                │
┌───────────────▼───────────────┐
│       SENTIMENT ENGINE         │
│       SentimentScore           │
└───────────────┬───────────────┘
                │
┌───────────────▼───────────────┐
│           RISK ENGINE           │
│           RiskScore             │
└───────────────┬───────────────┘
                │
                ▼
       ┌─────────────────┐
       │ DECISION ENGINE │
       └────────┬────────┘
                ▼
       Entry / Hold / Exit
                │
                ▼
          Position Size
                │
                ▼
           HARD GATES
```

## I would **not** initially give News + Sentiment a huge portfolio-level weight

For your system, I'd initially treat them as **event/confirmation variables**, not permanent alpha replacements for fundamentals.

A reasonable initial research allocation for a future composite could be:

| Engine      | Initial research weight |
| ----------- | ----------------------: |
| Fundamental |                 **35%** |
| Technical   |                 **20%** |
| Regime      |                 **15%** |
| Risk        |                 **15%** |
| News        |                **7.5%** |
| Sentiment   |                **7.5%** |
| **Total**   |                **100%** |

But I would label those **research weights**, not production truth.

And, consistent with your Q2 decision, eventually test these empirically:

$$
IC_{News}
$$

$$
IC_{Sentiment}
$$

$$
IC_{NewsMomentum}
$$

$$
IC_{SentimentMomentum}
$$

and, critically:

$$
IC_{News \times Regime}
$$

because news effects can be highly regime-dependent.

For example, a positive earnings surprise during a strong risk-on regime can behave very differently from the same surprise during a severe risk-off regime.

### One more architectural recommendation

I'd actually add **EventScore** as a separate engine before allowing NewsScore to influence `opportunity_score`:

```text
FundamentalScore
TechnicalScore
RegimeScore
NewsScore
SentimentScore
EventScore
RiskScore
```

That lets you distinguish:

**"The company received positive news"**

from

**"There is a high-impact event occurring right now."**

Earnings, FDA decisions, CPI/FOMC, product launches, court decisions, investor days, OPEX, etc. can then be handled through **EventScore**, while NewsScore remains focused on information flow.

This would fit very well with the market-read architecture you've already built, which already tracks earnings expected moves, OPEX, options positioning, flow, sentiment, and macro/event conditions. 

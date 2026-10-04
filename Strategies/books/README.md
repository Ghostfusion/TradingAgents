# Paper library — `Strategies/books/`

A category-by-category reading of the arXiv paper collection held at
`E:\fin paper\`, written to answer one question for every paper: **does this
tell us how to make this repo better?**

These documents are *research inputs*, not specs. A learning becomes work only
when it is written up as a plan in the vault (`Strategies/index.md` convention:
plan file → implementing module → config gate → consumer).

---

## 1. The corpus

| | |
| --- | --- |
| PDFs on disk | **4,348** (6.0 GB), numbered `<arxiv-id>.pdf` in one flat directory |
| Metadata records | **4,372** in `E:\fin paper\.state\metadata.jsonl` |
| Gap | 24 ids are withdrawn/404 (`unavailable.jsonl`); the metadata keeps them so the corpus is accounted for |
| Span | 1997 – 2026 |
| Domains | q-fin.ST (all), plus q-fin.TR / RM / PM / CP / GN / PR / MF, cs.LG / cs.AI / cs.CL, stat.ME / stat.AP / stat.ML, math.ST / math.PR, cond-mat.stat-mech, physics.soc-ph / physics.data-an, econ.EM / econ.GN |

Collected 2026-09-20 by a category crawl of arXiv q-fin and its cross-lists.

## 2. How this was produced

Three passes, in order:

1. **Taxonomy** — every paper classified from its title + abstract into the 19
   categories below (multi-label: a paper can belong to several; **2.72 books
   per paper** on average, 3,249 papers land in more than one).
2. **Abstract-level sweep — complete coverage.** 18 reviewers each took a
   contiguous slice of the corpus and produced one annotated row per paper:
   arXiv id, year, a ≤35-word takeaway naming the method and the finding, a
   candidate repo surface, and a relevance grade. **Coverage: 4,372 / 4,372
   papers — no paper unaccounted for.** These rows are collated per category
   into `evidence/<slug>.md`, shipped alongside the books.
3. **Deep reads** — 19 reviewers went back over the best papers of one category
   each, read their full texts, verified every claimed repo symbol against the
   actual source, and wrote the book document.

## 3. The books

| # | Book | Papers (primary / in category) | Read this for |
| --- | --- | --- | --- |
| 01 | [LLM & Agentic Trading Systems](01-llm-agents.md) | 134 / 134 | The repo's own subject: agent architecture, debate, hallucination, leakage, honest evaluation of LLM alpha |
| 02 | [Backtest Methodology, Overfitting & Evaluation](02-backtest-evaluation.md) | 402 / 430 | PBO, deflated Sharpe, purged CV, multiple testing, survivorship — the highest practical value in the corpus |
| 03 | [Data Quality, Robustness & Missing Data](03-data-quality.md) | 108 / 135 | Outliers, imputation bias, measurement error, denoising, vendor reliability |
| 04 | [News, Sentiment & Textual Signals](04-sentiment-text.md) | 246 / 341 | FinBERT, tone measures, aggregation, signal half-life, text-factor mining risk |
| 05 | [Options, Implied Volatility & Derivatives](05-options-implied.md) | 188 / 234 | Volatility risk premium, surface construction, risk-neutral densities |
| 06 | [Market Microstructure, Liquidity & Execution](06-microstructure-execution.md) | 552 / 703 | Order-flow imbalance, impact models, execution schedules, quote-free spreads |
| 07 | [Regimes, Change Points & Bubbles](07-regime-changepoint.md) | 460 / 663 | Markov switching, change-point detection, filtered vs smoothed states |
| 08 | [Risk Management & Tail Risk](08-risk-tail.md) | 228 / 510 | VaR/ES and their backtests, EVT, drawdown, coherent measures |
| 09 | [Portfolio Construction & Allocation](09-portfolio.md) | 236 / 573 | Estimation error, shrinkage, HRP, Kelly, turnover-aware rebalancing |
| 10 | [Volatility & Realized Variance](10-volatility.md) | 362 / 1,079 | HAR family, RV estimators, jumps, rough vol, forecast evaluation |
| 11 | [Correlation, Networks & Dependence](11-correlation-networks.md) | 408 / 1,053 | RMT eigenvalue cleaning, copulas, topology, causal discovery |
| 12 | [Factors, Anomalies & Cross-Sectional Signals](12-factors-crosssection.md) | 148 / 661 | The factor zoo, replication, anomaly decay, neutralisation |
| 13 | [Crypto & Digital Assets](13-crypto.md) | 53 / 331 | Out-of-domain contrast: what transferable lessons crypto offers an equity engine |
| 14 | [Market Efficiency, Predictability & Information](14-market-efficiency.md) | 68 / 387 | What predictability demonstrably exists, and at what horizon |
| 15 | [Machine Learning & Deep Learning Methods](15-ml-methods.md) | 90 / 800 | Why DL underperforms on noise, calibration, conformal, RL pitfalls |
| 16 | [Return, Price & Time-Series Forecasting](16-forecasting.md) | 146 / 1,567 | Achievable out-of-sample $R^2$, forecast combination, density forecasts and their scores |
| 17 | [Statistical & Econometric Methodology](17-stat-methodology.md) | 103 / 1,037 | Fractional integration and the spurious-long-memory trap, GARCH inference, state space |
| 18 | [Econophysics, Scaling & Agent-Based Models](18-econophysics.md) | 171 / 985 | Tail exponents, Hawkes, DFA/Hurst biases, stylised facts |
| 19 | [Other / Unclassified](19-other.md) | 269 / 269 | The classifier's residue, honestly labelled, plus re-homing suggestions |

**Start with 01, 02 and 03 if you only read three.** They cover the repo's own
method (agentic LLM trading), the discipline that decides whether any of its
numbers mean anything (backtest evaluation), and the input that determines
whether those numbers are even computed from real data (data quality).

Dozens of papers belong to more than one book; a paper is filed under its
**primary** category in the index but appears in every category's evidence pack
and, where genuinely relevant, in more than one book's learnings.

## 4. Reading a book

Every book follows the same shape:

- **§0 Scope** — what the category covers and whether it matters here.
- **§1 Corpus composition** — the counts, and what the category is dominated by.
- **§2 Deep reads** — the papers the reviewer actually read in full, with method, finding and stated limitation.
- **§3 Learnings applicable to this repo** — numbered; each names the paper, the finding, the exact repo symbol, whether that symbol's behaviour `shipped` / is `partial` / is `absent`, and the smallest concrete step to capture it.
- **§4 Where this repo is already ahead** — to stop us re-proposing shipped work.
- **§5 Defects or risks** — only evidence-backed ones, each tied to a paper *and* a repo file.
- **§6 Limits of this review** — what was skimmed rather than read.

## 5. What backs the numbers

- `CORPUS_INDEX.md` — **every one of the 4,372 papers**, grouped by primary
  category, with its arXiv id, year, cross-listings and title. Nothing in the
  corpus is missing from this index.
- `evidence/<slug>.md` — the sweep's output for each category, verbatim: every
  paper in it, its takeaway, its candidate repo surface, its relevance grade.
  These are the rows the book's §3 screens, so a book's claims can be checked
  against them.

## 6. Relationship to the existing 26xx survey — read this before acting on a learning

The owner has **already surveyed part of this same corpus**:
`docs/design_fin_paper_survey_26.md` (v1.0, 2026-09-23) read all **309 `26xx`
papers** (arXiv 2601–2609, Jan–Sep 2026) in `e:\fin paper` and routed the
usable ones into six themed design docs plus six implementation plans under
`docs/paper_survey_26/`.

Those 309 papers are a **subset of this library's 4,372**, and that survey is
the **authority** for them, because it is an owner decision document with
per-theme plans. It also already carries several things this library's §3
independently proposes — CSCV probability-of-backtest-overfitting, Minimum Track
Record Length, Diebold–Mariano, QLIKE, Ledoit-Wolf in the allocation path,
Yang-Zhang over the OHLC estimators.

So, for a `26xx` paper: **read `docs/paper_survey_26/` first.** This library's
§3 `Status` column (`shipped` / `partial` / `absent`) was checked against the
**live code**, not against those pending plans — so `absent` here can mean
"about to be built", and it does not mean "nobody thought of it".

What this library adds over that survey:

- **Breadth** — the whole corpus, 1997–2026, not one year's submissions.
- **A complete index** (`CORPUS_INDEX.md`) and per-category annotated sweep rows
  (`evidence/<slug>.md`) for every paper, not only the judged ones.
- **The long tail** — 1997–2025 work, which the survey's window excludes and
  which supplies the methodology the 2026 papers build on.
- **A defect register** (`FINDINGS.md`) — every claim of the form "the repo gets
  this wrong", consolidated and marked by verification status.

## 7. Honest limits

- **Abstract-level for most of the corpus.** All 4,372 papers were read at the
  level of title + abstract. Full-text reading covers the subset each book's
  §2 lists — several hundred papers in total, concentrated in the categories
  that matter most here. A takeaway drawn from an abstract can miss a caveat
  that only appears in the body; treat a sweep row as a lead, not a finding.
- **The classifier is keyword-based.** It is deliberately multi-label and
  tuned for recall, so categories overlap and 269 papers fell through to
  `19-other.md`. §3 of that book names papers that should be re-homed.
- **"High relevance" is per-reviewer judgement, uncalibrated.** Eighteen
  different reviewers graded eighteen slices; the proportion they called
  `high` ranges from ~2% to ~36% of a slice. Within a book, therefore, the
  `high` list is a *lead list*, not a ranking. The book reviewers re-judged for
  themselves — §3 of a book is the screened result, not the `high` list.
- **The corpus is not the literature.** It is one crawl of arXiv q-fin. It
  under-represents sell-side/industry practice, non-English work, and
  practitioner sources that never reach arXiv, and it over-represents
  econophysics and descriptive statistics relative to the tradeable core.
- **Nothing here is a recommendation to trade.** Several books record that a
  documented effect is decayed, cost-eaten, or un-replicable.

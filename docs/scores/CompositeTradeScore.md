# CompositeTradeScore — the composite layer, and the 2026-09-26 proposal

**Part of the score-engine design set: [`README.md`](README.md)** (master —
architecture, cross-engine rules, the composite, the code defects, the phase plan,
the open questions). Engine siblings: [`FundamentalScore.md`](FundamentalScore.md),
[`TechnicalScore.md`](TechnicalScore.md), [`RegimeScore.md`](RegimeScore.md),
[`RiskScore.md`](RiskScore.md), [`NewsScore.md`](NewsScore.md),
[`SentimentScore.md`](SentimentScore.md), [`EventScore.md`](EventScore.md),
[`MarketScore.md`](MarketScore.md), [`ValuationScore.md`](ValuationScore.md).

**Scope: the layer that combines engines.** The built object is
`strategies/trade_score.py::trade_score:293` (WP-11) — the four-engine decision
composite the master calls *the composite* (`README.md` §1.4). The owner pasted an
advisory design note on **2026-09-26** that renames the same object **Composite
Trade Score (CTS)** and proposes to reshape it: three layers, an `OpportunityScore`
that the trade score multiplies by a risk adjustment and a confidence adjustment,
a seven-engine weight vector, cross-sectional standardization, interaction terms,
and a separate *Composite Alpha Score*.

Status: **the built object is unchanged by this document; the note is a proposal —
no weight, gate, config key, tool leaf or code line was added for it
(2026-09-26).** §3 is the claim-by-claim ledger: what the note describes that
already exists, what it proposes that does not exist anywhere in the tree, and the
four places where adopting it as written would break a **binding** invariant. No
code defect was found in the composite path this round (§2.3 is the one doc-level
inaccuracy that was corrected).

---

## 0. Provenance, vocabulary, and what this document may not do

### 0.1 The note's opening claim is correct, and the repo already says so

The note opens: *"**Composite Trade Score** is a legitimate and useful concept,
but it is not a single universally standardized industry formula"*, then asserts
*"Your current formulation was: `TradeScore = 0.40 Fundamental + 0.25 Technical +
0.15 Regime + 0.20 Risk`. That is already a Composite Trade Score
mathematically."*

Verified against the tree — it is the built vector, not a reconstruction:

| Term in the note | Built symbol | Value |
| --- | --- | --- |
| 0.40 Fundamental | `strategies/trade_score.py::ENGINE_WEIGHTS:100` (`"fundamental": 0.40`) | `F` |
| 0.25 Technical | same table (`"technical": 0.25`) | `T` |
| 0.15 Regime | same table (`"regime": 0.15`) | `R` |
| 0.20 Risk | same table (`"risk": 0.20`) | **`K`** — not `R` |

One vocabulary slip worth pinning before anything else, because the printed block
is built from these letters: the repo prints **`K`** for `RiskScore` and **`R`**
for `RegimeScore` (`trade_score.py::ENGINE_LETTERS:67`). The note writes the risk
term last without a letter; taken literally it would collide with the regime
letter in the four-letter form `F/T/R/K` that `format_trade_score:432` emits and
that `tests/test_trade_score.py:57` pins (`ACCEPTANCE_CASE = {"F": 92, "T": 85,
"R": 78, "K": 35}`).

The note's two external anchors are real and are cited, with their DOI records
fetched this round, in Appendix A.

### 0.2 What this document may not do

1. **It may not create a weight table.** The cross-engine weight ledger is the
   master's (`README.md` §1.4) and the module's (`ENGINE_WEIGHTS:100`,
   `RESEARCH_ALLOCATION:112`). A composite weight is an owner decision with a
   measurement behind it, not a design choice a document may take — the module's
   own rule 3 ("no fabricated coefficients"), and its basis string prints the
   vector *as the owner's, unvalidated*.
2. **It may not seat an engine in the composite by adjacency** (invariant 17,
   `README.md` §2.1). `NewsScore` and `SentimentScore` are excluded **by name**
   (`trade_score.py::_normalise:263` puts a non-engine key in `__excluded__`,
   never in the denominator), and that exclusion is printed in the block.
3. **It may not turn a score into a gate or a size** (invariants 11 and 18). The
   17-check `GATE_PRECEDENCE` (`../TradingExecution/signald/contracts.py:42`) and
   `risk_multiplier.combine` (`strategies/risk_multiplier.py:37`) are downstream
   of the composite; `execution_contract.py::opportunity_score:240` stays `None`
   (owner Q1) and no hit for `trade_score` exists anywhere under
   `TradingExecution/` (`grep -rn "trade_score\|TradeScore" TradingExecution/
   --include=*.py` → no match).
4. **It may not restate the note as a decision.** Where the note and a recorded
   owner decision disagree, the decision governs, and the disagreement is
   recorded here as an open question for the owner (§6) — not resolved by this
   document.

### 0.3 Vocabulary — the note uses four names the repo has already spent

| The note's name | What the repo already means by it | Where |
| --- | --- | --- |
| Composite Trade Score (CTS) | `TradeScore`, the four-engine decision composite — **built** | `strategies/trade_score.py::trade_score:293` |
| **Opportunity Score** | `opportunity_score`, the **executor-owned** 0-100 slot that this repo leaves `None`; the key is deliberately **absent** from the composite's return dict | `execution_contract.py::opportunity_score:240`, `trade_score.py:314` |
| Alpha Score (Composite Alpha) | `alpha_eval.alpha_score`, a **forecast-accuracy** scorer (predicted direction/magnitude vs realized return), and the Phase C signal statistics (`ic`, rank IC, ICIR, decile spread) — neither is an expected excess return | `strategies/alpha_eval.py::alpha_score:229`, `strategies/alpha_health.py::score_evaluation_rows:627` |
| Confidence | `coverage` — a printed **weight fraction**, not a multiplier; and `alpha_eval`'s caller-supplied `confidence` parameter | `strategies/score_engine.py::combine:142`, `alpha_eval.py:231` |
| "composite score / ranking score" (the industry names the note lists) | `get_composite_rank`, the **vendor screener's** per-name rank, an unrelated object | `agents/utils/analysis_tools.py::get_composite_rank:5292` |

`RegimeConfidence` deserves its own line: the master's four-outputs rule
(`README.md` §1.4) illustrates the fourth output with `RegimeConfidence 0.75`, and
**that number has no producer** — it appears in the owner's library
(`../../Strategies/scores/regime_score.md:2190`) and in `RegimeScore.md` §104 as an
ABSENT output. The rule is about *types* and stands on the other three, which are
built: the score (`strategies/regime_score.py::regime_score:265`), the sizing
multiplier (`strategies/overlays.py:80`, `position_scale`) and the state label
(`strategies/regime_state.py:82`, `STRONG_BULL`). The master carries a dated
clarification for this (§2.3).

---

## 1. The built object, exactly

### 1.1 The facts, each with its producer

| Property | Value | Symbol |
| --- | --- | --- |
| Engines, in weight order | `fundamental, technical, regime, risk` | `trade_score.py::ENGINE_ORDER:65` |
| Weights (the owner's, re-affirmed 2026-09-17, **unvalidated**) | 0.40 / 0.25 / 0.15 / 0.20 | `trade_score.py::ENGINE_WEIGHTS:100` |
| A **different** object, six engines | 0.35 / 0.20 / 0.15 / 0.15 / 0.075 / 0.075 | `trade_score.py::RESEARCH_ALLOCATION:112` |
| Minimum engines for a composite | 2 | `trade_score.py::COMPOSITE_MIN_COVERAGE:126` |
| Advisory bands | **none** — declared empty, so a test can assert it | `trade_score.py::TRADE_BANDS:134` |
| Status ladder | `RESEARCH_ONLY` → `VALIDATED` → `CONTRACT_MIGRATION` → `PRODUCTION`, contiguously, each rung needing a **record** | `trade_score.py::promotion_state:185` |
| Printed block | weights, per-engine rows, coverage, excluded names, basis | `trade_score.py::format_trade_score:432` |
| Gate | `enable_trade_score`, default **False** | `trade_score.py::GATE_NAME:58`, `default_config.py:1246` |
| Leaf | `get_trade_score`, assembled by `_trade_score_engines` | `agents/utils/analysis_tools.py::get_trade_score:6388`, `::_trade_score_engines:6000` |
| Registry entries | `trade` in `ENGINE_GATES` / `COMPOSITE_ENGINES` / `ENGINE_TOOLS` | `strategies/quant_scorecard.py::ENGINE_GATES:78`, `::COMPOSITE_ENGINES:94`, `::ENGINE_TOOLS:97` |
| Report position | printed **last** of the eight engines | `agents/utils/report_hygiene.py:246` |

### 1.2 The aggregation rule — a renormalised weighted mean, not a raw sum

`combine` (`strategies/score_engine.py::combine:142`) is the one implementation
both the engines and the composite use. Its semantics, which are what the note's
`CTS = Σ wᵢSᵢ` does **not** capture:

* score = `Σ(wᵢ·vᵢ) / Σ(wᵢ for present i)` — an absent component leaves the
  **denominator** instead of contributing a zero;
* `coverage` = `Σ(w present) / Σ(w total)` — a **weight fraction**;
* `floor` = `coverage_floor(min_coverage, n_present)` — a **component count**
  (`score_engine.py::coverage_floor:53`), a different unit, exposed separately so
  a reader is not left parsing it out of the withheld reason;
* below the floor the score is `None` with its reason — **never 0, never 50**;
* a component with no declared weight is **dropped with the reason printed**.

So the built composite is *renormalised*, and the note's plain `Σ wᵢSᵢ` with
"`Σ wᵢ = 1`" holds only when every engine is present.

### 1.3 The acceptance case, and its arithmetic

`tests/test_trade_score.py:57` pins `F 92 / T 85 / R 78 / K 35`; the composite is
asserted as `76.75` at `:300`, `:313`, `:472`, `:617`, and the documented example
in `strategies/quant_scorecard.py:655` prints the same number:

$$0.40(92) + 0.25(85) + 0.15(78) + 0.20(35) = 76.75$$

The `K` leg moves the number over exactly its 20 points of weight at these legs
(§3.4 works the whole range), and the reported read is *"evidence favourable
overall, risk conditions unfavourable"* — the reviewer asks why risk is the low
leg. The `NO NEW RISK` that may follow is the **downstream gate's** verdict
(`README.md` §1.4), never this module's.

### 1.4 The contract the printed block holds

`format_trade_score`'s docstring states the invariant that most constrains any
proposal in the note: *"the leaf's tool text and the run-card block both read the
same dict, so a reader can recompute the printed number from the printed
attribution rows instead of quoting it."* Every attribution row carries
`letter`, `raw`, `value`, `weight` and `state` (`trade_score.py:398-420`), and the
composite line names the vector actually used (`weights_basis`) and the coverage.
**A non-additive composite cannot keep that promise** — §3.7.

---

## 2. Where the note is already the repo's architecture

### 2.1 Its three layers exist and are enforced

| The note's layer | Built as | Where |
| --- | --- | --- |
| Layer 1 — evidence scores | six engine composites + the structural scorers; `EventScore` has none **by decision** | `README.md` §1.3; `EventScore.md` §7 |
| Layer 2 — composite | `trade_score` | §1.1 above |
| Layer 3 — risk / execution gates | 17 fail-closed checks, the risk governor, the soft/hard multiplier | `../TradingExecution/signald/contracts.py:42`; `strategies/risk_multiplier.py::combine:37` |

Its closing statement — *"Score = measurement. Gate = constraint. LLM =
adjudication/research interpretation"* — is the repo's own master rule 2 plus
`README.md` §1.4's "what the composite is for", and its worked example
(`CTS = 82` does not mean `BUY` because `RiskGate = REJECT`) is the acceptance
case the tests already encode (`tests/test_trade_score.py:470`).

### 2.2 Its News/Sentiment recommendation is the current rule, not a change

The note says it would *not* put `NewsScore` and `SentimentScore` into the core
trade score, but treat them as "context / modifiers / attribution". That is
invariant 17 verbatim, implemented as an exclusion **by name** with the excluded
keys printed (`trade_score.py::_normalise:263`), and the six-engine table exists
separately as `RESEARCH_ALLOCATION:112` — a different object with a different job.

**Nothing to change, and the note itself supplies the reason the repo already
kept them out: "without allowing noisy short-term information to dominate the
core score."**

### 2.3 One doc-level inaccuracy this round corrected, and no code defect

Reviewed for defects rather than adopted: the composite path itself was read line
by line (`trade_score.py` in full, `score_engine.combine`, `risk_multiplier`,
the leaf and the report block) and **no code defect was found**. Two consumer
details were checked because the note's confidence proposal depends on them:

* the readers test `is not None`, not truthiness — `quant_scorecard.py:189`
  (`STATE_MEASURED if e.get("score") is not None else STATE_NA`) and `:521`, `:576`
  the same. So a legitimate `0` would read as measured, which is exactly why the
  module's "never 0" is a rule about **missing inputs**, not a guard on a real
  zero (§3.5);
* `coverage_floor` is one implementation, floored at 1, and cannot exceed the
  component count it is resolved against (`score_engine.py::coverage_floor:53`).

The inaccuracy is in **our** master doc, not code: `README.md` §1.4's four-outputs
paragraph illustrates the fourth output with `RegimeConfidence 0.75`, which has no
producer (owner's library only, `../../Strategies/scores/regime_score.md:2190`;
`RegimeScore.md` §104 records it ABSENT). It now carries a dated clarification
naming the three outputs that **are** built. Reported, not silently edited, for
the owner's own documents: `TechnicalScore.md` §1's volatility row and
`MEASUREMENT_FINDINGS.md:126` (both already on the open list).

---

## 3. The note, claim by claim

Verdict vocabulary: **PRESENT** (already built as described), **PRESENT,
DIFFERENT NAME** (built, the note's name is taken by something else),
**ABSENT** (nothing in the tree), **CONTRADICTS** (adopting it as written breaks a
binding invariant or a recorded owner decision).

### 3.1 The ledger

| # | The note says | Verdict | Evidence |
| --- | --- | --- | --- |
| 1 | "Composite Trade Score" is legitimate but not a standardized industry formula | **PRESENT** as a concept; the repo's object is `TradeScore` | §0.1, Appendix A.1 |
| 2 | `CTS = Σ wᵢSᵢ`, `Σ wᵢ = 1` | **PRESENT, with a difference**: renormalised over present components, `coverage` reported | `score_engine.py::combine:142` |
| 3 | V1 vector: `0.30F + 0.20T + 0.15V + 0.10Rg + 0.10E + 0.10K + 0.05S` | **CONTRADICTS** invariant 17 and has no producers for two legs | §3.3 |
| 4 | Three layers: evidence → composite → gates | **PRESENT** | §2.1 |
| 5 | Score = measurement, gate = constraint, LLM = adjudication | **PRESENT** (master rule 2, `README.md` §1.4) | §2.1 |
| 6 | Two composites: `OpportunityScore = f(evidence)`; `TradeScore = f(OpportunityScore, RiskScore)` | **CONTRADICTS** the owner's `opportunity_score` decision (Q1) on the name, and invariant 18 on the shape | §3.4 |
| 7 | `RiskMultiplier = RiskScore / 100` | **PRESENT, in the other layer** — and moving it inside the composite double-counts `K` | §3.4 |
| 8 | `CTS = OpportunityScore × RiskAdjustment × ConfidenceAdjustment` | **ABSENT** as a score shape; **CONTRADICTS** the four-outputs rule and the printed-coverage rule | §3.5 |
| 9 | Coverage-adjusted confidence divides by 100 and multiplies | **ABSENT** — `coverage` is a printed qualifier; the N-deflation question is open (decision 12) [CORRECTED 2026-09-26: the reference dangles — `IMPLEMENTATION_PLAN.md` §13 Q12 is the semivariance measure. The coverage/N-deflation question is this document's §6 Q3 (answered 2026-09-26) plus owner Q4's label; see §3.5's correction.] | §3.5 |
| 10 | News / Sentiment / Social / Analyst revisions / Options / Flows as context, not core | **PRESENT** for News and Sentiment (invariant 17); the rest are leaves, not engines | §2.2, `NewsScore.md` §8 |
| 11 | A 7-engine `OpportunityScore` weighting `Valuation` and `Event` | **ABSENT / CONTRADICTS** — `ValuationScore` has no producer at all; `EventScore` has no composite by decision | §3.3 |
| 12 | Nonlinear composite: `Σ wᵢSᵢ + Σ_{i<j} γᵢⱼ SᵢSⱼ` | **ABSENT**; needs measurement, and breaks recomputable attribution | §3.7 |
| 13 | Standardized composite: `Zᵢ = (Sᵢ − μᵢ)/σᵢ`, then `50 + 10·Σ wᵢZᵢ` | **ABSENT for engine scores**; the repo has one z implementation, and a production run has no cross-section | §3.6 |
| 14 | Separate `CompositeAlphaScore` (expected excess return) from `CompositeTradeScore` | **ABSENT**, and the name `alpha_score` is taken by a forecast-accuracy scorer | §3.8 |
| 15 | Hard gates stay outside the score, `RiskGate = REJECT ⇒ NoNewRisk` | **PRESENT** | §2.1, `tests/test_trade_score.py:470` |
| 16 | `TradeScore = f(AlphaScore, Risk, Regime, Liquidity, EventRisk)` | **CONTRADICTS** if read as a composite: liquidity is already a **gate** and a **soft multiplier** | §3.9 |
| 17 | Raw scores have different distributions, so raw averaging mis-weights engines | **PRESENT as a live concern**, and it is a measurement question, not a formula question | §3.6 |
| 18 | *(found while writing this doc)* the multiplicative confidence idea already exists in the owner's own survey, as a **separate** object | **PRESENT** — `Strategies/other_score.md` §32 `Conviction = BaseSignal × DataConfidence × Agreement × (1 − Risk)`, with the rationale "confidence in the evidence, rather than pretending that confidence is another directional alpha score" | §3.10 |

### 3.2 The direction convention the note does not mention

Every engine is 0-100 with **100 = favourable for the position** (`README.md`
§1.2), which is why `RiskScore` reads 100 = *low* risk
(`strategies/risk_score.py::risk_score:521`). The note's `RiskAdjustment =
RiskScore/100` is therefore arithmetically coherent — but note what direction it
imposes: the multiplier is 1.0 at zero risk and 0.0 at maximum risk, so the
**product is monotone in `K` in the same direction as the weighted sum**. The two
shapes are not opposites; they are two different *influences* for the same leg.
Quantified in §3.4.

### 3.3 The seven-engine vector — three separate reasons it cannot be adopted as written

The note's V1 vector is introduced as *"For example"*, so it is read here as an
illustration and not a decision. Taken as a vector, it breaks three things:

1. **Invariant 17.** `NewsScore` and `SentimentScore` do not directly contribute
   to the decision composite; an engine joins only by an explicit decision. The
   note's own §2.2 recommendation (News/Sentiment out of the core) **contradicts
   its own V1 vector**, which weights `Sentiment 0.05` — the note's Layer-2 list
   drops Sentiment while the V1 formula keeps it.
2. **No producer.** `ValuationScore` has no module, gate, leaf or config key
   (`ValuationScore.md` §0.1 is the grep), so a `0.15` weight would be a weight on
   a number that cannot be computed; `MarketScore` likewise absent.
3. **`EventScore` has no composite by decision.** `event_state.py::event_state:591`
   is a structured state, not a 0-100 score (`EventScore.md` §1; plan §13 Q7), so
   `+0.10·Event` has nothing to read.

The V1 vector is therefore an **open question** (§6 Q7), not a specification.

### 3.4 The product form, worked on the acceptance case

Same four inputs, two shapes. Renormalisation over present components is applied
to both (the note's Layer-2 OpportunityScore is written over the six engines it
lists, so the `F/T/Rg` legs carry `0.30/0.20/0.10` of its weight and renormalise
over `0.60`):

| Shape | `K = 35` (the case) | `K = 0` | `K` absent (`NA`) | `K = 100` | `K`'s whole influence |
| --- | --: | --: | --: | --: | --- |
| **Built** — weighted mean incl. `K` at 0.20 | **76.75** | 69.75 | 87.19 *(renormalised over 0.80)* | 89.75 | **20 points** (its weight) |
| **Note** — `Opportunity × K/100` | 30.57 *(87.33 × 0.35)* | 0.00 | 87.33 *(the product has no rule for `NA`)* | 87.33 | **87.33 points** (a 100% multiplier) |

Three consequences, each of which is a decision rather than a detail:

* **The composite gains a legitimate `0`.** Under the product a maximally risky
  name scores exactly `0`, while a *missing* risk read has no defined behaviour —
  the built object's `NA`-leaves-the-denominator rule (`§1.2`) has no analogue in
  a product, and `0` vs `None` is a distinction three consumers already depend on
  (§2.3). A product form must state what `K = NA` does, or it silently reads as
  maximum risk.
* **The attribution stops summing to the number** (§1.4) unless the block is
  redesigned to print a multiplier row.
* **Risk gets counted once or twice — and the repo has the multiplier.** The
  multiplicative risk adjustment **already exists** one layer down:
  `strategies/risk_multiplier.py::combine:37` multiplies the soft factors
  (`SOFT_CATALOG:18` — `regime`, `vol_cap`, `knife`, `drawdown`, `liquidity`,
  `momentum`, `flow`), zeroes the product when any hard flag is set
  (`HARD_NAMES:22`), and is reached from the leaf
  `agents/utils/quant_adds_tools.py::get_position_risk_multiplier:98`. So:

  * **reading (a), replace:** drop `K` from the weighted legs and multiply by
    `K/100` — risk counted once, but invariant 18 ("`RiskScore` contributes the
    `R`/`K` component of the four-engine composite") must be **amended**, and
    `COMPOSITE_MIN_COVERAGE` / the printed block change meaning;
  * **reading (b), add:** keep `K` at 0.20 **and** multiply — `RiskScore` then
    moves the number twice, which invariant 11 ("Score → decision information.
    Sizing multiplier → sizing. Do not merge them.") and invariant 15 (no derived
    quantity with two contributing implementations) forbid.

  Both readings are internally coherent; **neither is this document's to choose**
  (§6 Q1).

### 3.5 The confidence multiplier, against the two rules it would replace

`CTS = O × R × C` with `C = CoverageAdjustedConfidence / 100`. Nothing in the tree
produces a coverage-adjusted confidence, and the two rules it would supersede are
explicit:

* **"A number is only as good as its coverage, and the reader must see both"**
  (`README.md` §1.4): `TradeScore 72` at `coverage 68%` must read as *72 over 68%
  of the intended evidence*, with the missing components **named**. Folding
  coverage into the number destroys exactly that — after deflation, `51` no longer
  says *which* evidence was missing, and the absent list would have to be printed
  anyway to keep the block honest.
* **"Score, scale, state and confidence are four different outputs"**
  (`README.md` §1.4): confidence is a separate output, never collapsed into the
  score. The note's `C` collapses it, and `R` (the risk multiplier) collapses a
  *sizing* multiplier into a *score* — the same merge invariant 11 forbids.

This is also the live topic of the **score panel's coverage question** (owner Q4
labels a sub-floor run `INSUFFICIENT_CROSS_SECTION`; `IMPLEMENTATION_PLAN.md` §13
Q12 is a *different* decision — the semivariance measure — so the earlier "decision
12" reference here was wrong and is corrected), so the note is not inventing a
question; it is proposing a specific answer to an open one. Recorded as §6 Q3.

### 3.6 Standardization — what exists, and why it is panel-time

`Zᵢ = (Sᵢ − μᵢ)/σᵢ` needs a cross-section **per engine per date**. Three facts:

* The repo has **one** z implementation and a rule that there be no second:
  `strategies/cross_section.py::cross_sectional_z:70`, cited as such by
  `strategies/analyst_revisions.py:20`. `strategies/alpha_zoo.py:116` is a
  *signal-expression* `zscore` operator, a different layer.
* A production run scores **one ticker at a time**; the only per-date
  cross-section producer in the tree is the Phase C validation panel,
  `scripts/score_panel.py` (one snapshot per trading date, `…/panels/<date>.json`,
  per-date cached). A standardized composite is therefore **panel-time research
  today**, and would need a panel (or intra-run peers) to exist at run time.
* Standardizing changes what the number **means**: every engine's composite is a
  band-mapped 0-100 with a printed band table (empty for the composite,
  deliberately). `50 + 10·z` reintroduces a 0-100 scale whose meaning differs from
  every other engine's, so it needs its own scale key and its own vocabulary —
  and the note's own motivation (different engine distributions) is precisely what
  Phase C measures per factor (`strategies/alpha_health.py::score_evaluation_rows:627`) and
  what `MEASUREMENT_FINDINGS.md` reports. **Measure first, then decide whether
  weighting or standardization is the right correction** (§6 Q4).

### 3.7 Interaction terms — the coefficient problem and the attribution problem

`Σ_{i<j} γᵢⱼ Sᵢ Sⱼ` is **absent**, and the module's rule 3 ("no fabricated
coefficients") is the first obstacle: `γᵢⱼ` is a coefficient, and the repo's
discipline is that a coefficient arrives with a **record** — the same rule that
keeps the composite's own vector at `RESEARCH_ONLY` (`trade_score.py::PROMOTION_
EVIDENCE:159` requires a WP-10 measurement with vector id, universe, IC/rank IC/
ICIR/decile spread/monotonicity/OOS). The second obstacle is the printed-block
contract (§1.4): a non-additive score cannot be recomputed from attribution rows
unless the interaction terms are themselves printed as rows.

The design question is real and documented in the literature (Appendix A.3:
nonlinear/noncompensatory aggregation is a defensible *choice* that must be
declared, and it changes what a ranking means). The note's own example —
`Technical × Event` — is testable, and the honest path is the one the plan
already has: measure the interaction on the panel (§6 Q5).

### 3.8 A separate Composite Alpha Score — name taken, and a missing scale

The note's `AlphaScore` answers *"what is the expected excess-return signal?"*.
Nothing in the tree produces one:

* `strategies/alpha_eval.py::alpha_score:229` is a **forecast-accuracy** scorer
  over `{direction, predicted_magnitude, period_days, actual_return, confidence}`
  — it grades what a report *said* against what happened, and its `confidence`
  argument is caller-supplied text, not a computed quantity;
* the repo's signal-quality layer is `strategies/alpha_health.py::score_evaluation_rows:627`
  (IC / rank IC / ICIR / decile spread / ordering / turnover / OOS), run by the
  panel — measurement of a score, not a score;
* an expected excess return needs a **return scale, a horizon and a benchmark**,
  and the engine composites are 0-100 bands on a daily convention (invariants 13
  and 16). The conversion is the standard one (Appendix A.2: information
  coefficient × volatility × standardized score), and **IC and σ are exactly what
  Phase C measures**. A `CompositeAlphaScore` is therefore *possible later, from
  measured inputs* — not a rename of anything present (§6 Q6).

### 3.9 Liquidity, and the two layers it already occupies

The note's `TradeScore = f(AlphaScore, Risk, Regime, Liquidity, EventRisk)` adds
liquidity to the final composite. Liquidity is already:

* a **gate**: `"liquidity"` is one of the 17 `GATE_PRECEDENCE` checks
  (`../TradingExecution/signald/contracts.py:42`), fail-closed;
* a **soft sizing factor**: `"liquidity"` in `risk_multiplier.SOFT_CATALOG:18`.

Adding it as a composite *term* would make one quantity influence the decision at
three layers — invariant 15's exact concern. The `MarketScore` library's own
Liquidity sub-score (`MarketScore.md` §1) is the honest place for a liquidity
*measurement*; the composite is not.

### 3.10 The coherent reading of the product form — the owner's survey already separates it

The note's `OpportunityScore × RiskAdjustment × ConfidenceAdjustment` is not new to
this design set. The owner's survey specifies the same multiplicative confidence
layer on a **different object** (`../../Strategies/other_score.md:1061`):

> `Conviction = BaseSignal × DataConfidence × Agreement × (1 − Risk)`
>
> *"This gives you **confidence in the evidence**, rather than pretending that
> confidence is another directional alpha score."*

Three consequences for §3.4 and §3.5:

1. **It is the clean resolution of the double-count problem.** A separate
   `Conviction`-shaped object multiplies agreement, data confidence and risk
   *without* changing `TradeScore`'s shape: `RiskScore` keeps its `K` leg in the
   decision composite (invariant 18), the sizing multiplier stays in the sizing
   layer (invariant 11), and confidence stays a separate output (`README.md`
   §1.4). The note's product is the same arithmetic applied to the **wrong
   object** — the decision composite — which is what turns it into a re-weighting
   of `K` rather than a second measurement.
2. **The survey's `(1 − Risk)` term has the direction inverted for this repo.**
   Every engine is 0-100 with 100 = favourable (`README.md` §1.2) and `RiskScore`
   reads 100 = **low** risk (`strategies/risk_score.py::risk_score:521`), so
   `1 − Risk/100` is **1 at maximum risk and 0 at minimum risk** — the opposite of
   the multiplier the note itself writes (`RiskScore/100`, 1.0 at the favourable
   end). An implementer following the survey literally would invert the risk leg.
   The two documents in the owner's own set disagree; the repo's direction
   convention settles it, and this is the kind of contradiction the ledgers exist
   to surface.
3. **Two of the survey's four legs have no producer of that shape.** A data-quality
   aggregate exists (`strategies/data_quality.py::aggregate_quality:46`), but
   `Agreement` — agreement *across the engines* — does not: the nearest producer is
   `strategies/score_disagreement.py::risk_disagreement:128`, which compares **one**
   engine (`RiskScore`'s band) against the risk debate's own words and emits a
   **flag**, never a number; and `strategies/consensus.py::agreement_score:14`
   measures agreement among **analyst ratings**, a different input. So a
   `Conviction` object is buildable only after a cross-engine agreement read and a
   data-confidence read exist — §6 Q8.



---

## 4. What adopting each item would require

No item below may be started without the owner decision named in §6. The
"needs" columns name the **missing producer** — the thing that does not exist —
not an estimate.

| Item | Missing producer / input | Measurement behind it | Contract / ladder step | Decision |
| --- | --- | --- | --- | --- |
| Product form `O × K/100` (§3.4) | none — arithmetic only | none (it is a re-weighting) | printed block redesign; ladder rung `CONTRACT_MIGRATION` if any consumer reads it; invariant 18 amendment if `K` leaves the legs | **Q1** |
| `OpportunityScore` as a named object (§3.4) | a producer, and a scale distinct from `opportunity_score` | as above | a schema + version bump; the executor slot stays `None` | **Q2** |
| Coverage/confidence multiplier (§3.5) | a coverage-adjusted confidence producer (absent) | calibration of the discount | printed block redesign; supersedes the "reader must see both" rule | **Q3** |
| Cross-sectional standardization (§3.6) | a run-time cross-section (only the panel has one) | per-engine μ/σ distributions, per universe | a new scale key + vocabulary | **Q4** |
| Interaction terms `γᵢⱼ` (§3.7) | a fitted `γ` table with a record | WP-10 protocol (IC/ICIR/decile spread/monotonicity/OOS) per pair | attribution rows for each interaction | **Q5** |
| `CompositeAlphaScore` (§3.8) | IC and σ per engine/horizon; a return scale and benchmark | Phase C, per factor, already specified | new object + name (collision in §0.3) | **Q6** |
| Seven-engine vector (§3.3) | `ValuationScore` (no producer), `EventScore` composite (none by decision) | — | invariant 17 amendment | **Q7** |
| A separate `Conviction` object (§3.10) | a cross-engine **agreement** read and a **data-confidence** read (`strategies/data_quality.py::aggregate_quality:46` is the nearest producer) | calibration of both | new object + name; the survey's `(1 − Risk)` direction corrected | **Q8** |

---

## 5. Verification requirements, if any of this lands

Written now so a future implementation cannot land without them:

1. **Additive forms only, unless §6 Q5 says otherwise:** a test asserting the
   printed attribution rows recompute the printed score
   (`format_trade_score:432`'s promise), with a `K`-absent case.
2. **`NA` is not `0`, in every shape.** If a multiplicative form lands, a test
   must pin what `K = NA` does; today the analogue is
   `COMPOSITE_MIN_COVERAGE:126` + `combine`'s withheld-with-reason (`§1.2`), and a
   product must not silently read `NA` as maximum risk.
3. **No configuration promotes the vector** (`trade_score.py::promotion_state:185`
   — a flag is not a record), unchanged.
4. **A new coefficient needs a record.** Any `γ`, any new weight vector, any
   standardization constant: named producer, universe, OOS — or it ships
   `RESEARCH_ONLY` and says so.
5. **Direction stays one convention** (`README.md` §1.2): a multiplier is 1.0 at
   the favourable end, and a test states the direction it imposes.
6. **The gate boundary is untouched:** no score may reach `GATE_PRECEDENCE`, the
   size, or `opportunity_score` (`execution_contract.py::opportunity_score:240`).

---

## 6. OPEN questions for the owner

* **Q1 — the composite's shape.** Is the weighted mean with `K` at 0.20 still the
  decision composite, or does the risk leg become multiplicative? If
  multiplicative: reading **(a)** (`K` leaves the weighted legs, invariant 18
  amended, attribution redesigned) or reading **(b)** (`K` stays and is also
  multiplied — which invariants 11 and 15 forbid as written)?
  **[ANSWERED 2026-09-26: keep the weighted mean; no multiplication.** The
  owner's reasoning is attribution: a product *"becomes difficult to interpret and
  attribution becomes difficult"*, and this is *"a research/audit-oriented
  quantitative engine, not merely an opaque ranking model"*. The accepted form is
  unchanged — `0.40 F + 0.25 T + 0.15 R + 0.20 K` — and with the owner's own
  acceptance case it reads `0.40(90) + 0.25(85) + 0.15(80) + 0.20(40) = 76.25`,
  which the built code prints as **76.75** because `RiskScore` is aligned
  `higher_is_better` (100 = low risk) before it enters; the alignment is the
  engine's, and the arithmetic above uses the raw leg values. **Invariant 18 is not
  amended.** Two shape rules follow and are now stated: **(1)** `K = RiskScore` is an
  **input to the composite**, and the **hard risk gates remain outside it** —
  `CompositeTradeScore ≠ RiskGate`, so a composite of 84 beside a
  `RiskGate = REJECT` is a valid, meaningful pair: *"the quantitative evidence
  indicates a strong opportunity, but portfolio/risk constraints prohibit adding
  exposure."* **(2)** the three objects are named and kept distinct —
  `EngineScore` (*what does this evidence dimension say?*), `CompositeTradeScore`
  (*what does the combined quantitative evidence say about the trade setup?*) and
  `DecisionGate` (*is taking the trade permitted?*) — and *"those should not be
  collapsed into one number."* `MASTER_PLAN.md` §2.1.]**
* **Q2 — the name `OpportunityScore`.** The note's `OpportunityScore` and
  `execution_contract.opportunity_score()` are the same words for different
  objects; the slot is producer-owned and stays `None` (your Q1). Is a *second*,
  research-side opportunity object wanted — under what name — or is the
  four-engine composite the only one?
* **Q3 — coverage: multiplier or printed qualifier?** Folding coverage into the
  number contradicts "the reader must see both" and the four-outputs rule. This is
  the score panel's open N-deflation question with a specific proposed answer
  attached.
  **[ANSWERED 2026-09-26: neither a multiplier nor a silent qualifier — coverage
  SHRINKS THE SCORE TOWARD 50, and the parts are published separately.** The
  owner's objection to deflation is semantic: with `RawScore = 80` at 50% coverage,
  `80 × 0.50 = 40` says *"the stock is bearish"*, when what is known is *"the
  available evidence is bullish, but incomplete"* — *"those are fundamentally
  different statements."* The accepted form is

  $$Score_{adjusted} = 50 + Coverage^{\gamma}\,(Score_{raw} - 50),\quad 0 \le Coverage \le 1$$

  with γ controlling the penalty (γ = 1 gives 65 from the case above), and the
  report publishes **four** numbers rather than one:

  ```text
  Composite Trade Score: 80     (Score_raw)
  Coverage:              50%
  Confidence:            42%
  N:                     5 / 10
  ```

  *"Strong measured signal, incomplete evidence"* is then readable by the model
  without missing data being read as negative evidence. Consequences: the
  "reader must see both" rule **stays** (it was never the thing to supersede — the
  multiplier was); the shrunk value is a **new, separate output**, never a
  replacement for the raw score; γ and the confidence recipe are declared
  parameters that need their own record (module rule 3) before they are used; and
  the shrink must be tested **below 50 as well as above** (a 20 at half coverage
  moves toward 50, not away). `MASTER_PLAN.md` §2.1; the producer is Phase 7's
  CTS-1/CTS-9.]**
* **Q4 — standardization.** Do you want a cross-sectional z composite (today only
  computable in the validation panel), or does the 0-100 band convention stay?
* **Q5 — interactions.** Is measuring `γᵢⱼ` in scope for Phase C/E, or does the
  composite stay additive?
* **Q6 — a second alpha object.** Do you want a `CompositeAlphaScore` (expected
  excess return) as a distinct object, under a name that does not collide with
  `alpha_eval.alpha_score`?
* **Q7 — the V1 seven-engine vector.** Withdrawn as an illustration, or proposed
  as a replacement for `0.40 / 0.25 / 0.15 / 0.20`? If the latter, it needs
  `ValuationScore` and an `EventScore` composite to exist first, plus an explicit
  invariant-17 decision on Sentiment (the note's own §2.2 argues against it).
* **Q8 — a `Conviction` object.** Your survey's §32 already specifies the
  multiplicative confidence layer, as a **separate** object
  (`Conviction = BaseSignal × DataConfidence × Agreement × (1 − Risk)`). Do you
  want it built — which needs a cross-engine agreement read and a data-confidence
  read, neither of which exists — and with the risk leg written `RiskScore/100`
  (this repo's 100 = favourable convention) rather than the survey's `(1 − Risk)`?
  **[ANSWERED 2026-09-26 — the object is wanted, and the survey's formula is
  SUPERSEDED.** The owner's meta layer is *"meta-properties of the scorecard, not
  new evidence engines"*, and its Conviction is

  $$Conviction = AgreementScore \times EvidenceConfidence$$

  (or `Agreement × Coverage × DataQuality`), normalised 0-100 — *"this makes
  conviction explainable."* **There is no `BaseSignal` leg and no risk term**: the
  survey's `BaseSignal × DataConfidence × Agreement × (1 − Risk)` is replaced, so
  the `(1 − Risk)` direction question this row asks is **moot** — risk is a gate
  (D3), not a multiplier inside a conviction. `AgreementScore` comes from the meta
  layer's own cross-engine agreement (`Agreement = |Σ wᵢxᵢ/Σ wᵢ|` over centred
  engines, `Dispersion = √(Σ wᵢ(xᵢ−x̄)²/Σ wᵢ)`,
  `AgreementScore = 100·e^(−k·Dispersion)`); `EvidenceConfidence` is the
  data-quality/coverage read the fundamental engine already computes. The meta
  layer is **downstream only** — no engine reads it. `MASTER_PLAN.md` §2.1 (D6);
  the build is Phase 7's `CTS-8`/`UNIV-AGREE`.]**

---

## Appendix A — external sources, verified this round

Each DOI was resolved through CrossRef and the title, author, journal/publisher
and year below are what the record returned. Nothing else is quoted from them.

**A.1 Composite indicators — normalization, weighting and aggregation are
normative choices.** OECD / European Union / Joint Research Centre (2008),
*Handbook on Constructing Composite Indicators: Methodology and User Guide*,
OECD Publishing. DOI [`10.1787/9789264043466-en`](https://doi.org/10.1787/9789264043466-en).
*Bears on:* the note's V1 weights, its `50 + 10·z` standardization and its
interaction term are three separate aggregation choices. The handbook's whole
purpose is to make such choices explicit, tested for robustness and reported —
which is what `§4`'s "measurement behind it" column requires here.

**A.2 From signal to expected excess return — the conversion needs IC and σ.**
Grinold, R. C. (1989), "The fundamental law of active management", *The Journal of
Portfolio Management*. DOI [`10.3905/jpm.1989.409211`](https://doi.org/10.3905/jpm.1989.409211).
*Bears on:* §3.8. A 0-100 band score is not an expected excess return; the
standard bridge is information coefficient × volatility × standardized score, and
this repo measures IC and the standardized score statistics in Phase C
(`strategies/alpha_health.py::score_evaluation_rows:627`), not in a formula.

**A.3 Nonlinear and noncompensatory aggregation is defensible but must be
declared.** Munda, G. & Nardo, M. (2009), "Noncompensatory/nonlinear composite
indicators for ranking countries: a defensible setting", *Applied Economics*. DOI
[`10.1080/00036840601019364`](https://doi.org/10.1080/00036840601019364).
*Bears on:* §3.7. The paper's point is that a nonlinear/noncompensatory
aggregation rule is not an improvement *or* a defect in the abstract — it changes
what the ranking means (a weak leg can dominate) and must be declared as a design
choice. That is exactly why `γᵢⱼ` here needs an owner decision plus a measurement,
not a preference.

---

## Appendix B — internal citations used, verified against the tree

| Claim | Symbol |
| --- | --- |
| four-engine order, letters, weights, floor, empty band table | `strategies/trade_score.py::ENGINE_ORDER:65`, `::ENGINE_LETTERS:67`, `::ENGINE_WEIGHTS:100`, `::COMPOSITE_MIN_COVERAGE:126`, `::TRADE_BANDS:134` |
| the different six-engine object | `strategies/trade_score.py::RESEARCH_ALLOCATION:112` |
| ladder and its evidence rule | `strategies/trade_score.py::promotion_state:185`, `::PROMOTION_EVIDENCE:159` |
| the composite and its printed block | `strategies/trade_score.py::trade_score:293`, `::format_trade_score:432` |
| the one aggregation implementation | `strategies/score_engine.py::combine:142`, `::coverage_floor:53` |
| the multiplicative risk adjustment, already downstream | `strategies/risk_multiplier.py::combine:37`, `::SOFT_CATALOG:18`, `::HARD_NAMES:22` |
| its leaf | `agents/utils/quant_adds_tools.py::get_position_risk_multiplier:98` |
| the executor's 17 checks (no score read anywhere under `TradingExecution/`) | `../TradingExecution/signald/contracts.py:42` |
| the `opportunity_score` slot this repo leaves `None` | `execution_contract.py::opportunity_score:240` |
| the name collision on `alpha_score` | `strategies/alpha_eval.py::alpha_score:229` |
| the Phase C signal statistics | `strategies/alpha_health.py::score_evaluation_rows:627` |
| the single z implementation | `strategies/cross_section.py::cross_sectional_z:70` |
| composite consumers | `agents/utils/analysis_tools.py::get_trade_score:6388`, `::_trade_score_engines:6000`, `strategies/quant_scorecard.py::ENGINE_GATES:78`, `agents/utils/report_hygiene.py:246` |
| the engines the note names | `strategies/fundamental_score.py::fundamental_score:252`, `::valuation_subscore:211`, `strategies/technical_score.py::technical_score:324`, `strategies/regime_score.py::regime_score:265`, `strategies/risk_score.py::risk_score:521`, `strategies/news_score.py::news_score:210`, `strategies/sentiment_score.py::sentiment_score:467`, `strategies/event_state.py::event_state:591` |
| the survey's multiplicative confidence layer, and its direction | `../../Strategies/other_score.md:1061` (§32), `:1027` (§31), `:1177` (the four meta-scores) |
| the nearest producers to that object's legs | `strategies/data_quality.py::aggregate_quality:46`, `strategies/score_disagreement.py::risk_disagreement:128`, `strategies/consensus.py::agreement_score:14` |
| the acceptance case | `tests/test_trade_score.py:57`, `:300`, `:313`, `:472`, `:617` |

---

## Related documents

* [`README.md`](README.md) — the master: §1.1 (seven engines, not one composite),
  §1.2 (direction convention), §1.3 (engine map), §1.4 (the composite, the
  research allocation, the gate-order conflict, the four-outputs rule), §2.1
  (the binding invariants), §7 (the decision record).
* [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) §8 (WP-11), §9 Phase C and
  Phase E — where a measurement of this vector lives.
* [`MEASUREMENT_FINDINGS.md`](MEASUREMENT_FINDINGS.md) — Phase C's live panel.
* [`ScoreContextContract.md`](ScoreContextContract.md) — how a composite reaches
  the LLM context as a supplied number rather than a tool-calling choice.
* [`../ScoreWeight/market.md`](../ScoreWeight/market.md) — the owner's own
  specification, which states the same discipline: keep the scores separate rather
  than creating one giant composite (`../ScoreWeight/market.md:324`).

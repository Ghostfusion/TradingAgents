# Design: Conditional Research Overlays for TradingAgents

**Status:** DESIGN — not built  
**Version:** 1.0  
**Date:** 2026-09-22  
**Scope:** Extend the existing 8-engine score architecture with conditionally activated research overlays, without creating an ever-growing set of permanent scores.

---

## 1. Executive Summary

### Problem

The current score architecture provides a compact, deterministic representation of broad investment dimensions:

1. FundamentalScore
2. TechnicalScore
3. RegimeScore
4. RiskScore
5. NewsScore
6. SentimentScore
7. EventScore
8. TradeScore

Those eight engines are intentionally reusable across stocks.

However, some stocks are materially affected by structural forces that do not fit cleanly inside those universal engines. Examples include AI disruption, tariffs, China exposure, commodity sensitivity, regulation, cybersecurity, or other sector-specific structural changes.

A naive solution is to create another permanent score for every important theme. That produces score proliferation, increases context size, creates arbitrary weighting problems, and eventually produces dozens of partially overlapping scores per stock.

### Design thesis

Do **not** turn every important theme into a permanent score.

Instead:

> Keep the eight universal engines as the stable quantitative backbone, and introduce a conditional **Research Overlay** layer that activates only when a structural theme is materially relevant to the company and supported by sufficient evidence.

The overlay is not necessarily a 0–100 score. It is a compact, structured evidence object containing only the dimensions relevant to that theme.

For example, an AI overlay can contain:

- Exposure
- Disruption pressure
- Adoption
- Monetization
- Moat impact
- Evidence confidence
- Time horizon
- Key evidence and counter-evidence

For INTU, the AI overlay would be active. For a company where AI is immaterial to the earnings thesis, it would be absent or explicitly marked N/A.

### Core architectural principle

```text
                 UNIVERSAL SCORE ENGINES
              ┌───────────────────────────┐
              │ Fundamental                │
              │ Technical                  │
              │ Regime                    │
              │ Risk                      │
              │ News                      │
              │ Sentiment                 │
              │ Event                     │
              │ Trade                     │
              └─────────────┬─────────────┘
                            │
                            ▼
                  MATERIALITY DETECTOR
                            │
             ┌──────────────┼──────────────┐
             ▼              ▼              ▼
          AI Overlay    Tariff Overlay   China Overlay
             │              │              │
             └──────────────┼──────────────┘
                            ▼
                    DECISION CONTEXT
```

Only material overlays enter the decision context.

---

# 2. Goals

## 2.1 Primary goals

1. Preserve the existing eight-engine architecture.
2. Prevent permanent score proliferation.
3. Capture structural forces that materially affect individual companies.
4. Keep overlay calculations deterministic wherever practical.
5. Keep LLM judgment separate from deterministic measurement.
6. Reduce final decision context rather than expanding it.
7. Make overlays reusable across sectors.
8. Make overlays evidence-backed and confidence-aware.
9. Support time-series tracking of structural changes.
10. Allow overlays to appear or disappear as materiality changes.
11. Preserve existing report contracts unless explicitly changed.
12. Integrate cleanly with the existing research-vs-decision-context separation.

## 2.2 Secondary goals

- Detect emerging structural risks earlier than the eight universal engines alone.
- Provide compact explanatory context to the final decision layer.
- Allow new themes to be added without modifying TradeScore.
- Make thematic analysis auditable.
- Support historical comparison of overlay state and trajectory.

---

# 3. Non-Goals

This design does NOT:

1. Replace the eight existing engines.
2. Add every conceivable theme as a permanent score.
3. Make the LLM responsible for calculating deterministic scores.
4. Make overlays direct buy/sell instructions.
5. Automatically modify TradeScore weights.
6. Override risk gates.
7. Create a universal "AI score" for every stock.
8. Treat speculative narratives as equivalent to observed evidence.
9. Predict stock price outcomes from an overlay.
10. Require every overlay to produce a 0–100 score.

---

# 4. Design Principles

## P1 — Eight universal engines remain the backbone

The existing score architecture remains the stable quantitative foundation.

## P2 — Overlay activation is conditional

An overlay exists in decision context only when materiality is established.

## P3 — Not applicable is not zero

If AI is irrelevant to a company, the correct state is:

`N/A — immaterial`

not:

`AI Score = 0`

A zero implies negative or absent exposure; N/A means the dimension is not decision-relevant.

## P4 — Evidence before scoring

An overlay should be driven by observed evidence, not by an LLM's generic belief that a theme "could" matter.

## P5 — Preserve dimensions instead of collapsing everything into one number

A single composite can hide opposing forces. The overlay should retain its major dimensions.

## P6 — LLM adjudication, deterministic measurement

Where reliable structured data exists, calculate it deterministically. The LLM should interpret and adjudicate evidence rather than inventing numeric measurements.

## P7 — Context should shrink, not grow

The overlay layer must support the existing objective of separating research context from decision context.

The final decision model receives a compact overlay summary, not the entire research universe.

## P8 — Overlays are time-series objects

The system should track both current state and direction of change.

## P9 — Materiality is dynamic

A theme can become material or immaterial over time.

## P10 — No overlay automatically changes TradeScore

An overlay informs the decision layer. It does not silently alter the four-engine TradeScore formula.

---

# 5. Terminology

### Universal Engine

A permanently available quantitative engine applicable across the stock universe.

Examples:

- FundamentalScore
- TechnicalScore
- RegimeScore
- RiskScore
- NewsScore
- SentimentScore
- EventScore
- TradeScore

### Research Overlay

A conditional evidence structure describing a material cross-cutting theme.

Examples:

- AI
- Regulatory
- Tariff
- China
- Commodity
- Cybersecurity
- FX
- Geopolitical
- Supply-chain

### Materiality

The degree to which a theme can plausibly affect revenue, margins, cash flow, competitive position, valuation, risk, or the investment thesis within the relevant horizon.

### Evidence Confidence

Confidence that the underlying facts and measurements are sufficiently supported.

### Disruption

Potential erosion of the company's existing economics, moat, pricing power, customer relationship, or workflow.

### Adaptation

The company's demonstrated ability to use the structural change to improve its own economics or competitive position.

---

# 6. Architecture

## 6.1 High-level flow

```text
Raw evidence
    │
    ├── Fundamental data
    ├── Price/technical data
    ├── News
    ├── Events
    ├── Filings
    ├── Company disclosures
    └── External research
             │
             ▼
      Universal Engines
             │
             ▼
      Overlay Detector
             │
             ├── materiality test
             ├── evidence sufficiency
             └── applicability test
             │
             ▼
       Active Overlays
             │
             ▼
      Overlay Summarizer
             │
             ▼
     Compact Decision Context
             │
             ▼
       LLM Adjudication
             │
             ▼
       Existing gates / PM
```

---

# 7. Overlay Lifecycle

Every overlay should follow the same lifecycle.

```text
DISCOVER
   ↓
DETECT
   ↓
QUALIFY
   ↓
COMPUTE
   ↓
SUMMARIZE
   ↓
DELIVER
   ↓
TRACK
   ↓
RETIRE
```

## 7.1 Discover

Evidence gathering identifies potential thematic relevance.

Example:

- repeated company discussion of AI
- material AI-related revenue
- competitors changing pricing due to AI
- new AI-native entrants
- large AI-related capex
- AI-related margin impact

## 7.2 Detect

The detector determines whether the theme may be material.

## 7.3 Qualify

The system verifies sufficient evidence exists.

## 7.4 Compute

Deterministic metrics are calculated where possible.

## 7.5 Summarize

A compact overlay object is generated.

## 7.6 Deliver

Only the compact object enters decision context.

## 7.7 Track

Store historical state and velocity.

## 7.8 Retire

If materiality falls below the activation threshold, stop delivering the overlay.

---

# 8. Materiality Detector

The Materiality Detector is the key mechanism preventing score explosion.

## 8.1 Generic materiality dimensions

For each candidate theme, evaluate:

1. Revenue exposure
2. Cost exposure
3. Margin sensitivity
4. Competitive impact
5. Customer behavior impact
6. Capital intensity impact
7. Regulatory impact
8. Time horizon
9. Evidence strength
10. Management relevance

Not every dimension needs to be populated for every theme.

## 8.2 Activation states

```text
0 = NOT_APPLICABLE
1 = LOW
2 = MONITOR
3 = MATERIAL
4 = HIGHLY_MATERIAL
```

Only `MATERIAL` and `HIGHLY_MATERIAL` overlays enter the normal decision context.

`MONITOR` can remain in research context without reaching the final decision model.

## 8.3 Example

INTU:

```text
AI materiality = HIGHLY_MATERIAL
AI overlay = ACTIVE
```

A company with little AI exposure:

```text
AI materiality = LOW
AI overlay = NOT_DELIVERED
```

---

# 9. Generic Overlay Schema

Suggested logical schema:

```python
ResearchOverlay(
    overlay_id: str,
    overlay_type: str,
    symbol: str,
    as_of: datetime,

    activation_state: str,
    materiality: float,

    dimensions: dict,
    direction: str,

    evidence_confidence: float,
    horizon: str,

    key_evidence: list,
    counter_evidence: list,

    source_count: int,
    last_change: str | None,

    version: str,
)
```

Example:

```json
{
  "overlay_type": "AI",
  "symbol": "INTU",
  "activation_state": "HIGHLY_MATERIAL",
  "materiality": 91,
  "direction": "MIXED",
  "dimensions": {
    "exposure": "HIGH",
    "disruption": "HIGH",
    "adoption": "HIGH",
    "monetization": "MODERATE_HIGH",
    "moat_impact": "MIXED"
  },
  "evidence_confidence": 86,
  "horizon": "3-5Y"
}
```

---

# 10. AI Overlay

AI is the first reference implementation because it illustrates the architecture well.

## 10.1 AI dimensions

### Exposure

How materially can AI affect the company's economics?

### Disruption

How much of the existing revenue/profit pool, workflow, pricing power, or moat could AI threaten?

### Adoption

How extensively is the company deploying AI internally and in its products?

### Monetization

Is AI producing measurable revenue, ARPU, margin, retention, or productivity benefits?

### Moat Impact

Does AI strengthen, weaken, or have mixed effects on the company's competitive position?

### Evidence Confidence

How strongly are the conclusions supported by observed evidence?

## 10.2 Direction values

```text
POSITIVE
NEGATIVE
MIXED
NEUTRAL
UNCERTAIN
```

## 10.3 AI overlay example: INTU

```text
AI Overlay: ACTIVE

Materiality: HIGHLY_MATERIAL

Exposure: HIGH
Disruption: HIGH
Adoption: HIGH
Monetization: MODERATE_HIGH
Moat Impact: MIXED

Evidence Confidence: HIGH
Horizon: 3-5Y

Key evidence:
- AI can automate document ingestion and tax-preparation workflow.
- AI-native tax competitors are emerging.
- Intuit is deploying AI-driven TurboTax automation.
- Proprietary tax knowledge, data, distribution and filing infrastructure
  may provide defensive advantages.

Counter-evidence:
- Reliable complex tax computation remains difficult.
- Compliance and filing infrastructure create barriers.
- Intuit is itself adopting the AI-native workflow.
```

This is deliberately NOT reduced to one "AI score."

---

# 11. Why not use AI ThreatScore + AI AdoptionScore permanently?

Those concepts remain useful internally, but they should be treated as **dimensions of the AI overlay**, not new permanent engines.

A possible internal representation is:

```text
AI:
  threat_pressure: 72
  adaptation_strength: 84
```

But the report should emphasize the underlying dimensions and evidence.

This avoids false precision.

---

# 12. Overlay Scoring Rules

## 12.1 No universal hard-coded weights across all overlays

Do not assume:

`Exposure 20% + Disruption 20% + Adoption 20% ...`

is universally correct.

Different overlays have different causal structures.

Instead, use a common dimensional vocabulary while allowing each overlay implementation to define its own calculation logic.

## 12.2 Three classes of values

### Class A — deterministic

Examples:

- percentage of revenue exposed to a theme
- AI-related capex
- commodity revenue percentage
- China revenue percentage
- tariff exposure
- historical margin change

### Class B — evidence-derived categorical

Examples:

- HIGH / MEDIUM / LOW
- POSITIVE / NEGATIVE / MIXED

### Class C — LLM interpretation

Examples:

- likely strategic consequence
- conflicting evidence synthesis
- explanation of why the overlay matters

Class C must cite the underlying evidence.

---

# 13. Evidence Confidence

Every overlay should carry evidence confidence.

Suggested scale:

```text
90-100  Direct, repeated, high-quality evidence
75-89   Strong documented evidence
60-74   Moderate evidence
40-59   Limited/indirect evidence
20-39   Mostly inference
0-19    Speculative
```

This is not "probability that the conclusion is true."

It is:

> Confidence that the evidence supporting the overlay assessment is sufficient and reliable.

---

# 14. Time-Series / Velocity

Every active overlay should be stored historically.

Example:

```text
Date        Materiality   Disruption   Adoption
2026-Q1       48             42           30
2026-Q2       61             55           44
2026-Q3       77             69           63
2026-Q4       91             72           82
```

This enables:

### Materiality velocity

```text
ΔMateriality / Δtime
```

### Disruption velocity

```text
ΔDisruption / Δtime
```

### Adaptation velocity

```text
ΔAdoption / Δtime
```

These should be descriptive indicators, not predictive stock-price signals.

---

# 15. Overlay Selection

The system should enforce a maximum number of active overlays.

Recommended default:

```text
MAX_ACTIVE_OVERLAYS = 3
```

If more than three themes are material, rank them by **materiality and evidence confidence for context allocation**, not as investment recommendations.

For example:

```text
AI          materiality 91
China       materiality 72
Regulatory  materiality 61
FX          materiality 28
```

Deliver the first three to decision context.

The remaining overlays remain in research context.

This is a context-control mechanism, not an investment ranking.

---

# 16. Avoiding Score Explosion

The central rule:

> **New thematic concern ≠ new permanent score.**

Instead:

```text
New theme
   ↓
Does it materially affect the thesis?
   │
   ├── No → research only
   │
   └── Yes
        ↓
     overlay
```

Therefore the system can theoretically support dozens of overlay types without giving every stock dozens of scores.

A stock may have:

```text
8 universal scores
+
0 overlays
```

or:

```text
8 universal scores
+
AI
+
Tariff
```

but not:

```text
8 universal scores
+
30 permanent thematic scores
```

---

# 17. Sector Adaptation

The overlay framework is universal; its evidence fields can be theme-specific.

## Software / SaaS

AI evidence may include:

- seat replacement
- usage expansion
- pricing pressure
- developer productivity
- inference cost
- AI-native competitors

## Semiconductors

AI evidence may include:

- accelerator demand
- data-center capex
- hyperscaler concentration
- supply constraints
- pricing
- AI-related revenue

## Banks

AI evidence may include:

- employee productivity
- underwriting
- fraud detection
- customer service
- fintech competition
- technology spending

## Energy

AI evidence may include:

- data-center electricity demand
- power infrastructure
- generation capacity
- grid constraints
- AI-related load growth

The **schema remains the same** while the evidence adapters differ.

---

# 18. Overlay Registry

Introduce an overlay registry rather than hard-coding overlay logic throughout the graph.

Example:

```python
OVERLAY_REGISTRY = {
    "ai": AIOverlay,
    "tariff": TariffOverlay,
    "china": ChinaOverlay,
    "regulatory": RegulatoryOverlay,
    "commodity": CommodityOverlay,
    "cyber": CyberOverlay,
}
```

Each overlay implementation exposes:

```python
detect()
is_material()
compute()
summarize()
evidence_requirements()
```

This keeps the architecture modular.

---

# 19. Overlay Contract

Every overlay implementation should satisfy a common contract:

```python
class ResearchOverlay:

    def detect(self, symbol, evidence):
        ...

    def materiality(self, symbol, evidence):
        ...

    def compute(self, symbol, evidence):
        ...

    def summarize(self, result):
        ...

    def validate(self, result):
        ...
```

The overlay should not:

- place orders
- override risk gates
- modify TradeScore
- directly produce BUY/HOLD/SELL

---

# 20. Decision Context Contract

The decision layer should receive something like:

```text
UNIVERSAL SCORECARD
───────────────────
Fundamental: 78
Technical:   64
Regime:      71
Risk:        82
News:        69
Sentiment:   73
Event:       61
Trade:       74

ACTIVE RESEARCH OVERLAYS
────────────────────────
AI
  Materiality: HIGH
  Direction: MIXED
  Disruption: HIGH
  Adoption: HIGH
  Monetization: MODERATE+
  Moat impact: MIXED
  Evidence confidence: HIGH
  Horizon: 3-5Y

KEY EVIDENCE
────────────
...

COUNTER-EVIDENCE
────────────────
...

RISK / GATE STATE
─────────────────
...
```

This is intentionally compact.

---

# 21. Interaction With Existing TradeScore

No direct formula change.

Existing TradeScore remains:

```text
TradeScore =
    0.40 Fundamental
  + 0.25 Technical
  + 0.15 Regime
  + 0.20 Risk
```

The AI overlay does not silently become another term.

Instead:

```text
TradeScore
+
AI Overlay
+
other material overlays
```

are presented to the decision layer.

The LLM adjudicates the combined evidence subject to existing hard gates and decision guardrails.

This preserves the existing report contract.

---

# 22. Interaction With Risk Gates

Overlays cannot override:

```text
KILL
>
PORTFOLIO
>
TRADE
>
LIQUIDITY
>
REGIME
```

If the risk governor rejects a trade, an AI overlay cannot convert the result to GO.

The overlay can explain why the business thesis may be changing, but it cannot bypass portfolio risk controls.

---

# 23. Research Context vs Decision Context

This design directly supports the existing context-separation work.

### Research context

Can contain:

- all candidate overlays
- raw evidence
- detailed sources
- historical changes
- competing interpretations
- inactive/monitor overlays

### Decision context

Contains only:

- universal scorecard
- active material overlays
- compact evidence
- counter-evidence
- gates
- relevant plan information

This prevents the overlay system from becoming another source of context bloat.

---

# 24. Rendering

The overlay should have deterministic rendering.

Suggested:

```text
write_overlay_tree(
    overlay,
    destination="decision_context"
)
```

The renderer should not invent content.

Producers compute the overlay.

Renderer prints the existing result.

This is analogous to the existing Level-2 rendering approach for deterministic score blocks.

---

# 25. Tool Binding

Do not automatically bind every overlay tool to every analyst.

Preferred ownership:

```text
Fundamental Analyst
  → fundamental evidence
  → relevant business overlays

Market Analyst
  → technical/regime overlays

News Analyst
  → news/event overlays

Decision Layer
  → active cross-cutting overlays
```

An overlay should be available to the analyst that owns its evidence when useful, but the full overlay should generally be assembled at the decision layer.

This keeps analyst contexts narrow.

---

# 26. Avoiding Context-Volume Regression

The overlay system must have hard budgets.

Suggested defaults:

```text
MAX_ACTIVE_OVERLAYS = 3
MAX_OVERLAY_CHARS = 8,000
MAX_EVIDENCE_ITEMS_PER_OVERLAY = 5
MAX_COUNTER_EVIDENCE = 3
```

The exact values should be benchmarked.

The important requirement is that an overlay is **compact by construction**.

---

# 27. Reproducibility

Overlay output must be reproducible from:

```text
symbol
as_of
data snapshot
overlay version
configuration
```

Recommended hash inputs:

```text
overlay_type
overlay_version
materiality_threshold
evidence_ids
source_timestamps
computed_metrics
```

Do not hash volatile LLM prose as the primary reproducibility input.

---

# 28. Configuration

Example:

```yaml
overlays:
  enabled: true

  max_active: 3

  materiality_threshold: 60

  evidence_confidence_floor: 50

  decision_context:
    max_chars: 8000

  ai:
    enabled: true
    materiality_threshold: 60

  tariff:
    enabled: true
    materiality_threshold: 60

  china:
    enabled: true
    materiality_threshold: 60
```

The master switch should be one gate:

```text
enable_research_overlays
```

Individual overlay gates can remain underneath it.

---

# 29. Testing Strategy

## Unit tests

Test:

- materiality calculation
- activation/deactivation
- N/A handling
- evidence confidence
- schema validation
- deterministic rendering
- character budgets

## Integration tests

Verify:

1. Universal engines still run.
2. Overlay detection does not alter existing scores.
3. Inactive overlays do not enter decision context.
4. Active overlays do enter decision context.
5. TradeScore remains unchanged.
6. Risk gates remain authoritative.
7. Decision context stays within budget.

## Regression tests

For an unchanged input snapshot:

```text
Universal scores = unchanged
TradeScore = unchanged
Risk gates = unchanged
Overlay result = reproducible
```

---

# 30. Experiment Plan

Do not immediately activate overlays in production decisions.

Run three modes.

### A — Control

```text
8 scores
+
existing decision context
```

### B — Overlay research only

```text
8 scores
+
overlays in research context
```

### C — Overlay decision context

```text
8 scores
+
compact active overlays
```

Compare:

- decision distribution
- HOLD frequency
- context size
- token count
- decision consistency
- evidence citation
- hallucination rate
- confidence
- agreement with deterministic gates
- downstream trade-plan changes

Most importantly, test whether overlays cause the same context-volume conservatism that motivated the research-context separation in the first place.

---

# 31. Success Criteria

The enhancement succeeds if:

### Architecture

- No permanent score proliferation.
- Eight universal engines remain unchanged.
- Overlays are modular.

### Context

- Decision context grows only when material.
- Context remains substantially smaller than raw research evidence.
- No systematic increase in low-confidence HOLD behavior solely from overlay inclusion.

### Evidence

- Overlay conclusions trace to evidence.
- Confidence distinguishes fact from inference.

### Reproducibility

- Same evidence snapshot produces same deterministic overlay state.

### Decision quality

- Relevant structural changes reach the decision layer earlier.
- Irrelevant themes remain out of decision context.
- Existing risk gates remain authoritative.

---

# 32. Rollout Plan

## Phase 1 — Framework only

Implement:

- overlay contract
- registry
- materiality detector
- schema
- renderer
- configuration
- logging

No decision impact.

## Phase 2 — AI overlay

Implement AI as the first reference overlay.

Use INTU, NVDA, CRM, MSFT and several low-AI-exposure companies as test cases.

## Phase 3 — Historical backtest

Run the AI overlay against historical snapshots.

Measure:

- activation timing
- evidence quality
- false activation
- missed activation
- context size

## Phase 4 — Decision-context A/B

Compare:

```text
control
vs
AI overlay
```

without changing TradeScore.

## Phase 5 — Additional overlays

Only add an overlay when a repeated research need demonstrates that the theme is:

- material
- recurring
- evidence-supported
- not adequately represented by the universal engines

Candidate sequence:

1. AI
2. Regulatory
3. Tariff
4. China
5. Commodity
6. Cybersecurity

Do not add all six automatically.

---

# 33. Example: INTU

### Universal scorecard

```text
Fundamental       78
Technical         64
Regime            71
Risk              82
News              69
Sentiment         73
Event             61
Trade             74
```

### Overlay detector

```text
AI:
  materiality = 91
  evidence confidence = 86
  → ACTIVE

Tariff:
  materiality = 12
  → INACTIVE

Commodity:
  materiality = 4
  → INACTIVE
```

### Decision context

Only AI is delivered.

```text
AI OVERLAY

Materiality: HIGH
Exposure: HIGH
Disruption: HIGH
Adoption: HIGH
Monetization: MODERATE+
Moat impact: MIXED
Evidence confidence: HIGH
Horizon: 3-5Y
```

The decision model now knows AI is strategically important without receiving thousands of characters of AI research.

---

# 34. Example: Low-Relevance Company

```text
Universal Scores
  Fundamental 71
  Technical 62
  Regime 68
  Risk 77
  News 70
  Sentiment 66
  Event 59
  Trade 69

Active Overlays
  None
```

Nothing else is needed.

---

# 35. Example: Multiple Material Themes

```text
Universal Scores
  ...

Active Overlays
  AI
    Materiality: 89

  China
    Materiality: 76

  Tariff
    Materiality: 71
```

Fourth theme:

```text
Commodity
Materiality: 55
```

remains in research context because it is below the decision-delivery threshold.

This keeps the decision prompt bounded.

---

# 36. Open Decisions

The following should remain explicit before implementation:

1. Exact materiality threshold.
2. Maximum active overlays.
3. Evidence-confidence floor.
4. Overlay character/token budget.
5. Whether categorical dimensions should also have numeric internal values.
6. Whether historical overlay state belongs in the decision context.
7. Whether overlay velocity belongs in decision context or research context.
8. Which evidence sources qualify as high-confidence.
9. Whether the LLM may propose a new overlay for review.
10. Overlay retirement criteria.

Recommended defaults:

```text
Materiality threshold: 60
Evidence confidence floor: 50
Max active overlays: 3
Decision context overlay budget: 8,000 chars
LLM may propose: YES
LLM may activate: NO
```

The last distinction is important:

> The LLM can identify a potentially missing theme, but deterministic materiality/evidence rules should control activation.

---

# 37. Risks

## Risk 1 — Overlay explosion

Mitigation: registry + materiality gate + max-active limit.

## Risk 2 — Context bloat

Mitigation: strict overlay budgets and compact rendering.

## Risk 3 — False precision

Mitigation: preserve categorical dimensions and evidence confidence.

## Risk 4 — Narrative contamination

Mitigation: evidence-first construction and source references.

## Risk 5 — Hidden TradeScore changes

Mitigation: overlays never modify TradeScore directly.

## Risk 6 — LLM decides what matters

Mitigation: deterministic activation gate.

## Risk 7 — Stale overlays

Mitigation: timestamps, expiration/reassessment, velocity tracking.

---

# 38. Final Architecture

The recommended end-state is:

```text
                         RAW EVIDENCE
                              │
              ┌───────────────┴───────────────┐
              │                               │
              ▼                               ▼
       UNIVERSAL ENGINES              OVERLAY DETECTOR
              │                               │
              │                     ┌─────────┴─────────┐
              │                     │                   │
              │                 MATERIALITY         EVIDENCE
              │                     │                   │
              │                     └─────────┬─────────┘
              │                               │
              │                        ACTIVE OVERLAYS
              │                               │
              └───────────────┬───────────────┘
                              │
                              ▼
                   COMPACT DECISION CONTEXT
                              │
                    ┌─────────┴─────────┐
                    │                   │
               Scores + Gates      Overlays
                    │                   │
                    └─────────┬─────────┘
                              ▼
                       LLM ADJUDICATION
                              │
                              ▼
                    EXISTING DECISION FLOW
```

The key architectural rule is:

> **Eight permanent scores. Zero mandatory thematic scores. N conditional overlays.**

That gives the system the ability to recognize new structural forces without turning every stock into a 30-score object.

---

# 39. Recommended Implementation Order

1. `ResearchOverlay` contract
2. `OverlayRegistry`
3. `OverlayMaterialityDetector`
4. `OverlayEvidenceContract`
5. `write_overlay_tree`
6. configuration/master gate
7. AI overlay
8. decision-context integration
9. reproducibility hash
10. A/B experiment
11. historical evaluation
12. only then consider additional overlays

Do not begin by implementing six overlays.

The AI overlay should be the reference implementation used to prove the architecture.

---

# 40. Final Design Decision

### Adopt

**8 universal deterministic engines + conditional research overlays.**

### Reject

**Permanent AI/Regulatory/China/etc. scores for every stock.**

### Adopt

**Materiality-driven activation.**

### Adopt

**Evidence-confidence tracking.**

### Adopt

**Time-series overlay state and velocity.**

### Adopt

**Compact decision-context rendering.**

### Preserve

**Existing TradeScore formula and risk-gate hierarchy.**

### Preserve

**Research-context / decision-context separation.**

### Key invariant

> A new thematic overlay may enrich decision context, but it must not silently become a new voting mechanism inside TradeScore.

This keeps the scorecard compact, deterministic, extensible, and compatible with the existing TradingAgents architecture while giving the system a way to detect structural changes that the eight universal engines alone may not represent well.

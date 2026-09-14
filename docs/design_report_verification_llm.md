# Design: LLM report verification against tool evidence

Status: **IMPLEMENTED 2026-09-08** (all phases shipped; sizing go/no-go passed).
Parts below marked [x] shipped, [ ] deferred.
Reopen trigger: report claims ungrounded in `tool_evidence.json`, OR the
open A/B of `openrouter:web_search` vs Anthropic native search for the
verifier's spot-check affordance.

## Problem

Analyst reports (fundamentals.md / market.md / news.md / sentiment.md) must
contain only claims a deterministic analyst actually produced. Channels where
that contract currently weakens:

1. **Short-circuited tool calls** — vendor 403s (get_analyst_ratings Finnhub,
   get_edgar_fulltext_search), cap-forced empty final turns, "structured output
   returned no parsed result" — the analyst may still write a plausible-looking
   number the evidence block does not support.
2. **Adversarial sourcing** — news/reddit/stocktwits sentiment analysts can
   relay unverified vendor prose as fact.
3. **Latency-orphaned tools** (get_tranche_plan, get_scaleout_plan, get_trade_plan,
   get_edgar_fulltext_search were stripped): the analyst now lacks those signals
   and might paper over the gap.

The deterministic mitigation (already shipped, `862e6dd`) is the `--evidence`
repro cross-check: figure/price/percent claims vs `tool_evidence.json` leaves,
±0.5% numeric tolerance. It is cheap but purely numeric — it cannot judge
qualitative claims, causality wording, or "vendor never called" phrasing.

## Proposed layer (the "Claude verifies" idea)

A second LLM pass, post-run, per report:

- **Input**: the finished markdown report + its `tool_evidence.json` leaves.
- **Job**: flag sentences that assert facts not present in, or contradicting,
  the evidence block. Output a short verdict list: `GROUNDED | UNSUPPORTED |
  CONTRADICTED`, one per claim, NO rewriting.
- **Decision rule**: any UNSUPPORTED/CONTRADICTED → requeue or mark; never
  silently edit.

The evidence leaves already exist and are exact-figure oriented — the verifier
model consumes the same ground truth the analysts had, so it is a
grounded-claim judge, not a free-floating critic.

## Research findings (verified 2026-09-08)

The original plan had a blocker: Claude-hosted tools require specific
scaffolding (client-side harness). During research we confirmed **OpenRouter
host-executed server-side tools** exist and remove the blocker:

- `tools: [{"type": "openrouter:web_search"}]` (and `openrouter:web_fetch`,
  `openrouter:mcp__…`) are passed to the API and **executed by OpenRouter**, not
  the client. Works with **any tool-calling model** — no per-vendor tool bridge.
- Tool taxonomy (3 buckets):
  - **Server tools** — model decides to call, OpenRouter executes, 0-to-N times
    per request: `openrouter:web_search`, `openrouter:web_fetch` (full page
    content from a surfaced URL), `openrouter:datetime`,
    `openrouter:image_generation`, `openrouter:bash` (sandboxed shell; on
    OpenRouter this one is Anthropic-Messages-API-only).
  - **Plugins** — always run once automatically (e.g. PDF parsing).
  - **User-defined tools** — model suggests, the caller's own app executes.
- Search backend: **Exa by default**, with **Firecrawl as a configurable
  alternative** (bring your own key). This matters for result "shape" and
  citation quality, not just cost.
- Spec fetch path: `openrouter.ai/docs/guides/features/server-tools.md` and
  `.../web-search.md` — the rendered pages 403 on direct fetch; the `.md`
  variants and `openrouter.ai/llms.txt` both returned content.
- Live `/api/v1/models` hit verified the `.env` API key is valid for these calls.
- **Claude-routing caveat** (open question for our verifier): when routing to
  Claude through OpenRouter, two options exist — OpenRouter's normalized
  `openrouter:web_search`, or **passing Anthropic's native web search tool
  directly** (OpenRouter proxies to the Claude Messages API). Different
  backends + different result/citation formats; whichever gives better
  citation/result quality for financial-data validation needs to be measured,
  not assumed.

## Shape

- New module `agents/utils/report_verifier.py` (mirrors `repro_check` structure).
- CLI: extend the existing `--evidence`-style flag or add `--verify`; run once
  per report dir, not in the gather loop.
- No changes to agent prompts (the verifier is orthogonal, post-hoc).
- Only actionable output: per-claim verdicts + a report-level PASS/FLAG.

## Not in scope (decisions already made)

- No auto-editing of reports.
- No human-in-the-loop UI — CLI exit code + summary only.
- Keyed on the deterministic `--evidence` check first; the LLM layer is a
  second pass for qualitative claims, costed per report roughly 20–40k
  input tokens (report + evidence JSON).

## Reopen checklist (state 2026-09-08)

- [x] Prototype on a batch round (MSTR batch6 tree): deterministic + LLM passes
      on the same report, flag-set diff. **Result: GO** — LLM added 28 flags
      over the 26 numeric suspects; real catch classes include the sentiment
      "4.0/10 vs computed +0.08" divergence and headline/macro quotes; only 1
      false positive in 189 claims (anchor downgrades that class).
- [x] Wire as a post-run gate: `batch --verify` writes `verify_flags.json`
      (advisory; exit 1 on any FLAG via `scripts/report_verify.py`).
- [ ] Verifier model: resolved to the repo's quick tier by default
      (`TRADINGAGENTS_VERIFY_MODEL` overrides); running a deeper model is an
      env change, not code.
- [ ] **Open A/B: `openrouter:web_search` vs Anthropic native search for the
      verifier's spot-check affordance** — currently the verifier has NO web
      affordance (evidence-only by design, matching the deterministic layer).
      If a claims class needs a live source (`NO_LEAF_CATEGORY`), run the A/B
      (citation quality) and wire it explicitly. Backend choice (Exa vs
      Firecrawl) rides on the same test.
- [x] Truncation follow-up: CLOSED. The "no leaf evidence: truncated" flags
      traced to the verifier's own digest capping leaves at 200 chars (the
      income-statement revenue row sits ~4.4k chars in). Digest now passes the
      full gathered leaf (gatherer already caps at summary_window=12000). Also
      closed the unit-scale false-flag class: `_matches` is now magnitude-aware
      (report 122.4M vs leaf 122368000.0 match; canonical impl shared by
      repro_check). Deterministic suspects on the MSTR tree: 20 -> 0.
## Batch findings (2026-09-08 retail: WMT/COST/TJX/ROST — 16 stems, post-39d00ba)

Adjudicated per working-agreement rule 8: 140 flags =
26 CONTRADICTED (real report-side citation errors, leaves confirm; ROST mcap/
EV/debt/QoQ, TJX BlackRock-date/insider/DCF/EPV, COST insider/implied-move,
WMT consolidation-high/gates, LJX put-strike) + 62 no-leaf (scenario-DCF
invoked-but-unjournaled = manufactured, and macro/prediction leaves absent
because the news LLM did not call those model-pool tools) + 37 anchored-small
(<=0.5% figure noise) + 15 other-derived. NO open code defect: journaling
mechanics proven hermetic (short-circuit wraps every analyst node); the
missing scenario-DCF leaf on ROST is a fabricated call, correctly flagged.

## Batch findings (2026-09-14 live, MU/SNDK/DELL/SKHY — 16 stems)

727 claims: **639 GROUNDED, 78 INTERNAL_CONFLICT, 6 UNSUPPORTED, 4 MISQUOTED, 0
CONTRADICTED**. Adjudicating the conflicts (not accepting them) found the
deterministic scan was the noisy party, so this round hardened the *capture*
rather than the reports (reports are records; the producers were checked too —
see below).

**Capture defects proven on real text** (`agents/utils/report_verifier.py`):
thousands separators were not read, so `$28,243,000,000` became `28` and
`$1,166,000,000,000` became `1`; the `scenario dcf bear/base/bull` label regexes
consumed the value's leading digit (`bear 171.38` -> `71.38`, then the same
number looked like two conflicting scenarios); the printed raw value carried a
6-char slice of surrounding prose (`rice (919.97`); `stoch` matched `stochrsi`;
a VIF table row's multicollinearity score was read as the RSI level; `>= 1.3` was
read as a second RVOL print; `12m` (a window) was read as 12 million; three
period-labelled quarters were compared as one metric; `_r_multiple_identity`
crossed one tool's `entry` with another tool's `stop`; `_valuation_band_conflict`
demanded realized coverage from `get_expected_move`'s option-implied band (no
calibration pairs exist; the conformal tool prints its own); and a `[\d.]+`
capture swallowed a sentence period, which made `_dupont_identity` raise
(`could not convert string to float: '1.5286.'`) and silently lose the whole
identity family.

**Producer checks (independent, per family).** The 2R/3R/T1/T2 numbers are
verbatim tool output and internally consistent: `get_swing_set` derives
`T1 = close + 2*(close - structure_stop)`, `get_swing_exits` measures off the
chandelier stop, `get_tranche_plan` off a size-weighted averaged entry at
1.8R/3.0R — three frameworks, three pairs, no arithmetic in the prompt. The
SNDK ROA "identity break" (50.80% vs net margin x turnover = 69.27%) mixed a
single-quarter net margin (77.0%, derived in prose) with a TTM turnover; on the
TTM leg set the identity holds (0.5646 x 0.8996 = 50.79% ≈ get_ratios' 50.80%).
Both were verifier-side, not producer-side.

**Residual, accepted (advisory noise we can name but not yet remove).** Metrics
that are legitimately multi-source or multi-period still flag: `roe` at 93.18%
(get_ratios) vs 15.76% (get_analyst_verdict), `ev/ebit` at 17.62 vs 106.87,
`atr` at two windows, `vrp` printed from model-free and ATM-IV bases, and a
handful of historical R-multiple lines where a report mixes two frameworks in
one line. These are true statements about the text; whether they are defects is
a reader's call, which is exactly what "advisory" means here.

**Conclusion.** Corpus-wide over the 45 archived trees: same-metric conflict rows
409 -> 186, `metric_errors` > 0 -> 0, and 0 R-multiple/band claims on the four
new trees (12 before). 10 new pinned cases in `tests/test_report_verify.py`.

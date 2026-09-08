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
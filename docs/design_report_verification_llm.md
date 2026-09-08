# Design: LLM report verification against tool evidence

Status: **PARKED** (design + research done, no implementation; user decision on 2026-09-08).
Reopen trigger: recurrence of report claims ungrounded in `tool_evidence.json`,
or agreement that the deterministic `--evidence` check is insufficient.

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
- Spec fetch path: `openrouter.ai/docs/guides/features/server-tools.md` and
  `.../server-tools/web-search.md` — the rendered pages 403 on direct fetch;
  the `.md` variants and `openrouter.ai/llms.txt` both returned content.
- Live `/api/v1/models` hit verified the `.env` API key is valid for these calls.
- So the verifier model could be `claude-*` via OpenRouter with
  `openrouter:web_search` available for spot-check claims that need a live
  source (e.g. "latest earnings date"), matching the search-analyst behavior.

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

## Reopen checklist

- [ ] Re-verify OpenRouter server-tools spec (docs may 403 again; `.md` + llms.txt).
- [ ] Decide verifier model (`claude-*` fastest; deeper `claude-*` if qualitative rigor needed).
- [ ] Prototype on one batch round: run `--evidence` + LLM pass on the same report, diff the FLAG sets to size the delta.
- [ ] If delta ≈ 0 → keep deterministic-only; if > 0 → wire as a scheduled post-run gate.
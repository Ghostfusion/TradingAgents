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
   get_edgar_fulltext_search *were* stripped at the time): the analyst then lacked
   those signals and might have papered over the gap. **All four are bound again**
   (get_tranche_plan is the market analyst's scale-in ladder,
   `agents/analysts/market_analyst.py`; the rest ride `agents/toolsets.py` and
   `agents/utils/risk_tool_loop.py`), so this is historical context, not current
   exposure.

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
- **Decision rule**: any non-GROUNDED verdict → requeue or mark; never
  silently edit. The shipped verifier carries **five** literals, not three
  (`report_verifier.py`): the LLM pass emits GROUNDED / UNSUPPORTED /
  CONTRADICTED, the numeric anchor adds **MISQUOTED**, and the same-metric scan
  adds **INTERNAL_CONFLICT** - all four non-GROUNDED statuses raise the
  section's FLAG.

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
- Output: per-claim verdicts, a report-level `PASS | FLAG | NUMERIC_ONLY | UNKNOWN`, and the typed
  `basis` registry (`{metric, value, basis, source}` per stem) that makes two runs of one ticker
  comparable without diffing prose (2026-09-16).- Only actionable output: per-claim verdicts + a report-level PASS/FLAG.

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
      If a claims class needs a live source (the "no leaf evidence" class -
      UNSUPPORTED claims whose term appears in no leaf; `scripts/verify_sweep.py`
      classes it SUSPECT rather than CONFIRMED), run the A/B
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
(<=0.5% figure noise) + 15 other-derived. **The session's conclusion - "NO
open code defect: journaling mechanics proven hermetic (short-circuit wraps
every analyst node)" - was falsified on 2026-09-13**:
`make_short_circuit_tool_node` guarded on `callable(node)` while a LangGraph
`ToolNode` is a Runnable, so every production node came back unwrapped, the
short-circuit, the per-analyst tool-call journal and the model-pool leaves were
all dead, and **0 of the 38 archived runs** carried one. The ROST attribution
above ("a fabricated call, correctly flagged") rests on that broken journal and
must not be quoted as evidence.

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
`atr` at two windows, and a handful of historical R-multiple lines where a
report mixes two frameworks in one line. These are true statements about the
text; whether they are defects is a reader's call, which is exactly what
"advisory" means here. **Closed since:** the `vrp` pair (model-free
percentage-points vs the ATM-IV variance ratio) - `_UNIT_SCOPED_METRICS` exempts
a pair whose clusters carry different unit classes (2026-09-15).

**Conclusion.** Corpus-wide over the 45 archived trees: same-metric conflict rows
409 -> 186, `metric_errors` > 0 -> 0, and 0 R-multiple/band claims on the four
new trees (12 before). 10 new pinned cases in `tests/test_report_verify.py`.

## Verification round (2026-09-15 live, IEI_20260915_210623 — 4 stems)

13 non-GROUNDED claims, each adjudicated against `tool_evidence.json`: **1 real
report defect, 2 analyst-recall defects, 5 verifier false-positive classes**.

**Real, report-side.** market.md counted `get_capital_flow` as "negative in 7 of
the last 8 weeks"; its own weekly table shows 6 of 8 (07-27 +0.1B and 08-03
+0.7B are positive) - a counting error the LLM pass caught and no numeric
identity could. sentiment.md asserted a hedge-fund "basis-trade unwind ... a
mechanical seller of the belly of the curve" where no leaf carries "basis trade"
(the headline's supplied snippet stops mid-sentence), and sentiment.md + news.md
both quoted "IEI's ~4-5 year duration" while the same tree's fundamentals section
had correctly withheld a duration figure (`get_fixed_income_risk` = n/a). All
three corrected in place (stem + `complete_report.md`); the recall pair is the
class to watch, because the *sibling section* had already refused the number.

**Capture defects proven on real text.** `_PRIMARY_PRICE` had no leading `\b`, so
its alternation matched the "at" INSIDE an ordinary word: the market section's own
caveat `"...do not reconcile as a true print."* Treat 114.33 as unverified.` made
the *disowned* Alpaca print the report's spot price, and the swing-set summary
row's 2R/3R targets were then re-derived off the day low plus ATR
(114.33 + 2*0.2939 = 114.92 vs the quoted 115.2778) - two targets that are
verbatim `get_swing_set` output were flagged. `t1`/`t2` scoping was per LINE by
the FIRST tool named on it: a line naming both `get_tranche_plan` and
`get_swing_set` bound both values to the first, and the two tool-less summary rows
in the same table ("| Swing set | stop 114.0361, T1 115.2778 ... |" beside
"| Tranche plan | ... T1 115.40 ... |") shared the empty scope, so each framed
the other. Scoping is now per SEGMENT - each value binds to the producer named
nearest before it - with a framework-label fallback (`swing set` / `tranche
plan` / `chandelier` / `ema20`) for rows that name no tool. A percent inside the
60-char 200-SMA window is skipped when another metric's label introduces it or it
is a range leg ("200-SMA support with 4.8-4.9% 5-7y yields" is a YIELD; the
Bollinger "%b -6.22%" sits two clauses later). A dated series is one value
changing, not two readings, so both legs of "10 EMA 116.1043 -> **115.0450**" are
skipped. And the macro-authority gate's bare `fomc` trigger moved to its own
group, satisfied by a leaf naming the central bank (the sentiment analyst's own
news leaf carries UBS's "expects the Federal Reserve to raise its policy rate by
25 basis points on September 16" and Apollo's "Federal Open Market Committee");
probability/pricing phrases keep the strict pinned-tool requirement, so the SKHY
protection is unchanged.

Also checked and KEPT: sentiment's headline "Score: 0.2/10" against
`computed_score=-1.00` is inside the prompt's own anchor (`5 + 5*score` = 0.0,
+/-0.5 allowed) - a score is not a defect for being 0.2 off its floor.

Post-fix re-run: market/sentiment/news/fundamentals all PASS, 0 non-GROUNDED
claims, envelope OK, exit 0. Suite 4246 passed / 5 skipped - one new pinned
case in `tests/test_report_verify.py` (the word boundary) and one in
`tests/test_report_readable.py` (the round separators).

## Open items (state 2026-09-16)

Confirmed-but-unfixed, per working-agreement rule 8. None blocks delivery; all
are advisory-noise or capture gaps with a known reproducer.

- **Same-metric pairs that still flag (re-measured 2026-09-16 against the current
  code)**: LULU fundamentals `ev/ebit` 5.50 vs 4.40 and `scenario dcf base` /
  `scenario dcf bull` 173.58 vs 132.5 / 249.05 vs 132.5; LRCX `diluted eps` 1.81
  vs 5.76 and `altman z` 19.70 vs 20.84; AMZN 2026-09-14 `ev/ebit` 35.02 vs
  32.79; MSFT 2026-09-15 market `rvol` 0.30 vs 0.4220. Several look like a label
  cell whose values live in the next cell and are separated by "/" - the same class the 2026-09-14/16 capture work narrowed. **Measured
  2026-09-16 against the current code:** SKHY 2026-09-14's `t1`/`t2` pair and
  WDC 2026-09-15's `scenario dcf base/bull` pair no longer form (0 conflicts on
  those trees' market and fundamentals stems); the pairs above still do. Each survivor needs its own
  reproducer dump before the reader is touched.
- **SIMO net-cash capture**: not reproducible with `_NET_FIGURE_RE` /
  `_table_cell_pair_value`; dump the two values the reader binds before touching
  the checker (the report's own $12.5M net cash is correct).
- **Vendor statement-basis drift** (data layer, not the verifier): the same
  (ticker, date) resolved FY2025-annual flows at 22:5xZ where the 19:08Z run had
  TTM quarters, moving ROE 22.09 -> 18.90, P/E 30.12 -> 35.41, EV/EBIT 32.79 ->
  -30551.06. `statement_parsing.fetch_ticker` merges up to four payloads
  last-writer-wins. **Report side now recorded (2026-09-16):** `verify_flags.json`
  carries the per-stem `basis` registry, so which period each quoted figure claims is
  machine-readable. **Evidence side now recorded (2026-09-16):** the merge labels every
  absorbed payload from the payload itself - `{source, basis, period, observed_kind,
  basis_conflict}` - and the verdict tool's basis line names any key whose payload kind
  contradicts the basis it was requested with. **Still open:** neither record is written
  to `run_card.json`, so a run that anchors to whichever vendor won the merge is
  inspectable by re-running the tool and reading its basis line, not from the archived run
  artifact.
- **Provider safety rejections**: "Upstream error from Alibaba: Output data may
  contain inappropriate content" leaves stems UNKNOWN on dense fundamentals text
  (3rd occurrence 2026-09-14). A `TRADINGAGENTS_VERIFY_MODEL` outside Alibaba, or
  a fallback model, is the fix - an env change, not code.
- **The write-time record is a snapshot**: `run_card.json["analyst_consistency"]`
  holds what the identity checks said AT RUN TIME, so a tree whose checker later
  improved still shows its old conflicts (IEI_20260915_210623 carries two
  R-multiple conflicts in `analyst_consistency` while its `verify_flags.json` is
  clean). No consumer reads it (checked in TradingExecution and trading_web);
  annotating it in place would rewrite a run's own history, which is why it is
  documented here instead.
- **Verifier model / web affordance**: unchanged from the 2026-09-08 checklist
  (quick tier by default; the `openrouter:web_search` vs Anthropic-native A/B is
  still open, and the verifier remains evidence-only by design).

# External research leads - what a source list is worth, and what it changed here

Date: 2026-10-08. Status: the two process patterns are adopted (rules 11-12, two
tools, one scheduled sweep), one trap produced a real fix, one lead produced a
code change, and the rest are recorded as already-present or blocked on an owner
decision. This is a durable register, not a task plan.

## Why this exists

A public "awesome-quant"-style list was checked as a lead source. It is a 0-star
personal fork of `wilsonfreitas/awesome-quant` (29,990 stars), and the list
itself is low-signal: an enormous promotional section, novelty entries (one
advertises ">41.5M TPS, RTT 24.175 ns" against a `.store` site), and at least one
verifiable curation defect - it describes `edgar-traps` as "nine silent failure
modes" where the repo states **eleven**. So the list is a lead source, never
truth: two things in it earned a landing, and everything else was checked against
this repo before being believed.

## What was adopted (process)

**Rule 11 - the eligibility gate.** A review, a book, a list, a vendor page or a
subagent proposing an external library, repo or service offers a lead, not a
fact: verify the load-bearing claim from the primary source, require substance
and recent activity, check for an existing producer first, read the licence, and
cite the evidence. The line worth keeping verbatim is *"missing evidence is
unverified, not proof of eligibility"* - it is the same discipline the
`Strategies/books*/FINDINGS.md` registers apply with `[verified]`/`[reported]`.

**Rule 12 - no task-specific planning documents.** A change lands in the durable
docs it invalidates and in the code; it does not also land as a new per-task
plan, status note or scratch file.

Both are now permanent in `docs/AGENT_ONBOARDING.md` section 0.

**Two diff-scoped tools and a schedule.** `scripts/validate_registers.py` checks
two stated invariants - that an open register row carries a provenance marker,
and that a uniquely-resolvable `path:line` citation names a line that exists -
with legacy debt as a *warning* and the lines added since a ref as *errors* (the
"fix forward, do not re-litigate the backlog" shape). `scripts/url_probe.py`
probes the docs' external links and is SSRF-safe by construction: the host is
resolved once, the resolved address is refused unless it is globally routable,
and the connection is made to that pinned address while the TLS SNI and the HTTP
`Host` header keep the original name, so a redirect into a private range is
refused rather than followed. `.github/workflows/docs-audit.yml` runs both weekly
and opens an issue when either finds something.

## The trap list paid for itself

`talval-research/edgar-traps` trap #1 - "a company's own filings feed carries
other companies' insiders" - is true of this repo. It was reproduced live
(XOM's trailing-365-day Form 4 window returned 42 filings, one of them ProPetro
Holding Corp.'s) and fixed: the `sec_edgar` Form 4 read now filters each filing
on its own issuer. See `CHANGELOG.md` (2026-10-08, "Fixed").

## The leads, and where each one lands

| Lead | Disposition |
| --- | --- |
| `edgar-traps` (traps #2/#7/#10) | #1 fixed (above). **#2 Form 144 unhandled** - the form is read nowhere and is absent from `_FORM_LABELS`; adding it would move `news_score.corporate_events_score`, a scoring contract, so it is left for the owner. #3 (`fp`/`fy` describe the filing, not the period) is **already handled**: `sec_edgar._annual_rows` keys the period on the fact's own `end` plus a >= 300-day duration guard. |
| `eslazarev/purged-cross-validation` (DSR/PBO/MinTRL) | **Already present.** `tradingagents/strategies/evaluate.py` carries DSR, `cscv_pbo`, `min_track_record_length` and `purged_cpcv_splits`; the deflated hurdle is the named `_selection_threshold`. |
| `holdout-labs/{factor-qc,falsification-ledger,lookahead-free}` | **Partly present.** The `[verified]`/`[reported]` provenance convention is this repo's own; `hash_chain_audit.py` is the tamper-evident primitive. The remaining gap (indexing the deflation to the recorded search) is `enable_trial_ledger`, an owner decision (D2). |
| `momoddo/rulelint` (look-ahead / dead branches / regime drift) | **A rule-condition look-ahead linter would be redundant here.** `rule_eval.evaluate_rule` hands each rule only `closes[:i+1]` - a prefix - so a condition cannot see the future by construction; the look-ahead risk in this repo lives in the dataflow leaves (`stockstats_utils`, `federal_reserve`), which already carry their own guards. Dead-branch and regime-drift checks remain genuinely absent - listed below as open. |
| `charlieyanhx/exitkit` (6 families / 27 policies) | **5 of 6 families present** (`exits.py` precedence + `entry_exit_families.py` members). The absent family is **signal-reversal**, and it needs a calibrated price-reversal signal the repo does not emit (only 0-100 momentum scores) - not a bounded change. |
| `twowaymind/orderflow-metrics` (Kyle lambda, VPIN) | **Already present.** `liquidity_risk.kyle_lambda` and `orderflow.vpin` exist with callers. One real defect found: `get_value_dip_setup` never passes `vpin_value`, so the `knife_flow` row is dead on the agent path (it is behind `value_dip_knife_enable`, off by default) - recorded, not landed, because wiring it moves a guard the owner gates. D1 (the `kyle_lambda` default) stays open. |
| `Keenan-ux/implied-expectations` (reverse DCF) | **Already present.** `strategies/reverse_dcf.py` (`reverse_dcf`, `implied_growth_for_fcf`) backs `get_reverse_dcf`, bound to the fundamentals surface. |
| `Finance-broski/backtest-bias` (survivorship) | **Primitives present.** `coverage_window.SURVIVOR_ONLY` and `pit_registry.universe_membership` label a panel `survivor_only` unless it is explicit point-in-time, and `score_panel` carries the label. `scripts/backtest_strategy.py` is single-name by design, so there is no universe to gate there. |
| `pmxt-dev/pmxt` (Polymarket + Kalshi) | **Polymarket present**, keyless, routed in the prediction-markets chain. **Kalshi absent** - a new vendor needs its own study and a consumer, i.e. the vendor-study shape, not a line. |
| `autonomous-audit` (sha256 decision chain) | **Primitive present, not on decisions.** `hash_chain_audit` chains risk rows (`risk_audit.jsonl`) and has a CLI verifier; decisions are per-row self-hashed, not chained. Chaining them is a real, bounded enhancement - left for the owner because it changes what a decision record attests to. |
| `HimanshuJ16/Algo-Trading-Skills` | Not a dependency. Its playbook shape (idempotent orders, kill switches, point-in-time data) is this repo's own `docs/AGENT_ONBOARDING.md` + `skill://` approach. |
| `MarvinRey7879/honest-signals` (lift vs baseline) | **Landed.** `rule_eval` now reports each hit rate beside the always-up base rate over the same bars and their `lift`; the interval lives in `strategies/calibration.excess_accuracy` behind its own gate. The live read is the point: on AAPL, `rsi_overbought` hits 50% against a 53% base at one day - *worse* than always-up - while its raw 62% at ten days beats the 56% base. |

## Open, for the owner

- **Form 144** as a recognised form in `_FORM_LABELS` + `FORM_EVENT_SCORES` (moves `corporate_events_score`).
- **The decision hash chain** (chain the decision record through `hash_chain_audit`).
- **`vpin_value` into `get_value_dip_setup`** (revives the gated `knife_flow` guard).
- **Dead-branch and regime-drift lints** over the configured rules (the two rulelint checks that are not structural no-ops here).
- The standing owner decisions already on the books: the `kyle_lambda` default (D1), the refusal ledger (D2), the deflation value (D3), the volatility-estimator guard (D5) and the rest of `Strategies/books2/FINDINGS.md` section 3.

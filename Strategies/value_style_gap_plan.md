# Value-Style Enhancement Plan (gap analysis -> implementation)

Style: quantitative large-cap value with LLM overlay + swing execution.
Researched gaps (sources: Gray & Carlisle "Quantitative Value"; Asness
value+momentum / quality-minus-junk; Graham; arXiv 2601.04062, 2502.00828,
2605.19278, 2302.10573).

## Gap map

- **V1 Normalized earnings + trap verdict (CORE).** TTM EBIT mis-prices
  cyclicals (peak = fake cheap). Add 5y median-margin normalization, 5y
  percentile PE/PB/EV-EBIT, accruals ratio, and a single "trap risk"
  LOW/MED/HIGH verdict from the forensic gates.
- **V2 Value x momentum composite live.** `factors.py` exists but is not used
  in the ranked list (needs historical price series per candidate).
- **V3 Portfolio construction.** Per-name caps only; add sector caps, min-N,
  value-ratio weights, allocator script.
- **V4 Execution cadence & exits.** Monthly rebalance cadence hints,
  stop-to-breakeven / ATR targets, costs+slip defaulted into sizing.
- **V5 LLM debate from computed numbers.** Margin-of-safety + valuation
  percentile + trap verdict injected into analyst/PM prompts.

Status updated after each phase (tests + regression gates).

## V1 - normalized.py (planned)
- median_norm_ebit: 5y median EBIT margin × current sales
- percentile_hist(value, series) -> 0..1 vs trailing 5y
- accruals_ratio(ni, cfo, ta) trailing
- trap_verdict(f_string, ben-ish_z, mom, accrual) -> LOW|MEDIUM|HIGH + evidence
- wire: screener Trap column + EV/NEBIT where 5y data present (series inputs)

## V2 - factors default (planned)
- composite rank on demand; price history infra for momentum

## V3 - portfolio.py (planned)
- sector_cap, min_names, value_ratio weights, corr-reducer stub
- scripts/allocate.py

## V4 - exits.py (planned)
- stop_to_breakeven, target_level(atr_mult), costs default 10bps

## V5 - computed context (planned)
- build_debate_context(margin_safety, percentile, trap) snippet for prompts
- graph overlay appends when enable_computed_context
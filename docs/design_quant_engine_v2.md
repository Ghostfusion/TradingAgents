# Quant-Engine v2 — Design & Implementation (DuPont, scenario DCF, earnings-quality verdict)

Status: **design + implementation (2026-09-05).** From the 69-section
quant-engine spec review: the repo already covers ~85% of the master
architecture (returns, technicals, fundamentals, valuation, factor models,
ranking, regime, portfolio, backtest integrity via walk-forward/CPCV/PBO/
PIT/delisted-costs; web validation: the fork's stack matches 2025
institutional practice). Three genuinely-new, small, advisory items are
implemented here.

## 1. Web research (validating the three)

- **DuPont ROE** — still the institutional standard for *explaining* ROE:
  ROE = net margin × asset turnover × equity multiplier (or the 5-factor tax/
  interest/operating/asset/equity version); the key use is distinguishing
  margin- or turnover-led quality from leverage-led ROE. Consensus: "ROE
  rising because leverage rose" = less-quality than a margin-led
  improvement.
- **Scenario DCF** — practice favors scenario (bear/base/bull), not a single
  deterministic DCF: vary revenue growth, operating margin, WACC, terminal
  growth; report the range + margin-of-safety under each.
- **Earnings quality** — the consensus layer: OCF/NI >1.0 healthy, 0.8-1.0
  caution, <0.8 warning; accrual ratio <5% acceptable, 5-10% elevated,
  >10% concerning; FCF = OCF − capex sustainability; and the classic red
  flag "rising EPS while FCF/OCF deteriorates → quality penalty".

## 2. The three additions (implemented)

### 2.1 DuPont ROE (`strategies/dupont.py` + `get_dupont_read`)

- `dupont_3(net_margin, asset_turnover, equity_multiplier)` (and
  `dupont_5(net_margin, tax_burden, interest_burden, asset_turnover,
  equity_multiplier)`): ROE = product of legs + a ``driver`` verdict via
  **log-DuPont attribution** (each leg's |ln(factor)| deviation from the
  neutral 1.0 benchmark, shared over the total) labeled margin-led /
  turnover-led / leverage-led / tax- or interest-driven / mixed; a
  non-positive margin (loss-making) is always the story. Advisory.
- Tool `get_dupont_read(...)` — advisory "why ROE is high" context.

### 2.2 Scenario DCF (`strategies/scenario_dcf.py` + `get_scenario_dcf`)

- `scenario_dcf(fcf, wacc, *, shares, cash, debt, g_base=0.03, g_bear?,
  g_bull?, margin_shock_bear?, margin_shock_bull?, market_price?)` — one DCF
  per scenario (bear/base/bull; growth defaults base±2%, margin shocks scale
  FCF; g_base=0.0 is respected, not coerced to 3%), returns per-scenario
  {price, g, fcf_scale, mos}; when ``market_price`` is given the market dict
  adds the band (below bear / bear-base / base-bull / above bull) + base-case
  mos. Reuses the Gordon TV / parity math conventions from ``dcf.py``.
- Tool `get_scenario_dcf(...)` — None-safe; base+lateral shocks + band/mos.

### 2.3 Earnings-quality verdict (`strategies/earnings_quality.py` +
`get_earnings_quality` combined with the existing accruals/cash-conversion)

- `earnings_quality_verdict(net_income, ocf, total_assets, *, fcf?, capex?,
  eps_growth?, fcf_growth?)` — the consensus thresholds: OCF/NI >1 healthy,
  0.8-1 caution, <0.8 warning; accrual ratio <5% ok, 5-10 elevated, >10
  concerning; FCF negative + positive NI red flag; "rising EPS + falling FCF"
  quality penalty flag. Level = **concern** (LOW/MEDIUM/HIGH; HIGH = most
  concern = lowest quality) — never LOW confidence on no inputs: level is
  None (n/a) when nothing is usable. Returns {level, evidence,
  cash_conversion, accrual, fcf}.
- Tool `get_earnings_quality_verdict(...)` — advisory raw-number variant
  (distinct from the pre-existing ticker-based `get_earnings_quality`, which
  now feeds this same verdict: it fetches canonical statements via
  `fetch_ticker`, derives capex-signed FCF, and renders the concern level +
  evidence while keeping the forensic trap layer).

## 3. Non-goals

- Monte-Carlo stress, drawdown-duration, liquidity gate, event-study CAR:
  documented as future (the ai-hedge-fund P2 event-study plan already exists)
  — not built here.
- Anything execution.

## 4. Honest limits

- All three are **calculation layers on caller-supplied inputs** (the fork's
  statements parse supplies NI/OCF/FCF/assets); the reads surface the numbers
  + verdict, never fabricate.
- The DuPont "driver" is a heuristic (log-DuPont attribution vs the
  neutral 1.0 benchmark), advisory.
- Scenario DCF growth/margin scenarios are analyst overrides; the repo's
  "never fabricate" rule means a scenario with no inputs renders n/a.

## 5. Phases

1. This design doc.
2. `strategies/dupont.py` + `get_dupont_read` + tests.
3. `strategies/scenario_dcf.py` + `get_scenario_dcf` + tests.
4. `strategies/earnings_quality.py` + `get_earnings_quality` + tests.
5. Docs (api_reference / CHANGELOG / README / session) + suite + commit +
   push.
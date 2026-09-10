# Design: ETF-specific fundamental/valuation engine (security-type routing)

Status: **SHIPPED 2026-09-09** (all phases landed; default-off via
`TRADINGAGENTS_ENABLE_ETF_ENGINE`). Reopen trigger: an ETF report
(fundamentals.md) whose verdict is driven by "no company-level DCF → no BUY"
instead of ETF-appropriate valuation, OR a fund ticker routed through
company statement tools that return dozens of `n/a`.

## Problem

The IGV 2026-09-09 fundamentals report (reviewed 2026-09-09) is methodologically
honest but structurally one-sided: every company-level tool
(`get_balance_sheet`, `get_cashflow`, `get_income_statement`, `get_ratios`,
`get_analyst_verdict`, `get_earnings_quality`, `get_dcf_valuation`,
`get_fcf_yield`, `get_capex_quality`, `get_value_floors`,
`get_balance_sheet_health`, `get_earnings_surprise`, `get_insider_activity`,
`get_institution_holdings`, `get_company_peers`, `get_composite_rank`,
`get_patent_activity`) returns explicit "unavailable — do not fabricate" for
`igv`, and the analyst correctly refuses to invent numbers. The verdict then
collapses to:

> "absence of any computable undervaluation anchor precludes BUY"

That is **too strong for an ETF**. A BUY on an index wrapper does not require
company-level DCF/Graham/EPV/Piotroski — it requires an **ETF-level valuation
framework** (weighted constituent multiples, valuation percentile vs own
history, sector-relative valuation, breadth, concentration, flows, NAV
premium/discount, tracking). The pipeline currently has no such framework, so
every ETF report degrades to HOLD/Underweight by construction.

### What already exists (grounding — do not rebuild)

- **IT subsector ETF universe** (`tradingagents/strategies/sector_rank.py`,
  commit `268756f`): `INDUSTRY_ETFS` maps SOXX/IGV/CIBR/SKYY/AIQ/BOTZ/DTCR/
  NXTG/IYW/FINX/XSD/VGT to parent XLK; `rank_industry_group` ranks them
  inside the sector with dual-benchmark `rs2` vs VGT (VGT never a ranked
  member).
- **Constituent breadth + leadership** (`sector_rank.py` P3):
  `SECTOR_CONSTITUENTS` (curated: SOXX, XBI), `constituent_breadth` (% above
  SMA), `leadership_ratio` (EW vs CW total return).
- **Sector screener** (`sector_screener.py`): cap-weight/equal-weight sector
  ETF pairs, cross-sectional dispersion, leader/laggard vs sector ETF.
- **Price-series tools that already work for ETFs** (they consume OHLCV, not
  statements): `get_regime_state`, `get_verified_market_snapshot`,
  `get_swing_set`, `get_volatility_estimators`, `get_tail_risk`,
  `get_position_risk_multiplier`, `get_decline_driver_check` (price-based),
  `get_corporate_actions` (distributions + splits), `get_congress_trades`.
- **Wrapper-level snapshot** (`get_fundamentals` / `get_basic_financials`):
  PE (TTM) 31.665, P/B 0.255 (fund artifact), beta 1.197, 52W/3M/6M/YTD
  returns, `priceRelativeToS&P500` 52wk −24.74.

### What is missing (the review's asks)

1. **Security-type routing** — the pipeline treats every ticker as an
   operating company. No `security_type` gate (operating_company / ETF /
   CEF / REIT / BDC / preferred / bond-fund) that selects the methodology.
2. **ETF valuation engine** — weighted constituent P/E, forward P/E,
   earnings yield, FCF yield, earnings/revenue growth, valuation percentile
   vs own history, vs SPY and vs XLK. "No company DCF" must not imply "no
   valuation."
3. **ETF decline-driver hierarchy** — `get_decline_driver_check` returns
   `clean=True` for a fund because it is company-oriented. An ETF needs a
   MARKET / SECTOR / ETF_SPECIFIC / CONSTITUENT_DRIVEN / UNKNOWN classifier.
4. **Relative-strength scoring** — explicit RS vs SPY/QQQ/XLK at 3M/6M/12M
   (the report currently infers relative returns from a single
   `priceRelativeToS&P500` field with no S&P baseline shown).
5. **ETF risk metrics** — downside/upside capture, volatility percentile,
   ATR%, max drawdown, beta vs SPY and vs QQQ (beta alone is regime-dependent).
6. **Flows / NAV / tracking** — premium/discount to NAV, tracking
   difference, expense ratio, AUM/liquidity, distribution yield (labeled
   "ETF distributions", not corporate dividends).
7. **Decision-layer integration** — an ETFScore that can reach BUY without
   company-level anchors; congress weight ≈ 0 for funds; "healthy pullback"
   requires breadth/RS confirmation, not just price-above-DMA.

## Proposed layer

### Phase 0 — Security-type detection (routing gate)

New pure module `tradingagents/strategies/security_type.py`:

```text
classify_security(ticker, *, provider_meta=None, edgar_cik=None) -> SecurityType
```

Sources, in order of authority:
1. Provider metadata: `get_fundamentals` / `get_basic_financials` /
   `get_market_snapshot` already carry fund/ETF flags on some vendors
   (Finnhub `is_etf`, Massive instrument type, EODHD type).
2. EDGAR CIK match: iShares Trust / Vanguard / State Street / Invesco /
   ProShares / Global X / ARK / VanEck / First Trust / Direxion / Amplify /
   Roundhill / Simplify / GraniteShares / YieldMax / Defiance / Tidal /
   Pacer / Innovator / FT Vest / JPMorgan / BlackRock / Fidelity / Schwab /
   Goldman / Morgan Stanley / BNY / Nuveen / PIMCO / iShares / SPDR /
   WisdomTree / Franklin / Columbia / Hartford / Principal / American
   Century / Dimensional / Avantis / iShares (CIK 0001100663 for IGV) →
   fund.
3. Ticker heuristics: known ETF universe lists (`INDUSTRY_ETFS`,
   `SPDR_SECTORS`, `EW_CW_ETFS`), suffix patterns (`-USD`, `=F`), and the
   existing `symbol_utils` normalization.
4. Fallback: `UNKNOWN` → current company path (no behavior change).

Output: `{"security_type", "confidence", "evidence"}`. Advisory; never
blocks. A `security_type` field is stamped into the run state and the
report header (additive; old trees parse).

### Phase 1 — ETF valuation engine

New pure module `tradingagents/strategies/etf_valuation.py`:

```text
etf_valuation(ticker, *, constituents, closes_map, bench_closes, cfg) -> dict
```

Metrics (each `None` when uncomputable — never fabricated):

| Metric | Source |
|---|---|
| Weighted P/E (TTM) | harmonic mean of constituent P/Es weighted by ETF weight: `1 / Σ w_i/E_i`; fall back to provider aggregate when weights unavailable |
| Forward P/E | same on forward EPS |
| Earnings yield | `1 / weighted P/E` |
| Weighted FCF yield | Σ w_i · FCF_i / Σ w_i · mcap_i |
| Weighted revenue/EPS growth | Σ w_i · growth_i |
| Valuation percentile vs own history | ETF's own P/E rank over trailing 3Y (from provider history or constituent history) |
| Valuation vs SPY / vs XLK | ratio of ETF P/E to SPY P/E and XLK P/E |
| Top-10 weight / concentration | from provider holdings when available |
| Breadth | reuse `constituent_breadth` (already shipped) |
| Leadership | reuse `leadership_ratio` (already shipped) |

Constituent data: extend `SECTOR_CONSTITUENTS` to IGV (top software names:
MSFT, ORCL, CRM, ADBE, NOW, INTU, PANW, CRWD, SNPS, CDNS, ANSS, FTNT, etc.),
CIBR, SKYY, and the other `INDUSTRY_ETFS` members — curated, fetch-light,
matching the existing SOXX/XBI pattern. Anything missing renders `n/a`.

New advisory tool `get_etf_valuation(ticker, current_date)` in
`analysis_tools.py` beside `get_ratios`; the fundamentals analyst prompt
gains: "for a fund/ETF security, call get_etf_valuation; company-level
statement tools are expected to be unavailable — do not use their absence as
a valuation conclusion."

### Phase 2 — ETF decline-driver hierarchy

New pure function in `tradingagents/strategies/etf_decline_driver.py`:

```text
etf_decline_driver(ticker, *, etf_closes, spy_closes, qqq_closes, xlk_closes,
                   vix_series, constituents_map, cfg) -> {"driver", "evidence"}
```

Levels (first hit wins, else UNKNOWN):
1. **MARKET_DRIVEN** — SPY/QQQ drawdown beyond threshold, VIX spike, rates
   move (reuse `get_macro_indicators` / `get_tail_risk`).
2. **SECTOR_DRIVEN** — XLK/QQQ relative weakness, sector breadth
   deterioration (reuse `sector_screener` dispersion + `sector_rank`).
3. **ETF_SPECIFIC** — IGV relative weakness vs XLK, volume/flow divergence,
   NAV premium/discount, tracking error.
4. **CONSTITUENT_DRIVEN** — top-constituent earnings revisions / valuation
   compression (reuse `get_analyst_ratings` on the top names).
5. **UNKNOWN** — no signal (replaces the misleading `clean=True` for funds).

The fundamentals analyst renders this instead of `get_decline_driver_check`
when `security_type == ETF`.

### Phase 3 — ETF relative-strength + risk scoring

New pure module `tradingagents/strategies/etf_risk.py`:

```text
etf_relative_strength(ticker, *, closes_map, bench_map, windows=(21,63,126,252))
    -> {w: {"etf_ret", "bench_ret", "relative"}}   # vs SPY, QQQ, XLK

etf_risk_profile(ticker, *, closes, spy_closes, qqq_closes, cfg)
    -> {"beta_spy", "beta_qqq", "downside_capture", "upside_capture",
        "vol_percentile", "atr_pct", "max_drawdown_252d"}
```

- `downside_capture` = mean(IGV ret | SPY down) / mean(SPY ret | SPY down);
  `upside_capture` symmetric. Both `None` when no down/up periods.
- `vol_percentile` = current 20d realized vol rank vs trailing 3Y.
- The report renders **relative returns with both legs shown** (IGV 3M
  +7.10% vs SPY 3M +3.85% → relative +3.25%), fixing the current
  `priceRelativeToS&P500` ambiguity.

### Phase 4 — Flows / NAV / tracking (advisory, best-effort)

New tool `get_etf_mechanics(ticker)`:
- NAV premium/discount (provider NAV vs close; `None` when unavailable).
- Tracking difference (ETF return vs index return over 1Y, when index
  series available).
- Expense ratio, AUM, distribution yield + frequency (labeled **ETF
  distributions**, never "dividends").
- All `None`-safe; the analyst must not fabricate.

### Phase 5 — Decision-layer integration

- `security_type` gates the fundamentals analyst's tool set: ETF → run
  `get_etf_valuation` + `get_etf_mechanics` + `etf_decline_driver` +
  `etf_relative_strength`; skip company statement tools (they are expected
  `n/a` — no longer a verdict input).
- ETFScore (advisory, default-off, mirrors the review's weights):

```text
ETFScore = 0.20·Trend + 0.20·RS + 0.20·Valuation + 0.15·Constituent
         + 0.10·Breadth + 0.10·Risk + 0.05·Flows
```

  BUY is reachable without company-level DCF (valuation percentile + RS +
  breadth can carry it). Congress weight ≈ 0 for funds (stale 2020 trades
  stay in the audit trail, never the thesis).
- "Healthy pullback" wording requires breadth + RS confirmation; otherwise
  the report says "correction within an intact bullish price regime, with
  longer-term relative weakness requiring monitoring."

## Files

| File | Change |
|---|---|
| `tradingagents/strategies/security_type.py` | new — routing gate |
| `tradingagents/strategies/etf_valuation.py` | new — weighted valuation |
| `tradingagents/strategies/etf_decline_driver.py` | new — driver hierarchy |
| `tradingagents/strategies/etf_risk.py` | new — RS + risk profile |
| `tradingagents/strategies/sector_rank.py` | extend `SECTOR_CONSTITUENTS` (IGV/CIBR/SKYY/…) |
| `tradingagents/agents/utils/analysis_tools.py` | add `get_etf_valuation`, `get_etf_mechanics` |
| `tradingagents/agents/analysts/fundamentals_analyst.py` | security-type gate + ETF prompt |
| `tradingagents/agents/utils/agent_utils.py` | stamp `security_type` into state/report header |
| `tradingagents/default_config.py` | `enable_etf_engine` (default off) |
| `tests/test_security_type.py`, `tests/test_etf_valuation.py`, `tests/test_etf_decline_driver.py`, `tests/test_etf_risk.py` | new |
| `docs/api_reference.md`, `CHANGELOG.md` | rows per phase |

## Acceptance

- `classify_security("igv")` → ETF (CIK 0001100663 / provider flag); a
  company ticker (e.g. `msft`) → operating_company; unknown → UNKNOWN with
  no behavior change.
- `etf_valuation("igv", …)` returns weighted P/E, forward P/E, earnings
  yield, valuation percentile, vs-SPY/vs-XLK ratios — each `None`-safe.
- `etf_decline_driver("igv", …)` returns one of the 5 drivers, never a
  blanket `clean=True`.
- `etf_relative_strength` renders both legs (IGV 3M +7.10% vs SPY +3.85% →
  +3.25%), fixing the `priceRelativeToS&P500` ambiguity.
- A re-run of IGV fundamentals.md shows an ETFScore with a valuation
  percentile and RS legs — and the verdict can be BUY when those legs
  justify it, without any company-level DCF.
- All new behavior default-off/advisory; old `tool_evidence.json` files
  parse with the new additive fields.

## Deferred (explicitly out of scope)

- Full constituent lists for every ETF (fetch-heavy; curated core subset
  only, matching the existing SOXX/XBI pattern).
- Live NAV/tracking feeds (best-effort `None` when the vendor lacks them).
- CEF/REIT/BDC/preferred/bond-fund engines (the routing gate classifies
  them, but their methodology ships later).

# Design + implementation: the unused EODHD API surface

State 2026-09-19. Source: **live probing of the repo's own EODHD key** across five rounds
(~100 URLs, including path variants), plus the endpoint catalog the owner supplied. **No code
changed by this document.**

Companion to `docs/design_moomoo_unused_api_surface.md`,
`docs/design_finnhub_yfinance_unused_surface.md` and `docs/design_webull_data_provider.md`
(the same shape: a vendor capability read mapped onto the repo's existing seams, with a phased
plan and the constraints that decide it).

---

## Verdict

**The supplied catalog is materially wrong about what this key can reach.** It lists 68
endpoints as though the set were uniform; probed live, the set splits three ways and the
largest part is closed. EODHD is also **not** a removed vendor — the repo calls **8 of its
paths** today.

Of the **9 endpoints that are reachable and unused**, only **three clear master rule 15**
(no derived quantity may have two independent authoritative producers). The rest are either a
second producer for a quantity the tree already owns, or transport/reference plumbing.

| | Endpoint | Why it wins |
|---|---|---|
| **P0** | `/ust/real-yield-rates` | **TIPS real yields — no producer exists anywhere in the tree** (`grep -rn "real_yield\|TIPS"` returns nothing). Paired with the nominal curve the tree already reads, it converts the market's inflation expectation from an assumption into a reading. This is the only endpoint here that changes what a number *means*. |
| **P1** | `/ust/bill-rates` | Auction-level detail (`discount`, `coupon`, `avg_discount`, `avg_coupon`, `maturity_date`, `cusip`) that no existing producer carries. A bill curve point is not a note curve point. |
| **P2** | `/id-mapping` | **FIGI / LEI / CUSIP** — the tree has none of the three. Its **CIK** field is explicitly *demoted* to a cross-check, because `sec_edgar._cik_for` already owns that join. |

Everything else reachable is recorded in Appendix B with the reason it is **not** a P-item.

---

## What the scan covered

| Measure | Count |
|---|---|
| Endpoints in the supplied catalog | 68 |
| Called by this repo today | **8** |
| Probed live against the key | **~100 URLs** (catalog paths + path variants) |
| **Reachable and unused** | **9** |
| Plan-gated (403) | **20** |
| Not found at any probed path (404) | **~9** |

The used set was extracted from the tree, not from memory: every `_eodhd_get(...)` call site in
the single vendor seam `tradingagents/dataflows/eodhd.py`.

**A 404 is not evidence of absence, and a 403 is not evidence of absence either.** Several
catalog paths returned 404 on the documented spelling and 200 on a different one (`/ust/*` was
found only by guessing); one returned **422** — meaning *authorized but malformed* — which is
how `/calendar/dividends` was separated from the genuinely closed endpoints. Each failure is
recorded with its exact message below, because an entitlement wall, a wrong path and an absent
feature close differently.

---

## Verified live (2026-09-19)

### Already used — 8 paths, all 8 returned 200

| Path | Caller |
|---|---|
| `/eod/{SYM}` | `eodhd.get_stock_data_eodhd:104` (call at `:114`) |
| `/sentiments` | `eodhd._sentiment_points_eodhd:153` (call at `:161`) |
| `/news` | `eodhd.get_news_eodhd:240` (call at `:249`) |
| `/div/{SYM}` | `eodhd.get_corporate_actions_eodhd:275` (call at `:283`) |
| `/splits/{SYM}` | `eodhd.get_corporate_actions_eodhd:275` (call at `:295`) |
| `/exchange-symbol-list/{EX}` | `eodhd.get_exchange_symbols_eodhd:328` (call at `:335`) |
| `/real-time/{SYM}` | `eodhd.get_market_snapshot_eodhd:358` (call at `:368`) |
| `/real-time/US.US` | `eodhd.get_top_movers_eodhd:383` (`:395`) and `get_top_movers_symbols_eodhd:408` (`:426`) |

Every one returned 200, so the key is live and the plan is the **EOD** tier.

### Tier 1 — reachable, unused, and clears rule 15

#### 1. `/ust/real-yield-rates` — TIPS real yields

```json
{"meta":{"total":895},"data":[{"date":"2026-01-02","tenor":"5Y","rate":1.46},
                              {"date":"2026-01-02","tenor":"7Y","rate":1.69}, ...]}
```

**895 rows** for 2026, 42 KB, tenors from 5Y out. No `real_yield` or `TIPS` reader exists in
the tree.

Why this is the P0 and not a curiosity: `strategies/dcf.py::wacc_from_beta:28` is
`wacc_from_beta(rf, beta, erp: float = 0.05)`, and its own docstring says *"``rf`` is the 10y
Treasury yield (fraction) … ``erp`` the assumed equity risk premium (default 0.05 = 5%, the
usual central bank range is 4.5-6%)"*. So the tree already feeds a **nominal** 10y into the
DCF and **assumes** the premium. A real yield is the missing half of the pair that lets the
premium be *measured* (nominal − real ≈ expected inflation) instead of carried as a constant
with a stated range. This endpoint is what makes that a reading rather than a default.

#### 2. `/ust/bill-rates` — bill auction detail

```json
{"meta":{"total":1253},"data":[{"date":"2026-01-02","tenor":"4WK","discount":3.58,
  "coupon":3.64,"avg_discount":3.58,"avg_coupon":3.64,"maturity_date":"...","cusip":"..."}]}
```

**1,253 rows**, 187 KB. The `cusip` and `maturity_date` fields are auction identity, not curve
points — nothing else in the tree carries them.

#### 3. `/id-mapping` — identifier join

```json
{"data":[{"symbol":"AAPL.US","isin":"US0378331005","figi":"BBG000B9XRY4",
          "lei":"HWUPKR0MPOU8FGXBT394","cusip":"037833100","cik":"0000320193"}]}
```

Queryable by `filter[isin]` (18 rows for one ISIN — it maps to every listing) or
`filter[symbol]` (1 row). **FIGI, LEI and CUSIP are new to this repo.**

**The `cik` field must be demoted.** `sec_edgar._cik_for:175` already resolves a ticker to a
CIK from SEC's own `company_tickers.json` (`_TICKERS_URL:34`), and SEC is the *authoritative*
registrar for its own identifier. EODHD's CIK is a legitimate **fallback or cross-check** —
never a second contributor.

### Tier 2 — reachable, unused, but a second producer or plumbing

| Endpoint | Measured | Why it is not a P-item |
|---|---|---|
| `/eod-bulk-last-day/{EX}` | **45,009 rows / 6.6 MB in ONE call** | Same producer as `get_stock_data_eodhd`, batched. A **transport optimisation**, not a new source — valuable, but it must not become a second contributor. |
| `/ust/yield-rates` | 2,506 rows, `tenor → rate` | `federal_reserve.get_treasury_curve:116` already reads Treasury's own CSV for the nominal curve. **Second producer.** |
| `/ust/long-term-rates` | 537 rows, `rate_type` (`BC_20year`), `extrapolation_factor` | Same nominal curve, different taxonomy. **Second producer**; the `rate_type` shape is the only novelty and does not justify a second authority. |
| `/us-quote-delayed` | 10 symbols → 10 rows; `sector`, `industry`, `name`, `otcMarket`, `otcTier`, bid/ask | Same vendor quote as the already-used `/real-time`; `sector`/`industry` duplicate `yfinance_sector.fetch_sector:64`. The `otcTier` classification is the one field with no existing producer. |
| `/search/{q}` | `Code, Exchange, Name, Type, Country, Currency, ISIN, previousClose` | Discovery only. `/exchange-symbol-list` (already used, 51,107 rows) covers the same ground for universe construction. |
| `/exchanges-list` | **70 exchanges**, `OperatingMIC, Country, Currency, CountryISO2/3` | Pure reference data; feeds no scoring quantity. |

### Tier 3 — plan-gated (403), **not** absent

`intraday`, `technical`, `fundamentals`, `bulk-fundamentals`, `logo`,
`calendar/{earnings,trends,ipos,splits,dividends}`, `screener`, `exchange-details`,
`v2/exchange-details`, `economic-events`, `macro-indicator`, `eod/*.GBOND`, `eod/*.MONEY`,
`mp/unicornbay/options`, ESG/InvestVerte, trading-hours.

Appendix A lists all of them with their exact messages.

### Tier 4 — not found at any probed path (404)

`ticks`, `word-weights`, `mp/praams/*`, `fed/policy-rate`, `fed/fed-funds`, `rates/sofr`,
`ust/policy-rates`, `ust/treasury-rates`, `ust/sofr`, `v2/{intraday,ticks,screener,technical}`,
`trading-hours`, `interest-rates`.

The catalog asserts `word-weights` and the Treasury/rates set; the rates part is **half right** —
the four `/ust/*` endpoints above are real and reachable, but SOFR and the policy rate are not
at any path probed. `word-weights` was not found on either spelling.

---

## Fit against the repo (grounded, not inferred)

This is the section that decides the plan, and it is the reason six of the nine reachable
endpoints are **not** adopted.

| Existing producer | Location | Collides with |
|---|---|---|
| Treasury nominal curve | `federal_reserve.get_treasury_curve:116` | `/ust/yield-rates`, `/ust/long-term-rates` |
| SOFR curve | `federal_reserve.get_sofr_curve:71` | (EODHD's SOFR is 404 — no collision) |
| TGA balance | `treasury_fiscal.get_tga_balance:27` | — |
| CIK resolution | `sec_edgar._cik_for:175` | `/id-mapping`'s `cik` field |
| Sector / industry | `yfinance_sector.fetch_sector:64` | `/us-quote-delayed`'s `sector`, `industry` |
| Per-symbol EOD | `eodhd.get_stock_data_eodhd:104` | `/eod-bulk-last-day` (same producer, batched) |

**What has no producer at all**, verified by search rather than assumed:
real yields / TIPS, bill-auction discount and coupon, FIGI, LEI, CUSIP, and OTC market tier.

That list is the entire adopted set. It is short on purpose: the rule is that a secondary may
be a fallback, a cross-check or a diagnostic, and **never a second contributor** — so an
endpoint that duplicates an existing producer does not become a P-item merely because it is
reachable.

---

## Constraints

1. **The gate must default off, and gate-off must be byte-identical.** This is the house rule
   for every data-surface gate (`docs/gate_registry.md` §6).
2. **`/ust/*` costs one call for a year of rows.** 895 / 1,253 / 537 / 2,506 rows per call, so
   a per-run refresh is cheap; a per-symbol fetch would be absurd and is not proposed.
3. **`/id-mapping` returns one row per listing.** `filter[isin]` on a US ISIN returned **18**
   rows (foreign listings of the same security). Any consumer must select the primary listing
   explicitly rather than take row 0.
4. **CIK from EODHD is a fallback only.** `sec_edgar._cik_for` remains the authority; the
   EODHD path may only be consulted when SEC resolution fails, and must say so when it is.
5. **A real yield is a rate, not a price.** It must be printed with its tenor and date, and
   `None` is never `0.0` — an unreadable curve is *unavailable*, never a zero rate (master
   rule 1). A 0% risk-free rate silently inflates every DCF it touches.
6. **The nominal/real pairing is a derived quantity and needs one producer.** If both legs are
   ever read, the subtraction happens in exactly one place.

---

## Design

### Gate

One new gate, **`enable_eodhd_rates`**, default `False`, registered in all four places
(`default_config.DEFAULT_CONFIG`, an `_ENV_OVERRIDES` row, a `docs/gate_registry.md` §6 row, and
the `REGISTRY` dict in `tests/test_gate_env_toggles.py`).

**One gate, not three.** P0, P1 and P2 are one read of one vendor's rate/reference surface; a
gate per endpoint would multiply the toggle surface without changing what a user decides. This
mirrors the moomoo decision to put `get_option_underlying_overview` and
`get_option_underlying_his_volatility` behind a single gate.

### Module layout

All three readers live in `tradingagents/dataflows/eodhd.py`, beside the eight existing ones,
through the same `_eodhd_get` seam:

```
get_real_yield_rates_eodhd(tenor=None, year=None)   -> str   # rendered, for an LLM surface
real_yield_points_eodhd(tenor=None, year=None)      -> list  # structured, for a consumer
get_bill_auction_rates_eodhd(tenor=None, year=None) -> str
map_identifiers_eodhd(*, isin=None, symbol=None)    -> dict
```

`real_yield_points_eodhd` is deliberately the **structured** form of the same read — one entry
point, two presentations, the shape `moomoo.get_market_snapshot_moomoo` already established.
A second public function returning the same rows would be a second producer, and
`tests/test_calc_agent_wiring.py` enforces the reachability half of that rule.

### What each reader must print

- **The read date and the tenor**, because a rate without either is not a rate.
- **Coverage**: rows returned, and the requested tenor when one was asked for and not found —
  a missing tenor is named, never interpolated.
- **The basis** for the derived inflation expectation: `nominal − real`, with both legs' dates
  printed. Two series from different dates must not be subtracted silently.
- **`unavailable` with the reason** when the curve is empty or the gate is off.

---

## Implementation plan

| Phase | Work | Gate |
|---|---|---|
| **P0** | `real_yield_points_eodhd` + `get_real_yield_rates_eodhd`; the nominal/real pairing as a single derived read | `enable_eodhd_rates` |
| **P1** | `get_bill_auction_rates_eodhd` | same |
| **P2** | `map_identifiers_eodhd`, FIGI/LEI/CUSIP only; CIK as a named fallback behind `sec_edgar._cik_for` | same |
| **P3** | `/eod-bulk-last-day` as a **batched transport** for the existing price producer — only if the per-symbol path ever becomes the bottleneck | same |

Each phase needs: the gate row in all four places, a failing-first test **by mutation**, and a
`CHANGELOG.md` entry with a `**Web impact**:` line.

---

## Open questions

1. **Does the owner want the inflation expectation *computed*, or only the two legs
   *available*?** Computing it creates a derived quantity with a basis that must be printed;
   exposing the legs keeps the arithmetic in the consumer. The repo's precedent (the
   `level_basis` decision in `analyst_revisions`) favours measuring with an honest label over
   leaving a leg dead — but that is a call about a *new* number, not a dead one.
2. **Is the EOD plan expected to change?** Twenty endpoints are one upgrade away
   (`fundamentals`, `screener`, `calendar/*`, `technical`). If an upgrade is planned, the
   plan's phase order should be revisited before P1 is built — several 403 endpoints would
   outrank what is left.
3. **Does `/eod-bulk-last-day` (45,009 rows, one call) change the panel's cost model?** It is
   the same producer batched, so it is not a rule-15 question — but it is a 6.6 MB response and
   the panel fetches per symbol today.

---

## Recommendation

**Build P0.** It is the only endpoint in the whole surface that changes what an existing number
means: `wacc_from_beta` currently *assumes* the equity risk premium while already consuming a
real Treasury yield, and the real-yield series is the other half of that measurement. It is one
call, 42 KB, gated off by default.

**Build P1 and P2 behind the same gate** — they are small, they have no producer in the tree,
and P2's CIK demotion is already specified.

**Do not build Tier 2.** Six reachable endpoints are second producers or reference plumbing.
Reachability is not a reason to adopt; rule 15 is the reason not to.

---

## Appendix A — the plan-gated set (403, probed 2026-09-19, never wire)

| Endpoint | Exact message |
|---|---|
| `/intraday/{SYM}` (1m, 5m) | `Forbidden` |
| `/technical/{SYM}` | `Forbidden. Please contact support@eodhistoricaldata.com` |
| `/fundamentals/{SYM}` (incl. `?filter=`) | `Forbidden. Please contact support@eodhistoricaldata.com` |
| `/bulk-fundamentals/{EX}` | `Forbidden. Please contact support@eodhistoricaldata.com` |
| `/logo/{SYM}` | `Forbidden. Please contact support@eodhistoricaldata.com` |
| `/calendar/earnings` | `Forbidden. Please contact support@eodhistoricaldata.com` |
| `/calendar/trends` | `Forbidden. Please contact support@eodhistoricaldata.com` |
| `/calendar/ipos` | `Forbidden. Please contact support@eodhistoricaldata.com` |
| `/calendar/splits` | `Forbidden. Please contact support@eodhistoricaldata.com` |
| `/calendar/dividends` | `Forbidden` with a filter; **422** *"filter.date eq field is required"* without one |
| `/screener` | `Forbidden. Please contact support@eodhistoricaldata.com` |
| `/exchange-details/{EX}` | `Forbidden` |
| `/v2/exchange-details` | `Forbidden. Please contact support@eodhistoricaldata.com` |
| `/economic-events` | `Forbidden. Please contact support@eodhistoricaldata.com` |
| `/macro-indicator/{COUNTRY}` | `Forbidden` |
| `/eod/{SYM}.GBOND` | `This data is not available for your subscription plan.` |
| `/eod/{SYM}.MONEY` | `Forbidden` |
| `/mp/unicornbay/options/contracts` | `Forbidden` |
| ESG / InvestVerte | `Forbidden` |
| trading hours | `Forbidden` |

`/calendar/dividends` is the instructive one: a **422** proves the route is authorized and the
request was merely malformed, while the **403** on the well-formed request proves the *plan* is
the gate. Without the 422 probe this would have been indistinguishable from a wrong path.

---

## Appendix B — the reachable-and-unused inventory, in full

| Endpoint | Status | Rows / shape | Adopted? |
|---|---|---|---|
| `/eod-bulk-last-day/{EX}` | 200 | **45,009 rows, 6.6 MB**, one call | P3 (transport only) |
| `/us-quote-delayed` | 200 | 10 symbols → 10 rows | No — second producer |
| `/search/{q}` | 200 | list, `ISIN` + `previousClose` | No — discovery only |
| `/id-mapping` | 200 | 18 rows/ISIN; `FIGI, LEI, CUSIP, CIK` | **P2** |
| `/exchanges-list` | 200 | **70 exchanges** | No — reference only |
| `/ust/yield-rates` | 200 | 2,506 rows | No — second producer |
| `/ust/bill-rates` | 200 | 1,253 rows | **P1** |
| `/ust/long-term-rates` | 200 | 537 rows | No — second producer |
| `/ust/real-yield-rates` | 200 | 895 rows | **P0** |

Measured payload sizes for the `/ust/*` family: 116 KB, 187 KB, 46 KB, 42 KB respectively — a
year of rows per call in every case.

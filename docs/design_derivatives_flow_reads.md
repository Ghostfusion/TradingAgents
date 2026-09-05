# Derivatives-Flow Reads — Teacher Findings & Assessment (design only)

Status: **design study only — no code changes.** Reviewed a trader's
write-up on how option positioning (dealer delta/gamma hedging, call/put
walls, zero-gamma, OPEX pinning, IV skew, unusual activity) affects an
underlying's spot price and execution, and validated it against web
research (academic + practitioner). Everything here is **advisory and
opt-in**; the fork's no-execution / advisory / deterministic / PIT
mandates stand. Where the write-up overlaps the fork's existing reads
(`get_options_iv_read`), those are validated as already-adopted.

---

## 1. What the write-up claims (plain-English synthesis)

1. **Dealers delta-hedge** — options market makers take the opposing side
   and mechanically trade the underlying to stay delta-neutral.
2. **Gamma drives the regime** — short gamma (net put buys) ⇒ dealers chase
   the move (sell weakness, buy strength) ⇒ trend acceleration + cascade
   risk; long gamma ⇒ mean-reversion, "pinned/molasses" markets.
3. **Call/put walls** — strikes with concentrated dealer gamma act as
   resistance/support; **zero gamma / gamma flip** = the level where dealer
   gamma crosses sign = inflection.
4. **OPEX pinning** — heavy OI near the spot pins price toward the strike
   into expiry; **post-OPEX unwind** can break the stock out.
5. **Unusual activity** — aggressive OTM-call sweeps force dealer spot buys
   (gamma squeeze); OTM-put surges foreshadow de-risking/downside.
6. **IV skew as sentiment** — steep put skew = downside demand (downside
   pressure but short-squeeze setup); flat/inverted skew = speculative
   upside (crash-risk if momentum stalls).

## 2. What the web research actually supports

| Claim | Evidence | Verdict |
|---|---|---|
| Dealer delta-hedging mechanics | "Well established" — MMs hedge delta by trading the underlying; gamma forces repeated rehedging | **Supported (mechanics)** |
| Short-gamma ⇒ momentum/trend, long-gamma ⇒ mean-reversion volatility | 2025 SSRN 0DTE paper: positive dealer gamma ↔ stronger intraday **reversal**; negative ↔ stronger **momentum**; negative gamma predicted higher future vol | **Supported (aggregate, esp. 0DTE)** |
| Zero-gamma / wall levels as standalone support/resistance | "Much of the wall language comes from practitioner frameworks & vendor research ... weaker for any single strike-level label as a universal predictive rule" | **Weak / heuristic — treat as market-structure context, never a hard gate** |
| OPEX pinning + post-expiry drift | Real but **context-dependent** (OI concentration + dealer hedging can compress vol, then re-expand; put-vs-call composition matters) | **Supported as an effect, not a law** |
| IV skew = sentiment / tail-risk | Academically linked to sentiment, tail risk, return predictability | **Supported** (already covered by the fork) |

**Bottom line:** the *mechanics* and the *regime* (short vs long gamma) are
real and increasingly documented; the *strike-level labels* (walls,
zero-gamma flip) are **practitioner heuristics with weak standalone
predictive evidence** — best used as advisory context, exactly the fork's
stance. And skew/PCR are already computed reads here.

## 3. What maps onto the existing repo (mostly already adopted)

| Write-up concept | Repo equivalent (verified) | Verdict |
|---|---|---|
| IV skew (OTM put vs call IV) | `get_options_iv_read` (v9 chain): `_iv_skew(otm_put_iv, atm_iv, otm_call_iv)` → put-skew line | **Already adopted** |
| Put/call positioning | same read: `put_call_oi_concentration` (PCR line) | **Already adopted** (simple version) |
| Expected move / implied vol regime | `get_expected_move` (option-implied 1-sigma) + `get_variance_premium` (VRP) + `get_tail_risk` | **Already adopted** |
| Per-contract Greeks (incl. gamma) | `options_math.implied_vol_and_greeks` (black76: delta/gamma/vega/theta) | **Already adopted** (per-contract) |
| **Chain-level dealer gamma (GEX), call/put walls, zero-gamma** | NOT computed — only per-contract gamma; no aggregation across strikes/expiries | **The genuinely new gap** |
| OPEX schedule + pinning/unwind | `get_expected_move`, catalyst/earnings calendar (earnings, not options expiry); no OPEX calendar | **Gap (OPEX calendar + pinning context)** |
| Unusual activity / sweeps | no options-flow feed (chain only, no block/sweep tape) | **Data-gap — likely out of scope** (needs an options-flow vendor) |
| IV percentile | explicitly n/a in `get_options_iv_read` (needs per-day IV history no vendor gives) | **Known gap — unchanged** |

## 4. Adoptable lessons (advisory, default-off)

**A1 — Chain gamma profile (GEX-ish), gated default-off.**
Compute per-strike dealer-gamma contribution from the chain we already fetch
(`get_options_chain` v9 calls/puts with OI + IV) via `options_math` Greeks:
weighted by |OI| × Γ × notional proxy, summed per strike → a
**call-wall / put-wall / zero-gamma estimate** + a **short-vs-long-gamma
regime flag** (net dealer gamma sign). Advisory: "gamma regime: short
(momentum risk) — GEX flips to positive ≈ 412" — never a gate. **This is
the highest-value new read** (uses data we already have, turns the
write-up's one testable mechanism into a house formula). Caveat per §2: it
is a market-structure heuristic, not a price law.

**A2 — OPEX calendar + pinning context read.**
A small `option_expiry`/`opex` read: next monthly/quarterly OPEX date
(standard third-Friday), "in OPEX week" flag + "post-OPEX unwind window"
(Monday/Tuesday after), advisory note on pinning risk. Uses a static
calendar (no vendor needed); the china fork has no OPEX schedule today.

**A3 — Gamma-regime caveat in existing reads (optional, tiny).**
`get_options_iv_read` could add an advisory line cross-referencing the A1
regime when computed ("high put skew + short gamma ⇒ squeeze momentum risk" —
the write-up's synthesis). Only if A1 lands.

## 5. Explicit non-goals

- **Unusual options activity / sweep feeds** — needs an options-flow vendor
  (block/sweep tape) the fork doesn't subscribe to; out of scope.
- **IV-percentile** — still needs per-day IV history no vendor delivers
  (unchanged, already honest n/a).
- **Anything execution** — no-execution mandate stands; walls/gamma are
  advisory context, never a trade trigger.
- **Strike-level labels as gates** — weak standalone evidence; advisory only.

## 6. Honest limits

- **Practitioner-heuristic burden**: the wall/zero-gamma labels are
  convention, not peer-reviewed law — the fork should render them as
  "market-structure context" with the evidence caveat, not as signal.
- **Data quality**: GEX needs OI + IV per strike across expiries — the v9
  chain fetch must supply OI per strike (verify provider coverage) else the
  read degrades to n/a.
- **0DTE-centricity**: the strong evidence is around 0DTE/very short-dated
  expiries; a monthly-chain GEX estimate is a coarser proxy.
- **Pinning is context-dependent**: OPEX effects are real but not
  guaranteed — the read must stay advisory, per the fork's stance.

## 7. Recommended next step (design-only here)

If you want to proceed (no code yet): implement **A1 (chain gamma profile)
+ A2 (OPEX calendar)**, both gated default-off, reusing
`get_options_chain` + `options_math` + the catalyst-calendar pattern —
tests + docs + binding like `get_option_breakeven`. A3 rides A1. Everything
advisory; no execution; no trading_web change (LLM-facing reads).

Decision requested: implement **A1+A2** (per the above), a different subset,
or leave as design-only?
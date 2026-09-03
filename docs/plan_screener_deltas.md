# Implementation Plan — screener V2 sample deltas (price floor, PB bounds, configurable dip days)

**Goal**: bring the moomoo Screener V2 sample-code learnings into the repo's
`screen_value_dip_moomoo` + CLI, keeping current behavior as defaults where
sensible. No API/schema changes; advisory-only, defaults preserved.

## 1. `tradingagents/dataflows/moomoo.py` — `screen_value_dip_moomoo`

**Signature** (add 4 params, keep all existing):

```python
price_min: float | None = 5.0,      # PRICE >= floor (sample: 5.0 penny-stock guard)
pb_min: float | None = None,        # PB interval lower bound (off)
pb_max: float | None = None,        # PB interval upper bound (off)
dip_days: int = 5,                  # pullback window (sample: 20)
chg5d_max: float | None = -0.05,    # unchanged name; now "change over dip_days"
```

- `chg5d_max` **kept** (no rename) — avoids churn across CLI/backend/docs/tests;
  docstring: "max change over the `dip_days` window".
- Builder: conditional adds — `PRICE` lower when `price_min is not None`; `PB`
  min/max when either set; `PRICE_CHANGE_PCT` uses `days=dip_days` (was
  hardcoded 5).
- Retrieve: always add `PB` (currently absent) + existing PRICE/PE/etc.
- Docstring: document units + the new bounds + example (`--dip-days 20`).

## 2. `scripts/value_screener.py` — CLI branch

- `--dip-days` (int, default 5) → `dip_days`; config fallback
  `moomoo_screen_dip_days`.
- `--pb-min` / `--pb-max` (float, default 0) → `pb_min/pb_max` (PB is a ratio
  multiplier like PE — raw units, no scaling); config `moomoo_screen_pb_min/max`.
- `--price-min` **reused** as the server floor too (currently client-only).
  Same gate, earlier: server drops sub-floor names before the results loop;
  identical final set, fewer fetches. `0` disables both.
- Config-fallback block extends: `price` from `moomoo_screen_price_min`
  (default 5.0) when `--price-min` at argparse default.
- Decision: change `--price-min` default to `5.0` (server+client floor
  documented); users keep 15 by passing it.

## 3. Config + env

| key | default | notes |
|---|---|---|
| `moomoo_screen_price_min` | 5.0 | server PRICE floor; `0` = off |
| `moomoo_screen_pb_min` | None | off |
| `moomoo_screen_pb_max` | None | off |
| `moomoo_screen_dip_days` | 5 | pullback window |

Add to `TRADINGAGENTS_*` env map + `DEFAULT_CONFIG` + `.env.example` (commented).

## 4. Tests (hermetic, mocked ctx)

- `test_moomoo_value_dip_screen.py`:
  - defaults: `price_min==5.0, pb_min is None, pb_max is None, dip_days==5`.
  - with `pb_min/pb_max/price_min` set → `add_simple_property` called with
    PRICE + PB bounds; `dip_days=20` → cumulative call `days=20`.
  - retrieve includes PB.
- `test_value_screener.py` CLI: `--dip-days 20 --pb-min 0.5 --pb-max 3.0` →
  kwargs forwarded; `--price-min 0` → server `price_min` None.

## 5. Docs-true set

README bullet, CHANGELOG entry, `docs/api_reference.md` (+`--pb-min`/
`--pb-max`/`--dip-days`), `docs/developer/06-entrypoints.md`,
`docs/AGENT_ONBOARDING.md` changelog, `.env.example`.

## 6. Web sibling (`trading_web`)

- `backend/capabilities.py`: `run_screener` gains `pb_min/pb_max/dip_days` →
  flags; `price_min` already exists (forward it). Allowlist unchanged.
- `tests/test_backend.py`: forwarding assertions.
- Web README row.

## 7. Verification

1. Unit + CLI tests (mock ctx, no OpenD).
2. Ruff both repos.
3. Live smoke: `--universe moomoo-screen -n 20 --dip-days 20 --pb-min 0.5
   --pb-max 3.0 --scan value-dip --value-dip-loose` → expect fewer server rows
   than the 49 current (`price≥5 + PB band` tighten it), watchlist saved, no
   local-empty repeat.
4. Web backend suite (60).

## Risks / decisions

- **`--price-min` default 15.0 → 5.0**: behavior change for existing calls
  that relied on the 15 floor. Mitigate: results-loop floor stays at the
  parser value, but server floor now equals it (0 disables). Document the
  default change in CHANGELOG. If the old default is wanted, pass
  `--price-min 15`.
- **delta vs server filter**: server now does PRICE+PE+PB+ROE+chg+RSI; client
  gate (RSI/%b/stop) still trims → expected ~1-4 finals out of ~20 server
  rows (same as always).
- Sample `PB 0.5–3.0` kept off by default: negative/zero book (distressed) is
  a real value-dip cohort; user opts in.
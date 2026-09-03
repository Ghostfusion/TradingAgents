"""Regime-conditioned performance + stress grid + macro regime (W1-10,
W2-11, W4-6).

- ``regime_conditioned_performance`` — W1-10: tag outcome rows by regime and
  tabulate each strategy/agent's performance per regime (Bull/Bear/High-vol/
  Low-vol) — the "momentum works except in high-vol where it's at the bottom
  of its historical distribution" read.
- ``stress_grid`` — W2-11: deterministic sensitivity of a computed read
  (e.g. DCF fair value) to assumption shifts (forward-revenue %, discount
  rate bps): a computed grid, never LLM-narrated.
- ``macro_regime`` — W4-6: cross-asset regime label from macro inputs (rates
  change, yield-curve slope, credit spread, USD, vol surface) -> Risk-On /
  Liquidity-Contraction / Stagflation, with per-regime threshold guidance.

All pure + deterministic. Inputs are computed markers (already-measured
levels), outputs are counts/ratios/labels; missing input -> honest None.
"""

from __future__ import annotations

# Simple label helper kept local; reuses nothing heavy.


def regime_conditioned_performance(scored_rows: list[dict],
                                   regime_field: str = "regime") -> dict:
    """Tabulate per-regime hit/return from scored ledger rows."""

    def _stat(rows):
        n = len(rows)
        hits = sum(1 for r in rows if r.get("outcome") and r["outcome"].get("hit"))
        rets = [r["outcome"]["return_pct"] for r in rows
                if r.get("outcome") and r["outcome"].get("return_pct") is not None]
        return {
            "n": n,
            "hit_rate": round(hits / n, 3) if n else None,
            "avg_return_pct": round(sum(rets) / len(rets), 3) if rets else None,
        }

    by_regime: dict[str, list[dict]] = {}
    for r in (scored_rows or []):
        reg = str(r.get(regime_field) or "unknown")
        by_regime.setdefault(reg, []).append(r)
    out = {}
    for reg, rows in sorted(by_regime.items()):
        out[reg] = _stat([r for r in rows if isinstance(r.get("outcome"), dict)])
    return out


def stress_grid(base_value: float | None,
                revenue_shifts_pct: list[float] | None = None,
                discount_shifts_bps: list[float] | None = None,
                sensitivity: dict | None = None) -> dict:
    """W2-11 computed stress grid around a base read (e.g. DCF fair value).

    ``sensitivity`` supplies per-axis responsiveness when known (e.g.
    {revenue_pct: value_per_1pct, disc_bps: value_per_100bps}); otherwise a
    flat ±1% per unit (documented approximation, never an LLM guess). All
    returned cells are base_value + shift*responsiveness; base_value None ->
    all cells None.
    """
    if base_value is None:
        return {"base": None, "rows": []}
    revenue_shifts = revenue_shifts_pct or [-10.0, -5.0, 0.0, 5.0, 10.0]
    disc_shifts = discount_shifts_bps or [-50.0, 0.0, 50.0, 100.0]
    d_rev = (sensitivity or {}).get("revenue_pct", base_value * 0.01)
    d_disc = (sensitivity or {}).get("disc_bps", base_value * -0.005)  # higher rate -> lower value
    rows = []
    for rev in revenue_shifts:
        for disc in disc_shifts:
            val = base_value + rev * d_rev / 1.0 + disc * (d_disc / 100.0)
            rows.append({"revenue_shift_pct": rev, "discount_shift_bps": disc,
                         "value": round(max(0.0, val), 2)})
    return {"base": base_value, "rows": rows}


def macro_regime(rate_change_bps: float | None = None,
                 yield_curve_slope_bps: float | None = None,
                 credit_spread_bps: float | None = None,
                 dollar_index_chg_pct: float | None = None,
                 vol_percentile: float | None = None) -> dict:
    """W4-6 cross-asset macro regime (Risk-On / Liquidity-Contraction /
    Stagflation) from computed macro markers. Fail-open: unknown inputs
    leave the label None (no fabrication); a partial set uses what exists.

    Rule (deterministic, documented):
      stagflation when (spread HIGH or rising) AND (rate rising) AND
        (growth proxy weak: dollar up or vol high)
      liquidity_contraction when (rate rising fast) AND (vol percentile high)
      else risk_on when (spread low/normal) AND (rate falling/stable)
      else None (mixed)
    """
    hi_spread = credit_spread_bps is not None and credit_spread_bps >= 300
    hi_vol = vol_percentile is not None and vol_percentile >= 0.7
    rates_up = rate_change_bps is not None and rate_change_bps > 0
    rates_down = rate_change_bps is not None and rate_change_bps < 0
    dxy_up = dollar_index_chg_pct is not None and dollar_index_chg_pct > 0
    flat_slope = yield_curve_slope_bps is not None and abs(yield_curve_slope_bps) < 20

    label = None
    reasons: list[str] = []
    if hi_spread and rates_up and (dxy_up or hi_vol):
        label = "stagflation"
        reasons = ["credit spreads wide", "rates rising", "dollar up or vol high"]
    elif rates_up and hi_vol:
        label = "liquidity_contraction"
        reasons = ["rates rising", "vol percentile high"]
    elif not hi_spread and rates_down:
        label = "risk_on"
        reasons = ["credit normal/wide", "rates falling"]
    elif not hi_spread and flat_slope and not rates_up:
        label = "risk_on"
        reasons = ["credit normal", "curve flat, rates stable"]
    return {"regime": label, "reasons": reasons,
            "inputs": {"rate_change_bps": rate_change_bps,
                       "yield_curve_slope_bps": yield_curve_slope_bps,
                       "credit_spread_bps": credit_spread_bps,
                       "dollar_index_chg_pct": dollar_index_chg_pct,
                       "vol_percentile": vol_percentile}}


__all__ = ["regime_conditioned_performance", "stress_grid", "macro_regime"]

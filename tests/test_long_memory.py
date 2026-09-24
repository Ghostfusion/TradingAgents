"""V2 - memory parameter beside the HAR-family forecast (paper 2605.24285).

Failing-first proof for ``tradingagents/strategies/long_memory.py``:

1. On a synthetic series with a known memory parameter ``d``, GPH and local
   Whittle bracket the truth within their ``se``.
2. The estimate is strictly backward - a window that still contains an
   observation at or after the as-of date returns ``unavailable``.
3. The forecast record always carries ``d`` beside the forecast, and the HAR-X
   leg is refused (never zero-filled) until a panel read exists.

The card's mutation - computing ``d`` on the full sample so a future stressed
name enters the aggregate - fails assertion 2 by name.
"""

from __future__ import annotations

import numpy as np

from tradingagents.strategies.long_memory import (
    MEMORY_WINDOW,
    memory_parameter,
    rv_forecast,
)


def _arfima(n: int, d: float, seed: int) -> np.ndarray:
    """One ARFIMA(0, d, 0) draw with a known memory parameter ``d``.

    White noise through the fractional-difference filter ``(1 - L)^{-d}``, whose
    spectral density is ``~ lambda^{-2d}`` at low frequency - exactly the
    process the GPH / local-Whittle slope is built to recover.
    """
    burn = 200
    size = n + burn
    psi = np.empty(size)
    psi[0] = 1.0
    for k in range(1, size):
        psi[k] = psi[k - 1] * (k - 1 + d) / k
    noise = np.random.default_rng(seed).standard_normal(size)
    return np.convolve(noise, psi)[:size][burn:burn + n]


def test_memory_parameter_is_backward_and_reported_beside_forecast():
    # (1) A synthetic series with a known memory parameter: both estimators
    #     bracket the truth within `se`.
    for d_true, seed in ((0.0, 3), (0.44, 3)):
        rec = memory_parameter(_arfima(MEMORY_WINDOW, d_true, seed))
        assert rec["status"] == "ok", rec
        assert abs(rec["gph_d"] - d_true) <= rec["se"], (d_true, rec)
        assert abs(rec["whittle_d"] - d_true) <= rec["se"], (d_true, rec)

    # (2) Strictly backward: a window that still contains an observation at or
    #     after the as-of date is refused, never silently trimmed.
    as_of = MEMORY_WINDOW
    full = _arfima(as_of + 150, 0.44, 7)
    refused = memory_parameter(full, as_of=as_of)
    assert refused["status"] == "unavailable", refused
    assert refused["gph_d"] is None and refused["whittle_d"] is None, refused
    assert "backward" in refused["unavailable"], refused
    # the strictly-backward window itself is estimable
    assert memory_parameter(full[:as_of], as_of=as_of)["status"] == "ok"

    # (3) `d` travels beside the forecast, never instead of it.
    low = rv_forecast(_arfima(MEMORY_WINDOW, 0.0, 3))
    high = rv_forecast(_arfima(MEMORY_WINDOW, 0.44, 3))
    for rec in (low, high):
        assert "d" in rec, rec
        assert rec["forecast"] is not None, rec
        assert rec["memory"]["status"] == "ok", rec
    assert low["d"] != high["d"], (low["d"], high["d"])
    assert low != high
    # the HAR-X leg is refused, not zero-filled, until a panel read exists
    assert low["extra"]["status"] == "unavailable", low["extra"]
    # and the refusal still carries `d` (None), never drops the key
    refused_fc = rv_forecast(full, as_of=as_of)
    assert refused_fc["status"] == "unavailable", refused_fc
    assert "d" in refused_fc and refused_fc["d"] is None, refused_fc

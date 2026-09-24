"""H4: the out-of-sample R-squared ceiling and the excess-accuracy baseline.

``alpha_eval.ceiling_ratio`` reports the bound 2602.07841 derives as the point
``((2*DA - 1)^2, R2_OOS / kappa)`` and flags a point above the 45-degree line;
``calibration.excess_accuracy`` reports the model's hit rate minus the
always-up baseline's on the identical rows. Both are read through
``enable_accuracy_ceiling`` (default off).
"""

from __future__ import annotations

import math
import random

from tradingagents.strategies.alpha_eval import ceiling_ratio
from tradingagents.strategies.calibration import excess_accuracy

#: 300 rows: a 255-row fit window and a 45-row hold-out (``train_frac=0.85``).
_N_TRAIN = 255
_N_HOLD = 45


def _gate(monkeypatch, on: bool) -> None:
    """Flip ``enable_accuracy_ceiling`` at the config accessor the read uses."""
    monkeypatch.setattr(
        "tradingagents.dataflows.config.get_config",
        lambda: {"enable_accuracy_ceiling": on},
    )


def _series(seed: int = 11) -> tuple[list[float], list[float]]:
    """A returns/forecast pair whose directional skill sits in the fit window.

    The leading ``_N_TRAIN`` rows are called right 90% of the time, the
    hold-out only 60%; the forecast's magnitude is 0.6 sigma, large enough that
    the hold-out forecast is *worse* than the realized mean. That is the point
    the card constructs: a positive ``(2DA-1)^2`` beside a negative
    out-of-sample ``R^2``.
    """
    rng = random.Random(seed)
    sigma = 0.012
    returns: list[float] = []
    forecasts: list[float] = []
    for i in range(_N_TRAIN + _N_HOLD):
        realized = rng.gauss(0.0, sigma)
        right = rng.random() < (0.9 if i < _N_TRAIN else 0.6)
        call = 1.0 if realized > 0 else -1.0
        if not right:
            call = -call
        returns.append(realized)
        forecasts.append(call * 0.6 * sigma)
    return returns, forecasts


def test_above_line_point_is_flagged(monkeypatch):
    """A constructed forecast with a positive ``(2DA-1)^2`` and a negative
    out-of-sample ``R^2`` lands above the 45-degree line and is flagged.

    ``sigma_hat`` is a one-step-ahead GARCH(1,1) forecast from the 255-row fit
    window, so the ceiling is scored on rows that fit has never seen. Fitting
    ``sigma_hat`` in-sample - on the rows the ceiling evaluates - fails this
    test by name.
    """
    _gate(monkeypatch, on=True)
    returns, forecasts = _series()

    rec = ceiling_ratio(returns, forecasts, train_frac=0.85)

    assert rec["flagged"] is True, rec["unavailable"] or rec["basis"]
    assert rec["unavailable"] is None, rec["unavailable"]
    assert (rec["train_n"], rec["n"]) == (_N_TRAIN, _N_HOLD)
    assert rec["da_squared"] > 0.0, "the forecast claims directional skill"
    assert rec["r2_oos"] < 0.0, "and its out-of-sample R^2 is negative"
    assert rec["kappa_hat"] < 0.0
    assert rec["r2_ratio"] > rec["da_squared"], "the point is above the line"
    assert rec["flagged"] is True
    assert "above the 45-degree line" in rec["basis"]


def _clustered_series(seed: int = 7, om: float = 1e-5, al: float = 0.15,
                      be: float = 0.80) -> tuple[list[float], list[float]]:
    """A returns/forecast pair whose VOLATILITY is clustered.

    Needed because the property below is invisible without it: on iid data the
    GARCH(1,1) fit returns ``alpha = 0``, the conditional-variance recursion
    stops depending on the current return at all, and consuming that return
    before or after the emission makes no difference to any reported number.
    With clustering the fit returns ``alpha ~ 0.2`` and the two orders separate.
    """
    rng = random.Random(seed)
    s2 = om / (1.0 - al - be)
    rets: list[float] = []
    fcs: list[float] = []
    for i in range(_N_TRAIN + _N_HOLD):
        r = rng.gauss(0.0, math.sqrt(s2))
        s2 = om + al * r * r + be * s2
        right = rng.random() < (0.9 if i < _N_TRAIN else 0.6)
        call = 1.0 if r > 0 else -1.0
        if not right:
            call = -call
        rets.append(r)
        fcs.append(call * 0.6 * math.sqrt(om / (1.0 - al - be)))
    return rets, fcs


def test_sigma_hat_never_consumes_its_own_row(monkeypatch):
    """``sigma_hat_t`` is measurable at ``t-1``: the hold-out row's own return
    updates the conditional variance only AFTER that row's sigma is emitted.

    Consuming the return first makes ``eps_t`` the model's own standardized
    residual and the ceiling circular - the defect the train/hold-out split
    exists to prevent. Measured on this fixture, ``kappa_hat`` is ``-0.343``
    when the emission comes first and ``-0.255`` when the row's own return is
    consumed first, so the bound below is the property and not a magic number.
    """
    _gate(monkeypatch, on=True)
    returns, forecasts = _clustered_series()

    rec = ceiling_ratio(returns, forecasts, train_frac=0.85)

    assert rec["unavailable"] is None, rec["unavailable"]
    assert rec["kappa_hat"] < -0.30, rec["kappa_hat"]
    assert rec["flagged"] is True


def test_thin_hold_out_is_unavailable_never_a_ratio(monkeypatch):
    """Below the row floor the ceiling refuses: the hold-out is not enough to
    fit ``sigma_hat`` on, and a ratio off 20 rows is not reported."""
    _gate(monkeypatch, on=True)
    returns, forecasts = _series()

    rec = ceiling_ratio(returns, forecasts, train_frac=0.95)

    assert rec["n"] == 15
    assert rec["flagged"] is None
    assert rec["r2_ratio"] is None
    assert rec["unavailable"]


def test_excess_accuracy_scores_an_always_up_model_at_zero(monkeypatch):
    """The always-up model has zero excess accuracy against itself, and a model
    that calls every row right earns exactly the base rate it beat."""
    _gate(monkeypatch, on=True)
    realized = [0.01] * 20 + [-0.01] * 20
    always_up = [1.0] * 40
    perfect = [1.0] * 20 + [-1.0] * 20

    flat = excess_accuracy(always_up, realized)
    assert flat["unavailable"] is None, flat["unavailable"]
    assert flat["baseline_hit_rate"] == 0.5
    assert flat["model_hit_rate"] == 0.5
    assert flat["excess"] == 0.0
    assert len(flat["per_fold"]) == flat["folds"] == 5
    assert all(f["excess"] == 0.0 for f in flat["per_fold"])

    beating = excess_accuracy(perfect, realized)
    assert beating["model_hit_rate"] == 1.0
    assert beating["excess"] == 0.5
    interval = beating["interval"]
    assert interval is not None and interval["block"] >= 1
    assert interval["low"] <= beating["excess"] <= interval["high"]


def test_gate_off_is_unavailable(monkeypatch):
    """Both reads are the one instrument, and it is off by default."""
    _gate(monkeypatch, on=False)
    returns, forecasts = _series()

    ceiling = ceiling_ratio(returns, forecasts, train_frac=0.85)
    assert ceiling["flagged"] is None
    assert ceiling["unavailable"] == "accuracy ceiling off (enable_accuracy_ceiling)"

    excess = excess_accuracy([1.0] * 40, [0.01] * 40)
    assert excess["excess"] is None
    assert excess["unavailable"] == "excess accuracy off (enable_accuracy_ceiling)"

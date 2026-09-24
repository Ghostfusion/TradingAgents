"""R3 - the spectral null band (2607.06373), at the module boundary.

A spectrum estimated from a finite window moves on its own, so a spectral move is
only a structural change when it exceeds the first-order null band the paper
derives for a shrinkage covariance estimator's leading eigenspace and for the
scalar spectral functionals (the absorption ratio, the leading-eigenvalue share).
These tests pin:

* a pair of successive windows drawn from ONE fixed covariance is **not**
  flagged, a window carrying an injected block correlation at known name indices
  **is** flagged, and the band is a function of the window length and the
  shrinkage intensity alone;
* the read reports the window it was taken over and **refuses** a thin one,
  rather than reading a number off it (rule 4: missing data is `unavailable`,
  never a zero);
* a non-rejection reads "not detectable", never "no change" - the paper's own
  caveat is that a non-rejection partly reflects a wide band;
* the FLAG - never the absorption ratio, never the projector distance - is what
  reaches `regime_score`, and its direction is observable in the composite.

Offline and deterministic: every panel is drawn from a fixed covariance with a
fixed seed, no vendor call.
"""

from __future__ import annotations

import numpy as np
import pytest

import tradingagents.dataflows.config as cfgmod
from tradingagents.strategies.covariance_models import (
    SPECTRAL_DETECTED,
    SPECTRAL_MIN_OBS,
    SPECTRAL_NOT_DETECTABLE,
    SPECTRAL_NOT_DETECTABLE_REASON,
    SPECTRAL_NULL_Z,
    SPECTRAL_UNAVAILABLE,
    eigen_projector_distance,
    panel_spectrum,
    spectral_functionals,
    spectral_null_band,
)
from tradingagents.strategies.regime import spectral_change_read
from tradingagents.strategies.regime_score import (
    SPECTRAL_CHANGE_COMPONENT,
    SPECTRAL_CHANGE_KEY,
    SPECTRAL_CHANGE_RAMP,
    _spectral_change_values,
    align_components,
    regime_score,
)

#: An eight-name cross-section over a 120-observation window: the smallest shape
#: the read is meaningful at, and the paper's own working range (`N` in the tens).
NAMES = tuple("ABCDEFGH")
WINDOW = 120
GATE = {"enable_spectral_null_band": True}

#: The six market-level legs, at values whose aligned contributions the owner's
#: suite already pins (the same mid-band set `test_regime_score` uses).
ENVIRONMENT = {
    "market_trend": 0.06,
    "breadth": 60.0,
    "vix_percentile": 0.30,
    "vix_term_structure": 0.95,
    "choppiness": 35.0,
    "realized_vol_percentile": 0.30,
}


def _cov_market(n: int, rho: float = 0.2, sigma: float = 0.01) -> np.ndarray:
    """One market factor: every pair correlated at ``rho``."""
    cov = np.full((n, n), rho * sigma * sigma)
    np.fill_diagonal(cov, sigma * sigma)
    return cov


def _cov_block(
    n: int, block: tuple[int, ...], rho: float = 0.2, block_rho: float = 0.9,
    sigma: float = 0.01,
) -> np.ndarray:
    """The market factor, plus a strong equicorrelation inside ``block``."""
    cov = _cov_market(n, rho=rho, sigma=sigma)
    for i in block:
        for j in block:
            if i != j:
                cov[i, j] = block_rho * sigma * sigma
    return cov


def _draw(cov: np.ndarray, n_obs: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.multivariate_normal(np.zeros(len(cov)), cov, size=n_obs)


def _window(matrix: np.ndarray, start: int, length: int) -> dict:
    return {
        name: [float(v) for v in matrix[start:start + length, i]]
        for i, name in enumerate(NAMES)
    }


def _stable_pair() -> tuple[dict, dict]:
    """Two SUCCESSIVE windows of one series drawn from a fixed covariance."""
    matrix = _draw(_cov_market(len(NAMES)), 300, seed=11)
    return _window(matrix, 100, WINDOW), _window(matrix, 101, WINDOW)


def _injected_pair() -> tuple[dict, dict]:
    """Two windows whose CURRENT one carries a block at known name indices."""
    prev = _window(_draw(_cov_market(len(NAMES)), 300, seed=5), 0, WINDOW)
    curr = _window(_draw(_cov_block(len(NAMES), (1, 2, 3)), 300, seed=6), 0, WINDOW)
    return prev, curr


def _gate_on(monkeypatch) -> None:
    monkeypatch.setattr(cfgmod, "get_config", lambda: dict(GATE))


# --------------------------------------------------------------------------
# the card's failing-first test
# --------------------------------------------------------------------------


def test_a_stable_covariance_is_not_flagged() -> None:
    """Stable -> not flagged; an injected block -> flagged; band ~ (T, delta)."""
    prev, curr = _stable_pair()
    stable = spectral_change_read(prev, curr, cfg=GATE)
    assert stable["flag"] is False
    assert stable["reading"] == SPECTRAL_NOT_DETECTABLE_REASON
    # every functional is reported beside its own band and its own flag
    for leg in ("projector_distance", "absorption_ratio", "leading_share"):
        entry = stable[leg]
        assert entry["band"] > 0.0, leg
        assert entry["threshold"] == pytest.approx(entry["band"] * entry["geometry"])
        assert entry["exceeds"] is False, leg

    inj_prev, inj_curr = _injected_pair()
    injected = spectral_change_read(inj_prev, inj_curr, cfg=GATE)
    assert injected["flag"] is True
    for leg in ("projector_distance", "absorption_ratio", "leading_share"):
        assert injected[leg]["exceeds"] is True, leg
        assert injected[leg]["normalized"] > injected[leg]["band"], leg

    # the band is calibrated from the window length and the shrinkage intensity
    # alone - the same length and intensity carry the same band, whatever the
    # data did (these two panels disagree on the flag and agree on the band).
    assert spectral_null_band(WINDOW, 0.25) == spectral_null_band(WINDOW, 0.25)
    assert spectral_null_band(WINDOW, 0.5) < spectral_null_band(WINDOW, 0.25)
    assert spectral_null_band(WINDOW * 2, 0.25) < spectral_null_band(WINDOW, 0.25)
    assert stable["band_calibration"] == injected["band_calibration"]
    assert stable["projector_distance"]["band"] == injected["projector_distance"]["band"]
    assert stable["band_calibration"] == pytest.approx(
        SPECTRAL_NULL_Z / (WINDOW ** 0.5), rel=1e-9
    )


# --------------------------------------------------------------------------
# rule 4: the window travels with the number, and a thin one is refused
# --------------------------------------------------------------------------


def test_a_thin_window_is_refused_with_its_window_never_a_zero() -> None:
    thin = SPECTRAL_MIN_OBS - 10
    matrix = _draw(_cov_market(len(NAMES)), 300, seed=11)
    spectrum = panel_spectrum(_window(matrix, 100, thin))
    assert spectrum["eigenvalues"] is None and spectrum["shrinkage"] is None
    assert f"{thin} observation(s)" in spectrum["unavailable"]
    assert str(SPECTRAL_MIN_OBS) in spectrum["unavailable"]

    read = spectral_change_read(
        _window(matrix, 100, thin), _window(matrix, 101, thin), cfg=GATE
    )
    assert read["flag"] is None
    assert read["reading"] == SPECTRAL_UNAVAILABLE
    assert str(SPECTRAL_MIN_OBS) in read["unavailable"]
    assert read["band_calibration"] is None
    for leg in ("projector_distance", "absorption_ratio", "leading_share"):
        assert read[leg]["exceeds"] is None, leg
        assert read[leg]["value"] is None, leg


def test_a_zero_band_is_refused_rather_than_flagging_every_move() -> None:
    """A saturated intensity leaves no band, so nothing is distinguishable."""
    read = spectral_change_read(*_injected_pair(), cfg=GATE, shrinkage=1.0)
    assert read["band_calibration"] == 0.0
    assert read["flag"] is None
    assert read["reading"] == SPECTRAL_UNAVAILABLE
    assert "band is zero" in read["unavailable"]


def test_the_engine_intensity_is_reported_beside_the_band() -> None:
    """The band's intensity is the caller's; the engine's is reported, not used."""
    read = spectral_change_read(*_stable_pair(), cfg=GATE)
    assert read["shrinkage"] == 0.0  # the band: the correlation matrix read raw
    engine = read["engine_shrinkage"]
    assert engine is not None and 0.0 <= engine <= 1.0
    assert f"{engine:.6f}" in read["basis"]


# --------------------------------------------------------------------------
# the wording: "not detectable", never "no change"
# --------------------------------------------------------------------------


def test_a_non_rejection_reads_not_detectable_never_no_change() -> None:
    read = spectral_change_read(*_stable_pair(), cfg=GATE)
    assert read["flag"] is False
    assert SPECTRAL_NOT_DETECTABLE in read["reading"]
    assert "no change" not in read["reading"].lower()
    assert "not evidence that the structure held" in read["reading"]
    for leg in ("projector_distance", "absorption_ratio", "leading_share"):
        assert SPECTRAL_NOT_DETECTABLE in read[leg]["reading"], leg
        assert "no change" not in read[leg]["reading"].lower(), leg
    assert SPECTRAL_DETECTED != SPECTRAL_NOT_DETECTABLE


# --------------------------------------------------------------------------
# the gate, and the flag that feeds the score
# --------------------------------------------------------------------------


def test_the_gate_is_off_by_default_and_the_read_is_none() -> None:
    prev, curr = _stable_pair()
    assert spectral_change_read(prev, curr, cfg={}) is None
    assert spectral_change_read(prev, curr) is None  # the tree's own default
    assert spectral_change_read(prev, curr, cfg=GATE) is not None


def test_the_gate_off_leaves_the_six_leg_component_set_unchanged(monkeypatch) -> None:
    monkeypatch.setattr(cfgmod, "get_config", lambda: {})
    res = regime_score(ENVIRONMENT)
    assert SPECTRAL_CHANGE_KEY not in res["components"]
    assert len(res["measured"]) == 6
    assert res["coverage"] == pytest.approx(1.0)
    # an undeclared key is ignored, never scored
    assert SPECTRAL_CHANGE_KEY not in align_components({SPECTRAL_CHANGE_KEY: 0.0})


def test_the_flag_is_what_the_component_takes_never_the_functional(
    monkeypatch,
) -> None:
    _gate_on(monkeypatch)
    # the glue a leaf uses: two panels in, the FLAG out
    assert _spectral_change_values(*_stable_pair(), cfg=GATE) == {
        SPECTRAL_CHANGE_KEY: 0.0
    }
    assert _spectral_change_values(*_injected_pair(), cfg=GATE) == {
        SPECTRAL_CHANGE_KEY: 1.0
    }

    read = spectral_change_read(*_injected_pair(), cfg=GATE)
    # the read itself is accepted, and it is its flag that is aligned - the
    # component is declared lower_better, so a detected change scores 0
    assert align_components({SPECTRAL_CHANGE_KEY: read})[SPECTRAL_CHANGE_KEY] == 0.0
    assert align_components({SPECTRAL_CHANGE_KEY: 0.0})[SPECTRAL_CHANGE_KEY] == 100.0
    # a functional on any other scale is NOT the flag: absent, never scored
    for raw in (read["absorption_ratio"]["value"], 0.42, 2.0, -1.0):
        assert align_components({SPECTRAL_CHANGE_KEY: raw})[SPECTRAL_CHANGE_KEY] is None
    assert SPECTRAL_CHANGE_COMPONENT.unit.startswith("flag:")
    assert SPECTRAL_CHANGE_RAMP == (0.0, 1.0)


def test_a_detected_change_lowers_the_environment_read(monkeypatch) -> None:
    _gate_on(monkeypatch)
    quiet = regime_score({**ENVIRONMENT, SPECTRAL_CHANGE_KEY: 0.0})
    detected = regime_score({**ENVIRONMENT, SPECTRAL_CHANGE_KEY: 1.0})
    assert quiet["coverage"] == pytest.approx(1.0)
    assert detected["score"] < quiet["score"]
    assert len(quiet["measured"]) == 7
    assert SPECTRAL_CHANGE_KEY in quiet["components"]


# --------------------------------------------------------------------------
# the cost contract: one eigendecomposition per rolling window
# --------------------------------------------------------------------------


def test_one_eigendecomposition_per_window(monkeypatch) -> None:
    calls = {"n": 0}
    real_eigh = np.linalg.eigh

    def counting_eigh(*args, **kwargs):
        calls["n"] += 1
        return real_eigh(*args, **kwargs)

    monkeypatch.setattr(np.linalg, "eigh", counting_eigh)
    prev, curr = _stable_pair()
    read = spectral_change_read(prev, curr, cfg=GATE)
    assert read["flag"] is False
    assert calls["n"] == 2  # one per window, shared by all three functionals


# --------------------------------------------------------------------------
# the two legs the read is built from, standalone
# --------------------------------------------------------------------------


def test_the_projector_leg_is_bounded_by_its_own_geometry() -> None:
    prev, curr = _injected_pair()
    leg = eigen_projector_distance(prev, curr, k=1)
    assert 0.0 <= leg["value"] <= leg["geometry"]  # ||P1 - P2||_F <= sqrt(2k)
    assert leg["normalized"] == pytest.approx(leg["value"] / leg["geometry"])
    assert leg["exceeds"] == (leg["normalized"] > leg["band"])


def test_the_scalars_are_shares_of_the_same_spectrum() -> None:
    prev, curr = _stable_pair()
    scalars = spectral_functionals(prev, curr)
    for name in ("absorption_ratio", "leading_share"):
        entry = scalars[name]
        assert 0.0 < entry["value"] <= 1.0, name
        assert entry["move"] == pytest.approx(entry["curr"] - entry["prev"]), name
        assert entry["geometry"] > 0.0 and entry["band"] > 0.0, name
    # the absorption ratio covers at least the leading mode it contains
    assert scalars["absorption_ratio"]["value"] >= scalars["leading_share"]["value"]
    assert scalars["absorption_ratio"]["k"] >= 1
    assert scalars["leading_share"]["k"] == 1

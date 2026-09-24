"""V5 - eigenspace rotation as a state variable (2608.14487), at the boundary.

The read removes the market mode from two rolling correlation matrices and
measures the rotation of the subdominant eigenspace. The **failing-first** test
is ``test_rotation_refuses_inside_the_mp_edge``: an eigenspace whose subdominant
block sits inside the Marchenko-Pastur edge is noise, so the read must refuse -
the mutation that deletes the edge check returns a rotation number and fails it.
"""

import math

import numpy as np
import pytest

from tradingagents.strategies.eigen_rotation import eigen_rotation

pytestmark = pytest.mark.timeout(60)

#: A six-name cross-section over a one-year window - the smallest panel that can
#: carry a market mode plus three subdominant directions, at the window the X3
#: read already uses.
N_NAMES = 6
WINDOW = 252
AS_OF = "2026-09-24"


def _factor_corr(rho: float) -> np.ndarray:
    corr = np.full((N_NAMES, N_NAMES), rho, dtype=float)
    np.fill_diagonal(corr, 1.0)
    return corr


def _sampled_corr(rho: float, seed: int) -> np.ndarray:
    """A correlation matrix drawn from a one-factor population - a real window."""
    rng = np.random.default_rng(seed)
    draws = rng.multivariate_normal(np.zeros(N_NAMES), _factor_corr(rho), size=WINDOW)
    return np.corrcoef(draws, rowvar=False)


def _subdominant_basis(corr: np.ndarray) -> np.ndarray:
    """The market mode removed, then the three subdominant eigenvectors as columns."""
    vals, vecs = np.linalg.eigh(corr)
    order = np.argsort(vals)[::-1]
    return vecs[:, order][:, 1:4]


def _mean_squared_sine(prev: np.ndarray, curr: np.ndarray) -> float:
    """The rotation measure, computed independently of the production path."""
    u = _subdominant_basis(prev)
    v = _subdominant_basis(curr)
    cosines = np.clip(np.linalg.svd(u.T @ v, compute_uv=False), -1.0, 1.0)
    return float(np.mean(1.0 - cosines ** 2))


def _mp_lower() -> float:
    return (1.0 - math.sqrt(N_NAMES / WINDOW)) ** 2


# --------------------------------------------------------------------------
# the card's failing-first test
# --------------------------------------------------------------------------


def test_rotation_refuses_inside_the_mp_edge() -> None:
    """A subdominant block inside the Marchenko-Pastur edge is noise -> unavailable.

    The panel is drawn from an isotropic (rho=0) population, so after the market
    mode is removed every subdominant eigenvalue sits at or above the
    Marchenko-Pastur lower edge - inside the bulk, where an eigenvector is noise
    and the angle between two of them carries no rotation.
    """
    lower = _mp_lower()
    prev, curr = _sampled_corr(0.0, 1), _sampled_corr(0.0, 2)
    # the premise: the block really is inside the edge
    for corr in (prev, curr):
        assert np.all(np.linalg.eigvalsh(corr)[::-1][1:4] >= lower)

    read = eigen_rotation(prev, curr, window=WINDOW, as_of=AS_OF)

    assert read["status"] == "unavailable"
    # never a rotation number, and never an angle from a noise eigenspace
    assert read["rec"] is None
    assert read["angles"] is None
    assert "inside the Marchenko-Pastur edge" in read["unavailable"]
    # the conditioning spectrum is reported with the refusal
    edge = read["mp_edge_check"]
    assert edge is not None
    assert edge["outside"] is False
    assert edge["mp_lower"] == pytest.approx(lower, rel=1e-12)
    assert len(edge["subdominant_eigenvalues"]) == 2 * 3
    assert all(v >= lower for v in edge["subdominant_eigenvalues"])


# --------------------------------------------------------------------------
# acceptance: outside the edge, the number IS the mean squared sine
# --------------------------------------------------------------------------


def test_rotation_outside_the_edge_is_the_mean_squared_sine() -> None:
    """Outside the edge ``rec`` equals the mean squared sine of the principal
    angles, and the angles are the principal angles themselves."""
    prev, curr = _sampled_corr(0.6, 1), _sampled_corr(0.6, 2)
    read = eigen_rotation(prev, curr, window=WINDOW, as_of=AS_OF)

    assert read["status"] == "ok"
    assert read["mp_edge_check"]["outside"] is True
    assert read["rec"] == pytest.approx(_mean_squared_sine(prev, curr), abs=1e-9)

    # the principal angles are arccos of the singular values of U^T V
    cosines = np.clip(
        np.linalg.svd(_subdominant_basis(prev).T @ _subdominant_basis(curr),
                      compute_uv=False), -1.0, 1.0)
    assert read["angles"] == pytest.approx([math.acos(c) for c in cosines], abs=1e-9)
    assert read["window"] == WINDOW
    assert read["as_of"] == AS_OF
    assert read["n_names"] == N_NAMES


def test_rotation_is_invariant_to_eigenvector_sign(monkeypatch) -> None:
    """A sign-flipped eigenvector is the same direction, so the rotation cannot move.

    ``eigh`` returns each eigenvector up to a sign; the read must not depend on
    which sign LAPACK happened to pick.
    """
    prev, curr = _sampled_corr(0.6, 1), _sampled_corr(0.6, 2)
    base = eigen_rotation(prev, curr, window=WINDOW)
    assert base["status"] == "ok"

    real_eigh = np.linalg.eigh

    def flipping_eigh(*args, **kwargs):
        vals, vecs = real_eigh(*args, **kwargs)
        vecs = vecs.copy()
        vecs[:, ::2] *= -1.0  # flip half the eigenvectors' signs
        return vals, vecs

    monkeypatch.setattr(np.linalg, "eigh", flipping_eigh)
    flipped = eigen_rotation(prev, curr, window=WINDOW)

    assert flipped["status"] == "ok"
    assert flipped["rec"] == pytest.approx(base["rec"], abs=1e-12)


# --------------------------------------------------------------------------
# rule 4: the window travels with the refusal
# --------------------------------------------------------------------------


def test_rotation_needs_a_window_longer_than_the_panel() -> None:
    """At a window no longer than the panel the bulk has no lower edge -> refuse."""
    prev, curr = _sampled_corr(0.6, 1), _sampled_corr(0.6, 2)
    read = eigen_rotation(prev, curr, window=N_NAMES)
    assert read["status"] == "unavailable"
    assert read["rec"] is None
    assert read["window"] == N_NAMES

    missing = eigen_rotation(prev, curr)
    assert missing["status"] == "unavailable"
    assert "window" in missing["unavailable"]

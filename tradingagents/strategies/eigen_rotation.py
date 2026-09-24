"""Eigenspace rotation as a state variable (V5, 2608.14487).

A rolling correlation matrix's eigenspace is not a fixed object: the market mode
is one direction and the residual, *subdominant* directions drift as the
cross-section's factor structure reshapes. ``eigen_rotation`` measures that
drift as a scalar state variable - the mean squared sine of the three principal
angles between consecutive windows' subdominant eigenspaces - after removing the
market mode (the leading eigenvector).

Why a *state* and not a signal: the rotation is coincident and direction-blind,
exactly like the Marchenko-Pastur lower-spectrum count it is gated beside (X3).
It describes that the cross-section's residual geometry moved; it does not say
what it moved toward.

The Marchenko-Pastur guard (mandatory). An eigenvector whose eigenvalue lies
*inside* the Marchenko-Pastur bulk is a noise direction, and the angle between
two noise directions carries no rotation. This read therefore requires the
subdominant block to sit **outside** the bulk before it will report a number:
with only the bulk's **lower** edge available (``mp_below_count`` returns
``mp_lower``), the conservative sufficient condition for "outside" is that every
eigenvalue in the block is **below** that lower edge - an eigenvalue at or above
the lower edge may still lie in the bulk, so the block is refused. The bound is
reused from ``market_breadth.mp_below_count`` (ground rule 2: one producer), never
re-derived here.

No-fabrication (rule 4): a refused read returns ``unavailable`` with the reason
and the window it was computed over, never a zero and never a number from a
noise eigenspace.
"""

from __future__ import annotations

import math

import numpy as np

#: The number of subdominant eigenvectors the rotation is measured between. The
#: market mode is removed first, so these are the residual directions the read
#: tracks; three is the smallest block that still spans a 3-D rotation.
SUBSPACE_MODES = 3

#: The smallest panel that can carry a market mode PLUS the subdominant block.
MIN_NAMES = SUBSPACE_MODES + 2


def _unavailable(reason: str, *, n_names: int = 0, window=None,
                 n_modes: int = SUBSPACE_MODES, mp_edge_check=None,
                 as_of=None) -> dict:
    """The refusal shape of the V5 read: ``unavailable``, never a zero.

    The window the read was computed over and (when it was taken) the
    Marchenko-Pastur record travel with the reason, so a caller can see WHICH
    panel the refusal is about (rule 4 / H10).
    """
    return {
        "rec": None,
        "angles": None,
        "mp_edge_check": mp_edge_check,
        "status": "unavailable",
        "unavailable": reason,
        "n_names": int(n_names),
        "window": None if window is None else int(window),
        "n_modes": int(n_modes),
        "as_of": as_of,
        "basis": f"eigenspace rotation unavailable: {reason}",
    }


def _as_matrix(corr):
    """A finite square matrix from ``corr``, or None when it is not one."""
    if corr is None:
        return None
    try:
        mat = np.asarray(corr, dtype=float)
    except (TypeError, ValueError):
        return None
    if mat.ndim != 2 or mat.shape[0] != mat.shape[1] or mat.shape[0] == 0:
        return None
    if not np.all(np.isfinite(mat)):
        return None
    return mat


def eigen_rotation(prev_corr, curr_corr, *, window=None,
                   n_modes: int = SUBSPACE_MODES, as_of=None) -> dict:
    """Rotation of the subdominant eigenspace between two rolling windows (V5).

    ``prev_corr`` / ``curr_corr`` are the ``n x n`` correlation matrices of two
    rolling windows of ONE cross-section - **never a single symbol**, because the
    read needs a panel. The caller owns the window alignment (both windows end at
    the same as-of date); ``as_of`` is echoed so that alignment is visible in the
    record.

    ``window`` is the number of return observations each correlation matrix was
    built over. It is required: it is the only input to the Marchenko-Pastur
    lower edge the guard is cut at, and a read that cannot name its window cannot
    say whether the subdominant block is signal or noise. It must be **longer
    than the panel** (``window > n``) - at a window no longer than the panel the
    bulk has no lower edge, and ``mp_below_count`` refuses it (rule 4).

    The market mode (the leading eigenvector) is removed from each matrix, and
    the rotation is the mean squared sine of the three principal angles between
    the two subdominant eigenspaces: with ``U`` / ``V`` the orthonormal ``n x k``
    bases, ``cos(theta_i) = svd(U^T V)_i`` and ``rec = mean(1 - cos(theta_i)^2)``.
    The measure is invariant to an eigenvector's SIGN, because the singular
    values of ``U^T V`` are.

    Returns ``{rec, angles, mp_edge_check, status, unavailable, n_names, window,
    n_modes, as_of, basis}``. ``rec`` is the rotation state variable (the mean
    squared sine) and ``angles`` the three principal angles in radians. Every
    value is ``None`` and ``status`` is ``"unavailable"`` - never a zero - when
    either matrix is unusable, the window is missing or not longer than the panel,
    the subdominant block lies at or above the Marchenko-Pastur lower edge, or the
    panel is too small for a market mode plus the block.
    """
    modes = int(n_modes)
    if modes < 1:
        return _unavailable(f"n_modes must be at least 1, got {modes}", as_of=as_of)
    prev = _as_matrix(prev_corr)
    curr = _as_matrix(curr_corr)
    if prev is None or curr is None:
        return _unavailable(
            "both inputs must be finite square correlation matrices", as_of=as_of
        )
    n = int(prev.shape[0])
    if curr.shape != prev.shape:
        return _unavailable(
            f"the two correlation matrices differ in shape "
            f"({prev.shape} vs {curr.shape})",
            n_names=n, as_of=as_of,
        )
    if n < modes + 2 or n < MIN_NAMES:
        return _unavailable(
            f"{n} name(s) cannot carry a market mode plus {modes} subdominant "
            f"directions (needs at least {max(modes + 2, MIN_NAMES)})",
            n_names=n, as_of=as_of,
        )
    if window is None:
        return _unavailable(
            "the observation window behind the correlation matrices was not "
            "supplied, so the Marchenko-Pastur edge cannot be read and the "
            "subdominant block cannot be checked against noise",
            n_names=n, as_of=as_of,
        )
    try:
        win = int(window)
    except (TypeError, ValueError):
        return _unavailable(
            f"window {window!r} is not an integer", n_names=n, as_of=as_of
        )
    # Ground rule 2: the Marchenko-Pastur lower edge has ONE producer.
    from .market_breadth import mp_below_count

    mp = mp_below_count(prev, n, win)
    if mp.get("status") != "ok" or mp.get("mp_lower") is None:
        return _unavailable(
            "the Marchenko-Pastur edge could not be read: "
            f"{mp.get('unavailable') or 'unknown reason'}",
            n_names=n, window=win, mp_edge_check=mp, as_of=as_of,
        )
    lower = float(mp["mp_lower"])
    prev_vals, prev_vecs = np.linalg.eigh(prev)
    curr_vals, curr_vecs = np.linalg.eigh(curr)
    prev_order = np.argsort(prev_vals)[::-1]
    curr_order = np.argsort(curr_vals)[::-1]
    sub_prev = prev_vals[prev_order][1:1 + modes]
    sub_curr = curr_vals[curr_order][1:1 + modes]
    block = np.concatenate([sub_prev, sub_curr])
    inside = [float(v) for v in block if v >= lower]
    mp_edge_check = {
        **mp,
        "subdominant_eigenvalues": [round(float(v), 12) for v in block],
        "outside": len(inside) == 0,
        "basis": (
            f"subdominant block of {modes} eigenvector(s) per window removed the "
            f"market mode; eigenvalues checked against the Marchenko-Pastur lower "
            f"edge {lower:.6g} (n={n}, window={win}); a value at or above the lower "
            "edge may lie inside the i.i.d. noise bulk, where the eigenvector is "
            "noise and its angle carries no rotation"
        ),
    }
    if inside:
        shown = ", ".join(f"{v:.6g}" for v in inside)
        return _unavailable(
            "the subdominant block lies inside the Marchenko-Pastur edge: "
            f"eigenvalue(s) {shown} at or above the lower edge {lower:.6g} over "
            f"{win} observation(s) - inside the bulk those eigenvectors are noise, "
            "so the angle they define is not a rotation",
            n_names=n, window=win, mp_edge_check=mp_edge_check, as_of=as_of,
        )
    prev_basis = prev_vecs[:, prev_order][:, 1:1 + modes]
    curr_basis = curr_vecs[:, curr_order][:, 1:1 + modes]
    cosines = np.linalg.svd(prev_basis.T @ curr_basis, compute_uv=False)
    cosines = np.clip(cosines, -1.0, 1.0)
    angles = [float(math.acos(float(c))) for c in cosines]
    rec = float(np.mean(1.0 - cosines ** 2))
    return {
        "rec": round(rec, 12),
        "angles": [round(a, 12) for a in angles],
        "mp_edge_check": mp_edge_check,
        "status": "ok",
        "unavailable": None,
        "n_names": n,
        "window": win,
        "n_modes": modes,
        "as_of": as_of,
        "basis": (
            f"eigenspace rotation (V5): market mode removed, mean squared sine of "
            f"the {modes} principal angles between the subdominant eigenspaces of "
            f"{n} name(s) x {win} return(s); block outside the Marchenko-Pastur "
            f"lower edge {lower:.6g}; {rec:.6g} of the subdominant block rotated "
            f"(sign-invariant, coincident, direction-blind - a state, not a signal)"
        ),
    }


__all__ = ["eigen_rotation", "SUBSPACE_MODES", "MIN_NAMES"]

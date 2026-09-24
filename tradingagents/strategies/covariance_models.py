"""Covariance modeling (six-pillar / master-catalog PART XVII).

Pure, offline estimators that stabilize the sample covariance the
covariance-based allocators consume (risk-parity / min-variance /
Black-Litterman / max-diversification / risk contribution):

- ``ledoit_wolf_shrink`` - Ledoit-Wolf (2004) linear shrinkage toward a
  target (scaled identity ``mu*I`` or the diagonal of the sample), with the
  shrinkage intensity ``delta = clip(b^2 / d^2, 0, 1)`` where ``b^2`` is the
  average squared Frobenius error of the sample covariance rows and ``d^2``
  the target mismatch (web-verified against the standard implementation).
  Most valuable when ``n_names ~ n_obs`` (sample covariance overfits).
- ``ewma_covariance`` - RiskMetrics EWMA covariance
  ``Sigma_t = lam*Sigma_{t-1} + (1-lam)*r_{t-1} r_{t-1}'`` seeded on the
  sample covariance of the first window.

Every function returns a plain ``dict`` with explicit None fields on
insufficient/degenerate input - never fabricated. NumPy only (already a repo
dependency); all covariance output is ``list[list[float]]`` for the pure
callers.

- ``spectral_null_band`` / ``panel_spectrum`` / ``eigen_projector_distance`` /
  ``spectral_functionals`` - R3 (2607.06373): the movement of a panel's
  correlation spectrum between two rolling windows, each functional reported
  beside the **calibrated first-order null band** it must exceed before a
  structural change is declared. The band is a function of the window length
  and the shrinkage intensity alone; a non-rejection reads "not detectable",
  never "no change".
"""

from __future__ import annotations

import math

__all__ = [
    "ledoit_wolf_shrink",
    "ewma_covariance",
    "SPECTRAL_MIN_OBS",
    "SPECTRAL_NULL_Z",
    "SPECTRAL_DETECTED",
    "SPECTRAL_NOT_DETECTABLE",
    "SPECTRAL_NOT_DETECTABLE_REASON",
    "SPECTRAL_UNAVAILABLE",
    "spectral_null_band",
    "panel_spectrum",
    "eigen_projector_distance",
    "spectral_functionals",
]

_MIN_OBS = 30


def _aligned_matrix(returns_by_name: dict, min_obs: int = _MIN_OBS):
    """Aligned (T x N) centered return matrix over the last common window.

    Mirrors ``portfolio_optimizer._covariance_matrix`` alignment (per-name
    series aligned by index, last ``n`` rows). Returns ``(X_centered, names)``
    or ``(None, [])`` when fewer than two names or a name has too little
    history - never fabricates.
    """
    import numpy as _np

    names = [n for n in (returns_by_name or {}) if returns_by_name.get(n)]
    if len(names) < 2:
        return None, []
    series = []
    for n in names:
        vals = [float(v) for v in returns_by_name[n] if v is not None]
        if len(vals) < min_obs:
            return None, []
        series.append(vals)
    n = min(len(s) for s in series)
    if n < 2:
        return None, []
    mat = _np.array([s[-n:] for s in series], dtype=float)  # N x T
    mat = mat.T  # T x N
    mat = mat - mat.mean(axis=0, keepdims=True)
    return mat, names


def ledoit_wolf_shrink(
    returns_by_name: dict,
    target: str = "scaled_identity",
    min_obs: int = _MIN_OBS,
) -> dict:
    """Ledoit-Wolf (2004) shrunk covariance matrix.

    ``Sigma = (1-delta)*S + delta*F`` with ``S`` the sample covariance
    (MLE convention) and ``F`` the target (``mu*I`` or ``diag(S)``). Returns
    ``{"names", "cov", "shrinkage", "target", "n_obs", "n_names"}``; the
    ``cov`` is a ``list[list[float]]`` keyed by ``names``. ``shrinkage`` in
    [0, 1]; a target that already equals the sample (shrinkage 0) is
    reported, never forced. None-degraded fields are ``None``.
    """
    import numpy as _np

    X, names = _aligned_matrix(returns_by_name, min_obs)
    if X is None:
        return {"names": [], "cov": None, "shrinkage": None, "target": target,
                "n_obs": 0, "n_names": 0}
    t, p = X.shape
    S = (X.T @ X) / t
    if target == "diag":
        F = _np.diag(_np.diag(S))
    else:  # scaled_identity
        mu = float(_np.trace(S)) / p
        F = mu * _np.eye(p)
    outer = _np.einsum("ni,nj->nij", X, X)
    b2 = float(_np.mean(_np.sum((outer - S) ** 2, axis=(1, 2))))
    d2 = float(_np.sum((S - F) ** 2))
    shrinkage = 0.0 if d2 <= 0 else min(max(b2 / d2, 0.0), 1.0)
    Sigma = (1.0 - shrinkage) * S + shrinkage * F
    cov = [[float(x) for x in row] for row in Sigma]
    return {
        "names": names,
        "cov": cov,
        "shrinkage": round(shrinkage, 6),
        "target": target,
        "n_obs": t,
        "n_names": p,
    }


def ewma_covariance(
    returns_by_name: dict,
    lam: float = 0.94,
    min_obs: int = _MIN_OBS,
    seed_window: int = 30,
) -> dict:
    """RiskMetrics EWMA covariance.

    ``Sigma_t = lam*Sigma_{t-1} + (1-lam)*r_{t-1} r_{t-1}'`` seeded with the
    sample covariance of the first ``seed_window`` aligned rows, then
    recursed over every later row. Returns ``{"names", "cov", "lam",
    "n_obs"}``; ``cov`` is a ``list[list[float]]`` (sample-degenerate input
    yields ``None`` cov with the counts still reported).
    """
    import numpy as _np

    X, names = _aligned_matrix(returns_by_name, min_obs)
    if X is None:
        return {"names": [], "cov": None, "lam": float(lam), "n_obs": 0}
    t, p = X.shape
    use_lam = float(lam)
    if not 0.0 < use_lam < 1.0:
        use_lam = 0.94
    seed = min(seed_window, t)
    seed_rows = X[:seed]
    Sigma = (seed_rows.T @ seed_rows) / max(1, seed - 1)
    if not math.isfinite(float(_np.trace(Sigma))):
        return {"names": names, "cov": None, "lam": use_lam, "n_obs": t}
    for i in range(seed, t):
        r = X[i]
        Sigma = use_lam * Sigma + (1.0 - use_lam) * _np.outer(r, r)
    cov = [[float(x) for x in row] for row in Sigma]
    return {"names": names, "cov": cov, "lam": use_lam, "n_obs": t}


# --- R3: the spectral null band (2607.06373) ------------------------------
#
# A spectrum estimated from a finite window moves on its own: shrink an
# estimator and its leading eigenspace wanders. 2607.06373 derives a
# first-order null law for the movement of a shrinkage covariance estimator's
# leading eigenspace - the projector movement ``D = ||P_k - P_k'||_F`` - and for
# the scalar spectral functionals (the absorption ratio, the leading-eigenvalue
# share), so that structural change is declared only when the move exceeds what
# estimation noise produces.
#
# This section is the engine's implementation of that first-order law, as a
# READ and never a second authority: the correlation matrix is
# ``statistical.correlation_matrix``'s and the shrinkage intensity is
# ``ledoit_wolf_shrink``'s (one producer each, neither re-estimated here). What
# this section owns is the movement and the band.
#
# The band is CALIBRATED, not measured: a pure function of the window length
# ``T`` and the shrinkage intensity ``delta``, because the first-order standard
# error of a sample correlation's off-diagonal entries is ``O(1/sqrt(T))`` and a
# shrinkage estimator scales its deviation from the target by ``(1 - delta)``.
# The geometry of the functional - how many channels its movement is spread over
# - is a SEPARATE, reported factor, so the same window length and shrinkage
# intensity carry the same band whatever panel they were read on. The band is
# deliberately data-independent: a band that moved with the realised movement
# could never be falsified by it.

#: The smallest window the spectral read will eigendecompose - the same floor the
#: covariance estimators above use (``_MIN_OBS``). Below it the correlation
#: matrix is not a spectrum and the read refuses with its window, rather than
#: reporting a number from a window it cannot support.
SPECTRAL_MIN_OBS = _MIN_OBS

#: The one-sided normal quantile the first-order null band is cut at. Declared
#: policy, not measured: this engine has no calibration panel to refit the
#: paper's own constants on.
SPECTRAL_NULL_Z = 1.96

#: The three readings a movement leg can carry. A non-rejection is *not
#: detectable* - never "no change" (2607.06373's own framing: non-rejections
#: partly reflect wide null bands).
SPECTRAL_DETECTED = "change detected"
SPECTRAL_NOT_DETECTABLE = "not detectable"
SPECTRAL_UNAVAILABLE = "unavailable"
SPECTRAL_NOT_DETECTABLE_REASON = (
    "not detectable: the move is inside the calibrated first-order null band - "
    "a non-rejection here partly reflects how wide that band is, so it is not "
    "evidence that the structure held"
)


def spectral_null_band(
    n_obs, shrinkage, *, z: float = SPECTRAL_NULL_Z
) -> float | None:
    """R3: the first-order null band for ONE channel of spectral movement.

    The calibrated half of 2607.06373's first-order null law, and it depends on
    **nothing but the window length and the shrinkage intensity**:
    ``z * (1 - shrinkage) / sqrt(n_obs)``. The first-order standard error of a
    sample correlation's off-diagonal entries is ``O(1/sqrt(T))`` under an
    elliptical population, and a shrinkage estimator scales its deviation from
    the target by ``(1 - delta)``, so those two numbers are the whole
    calibration. The *geometry* of a functional - how many channels its movement
    is spread over - is a separate, reported factor
    (:func:`eigen_projector_distance`, :func:`spectral_functionals`), which is
    what lets the same length and intensity carry the same band on any panel.

    The band is deliberately **data-independent**: a band that moved with the
    realised movement could never be falsified by it. ``z`` (``SPECTRAL_NULL_Z``)
    is declared policy.

    Returns ``None`` for degenerate input - a non-positive or non-finite
    ``n_obs``, a ``shrinkage`` outside ``[0, 1]``, a non-positive ``z``, an
    unreadable argument - never a fabricated band.
    """
    try:
        t = float(n_obs)
        delta = float(shrinkage)
        zz = float(z)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(t) and math.isfinite(delta) and math.isfinite(zz)):
        return None
    if t < 1.0 or zz <= 0.0 or not 0.0 <= delta <= 1.0:
        return None
    return zz * (1.0 - delta) / math.sqrt(t)


def _refused_spectrum(panel_n: int, min_n: int, method: str, reason: str) -> dict:
    """The refusal shape of :func:`panel_spectrum` - every value None, with the
    window it was offered and the reason, never a zero."""
    return {
        "names": [],
        "n_names": 0,
        "n_obs": 0,
        "panel_n": int(panel_n),
        "min_n": int(min_n),
        "method": str(method),
        "shrinkage": None,
        "eigenvalues": None,
        "eigenvectors": None,
        "unavailable": reason,
        "basis": f"panel spectrum unavailable: {reason}",
    }


def panel_spectrum(
    window: dict, *, min_n: int = SPECTRAL_MIN_OBS, method: str = "pearson"
) -> dict:
    """R3: ONE rolling panel window -> its correlation spectrum, under shrinkage.

    ``window`` is ``{name: [return, ...]}`` - the shape ``statistical.
    correlation_matrix`` and ``ledoit_wolf_shrink`` already take, and the shape a
    rolling cross-section read builds. This is a per-PANEL read, never
    per-symbol. One **eigendecomposition per window** (``O(N^3)`` naive, trivial
    at ``N`` in the tens): every functional the R3 read reports is derived from
    the spectrum this returns, so a rolling pair costs two decompositions rather
    than one per functional.

    Rule 2 shapes it. The correlation matrix is
    ``statistical.correlation_matrix``'s and the shrinkage intensity is
    ``ledoit_wolf_shrink``'s - neither is re-estimated here - and this function
    owns only the spectrum and its coverage. The ``shrinkage`` it reports is the
    intensity the engine's estimator applies to the same window: it travels
    **beside** the spectrum and is not the read's default band intensity, because
    on every panel this engine's estimator has been asked about it saturates at
    ``1.0``, where a band scaled by ``(1 - shrinkage)`` is zero and
    :func:`_band_refusal` refuses it rather than flagging every move.

    Returns ``{"names", "n_names", "n_obs", "panel_n", "min_n", "method",
    "shrinkage", "eigenvalues", "eigenvectors", "unavailable", "basis"}`` with
    the eigenvalues descending and each eigenvector a list of length
    ``n_names``. The same record with ``unavailable`` set (and every value
    ``None``) is returned when the window carries fewer than ``min_n``
    observations, offers fewer than two names with a common window, leaves a
    correlation pair unresolved, or has no measurable shrinkage intensity - a
    refusal, never a zero and never a substituted spectrum.
    """
    import numpy as _np

    from .statistical import correlation_matrix

    offered = len([name for name, series in (window or {}).items() if series])
    rec = correlation_matrix(
        {name: series for name, series in (window or {}).items() if series},
        method=method,
    )
    if not rec or not rec.get("names"):
        return _refused_spectrum(
            offered,
            min_n,
            method,
            f"{offered} name(s) offered and fewer than two carry a common return "
            "window (a correlation matrix needs two)",
        )
    names = [str(name) for name in rec["names"]]
    n = len(names)
    corr = rec.get("corr") or {}
    mat = _np.eye(n, dtype=float)
    unresolved = 0
    for i in range(n):
        for j in range(i + 1, n):
            r = (corr.get(names[i]) or {}).get(names[j])
            if r is None:
                unresolved += 1
                continue
            mat[i, j] = mat[j, i] = float(r)
    if unresolved:
        return _refused_spectrum(
            offered,
            min_n,
            method,
            f"the correlation matrix leaves {unresolved} pair(s) unresolved, so "
            "it is not a spectrum the read can decompose",
        )
    counts = [
        len([v for v in (window.get(name) or []) if v is not None]) for name in names
    ]
    n_obs = min(counts)
    if n_obs < int(min_n):
        return _refused_spectrum(
            offered,
            min_n,
            method,
            f"the window carries {n_obs} observation(s); {int(min_n)} are needed "
            "for a spectrum",
        )
    shrink = ledoit_wolf_shrink(window, min_obs=int(min_n))
    delta = shrink.get("shrinkage")
    if delta is None:
        return _refused_spectrum(
            offered,
            min_n,
            method,
            "the Ledoit-Wolf shrinkage intensity is unmeasurable on this window",
        )
    n_obs = int(shrink.get("n_obs") or n_obs)
    try:
        vals, vecs = _np.linalg.eigh(mat)
    except Exception:  # noqa: BLE001 - a numerical failure is a refusal, not a crash
        return _refused_spectrum(
            offered,
            min_n,
            method,
            "the correlation matrix could not be eigendecomposed",
        )
    order = [int(i) for i in _np.argsort(vals)[::-1]]
    return {
        "names": names,
        "n_names": n,
        "n_obs": n_obs,
        "panel_n": offered,
        "min_n": int(min_n),
        "method": str(method),
        "shrinkage": round(float(delta), 6),
        "eigenvalues": [round(float(vals[i]), 12) for i in order],
        "eigenvectors": [[float(v) for v in vecs[:, i]] for i in order],
        "unavailable": None,
        "basis": (
            f"panel spectrum: {n} name(s) x {n_obs} return(s); correlation from "
            f"statistical.correlation_matrix ({method}), shrinkage "
            f"{float(delta):.6f} from covariance_models.ledoit_wolf_shrink; one "
            "eigendecomposition, eigenvalues descending"
        ),
    }


def _spectral_pair(prev: dict, curr: dict):
    """Two spectra in ONE name order, or ``(None, None, reason)``.

    Each window's eigendecomposition lives in that window's own name order, so a
    pair whose name sets differ is refused rather than compared in mismatched
    coordinates. A shared set is re-ordered by permuting the eigenvector entries
    - never by a second decomposition.
    """
    if prev.get("unavailable"):
        return None, None, f"previous window: {prev['unavailable']}"
    if curr.get("unavailable"):
        return None, None, f"current window: {curr['unavailable']}"
    prev_names = [str(name) for name in prev["names"]]
    curr_names = [str(name) for name in curr["names"]]
    if sorted(prev_names) != sorted(curr_names):
        return None, None, (
            f"the two windows do not carry the same names "
            f"({len(prev_names)} vs {len(curr_names)})"
        )
    if prev_names != curr_names:
        order = [curr_names.index(name) for name in prev_names]
        curr = {
            **curr,
            "names": prev_names,
            "eigenvectors": [
                [vec[i] for i in order] for vec in curr["eigenvectors"]
            ],
        }
    return prev, curr, None


def _pair_calibration(prev: dict, curr: dict, shrinkage) -> tuple[int, float]:
    """The pair's ``(n_obs, shrinkage)``: the SMALLER window, at the band's intensity.

    The band must be the same whichever window is called "previous", so the pair
    is calibrated on the weaker of the two windows. ``shrinkage`` is the intensity
    the band is calibrated FOR; ``None`` reads as ``0.0`` - the engine's own
    correlation matrix read raw, whose first-order null is the un-shrunk one. The
    intensity the ENGINE's estimator applies to the window is a separate,
    reported number (:func:`_engine_shrinkage`), because it is not the band's
    default - see :func:`panel_spectrum`.
    """
    n_obs = min(int(prev["n_obs"]), int(curr["n_obs"]))
    delta = 0.0 if shrinkage is None else float(shrinkage)
    return n_obs, delta


def _engine_shrinkage(prev: dict, curr: dict) -> float | None:
    """The mean Ledoit-Wolf intensity the engine's estimator applies to the pair.

    Reported beside the band, never folded into it: on every panel this engine's
    estimator has been asked about the intensity saturates at ``1.0`` (its ``b^2``
    is a per-row residual rather than the textbook beta), and a band calibrated at
    ``1.0`` is zero - the refusal path in :func:`_band_refusal`.
    """
    if prev.get("shrinkage") is None or curr.get("shrinkage") is None:
        return None
    return round(0.5 * (float(prev["shrinkage"]) + float(curr["shrinkage"])), 6)


def _band_refusal(n_obs: int, shrinkage: float) -> str:
    """Why a band of zero is a refusal rather than a licence to flag every move."""
    if n_obs < 1:
        return f"the null band is uncalibrated: {n_obs} observation(s)"
    return (
        f"the calibrated band is zero at shrinkage={float(shrinkage):.6g} over "
        f"{int(n_obs)} observation(s): the estimator's sampling noise is fully "
        "shrunk away, so no movement can be separated from it - the read refuses "
        "rather than flagging every move"
    )


def _unavailable_leg(
    functional: str,
    reason: str,
    *,
    k: int,
    n_names: int,
    n_obs: int,
    min_n: int,
    shrinkage=None,
) -> dict:
    """One movement leg the pair could not measure - every value None, the window
    still reported, and ``exceeds`` ``None`` rather than ``False``."""
    window = {"n_obs": int(n_obs), "n_names": int(n_names), "min_n": int(min_n)}
    return {
        "functional": functional,
        "value": None,
        "prev": None,
        "curr": None,
        "move": None,
        "normalized": None,
        "band": None,
        "geometry": None,
        "threshold": None,
        "exceeds": None,
        "reading": SPECTRAL_UNAVAILABLE,
        "k": int(k),
        "n_names": int(n_names),
        "n_obs": int(n_obs),
        "shrinkage": None if shrinkage is None else round(float(shrinkage), 6),
        "min_n": int(min_n),
        "window": window,
        "unavailable": reason,
        "basis": f"{functional} unavailable: {reason}",
    }


def _movement_leg(
    functional: str,
    *,
    value: float,
    move: float,
    geometry: float,
    band: float,
    k: int,
    n_names: int,
    n_obs: int,
    min_n: int,
    shrinkage: float,
    prev=None,
    curr=None,
) -> dict:
    """One measured movement leg: the move, its band, and the flag.

    ``normalized`` is the move per channel of the subspace it is spread over, so
    the (length, intensity)-calibrated ``band`` is comparable across panels;
    ``threshold`` is the same band converted back into the functional's own
    units. ``exceeds`` is the leg's flag - the movement is only a structural
    change when it clears the band.
    """
    normalized = abs(float(move)) / float(geometry)
    exceeds = bool(normalized > float(band))
    reading = (
        SPECTRAL_DETECTED
        if exceeds
        else SPECTRAL_NOT_DETECTABLE_REASON
    )
    return {
        "functional": functional,
        "value": float(value),
        "prev": None if prev is None else float(prev),
        "curr": None if curr is None else float(curr),
        "move": float(move),
        "normalized": normalized,
        "band": float(band),
        "geometry": float(geometry),
        "threshold": float(band) * float(geometry),
        "exceeds": exceeds,
        "reading": reading,
        "k": int(k),
        "n_names": int(n_names),
        "n_obs": int(n_obs),
        "shrinkage": round(float(shrinkage), 6),
        "min_n": int(min_n),
        "window": {"n_obs": int(n_obs), "n_names": int(n_names), "min_n": int(min_n)},
        "unavailable": None,
        "basis": (
            f"{functional}: move {float(move):+.6g} ({normalized:.6g} per channel) "
            f"against a calibrated first-order null band of {float(band):.6g} "
            f"(z={SPECTRAL_NULL_Z}, {int(n_obs)} observation(s), shrinkage "
            f"{float(shrinkage):.6f}); threshold {float(band) * float(geometry):.6g} "
            f"in the functional's own units (geometry {float(geometry):.6g}); "
            f"{reading}"
        ),
    }


def eigen_projector_distance(
    prev_window: dict | None = None,
    curr_window: dict | None = None,
    *,
    k: int = 1,
    shrinkage: float = 0.0,
    min_n: int = SPECTRAL_MIN_OBS,
    prev_spectrum: dict | None = None,
    curr_spectrum: dict | None = None,
) -> dict:
    """R3: ``D = ||P_k(prev) - P_k(curr)||_F`` against its first-order null band.

    ``D`` is the projector movement of the dominant ``k``-dimensional eigenspace
    of the panel's correlation matrix between two rolling windows - the quantity
    2607.06373 monitors. ``D`` is bounded by ``sqrt(2*k)`` (two orthogonal
    ``k``-subspaces), so the leg reports the move both raw and **normalized per
    channel** (``D / sqrt(2*k)``); the calibrated band compares against the
    normalized move, and ``threshold`` is the band in ``D``'s own units.

    ``prev_window``/``curr_window`` are ``{name: [return, ...]}``. Pass
    ``prev_spectrum``/``curr_spectrum`` (from :func:`panel_spectrum`) to reuse
    decompositions a caller has already taken - the gate's per-panel read does
    exactly that, so a rolling pair costs ONE eigendecomposition per window.

    ``shrinkage`` is the intensity the band is calibrated FOR: ``0.0`` (the
    default) is the engine's correlation matrix read raw, whose null is the
    un-shrunk first-order law, and a caller monitoring a shrunk estimator passes
    its intensity. A **band of zero is refused**, never treated as a licence to
    flag every move - see :func:`_band_refusal`.

    Returns the leg record (``value``, ``move``, ``normalized``, ``band``,
    ``geometry``, ``threshold``, ``exceeds``, ``reading``, the window, the
    shrinkage and a basis). ``exceeds`` is the leg's flag and is ``None`` - never
    ``False`` - when the windows could not be read: a thin window, a name set
    that changed between the two, or a band that is zero/uncalibrated. The
    movement is only a structural change when it clears the band, and a leg that
    does not is ``"not detectable"``, never "no change".
    """
    import numpy as _np

    prev = (
        prev_spectrum
        if prev_spectrum is not None
        else panel_spectrum(prev_window if prev_window is not None else {}, min_n=min_n)
    )
    curr = (
        curr_spectrum
        if curr_spectrum is not None
        else panel_spectrum(curr_window if curr_window is not None else {}, min_n=min_n)
    )
    functional = "projector_distance"
    p, c, reason = _spectral_pair(prev, curr)
    n_names = int(prev.get("n_names") or 0)
    n_obs = min(int(prev.get("n_obs") or 0), int(curr.get("n_obs") or 0))
    if reason is not None:
        return _unavailable_leg(
            functional, reason, k=max(1, int(k)), n_names=n_names, n_obs=n_obs,
            min_n=min_n,
        )
    kk = max(1, min(int(k), int(p["n_names"])))
    n_obs, delta = _pair_calibration(p, c, shrinkage)
    band = spectral_null_band(n_obs, delta)
    if band is None or band <= 0.0:
        return _unavailable_leg(
            functional, _band_refusal(n_obs, delta), k=kk, n_names=n_names,
            n_obs=n_obs, min_n=min_n, shrinkage=delta,
        )
    p_basis = _np.asarray(p["eigenvectors"][:kk], dtype=float).T  # N x k
    q_basis = _np.asarray(c["eigenvectors"][:kk], dtype=float).T
    distance = float(_np.linalg.norm(p_basis @ p_basis.T - q_basis @ q_basis.T, "fro"))
    return _movement_leg(
        functional,
        value=distance,
        move=distance,
        geometry=math.sqrt(2.0 * kk),
        band=band,
        k=kk,
        n_names=n_names,
        n_obs=n_obs,
        min_n=min_n,
        shrinkage=delta,
    )


def spectral_functionals(
    prev_window: dict | None = None,
    curr_window: dict | None = None,
    *,
    absorption_k: int | None = None,
    shrinkage: float = 0.0,
    min_n: int = SPECTRAL_MIN_OBS,
    prev_spectrum: dict | None = None,
    curr_spectrum: dict | None = None,
) -> dict:
    """R3: the scalar spectral functionals of two rolling windows, each with a band.

    Both scalars are shares of the correlation matrix's total eigenvalue mass
    (its trace):

    - ``absorption_ratio`` - the share held by the top ``absorption_k``
      eigenmodes, the canonical top-fifth read (``round(n/5)``, at least one
      mode): how concentrated the cross-section's variance is.
    - ``leading_share`` - the share held by the first eigenmode alone.

    Each is reported with its move, its own first-order null band and its flag.
    The geometry factor is the number of channels the top-``K`` mass can be
    displaced across (``K`` leading against ``N - K`` remaining, scaled by the
    trace ``N``), so the scalar bands and the projector band share ONE
    calibration: the same window length and shrinkage intensity.

    ``prev_window``/``curr_window`` are ``{name: [return, ...]}``; pass
    ``prev_spectrum``/``curr_spectrum`` to reuse decompositions already taken.
    ``shrinkage`` is the intensity the band is calibrated FOR (``0.0`` - the
    default - is the correlation matrix read raw); a band of zero is refused,
    never a licence to flag every move.

    Returns ``{"absorption_ratio", "leading_share", "n_names", "n_obs",
    "min_n", "shrinkage", "band_calibration", "window", "unavailable",
    "basis"}``. Both legs are ``exceeds: None`` and ``unavailable`` when the
    windows could not be read or the band is zero; a leg whose move is inside its
    band reads ``"not detectable"``, never "no change".
    """
    prev = (
        prev_spectrum
        if prev_spectrum is not None
        else panel_spectrum(prev_window if prev_window is not None else {}, min_n=min_n)
    )
    curr = (
        curr_spectrum
        if curr_spectrum is not None
        else panel_spectrum(curr_window if curr_window is not None else {}, min_n=min_n)
    )
    p, c, reason = _spectral_pair(prev, curr)
    n_names = int(prev.get("n_names") or 0)
    n_obs = min(int(prev.get("n_obs") or 0), int(curr.get("n_obs") or 0))
    names = ("absorption_ratio", "leading_share")
    if reason is not None:
        legs = {
            name: _unavailable_leg(
                name, reason, k=1, n_names=n_names, n_obs=n_obs, min_n=min_n
            )
            for name in names
        }
        return {
            **legs,
            "n_names": n_names,
            "n_obs": n_obs,
            "min_n": int(min_n),
            "shrinkage": None,
            "band_calibration": None,
            "window": {"n_obs": n_obs, "n_names": n_names, "min_n": int(min_n)},
            "unavailable": reason,
            "basis": f"spectral functionals unavailable: {reason}",
        }
    n_obs, delta = _pair_calibration(p, c, shrinkage)
    band = spectral_null_band(n_obs, delta)
    if band is None or band <= 0.0:
        reason = _band_refusal(n_obs, delta)
        legs = {
            name: _unavailable_leg(
                name, reason, k=1, n_names=n_names, n_obs=n_obs, min_n=min_n,
                shrinkage=delta,
            )
            for name in names
        }
        return {
            **legs,
            "n_names": n_names,
            "n_obs": n_obs,
            "min_n": int(min_n),
            "shrinkage": round(float(delta), 6),
            "band_calibration": None,
            "window": {"n_obs": n_obs, "n_names": n_names, "min_n": int(min_n)},
            "unavailable": reason,
            "basis": f"spectral functionals unavailable: {reason}",
        }
    k_absorption = (
        max(1, min(int(round(n_names / 5.0)), n_names))
        if absorption_k is None
        else max(1, min(int(absorption_k), n_names))
    )
    prev_mass = sum(float(v) for v in p["eigenvalues"])
    curr_mass = sum(float(v) for v in c["eigenvalues"])
    legs: dict = {}
    for name, k_modes in (("absorption_ratio", k_absorption), ("leading_share", 1)):
        geometry = math.sqrt(2.0 * k_modes * (n_names - k_modes)) / float(n_names)
        if geometry <= 0.0 or prev_mass <= 0.0 or curr_mass <= 0.0:
            legs[name] = _unavailable_leg(
                name,
                f"the functional's geometry factor is degenerate at {n_names} "
                "name(s)",
                k=k_modes,
                n_names=n_names,
                n_obs=n_obs,
                min_n=min_n,
                shrinkage=delta,
            )
            continue
        prev_value = sum(float(v) for v in p["eigenvalues"][:k_modes]) / prev_mass
        curr_value = sum(float(v) for v in c["eigenvalues"][:k_modes]) / curr_mass
        legs[name] = _movement_leg(
            name,
            value=curr_value,
            prev=prev_value,
            curr=curr_value,
            move=curr_value - prev_value,
            geometry=geometry,
            band=band,
            k=k_modes,
            n_names=n_names,
            n_obs=n_obs,
            min_n=min_n,
            shrinkage=delta,
        )
    return {
        **legs,
        "n_names": n_names,
        "n_obs": n_obs,
        "min_n": int(min_n),
        "shrinkage": round(float(delta), 6),
        "band_calibration": float(band),
        "window": {"n_obs": n_obs, "n_names": n_names, "min_n": int(min_n)},
        "unavailable": None,
        "basis": (
            f"spectral functionals over {n_names} name(s) x {n_obs} return(s): "
            f"absorption ratio over the top {k_absorption} mode(s), leading share "
            f"over the top 1; band {float(band):.6g} (z={SPECTRAL_NULL_Z}, "
            f"shrinkage {float(delta):.6f}) depends on the window length and the "
            "shrinkage intensity alone"
        ),
    }

"""Triadic stress over the correlation network, and *where* it is centred (R7).

The engine already reads cross-sectional concentration - the largest-cluster
share, the absorption ratio, breadth - and each of those says only that
concentration *moved*. None of them says **which names** carry it. This module
adds that half: a coincident stress index over the correlation network, plus a
per-node attribution that names the epicentre.

``triadic_stress(returns_by_name) ->``

* ``tsi`` - the Triadic Stress Index ``(C * D / M) * Coex`` over the network the
  engine's own ``statistical.correlation_matrix`` already produces (rule 2: the
  correlation matrix is read, never recomputed here):

  - ``C`` - the weighted clustering, the **normalized** ``Tr(A^3)``
    (``Tr(A^3) / (n(n-1)(n-2))``, so a unit-weight clique reads 1);
  - ``D`` - the **weighted** edge density (``sum A_ij / (n(n-1))``); a binary
    density over the ``|rho|`` network is 1 by construction, so the weighted
    reading is the informative one;
  - ``M`` - the **inverse spectral gap** of the graph Laplacian, ``1 / lambda_2``
    (the second-smallest eigenvalue of the normalized Laplacian
    ``I - D^-1/2 A D^-1/2``), the paper's modularity proxy;
  - ``Coex`` - the variance of the (weighted) degree sequence.

  ``A`` is the **absolute** correlation network with a zero diagonal
  (``A_ij = |rho_ij|``), the paper's own construction: two names that move
  together in either direction are one edge.
* ``epicentre`` - the ordered per-node attribution ``diag(A^3)`` (the weighted
  triangle participation of each name). ``diag(A^3)_i`` is
  ``sum_jk A_ij A_jk A_ki``, i.e. how much of the network's triadic closure runs
  through name ``i``; the epicentre is the names whose attribution exceeds the
  cross-sectional mean, ordered **descending**, so the read names the block
  instead of only reporting that the index rose. ``attribution`` carries every
  name's value beside it.
* ``coincident`` - **always** ``True``. The paper states plainly that this is a
  coincident index and not a forecast: it says where stress is, never that any
  is coming. Ground rule 4 of the regime theme (R8) binds that label, so it
  travels on every returned read, including the ``unavailable`` ones.
* ``window`` - the coverage window the panel read was taken over
  (``strategies/coverage_window``, H10 - read, not re-derived), with the count
  of aligned bars, the names whose histories are padded, and the alignment.

Missing data is ``unavailable``, never zero, and never a substituted default:
the read refuses below ``MIN_NAMES`` (8) names - the index **saturates on a
small cross-section**, and a four-symbol book IS thin - below ``MIN_OBS``
aligned bars, when the correlation matrix cannot be formed, and when the
network is (near-)disconnected (``lambda_2 ~ 0`` leaves ``M`` without a finite
inverse, so the index would be an artefact of a floor rather than a measurement).

Behind ``enable_triadic_stress`` (default off, env
``TRADINGAGENTS_ENABLE_TRIADIC_STRESS``): with the gate off the read reports
``unavailable`` with the reason, so a gate-off run is byte-identical to the run
before this module existed. The consumer is ``strategies/risk_score`` (the
correlation category's cross-sectional read), where the index is **printed
beside** the score and never scored by it - it is a coincident network read,
never a second breadth authority (rule 2).

Caveat (the paper's own): the index is coincident, not leading; it only
marginally exceeds the Absorption Ratio; and it needs a cross-section, so it
saturates when the cross-section is small.

Pure, deterministic, O(n^3) - trivial at this engine's book size. No network,
no state.
"""

from __future__ import annotations

import math

import numpy as np

from .coverage_window import coverage_window
from .statistical import correlation_matrix

#: The cross-section floor. Below this many names the index is ``unavailable``:
#: the paper notes the read saturates on a small network, and a four-symbol book
#: is thin. Never a saturated index in place of a refusal.
MIN_NAMES = 8

#: The aligned-observation floor: a correlation network estimated over fewer
#: bars than this is an artefact of the window, not a network (ground rule 4).
MIN_OBS = 60

#: Below this second eigenvalue of the normalized Laplacian the network is
#: (near-)disconnected and ``M`` - the *inverse* spectral gap - has no finite
#: value. The read refuses rather than reporting the reciprocal of a floor.
SPECTRAL_GAP_FLOOR = 1e-9

#: The label that must travel on every returned read (R8): the index is
#: coincident, and it never claims to see a shift coming.
COINCIDENT = True

#: What the record names itself.
LABEL = "triadic stress index (coincident, not leading)"

#: The declared policy for the epicentre cut: a name is part of the epicentre
#: when its triadic attribution exceeds the cross-sectional mean attribution, so
#: the list names a *subset* (the names carrying more than their share) rather
#: than reprinting the whole book. ``attribution`` carries every value, so the
#: cut is visible rather than implied.
EPICENTRE_CUT = "above the cross-sectional mean diag(A^3) attribution"


def _gate_on() -> bool:
    """Is ``enable_triadic_stress`` on? (default off).

    The key is read by its literal name so the gate registry's read-site scan
    finds it. A config read must never break the read it guards: an unreadable
    config leaves the gate off.
    """
    try:
        from tradingagents.dataflows.config import get_config

        cfg = get_config() or {}
    except Exception:  # noqa: BLE001 - a config read must never break the read
        cfg = {}
    return bool(cfg.get("enable_triadic_stress", False))


def _unavailable(reason: str, *, n_names: int = 0, n_bars: int = 0,
                 window: dict | None = None) -> dict:
    """The refusal record: no number, the reason, and the ``coincident`` label."""
    return {
        "label": LABEL,
        "tsi": None,
        "epicentre": [],
        "attribution": {},
        "coincident": COINCIDENT,
        "status": "unavailable",
        "unavailable": reason,
        "n_names": n_names,
        "n_bars": n_bars,
        "window": window,
        "components": None,
        "epicentre_cut": EPICENTRE_CUT,
        "basis": reason,
    }


def _panel_window(returns_by_name: dict, names: list[str]) -> dict:
    """The panel's coverage window, read off the frames (H10), never assumed."""
    windows = {name: coverage_window(returns_by_name[name]) for name in names}
    alignments = {w["alignment"] for w in windows.values()}
    return {
        "n_names": len(names),
        "n_bars": min((w["n_bars"] for w in windows.values()), default=0),
        "padded_names": sorted(
            name for name, w in windows.items() if w["padded_days"] > 0
        ),
        "alignment": alignments.pop() if len(alignments) == 1 else "mixed",
        "names": list(names),
    }


def _adjacency(names: list[str], corr: dict) -> np.ndarray:
    """``A_ij = |rho_ij|`` over the names, diagonal zero (the paper's network)."""
    n = len(names)
    a = np.zeros((n, n), dtype=float)
    for i, ni in enumerate(names):
        for j in range(i + 1, n):
            r = (corr.get(ni) or {}).get(names[j])
            if r is None:
                r = (corr.get(names[j]) or {}).get(ni)
            if r is None:
                continue
            try:
                r = float(r)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(r):
                continue
            a[i, j] = a[j, i] = abs(r)
    return a


def _spectral_gap(a: np.ndarray) -> float:
    """``lambda_2`` of the normalized Laplacian ``I - D^-1/2 A D^-1/2``.

    ``lambda_1`` is 0 for any graph; ``lambda_2`` is 0 exactly when the network
    is disconnected. The zero-degree convention (an isolated name keeps
    ``L_ii = 1`` and contributes no edges) is the standard one, so a name with no
    edge at all cannot manufacture a gap.
    """
    deg = a.sum(axis=1)
    inv_sqrt = np.zeros_like(deg)
    positive = deg > 0
    inv_sqrt[positive] = 1.0 / np.sqrt(deg[positive])
    lap = np.eye(a.shape[0]) - (inv_sqrt[:, None] * a * inv_sqrt[None, :])
    evals = np.linalg.eigvalsh(lap)
    return float(evals[1]) if evals.size >= 2 else 0.0


def triadic_stress(returns_by_name: dict) -> dict:
    """The Triadic Stress Index and its epicentre over one cross-section (R7).

    ``returns_by_name`` is ``{name: return series}`` - the same dict
    ``statistical.correlation_matrix`` reads. The correlation matrix, the
    coverage window and the network are all **read** from the engine's existing
    producers; nothing here recomputes a correlation or a data-quality
    threshold (rule 2).

    Returns ``{'label', 'tsi', 'epicentre', 'attribution', 'coincident',
    'status', 'unavailable', 'n_names', 'n_bars', 'window', 'components',
    'epicentre_cut', 'basis'}``. ``epicentre`` is ordered by descending
    ``diag(A^3)`` attribution (ties by name), and ``coincident`` is ``True`` on
    every returned read. Any refusal - gate off, fewer than ``MIN_NAMES`` names,
    fewer than ``MIN_OBS`` aligned bars, no usable correlation matrix, or a
    (near-)disconnected network - returns ``tsi`` None with ``unavailable``
    carrying the reason: never 0, never a saturated index.
    """
    if not _gate_on():
        return _unavailable(
            "enable_triadic_stress is off (default): the read is not produced "
            "on a gate-off run"
        )

    names = [n for n in (returns_by_name or {}) if returns_by_name.get(n)]
    if len(names) < MIN_NAMES:
        return _unavailable(
            f"cross-section of {len(names)} name(s) is below the {MIN_NAMES}-name "
            "floor: the triadic index saturates on a small network, so a "
            "cross-section this thin is refused rather than reported",
            n_names=len(names),
        )

    window = _panel_window(returns_by_name, names)
    n_bars = window["n_bars"]
    if n_bars < MIN_OBS:
        return _unavailable(
            f"only {n_bars} aligned bar(s) over {len(names)} name(s), below the "
            f"{MIN_OBS}-bar floor: a correlation network over a window this thin "
            "is an artefact of the window, not a network",
            n_names=len(names),
            n_bars=n_bars,
            window=window,
        )

    net = correlation_matrix(returns_by_name)
    if not net or len(net.get("names") or []) < MIN_NAMES:
        return _unavailable(
            "correlation_matrix produced no network over the cross-section "
            "(fewer than 2 aligned names, or no pair with an aligned window)",
            n_names=len(names),
            n_bars=n_bars,
            window=window,
        )

    used = list(net["names"])
    a = _adjacency(used, net["corr"])
    n = len(used)

    gap = _spectral_gap(a)
    if not math.isfinite(gap) or gap <= SPECTRAL_GAP_FLOOR:
        return _unavailable(
            f"the correlation network is (near-)disconnected (lambda_2 = {gap:g}): "
            "M is the INVERSE spectral gap and has no finite value here, so the "
            "index would be the reciprocal of a floor, not a measurement",
            n_names=len(used),
            n_bars=n_bars,
            window=window,
        )

    tri = a @ a @ a
    attribution = np.diag(tri)
    tr_a3 = float(attribution.sum())
    c = tr_a3 / (n * (n - 1) * (n - 2))
    d = float(a.sum() / (n * (n - 1)))
    coex = float(np.var(a.sum(axis=1)))
    m = 1.0 / gap
    tsi = (c * d / m) * coex

    order = sorted(range(n), key=lambda i: (-float(attribution[i]), used[i]))
    mean_attr = float(attribution.mean())
    epicentre = [used[i] for i in order if float(attribution[i]) > mean_attr]

    basis = (
        f"TSI = (C*D/M)*Coex = ({c:.6g}*{d:.6g}/{m:.6g})*{coex:.6g} = {tsi:.6g} "
        f"over {n} name(s) and {n_bars} aligned bar(s); "
        f"C = normalized Tr(A^3) = {tr_a3:.6g}/{n * (n - 1) * (n - 2)}; "
        f"D = weighted |rho| density; M = 1/lambda_2 = 1/{gap:.6g}; "
        f"Coex = Var(degree); "
        f"epicentre = {EPICENTRE_CUT} ({len(epicentre)} of {n} name(s)); "
        "COINCIDENT, not leading - it says where stress is, never that any is "
        "coming (regime rule R8)"
    )
    return {
        "label": LABEL,
        "tsi": tsi,
        "epicentre": epicentre,
        "attribution": {used[i]: float(attribution[i]) for i in range(n)},
        "coincident": COINCIDENT,
        "status": "ok",
        "unavailable": None,
        "n_names": n,
        "n_bars": n_bars,
        "window": window,
        "components": {
            "C": c,
            "D": d,
            "M": m,
            "Coex": coex,
            "spectral_gap": gap,
            "tr_a3": tr_a3,
        },
        "epicentre_cut": EPICENTRE_CUT,
        "basis": basis,
    }


__all__ = [
    "MIN_NAMES",
    "MIN_OBS",
    "SPECTRAL_GAP_FLOOR",
    "COINCIDENT",
    "LABEL",
    "EPICENTRE_CUT",
    "triadic_stress",
]

"""H9 - report influence attribution and factor novelty (paper-survey honesty gates).

Two **descriptive** reads over material a completed run already produced, both
exposed through one gate that ships **off**:

* ``attribution(reports, thesis)`` - a **non-negative least squares** projection
  of the thesis vector onto the report vectors, so the engine can say which
  report drove a decision instead of guessing. The weights are non-negative and
  normalized to sum 1; the residual and the aligned row count travel with them.
  2604.17327's construction.
* ``novelty(candidates, reference)`` / ``admit_factor(...)`` - the factor
  novelty screen ``novelty = mean_f max_{z in Z} |corr(s_f, z)|`` against a
  **held-out** reference set ``Z`` (2609.00731), so a "new" factor that is a
  relabelling of a zoo member is **flagged rather than admitted as new**.
  Productivity, performance and novelty are required **jointly**; a factor with
  any of the three missing is not admitted.

**No look-ahead.** Both reads consume vectors/series supplied by the caller and
never refetch, shift or forward-fill: alignment keeps only positions where every
input is finite, and a screen that cannot be measured is ``unavailable`` with a
reason - never a substituted 0 or a fabricated weight.

**The embedding stage is refused, not approximated.** 2604.17327 embeds the
report *texts* with a text model before the NNLS solve. This repo has **no
text-embedding provider** (grep ``embed`` across ``tradingagents/``: nothing),
so ``embed_reports`` returns a named ``no_embedding_backend`` reason rather than
substituting a hashing/bag-of-words pseudo-embedding. A caller that *has* an
embedder passes it in; a caller that has vectors calls ``attribution`` directly.
The spec's rolling re-execution protocol is likewise out of scope, as its card
says.

**The gate.** ``enable_report_influence`` (env
``TRADINGAGENTS_ENABLE_REPORT_INFLUENCE``), default off.

**Rejected alternative - extending ``enable_report_attribution``.** That key
already ships for the DSA-2 advisory layer (``reporting.write_report_tree``'s
computed driver-attribution + disclosure block, `docs/gate_registry.md` §7f).
Reusing it was considered and rejected: the DSA-2 read is a *sum-100
normalization of four already-computed engine reads*, while this read is an
*NNLS projection of a thesis vector onto report vectors* - the same decision
being described, by a different construction, over different inputs (DSA-2
normalizes scalars, H9 solves a vector projection). Registering a new gate under
an existing key would also violate the six-point registration (the key must be
absent), so H9 takes a **new key** and the overlap is disclosed here rather than
silently merged. The plan card records the same decision.

**Reference-set machinery.** The reference set ``Z`` is supplied by the caller
and must be **held out from generation** (never the series the candidate was fit
on). For a run's peer universe the names are resolved through the existing
single implementation, ``peer_universe.resolved_peer_names`` - ``reference_names``
here is a thin disclosure wrapper over it, not a second resolver.

Pure and deterministic; advisory only (never gates, never changes a rating,
size, score or verdict).
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "GATE_NAME",
    "NOVELTY_MAX_CORR",
    "REPORT_KEYS",
    "admit_factor",
    "attribution",
    "embed_reports",
    "gate_on",
    "novelty",
    "reference_names",
]

#: The config key (and env ``TRADINGAGENTS_ENABLE_REPORT_INFLUENCE``) this gate reads.
GATE_NAME = "enable_report_influence"

#: The four analyst report vectors the influence read projects onto.
REPORT_KEYS: tuple[str, ...] = ("market", "sentiment", "news", "fundamentals")

#: A candidate whose maximum absolute correlation against the reference set
#: reaches this is a relabelling, not a discovery (2609.00731's screen).
NOVELTY_MAX_CORR = 0.90

#: NNLS needs at least as many aligned rows as report columns, and a usable
#: screening correlation needs at least a few aligned observations.
_MIN_ROWS = 4
_MIN_CORR_ROWS = 3


def _cfg_or_ambient(cfg: dict | None) -> dict:
    """The config to read the gate from: the caller's, else the ambient one."""
    if cfg is not None:
        return dict(cfg)
    try:
        from tradingagents.dataflows.config import get_config

        return dict(get_config() or {})
    except Exception:  # noqa: BLE001 - a missing ambient config is gate-off, not a crash
        return {}


def gate_on(cfg: dict | None = None) -> bool:
    """Is the report-influence read enabled? Default off (``enable_report_influence``)."""
    return bool(_cfg_or_ambient(cfg).get("enable_report_influence", False))


def _finite_vector(values) -> np.ndarray | None:
    """A 1-D finite-candidate float array, or ``None`` when it is not one."""
    if values is None:
        return None
    try:
        arr = np.asarray(list(values), dtype=float)
    except (TypeError, ValueError):
        return None
    if arr.ndim != 1 or arr.size == 0:
        return None
    return arr


def _series_map(series) -> dict[str, np.ndarray]:
    """``{name: float array}`` from a mapping, dropping entries that are not series."""
    if not isinstance(series, dict):
        return {}
    out: dict[str, np.ndarray] = {}
    for name, values in series.items():
        arr = _finite_vector(values)
        if arr is not None:
            out[str(name)] = arr
    return out


def _report_columns(reports) -> tuple[list[str], list[np.ndarray]]:
    """``(names, columns)`` from a ``{name: vector}`` map or a list of vectors.

    A mapping keeps its names; a sequence is named positionally. Columns of
    unequal length or with a non-numeric entry are refused (an empty column
    list), never truncated - a ragged projection is not a projection.
    """
    if isinstance(reports, dict):
        names = [str(k) for k in reports]
        cols = [_finite_vector(reports[k]) for k in reports]
    elif isinstance(reports, (list, tuple)):
        names = [f"report_{i + 1}" for i in range(len(reports))]
        cols = [_finite_vector(v) for v in reports]
    else:
        return [], []
    if not cols or any(c is None for c in cols):
        return names, []
    lengths = {c.shape[0] for c in cols}
    if len(lengths) != 1:
        return names, []
    return names, cols


def _unavailable(reason: str, names: list[str]) -> dict:
    """The refusal shape: weights ``None``, never a fabricated vector."""
    return {
        "weights": None,
        "residual_norm": None,
        "thesis_norm": None,
        "fit": None,
        "n_reports": len(names),
        "n_rows": 0,
        "basis": f"report influence unavailable: {reason}",
        "unavailable": reason,
    }


def attribution(reports, thesis, *, cfg: dict | None = None) -> dict:
    """NNLS influence weights of the thesis vector over the report vectors (H9).

    ``reports`` is a ``{name: vector}`` mapping (or a list of vectors); the four
    analyst reports are named by ``REPORT_KEYS`` when the caller uses those keys.
    ``thesis`` is the vector to explain. Both must be 1-D and equal-length; rows
    where either is non-finite are dropped (never filled), and a projection with
    too few aligned rows is refused rather than solved.

    Returns ``{"weights": {name: w}, "residual_norm", "thesis_norm", "fit",
    "n_reports", "n_rows", "basis", "unavailable"}``. ``weights`` are
    non-negative (NNLS) and normalized to **sum 1**; a thesis orthogonal to every
    report vector has no attribution and is refused with that reason.
    """
    names, cols = _report_columns(reports)
    y = _finite_vector(thesis)
    if not cols:
        return _unavailable(
            "the report vectors are missing, non-numeric or of unequal length", names
        )
    if y is None or y.shape[0] != cols[0].shape[0]:
        return _unavailable(
            "the thesis vector is missing or not the same length as the report vectors",
            names,
        )

    mask = np.isfinite(y)
    for col in cols:
        mask &= np.isfinite(col)
    rows = int(mask.sum())
    n_reports = len(cols)
    if rows < max(n_reports, _MIN_ROWS):
        return _unavailable(
            f"only {rows} aligned finite rows for {n_reports} report vectors", names
        )

    from scipy.optimize import nnls

    design = np.column_stack([col[mask] for col in cols])
    target = y[mask]
    weights, residual = nnls(design, target)
    total = float(weights.sum())
    if total <= 0.0:
        return _unavailable(
            "the thesis is orthogonal to every report vector (all weights zero)", names
        )

    normalized = weights / total
    thesis_norm = float(np.linalg.norm(target))
    fit = None if thesis_norm <= 0.0 else 1.0 - float(residual) / thesis_norm
    return {
        "weights": {
            name: float(w) for name, w in zip(names, normalized, strict=True)
        },
        "residual_norm": float(residual),
        "thesis_norm": thesis_norm,
        "fit": fit,
        "n_reports": n_reports,
        "n_rows": rows,
        "basis": (
            f"non-negative least squares over {n_reports} report vectors, "
            f"{rows} aligned finite rows; weights normalized to sum 1"
        ),
        "unavailable": None,
    }


def _pearson_abs(a: np.ndarray | None, b: np.ndarray | None) -> float | None:
    """``|corr(a, b)|`` over their aligned finite positions, or ``None``.

    ``None`` means the pair cannot be measured (too few common rows, or a
    constant series) - never a substituted 0.0, which would read as "unrelated".
    """
    if a is None or b is None or a.shape[0] != b.shape[0]:
        return None
    mask = np.isfinite(a) & np.isfinite(b)
    if int(mask.sum()) < _MIN_CORR_ROWS:
        return None
    x, z = a[mask], b[mask]
    if float(x.std()) == 0.0 or float(z.std()) == 0.0:
        return None
    corr = float(np.corrcoef(x, z)[0, 1])
    if not np.isfinite(corr):
        return None
    return abs(corr)


def novelty(candidates: dict, reference: dict, *, cfg: dict | None = None) -> dict:
    """``mean_f max_{z in Z} |corr(s_f, z)|`` for the candidate factors (H9).

    ``candidates`` is ``{factor_name: series}``; ``reference`` is the **held-out**
    reference set ``Z`` as ``{name: series}``. For each candidate the screen takes
    the maximum absolute correlation over ``Z``; ``novelty`` is the mean of those
    maxima over the candidates. A candidate that cannot be measured against any
    reference series makes the whole screen **unavailable** with that factor
    named (missing is never 0 - see `docs/paper_survey_26` ground rule 4).
    """
    cand = _series_map(candidates)
    ref = _series_map(reference)
    base = {
        "novelty": None,
        "per_factor": {},
        "n_reference": len(ref),
        "basis": "factor novelty unavailable",
        "unavailable": None,
    }
    if not cand:
        base["unavailable"] = "no candidate factor series supplied"
        return base
    if not ref:
        base["unavailable"] = (
            "no held-out reference set supplied: the novelty screen needs Z"
        )
        return base

    per_factor: dict[str, dict] = {}
    for factor, series in cand.items():
        best = 0.0
        matched: str | None = None
        for name, ref_series in ref.items():
            score = _pearson_abs(series, ref_series)
            if score is not None and (matched is None or score > best):
                best, matched = score, name
        if matched is None:
            base["per_factor"] = per_factor
            base["unavailable"] = (
                f"factor {factor!r} could not be correlated with any reference "
                "series (too few aligned rows or a constant series)"
            )
            return base
        per_factor[factor] = {"max_abs_corr": best, "matched": matched}

    mean = sum(v["max_abs_corr"] for v in per_factor.values()) / len(per_factor)
    return {
        "novelty": mean,
        "per_factor": per_factor,
        "n_reference": len(ref),
        "basis": (
            f"mean over {len(per_factor)} candidate factor(s) of the maximum "
            f"|corr| against {len(ref)} held-out reference series"
        ),
        "unavailable": None,
    }


def admit_factor(
    name: str,
    series,
    reference: dict,
    *,
    productivity: float | None = None,
    performance: float | None = None,
    novelty_max_corr: float = NOVELTY_MAX_CORR,
) -> dict:
    """Admit a newly proposed factor, or flag it as a relabelling (H9).

    2609.00731 requires **productivity, performance and novelty jointly**. The
    novelty screen runs first: a factor whose maximum absolute correlation
    against the held-out ``reference`` set reaches ``novelty_max_corr`` is
    **flagged** (``flagged: True``, ``admitted: False``) with the reference member
    it matches. A factor that passes the novelty screen but is handed no
    productivity or performance read is **not admitted** either - the joint
    requirement is the point, not an optional extra.

    Returns ``{"admitted", "flagged", "max_abs_corr", "matched", "novelty",
    "reason", "basis"}``.
    """
    screen = novelty({name: series}, reference)
    out = {
        "admitted": False,
        "flagged": False,
        "max_abs_corr": None,
        "matched": None,
        "novelty": screen["novelty"],
        "reason": screen["unavailable"],
        "basis": screen["basis"],
    }
    if screen["unavailable"]:
        return out

    entry = screen["per_factor"][name]
    out["max_abs_corr"] = entry["max_abs_corr"]
    out["matched"] = entry["matched"]
    if entry["max_abs_corr"] >= novelty_max_corr:
        out["flagged"] = True
        out["reason"] = (
            f"relabelled: |corr|={entry['max_abs_corr']:.3f} with reference "
            f"{entry['matched']!r} >= {novelty_max_corr}"
        )
        return out

    missing = [
        key
        for key, value in (("productivity", productivity), ("performance", performance))
        if value is None
    ]
    if missing:
        out["reason"] = (
            "admission requires productivity, performance and novelty jointly; "
            f"missing {', '.join(missing)}"
        )
        return out

    out["admitted"] = True
    out["reason"] = "novel against the reference set; productivity and performance supplied"
    return out


def embed_reports(report_texts: dict, thesis_text: str, *, embedder=None) -> dict:
    """Embed report texts and a thesis with one text model (H9's embedding stage).

    **Refused by default with a named reason.** This repo ships no text-embedding
    provider, so with no ``embedder`` supplied the read returns
    ``no_embedding_backend`` rather than substituting a pseudo-embedding; the
    number is never approximated. A caller that has an embedding model passes a
    ``embedder(text) -> sequence[float]`` callable.
    """
    reason = (
        "no_embedding_backend: this repo has no text-embedding provider, so the "
        "report texts cannot be embedded; the influence read is solved over vectors "
        "supplied directly to attribution()"
    )
    if embedder is None or not callable(embedder):
        return {
            "reports": None,
            "thesis": None,
            "basis": "report influence refused at the embedding stage",
            "unavailable": reason,
        }
    try:
        reports = {
            str(name): [float(v) for v in embedder(text)]
            for name, text in dict(report_texts or {}).items()
        }
        thesis = [float(v) for v in embedder(thesis_text)]
    except Exception as exc:  # noqa: BLE001 - an advisory read must not raise
        return {
            "reports": None,
            "thesis": None,
            "basis": "report influence refused at the embedding stage",
            "unavailable": f"{type(exc).__name__}: {exc}",
        }
    return {
        "reports": reports,
        "thesis": thesis,
        "basis": f"embedded {len(reports)} report(s) and the thesis with the supplied embedder",
        "unavailable": None,
    }


def reference_names(ticker: str, *, limit: int = 8) -> list[str]:
    """The disclosed reference-set names for a run, through ``peer_universe``.

    One implementation for the reference set: ``peer_universe.resolved_peer_names``
    is the repo's only peer-name resolver, so this wraps it rather than adding a
    second. Never raises - a peer fetch that fails leaves ``[]`` and the caller's
    screen then refuses for a missing ``Z`` (missing is never an empty set
    presented as a passed screen).
    """
    try:
        from tradingagents.strategies.peer_universe import resolved_peer_names

        return list(resolved_peer_names(ticker, limit=limit))
    except Exception:  # noqa: BLE001 - a peer fetch must never break a scoring read
        return []

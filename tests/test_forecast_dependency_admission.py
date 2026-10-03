"""The dependency-admission gate (design doc §9 + plan §3, item FL-4).

The design doc's per-library verdicts are **policy**, and today's net dependency
change is **zero** — `pyproject.toml` carries no forecasting extra at all. This
file makes both facts executable:

- a forecasting-related extra that appears in `pyproject.toml` must carry a
  declared **verdict**, a categorized **reason** and a **licence tier**, and a
  `CONDITIONAL` verdict must additionally name the **FD-1 clauses** it would
  satisfy and the **benchmark record** that would admit it (design doc §9.1:
  admission is refit-environment admission, and a capability gap alone is
  explicitly insufficient);
- the real `pyproject.toml` installs **none** of them today.

**What it enforces is the process, not the judgement** (plan §9 limit 2): a
wrong `REJECT` still passes. And the licence **tier** here is the observed licence
family, not the policy question of which tiers are acceptable — that is the
owner's open §11.3 decision, so an unread licence is recorded `unverified` rather
than assumed permissive.

Offline, pure, sub-second: `tomllib` and a dict, no vendor, no network.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import tomllib

pytestmark = pytest.mark.timeout(60)

REPO = Path(__file__).resolve().parents[1]
PYPROJECT = REPO / "pyproject.toml"

#: The closed verdict set (design doc §9). Categorized on purpose: a future
#: contributor re-opens the *right* argument rather than the whole row.
VERDICTS = (
    "ADMITTED",
    "CONDITIONAL",
    "REJECT_DUPLICATE",
    "REJECT_DIRECT",
    "REJECT_NO_CONSUMER",
    "REJECT_THIS_PASS",
    "REJECT_NO_RESEARCH_CASE",
    "ALREADY_COVERED",
)

#: The observed licence families, plus `unverified` for a licence not read from
#: source. `unverified` is a **fact**, not a policy tier: whether an OSI-approved
#: permissive licence may be admitted *by policy* is the owner's §11.3 call.
LICENCE_TIERS = ("default", "osi_review", "custom_review", "unverified")

#: Packages that make a dependency "forecasting-related" for this gate: the
#: declared table's own names plus the families the design doc evaluated. A
#: distribution matching one of these must have a row.
FORECASTING_HINTS = (
    "statsforecast",
    "mlforecast",
    "neuralforecast",
    "forecasting",
    "sktime",
    "pmdarima",
    "statsmodels",
    "arch",
    "hmmlearn",
    "pomegranate",
    "ruptures",
    "changepoint",
    "darts",
    "gluonts",
    "autogluon",
    "pymc",
    "pyro",
    "tensorflow-probability",
    "chronos",
    "timesfm",
    "uni2ts",
    "moirai",
    "lag-llama",
    "moment",
    "prophet",
    "pyaf",
    "greykite",
    "kats",
    "pyflux",
    "qlib",
    "finrl",
    "orbit",
)

#: The declared table (design doc §9 / plan §3). Keys are the design's own
#: package names — `moirai`/`uni2ts` and `chronos` are recorded under the names
#: the design uses, and a real distribution is matched by `FORECASTING_HINTS`.
#: `benchmark_ref`/`fd1_clauses` are mandatory for a `CONDITIONAL` row.
ADMISSION = {
    "statsforecast": {
        "verdict": "CONDITIONAL",
        "reason": "candidate classical forecasters for a declared pool; NOT the -t/FIGARCH source",
        "licence_tier": "default",
        "fd1_clauses": (3, 4),
        "benchmark_ref": "volatility.har_rv_and_naive_trailing",
    },
    "mlforecast": {
        "verdict": "CONDITIONAL",
        "reason": "candidate tabular/lag-feature learned members; not a neural framework",
        "licence_tier": "default",
        "fd1_clauses": (3, 4),
        "benchmark_ref": "volatility.har_rv_and_naive_trailing",
    },
    "arch": {
        "verdict": "REJECT_DUPLICATE",
        "reason": "garch11_fit owns GARCH conditional variance (FD-1 cl. 5)",
        "licence_tier": "osi_review",
    },
    "statsmodels": {
        "verdict": "REJECT_DIRECT",
        "reason": "existing regime/covariance surface; transitive via statsforecast",
        "licence_tier": "default",
    },
    "hmmlearn": {
        "verdict": "REJECT_DUPLICATE",
        "reason": "hmm_filtered_regime exists and feeds book_risk's VaR",
        "licence_tier": "unverified",
    },
    "ruptures": {
        "verdict": "REJECT_DUPLICATE",
        "reason": "cusum + bocpd + spectral_change_read",
        "licence_tier": "unverified",
    },
    "darts": {
        "verdict": "REJECT_NO_CONSUMER",
        "reason": "no declared producer; large compiled/torch surface",
        "licence_tier": "unverified",
    },
    "neuralforecast": {
        "verdict": "REJECT_NO_CONSUMER",
        "reason": "no declared producer; large compiled/torch surface",
        "licence_tier": "unverified",
    },
    "gluonts": {
        "verdict": "REJECT_NO_CONSUMER",
        "reason": "no declared producer; large compiled/torch surface",
        "licence_tier": "unverified",
    },
    "pytorch-forecasting": {
        "verdict": "REJECT_NO_CONSUMER",
        "reason": "no declared producer; large compiled/torch surface",
        "licence_tier": "unverified",
    },
    "autogluon": {
        "verdict": "REJECT_NO_CONSUMER",
        "reason": "no declared producer; large compiled/torch surface",
        "licence_tier": "unverified",
    },
    "pymc": {
        "verdict": "REJECT_NO_CONSUMER",
        "reason": "no declared probabilistic producer",
        "licence_tier": "unverified",
    },
    "pyro": {
        "verdict": "REJECT_NO_CONSUMER",
        "reason": "no declared probabilistic producer",
        "licence_tier": "unverified",
    },
    "tensorflow-probability": {
        "verdict": "REJECT_NO_CONSUMER",
        "reason": "no declared probabilistic producer",
        "licence_tier": "unverified",
    },
    "chronos": {
        "verdict": "REJECT_THIS_PASS",
        "reason": "no consumer + no demonstrated incremental value (source + LICENSE are Apache-2.0)",
        "licence_tier": "custom_review",
    },
    "timesfm": {
        "verdict": "REJECT_THIS_PASS",
        "reason": "no consumer + no demonstrated value; 3.0 weights are non-commercial",
        "licence_tier": "custom_review",
    },
    "moirai": {
        "verdict": "REJECT_THIS_PASS",
        "reason": "no consumer + no demonstrated incremental value",
        "licence_tier": "custom_review",
    },
    "lag-llama": {
        "verdict": "REJECT_THIS_PASS",
        "reason": "no consumer + no demonstrated incremental value",
        "licence_tier": "custom_review",
    },
    "moment": {
        "verdict": "REJECT_THIS_PASS",
        "reason": "no consumer + no demonstrated incremental value",
        "licence_tier": "custom_review",
    },
    "prophet": {
        "verdict": "REJECT_NO_RESEARCH_CASE",
        "reason": "no research case",
        "licence_tier": "unverified",
    },
    "pyaf": {
        "verdict": "REJECT_NO_RESEARCH_CASE",
        "reason": "no research case",
        "licence_tier": "unverified",
    },
    "greykite": {
        "verdict": "REJECT_NO_RESEARCH_CASE",
        "reason": "no research case",
        "licence_tier": "unverified",
    },
    "kats": {
        "verdict": "REJECT_NO_RESEARCH_CASE",
        "reason": "no research case",
        "licence_tier": "unverified",
    },
    "pyflux": {
        "verdict": "REJECT_NO_RESEARCH_CASE",
        "reason": "no research case",
        "licence_tier": "unverified",
    },
    "qlib": {
        "verdict": "ALREADY_COVERED",
        "reason": "territory covered by existing design+plan pairs; not an installed producer",
        "licence_tier": "default",
    },
    "finrl": {
        "verdict": "ALREADY_COVERED",
        "reason": "territory covered by existing design+plan pairs; not an installed producer",
        "licence_tier": "default",
    },
}


# ---------------------------------------------------------------------------
# The checker
# ---------------------------------------------------------------------------


def _normalize(name: str) -> str:
    """PEP 503 normalization: lowercase, runs of `-_.` collapsed to `-`."""
    out = []
    for ch in name.strip().lower():
        out.append("-" if ch in "-_." else ch)
    joined = "".join(out)
    while "--" in joined:
        joined = joined.replace("--", "-")
    return joined.strip("-")


def _distribution_name(spec: str) -> str:
    """The distribution name from a PEP 508 requirement string."""
    for sep in ("[", " ", ";", "=", "<", ">", "!", "~", "("):
        spec = spec.split(sep, 1)[0]
    return _normalize(spec)


def _is_forecasting(dist: str) -> bool:
    norm = _normalize(dist)
    tokens = norm.split("-")
    return any(hint in tokens or norm.startswith(hint) for hint in FORECASTING_HINTS)


def _installed_distributions(project: dict) -> dict[str, list[str]]:
    """``{group: [distribution, ...]}`` for core deps and every extra."""
    out: dict[str, list[str]] = {}
    core = (project.get("project") or {}).get("dependencies") or []
    out["core"] = [_distribution_name(spec) for spec in core]
    for group, specs in ((project.get("project") or {}).get("optional-dependencies") or {}).items():
        out[group] = [_distribution_name(spec) for spec in specs]
    return out


def _unlisted_forecasting(installed: dict[str, list[str]]) -> list[tuple[str, str]]:
    """``(group, distribution)`` pairs that are forecasting-related but undeclared."""
    return sorted(
        (group, dist)
        for group, dists in installed.items()
        for dist in dists
        if _is_forecasting(dist) and dist not in ADMISSION
    )


def _admission_problems(table: dict) -> list[str]:
    """Every way a declared row can be incomplete, named by row and field."""
    problems: list[str] = []
    for package, row in table.items():
        verdict = row.get("verdict")
        if verdict not in VERDICTS:
            problems.append(f"{package}: verdict {verdict!r} is not one of {list(VERDICTS)}")
        if not (row.get("reason") or "").strip():
            problems.append(f"{package}: no categorized reason")
        if row.get("licence_tier") not in LICENCE_TIERS:
            problems.append(f"{package}: licence_tier {row.get('licence_tier')!r} is not declared")
        if verdict == "CONDITIONAL":
            if not row.get("benchmark_ref"):
                problems.append(f"{package}: CONDITIONAL without a benchmark_ref")
            if not row.get("fd1_clauses"):
                problems.append(f"{package}: CONDITIONAL without the FD-1 clauses it satisfies")
    return problems


def _project_from_text(text: str) -> dict:
    return tomllib.loads(text)


# ---------------------------------------------------------------------------
# The real tree
# ---------------------------------------------------------------------------


def test_the_real_pyproject_installs_no_forecasting_dependency():
    """Today's net dependency change is zero — the acceptance, measured."""
    installed = _installed_distributions(_project_from_text(PYPROJECT.read_text(encoding="utf-8")))
    offending = sorted(
        (group, dist) for group, dists in installed.items() for dist in dists if _is_forecasting(dist)
    )
    assert offending == [], (
        f"a forecasting dependency is installed: {offending}. Adding one requires an ADMISSION row "
        "(verdict + reason + licence tier) and, for CONDITIONAL, the FD-1 clauses and the benchmark "
        "record that would admit it (design doc §9.1, plan FL-4)."
    )
    assert _unlisted_forecasting(installed) == []


def test_the_declared_table_is_internally_complete():
    assert _admission_problems(ADMISSION) == []
    conditional = [p for p, row in ADMISSION.items() if row["verdict"] == "CONDITIONAL"]
    assert sorted(conditional) == ["mlforecast", "statsforecast"], (
        "the ONLY conditionally-admissible libraries are the two the design doc §9 names"
    )


# ---------------------------------------------------------------------------
# Mutations that must fail, by name
# ---------------------------------------------------------------------------


def test_a_new_forecasting_extra_requires_a_verdict():
    mutated = PYPROJECT.read_text(encoding="utf-8") + (
        '\n[project.optional-dependencies.sktime]\nsktime = ["sktime>=0.30"]\n'
    )
    installed = _installed_distributions(_project_from_text(mutated))
    flagged = _unlisted_forecasting(installed)
    assert any(dist == "sktime" for _, dist in flagged), (
        f"an unlisted forecasting extra must be flagged, got {flagged}"
    )
    # ...and a declared one is not an "unlisted" problem (it has its own row).
    declared = _installed_distributions(
        _project_from_text(
            PYPROJECT.read_text(encoding="utf-8")
            + '\n[project.optional-dependencies.fc]\nstatsforecast = ["statsforecast>=2.1"]\n'
        )
    )
    assert _unlisted_forecasting(declared) == []


def test_a_conditional_row_must_name_its_benchmark():
    stripped = {
        key: dict(row) for key, row in ADMISSION.items()
    }
    stripped["statsforecast"].pop("benchmark_ref")
    problems = _admission_problems(stripped)
    assert any(p == "statsforecast: CONDITIONAL without a benchmark_ref" for p in problems), problems

    stripped["mlforecast"].pop("fd1_clauses")
    problems = _admission_problems(stripped)
    assert any("mlforecast: CONDITIONAL without the FD-1 clauses" in p for p in problems), problems


def test_every_admitted_row_declares_a_licence_tier():
    assert {row["licence_tier"] for row in ADMISSION.values()} <= set(LICENCE_TIERS)
    dropped = {key: dict(row) for key, row in ADMISSION.items()}
    dropped["arch"].pop("licence_tier")
    problems = _admission_problems(dropped)
    assert any(p == "arch: licence_tier None is not declared" for p in problems), problems

    bogus = {key: dict(row) for key, row in ADMISSION.items()}
    bogus["arch"]["licence_tier"] = "permissive-whatever"
    assert any("arch: licence_tier 'permissive-whatever'" in p for p in _admission_problems(bogus))

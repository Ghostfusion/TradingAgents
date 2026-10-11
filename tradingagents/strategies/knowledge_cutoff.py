"""Model-knowledge cutoffs: was a replay inside a model's own training window?

The engine polices *data* look-ahead thoroughly - ``load_ohlcv`` cuts at the run
date, ``date_window`` masks windows, the per-vendor date guards, FRED's
``observation_end``, the post-16:00-ET news bucket. Every one of those keeps the
model from being SHOWN the future. None of them keeps the model from KNOWING it:
a replay that asks a 2026-10 model snapshot about a 2024 date hands the model a
period it may already have memorised, and no date filter in a data layer can see
that. This module is the instrument for that one class.

Two sources, and never a guess:

* **Declared.** :data:`MODEL_KNOWLEDGE_CUTOFFS` maps a model-id PREFIX to the
  last date its training data covers. It ships EMPTY: the models this repo
  configures are self-hosted or synthetic names with no publicly documented
  cutoff, and inventing one would be a fabricated fact. Declare the ones you
  actually run with ``TRADINGAGENTS_MODEL_KNOWLEDGE_CUTOFFS``
  (``"prefix=YYYY-MM-DD;prefix2=YYYY-MM-DD"``), merged over the table.
* **Derived.** A served snapshot whose id ends in ``YYYYMMDD`` (the decisions API
  answers ``openai/gpt-6-luna-decisions-20261006``) was frozen that day, so its
  training data cannot extend past it. That date is a **conservative** cutoff: it
  can only flag MORE windows as contaminated than the true training cutoff would,
  and it is read off the run's own recorded response rather than assumed.

:func:`contamination_verdict` is the read, and it FAILS CLOSED:

* ``CONTAMINATED`` - at least one model's cutoff is strictly AFTER the analysis
  date, so the model could have read the outcome;
* ``CLEAN`` - every model resolved a cutoff and none is after the analysis date;
* ``UNKNOWN`` - no analysis date, no model id, or any model with no resolvable
  cutoff. An unmeasured window is never reported clean.

A cutoff EQUAL to the analysis date is CLEAN: a model frozen that day cannot have
trained on that day's outcome. The comparison is date-string ordered
(``YYYY-MM-DD``).

The caller is ``tradingagents/jev.py``: each verdict file records its own
``knowledge_cutoff`` block beside the decider's ratings, so the window check
travels with the verdict. The analysis date comes from the tree's own
``research_decision.json`` (``effective_date``), the run clock, or the tree's name
stamp, and the block names which (``date_source``) - a silently substituted date
would make the check unfalsifiable.

Design: H12 in ``docs/paper_survey_26/design_research_honesty_gates.md``. Pure,
deterministic, offline. No network, no state.
"""

from __future__ import annotations

import os
import re
from collections.abc import Sequence

#: Model-id prefix -> the last date the model's training data covers
#: (``YYYY-MM-DD``). Ships EMPTY by design (see the module docstring): declare
#: the models you run, or let the served snapshot's own date stand in.
MODEL_KNOWLEDGE_CUTOFFS: dict[str, str] = {}

#: The env override that declares cutoffs without an edit here:
#: ``"prefix=YYYY-MM-DD;prefix2=YYYY-MM-DD"``.
ENV_OVERRIDE = "TRADINGAGENTS_MODEL_KNOWLEDGE_CUTOFFS"

_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

#: A served-snapshot stamp: the model id's FINAL token is ``YYYYMMDD``. Anchored
#: to the end so a version-shaped id (``typesafe/jev-1.13``) is never read as a
#: date.
_SNAPSHOT_RE = re.compile(r"(\d{4})(\d{2})(\d{2})$")


def _parse_declarations(raw: str | None) -> dict[str, str]:
    """``"prefix=YYYY-MM-DD;prefix2=YYYY-MM-DD"`` -> a prefix map.

    A malformed pair is SKIPPED, not raised: this is a diagnostic declaration,
    and a typo in it must not take a run down. A date that is not ``YYYY-MM-DD``
    is skipped too.
    """
    out: dict[str, str] = {}
    for part in str(raw or "").split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        prefix, _, date = part.rpartition("=")
        prefix, date = prefix.strip(), date.strip()
        if prefix and _DATE_RE.fullmatch(date):
            out[prefix] = date
    return out


def _declared() -> dict[str, str]:
    """The table merged with the env override (the env wins on a collision)."""
    merged = dict(MODEL_KNOWLEDGE_CUTOFFS)
    merged.update(_parse_declarations(os.environ.get(ENV_OVERRIDE)))
    return merged


def _derived(model: str) -> str | None:
    """A dated served-snapshot id -> its freeze date, else ``None``.

    ``openai/gpt-6-luna-decisions-20261006`` -> ``2026-10-06``. A stamp with an
    impossible month or day is refused rather than normalised.
    """
    m = _SNAPSHOT_RE.search(str(model or "").strip())
    if not m:
        return None
    year, month, day = m.groups()
    if not (1 <= int(month) <= 12 and 1 <= int(day) <= 31):
        return None
    return f"{year}-{month}-{day}"


def _cutoff_for(model: str) -> tuple[str | None, str]:
    """``(cutoff, provenance)`` for one model id.

    A DECLARED prefix wins - it is the true training cutoff, which a freeze date
    only bounds from above - longest prefix first, so ``openai/gpt-6`` beats
    ``openai``. Otherwise the served snapshot's own date, marked
    ``"served-snapshot"``. Otherwise ``(None, "no declared cutoff")``.
    """
    model = str(model or "").strip()
    if not model:
        return None, "no model id"
    table = _declared()
    best: str | None = None
    for prefix in table:
        if model.startswith(prefix) and (best is None or len(prefix) > len(best)):
            best = prefix
    if best is not None:
        return table[best], f"declared ({best})"
    derived = _derived(model)
    if derived is not None:
        return derived, "served-snapshot"
    return None, "no declared cutoff"


def contamination_verdict(
    *,
    as_of: str | None,
    models: Sequence[str],
    date_source: str = "caller",
) -> dict:
    """The window check over one run's input models.

    ``as_of`` is the date the analysis is ABOUT (the run's trade date), not the
    wall clock the run happened on. ``models`` is every model id that touched the
    run - the served snapshot ids the vendor reported, or the configured names
    when no snapshot was recorded.

    Returns ``{status, as_of, date_source, models, offenders, unresolved, basis}``
    with ``status`` in ``CONTAMINATED | CLEAN | UNKNOWN``. ``models`` maps each id
    to ``{cutoff, provenance, verdict}`` (``verdict`` is ``unknown`` when no
    cutoff resolved, else ``contaminated``/``clean``). Never raises: an
    unparseable ``as_of`` is an unknown window, not an exception.
    """
    ids = [str(m).strip() for m in (models or []) if str(m or "").strip()]
    as_of = str(as_of).strip() if as_of else ""
    dated = bool(_DATE_RE.fullmatch(as_of))
    resolved = {m: _cutoff_for(m) for m in ids}
    detail: dict[str, dict] = {}
    offenders: list[str] = []
    unresolved: list[str] = []
    for m in ids:
        cutoff, provenance = resolved[m]
        if cutoff is None:
            unresolved.append(m)
            verdict = "unknown"
        elif dated and cutoff > as_of:
            offenders.append(m)
            verdict = "contaminated"
        else:
            verdict = "clean"
        detail[m] = {"cutoff": cutoff, "provenance": provenance, "verdict": verdict}

    if not ids:
        status = "UNKNOWN"
        basis = "no model id recorded - window unmeasured"
    elif not dated:
        status = "UNKNOWN"
        basis = f"no usable analysis date ({as_of or 'none'}) - window unmeasured"
    elif offenders:
        status = "CONTAMINATED"
        basis = (
            "model knowledge cutoff after the analysis date: "
            + ", ".join(offenders)
            + " - the run's window is inside their training knowledge"
        )
    elif unresolved:
        status = "UNKNOWN"
        basis = (
            "no cutoff for " + ", ".join(unresolved)
            + " - declare it (TRADINGAGENTS_MODEL_KNOWLEDGE_CUTOFFS) or record a "
            "dated snapshot id"
        )
    else:
        status = "CLEAN"
        basis = (
            "every input model's cutoff is at or before the analysis date (date "
            f"from {date_source or 'caller'})"
        )
    return {
        "status": status,
        "as_of": as_of or None,
        "date_source": date_source,
        "models": detail,
        "offenders": offenders,
        "unresolved": unresolved,
        "basis": basis,
    }


__all__ = ["ENV_OVERRIDE", "MODEL_KNOWLEDGE_CUTOFFS", "contamination_verdict"]

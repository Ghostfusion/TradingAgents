"""The metric authority registry - one canonical producer per MEASURED metric.

A **manifest plus one resolver**, not a calculator and not a second reconciler.
It reads no vendor, computes no metric, and declares - in one place - which
symbol is the authoritative producer of each *measured* metric the engine
publishes, so one metric cannot be published on two bases at once.

Why (design + plan: ``docs/design_metric_authority_registry.md``):
``docs/MASTER_DESIGN.md`` §2.1 **rule 8** ("one producer per number") is
enforced for *forecasts* (``strategies/forecast_registry.py``); for *measured
inputs* the repo has four DETECTORS - ``metric_reconcile``'s tool -> metric
index, ``data_quality.disagreement_flag``'s cross-vendor spread, the report
verifier's basis ledger, and the in-module refusals in ``regime_score`` /
``sentiment_score`` - and **no authority column**. So a report or a card can
publish either of two disagreeing values, and the only thing that objects is a
post-hoc verifier after the number shipped. This module is the authority column,
and :func:`resolve_metric` is where the refusal lives.

Shapes are copied from ``forecast_registry`` deliberately, including its
``_module_and_attr`` transform (imported, never re-implemented - rule 8 applies
to the transform too). ``implementation_ref`` is a *location*; ``producer_id``
is the stable semantic owner and is **never** a code path; a ``declined`` row is
a *cited policy* - no producer, no basis, no gate, no fallback, and a
``reason_code`` + ``citation`` that makes the refusal reversible.

Contract
--------
``resolve_metric(metric)`` is a **declaration lookup**: it names the producer of
record and never invents a value. ``resolve_metric(metric, values={...})``
**resolves a measurement**: the canonical producer's own value is published WITH
its basis, and any secondary producer more than ``tolerance_pct`` away is a
visible ``conflict`` - never silently averaged or picked (the ``regime_score`` /
``disagreement_flag`` precedent).

The fail-closed switch ``enable_metric_authority`` (owner-approved) is read
HERE. When it is **on**, a metric that does not resolve to an admitted producer
is ``unavailable`` - never the computed value, never a legacy fallback: the
*absence of authority* is itself the reason. When it is **off** (the shipped
default) every read is unchanged.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass

from tradingagents.strategies import forecast_registry as _forecast_registry

#: The repo's ONE ``implementation_ref`` transform, imported from the forecast
#: registry rather than copied (rule 8: one producer for the transform too).
_module_and_attr = _forecast_registry._module_and_attr


class MetricAuthorityError(ValueError):
    """The registry declared something that cannot be true of the tree."""


#: A row is either an admitted producer or a cited refusal.
METRIC_STATUSES = ("ok", "declined")

#: The closed vocabulary for a ``declined`` row's reason. Free prose is not a
#: code: a reader greps the code, and the ``citation`` makes it reversible.
METRIC_DECLINED_REASON_CODES = (
    "OWNER_BASIS_DECISION_PENDING",
    "BASIS_AMBIGUOUS",
)

#: The same-basis comparison band - matches ``metric_reconcile.MATCH_TOLERANCE``
#: (1%). A secondary producer inside it is the same number; outside it is a
#: visible ``conflict``, never silently averaged (design doc §8, the tolerance
#: rule: "never auto-pick within tolerance").
METRIC_TOLERANCE_PCT = 0.01


@dataclass(frozen=True, kw_only=True)
class MetricRow:
    """One declared authoritative producer for one measured metric.

    ``status`` is ``ok`` (a producer is authorized) or ``declined`` (the engine
    refuses to name one - a cited policy, not an omission). A ``declined`` row
    carries **no** producer, basis, gate or fallback, mirroring the forecast
    registry's rule: a cited refusal is a decision, an absent row is an
    invitation.
    """

    metric: str
    definition: str
    definition_version: str
    unit: str
    status: str
    producer_id: str | None = None
    implementation_ref: str | None = None
    basis: str | None = None
    fallback: tuple[str, ...] = ()
    tolerance_pct: float | None = None
    gate: str | None = None
    reason_code: str | None = None
    citation: str | None = None

    def __post_init__(self) -> None:
        for name in ("metric", "definition", "definition_version", "unit"):
            if not str(getattr(self, name) or "").strip():
                raise MetricAuthorityError(
                    f"MetricRow: a row must name its {name} (design doc §3)"
                )
        if self.status not in METRIC_STATUSES:
            raise MetricAuthorityError(
                f"MetricRow {self.metric!r}.status must be one of "
                f"{list(METRIC_STATUSES)}, got {self.status!r}"
            )
        if self.status == "declined":
            missing = [
                name
                for name, value in (
                    ("reason_code", self.reason_code),
                    ("citation", self.citation),
                )
                if not (value or "").strip()
            ]
            if missing:
                raise MetricAuthorityError(
                    f"MetricRow {self.metric!r} is declined but names no {missing}: "
                    "an uncited refusal is only an omission (design doc §3)"
                )
            if self.reason_code not in METRIC_DECLINED_REASON_CODES:
                raise MetricAuthorityError(
                    f"MetricRow {self.metric!r}: reason_code {self.reason_code!r} is "
                    f"not in {list(METRIC_DECLINED_REASON_CODES)} - free prose is not "
                    "a code (design doc §3)"
                )
            if (
                self.producer_id
                or self.implementation_ref
                or self.basis
                or self.gate
                or self.fallback
            ):
                raise MetricAuthorityError(
                    f"MetricRow {self.metric!r}: a declined row has no producer, no "
                    "basis, no gate and no fallback - nothing produces it (design "
                    "doc §3)"
                )
            return
        if not self.producer_id or not self.implementation_ref:
            raise MetricAuthorityError(
                f"MetricRow {self.metric!r}: a non-declined row must name BOTH its "
                "stable producer_id and its implementation_ref (design doc §3)"
            )
        if ".py" in self.producer_id or "::" in self.producer_id:
            raise MetricAuthorityError(
                f"MetricRow.producer_id {self.producer_id!r} is a code path; it is the "
                "stable semantic owner (design doc §3)"
            )
        try:
            _module_and_attr(self.implementation_ref)
        except Exception as exc:  # noqa: BLE001 - re-raised as the registry's error
            raise MetricAuthorityError(
                f"MetricRow.implementation_ref {self.implementation_ref!r} is not "
                f"'<path>.py::<symbol>': {exc} (design doc §3)"
            ) from exc
        if self.gate is not None and not self.gate.startswith("enable_"):
            raise MetricAuthorityError(
                f"MetricRow.gate {self.gate!r} is not an `enable_*` config switch"
            )
        if self.reason_code is not None or self.citation is not None:
            raise MetricAuthorityError(
                f"MetricRow {self.metric!r}: only a declined row carries a "
                "reason_code or a citation - a produced metric is not a refusal"
            )
        for ref in self.fallback:
            _module_and_attr(ref)


# ---------------------------------------------------------------------------
# The seed (design doc §4 P2). The five numbers named there, in the order the
# defects were found. Every `implementation_ref` is resolved against the live
# tree by `tests/test_metric_authority.py` - a renamed producer fails a build,
# not a report.
# ---------------------------------------------------------------------------

METRIC_REGISTRY: tuple[MetricRow, ...] = (
    MetricRow(
        metric="price",
        definition=(
            "the reference price a run measures its levels against - the last close "
            "of the run's adjusted OHLCV series"
        ),
        definition_version="price.v1",
        unit="usd_per_share",
        status="ok",
        producer_id="ohlcv.last_close",
        implementation_ref="dataflows/stockstats_utils.py::load_ohlcv",
        basis=(
            "the run's adjusted close (`load_ohlcv`, auto_adjust=True); the price "
            "CALIBER a vendor serves is `market_router.price_caliber_for`, and two "
            "calibers are not the same number (design doc §6)"
        ),
    ),
    MetricRow(
        metric="p_e",
        definition=(
            "trailing price/earnings: the reference price over the engine's own "
            "trailing-twelve-month net income per share"
        ),
        definition_version="p_e.v1",
        unit="ratio",
        status="ok",
        producer_id="ratios.compute_ratios",
        implementation_ref="strategies/ratios.py::compute_ratios",
        basis=(
            "the engine's `trailing_twelve_months` net income over the share count "
            "(owner, 2026-10-05: the ENGINE's basis is canonical - it is the repo's "
            "own reproducible TTM)"
        ),
        fallback=("dataflows/y_finance.py::get_fundamentals",),
    ),
    MetricRow(
        metric="cash",
        definition="the canonical cash and cash-equivalents line on the latest balance sheet",
        definition_version="cash.v1",
        unit="usd",
        status="ok",
        producer_id="statement.cash_line",
        implementation_ref="dataflows/statement_parsing.py::fetch_ticker",
        basis=(
            "us-gaap `CashAndCashEquivalents` (owner, 2026-10-05: the canonical tag). "
            "The short-term-investments tag `CashCashEquivalentsAndShortTermInvestments` "
            "is a labelled fallback, never the canonical reading - the same period "
            "resolves to either, which is the unstable-key defect"
        ),
    ),
    MetricRow(
        metric="fcf",
        definition="free cash flow: operating cash flow less capex, filed positive",
        definition_version="fcf.v1",
        unit="usd",
        status="ok",
        producer_id="statement.fcf_series",
        implementation_ref="dataflows/statement_parsing.py::_add_derived_series",
        basis=(
            "`operating_cashflow - capex` joined BY PERIOD, never by position; the "
            "capex concept is a candidate list merged by period end (the AMZN "
            "`79a1379` fix), which is what makes the two operands share a year"
        ),
    ),
    MetricRow(
        metric="entry_ceiling",
        definition=(
            "the maximum economically acceptable long entry - the price above which "
            "the trade's own economics fail"
        ),
        definition_version="entry_ceiling.v1",
        unit="usd_per_share",
        status="ok",
        producer_id="entry_ceiling.compose",
        implementation_ref="strategies/entry_ceiling.py::entry_ceiling",
        basis=(
            "§103's `max_entry_price`: the `min` over the available ceiling sources "
            "(valuation / expected_return / risk_reward); owner, 2026-10-05: THIS is "
            "the canonical entry ceiling, not the value a prose line may cite"
        ),
    ),
)


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


def _metric_row(metric: str) -> MetricRow | None:
    name = str(metric or "").strip()
    for row in METRIC_REGISTRY:
        if row.metric == name:
            return row
    return None


def _duplicate_metrics(rows) -> dict[str, int]:
    """Metric ids carried by more than one row, with their row counts."""
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.metric] = counts.get(row.metric, 0) + 1
    return {name: n for name, n in counts.items() if n > 1}


def _live_config(config: dict | None) -> dict:
    """The runtime config, or ``config`` when one is passed."""
    if config is not None:
        return config
    try:
        from tradingagents.dataflows.config import get_config

        return get_config() or {}
    except Exception:  # noqa: BLE001 - a config read must never break a read
        return {}


def _metric_authority_on(config: dict | None) -> bool:
    """The fail-closed switch (P4). Off is the shipped default and is inert."""
    return bool(_live_config(config).get("enable_metric_authority", False))


def _resolve_ref(implementation_ref: str):
    """Import the declared symbol; raise naming the ref when it is gone."""
    module_path, symbol = _module_and_attr(implementation_ref)
    module = importlib.import_module(module_path)
    return getattr(module, symbol)


def resolve_metric(
    metric: str,
    *,
    values: dict[str, float] | None = None,
    config: dict | None = None,
) -> dict:
    """The value, its declared producer and its basis - or a refusal.

    ``status`` is one of ``ok`` / ``unavailable`` / ``conflict`` / ``unknown`` /
    ``declined`` - the same five-state discipline the report verifier uses, and
    the same ``None != 0`` rule this codebase keeps (a refusal never carries
    ``0.0``).

    * **unknown** - the metric is named nowhere in the registry: a *named
      absence*, never a guess.
    * **declined** - a cited refusal (``reason_code`` + ``citation``).
    * **ok** - an admitted producer is named; with ``values``, its own value is
      published *with its basis*.
    * **conflict** - a second producer sits outside ``tolerance_pct``; the
      canonical is still named and the spread is visible, never resolved.
    * **unavailable** - no producer of record supplied a value; or the metric has
      no admitted producer **and** the fail-closed gate is on.

    With the gate on, ``unknown`` and ``declined`` both read ``unavailable``:
    the absence of a named, registered producer is itself the reason, and no
    legacy value is ever substituted.
    """
    on = _metric_authority_on(config)
    row = _metric_row(metric)
    out: dict = {
        "metric": str(metric or "").strip(),
        "status": "unknown",
        "value": None,
        "unit": None,
        "producer_id": None,
        "implementation_ref": None,
        "basis": None,
        "definition": None,
        "definition_version": None,
        "spread_pct": None,
        "conflicts": [],
        "reason_code": None,
        "citation": None,
    }
    if row is None:
        # A metric named nowhere is a named absence. With the gate on it has no
        # producer of record, so it may not publish.
        out["status"] = "unavailable" if on else "unknown"
        return out
    out["unit"] = row.unit
    out["definition"] = row.definition
    out["definition_version"] = row.definition_version
    if row.status == "declined":
        out["status"] = "unavailable" if on else "declined"
        out["reason_code"] = row.reason_code
        out["citation"] = row.citation
        return out
    out["producer_id"] = row.producer_id
    out["implementation_ref"] = row.implementation_ref
    out["basis"] = row.basis
    if not values:
        # A declaration lookup: the producer is named; nothing was measured.
        out["status"] = "ok"
        return out
    canonical: float | None = None
    for key in (row.producer_id, row.implementation_ref):
        if key is None:
            continue
        raw = values.get(key)
        if raw is not None:
            try:
                canonical = float(raw)
            except (TypeError, ValueError):
                canonical = None
            if canonical is not None:
                break
    if canonical is None:
        # No producer of record supplied a value: absent, never 0.0.
        out["status"] = "unavailable"
        return out
    tol = row.tolerance_pct if row.tolerance_pct is not None else METRIC_TOLERANCE_PCT
    conflicts: list[dict] = []
    for source, raw in values.items():
        if raw is None or source in (row.producer_id, row.implementation_ref):
            continue
        try:
            other = float(raw)
        except (TypeError, ValueError):
            continue
        deviation = abs(other - canonical) / max(abs(other), abs(canonical), 1e-9)
        if deviation > tol:
            conflicts.append(
                {"source": str(source), "value": other, "deviation_pct": deviation}
            )
    out["value"] = canonical
    out["conflicts"] = conflicts
    if conflicts:
        out["spread_pct"] = max(c["deviation_pct"] for c in conflicts)
    # A conflicting secondary does NOT change the published value; the canonical
    # is still named, and the disagreement is visible (never silently resolved).
    out["status"] = "conflict" if conflicts else "ok"
    return out


__all__ = [
    "METRIC_DECLINED_REASON_CODES",
    "METRIC_REGISTRY",
    "METRIC_STATUSES",
    "METRIC_TOLERANCE_PCT",
    "MetricAuthorityError",
    "MetricRow",
    "resolve_metric",
]

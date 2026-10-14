"""The Fact layer: a number, its qualifiers, and the rule that produced it.

**Why this exists.** The engine pulled an XBRL-shaped fact (a value WITH its
context, unit and declared precision) out of the vendor payload and then
converted it to a bare float at its internal interface: ``_canonicalize``
collapses a statement to ``{current, prior}`` scalars and ``fetch_ticker``'s
``absorb`` is last-writer-wins over loosely-matched labels, with the period map
opt-in. Every one of ~100 tool leaves then RE-AUTHORED the qualifiers it needed -
so a leaf that could not see the period printed the number without it (the DCF
bridge read FY2025-12-31 while 2026-06-30 sat in the payload), a leaf that
scored a missing input as 0 published a partial sum as a measurement
(Piotroski 3-of-9 read as "3"), and a leaf that consumed a period whose filings
were not yet due reported an incomplete aggregate as a completed quarter (the
2026/Q3 13F at 90.3 % on 2026-10-14).

The normative statements, both older than this repo:

- **VIM 2.9 / GUM 3.1.2** (JCGM 200:2012): a measurement result is a value
  "together with any other available relevant information" and "is complete only
  when accompanied by a statement of the uncertainty of that estimate".
- **XBRL 2.1 §1.4**: an item "contains the value of the simple fact and a
  reference to the context (and unit for numeric items) needed to correctly
  interpret that fact"; numeric items are REQUIRED to document their measurement
  accuracy and unit, ``@decimals`` states "the range in which the actual value
  ... lies", and a Period is "an instant or duration of time".

So a Fact is the internal unit of exchange: :class:`Observation` (the reconcile
layer's value + unit/scale/basis/decimals, extended rather than duplicated) plus
the three qualifiers that were being re-authored - **coverage** (how much of the
derivation was actually measured), **period** (which as-of the value belongs to,
with its kind) and **availability** (the earliest instant a FILED basis for that
period can exist, from :mod:`tradingagents.strategies.availability`).

**One producer per concept.** ``latest``/``prior`` are the only readers of the
``{current, prior}`` shape; ``derive`` is the only producer of a derived value's
coverage; ``render_fact``/``basis_line`` are the only renderers of a fact's
qualifiers; ``FACT_UNITS`` is the only declaration of a canonical line item's
unit, and ``tests/test_measurement_contract.py`` holds it to set equality with
the parser's own canonical keys - so a new statement field cannot enter the tree
without a declared unit.

**The gate.** ``enable_fact_layer`` (default OFF) selects the Fact-rendered
qualifier lines over the legacy hand-authored ones. OFF is byte-identical to the
pre-layer path; ON changes only how a number's qualifiers are PRINTED, never a
value. This is the repo's release-toggle convention (one ``enable_*`` key, read
through ``default_config``, declared in ``docs/gate_registry.md``).
"""

from __future__ import annotations

from dataclasses import dataclass

from tradingagents.strategies.availability import (
    fact_availability,
    form_for_kind,
    period_end_of,
)
from tradingagents.strategies.metric_authority import Observation, declared_decimals

__all__ = [
    "COVERAGE_RULES",
    "FACT_UNITS",
    "UNIT_LABELS",
    "Fact",
    "FactCoverage",
    "FactError",
    "basis_line",
    "coverage_note",
    "derive",
    "fact_layer_on",
    "fact_from_provenance",
    "latest",
    "prior",
    "render_fact",
    "resolve_facts",
]


class FactError(ValueError):
    """A Fact was asked to be something it cannot be (an undeclared unit, a
    derivation over a non-Fact)."""


#: The closed vocabulary for what a canonical statement line item IS. A unit is
#: a declaration about the measurement, not a formatting hint: ``usd`` is a
#: currency amount, ``ratio`` a dimensionless quotient, ``score`` a
#: bounded model output, ``text`` a non-numeric label (``sector``).
UNIT_LABELS = (
    "usd",
    "usd_per_share",
    "shares",
    "ratio",
    "score",
    "count",
    "days",
    "text",
)

#: Canonical line item -> unit. Held to set equality with the parser's own
#: canonical keys by ``tests/test_measurement_contract.py``: adding an alias to
#: ``statement_parsing._ROW_ALIASES`` (or a derived canonical to
#: ``_flat_canonical``) without declaring its unit here fails that test, which
#: is how "no leaf prints an undeclared number" is machine-checked rather than
#: hoped for.
FACT_UNITS: dict[str, str] = {
    # --- income statement -------------------------------------------------
    "revenue": "usd",
    "cogs": "usd",
    "sga": "usd",
    "research_development": "usd",
    "deferred_revenue": "usd",
    "depreciation": "usd",
    "operating_income": "usd",
    "net_income": "usd",
    "eps": "usd_per_share",
    "eps_yoy": "ratio",
    "revenue_yoy": "ratio",
    "interest_expense": "usd",
    "tax_expense": "usd",
    # --- balance sheet ----------------------------------------------------
    "cash": "usd",
    "cash_and_investments": "usd",
    "total_debt": "usd",
    "short_term_debt": "usd",
    "total_assets": "usd",
    "total_equity": "usd",
    "total_liabilities": "usd",
    "current_assets": "usd",
    "current_liabilities": "usd",
    "working_capital": "usd",
    "payables": "usd",
    "retained_earnings": "usd",
    "ppem": "usd",
    "marketable_securities": "usd",
    "inventory": "usd",
    "net_receivables": "usd",
    # --- cash flow --------------------------------------------------------
    "operating_cashflow": "usd",
    "capex": "usd",
    "dividends_paid": "usd",
    "share_buybacks": "usd",
    "debt_repayment": "usd",
    # --- market / identity ------------------------------------------------
    "market_cap": "usd",
    "shares": "shares",
    "beta": "ratio",
    "roe": "ratio",
    "sector": "text",
    "currency": "text",
    # --- derived ratio inputs the screens declare (see
    # ``statement_parsing.enrich_screen_ratios``) --------------------------
    "roa": "ratio",
    "leverage": "ratio",
    "current_ratio": "ratio",
    "gross_margin": "ratio",
    "asset_turnover": "ratio",
    "shares_issued": "shares",
}

#: How `derive` decides whether a derivation was measured well enough.
COVERAGE_RULES = ("all", "any", "floor")


@dataclass(frozen=True, kw_only=True)
class FactCoverage:
    """How much of a derivation's input set was actually measured.

    ``n_of`` and ``required`` are in the SAME unit (counts of inputs), unlike
    ``score_engine.combine``'s weight-fraction coverage, and the two are never
    compared to each other. ``withheld`` names the inputs that were missing, so
    a reader sees WHICH leg was absent and not just how many.
    """

    n_of: int
    required: int
    rule: str = "all"
    withheld: tuple[str, ...] = ()

    @property
    def satisfied(self) -> bool:
        return self.n_of >= self.required

    def render(self) -> str:
        """``"8 of 9 inputs measured; missing: f_eq"``."""
        bits = [f"{self.n_of} of {self.required} inputs measured"]
        if self.withheld:
            bits.append("missing: " + ", ".join(self.withheld))
        return "; ".join(bits)


@dataclass(frozen=True, kw_only=True)
class Fact(Observation):
    """One measured line item, with every qualifier it needs to be read.

    ``metric`` (inherited) is the canonical key; ``period_label`` is the
    vendor's own label while ``period_end`` is the ISO instant it ends (only
    set when the label STATES one - see :func:`availability.period_end_of`);
    ``basis_text`` is what the merge ASKED the vendor for. ``value`` is the
    number a reader sees, and a partial derivation still carries it: refusing to
    publish a number the owner already publishes is not this layer's call - the
    layer's job is that the PARTIAL qualifier travels with it
    (:attr:`usable`, :meth:`FactCoverage.render`).
    """

    period_kind: str = "unstated"
    period_label: str | None = None
    basis_text: str | None = None
    basis_conflict: bool = False
    prior_value: float | None = None
    available_at: str | None = None
    available_latest: str | None = None
    availability_state: str = "unknown"
    availability_reason: str | None = None
    availability_basis: str | None = None
    coverage: FactCoverage | None = None
    derivation: tuple[str, ...] = ()
    invalid_reason: str | None = None

    @property
    def usable(self) -> bool:
        """Whether this value may be consumed AS a measurement.

        A partial derivation is False: the F-Score's leg may not fire, and
        ``combine``'s component arrives absent. A value that is missing or not
        finite is False. Availability does NOT appear here on purpose - a
        preliminary (pre-filing) figure is legitimately usable, and a consumer
        that needs a FILED basis asks :attr:`filed_basis` instead.
        """
        return (
            self.value is not None
            and self.invalid_reason is None
            and (self.coverage is None or self.coverage.satisfied)
        )

    @property
    def filed_basis(self) -> bool:
        """True when the period's filing form is already DUE as of the run clock.

        ``False`` covers both ``not_yet_due`` (the form is not due, so a filed
        basis cannot exist) and ``unknown``/``not_applicable`` (no form, no
        period end, or no clock). Read it as "proven filed", never as "not
        real": a press-release figure is real and merely unverified.
        """
        return self.availability_state == "available"

    def qualifiers(self) -> tuple[str, ...]:
        """The non-numeric parts of this measurement, in reading order."""
        bits: list[str] = []
        if self.period_label:
            bits.append(str(self.period_label))
        if self.period_end and self.period_end != self.period_label:
            bits.append(f"ending {self.period_end}")
        if self.source:
            bits.append(str(self.source))
        if self.basis_group and self.basis_group not in ("vendor_reported", "engine_computed"):
            bits.append(str(self.basis_group))
        if self.prior_value is not None:
            bits.append(f"prior {self.prior_value:,.2f} (period unstated)")
        return tuple(bits)


def _finite(value) -> bool:
    try:
        return float(value) == float(value) and float(value) not in (float("inf"), float("-inf"))
    except (TypeError, ValueError):
        return False


def latest(value):
    """The current-period value of a canonical item (a bare value or a
    ``{current, prior}`` dict). The ONE reader of that shape."""
    if isinstance(value, dict):
        return value.get("current", value.get("value"))
    return value


def prior(value):
    """The prior-period value of a canonical item, or ``None``."""
    return value.get("prior") if isinstance(value, dict) else None


def coverage_note(fact: Fact) -> str:
    """The PARTIAL qualifier for a fact, or ``""`` when it is whole.

    A partial value is not a measurement of the composite: the F-Score's band is
    defined over all nine signals, so a 3-of-9 sum states its coverage and
    refuses the band rather than reporting a smaller number as the same thing.
    """
    cov = fact.coverage
    if cov is None or cov.satisfied:
        return ""
    return f"PARTIAL: {cov.render()}"


def _render_value(fact: Fact) -> str:
    """The value as the source's own precision allows it to be printed."""
    if fact.value is None:
        return "n/a"
    try:
        number = float(fact.value)
    except (TypeError, ValueError):
        return str(fact.value)
    decimals = fact.decimals if fact.decimals is not None else 2
    if fact.scale == "percent":
        return f"{number:.{max(0, min(decimals, 6))}f}%"
    if fact.unit in ("ratio", "score"):
        return f"{number:.{max(0, min(decimals, 6))}f}"
    if fact.unit == "usd":
        return f"{number:,.0f}" if abs(number) >= 1000 else f"{number:,.2f}"
    if fact.unit == "usd_per_share":
        return f"{number:,.{max(0, min(decimals, 6))}f}"
    if fact.unit in ("shares", "count"):
        return f"{number:,.0f}"
    return f"{number:,.{max(0, min(decimals, 6))}f}"


def render_fact(fact: Fact | None, *, label: str | None = None) -> str:
    """One measurement: ``<label>: <value> <unit> (<qualifiers>) [ - notes]``.

    A projection, not an authorship: every part of the string is read off the
    Fact, so a caller cannot state a period the value does not carry. An absent
    unit prints as ``unit undeclared`` rather than being silently omitted - a
    number whose unit nobody declared is not a measurement.
    """
    if fact is None:
        return f"{label or '?'}: n/a"
    name = label or fact.metric
    unit = fact.unit or "unit undeclared"
    value = _render_value(fact)
    quals = fact.qualifiers()
    head = f"{name}: {value} {unit}"
    if quals:
        head += " (" + ", ".join(quals) + ")"
    notes: list[str] = []
    cov = coverage_note(fact)
    if cov:
        notes.append(cov)
    if fact.invalid_reason:
        notes.append(fact.invalid_reason)
    if fact.availability_state == "not_yet_due":
        notes.append(
            f"NOT FILED YET - {fact.availability_basis or 'the form is not yet due'}"
        )
    if fact.derivation:
        notes.append("derived from " + ", ".join(fact.derivation))
    return head + (" - " + " - ".join(notes) if notes else "")


def basis_line(facts: dict, keys, *, indent: str = "  ") -> str:
    """The grouped basis line for a set of facts - ONE producer for it.

    Groups the keys by the period+source their facts carry, so a reader sees
    which figures share an as-of and which do not (the NVDA 2026-09-12 defect
    was an annual P/E quoted beside quarterly balance-sheet rows). A fact whose
    payload period kind contradicts the basis it was requested with is called
    out, as is a partial (coverage-bearing) fact.
    """
    groups: dict[tuple[str, str], list[str]] = {}
    missing: list[str] = []
    for key in keys:
        fact = (facts or {}).get(key)
        if fact is None or (fact.value is None and str(fact.source or "") == "unknown source"):
            missing.append(key)
            continue
        period = str(
            fact.period_label or fact.period_end or fact.basis_text or "period unstated"
        )
        period = " ".join(period.split())[:60]
        source = str(fact.source or "unknown source")
        groups.setdefault((period, source), []).append(key)
    if not groups:
        line = f"{indent}basis: period unstated (no provenance from the vendor chain)"
        if missing:
            line += f"{indent}|  NOT SUPPLIED BY THE CHAIN: " + "/".join(missing)
        return line
    parts = [
        f"{'/'.join(sorted(keys_))} {period} ({source})"
        for (period, source), keys_ in sorted(groups.items())
    ]
    line = f"{indent}basis: " + "; ".join(parts)
    if missing:
        line += f"{indent}|  NOT SUPPLIED BY THE CHAIN: " + "/".join(missing)
    conflicted = sorted(key for key in keys if (facts.get(key) or None) and facts[key].basis_conflict)
    if conflicted:
        line += (
            f"{indent}|  BASIS CONFLICT: "
            + "/".join(conflicted)
            + " came from a payload whose newest period kind contradicts the basis "
            "it was requested with - re-check the period before quoting"
        )
    partial = sorted(
        key
        for key in keys
        if (facts.get(key) or None) and facts[key].coverage and not facts[key].coverage.satisfied
    )
    if partial:
        line += (
            f"{indent}|  PARTIAL: "
            + "; ".join(f"{k} ({facts[k].coverage.render()})" for k in partial)
        )
    unfiled = sorted(
        key
        for key in keys
        if (facts.get(key) or None)
        and not facts[key].filed_basis
        and facts[key].availability_state == "not_yet_due"
    )
    if unfiled:
        earliest = next(
            (facts[k].available_at for k in unfiled if facts[k].available_at), None
        )
        line += (
            f"{indent}|  NOT FILED YET: "
            + "/".join(unfiled)
            + (f" (earliest due {earliest})" if earliest else "")
            + " - the form covering the period is not due as of the run clock"
        )
    return line


def fact_layer_on(config: dict | None = None) -> bool:
    """The ``enable_fact_layer`` release toggle (default OFF, never raises).

    OFF selects the legacy hand-authored qualifier lines, so the gate is
    byte-identical to the pre-layer path; ON renders a number's qualifiers from
    the Fact that carries it. A config read must never break a leaf.
    """
    try:
        if config is None:
            from tradingagents.dataflows.config import get_config  # noqa: PLC0415

            config = get_config()
        return bool((config or {}).get("enable_fact_layer", False))
    except Exception:  # noqa: BLE001 - a config read never breaks a leaf
        return False


def fact_from_provenance(
    key: str,
    value,
    entry: dict | None,
    *,
    prior_value=None,
    as_of=None,
    unit: str | None = None,
    filer_status: str = "unknown",
    form: str | None = None,
) -> Fact:
    """Build one Fact from a canonical value and its provenance record.

    ``entry`` is one row of ``fetch_ticker``'s provenance map
    (``{source, basis, period, observed_kind, basis_conflict}``); a missing or
    empty entry leaves the qualifiers UNKNOWN rather than inventing them.
    """
    entry = dict(entry or {})
    period_label = entry.get("period") or None
    kind = str(entry.get("observed_kind") or "unstated")
    period_end = period_end_of(period_label)
    declared = unit if unit is not None else FACT_UNITS.get(key)
    available = fact_availability(
        period_end=period_end,
        form=form or form_for_kind(kind) or form_for_kind(entry.get("basis")),
        as_of=as_of,
        filer_status=filer_status,
    )
    reason = None
    if value is None:
        reason = "MISSING"
    elif not _finite(value):
        reason = "NOT_FINITE"
    return Fact(
        source=str(entry.get("source") or "unknown source"),
        metric=str(key),
        value=value,
        unit=declared,
        scale="one",
        period_end=period_end.isoformat() if period_end else None,
        as_of=str(as_of)[:10] if as_of else None,
        decimals=declared_decimals(value),
        period_kind=kind,
        period_label=period_label,
        basis_text=entry.get("basis") or None,
        basis_conflict=bool(entry.get("basis_conflict")),
        prior_value=prior_value,
        available_at=available.get("earliest"),
        available_latest=available.get("latest"),
        availability_state=str(available.get("state") or "unknown"),
        availability_reason=available.get("reason"),
        availability_basis=available.get("basis") or None,
        invalid_reason=reason,
    )


def resolve_facts(
    canonical: dict,
    provenance: dict | None = None,
    *,
    as_of=None,
    keys=None,
    units: dict | None = None,
    filer_status: str = "unknown",
) -> dict[str, Fact]:
    """One Fact per canonical line item, with its period, unit and availability.

    Pure over the pair ``fetch_ticker`` already returns: no vendor call, no
    second parse, and no value is ever fabricated. ``keys`` restricts the result
    (default: every key the canonical carries except the ``currency`` marker);
    each fact's ``prior`` period is NOT a key of its own - the ``{current,
    prior}`` shape is read by :func:`latest`/:func:`prior` only.
    """
    canonical = canonical or {}
    provenance = provenance or {}
    units = units or FACT_UNITS
    out: dict[str, Fact] = {}
    for key in keys if keys is not None else canonical:
        if key == "currency":
            continue
        raw = canonical.get(key)
        if isinstance(raw, (list, tuple)):
            # A stacked multi-year series (``annual_series``) is not one
            # measurement: its period span is in the provenance row and its
            # values are a series, so it stays out of the fact map.
            continue
        out[key] = fact_from_provenance(
            key,
            latest(raw),
            provenance.get(key),
            prior_value=prior(raw),
            as_of=as_of,
            unit=units.get(key),
            filer_status=filer_status,
        )
    return out


def derive(
    key: str,
    inputs: dict,
    fn,
    *,
    unit: str | None = None,
    coverage_rule: str = "all",
    required: int | None = None,
    note: str | None = None,
    as_of=None,
    source: str = "derived",
    claim_period: bool = True,
) -> Fact:
    """A derived Fact: the value, its inputs' names, and its COVERAGE.

    ``inputs`` is ``{name: Fact | None | value}``. An input is counted as
    measured when it is a ``Fact`` with :attr:`Fact.usable` true, or a plain
    non-``None`` value; everything else is withheld BY NAME.

    ``coverage_rule``:

    - ``"all"`` (default) - every input must be measured;
    - ``"any"`` - one is enough;
    - ``"floor"`` - ``required`` inputs must be measured.

    ``fn`` receives ``{name: value}`` for the measured inputs only, and is
    called even when the rule fails (so the caller's partial figure is available
    to print) - but the Fact's coverage then says PARTIAL and :attr:`Fact.usable`
    is False. That is the whole point: "a composite that scores a missing input
    as 0 is not a measurement".

    ``claim_period=False`` is for a derivation whose inputs span bases it cannot
    name in one label (a DCF over a TTM cash-flow series plus a quarterly
    balance-sheet bridge): the Fact then claims NO period rather than inheriting
    the one label its inputs happen to agree on.
    """
    if coverage_rule not in COVERAGE_RULES:
        raise FactError(f"unknown coverage_rule {coverage_rule!r}; expected one of {COVERAGE_RULES}")
    inputs = dict(inputs or {})
    values: dict[str, object] = {}
    withheld: list[str] = []
    for name, item in inputs.items():
        if isinstance(item, Fact):
            if item.usable:
                values[name] = item.value
            else:
                withheld.append(name)
        elif item is None:
            withheld.append(name)
        else:
            values[name] = item
    n_of = len(values)
    total = len(inputs)
    if coverage_rule == "all":
        need = total
    elif coverage_rule == "any":
        need = 1 if total else 0
    else:
        need = int(required if required is not None else total)
    try:
        value = fn(values)
    except Exception:  # noqa: BLE001 - a derivation over a partial set may not be defined
        value = None
    satisfied = n_of >= need
    reason = None
    if value is None:
        reason = "MISSING"
    elif not satisfied:
        reason = "COVERAGE_INCOMPLETE"
    bases = {
        str(getattr(item, "source", "") or "") for item in inputs.values() if isinstance(item, Fact)
    }
    periods = {str(getattr(item, "period_label", "") or "") for item in inputs.values() if isinstance(item, Fact)}
    periods.discard("")
    fn_name = getattr(fn, "__name__", "") or ""
    label = None
    if claim_period:
        label = next(iter(periods)) if len(periods) == 1 else (", ".join(sorted(periods)) or None)
    return Fact(
        source=f"{source}:{fn_name}" if fn_name and fn_name != "<lambda>" else source,
        metric=str(key),
        value=value,
        unit=unit if unit is not None else FACT_UNITS.get(key),
        scale="one",
        period_label=label,
        as_of=str(as_of)[:10] if as_of else None,
        decimals=declared_decimals(value),
        coverage=FactCoverage(
            n_of=n_of,
            required=need,
            rule=coverage_rule,
            withheld=tuple(sorted(withheld)),
        ),
        derivation=tuple(sorted(inputs)),
        invalid_reason=reason,
        citation=note,
        upstream=next(iter(bases)) if len(bases) == 1 else None,
    )

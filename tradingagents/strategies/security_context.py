"""Deterministic security classification - the front end the overlay layer lacks.

Design: ``docs/design_security_context.md`` (work items SC-1, SC-2, SC-4a, SC-4,
SC-5, SC-8). The parent design (``docs/Conditional_Research_Overlays_Design.md``,
called ``doc:`` below) specifies a conditional research-overlay layer whose
Overlay Detector has three sub-steps (``doc:263-265``): materiality, evidence
sufficiency, and an ``applicability test``. **That third step has no producer
anywhere in the parent doc** - it is named once and never defined, and nothing in
that doc reads a property of the company. This module is that producer.

Three rules shape everything here.

**Classification is metadata, not analysis.** It answers "what kind of company is
this", never "is this company good". It consumes no LLM context and makes no
judgement, so it cannot be a decision.

**The prior may only widen.** :func:`candidate_themes` is a *union*, and
``ALL_REGISTERED_THEMES`` is always a subset of its result. The matrix orders
evidence-gathering effort; it can never remove a theme from consideration. A
sector label is blunter than an LLM, so letting it exclude would reintroduce the
very error (``doc:1451-1453``) the parent doc keeps the LLM away from. The parent
brief's own example is the reason: a company in **Energy** whose AI exposure is
material anyway, because of data-centre electricity demand.

**Provenance travels with the value.** Four provider legs return four different
taxonomies under one string (``yfinance_sector.fetch_sector``, documented as
"GICS sector" while returning FMP's taxonomy, Finnhub's proprietary
``finnhubIndustry``, Yahoo's sub-industry label, or the repo's own ETF label), so
a sector string without its source is unusable. Every value here carries the
source that produced it, and **no field is named GICS, SIC or NAICS unless it is
that**.

No network call of its own: this reads ``resolve_instrument_identity`` (already
``lru_cache``d at ``agent_utils.py:574``) and, opportunistically, an SEC
submissions payload some earlier step already fetched. When neither is available
the context is empty, which is valid and means "unclassified" - and per
"absence is not exclusion" an unclassified company is checked *more*, not less.

The canonical vocabulary is the repo's own: the eleven ``SPDR_SECTORS`` labels,
reached through the existing ``_canonical_sector``. This module never creates a
second taxonomy or a second normalizer (master rule 15).
"""

from __future__ import annotations

import functools
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from tradingagents.strategies.sector_rank import (
    SPDR_SECTORS,
    _canonical_sector,
    sector_group_of,
)

# ---------------------------------------------------------------------------
# The theme registry
# ---------------------------------------------------------------------------

#: The themes the framework supports, keyed by theme id.
#:
#: The six ids are the parent doc's own §18 registry (``doc:782-789``). None is
#: implemented yet - the overlay framework does not exist - so ``declared`` is
#: the honest status: the id is reserved and the matrix may key on it, but
#: nothing claims an implementation.
#:
#: The registry is deliberately the ONLY source of valid theme ids. A theme
#: enters it when it has an implementation *and* an evidence trigger, never
#: because it exists conceptually - otherwise the widening invariant's input set
#: grows without bound and every registered theme becomes work for every stock.
THEME_REGISTRY: dict[str, str] = {
    "ai": "declared",
    "tariff": "declared",
    "china": "declared",
    "regulatory": "declared",
    "commodity": "declared",
    "cyber": "declared",
}

#: Every theme the framework will let a caller evaluate. The widening invariant's
#: lower bound.
ALL_REGISTERED_THEMES: frozenset[str] = frozenset(THEME_REGISTRY)

# ---------------------------------------------------------------------------
# The theme priority matrix - declared policy, never a measurement
# ---------------------------------------------------------------------------

HIGH = "HIGH"
MEDIUM = "MEDIUM"
LOW = "LOW"
PRIORITIES = (HIGH, MEDIUM, LOW)

#: Declared policy: canonical sector -> {theme_id: priority}.
#:
#: **NOT** a measurement, a score or a direction. This is the engine declaring a
#: prior, exactly as ``risk_score.RAMPS`` declares one - printed with the output,
#: versioned, revisable, and never presented as a finding.
#:
#: Priority orders *effort*, and nothing else:
#:
#: - ``HIGH`` - evaluate in this pass.
#: - ``MEDIUM`` - evaluate if budget remains.
#: - ``LOW`` - evaluate last; only a cheap trigger scan can promote it.
#:
#: A wrong cell costs a missed *earlier* check, never a missed theme, because
#: :func:`candidate_themes` cannot exclude. Rows are canonical sectors (the
#: eleven ``SPDR_SECTORS`` labels after ``_canonical_sector``); columns are theme
#: ids that exist in ``THEME_REGISTRY``. Both are enforced by
#: :func:`_validate_matrix`, and relevance is categorical - a numeric value is
#: unrepresentable, so no cell can be quoted as a score.
THEME_PRIORITY_MATRIX: dict[str, dict[str, str]] = {
    "technology": {
        "ai": HIGH,
        "cyber": HIGH,
        "china": MEDIUM,
        "regulatory": MEDIUM,
        "commodity": LOW,
        "tariff": LOW,
    },
    "energy": {
        "commodity": HIGH,
        "regulatory": HIGH,
        "ai": MEDIUM,
        "china": MEDIUM,
        "cyber": MEDIUM,
        "tariff": MEDIUM,
    },
    "financials": {
        "cyber": HIGH,
        "regulatory": HIGH,
        "ai": MEDIUM,
        "china": LOW,
        "commodity": LOW,
        "tariff": LOW,
    },
    "health care": {
        "regulatory": HIGH,
        "ai": MEDIUM,
        "china": MEDIUM,
        "cyber": MEDIUM,
        "tariff": MEDIUM,
        "commodity": LOW,
    },
    "industrials": {
        "china": HIGH,
        "tariff": HIGH,
        "ai": MEDIUM,
        "commodity": MEDIUM,
        "cyber": MEDIUM,
        "regulatory": MEDIUM,
    },
    "consumer disc.": {
        "china": HIGH,
        "tariff": HIGH,
        "ai": MEDIUM,
        "regulatory": MEDIUM,
        "commodity": LOW,
        "cyber": LOW,
    },
    "consumer staples": {
        "tariff": HIGH,
        "china": MEDIUM,
        "commodity": MEDIUM,
        "regulatory": MEDIUM,
        "ai": LOW,
        "cyber": LOW,
    },
    "materials": {
        "china": HIGH,
        "commodity": HIGH,
        "tariff": HIGH,
        "regulatory": MEDIUM,
        "ai": LOW,
        "cyber": LOW,
    },
    "real estate": {
        "regulatory": HIGH,
        "ai": MEDIUM,
        "commodity": MEDIUM,
        "tariff": MEDIUM,
        "china": LOW,
        "cyber": LOW,
    },
    "utilities": {
        "ai": HIGH,
        "regulatory": HIGH,
        "commodity": MEDIUM,
        "cyber": MEDIUM,
        "china": LOW,
        "tariff": LOW,
    },
    "communications": {
        "ai": HIGH,
        "cyber": HIGH,
        "regulatory": HIGH,
        "china": MEDIUM,
        "tariff": LOW,
        "commodity": LOW,
    },
}

#: The declared policy basis for every cell, keyed ``"<sector>.<theme>"``.
#:
#: This is **policy, not evidence**. It states why the engine holds the prior; it
#: is not a factual observation about any company. Keeping the two apart is the
#: point: a future reader must not mistake ``ai=HIGH`` for something measured
#: about the company in front of them. A cell without a basis does not belong in
#: the matrix, and :func:`_validate_matrix` enforces that.
THEME_PRIORITY_BASIS: dict[str, str] = {
    "technology.ai": "software and services are directly exposed to AI substitution and to AI-driven demand",
    "technology.cyber": "security posture is a direct operating risk for software and platform businesses",
    "technology.china": "supply chains and end markets carry material China concentration",
    "technology.regulatory": "data, privacy and platform rules bind the core business model",
    "technology.commodity": "input costs are immaterial to a software-heavy cost base",
    "technology.tariff": "tariffs affect hardware flows more than software revenue",
    "energy.commodity": "realised prices are the primary driver of earnings",
    "energy.regulatory": "emissions, permitting and methane rules bind the operating model",
    "energy.ai": "data-centre electricity demand is a demand-side force on the sector",
    "energy.china": "import and export flows are materially exposed to China demand",
    "energy.cyber": "operational technology and grid assets are attack surface",
    "energy.tariff": "tariffs move refined product and equipment trade",
    "financials.cyber": "payments, custody and ledger integrity are the core operating risk",
    "financials.regulatory": "capital, conduct and rate rules define the business model",
    "financials.ai": "automation changes cost-to-serve and distribution economics",
    "financials.china": "cross-border exposure is bounded by licensing and sanctions",
    "financials.commodity": "commodity prices reach the sector only indirectly",
    "financials.tariff": "tariffs reach the sector only through the real economy",
    "health care.regulatory": "approval, pricing and reimbursement rules dominate economics",
    "health care.ai": "discovery and trial productivity are exposed to AI leverage",
    "health care.china": "active ingredient and device sourcing is materially China-linked",
    "health care.cyber": "clinical and patient data systems are regulated attack surface",
    "health care.tariff": "device and ingredient trade flows are tariff-exposed",
    "health care.commodity": "input commodities are a small share of the cost base",
    "industrials.china": "component sourcing and end-market demand are China-linked",
    "industrials.tariff": "tariffs move input costs and cross-border demand directly",
    "industrials.ai": "automation and robotics change the production cost curve",
    "industrials.commodity": "steel, metals and energy are direct input costs",
    "industrials.cyber": "factory and logistics systems are operational attack surface",
    "industrials.regulatory": "safety, emissions and procurement rules apply",
    "consumer disc..china": "sourcing and consumer demand are both materially China-linked",
    "consumer disc..tariff": "tariffs lift landed cost on imported goods directly",
    "consumer disc..ai": "demand forecasting and channel economics are AI-exposed",
    "consumer disc..regulatory": "consumer protection and product rules apply",
    "consumer disc..commodity": "commodity input costs are largely passed through",
    "consumer disc..cyber": "customer data breaches carry reputational cost",
    "consumer staples.tariff": "packaging and imported input costs are tariff-exposed",
    "consumer staples.china": "sourcing concentration creates supply exposure",
    "consumer staples.commodity": "agricultural and packaging inputs move margins",
    "consumer staples.regulatory": "food safety and labelling rules apply",
    "consumer staples.ai": "demand is stable; AI leverage on the cost base is modest",
    "consumer staples.cyber": "data exposure is largely limited to retail channels",
    "materials.china": "Chinese demand sets the clearing price for several commodities",
    "materials.commodity": "the product IS the commodity; price is the business",
    "materials.tariff": "trade barriers redirect flows and set regional premia",
    "materials.regulatory": "extraction, emissions and land rules apply",
    "materials.ai": "AI has little direct leverage on a physical conversion process",
    "materials.cyber": "industrial control systems are exposed but not core-demand linked",
    "real estate.regulatory": "rates, zoning and tax rules dominate valuation",
    "real estate.ai": "data-centre and power demand is reshaping asset demand",
    "real estate.commodity": "construction input costs move development economics",
    "real estate.tariff": "building material costs are tariff-exposed",
    "real estate.china": "cross-border capital flows are constrained",
    "real estate.cyber": "building systems exposure is operational, not demand-linked",
    "utilities.ai": "data-centre load growth is the sector's demand-side force",
    "utilities.regulatory": "rate cases and grid rules define allowed returns",
    "utilities.commodity": "fuel cost is passed through under most rate structures",
    "utilities.cyber": "grid control systems are critical-infrastructure attack surface",
    "utilities.china": "the sector is domestic; cross-border exposure is minimal",
    "utilities.tariff": "tariffs reach equipment sourcing only indirectly",
    "communications.ai": "network and content economics are directly AI-exposed",
    "communications.cyber": "network integrity is the core operating risk",
    "communications.regulatory": "spectrum, pricing and content rules apply",
    "communications.china": "equipment sourcing carries China exposure",
    "communications.tariff": "equipment trade is tariff-exposed",
    "communications.commodity": "commodity inputs are immaterial to the cost base",
}

#: The matrix's declared version. A prior without a version is not auditable, so
#: this travels with every rendered basis. A cell edit requires a bump.
MATRIX_VERSION = "2026-09-22.1"


def _canonical_rows() -> frozenset[str]:
    """The eleven canonical sector labels, derived from ``SPDR_SECTORS``."""
    return frozenset(_canonical_sector(name) for name in SPDR_SECTORS.values())


class MatrixError(ValueError):
    """Raised when the declared matrix is not well formed."""


def _validate_matrix(
    matrix: Mapping[str, Mapping[str, Any]] | None = None,
    basis: Mapping[str, str] | None = None,
) -> None:
    """Raise unless the matrix is well formed.

    Mirrors ``factor_schema.validate_schema``: a declared table that can silently
    grow a second vocabulary is worse than no table. Enforced here:

    - every row key is a canonical sector - no row is missing, because a missing
      row means "no prior" and that must be an explicit choice, not an accident;
    - every column key is a theme id in ``THEME_REGISTRY``;
    - every cell is one of :data:`PRIORITIES` - a numeric or free-text relevance
      is unrepresentable, so no cell can be read as a score;
    - every cell states its declared policy basis;
    - the basis names no cell the matrix does not have.
    """
    matrix = THEME_PRIORITY_MATRIX if matrix is None else matrix
    basis = THEME_PRIORITY_BASIS if basis is None else basis

    rows, expected = set(matrix), set(_canonical_rows())
    if rows != expected:
        missing = sorted(expected - rows)
        unknown = sorted(rows - expected)
        raise MatrixError(
            f"matrix rows must be exactly the canonical sectors. "
            f"missing: {missing}; unknown: {unknown}"
        )
    for sector, cells in matrix.items():
        if set(cells) != set(ALL_REGISTERED_THEMES):
            raise MatrixError(
                f"{sector!r}: columns must be exactly the registered themes. "
                f"missing: {sorted(ALL_REGISTERED_THEMES - set(cells))}; "
                f"unknown: {sorted(set(cells) - ALL_REGISTERED_THEMES)}"
            )
        for theme, priority in cells.items():
            if priority not in PRIORITIES:
                raise MatrixError(
                    f"{sector}.{theme}: priority {priority!r} is not one of "
                    f"{PRIORITIES} - relevance is categorical, never numeric"
                )
            if not str(basis.get(f"{sector}.{theme}") or "").strip():
                raise MatrixError(
                    f"{sector}.{theme}: no declared policy basis - a cell that "
                    "cannot state its rationale does not belong in the matrix"
                )
    extra = sorted(set(basis) - {f"{s}.{t}" for s in matrix for t in matrix[s]})
    if extra:
        raise MatrixError(f"basis entries for cells the matrix does not have: {extra}")


@functools.lru_cache(maxsize=1)
def _matrix_checked() -> bool:
    """Validate the matrix once per process, lazily.

    A bad matrix must fail loudly in the run that uses it rather than silently
    returning a prior nobody declared. Cached because the check is a property of
    the module's own constants, not of the call.
    """
    _validate_matrix()
    return True


# ---------------------------------------------------------------------------
# The context object
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SecurityContext:
    """What kind of company this is - deterministic metadata, with provenance.

    Every field is ``None``-able, and a context with everything ``None`` is
    valid: it means "unclassified", not "error". Per the widening rule an
    unclassified company yields the full candidate set.

    ``sector_source`` names the source that produced ``sector_raw``. In this
    repo that is ``resolve_instrument_identity``, whose single vendor read is
    Yahoo - so ``"yfinance"`` is the only value this layer can produce. The field
    exists because a sector string without its source is unusable, and because
    the source is the thing that tells a reader which taxonomy they hold.

    **There is deliberately no cross-source agreement field.** The design's
    first draft carried ``agreement`` / ``disagreement`` over "two sources that
    canonicalize differently". With one reachable sector source those states are
    unreachable: the enum could only ever be ``single_source`` or ``unknown``,
    the disagreement dict could only ever be empty, and a state that cannot occur
    is worse than a named absence - it reads as a check that ran and passed.
    ``sec_sic`` is kept as an **independent regulatory signal**, recorded and
    never compared, because comparing it would need the SIC-to-sector crosswalk
    this layer explicitly refuses to build.
    """

    symbol: str
    company_name: str | None = None

    #: Verbatim from the provider - the value is evidence, the canonical label
    #: below is derived.
    sector_raw: str | None = None
    sector_source: str | None = None
    industry_raw: str | None = None
    industry_source: str | None = None

    #: ``industry_raw`` mapped through the SAME ``_canonical_sector``. Named for
    #: what it is: an industry value bridged to a *sector*, not a normalized
    #: industry. The repo has no industry vocabulary and does not claim one.
    industry_implied_sector: str | None = None

    #: The repo's own canonical vocabulary, and its SPDR key.
    sector_canonical: str | None = None
    spdr_etf: str | None = None

    #: Free, independent, regulatory. Captured opportunistically from a payload
    #: an earlier step already fetched; never fetched for this purpose, and
    #: never mapped to a sector.
    sec_sic: str | None = None
    sec_sic_description: str | None = None

    #: ``strategies.security_type.classify_security``. All three of its states
    #: are reachable: ``operating_company`` needs a provider ``quote_type`` of
    #: ``EQUITY``, and ``UNKNOWN`` is its non-fund fallback when there is no
    #: evidence at all. A fund that escapes both the universe lists and the
    #: wrapper patterns still reads ``UNKNOWN``, which is honest - and either
    #: way the caller branches only on ``ETF``.
    security_type: str | None = None

    #: The run's own date. Passed in, never read from the clock, so the same
    #: inputs produce the same context.
    classification_as_of: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Plain JSON-able form, for the run card."""
        return {k: v for k, v in asdict(self).items() if v is not None}


def build_security_context(
    ticker: str,
    *,
    identity: Mapping[str, Any] | None = None,
    sec_sic: str | None = None,
    sec_sic_description: str | None = None,
    as_of: str | None = None,
) -> SecurityContext:
    """Build the context for one ticker, from data the run already holds.

    Makes **no** network call of its own. ``identity`` defaults to
    ``resolve_instrument_identity`` (already ``lru_cache``d, so it is fetched at
    most once per ticker per process); the SEC fields are passed in by a caller
    that already fetched a submissions payload, and are ``None`` when it did not.

    Deliberately tolerant: a missing identity yields an unclassified context
    rather than an exception, because "unclassified" is a supported answer.
    """
    _matrix_checked()

    if identity is None:
        try:
            from tradingagents.agents.utils.agent_utils import resolve_instrument_identity

            identity = resolve_instrument_identity(ticker) or {}
        except Exception:  # noqa: BLE001 - identity is best-effort by contract
            identity = {}

    company_name = identity.get("company_name") or None
    sector_raw = identity.get("sector") or None
    industry_raw = identity.get("industry") or None

    # The source is named only when a value exists to attribute it to. Yahoo is
    # the only producer on that path (§module docstring).
    sector_source = "yfinance" if sector_raw else None
    industry_source = "yfinance" if industry_raw else None

    sector_canonical = _canonical_sector(sector_raw) if sector_raw else None
    industry_implied = _canonical_sector(industry_raw) if industry_raw else None
    spdr_etf = sector_group_of(sector_raw) if sector_raw else None

    security_type: str | None = None
    try:
        from tradingagents.strategies.security_type import classify_security

        security_type = (classify_security(ticker, identity=identity) or {}).get(
            "security_type"
        )
    except Exception:  # noqa: BLE001 - classification is advisory
        security_type = None

    return SecurityContext(
        symbol=(ticker or "").strip().upper(),
        company_name=company_name,
        sector_raw=sector_raw,
        sector_source=sector_source,
        industry_raw=industry_raw,
        industry_source=industry_source,
        industry_implied_sector=industry_implied,
        sector_canonical=sector_canonical,
        spdr_etf=spdr_etf,
        sec_sic=str(sec_sic) if sec_sic else None,
        sec_sic_description=sec_sic_description or None,
        security_type=security_type,
        classification_as_of=as_of or None,
    )


# ---------------------------------------------------------------------------
# The widening invariant
# ---------------------------------------------------------------------------


def _matrix_candidates(sector_canonical: str | None) -> frozenset[str]:
    """Themes the matrix holds a positive prior for (``HIGH`` or ``MEDIUM``).

    ``LOW`` cells are deliberately excluded and an unknown sector yields the
    empty set: this is the *ordering* contribution only. A prior that could
    exclude would be a decision, and this layer is not permitted to make one.
    """
    cells = THEME_PRIORITY_MATRIX.get((sector_canonical or "").strip().lower())
    if not cells:
        return frozenset()
    return frozenset(t for t, p in cells.items() if p in (HIGH, MEDIUM))


def candidate_themes(context: SecurityContext | None = None) -> frozenset[str]:
    """Every theme the framework will evaluate for this company.

    The union form is load-bearing, not cosmetic: it makes
    ``ALL_REGISTERED_THEMES <= candidate_themes(...)`` a structural fact rather
    than a convention, so the widening invariant holds for *every* sector
    including an unknown one, and any future exclusion path breaks the property
    test immediately.

    The result is therefore always all registered themes. That is the design:
    the matrix orders effort, it does not admit or reject. See
    :func:`theme_priority_order` for the ordering, which is the matrix's real
    contribution.
    """
    sector = context.sector_canonical if context is not None else None
    return frozenset(ALL_REGISTERED_THEMES) | _matrix_candidates(sector)


def theme_priority_order(context: SecurityContext | None = None) -> tuple[str, ...]:
    """The registered themes, ordered by the declared prior.

    ``HIGH`` first, then ``MEDIUM``, then ``LOW``. Ties break on the theme id so
    the order is deterministic and reproducible; a sector with no row falls
    through to the plain id order (no prior).

    This is what the matrix is actually for: with a budget of a few overlays, it
    says which to evaluate *first*. It never says which to skip.
    """
    sector = (context.sector_canonical if context is not None else None) or ""
    cells = THEME_PRIORITY_MATRIX.get(sector.strip().lower(), {})
    rank = {HIGH: 0, MEDIUM: 1, LOW: 2}
    return tuple(
        sorted(ALL_REGISTERED_THEMES, key=lambda t: (rank.get(cells.get(t, ""), 3), t))
    )


# ---------------------------------------------------------------------------
# Rendering - one line, deterministic
# ---------------------------------------------------------------------------


def render_security_context_basis(context: SecurityContext) -> str:
    """One deterministic line stating the classification and its prior.

    **Deliberately one line.** It is read by analysts, so it is kept to a single
    bounded sentence: the structured detail lives in the run card, not in an
    LLM's context. Three properties are non-negotiable and each is tested:

    1. the source is always named when a value exists - a sector without its
       source is unusable;
    2. the matrix version is always named, or the prior is not auditable;
    3. the widening disclaimer is always present, so no reader mistakes the
       prior for a gate.
    """
    parts: list[str] = []
    if context.sector_raw:
        parts.append(f'sector={context.sector_raw} (source: {context.sector_source})')
    else:
        parts.append("sector=unclassified")
    if context.sector_canonical:
        parts.append(f"canonical={context.sector_canonical}")
    if context.spdr_etf:
        parts.append(f"spdr={context.spdr_etf}")
    if context.industry_raw:
        parts.append(f'industry={context.industry_raw} (source: {context.industry_source})')
    if context.sec_sic:
        parts.append(f"sec_sic={context.sec_sic} (independent, not compared)")
    if context.security_type:
        parts.append(f"type={context.security_type}")

    order = theme_priority_order(context)
    cells = THEME_PRIORITY_MATRIX.get((context.sector_canonical or "").strip().lower(), {})
    prior = ", ".join(f"{t}={cells.get(t, 'no prior')}" for t in order)

    return (
        f"Security context: {'; '.join(parts)}. "
        f"Candidate themes: {len(candidate_themes(context))} registered "
        f"(prior order, {MATRIX_VERSION}: {prior}). "
        "This is a declared prior, not a measurement, and it does not gate: "
        "every registered theme remains a candidate."
    )

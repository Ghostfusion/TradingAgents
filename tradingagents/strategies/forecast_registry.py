"""The forecast registry - one AUTHORITATIVE producer per forecast key (plan FL-2).

A **manifest**, not a calculator. It reads no config, computes nothing, imports
no vendor and no optional dependency, and it declares - in one place - which
symbol is the authoritative producer of each forecast key:

    (target.name, entity_scope, frequency, horizon_steps)

Why a registry exists at all (design doc §7.2 rule 2, invariant 8)
-----------------------------------------------------------------
A forecast is a *derived quantity*, so the repo's one-authoritative-producer
rule binds it exactly as it binds a score. The failure this prevents is not a
missing forecast but **two disagreeing ones**: two regime labels, two realized
vols for the same name and horizon, are indistinguishable from a genuine change.
The uniqueness rule binds the **pool/selector**, never its members - several
candidate models may each emit a value for the same target (FD-1 §3.2), which is
why V1's pool is legal here (design doc §3.2/§7.2 rule 2).

What a row is *not*
-------------------
``implementation_ref`` is a **location**, written ``strategies/<module>.py::<symbol>``
and resolved by the fixed transform of design doc §7.2 rule 8: strip ``.py``, map
``/`` to ``.``, prefix ``tradingagents.``, split on ``::``. The ``tradingagents.``
prefix is mandatory at resolution time - a *top-level* ``strategies/`` directory
also exists and it is the docs vault (no ``.py``, no ``__init__.py``), so the bare
``strategies.long_memory`` does not import. ``producer_id`` is the stable
semantic owner and is **never** a code path: code paths move during refactoring,
the owner does not (rule 8).

Coverage, stated honestly
-------------------------
The seed is **not** a proof of completeness, and it excludes the contemporaneous
*measurements* the engine owns (``memory_parameter``, ``bipower_proxy``,
``hmm_filtered_regime``): rule 6 says a state read is not a forecast, and the
design doc's target vocabulary (§7.3) does not declare them. They become
forecast keys only if a producer forecasts them.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass

from tradingagents.strategies import forecast_contract as _contract


class ForecastRegistryError(ValueError):
    """The registry declared something that cannot be true of the tree."""


@dataclass(frozen=True, kw_only=True)
class RegistryRow:
    """One declared authoritative producer for one forecast key.

    ``status`` is the declaration's own state, from the contract's vocabulary
    (design doc §7.2 rule 3): ``ok`` means a producer is authorized for the key
    and its gate - when it names one - is the switch that turns production on,
    and the row must name the benchmark it will be scored against; ``declined``
    means the engine does not produce the quantity **by policy**, and the row is
    then a *cited refusal* - no symbol, no gate, no benchmark, and a
    ``reason_code`` plus the citation that makes it reversible. ``gate=None`` on
    an ``ok`` row means the producer has no switch of its own.
    """

    target: _contract.TargetRef
    entity_scope: str
    frequency: str
    horizon_steps: int
    status: str
    producer_id: str | None = None
    implementation_ref: str | None = None
    gate: str | None = None
    benchmark_ref: str | None = None
    reason_code: str | None = None
    citation: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.target, _contract.TargetRef):
            raise ForecastRegistryError(
                f"RegistryRow.target must be a TargetRef, got {type(self.target).__name__}"
            )
        if self.status not in _contract.FORECAST_STATUSES:
            raise ForecastRegistryError(
                f"RegistryRow.status must be one of {list(_contract.FORECAST_STATUSES)}, "
                f"got {self.status!r}"
            )
        if self.horizon_steps < 1:
            raise ForecastRegistryError(
                f"RegistryRow.horizon_steps must be >= 1, got {self.horizon_steps} - a state read "
                "is not a forecast (design doc §7.2 rule 6)"
            )
        if self.status == "declined":
            # A declined row is a CITED POLICY STATEMENT, not a producer (design doc
            # §7.2 rule 3, plan FL-3). It names no symbol, no gate and no benchmark -
            # nothing produces it - and it must say WHY: an absent row is an
            # invitation, a cited refusal is a decision.
            missing = [
                name
                for name, value in (("reason_code", self.reason_code), ("citation", self.citation))
                if not (value or "").strip()
            ]
            if missing:
                raise ForecastRegistryError(
                    f"RegistryRow {self.target.name!r} is declined but names no {missing}: an uncited "
                    "refusal is only an omission (design doc §7.2 rule 3)"
                )
            if self.reason_code not in _contract.DECLINED_REASON_CODES:
                raise ForecastRegistryError(
                    f"RegistryRow {self.target.name!r}: reason_code {self.reason_code!r} is not in the "
                    f"closed declined vocabulary {list(_contract.DECLINED_REASON_CODES)} - free prose "
                    "is not a code (design doc §7.2 rules 3-4)"
                )
            if self.producer_id or self.implementation_ref or self.gate or self.benchmark_ref:
                raise ForecastRegistryError(
                    f"RegistryRow {self.target.name!r}: a declined row has no producer, no gate and no "
                    "benchmark - nothing produces it and nothing scores it (design doc §7.2 rule 3)"
                )
            return
        if not self.producer_id or not self.implementation_ref:
            raise ForecastRegistryError(
                f"RegistryRow {self.target.name!r}: a non-declined row must name BOTH its stable "
                "producer_id and its implementation_ref (design doc §7.2 rule 8)"
            )
        if not self.benchmark_ref:
            raise ForecastRegistryError(
                f"RegistryRow {self.target.name!r}: a non-declined row must name the benchmark it "
                "will be scored against - a forecast does not get credit for producing a number "
                "(design doc §8.2, plan FL-6)"
            )
        if self.benchmark_ref not in BENCHMARK_REFS:
            raise ForecastRegistryError(
                f"RegistryRow {self.target.name!r}: benchmark_ref {self.benchmark_ref!r} is not in "
                "the declared benchmark set - the family's benchmark is declared once, in "
                "BENCHMARK_BY_FAMILY (design doc §8.2)"
            )
        if self.reason_code is not None or self.citation is not None:
            raise ForecastRegistryError(
                f"RegistryRow {self.target.name!r}: only a declined row carries a reason_code or a "
                "citation - a produced forecast is not a refusal (design doc §7.2 rule 3)"
            )
        if ".py" in self.producer_id or "::" in self.producer_id:
            raise ForecastRegistryError(
                f"RegistryRow.producer_id {self.producer_id!r} is a code path; it is the stable "
                "semantic owner (design doc §7.2 rule 8)"
            )
        try:
            _module_and_attr(self.implementation_ref)
        except ForecastRegistryError as exc:
            raise ForecastRegistryError(
                f"RegistryRow.implementation_ref {self.implementation_ref!r} is not "
                f"'strategies/<module>.py::<symbol>': {exc} (design doc §7.2 rule 8)"
            ) from exc
        if self.gate is not None and not self.gate.startswith("enable_"):
            raise ForecastRegistryError(
                f"RegistryRow.gate {self.gate!r} is not an `enable_*` config switch"
            )


def _module_and_attr(implementation_ref: str) -> tuple[str, str]:
    """Apply the §7.2 rule 8 transform; return ``(module, attribute)``."""
    path, sep, symbol = implementation_ref.partition("::")
    if not sep or not symbol or not path.endswith(".py"):
        raise ForecastRegistryError(
            f"implementation_ref {implementation_ref!r} is not '<path>.py::<symbol>'"
        )
    module = "tradingagents." + path[: -len(".py")].replace("/", ".")
    return module, symbol


# ---------------------------------------------------------------------------
# The declared benchmarks (design doc §8.2, plan FL-6)
# ---------------------------------------------------------------------------

#: One declared benchmark set per target family. **A forecast does not get credit
#: for producing a number** (design doc §8.2): the family names what it must beat
#: before it may be scored, and ``return_rank``'s two baselines are deliberately
#: separate hypotheses rather than one line.
BENCHMARK_BY_FAMILY = {
    "realized_volatility": (
        "volatility.har_rv",
        "volatility.naive_trailing_realized",
        "volatility.garch11",
    ),
    "volatility": ("volatility.har_rv", "volatility.naive_trailing_realized"),
    "variance": ("volatility.har_rv", "volatility.naive_trailing_realized"),
    "volatility_rank": ("rank.cross_sectional_persistence", "rank.cross_sectional_mean"),
    "absolute_return": (
        "return.zero",
        "return.expanding_mean",
        "return.rolling_mean",
    ),
    "relative_return": ("return.sector_neutral_factor",),
    "residual_return": ("return.beta_neutral_residual",),
    "return_rank": ("rank.cross_sectional_persistence", "rank.cross_sectional_mean"),
    "regime_probability": ("regime.sticky_markov",),
    "regime_stress_probability": ("regime.sticky_markov",),
}

#: The floor for any interval: `conformal.iid_interval`'s own module comment says
#: to read the REALIZED coverage, never the nominal level.
INTERVAL_BENCHMARK = "interval.conformal_iid_floor"

#: Every declared benchmark ref, in one place, so a row cannot invent one.
BENCHMARK_REFS = frozenset(
    {ref for refs in BENCHMARK_BY_FAMILY.values() for ref in refs} | {INTERVAL_BENCHMARK}
)

#: Targets whose claims are **directional** - they must carry both ceilings, not
#: only a benchmark: the H-theme's out-of-sample R² ceiling (`2602.07841`) and
#: `H4`'s base-rate ceiling. Binding them is a declaration, so a directional claim
#: cannot be scored without both in view.
DIRECTIONAL_TARGETS = ("absolute_return", "relative_return", "residual_return", "return_rank")

DIRECTIONAL_CEILINGS = {
    "out_of_sample_r2": "2602.07841",
    "base_rate": "H4",
}


# ---------------------------------------------------------------------------
# The seed
# ---------------------------------------------------------------------------

#: The declared authoritative producers. Every ``implementation_ref`` is
#: resolved against the live tree by ``tests/test_forecast_registry.py`` - a
#: renamed symbol must fail a build, not drift quietly (plan §8 risk 6).
FORECAST_REGISTRY: tuple[RegistryRow, ...] = (
    RegistryRow(
        target=_contract.TargetRef(
            name="realized_volatility",
            definition=(
                "next-session realized VARIANCE: HAR-RV fitted on RV = squared close-to-close "
                "log returns (RV_{t+1} = b0 + b_d RV_t + b_w RV_w + b_m RV_m), with the GPH "
                "memory parameter reported beside the forecast"
            ),
            definition_version="realized_volatility.v2",
            unit="variance",
            annualization=None,
        ),
        entity_scope="single_asset",
        frequency="1d",
        horizon_steps=1,
        producer_id="long_memory.realized_volatility.v1",
        implementation_ref="strategies/long_memory.py::rv_forecast",
        gate="enable_long_memory",
        status="ok",
        benchmark_ref="volatility.har_rv",
    ),
    RegistryRow(
        target=_contract.TargetRef(
            name="regime_stress_probability",
            definition=(
                "calibrated one-month-ahead probability the equal-weight panel enters stress "
                "(the panel's own bottom FS_STRESS_QUANTILE of monthly returns), from the "
                "cross-sectional dispersion / downside-share / skew trio"
            ),
            definition_version="regime_stress_probability.v1",
            unit="probability",
            annualization=None,
        ),
        entity_scope="index",
        frequency="1d",
        # market_breadth._fs_horizon(1)["sessions"] - MONTH_SESSIONS = 21 sessions.
        horizon_steps=21,
        producer_id="market_breadth.regime_stress_probability.v1",
        implementation_ref="strategies/market_breadth.py::forward_stress_probability",
        gate="enable_forward_stress_probability",
        status="ok",
        benchmark_ref="regime.sticky_markov",
    ),
    # FL-3 - the return families ship DECLINED. A cited, reversible policy
    # statement, never a number: the engine has not authorized the target, and an
    # absent row would be an invitation rather than a decision (design doc §7.2
    # rule 3, §11.1).
    RegistryRow(
        target=_contract.TargetRef(
            name="absolute_return",
            definition=(
                "the LEVEL of the forward return over one session - the quantity whose "
                "out-of-sample predictability is the contested one"
            ),
            definition_version="absolute_return.v1",
            unit="pct",
            annualization=None,
        ),
        entity_scope="single_asset",
        frequency="1d",
        horizon_steps=1,
        status="declined",
        reason_code="RETURN_LEVEL_NOT_ADMITTED",
        citation=(
            "Hjalmarsson (2006, Fed IFDP 855): out-of-sample exercises fail to DETECT "
            "predictability even under the true DGP; Goyal/Welch/Zafirov (2021/2024, RFS 37(11)): "
            "a majority of variables no longer have empirical support even in-sample"
        ),
    ),
    RegistryRow(
        target=_contract.TargetRef(
            name="return_rank",
            definition=(
                "the cross-sectional rank of the forward 22-session return - the rank that must be "
                "distinguished from the rank of its volatility"
            ),
            definition_version="return_rank.v1",
            unit="rank_decile",
            annualization=None,
        ),
        entity_scope="cross_section",
        frequency="1d",
        horizon_steps=22,
        status="declined",
        reason_code="RETURN_RANK_NOT_ADMITTED",
        citation=(
            "2607.27461: a 0.007 log-likelihood gain for the return rank against 0.108 for the "
            "volatility rank - ranking returns is not ranking their volatility"
        ),
    ),
)

#: Declared pool MEMBERS - candidates, never authoritative (FD-1 §3.2). They may
#: share an (target, scope, frequency, horizon) with the registry and must not
#: trip the uniqueness gate; only the pool/selector publishes.
#: Empty today: V1's volatility forecast pool is blocked (design doc §10 - the
#: pool and its member list belong to ``design_vol_surface_and_vrp.md`` §V1).
CANDIDATE_MEMBERS: tuple[RegistryRow, ...] = ()


# ---------------------------------------------------------------------------
# Keys, resolution, and the uniqueness check
# ---------------------------------------------------------------------------


def _key(row: RegistryRow) -> tuple[str, str, str, int]:
    return (row.target.name, row.entity_scope, row.frequency, row.horizon_steps)


def _resolve(implementation_ref: str) -> object:
    """Import the declared symbol; raise naming key and path when it is gone."""
    module_name, symbol = _module_and_attr(implementation_ref)
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:  # pragma: no cover - only on a real rename
        raise ForecastRegistryError(
            f"{implementation_ref!r} does not import: {module_name} is missing ({exc})"
        ) from exc
    try:
        return getattr(module, symbol)
    except AttributeError as exc:  # pragma: no cover - only on a real rename
        raise ForecastRegistryError(
            f"{implementation_ref!r} resolves to {module_name}, which has no {symbol!r} - the "
            "producer was renamed or removed and the registry must be corrected"
        ) from exc


def _duplicate_keys(rows) -> dict[tuple[str, str, str, int], int]:
    """Keys carried by more than one row, with their row counts."""
    counts: dict[tuple[str, str, str, int], int] = {}
    for row in rows:
        counts[_key(row)] = counts.get(_key(row), 0) + 1
    return {key: n for key, n in counts.items() if n > 1}


def _candidate_collisions(authoritative, candidates) -> list[tuple[str, str, str, int]]:
    """Candidate keys that ALSO carry an authoritative producer.

    Not an error - a candidate is allowed to share a key with the pool that
    publishes it (FD-1 §3.2) - but a *collision with a second authority* is:
    this returns the keys a caller should inspect against ``_duplicate_keys``.
    """
    auth_keys = {_key(row) for row in authoritative}
    return sorted({_key(row) for row in candidates if _key(row) in auth_keys})


# ---------------------------------------------------------------------------
# The run-card block (FL-2's first caller)
# ---------------------------------------------------------------------------


def forecast_registry_block() -> dict:
    """The registry as a JSON-able run-card block.

    A **declaration**, so it is always present and carries no gate of its own: a
    reader of any card can see which producer owns which forecast key, and which
    keys are refused by policy. It computes nothing the registry does not
    already state - no vendor read, no fit, no config.
    """
    return {
        "rows": [
            {
                "key": {
                    "target_name": row.target.name,
                    "entity_scope": row.entity_scope,
                    "frequency": row.frequency,
                    "horizon_steps": row.horizon_steps,
                },
                "unit": row.target.unit,
                "definition_version": row.target.definition_version,
                "producer_id": row.producer_id,
                "implementation_ref": row.implementation_ref,
                "gate": row.gate,
                "status": row.status,
                "benchmark_ref": row.benchmark_ref,
                "reason_code": row.reason_code,
                "citation": row.citation,
            }
            for row in FORECAST_REGISTRY
        ],
        "candidate_members": [
            {
                "key": {
                    "target_name": row.target.name,
                    "entity_scope": row.entity_scope,
                    "frequency": row.frequency,
                    "horizon_steps": row.horizon_steps,
                },
                "producer_id": row.producer_id,
                "implementation_ref": row.implementation_ref,
            }
            for row in CANDIDATE_MEMBERS
        ],
        "n_rows": len(FORECAST_REGISTRY),
        "n_candidate_members": len(CANDIDATE_MEMBERS),
        "basis": (
            "declared authoritatively; one producer per (target_name, entity_scope, frequency, "
            "horizon_steps); candidates are pool members and are never authoritative "
            "(design doc §7.2 rule 2, FD-1 §3.2)"
        ),
    }


__all__ = [
    "BENCHMARK_BY_FAMILY",
    "BENCHMARK_REFS",
    "CANDIDATE_MEMBERS",
    "DIRECTIONAL_CEILINGS",
    "DIRECTIONAL_TARGETS",
    "FORECAST_REGISTRY",
    "ForecastRegistryError",
    "INTERVAL_BENCHMARK",
    "RegistryRow",
    "forecast_registry_block",
]

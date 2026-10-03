"""Publish a registry-declared producer as a ``ForecastRecord`` (plan FL-9).

The contract (``forecast_contract.py``, plan FL-1) says what a forecast record
must contain. This module is what can actually fill one in, and it exists
because FL-5's ledger adapter had neither a caller nor a record to write: a
``ForecastRecord`` requires mandatory ``Provenance`` (design doc §7.2 rule 9)
and no producer emitted one.

**It is not a producer, and it makes no forecast.** Every number it publishes
comes from the producer the registry already declares
(``forecast_registry.FORECAST_REGISTRY``), and it re-declares no target, scope,
frequency, horizon, gate or symbol of its own - those are read from the row, so
a record and the registry cannot drift apart.

The rule that shapes the signature: **an identity is never invented.**
``data_snapshot_id``, ``calendar_id``, ``price_caliber`` and ``code_revision``
each come from a real source, and when a real source is absent the publisher
raises :class:`PublishRefusal` rather than filling the field with something
plausible. A fabricated ``data_snapshot_id`` makes a record reproducible against
nothing, which is the exact failure provenance exists to prevent.

Where each mandatory field comes from:

``data_snapshot_id``
    The caller's own evidence identity:
    ``agents.utils.prompt_metrics.snapshot_identity(cfg, state)`` yields
    ``snapshot_id`` and a content-addressed ``data_snapshot_hash`` that already
    covers the ticker, the trade date and the price caliber.
``calendar_id``
    ``CALENDAR_BY_MARKET`` - a declared table. A market that is not in it yields
    no record.
``adjusted_prices``
    ``dataflows.market_router.price_caliber_for`` - the repo's verified table,
    the same one its tools attach to a vendor result. For a **return** series
    the flag means "does the return carry dividends": a split changes the price
    scale, not the return, so ``split_adjusted`` and ``raw`` are both ``False``
    and only ``adjusted`` is ``True``. ``unknown`` yields no record, because this
    repo never assumes "adjusted".
``padded``
    ``False``, and that is a fact about this producer rather than a default:
    ``rv_forecast`` drops non-finite pairs together with their labels and
    refuses below ``HAR_MIN_OBS``; it never pads a window to reach the
    requested length.
``missing_obs`` / ``imputed_obs``
    Non-finite observations the input carried inside the requested window, and
    ``0`` - the engine drops, it never imputes.
``parameter_hash``
    The hash of the regressor set and the fitted coefficients the forecast
    depended on. "No fit happened" is a distinct recorded value, never ``""``.
``training_start`` / ``training_end``
    The first and last label of the window actually used. A series whose labels
    are not datable yields no record: a timestamp field cannot be honestly
    filled from an integer position.
``code_revision``
    ``execution_contract.git_sha()`` unless the caller passes one - an offline
    refit artefact carries its own.
``feature_version`` / ``model_version``
    The producer's declared definition versions. §7.1 makes a redefinition a new
    target, so these are the producer's to state.
"""

from __future__ import annotations

import hashlib
import json as _json
import math
from datetime import date, datetime

from tradingagents.strategies import forecast_contract as _contract, forecast_registry as _registry

__all__ = [
    "CALENDAR_BY_MARKET",
    "FEATURE_VERSION",
    "MODEL_VERSION",
    "PublishRefusal",
    "RV_PRODUCER_ID",
    "publish_realized_volatility_forecast",
]

#: The producer this publisher knows how to publish. The identity itself - the
#: target, the scope, the frequency, the horizon, the gate and the symbol - is
#: read from the registry row; this is only the key that finds it.
RV_PRODUCER_ID = "long_memory.realized_volatility.v1"

#: Declared calendar identity per market. Only the markets whose session
#: calendar this engine trades are listed - a market that is not here yields no
#: record rather than a guessed calendar (design doc §7.2 rule 9: `calendar_id`
#: is required with no default precisely because 22 `1d` steps is not 22 days).
CALENDAR_BY_MARKET = {"US": "XNYS"}

#: The producer's own definition versions (design doc §7.1: a redefinition is a
#: NEW target). These pin the feature/model half of the reproducibility tuple.
FEATURE_VERSION = "rv_forecast.features.v1"
MODEL_VERSION = "har_rv.ols.v1"

#: The HAR regressor set, spelled out, so the parameter hash covers the design
#: the coefficients were fitted under and not only the coefficients.
RV_TERMS = ("RV_t", "mean(RV,5)", "mean(RV,22)")

#: ``rv_forecast``'s refusal prose -> the contract's CLOSED vocabulary (§7.2
#: rule 4). An unmapped reason is a refusal to publish, never a mislabelled row:
#: a new sentence in the producer must be added here deliberately.
_RV_REASON_ORDER = (
    ("at or after the as-of", "COVERAGE_FAILURE"),
    ("no finite realized-variance observations", "INSUFFICIENT_HISTORY"),
    ("needs at least", "INSUFFICIENT_HISTORY"),
    ("rank-deficient", "MODEL_FIT_FAILURE"),
    ("column has", "MODEL_FIT_FAILURE"),
)

#: Price calibers that can be stated for a RETURN series. `raw` and
#: `split_adjusted` are both "the return carries no dividend"; `unknown` is
#: neither, so it is absent here on purpose.
_STATABLE_CALIBERS = ("adjusted", "split_adjusted", "raw")


class PublishRefusal(ValueError):
    """A mandatory provenance input has no true value, so no record is published.

    Distinct from ``ForecastContractError``: nothing about the record would be
    malformed. There is simply no honest value for a field the contract has no
    way to leave open, and inventing one is the failure mode ``Provenance``
    exists to prevent.
    """


def _hash(payload) -> str:
    return hashlib.sha256(
        _json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]


def _label_time(label):
    """The label as an epoch float; ``None`` when it is not a date at all."""
    if isinstance(label, datetime):
        return label.timestamp()
    if isinstance(label, date):
        return datetime(label.year, label.month, label.day).timestamp()
    if isinstance(label, str):
        try:
            return datetime.fromisoformat(label).timestamp()
        except ValueError:
            return None
    return None


def _label_value_pairs(series) -> list[tuple]:
    """``(label, float value)`` with an unreadable value kept as NaN.

    Three input forms are accepted, and the difference matters: a **mapping or
    pandas Series** carries its labels, and so does a **sequence of
    ``(label, value)`` pairs**. A plain sequence of numbers carries only
    positions - which is exactly the case ``_label_time`` then refuses, because
    a position is not a timestamp.

    A value that cannot be read as a float is *missing*, exactly as
    ``long_memory._finite_pairs`` treats it, so the count survives to the
    provenance record instead of vanishing here.
    """
    if series is None:
        return []
    if hasattr(series, "items"):
        items = list(series.items())
    else:
        raw = list(series)
        if raw and all(
            isinstance(item, (tuple, list)) and len(item) == 2 for item in raw
        ):
            items = [(item[0], item[1]) for item in raw]
        else:
            items = list(enumerate(raw))
    out: list[tuple] = []
    for label, value in items:
        try:
            out.append((label, float(value)))
        except (TypeError, ValueError):
            out.append((label, float("nan")))
    return out


def _rv_row(producer_id: str) -> _registry.RegistryRow:
    """The registry row that authorizes this producer - the identity's source."""
    for row in _registry.FORECAST_REGISTRY:
        if row.producer_id == producer_id:
            if row.status != "ok":
                raise PublishRefusal(
                    f"registry row {producer_id!r} is {row.status!r}, so it has no producer to "
                    "publish (design doc §7.2 rule 3)"
                )
            return row
    raise PublishRefusal(
        f"no registry row declares producer_id {producer_id!r}; a record may only be published "
        "for a key the registry authorizes (design doc §7.2 rule 2)"
    )


def _git_sha() -> str:
    """The repo's short HEAD sha, best effort; ``""`` when git is unavailable."""
    try:
        from tradingagents.execution_contract import git_sha

        return git_sha() or ""
    except Exception:  # noqa: BLE001 - a missing revision is a refusal, not a crash
        return ""


def _rv_reason_code(reason: str) -> str:
    """Map ``rv_forecast``'s refusal prose onto the contract's closed codes."""
    low = str(reason or "").lower()
    for needle, code in _RV_REASON_ORDER:
        if needle in low:
            return code
    raise PublishRefusal(
        f"rv_forecast refused with an unmapped reason ({reason!r}); the contract's vocabulary "
        "cannot label it, so no record is published (design doc §7.2 rule 4)"
    )


def publish_realized_volatility_forecast(
    returns,
    *,
    data_snapshot_id: str,
    price_caliber: str | None = None,
    market: str = "US",
    as_of=None,
    window: int | None = None,
    config: dict | None = None,
    code_revision: str | None = None,
    producer_id: str = RV_PRODUCER_ID,
) -> _contract.ForecastRecord:
    """Publish ``rv_forecast``'s output as the registry's ``realized_volatility`` record.

    ``returns`` is the dated close-to-close return series (a mapping/pandas
    Series of ``label -> return``, or a sequence, in which case the labels are
    its positions and the record is refused - a window has to be datable).
    ``config`` is read only through ``long_memory.long_memory_enabled``, the
    gate's single enforcement site; with the gate off the record is still
    published, as ``status="unavailable"`` with ``reason_code="GATE_OFF"``, so
    the ledger records *why* the quantity is absent instead of showing a gap.

    Raises :class:`PublishRefusal` when a mandatory provenance input is absent
    or unstatable.
    """
    row = _rv_row(producer_id)
    # `status == "ok"` is what `_rv_row` returned, and a non-declined row must
    # name both (RegistryRow.__post_init__) - restated here so the record cannot
    # be built from a row that only looks authorized.
    producer, symbol = row.producer_id, row.implementation_ref
    if not producer or not symbol:
        raise PublishRefusal(
            f"registry row {producer_id!r} names no producer_id/implementation_ref; a record "
            "needs both the stable owner and the current code location (design doc §7.2 rule 8)"
        )

    snapshot = str(data_snapshot_id or "").strip()
    if not snapshot:
        raise PublishRefusal(
            "data_snapshot_id is required: it is the record's 'which observations', and a "
            "fabricated one is reproducible against nothing (design doc §7.2 rule 9)"
        )

    calendar_id = CALENDAR_BY_MARKET.get(str(market or "").upper())
    if not calendar_id:
        raise PublishRefusal(
            f"market {market!r} has no declared calendar identity; add it to CALENDAR_BY_MARKET "
            "or publish nothing (design doc §7.2 rule 9)"
        )

    caliber = str(price_caliber or "").strip().lower()
    if caliber not in _STATABLE_CALIBERS:
        raise PublishRefusal(
            f"price_caliber {price_caliber!r} does not say whether the returns carry dividends; "
            "`adjusted_prices` has no third value and this repo never assumes 'adjusted' "
            "(design doc §7.2 rule 9)"
        )

    revision = _git_sha() if code_revision is None else str(code_revision)
    if not revision.strip():
        raise PublishRefusal(
            "no code revision is available (git_sha() returned empty and none was passed); an "
            "unreproducible implementation version is not a provenance value (design doc §7.2 rule 9)"
        )

    from tradingagents.strategies.long_memory import (
        MEMORY_WINDOW,
        long_memory_enabled,
        rv_forecast,
    )

    requested = int(window if window is not None else MEMORY_WINDOW)
    pairs = _label_value_pairs(returns)
    if not pairs:
        raise PublishRefusal("the return series is empty; there is no window to describe")

    raw_window = pairs[-requested:]
    finite = [(label, value) for label, value in raw_window if math.isfinite(value)]
    missing_obs = len(raw_window) - len(finite)
    if not finite:
        raise PublishRefusal(
            "the requested window holds no finite observation, so there is no window to date"
        )

    start = _label_time(finite[0][0])
    end = _label_time(finite[-1][0])
    if start is None or end is None:
        raise PublishRefusal(
            "the window's labels are not datable (positions or an unrecognised format); "
            "`training_start`/`training_end` are timestamps and a position is not one "
            "(design doc §7.2 rule 9)"
        )

    gate_on = long_memory_enabled(config)
    if gate_on:
        # The labels travel as a mapping, not as a bare value list:
        # `rv_forecast` checks backwardness against the labels, so a positional
        # list would make its as-of comparison incomparable with a date and
        # turn a good window into a refusal.
        raw = rv_forecast(dict(finite), as_of, window=requested)
        coeffs = raw.get("coeffs")
        effective = int(raw.get("n") or 0)
        if raw.get("status") == "ok":
            status, value = "ok", float(raw["forecast"])
            reason_code = reason_detail = None
        else:
            status, value = "unavailable", None
            reason_code = _rv_reason_code(str(raw.get("unavailable") or ""))
            reason_detail = str(raw.get("unavailable") or "")
    else:
        coeffs = None
        effective = 0
        status, value, reason_code = "unavailable", None, "GATE_OFF"
        reason_detail = (
            "enable_long_memory is off (default): no fit was attempted, so no value exists - "
            "recorded as a named absence, never a zero"
        )

    provenance = _contract.Provenance(
        data_snapshot_id=snapshot,
        training_start=float(start),
        training_end=float(end),
        requested_window=requested,
        effective_window=effective,
        padded=False,
        missing_obs=missing_obs,
        imputed_obs=0,
        adjusted_prices=(caliber == "adjusted"),
        feature_version=FEATURE_VERSION,
        model_version=MODEL_VERSION,
        parameter_hash=_hash({"terms": RV_TERMS, "window": requested, "coeffs": coeffs}),
        code_revision=revision,
        calendar_id=calendar_id,
    )

    origin = float(end)
    return _contract.ForecastRecord(
        forecast_id=":".join(
            [
                producer,
                row.target.name,
                row.entity_scope,
                row.frequency,
                str(row.horizon_steps),
                f"{origin:.0f}",
                snapshot,
            ]
        ),
        producer_id=producer,
        implementation_ref=symbol,
        gate=row.gate,
        target=row.target,
        entity_scope=row.entity_scope,
        frequency=row.frequency,
        horizon_steps=row.horizon_steps,
        forecast_origin=origin,
        value=value,
        status=status,
        provenance=provenance,
        interval=None,
        reason_code=reason_code,
        reason_detail=reason_detail,
    )

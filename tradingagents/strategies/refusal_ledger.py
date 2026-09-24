"""Refusal ledger + forward sampler (H7).

``prediction_ledger`` and ``invalidation_ledger`` record decisions the engine
**took**. Nothing records the candidates its gates **refused**, so a guardrail's
precision - capital saved versus profit forgone - is unmeasurable, and a report
claiming a guardrail protected the book cannot be contradicted by any computed
artifact.

This module is the other half. One immutable row per refused candidate (symbol,
as-of, gate, reason, input snapshot hash), then a forward sampler that classifies
each refusal against the price path that followed it into the taxonomy of
2607.02830 - ``saved-windowed`` / ``missed-moon`` / ``saved-early-death`` /
``flat`` / ``unclassifiable`` - and a per-gate save-to-miss ratio that is always
published **with the event count it rests on**.

Two things are adopted from the paper and one is not:

* the **taxonomy** (the five tiers), and
* the **tie-break**: a refusal that both saved capital and missed a subsequent
  run is a **miss** (missed beats saved), which makes the published ratio a
  conservative lower bound;
* the **ratio itself is not adopted**. 2607.02830's 3.7:1 rests on 13-22 day
  windows, one chain, one deployment and one regime, and its own matched
  lifecycle test refuted its headline tier (48.9% vs 57.6% reaching "gone").
  This module reports a per-gate ratio beside its counts, never as a constant.

Append-only JSONL, like ``prediction_ledger``/``trial_ledger``: rows are
immutable once written, the read never mutates them, and nothing here raises on
IO. Behind ``enable_refusal_ledger`` (default off): with the gate off
``log_refusal`` writes nothing and says so (``written: False``), so an
unregistered ledger cannot move a published number. Every refusal site wraps the
call, because a ledger that can break the refusal path it observes is worse than
no ledger.

Missing data is ``unavailable`` with the reason, never zero: a refusal with no
forward path is ``unclassifiable``, a gate with no miss events has no ratio (not
an infinite one), and a refusal site that does not know the symbol records
``None`` rather than a fabricated one.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
from pathlib import Path

#: The config key (and env ``TRADINGAGENTS_ENABLE_REFUSAL_LEDGER``) this gate reads.
GATE_NAME = "enable_refusal_ledger"

_LEDGER_NAME = "refusals.jsonl"

#: The five tiers of 2607.02830, verbatim.
TIER_SAVED_WINDOWED = "saved-windowed"
TIER_MISSED_MOON = "missed-moon"
TIER_SAVED_EARLY_DEATH = "saved-early-death"
TIER_FLAT = "flat"
TIER_UNCLASSIFIABLE = "unclassifiable"
TIERS: tuple[str, ...] = (
    TIER_SAVED_WINDOWED,
    TIER_MISSED_MOON,
    TIER_SAVED_EARLY_DEATH,
    TIER_FLAT,
    TIER_UNCLASSIFIABLE,
)

#: The paper's tie-break, stated once and carried on every classification.
TIE_BREAK = "missed beats saved"

#: Forward-sampler defaults. Declared, and reported on every score so a reader
#: can see which window and which thresholds produced the tier.
DEFAULT_HORIZON = 21  # trading days; the paper's windows are 13-22 days
DEFAULT_SAVE_PCT = 0.10  # a drawdown at least this deep is a save
DEFAULT_MISS_PCT = 0.10  # a run-up at least this high is a forgone run
DEFAULT_FLAT_BAND = 0.02  # "flat" tolerance around the refusal price
DEFAULT_MIN_BARS = 2  # a reference price plus one observation
DEFAULT_MIN_EVENTS = 30  # below this the ratio is flagged underpowered


def _ledger_path(results_dir: str | None) -> Path:
    base = results_dir or os.path.expanduser("~/.tradingagents/logs")
    return Path(base) / _LEDGER_NAME


def _cfg_or_ambient(cfg: dict | None) -> dict:
    """The config to read the gate from: the caller's, else the ambient one."""
    if cfg is not None:
        return cfg
    try:
        from tradingagents.dataflows.config import get_config

        return get_config() or {}
    except Exception:  # noqa: BLE001 - a missing config is an ungated read, not a crash
        return {}


def gate_on(cfg: dict | None = None) -> bool:
    """Is the refusal ledger enabled? Default off (``enable_refusal_ledger``).

    The key is read by its literal name, not through :data:`GATE_NAME`: the
    registry's read-site scan looks for a quoted key in an access idiom, and a
    gate read through a variable is a gate the registry cannot see.
    """
    return bool(_cfg_or_ambient(cfg).get("enable_refusal_ledger", False))


def _clean(value, *, upper: bool = False) -> str | None:
    """A ledger field as a trimmed string, or ``None`` when not supplied.

    An unsupplied symbol/as-of stays ``None``: a gate that refuses before the
    name is attached records what it has, and the sampler then reports that row
    unclassifiable for want of a path - never a fabricated default.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text.upper() if upper else text


def _snapshot_hash(snapshot) -> str | None:
    """Stable sha256 digest of a refusal's input snapshot (``None`` = no snapshot).

    One producer for the digest, so two refusals of the same inputs cannot
    record two identities for them. A snapshot that cannot be canonicalised
    digests to ``""`` rather than to a fabricated identity (the
    ``trial_ledger.returns_sha`` convention).
    """
    if snapshot is None:
        return None
    try:
        payload = json.dumps(
            snapshot, sort_keys=True, default=str, ensure_ascii=False,
            separators=(",", ":"),
        )
    except (TypeError, ValueError):
        return ""
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def log_refusal(
    symbol: str | None = None,
    as_of: str | None = None,
    gate: str = "",
    reason: str = "",
    snapshot=None,
    *,
    results_dir: str | None = None,
    cfg: dict | None = None,
    **extra,
) -> dict:
    """Append one immutable refusal row; returns it (never raises on IO).

    ``symbol``/``as_of`` are the refused candidate's identity and may be ``None``
    when the refusal site does not know them; ``gate`` names the rule that
    refused (``risk_governor`` / ``knife_guard`` / ``market_tradability`` /
    ``news_admission`` / ``value_dip``), ``reason`` its stated cause, and
    ``snapshot`` the inputs the gate saw (hashed, never stored whole).

    With the gate off nothing is written and the returned row carries
    ``written: False``, so a caller can print what it would have recorded instead
    of silently believing it recorded something.
    """
    row = {
        "symbol": _clean(symbol, upper=True),
        "as_of": _clean(as_of),
        "gate": str(gate or ""),
        "reason": str(reason or ""),
        "snapshot_hash": _snapshot_hash(snapshot),
        "ts": time.time(),
        "written": False,
    }
    for k, v in (extra or {}).items():
        if k not in row:
            row[k] = v
    if not gate_on(cfg):
        return row
    path = _ledger_path(results_dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # The flag is set BEFORE the row is serialised, so the row on disk says
        # what happened to it rather than claiming it was never written.
        row["written"] = True
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except (OSError, TypeError, ValueError):
        row["written"] = False
    return row


def rows(results_dir: str | None = None) -> list[dict]:
    """Read all ledger rows (append order by ts); never raises."""
    path = _ledger_path(results_dir)
    if not path.is_file():
        return []
    out: list[dict] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    except OSError:
        return []
    return sorted(out, key=lambda r: r.get("ts", 0.0))


def _path(closes) -> list[float]:
    """Every finite observation in ``closes``, in order (NaNs dropped, not filled)."""
    out: list[float] = []
    for c in closes or []:
        try:
            f = float(c)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f):
            out.append(f)
    return out


def classify_refusal(
    row: dict,
    closes,
    *,
    horizon: int = DEFAULT_HORIZON,
    save_pct: float = DEFAULT_SAVE_PCT,
    miss_pct: float = DEFAULT_MISS_PCT,
    flat_band: float = DEFAULT_FLAT_BAND,
    min_bars: int = DEFAULT_MIN_BARS,
) -> dict:
    """Classify ONE refusal against the price path that followed it (H7).

    ``closes`` is the forward close series for the row's symbol, starting at (or
    just after) the refusal's as-of; its first valid value is the reference price
    the refusal declined to pay. The path is cut to ``horizon`` bars and the
    refusal lands in one of the paper's five tiers:

    * ``missed-moon`` - the path ran at least ``miss_pct`` above the reference,
      so the refusal forwent a run. **A path that both fell at least ``save_pct``
      and ran at least ``miss_pct`` is classified here too** - the paper's
      tie-break, missed beats saved.
    * ``saved-early-death`` - it fell at least ``save_pct`` and had not recovered
      by the end of the window (the decline persisted).
    * ``saved-windowed`` - it fell at least ``save_pct`` but was back within
      ``flat_band`` of the reference by the end of the window (the save was only
      a window).
    * ``flat`` - neither threshold was crossed.
    * ``unclassifiable`` - no forward path, or fewer than ``min_bars``
      observations: nothing is invented for missing data.

    Returns the row plus a ``classification`` dict carrying the tier, the raw
    ``saved``/``missed`` flags (so the tie-break is visible rather than inferred
    from the tier), the path extremes, the declared thresholds and - when
    nothing could be measured - the ``unavailable`` reason.
    """
    horizon = max(1, int(horizon))
    min_bars = max(2, int(min_bars))
    vals = _path(closes)[:horizon]
    out = {
        "tier": TIER_UNCLASSIFIABLE,
        "saved": False,
        "missed": False,
        "horizon": horizon,
        "n_bars": len(vals),
        "ref_price": None,
        "last_price": None,
        "min_price": None,
        "max_price": None,
        "max_drawdown_pct": None,
        "max_runup_pct": None,
        "thresholds": {
            "save_pct": float(save_pct),
            "miss_pct": float(miss_pct),
            "flat_band": float(flat_band),
        },
        "tie_break": TIE_BREAK,
        "unavailable": None,
    }
    scored = dict(row)
    if len(vals) < min_bars:
        out["unavailable"] = (
            f"refusal unclassifiable: {len(vals)} forward bar(s) in the "
            f"{horizon}-bar window ({min_bars} needed to measure a path)"
        )
        scored["classification"] = out
        return scored
    ref = vals[0]
    if ref <= 0:
        out["unavailable"] = (
            f"refusal unclassifiable: non-positive reference price {ref!r}"
        )
        scored["classification"] = out
        return scored
    lo = min(vals)
    hi = max(vals)
    last = vals[-1]
    max_dd = (ref - lo) / ref
    max_ru = (hi - ref) / ref
    saved = max_dd >= float(save_pct)
    missed = max_ru >= float(miss_pct)
    still_down = last < ref * (1.0 - float(flat_band))
    # The tie-break: a refusal that both saved capital and missed a run is a
    # MISS. Without this branch the ordering below decides, and saved-first
    # ordering would call such a refusal saved.
    if saved and missed:
        tier = TIER_MISSED_MOON
    elif saved:
        tier = TIER_SAVED_EARLY_DEATH if still_down else TIER_SAVED_WINDOWED
    elif missed:
        tier = TIER_MISSED_MOON
    else:
        tier = TIER_FLAT
    out.update({
        "tier": tier,
        "saved": bool(saved),
        "missed": bool(missed),
        "ref_price": ref,
        "last_price": last,
        "min_price": lo,
        "max_price": hi,
        "max_drawdown_pct": max_dd * 100.0,
        "max_runup_pct": max_ru * 100.0,
    })
    scored["classification"] = out
    return scored


def score_all(
    closes_by_key: dict,
    results_dir: str | None = None,
    **kwargs,
) -> list[dict]:
    """Classify every ledger row using ``closes_by_key[(symbol, as_of)]``.

    A row whose key is absent from ``closes_by_key`` is reported with
    ``classification: None`` - "not sampled", never an invented tier. The key is
    the row's own ``(symbol, as_of)``, the identity the writer recorded.
    """
    out = []
    for r in rows(results_dir):
        closes = closes_by_key.get((r.get("symbol"), r.get("as_of")))
        if closes is None:
            r = dict(r)
            r["classification"] = None
        else:
            r = classify_refusal(r, closes, **kwargs)
        out.append(r)
    return out


def save_to_miss_ratio(
    scored_rows,
    *,
    min_events: int = DEFAULT_MIN_EVENTS,
) -> dict:
    """Per-gate taxonomy + save-to-miss ratio, each with its event count (H7).

    Every gate entry carries ``events`` beside ``ratio`` - the ratio is never
    published without the count it rests on, and it is a **conservative lower
    bound**: the tie-break moves a refusal that both saved and missed into
    ``missed-moon``, so ``saves`` here never includes a path that also ran.

    ``ratio`` is ``saves / misses`` over the measured events (``flat`` is an
    event; ``unclassifiable`` is not - it has no measured outcome). A gate with
    no miss events has **no ratio** (``None`` with the reason, never an infinite
    one), and a gate below ``min_events`` is flagged ``underpowered``.
    """
    gates: dict[str, dict] = {}
    for r in scored_rows or []:
        gate = str((r or {}).get("gate") or "")
        tier = ((r or {}).get("classification") or {}).get("tier")
        entry = gates.setdefault(gate, {
            "events": 0,
            "saves": 0,
            "misses": 0,
            "flat": 0,
            "unclassifiable": 0,
            "taxonomy": dict.fromkeys(TIERS, 0),
        })
        if tier in TIERS:
            entry["taxonomy"][tier] += 1
        if tier in (TIER_SAVED_WINDOWED, TIER_SAVED_EARLY_DEATH):
            entry["events"] += 1
            entry["saves"] += 1
        elif tier == TIER_MISSED_MOON:
            entry["events"] += 1
            entry["misses"] += 1
        elif tier == TIER_FLAT:
            entry["events"] += 1
            entry["flat"] += 1
        else:
            entry["unclassifiable"] += 1
    floor = max(0, int(min_events))
    out_gates: dict[str, dict] = {}
    for gate, e in gates.items():
        ratio = None
        unavailable = None
        if e["misses"] > 0:
            ratio = e["saves"] / e["misses"]
        else:
            unavailable = (
                f"save-to-miss ratio unavailable for gate {gate!r}: "
                f"{e['misses']} miss event(s) among {e['events']} measured "
                "event(s) - a ratio with no miss has no value"
            )
        out_gates[gate] = {
            **e,
            "ratio": ratio,
            "min_events": floor,
            "underpowered": e["events"] < floor,
            "unavailable": unavailable,
            "tie_break": TIE_BREAK,
        }
    return {
        "gates": out_gates,
        "min_events": floor,
        "tiers": list(TIERS),
        "tie_break": TIE_BREAK,
        "conservative": True,
        "basis": (
            "per-gate saves/misses over measured events, each gate reported "
            "with its own event count; the tie-break (missed beats saved) makes "
            "every ratio a conservative lower bound. The taxonomy and the "
            "discipline transfer from 2607.02830; its 3.7:1 figure does not "
            "(13-22 day windows, one chain, one deployment, one regime, and a "
            "headline tier its own matched lifecycle test refuted)"
        ),
    }


__all__ = [
    "GATE_NAME",
    "TIERS",
    "TIER_FLAT",
    "TIER_MISSED_MOON",
    "TIER_SAVED_EARLY_DEATH",
    "TIER_SAVED_WINDOWED",
    "TIER_UNCLASSIFIABLE",
    "TIE_BREAK",
    "classify_refusal",
    "gate_on",
    "log_refusal",
    "rows",
    "save_to_miss_ratio",
    "score_all",
    "_LEDGER_NAME",
]

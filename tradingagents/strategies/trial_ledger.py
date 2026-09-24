"""Trial ledger: one immutable row per evaluated candidate (H1).

The engine's deflated numbers take their trial count from a caller's
assertion today: ``evaluate.deflated_sharpe(..., n_trials=N)`` believes whatever
integer it is handed, and never sees the trials' Sharpe *dispersion* at all.
This module is the measurement instead. Every candidate the engine evaluates is
appended as one immutable row (candidate id, the window it was evaluated over,
the digest of the return series, the Sharpe it produced, the as-of date), and
both quantities the deflation needs are read back **from the rows**:

* ``n_trials`` - how many evaluations the ledger holds (the search's size), and
* ``sharpe_dispersion`` - V, the variance of their Sharpe ratios.

Neither is ever a caller's assertion, because a search that reported its own
trial count is exactly the claim under audit.

Append-only JSONL, like ``prediction_ledger`` and ``invalidation_ledger``: rows
are immutable once written, the read is a pure pass that never mutates them, and
nothing here raises on IO. Behind ``enable_trial_ledger`` (default off): with the
gate off ``record`` writes nothing and ``trial_stats`` reports ``unavailable``,
so an unregistered ledger cannot move a published number.

Missing data is ``unavailable`` with the reason, never zero - a ledger with fewer
than two usable Sharpes has no dispersion, and says so rather than reporting 0.0.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
from pathlib import Path

#: The config key (and env ``TRADINGAGENTS_ENABLE_TRIAL_LEDGER``) this gate reads.
GATE_NAME = "enable_trial_ledger"

_LEDGER_NAME = "trials.jsonl"


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
    """Is the trial ledger enabled? Default off (``enable_trial_ledger``).

    The key is read by its literal name, not through :data:`GATE_NAME`: the
    registry's read-site scan looks for a quoted key in an access idiom, and a
    gate read through a variable is a gate the registry cannot see (which is how
    it read as "claimed wired but nothing reads it").
    """
    return bool(_cfg_or_ambient(cfg).get("enable_trial_ledger", False))


def returns_sha(returns: list) -> str:
    """Stable sha256 digest of a return series: one identity per series.

    One producer for the digest, so two evaluations of the same series cannot
    record two different identities for it. ``None`` entries keep their
    position (a series with a gap digests differently from one without), and a
    non-numeric series digests to ``""`` rather than to a fabricated identity.
    """
    try:
        payload = json.dumps(
            [None if v is None else float(v) for v in (returns or [])],
            separators=(",", ":"),
        )
    except (TypeError, ValueError):
        return ""
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sharpe_or_none(sharpe: float | None) -> float | None:
    try:
        return None if sharpe is None else float(sharpe)
    except (TypeError, ValueError):
        return None


def record(candidate_id: str, window: str, returns_sha: str,
           sharpe: float | None, as_of: str, *, results_dir: str | None = None,
           cfg: dict | None = None) -> dict:
    """Append one immutable trial row; returns it (never raises on IO).

    ``candidate_id`` names the evaluated candidate, ``window`` the window it was
    evaluated over, ``returns_sha`` the digest of the return series it was
    evaluated on (``returns_sha``), ``sharpe`` the Sharpe that evaluation
    produced, ``as_of`` the decision date. With the gate off nothing is written
    and the returned row carries ``written: False``, so a caller can print what
    it would have recorded instead of silently believing it recorded something.
    """
    row = {
        "candidate_id": str(candidate_id or ""),
        "window": str(window or ""),
        "returns_sha": str(returns_sha or ""),
        "sharpe": _sharpe_or_none(sharpe),
        "as_of": str(as_of or ""),
        "ts": time.time(),
        "written": False,
    }
    if not gate_on(cfg):
        return row
    path = _ledger_path(results_dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        row["written"] = True
    except OSError:
        pass
    return row


def _rows(results_dir: str | None = None) -> list[dict]:
    """Read all ledger rows in append order; never raises."""
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
    return out


def _finite(value: object) -> bool:
    try:
        return math.isfinite(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False


def _unavailable(reason: str, n_trials: int | None, window: str | None) -> dict:
    return {"n_trials": n_trials, "n_sharpes": 0, "sharpe_dispersion": None,
            "mean_sharpe": None, "window": window, "unavailable": reason,
            "basis": f"trial ledger stats unavailable: {reason}"}


def trial_stats(*, results_dir: str | None = None, window: str | None = None,
                candidate_ids: list[str] | None = None,
                cfg: dict | None = None) -> dict:
    """N and V read back from the ledger rows - the trial count and dispersion.

    ``n_trials`` is the number of rows recorded (every evaluation the ledger
    holds, optionally filtered to one ``window`` and/or a set of
    ``candidate_ids``), and ``sharpe_dispersion`` is V, the sample variance of
    their Sharpe ratios - the quantity ``evaluate.deflated_sharpe`` takes the
    square root of in the selection threshold.

    With the gate off, or with fewer than two usable Sharpe rows, the dispersion
    is ``unavailable`` with the reason and a ``None`` value: an unmeasured
    dispersion is not zero.
    """
    if not gate_on(cfg):
        return _unavailable(f"{GATE_NAME} is off", None, window)
    rows = _rows(results_dir)
    if window is not None:
        rows = [r for r in rows if str(r.get("window") or "") == str(window)]
    if candidate_ids is not None:
        wanted = {str(c) for c in candidate_ids}
        rows = [r for r in rows if str(r.get("candidate_id") or "") in wanted]
    sharpes = [float(r["sharpe"]) for r in rows if _finite(r.get("sharpe"))]
    if len(sharpes) < 2:
        return _unavailable(
            f"{len(sharpes)} usable Sharpe row(s) in the ledger (2 needed for a "
            "dispersion)", len(rows), window)
    mean = sum(sharpes) / len(sharpes)
    var = sum((s - mean) ** 2 for s in sharpes) / (len(sharpes) - 1)
    return {
        "n_trials": len(rows),
        "n_sharpes": len(sharpes),
        "sharpe_dispersion": var,
        "mean_sharpe": mean,
        "window": window,
        "unavailable": None,
        "basis": (
            f"read back from {len(rows)} trial-ledger row(s)"
            + (f" in window {window}" if window is not None else "")
            + f"; V is the sample variance of {len(sharpes)} recorded Sharpe "
            "ratios (ddof=1), which the selection threshold takes the square "
            "root of - N and V are measured here, never asserted by a caller"
        ),
    }


__all__ = ["GATE_NAME", "record", "trial_stats", "returns_sha", "gate_on",
           "_LEDGER_NAME"]

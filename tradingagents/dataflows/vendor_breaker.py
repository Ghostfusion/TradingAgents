"""Per-(market, vendor) circuit breaker (DSA research §3.4, pillar 7).

Port of daily_stock_analysis's layered source-health: a 3-fail / 300 s
cooldown / half-open-probe breaker per (market, vendor) key, plus a TTL
negative capability cache (a source known to lack a capability is skipped for
a while). Thread-safe (a single lock; batch workers share one process).

Semantics:
- ``record_success(key)`` clears the failure count and cools the key.
- ``record_failure(key)`` increments; at ``max_failures`` the key trips into
  OPEN with a ``cooled_until`` timestamp.
- ``allow_call(key, now)``: False while OPEN AND cooled_until not yet passed
  (for a probe the caller decides; the half-open probe pattern is explicit:
  ``probe_due(key, now)`` True only in the window after cooldown).
- ``probe_due(key, now)``: True when OPEN and now >= cooled_until (the
  first call after cooldown is the probe — if it succeeds it re-closes).
- Negative capability cache: ``mark_capability_absent(key)`` /
  ``capability_available(key, now, ttl)``.

Pure + deterministic; no I/O. Reset hook for tests.
"""

from __future__ import annotations

import threading
import time as _time

_LOCK = threading.Lock()

# (market, vendor) -> {"fails": int, "cooled_until": float, "open": bool}
_STATE: dict[tuple[str, str], dict] = {}
# (market, vendor, capability) -> float (absent until)
_NEGATIVE: dict[tuple[str, str, str], float] = {}

DEFAULT_MAX_FAILURES = 3
DEFAULT_COOLDOWN_SECONDS = 300
DEFAULT_NEGATIVE_TTL_SECONDS = 900


def _key(market: str, vendor: str) -> tuple[str, str]:
    return (str(market).upper(), str(vendor).lower())


def reset() -> None:
    """Drop all breaker + negative-cache state (tests / fresh runs)."""
    with _LOCK:
        _STATE.clear()
        _NEGATIVE.clear()


def allow_call(market: str, vendor: str, now: float | None = None,
               max_failures: int = DEFAULT_MAX_FAILURES,
               cooldown: int = DEFAULT_COOLDOWN_SECONDS) -> bool:
    """True when a call to (market, vendor) is allowed right now.

    Open + within cooldown -> False. Open + past cooldown -> True (this is
    the half-open probe; the caller should ``record_*`` the outcome so the
    next call sees a stable state). Never raises.
    """
    t = _time.time() if now is None else now
    with _LOCK:
        st = _STATE.get(_key(market, vendor))
        if not st or not st.get("open"):
            return True
        return t >= float(st.get("cooled_until", 0))


def record_success(market: str, vendor: str, max_failures: int = DEFAULT_MAX_FAILURES,
                   cooldown: int = DEFAULT_COOLDOWN_SECONDS) -> None:
    """A successful call re-closes the breaker (fails cleared, not open).

    ``max_failures``/``cooldown`` are accepted for signature symmetry with
    ``record_failure`` (a caller tuning thresholds passes the same values to
    both); a success always resets regardless of the thresholds.
    """
    del max_failures, cooldown  # reset semantics need no thresholds
    with _LOCK:
        st = _STATE.setdefault(_key(market, vendor), {"fails": 0, "open": False, "cooled_until": 0.0})
        st["fails"] = 0
        st["open"] = False
        st["cooled_until"] = 0.0


def record_failure(market: str, vendor: str, now: float | None = None,
                   max_failures: int = DEFAULT_MAX_FAILURES,
                   cooldown: int = DEFAULT_COOLDOWN_SECONDS) -> bool:
    """Register a failure; returns True when this call TRIPPED the breaker."""
    t = _time.time() if now is None else now
    with _LOCK:
        st = _STATE.setdefault(_key(market, vendor), {"fails": 0, "open": False, "cooled_until": 0.0})
        st["fails"] = int(st.get("fails", 0)) + 1
        if st["fails"] >= max_failures:
            st["open"] = True
            st["cooled_until"] = t + float(cooldown)
            return True
        return False


def probe_due(market: str, vendor: str, now: float | None = None) -> bool:
    """True when the breaker is OPEN and the cooldown has elapsed (probe)."""
    t = _time.time() if now is None else now
    with _LOCK:
        st = _STATE.get(_key(market, vendor))
        return bool(st and st.get("open") and t >= float(st.get("cooled_until", 0)))


def state_snapshot() -> dict:
    """Read-only breaker state (tests/debug)."""
    with _LOCK:
        return {f"{m}:{v}": dict(st) for (m, v), st in _STATE.items()}


def mark_capability_absent(market: str, vendor: str, capability: str,
                           ttl: int = DEFAULT_NEGATIVE_TTL_SECONDS,
                           now: float | None = None) -> None:
    """``vendor`` cannot provide ``capability`` on ``market`` until ttl passes."""
    t = _time.time() if now is None else now
    with _LOCK:
        _NEGATIVE[(_key(market, vendor)[0], _key(market, vendor)[1], str(capability).lower())] = t + float(ttl)


def capability_available(market: str, vendor: str, capability: str,
                         now: float | None = None) -> bool:
    """False while the negative-cache entry for (market, vendor, capability) is live."""
    t = _time.time() if now is None else now
    with _LOCK:
        until = _NEGATIVE.get((_key(market, vendor)[0], _key(market, vendor)[1], str(capability).lower()))
        if until is None:
            return True
        return t >= until


__all__ = [
    "reset",
    "allow_call",
    "record_success",
    "record_failure",
    "probe_due",
    "state_snapshot",
    "mark_capability_absent",
    "capability_available",
]

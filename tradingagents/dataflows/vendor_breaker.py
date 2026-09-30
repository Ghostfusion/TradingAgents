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


#: Wildcard market for the vendor-layer gate. A vendor module does not know
#: which market a call serves, so its entries are keyed market-free. The
#: market-routing gate uses a real market ("US"/"CA"/...) and is therefore a
#: narrower, separate scope - the two never shadow each other.
ANY_MARKET = "*"


def vendor_skip_reason(vendor: str, capability: str = "",
                       now: float | None = None) -> str | None:
    """Why ``vendor`` must be skipped right now, or ``None`` when it may be called.

    Both halves of the endorsed vendor-failure policy - and they are deliberately
    distinguishable, because they leave the vendor module as DIFFERENT error
    types:

    * ``"absent"`` - a 401/403 verdict held in the negative cache. A key/plan
      fact, stable for the process, which must not be re-asked per call.
      Measured 2026-09-30: one set of batch logs carried **575** FMP ``profile``
      429s, **60** Massive snapshot 403s and **26** Finnhub analyst-ratings
      403s - every one of them a re-ask of a refusal already known.
    * ``"breaker"`` - the cooldown breaker is open after repeated transient
      failures.

    Collapsing the two would report a transient throttle as a served advisory
    "unavailable", which is what the typed taxonomy exists to prevent.
    """
    if not capability_available(ANY_MARKET, vendor, capability, now=now):
        return "absent"
    if not allow_call(ANY_MARKET, vendor, now=now):
        return "breaker"
    return None


def note_vendor_refused(vendor: str, capability: str = "",
                        ttl: int = DEFAULT_NEGATIVE_TTL_SECONDS,
                        now: float | None = None) -> None:
    """Remember that ``vendor`` cannot serve ``capability`` (HTTP 401/403).

    A key/plan verdict does not change within a run, so it is remembered rather
    than rediscovered. ``capability`` is the ENDPOINT identity, never the
    symbol: a 403 on ``.../tickers/ZM`` is not about ZM.
    """
    mark_capability_absent(ANY_MARKET, vendor, capability, ttl=ttl, now=now)


def note_vendor_transient(vendor: str, now: float | None = None) -> bool:
    """Count a transient failure (429/5xx); True when this tripped the breaker."""
    return record_failure(ANY_MARKET, vendor, now=now)


def note_vendor_ok(vendor: str) -> None:
    """A successful call re-closes the breaker (fails cleared)."""
    record_success(ANY_MARKET, vendor)


__all__ = [
    "ANY_MARKET",
    "reset",
    "allow_call",
    "record_success",
    "record_failure",
    "probe_due",
    "state_snapshot",
    "mark_capability_absent",
    "capability_available",
    "vendor_skip_reason",
    "note_vendor_refused",
    "note_vendor_transient",
    "note_vendor_ok",
]

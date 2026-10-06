"""EODHD quota awareness: what the plan has left, and what this process has spent.

Two measured facts make this module possible. Both were probed live on 2026-10-06
against the account's own key:

1. **``GET /user`` is free of quota.** ``apiRequests`` moved 2663 -> 2664 across
   exactly one ``/eod`` call; a 13-request probe (1 data call + 2 searches + 7
   plan-gated refusals) moved it by 3; a 403 moved it by 0. Reading the quota
   therefore does not spend the thing it measures - which is the only reason a
   watcher can exist at all. It is not free of *traffic*, so the reading is
   TTL-cached and the per-endpoint spend is counted locally instead of re-read.
2. **EODHD bills weighted calls per request, not requests.** The vendor's own
   endpoint references declare 5 calls for ``/symbol-change-history`` and 10 apiece
   for ``calendar/trends``, ``historical-market-cap``, ``insider-transactions`` and
   the CBOE feeds; everything else measured (``/eod``, ``/search``) is one. A
   ledger that counted requests would understate a CBOE read by 10x. The weights
   are the vendor's DECLARED numbers, not measured - none of the 5/10-call
   endpoints is reachable on this plan, which is itself why a ledger is worth
   having.

Nothing here raises. A monitoring read that can break a data read is worse than no
monitoring at all, so ``quota_snapshot`` reports ``unavailable`` with the reason and
the ledger keeps counting. The watcher never blocks, never retries and never spends
more than one cached request per ``SNAPSHOT_TTL_SECONDS``.

Rule 6 (no personal info in commits): the account payload also carries an ``email``
field. It is deliberately **not** returned - only the quota, the plan label and the
counter window leave this module.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

#: One reading is reused for this long. The read costs no quota but it is still a
#: request against the per-minute throttle, so it is not made per call.
SNAPSHOT_TTL_SECONDS = 60.0

#: Fractions of the daily limit worth saying out loud, highest first. Each is logged
#: at most once per UTC day, so a long session is not nagged.
WARNING_THRESHOLDS = (0.95, 0.80)

#: The vendor's declared call weights, keyed by the endpoint path (full path first,
#: then the leading segment - ``historical-market-cap/AAPL.US`` is billed as the
#: feed). A path absent here is one counted call per request, which is what a direct
#: measurement of ``/eod`` and ``/search`` showed.
CALL_WEIGHTS: dict[str, int] = {
    "symbol-change-history": 5,
    "calendar/trends": 10,
    "historical-market-cap": 10,
    "insider-transactions": 10,
    "cboe/index": 10,
    "cboe/indices": 10,
}

#: The account endpoint that is not counted. Named once, read by both the ledger and
#: the snapshot so the free path can never drift from the guard.
_FREE_PATH = "user"

_ledger: dict = {"requests": 0, "weighted_calls": 0, "by_endpoint": {}}
_snapshot: dict | None = None
_snapshot_at: float = 0.0
_announced: set[float] = set()
_announced_on: str = ""


def _clean_path(path: str) -> str:
    """The endpoint key: no leading slash, no query, no fragment."""
    clean = str(path or "").strip().lstrip("/")
    return clean.split("?", 1)[0].split("#", 1)[0]


def is_free_path(path: str) -> bool:
    """True for the one endpoint EODHD does not count against the daily limit."""
    return _clean_path(path) == _FREE_PATH


def weight_for(path: str) -> int:
    """Declared counted calls for one request to ``path`` (``1`` when undeclared).

    The full path wins over the leading segment so a weighted feed can live beside an
    unweighted sibling under the same prefix.
    """
    clean = _clean_path(path)
    if clean in CALL_WEIGHTS:
        return CALL_WEIGHTS[clean]
    return CALL_WEIGHTS.get(clean.split("/", 1)[0], 1)


def note_call(path: str, *, weight: int | None = None) -> None:
    """Record one request in the local ledger. Pure Python - it makes no request.

    This is the only accounting that does not need a snapshot: the vendor's own
    counter answers "how much is left", and the ledger answers "what did this run
    spend", which is the question a report or a log line actually asks.
    """
    clean = _clean_path(path)
    counted = weight_for(clean) if weight is None else max(1, int(weight))
    _ledger["requests"] += 1
    _ledger["weighted_calls"] += counted
    row = _ledger["by_endpoint"].setdefault(
        clean, {"requests": 0, "weighted_calls": 0}
    )
    row["requests"] += 1
    row["weighted_calls"] += counted


def observed_spend() -> dict:
    """What this process has spent: ``{requests, weighted_calls, by_endpoint}``.

    ``by_endpoint`` is a copy keyed by path, each row ``{requests, weighted_calls}``,
    so a caller can render the breakdown without reaching into module state.
    """
    return {
        "requests": _ledger["requests"],
        "weighted_calls": _ledger["weighted_calls"],
        "by_endpoint": {
            key: dict(row) for key, row in _ledger["by_endpoint"].items()
        },
    }


def _fetch_account() -> dict:
    """The raw ``/user`` payload through the shared EODHD seam (token + typing)."""
    from .eodhd import _eodhd_get

    data = _eodhd_get(_FREE_PATH, {"fmt": "json"})
    return data if isinstance(data, dict) else {}


def _parse(payload: dict) -> dict | None:
    """The quota fields from an ``/user`` body, or ``None`` when it is not one."""
    try:
        limit = int(payload["dailyRateLimit"])
        used = int(payload["apiRequests"])
    except (KeyError, TypeError, ValueError):
        return None
    try:
        extra = int(payload.get("extraLimit") or 0)
    except (TypeError, ValueError):
        extra = 0
    return {"used": used, "limit": limit, "extra": extra}


def _resets_at() -> str:
    """The next 00:00 UTC - EODHD's counter turns over on the UTC day."""
    now = datetime.now(timezone.utc)
    midnight = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return midnight.isoformat().replace("+00:00", "Z")


def _status(used: int, limit: int, extra: int) -> str:
    if limit <= 0:
        return "unknown"
    if limit - used <= 0 and extra <= 0:
        return "exhausted"
    fraction = used / limit
    if fraction >= WARNING_THRESHOLDS[0]:
        return "critical"
    if fraction >= WARNING_THRESHOLDS[1]:
        return "near_limit"
    return "ok"


def _warn_once(status: str, used: int, limit: int, extra: int) -> None:
    """Log one line the first time the day crosses each threshold, and never again.

    Same rule as the vendor's own watcher: announcing 95% settles 80%, because
    hearing about 80% afterwards would read as though the situation had improved.
    """
    global _announced_on
    today = datetime.now(timezone.utc).date().isoformat()
    if _announced_on != today:
        _announced.clear()
        _announced_on = today
    if limit <= 0:
        return
    fraction = used / limit
    for threshold in WARNING_THRESHOLDS:
        if fraction >= threshold and threshold not in _announced:
            _announced.update(low for low in WARNING_THRESHOLDS if low <= threshold)
            logger.warning(
                "EODHD daily quota %s: %d of %d calls used (%.0f%%), %d in reserve. "
                "Counter resets at %s.",
                status,
                used,
                limit,
                fraction * 100,
                extra,
                _resets_at(),
            )
            return


def _remember(result: dict) -> dict:
    """Cache a reading - including a FAILED one - for the TTL, and return a copy.

    The failure is cached deliberately: without it an outage would re-request the
    account on every call, which is the request storm the TTL exists to prevent. A
    first attempt is never delayed, and ``refresh=True`` always retries, so a
    transient failure still clears - it just cannot be re-hammered. A cached failure
    is still rendered as ``unavailable``, never as a zero.
    """
    global _snapshot, _snapshot_at
    _snapshot = result
    _snapshot_at = time.monotonic()
    return dict(result)


def quota_snapshot(*, refresh: bool = False, fetch=None) -> dict:
    """The account's quota state, TTL-cached. Never raises.

    Returns::

        {"available", "used", "limit", "extra", "remaining", "percent_used",
         "resets_at", "status", "plan", "unavailable"}

    ``available`` is False and ``unavailable`` carries the reason when the account
    read failed - a caller renders the reason rather than a fabricated zero, because
    ``used=0`` and ``unavailable`` are different facts and ``NA != 0``.

    The account's ``email`` is deliberately dropped (rule 6): only the quota, the
    plan label and the counter window leave this function.
    """
    global _snapshot, _snapshot_at
    now = time.monotonic()
    if not refresh and _snapshot is not None and now - _snapshot_at < SNAPSHOT_TTL_SECONDS:
        return dict(_snapshot)

    try:
        payload = (fetch or _fetch_account)()
    except Exception as exc:  # noqa: BLE001 - a monitoring read never breaks a caller
        return _remember(
            {
                "available": False,
                "used": None,
                "limit": None,
                "extra": None,
                "remaining": None,
                "percent_used": None,
                "resets_at": None,
                "status": "unavailable",
                "plan": "",
                "unavailable": f"account read failed: {exc}",
            }
        )

    parsed = _parse(payload) if isinstance(payload, dict) else None
    if parsed is None:
        return _remember(
            {
                "available": False,
                "used": None,
                "limit": None,
                "extra": None,
                "remaining": None,
                "percent_used": None,
                "resets_at": None,
                "status": "unavailable",
                "plan": "",
                "unavailable": "account payload carried no dailyRateLimit/apiRequests",
            }
        )

    used, limit, extra = parsed["used"], parsed["limit"], parsed["extra"]
    status = _status(used, limit, extra)
    result = {
        "available": True,
        "used": used,
        "limit": limit,
        "extra": extra,
        "remaining": max(limit - used, 0),
        "percent_used": round(used / limit * 100, 1) if limit > 0 else None,
        "resets_at": _resets_at(),
        "status": status,
        "plan": str(payload.get("subscriptionType") or ""),
        "unavailable": None,
    }
    _warn_once(status, used, limit, extra)
    return _remember(result)


def format_quota_line(*, refresh: bool = False) -> str:
    """One line: the account's remaining allowance and this process's own spend."""
    snap = quota_snapshot(refresh=refresh)
    spend = observed_spend()
    mine = (
        f"This process: {spend['requests']} requests = "
        f"~{spend['weighted_calls']} counted calls."
    )
    if not snap["available"]:
        return f"EODHD quota unavailable - {snap['unavailable']} {mine}"
    reserve = (
        f" plus {snap['extra']:,} in reserve" if snap["extra"] else ""
    )
    plan = f" [{snap['plan']}]" if snap["plan"] else ""
    return (
        f"EODHD quota{plan}: {snap['used']:,} of {snap['limit']:,} daily calls used "
        f"({snap['percent_used']}%), {snap['remaining']:,} left{reserve}, "
        f"resets {snap['resets_at']}. {mine}"
    )


def format_spend_breakdown(limit: int = 12) -> str:
    """The per-endpoint spend, heaviest weighted first, as one line (or ``""``)."""
    spend = observed_spend()
    rows = sorted(
        spend["by_endpoint"].items(),
        key=lambda kv: (-kv[1]["weighted_calls"], kv[0]),
    )[:limit]
    if not rows:
        return ""
    parts = ", ".join(
        f"{path} {row['requests']}x (~{row['weighted_calls']})" for path, row in rows
    )
    return f"By endpoint: {parts}."


def _reset() -> None:
    """Drop all module state. Intended for tests (private: not a public surface)."""
    global _snapshot, _snapshot_at, _announced_on
    _ledger["requests"] = 0
    _ledger["weighted_calls"] = 0
    _ledger["by_endpoint"].clear()
    _snapshot = None
    _snapshot_at = 0.0
    _announced.clear()
    _announced_on = ""

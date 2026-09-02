"""Owner-wait coalescing + TTL result cache for heavy read surfaces.

Port of daily_stock_analysis's request coalescing (DSA research §3.5,
pillar 9): the first caller for a key OWNS the fetch, concurrent waiters
block on an event; only successes are cached; a waiter whose owner failed
re-competes; hits are attributed `provider=SearchCache`.

Thread-safe; bounded (cap eviction, expired eviction).
"""

from __future__ import annotations

import threading
import time as _time


class CoalescingCache:
    """TTL result cache with owner-wait coalescing for identical keys.

    ``fetch(key)`` is the canonical entry: one caller per key at a time does
    the work; others wait (up to ``wait_max_s``) and reuse a successful
    result. A failed fetch (returning None/raising) means the waiter
    re-competes so it may run the work itself if the owner produced nothing.
    """

    def __init__(self, ttl_s: float = 600.0, max_entries: int = 500,
                 wait_max_s: float = 30.0):
        self._ttl = float(ttl_s)
        self._max = int(max_entries)
        self._wait = float(wait_max_s)
        self._data: dict = {}          # key -> (ts, value)
        self._inflight: dict = {}      # key -> threading.Event
        self._lock = threading.Lock()

    def _expire(self) -> None:
        now = _time.time()
        stale = [k for k, (ts, _) in self._data.items() if now - ts > self._ttl]
        for k in stale:
            del self._data[k]
        while len(self._data) > self._max:  # FIFO oldest
            self._data.pop(next(iter(self._data)))

    def get(self, key) -> object | None:
        """Cached value; None on miss/expired."""
        with self._lock:
            self._expire()
            hit = self._data.get(key)
            if hit is not None and _time.time() - hit[0] <= self._ttl:
                return hit[1]
        return None

    def put(self, key, value) -> None:
        """Cache a SUCCESSFUL result (only successes are cached)."""
        with self._lock:
            self._expire()
            self._data[key] = (_time.time(), value)

    def fetch(self, key, work, *args, **kwargs):
        """Either deliver a cached result or run ``work`` exactly once per key.

        Waiter semantics: a concurrent caller for the same key waits up to
        ``wait_max_s`` for the owner; on owner success it reuses the result,
        on owner failure (None/exception) it re-competes so it may fetch
        itself (never returns "failed" when it could have tried).
        """
        cached = self.get(key)
        if cached is not None:
            return cached, True
        deadline = _time.time() + self._wait
        while True:
            with self._lock:
                self._expire()
                cached = self._data.get(key)
                if cached is not None and _time.time() - cached[0] <= self._ttl:
                    return cached[1], True
                if key not in self._inflight:
                    event = threading.Event()
                    self._inflight[key] = event
                    owner = True
                else:
                    event = self._inflight[key]
                    owner = False
            if not owner:
                remaining = deadline - _time.time()
                if remaining <= 0:
                    break
                event.wait(min(remaining, 1.0))
                with self._lock:
                    cached = self._data.get(key)
                    if cached is not None and _time.time() - cached[0] <= self._ttl:
                        return cached[1], True  # owner succeeded while we waited
                    if key in self._inflight:
                        continue  # owner still working; keep waiting
                    owner = True  # owner finished w/o cache: re-compete
            # owner path
            try:
                value = work(*args, **kwargs)
            except Exception:  # noqa: BLE001 - degrade, never raise
                value = None
            with self._lock:
                self._inflight.pop(key, None)
                if value is not None:
                    self._data[key] = (_time.time(), value)
            if value is not None:
                return value, True
            if owner:
                return None, False  # we were the owner and produced nothing
            # waiter whose owner failed: loop to re-compete (become owner)
            continue


__all__ = ["CoalescingCache"]


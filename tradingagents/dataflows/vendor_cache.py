"""Disk-backed TTL cache for vendor data results.

Most vendor fetches (fundamentals, analyst ratings, short interest, options,
SEC filings, technical indicators) are deterministic for a given ticker+date,
yet the data tools re-fetch them on every run — burning free-tier API quotas
(Alpha Vantage is 25 req/day; Finnhub ~60 req/min) across daily batch runs.

This cache stores each successful vendor *string* result under
``<data_cache_dir>/vendor_cache/<hash>.json`` with a written timestamp, and
re-serves it when a later call matches the same ``(method, args, kwargs)`` key
within the TTL. Only successful results are cached — the router's sentinel
strings (``NO_DATA_AVAILABLE`` / ``DATA_UNAVAILABLE`` / ``DATA_DISABLED``) are
never written, so a transient failure can't be frozen and replayed.

Safety knobs live in the config (all overridable):

- ``vendor_cache_enabled`` (bool) — master switch (default True).
- ``vendor_cache_ttl_seconds`` (int) — freshness window (default 21600 = 6h).
- ``vendor_cache_skip_categories`` (set of str) — categories excluded from the
  cache because their content is genuinely live (default: ``news_data``).

The cache is process-safe via a lock; writes are atomic (temp file + replace).
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
import threading
import time

logger = logging.getLogger(__name__)

_SENTINEL_PREFIXES = ("NO_DATA_AVAILABLE", "DATA_UNAVAILABLE", "DATA_DISABLED")


def _stable_key(method: str, args: tuple, kwargs: dict) -> str:
    """A deterministic hash for a (method, args, kwargs) call."""
    payload = json.dumps(
        [method, list(args), dict(sorted(kwargs.items()))],
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class VendorCache:
    """Thread-safe, disk-backed TTL cache for vendor result strings."""

    def __init__(self):
        self._lock = threading.Lock()
        self._memory: dict[str, tuple[float, str]] = {}

    # -- config helpers ----------------------------------------------------

    def _settings(self) -> tuple[bool, int]:
        # Import lazily to avoid a circular import at module load.
        from .config import get_config

        cfg = get_config()
        enabled = cfg.get("vendor_cache_enabled", True)
        ttl = cfg.get("vendor_cache_ttl_seconds", 21600)
        try:
            ttl = int(ttl)
        except (TypeError, ValueError):
            ttl = 21600
        return bool(enabled), max(0, ttl)

    def _dir(self) -> str | None:
        from .config import get_config

        base = get_config().get("data_cache_dir")
        if not base:
            return None
        d = os.path.join(base, "vendor_cache")
        try:
            os.makedirs(d, exist_ok=True)
        except OSError as exc:
            # A read-only / unwritable cache dir must degrade to "no cache", not
            # crash the routing layer (e.g. under a restricted sandbox).
            logger.debug("Vendor cache dir unavailable (%s); caching disabled.", exc)
            return None
        return d

    def _path(self, key: str) -> str | None:
        d = self._dir()
        return os.path.join(d, f"{key}.json") if d else None

    # -- public API --------------------------------------------------------

    def should_skip(self, category: str) -> bool:
        from .config import get_config

        skip = get_config().get("vendor_cache_skip_categories", set())
        return category in skip

    def get(self, method: str, category: str, args: tuple, kwargs: dict) -> str | None:
        """Return a cached, unexpired result string, or None on miss."""
        enabled, ttl = self._settings()
        if not enabled or ttl <= 0 or self.should_skip(category):
            return None

        key = _stable_key(method, args, kwargs)

        # Fast path: in-memory.
        with self._lock:
            hit = self._memory.get(key)
            if hit is not None:
                expires, value = hit
                if time.time() < expires:
                    return value
                self._memory.pop(key, None)

        # Slow path: disk.
        path = self._path(key)
        if not path or not os.path.exists(path):
            return None
        try:
            with open(path, encoding="utf-8") as f:
                record = json.load(f)
            if time.time() - float(record.get("written", 0)) < ttl:
                value = record.get("value")
                if isinstance(value, str):
                    with self._lock:
                        self._memory[key] = (time.time() + ttl, value)
                    return value
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            logger.debug("Vendor cache read miss for %s: %s", method, exc)
        return None

    def set(self, method: str, category: str, args: tuple, kwargs: dict, value: str) -> None:
        """Store a successful vendor result (sentinel strings are skipped)."""
        enabled, ttl = self._settings()
        if not enabled or ttl <= 0 or self.should_skip(category):
            return
        if not isinstance(value, str) or value.startswith(_SENTINEL_PREFIXES):
            return

        key = _stable_key(method, args, kwargs)
        now = time.time()
        with self._lock:
            self._memory[key] = (now + ttl, value)

        path = self._path(key)
        if not path:
            return
        record = {"written": now, "method": method, "value": value}
        tmp = path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(record, f)
            os.replace(tmp, path)
        except OSError as exc:
            logger.debug("Vendor cache write failed for %s: %s", method, exc)

    def clear(self) -> None:
        """Drop all cached results, both in-memory and on-disk.

        The router consults the cache *before* running the configured vendor
        chain, so cached results are keyed on ``(method, args, kwargs)`` and
        blind to which vendor implementation is live at call time. Clearing
        only the in-memory layer let a disk entry written by a prior test (or
        a real run) with the same key be served to a later test that mocks the
        vendors — silently skipping the mocked chain and causing
        order-dependent test failures. Now the whole cache (including the
        TTL-bound disk layer) is emptied, so ``clear()`` actually restores a
        fresh cache as its name implies.
        """
        with self._lock:
            self._memory.clear()

        d = self._dir()
        if not d:
            return
        with contextlib.suppress(OSError):
            for name in os.listdir(d):
                if name.endswith(".json"):
                    with contextlib.suppress(OSError):
                        os.unlink(os.path.join(d, name))


# Module-level singleton shared by the router.
vendor_cache = VendorCache()

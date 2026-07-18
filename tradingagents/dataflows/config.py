"""Thread-safe, thread-local data-flow configuration.

The data tools (``route_to_vendor``, vendor modules, ``load_ohlcv``) all read
their settings through :func:`get_config`.  Originally ``_config`` was a single
process-global dict that ``TradingAgentsGraph.__init__`` mutated via
:func:`set_config`, so concurrent batch workers (a single process running
several analyses via ``ThreadPoolExecutor``) raced on it: one worker's
per-symbol overrides (e.g. disabling analyst ratings for crypto) could leak
into another worker's fetches, and a ``deepcopy`` in :func:`get_config` could
observe a half-applied merge.

This module makes the config **thread-local**: each thread that calls
:func:`set_config` gets its own merged copy, and :func:`get_config` returns
that thread's copy (falling back to the process default when the thread has
never set one).  A module lock guards the shared fallback so its lazy init and
any direct reset stay atomic.
"""
from __future__ import annotations

import threading
from copy import deepcopy

import tradingagents.default_config as default_config

# Process-wide fallback (the default). Each thread may override it via
# set_config(); get_config() returns the thread's override when present.
_config: dict | None = None
_tls = threading.local()
_lock = threading.Lock()


def initialize_config():
    """Ensure the process fallback is populated."""
    global _config
    with _lock:
        if _config is None:
            _config = deepcopy(default_config.DEFAULT_CONFIG)


def set_config(config: dict):
    """Merge ``config`` into this thread's configuration.

    Dict-valued keys (e.g. ``data_vendors``) are merged one level deep so a
    partial update like ``{"data_vendors": {"core_stock_apis": "alpha_vantage"}}``
    keeps the other nested keys; scalar keys are replaced.  The merge happens
    against this thread's existing config (or a fresh copy of the process
    default), so concurrent workers never observe each other's overrides.
    """
    global _config
    initialize_config()
    incoming = deepcopy(config)
    with _lock:
        base = getattr(_tls, "config", None)
        if base is None:
            base = deepcopy(_config)
        for key, value in incoming.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                base[key].update(value)
            else:
                base[key] = value
        _tls.config = base


def get_config() -> dict:
    """Return a deep copy of this thread's config (or the process default)."""
    initialize_config()
    with _lock:
        base = getattr(_tls, "config", None) or _config
        return deepcopy(base)


def reset_config():
    """Reset both the thread override and the process fallback to defaults.

    Intended for tests that need clean isolation; also clears this thread's
    override so a prior ``set_config`` can't leak into the next test.
    """
    global _config
    with _lock:
        _config = deepcopy(default_config.DEFAULT_CONFIG)
        _tls.config = None


# Initialize with default config
initialize_config()

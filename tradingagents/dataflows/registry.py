"""Provider registry + coverage / credentials map (OpenBB P2).

Builds a machine-queryable catalog from the existing ``interface.VENDOR_METHODS``
and ``default_config``: which vendors serve method X, which need which key, and
which params are supported. Lets UIs / CLI / web derive the capability surface
instead of hardcoding it, and lets ``route_to_vendor`` pre-skip missing-key
vendors.
"""

from __future__ import annotations

from typing import Any

from tradingagents.dataflows.interface import VENDOR_METHODS

#: provider -> config key(s) it needs for authentication.
#: Mirrors the config side of default_config (keys are config names, NOT env).
_PROVIDER_CREDENTIAL_KEYS: dict[str, tuple[str, ...]] = {
    "finnhub": ("finnhub_api_key",),
    "massive": ("massive_api_key",),
    "fmp": ("fmp_api_key",),
    "eodhd": ("eodhd_api_key",),
    "alpha_vantage": ("alpha_vantage_api_key",),
    "fred": ("fred_api_key",),
    "alpaca": ("alpaca_api_key_id", "alpaca_api_secret"),
    # yfinance / moomoo(OpenD) / sec_edgar / polymarket need no config key
    # (OpenD login or anonymous) -> no entries.
}


def _all_methods() -> set[str]:
    return set(VENDOR_METHODS)


def coverage(method: str) -> list[str]:
    """Ordered vendor list that can serve ``method`` (from VENDOR_METHODS)."""
    return list(VENDOR_METHODS.get(method, {}).keys())


def all_coverage() -> dict[str, list[str]]:
    """method -> [vendors] for every registered method."""
    return {m: list(vendors.keys()) for m, vendors in VENDOR_METHODS.items()}


def required_credentials(provider: str) -> tuple[str, ...]:
    """Config keys a provider needs to authenticate (empty = keyless)."""
    return _PROVIDER_CREDENTIAL_KEYS.get(provider, ())


def missing_credentials(provider: str, cfg: dict | None = None) -> list[str]:
    """Config keys the provider requires that are unset in ``cfg``."""
    cfg = cfg or {}
    return [k for k in required_credentials(provider) if not cfg.get(k)]


def method_requires_credentials(method: str) -> dict[str, list[str]]:
    """vendor -> missing credential keys for the given method (based on cfg)."""
    out: dict[str, list[str]] = {}
    for v in coverage(method):
        missing = missing_credentials(v)
        if missing:
            out[v] = missing
    return out


def filter_params(method: str, params: dict) -> tuple[dict, list[str]]:
    """Filter unsupported params per the method's vendor signatures.

    Returns ``(kept, warned)`` where ``warned`` lists the params no vendor for
    ``method`` accepts (silent misconfig previously; surfaced now). Uses the
    actual vendor callables' parameter names when available.
    """
    kept = dict(params)
    warned: list[str] = []
    accepted = set()
    for v in coverage(method):
        fn = VENDOR_METHODS[method][v]
        try:
            import inspect

            accepted.update(inspect.signature(fn).parameters)
        except Exception:  # noqa: BLE001 - builtin/wrapped; accept all
            continue
    if accepted:
        warned = [k for k in params if k not in accepted]
        kept = {k: v for k, v in params.items() if k in accepted}
    return kept, warned


def command_map() -> dict[str, dict[str, Any]]:
    """method -> {category?, vendors, requires_credentials, keyless?}.

    A single source the web job menu / CLI / docs can derive from instead of a
    hardcoded allowlist.
    """
    from tradingagents.dataflows.interface import get_category_for_method

    out = {}
    for m in sorted(_all_methods()):
        vendors = coverage(m)
        out[m] = {
            "category": get_category_for_method(m),
            "vendors": vendors,
            "requires_credentials": {
                v: list(required_credentials(v)) for v in vendors
            },
            "keyless": any(not required_credentials(v) for v in vendors),
        }
    return out


def vendor_for_cfg(cfg: dict | None = None) -> list[str]:
    """Reachable vendors given the current config (non-keyless or key set)."""
    cfg = cfg or {}
    out = []
    for v in set(_PROVIDER_CREDENTIAL_KEYS) | {"yfinance", "moomoo", "sec_edgar", "polymarket"}:
        if not required_credentials(v) or not missing_credentials(v, cfg):
            out.append(v)
    return sorted(out)


__all__ = [
    "coverage", "all_coverage", "required_credentials", "missing_credentials",
    "method_requires_credentials", "filter_params", "command_map",
    "vendor_for_cfg",
]

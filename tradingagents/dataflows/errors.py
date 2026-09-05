"""Vendor data-error taxonomy.

A single hierarchy so the routing layer reacts by *behavior*, not by vendor:
every condition where a vendor cannot return usable data derives from
``VendorError``, and the router catches the base types. A new vendor raises
these (or a thin vendor-named subclass) and needs no new ``except`` clause.

    VendorError
    ├── NoMarketDataError          no usable rows (empty result OR stale data)
    ├── VendorRateLimitError       transient throttle -> skip to next vendor
    └── VendorNotConfiguredError   missing API key/config -> vendor unavailable

The number of types is the number of distinct router reactions, not the number
of human-describable causes: empty and stale data get identical handling, so
they share ``NoMarketDataError`` and differ only in the free-text ``detail``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


class VendorError(Exception):
    """Base for any condition where a vendor could not return usable data."""


class NoMarketDataError(VendorError):
    """A vendor returned no usable rows for a symbol (empty result or stale data).

    Carries both the symbol the user requested and the canonical symbol the
    vendor was actually queried with, plus a free-text ``detail``, so callers
    can build a clear message instead of emitting a vendor-specific empty
    string into the data channel.
    """

    def __init__(self, symbol: str, canonical: str | None = None, detail: str = ""):
        self.symbol = symbol
        self.canonical = canonical or symbol
        self.detail = detail
        msg = f"No market data for {symbol!r}"
        if canonical and canonical != symbol:
            msg += f" (queried as {canonical!r})"
        if detail:
            msg += f": {detail}"
        super().__init__(msg)


class VendorRateLimitError(VendorError):
    """A vendor throttled the request; the router skips to the next vendor."""


class VendorNotConfiguredError(VendorError, ValueError):
    """A vendor was selected but its API key/configuration is missing.

    Also a ``ValueError`` so existing callers that catch ``ValueError`` keep
    working while the routing layer can treat it as "vendor unavailable".
    """


@dataclass(frozen=True)
class VendorAbsence:
    """Machine-readable *reason* a vendor chain ended without data (yfinance
    P1 study: typed absence reasons through the read envelope).

    The router already distinguishes *reactions* (``NoMarketDataError`` vs
    ``VendorRateLimitError`` vs ``VendorNotConfiguredError``); this carries
    which kind ended the chain OUT of the router so a run_card / OHLCV
    envelope can audit "ticker not found" apart from "rate-limited" apart
    from "vendor disabled" without re-running the fetch.

    Serializes via ``to_dict()`` (dataclass ``asdict``); defaults keep it
    JSON-safe and null-friendly.
    """

    reason: str = "unknown"
    source: str | None = None
    retryable: bool = False
    detail: str = ""

    @classmethod
    def from_error(cls, error: BaseException, source: str | None = None) -> VendorAbsence:
        """Build from a routed exception (or None -> unknown)."""
        if error is None:
            return cls()
        if isinstance(error, NoMarketDataError):
            return cls(
                reason="no_data",
                source=source,
                retryable=False,
                detail=getattr(error, "detail", "") or "",
            )
        if isinstance(error, VendorRateLimitError):
            return cls(reason="rate_limited", source=source, retryable=True)
        if isinstance(error, VendorNotConfiguredError):
            return cls(reason="not_configured", source=source, retryable=False)
        return cls(reason="error", source=source, retryable=True, detail=str(error))

    def to_dict(self) -> dict:
        return asdict(self)

"""Typed vendor-result envelope (OpenBB P1).

``route_to_vendor`` historically returns one flat string (a report / sentinel).
This module adds an additive typed ``VendorResult`` that carries the result,
provider provenance, warnings and per-format converters (``to_df``/``to_dict``/
``to_llm``) — used by new callers (web endpoints, reporting, dashboards) while
the string path stays for existing strategy callees (clean cutover per item).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class VendorWarning:
    """A surfaced non-fatal issue during a vendor fetch (rate limit, degraded
    vendor, unsupported param...)."""

    kind: str
    message: str

@dataclass
class VendorResult:
    """Typed envelope: results + provider + warnings + metadata + converters.

    - ``results``: the payload (str, list[dict] or dict) or None.
    - ``provider``: which vendor actually served it.
    - ``warnings``: non-fatal issues during the fetch.
    - ``extra``: metadata (fetched_at, url, rows...) for provenance/"Sources".
    - ``error_kind``: a machine-readable error taxonomy name (e.g.
      ``NoMarketDataError``) or None on success — mirrors OpenBB
      ``OpenBBErrorResponse.error_kind``.
    """

    results: Any = None
    provider: str | None = None
    warnings: list[VendorWarning] = field(default_factory=list)
    extra: dict = field(default_factory=dict)
    error_kind: str | None = None
    # DSA research §3.4 honesty fields (advisory; None until populated)
    fallback_from: str | None = None
    is_stale: bool = False
    stale_seconds: float | None = None
    data_quality: str | None = None  # fresh | stale | partial | unknown
    missing_fields: list[str] = field(default_factory=list)
    # Vibe-Trading cross-vendor calibration (honesty): the price adjustment
    # caliber the serving vendor returns and the volume unit of its volume
    # column. None = unknown/unmeasured (never assumed). Values:
    #   price_caliber: adjusted | split_adjusted | raw | unknown
    #   volume_unit: shares | board_lots | contracts | unknown
    price_caliber: str | None = None
    volume_unit: str | None = None

    @property
    def ok(self) -> bool:
        return self.error_kind is None

    def to_dict(self) -> dict:
        """Serializable dict (drops nothing; JSON-safe for a REST response)."""
        return {
            "results": self.results,
            "provider": self.provider,
            "warnings": [{"kind": w.kind, "message": w.message} for w in self.warnings],
            "extra": self.extra,
            "error_kind": self.error_kind,
            "ok": self.ok,
            "fallback_from": self.fallback_from,
            "is_stale": self.is_stale,
            "stale_seconds": self.stale_seconds,
            "data_quality": self.data_quality,
            "missing_fields": self.missing_fields,
            "price_caliber": self.price_caliber,
            "volume_unit": self.volume_unit,
        }

    def to_llm(self) -> str:
        """LLM-friendly rendering: JSON records when results are tabular,
        else the string results (sentinel-safe)."""
        if self.error_kind:
            return f"unavailable ({self.error_kind}): {self.extra.get('detail') or 'no data'}"
        if isinstance(self.results, str):
            return self.results
        if isinstance(self.results, dict) and "closes" in self.results:
            # OHLCV-ish dict -> compact records
            return json.dumps(self.results, default=str)
        if isinstance(self.results, list) and self.results and isinstance(self.results[0], dict):
            try:
                return json.dumps(self.results, default=str)
            except Exception:  # noqa: BLE001
                return str(self.results)
        return str(self.results) if self.results is not None else "unavailable"

    def to_markdown(self) -> str:
        """Compact markdown table for report sections (best-effort)."""
        if self.error_kind:
            return f"**Data unavailable** ({self.error_kind}): {self.extra.get('detail') or ''}"
        if isinstance(self.results, str):
            return self.results
        if isinstance(self.results, list) and self.results and isinstance(self.results[0], dict):
            rows = self.results
            headers = list(rows[0].keys())
            lines = ["| " + " | ".join(str(h) for h in headers) + " |",
                     "| " + " | ".join("---" for _ in headers) + " |"]
            for r in rows[:50]:
                lines.append("| " + " | ".join(str(r.get(h, "")) for h in headers) + " |")
            if len(rows) > 50:
                lines.append(f"_(+{len(rows) - 50} more rows)_")
            return "\n".join(lines)
        return str(self.results) if self.results is not None else "unavailable"

    def __str__(self) -> str:
        return self.to_llm()

__all__ = ["VendorWarning", "VendorResult"]

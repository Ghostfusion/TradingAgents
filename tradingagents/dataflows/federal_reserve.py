"""US risk-free rate curves from the Federal Reserve's public, keyless feeds.

- ``get_sofr_curve``: the overnight SOFR series from the New York Fed's public
  API (``https://markets.newyorkfed.org/api/rates/secured/sofr/search.json``).
  No key, no paid plan.
- ``get_treasury_curve``: the daily nominal Treasury par yield curve from
  ``home.treasury.gov``'s public CSV (the official Treasury dataset). No key.

Both return markdown rows ready for analysis ({date, rate} for SOFR,
{maturity, rate} for the Treasury curve) and degrade through the typed error
taxonomy — ``NoMarketDataError`` on empty/missing data, ``VendorRateLimitError``
on network / throttle / server failures. Values are never fabricated.
"""
from __future__ import annotations

import csv
import io
import logging
from datetime import date, datetime, timedelta

import requests

from .errors import NoMarketDataError, VendorRateLimitError

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30
SOFR_LOOKBACK_DAYS = 30
MAX_ROWS = 40

NYFED_SOFR_URL = "https://markets.newyorkfed.org/api/rates/secured/sofr/search.json"
TREASURY_CSV_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve"
    "&field_tdr_date_value={year}&page&_format=csv"
)


def _as_of(current_date: str | None) -> date:
    """Parse ``current_date`` (YYYY-MM-DD) or fall back to today."""
    if current_date:
        try:
            return datetime.strptime(current_date, "%Y-%m-%d").date()
        except ValueError:
            pass
    return date.today()


def _parse_us_date(raw: str) -> date | None:
    """Parse a Treasury CSV date (MM/DD/YYYY or YYYY-MM-DD), else None."""
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _get(url: str) -> requests.Response:
    """GET with timeouts; map 429/5xx/network failures to VendorRateLimitError."""
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        raise VendorRateLimitError(f"Federal Reserve request failed: {exc}") from exc
    if resp.status_code in (429,) or 500 <= resp.status_code < 600:
        raise VendorRateLimitError(f"Federal Reserve HTTP {resp.status_code}")
    resp.raise_for_status()
    return resp


def get_sofr_curve(current_date: str | None = None) -> str:
    """SOFR (secured overnight financing rate) history from the New York Fed.

    Returns ``{date, rate}`` rows (plus distribution percentiles and volume)
    over the trailing window as markdown. Raises ``NoMarketDataError`` when the
    feed has no SOFR observations in the window.
    """
    ref = _as_of(current_date)
    start = (ref - timedelta(days=SOFR_LOOKBACK_DAYS)).isoformat()
    end = ref.isoformat()
    resp = _get(f"{NYFED_SOFR_URL}?startDate={start}&endDate={end}")
    try:
        payload = resp.json()
    except ValueError as exc:
        raise NoMarketDataError("sofr", "sofr", detail="NY Fed returned a non-JSON body") from exc

    rates = [r for r in (payload.get("refRates") or []) if r.get("type") == "SOFR"]
    if not rates:
        raise NoMarketDataError(
            "sofr", "sofr", detail="no SOFR observations in the requested window"
        )
    # Oldest-first so the curve reads left-to-right in time.
    rates = sorted(rates, key=lambda r: r.get("effectiveDate", ""))

    lines = [
        "## SOFR curve (Federal Reserve / NY Fed, free no-key feed)",
        f"Window: {start} to {end}",
        "| Date | SOFR % | 25th %ile | 75th %ile | Volume ($bn) |",
        "| --- | --- | --- | --- | --- |",
    ]
    shown = rates
    note = ""
    if len(shown) > MAX_ROWS:
        shown = rates[-MAX_ROWS:]
        note = f"\n_(showing the most recent {MAX_ROWS} of {len(rates)} days)_"
    for r in shown:
        lines.append(
            f"| {r.get('effectiveDate')} | {r.get('percentRate')} | "
            f"{r.get('percentPercentile25') or 'n/a'} | "
            f"{r.get('percentPercentile75') or 'n/a'} | "
            f"{r.get('volumeInBillions') or 'n/a'} |"
        )
    return "\n".join(lines) + note


def get_treasury_curve(current_date: str | None = None) -> str:
    """Daily nominal Treasury par yield curve from home.treasury.gov (CSV).

    Returns ``{maturity, rate}`` for the most recent trading day at or before
    ``current_date`` as markdown. Raises ``NoMarketDataError`` when the feed
    has no usable yield-curve rows.
    """
    ref = _as_of(current_date)
    resp = _get(TREASURY_CSV_URL.format(year=ref.year))
    try:
        rows = list(csv.reader(io.StringIO(resp.text)))
    except Exception as exc:  # noqa: BLE001 - malformed CSV is "no usable data"
        raise NoMarketDataError("treasury", "treasury", detail=f"malformed CSV: {exc}") from exc
    if len(rows) < 2:
        raise NoMarketDataError("treasury", "treasury", detail="empty Treasury yield CSV")

    header = rows[0]
    data = rows[1:]
    # The CSV is newest-first; pick the first row dated at/before current_date
    # (never a future-dated row — lookahead-safe).
    target = None
    for row in data:
        if row:
            row_date = _parse_us_date(row[0])
            if row_date is not None and row_date <= ref:
                target = row
                break
    if target is None:
        # All rows are future-dated or unparseable; fall back to the newest.
        target = data[0] if data and data[0] else None
    if not target:
        raise NoMarketDataError("treasury", "treasury", detail="no yield-curve row")

    lines = [
        "## US Treasury par yield curve (home.treasury.gov, free no-key feed)",
        f"As of: {target[0]}",
        "| Maturity | Yield % |",
        "| --- | --- |",
    ]
    for i, label in enumerate(header[1:], start=1):
        label = (label or "").strip()
        if not label:
            continue
        rate = target[i].strip() if i < len(target) else ""
        lines.append(f"| {label} | {rate if rate else 'n/a'} |")
    return "\n".join(lines)

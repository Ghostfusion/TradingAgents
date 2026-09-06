"""US Treasury Fiscal Data vendor (free, keyless) for macro liquidity reads.

Pulls the Daily Treasury Statement **operating cash balance** (the Treasury
General Account, TGA) from the official Treasury Fiscal Data API
(``fiscaldata.treasury.gov``) - the same "US Treasury Fiscal Data" source the
macro spec cites. TGA draws/refills move bank reserves: a falling TGA injects
reserves into the banking system (supportive for risk), a rising TGA drains
them. Purely advisory liquidity context for the macro/news strategist; any
network/service failure degrades to an explicit 'unavailable' string.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_TGA_URL = (
    "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/"
    "v1/accounting/dts/operating_cash_balance"
)
_TIMEOUT = 25
_UA = "tradingagents/0.3 (+https://github.com/TauricResearch/TradingAgents)"
_CLOSING_ACCOUNTS = ("Treasury General Account (TGA) Closing Balance", "TGA Closing Balance", "Operating Cash Balance")


def get_tga_balance(current_date: str | None = None, days: int = 12) -> str:
    """Daily Treasury General Account (TGA / operating cash) balance.

    Returns the latest operating-cash balance, the last ``days`` daily
    records, and a net draw/build read over the window (falling TGA =
    reserve injection, rising = liquidity drain). Keyless.
    """
    try:
        import requests

        resp = requests.get(
            _TGA_URL,
            params={
                "sort": "-record_date",
                "page[size]": str(max(days, 2)),
                "fields": "record_date,account_type,close_today_bal,open_today_bal",
                "format": "json",
            },
            timeout=_TIMEOUT,
            headers={"User-Agent": _UA},
        )
        resp.raise_for_status()
        data = resp.json().get("data") or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("TGA balance fetch failed: %s", exc)
        return f"TGA balance unavailable: {exc}"
    rows = [d for d in data if d.get("account_type") in _CLOSING_ACCOUNTS]
    if not rows:
        rows = [d for d in data if "Closing Balance" in str(d.get("account_type") or "")]
    if not rows:
        rows = data
    if not rows:
        return "TGA balance unavailable: no records returned"
    lines = ["## US Treasury General Account (TGA) — operating cash balance ($B, DTS)", ""]
    vals = []
    for r in rows[:days]:
        d = str(r.get("record_date") or "")
        # The DTS export rides the value in "open_today_bal" while
        # "close_today_bal" is the literal string "null" - treat both as
        # missing when they are None/""/"null".
        raw = None
        for key in ("close_today_bal", "open_today_bal", "current_day_balance"):
            cand = r.get(key)
            if cand not in (None, "", "null"):
                raw = cand
                break
        try:
            b = float(raw)
            vals.append(b)
            lines.append(f"- {d}: {b / 1000:,.1f}B")  # values are $M
        except (TypeError, ValueError):
            lines.append(f"- {d}: n/a")
    if len(vals) >= 2:
        chg = vals[0] - vals[-1]
        lines.append("")
        lines.append(
            f"Net {'draw' if chg < 0 else 'build'} over the window: "
            f"{abs(chg) / 1000:,.1f}B "  # values are $M
            f"({'reserve injection into the banking system' if chg < 0 else 'liquidity drain'})"
        )
    lines.append("")
    lines.append("Source: US Treasury Fiscal Data API (keyless). Advisory liquidity context.")
    return "\n".join(lines)


__all__ = ["get_tga_balance"]

"""FX snapshot vendor (yfinance, free) for the macro/news strategist.

DXY + the major pairs via yfinance tickers (delayed quotes, purely advisory).
Pairs: ^DXY, EURUSD=X, USDJPY=X, GBPUSD=X, USDCNH=X, AUDUSD=X. Any failure
degrades to None (the analysis tool renders an explicit 'unavailable').
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_PAIRS = [
    ("^DXY", "DXY (US dollar index)", "up = USD strength"),
    ("EURUSD=X", "EUR/USD", ""),
    ("USDJPY=X", "USD/JPY", ""),
    ("GBPUSD=X", "GBP/USD", ""),
    ("USDCNH=X", "USD/CNH (offshore)", ""),
    ("AUDUSD=X", "AUD/USD", ""),
]


def get_fx_snapshot(current_date: str | None = None) -> str | None:
    """Latest DXY + major pairs with 1d/5d % changes (delayed, advisory).

    Returns a formatted snapshot string, or None when yfinance cannot serve
    any pair (network/key issue) - the tool turns that into 'unavailable'.
    """
    try:
        import yfinance as yf

        out = []
        for sym, label, note in _PAIRS:
            hist = yf.Ticker(sym).history(period="10d")
            if hist is None or len(hist) < 2:
                continue
            closes = [float(x) for x in hist["Close"].tolist()]
            last = closes[-1]
            d1 = (last / closes[-2] - 1.0) * 100
            five = (last / closes[-6] - 1.0) * 100 if len(closes) >= 6 else float("nan")
            line = f"- {label}: {last:.4f} (1d {d1:+.2f}%, 5d {five:+.2f}%){(' — ' + note) if note else ''}"
            out.append(line)
        if not out:
            return None
        return "## FX snapshot (delayed, advisory)\n" + "\n".join(out)
    except Exception as exc:  # noqa: BLE001
        logger.warning("FX snapshot failed: %s", exc)
        return None


__all__ = ["get_fx_snapshot"]

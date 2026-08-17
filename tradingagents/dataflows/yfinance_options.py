"""Options-market data from yfinance (free, no API key).

Surfaces the options market's *forward-looking* read on a symbol: implied
volatility, put/call open-interest skew, and the put/call ratio. These are
leading positioning/expectation signals that complement the mostly-lagging
price and fundamentals data the other analysts use.

yfinance's options chain has no separate rate tier (it rides the same public
Yahoo endpoint the OHLCV path already uses), so no key or paid plan is needed.
Failures degrade the same way the rest of the yfinance family does: empty /
unavailable chains raise ``NoMarketDataError`` so the router emits one honest
"no data" signal instead of fabricating a value.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from .errors import NoMarketDataError
from .stockstats_utils import yf_retry
from .symbol_utils import normalize_symbol

logger = logging.getLogger(__name__)

# Look forward this many days (from curr_date) for the nearest expiry. Options
# farther out are less informative about near-term positioning; anything nearer
# is illiquid.
_LOOKAHEAD_DAYS = 60


def _nearest_expiry(expiries: list[str], curr_date: str) -> str | None:
    """Pick the nearest expiry at least a few days after curr_date.

    Options at/inside a few days of expiry are dominated by pin/expiry noise and
    thin liquidity; prefer the first expiry comfortably beyond the trade date.
    """
    if not expiries:
        return None
    try:
        cutoff = datetime.strptime(curr_date, "%Y-%m-%d") + timedelta(days=3)
    except ValueError:
        cutoff = datetime.now() + timedelta(days=3)
    for exp in sorted(expiries):
        try:
            if datetime.strptime(exp, "%Y-%m-%d") >= cutoff:
                return exp
        except ValueError:
            continue
    return expiries[-1]


def _option_greeks_row(row) -> dict:
    """Pull the IV / OI / volume fields we care about from one chain row."""
    if row is None:
        return {}
    iv = row.get("impliedVolatility")
    if iv is None and hasattr(row, "impliedVolatility"):
        iv = row.impliedVolatility
    return {
        "strike": row.get("strike") if hasattr(row, "get") else getattr(row, "strike", None),
        "implied_volatility": iv,
        "open_interest": row.get("openInterest") if hasattr(row, "get") else getattr(row, "openInterest", None),
        "volume": row.get("volume") if hasattr(row, "get") else getattr(row, "volume", None),
        "last_price": row.get("lastPrice") if hasattr(row, "get") else getattr(row, "lastPrice", None),
    }


def _mean_iv(rows) -> float | None:
    vals = []
    for r in rows:
        v = r.get("implied_volatility")
        if v is None:
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if f != f:  # NaN is the only float not equal to itself
            continue
        vals.append(f)
    if not vals:
        return None
    return sum(vals) / len(vals)


def _to_int(v) -> int:
    """Safely coerce a chain value to int; None/NaN/non-numeric become 0.

    yfinance option chains carry float ``NaN`` for open interest/volume on many
    rows, and ``int(nan)`` raises ``ValueError`` — so any value that is not a
    finite number contributes 0 to the totals instead of crashing the call.
    """
    if v is None:
        return 0
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0
    if f != f:  # NaN
        return 0
    return int(f)


def get_options_chain_yfinance(ticker: str, curr_date: str = None) -> str:
    """Fetch the nearest-dated options chain and summarize implied vol + put/call.

    Returns a formatted report with:
      - mean at-the-money-ish implied volatility for calls and puts
      - total open interest and volume for calls vs puts
      - the put/call OI ratio and a short interpretation note
    """
    canonical = normalize_symbol(ticker)
    tk = __import__("yfinance", fromlist=["Ticker"]).Ticker(canonical)

    try:
        expiries = yf_retry(lambda: tk.options)
    except Exception as exc:  # noqa: BLE001 — degrade like other yfinance paths
        logger.warning("Options chain unavailable for %s: %s", ticker, exc)
        raise NoMarketDataError(ticker, canonical, "no options expiries returned") from exc

    expiry = _nearest_expiry(expiries or [], curr_date or "")
    if expiry is None:
        raise NoMarketDataError(ticker, canonical, "no options expiries available")

    try:
        chain = yf_retry(lambda: tk.option_chain(expiry))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Options chain fetch failed for %s (%s): %s", ticker, expiry, exc)
        raise NoMarketDataError(ticker, canonical, f"options chain failed for {expiry}") from exc

    calls = [_option_greeks_row(r) for r in (chain.calls.to_dict("records") if hasattr(chain, "calls") else [])]
    puts = [_option_greeks_row(r) for r in (chain.puts.to_dict("records") if hasattr(chain, "puts") else [])]

    if not calls and not puts:
        raise NoMarketDataError(ticker, canonical, f"empty options chain for {expiry}")

    call_iv = _mean_iv(calls)
    put_iv = _mean_iv(puts)
    call_oi = sum(_to_int(r.get("open_interest")) for r in calls)
    put_oi = sum(_to_int(r.get("open_interest")) for r in puts)
    call_vol = sum(_to_int(r.get("volume")) for r in calls)
    put_vol = sum(_to_int(r.get("volume")) for r in puts)

    lines = [
        f"## {ticker.upper()} Options Snapshot (yfinance, expiry {expiry})",
        "",
    ]
    if call_iv is not None:
        lines.append(f"- Call implied vol (mean): {call_iv:.1%}")
    if put_iv is not None:
        lines.append(f"- Put implied vol (mean): {put_iv:.1%}")
    if call_iv is not None and put_iv is not None:
        skew = put_iv - call_iv
        skew_note = "puts richer than calls (downside protection demand)" if skew > 0.02 else (
            "calls richer than puts (upside positioning)" if skew < -0.02 else "roughly balanced"
        )
        lines.append(f"- IV skew (put - call): {skew:+.1%} — {skew_note}")

    lines.append(f"- Call open interest: {call_oi:,}")
    lines.append(f"- Put open interest: {put_oi:,}")
    lines.append(f"- Call volume: {call_vol:,}")
    lines.append(f"- Put volume: {put_vol:,}")

    if put_oi > 0:
        pc_oi = call_oi / put_oi
        lines.append(f"- Put/Call OI ratio (call/put): {pc_oi:.2f}")
    if put_vol > 0:
        pc_vol = call_vol / put_vol
        lines.append(f"- Put/Call volume ratio (call/put): {pc_vol:.2f}")

    lines.append("")
    lines.append(
        "Interpretation: high put open interest and/or put IV skew indicates "
        "downside hedging demand (bearish/uncertain); high call OI and call-rich "
        "skew indicates upside positioning. Use as a positioning gauge, not a "
        "directional price call."
    )
    return "\n".join(lines)

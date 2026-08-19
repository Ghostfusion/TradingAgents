"""Moomoo OpenAPI data vendor — quote-only, via the local OpenD gateway.

Architecture
------------
  moomoo.py -> moomoo-api SDK -> OpenD (local daemon, TCP) -> Moomoo servers

OpenD is a local gateway you install and log into once (mozmo ID, "remember
password").  This vendor connects to it at ``host:port`` (default 127.0.0.1:11111)
and raises typed errors when:

- OpenD is unreachable / not logged in → ``MoomooNotConfiguredError``
  → the router falls back to the next configured vendor (yfinance, …).
- Quote permission is missing for a symbol → ``NoMarketDataError``
  → the router emits ``NO_DATA_AVAILABLE`` and continues.
- Rate-limit/quota exhausted → ``VendorRateLimitError``
  → the router logs and tries the next vendor.

All SDK calls are lazy and thread-safe (one context per thread).  The module
avoids expensive SDK-side imports at module load so the package can be installed
without a running OpenD.

Market coverage (Yahoo → Moomoo code mapping)
----------------------------------------------
  US AAPL         → US.AAPL
  HK 0700.HK      → HK.00700
  JP 7203.T       → JP.7203
  SH 600519.SS    → SH.600519
  SZ 000001.SZ    → SZ.000001
  AU BHP.AX       → AU.BHP
  CA RY.TO        → CA.RY
  SG D05.SI       → SG.D05
  MY 1155.KL      → MY.1155
  CC BTC-USD      → CC.BTCUSD
  CC BTCUSDT      → CC.BTCUSD
  ^GSPC, index    → (unmapped → NoMarketDataError → falls to yfinance)
  .L, .NS, .BO    → (unmapped → falls to yfinance)
"""

from __future__ import annotations

import atexit
import contextlib
import logging
import os
import socket
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from .config import get_config
from .errors import (
    NoMarketDataError,
    VendorNotConfiguredError,
    VendorRateLimitError,
)
from .symbol_utils import crypto_base

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Typed error for the router
# ---------------------------------------------------------------------------


class MoomooNotConfiguredError(VendorNotConfiguredError):
    """OpenD is unreachable, not logged in, or the SDK is missing.

    A ``VendorNotConfiguredError`` (and thus also a ``ValueError``), so the
    routing layer's "vendor unavailable" handling and existing ``ValueError``
    callers both keep working.
    """


# ---------------------------------------------------------------------------
# Thread-local OpenQuoteContext (lazy, max one per thread)
# ---------------------------------------------------------------------------

_tls = threading.local()
_autostart_attempted = False  # module-level flag: try autostart at most once
_last_probe_fail = 0.0  # monotonic() time of the last failed OpenD probe
_PROBE_FAIL_TTL = 20.0  # skip re-probing for this long after a failure
_PROBE_TIMEOUT = 0.5  # seconds for a single TCP probe

# Live-context registry so atexit can close every thread's gateway connection.
_live_ctxs: set = set()
_ctx_lock = threading.Lock()


def _atexit_close_all():
    """Release all live OpenQuoteContext TCP connections at interpreter exit."""
    _close_all_ctxs()


atexit.register(_atexit_close_all)


def _get_moomoo_config() -> dict:
    """Return a config dict with the moomoo-* keys."""
    cfg = get_config()
    return {
        "host": cfg.get("moomoo_host", "127.0.0.1"),
        "port": int(cfg.get("moomoo_port", 11111)),
        "account": cfg.get("moomoo_account") or None,
        "autostart": bool(cfg.get("moomoo_autostart", False)),
        "opend_path": cfg.get("moomoo_opend_path") or None,
    }


def _opend_reachable(host: str, port: int, timeout: float = _PROBE_TIMEOUT) -> bool:
    """TCP connect check — pure probe, no data sent."""
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return True
    except OSError:
        return False


def _probe_or_use_cache(host: str, port: int) -> bool:
    """Probe OpenD, caching a negative verdict for a short TTL.

    A filtered/unreachable port can cost the full TCP timeout on every call
    (e.g. 1 s on a black-holed port), so once a probe fails we treat the
    gateway as down for ``_PROBE_FAIL_TTL`` seconds instead of re-probing
    on every vendor call.  This keeps the fallback-to-yfinance path cheap
    inside a single run.
    """
    global _last_probe_fail
    now = time.monotonic()
    if now - _last_probe_fail < _PROBE_FAIL_TTL:
        return False
    if _opend_reachable(host, port):
        return True
    _last_probe_fail = time.monotonic()
    return False


def _find_opend_executable() -> str | None:
    """Search likely locations for the GUI OpenD exe.

    The GUI version is named ``moomoo_OpenD*`` (with underscore) on Windows,
    **not** the CLI ``MoomooOpenD.exe``.  Returns the first match, or None.

    Search order (fast first):
    1. Explicit path from config (``moomoo_opend_path``).
    2. Common app-local directories (APPDATA, LOCALAPPDATA, Program Files).
    3. Desktop, user home.
    4. Other drives (D:\\, E:\\) — only when the user has set an account
       (a sign they intend to use moomoo autostart).
    """
    exe_candidates = ["moomoo_OpenD.exe", "FutuOpenD.exe", "OpenD-GUI.exe"]
    cfg = _get_moomoo_config()
    explicit = cfg.get("opend_path")
    if explicit:
        p = Path(explicit)
        if p.is_file():
            return str(p.resolve())

    roots: list[str] = []
    for env_var in ("APPDATA", "LOCALAPPDATA"):
        val = os.environ.get(env_var)
        if val:
            roots.append(val)
    for env_var in ("PROGRAMFILES", "PROGRAMFILES(X86)", "USERPROFILE"):
        val = os.environ.get(env_var)
        if val:
            roots.append(val)
    home = os.environ.get("USERPROFILE")
    if home:
        desktop = os.path.join(home, "Desktop")
        if os.path.isdir(desktop):
            roots.append(desktop)
    # Full drive walks are slow; only scan extra drives when the user has
    # opted into autostart (account id set in config).
    if cfg.get("account"):
        for letter in ("D:", "E:"):
            candidate = os.path.join(letter, os.sep)
            if os.path.exists(candidate):
                roots.append(candidate)

    for root in roots:
        if not os.path.isdir(root):
            continue
        for exe in exe_candidates:
            for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
                # Prune the walk beyond 3 levels so a huge drive (e.g. D:\\)
                # is not scanned in full on a failed autostart attempt.
                rel = os.path.relpath(dirpath, root)
                depth = 0 if rel == "." else rel.count(os.sep) + 1
                if depth > 3:
                    dirnames[:] = []
                    continue
                for fname in filenames:
                    if fname.lower() == exe.lower():
                        return os.path.join(dirpath, fname)
    return None


def _autostart_opend() -> bool:
    """Launch OpenD with the remembered-login account, then wait for the port.

    Attempts at most once per process (``_autostart_attempted`` flag).  Returns
    True when the port becomes reachable, False otherwise.
    """
    global _autostart_attempted
    if _autostart_attempted:
        return False
    _autostart_attempted = True

    cfg = _get_moomoo_config()
    if not cfg["autostart"]:
        return False
    exe_path = _find_opend_executable()
    if exe_path is None:
        logger.info(
            "Moomoo autostart: OpenD executable not found. "
            "Install OpenD from https://www.moomoo.com/download/OpenAPI "
            "or set TRADINGAGENTS_MOOMOO_OPEND_PATH."
        )
        return False
    account = cfg.get("account")
    if not account:
        logger.info(
            "Moomoo autostart: no account id (set TRADINGAGENTS_MOOMOO_ACCOUNT). "
            "Launching OpenD without auto-login — you may need to log in manually."
        )
    try:
        import subprocess

        args = [exe_path]
        if account:
            args.append(f"-login_account={account}")
            args.append("-login_by_remember=1")
        subprocess.Popen(args, shell=False)
        logger.info("Moomoo autostart: launched %s", exe_path)
    except OSError as exc:
        logger.warning("Moomoo autostart: failed to launch %s: %s", exe_path, exc)
        return False
    # Poll for the port to come up (up to 45 s)
    host, port = cfg["host"], cfg["port"]
    for _ in range(60):  # 60 × 0.75 s = 45 s
        time.sleep(0.75)
        if _opend_reachable(host, port, timeout=0.5):
            logger.info("Moomoo autostart: OpenD is now reachable on %s:%s", host, port)
            return True
    logger.warning(
        "Moomoo autostart: OpenD did not become reachable on %s:%s within 45 s", host, port
    )
    return False


def _max_open_ctxs() -> int:
    """Connection cap (default 24, safely under OpenD's 128 limit)."""
    try:
        return int(get_config().get("moomoo_max_connections", 25) or 25)
    except Exception:
        return 25


def _cap_open_ctxs():
    """Close oldest live contexts until under the cap (LRU-ish, thread-safe).

    Parallel batch workers each spawn their own thread-local OpenQuoteContext;
    without a cap the gateway hits its 128-connection limit and new contexts
    fail with 'The number of connections exceeds 128'.
    """
    limit = _max_open_ctxs()
    with _ctx_lock:
        while len(_live_ctxs) > limit:
            victim = next(iter(_live_ctxs))
            _live_ctxs.discard(victim)
            with contextlib.suppress(Exception):
                victim.close()


def _ensure_ctx():
    """Return a thread-local ``OpenQuoteContext``, or raise ``MoomooNotConfiguredError``."""
    ctx = getattr(_tls, "moomoo_ctx", None)
    if ctx is not None:
        return ctx
    cfg = _get_moomoo_config()
    host, port = cfg["host"], cfg["port"]
    if not _probe_or_use_cache(host, port):
        if _autostart_opend() and _probe_or_use_cache(host, port):
            pass  # autostart succeeded
        else:
            raise MoomooNotConfiguredError(
                f"OpenD is not reachable on {host}:{port}. "
                "Ensure OpenD (mozmo OpenD gateway) is running and logged in. "
                "Install from https://www.moomoo.com/download/OpenAPI"
            )
    try:
        from moomoo import OpenQuoteContext

        ctx = OpenQuoteContext(host=host, port=port, ai_type=1)
    except ImportError as exc:
        raise MoomooNotConfiguredError(
            "mozmo-api SDK is not installed. Run: pip install moomoo-api"
        ) from exc
    except Exception as exc:
        raise MoomooNotConfiguredError(f"Failed to create OpenQuoteContext: {exc}") from exc
    _tls.moomoo_ctx = ctx
    with _ctx_lock:
        _live_ctxs.add(ctx)
    _cap_open_ctxs()
    return ctx


def _close_ctx():
    """Close the current thread's context (e.g. on shutdown or reconnect)."""
    ctx = getattr(_tls, "moomoo_ctx", None)
    if ctx is not None:
        with contextlib.suppress(Exception):
            ctx.close()
        _tls.moomoo_ctx = None
        with _ctx_lock:
            _live_ctxs.discard(ctx)


def close_context():
    """Public helper: close this thread's OpenQuoteContext (no-op when unused).

    Call at the end of a run so the SDK's background threads tear down while
    the process is healthy (closing at interpreter exit can block on the
    now-dead receive loop).
    """
    _close_ctx()


def _close_all_ctxs(timeout: float = 3.0):
    """Close every live context; never blocks process exit.

    ``ctx.close()`` performs a network round-trip that can block indefinitely
    if the context's receive loop is already gone (interpreter shutdown). Each
    close runs on a *daemon* thread joined with ``timeout``, so a stuck close
    cannot hold the interpreter alive.
    """
    with _ctx_lock:
        live = list(_live_ctxs)
        _live_ctxs.clear()
        _tls.moomoo_ctx = None
    for ctx in live:
        closer = threading.Thread(target=ctx.close, daemon=True)
        closer.start()
        closer.join(timeout)


def _close_all_ctxs():
    """Close every live context (atexit). Batch workers hold one TCP connection
    per thread for the whole process; this releases them at interpreter exit."""
    with _ctx_lock:
        live = list(_live_ctxs)
        _live_ctxs.clear()
    for ctx in live:
        with contextlib.suppress(Exception):
            ctx.close()


# ---------------------------------------------------------------------------
# Error classification helper
# ---------------------------------------------------------------------------

_RET_OK = 0
_RET_ERROR = -1


def _check_ret(ret_code, data, symbol: str, canonical: str, action: str = "request"):
    """Check the SDK return code and raise a typed error on failure.

    :raises MoomooNotConfiguredError:  OpenD not logged in / no account.
    :raises VendorRateLimitError:      rate limit or quota exhausted.
    :raises NoMarketDataError:         permission denied, no data, or empty result.
    :returns:                          the data on success.
    """
    if ret_code == _RET_OK:
        return data
    # Error path — data is an error string
    msg = str(data) if data is not None else str(ret_code)
    msg_lower = msg.lower()
    # Login / account errors
    login_keywords = (
        "login",
        "no available",
        "unlock",
        "unauthorized",
        "not logged in",
        "账号未登录",
        "请先登录",
    )
    if any(kw in msg_lower for kw in login_keywords):
        raise MoomooNotConfiguredError(f"OpenD login required for {action} on {symbol}: {msg}")
    # Permission / quote-right errors
    perm_keywords = (
        "permission",
        "no permission",
        "authority",
        "no authority",
        "bmp",
        "lv1",
        "lv2",
        "lv3",
        "quota",
        "not purchased",
        "未开通",
        "未购买",
        "权限不足",
    )
    if any(kw in msg_lower for kw in perm_keywords):
        raise NoMarketDataError(symbol, canonical, detail=f"quote permission: {msg}")
    # Rate limit
    if any(kw in msg_lower for kw in ("429", "too many", "rate limit", "throttle")):
        raise VendorRateLimitError(f"mozmo rate limit: {msg}")
    # Everything else — treat as "no data" so the router falls back
    raise NoMarketDataError(symbol, canonical, detail=msg)


# ---------------------------------------------------------------------------
# Ticker conversion: Yahoo → Moomoo code
# ---------------------------------------------------------------------------

# Market suffix → Moomoo prefix + optional code-format rule
_MARKET_MAP: dict[str, tuple[str, bool]] = {
    # suffix: (moomoo_prefix, is_digit_fill)
    ".HK": ("HK.", True),  # 0700.HK → HK.00700  (pad to 5 digits)
    ".T": ("JP.", False),  # 7203.T → JP.7203
    ".SS": ("SH.", False),  # 600519.SS → SH.600519
    ".SZ": ("SZ.", False),  # 000001.SZ → SZ.000001
    ".AX": ("AU.", False),  # BHP.AX → AU.BHP
    ".TO": ("CA.", False),  # RY.TO → CA.RY
    ".SI": ("SG.", False),  # D05.SI → SG.D05
    ".KL": ("MY.", False),  # 1155.KL → MY.1155
}

# Dotted suffixes that moomoo does NOT cover. These must raise a typed
# NoMarketDataError so the router falls back to yfinance instead of
# silently re-interpreting e.g. AZN.L as a US ticker.
_UNSUPPORTED_SUFFIXES = (".L", ".NS", ".BO")

# Crypto bases that map to CC. prefix
_CRYPTO_BASES = frozenset(
    {"BTC", "ETH", "SOL", "XRP", "ADA", "DOGE", "LTC", "BCH", "DOT", "AVAX", "LINK"}
)


def _moomoo_code(symbol: str) -> str:
    """Convert a Yahoo-style ticker to a Moomoo code.

    Raises ``NoMarketDataError`` when the symbol's market is not covered by
    moomoo (fell through to unmapped suffixes like ``.L``, ``.NS``, ``.BO``,
    or indices like ``^GSPC``).
    """
    raw = symbol.strip()
    upper = raw.upper()
    # 1. Crypto (BTC-USD, BTCUSDT, etc.)
    base = crypto_base(raw)
    if base and base in _CRYPTO_BASES:
        return f"CC.{base}USD"
    # 2. Indices starting with ^ — not supported
    if upper.startswith("^"):
        raise NoMarketDataError(symbol, symbol, detail="moomoo does not support this index symbol")
    # 3. Known exchange suffixes
    for suffix, (prefix, do_fill) in _MARKET_MAP.items():
        if upper.endswith(suffix):
            code = upper[: -len(suffix)]
            if do_fill:
                with contextlib.suppress(ValueError):
                    code = f"{int(code):05d}"  # non-numeric codes keep as-is
            return f"{prefix}{code}"
    # 4. Dotted but explicitly unsupported markets (LSE, India, …)
    if any(upper.endswith(suf) for suf in _UNSUPPORTED_SUFFIXES):
        raise NoMarketDataError(
            symbol,
            symbol,
            detail=f"moomoo does not cover the '{upper.rsplit('.', 1)[-1]}' market",
        )
    # 5. Bare ticker, or a US-style dotted ticker (BRK.B, BF.B) → US
    return f"US.{upper}"


# ---------------------------------------------------------------------------
# Vendor functions (called by route_to_vendor)
# ---------------------------------------------------------------------------


def get_stock_data_moomoo(symbol: str, start_date: str, end_date: str) -> str:
    """OHLCV via ``request_history_kline``, formatted as CSV (matching yfinance shape)."""
    code = _moomoo_code(symbol)
    ctx = _ensure_ctx()
    ret, data, _page_key = ctx.request_history_kline(
        code,
        start=start_date,
        end=end_date,
        ktype="K_DAY",
        autype="qfq",
        max_count=1000,
    )
    _check_ret(ret, data, symbol, code, "request_history_kline")
    df: pd.DataFrame = data
    if df.empty:
        # NB: request_history_kline returns an empty DataFrame when there are
        # no trading days in the range (e.g. a future date).  Raise a typed
        # error so the router falls through cleanly.
        raise NoMarketDataError(
            symbol,
            code,
            detail=f"no kline rows between {start_date} and {end_date}",
        )
    # Rename columns to match the yfinance-style CSV shape
    df = df.rename(
        columns={
            "time_key": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        }
    )
    # Keep only the columns the rest of the pipeline expects, in a FIXED order
    # (set-based selection produced run-to-run column reordering).
    ordered = [c for c in ("Date", "Open", "High", "Low", "Close", "Volume") if c in df.columns]
    df = df[ordered]
    # Round numeric columns
    for col in ("Open", "High", "Low", "Close"):
        if col in df.columns:
            df[col] = df[col].round(2)
    csv = df.to_csv(index=False)
    header = (
        f"# Stock data for {code} (from {symbol}) from {start_date} to {end_date}\n"
        f"# Total records: {len(df)}\n"
        f"# Data retrieved via moomoo OpenAPI on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    )
    return header + csv


def get_indicators_moomoo(
    symbol: str,
    indicator: str,
    curr_date: str,
    look_back_days: int = 30,
) -> str:
    """Fetch klines from moomoo, then compute the indicator via stockstats.

    Mirrors the yfinance vendor's local computation path (``_get_stock_stats_bulk``)
    so the output format is identical and the analyst prompt sees the same shape
    regardless of which vendor served the request.

    Stockstats indicators need warm-up bars (SMA200 needs 200, MACD ~35, ...);
    the yfinance path hides this by loading 5 years of data. Moomoo fetches a
    ``max(look_back_days * 2 + 100, 300)``-day window and reports only the last
    ``look_back_days`` so warm-up seeds never reach the report.
    """
    from stockstats import wrap

    code = _moomoo_code(symbol)
    ctx = _ensure_ctx()
    end_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    warmup_days = max(look_back_days * 2 + 100, 300)
    start_dt = end_dt - timedelta(days=warmup_days)
    ret, data, _page_key = ctx.request_history_kline(
        code,
        start=start_dt.strftime("%Y-%m-%d"),
        end=curr_date,
        ktype="K_DAY",
        autype="qfq",
        max_count=1000,
    )
    _check_ret(ret, data, symbol, code, "request_history_kline")
    df: pd.DataFrame = data
    if df.empty:
        raise NoMarketDataError(symbol, code, detail="no kline data for indicator calculation")
    # Build a stockstats-compatible DataFrame
    ss_df = pd.DataFrame(
        {
            "Date": pd.to_datetime(df["time_key"]),
            "Open": df["open"].astype(float),
            "High": df["high"].astype(float),
            "Low": df["low"].astype(float),
            "Close": df["close"].astype(float),
            "Volume": df["volume"].astype(float),
        }
    )
    ss = wrap(ss_df)
    # stockstats names the indicator column by its key, e.g. "close_50_sma"
    lower_ind = indicator.lower().strip()
    try:
        ss[lower_ind]  # trigger computation
    except Exception as exc:
        raise NoMarketDataError(
            symbol,
            code,
            detail=f"stockstats indicator '{lower_ind}' computation failed: {exc}",
        ) from exc
    # Report only the last ``look_back_days`` calendar days (warm-up trimmed).
    cutoff = (end_dt - timedelta(days=look_back_days)).strftime("%Y-%m-%d")
    lines: list[str] = []
    for _, row in ss.iterrows():
        date_str = (
            row["Date"].strftime("%Y-%m-%d")
            if hasattr(row["Date"], "strftime")
            else str(row["Date"])
        )
        if date_str < cutoff:
            continue
        val = row[lower_ind]
        if pd.isna(val) or val is None or val == "":
            val_str = "N/A"
        else:
            val_str = f"{val:.4f}" if isinstance(val, float) else str(val)
        lines.append(f"{date_str}: {val_str}")
    # Description from the yfinance vendor's best_ind_params
    description = _INDICATOR_DESCRIPTIONS.get(lower_ind, "")
    sep = "\n\n"
    return (
        f"## {lower_ind} values from {cutoff} to {curr_date} (moomoo):"
        + sep
        + sep.join(lines)
        + sep
        + description
    )


_INDICATOR_DESCRIPTIONS = {
    "close_50_sma": "50 SMA: A medium-term trend indicator. Usage: Identify trend direction and serve as dynamic support/resistance.",
    "close_200_sma": "200 SMA: A long-term trend benchmark. Usage: Confirm overall market trend and identify golden/death cross setups.",
    "close_10_ema": "10 EMA: A responsive short-term average. Usage: Capture quick shifts in momentum and potential entry points.",
    "macd": "MACD: Computes momentum via differences of EMAs. Usage: Look for crossovers and divergence as signals of trend changes.",
    "macds": "MACD Signal: An EMA smoothing of the MACD line. Usage: Use crossovers with the MACD line to trigger trades.",
    "macdh": "MACD Histogram: Shows the gap between the MACD line and its signal. Usage: Visualize momentum strength and spot divergence early.",
    "rsi": "RSI: Measures momentum to flag overbought/oversold conditions. Usage: Apply 70/30 thresholds and watch for divergence to signal reversals.",
    "boll": "Bollinger Middle: A 20 SMA serving as the basis for Bollinger Bands.",
    "boll_ub": "Bollinger Upper Band: Typically 2 standard deviations above the middle line.",
    "boll_lb": "Bollinger Lower Band: Typically 2 standard deviations below the middle line.",
    "atr": "ATR: Averages true range to measure volatility. Usage: Set stop-loss levels and adjust position sizes based on current market volatility.",
    "vwma": "VWMA: A moving average weighted by volume. Usage: Confirm trends by integrating price action with volume data.",
    "mfi": "MFI: The Money Flow Index — a momentum indicator that uses both price and volume to measure buying and selling pressure.",
}


# ---------------------------------------------------------------------------
# Fundamentals
# ---------------------------------------------------------------------------

_STATEMENT_TYPE_INCOME = 1
_STATEMENT_TYPE_BALANCE = 2
_STATEMENT_TYPE_CASHFLOW = 3

_FINANCIAL_TYPE_ANNUAL = 7
_FINANCIAL_TYPE_QUARTERLY_COMBO = 9


def _report_date(rpt) -> datetime.date | None:
    """Best-effort parse of a report's publication date; None if unparseable.

    The SDK exposes the date as either ``date_time_str`` (string, e.g. ``2025-12-31``)
    or ``date_time`` (epoch seconds)."""
    raw = rpt.get("date_time_str") or rpt.get("date_time") or ""
    if not raw:
        return None
    if isinstance(raw, (int, float)) or (isinstance(raw, str) and raw.isdigit()):
        try:
            return datetime.fromtimestamp(int(raw)).date()
        except (OSError, OverflowError, ValueError):
            return None
    try:
        return datetime.strptime(str(raw)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _format_financials(code: str, data: dict, label: str, curr_date: str = None) -> str:
    """Format the dict returned by get_financials_statements into a markdown table.

    When ``curr_date`` is given, reports published after it are dropped so the
    analyst never sees statements dated past the trading day (look-ahead guard,
    mirroring the alpha_vantage vendor). Reports whose date cannot be parsed are
    kept rather than risk hiding a usable statement.
    """
    structure = data.get("structure_list") or []
    reports = data.get("report_list") or []
    if not reports:
        return f"No {label} data available for {code}"
    if curr_date:
        try:
            cutoff = datetime.strptime(curr_date, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            cutoff = None
        if cutoff is not None:
            kept = []
            for rpt in reports:
                rpt_date = _report_date(rpt)
                if rpt_date is None or rpt_date <= cutoff:
                    kept.append(rpt)
            reports = kept
            if not reports:
                return f"No {label} data available for {code} on or before {curr_date}"
    id_to_name = {e["field_id"]: e.get("display_name", f"field_{e['field_id']}") for e in structure}
    lines = [f"## {label} — {code}", ""]
    for rpt in reports[:4]:  # most recent 4 periods
        period = rpt.get("period_text") or rpt.get("date_time_str") or "?"
        fiscal_year = rpt.get("fiscal_year") or ""
        currency = rpt.get("currency_code") or ""
        lines.append(f"### {period}  (FY {fiscal_year}, currency: {currency})")
        items = rpt.get("item_list") or []
        table = ["| Item | Value | YoY | QoQ |", "| --- | --- | --- | --- |"]
        for item in items:
            fid = item.get("field_id")
            name = id_to_name.get(fid, str(fid))
            val = _fmt_fin_val(item.get("data"), currency)
            yoy = _fmt_fin_pct(item.get("yoy"))
            qoq = _fmt_fin_pct(item.get("qoq"))
            table.append(f"| {name} | {val} | {yoy} | {qoq} |")
        lines.extend(table)
        lines.append("")
    return "\n".join(lines)


def _fmt_fin_val(v, currency: str = ""):
    if v is None:
        return "--"
    try:
        fv = float(v)
        prefix = (
            "$" if not currency or currency.upper() in ("USD", "HKD", "SGD") else f"{currency} "
        )
        if abs(fv) >= 1e9:
            return f"{prefix}{fv / 1e9:.2f}B"
        if abs(fv) >= 1e6:
            return f"{prefix}{fv / 1e6:.2f}M"
        if abs(fv) >= 1e3:
            return f"{prefix}{fv / 1e3:.2f}K"
        return f"{prefix}{fv:,.2f}"
    except (TypeError, ValueError):
        return str(v) if v else "--"


def _fmt_fin_pct(v):
    if v is None:
        return "--"
    try:
        return f"{float(v):.2f}%"
    except (TypeError, ValueError):
        return "--"


def _get_financials(
    symbol: str,
    statement_type: int,
    label: str,
    freq: str = "annual",
    curr_date: str = None,
) -> str:
    """Fetch and format a statement, honoring the tool-level freq/curr_date args.

    ``freq`` selects the annual (7) vs quarterly (9) financial report type on the
    moomoo SDK; the quarterly type is the combined-quarter breakdown. ``curr_date``
    is passed through to ``_format_financials`` as a look-ahead guard.
    """
    code = _moomoo_code(symbol)
    ctx = _ensure_ctx()
    financial_type = (
        _FINANCIAL_TYPE_QUARTERLY_COMBO
        if str(freq).strip().lower() == "quarterly"
        else _FINANCIAL_TYPE_ANNUAL
    )
    ret, data = ctx.get_financials_statements(
        code,
        statement_type=statement_type,
        financial_type=financial_type,
        num=8,
    )
    _check_ret(ret, data, symbol, code, f"get_financials ({label})")
    return _format_financials(code, data, label, curr_date=curr_date)


def get_fundamentals_moomoo(symbol: str, curr_date: str = None) -> str:
    """Return a combined fundamentals overview (income + balance + cash flow).

    ``curr_date`` is optional (the tool always passes it) and acts as a look-ahead
    guard on each statement. The overview uses the annual report type, matching the
    pre-existing behavior.
    """
    income = _get_financials(
        symbol, _STATEMENT_TYPE_INCOME, "Income Statement", "annual", curr_date
    )
    balance = _get_financials(symbol, _STATEMENT_TYPE_BALANCE, "Balance Sheet", "annual", curr_date)
    cashflow = _get_financials(symbol, _STATEMENT_TYPE_CASHFLOW, "Cash Flow", "annual", curr_date)
    return f"{income}\n\n{balance}\n\n{cashflow}"


def get_balance_sheet_moomoo(symbol: str, freq: str = "quarterly", curr_date: str = None) -> str:
    return _get_financials(symbol, _STATEMENT_TYPE_BALANCE, "Balance Sheet", freq, curr_date)


def get_cashflow_moomoo(symbol: str, freq: str = "quarterly", curr_date: str = None) -> str:
    return _get_financials(symbol, _STATEMENT_TYPE_CASHFLOW, "Cash Flow", freq, curr_date)


def get_income_statement_moomoo(symbol: str, freq: str = "quarterly", curr_date: str = None) -> str:
    return _get_financials(symbol, _STATEMENT_TYPE_INCOME, "Income Statement", freq, curr_date)


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------


def get_news_moomoo(symbol: str, start_date: str, end_date: str) -> str:
    """Search news for the ticker via ``get_search_news``."""
    code = _moomoo_code(symbol)
    ctx = _ensure_ctx()
    ret, data = ctx.get_search_news(code, max_count=20)
    _check_ret(ret, data, symbol, code, "get_search_news")
    df: pd.DataFrame = data
    if df.empty:
        return f"No news found for {symbol} (moomoo)"
    lines = [f"## {symbol} News — Moomoo", ""]
    for _, row in df.iterrows():
        title = row.get("title") or "(no title)"
        content = row.get("content") or ""
        news_time = row.get("time") or row.get("date") or ""
        source = row.get("source") or ""
        if content:
            content = str(content).replace("\n", " ").strip()[:200]
        lines.append(f"- **{title}**  ({news_time} {source})")
        if content:
            lines.append(f"  {content}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Options
# ---------------------------------------------------------------------------


def get_options_chain_moomoo(symbol: str, curr_date: str = None) -> str:
    """Fetch the nearest-dated options chain: implied vol, put/call OI, ratio."""
    code = _moomoo_code(symbol)
    ctx = _ensure_ctx()
    # Get expiration dates
    ret, exp_data = ctx.get_option_expiration_date(code)
    _check_ret(ret, exp_data, symbol, code, "get_option_expiration_date")
    if exp_data is None or exp_data.empty:
        raise NoMarketDataError(symbol, code, detail="no option expiration dates")
    try:
        import pandas as pd

        expiry = str(pd.to_datetime(exp_data.iloc[0]["time"]).strftime("%Y-%m-%d"))
    except Exception:
        expiry = ""
    # Fetch the chain for the nearest expiry
    ret, chain_data, _next_key = ctx.get_option_chain(code, start=expiry, end=expiry)
    _check_ret(ret, chain_data, symbol, code, "get_option_chain")
    if chain_data is None or chain_data.empty:
        raise NoMarketDataError(symbol, code, detail=f"empty option chain for {expiry}")
    # Format: similar to yfinance_options output
    calls = (
        chain_data[chain_data.get("option_type", "") == "CALL"]
        if "option_type" in chain_data.columns
        else chain_data
    )
    puts = (
        chain_data[chain_data.get("option_type", "") == "PUT"]
        if "option_type" in chain_data.columns
        else chain_data
    )
    call_iv = (
        calls["implied_vol"].mean() if "implied_vol" in calls.columns and not calls.empty else None
    )
    put_iv = (
        puts["implied_vol"].mean() if "implied_vol" in puts.columns and not puts.empty else None
    )
    call_oi = (
        int(calls["open_interest"].sum())
        if "open_interest" in calls.columns and not calls.empty
        else 0
    )
    put_oi = (
        int(puts["open_interest"].sum())
        if "open_interest" in puts.columns and not puts.empty
        else 0
    )
    call_vol = int(calls["volume"].sum()) if "volume" in calls.columns and not calls.empty else 0
    put_vol = int(puts["volume"].sum()) if "volume" in puts.columns and not puts.empty else 0

    def _fmt_iv(v):
        """Normalize moomoo implied vol: 0-1 fractions and 0-100+ percentages."""
        if v is None:
            return None
        f = float(v)
        if 0.0 <= f < 10.0:
            return f  # fraction (e.g. 0.319 = 31.9%)
        return f / 100.0  # percent (e.g. 31.9)

    call_iv_n = _fmt_iv(call_iv)
    put_iv_n = _fmt_iv(put_iv)
    lines = [
        f"## {symbol} Options Snapshot (moomoo, expiry {expiry})",
        "",
    ]
    if call_iv_n is not None:
        lines.append(f"- Call implied vol (mean): {call_iv_n:.1%}")
    if put_iv_n is not None:
        lines.append(f"- Put implied vol (mean):  {put_iv_n:.1%}")
    if call_iv_n is not None and put_iv_n is not None:
        skew = put_iv_n - call_iv_n
        skew_note = (
            "puts richer than calls (downside protection demand)"
            if skew > 0.02
            else (
                "calls richer than puts (upside positioning)"
                if skew < -0.02
                else "roughly balanced"
            )
        )
        lines.append(f"- IV skew (put - call): {skew:+.1%} — {skew_note}")
    lines.append(f"- Call open interest: {call_oi:,}")
    lines.append(f"- Put open interest:  {put_oi:,}")
    if put_oi > 0:
        lines.append(f"- Put/Call OI ratio (call/put): {call_oi / put_oi:.2f}")
    if put_vol > 0:
        lines.append(f"- Put/Call volume ratio (call/put): {call_vol / put_vol:.2f}")
    lines.append("")
    lines.append(
        "Interpretation: high put open interest and/or put IV skew indicates "
        "downside hedging demand (bearish/uncertain); high call OI and call-rich "
        "skew indicates upside positioning. Use as a positioning gauge, not a "
        "directional price call."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Short interest
# ---------------------------------------------------------------------------


def get_short_interest_moomoo(symbol: str) -> str:
    """Short interest via ``get_short_interest``."""
    code = _moomoo_code(symbol)
    ctx = _ensure_ctx()
    ret, us_df, hk_df = ctx.get_short_interest(code)
    _check_ret(ret, (us_df, hk_df), symbol, code, "get_short_interest")
    is_us = code.startswith("US.")
    df = us_df if is_us else hk_df
    if df is None or df.empty:
        raise NoMarketDataError(symbol, code, detail="no short interest data")
    df = df.copy()
    for col in ("timestamp",):
        if col in df.columns:
            df = df.drop(columns=[col], errors="ignore")
    lines = [f"## Short Interest — {symbol} (moomoo)", ""]
    for _, row in df.iterrows():
        lines.append(f"- Settlement date: {row.get('timestamp_str', '?')}")
        for key, label in [
            ("shares_short", "Shares Short"),
            ("short_percent", "Short % of Float"),
            ("avg_daily_share_volume", "Avg Daily Share Volume"),
            ("days_to_cover", "Days to Cover"),
            ("close_price", "Close Price"),
            ("last_close_price", "Last Close Price"),
        ]:
            val = row.get(key)
            if val is not None and val != "":
                lines.append(f"  - {label}: {val}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Analyst ratings
# ---------------------------------------------------------------------------


def get_analyst_ratings_moomoo(symbol: str) -> str:
    """Analyst consensus via ``get_research_analyst_consensus``."""
    code = _moomoo_code(symbol)
    ctx = _ensure_ctx()
    ret, data = ctx.get_research_analyst_consensus(code)
    _check_ret(ret, data, symbol, code, "get_research_analyst_consensus")
    if not data or not isinstance(data, dict):
        raise NoMarketDataError(symbol, code, detail="no analyst consensus data")
    lines = [f"## Analyst Consensus — {symbol} (moomoo)", ""]
    rating = data.get("rating", "")
    highest = data.get("highest", "")
    average = data.get("average", "")
    lowest = data.get("lowest", "")
    total = data.get("total", "")
    lines.append(f"- Rating: {rating}")
    lines.append(f"- Price target: high={highest}, mean={average}, low={lowest}")
    if total:
        lines.append(f"- Analysts covering: {total}")
    update_time = data.get("update_time_str", "")
    if update_time:
        lines.append(f"- Last updated: {update_time}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Earnings calendar
# ---------------------------------------------------------------------------


def get_earnings_calendar_moomoo(symbol: str, curr_date: str, look_back_days: int = 30) -> str:
    """Earnings calendar via ``get_earnings_calendar``, filtered by symbol.

    The moomoo calendar caps its date window at **7 days** and is anchored on
    the requested date, so we look *forward* from ``curr_date`` (the tool's
    "upcoming earnings" semantic) for at most 7 days; anything the caller
    asked for beyond that is clamped.  When no entry for the symbol falls in
    the window, a typed ``NoMarketDataError`` is raised so the router falls
    back to Finnhub.
    """
    code = _moomoo_code(symbol)
    # Derive the market from the code prefix (e.g. US. → "US")
    market_key = code.split(".")[0] if "." in code else "US"
    ctx = _ensure_ctx()
    start_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    window_days = min(int(look_back_days or 7), 7)  # API caps the window at 7 days
    end_dt = start_dt + timedelta(days=window_days)
    ret, data = ctx.get_earnings_calendar(
        market=market_key,
        begin_date=start_dt.strftime("%Y-%m-%d"),
        end_date=end_dt.strftime("%Y-%m-%d"),
    )
    _check_ret(ret, data, symbol, code, "get_earnings_calendar")
    df: pd.DataFrame = data
    if df.empty:
        raise NoMarketDataError(
            symbol,
            code,
            detail=f"no earnings calendar entries in the {window_days}-day window",
        )
    # Filter rows for our symbol when the response carries a code column
    # (moomoo codes look like US.AAPL / HK.00700).
    if "code" in df.columns:
        df = df[df["code"].str.contains(code.split(".")[-1], case=False, na=False)]
    if df.empty:
        raise NoMarketDataError(
            symbol,
            code,
            detail=f"no earnings entries for {symbol} in the {window_days}-day window",
        )
    lines = [f"## Earnings Calendar — {symbol} (moomoo)", ""]
    for _, row in df.head(5).iterrows():
        date = row.get("date") or row.get("time") or "?"
        eps_est = row.get("eps_estimate") or row.get("q1_eps_estimate") or ""
        eps_act = row.get("eps_actual") or row.get("q1_eps_actual") or ""
        surprise = row.get("surprise") or ""
        lines.append(f"- {date}: EPS est={eps_est}, actual={eps_act}, surprise={surprise}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Insider transactions
# ---------------------------------------------------------------------------


def get_insider_transactions_moomoo(symbol: str) -> str:
    """Insider trades via ``get_insider_trade_list``."""
    code = _moomoo_code(symbol)
    ctx = _ensure_ctx()
    ret, data = ctx.get_insider_trade_list(code)
    _check_ret(ret, data, symbol, code, "get_insider_trade_list")
    df: pd.DataFrame = data
    if df.empty:
        raise NoMarketDataError(symbol, code, detail="no insider trade data")
    lines = [f"## Insider Transactions — {symbol} (moomoo)", ""]
    for _, row in df.head(10).iterrows():
        name = row.get("name") or "?"
        title = row.get("title") or ""
        tx_type = row.get("transaction_type") or ""
        shares = row.get("trade_shares")
        price = row.get("max_price") or row.get("min_price")
        date = row.get("max_trade_date_str") or row.get("min_trade_date_str") or "?"
        source = row.get("source_group_name") or ""
        shares_str = (
            f"{shares:+,}" if isinstance(shares, (int, float)) and shares else str(shares or "?")
        )
        price_str = f"{price:.2f}" if isinstance(price, (int, float)) else str(price or "?")
        lines.append(
            f"- {date}: {name} ({title}) — {tx_type} {shares_str} @ {price_str} ({source})"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Macro indicators
# ---------------------------------------------------------------------------


def get_macro_indicators_moomoo(
    indicator: str, curr_date: str, look_back_days: int | None = None
) -> str:
    """Map common FRED-style indicator names to moomoo indicator IDs and fetch history.

    The mapping is limited to the most common macro series.  Unrecognised
    indicators raise ``NoMarketDataError`` (falls to FRED, which is the
    primary source for this category).
    """
    _MACRO_ID_MAP = {
        "cpi": "US.CPI",
        "core_pce": "US.PCE",
        "unemployment": "US.UNEMPLOYMENT",
        "fed_funds_rate": "US.FFR",
        "10y_treasury": "US.GT10",
        "yield_curve": "US.GT10_2",
        "gdp": "US.GDP",
        "nonfarm_payrolls": "US.NFP",
        "retail_sales": "US.RETAIL",
    }
    ind = indicator.lower().strip()
    if ind not in _MACRO_ID_MAP:
        raise NoMarketDataError(
            indicator,
            indicator,
            detail=f"moomoo does not have a mapping for '{indicator}'; falls back to FRED",
        )
    code = _MACRO_ID_MAP[ind]
    ctx = _ensure_ctx()
    max_count = min(look_back_days, 500) if look_back_days is not None else 365
    ret, data = ctx.get_macro_indicator_history(code, max_count=max_count)
    _check_ret(ret, data, indicator, code, "get_macro_indicator_history")
    df: pd.DataFrame = data
    if df.empty:
        raise NoMarketDataError(indicator, code, detail="no macro indicator history")
    lines = [f"## {indicator.upper()} — Moomoo", ""]
    for _, row in df.head(30).iterrows():
        t = row.get("time") or row.get("date") or "?"
        val = row.get("value") or row.get("close") or ""
        lines.append(f"- {t}: {val}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Prediction markets (event contracts)
# ---------------------------------------------------------------------------


def get_prediction_markets_moomoo(topic: str | None = None, limit: int | None = None) -> str:
    """Live prediction-market probabilities via Moomoo event contracts.

    Navigates the event-contract hierarchy — category → series → event →
    contract — then snapshots the active contracts to read their implied
    YES probabilities (the ``price`` of a YES contract, 0–1).  Mirrors the
    Polymarket vendor's output shape so the news-analyst prompt sees the
    same markdown regardless of which vendor served the call.

    Availability: event contracts are server-gated to Moomoo SG/MY accounts;
    for other regions the SDK returns a permission error, which ``_check_ret``
    maps to ``NoMarketDataError`` and the router falls back to Polymarket.
    """
    ctx = _ensure_ctx()
    limit = limit or 6
    topic_lower = (topic or "").lower().strip()

    # 1. Top-level categories (category / category_name / tags)
    ret, cats = ctx.get_event_contract_category()
    _check_ret(
        ret,
        cats,
        topic_lower or "prediction_market",
        "event_contract",
        "get_event_contract_category",
    )
    if cats is None or cats.empty:
        raise NoMarketDataError(
            topic_lower or "prediction_market",
            "event_contract",
            detail="no event contract categories",
        )

    # 2. Match the topic against category names / tags (case-insensitive).
    #    No topic or no match → use the first two categories as a default.
    matched: list[dict] = []
    for row in cats.to_dict("records"):
        name = str(row.get("category_name") or row.get("category") or "")
        tags = str(row.get("tags") or "")
        if not topic_lower or topic_lower in name.lower() or topic_lower in tags.lower():
            matched.append(row)
    if not matched:
        matched = cats.to_dict("records")[:2]

    # 3. Walk category → series → event → contract codes.  Each step degrades
    #    independently (empty/short series, non-dict payloads, …).
    contract_codes: list[str] = []
    for cat_row in matched[:2]:
        cat_id = cat_row.get("category") or cat_row.get("category_id") or cat_row.get("id")
        if not cat_id:
            continue
        try:
            ret, series_df = ctx.get_event_contract_series_list(category=cat_id)
        except Exception:
            continue
        if ret != _RET_OK or series_df is None or series_df.empty:
            continue
        for _, srow in series_df.head(3).iterrows():
            series_code = srow.get("series_code") or srow.get("code") or srow.get("series")
            if not series_code:
                continue
            try:
                ret, events_df = ctx.get_event_contract_event_list(series_code)
            except Exception:
                continue
            if ret != _RET_OK or events_df is None or events_df.empty:
                continue
            for _, erow in events_df.head(2).iterrows():
                event_code = erow.get("event_code") or erow.get("code")
                if not event_code:
                    continue
                try:
                    ret, cdata, _page = ctx.get_event_contract(event_code, count=20)
                except Exception:
                    continue
                if ret != _RET_OK or not isinstance(cdata, dict):
                    continue
                clist = cdata.get("contract_list")
                if clist is None or clist.empty:
                    continue
                for code in clist["contract_code"].dropna().astype(str).tolist():
                    contract_codes.append(code)
            if len(contract_codes) >= limit:
                break
        if len(contract_codes) >= limit:
            break

    if not contract_codes:
        raise NoMarketDataError(
            topic_lower or "prediction_market",
            "event_contract",
            detail=f"no contracts matched the topic '{topic_lower}'",
        )

    # 4. Batch snapshot for live YES prices (cap the batch at 20 contracts).
    ret, snap = ctx.get_event_contract_snapshot(contract_codes[: min(limit, 20)])
    _check_ret(
        ret,
        snap,
        topic_lower or "prediction_market",
        "event_contract",
        "get_event_contract_snapshot",
    )
    if snap is None or snap.empty:
        raise NoMarketDataError(
            topic_lower or "prediction_market",
            "event_contract",
            detail="no event contract snapshots",
        )

    # 5. Format — keep only open contracts (0 < price < 1; resolved sit at 0/1).
    header = (
        f'## Moomoo prediction markets: "{topic or "default"}"\n'
        "Live, market-implied probabilities (YES contract price). A probability "
        "is the crowd's priced odds of the event, not a forecast you should "
        "take as certain.\n\n"
    )
    lines: list[str] = [header]
    shown = 0
    for _, row in snap.iterrows():
        if shown >= limit:
            break
        price = row.get("price")
        try:
            price = float(price)
        except (TypeError, ValueError):
            continue
        if not (0.0 < price < 1.0):
            continue  # resolved contracts sit at 0 or 1
        code = row.get("code", "")
        name = row.get("name") or row.get("yes_sub_title") or code
        vol = row.get("cumulative_volume") or row.get("volume_24h") or 0
        try:
            vol = float(vol)
        except (TypeError, ValueError):
            vol = 0
        lines.append(f"- **{name}** — Yes {price:.0%} (${vol:,.0f} cumulative volume, code {code})")
        shown += 1
    if shown == 0:
        lines.append("(no open contracts with live prices matched)")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Tier 1: capital flow + smart-money (institutional) signals
# ---------------------------------------------------------------------------


def get_capital_flow_moomoo(ticker: str, curr_date: str = None) -> str:
    """Capital inflow/outflow by order size (weekly) + intraday distribution.

    ``get_capital_flow`` (weekly buckets) shows net money flow split by order
    size (super/big/mid/small); ``get_capital_distribution`` shows the capital
    in/out split across size buckets for the latest session.  A weekly view is
    used because the intraday period is only meaningful for a live session.
    ``curr_date`` anchors the weekly window (last 8 weeks up to that date).
    """
    code = _moomoo_code(ticker)
    ctx = _ensure_ctx()
    kwargs = {}
    if curr_date:
        end_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        kwargs = {
            "start": (end_dt - timedelta(days=56)).strftime("%Y-%m-%d"),
            "end": curr_date,
        }
    ret, flow_df = ctx.get_capital_flow(code, period_type="WEEK", **kwargs)
    _check_ret(ret, flow_df, ticker, code, "get_capital_flow")
    ret2, dist_df = ctx.get_capital_distribution(code)
    _check_ret(ret2, dist_df, ticker, code, "get_capital_distribution")

    lines = [f"## Capital Flow — {ticker} (moomoo)", ""]
    if isinstance(flow_df, pd.DataFrame) and not flow_df.empty:
        lines.append("### Weekly net inflow by order size (negative = outflow)")
        lines.append("| Week | Net | Super | Big | Mid | Small | Main |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for _, row in flow_df.head(8).iterrows():
            wk = str(row.get("capital_flow_item_time", ""))[:10]

            def _fmt_flow(v):
                return f"{v / 1e8:+.1f}B" if isinstance(v, (int, float)) else "N/A"

            lines.append(
                f"| {wk} | {_fmt_flow(row.get('in_flow'))} | {_fmt_flow(row.get('super_in_flow'))} "
                f"| {_fmt_flow(row.get('big_in_flow'))} | {_fmt_flow(row.get('mid_in_flow'))} "
                f"| {_fmt_flow(row.get('sml_in_flow'))} | {_fmt_flow(row.get('main_in_flow'))} |"
            )
        lines.append("")
    if isinstance(dist_df, pd.DataFrame) and not dist_df.empty:
        lines.append("### Latest session capital distribution (in / out)")
        lines.append("| Bucket | In | Out |")
        lines.append("| --- | --- | --- |")
        row = dist_df.iloc[0]
        for bucket, in_key, out_key in [
            ("Super", "capital_in_super", "capital_out_super"),
            ("Big", "capital_in_big", "capital_out_big"),
            ("Mid", "capital_in_mid", "capital_out_mid"),
            ("Small", "capital_in_small", "capital_out_small"),
        ]:
            iv, ov = row.get(in_key), row.get(out_key)
            ivs = f"{iv / 1e8:+.1f}B" if isinstance(iv, (int, float)) else "N/A"
            ovs = f"{ov / 1e8:+.1f}B" if isinstance(ov, (int, float)) else "N/A"
            lines.append(f"| {bucket} | {ivs} | {ovs} |")
    lines.append("")
    lines.append(
        "Interpretation: sustained large/super order outflows (with price flat or "
        "falling) suggest institutional distribution; sustained inflows suggest "
        "accumulation. Use as a positioning gauge, not a directional call."
    )
    # L2: deterministic flow signal so ratio math is not left to the LLM.
    try:
        from tradingagents.strategies.orderflow import summarize

        if isinstance(dist_df, pd.DataFrame) and not dist_df.empty:
            row0 = dist_df.iloc[0]
            buckets = {
                k: row0.get(k)
                for k in (
                    "capital_in_super",
                    "capital_out_super",
                    "capital_in_big",
                    "capital_out_big",
                    "capital_in_mid",
                    "capital_out_mid",
                    "capital_in_small",
                    "capital_out_small",
                )
            }
            weekly_nets = []
            if isinstance(flow_df, pd.DataFrame) and not flow_df.empty:
                weekly_nets = [
                    float(r.get("in_flow") or 0.0) for _, r in flow_df.head(8).iterrows()
                ]
            signal = summarize(buckets, weekly_nets=weekly_nets)
            lines.append("")
            lines.append("**Flow Signal**")
            lines.append(signal["text"])
    except Exception:  # noqa: BLE001 - enrichment must never break the tool
        pass
    return "\n".join(lines)


def get_smart_money_moomoo(ticker: str) -> str:
    """ARK fund activity in the ticker (a high-profile institutional buyer)."""
    code = _moomoo_code(ticker)
    ctx = _ensure_ctx()
    ret, data = ctx.get_ark_stock_dynamic(code)
    _check_ret(ret, data, ticker, code, "get_ark_stock_dynamic")
    if not isinstance(data, dict):
        raise NoMarketDataError(ticker, code, detail="unexpected ARK response")
    count = data.get("transaction_count", 0) or 0
    net = data.get("net_shares", 0) or 0
    dyn_type = data.get("dynamic_type", "")
    last = data.get("last_transaction_time", "")
    if not count:
        return (
            f"## Smart Money (ARK) — {ticker} (moomoo)\n\n"
            "No recent ARK fund activity for this ticker. This is neutral — "
            "absence of ARK positioning is not a signal either way."
        )
    side = "net BUY" if net > 0 else "net SELL" if net < 0 else "flat"
    return (
        f"## Smart Money (ARK) — {ticker} (moomoo)\n\n"
        f"- Dynamic type: {dyn_type}\n"
        f"- Transactions: {count}\n"
        f"- Net shares: {net:+,}\n"
        f"- Last activity: {last}\n\n"
        f"Interpretation: ARK funds are a high-profile growth investor; sustained "
        f"{side} activity can flag institutional conviction, but is a single "
        f"institution's view — weigh alongside other evidence."
    )


# ---------------------------------------------------------------------------
# Tier 1: scheduled catalysts — economic calendar + Fed watch
# ---------------------------------------------------------------------------


def get_economic_calendar_moomoo(curr_date: str, look_days: int = 14) -> str:
    """Upcoming economic events (CPI, FOMC, payrolls, …) with consensus/actual."""
    ctx = _ensure_ctx()
    start_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    end_dt = start_dt + timedelta(days=look_days)
    ret, data, _next_page, _has_more = ctx.get_economic_calendar(
        begin_date=start_dt.strftime("%Y-%m-%d"),
        end_date=end_dt.strftime("%Y-%m-%d"),
    )
    _check_ret(ret, data, curr_date, "economic_calendar", "get_economic_calendar")
    if data is None or data.empty:
        raise NoMarketDataError(
            curr_date, "economic_calendar", detail="no economic events in window"
        )
    lines = [
        f"## Economic Calendar ({start_dt:%Y-%m-%d} → {end_dt:%Y-%m-%d}) — moomoo",
        "",
        "| Date | Event | Country | Importance | Previous | Consensus | Actual |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for _, row in data.head(15).iterrows():
        ts = row.get("timestamp")
        try:
            d = datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d")
        except (TypeError, ValueError):
            d = str(ts or "?")
        title = str(row.get("title", "?"))
        country = str(row.get("country", ""))
        star = str(row.get("star", ""))
        prev = str(row.get("previous", "")) or "-"
        cons = str(row.get("consensus", "")) or "-"
        actual = str(row.get("actual", "")) or "-"
        lines.append(f"| {d} | {title} | {country} | {star} | {prev} | {cons} | {actual} |")
    lines.append("")
    lines.append(
        "Interpretation: high-importance events (CPI, FOMC, payrolls) are the "
        "dominant short-term catalysts for rates and equities — flag positions "
        "exposed to them."
    )
    return "\n".join(lines)


def get_fed_watch_moomoo() -> str:
    """Market-implied Fed target-rate probabilities for upcoming meetings."""
    ctx = _ensure_ctx()
    ret, data = ctx.get_fed_watch_target_rate()
    _check_ret(ret, data, "fed_watch", "fed_watch", "get_fed_watch_target_rate")
    if data is None or data.empty:
        raise NoMarketDataError("fed_watch", "fed_watch", detail="no fed watch data")
    lines = ["## Fed Watch — market-implied rate probabilities (moomoo)", ""]
    lines.append("| Meeting | Target range | Implied probability |")
    lines.append("| --- | --- | --- |")
    for _, row in data.head(6).iterrows():
        meeting = str(row.get("meeting_date", "?"))
        tgt = str(row.get("target_range", "?"))
        prob = row.get("probability")
        prob_s = f"{float(prob):.1f}%" if isinstance(prob, (int, float)) else str(prob)
        lines.append(f"| {meeting} | {tgt} | {prob_s} |")
    lines.append("")
    lines.append(
        "Interpretation: the implied probability is what the rates market prices "
        "for each target range — a macro anchor for rate-sensitive analysis."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tier 2: breadth, segment revenue, corporate actions, earnings catalyst
# ---------------------------------------------------------------------------


def get_market_breadth_moomoo() -> str:
    """US market breadth: sector heat map + rise/fall distribution."""
    ctx = _ensure_ctx()
    lines = ["## Market Breadth — US (moomoo)", ""]
    try:
        ret, hm = ctx.get_heat_map_data("US", count=8)
        if ret == _RET_OK and isinstance(hm, pd.DataFrame) and not hm.empty:
            lines.append("### Sector heat (top movers)")
            lines.append("| Sector | Change % | Up | Down | Leader |")
            lines.append("| --- | --- | --- | --- | --- |")
            for _, row in hm.head(8).iterrows():
                name = str(row.get("plate_name", "?"))
                chg = row.get("change_rate")
                chg_s = f"{float(chg):+.2f}%" if isinstance(chg, (int, float)) else "-"
                rise, fall = row.get("rise_count", 0), row.get("fall_count", 0)
                leader = str(row.get("leader_stock", ""))
                lines.append(f"| {name} | {chg_s} | {rise} | {fall} | {leader} |")
    except Exception:
        pass
    try:
        ret, rf = ctx.get_rise_fall_distribution(market="US")
        if ret == _RET_OK and isinstance(rf, dict):
            buckets = rf.get("range_list") or []
            if buckets:
                lines.append("")
                lines.append("### Rise/fall distribution (US)")
                lines.append("| Move range | Stocks |")
                lines.append("| --- | --- |")
                for b in buckets[:9]:
                    lo, hi = b.get("left_border"), b.get("right_border")
                    n = b.get("stock_count", 0)
                    lo_s = "-inf" if lo is None or str(lo) == "NEGATIVE_INFINITY" else f"{lo}%"
                    hi_s = "+inf" if hi is None or str(hi) == "POSITIVE_INFINITY" else f"{hi}%"
                    lines.append(f"| {lo_s} … {hi_s} | {n} |")
    except Exception:
        pass
    if len(lines) == 2:
        raise NoMarketDataError("US", "market_breadth", detail="no breadth data")
    lines.append("")
    lines.append(
        "Interpretation: breadth (how many stocks rise vs fall, which sectors lead) "
        "separates idiosyncratic moves from market-wide regimes."
    )
    return "\n".join(lines)


def get_revenue_breakdown_moomoo(ticker: str) -> str:
    """Segment/regional revenue breakdown for the latest reported period."""
    code = _moomoo_code(ticker)
    ctx = _ensure_ctx()
    ret, data = ctx.get_financials_revenue_breakdown(code)
    _check_ret(ret, data, ticker, code, "get_financials_revenue_breakdown")
    if not isinstance(data, dict):
        raise NoMarketDataError(ticker, code, detail="unexpected revenue breakdown response")
    period = data.get("period", "?")
    currency = data.get("currency_code", "")
    items: list[dict] = []
    for bd in data.get("breakdown_list") or []:
        items.extend(bd.get("item_list") or [])
    if not items:
        raise NoMarketDataError(ticker, code, detail="no revenue breakdown items")
    lines = [f"## Revenue Breakdown — {ticker} ({period}, {currency}) (moomoo)", ""]
    lines.append("| Segment | Revenue | Share |")
    lines.append("| --- | --- | --- |")
    for item in items:
        name = str(item.get("name", "?"))
        rev = item.get("main_oper_income")
        rev_s = _fmt_fin_val(rev, currency)
        ratio = item.get("ratio")
        ratio_s = f"{float(ratio):.1f}%" if isinstance(ratio, (int, float)) else "-"
        lines.append(f"| {name} | {rev_s} | {ratio_s} |")
    lines.append("")
    lines.append(
        "Interpretation: segment mix and concentration — a shrinking core segment "
        "or heavy single-segment concentration are quality flags beyond aggregate "
        "revenue growth."
    )
    return "\n".join(lines)


def get_corporate_actions_moomoo(ticker: str) -> str:
    """Dividend history + stock splits (buybacks are HK/A-share only)."""
    code = _moomoo_code(ticker)
    ctx = _ensure_ctx()
    lines = [f"## Corporate Actions — {ticker} (moomoo)", ""]
    try:
        ret, div = ctx.get_corporate_actions_dividends(code)
        if ret == _RET_OK and isinstance(div, dict):
            dl = div.get("dividend_list") or []
            if dl:
                lines.append("### Recent dividends")
                for d in dl[:5]:
                    lines.append(
                        f"- {d.get('statement', '?')} | ex-date {d.get('ex_date', '?')} "
                        f"| record {d.get('record_date', '?')} | payable {d.get('dividend_payable_date', '?')}"
                    )
    except Exception:
        pass
    try:
        ret, sp = ctx.get_corporate_actions_stock_splits(code)
        if ret == _RET_OK and isinstance(sp, dict):
            sl = sp.get("split_list") or []
            if sl:
                lines.append("")
                lines.append("### Stock splits")
                for s in sl[:5]:
                    lines.append(f"- {s.get('statement', s)}")
    except Exception:
        pass
    if len(lines) == 2:
        raise NoMarketDataError(ticker, code, detail="no corporate action data")
    lines.append("")
    lines.append(
        "Interpretation: consistent dividend growth and share buybacks signal "
        "management confidence and shareholder return discipline; splits are "
        "usually cosmetic (note adjustment factors)."
    )
    return "\n".join(lines)


def get_earnings_catalyst_moomoo(ticker: str) -> str:
    """Historical earnings-day reaction: implied move, IV crush, price behavior.

    ``get_financials_earnings_price_history`` returns, per past earnings, the
    implied move (predict_vola_*), the IV crush, and the day-of price range —
    exactly what a trader needs to size catalyst risk before an upcoming print.
    """
    code = _moomoo_code(ticker)
    ctx = _ensure_ctx()
    ret, data = ctx.get_financials_earnings_price_history(code)
    _check_ret(ret, data, ticker, code, "get_financials_earnings_price_history")
    if data is None or data.empty:
        raise NoMarketDataError(ticker, code, detail="no earnings price history")
    lines = [f"## Earnings Catalyst History — {ticker} (moomoo)", ""]
    lines.append("| Period | Pub date | Implied move | IV crush | Day move |")
    lines.append("| --- | --- | --- | --- | --- |")
    for _, row in data.head(8).iterrows():
        period = str(row.get("period_text", "?"))
        pub = str(row.get("pub_trading_day_str", "?"))[:10]
        imp = row.get("predict_vola_ratio_newest")
        imp_s = f"{float(imp):.1f}%" if isinstance(imp, (int, float)) else "-"
        crush = row.get("option_iv_crush")
        crush_s = f"{float(crush):.1f}pp" if isinstance(crush, (int, float)) else "-"
        close, last_close = row.get("close_price"), row.get("last_close_price")
        move = "-"
        if isinstance(close, (int, float)) and isinstance(last_close, (int, float)) and last_close:
            move = f"{(close / last_close - 1) * 100:+.1f}%"
        lines.append(f"| {period} | {pub} | {imp_s} | {crush_s} | {move} |")
    lines.append("")
    lines.append(
        "Interpretation: a large historical implied move + deep IV crush means "
        "earnings is a major single-day catalyst — size positions accordingly and "
        "avoid entering options/stock right before the print unless that risk is "
        "intended."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tier 3: trading-day calendar (exact holding-day counting)
# ---------------------------------------------------------------------------


def get_trading_days_between(symbol: str, start_date: str, end_date: str) -> list[str]:
    """Return the trading dates in [start, end] for the symbol's market.

    Raises ``MoomooNotConfiguredError`` when OpenD is unavailable, so callers
    can fall back to a calendar heuristic; raises ``NoMarketDataError`` when
    the market suffix is not covered.
    """
    code = _moomoo_code(symbol)
    market_key = code.split(".")[0] if "." in code else "US"
    ctx = _ensure_ctx()
    ret, data = ctx.request_trading_days(market=market_key, start=start_date, end=end_date)
    _check_ret(ret, data, symbol, code, "request_trading_days")
    if not isinstance(data, list) or not data:
        raise NoMarketDataError(symbol, code, detail="no trading days returned")
    days: list[str] = []
    for item in data:
        t = item.get("time") if isinstance(item, dict) else None
        if t:
            days.append(str(t)[:10])
    return days


# ---------------------------------------------------------------------------
# Top movers rank (daily-changing universe source: 领涨/领跌榜单)
# ---------------------------------------------------------------------------


def _num_or_none(v):
    """Float a value, mapping None / SDK NoneDataType / NaN to None."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f else None  # NaN check


def _yahoo_style_symbol(security: str) -> str:
    """Convert a moomoo security code (``US.AAPL``, ``HK.00700``) to the
    Yahoo-style ticker the rest of the pipeline expects (``AAPL``, ``0700.HK``).

    Unmapped prefixes (JP/AU/…) fall back to the bare code, which the router
    would treat as US — callers piping non-US markets should double-check the
    mapping themselves.
    """
    sec = str(security or "")
    prefix, sep, rest = sec.partition(".")
    if not sep or not rest:
        return sec
    if prefix == "HK":
        with contextlib.suppress(ValueError):
            return f"{int(rest):05d}.HK"
    return rest  # US.AAPL -> AAPL; unknown prefixes used bare


def get_hot_movers_moomoo(
    count: int = 50,
    market: str = "US",
    min_market_cap: float = 0.0,
) -> list[dict]:
    """The intraday 'hot' master list: gainers + losers, merged and deduped.

    The in-app Heat List (search/trade/news telemetry) is not exposed by any
    moomoo API, so this is its sanctioned stand-in: both sides of the official
    intraday movers rank, sorted by absolute change (hottest first). Callers
    pick the losers subset with change_ratio < 0.
    """
    seen: set = set()
    merged: list[dict] = []
    for direction in ("gainers", "losers"):
        for row in get_top_movers_moomoo(
            sort_dir=direction,
            count=count,
            market=market,
            min_market_cap=min_market_cap,
        ):
            symbol = row["symbol"]
            if symbol in seen:
                continue
            seen.add(symbol)
            merged.append(row)
    merged.sort(key=lambda r: abs(r.get("change_ratio") or 0.0), reverse=True)
    return merged


def get_top_movers_moomoo(
    sort_dir: str = "losers",
    count: int = 50,
    market: str = "US",
    min_market_cap: float = 0.0,
) -> list[dict]:
    """Return the intraday movers rank (领涨/领跌榜) as Yahoo-style symbols.

    Wraps the SDK's ``get_top_movers_rank`` so a daily-changing watchlist
    universe can be built *before* the value screener runs: whichever symbols
    are down/up the most today are the ones screened today.

    :param sort_dir: ``"losers"`` (biggest decliners first) or ``"gainers"``.
    :param count: how many symbols to return (SDK allows 1-200).
    :param market: market key, e.g. ``"US"`` or ``"HK"``.
    :param min_market_cap: optional market-cap floor in USD (skips micro-caps).
    :returns: list of ``{symbol, name, cur_price, change_ratio, change_amount,
        pe_ttm, market_cap, volume}`` sorted with the biggest movers first.
        ``change_ratio`` is a fraction (e.g. ``-0.0324`` = -3.24%).
    :raises MoomooNotConfiguredError: OpenD down / not logged in.
    :raises NoMarketDataError: no quote permission or empty ranking.
    """
    from moomoo import Market, RankSortDir, SimpleRankFilter, SimpleRankIndicatorType

    market_key = str(market).strip().upper()
    market_enum = {"US": Market.US, "HK": Market.HK}.get(market_key, Market.US)
    ascending = str(sort_dir).strip().lower() == "losers"
    filters = None
    try:
        mcap = float(min_market_cap or 0.0)
    except (TypeError, ValueError):
        mcap = 0.0
    if mcap > 0:
        filters = [SimpleRankFilter(SimpleRankIndicatorType.MARKET_CAP, interval_min=mcap)]
    ctx = _ensure_ctx()
    ret, data = ctx.get_top_movers_rank(
        market=market_enum,
        sort_dir=RankSortDir.ASCENDING if ascending else RankSortDir.DESCENDING,
        count=int(count),
        filter_list=filters,
    )
    _check_ret(ret, data, market_key, market_key, "get_top_movers_rank")
    _all_count, df = data
    if df is None or df.empty:
        raise NoMarketDataError(
            market_key,
            market_key,
            detail="top movers rank returned no rows",
        )
    rows: list[dict] = []
    for _, row in df.iterrows():
        change_ratio = _num_or_none(row.get("change_ratio"))
        # The SDK's change_ratio scale varies by market session: some calls
        # return a fraction (-0.2138 = -21.38%), others a percent (-21.38).
        # Normalize to a fraction either way.
        if change_ratio is not None and abs(change_ratio) > 1.5:
            change_ratio /= 100.0
        rows.append(
            {
                "symbol": _yahoo_style_symbol(row.get("security")),
                "name": row.get("name") or "",
                "cur_price": _num_or_none(row.get("cur_price")),
                "change_ratio": change_ratio,
                "change_amount": _num_or_none(row.get("change_amount")),
                "pe_ttm": _num_or_none(row.get("pe_ttm")),
                "market_cap": _num_or_none(row.get("market_cap")),
                "volume": _num_or_none(row.get("volume")),
            }
        )
    return rows


# ---------------------------------------------------------------------------
# A2: institutional ownership (13F-style aggregate, moomoo)
# ---------------------------------------------------------------------------


def get_institution_holdings_moomoo(ticker: str) -> str:
    """Institutional ownership + change by reporting period (shareholders F10).

    ``get_shareholders_institutional`` aggregates the 13F-style holder data:
    institutional share of the float, the change vs the prior period, and the
    number of reporting institutions.  A rising institutional % with price
    stable flags accumulation; a falling % flags distribution.
    """
    code = _moomoo_code(ticker)
    ctx = _ensure_ctx()
    ret, data = ctx.get_shareholders_institutional(code)
    _check_ret(ret, data, ticker, code, "get_shareholders_institutional")
    df = data
    if df is None or df.empty:
        raise NoMarketDataError(ticker, code, detail="no institutional holding data")
    lines = [f"## Institutional Ownership — {ticker} (moomoo)", ""]
    lines.append("| Period | Institutions | Shares held | % of float | Chg (pp) |")
    lines.append("| --- | --- | --- | --- | --- |")
    for _, row in df.head(6).iterrows():
        period = str(row.get("period_text", "?"))
        inst = row.get("institution_quantity")
        inst_s = int(inst) if isinstance(inst, (int, float)) else "n/a"
        qty = row.get("holder_quantity")
        qty_s = (
            f"{qty / 1e9:.2f}B"
            if isinstance(qty, (int, float)) and abs(qty) >= 1e9
            else (f"{qty / 1e6:.1f}M" if isinstance(qty, (int, float)) else "n/a")
        )
        pct = row.get("holder_pct")
        pct_s = f"{float(pct):.1f}%" if isinstance(pct, (int, float)) else "n/a"
        chg = row.get("holder_pct_change")
        chg_s = f"{float(chg):+.1f}pp" if isinstance(chg, (int, float)) else "n/a"
        lines.append(f"| {period} | {inst_s} | {qty_s} | {pct_s} | {chg_s} |")
    lines.append("")
    lines.append(
        "Interpretation: the % of float held by institutions and its period change "
        "is the smart-money ownership signal; a persistent decline can precede "
        "under-performance, a rise can support supply/demand. Weigh alongside "
        "capital flow and price action."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# A3: historical earnings surprises (calendar actuals vs estimates)
# ---------------------------------------------------------------------------


def _earnings_cal_chunks(ctx, market: str, start: str, end: str) -> list:
    """Chunked market earnings calendar (7-days-inclusive per call)."""
    from pandas import concat

    parts = []
    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")
    cur = start_dt
    while cur <= end_dt:
        chunk_end = min(cur + timedelta(days=6), end_dt)
        ret, df = ctx.get_earnings_calendar(
            market=market,
            begin_date=cur.strftime("%Y-%m-%d"),
            end_date=chunk_end.strftime("%Y-%m-%d"),
        )
        if ret == 0 and df is not None and not df.empty:
            parts.append(df)
        cur = chunk_end + timedelta(days=1)
    if not parts:
        return []
    combined = concat(parts, ignore_index=True)
    rows = []
    for r in combined.to_dict("records"):
        rows.append(
            {
                "security": str(r.get("security", "") or ""),
                "date": str(r.get("earnings_date") or "").strip(),
                "eps_predict": _num(r.get("eps_predict")),
                "eps_actual": _num(r.get("eps_actual")),
                "revenue_predict": _num(r.get("revenue_predict")),
                "revenue_actual": _num(r.get("revenue_actual")),
                "ebit_predict": _num(r.get("ebit_predict")),
                "ebit_actual": _num(r.get("ebit_actual")),
            }
        )
    return rows


def _num(v):
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def get_earnings_surprise_history_moomoo(ticker: str, curr_date: str = None) -> str:
    """Earnings surprises + reaction history for the last ~6 prints.

    Combines moomoo's earnings price history (print dates, market-implied
    move, IV crush, day move) with the earnings calendar's actual-vs-estimate
    EPS/revenue/EBIT around those dates, plus the implied move for the upcoming
    print. Deterministic table intended for catalyst-risk and surprise-momentum
    analysis.
    """
    code = _moomoo_code(ticker)
    ctx = _ensure_ctx()
    market = code.split(".")[0] if "." in code else "US"
    ret, hist = ctx.get_financials_earnings_price_history(code)
    _check_ret(ret, hist, ticker, code, "get_financials_earnings_price_history")
    if hist is None or hist.empty:
        raise NoMarketDataError(ticker, code, detail="no earnings price history")

    # Distinct prints (fiscal period -> print date), most recent first.
    prints = []
    seen = set()
    for _, row in hist.iterrows():
        period = str(row.get("period_text") or "")
        pub = str(row.get("pub_trading_day_str") or "")[:10]
        key = (period, pub)
        if not pub or key in seen:
            continue
        seen.add(key)
        prints.append(
            {
                "period": period,
                "date": pub,
                "implied": _num(row.get("predict_vola_ratio_newest")),
                "iv_crush": _num(row.get("option_iv_crush")),
                "close": _num(row.get("close_price")),
                "last_close": _num(row.get("last_close_price")),
            }
        )
    prints.sort(key=lambda p: p["date"], reverse=True)

    # Fetch actuals/estimates for the last several prints via targeted windows.
    cal = []
    for p in prints[:6]:
        day = datetime.strptime(p["date"], "%Y-%m-%d")
        start = (day - timedelta(days=3)).strftime("%Y-%m-%d")
        end = (day + timedelta(days=3)).strftime("%Y-%m-%d")
        window = _earnings_cal_chunks(ctx, market, start, end)
        cal.extend(window)
    cal = [c for c in cal if code.upper() in str(c.get("security") or "").upper()]

    lines = [f"## Earnings Surprise History — {ticker} (moomoo)", ""]
    lines.append("| Period | Date | EPS est | EPS act | Surprise% | Day move | Implied |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for _shown, p in enumerate(prints[:8]):
        date_s = p["date"]
        match = next((c for c in cal if c["date"] == date_s), None)
        est, act = (match or {}).get("eps_predict"), (match or {}).get("eps_actual")
        surprise = ""
        if est is not None and act is not None and est != 0:
            surprise = f"{(act - est) / abs(est) * 100:+.1f}"
        close, last = p.get("close"), p.get("last_close")
        move = ""
        finite = (
            close is not None
            and last is not None
            and close == close
            and last == last
            and last not in (0,)
        )
        if finite:
            move = f"{(close / last - 1) * 100:+.1f}%"
        implied = f"{p['implied']:.1f}%" if p.get("implied") is not None else "-"
        lines.append(
            f"| {p['period']} | {date_s} | {est if est is not None else '-'} | "
            f"{act if act is not None else '-'} | {surprise or '-'} | {move or '-'} | {implied} |"
        )
    lines.append("")
    lines.append(
        "Interpretation: negative-surprise quarters with a large implied move "
        "flag elevated catalyst risk; a succession of beats (acceleration) with "
        "rising implied moves supports momentum. Use for event-risk sizing, not "
        "direction alone."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# A1: option-market expected move (earnings implied move primary)
# ---------------------------------------------------------------------------


def get_expected_move_moomoo(ticker: str, curr_date: str = None) -> str:
    """Expected single-event move for the upcoming earnings print.

    The option market prices the upcoming print's 1-day move via
    ``predict_vola_ratio_newest`` from moomoo's earnings price history (the
    current-period row, falling back to the most recent print). Degrades to a
    typed no-data error when no source serves (the analyst then skips this
    optional signal).
    """
    code = _moomoo_code(ticker)
    ctx = _ensure_ctx()
    current_move = None
    ret, hist = ctx.get_financials_earnings_price_history(code)
    if ret == 0 and hist is not None and not hist.empty:
        rows = hist.to_dict("records")
        for row in rows:
            if bool(row.get("is_current")):
                v = _num(row.get("predict_vola_ratio_newest"))
                if v is not None and v > 0:
                    current_move = v / 100.0
                break
        if current_move is None and rows:
            v = _num((rows[0] or {}).get("predict_vola_ratio_newest"))
            if v is not None and v > 0:
                current_move = v / 100.0
    if current_move is None:
        raise NoMarketDataError(
            ticker,
            code,
            detail="no option-implied move available (moomoo earnings history or options chain)",
        )
    lines = [
        f"## Expected Move — {ticker} (moomoo, option-implied)",
        "",
        f"- Expected 1σ move at next earnings: **{current_move:.1%}**",
        "",
        "Interpretation: the option market's priced move around the upcoming "
        "earnings print. Use to size the event risk (a ±10% expected move "
        "warrants smaller size than ±2%) and set wider stops *through* the "
        "event when the thesis is event-based.",
    ]
    # Append a spot-based band when a recent close is available.
    try:
        end_dt = datetime.strptime(curr_date, "%Y-%m-%d") if curr_date else datetime.now()
        start_dt = end_dt - timedelta(days=21)
        ret2, kdf, _page = ctx.request_history_kline(
            code, start=start_dt.strftime("%Y-%m-%d"), end=end_dt.strftime("%Y-%m-%d"),
            ktype="K_DAY", autype="qfq", max_count=21,
        )
        if ret2 == 0 and kdf is not None and not kdf.empty:
            spot = float(kdf.iloc[-1]["close"])
            hi = spot * (1 + current_move)
            lo = spot * (1 - current_move)
            lines.append(f"- Last close {spot:.2f}; band [{lo:.2f}, {hi:.2f}] (±{current_move:.1%})")
    except Exception:
        pass
    return "\n".join(lines)

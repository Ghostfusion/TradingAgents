"""Value Dip + Swing computed-analysis tools for the analyst LLMs.

Wraps the deterministic ``tradingagents/strategies/value_dip.py`` calculators
as LangChain tools so the agents can ground their "value dip / margin of
safety / oversold / scale-in / expectancy" claims in computed numbers instead
of re-deriving or inventing them (the project's no-fabrication contract).

Each tool is pure/read-only and degrades to an explicit "unavailable" message
when data is missing or the vendor chain fails - the analyst then reports the
signal is unavailable rather than guessing.

Bound to the analyst tool loops in ``graph/trading_graph.py::_create_tool_nodes``
(market node: get_bollinger_pct_b / get_tranche_plan / get_trade_expectancy;
fundamentals node: get_fcf_yield / get_valuation_z_score / get_value_dip_setup).
"""

from __future__ import annotations

from typing import Annotated

from langchain_core.tools import tool

from tradingagents.dataflows.interface import route_to_vendor

# ---------------------------------------------------------------------------
# Shared data helpers (mirror analysis_tools.py conventions)
# ---------------------------------------------------------------------------


def _ohlcv(ticker: str, days: int = 320) -> dict:
    """Daily OHLCV via the vendor chain (Date,Open,High,Low,Close,Volume rows).

    Returns {"dates", "closes", "highs", "lows", "volumes", "opens"} (all
    empty on failure).
    """
    try:
        from datetime import datetime, timedelta

        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        out = route_to_vendor("get_stock_data", ticker, start, end) or ""
        dates, closes, opens, highs, lows, volumes = [], [], [], [], [], []
        for line in out.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.lower().startswith("date,"):
                continue
            parts = line.split(",")
            if len(parts) < 6:
                continue
            try:
                dates.append(parts[0].strip())
                opens.append(float(parts[1]))
                highs.append(float(parts[2]))
                lows.append(float(parts[3]))
                closes.append(float(parts[4]))
                volumes.append(float(parts[5]))
            except ValueError:
                continue
        return {
            "dates": dates,
            "closes": closes,
            "highs": highs,
            "lows": lows,
            "volumes": volumes,
            "opens": opens,
        }
    except Exception:  # noqa: BLE001 - a fetch failure degrades, never raises
        return {
            "dates": [],
            "closes": [],
            "opens": [],
            "highs": [],
            "lows": [],
            "volumes": [],
        }


def _period_price_series(dates: list, closes: list) -> dict:
    """Map each date string -> its close, for pairing period-end prices.

    Returns {} on empty inputs.
    """
    out = {}
    for d, c in zip(dates, closes, strict=False):
        if d:
            out[str(d).strip()] = c
    return out


def _fcf_series_from_cashflow(payload: str) -> list | None:
    """Time-ordered FCF series from a cashflow payload (annual periods).

    Looks for the "Free Cash Flow" row first, else operating cash flow minus
    capex (sign-preserving - the DCF tool's positive-only variant is not
    reused here because a negative FCF year is a real signal for the value
    dip value floor).
    """
    if not payload or str(payload).startswith(("NO_DATA", "DATA_")):
        return None
    try:
        from scripts.value_screener import (
            _markdown_period_tables,
            _parse_csv_statements,
        )

        # moomoo markdown: period tables (newest first) -> per-period row dicts
        try:
            tables = _markdown_period_tables(payload)
        except Exception:  # noqa: BLE001
            tables = []
        if tables:
            series = []
            for _, rows in tables:
                fcf = None
                for label, value in rows.items():
                    low = str(label).lower()
                    if "free cash flow" in low:
                        fcf = value
                        break
                if fcf is None:
                    op = cap = None
                    for label, value in rows.items():
                        low = str(label).lower()
                        if "operating cash flow" in low or "cash flow from operating" in low:
                            op = value
                        if "capital expenditure" in low or "purchase of property" in low:
                            cap = value
                    if op is not None and cap is not None:
                        fcf = float(op) - float(cap)
                if fcf is not None:
                    try:
                        series.append(float(fcf))
                    except (TypeError, ValueError):
                        continue
            return series if series else None

        # yfinance CSV (annual): rightmost numeric cell per row
        rows = _parse_csv_statements(payload)
        if rows:
            fcf = None
            for label, value in rows.items():
                if "free cash flow" in str(label).lower():
                    fcf = value
                    break
            if fcf is None:
                op = cap = None
                for label, value in rows.items():
                    low = str(label).lower()
                    if "operating cash flow" in low or "cash flow from operating" in low:
                        op = value
                    if "capital expenditure" in low or "purchase of property" in low:
                        cap = value
                if op is not None and cap is not None:
                    fcf = float(op) - float(cap)
            if fcf is not None:
                try:
                    return [float(fcf)]
                except (TypeError, ValueError):
                    return None
    except Exception:  # noqa: BLE001 - parsing failure degrades
        return None
    return None


def _canonical_financials(ticker: str, current_date: str) -> dict:
    """Canonical line items via the screener's own fetch_ticker."""
    try:
        from scripts.value_screener import fetch_ticker

        return fetch_ticker(ticker, current_date) or {}
    except Exception:  # noqa: BLE001
        return {}


def _latest(v):
    """Current-period value of a canonical item (flat float or a
    ``{"current": .., "prior": ..}`` dict)."""
    if isinstance(v, dict):
        return v.get("current", v.get("value"))
    return v


def _txt_round(v, nd: int = 4) -> str:
    return f"{v:.{nd}f}" if v is not None else "n/a"


def _txt_pct(v, nd: int = 1) -> str:
    return f"{v:.{nd}%}" if v is not None else "n/a"


# ---------------------------------------------------------------------------
# Market analyst: %b, tranche plan, expectancy
# ---------------------------------------------------------------------------


@tool
def get_bollinger_pct_b(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Bollinger Band %b (price position inside the 20-day, 2-sigma band).

    %b <= 0 means price is at/piercing the lower band; %b <= 0.10 is the
    mean-reversion entry zone of the value-dip framework. Use before any
    'oversold / at the lower Bollinger / mean-reversion entry' claim.
    """
    try:
        from tradingagents.strategies.value_dip import bollinger_pct_b
    except Exception as exc:  # noqa: BLE001
        return f"bollinger %b unavailable for {ticker}: {exc}"
    closes = _ohlcv(ticker).get("closes") or []
    bb = bollinger_pct_b(closes)
    if not bb or bb.get("pct_b") is None:
        return f"bollinger %b unavailable for {ticker}: insufficient price history."
    zone = (
        "lower-band" if bb["pct_b"] <= 0 else ("entry-zone" if bb["pct_b"] <= 0.10 else "mid/high")
    )
    return (
        f"bollinger %b {ticker}: {bb['pct_b']:.2%} ({zone}); "
        f"price={bb['price']:.2f} lower={bb['lower']:.2f} upper={bb['upper']:.2f} mid={bb['mid']:.2f}"
    )


@tool
def get_tranche_plan(
    ticker: Annotated[str, "ticker symbol"],
    weights: Annotated[
        str | None,
        "3 tranche weights as comma-separated fractions summing to 1.0, e.g. '0.3,0.3,0.4'",
    ] = None,
    risk_pct: Annotated[float, "max account risk as a fraction, e.g. 0.015"] = 0.015,
    account: Annotated[float, "account size in $"] = 100_000.0,
) -> str:
    """Three-tranche scale-in plan for a value dip (P1/P2/P3, weighted avg
    entry, composite stop, capital-at-risk check, 1.8R/3.0R targets + blended
    R:R and breakeven win rate).

    P1 = latest close (the signal price), P2 = P1 - 1.0*ATR(14),
    P3 = P1 - 2.0*ATR(14); composite stop = P3 - 1.5*ATR. Sizing uses
    (account * risk_pct) / (avg_entry - stop). Use before proposing a
    scale-in entry or citing tranche levels / blended expectancy.
    """
    try:
        from tradingagents.strategies.size import atr as _atr
        from tradingagents.strategies.value_dip import tranche_plan
    except Exception as exc:  # noqa: BLE001
        return f"tranche plan unavailable for {ticker}: {exc}"
    ohlcv = _ohlcv(ticker)
    closes = ohlcv.get("closes") or []
    highs = ohlcv.get("highs") or []
    lows = ohlcv.get("lows") or []
    if not closes:
        return f"tranche plan unavailable for {ticker}: no price history."
    p1 = float(closes[-1])
    atr_v = _atr(highs, lows, closes, window=14)
    try:
        w = tuple(float(x.strip()) for x in (weights or "0.3,0.3,0.4").split(","))
        if len(w) != 3 or abs(sum(w) - 1.0) > 1e-9:
            return (
                f"tranche plan unavailable for {ticker}: weights must be 3 "
                "comma-separated fractions summing to 1.0."
            )
    except (TypeError, ValueError):
        return f"tranche plan unavailable for {ticker}: malformed weights."
    plan = tranche_plan(p1, atr_v, weights=w, account=account, risk_pct=risk_pct)
    if not plan.get("valid"):
        return f"tranche plan unavailable for {ticker}: {plan.get('reason', 'invalid inputs')}."
    tg = plan["targets"]
    return (
        f"tranche plan {ticker}: P1={plan['p1']:.2f} P2={plan['p2']:.2f} "
        f"P3={plan['p3']:.2f} stop={plan['stop']:.2f} avg_entry={plan['avg_entry']:.2f} "
        f"risk/share={plan['risk_per_share']:.2f} shares={plan['total_shares']} "
        f"(w={plan['weights']} n={plan['shares']}) "
        f"capital_at_risk=${plan['capital_at_risk']:,.0f} vs max ${plan['max_dollar_risk']:,.0f} "
        f"risk_ok={plan['risk_ok']} "
        f"T1={tg['t1']:.2f} (1.8R) T2={tg['t2']:.2f} (3.0R) "
        f"blended_rr={tg['blended_rr']:.2f} breakeven_win_rate={plan['breakeven_win_rate']:.1%}"
    )


@tool
def get_trade_expectancy(
    p_win: Annotated[float, "estimated win probability, 0-1"],
    avg_win: Annotated[float | None, "average win amount in $"] = None,
    avg_loss: Annotated[float | None, "average loss amount in $"] = None,
    rr: Annotated[float | None, "reward-to-risk ratio, e.g. 2.4"] = None,
) -> str:
    """Per-trade mathematical expectancy E = p*W - (1-p)*L and the breakeven
    win rate 1/(1+R:R).

    Pass your estimated win probability and average win/loss amounts; ``rr``
    is optional (breakeven rate renders n/a without it). Use before any
    'this trade has positive expectancy / the win rate needed to break even'
    claim - it is the computed number.
    """
    try:
        from tradingagents.strategies.value_dip import breakeven_win_rate, expectancy
    except Exception as exc:  # noqa: BLE001
        return f"trade expectancy unavailable: {exc}"
    e = expectancy(p_win, avg_win, avg_loss)
    be = breakeven_win_rate(rr)
    if e is None:
        return "trade expectancy unavailable: pass win probability and average win/loss amounts."
    return (
        f"trade expectancy: E=${e:,.2f} per trade (p_win={p_win:.2f} "
        f"avg_win=${avg_win:,.2f} avg_loss=${avg_loss:,.2f}); "
        f"breakeven_win_rate={_txt_pct(be)}"
    )


# ---------------------------------------------------------------------------
# Fundamentals analyst: FCF yield, valuation Z, the hybrid matrix
# ---------------------------------------------------------------------------


@tool
def get_fcf_yield(
    ticker: Annotated[str, "ticker symbol"],
    current_date: Annotated[str, "the current trading date, YYYY-mm-dd"],
) -> str:
    """Free cash flow yield = FCF / market cap.

    The value-dip framework's baseline yield to guard against terminal risk
    during extended consolidations (>= 6% is the matrix's value-floor row).
    Use before any 'strong cash generation / FCF yield supports the value'
    claim.
    """
    try:
        from tradingagents.strategies.value_dip import fcf_yield
    except Exception as exc:  # noqa: BLE001
        return f"fcf yield unavailable for {ticker}: {exc}"
    fin = _canonical_financials(ticker, current_date)
    mc = _latest(fin.get("market_cap"))
    try:
        cf_payload = route_to_vendor("get_cashflow", ticker, "annual", current_date) or ""
        fcf_series = _fcf_series_from_cashflow(cf_payload)
        fcf = fcf_series[0] if fcf_series else None  # newest period first
    except Exception:  # noqa: BLE001
        fcf = None
    fy = fcf_yield(fcf, mc)
    if fy is None:
        return (
            f"fcf yield unavailable for {ticker}: need free cash flow and "
            "market cap from the vendor chain."
        )
    band = "floor-pass" if fy >= 0.06 else "below-floor"
    return f"fcf yield {ticker}: {fy:.2%} ({band}); fcf=${fcf:,.0f} market_cap=${mc:,.0f}"


@tool
def get_valuation_z_score(
    ticker: Annotated[str, "ticker symbol"],
    current_date: Annotated[str, "the current trading date, YYYY-mm-dd"],
    multiple: Annotated[str, "which multiple: 'pe' | 'ev_ebitda' | 'p_fcf'"] = "pe",
) -> str:
    """Historical valuation deviation (Z-score of a multiple vs its own
    history): (multiple_current - mean) / std.

    A Z <= -1.5 means the name trades significantly below its historical
    norm (the framework's value-dip trigger). Supports P/E (default),
    EV/EBITDA and P/FCF. The series is built from the per-period statement
    tables (moomoo concatenated fundamentals markdown: income + balance +
    cashflow, newest first) with the current price as the numerator, so a
    Z <= -1.5 means "today's price is far below the multiple's own norm".
    Use before any 'trades below its historical norm / cheap vs its own
    history' claim.
    """
    try:
        from tradingagents.strategies.value_dip import valuation_z_read
    except Exception as exc:  # noqa: BLE001
        return f"valuation z-score unavailable for {ticker}: {exc}"
    multiple = (multiple or "pe").lower()
    if multiple not in ("pe", "ev_ebitda", "p_fcf"):
        return (
            f"valuation z-score unavailable for {ticker}: multiple must be "
            "'pe', 'ev_ebitda' or 'p_fcf'."
        )
    closes = _ohlcv(ticker).get("closes") or []
    price = float(closes[-1]) if closes else None
    if price is None:
        return f"valuation z-score unavailable for {ticker}: no price history."
    try:
        from scripts.value_screener import _markdown_period_tables

        payload = route_to_vendor("get_fundamentals", ticker, current_date) or ""
        tables = _markdown_period_tables(payload) if payload else []
    except Exception:  # noqa: BLE001
        tables = []
    if not tables:
        return (
            f"valuation z-score unavailable for {ticker}: no per-period "
            "statement tables from the vendor chain."
        )
    series = []
    for _, rows in tables:
        series.append(_period_multiple(rows, multiple, price=price))
    series = [v for v in series if v is not None]
    if len(series) < 4:
        return (
            f"valuation z-score unavailable for {ticker}: need >= 4 historical "
            f"periods of {multiple} from the vendor chain (got {len(series)})."
        )
    read = valuation_z_read(series, series[0], min_n=4)
    if read.get("z") is None:
        return f"valuation z-score unavailable for {ticker}: unquantifiable."
    verdict = read["verdict"]
    note = (
        " (cheap vs history)"
        if verdict == "cheap"
        else (" (rich vs history)" if verdict == "rich" else "")
    )
    return (
        f"valuation z-score {ticker} ({multiple}): z={read['z']:.2f}{note} "
        f"current={_txt_round(series[0])} mean={_txt_round(read['mean'])} "
        f"std={_txt_round(read['std'])} n={read['n']}"
    )


@tool
def get_value_dip_setup(
    ticker: Annotated[str, "ticker symbol"],
    current_date: Annotated[str, "the current trading date, YYYY-mm-dd"],
) -> str:
    """The Value Dip + Swing hybrid allocation matrix as one computed setup.

    Rows: value_floor (margin of safety >= 20% OR FCF yield >= 6%),
    technical_entry (RSI(14) <= 35 AND Bollinger %b <= 0.10),
    trade_risk (ATR stop <= 2% of price), exit_target (R:R >= 2.5 by
    construction). candidate = all gates pass. Call before any 'value dip
    setup / discounted entry with oversold timing' claim.
    """
    try:
        from tradingagents.strategies.value_dip import fcf_yield, value_dip_setup
    except Exception as exc:  # noqa: BLE001
        return f"value dip setup unavailable for {ticker}: {exc}"
    fin = _canonical_financials(ticker, current_date)
    if not fin:
        return (
            f"value dip setup unavailable for {ticker}: no statements from "
            "the vendor chain; do not fabricate value screens."
        )
    mc = _latest(fin.get("market_cap"))
    try:
        cf_payload = route_to_vendor("get_cashflow", ticker, "annual", current_date) or ""
        fcf_series = _fcf_series_from_cashflow(cf_payload)
        fcf = fcf_series[0] if fcf_series else None  # newest period first
    except Exception:  # noqa: BLE001
        fcf = None
    fy = fcf_yield(fcf, mc)
    # margin of safety: reuse the DCF intrinsic when computable, else None.
    mos = None
    try:
        from tradingagents.agents.utils.analysis_tools import get_dcf_valuation

        dcf_out = get_dcf_valuation.invoke({"ticker": ticker, "current_date": current_date})
        mos = margin_of_safety_impl(dcf_out, _ohlcv(ticker).get("closes") or [])
    except Exception:  # noqa: BLE001
        mos = None
    ohlcv = _ohlcv(ticker)
    closes = ohlcv.get("closes") or []
    highs = ohlcv.get("highs") or []
    lows = ohlcv.get("lows") or []
    vols = ohlcv.get("volumes") or []
    setup = value_dip_setup(
        closes,
        highs,
        lows,
        vols,
        margin_of_safety=mos,
        fcf_yield=fy,
        atr_value=None,
    )
    if not setup.get("rows"):
        return f"value dip setup unavailable for {ticker}: insufficient price history."
    rows = setup["rows"]
    vf = rows.get("value_floor") or {}
    te = rows.get("technical_entry") or {}
    tr = rows.get("trade_risk") or {}
    lines = [
        f"value dip setup {ticker}: candidate={setup['candidate']}",
        f"  value_floor: pass={vf.get('pass')} mos={_txt_pct(vf.get('margin_of_safety'))} "
        f"fcf_yield={_txt_pct(vf.get('fcf_yield'))}",
        f"  technical_entry: pass={te.get('pass')} rsi={_txt_round(te.get('rsi'), 2)} "
        f"pct_b={_txt_pct(te.get('pct_b'), 2)}",
        f"  trade_risk: pass={tr.get('pass')} stop_pct={_txt_pct(tr.get('stop_pct'))}",
        f"  exit_target: pass={rows.get('exit_target', {}).get('pass')} rr>=2.5",
    ]
    vz = rows.get("valuation")
    if vz:
        lines.append(f"  valuation: z={_txt_round(vz.get('z'))} verdict={vz.get('verdict')}")
    if setup.get("reasons"):
        lines.append("  reasons: " + "; ".join(setup["reasons"]))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers for the tools above
# ---------------------------------------------------------------------------


def _period_multiple(rows: dict, multiple: str, price: float | None = None) -> float | None:
    """One period's valuation multiple from a row dict (raw period table or
    canonical line items).

    ``rows`` may be a canonical line-item dict (``_latest`` unwraps
    ``{current, prior}``) or a raw moomoo period-table dict with display
    labels (e.g. "Diluted EPS"). The current ``price`` is the numerator for
    P/E and P/FCF (only the current price is available from the vendor layer,
    so the series measures today's price against each period's fundamentals).
    """
    try:
        from scripts.value_screener import _first_number as _fn
    except Exception:  # noqa: BLE001
        _fn = None

    def num(v):
        if v is None:
            return None
        if isinstance(v, dict):
            v = v.get("current", v.get("value"))
        if isinstance(v, str) and _fn is not None:
            v = _fn(v)
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    def find(*needles):
        """Case-insensitive substring match against the row labels.

        Canonical dicts use short keys ("eps") while raw moomoo period tables
        use display names ("Diluted EPS") - match either by substring.
        """
        for label, value in rows.items():
            if str(label).startswith("-"):
                continue  # moomoo sub-item / contra breakdowns
            low = str(label).lower()
            if any(n in low for n in needles) or any(low == n for n in needles):
                return value
        return None

    if multiple == "pe":
        eps = num(find("diluted eps", "earnings per share", "basic eps", "eps"))
        if eps and price:
            return price / eps
        pe = num(find("pe ratio", "price to earnings"))
        if pe:
            return pe
    elif multiple == "ev_ebitda":
        ebitda = num(find("ebitda"))
        if ebitda and price:
            return price / ebitda
        ev = num(find("enterprise value", "ev"))
        if ev and ebitda:
            return ev / ebitda
    elif multiple == "p_fcf":
        fcf = num(find("free cash flow"))
        if fcf and price:
            return price / fcf
    return None


def margin_of_safety_impl(dcf_out: str, closes: list) -> float | None:
    """Best-effort margin of safety from a get_dcf_valuation output string.

    Parses the "fair value" line (``fair value: <x>``) from the DCF tool's
    markdown, then returns (intrinsic - price) / intrinsic using the latest
    close. None when the DCF string or price is unavailable.
    """
    if not dcf_out or not closes:
        return None
    import re

    m = re.search(r"fair value:?\s*\$?([0-9]+(?:\.[0-9]+)?)", dcf_out, re.IGNORECASE)
    if not m:
        return None
    try:
        intrinsic = float(m.group(1))
    except (TypeError, ValueError):
        return None
    price = float(closes[-1])
    if intrinsic <= 0 or price <= 0:
        return None
    return (intrinsic - price) / intrinsic


__all__ = [
    "get_bollinger_pct_b",
    "get_tranche_plan",
    "get_trade_expectancy",
    "get_fcf_yield",
    "get_valuation_z_score",
    "get_value_dip_setup",
]

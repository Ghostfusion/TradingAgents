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
        from tradingagents.dataflows.statement_parsing import (
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
                        # abs(cap): capex may be a negative GAAP outflow or a
                        # positive magnitude depending on the vendor.
                        fcf = float(op) - abs(float(cap))
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
                    fcf = float(op) - abs(float(cap))
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
        from tradingagents.dataflows.statement_parsing import fetch_ticker

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
        from tradingagents.dataflows.statement_parsing import _markdown_period_tables

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
    # Step-1 balance-sheet / profitability inputs from the canonical items.
    d_e = cr = roe = None
    te = _latest(fin.get("total_equity"))
    td = _latest(fin.get("total_debt"))
    if td is not None and te:
        d_e = float(td) / float(te)
    ca_ = _latest(fin.get("current_assets"))
    cl_ = _latest(fin.get("current_liabilities"))
    if ca_ is not None and cl_:
        cr = float(ca_) / float(cl_)
    ne = _latest(fin.get("net_income"))
    if ne is not None and te:
        roe = float(ne) / float(te)
    ohlcv = _ohlcv(ticker)
    closes = ohlcv.get("closes") or []
    highs = ohlcv.get("highs") or []
    lows = ohlcv.get("lows") or []
    vols = ohlcv.get("volumes") or []
    # Hard real data for the regime + re-rating rows: the regime read comes
    # from the actual close series (rolling realized-vol percentile + 200-SMA
    # trend); the re-rating catalyst uses the REAL last EPS surprise from the
    # computed-earnings tool when available (never invented - None on failure).
    regime_row = None
    eps_surprise = None
    try:
        from tradingagents.strategies.regime import regime_gate_read

        try:
            from tradingagents.dataflows.config import get_config as _gc
            _idx_sym = str(_gc().get("market_stress_index") or "").strip()
        except Exception:  # noqa: BLE001
            _idx_sym = ""
        _idx_closes = []
        if _idx_sym:
            try:
                from tradingagents.agents.utils.analysis_tools import _ohlcv as _ot_ohlcv

                _idx_closes = _ot_ohlcv(_idx_sym).get("closes") or []
            except Exception:  # noqa: BLE001
                _idx_closes = []
        regime_row = regime_gate_read(
            closes, cfg=None, catalyst_window=False,
            index_closes=_idx_closes or None,
        ) or None
    except Exception:  # noqa: BLE001 - advisory row degrades to None
        regime_row = None
    try:
        from tradingagents.agents.utils.analysis_tools import get_earnings_surprise

        _sur = get_earnings_surprise.invoke(
            {"ticker": ticker, "current_date": current_date}
        ) or ""
        import re as _re

        m = _re.search(r"[+-]?\d+(?:\.\d+)?%", _sur)
        if m:
            eps_surprise = float(m.group(0).rstrip("%")) / 100.0
    except Exception:  # noqa: BLE001 - degrade to None (no fabrication)
        eps_surprise = None
    setup = value_dip_setup(
        closes,
        highs,
        lows,
        vols,
        margin_of_safety=mos,
        fcf_yield=fy,
        atr_value=None,
        debt_to_equity=d_e,
        current_ratio=cr,
        roe=roe,
        fcf=fcf,
        regime_gate=regime_row,
        eps_surprise=eps_surprise,
        require_knife=bool(
            (__import__("tradingagents.dataflows.config", fromlist=["get_config"]).get_config() or {}).get(
                "value_dip_knife_enable"
            )
        ),
    )
    if not setup.get("rows"):
        return f"value dip setup unavailable for {ticker}: insufficient price history."
    rows = setup["rows"]
    vf = rows.get("value_floor") or {}
    te_ = rows.get("technical_entry") or {}
    tr = rows.get("trade_risk") or {}
    bs = rows.get("balance_sheet") or {}
    prof = rows.get("profitability") or {}
    lines = [
        f"value dip setup {ticker}: candidate={setup['candidate']}",
        f"  value_floor: pass={vf.get('pass')} mos={_txt_pct(vf.get('margin_of_safety'))} "
        f"fcf_yield={_txt_pct(vf.get('fcf_yield'))}",
        f"  technical_entry: pass={te_.get('pass')} rsi={_txt_round(te_.get('rsi'), 2)} "
        f"pct_b={_txt_pct(te_.get('pct_b'), 2)}",
        f"  trade_risk: pass={tr.get('pass')} stop_pct={_txt_pct(tr.get('stop_pct'))}",
        f"  balance_sheet: pass={bs.get('pass')} d_e={_txt_round(bs.get('d_e'))} "
        f"current_ratio={_txt_round(bs.get('current_ratio'))}",
        f"  profitability: pass={prof.get('pass')} fcf_positive={prof.get('fcf_positive')} "
        f"roe={_txt_pct(prof.get('roe'))}",
        f"  exit_target: pass={rows.get('exit_target', {}).get('pass')} rr>=2.5",
    ]
    vz = rows.get("valuation")
    if vz:
        lines.append(f"  valuation: z={_txt_round(vz.get('z'))} verdict={vz.get('verdict')}")
    vdu = rows.get("vdu") or {}
    if vdu:
        tg = (vdu.get("trigger_candle") or {}).get("trigger")
        hll = (vdu.get("higher_low") or {}).get("higher_low")
        mv = (vdu.get("momentum") or {}).get("verdict")
        lines.append(
            f"  vdu_ladder: trigger={tg} higher_low={hll} momentum={mv} candidate={vdu.get('candidate')}"
        )
    mom = rows.get("momentum_divergence") or {}
    if mom:
        lines.append(f"  momentum_divergence: {mom.get('verdict')} bullish={mom.get('bullish')}")
    sup = rows.get("support") or {}
    if sup:
        lines.append(
            f"  support: {sup.get('verdict')} dist_base={_txt_pct(sup.get('distance_to_base_pct'))} "
            f"dist_sma200={_txt_pct(sup.get('distance_to_sma200_pct'))}"
        )
    rg = rows.get("regime_gate") or {}
    if rg.get("verdict"):
        lines.append(
            f"  regime_gate: {rg.get('verdict')} pass={rg.get('pass')} "
            f"vol_pct={_txt_round(rg.get('vol_pct'), 3)} fast_downtrend={rg.get('fast_downtrend')} "
            f"catalyst_window={rg.get('catalyst_window')}"
        )
    rr = rows.get("re_rating") or {}
    if rr.get("measured"):
        lines.append(
            f"  re_rating: pass={rr.get('pass')} evidence={rr.get('evidence') or 'none measured'}"
        )
    kv = rows.get("knife_velocity") or {}
    if kv:
        lines.append(
            f"  knife_velocity: active={kv.get('active')} z={_txt_round(kv.get('velocity_z'), 2)} "
            f"(thr {kv.get('threshold')})"
        )
    kr = rows.get("knife_range") or {}
    if kr:
        lines.append(
            f"  knife_range: active={kr.get('active')} range_atr={kr.get('range_atr_mult')}x "
            f"(max {kr.get('max_mult')}x, close_below_ema={kr.get('close_below_ema')})"
        )
    kf = rows.get("knife_flow") or {}
    if kf:
        lines.append(
            f"  knife_flow: active={kf.get('active')} vpin={kf.get('vpin')} "
            f"delta={kf.get('price_delta')} (thr {kf.get('threshold')})"
        )
    kc = rows.get("knife_composite") or {}
    if kc:
        lines.append(
            f"  knife_composite: K={kc.get('K')} factor={kc.get('factor')} "
            f"band={kc.get('band')} (z_ret={kc.get('z', {}).get('ret')}, "
            f"z_vol={kc.get('z', {}).get('vol')}, z_atr={kc.get('z', {}).get('atr')}, "
            f"z_dd={kc.get('z', {}).get('dd')}, below_ema={kc.get('below_ema')})"
        )
    if setup.get("reasons"):
        lines.append("  reasons: " + "; ".join(setup["reasons"]))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Step-1 + Step-2 gap tools (balance sheet, momentum divergence, VDU ladder,
# support structure, decline driver)
# ---------------------------------------------------------------------------


@tool
def get_balance_sheet_health(
    ticker: Annotated[str, "ticker symbol"],
    current_date: Annotated[str, "the current trading date, YYYY-mm-dd"],
) -> str:
    """Balance-sheet health (Value_Dip_swing.md §1): debt/equity < 1.0 OR
    current ratio > 1.5.

    Use before any 'low leverage / strong balance sheet / low debt profile'
    claim on a value-dip candidate. Degrades to 'unavailable' when neither
    input is measurable.
    """
    try:
        from tradingagents.strategies.value_dip import balance_sheet_health
    except Exception as exc:  # noqa: BLE001
        return f"balance sheet health unavailable for {ticker}: {exc}"
    fin = _canonical_financials(ticker, current_date)
    te = _latest(fin.get("total_equity"))
    td = _latest(fin.get("total_debt"))
    d_e = (float(td) / float(te)) if (td is not None and te) else None
    ca_ = _latest(fin.get("current_assets"))
    cl_ = _latest(fin.get("current_liabilities"))
    cr = (float(ca_) / float(cl_)) if (ca_ is not None and cl_) else None
    out = balance_sheet_health(d_e, cr)
    if out.get("pass") is None:
        return (
            f"balance sheet health unavailable for {ticker}: need debt/equity and "
            "current ratio from the vendor chain."
        )
    return (
        f"balance sheet health {ticker}: pass={out['pass']} d_e={_txt_round(out.get('d_e'))} "
        f"current_ratio={_txt_round(out.get('current_ratio'))}; "
        + "; ".join(out.get("reasons") or [])
    )


@tool
def get_macd_divergence(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Momentum divergence on the Daily RSI(14) / MACD histogram
    (Value_Dip_swing.md §2): a LOWER price low with a HIGHER MACD/RSI low is a
    bullish divergence (mean-reversion entry support); a higher-low is a
    bullish momentum shift. Verdicts: bullish-divergence / higher-low /
    lower-low-confirmation / none / unknown.

    Use before any 'bullish divergence / momentum turning / reversal support'
    claim.
    """
    try:
        from tradingagents.strategies.value_dip import macd_divergence
    except Exception as exc:  # noqa: BLE001
        return f"macd divergence unavailable for {ticker}: {exc}"
    ohlcv = _ohlcv(ticker)
    closes = ohlcv.get("closes") or []
    lows = ohlcv.get("lows") or []
    if len(closes) < 60:
        return f"macd divergence unavailable for {ticker}: insufficient price history."
    m = macd_divergence(closes, lows, window=120)
    if m.get("verdict") == "unknown":
        return f"macd divergence unavailable for {ticker}: insufficient history."
    rsi_note = m.get("rsi_note")
    return (
        f"macd divergence {ticker}: verdict={m['verdict']} bullish={m['bullish']} "
        f"price_lows={m.get('price_lows')} macd_hist_lows={m.get('macd_hist_lows')} "
        + (f"({rsi_note})" if rsi_note else "")
    )


@tool
def get_vdu_entry_setup(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """The Step-2 entry ladder (Value_Dip_swing.md §2): volume dry-up (VDU)
    near support -> momentum divergence / higher-low -> a trigger candle (close
    above the prior day's high, RVOL >= 1.3x). ``candidate`` = trigger AND
    momentum confirmation AND (dry-up not absent).

    Use before proposing an active swing entry out of an oversold dip - it is
    the technical confirmation ladder, distinct from the fundamental value
    gates.
    """
    try:
        from tradingagents.strategies.value_dip import vdu_entry_setup
    except Exception as exc:  # noqa: BLE001
        return f"vdu entry setup unavailable for {ticker}: {exc}"
    ohlcv = _ohlcv(ticker)
    closes = ohlcv.get("closes") or []
    highs = ohlcv.get("highs") or []
    lows = ohlcv.get("lows") or []
    vols = ohlcv.get("volumes") or []
    if len(closes) < 30 or not vols:
        return f"vdu entry setup unavailable for {ticker}: insufficient data."
    vd = vdu_entry_setup(closes, highs, lows, vols)
    dry = vd.get("volume_dry_up") or {}
    trig = vd.get("trigger_candle") or {}
    hl = vd.get("higher_low") or {}
    mom = vd.get("momentum") or {}
    return (
        f"vdu entry setup {ticker}: candidate={vd['candidate']} "
        f"dry_up={dry.get('dry_up')} (ratio={_txt_round(dry.get('vdu_ratio'))}) "
        f"trigger={trig.get('trigger')} (rvol={_txt_round(trig.get('rvol'))}) "
        f"higher_low={hl.get('higher_low')} momentum={mom.get('verdict')}; "
        + ("; ".join(vd.get("reasons") or []) or "ok")
    )


@tool
def get_support_structure(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Major technical support (Value_Dip_swing.md §2): multi-month
    consolidation-base low, 200-day SMA proximity, or holding above a shallow
    base.

    Verdicts: multi-month-base-support / 200-day-sma-support /
    holding-above-base / no-near-support / unknown. Use before any 'at major
    support / near the 200-day / multi-month base' claim. Requires 200+ closes.
    """
    try:
        from tradingagents.strategies.value_dip import support_structure
    except Exception as exc:  # noqa: BLE001
        return f"support structure unavailable for {ticker}: {exc}"
    ohlcv = _ohlcv(ticker)
    closes = ohlcv.get("closes") or []
    highs = ohlcv.get("highs") or []
    lows = ohlcv.get("lows") or []
    if len(closes) < 205:
        return f"support structure unavailable for {ticker}: need 200+ closes."
    sp = support_structure(closes, highs, lows)
    if sp.get("verdict") == "unknown":
        return f"support structure unavailable for {ticker}: insufficient history."
    return (
        f"support structure {ticker}: verdict={sp['verdict']} "
        f"price={sp.get('price')} base_low={sp.get('base_low')} "
        f"distance_to_base={_txt_pct(sp.get('distance_to_base_pct'))} "
        f"distance_to_sma200={_txt_pct(sp.get('distance_to_sma200_pct'))}"
    )


@tool
def get_decline_driver_check(
    ticker: Annotated[str, "ticker symbol"],
    current_date: Annotated[str, "the current trading date, YYYY-mm-dd"],
) -> str:
    """Negative-force screen (Value_Dip_swing.md §1): is the dip a temporary
    macro / headline pullback or structural company deterioration?

    Direct 'loss of moat / regulatory ban' data is unavailable, so this proxies
    with measurable red flags: trap_risk HIGH (fraud/distress), Sloan accruals
    > 6%, deeply negative 12-1m momentum, non-positive FCF, non-positive ROE,
    or a severe EPS YoY decline. Verdicts: clean / caution / structural.

    Use before proposing any value dip - a 'structural' verdict means the
    decline looks company-specific and the setup should be rejected.
    """
    try:
        from tradingagents.strategies.value_dip import decline_driver_check
    except Exception as exc:  # noqa: BLE001
        return f"decline driver unavailable for {ticker}: {exc}"
    fin = _canonical_financials(ticker, current_date)
    # trap_risk from the analyst verdict pipeline (Beneish/Altman/F/Net-Net).
    trap_level = None
    try:
        trap_level = _trap_level_from_fin(fin, ticker, current_date)
    except Exception:  # noqa: BLE001
        trap_level = None
    # 12-1m momentum from price history.
    ohlcv = _ohlcv(ticker)
    closes = ohlcv.get("closes") or []
    mom12 = None
    if len(closes) >= 2:
        look = min(252, len(closes))
        ref = closes[-(look + 1)] if len(closes) > look else closes[0]
        if ref:
            mom12 = closes[-1] / ref - 1.0
    # FCF, ROE, EPS YoY from canonical + cashflow.
    fcf = None
    try:
        cf_payload = route_to_vendor("get_cashflow", ticker, "annual", current_date) or ""
        ser = _fcf_series_from_cashflow(cf_payload)
        fcf = ser[0] if ser else None
    except Exception:  # noqa: BLE001
        fcf = None
    te = _latest(fin.get("total_equity"))
    ne = _latest(fin.get("net_income"))
    roe = (float(ne) / float(te)) if (ne is not None and te) else None
    eps_yoy = _latest(fin.get("eps_yoy"))
    try:
        accrual_ = _accrual_from_fin(fin, ticker, current_date)
    except Exception:  # noqa: BLE001
        accrual_ = None
    out = decline_driver_check(
        trap_level=trap_level,
        accrual=accrual_,
        mom12=mom12,
        fcf=fcf,
        roe=roe,
        eps_yoy=eps_yoy,
    )
    return f"decline driver {ticker}: verdict={out['verdict']} clean={out['clean']}" + (
        " ; " + "; ".join(out["reasons"]) if out["reasons"] else ""
    )


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
        from tradingagents.dataflows.statement_parsing import _first_number as _fn
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
        if not ebitda:
            return None
        ev = num(find("enterprise value", "ev"))
        if ev:
            return ev / ebitda
        # No explicit EV row: derive EV = market cap + debt - cash so the
        # multiple measures enterprise value, not P/EBITDA (which understates
        # EV for a levered name and corrupts the historical z-score).
        mc = num(find("market cap", "market capitalization", "market value"))
        debt = num(find("total debt", "long term debt"))
        cash = num(find("cash and cash equivalents", "cash"))
        if mc is not None and mc > 0:
            return (mc + (debt or 0.0) - (cash or 0.0)) / ebitda
        return None
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


def _trap_level_from_fin(fin: dict, ticker: str, current_date: str) -> str | None:
    """Trap-risk level (LOW/MEDIUM/HIGH) for the decline-driver tool.

    Reuses the screener's forensic pipeline (Beneish M / Altman Z / F-Score /
    net-net) via ``screen_ticker``; best-effort, None when unavailable.
    """
    try:
        from tradingagents.dataflows.statement_parsing import fetch_ticker, screen_ticker

        if not fin:
            fin = fetch_ticker(ticker, current_date)
        row = screen_ticker(ticker, fin)
        trap = row.get("trap")
        return trap if trap not in (None, "n/a") else None
    except Exception:  # noqa: BLE001
        return None


def _accrual_from_fin(fin: dict, ticker: str, current_date: str) -> float | None:
    """Sloan accruals ratio (NI - CFO) / total assets for the decline-driver
    tool; best-effort from the canonical items + cashflow, None when missing.
    """
    try:
        from tradingagents.dataflows.statement_parsing import fetch_ticker
        from tradingagents.strategies.normalized import accruals_ratio

        if not fin:
            fin = fetch_ticker(ticker, current_date)
        ni = _latest(fin.get("net_income"))
        ta = _latest(fin.get("total_assets"))
        cfo = None
        cf_payload = route_to_vendor("get_cashflow", ticker, "annual", current_date) or ""
        # accruals needs CFO, not FCF - derive from the cashflow payload's
        # operating-cash-flow row via the same period parser when available.
        cfo = _cfo_from_payload(cf_payload)
        if ni is None or ta is None or cfo is None:
            return None
        return accruals_ratio(ni, cfo, ta)
    except Exception:  # noqa: BLE001
        return None


def _cfo_from_payload(payload: str) -> float | None:
    """Latest operating cash flow from a cashflow payload (moomoo markdown
    newest-first or yfinance CSV), or None."""
    if not payload or str(payload).startswith(("NO_DATA", "DATA_")):
        return None
    try:
        from tradingagents.dataflows.statement_parsing import (
            _markdown_period_tables,
            _parse_csv_statements,
        )

        tables = _markdown_period_tables(payload)
        if tables:
            for _, rows in tables:
                for label, value in rows.items():
                    if (
                        "operating cash flow" in str(label).lower()
                        or "cash flow from operating" in str(label).lower()
                    ):
                        try:
                            return float(value)
                        except (TypeError, ValueError):
                            return None
        rows = _parse_csv_statements(payload)
        for label, value in rows.items():
            if (
                "operating cash flow" in str(label).lower()
                or "cash flow from operating" in str(label).lower()
            ):
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return None
    except Exception:  # noqa: BLE001
        return None
    return None


__all__ = [
    "get_bollinger_pct_b",
    "get_tranche_plan",
    "get_trade_expectancy",
    "get_fcf_yield",
    "get_valuation_z_score",
    "get_value_dip_setup",
    "get_balance_sheet_health",
    "get_macd_divergence",
    "get_vdu_entry_setup",
    "get_support_structure",
    "get_decline_driver_check",
    "get_value_floors",
]


@tool
def get_value_floors(
    ticker: Annotated[str, "ticker symbol"],
    current_date: Annotated[str, "the current trading date, YYYY-mm-dd"],
) -> str:
    """Structural value floors: Graham Number, NCAV (net-net), Earnings Power
    Value (EPV) - the value-dip's asset/earnings-backed cheapness floors.

    Computed from the canonical statements (EPS, book value, current assets,
    liabilities, shares, EBIT, tax, WACC proxy). Use before any 'cheap on
    assets / below book / earnings-power floor' claim; missing inputs render
    n/a (never fabricated).
    """
    try:
        from tradingagents.strategies.fundamental_floors import (
            earnings_power_value as _epv,
            epv_per_share as _epv_ps,
            graham_cheap as _g_cheap,
            graham_number as _g,
            ncav_cheap as _n_cheap,
            ncav_per_share as _ncav,
        )
    except Exception as exc:  # noqa: BLE001
        return f"value floors unavailable for {ticker}: {exc}"
    fin = _canonical_financials(ticker, current_date)
    price = None
    try:
        from tradingagents.agents.utils.analysis_tools import _ohlcv

        closes = _ohlcv(ticker).get("closes") or []
        price = float(closes[-1]) if closes else None
    except Exception:  # noqa: BLE001
        price = None
    eps = _latest(fin.get("eps"))
    te = _latest(fin.get("total_equity"))
    sh = _latest(fin.get("shares"))
    bvps = (te / sh) if (te is not None and sh) else None
    ca = _latest(fin.get("current_assets"))
    tl = _latest(fin.get("total_liabilities"))
    ebit = _latest(fin.get("operating_income"))
    tax = _latest(fin.get("tax_expense"))
    ta = _latest(fin.get("total_assets"))
    # WACC proxy: rf + beta*erp via the DCF helper (beta from canonical).
    wacc = None
    try:
        from tradingagents.strategies.dcf import wacc_from_beta

        beta = _latest(fin.get("beta"))
        wacc = wacc_from_beta(0.04, beta if beta is not None else 1.0)
    except Exception:  # noqa: BLE001
        wacc = None
    tax_rate = (tax / ebit) if (ebit and tax is not None) else None
    roic = (ebit * (1.0 - (tax_rate or 0.0))) / ta if (ebit and ta) else None
    g = _g(eps, bvps)
    ncav = _ncav(ca, tl, sh)
    epv = _epv(ebit, tax_rate, wacc, roic=roic)
    epv_ps = _epv_ps(epv.get("epv"), sh) if epv else None
    lines = [
        f"value floors {ticker} (price {price if price is not None else 'n/a'}):",
        f"  graham_number={g} cheap={_g_cheap(price, g)}",
        f"  ncav_per_share={ncav} cheap={_n_cheap(price, ncav)}",
        f"  epv={epv.get('epv') if epv else None} per_share={epv_ps} "
        f"conclusion={epv.get('conclusion') if epv else None}",
    ]
    return "\n".join(lines)

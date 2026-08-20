"""Computed-analysis tools for the analyst LLMs (analysis-only).

Wraps the deterministic calculation layer (tradingagents/strategies/*) as
LangChain tools so the analyst agents can ground their judgements in computed
signals instead of re-deriving them from raw vendor output:

  get_swing_set          - swing trend/pullback/stop/target read (strategies.swing)
  get_relative_strength  - RS line vs benchmark (strategies.relative_strength)
  get_earnings_event_read- last earnings surprise + PEAD setup (events/catalyst)
  get_catalyst_scale     - B1 scheduled-catalyst scale & verdict (catalyst)
  get_position_sizing    - Kelly + risk-budget position size (size)
  get_risk_verdict       - risk-governor PASS/WARN/REJECT (risk_governor)

Every tool is pure/read-only, follows the project's no-fabrication contract
(exact numbers or an explicit "unavailable", never an estimate), and degrades
to a clear message when data is missing or the vendor chain fails - the
analyst then says the signal is unavailable rather than inventing it.
"""

from __future__ import annotations

from typing import Annotated

from langchain_core.tools import tool

# ---------------------------------------------------------------------------
# Shared data helpers (vendor chain CSV, benchmark closes)
# ---------------------------------------------------------------------------


def _ohlcv(ticker: str, days: int = 320) -> dict:
    """Daily OHLCV via the vendor chain (Date,Open,High,Low,Close,Volume rows).

    Returns {"dates", "closes", "highs", "lows", "volumes", "opens"} (all
    empty on failure). Mirrors the graph's close-fetch but keeps the full
    OHLCV the swing/PEAD calculations need.
    """
    try:
        from datetime import datetime, timedelta

        from tradingagents.dataflows.interface import route_to_vendor

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


def _benchmark_closes() -> list:
    """Benchmark (benchmark_ticker, default SPY) closes for the RS line."""
    try:
        from tradingagents.dataflows.config import get_config

        bench = get_config().get("benchmark_ticker") or "SPY"
    except Exception:
        bench = "SPY"
    return _ohlcv(bench).get("closes") or []


def _txt_round(v, nd: int = 4) -> str:
    return f"{v:.{nd}f}" if v is not None else "n/a"


# ---------------------------------------------------------------------------
# Swing / relative strength (market analyst)
# ---------------------------------------------------------------------------


@tool
def get_swing_set(
    ticker: str,
) -> str:
    """Deterministic multi-week swing read for a ticker (analysis-only).

    Computes the techno-fundamental swing setup from daily OHLCV: the trend
    architecture (20-day EMA stacked over rising 50/200 SMAs), RSI band
    (45-70 strong / 40-50 reset / <40 broken), pullback-into-EMA20 status,
    a 1-ATR structure stop below the swing low, 2R/3R profit targets, the
    scale-out + 20-day-EMA trail, and the volatility-contraction (VCP) base
    state. Call this before making claims about entry levels, stop placement,
    reward:risk or whole-discussion setups - it is the source of truth for
    those exact numbers.

    Args:
        ticker: single ticker symbol (e.g. "AAPL").

    Returns:
        Compact text lines with the candidate verdict + the computed
        stop/target levels, or an 'insufficient history' message when the
        vendor chain yields fewer than 200 daily bars.
    """
    data = _ohlcv(ticker)
    closes = data["closes"]
    if len(closes) < 200:
        return (
            f"swing set unavailable for {ticker}: fewer than 200 daily bars "
            f"({len(closes)}). The 200-day SMA is structural; report the setup "
            "as not computable."
        )
    try:
        from tradingagents.strategies.size import atr
        from tradingagents.strategies.swing import swing_report

        atr_v = atr(data["highs"], data["lows"], closes, window=14)
        bench = _benchmark_closes()
        rep = swing_report(
            closes,
            data["highs"],
            data["lows"],
            data["volumes"],
            atr_value=atr_v,
            benchmark_closes=bench or None,
        )
        if rep is None:
            return f"swing set unavailable for {ticker} (computation refused)."
        arch = rep.get("architecture") or {}
        rsi = rep.get("rsi") or {}
        pull = rep.get("pullback") or {}
        stop = rep.get("stop") or {}
        tg = rep.get("targets") or {}
        sc = rep.get("scaleout") or {}
        tr = rep.get("trail") or {}
        vcp = rep.get("vcp") or {}
        rs = rep.get("relative_strength") or {}
        lines = [
            f"swing set {ticker}:",
            f"  verdict={'PASS' if rep.get('candidate') else 'NO'} ({rep.get('context')})",
            f"  trend: stacked={arch.get('stacked')} above50={arch.get('above_sma50')} "
            f"above200={arch.get('above_sma200')} sma50_rising={arch.get('sma50_rising')}",
            f"  rsi: {rsi.get('value')} ({rsi.get('label')}) "
            f"strong={rsi.get('strong')} broken={rsi.get('broken')}",
            f"  pullback: near_ema20={pull.get('near_ema')} volume_fade={pull.get('volume_fade')}",
        ]
        if stop.get("stop") is not None:
            lines.append(
                f"  structure_stop: swing_low={_txt(stop.get('swing_low'))} "
                f"stop={_txt(stop.get('stop'))} risk={_txt(stop.get('risk_pct'))} "
                f"(1 ATR below swing low, ATR={_txt(stop.get('atr'))})"
            )
        if tg.get("t1") is not None:
            lines.append(
                f"  targets: entry={_txt(tg.get('entry'))} T1(2R)={_txt(tg.get('t1'))} "
                f"T2(3R)={_txt(tg.get('t2'))} risk={_txt(tg.get('risk'))}"
            )
        if sc.get("valid"):
            lines.append(
                f"  scaleout: {sc.get('t1_fraction')} at T1 -> break-even, trail {sc.get('trail')}"
            )
        if tr.get("ema") is not None:
            lines.append(
                f"  trail: ema20={_txt(tr.get('ema'))} below={tr.get('below')} "
                f"exit={tr.get('exit')}"
            )
        if vcp is not None:
            lines.append(
                f"  vcp: candidate={vcp.get('candidate')} depths={vcp.get('depths')} "
                f"close_to_base={_txt(vcp.get('close_to_base'))} "
                f"near_breakout={vcp.get('near_breakout')}"
            )
        if rs:
            lines.append(
                f"  relative_strength: {rs.get('verdict')} rs={_txt(rs.get('rs'))} "
                f"slope%={_txt(rs.get('slope_pct'))} near_high={rs.get('near_high')}"
            )
        return chr(10).join(lines)
    except Exception as exc:  # noqa: BLE001
        return f"swing set unavailable for {ticker}: {exc}"


def _txt(v) -> str:
    return "n/a" if v is None else (f"{v:.4f}" if isinstance(v, float) else str(v))


def _fmt_pct(v) -> str:
    if v is None:
        return "n/a"
    try:
        return f"{float(v):+.1%}"
    except (TypeError, ValueError):
        return str(v)


@tool
def get_relative_strength(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Relative-strength line vs the market benchmark (deterministic).

    Computes the stock/benchmark ratio series (benchmark_ticker, default SPY)
    and its 63-day established-trend slope, its position vs its own high
    (new-high / near-high), and negative divergence (price new high without
    RS backing). Call this before any 'strong vs the market / outperforming
    the index / leading sector' claim.

    Args:
        ticker: the single ticker symbol (e.g. "AAPL").

    Returns:
        Compact verdict line: leading / uptrend / lagging / diverging /
        unknown with the slope and divergence flags.
    """
    closes = _ohlcv(ticker).get("closes") or []
    bench = _benchmark_closes()
    if not closes or len(closes) < 63 or not bench:
        return (
            f"relative strength unavailable for {ticker}: benchmark or price "
            "history missing (len stock=%d bench=%d). Can't assess vs-market "
            "leadership - do not claim outperformance." % (len(closes), len(bench))
        )
    try:
        from tradingagents.strategies.relative_strength import relative_strength_report

        r = relative_strength_report(closes, bench)
        return (
            f"relative_strength {ticker}: verdict={r.get('verdict')} "
            f"rs={_txt(r.get('rs'))} slope_63d_pct={_txt(r.get('slope_pct'))} "
            f"uptrend={r.get('uptrend')} near_high={r.get('near_high')} "
            f"new_high={r.get('new_high')} divergence={r.get('divergence')} "
            f"context: {r.get('context')}"
        )
    except Exception as exc:  # noqa: BLE001
        return f"relative strength unavailable for {ticker}: {exc}"


# ---------------------------------------------------------------------------
# Earnings event / catalyst (news analyst)
# ---------------------------------------------------------------------------


@tool
def get_earnings_event_read(
    ticker: Annotated[str, "ticker symbol"],
    current_date: Annotated[str, "the current trading date, YYYY-mm-dd"],
) -> str:
    """Standardized earnings surprise + post-earnings drift (PEAD) read.

    Computes the last reported EPS surprise % and its drift side (beat/miss)
    from the vendor earnings calendar, then (when enough daily bars are
    available) the print-day price move, print-day volume vs its 20-day
    average, and the post-print consolidation/break status - the framework's
    post-earnings entry logic. Call this before any 'beat/miss', 'gap up on
    volume', 'PEAD' or 'post-earnings drift' claim.

    Args:
        ticker: single ticker symbol.
        current_date: the current trading date (YYYY-mm-dd).

    Returns:
        Surprise / side / day-0 move / volume ratio / PEAD verdict lines, or
        the surprise + an 'insufficient bars' note for the entry part.
    """
    try:
        from tradingagents.strategies.catalyst import (
            fetch_catalyst_data,
            last_earnings_surprise,
        )
        from tradingagents.strategies.events import post_earnings_play
    except Exception as exc:  # noqa: BLE001
        return f"earnings event read unavailable for {ticker}: {exc}"
    cat = fetch_catalyst_data(ticker, current_date) or {}
    last = last_earnings_surprise(cat.get("earnings_calendar") or [])
    if not last:
        return (
            f"earnings event read unavailable for {ticker}: no reported "
            f"earnings surprise in the calendar window."
        )
    lines = [
        f"earnings event {ticker}:",
        f"  last surprise={_fmt_pct(last['surprise'])} side={last['side']} date={last.get('date')}",
    ]
    data = _ohlcv(ticker)
    try:
        idx = _find_bar_on_or_after(data["dates"], last.get("date"))
        if idx is not None and 1 <= idx < len(data["closes"]):
            day0_ret = data["closes"][idx] / data["closes"][idx - 1] - 1.0
            vol_ratio = (
                data["volumes"][idx]
                / (sum(data["volumes"][max(0, idx - 20) : idx]) / max(1, min(20, idx)))
                if data["volumes"] and idx > 0
                else None
            )
            post_h = data["highs"][idx + 1 : idx + 5]
            post_c = data["closes"][idx + 1 : idx + 5]
            play = post_earnings_play(day0_ret, vol_ratio, post_h, post_c, hold_days=4)
            lines.append(
                f"  print_day: return={_txt(day0_ret)} volume_ratio={_txt(vol_ratio)} (2.5x gate)"
            )
            if play and play.get("verdict"):
                lines.append(
                    f"  pead: {play.get('verdict')} "
                    f"consolidation_high={_txt(play.get('range_high'))} "
                    f"breakout={play.get('breakout')}"
                )
        else:
            lines.append("  pead: print-day bar not in history (entry part skipped)")
    except Exception:  # noqa: BLE001 - entry part is best-effort; keep surprise
        lines.append("  pead: print-day data unavailable")
    return chr(10).join(lines)


def _find_bar_on_or_after(dates: list, target: str | None) -> int | None:
    """Index of the first bar dated on/after ``target`` (YYYY-MM-DD)."""
    if not target or not dates:
        return None
    target = str(target)[:10]
    for i, d in enumerate(dates):
        if str(d)[:10] >= target:
            return i
    return None


@tool
def get_catalyst_scale(
    ticker: Annotated[str, "ticker symbol"],
    current_date: Annotated[str, "the current trading date, YYYY-mm-dd"],
) -> str:
    """One scheduled-catalyst risk scale (0..1) + verdict for the ticker.

    Computes the B1 catalyst snapshot: upcoming earnings date + market-implied
    move, HIGH-importance macro events (CPI, FOMC, payrolls) and Fed-watch
    meetings in their windows - all folded into a single 0..1 position-scale
    multiplier and a verdict (earnings-window / macro-catalyst / fed-catalyst /
    no-imminent-catalyst / earnings-hard-block). Call this before sizing any
    position near a scheduled catalyst.

    Args:
        ticker: the single ticker symbol.
        current_date: the current trading date (YYYY-MM-DD).

    Returns:
        scale + verdict + the per-factor reasons; 'unavailable (neutral)' when
        the catalyst data cannot be fetched (treat scale = 1.0).
    """
    try:
        from tradingagents.dataflows.config import get_config
        from tradingagents.strategies.catalyst import (
            build_catalyst_snapshot,
            fetch_catalyst_data,
        )
    except Exception as exc:  # noqa: BLE001
        return f"catalyst scale unavailable for {ticker}: {exc}"
    data = fetch_catalyst_data(ticker, current_date)
    if data is None:
        return (
            f"catalyst scale unavailable for {ticker} (gateway/fetch failed) -> "
            f"treat scale = 1.0 (no catalyst adjustment)."
        )
    snap = build_catalyst_snapshot(data, current_date, get_config())
    lines = [
        f"catalyst scale {ticker}: scale={snap.get('scale')} verdict={snap.get('verdict')}",
    ]
    if snap.get("earnings"):
        e = snap["earnings"]
        lines.append(
            f"  earnings: {e.get('date')} in {e.get('days_until')}d "
            f"est={_txt(e.get('eps_estimate'))}"
        )
    if snap.get("implied_move") is not None:
        lines.append(f"  implied_move={_txt(snap.get('implied_move'))}")
    if snap.get("macro") and snap["macro"].get("count_high"):
        lines.append(
            f"  macro HIGH events within {snap['macro'].get('min_days')}d: "
            f"{snap['macro']['count_high']}"
        )
    if snap.get("fed") and snap["fed"].get("days_until") is not None:
        lines.append(
            f"  fomc {snap['fed']['days_until']}d out "
            f"modal_prob={_txt(snap['fed'].get('modal_prob'))}"
        )
    if snap.get("reasons"):
        lines.append("  reasons: " + "; ".join(snap["reasons"]))
    return chr(10).join(lines)


# ---------------------------------------------------------------------------
# Position sizing + risk gate (pure maths)
# ---------------------------------------------------------------------------


@tool
def get_position_sizing(
    confidence: Annotated[float, "win probability of the setup, 0..1"],
    stop_dist_pct: Annotated[
        float,
        "stop-loss distance from entry as a fraction, e.g. 0.05 for 5% (1 ATR below the swing low)",
    ],
    odds: Annotated[float, "win/loss payoff ratio (R:R), 1.0 default"] = 1.0,
    risk_per_trade: Annotated[
        float, "max fraction of capital to risk per trade, default 0.01 (1%)"
    ] = 0.01,
    max_position_pct: Annotated[float, "hard cap on the position fraction, default 0.30"] = 0.30,
    kelly_frac: Annotated[
        float, "fraction of full Kelly to use, default 0.25 (quarter-Kelly)"
    ] = 0.25,
) -> str:
    """Size a position by the risk budget and quarter-Kelly (deterministic).

    Returns both the Kelly share and the risk-budget size
    (risk_per_trade / stop_dist_pct), and the final capped size =
    min(kelly_part, risk_part, max_position_pct). Use these numbers, not a
    back-of-envelope, when proposing a position size; the framework's
    structure stop from get_swing_set is the natural ``stop_dist_pct`` input.

    Args:
        confidence: win probability of the setup (0..1).
        stop_dist_pct: stop distance from entry as a fraction (e.g. 0.05).
        odds: payoff ratio (R) for the trade.
        risk_per_trade: account risk budget per trade as a fraction.
        max_position_pct: absolute cap on the position fraction.
        kelly_fraction: fraction of full Kelly to apply (default quarter).

    Returns:
        A one-line sizing verdict with the numbers.
    """
    try:
        from tradingagents.strategies.size import kelly_fraction
    except Exception as exc:  # noqa: BLE001
        return f"position sizing unavailable: {exc}"
    if stop_dist_pct is None or stop_dist_pct <= 0:
        return "position sizing unavailable: stop_dist_pct must be > 0 (e.g. 0.05 for a 5% stop)."
    kelly = kelly_fraction(confidence, odds)
    kelly_part = kelly * kelly_frac
    risk_part = risk_per_trade / stop_dist_pct if stop_dist_pct else max_position_pct
    size = min(kelly_part, risk_part, max_position_pct)
    return (
        f"position size: {size:.1%} (kelly={kelly:.2%} -> quarter={kelly_part:.1%}, "
        f"risk_budget={risk_part:.1%}, cap={max_position_pct:.0%}); "
        f"formula min(kelly_quarter, risk/stop, cap) with confidence={confidence}, "
        f"odds={odds}, risk/trade={risk_per_trade:.1%}, "
        f"note: a size 0 means the setup fails the sizing gate."
    )


@tool
def get_risk_gate(
    size_pct: Annotated[
        float, "proposed position size as a fraction of capital, 0..1 (e.g. 0.10 = 10%)"
    ],
    cvar_pct: Annotated[
        float | None, "portfolio-level CVaR (tail loss) as a fraction, if known"
    ] = None,
    drawdown_pct: Annotated[
        float | None, "current realized drawdown as a fraction, if known"
    ] = None,
) -> str:
    """House risk-gate verdict for a proposed position (deterministic).

    Applies the project's risk governor limits (max_position_pct, book cap,
    CVaR budget, drawdown limit) to a proposed size and returns PASS / WARN /
    REJECT with the numeric reasons. Use this when evaluating any proposed size (including the Trader's), instead of asserting a size is 'reasonable' in prose.

    Args:
        size_pct: the proposed position size (0..1).
        cvar_pct: portfolio tail-loss budget used (optional).
        drawdown_pct: current drawdown (optional).

    Returns:
        verdict + numbers snapshot.
    """
    try:
        from tradingagents.dataflows.config import get_config
        from tradingagents.strategies.risk_governor import build_risk_snapshot, govern
    except Exception as exc:  # noqa: BLE001
        return f"risk gate unavailable: {exc}"
    verdict = govern(
        size_pct,
        get_config(),
        cvar_pct=cvar_pct,
        drawdown_pct=drawdown_pct,
    )
    if verdict.get("verdict") == "PASS" and not verdict.get("reasons"):
        lines = [f"risk: PASS {size_pct:.1%}"]
    else:
        lines = [
            build_risk_snapshot(verdict, size_pct, cvar_pct=cvar_pct, drawdown_pct=drawdown_pct)
        ]
    if verdict.get("reasons"):
        lines.append("reasons: " + "; ".join(verdict["reasons"]))
    return chr(10).join(lines)


# ---------------------------------------------------------------------------
# Regime / VCP / orderflow (market analyst)
# ---------------------------------------------------------------------------


@tool
def get_regime_read(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Deterministic market-regime read for a ticker (risk-on / risk-off).

    Computes the strategy-regime label (vol percentile + trend strength),
    the volatility-target position scale, and the 60-day momentum + 52-week
    high distance from the same pure calculators the overlay pipeline uses.
    Call this before any claim that 'the regime is supportive / risk-on' or
    when deciding how aggressively to size against the price backdrop.

    Args:
        ticker: single ticker symbol.

    Returns:
        regime label + position scale + momentum/distance lines, or an
        'insufficient history' message when fewer than 60 daily bars exist.
    """
    closes = _ohlcv(ticker).get("closes") or []
    if len(closes) < 60:
        return (
            f"regime read unavailable for {ticker}: fewer than 60 daily bars "
            f"({len(closes)}) - regime needs a real vol history."
        )
    try:
        from tradingagents.dataflows.config import get_config
        from tradingagents.strategies.overlays import build_strategy_overlays

        ov = build_strategy_overlays(get_config(), closes)
        if ov is None:
            return (
                f"regime read unavailable for {ticker}: strategy overlays "
                "disabled in the current config."
            )
        return (
            f"regime {ticker}: regime={ov.get('regime')} "
            f"position_scale={ov.get('position_scale')} "
            f"momentum_60d={_txt(ov.get('momentum60'))} "
            f"52w_distance={_txt(ov.get('high_distance'))} "
            f"context: {ov.get('context')}"
        )
    except Exception as exc:  # noqa: BLE001
        return f"regime read unavailable for {ticker}: {exc}"


@tool
def get_volatility_contraction(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Volatility Contraction Pattern (VCP) base state for a ticker.

    Detects a classic 15% -> 8% -> 3% base: successively shallower pullbacks
    off a base high on declining volume (strict pivot troughs, last-3 depth
    contraction with a 10% noise tolerance, deepest pullback within 30% of
    the base). Call this before any 'volatility contraction', 'VCP base' or
    'tight base' / 'spring' claim - it is the computed state.

    Args:
        ticker: single ticker symbol.

    Returns:
        candidate flag + the base depths + volume-fade + near-breakout lines.
    """
    data = _ohlcv(ticker)
    closes = data["closes"]
    if len(closes) < 90:
        return f"VCP unavailable for {ticker}: fewer than 90 daily bars ({len(closes)})"
    try:
        from tradingagents.strategies.swing import vcp_setup

        v = vcp_setup(closes, data["highs"], data["lows"], data["volumes"])
        return (
            f"vcp {ticker}: candidate={v.get('candidate')} "
            f"pullback_depths={v.get('depths')} "
            f"base_high={_txt(v.get('base_high'))} "
            f"close_to_base={_txt(v.get('close_to_base'))} "
            f"contraction_ok={v.get('contraction_ok')} "
            f"volume_fade={v.get('volume_fade')} "
            f"near_breakout={v.get('near_breakout')} "
            f"context: {v.get('context')}"
        )
    except Exception as exc:  # noqa: BLE001
        return f"VCP unavailable for {ticker}: {exc}"


@tool
def get_orderflow_read(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Institutional vs retail capital-flow read for a ticker.

    Fetches the live moomoo capital buckets and weekly net flows and folds
    them into the deterministic order-flow summary: institutional/retail net,
    distribution score, divergence, alignment, exhaustion. Call before any
    'institutional accumulation / distribution / large orders' claim.

    Args:
        ticker: single ticker symbol.

    Returns:
        The computed flow lines, or an explicit 'unavailable (neutral)' note
        when the live gateway is down - never an estimated number.
    """
    try:
        from tradingagents.strategies.orderflow import fetch_flow, summarize
    except Exception as exc:  # noqa: BLE001
        return f"order flow unavailable for {ticker}: {exc}"
    payload = fetch_flow(ticker)
    if payload is None:
        return (
            f"order flow unavailable for {ticker} (gateway down / no data) - "
            "treat as neutral; do not fabricate a flow reading."
        )
    try:
        summary = summarize(
            payload.get("buckets", {}),
            weekly_nets=payload.get("weekly_nets"),
        )
    except Exception as exc:  # noqa: BLE001
        return f"order flow unavailable for {ticker}: {exc}"
    return (
        f"order flow {ticker}: inst_net={summary.get('institutional_net'):+,} "
        f"retail_net={summary.get('retail_net'):+,} "
        f"distribution={summary.get('distribution_score'):.2f} "
        f"divergence={summary.get('divergence')} "
        f"alignment={summary.get('alignment')} "
        f"exhaustion={summary.get('exhaustion')} "
        f"flag={summary.get('flag')}"
    )


# ---------------------------------------------------------------------------
# Fundamentals verdict / earnings surprise / portfolio weights (fundamentals)
# ---------------------------------------------------------------------------


@tool
def get_analyst_verdict(
    ticker: Annotated[str, "ticker symbol"],
    current_date: Annotated[str, "the current trading date, YYYY-mm-dd"],
) -> str:
    """Deterministic value-quality verdict (trap risk + forensic screens).

    Runs the same canonical financial pipeline as the value watchlist and
    returns the computed screens: Earnings Yield, EV/EBIT (Acquirer's
    Multiple), Piotroski F-Score, Beneish M-Score, Altman Z-Score, Net-Net,
    the collapsed trap-risk verdict (LOW/MEDIUM/HIGH + evidence), ROE, and
    EPS/Revenue YoY growth. Call this before any 'cheap / quality / value /
    accounting risk / trap' claim - it is the computed number, not a guess.

    Args:
        ticker: single ticker symbol.
        current_date: the current trading date (YYYY-mm-dd).

    Returns:
        One line per computed screen (missing figures render n/a); an
        'unavailable' message when the vendor chain yields no statements.
    """
    try:
        from scripts.value_screener import fetch_ticker, screen_ticker
    except Exception as exc:  # noqa: BLE001
        return f"analyst verdict unavailable for {ticker}: {exc}"
    fin = fetch_ticker(ticker, current_date)
    if not fin:
        return (
            f"analyst verdict unavailable for {ticker}: no statements from "
            "the vendor chain; do not fabricate value screens."
        )
    row = screen_ticker(ticker, fin)
    lines = [f"analyst verdict {ticker}:"]
    for key, label in (
        ("earnings_yield", "EY"),
        ("ev_ebit", "EV/EBIT"),
        ("f_score", "Piotroski F"),
        ("beneish_m", "Beneish M"),
        ("altman_z", "Altman Z"),
        ("roe", "ROE"),
        ("eps_yoy", "EPS YoY"),
        ("revenue_yoy", "Revenue YoY"),
    ):
        v = row.get(key)
        if v is None:
            lines.append(f"  {label}: n/a")
        elif key in ("beneish_m", "altman_z", "f_score", "ev_ebit"):
            lines.append(f"  {label}: {v:.2f}")
        elif key in ("roe", "eps_yoy", "revenue_yoy", "earnings_yield"):
            lines.append(f"  {label}: {v:.2%}")
        else:
            lines.append(f"  {label}: {v}")
    lines.append(f"  net_net: {row.get('net_net')}")
    trap = row.get("trap")
    lines.append(f"  trap_risk: {trap}" if trap not in (None, "n/a") else "  trap_risk: n/a")
    return chr(10).join(lines)


@tool
def get_earnings_surprise(
    ticker: Annotated[str, "ticker symbol"],
    current_date: Annotated[str, "the current trading date, YYYY-mm-dd"],
) -> str:
    """Standardized last-reported EPS surprise and its drift side.

    Computes surprise = (actual - estimate) / |estimate| and the side
    (beat / miss / flat) from the vendor earnings calendar. Use before any
    'the company beat/missed expectations' claim - it is the computed %, and
    it anchors the PEAD reasoning without re-deriving the arithmetic.

    Args:
        ticker: single ticker symbol.
        current_date: the current trading date (YYYY-mm-dd).

    Returns:
        surprise % + side + date; 'no reported surprise' when the calendar
        carries no quantifiable print.
    """
    try:
        from tradingagents.strategies.catalyst import (
            fetch_catalyst_data,
            last_earnings_surprise,
        )
    except Exception as exc:  # noqa: BLE001
        return f"earnings surprise unavailable for {ticker}: {exc}"
    data = fetch_catalyst_data(ticker, current_date) or {}
    last = last_earnings_surprise(data.get("earnings_calendar") or [])
    if not last:
        return (
            f"earnings surprise unavailable for {ticker}: no reported print "
            "with both actual and estimate in the window."
        )
    return (
        f"earnings surprise {ticker}: last_surprise={_fmt_pct(last['surprise'])} "
        f"side={last['side']} date={last.get('date')}"
    )


@tool
def get_portfolio_weights(
    scores: Annotated[
        dict,
        "map of ticker -> value/composite score (higher = better; only positive scores are weighted)",
    ],
    sector_map: Annotated[
        dict | None, "map of ticker -> sector name (optional; used for the per-sector cap)"
    ] = None,
    max_name_pct: Annotated[float, "per-name weight cap as a fraction, default 0.25"] = 0.25,
    sector_cap_pct: Annotated[float, "per-sector weight cap as a fraction, default 0.35"] = 0.35,
) -> str:
    """Value-proportional portfolio weights with the framework's hard caps.

    Deterministic allocation for a small watchlist: weights proportional to
    the composite score, then clipped to the per-name and per-sector caps; the
    excess stays as cash (weights sum to <= 1). Call this when trading a
    multi-name value book and report the computed weights instead of choosing
    them by feel.

    Args:
        scores: {ticker: positive score}. Zero/negative scores are left out.
        sector_map: {ticker: sector} to apply the sector cap (optional).
        max_name_pct: per-name cap (fraction).
        sector_cap_pct: per-sector cap (fraction).

    Returns:
        One line per name (weight %) + the total allocated (cash remainder).
    """
    try:
        from tradingagents.strategies.portfolio import (
            adjust_for_caps,
            value_ratio_weights,
        )
    except Exception as exc:  # noqa: BLE001
        return f"portfolio weights unavailable: {exc}"
    scores = {k: float(v) for k, v in (scores or {}).items() if v is not None and float(v) > 0}
    if not scores:
        return "portfolio weights unavailable: no positive scores provided."
    raw = value_ratio_weights(scores)
    out = adjust_for_caps(
        raw, sector_map or {}, sector_cap_limit=sector_cap_pct, max_name=max_name_pct
    )
    lines = ["portfolio weights:"]
    for name, w in sorted(out.items(), key=lambda kv: -float(kv[1])):
        lines.append(f"  {name}: {float(w):.1%}")
    alloc = sum(float(v) for v in out.values())
    lines.append(f"  total allocated: {alloc:.1%} (cash remainder {1.0 - alloc:.1%})")
    return chr(10).join(lines)


@tool
def get_basic_financials(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Key fundamental metrics for a ticker (Finnhub free tier).

    One call to the Finnhub basic-financials endpoint returns the metric set
    the framework's Phase-1 screens need: EPS / revenue YoY growth, ROE/ROA,
    margins, current ratio, payout ratio, 52-week high/low and average daily
    volumes. Call this before any 'EPS growth of X%', 'revenue growing Y%',
    'ROE of Z' style claim - it is the computed number, not a guess.

    Args:
        ticker: single ticker symbol.

    Returns:
        A ``Metric: value`` block (the growth/quality numbers), or an
        explicit 'unavailable' message when Finnhub has no metrics for the
        symbol or the key is unset.
    """
    try:
        from tradingagents.dataflows.finnhub import get_basic_financials_finnhub

        return get_basic_financials_finnhub(ticker, None)
    except Exception as exc:  # noqa: BLE001
        return f"basic financials unavailable for {ticker}: {exc}"


@tool
def get_insider_activity(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Insider net activity + trend for a ticker (Finnhub, computed).

    Returns the summed net insider share change over the last 12 months, the
    recent-vs-prior trend, and the latest month's mspr score (the proprietary
    insider-sentiment metric). Use before any net insider-buy/sell claim; a
    positive net change is a (weak, secondary) accumulation signal.

    Args:
        ticker: single ticker symbol.

    Returns:
        window summary lines, or an explicit 'unavailable' message when
        Finnhub has no insider data for the symbol.
    """
    try:
        from tradingagents.dataflows.finnhub import get_insider_activity_finnhub

        return get_insider_activity_finnhub(ticker)
    except Exception as exc:  # noqa: BLE001
        return f"insider activity unavailable for {ticker}: {exc}"


@tool
def get_company_peers(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Comparable-company peer group from Finnhub.

    Returns a comma-separated list of Finnhub's peer tickers for the symbol -
    useful context for 'cheap vs peers' or 'sector comparison' reasoning.

    Args:
        ticker: single ticker symbol.

    Returns:
        Peer-ticker list, or an explicit 'unavailable' message.
    """
    try:
        from tradingagents.dataflows.finnhub import get_company_peers_finnhub

        return get_company_peers_finnhub(ticker)
    except Exception as exc:  # noqa: BLE001
        return f"company peers unavailable for {ticker}: {exc}"


@tool
def get_form4_insider(
    ticker: Annotated[str, "ticker symbol"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """Open-market insider transactions (Form 4) for a ticker over a window.

    Computes net open-market insider buying (purchases P minus sales S) from
    SEC Form 4 filings via Massive.com, excluding option grant/exercise (A/M)
    rows to avoid compensation noise. A positive net dollar amount is a
    (secondary) accumulation signal; net selling is a caution flag.

    Args:
        ticker: single ticker symbol.
        start_date: window start (yyyy-mm-dd).
        end_date: window end (yyyy-mm-dd).

    Returns:
        net open-market $ + buy/sell tx counts + sample transactions, or an
        explicit 'unavailable' message.
    """
    try:
        from tradingagents.dataflows.massive import get_form4_insider_massive

        return get_form4_insider_massive(ticker, start_date, end_date)
    except Exception as exc:  # noqa: BLE001
        return f"form-4 insider activity unavailable for {ticker}: {exc}"


@tool
def get_ratios(
    ticker: Annotated[str, "ticker symbol"],
    current_date: Annotated[str | None, "as-of date (yyyy-mm-dd)"] = None,
) -> str:
    """Precomputed valuation & profitability ratios for a ticker (Massive.com).

    Returns EV/EBITDA, EV/Sales, P/E, P/B, P/S, ROE/ROA, D/E, liquidity and
    FCF so the analyst reads precomputed numbers instead of deriving them.
    Cross-check against the screener value screens (EY / EV-EBIT / F / Z)
    before a final cheap/quality claim. Returns an explicit 'unavailable'
    message when the Massive account plan lacks ratios access.

    Args:
        ticker: single ticker symbol.
        current_date: optional as-of date (yyyy-mm-dd).

    Returns:
        A ``key: value`` block, or an explicit 'unavailable' message.
    """
    try:
        from tradingagents.dataflows.massive import get_ratios_massive

        return get_ratios_massive(ticker, current_date)
    except Exception as exc:  # noqa: BLE001
        return f"ratios unavailable for {ticker}: {exc}"


__all__ = [
    "get_swing_set",
    "get_relative_strength",
    "get_earnings_event_read",
    "get_catalyst_scale",
    "get_position_sizing",
    "get_risk_gate",
    "get_regime_read",
    "get_volatility_contraction",
    "get_orderflow_read",
    "get_analyst_verdict",
    "get_earnings_surprise",
    "get_portfolio_weights",
    "get_basic_financials",
    "get_insider_activity",
    "get_company_peers",
    "get_form4_insider",
    "get_ratios",
]

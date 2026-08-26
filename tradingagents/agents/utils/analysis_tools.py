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

from tradingagents.dataflows.interface import route_to_vendor

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


def _daily_returns(closes) -> list:
    """Period-over-period simple returns from a close series (None gaps skipped)."""
    rets: list = []
    prev = None
    for c in closes:
        if c is None:
            prev = None
            continue
        if prev:
            rets.append(c / prev - 1.0)
        prev = c
    return rets


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
def get_swing_exits(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Swing exit read: chandelier trailing stop + EMA trail + targets.

    Computes the ATR chandelier exit (highest high in 22 bars - 3 x ATR) and
    the 20-day EMA trail from daily OHLCV, plus the 2R/3R targets. Call
    before any 'trailing stop / exit level / let winners run' claim on a swing
    position.

    Args:
        ticker: single ticker symbol.

    Returns:
        Compact exit lines (chandelier level + exit flag, EMA trail, targets)
        or an explicit 'unavailable' when fewer than ~200 bars.
    """
    data = _ohlcv(ticker)
    closes = data["closes"]
    if len(closes) < 200:
        return (
            f"swing exits unavailable for {ticker}: fewer than 200 daily bars "
            f"({len(closes)}); report exits as not computable."
        )
    try:
        from tradingagents.strategies.size import atr
        from tradingagents.strategies.swing import chandelier_exit, targets_rr, trail_ema

        atr_v = atr(data["highs"], data["lows"], closes, window=14)
        ch = chandelier_exit(closes, atr_v)
        tr = trail_ema(closes)
        last = float(closes[-1])
        # targets from the chandelier as the trailing reference.
        stop_ref = ch.get("chandelier")
        tg = targets_rr(last, stop_ref) if stop_ref else None
        lines = [
            f"swing exits {ticker} (close {last:.2f}):",
            f"  chandelier stop={ch.get('chandelier')} exit={ch.get('exit')} "
            f"(3x ATR below 22-bar high)",
            f"  ema20={tr.get('ema')} trail_exit={tr.get('exit')}",
        ]
        if tg:
            lines.append(f"  targets: t1={tg.get('t1')} t2={tg.get('t2')} "
                         f"r1={tg.get('r1')} r2={tg.get('r2')}")
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001
        return f"swing exits unavailable for {ticker}: {exc}"


@tool
def get_dip_technical(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Value-dip technical read: RSI/%b + Stochastic + MFI + KST momentum.

    Confirms a value-dip's timing with the volume-price oscillators: RSI(14),
    Bollinger %b, Stochastic %K oversold, Money Flow Index, and the KST
    momentum oscillator. Call before any 'oversold / dip timing / mean
    reversion' claim - it separates a turnable value dip from a falling knife.

    Args:
        ticker: single ticker symbol.

    Returns:
        The computed oscillator lines, or an explicit 'unavailable' message.
    """
    data = _ohlcv(ticker)
    closes = data["closes"]
    if not closes or len(closes) < 30:
        return f"dip technical unavailable for {ticker}: fewer than 30 bars."
    try:
        from tradingagents.strategies.swing import rsi
        from tradingagents.strategies.technical_factors import (
            kst as _kst,
            mf_index as _mfi,
            stochastic_oscillator as _stoch,
        )
        from tradingagents.strategies.value_dip import bollinger_pct_b

        rsi_val = rsi(closes)
        bb = bollinger_pct_b(closes)
        s = _stoch(data["highs"], data["lows"], closes)
        mfi = _mfi(data["highs"], data["lows"], closes, data["volumes"])
        kk = _kst(closes)
        oversold = bool(
            (rsi_val is not None and rsi_val <= 35)
            or (s.get("oversold"))
        )
        lines = [
            f"dip technical {ticker}:",
            f"  rsi={rsi_val} pct_b={bb.get('pct_b') if bb else None}",
            f"  stochK={s.get('k')} oversold={s.get('oversold')}",
            f"  mfi={mfi} kst={kk.get('kst')} kst_up={kk.get('kst_up')}",
            f"  verdict={'OVERSOLD' if oversold else 'not-oversold'} "
            f"(dip timing evidence; combine with the value floor)",
        ]
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001
        return f"dip technical unavailable for {ticker}: {exc}"


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
        from tradingagents.dataflows.statement_parsing import fetch_ticker, screen_ticker
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


# ---------------------------------------------------------------------------
# Decision-grounding tools (agent-decision plan P0/P1/P2)
#   Expose deterministic strategy functions so the trader / PM / analysts
#   cite computed stops, allocation, regime components, consensus, momentum
#   detail, and event multipliers instead of re-deriving or guessing them.
# ---------------------------------------------------------------------------


@tool
def get_exit_check(
    entry: Annotated[float, "entry price of the position"],
    close: Annotated[float, "current price"],
    atr: Annotated[float, "current ATR (use get_swing_set / get_volatility_contraction)"],
    target_mult: Annotated[float, "ATR multiple for the profit target, default 4.0"] = 4.0,
    breakeven_cushion: Annotated[
        float, "ATRs above entry for stop-to-breakeven, default 1.0"
    ] = 1.0,
) -> str:
    "Deterministic exit state for a held long position: stop-to-breakeven, ATR target, holding action."
    try:
        from tradingagents.strategies.exits import exit_check
    except Exception as exc:  # noqa: BLE001
        return f"exit check unavailable: {exc}"
    if atr is None or atr <= 0:
        return "exit check unavailable: atr must be > 0."
    r = exit_check(
        float(entry),
        float(close),
        float(atr),
        target_mult=float(target_mult),
        breakeven_cushion=float(breakeven_cushion),
    )
    return (
        f"exit: breakeven_stop={r['breakeven_stop']:.2f} target={r['target']:.2f} "
        f"stop_hit={r['stop_hit']} target_hit={r['target_hit']} "
        f"action={r['holding_action']}"
    )


@tool
def get_allocation(
    scores: Annotated[dict, "name -> composite/value score"],
    sector_map: Annotated[dict | None, "name to sector; optional, enables per-sector caps"] = None,
    max_name: Annotated[float, "max single-name weight, default 0.25"] = 0.25,
    sector_cap_limit: Annotated[float, "max per-sector weight, default 0.35"] = 0.35,
) -> str:
    "Cap-respecting, value-proportional allocation across a book (hard per-name and per-sector caps)."
    try:
        from tradingagents.strategies.portfolio import (
            adjust_for_caps,
            capped_weights,
            summary,
            value_ratio_weights,
        )
    except Exception as exc:  # noqa: BLE001
        return f"allocation unavailable: {exc}"
    w = value_ratio_weights(scores, min_weight=0.0)
    if sector_map:
        w = adjust_for_caps(
            w, sector_map, sector_cap_limit=float(sector_cap_limit), max_name=float(max_name)
        )
    else:
        w = capped_weights(w, cap=float(max_name))
    info = summary(w, min_n=1)
    lines = ["## Allocation plan", ""]
    for name, wt in sorted(w.items(), key=lambda kv: -kv[1])[:15]:
        lines.append(f"- {name}: {wt:.1%}")
    lines.append("")
    lines.append(f"allocated: {info['allocated']:.1%} active_names: {info['active']}")
    return "\n".join(lines)


@tool
def get_regime_components(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    "Drill into why the regime label says what it does: vol_pct, trend, choppiness, label."
    try:
        from tradingagents.strategies.regime import (
            choppiness,
            regime_label,
            trend_strength,
            vol_percentile,
        )
    except Exception as exc:  # noqa: BLE001
        return f"regime components unavailable for {ticker}: {exc}"
    data = _ohlcv(ticker)
    closes = data.get("closes") or []
    if not closes or len(closes) < 30:
        return f"regime components unavailable for {ticker}: not enough price history."
    try:
        # vol_percentile expects a list of close *windows* (it computes vol of
        # each). Build 21-day rolling windows over the close series.
        window = 21
        windows = [closes[i - window : i] for i in range(window, len(closes) + 1, window)]
        vol_pct = vol_percentile(windows or [closes], current_window=window)
        trend = trend_strength(closes, sma_window=min(200, max(2, len(closes) // 2)))
        chop = choppiness(closes, window=14)
        label = regime_label(vol_pct, trend, chop)
    except Exception as exc:  # noqa: BLE001
        return f"regime components unavailable for {ticker}: {exc}"
    return f"regime {ticker}: vol_pct={vol_pct:.2f} trend={trend:.4f} chop={chop:.2f} label={label}"


@tool
def get_consensus(
    ratings: Annotated[list, "list of rating strings/scores, e.g. ['Buy','Hold','Sell']"],
) -> str:
    "Numeric agreement / consensus across ratings; call before setting consensus in a decision."
    try:
        from tradingagents.strategies.consensus import (
            agreement_score,
            consensus_from_score,
        )
    except Exception as exc:  # noqa: BLE001
        return f"consensus unavailable: {exc}"
    # agreement_score maps ratings internally (Buy/Hold/Sell/... -> stance).
    score = agreement_score(ratings or [])
    level = consensus_from_score(score)
    s = "n/a" if score is None else f"{score:.2f}"
    n = len(ratings or [])
    return f"consensus: agreement={s} level={level} (n={n})"


@tool
def get_momentum_detail(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    "Exact momentum microstructure (pillars, RVOL, VWAP, first-pullback, session) for a ticker."
    try:
        from tradingagents.strategies.momentum import (
            ema9,
            first_pullback,
            pillars,
            rvol,
            vwap,
        )
    except Exception as exc:  # noqa: BLE001
        return f"momentum detail unavailable for {ticker}: {exc}"
    data = _ohlcv(ticker)
    closes = data.get("closes") or []
    highs = data.get("highs") or []
    lows = data.get("lows") or []
    vols = data.get("volumes") or []
    opens = data.get("opens") or []
    if not closes:
        return f"momentum detail unavailable for {ticker}: no history."
    try:
        rv = rvol(vols, window=50) if vols else None
        vw = vwap(closes, vols) if vols else None
        ema = ema9(closes[-10:]) if len(closes) >= 10 else None
        p = pillars(
            close=closes[-1],
            day_volume=vols[-1] if vols else None,
            prev_close=closes[-2] if len(closes) >= 2 else None,
            day_open=opens[-1] if opens else None,
        )
        fp = first_pullback(closes, highs, lows, vols) if len(closes) >= 5 else None
    except Exception as exc:  # noqa: BLE001
        return f"momentum detail unavailable for {ticker}: {exc}"
    parts = [f"momentum detail {ticker}:"]
    if rv is not None:
        parts.append(f"  rvol={rv:.2f}")
    if vw is not None:
        parts.append(f"  vwap={vw:.2f}")
    if ema is not None:
        parts.append(f"  ema9={ema:.2f}")
    if p:
        for k in ("a", "m", "e", "l"):
            if p.get(k) is not None:
                parts.append(f"  pillar_{k}={p[k]}")
    if fp:
        parts.append(f"  first_pullback={fp}")
    return "\n".join(parts)


@tool
def get_beat_miss_sizing(
    side: Annotated[str, "'beat' or 'miss' (the earnings surprise side)"],
    catalyst: Annotated[float, "catalyst scale 0..1, default 1.0"] = 1.0,
) -> str:
    "Position multiplier implied by an earnings beat/miss side (with catalyst scale)."
    try:
        from tradingagents.strategies.events import position_mult_by_side
    except Exception as exc:  # noqa: BLE001
        return f"beat/miss sizing unavailable: {exc}"
    mult = position_mult_by_side(side, catalyst=float(catalyst))
    return f"beat/miss sizing: side={side} position_mult={mult:.2f}"


# ---------------------------------------------------------------------------
# DCF valuation (pragmatic FCF-DCF) - an intrinsic-value lens for the
# fundamentals analyst. Uses provider-sourced free cash flow + market inputs.
# ---------------------------------------------------------------------------
def _dcf_latest(d):
    """Latest-of a canonical value (handles {current,prior} dicts)."""
    if isinstance(d, dict):
        return d.get("current", d.get("value"))
    return d


def _dcf_canonical(payload):
    from tradingagents.dataflows.statement_parsing import _canonicalize

    return _canonicalize(payload)


def _dcf_yf_rows(payload):
    """Parse a yfinance-style CSV statement into {label: {date: value}} using
    the header date columns (most recent first).

    yfinance statements are ``# comment`` + data.to_csv(): a header line whose
    first cell is blank followed by the date columns, then row lines. Skip
    comment (#) and blank lines so we locate the real header.
    """
    import csv as _csv
    import io as _io

    from tradingagents.dataflows.statement_parsing import _first_number

    rows = {}
    try:
        reader = _csv.reader(_io.StringIO(payload or ""))
        lines = [r for r in reader if r and not (r[0] or "").startswith("#")]
    except Exception:
        return rows
    if not lines:
        return rows
    # Header = first line whose first cell is blank (the date-column header).
    header = None
    data_start = 0
    for idx, row in enumerate(lines):
        if not (row[0] or "").strip():
            header = row[1:]
            data_start = idx + 1
            break
    if header is None:
        return rows
    for row in lines[data_start:]:
        if not row or not (row[0] or "").strip():
            continue
        label = row[0].strip()
        vals = {}
        for i, cell in enumerate(row[1:]):
            parsed = _first_number(cell)
            if parsed is not None and i < len(header):
                vals[str(header[i])[:10]] = parsed
        if vals:
            rows[label] = vals
        else:
            rows[label] = {}
    return rows
    return rows


def _dcf_fcf_series(cashflow_payload):
    """Time-ordered positive FCF series from a cashflow payload.

    Supports both shapes the vendor chain returns for "annual" cashflow:
    yfinance-style CSV rows (``_dcf_yf_rows``) and moomoo per-period markdown
    tables (``statement_parsing._markdown_period_tables``, which arranges the
    rows newest-first). FCF is the "Free Cash Flow" row when present, else
    operating cash flow minus capex; only positive values enter the series
    (compute_dcf's contract). moomoo is the default first vendor, so a
    CSV-only parser previously degraded DCF to "no usable free cash flow".
    """
    if not cashflow_payload or str(cashflow_payload).lstrip().startswith(
        ("NO_DATA", "DATA_DISABLED", "DATA_UNAVAILABLE")
    ):
        return []
    # moomoo markdown: period tables (newest first) -> per-year FCF.
    try:
        from tradingagents.dataflows.statement_parsing import (
            _markdown_period_tables,
            _period_year,
        )

        tables = _markdown_period_tables(cashflow_payload)
    except Exception:  # noqa: BLE001 - CSV payloads parse to no tables
        tables = []
    if tables:
        by_year = {}
        for period, rows in tables:
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
                    try:
                        fcf = float(op) - float(cap)
                    except (TypeError, ValueError):
                        fcf = None
            if fcf is not None:
                try:
                    by_year[_period_year(period)] = float(fcf)
                except (TypeError, ValueError):
                    continue
        series = [v for _, v in sorted(by_year.items()) if v > 0]
        if series:
            return series
    # yfinance-style CSV: per-date columns parsed by _dcf_yf_rows.
    rows = _dcf_yf_rows(cashflow_payload)
    fcf_row = None
    for label, vals in rows.items():
        if "free cash flow" in label.lower():
            fcf_row = vals
            break
    if fcf_row is None:
        op = cap = None
        for label, vals in rows.items():
            low = label.lower()
            if "operating cash flow" in low or "cash flow from operating" in low:
                op = vals
            if "capital expenditure" in low or "purchase of property" in low:
                cap = vals
        if op and cap:
            fcf_row = {d: op.get(d, 0.0) - cap.get(d, 0.0) for d in op}
    if not fcf_row:
        return []
    series = [fcf_row[d] for d in sorted(fcf_row) if fcf_row[d] is not None]
    return [float(v) for v in series if float(v) > 0]


def _dcf_market_cap(fund):
    return _dcf_latest(fund.get("market_cap"))


def _dcf_beta(fund):
    return _dcf_latest(fund.get("beta")) or 1.0


def _dcf_cash_debt(bal):
    return _dcf_latest(bal.get("cash")) or 0.0, _dcf_latest(bal.get("total_debt")) or 0.0


def _dcf_shares(fund, bal, market_cap, ticker):
    """Shares from balance/fundamentals, else derived (market_cap / last close)."""
    for src in (bal, fund):
        for key in ("diluted_shares", "shares_outstanding", "shares", "shares_os"):
            v = _dcf_latest(src.get(key)) if isinstance(src, dict) else None
            if v:
                return float(v)
    last = _dcf_last_close(ticker)
    if last and market_cap:
        return float(market_cap) / float(last)
    return None


def _dcf_rf(current_date):
    out = route_to_vendor("get_macro_indicators", "10y_treasury", current_date, None)
    import re

    try:
        m = re.search(r"Latest[^0-9]*([0-9.]+)", out or "")
        return float(m.group(1)) / 100.0 if m else None
    except Exception:
        return None


def _dcf_last_close(ticker):
    data = _ohlcv(ticker)
    closes = data.get("closes") or []
    return closes[-1] if closes else None


@tool
def get_dcf_valuation(
    ticker: Annotated[str, "ticker symbol"],
    current_date: Annotated[str, "the current trading date, YYYY-mm-dd"],
    growth: Annotated[float, "forward FCF growth as a fraction (e.g. 0.025)"] = 0.025,
    erp: Annotated[float, "equity risk premium as a fraction, default 0.05"] = 0.05,
    years: Annotated[int, "explicit forecast years, default 5"] = 5,
) -> str:
    "Pragmatic discounted-cash-flow valuation from provider-sourced free cash flow."
    try:
        from tradingagents.strategies.dcf import compute_dcf
    except Exception as exc:  # noqa: BLE001
        return f"dcf unavailable for {ticker}: {exc}"
    try:
        cf_payload = route_to_vendor("get_cashflow", ticker, "annual", current_date) or ""
        fcf = _dcf_fcf_series(cf_payload)
        if not fcf:
            return f"dcf unavailable for {ticker}: no usable free cash flow series."
        rf = _dcf_rf(current_date)
        # Screener-grade canonical line items (fundamentals + balance sheet +
        # income statement + finnhub gap-fill), so market cap / shares resolve
        # even when moomoo's statement payload has no "Market Cap" row.
        from tradingagents.dataflows.statement_parsing import fetch_ticker

        fin = fetch_ticker(ticker, current_date) or {}
        market_cap = _dcf_market_cap(fin)
        beta = _dcf_beta(fin)
        cash, debt = _dcf_cash_debt(fin)
        shares = _dcf_shares(fin, fin, market_cap, ticker)
        if not shares:
            return f"dcf unavailable for {ticker}: no shares outstanding."
        if rf is None:
            rf = 0.04
    except Exception as exc:  # noqa: BLE001
        return f"dcf unavailable for {ticker}: {exc}"
    res = compute_dcf(
        fcf,
        rf=rf,
        beta=beta,
        erp=erp,
        growth=growth,
        years=years,
        shares=shares,
        cash=cash,
        debt=debt,
    )
    if not res:
        return f"dcf unavailable for {ticker}: inputs not usable (no positive FCF or g>=wacc)."
    return (
        f"dcf {ticker}: fair_value={res['price']:.2f} "
        f"ev={res['ev']:.2f} pv_explicit={res['pv_explicit']:.2f} "
        f"pv_terminal={res['pv_tv']:.2f} terminal_share={res['terminal_share']:.0%} "
        f"wacc={res['wacc']:.2%} g={res['growth']:.2%} "
        f"fcf_latest={res['fcf_latest']:.2f} shares={res['shares']:.1f} "
        f"(provider-derived; growth/ERP are analyst overrides)"
    )


# ---------------------------------------------------------------------------
# Item-1: sector leadership / sector standing (market analyst)
# ---------------------------------------------------------------------------


@tool
def get_sector_rank(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Sector-momentum ranking (11 SPDR groups, 1m + 3m) and where the ticker's
    own sector sits (top3 / tracking / unknown). Use before any sector-rotation
    or 'sector leadership' claim.

    Args:
        ticker: single ticker symbol (e.g. "AAPL").

    Returns:
        The 3m top-3 SPDR group tickers + the ticker's sector standing, or
        an explicit 'unavailable' message when no SPDR series resolves.
    """
    try:
        from tradingagents.strategies.sector_rank import (
            rank_sectors,
            sector_standing,
        )
    except Exception as exc:  # noqa: BLE001
        return f"sector rank unavailable for {ticker}: {exc}"
    from tradingagents.strategies.sector_rank import SPDR_SECTORS

    closes_map = {}
    for etf in SPDR_SECTORS:
        closes = _ohlcv(etf).get("closes") or []
        if len(closes) >= 65:  # ~3 months of bars
            closes_map[etf] = closes
    if not closes_map:
        return f"sector rank unavailable for {ticker}: no SPDR history from the vendor chain."
    ranking = rank_sectors(closes_map)
    top3 = ranking.get("top3_3m") or []
    top1 = ranking.get("top3_1m") or []
    top3_names = [SPDR_SECTORS.get(e, e) for e in top3]

    # Resolve the ticker's sector -> standing.
    sector = None
    try:
        from tradingagents.dataflows.yfinance_sector import fetch_sector

        sector = fetch_sector(ticker)
    except Exception:  # noqa: BLE001
        sector = None
    standing = sector_standing(sector, ranking)
    lines = [
        f"sector rank {ticker}:",
        f"  top3_3m={top3_names}",
        f"  top1_1m={[SPDR_SECTORS.get(e, e) for e in top1[:1]]}",
        f"  sector={sector or 'n/a'} standing={standing.get('verdict')} "
        f"rank={standing.get('rank') if standing.get('rank') is not None else 'n/a'}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Item-2: strategy quality (market analyst) - net CAGR / Sharpe / drawdown
# ---------------------------------------------------------------------------


@tool
def get_strategy_quality(
    ticker: Annotated[str, "ticker symbol"],
    returns: Annotated[
        list[float] | None, "optional daily/simple returns; defaults to price-derived"
    ] = None,
    cost_bps: Annotated[float, "per-trade cost in basis points, default 10"] = 10.0,
) -> str:
    """Risk-adjusted quality of a strategy over its return series: net CAGR,
    annualized volatility and Sharpe ratio. Use when judging whether a
    strategy is backtest-worth / risk-adjusted rather than just gross return.

    Args:
        ticker: ticker symbol (used to derive default returns when not given).
        returns: optional explicit daily/% returns list.
        cost_bps: per-trade cost subtracted from each period return.

    Returns:
        A single line with the computed metrics, or an explicit 'unavailable'.
    """
    try:
        from tradingagents.strategies.evaluate import (
            cagr,
            equity_curve,
            max_drawdown,
            net_returns,
            sharpe,
            volatility,
        )
    except Exception as exc:  # noqa: BLE001
        return f"strategy quality unavailable: {exc}"
    if returns is None or not returns:
        closes = _ohlcv(ticker).get("closes") or []
        if len(closes) < 30:
            return f"strategy quality unavailable for {ticker}: not enough price history."
        returns = _daily_returns(closes)
    if len(returns) < 4:
        return f"strategy quality unavailable for {ticker}: need >=4 returns."
    net = net_returns(returns, cost_bps=cost_bps)
    cg = cagr(net)
    vol = volatility(net)
    shr = sharpe(net)
    curve = equity_curve(net)
    mdd = max_drawdown(curve)
    return (
        f"strategy quality {ticker}: net_cagr={cg:.2%} vol={vol:.2%} "
        f"sharpe={shr:.2f} max_dd={mdd:.2%} n={len(net)}"
    )


# ---------------------------------------------------------------------------
# Item-3a: safety margin (fundamentals) ----------------
# ---------------------------------------------------------------------------


@tool
def get_margin_of_safety(
    ticker: Annotated[str, "ticker symbol"],
    intrinsic: Annotated[
        float | None, "intrinsic value estimate, e.g. from a DCF / normalized EV/EBIT"
    ] = None,
) -> str:
    """(intrinsic - price) / intrinsic safety margin for a name.

    Use when arguing about 'undervalued / margin-of-safety' on intrinsics. Pass
    ``intrinsic`` from a valuation the analyst already produced (e.g. from
    get_dcf_valuation / get_analyst_verdict / your own fair value) - it is
    required, since the safety margin is only meaningful against an explicit
    intrinsic estimate.
    """
    try:
        from tradingagents.strategies.normalized import margin_of_safety
    except Exception as exc:  # noqa: BLE001
        return f"margin of safety unavailable for {ticker}: {exc}"
    closes = _ohlcv(ticker).get("closes") or []
    price = closes[-1] if closes else None
    if price is None:
        return f"margin of safety unavailable for {ticker}: no price."
    if intrinsic is None or intrinsic <= 0:
        return f"margin of safety unavailable for {ticker}: pass a positive intrinsic estimate (e.g. from get_dcf_valuation) to compute the safety margin."
    mos = margin_of_safety(price, float(intrinsic))
    if mos is None:
        return f"margin of safety unavailable for {ticker}: unquantifiable."
    band = "wide" if mos > 0.3 else ("modest" if mos > 0 else "negative")
    return f"margin of safety {ticker}: {mos:.1%} ({band}); price={price:.2f} intrinsic={intrinsic:.2f}"


# ---------------------------------------------------------------------------
# Item 3b: composite factor rank (fundamentals) ---
# ---------------------------------------------------------------------------


@tool
def get_composite_rank(
    ticker: Annotated[str, "ticker symbol"],
    factors: Annotated[
        dict | None, "optional extra factor -> value map (e.g. {'ev_ebit': -1})"
    ] = None,
) -> str:
    """Cross-sectional value+momentum composite (percentile-ranked)
    from the ticker + its industry peers, folding in optional factor weights.

    Returns the percentile composite (0-1) and the per-factor percentile ranks.
    """
    try:
        from tradingagents.strategies.factors import composite_score, high_distance, momentum
    except Exception as exc:  # noqa: BLE001
        return f"composite rank unavailable for {ticker}: {exc}"
    # Peer universe: the ticker plus its company peers, when available.
    peers = [ticker]
    try:
        from tradingagents.dataflows.finnhub import get_company_peers_finnhub

        peer_list = get_company_peers_finnhub(ticker) or []
        peers = [ticker] + list(peer_list)[:8]
    except Exception:  # noqa: BLE001
        peers = [ticker]
    factors_by_ticker = {}
    for t in peers:
        closes = _ohlcv(t).get("closes") or []
        f = {}
        if len(closes) >= 64:
            mom = momentum(closes)
            if mom is not None:
                f["momentum"] = mom
            hd = high_distance(closes)
            if hd is not None:
                f["high_distance"] = hd
        if factors and t == ticker:
            f.update(factors)
        if f:
            factors_by_ticker[t] = f
    if len(factors_by_ticker) < 2 or ticker not in factors_by_ticker:
        return f"composite rank unavailable for {ticker}: <2 comparable tickers with factor data."
    weights = None
    if factors:
        # weight the explicit factors & default the momentum peers.
        weights = {"momentum": 1.0, "high_distance": 1.0}
        for k in factors:
            weights[k] = -1.0 if factors[k] < 0 else 1.0
    scores = composite_score(factors_by_ticker, weights)
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])[:6]
    peers_str = "; ".join(f"{t}={v:.0%}" for t, v in ranked)
    return (
        f"composite rank {ticker}: score={scores[ticker]:.2%} "
        f"(vs {len(scores) - 1} peers); {peers_str}"
    )


# ---------------------------------------------------------------------------
# Item 4: tail / book risk (market analyst) ----------------
# ---------------------------------------------------------------------------


@tool
def get_tail_risk(
    ticker: Annotated[str, "ticker symbol"],
    alpha: Annotated[float, "tail size, default 0.05"] = 0.05,
    weight: Annotated[float, "allocation weight for stress-loss exposure, default 1.0"] = 1.0,
) -> str:
    """Book & tail-risk read: historical VaR and CVaR over the trailing
    return series, plus a uniform -10% stress loss on the given weight."""
    try:
        from tradingagents.strategies.book_risk import cvar, stress_loss
    except Exception as exc:  # noqa: BLE001
        return f"tail risk unavailable for {ticker}: {exc}"
    closes = _ohlcv(ticker).get("closes") or []
    if len(closes) < 30:
        return f"tail risk unavailable for {ticker}: not enough price history."
    returns = _daily_returns(closes)
    if not returns:
        return f"tail risk unavailable for {ticker}: no returns."
    c = cvar(returns, alpha=alpha)
    stress = stress_loss({ticker: weight}, shock=-0.10)
    var = None
    try:
        from tradingagents.strategies.book_risk import simple_var

        var = simple_var(returns, alpha=alpha)
    except Exception:
        var = None
    return (
        f"tail risk {ticker}: cvar={abs(c):.2%} var={abs(var) if var is not None else 'n/a'} "
        f"stress_-10pct={stress:.2%} alpha={alpha:.0%}"
    )


@tool
def get_ratios(
    ticker: Annotated[str, "ticker symbol"],
    current_date: Annotated[str | None, "as-of date (yyyy-mm-dd)"] = None,
) -> str:
    """Computed valuation & profitability ratios (free, local derivation).

    Replicates the block Massive's plan-gated ``/stocks/financials/v1/ratios``
    returns, computed from this project's own canonical line items
    (moomoo/yfinance/alpha_vantage): EV, EV/EBIT, EV/EBITDA, EV/Sales, P/E,
    P/B, P/S, P/CF, P/FCF, ROE, ROA, D/E, Current, Quick, Cash ratio,
    dividend yield, FCF, market cap. Use before any 'cheap / richly valued /
    quality' claim. Missing inputs render ``n/a`` (never fabricated).

    Args:
        ticker: single ticker symbol.
        current_date: optional as-of date (yyyy-mm-dd).

    Returns:
        A ``key: value`` block of the computable ratios.
    """
    try:
        from tradingagents.strategies.ratios import compute_ratios, render_ratios
    except Exception as exc:  # noqa: BLE001
        return f"ratios unavailable for {ticker}: {exc}"
    try:
        from tradingagents.dataflows.statement_parsing import fetch_ticker

        fin = fetch_ticker(ticker, current_date or "2026-08-24") or {}
    except Exception as exc:  # noqa: BLE001
        return f"ratios unavailable for {ticker}: {exc}"
    ratios = compute_ratios(fin)
    if not any(v is not None for v in ratios.values()):
        return (
            f"ratios unavailable for {ticker}: no usable statement line items; "
            "do not fabricate valuation ratios."
        )
    return f"## {ticker.upper()} Ratios (computed)\n\n" + render_ratios(ratios)


# Item-5: credit-stress read (market analyst) - HY/CCC/BB OAS from FRED
# ---------------------------------------------------------------------------


def _fred_latest_pct(payload: str) -> float | None:
    """Parse the latest value (%) from a FRED macro markdown payload."""
    import re as _re

    m = _re.search(r"Latest:\*{2}\s*([0-9.]+)", payload or "")
    return float(m.group(1)) if m else None


@tool
def get_credit_spread_read(
    current_date: Annotated[str, "the current trading date, YYYY-mm-dd"],
) -> str:
    """Credit-stress read from the three ICE BofA US high-yield OAS spreads
    (FRED, daily): whole HY (BAMLH0A0HYM2), CCC & lower (BAMLH0A3HYC) and BB
    (BAMLH0A1HYBB). Returns each spread in % and a deterministic credit-cycle
    band (low/moderate/high/severe) + a 0..1 de-risk scale. Call before any
    'credit stress / risk-off / debt market' claim; the CCC spread is the
    leading risk-off sentinel."""
    try:
        from tradingagents.strategies.credit_spread import credit_stress_level
    except Exception as exc:  # noqa: BLE001
        return f"credit spread read unavailable: {exc}"
    hy = _fred_latest_pct(route_to_vendor("get_macro_indicators", "hy_oas", current_date, None))
    ccc = _fred_latest_pct(route_to_vendor("get_macro_indicators", "ccc_oas", current_date, None))
    bb = _fred_latest_pct(route_to_vendor("get_macro_indicators", "bb_oas", current_date, None))
    if hy is None and ccc is None and bb is None:
        return (
            f"credit spread read unavailable for {current_date}: no FRED OAS data "
            "(FRED_API_KEY unset or series missing in the window)."
        )
    res = credit_stress_level(hy, ccc, bb)
    if res["level"] == "unknown":
        return f"credit spread read unavailable for {current_date}."
    lines = [
        f"credit spread read {current_date}:",
        f"  level={res['level']} scale={res['scale']:.2f}",
    ]
    for r in res["reasons"]:
        lines.append(f"  {r}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Session discipline (market analyst) - waves `momentum.session_flags` +
# `psych_level` + `past_optimal_window` into one intraday walk-away read.
# ---------------------------------------------------------------------------


@tool
def get_session_discipline(
    ticker: Annotated[str, "ticker symbol"],
    peak_pnl: Annotated[
        float | None, "session peak P&L as a fraction of capital, if trading live"
    ] = None,
    current_pnl: Annotated[
        float | None, "current session P&L as a fraction of capital, if trading live"
    ] = None,
) -> str:
    """Intraday session-discipline read (walk-away rules + psychological levels).

    Deterministic "walk away for the day" flags from the momentum playbook:
    50% giveback from session peak, max-daily-loss breach, past the 10:00 ET
    optimal window, and no quality setups. Also reports the nearest
    whole/half-dollar psychological levels around the current price. Call this
    before any 'sell into strength / take the day off / giveback' claim when
    trading intraday momentum.

    Args:
        ticker: single ticker symbol.
        peak_pnl: session peak P&L as a fraction (e.g. 0.02 for +2%); omit when
            not tracking live P&L (the giveback/max-loss rules stay unknown).
        current_pnl: current session P&L as a fraction; omit when not tracking
            live P&L.

    Returns:
        The walk-away flag + each rule's state + the psych levels, or an
        explicit 'unavailable' message when price data is missing.
    """
    try:
        from tradingagents.strategies.momentum import (
            past_optimal_window,
            psych_level,
            session_flags,
        )
    except Exception as exc:  # noqa: BLE001
        return f"session discipline unavailable for {ticker}: {exc}"
    closes = _ohlcv(ticker).get("closes") or []
    if not closes:
        return f"session discipline unavailable for {ticker}: no price history."
    price = closes[-1]
    past_window = past_optimal_window()
    flags = session_flags(
        peak_pnl=peak_pnl,
        current_pnl=current_pnl,
        past_optimal_window=past_window,
    )
    pl = psych_level(price)
    lines = [
        f"session discipline {ticker}:",
        f"  walk_away={flags['walk_away']}",
        f"  giveback_50={flags['giveback_50']} max_daily_loss_hit={flags['max_daily_loss_hit']}",
        f"  past_optimal_window={flags['past_optimal_window']}"
        f" no_quality_setups={flags['no_quality_setups']}",
    ]
    if pl.get("above") is not None:
        lines.append(
            f"  psych_levels: next={pl['above']} below={pl['below']} "
            f"dist_to_next={pl['dist_pct'] and round(pl['dist_pct'], 2)}%"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Earnings quality (fundamentals analyst) - Sloan accruals + the forensic
# trap verdict that *includes* the accrual evidence (screen_ticker's trap call
# drops it today).
# ---------------------------------------------------------------------------


@tool
def get_earnings_quality(
    ticker: Annotated[str, "ticker symbol"],
    current_date: Annotated[str, "the current trading date, YYYY-mm-dd"],
) -> str:
    """Deterministic earnings-quality read: Sloan accruals + forensic trap.

    Computes the accruals ratio (net income - operating cash flow) / total
    assets - a high value signals earnings quality risk - then folds it into
    the forensic trap verdict (Beneish M / Altman Z / F-Score) with the
    accrual as an extra evidence trigger. Call this before any
    'strong earnings quality / accrual-driven earnings / manipulation risk'
    claim; it is the computed number, not a guess.

    Args:
        ticker: single ticker symbol.
        current_date: the current trading date (YYYY-mm-dd).

    Returns:
        accruals + quality/trap verdict lines, or an explicit 'unavailable'
        message when the vendor chain yields no statements.
    """
    try:
        from tradingagents.dataflows.statement_parsing import fetch_ticker
    except Exception as exc:  # noqa: BLE001
        return f"earnings quality unavailable for {ticker}: {exc}"
    fin = fetch_ticker(ticker, current_date)
    if not fin:
        return (
            f"earnings quality unavailable for {ticker}: no statements from "
            "the vendor chain; do not fabricate quality screens."
        )
    try:
        from tradingagents.dataflows.statement_parsing import _latest
        from tradingagents.strategies.normalized import accruals_ratio, trap_verdict
    except Exception as exc:  # noqa: BLE001
        return f"earnings quality unavailable for {ticker}: {exc}"
    ni = _latest(fin.get("net_income"))
    cfo = _latest(fin.get("operating_cashflow"))
    ta = _latest(fin.get("total_assets"))
    accrual = accruals_ratio(ni, cfo, ta) if (ni is not None or cfo is not None) else None
    lines = [f"earnings quality {ticker}:"]
    if accrual is None:
        lines.append("  accruals_ratio: n/a (needs net_income + operating_cashflow + total_assets)")
        lines.append("  guidance: do not claim earnings quality without the accrual input.")
    else:
        band = (
            "low-earnings-quality-risk"
            if accrual > 0.06
            else ("moderate" if accrual > 0.02 else "clean")
        )
        lines.append(f"  accrual_ratio={accrual:.3f} ({band}): high accruals = quality risk")
    m = z = f = None
    try:
        # Reuse the screener's screens so the trap verdict includes the accrual,
        # which screen_ticker's own trap call currently omits.
        from tradingagents.dataflows.statement_parsing import screen_ticker

        row = screen_ticker(ticker, fin)
        m, z, f = row.get("beneish_m"), row.get("altman_z"), row.get("f_score")
    except Exception:  # noqa: BLE001
        pass
    trap = None
    if any(v is not None for v in (m, z, f, accrual)):
        import contextlib

        with contextlib.suppress(Exception):
            trap = trap_verdict(f_score=f, m_score=m, z_score=z, accrual=accrual)
    if trap:
        lines.append(f"  trap_risk={trap.get('level')}")
        for ev in trap.get("evidence") or []:
            lines.append(f"    - {ev}")
    else:
        lines.append("  trap_risk: insufficient forensic inputs")
    return chr(10).join(lines)


@tool
def get_ownership_concentration(
    ticker: Annotated[str, "ticker symbol"],
    current_date: Annotated[str, "the current trading date, YYYY-mm-dd"],
) -> str:
    """Ownership-concentration read (Strategies/risk2.md).

    Computes the free-float factor (IWF = float / total shares) and, when a
    per-holder breakdown is available, the Herfindahl-Hirschman index (HHI =
    sum of squared ownership %). IWF < 0.5 signals structural passive
    under-allocation; HHI > 2500 signals highly concentrated governance risk.
    Best-effort: HHI is n/a when no per-holder data source is configured.
    Use before any 'widely held / concentrated ownership / index-eligible'
    claim.

    Args:
        ticker: single ticker symbol.
        current_date: the current trading date (YYYY-mm-dd).

    Returns:
        IWF + HHI lines, or an explicit 'unavailable' message.
    """
    try:
        from tradingagents.dataflows.float_shares import fetch_float_shares
        from tradingagents.dataflows.statement_parsing import fetch_ticker
        from tradingagents.strategies.liquidity_risk import (
            free_float_factor as _iwf,
            ownership_hhi as _hhi,
        )

        float_sh = fetch_float_shares(ticker)
        fin = fetch_ticker(ticker, current_date) or {}
        sh = fin.get("shares")
        tot_sh = sh.get("current") if isinstance(sh, dict) else sh
        iwf = _iwf(float_sh, tot_sh)
        lines = [f"ownership concentration {ticker}:"]
        lines.append(
            f"  iwf={iwf:.2%}" if iwf is not None else "  iwf=n/a (needs float + total shares)"
        )
        if iwf is not None and iwf < 0.5:
            lines.append("  note: IWF < 0.5 -> structural passive under-allocation")
        # HHI needs a per-holder breakdown; best-effort (n/a when unavailable).
        hhi = None
        try:
            from tradingagents.dataflows.interface import route_to_vendor

            payload = route_to_vendor("get_institution_holdings", ticker) or ""
            # Parse per-holder percentages from the institutional-holdings
            # payload if it carries them (moomoo aggregate has none).
            import re

            pcts = [
                float(m)
                for m in re.findall(r"([0-9]+(?:\.[0-9]+)?)%", payload)
                if float(m) <= 100.0
            ]
            if pcts:
                hhi = _hhi(pcts)
        except Exception:  # noqa: BLE001 - best-effort
            hhi = None
        lines.append(
            f"  hhi={hhi:.0f}" if hhi is not None else "  hhi=n/a (no per-holder breakdown)"
        )
        if hhi is not None and hhi > 2500:
            lines.append("  note: HHI > 2500 -> highly concentrated governance risk")
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001
        return f"ownership concentration unavailable for {ticker}: {exc}"


__all__ = [
    "get_sector_rank",
    "get_strategy_quality",
    "get_credit_spread_read",
    "get_margin_of_safety",
    "get_composite_rank",
    "get_tail_risk",
    "get_swing_set",
    "get_relative_strength",
    "get_earnings_event_read",
    "get_catalyst_scale",
    "get_position_sizing",
    "get_risk_gate",
    "get_regime_read",
    "get_volatility_contraction",
    "get_swing_exits",
    "get_dip_technical",
    "get_orderflow_read",
    "get_analyst_verdict",
    "get_earnings_surprise",
    "get_portfolio_weights",
    "get_basic_financials",
    "get_insider_activity",
    "get_company_peers",
    "get_form4_insider",
    "get_ratios",
    "get_exit_check",
    "get_allocation",
    "get_regime_components",
    "get_consensus",
    "get_momentum_detail",
    "get_beat_miss_sizing",
    "get_dcf_valuation",
    "get_session_discipline",
    "get_earnings_quality",
    "get_ownership_concentration",
]

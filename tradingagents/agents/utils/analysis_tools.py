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

import contextlib
from typing import Annotated

from langchain_core.tools import tool

from tradingagents.dataflows.interface import route_to_vendor

# ---------------------------------------------------------------------------
# Shared data helpers (vendor chain CSV, benchmark closes)
# ---------------------------------------------------------------------------

# Run-level OHLCV cache: every tool that needs daily bars shares ONE fetch per
# ticker per run (the analyst tool loops call many tools that each wrap
# strategies/* over the same OHLCV). Without this, a run re-fetches the same
# vendor CSV N times (duplicate data + quota burn). Keyed by (ticker, days).
_RUN_OHLCV_CACHE: dict[tuple[str, int], dict] = {}


def _clear_ohlcv_cache() -> None:
    """Drop the run-level OHLCV cache (tests / fresh runs)."""
    _RUN_OHLCV_CACHE.clear()


def _ohlcv(ticker: str, days: int = 320) -> dict:
    """Daily OHLCV via the vendor chain (Date,Open,High,Low,Close,Volume rows).

    Returns {"dates", "closes", "highs", "lows", "volumes", "opens"} (all
    empty on failure). Mirrors the graph's close-fetch but keeps the full
    OHLCV the swing/PEAD calculations need. Cached per (ticker, days) for the
    run so multiple tools sharing the series never re-fetch it.
    """
    key = (str(ticker).upper(), int(days))
    cached = _RUN_OHLCV_CACHE.get(key)
    if cached is not None:
        return cached
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
        result = {
            "dates": dates,
            "closes": closes,
            "highs": highs,
            "lows": lows,
            "volumes": volumes,
            "opens": opens,
        }
        _RUN_OHLCV_CACHE[key] = result
        return result
    except Exception:  # noqa: BLE001 - a fetch failure degrades, never raises
        result = {
            "dates": [],
            "closes": [],
            "opens": [],
            "highs": [],
            "lows": [],
            "volumes": [],
        }
        _RUN_OHLCV_CACHE[key] = result
        return result


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
    book_total_pct: Annotated[
        float | None, "current book exposure as a fraction, if known"
    ] = None,
    daily_loss_pct: Annotated[
        float | None, "today's realized loss as a fraction of capital, if known"
    ] = None,
    hwm_drawdown_pct: Annotated[
        float | None, "drawdown from the high-water mark as a fraction, if known"
    ] = None,
    capital_at_risk_pct: Annotated[
        float | None, "worst-case capital-at-risk at the hard stop (tranche fold), if known"
    ] = None,
    risk_cap_pct: Annotated[
        float | None, "capital-at-risk budget (e.g. tranche_risk_pct), if known"
    ] = None,
    liquidity_verdict: Annotated[
        str | None, "composite liquidity verdict: LIQUID | CAUTION | ILLIQUID, if known"
    ] = None,
    sector_pct: Annotated[
        float | None, "current sector exposure as a fraction, if known"
    ] = None,
    halted: Annotated[bool, "whether a risk halt is active"] = False,
) -> str:
    """House risk-gate verdict for a proposed position (deterministic).

    Applies the project's risk governor limits (max_position_pct, book cap,
    CVaR budget, drawdown, daily-loss budget, high-water-mark tiers, sector
    cap, tranche capital-at-risk, liquidity verdict) to a proposed size and
    returns PASS / WARN / REJECT with the numeric reasons. Use this when
    evaluating any proposed size (including the Trader's), instead of
    asserting a size is 'reasonable' in prose.

    Args:
        size_pct: the proposed position size (0..1).
        cvar_pct: portfolio tail-loss budget used (optional).
        drawdown_pct: current realized drawdown (optional).
        book_total_pct: current book exposure (optional; book cap check).
        daily_loss_pct: session realized loss (optional; daily-loss budget).
        hwm_drawdown_pct: drawdown from high-water mark (optional; soft/hard
            de-risk tiers).
        capital_at_risk_pct: worst-case capital at the hard stop under a
            tranche scale-in plan (optional).
        risk_cap_pct: the capital-at-risk budget that bounds it (optional).
        liquidity_verdict: LIQUID / CAUTION / ILLIQUID (optional; ILLIQUID
            REJECTs, CAUTION WARNs).
        sector_pct: current sector exposure (optional; sector cap check).
        halted: True when a risk halt is active (immediate REJECT).

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
        book_total_pct=book_total_pct,
        cvar_pct=cvar_pct,
        drawdown_pct=drawdown_pct,
        daily_loss_pct=daily_loss_pct,
        hwm_drawdown_pct=hwm_drawdown_pct,
        sector_pct=sector_pct,
        halted=halted,
        capital_at_risk_pct=capital_at_risk_pct,
        risk_cap_pct=risk_cap_pct,
        liquidity_verdict=liquidity_verdict,
    )
    if verdict.get("verdict") == "PASS" and not verdict.get("reasons"):
        lines = [f"risk: PASS {size_pct:.1%}"]
    else:
        lines = [
            build_risk_snapshot(
                verdict,
                size_pct,
                cvar_pct=cvar_pct,
                drawdown_pct=drawdown_pct,
                capital_at_risk_pct=capital_at_risk_pct,
            )
        ]
    extra = []
    if daily_loss_pct is not None:
        extra.append(f"daily_loss={daily_loss_pct:.2%}")
    if hwm_drawdown_pct is not None:
        extra.append(f"hwm_drawdown={hwm_drawdown_pct:.2%}")
    if book_total_pct is not None:
        extra.append(f"book_total={book_total_pct:.1%}")
    if sector_pct is not None:
        extra.append(f"sector={sector_pct:.1%}")
    if liquidity_verdict is not None:
        extra.append(f"liquidity={str(liquidity_verdict).upper()}")
    if extra:
        lines.append("inputs: " + "; ".join(extra))
    if verdict.get("reasons"):
        lines.append("reasons: " + "; ".join(verdict["reasons"]))
    return chr(10).join(lines)




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
        ch = chandelier_exit(closes, atr_v, highs=data["highs"])
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
def get_mean_reversion_tech(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Mean-reversion dip-timing + exit technicals: StochRSI, RSI2, Williams %R,
    Keltner, Donchian, OBV divergence, Parabolic SAR, Elder thermometer.

    Complements get_dip_technical with the faster/smoother oscillators and
    channel/volume confirmations. Use before any 'oversold / dip timing /
    mean reversion / channel support / trailing exit' claim.

    Args:
        ticker: single ticker symbol.

    Returns:
        The computed oscillator/channel lines, or an explicit 'unavailable'.
    """
    data = _ohlcv(ticker)
    closes = data["closes"]
    if not closes or len(closes) < 30:
        return f"mean reversion tech unavailable for {ticker}: fewer than 30 bars."
    try:
        from tradingagents.strategies.size import atr
        from tradingagents.strategies.technical_factors import (
            donchian_channel as _don,
            elder_thermometer as _elder,
            keltner_channel as _kelt,
            obv_divergence as _obv,
            parabolic_sar as _psar,
            rsi2 as _rsi2,
            stoch_rsi as _srsi,
            williams_r as _wr,
        )

        atr_v = atr(data["highs"], data["lows"], closes, window=14)
        s = _srsi(closes)
        k = _kelt(closes, atr_value=atr_v)
        d = _don(data["highs"], data["lows"])
        o = _obv(closes, data["volumes"])
        p = _psar(data["highs"], data["lows"])
        e = _elder(data["volumes"])
        lines = [
            f"mean reversion tech {ticker}:",
            f"  stochrsi={s.get('stochrsi')} oversold={s.get('oversold')}",
            f"  rsi2={_rsi2(closes)} williams_r={_wr(data['highs'], data['lows'], closes)}",
            f"  keltner mid={k.get('mid')} pct={k.get('pct')}",
            f"  donchian up={d.get('upper')} lo={d.get('lower')}",
            f"  obv_up={o.get('obv_up')} bullish_div={o.get('bullish_div')}",
            f"  psar={p.get('sar')} elder_ratio={e.get('ratio')} heavy={e.get('heavy')}",
        ]
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001
        return f"mean reversion tech unavailable for {ticker}: {exc}"


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
    returns_by_name: Annotated[
        dict | None,
        "name -> daily return series (optional). When provided and the "
        "enable_correlation_penalty config is on, names whose average pairwise "
        "correlation with the rest of the book exceeds the threshold are "
        "down-weighted before the caps (risk-parity concentration control).",
    ] = None,
) -> str:
    "Cap-respecting, value-proportional allocation across a book (hard per-name and per-sector caps)."
    try:
        from tradingagents.dataflows.config import get_config
        from tradingagents.strategies.portfolio import (
            adjust_for_caps,
            capped_weights,
            correlation_penalty,
            summary,
            value_ratio_weights,
        )
    except Exception as exc:  # noqa: BLE001
        return f"allocation unavailable: {exc}"
    w = value_ratio_weights(scores, min_weight=0.0)
    corr_note = ""
    if returns_by_name and get_config().get("enable_correlation_penalty"):
        w = correlation_penalty(
            w,
            returns_by_name,
            threshold=float(get_config().get("correlation_threshold", 0.6)),
            penalty=float(get_config().get("correlation_penalty_frac", 0.3)),
        )
        corr_note = " · correlation-penalized"
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
    if corr_note:
        lines.append(corr_note)
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
        for k in ("rvol", "high_volume", "gap", "price_band", "float"):
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
                        # abs(cap): the vendor may sign capital expenditure as a
                        # GAAP outflow (yfinance/Tiingo) or a positive magnitude;
                        # OCF - negative capex would inflate FCF.
                        fcf = float(op) - abs(float(cap))
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
            fcf_row = {d: abs(op.get(d, 0.0)) - abs(cap.get(d, 0.0)) for d in op}
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
            calmar_ratio,
            equity_curve,
            expectancy_stats,
            max_drawdown,
            net_returns,
            probabilistic_sharpe,
            sharpe,
            sortino,
            tail_ratio,
            ulcer_index,
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
    so = sortino(net)
    psr = probabilistic_sharpe(net)
    so_txt = f"{so:.2f}" if so is not None else "unavailable"
    psr_txt = f"{psr:.2f}" if psr is not None else "unavailable"
    # Opportunistic breadth (evaluate.* extras the audit found unwrapped):
    cal = calmar_ratio(net)
    ul = ulcer_index(net)
    tr = tail_ratio(net)
    ex = expectancy_stats([r for r in net if r > 0], [r for r in net if r < 0])

    def _f(v, nd=2):
        return "unavailable" if v is None else f"{v:.{nd}f}"

    ex_txt = "unavailable"
    if ex is not None:
        ex_txt = f"pf={_f(ex.get('profit_factor'))} win_rate={ex.get('win_rate')!s}"
    return (
        f"strategy quality {ticker}: net_cagr={cg:.2%} vol={vol:.2%} "
        f"sharpe={shr:.2f} sortino={so_txt} psr={psr_txt} max_dd={mdd:.2%} "
        f"calmar={_f(cal)} ulcer={_f(ul)} tail_ratio={_f(tr)} "
        f"{ex_txt} n={len(net)}"
    )


@tool
def get_downside_read(
    ticker: Annotated[str, "ticker symbol"],
    target: Annotated[float | None, "target/minimum return (MAR), default 0"] = None,
) -> str:
    """Downside / regret measures about a target (QuantLib Q7).

    Reports semi-deviation (about the mean), downside deviation (about the
    target), shortfall probability and average shortfall — the exact
    target-anchored downside numbers that complement CVaR. Use when the analyst
    wants to quantify 'how bad is the downside' rather than assert it.
    """
    try:
        from tradingagents.strategies.rate_utils import downside_measures
    except Exception as exc:  # noqa: BLE001
        return f"downside read unavailable for {ticker}: {exc}"
    closes = _ohlcv(ticker).get("closes") or []
    if len(closes) < 15:
        return f"downside read unavailable for {ticker}: not enough history."
    returns = _daily_returns(closes)
    d = downside_measures(returns, 0.0 if target is None else float(target))
    if d["n"] == 0:
        return f"downside read unavailable for {ticker}: no returns."
    return (
        f"downside {ticker}: semi_dev={(d['semi_deviation'] or 0):.2%} "
        f"downside_dev={(d['downside_deviation'] or 0):.2%} "
        f"shortfall_prob={(d['shortfall_prob'] or 0):.1%} "
        f"avg_shortfall={(d['avg_shortfall'] or 0):.2%} n={d['n']}"
    )


@tool
def get_horizon_var(
    ticker: Annotated[str, "ticker symbol"],
    horizon_days: Annotated[int, "risk horizon in days"] = 5,
    alpha: Annotated[float, "confidence level, default 0.95"] = 0.95,
) -> str:
    """Horizon VaR/CVaR (QuantLib Q1) gated on autocorrelation.

    Reports empirical + parametric VaR/CVaR at a multi-day horizon and whether
    the sqrt(T) scaling is valid (i.i.d. gate). Use when the risk-governor /
    book-tails need a horizon-correct number instead of '~3x daily'.
    """
    try:
        from tradingagents.strategies.book_risk import var_cvar_horizon
    except Exception as exc:  # noqa: BLE001
        return f"horizon var unavailable for {ticker}: {exc}"
    closes = _ohlcv(ticker).get("closes") or []
    if len(closes) < 60:
        return f"horizon var unavailable for {ticker}: need >=60 bars."
    returns = _daily_returns(closes)
    r = var_cvar_horizon(returns, int(horizon_days), float(alpha))
    if r["n"] < 2:
        return f"horizon var unavailable for {ticker}: no returns."
    valid = "valid" if r["scaling_valid"] else "NOT-iid"
    return (
        f"horizon_var {ticker} {horizon_days}d: emp_var={(r['emp_var'] or 0):.2%} "
        f"emp_cvar={(r['emp_cvar'] or 0):.2%} "
        f"param_var={(r['param_var'] or 0):.2%} scaling={valid} n={r['n']}"
    )


@tool
def get_trailing_exit(
    ticker: Annotated[str, "ticker symbol"],
    entry: Annotated[float, "entry price"],
    peak: Annotated[float, "highest price since entry"],
    current: Annotated[float, "current price"],
    trail_pct: Annotated[float, "trailing-stop % from peak, default 0.05"] = 0.05,
) -> str:
    """Peak-trailing / give-back exit arithm (Lean L4).

    Reports whether a peak-trail stop is struck and the exit price. Use when
    deciding to hold or take profit on a runner that has given back ground
    from its peak — the fixed ATR rules never force such an exit.
    """
    try:
        from tradingagents.strategies.exits import trailing_stop_exit
    except Exception as exc:  # noqa: BLE001
        return f"trailing exit unavailable for {ticker}: {exc}"
    r = trailing_stop_exit(float(entry), float(peak), float(current), float(trail_pct))
    if r["stop_px"] is None:
        return f"trailing exit unavailable for {ticker}: unusable inputs."
    verdict = "EXIT" if r["exit"] else "hold"
    return (
        f"trailing_exit {ticker}: {verdict} stop_px={r['stop_px']:.2f} "
        f"drawdown_from_peak={r['drawdown_from_peak']:.1%} (trail {float(trail_pct):.0%})"
    )


@tool
def get_exit_plan(
    entry: Annotated[float, "entry price"],
    atr: Annotated[float, "ATR at exit decision"],
    current: Annotated[float, "current price"],
    peak: Annotated[float, "highest price since entry, default = current"] = 0.0,
    stop: Annotated[float | None, "entry stop price, for the R-based BE rule"] = None,
    giveback_pct: Annotated[float, "margin give-back fraction, default 0.30"] = 0.30,
) -> str:
    """Trade-management exit arithm (B3 + Lean L4).

    Combines the breakeven rule (move to BE only after confirmation - 1R or a
    higher low, never too early) and the margin-giveback stop (a runner that
    has surrendered a set fraction of its best peak gain is exited) into one
    deterministic read the Trader/manager cites. Pass entry/atr/current/peak
    and optionally the entry stop price for the R-based BE trigger.
    """
    try:
        from tradingagents.strategies.exits import (
            breakeven_after_confirmation,
            max_giveback_exit,
        )
    except Exception as exc:  # noqa: BLE001
        return f"exit plan unavailable: {exc}"
    peak = float(peak) if peak else float(current)
    be = breakeven_after_confirmation(
        entry_price=float(entry),
        stop_price=float(stop) if stop is not None else None,
        trigger="structure",
        rr=1.0,
        atr=float(atr),
    )
    gb = max_giveback_exit(float(entry), float(peak), float(current), float(giveback_pct))
    be_s = f"{be.get('price'):.2f}" if be.get("price") is not None else "unavailable"
    gb_v = "EXIT" if gb.get("exit") else "hold"
    return (
        f"exit_plan: breakeven_stop={be_s} (trigger={be.get('trigger')}) "
        f"giveback_{gb_v} stop_px={gb.get('stop_px')} "
        f"remaining_gain_pct={gb.get('remaining_gain_pct')} (giveback {float(giveback_pct):.0%})"
    )


@tool
def get_scaleout_plan(
    entry: Annotated[float, "entry price"],
    stop: Annotated[float, "invalidation/stop price"],
    t1_fraction: Annotated[float, "fraction to sell at target 1, default 0.5"] = 0.5,
) -> str:
    """Scale-out profit policy (swing.scaleout_plan, Phase-5 profit mgmt).

    Reports the tiered partial-profit plan: sell ``t1_fraction`` at T1, move
    the rest to break-even, trail the remainder. Use before any 'take partial
    profits / scale out / let winners run' claim on a swing position.
    """
    try:
        from tradingagents.strategies.swing import scaleout_plan
    except Exception as exc:  # noqa: BLE001
        return f"scaleout plan unavailable: {exc}"
    r = scaleout_plan(float(entry), float(stop), t1_fraction=float(t1_fraction))
    if not r.get("valid"):
        return "scaleout plan unavailable: unusable entry/stop."
    return (
        f"scaleout_plan: t1={r['t1']:.2f} t2={r['t2']:.2f} "
        f"sell_t1_fraction={r['t1_fraction']:.0%} keep_t2={r['t2_fraction']:.0%} "
        f"breakeven_after_t1={r['breakeven_after_t1']} trail={r['trail']}"
    )


@tool
def get_payoff_asymmetry(
    ticker: Annotated[str, "ticker symbol"],
    returns: Annotated[
        list[float] | None, "optional return series; default price-derived"
    ] = None,
    threshold: Annotated[float, "payoff threshold, default 0"] = 0.0,
) -> str:
    """Omega ratio (statistical.omega): parameter-free payoff asymmetry about a
    threshold - sum of gains / sum of losses; >1 = upside-heavy payoff. Use
    before any 'positive skew / asymmetric payoff / limited downside' claim.
    """
    try:
        from tradingagents.strategies.statistical import omega
    except Exception as exc:  # noqa: BLE001
        return f"payoff asymmetry unavailable for {ticker}: {exc}"
    if returns is None or not returns:
        closes = _ohlcv(ticker).get("closes") or []
        if len(closes) < 15:
            return f"payoff asymmetry unavailable for {ticker}: not enough history."
        returns = _daily_returns(closes)
    o = omega(returns, threshold=float(threshold))
    if o is None:
        return f"payoff asymmetry unavailable for {ticker}: needs gains and losses."
    return f"payoff asymmetry {ticker}: omega={o:.2f} threshold={threshold} n={len(returns)}"


@tool
def get_book_correlation(
    returns_by_name: Annotated[
        dict, "dict of name -> aligned return series"
    ],
    method: Annotated[str, "pearson | spearman | kendall, default pearson"] = "pearson",
) -> str:
    """Full pairwise correlation matrix over a book (statistical.correlation_matrix).

    Reports the average pairwise correlation and the most-correlated pair - the
    concentration control behind the correlation-aware allocation. Use before
    any 'this book is diversified / over-concentrated' claim.
    """
    try:
        from tradingagents.strategies.statistical import correlation_matrix
    except Exception as exc:  # noqa: BLE001
        return f"book correlation unavailable: {exc}"
    m = correlation_matrix(returns_by_name, method=method)
    if not m or "names" not in m or len(m["names"]) < 2:
        return "book correlation unavailable: need >= 2 aligned return series."
    names = m["names"]
    flat = []
    for ni, row in m["corr"].items():
        for nj, r in row.items():
            if r is not None and ni < nj:
                flat.append((abs(r), ni, nj))
    if not flat:
        return "book correlation unavailable: no computable pairs."
    avg = sum(v for v, _, _ in flat) / len(flat)
    max_v, max_i, max_j = max(flat, key=lambda t: t[0])
    return (
        f"book_correlation ({method}): n={len(names)} avg_pairwise={avg:.2f} "
        f"max=|{max_i}/{max_j}|={max_v:.2f}"
    )


@tool
def get_risk_parity_alloc(
    ticker: Annotated[str, "anchor ticker (signal context)"],
    returns_by_name: Annotated[
        dict, "dict of name -> return series (aligned daily/monthly returns)"
    ],
) -> str:
    """Risk-parity / min-variance / confidence-weighted allocation over a book.

    Reports risk-parity weights (equalized risk contribution), minimum-variance
    weights and per-name risk contributions from an actual covariance matrix —
    instead of value-ratio + hard clips. Pass ``returns_by_name`` of the book.
    """
    try:
        from tradingagents.strategies.portfolio_optimizer import (
            max_diversification_weights,
            min_variance_weights,
            risk_contribution,
            risk_parity_weights,
        )
    except Exception as exc:  # noqa: BLE001
        return f"risk-parity alloc unavailable: {exc}"
    rp = risk_parity_weights(returns_by_name)
    mv = min_variance_weights(returns_by_name)
    md = max_diversification_weights(returns_by_name)
    rc = risk_contribution(rp["weights"], returns_by_name)
    if not rp["weights"]:
        return "risk-parity alloc unavailable: covariance not computable."
    rp_s = ", ".join(f"{k}={v:.1%}" for k, v in rp["weights"].items())
    rc_s = ", ".join(f"{k}={v:.1%}" for k, v in rc.items()) if rc else "n/a"
    md_s = ", ".join(f"{k}={v:.1%}" for k, v in md["weights"].items()) if md.get("weights") else "n/a"
    return (
        f"risk_parity_alloc {ticker}: {rp_s} [{rp['note']}]; "
        f"min_var={mv['note']}; max_div={md_s} [{md['note']}]; "
        f"risk_contribution={{ {rc_s} }}"
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
    cdar_line = ""
    try:
        from tradingagents.strategies.book_risk import cdar

        cd = cdar(closes, alpha=alpha)  # close series as the equity proxy
        if cd is not None:
            cdar_line = f" cdar={cd['cdar']:.2%} dvar={cd['dvar']:.2%}"
    except Exception:
        pass
    return (
        f"tail risk {ticker}: cvar={abs(c):.2%} var={abs(var) if var is not None else 'n/a'}"
        f"{cdar_line} stress_-10pct={stress:.2%} alpha={alpha:.0%}"
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
        from tradingagents.strategies.credit_spread import (
            credit_stress_level,
            default_probability,
            hazard_from_spread,
        )
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
    # Implied default probability from the HY spread (RR = 0.40 assumption).
    if hy is not None:
        lam = hazard_from_spread(hy, 0.40)
        pd = default_probability(hy, 1.0, 0.40)
        if lam is not None and pd is not None:
            lines.append(
                f"  implied 1y default prob (HY, RR=0.40): {pd:.1%} "
                f"(hazard {lam:.3f})"
            )
    return "\n".join(lines)


@tool
def get_merton_distance(
    equity: Annotated[float, "market equity value (dollars)"],
    debt: Annotated[float, "total debt / liabilities (dollars)"],
    equity_vol: Annotated[float, "annualized equity vol (e.g. 0.30)"],
    r: Annotated[float, "risk-free rate, default 0.03"] = 0.03,
    t: Annotated[float, "horizon years, default 1.0"] = 1.0,
) -> str:
    """Merton structural distance-to-default (quants.md §Credit).

    Calibrates asset value + asset vol from equity-as-a-call and reports
    distance-to-default (d2), asset vol and the risk-neutral default
    probability. A structural credit read complementing the spread-based band
    in get_credit_spread_read. Advisory; state your equity/debt/vol inputs.
    """
    try:
        from tradingagents.strategies.credit_spread import merton_distance_to_default
    except Exception as exc:  # noqa: BLE001
        return f"merton distance unavailable: {exc}"
    try:
        m = merton_distance_to_default(equity, debt, equity_vol, float(r), float(t))
    except (TypeError, ValueError):
        return "merton distance unavailable: invalid inputs"
    if m is None:
        return "merton distance unavailable: non-positive / non-convergent inputs"
    return (
        f"merton distance-to-default: dtd={m['distance_to_default']:.2f} "
        f"asset_vol={m['asset_volatility']:.1%} pd_1y={m['risk_neutral_pd']:.2%} "
        f"converged={m['converged']} (E={equity} D={debt} sE={equity_vol})"
    )


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


@tool
def get_opening_range(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Opening-range breakout (ORB) read: first-15-min high/low + breakout.

    Computes the opening range (first ~15 bars of the daily series), whether
    the latest close broke above/below it, and a 2R stop/target. Call before
    any 'opening range / ORB / first-15-min breakout' claim on a swing entry.
    """
    data = _ohlcv(ticker)
    closes = data["closes"]
    if len(closes) < 20:
        return f"opening range unavailable for {ticker}: fewer than 20 bars."
    try:
        from tradingagents.strategies.market_session import opening_range

        r = opening_range(data["highs"], data["lows"], closes=closes)
        if r.get("or_high") is None:
            return f"opening range unavailable for {ticker}: insufficient bars."
        return (
            f"opening range {ticker}: or_high={r['or_high']} or_low={r['or_low']} "
            f"breakout={r.get('breakout')} stop={r.get('stop')} target={r.get('target')}"
        )
    except Exception as exc:  # noqa: BLE001
        return f"opening range unavailable for {ticker}: {exc}"


@tool
def get_gap_type(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Overnight gap classification: common / breakaway / runaway / exhaustion
    + heuristic fill probability and days-to-fill.

    Call before any 'gap will fill / breakaway gap / gap risk' claim on a
    pre-market or post-close read. The fill stats are heuristic estimates
    from gap size + volume (never fabricated).
    """
    data = _ohlcv(ticker)
    closes = data["closes"]
    if len(closes) < 25:
        return f"gap type unavailable for {ticker}: fewer than 25 bars."
    try:
        from tradingagents.strategies.market_session import gap_type

        r = gap_type(closes, data["highs"], data["lows"], data["volumes"])
        if r.get("type") is None:
            return f"gap type unavailable for {ticker}: insufficient data."
        return (
            f"gap type {ticker}: {r['type']} gap_pct={r['gap_pct']:.2%} "
            f"fill_probability={r['fill_probability']:.0%} days_to_fill={r['days_to_fill']}"
        )
    except Exception as exc:  # noqa: BLE001
        return f"gap type unavailable for {ticker}: {exc}"


@tool
def get_order_imbalance(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Order-imbalance verdict (buy-heavy / sell-heavy / balanced) from the
    institutional vs retail net flow.

    Reuses the orderflow module's institutional/retail nets. Call before any
    'institutions are buying/selling / order imbalance' claim.
    """
    try:
        from tradingagents.dataflows.interface import route_to_vendor
        from tradingagents.strategies.market_session import order_imbalance
        from tradingagents.strategies.orderflow import (
            institutional_net as _inst_net,
            retail_net as _retail_net,
            tier_nets as _tier_nets,
        )

        payload = route_to_vendor("get_capital_flow", ticker) or ""
        buckets = {}
        for line in payload.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.lower().startswith("date"):
                continue
            parts = line.split(",")
            if len(parts) >= 2:
                with contextlib.suppress(ValueError):
                    buckets[parts[0].strip()] = float(parts[1])
        nets = _tier_nets(buckets)
        inst = _inst_net(nets)
        retail = _retail_net(nets)
        r = order_imbalance(inst, retail)
        if r.get("verdict") is None:
            return f"order imbalance unavailable for {ticker}: no flow data."
        return (
            f"order imbalance {ticker}: {r['verdict']} ratio={r['ratio']:.2f} "
            f"(inst_net={inst} retail_net={retail})"
        )
    except Exception as exc:  # noqa: BLE001
        return f"order imbalance unavailable for {ticker}: {exc}"


@tool
def get_premarket_liquidity(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Pre-market liquidity read: pre-market volume vs the daily average.

    A very low ratio = thin book (wide spreads, gap risk). Call before any
    'liquid enough to trade pre-market / thin book / wide spread' claim.
    """
    try:
        from tradingagents.strategies.market_session import premarket_liquidity

        # pre-market volume is not exposed by the free vendors; use the latest
        # daily volume as a proxy and label it clearly.
        data = _ohlcv(ticker)
        vols = data["volumes"]
        if len(vols) < 30:
            return f"premarket liquidity unavailable for {ticker}: insufficient volume history."
        latest = float(vols[-1])
        avg = sum(float(v) for v in vols[-30:]) / 30
        r = premarket_liquidity(latest, avg)
        if r.get("verdict") is None:
            return f"premarket liquidity unavailable for {ticker}."
        return (
            f"premarket liquidity {ticker}: ratio={r['ratio']:.2f} verdict={r['verdict']} "
            "(latest daily volume vs 30d avg - pre-market volume not exposed by free vendors)"
        )
    except Exception as exc:  # noqa: BLE001
        return f"premarket liquidity unavailable for {ticker}: {exc}"


@tool
def get_post_close_confirmation(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Post-close confirmation: did the latest close confirm the plan?

    Compares the latest close against the prior report's stop/target (from
    the newest report folder's decision.md). Verdicts: stopped-out /
    target-hit / holding. Call before any 'the close confirmed / stopped out'
    claim on a held position.
    """
    try:
        from tradingagents.strategies.market_session import post_close_confirmation

        data = _ohlcv(ticker)
        closes = data["closes"]
        if not closes:
            return f"post-close confirmation unavailable for {ticker}: no price history."
        close = float(closes[-1])
        # find the newest report's stop/target from decision.md
        stop = target = None
        import glob
        import os

        root = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "reports")
        hits = sorted(glob.glob(os.path.join(root, f"{ticker.upper()}_*")), reverse=True)
        for folder in hits:
            md = os.path.join(folder, "5_portfolio", "decision.md")
            if not os.path.isfile(md):
                continue
            import re

            with open(md, encoding="utf-8") as fh:
                text = fh.read()
            m = re.search(r"\*\*Stop Loss\*\*[^0-9]*([0-9.]+)", text)
            if m:
                stop = float(m.group(1))
            m = re.search(r"\*\*Price Target\*\*[^0-9]*([0-9.]+)", text)
            if m:
                target = float(m.group(1))
            break
        r = post_close_confirmation(close, stop, target)
        if r.get("verdict") is None:
            return f"post-close confirmation unavailable for {ticker}."
        return (
            f"post-close confirmation {ticker}: close={close:.2f} verdict={r['verdict']} "
            f"action={r['action']} (stop={stop} target={target})"
        )
    except Exception as exc:  # noqa: BLE001
        return f"post-close confirmation unavailable for {ticker}: {exc}"


@tool

def get_technical_factors(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Extended technical factors: ADX, pivots, Aroon, Fisher, Chaikin,
    Elder-Ray, Supertrend, volume profile (POC + value area).

    Complements get_indicators / get_dip_technical with the trend-strength,
    reversal, accumulation and volume-profile reads the analyst prompt does
    not otherwise expose. One combined call (shares the run-level OHLCV
    cache) so no duplicate data is fetched. Use before any 'trend strength /
    pivot support-resistance / Aroon age / Fisher turn / Chaikin accumulation /
    Elder-Ray buying pressure / Supertrend direction / POC-value-area' claim.
    """
    try:
        from tradingagents.strategies.technical_factors import (
            adx as _adx,
            aroon as _aroon,
            chaikin_oscillator as _chaikin,
            elder_ray as _elder_ray,
            fisher_transform as _fisher,
            pivot_points as _pivots,
            supertrend as _supertrend,
            volume_profile as _volprof,
        )
    except Exception as exc:  # noqa: BLE001
        return f"technical factors unavailable for {ticker}: {exc}"
    data = _ohlcv(ticker)
    closes = data["closes"]
    if len(closes) < 30:
        return f"technical factors unavailable for {ticker}: fewer than 30 bars."
    try:
        a = _adx(data["highs"], data["lows"], closes)
        piv = _pivots(data["highs"][-1], data["lows"][-1], closes[-1])
        ar = _aroon(data["highs"], data["lows"])
        fi = _fisher(closes)
        ch = _chaikin(data["highs"], data["lows"], closes, data["volumes"])
        er = _elder_ray(data["highs"], data["lows"], closes)
        st = _supertrend(data["highs"], data["lows"], closes)
        vp = _volprof(closes, data["volumes"])
        lines = [
            f"technical factors {ticker} (close {closes[-1]:.2f}):",
            f"  adx={a.get('adx')} di+={a.get('di_plus')} di-={a.get('di_minus')} "
            f"strong={a.get('strong')}",
            f"  pivots: p={piv.get('p')} r1={piv.get('r1')} s1={piv.get('s1')} "
            f"r2={piv.get('r2')} s2={piv.get('s2')}",
            f"  aroon: up={ar.get('aroon_up')} down={ar.get('aroon_down')} "
            f"verdict={ar.get('verdict')}",
            f"  fisher={fi.get('fisher') if fi else None} trigger={fi.get('trigger') if fi else None}",
            f"  chaikin={ch} (positive=buying pressure)",
            f"  elder_ray: bull={er.get('bull_power')} bear={er.get('bear_power')} "
            f"verdict={er.get('verdict')}",
            f"  supertrend: line={st.get('line')} direction={st.get('direction')}",
            f"  volume_profile: poc={vp.get('poc')} va_high={vp.get('value_area_high')} "
            f"va_low={vp.get('value_area_low')}",
        ]
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001
        return f"technical factors unavailable for {ticker}: {exc}"


@tool
def get_extended_indicators(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Extended trend/momentum/volume indicators: Ichimoku cloud, CCI, ROC,
    momentum oscillator, TRIX, Force Index, A/D line, VPT, Chaikin Money Flow,
    anchored VWAP and the golden/death cross.

    Complements get_technical_factors / get_indicators / get_mean_reversion_tech
    with the standard indicator group the project did not previously compute.
    One combined call (shares the run-level OHLCV cache). Use before any
    'Ichimoku cloud / CCI overbought / ROC momentum / TRIX turn / A-D
    accumulation / volume-price trend / Chaikin Money Flow / VWAP cost-basis /
    golden cross' claim.
    """
    try:
        from tradingagents.strategies.extended_indicators import (
            accumulation_distribution as _ad,
            anchored_vwap as _avwap,
            cci as _cci,
            chaikin_money_flow as _cmf,
            force_index as _fi,
            golden_death_cross as _gdc,
            ichimoku as _ichimoku,
            momentum_oscillator as _mom_osc,
            roc as _roc,
            trix as _trix,
            vpt as _vpt,
        )
    except Exception as exc:  # noqa: BLE001
        return f"extended indicators unavailable for {ticker}: {exc}"
    data = _ohlcv(ticker)
    closes = data["closes"]
    if len(closes) < 60:
        return f"extended indicators unavailable for {ticker}: fewer than 60 bars."
    try:
        ic = _ichimoku(data["highs"], data["lows"], closes)
        cc = _cci(data["highs"], data["lows"], closes)
        rc = _roc(closes)
        mo = _mom_osc(closes)
        tr = _trix(closes)
        fi = _fi(closes, data["volumes"])
        ad = _ad(data["highs"], data["lows"], closes, data["volumes"])
        vp = _vpt(closes, data["volumes"])
        cmf = _cmf(data["highs"], data["lows"], closes, data["volumes"])
        av = _avwap(closes, data["volumes"])
        gdc = _gdc(closes)
        lines = [
            f"extended indicators {ticker} (close {closes[-1]:.2f}):",
            f"  ichimoku: conversion={ic.get('conversion')} base={ic.get('base')} "
            f"span_a={ic.get('span_a')} span_b={ic.get('span_b')} "
            f"position={ic.get('label')}",
            f"  golden/death cross: {gdc.get('label')}",
            f"  cci={cc} (above +100 / below -100)",
            f"  roc={rc}  momentum_osc={mo}",
            f"  trix={tr.get('trix')} signal={tr.get('signal')}",
            f"  force_index={fi} (price x volume momentum)",
            f"  accumulation_distribution={ad} (rising = accumulation)",
            f"  vpt={vp} (volume price trend)",
            f"  cmf={cmf} (above +0.1 = buying pressure)",
            f"  anchored_vwap={av} (cumulative cost basis)",
        ]
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001
        return f"extended indicators unavailable for {ticker}: {exc}"


@tool
def get_candlestick_patterns(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Candlestick pattern scan for the most recent bars: doji, hammer,
    shooting star, bullish/bearish engulfing, morning/evening star.

    Complements the numeric indicators with price-structure reads. One call
    (shares the run-level OHLCV cache). Use before any 'doji indecision /
    hammer reversal / engulfing / morning star / shooting star' claim.
    """
    try:
        from tradingagents.strategies.extended_indicators import scan_candlesticks
    except Exception as exc:  # noqa: BLE001
        return f"candlestick patterns unavailable for {ticker}: {exc}"
    data = _ohlcv(ticker)
    closes = data["closes"]
    if not closes or not data.get("opens"):
        return f"candlestick patterns unavailable for {ticker}: no OHLCV."
    try:
        res = scan_candlesticks(
            data["opens"], data["highs"], data["lows"], closes
        )
        pat = res["patterns"]
        hits = [k for k, v in pat.items() if v]
        lines = [
            f"candlestick patterns {ticker} (last {len(res['bars'])} bars):",
            f"  detected: {', '.join(hits) if hits else 'none'}",
        ]
        if res["bars"]:
            last = res["bars"][-1]
            if "close" in last:
                lines.append(
                    f"  last bar: open={last['open']:.2f} high={last['high']:.2f} "
                    f"low={last['low']:.2f} close={last['close']:.2f}"
                )
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001
        return f"candlestick patterns unavailable for {ticker}: {exc}"


@tool
def get_tail_decomposition(
    names: Annotated[str, "Comma-separated ticker list for the book"],
    weights: Annotated[str, "Comma-separated name=weight pairs (sums to 1)"] = "",
) -> str:
    """Which names drive the book tail? Component VaR (sums to the book's
    historical VaR) + incremental VaR per name. Advisory - the components
    answer 'who is the tail' before a sizing/tail claim.
    """
    try:
        from tradingagents.strategies.book_risk import component_var, incremental_var

        tickers = [t.strip().upper() for t in str(names).split(",") if t.strip()]
        if len(tickers) < 3:
            return "tail decomposition unavailable: need >= 3 names"
        weights_dict: dict = {}
        if weights:
            for pair in str(weights).split(","):
                pair = pair.strip()
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    try:
                        weights_dict[k.strip().upper()] = float(v)
                    except ValueError:
                        continue
        if not weights_dict:
            weights_dict = dict.fromkeys(tickers, 1.0 / len(tickers))
        returns_by_name = {}
        for t in tickers:
            ohlcv = _ohlcv(t, days=320)
            closes = ohlcv["closes"]
            if len(closes) < 60:
                return f"tail decomposition unavailable for {t}: insufficient history"
            rets = []
            for i in range(1, len(closes)):
                if closes[i - 1] and closes[i]:
                    rets.append(closes[i] / closes[i - 1] - 1.0)
            returns_by_name[t] = rets
        comp = component_var(returns_by_name, weights_dict)
        inc = incremental_var(returns_by_name, weights_dict)
        lines = [f"## Tail Decomposition — {', '.join(tickers)}", ""]
        if comp:
            lines.append(f"- Book historical VaR(95%): {comp['total_var']:.4%}")
            lines.append("| name | component VaR | % of book |")
            lines.append("| --- | --- | --- |")
            for n, v in sorted(comp["components"].items(), key=lambda kv: abs(kv[1]), reverse=True):
                pct = v / comp["total_var"] if comp["total_var"] else 0.0
                lines.append(f"| {n} | {v:.4%} | {pct:.1%} |")
            lines.append(
                f"- components sum to {comp['coverage']:.1%} of total VaR (normal decomposition)"
            )
        else:
            lines.append("- component VaR unavailable (degenerate covariance)")
        if inc:
            lines.append("")
            lines.append("| name | incremental VaR (+1% weight) |")
            lines.append("| --- | --- |")
            for n, v in sorted(inc["incremental"].items(), key=lambda kv: abs(kv[1]), reverse=True):
                lines.append(f"| {n} | {v:+.4%} |")
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001 - degrades
        return f"tail decomposition unavailable: {exc}"


@tool

def get_book_tail_risk(
    ticker: Annotated[str, "ticker symbol"],
    weights: Annotated[
        dict | None, "name -> weight map for the book (optional; defaults to the ticker alone)"
    ] = None,
) -> str:
    """Book-level tail risk: portfolio CVaR, correlated stress loss and the
    drawdown gate.

    Complements get_tail_risk (single-name VaR/CVaR) with the book-level
    reads: portfolio CVaR from a weighted return mix, the correlated -10%
    stress loss (a macro event moves every position at once), and the
    drawdown gate (new risk blocked while realized drawdown exceeds the
    limit). Use before any 'book tail / correlated stress / drawdown gate'
    claim. One combined call (shares the run-level OHLCV cache).
    """
    try:
        from tradingagents.strategies.book_risk import (
            book_correlated_stress as _stress,
            drawdown_gate as _gate,
            portfolio_cvar as _pcvar,
            portfolio_returns as _prets,
        )
    except Exception as exc:  # noqa: BLE001
        return f"book tail risk unavailable for {ticker}: {exc}"
    try:
        w = dict(weights or {})
        if not w:
            w = {ticker: 1.0}
        returns_by_name = {}
        for name in w:
            closes = _ohlcv(name).get("closes") or []
            rets = _daily_returns(closes)
            if len(rets) >= 30:
                returns_by_name[name] = rets
        if not returns_by_name:
            return f"book tail risk unavailable for {ticker}: no return series."
        pcvar = _pcvar(returns_by_name, weights=w)
        stress = _stress(returns_by_name, weights=w, shock=-0.10)
        # realized drawdown of the weighted book (best-effort)
        dd = None
        try:
            from tradingagents.strategies.evaluate import max_drawdown

            eq = []
            acc = 1.0
            for r in _prets(w, returns_by_name):
                acc *= 1.0 + r
                eq.append(acc)
            dd = max_drawdown(eq) if eq else None
        except Exception:
            dd = None
        gate = _gate(dd) if dd is not None else None
        pcvar_s = f"{abs(pcvar):.2%}" if pcvar is not None else "n/a"
        stress_s = f"{stress:.2%}" if stress is not None else "n/a"
        dd_s = f"{dd:.2%}" if dd is not None else "n/a"
        gate_s = str(gate) if gate is not None else "n/a"
        return (
            f"book tail risk {ticker}: portfolio_cvar={pcvar_s} "
            f"correlated_stress_-10pct={stress_s} "
            f"drawdown={dd_s} drawdown_gate={gate_s} (True=block new risk)"
        )
    except Exception as exc:  # noqa: BLE001
        return f"book tail risk unavailable for {ticker}: {exc}"


@tool

def get_liquidation_days(
    ticker: Annotated[str, "ticker symbol"],
    shares_to_liquidate: Annotated[
        float | None, "shares to liquidate (optional; defaults to the float)"
    ] = None,
) -> str:
    """Days for the market to absorb a block liquidation (Strategies/risk2.md).

    Wraps liquidity_risk.days_to_absorb: how many days of heavy supply the
    float must absorb at a 15% participation cap. Use before any 'can the
    market absorb this block / days to liquidate / unwind risk' claim.
    """
    try:
        from tradingagents.dataflows.float_shares import fetch_float_shares
        from tradingagents.strategies.liquidity_risk import days_to_absorb as _dta
    except Exception as exc:  # noqa: BLE001
        return f"liquidation days unavailable for {ticker}: {exc}"
    try:
        vols = _ohlcv(ticker).get("volumes") or []
        adv = sum(vols[-30:]) / len(vols[-30:]) if len(vols) >= 30 else None
        fs = fetch_float_shares(ticker)
        shares = shares_to_liquidate if shares_to_liquidate is not None else fs
        d = _dta(shares, adv)
        if d is None:
            return f"liquidation days unavailable for {ticker}: missing shares/ADV."
        return (
            f"liquidation days {ticker}: {d:.1f} days to absorb "
            f"{shares:,.0f} shares at 15% of ADV ({adv:,.0f}/day)"
        )
    except Exception as exc:  # noqa: BLE001
        return f"liquidation days unavailable for {ticker}: {exc}"


@tool

def get_premarket_review(
    ticker: Annotated[str, "ticker symbol"],
    prior_close: Annotated[float | None, "prior close price"] = None,
    open_price: Annotated[float | None, "pre-market / opening price"] = None,
    prior_stop: Annotated[float | None, "prior report stop loss"] = None,
    entry_price: Annotated[float | None, "prior report entry price"] = None,
) -> str:
    """Deterministic pre-market review: gap read + catalyst window + re-anchor.

    Wraps pre_market.premarket_gap / catalyst_window_read / reanchor_plan /
    review_decision into one CONFIRM / REVISE / REJECT arbiter from measured
    deltas (gap vs ATR, catalyst window, re-anchored tranche caps). Use
    before any 'gap risk / re-anchor / pre-market review' claim on a held
    plan. Missing inputs degrade to CONFIRM (never fabricate).
    """
    try:
        from tradingagents.strategies.pre_market import review_decision as _review
    except Exception as exc:  # noqa: BLE001
        return f"premarket review unavailable for {ticker}: {exc}"
    try:
        closes = _ohlcv(ticker).get("closes") or []
        atr_v = None
        if len(closes) >= 15:
            from tradingagents.strategies.size import atr as _atr

            atr_v = _atr(_ohlcv(ticker).get("highs") or [], _ohlcv(ticker).get("lows") or [], closes)
        r = _review(
            prior_close=prior_close,
            open_price=open_price,
            prior_stop=prior_stop,
            entry_price=entry_price,
            atr_value=atr_v,
        )
        return (
            f"premarket review {ticker}: verdict={r.get('verdict')} "
            f"entry={r.get('entry')} stop={r.get('stop')} size_pct={r.get('size_pct')} "
            f"reasons={r.get('reasons') or []}"
        )
    except Exception as exc:  # noqa: BLE001
        return f"premarket review unavailable for {ticker}: {exc}"


@tool

def get_sentiment_computed(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Deterministic computed sentiment: score + surprise velocity + counts.

    Wraps sentiment.compute_social_scores (StockTwits labeled counts ->
    signed score, z-scored surprise velocity vs the ticker's own baseline,
    sample size). Use before any 'sentiment is bullish/bearish / sentiment
    surprise / crowd positioning' claim - it is the computed number, not a
    vibe. Degrades to an explicit 'unavailable' when StockTwits has no data.
    """
    try:
        from tradingagents.dataflows.config import get_config
        from tradingagents.strategies.sentiment import (
            compute_social_scores as _scores,
            computed_sentiment_line as _line,
        )
    except Exception as exc:  # noqa: BLE001
        return f"computed sentiment unavailable for {ticker}: {exc}"
    try:
        cfg = get_config()
        result = _scores(ticker, cache_dir=cfg.get("data_cache_dir"), limit=30)
        if not result:
            return f"computed sentiment unavailable for {ticker}: no StockTwits data."
        return _line(result)
    except Exception as exc:  # noqa: BLE001
        return f"computed sentiment unavailable for {ticker}: {exc}"


@tool
def get_news_sentiment_series(
    ticker: Annotated[str, "ticker symbol"],
    look_back_days: Annotated[int, "Days of sentiment history to aggregate"] = 30,
) -> str:
    """Daily news-sentiment series: per-day score (-1..1), 7-day SMA, latest
    innovation, article count — the computed series from the news_sentiment
    chain (EODHD /sentiments -> Alpha Vantage NEWS_SENTIMENT -> GDELT tone).
    Use before any 'news sentiment is shifting / at extremes' claim; it is a
    computed number, not a vibe. Degrades to an explicit unavailable string.
    """
    try:
        from datetime import datetime, timedelta

        from tradingagents.dataflows.interface import route_to_vendor

        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=int(look_back_days) + 1)).strftime("%Y-%m-%d")
        return route_to_vendor("get_news_sentiment", ticker, start, end)
    except Exception as exc:  # noqa: BLE001 - degrades, never crashes
        return f"news sentiment series unavailable for {ticker}: {exc}"


@tool
def get_sentiment_lead_lag(
    ticker: Annotated[str, "ticker symbol"],
    max_lags: Annotated[int, "Max lead/lag days to test"] = 10,
    innovations: Annotated[bool, "Use raw daily sentiment innovations instead of levels"] = False,
) -> str:
    """Cross-correlation of the ticker's daily news sentiment vs its forward
    returns (Pearson + Spearman, lags -max_lags..+max_lags). Positive lag =
    sentiment leads price; the row with the strongest |correlation| shows the
    observed lead relation. Grounds any 'sentiment leads/lags the move' claim.
    """
    try:
        from datetime import datetime, timedelta

        from tradingagents.strategies import sentiment_research as _sr

        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=250)).strftime("%Y-%m-%d")
        points = None
        label = "EODHD"
        try:
            from tradingagents.dataflows.eodhd import _sentiment_points_eodhd

            points = _sentiment_points_eodhd(ticker, start, end)
        except Exception:  # noqa: BLE001
            points = None
        if not points:
            label = "Alpha Vantage"
            try:
                from tradingagents.dataflows.alpha_vantage_news import (
                    _sentiment_points_alpha_vantage,
                )

                points = _sentiment_points_alpha_vantage(ticker, start, end)
            except Exception:  # noqa: BLE001
                points = None
        if not points:
            label = "GDELT"
            try:
                from tradingagents.dataflows.gdelt import _sentiment_points_gdelt

                points = _sentiment_points_gdelt(ticker, start, end)
            except Exception:  # noqa: BLE001
                points = None
        if not points:
            return (
                f"sentiment lead/lag unavailable for {ticker}: "
                "no sentiment series from any feed"
            )
        ohlcv = _ohlcv(ticker, days=320)
        closes = ohlcv["closes"]
        dates = ohlcv["dates"]
        if len(closes) < 30:
            return (
                f"sentiment lead/lag unavailable for {ticker}: "
                "insufficient OHLCV history"
            )
        by_date = {p["date"]: p["score"] for p in points}
        idx = [i for i, d in enumerate(dates) if d in by_date]
        if len(idx) < 10:
            return (
                f"sentiment lead/lag unavailable for {ticker}: "
                f"only {len(idx)} aligned sentiment days"
            )
        s = [by_date[dates[i]] for i in idx]
        r = []
        for i in idx:
            if i > 0 and closes[i - 1]:
                r.append(closes[i] / closes[i - 1] - 1.0)
            else:
                r.append(None)
        rows = [(a, b) for a, b in zip(s, r, strict=False) if b is not None]
        if len(rows) < 10:
            return (
                f"sentiment lead/lag unavailable for {ticker}: "
                "insufficient aligned returns"
            )
        out = _sr.sentiment_lead_lag(
            [x[0] for x in rows], [x[1] for x in rows],
            max_lags=int(max_lags), innovations=bool(innovations),
        )
        if not out:
            return f"sentiment lead/lag unavailable for {ticker}: degenerate series"
        lines = [f"## Sentiment Lead/Lag — {ticker} (source {label})", ""]
        lines.append("| lag | pearson | p | spearman | p | n |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for row in out:
            lines.append(
                f"| {row['lag_days']:+d} | {row['pearson_corr']:.3f} | "
                f"{row['pearson_pval']:.3f} | {row['spearman_corr']:.3f} | "
                f"{row['spearman_pval']:.3f} | {row['sample_size']} |"
            )
        if out:
            best = max(abs(r2["spearman_corr"]) for r2 in out)
            return "\n".join(lines) + f"\n- strongest |corr|: {best:.3f} ({label})"
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001 - degrades, never crashes
        return f"sentiment lead/lag unavailable for {ticker}: {exc}"


def _vol_models_read(ticker: str, model: str) -> str:
    """Shared helper: fetch OHLCV via the run cache, run the chosen estimator."""
    import math

    from tradingagents.strategies import volatility_models as _vm

    ohlcv = _ohlcv(ticker, days=320)
    closes = ohlcv["closes"]
    if len(closes) < 60:
        return f"{model} volatility unavailable for {ticker}: insufficient history"
    logrets = []
    for i in range(1, len(closes)):
        if closes[i - 1] and closes[i]:
            logrets.append(math.log(closes[i] / closes[i - 1]))
    if model == "ewma":
        v = _vm.ewma_vol(logrets)
        if v is None:
            return f"ewma volatility unavailable for {ticker}: insufficient returns"
        return (
            f"## EWMA Volatility — {ticker}\n"
            f"- annualized vol (lambda 0.94): {v:.2%}\n"
            f"- n={len(logrets)}"
        )
    if model == "garch":
        fit = _vm.garch11_fit(logrets)
        if not fit:
            return f"garch volatility unavailable for {ticker}: fit did not converge"
        recent = fit["series"][-1] if fit.get("series") else None
        lines = [
            f"## GARCH(1,1) Volatility — {ticker}",
            f"- omega={fit['omega']} alpha={fit['alpha']} beta={fit['beta']}",
            f"- long-run annualized vol: {fit['long_run_vol']:.2%}",
        ]
        if recent is not None:
            lines.append(f"- latest conditional annualized vol: {recent:.2%}")
        lines.append(f"- n={fit['n']}")
        return "\n".join(lines)
    highs, lows, opens = ohlcv["highs"], ohlcv["lows"], ohlcv["opens"]
    if model == "parkinson":
        v = _vm.parkinson_vol(highs, lows, window=min(60, len(closes)))
        label = "Parkinson"
    else:
        v = _vm.garman_klass_vol(opens, highs, lows, closes, window=min(60, len(closes)))
        label = "Garman-Klass"
    if v is None:
        return f"{label.lower()} volatility unavailable for {ticker}: degenerate OHLC"
    return (
        f"## {label} Volatility — {ticker} (day-only estimate)\n"
        f"- annualized vol: {v:.2%}\n"
        f"- note: range-based estimator assumes continuous trading (no overnight gaps); "
        f"use as the intraday-risk read, not a full-period vol"
    )


@tool
def get_garch_volatility(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Conditional volatility from a GARCH(1,1) fit (omega/alpha/beta,
    long-run annualized vol, conditional-vol series). Pure MLE, offline.
    Use before any 'volatility regime / clustering / long-run vol' claim.
    """
    try:
        return _vol_models_read(ticker, model="garch")
    except Exception as exc:  # noqa: BLE001 - degrades
        return f"garch volatility unavailable for {ticker}: {exc}"


@tool
def get_mean_reversion_quality(
    ticker: Annotated[str, "ticker symbol"],
    window: Annotated[int, "Lookback days for the AR(1) / OU fit"] = 120,
) -> str:
    """Is this series mean-reverting, and how fast? AR(1) / OU half-life +
    verdict (mean-reverting / trending / stable) from the closing series.
    Use before any 'mean reversion / buy the dip / fading the move' claim; a
    trend, not a mean-reversion, in the measured half-life invalidates a
    pure fade.
    """
    try:
        from tradingagents.strategies.mean_reversion import (
            ar1_half_life,
            mean_reversion_verdict,
            ou_half_life,
        )

        ohlcv = _ohlcv(ticker, days=320)
        closes = ohlcv["closes"]
        window = max(60, min(int(window), len(closes)))
        use = closes[-window:] if closes else []
        if len(use) < 60:
            return f"mean-reversion quality unavailable for {ticker}: insufficient history"
        v = mean_reversion_verdict(use)
        hl_ar1 = ar1_half_life(use)
        hl_ou = ou_half_life(use)
        lines = [
            f"## Mean-Reversion Quality — {ticker}",
            f"- verdict: {v['verdict']} (n={v['n']})",
            f"- phi (AR(1) slope): {v['phi'] if v['phi'] is not None else 'n/a'}",
        ]
        if hl_ar1 is not None:
            lines.append(f"- AR(1) half-life: {hl_ar1} days")
        if hl_ou is not None:
            lines.append(f"- OU half-life: {hl_ou} days")
        if v["verdict"] == "mean-reverting":
            lines.append(
                "- read: dip entries supported by the measured mean-reversion "
                f"(half-life {v['half_life']}d); sized to the reversion cadence"
            )
        elif v["verdict"] == "trending":
            lines.append(
                "- read: the series is TRENDING (phi >= 0); a pure mean-reversion "
                "entry is unsupported - trend-follow the structure instead"
            )
        else:
            lines.append("- read: not enough signal to classify (stable); treat as trend until evidence")
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001 - degrades
        return f"mean-reversion quality unavailable for {ticker}: {exc}"


@tool
def get_volatility_estimators(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """All four volatility estimators side by side (closing, Parkinson,
    Garman-Klass, EWMA, GARCH long-run) for the ticker. Use it before any
    'the stock is/isn't volatile / vol is elevated' claim — the range-based
    and conditional reads complement the close-to-close number.
    """
    try:
        import math

        from tradingagents.strategies import volatility_models as _vm
        from tradingagents.strategies.regime import realized_vol

        ohlcv = _ohlcv(ticker, days=320)
        closes = ohlcv["closes"]
        if len(closes) < 40:
            return f"volatility estimators unavailable for {ticker}: insufficient history"
        logrets = []
        for i in range(1, len(closes)):
            if closes[i - 1] and closes[i]:
                logrets.append(math.log(closes[i] / closes[i - 1]))
        close_v = realized_vol(closes, window=min(60, len(closes)))
        par = _vm.parkinson_vol(ohlcv["highs"], ohlcv["lows"], window=min(60, len(closes)))
        gk = _vm.garman_klass_vol(
            ohlcv["opens"], ohlcv["highs"], ohlcv["lows"], closes, window=min(60, len(closes))
        )
        ew = _vm.ewma_vol(logrets)
        garch = _vm.garch11_fit(logrets)
        rows = [
            ("close-to-close (60d)", close_v),
            ("parkinson (60d, day-only)", par),
            ("garman-klass (60d, day-only)", gk),
            ("ewma 0.94", ew),
            ("garch long-run", (garch or {}).get("long_run_vol")),
        ]
        lines = [f"## Volatility Estimators — {ticker}", ""]
        for name, v in rows:
            lines.append(f"- **{name}**: {f'{v:.2%}' if v is not None else 'n/a'}")
        lines.append(
            "\nNote: parkinson / garman-klass are day-only (no overnight gap); "
            "garch long-run is the conditional mean vol."
        )
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001 - degrades
        return f"volatility estimators unavailable for {ticker}: {exc}"


@tool
def get_normality(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Distributional hypothesis tests on a return series (OpenBB Q1).

    Reports D'Agostino-Pearson, Jarque-Bera, Shapiro-Wilk, Kolmogorov-Smirnov
    p-values + an overall 'normal' verdict. Use before any 'returns are
    Gaussian / not fat-tailed / tail-risk is normal' claim — it is the p-value,
    not a vibe. Degrades to 'unavailable' on insufficient data.
    """
    try:
        from tradingagents.strategies.statistical import normality
    except Exception as exc:  # noqa: BLE001
        return f"normality unavailable for {ticker}: {exc}"
    closes = _ohlcv(ticker).get("closes") or []
    if len(closes) < 20:
        return f"normality unavailable for {ticker}: need >=20 bars."
    rets = _daily_returns(closes)
    n = normality(rets)
    jb = n.get("jarque_bera") or {}
    sw = n.get("shapiro_wilk") or {}
    return (
        f"normality {ticker}: jarque_bera_p={(jb.get('p_value') or 0):.3f} "
        f"shapiro_p={(sw.get('p_value') or 0):.3f} normal={'yes' if n.get('normal') else 'no'} n={len(rets)}"
    )


@tool
def get_unit_root(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Stationarity (unit-root) tests on the close series (OpenBB Q1b).

    ADF (H0: unit root) + KPSS (H0: stationary) with p-value approximations.
    Use before any 'this is a trend-stationary / random-walk / mean-reverting
    / cointegratable' claim — gates whether momentum/vol estimators are valid.
    Degrades to 'unavailable' on insufficient data.
    """
    try:
        from tradingagents.strategies.statistical import unit_root
    except Exception as exc:  # noqa: BLE001
        return f"unit_root unavailable for {ticker}: {exc}"
    closes = _ohlcv(ticker).get("closes") or []
    if len(closes) < 30:
        return f"unit_root unavailable for {ticker}: need >=30 bars."
    u = unit_root(closes)
    adf = u.get("adf") or {}
    print_adf = f"{adf.get('statistic'):.2f} (p~{adf.get('p_value_approx'):.2f})" if adf else "n/a"
    st = "stationary" if u.get("stationary") else ("non-stationary" if u.get("stationary") is False else "unknown")
    return f"unit_root {ticker}: adf={print_adf} verdict={st} n={u.get('n')}"


@tool
def get_relative_rotation(
    ticker: Annotated[str, "anchor ticker"],
    benchmark: Annotated[str | None, "benchmark symbol, default SPY"] = None,
) -> str:
    """Relative-rotation quadrant vs a benchmark (OpenBB Q6).

    RS ratio x RS momentum -> leading / weakening / lagging / improving.
    Use before any 'sector/name is rotating into leadership / losing relative
    strength' claim. Degrades to 'unavailable' when either series is short.
    """
    try:
        from tradingagents.strategies.rotation import relative_rotation
    except Exception as exc:  # noqa: BLE001
        return f"relative_rotation unavailable for {ticker}: {exc}"
    bench = (benchmark or "SPY").upper()
    closes = _ohlcv(ticker).get("closes") or []
    bcloses = _ohlcv(bench).get("closes") or []
    if len(closes) < 300 or len(bcloses) < 300:
        return f"relative_rotation unavailable for {ticker}: need >=300 bars of {ticker} and {bench}."
    r = relative_rotation(closes, bcloses, long=252, short=21)
    if r.get("quadrant") is None:
        return f"relative_rotation unavailable for {ticker}: not enough aligned history."
    return (f"relative_rotation {ticker} vs {bench}: {r['quadrant']} "
            f"(rs_ratio={r['rs_ratio']:.2f} rs_momentum={r['rs_momentum']:.2f})")


@tool
def get_capm_risk(
    ticker: Annotated[str, "ticker symbol"],
    benchmark: Annotated[str | None, "benchmark symbol, default SPY"] = None,
) -> str:
    """CAPM risk decomposition: beta, systematic & idiosyncratic risk.
    Use before 'this is market-driven / stock-specific risk' claims.
    """
    try:
        from tradingagents.strategies.statistical import capm_decomposition
    except Exception as exc:  # noqa: BLE001
        return f"capm_risk unavailable for {ticker}: {exc}"
    bench = (benchmark or "SPY").upper()
    closes = _ohlcv(ticker).get("closes") or []
    bcloses = _ohlcv(bench).get("closes") or []
    if len(closes) < 60 or len(bcloses) < 60:
        return f"capm_risk unavailable for {ticker}: need >=60 bars."
    a = _daily_returns(closes)
    b = _daily_returns(bcloses)
    c = capm_decomposition(a, b)
    if c.get("beta") is None:
        return f"capm_risk unavailable for {ticker}: not computable."
    return (f"capm_risk {ticker} vs {bench}: beta={c['beta']:.2f} "
            f"systematic={c['systematic_risk']:.0%} idiosyncratic={c['idiosyncratic_risk']:.0%} n={c['n']}")


@tool
def get_clenow_momentum(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Clenow trend-quality momentum (persistence x noise, OpenBB Q7).

    exp(OLS 90d log-slope x 252) x R². Use before any 'strong/clean uptrend'
    claim — it penalizes a noisy rally. Degrades to 'unavailable' on short
    history.
    """
    try:
        from tradingagents.strategies.rotation import clenow_momentum
    except Exception as exc:  # noqa: BLE001
        return f"clenow momentum unavailable for {ticker}: {exc}"
    closes = _ohlcv(ticker).get("closes") or []
    if len(closes) < 120:
        return f"clenow momentum unavailable for {ticker}: need >=120 bars."
    s = clenow_momentum(closes, window=90)
    if s is None:
        return f"clenow momentum unavailable for {ticker}: not computable."
    return f"clenow_momentum {ticker}: {s:.3f}"


# ---------------------------------------------------------------------------
# OpenBB Phase-3 free-tier data surfaces (keyless/free; opt-in via config).
# Each gate is OFF by default: while disabled the tool returns a clear
# DISABLED sentinel so the analyst reports "unavailable" instead of inventing
# data. When enabled, data flows through the vendor chain.
# ---------------------------------------------------------------------------


def _feature_gate(flag_key: str, env_var: str) -> str | None:
    """Return a DISABLED sentinel when the feature flag is off, else None.

    Reads the thread-local config (which falls back to the process default),
    so a gate can be flipped per run via ``set_config`` or a
    ``TRADINGAGENTS_*`` env override. Config problems degrade to "off" — a
    broken gate must never let a tool pretend data exists.
    """
    try:
        from tradingagents.dataflows.config import get_config

        enabled = bool(get_config().get(flag_key, False))
    except Exception:  # noqa: BLE001 - config problems degrade to "off"
        enabled = False
    if enabled:
        return None
    return (
        f"DATA_DISABLED: the {flag_key.replace('_', ' ')} feature is off by "
        f"default. Set {env_var}=true (or the matching config key) to enable "
        f"it. Do not fabricate data."
    )


def _machine_chain_vrp(ticker: str) -> dict | None:
    """Model-free variance risk premium from a machine options chain (yfinance).

    Uses the chain's OTM mids across strikes with the cookbook/Cboe model-free
    variance formula (forward-discreteness term included), minus the annualized
    realized variance of the trailing 20-day log returns. ``r`` assumed 3.0%
    and ``q = 0`` (stated, not claimed precision). Returns ``{implied_var,
    realized_var, vrp, n, forward}`` or None when the chain is unavailable /
    unusable (honest no-fabrication).
    """
    import datetime as _dt
    import math as _math

    closes = _ohlcv(ticker).get("closes") or []
    if len(closes) < 30:
        return None
    spot = float(closes[-1])
    rets = []
    for i in range(1, len(closes)):
        if closes[i - 1] > 0:
            rets.append(_math.log(float(closes[i]) / float(closes[i - 1])))
    rv = 0.0
    if len(rets) >= 20:
        tail = rets[-20:]
        m = sum(tail) / len(tail)
        var = sum((x - m) ** 2 for x in tail) / (len(tail) - 1)
        rv = max(var * 252.0, 0.0)
    try:
        import yfinance as _yf

        tk = _yf.Ticker(str(ticker).upper())
        expiries = list(tk.options or [])
        if not expiries:
            return None
        expiry = expiries[min(2, len(expiries) - 1)]
        chain = tk.option_chain(expiry)
        calls = chain.calls
        puts = chain.puts
        if calls is None or puts is None or calls.empty or puts.empty:
            return None
        # Days to expiry from the contract symbol (or default 30d).
        import re as _re

        m = _re.search(r"(\d{6})", expiry)
        T = 30.0 / 365.0
        if m:
            try:
                exp_d = _dt.datetime.strptime(m.group(1), "%y%m%d")
                now = _dt.datetime.now()
                T = max((exp_d - now).days, 1) / 365.0
            except ValueError:
                T = 30.0 / 365.0
        fwd = spot  # q=0 approximation: F = S (no dividend model) - stated
        rows = []
        for _, row in calls.iterrows():
            try:
                k = float(row.get("strike"))
                bid = row.get("bid")
                ask = row.get("ask")
                last = row.get("lastPrice")
                mid = (float(bid) + float(ask)) / 2.0 if bid is not None and ask is not None else None
                if mid is None or mid != mid:
                    mid = float(last) if last is not None else None
                if k > fwd and mid is not None and mid == mid and mid > 0:
                    rows.append((k, float(mid)))
            except (TypeError, ValueError):
                continue
        for _, row in puts.iterrows():
            try:
                k = float(row.get("strike"))
                bid = row.get("bid")
                ask = row.get("ask")
                last = row.get("lastPrice")
                mid = (float(bid) + float(ask)) / 2.0 if bid is not None and ask is not None else None
                if mid is None or mid != mid:
                    mid = float(last) if last is not None else None
                if k < fwd and mid is not None and mid == mid and mid > 0:
                    rows.append((k, float(mid)))
            except (TypeError, ValueError):
                continue
        if len(rows) < 6:
            return None
        from tradingagents.strategies.options_math import model_free_implied_variance

        iv2 = model_free_implied_variance(
            [r[0] for r in rows], [r[1] for r in rows], fwd, T, 0.03
        )
        if iv2 is None:
            return None
        return {
            "implied_var": float(iv2),
            "realized_var": float(rv),
            "vrp": float(iv2) - float(rv),
            "n": len(rows),
            "forward": round(float(fwd), 2),
        }
    except Exception:  # noqa: BLE001 - no fabrication
        return None


@tool
def get_variance_premium(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Variance risk premium (cookbook recipe 5): implied variance from the
    OTM options strip minus trailing realized variance.

    Uses the model-free (Cboe/VIX-style) implied-variance formula on the
    machine options chain (yfinance), with the forward-discreteness term, and
    the annualized realized variance of the trailing 20-day log returns. A
    positive premium = the market prices more future vol than has realized -
    useful before any 'vol is rich / cheap into the event' claim. Degrades to
    the live IV snapshot (get_options_surface) when the machine chain is
    unavailable - never fabricates. r=3%, q=0 assumptions are stated.
    """
    v = _machine_chain_vrp(ticker)
    if v is not None:
        return (
            f"variance premium {ticker}: implied_var={v['implied_var']:.4f} "
            f"realized_var={v['realized_var']:.4f} vrp={v['vrp']:+.4f} "
            f"(model-free, n={v['n']} OTM strikes, fwd~={v['forward']}, "
            f"r=3% q=0; positive = rich IV)"
        )
    try:
        from tradingagents.agents.utils.analysis_tools import get_options_surface

        surf = get_options_surface.invoke({"ticker": ticker})
        head = (surf or "").splitlines()[:8]
        lines = [
            f"variance premium unavailable for {ticker}: machine options chain "
            "unavailable (no strikes/mids).",
            "",
            "Live IV surface (get_options_surface) - first rows:",
        ]
        lines.extend(head or ["(no rows)"])
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001
        return f"variance premium unavailable for {ticker}: {exc}"


@tool
def get_options_surface(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Free delayed options-chain surface for a ticker from CBOE (no key):
    strike, days-to-expiry, IV, and the greeks exactly as CBOE delivers them
    (missing values render 'n/a' — never estimated). Use before any
    'volatility surface / option greeks / skew' claim. Opt-in (default off).
    """
    gate = _feature_gate("enable_options_surface", "TRADINGAGENTS_ENABLE_OPTIONS_SURFACE")
    if gate:
        return gate
    return route_to_vendor("get_options_surface", ticker)


@tool
def get_sofr_curve(
    current_date: Annotated[str | None, "as-of date, YYYY-MM-DD; default today"] = None,
) -> str:
    """Risk-free overnight curve: SOFR history from the NY Fed's free feed
    (no key). Rows of {date, rate} plus distribution percentiles. Use before
    any 'risk-free rate / overnight funding' claim. Opt-in (default off).
    """
    gate = _feature_gate("enable_risk_free_curve", "TRADINGAGENTS_ENABLE_RISK_FREE_CURVE")
    if gate:
        return gate
    return route_to_vendor("get_sofr_curve", current_date)


@tool
def get_treasury_curve(
    current_date: Annotated[str | None, "as-of date, YYYY-MM-DD; default today"] = None,
) -> str:
    """US Treasury par yield curve (1M-30Y) from home.treasury.gov's free CSV
    (no key). Rows of {maturity, rate}. Use before any 'yield curve / term
    premium / carry' claim. Opt-in (default off).
    """
    gate = _feature_gate("enable_risk_free_curve", "TRADINGAGENTS_ENABLE_RISK_FREE_CURVE")
    if gate:
        return gate
    return route_to_vendor("get_treasury_curve", current_date)


@tool
def screen_equities(
    market: Annotated[str, "market/universe to screen, default 'us'"] = "us",
    limit: Annotated[int, "max rows, default 50"] = 50,
    filters: Annotated[
        str | None, "optional Yahoo predefined screener query (e.g. 'day_gainers')"
    ] = None,
) -> str:
    """Universe screen of US equities via yfinance's free screener: rows of
    {symbol, price, pe, eps, beta, mkt_cap, change_pct, name}. Use before any
    'universe / screen / valuation basket' claim. Opt-in (default off).
    """
    gate = _feature_gate("enable_screener", "TRADINGAGENTS_ENABLE_SCREENER")
    if gate:
        return gate
    return route_to_vendor("screen_equities", market, limit, filters)


@tool
def get_market_movers(
    kind: Annotated[str, "'gainers', 'losers', or 'active'"] = "gainers",
) -> str:
    """Top U.S. market movers via yfinance's free discovery feed: ranked rows
    of {symbol, price, change_pct, volume, name}. Use before any 'top
    gainers/losers / most active' claim. Opt-in (default off).
    """
    gate = _feature_gate("enable_market_movers", "TRADINGAGENTS_ENABLE_MARKET_MOVERS")
    if gate:
        return gate
    return route_to_vendor("get_market_movers", kind)




# ---------------------------------------------------------------------------
# Risk-decision tools (Phase-2 audit wiring): untooled deterministic
# calculators exposed to the analyst / risk-debator / trader loops. All wrap
# existing pure strategies functions; every number is computed or explicit
# "unavailable" - never fabricated, advisory-only.
# ---------------------------------------------------------------------------


@tool
def get_fixed_risk_size(
    equity: Annotated[float, "account equity in the position currency"],
    risk_frac: Annotated[float, "risk budget as a fraction of equity, e.g. 0.01"],
    entry: Annotated[float, "planned entry price"],
    stop_loss: Annotated[float, "hard stop price"],
    commission_rate: Annotated[float, "one-way commission rate, default 0"] = 0.0,
    units: Annotated[int, "tranche count to split into, default 1"] = 1,
    hard_limit: Annotated[float | None, "max units bound, if any"] = None,
) -> str:
    """Commission-aware fixed-risk position size (NautilusTrader R1).

    ``riskable_money = equity * risk_frac / (1 + commission)`` then
    ``size = riskable_money / |entry - stop|``, optionally capped and split
    across ``units`` tranches. The exact sizer the risk governor's budget
    implies - cite its share count before proposing a position size.

    Args:
        equity: account equity in the position currency.
        risk_frac: risk budget as a fraction of equity (0..1).
        entry: planned entry price.
        stop_loss: hard stop price.
        commission_rate: one-way commission rate (0 for none).
        units: tranche count to split the total across.
        hard_limit: optional max-units bound.

    Returns:
        total units (and per-tranche) sizing line, or an explicit
        "unavailable" when the risk distance / equity is unusable.
    """
    try:
        from tradingagents.strategies.risk_sizing import (
            risk_money,
            riskable_money,
        )
    except Exception as exc:
        return f"fixed risk size unavailable: {exc}"
    try:
        e = float(equity)
        rf = float(risk_frac)
        ent = float(entry)
        st = float(stop_loss)
    except (TypeError, ValueError):
        return "fixed risk size unavailable: non-numeric inputs"
    if e <= 0 or not (0.0 <= rf <= 1.0) or ent <= 0 or st <= 0:
        return "fixed risk size unavailable: equity/risk/price must be positive"
    budget = riskable_money(e, rf, commission_rate)
    qty = risk_money(ent, st, e, rf, commission_rate=commission_rate, hard_limit=hard_limit)
    n = max(1, int(units))
    per = (qty / n) if qty and n else 0.0
    return (
        f"fixed risk size: total={qty:.0f} units ({n} tranche(s) x {per:.0f}) "
        f"risk_budget=${budget:,.0f} risk_per_share={abs(ent - st):.2f} "
        f"entry={ent:.2f} stop={st:.2f} commission={float(commission_rate):.4%}"
    )


@tool
def get_exit_overrides(
    targets: Annotated[
        dict, "current target weight per symbol, e.g. {'AAPL': 0.1}"
    ],
    state_by_name: Annotated[
        dict,
        "per-symbol state {'entry','peak','current'}, e.g. {'AAPL': {'entry': 100, 'peak': 110, 'current': 103}}",
    ],
    max_drawdown_pct: Annotated[float, "drawdown-from-peak override trigger, default 0.05"] = 0.05,
    trail_pct: Annotated[float, "trailing-stop override trigger, default 0.05"] = 0.05,
) -> str:
    """Two-pass position-exit overrides (Lean L1, advisory).

    Evaluates each held name's drawdown-from-peak and peak-trail against the
    given thresholds and reports which targets would be liquidated (weight 0)
    by the risk-management pass. Pure read over persisted state - it never
    touches a position.

    Args:
        targets: current desired weight per symbol.
        state_by_name: per-symbol {'entry','peak','current'} state (from the
            paper ledger).
        max_drawdown_pct: drawdown-from-peak liquidation trigger.
        trail_pct: trailing-stop liquidation trigger.

    Returns:
        override/liquidate lines, or an explicit "unavailable" when no
        peak/current state exists for a name.
    """
    try:
        from tradingagents.strategies.risk_manager import (
            manage_risk,
            trailing_stop_targets,
        )
    except Exception as exc:
        return f"exit overrides unavailable: {exc}"
    try:
        targets = dict(targets or {})
        state_by_name = dict(state_by_name or {})
        dd = manage_risk(targets, state_by_name, max_drawdown_pct=float(max_drawdown_pct))
        tr = trailing_stop_targets(targets, state_by_name, trail_pct=float(trail_pct))
        lines = []
        if isinstance(dd, str):
            lines.append(f"drawdown overrides: {dd}")
        else:
            o = dd.get("overrides", {})
            lines.append(
                "drawdown overrides: " + ("; ".join(f"{k}=0" for k in o) if o else "none")
            )
        if isinstance(tr, str):
            lines.append(f"trailing overrides: {tr}")
        else:
            o = tr.get("overrides", {})
            lines.append(
                "trailing overrides: " + ("; ".join(f"{k}=0" for k in o) if o else "none")
            )
        return chr(10).join(lines)
    except Exception as exc:
        return f"exit overrides unavailable: {exc}"


@tool
def get_pre_trade_read(
    symbol: Annotated[str, "symbol to check"],
    notional: Annotated[float, "order notional (price * quantity)"],
    max_notional: Annotated[float | None, "per-symbol notional cap, if any"] = None,
    max_rate: Annotated[int | None, "max submissions per window, if any"] = None,
    window_secs: Annotated[float, "rolling window for the rate limit, default 60"] = 60.0,
) -> str:
    """Pre-trade submission gate (NautilusTrader R2, advisory).

    Reports whether an order passes the per-symbol notional cap and a
    rolling-window submission throttle. Pure read over the supplied inputs -
    it never submits or records anything.

    Args:
        symbol: the order symbol.
        notional: order notional (price * quantity).
        max_notional: per-symbol notional cap (optional).
        max_rate: max submissions allowed per rolling window (optional).
        window_secs: the rolling window in seconds (default 60).

    Returns:
        PASS/REJECT line naming which gate blocked, or "unavailable" on a
        non-numeric notional.
    """
    try:
        from tradingagents.strategies.risk_checks import pre_trade_check
    except Exception as exc:
        return f"pre-trade read unavailable: {exc}"
    try:
        notional_v = float(notional)
    except (TypeError, ValueError):
        return "pre-trade read unavailable: non-numeric notional"
    gates = []
    if max_notional is not None and notional_v > float(max_notional):
        gates.append(f"notional {notional_v:,.0f} > cap {float(max_notional):,.0f}")
    limiter = None
    if max_rate is not None:
        try:
            from tradingagents.strategies.risk_checks import RateLimiter

            limiter = RateLimiter(max_count=int(max_rate), window_secs=float(window_secs))
            if not limiter.allow(0.0):
                gates.append(f"rate limit {int(max_rate)}/window")
        except Exception as exc:
            gates.append(f"rate limiter unavailable ({exc})")
    ok = pre_trade_check(
        str(symbol),
        notional_v,
        {},
        max_notional=max_notional,
        limiter=limiter,
    )
    if ok is False and not gates:
        gates.append("pre-trade gate blocked")
    verdict = "REJECT - " + "; ".join(gates) if gates else "PASS"
    cap_txt = f" cap={float(max_notional):,.0f}" if max_notional is not None else ""
    rate_txt = f" rate={int(max_rate)}/window" if max_rate is not None else ""
    return f"pre-trade {symbol}: {verdict}; notional={notional_v:,.0f}{cap_txt}{rate_txt}"


@tool
def get_ledger_risk_state(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Daily-loss / HWM / win-rate risk state from the paper + memory ledgers.

    Supplies the governor inputs the analyst LLMs could not see before:
    realized-win-rate drift (from the memory log) and the paper-book reviewer
    track record (from the pre-market ledger). Every number is measured or
    explicit "unavailable".

    Args:
        ticker: ticker symbol.

    Returns:
        ledger risk-state lines (win rate, resolved count, paper record).
    """
    try:
        from tradingagents.dataflows.config import get_config
    except Exception as exc:
        return f"ledger risk state unavailable: {exc}"
    cfg = get_config()
    lines = []
    try:
        from tradingagents.agents.utils.memory import TradingMemoryLog

        mlog = TradingMemoryLog(cfg.get("memory_log_path") or "")
        entries = mlog.load_entries()
        resolved = [e for e in entries if not e.get("pending") and e.get("raw") is not None]
        if len(resolved) >= 5:
            wins = sum(1 for e in resolved if float(e["raw"]) > 0)
            recent = resolved[-8:]
            rec_wins = sum(1 for e in recent if float(e["raw"]) > 0)
            lines.append(
                f"memory ledger: resolved={len(resolved)} win_rate={wins / len(resolved):.0%} "
                f"recent_win_rate={rec_wins / len(recent):.0%}"
            )
        else:
            lines.append(f"memory ledger: resolved={len(resolved)} (need >= 5 for win-rate)")
    except Exception as exc:
        lines.append(f"memory ledger: unavailable ({exc})")
    try:
        import os

        from tradingagents.strategies.pre_market import ledger_track_record

        lp = cfg.get("pre_market_ledger_path") or os.path.join(
            cfg.get("data_cache_dir") or "", "pre_market_ledger.jsonl"
        )
        rec = ledger_track_record(str(lp), direction=None)
        if rec.get("resolved"):
            lines.append(
                f"paper reviewer: resolved={rec['resolved']} win_rate={rec['win_rate']:.0%} "
                f"avg_realized={rec['avg_realized']:+.2%}"
            )
        else:
            lines.append(f"paper reviewer: no resolved rows ({rec.get('count', 0)} total)")
    except Exception as exc:
        lines.append(f"paper reviewer: unavailable ({exc})")
    return chr(10).join(lines) if lines else "ledger risk state: unavailable"


@tool
def get_trade_plan(
    ticker: Annotated[str, "ticker symbol"],
    price: Annotated[float | None, "current price if known"] = None,
) -> str:
    """The written pre-entry trade plan card (B2).

    Emits the plan card (setup rows, tranche levels, composite stop, tier
    targets, BE rule, trailing method, invalidation, adherence checklist) that
    the Trader / PM / risk debators are supposed to argue over - now callable
    instead of only an injected context string.

    Args:
        ticker: ticker symbol.
        price: optional current price anchor.

    Returns:
        the markdown plan card.
    """
    try:
        from tradingagents.dataflows.config import get_config
        from tradingagents.strategies.trade_plan import build_trade_plan
    except Exception as exc:
        return f"trade plan unavailable: {exc}"
    try:
        cfg = get_config()
        if price is None:
            closes = _ohlcv(ticker).get("closes") or []
            price = closes[-1] if closes else None
        return build_trade_plan(ticker=ticker, price=price, config=cfg)
    except Exception as exc:
        return f"trade plan unavailable: {exc}"


@tool
def get_fixed_income_risk(
    ticker: Annotated[str, "ticker symbol"],
    years: Annotated[float | None, "call/redemption horizon in years; omit for a perpetual (YTM=n/a)"] = None,
) -> str:
    """Preferred / fixed-income risk rows (quants.md §Fixed Income).

    Indicated yield, and - only when a call/redemption horizon is inferable -
    yield-to-maturity, Macaulay/modified duration, DV01 and convexity. A
    perpetual with no horizon renders YTM/duration n/a (never a fake YTM).

    Args:
        ticker: ticker symbol.
        years: optional call/redemption horizon in years.

    Returns:
        dividend-yield row + YTM/duration/DV01/convexity lines (or n/a).
    """
    try:
        from tradingagents.strategies.fixed_income import (
            bond_convexity,
            dv01,
            indicated_yield,
            macaulay_duration,
            modified_duration,
            preferred_ytm,
        )
    except Exception as exc:
        return f"fixed income risk unavailable: {exc}"
    try:
        import re as _re

        from tradingagents.dataflows.interface import route_to_vendor

        fund = route_to_vendor("get_fundamentals", ticker, "") or ""
        div = None
        price = None
        m = _re.search(r"dividend[_ ]?rate[^:]*:[^\d]*([0-9.]+)", fund, _re.I)
        if m:
            div = float(m.group(1))
        m2 = _re.search(r"(?:current|last)[_ ]?price[^:]*:[^\d]*([0-9.]+)", fund, _re.I)
        if m2:
            price = float(m2.group(1))
        if div is None or price is None or price <= 0:
            return f"fixed income risk {ticker}: dividend/price unavailable (n/a)"
        iy = indicated_yield(div, price)
        lines = [f"fixed income risk {ticker}: indicated_yield={iy:.2%} price={price:.2f}"]
        if years is not None and float(years) > 0:
            ytm = preferred_ytm(div, price, 100.0, float(years))
            cashflows = [{"t": float(years), "amount": price * float(years)}]
            mac = macaulay_duration(cashflows, iy / 100.0)
            mod = modified_duration(mac, iy / 100.0) if mac else None
            d01 = dv01(mod, price) if mod else None
            cv = bond_convexity(cashflows, iy / 100.0)
            lines.append(f"  ytm={ytm:.2%}" if ytm is not None else "  ytm=n/a")
            lines.append(f"  macaulay={mac:.2f}y" if mac is not None else "  macaulay=n/a")
            lines.append(f"  modified={mod:.2f}" if mod is not None else "  modified=n/a")
            lines.append(f"  dv01={d01:.4f}" if d01 is not None else "  dv01=n/a")
            lines.append(f"  convexity={cv:.2f}" if cv is not None else "  convexity=n/a")
        else:
            lines.append("  ytm=n/a (perpetual; pass a call/redemption horizon to compute)")
        return chr(10).join(lines)
    except Exception as exc:
        return f"fixed income risk unavailable: {exc}"


@tool
def get_pair_risk(
    x: Annotated[list, "first series (e.g. closes of the anchor)"],
    y: Annotated[list, "second series (e.g. closes of the pair)"],
    maxlag: Annotated[int, "max lag for the Granger test, default 3"] = 3,
) -> str:
    """Pair risk: cointegration + Granger causality (OpenBB Q5).

    Engle-Granger cointegration (ADF on the residual) and lag-wise Granger
    causality for the pair - the mean-reversion/lead-lag risk read the single
    name tools cannot give.

    Args:
        x: first aligned series.
        y: second aligned series.
        maxlag: max Granger lag.

    Returns:
        cointegration + Granger lines, or "unavailable" below min observations.
    """
    try:
        from tradingagents.strategies.statistical import (
            cointegration_pair,
            granger_causality,
        )
    except Exception as exc:
        return f"pair risk unavailable: {exc}"
    try:
        xs = [float(v) for v in (x or [])]
        ys = [float(v) for v in (y or [])]
    except (TypeError, ValueError):
        return "pair risk unavailable: non-numeric series"
    if len(xs) < 20 or len(ys) < 20:
        return f"pair risk unavailable: need >= 20 aligned obs (got {min(len(xs), len(ys))})"
    c = cointegration_pair(xs, ys, maxlag=max(1, int(maxlag)))
    g = granger_causality(xs, ys, maxlag=max(1, int(maxlag)))
    lags = [(r.get("lag"), r.get("p_value")) for r in g.get("lags", [])]
    reminder = "; ".join(f"lag{lag_row[0]}={lag_row[1]}" for lag_row in lags) if lags else "n/a"
    return (
        f"pair risk: cointegrated={c.get('cointegrated')} n={c.get('n')} "
        f"beta={c.get('beta')} residual_adf={c.get('residual_adf_stat')}"
        f" | granger(x->y): {g.get('x_causes_y')} [{reminder}]"
    )


@tool
def get_pair_trade_signal(
    x: Annotated[list, "first series (e.g. closes of the anchor)"],
    y: Annotated[list, "second series (e.g. closes of the pair)"],
    entry: Annotated[float, "spread-z entry band, default 2.0"] = 2.0,
    exit_thresh: Annotated[float, "spread-z exit band, default 0.5"] = 0.5,
    stop: Annotated[float, "spread-z risk stop, default 3.0"] = 3.0,
) -> str:
    """Pairs-trading trade signal (cookbook recipe 3): spread z-score bands.

    Entry at |z| >= entry (short when +, long when -), exit when |z| <=
    exit_thresh, risk stop at |z| >= stop, with the cointegration + half-life
    cross-check. Advisory signal - never an order recommendation.

    Args:
        x: first aligned price series.
        y: second aligned price series.
        entry: z entry threshold (default 2.0).
        exit_thresh: z exit band (default 0.5).
        stop: z stop band (default 3.0).

    Returns:
        signal + spread/z/beta/half-life lines, or "unavailable" below the
        min-observation floor.
    """
    try:
        from tradingagents.strategies.statistical import pair_signal
    except Exception as exc:
        return f"pair trade signal unavailable: {exc}"
    try:
        xs = [float(v) for v in (x or [])]
        ys = [float(v) for v in (y or [])]
    except (TypeError, ValueError):
        return "pair trade signal unavailable: non-numeric series"
    if len(xs) < 70 or len(ys) < 70:
        return f"pair trade signal unavailable: need >= 70 aligned obs (got {min(len(xs), len(ys))})"
    s = pair_signal(xs, ys, entry=entry, exit_thresh=exit_thresh, stop=stop)
    if s.get("z") is None:
        return "pair trade signal unavailable: no measurable spread"
    return (
        f"pair trade signal: {s.get('signal')} z={s.get('z')} "
        f"spread={s.get('spread')} beta={s.get('beta')} "
        f"half_life={s.get('half_life')} cointegrated={s.get('cointegrated')} n={s.get('n')}"
    )


@tool
def get_event_pnl_response(
    spot: Annotated[float, "current underlying price"],
    delta: Annotated[float, "option delta (e.g. from get_options_surface)"],
    gamma: Annotated[float, "option gamma"],
    vega: Annotated[float, "option vega (per 1.0 vol move)"],
    theta: Annotated[float, "option theta (price units per year)"],
    dS_pct: Annotated[float, "expected underlying move as decimal (e.g. 0.02 = 2%)"],
    dSigma: Annotated[float, "expected vol change as absolute (e.g. 0.05 = +5 vol pts)"] = 0.0,
) -> str:
    """Event-window P&L response (cookbook recipe 5): delta-gamma-vega-theta.

    ``dPi ~= Delta*dS + 1/2*Gamma*dS^2 + Vega*dSigma + Theta*dt`` (dt = 1 day)
    - the scenario P&L a catalyst/earnings move implies for one option unit.
    Use the surface's greeks plus the expected move (get_expected_move) before
    any 'the move would be worth X' claim. Purely advisory; not a trade size.
    """
    try:
        from tradingagents.strategies.options_math import greek_pnl_response
    except Exception as exc:
        return f"event pnl response unavailable: {exc}"
    try:
        p = greek_pnl_response(
            None if delta is None else float(delta),
            None if gamma is None else float(gamma),
            None if vega is None else float(vega),
            None if theta is None else float(theta),
            float(spot), float(dS_pct), float(dSigma),
        )
    except (TypeError, ValueError):
        return "event pnl response unavailable: invalid inputs"
    return (
        f"event pnl response: dS={dS_pct:.1%} dSigma={dSigma:+.2f} "
        f"delta_pnl={p['delta_pnl']} gamma_pnl={p['gamma_pnl']} "
        f"vega_pnl={p['vega_pnl']} theta_pnl={p['theta_pnl']} "
        f"total_pnl={p['total_pnl']} (per option unit, 1-day)"
    )


@tool
def get_ts_momentum_weights(
    closes_by_name: Annotated[
        dict, "dict of name -> daily close series, e.g. {'SPY': [...], 'TLT': [...]}"
    ],
    horizon: Annotated[int, "momentum lookback in trading days, default 252"] = 252,
    target_vol: Annotated[float, "portfolio target annualized vol, default 0.10"] = 0.10,
    max_leverage: Annotated[float, "max gross leverage, default 2.0"] = 2.0,
) -> str:
    """Time-series momentum portfolio weights (cookbook recipe 1, MOP-style).

    Each name gets ``sign(trailing log return) / EWMA vol``, normalized to the
    portfolio ``target_vol`` and hard-capped at ``max_leverage`` gross. Gives
    the vol-scaled trend book before any 'this asset is trending, size more'
    claim - a deterministic, cost-aware diversification input.

    Args:
        closes_by_name: name -> aligned daily closes.
        horizon: momentum lookback (default 252).
        target_vol: portfolio annualized vol target (default 0.10).
        max_leverage: gross leverage cap (default 2.0).

    Returns:
        per-name weights + meta (target_vol / gross / n_names), or
        "unavailable" when no name has a measurable signal.
    """
    try:
        from tradingagents.strategies.momentum import ts_momentum_weights
    except Exception as exc:
        return f"ts momentum weights unavailable: {exc}"
    try:
        cleaned = {
            k: [float(v) for v in (s or [])]
            for k, s in (closes_by_name or {}).items()
        }
    except (TypeError, ValueError):
        return "ts momentum weights unavailable: non-numeric series"
    cleaned = {k: v for k, v in cleaned.items() if len(v) >= horizon + 2}
    if not cleaned:
        return f"ts momentum weights unavailable: need >= {horizon + 2} closes per name"
    w = ts_momentum_weights(cleaned, horizon=horizon, target_vol=target_vol,
                            max_leverage=max_leverage)
    if w is None:
        return "ts momentum weights unavailable: no measurable signal"
    meta = w.pop("_meta", {})
    lines = [f"ts momentum weights (target_vol={meta.get('target_vol')} "
             f"gross={meta.get('gross')} n_names={meta.get('n_names')}):"]
    for name, weight in w.items():
        lines.append(f"  {name}={weight:+.4f}")
    return "\n".join(lines)


@tool
def get_book_depth_read(
    bid: Annotated[float, "bid price"],
    ask: Annotated[float, "ask price"],
    bid_size: Annotated[float, "bid-side depth (shares)"],
    ask_size: Annotated[float, "ask-side depth (shares)"],
) -> str:
    """Microprice + order-book imbalance (cookbook recipe 2 execution).

    Microprice = (bid*ask_size + ask*bid_size) / (bid_size + ask_size) - the
    size-weighted fair value that shifts toward the thinner side; OBI =
    (bid_size - ask_size) / (bid_size + ask_size). Short-horizon price-pressure
    read for the pre-market / thin-book path. Honest 'unavailable' without
    both sizes (never fabricates a depth).
    """
    try:
        from tradingagents.strategies.market_session import book_depth_read
    except Exception as exc:
        return f"book depth read unavailable: {exc}"
    try:
        r = book_depth_read(bid, ask, bid_size, ask_size)
    except (TypeError, ValueError):
        return "book depth read unavailable: invalid inputs"
    if r.get("microprice") is None:
        return "book depth read unavailable: missing bid/ask sizes"
    return (
        f"book depth read: microprice={r['microprice']} obi={r['obi']} "
        f"verdict={r['verdict']}"
    )


@tool
def get_vif_read(
    columns: Annotated[dict, "name -> aligned series dict, e.g. {'mom': [...], 'rsi': [...]}"],
) -> str:
    """Multicollinearity check (OpenBB Q2): VIF per factor column.

    Regresses each column on the others; VIF > 5 flags a collinear factor the
    LLM should not stack with its peers. None for < 3 columns or a singular
    fit.

    Args:
        columns: dict of factor name -> aligned series.

    Returns:
        per-column VIF + high flags, or "unavailable" below 3 columns.
    """
    try:
        from tradingagents.strategies.statistical import variance_inflation_factor
    except Exception as exc:
        return f"vif read unavailable: {exc}"
    try:
        cols = {k: [float(v) for v in (s or [])] for k, s in (columns or {}).items()}
    except (TypeError, ValueError):
        return "vif read unavailable: non-numeric columns"
    cols = {k: v for k, v in cols.items() if len(v) >= 10}
    if len(cols) < 3:
        return f"vif read unavailable: need >= 3 columns with >= 10 obs (got {len(cols)})"
    v = variance_inflation_factor(cols)
    rows = v.get("columns", {}) if isinstance(v, dict) else {}
    if not rows:
        return "vif read unavailable: singular fit / no result"
    lines = []
    for name, info in rows.items():
        if isinstance(info, dict):
            vif = info.get("vif")
            high = bool(info.get("high", False))
        else:
            vif = info
            high = bool(vif is not None and vif > 5)
        if vif is not None:
            lines.append(f"vif {name}: {vif:.1f} {'HIGH>5' if high else 'ok'}")
        else:
            lines.append(f"vif {name}: n/a")
    return chr(10).join(lines) if lines else "vif read unavailable"


@tool
def get_vol_cones(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Realized-volatility cones: multi-horizon percentiles (OpenBB Q8).

    Current realized vol vs its own p25/p50/p75 per horizon (5/10/21/63/126d,
    annualized) - the "is today's vol cheap or expensive" read.

    Args:
        ticker: ticker symbol.

    Returns:
        per-window current/p25/p50/p75 vol lines.
    """
    try:
        from tradingagents.strategies.rotation import vol_cones
    except Exception as exc:
        return f"vol cones unavailable: {exc}"
    try:
        closes = _ohlcv(ticker).get("closes") or []
        if len(closes) < 140:
            return f"vol cones unavailable for {ticker}: need >= 140 bars ({len(closes)})"
        cones = vol_cones(closes)
        lines = [f"vol cones {ticker} (annualized):"]
        for win, band in sorted((cones or {}).items(), key=lambda kv: int(kv[0])):
            lines.append(
                f"  {win}d: current={band.get('current'):.1%} "
                f"p25={band.get('p25'):.1%} p50={band.get('p50'):.1%} p75={band.get('p75'):.1%}"
            )
        return chr(10).join(lines)
    except Exception as exc:
        return f"vol cones unavailable for {ticker}: {exc}"


@tool
def get_trade_excursions(
    trades: Annotated[list, "trade rows: {'entry_price','exit_price','low','high'}"],
) -> str:
    """Exit-quality: MAE / MFE / profit-factor / max intra-trade drawdown (Lean L5).

    Rows without an entry/exit/OHLC path contribute only the counts they can
    support - no number is fabricated.

    Args:
        trades: list of trade dicts with entry_price/exit_price and ideally
            low/high (the holding OHLC path).

    Returns:
        MAE/MFE/profit-factor/max-intra-drawdown lines.
    """
    try:
        from tradingagents.strategies.journal import trade_excursions
    except Exception as exc:
        return f"trade excursions unavailable: {exc}"
    try:
        rows = [dict(r) for r in (trades or [])]
    except (TypeError, ValueError):
        return "trade excursions unavailable: trades must be a list of dicts"
    if not rows:
        return "trade excursions unavailable: no trades"
    s = trade_excursions(rows)
    return (
        f"trade excursions: n={s.get('n')} "
        f"avg_mae={s.get('avg_mae')} largest_mae={s.get('largest_mae')} "
        f"avg_mfe={s.get('avg_mfe')} largest_mfe={s.get('largest_mfe')} "
        f"profit_factor={s.get('profit_factor')} "
        f"max_intra_trade_drawdown={s.get('max_intra_trade_drawdown')}"
    )


@tool
def get_alpha_scoring(
    direction: Annotated[str, "'up'/'long' or 'down'/'short'"],
    predicted_magnitude: Annotated[float | None, "predicted return magnitude over the horizon"] = None,
    period_days: Annotated[int | None, "horizon in days"] = None,
    actual_return: Annotated[float | None, "realized return over the horizon"] = None,
    confidence: Annotated[float | None, "decision confidence, if any"] = None,
) -> str:
    """Magnitude + horizon-scored alpha (Lean L7).

    Scores one insight against its realized outcome: directional hit, magnitude
    error ("I said +12%, realized +2%"), and a magnitude-scaled score. Pure
    read; no ledger writes.

    Args:
        direction: 'up'/'long' or 'down'/'short'.
        predicted_magnitude: predicted return magnitude over the horizon.
        period_days: horizon in days.
        actual_return: realized return over the horizon.
        confidence: optional decision confidence.

    Returns:
        hit / magnitude-error / score / horizon-ok line.
    """
    try:
        from tradingagents.strategies.alpha_eval import alpha_score
    except Exception as exc:
        return f"alpha scoring unavailable: {exc}"
    if actual_return is None:
        return "alpha scoring unavailable: actual_return required"
    s = alpha_score(
        direction,
        predicted_magnitude if predicted_magnitude is not None else None,
        period_days,
        float(actual_return),
        confidence=confidence,
    )
    return (
        f"alpha scoring: hit={s.get('hit')} magnitude_err={s.get('magnitude_err')} "
        f"score={s.get('score')} horizon_ok={s.get('horizon_ok')} n=1"
    )


@tool
def get_regime_gate_read(
    ticker: Annotated[str, "ticker symbol"],
    catalyst_window: Annotated[bool, "treat an open catalyst window as blocking, default False"] = False,
) -> str:
    """Mean-reversion regime gate (A1): the knife-guard verdict.

    Mirrors the context line the decision agents see: vol_pct, fast-downtrend
    and the pass/block verdict for mean-reversion entries. Callable so the
    risk debators can re-derive it with their own catalyst-window choice.

    Args:
        ticker: ticker symbol.
        catalyst_window: when True, an open catalyst window blocks the entry.

    Returns:
        verdict + vol/downtrend reasons line.
    """
    try:
        from tradingagents.dataflows.config import get_config
        from tradingagents.strategies.regime import regime_gate_read
    except Exception as exc:
        return f"regime gate read unavailable: {exc}"
    try:
        closes = _ohlcv(ticker).get("closes") or []
        if len(closes) < 60:
            return f"regime gate read unavailable for {ticker}: need >= 60 bars ({len(closes)})"
        rg = regime_gate_read(closes, cfg=get_config(), catalyst_window=bool(catalyst_window)) or {}
        return (
            f"regime gate {ticker}: verdict={rg.get('verdict')} pass={rg.get('pass')} "
            f"vol_pct={rg.get('vol_pct')} fast_downtrend={rg.get('fast_downtrend')} "
            f"reasons={'; '.join(rg.get('reasons') or [])}"
        )
    except Exception as exc:
        return f"regime gate read unavailable for {ticker}: {exc}"

@tool
def get_factor_profile(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Compact Alpha158-style factor profile for ONE ticker (Qlib pillar 1, advisory).

    Returns the latest computed values of a 16-factor subset
    (momentum/reversal/volatility/value) off the run-level OHLCV cache, with
    the data as-of date. Gated by ``enable_factor_profile`` (default off):
    when off, returns an explicit unavailable (never a guess). The values are
    computed, citable numbers for the LLM - never gates.
    """
    try:
        from tradingagents.dataflows.config import get_config
        from tradingagents.strategies.factor_expressions import cached_expression
    except Exception as exc:  # noqa: BLE001
        return f"factor profile unavailable: {exc}"
    if not get_config().get("enable_factor_profile"):
        return f"factor profile unavailable for {ticker}: enable_factor_profile is off"
    try:
        ohlcv = _ohlcv(ticker)
        closes = ohlcv.get("closes") or []
        if len(closes) < 25:
            return (f"factor profile unavailable for {ticker}: "
                    f"{len(closes)} closes < 25 (min-observation)")
        dates = ohlcv.get("dates") or []
        as_of = dates[-1] if dates else None
        if get_config().get("enable_pit_registry"):
            from tradingagents.dataflows import pit_registry
            pit_registry.store_snapshot(ticker, as_of or "unknown", {"kind": "ohlcv_profile", "closes": closes[-5:]})
            moments = pit_registry.get_moments(ticker)
            if moments is None:
                from tradingagents.strategies.factor_expressions import fit_zscore
                m = fit_zscore(closes[-60:])  # train segment only
                if m:
                    pit_registry.put_moments(ticker, as_of or "unknown", {"mean": m[0], "std": m[1]})
        alpha = cached_expression("alpha158", ticker, 320, as_of, ohlcv)
        lines = [f"## Factor profile {ticker} (as-of {as_of})", ""]
        labels = {
            "mom_5": "5d momentum", "mom_20": "20d momentum", "mom_60": "60d momentum",
            "rsi_14": "RSI-14", "bias_20": "20d bias", "zscore_20": "20d z-score",
            "return_std_10": "10d return vol", "high_low_range_20": "20d range/close",
            "avg_vol_20": "20d avg volume", "corr_ret_vol_20": "close-vol corr",
        }
        shown = 0
        for key, label in labels.items():
            series = (alpha or {}).get(key)
            if series and series[-1] is not None:
                lines.append(f"- {label}: {float(series[-1]):.4f}")
                shown += 1
        if not shown:
            return f"factor profile unavailable for {ticker}: no factor with a latest value"
        lines.append("")
        lines.append("computed, advisory - never a gate")
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001
        return f"factor profile unavailable for {ticker}: {exc}"


@tool
def get_topk_drop_plan(
    scores: Annotated[dict, "name -> score"],
    topk: Annotated[int, "target book size (names to hold)"] = 10,
    n_drop: Annotated[int, "worst-held names to sell each rebalance"] = 1,
    held: Annotated[list | None, "current holdings (names); empty = fresh book"] = None,
) -> str:
    """Qlib Topk-Drop rebalance plan (pillar 3, advisory).

    Holds the top-``topk`` by score, sells the worst-``n_drop`` of the current
    holdings, buys the best unheld names, equal-weights. Reports the turnover
    = 2 * drops / book-size. Never a gate - the PM decides.
    """
    try:
        from tradingagents.strategies.portfolio_strategy import topk_drop_weights
    except Exception as exc:  # noqa: BLE001
        return f"topk-drop plan unavailable: {exc}"
    try:
        if not scores:
            return "topk-drop plan unavailable: no scores"
        out = topk_drop_weights(
            scores,
            held=[str(h).upper() for h in (held or [])],
            topk=int(topk),
            n_drop=int(n_drop),
        )
        if out is None:
            return "topk-drop plan unavailable: degenerate input"
        lines = [
            "## Topk-Drop rebalance plan",
            "",
            f"hold: {', '.join(out['held'])}",
            f"sell: {', '.join(out['dropped']) or 'none'}",
            f"buy: {', '.join(out['added']) or 'none'}",
        ]
        if out["held"]:
            eq = 1.0 / len(out["held"])
            lines.append(f"turnover: {out['turnover']:.2%} · weights: equal {eq:.1%} each")
        else:
            lines.append("turnover: n/a (no holdings)")
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001
        return f"topk-drop plan unavailable: {exc}"


@tool
def get_enhanced_index_tilt(
    scores: Annotated[dict, "name -> score"],
    benchmark_weights: Annotated[dict, "name -> benchmark weight (sums to 1)"],
    w0: Annotated[dict | None, "current portfolio weights; default = benchmark"] = None,
    turnover_cap: Annotated[float, "max one-way turnover ||w - w0||_1"] = 0.2,
    b_dev: Annotated[float, "max |w - benchmark| per name"] = 0.02,
) -> str:
    """Qlib convex enhanced-indexing tilt (pillar 14, advisory).

    The pure constrained program: long-only, sum(w)=1, turnover cap,
    benchmark-deviation bounds, two-stage fallback (drop the cap, then hold
    ``w0``) on an infeasible problem. Outputs the target weights + turnover
    vs ``w0``. Never a gate.
    """
    try:
        from tradingagents.strategies.portfolio_strategy import enhanced_index_weights
    except Exception as exc:  # noqa: BLE001
        return f"enhanced-index tilt unavailable: {exc}"
    try:
        if not scores or not benchmark_weights:
            return "enhanced-index tilt unavailable: scores and benchmark_weights required"
        w0w = w0 or benchmark_weights
        out = enhanced_index_weights(
            scores, benchmark_weights, w0w,
            turnover_cap=float(turnover_cap), b_dev=float(b_dev),
        )
        if out is None:
            return "enhanced-index tilt unavailable: degenerate input"
        w0_expect = {str(k).upper(): round(float(v), 6) for k, v in w0w.items()}
        if out == w0_expect:
            return ("enhanced-index tilt unavailable: infeasible, holdings "
                    "unchanged (w0 kept)")
        w0n = {str(k).upper(): float(v) for k, v in w0w.items()}
        turn = sum(abs(float(out.get(n, 0.0)) - w0n.get(n.upper(), 0.0))
                   for n in set(out) | set(w0n)) / 2.0
        lines = ["## Enhanced-index tilt", ""]
        for name, wt in sorted(out.items(), key=lambda kv: -kv[1])[:15]:
            lines.append(f"- {name}: {wt:.2%}")
        lines.append("")
        lines.append(f"one-way turnover vs w0: {turn:.2%} · cap {float(turnover_cap):.0%}")
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001
        return f"enhanced-index tilt unavailable: {exc}"


__all__ = [
    "get_sector_rank",
    "get_normality",
    "get_unit_root",
    "get_relative_rotation",
    "get_capm_risk",
    "get_clenow_momentum",
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
    "get_mean_reversion_tech",
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
    "get_exit_plan",
    "get_scaleout_plan",
    "get_payoff_asymmetry",
    "get_book_correlation",
    "get_allocation",
    "get_regime_components",
    "get_consensus",
    "get_momentum_detail",
    "get_beat_miss_sizing",
    "get_dcf_valuation",
    "get_session_discipline",
    "get_earnings_quality",
    "get_ownership_concentration",
    "get_opening_range",
    "get_gap_type",
    "get_order_imbalance",
    "get_premarket_liquidity",
    "get_post_close_confirmation",
    "get_technical_factors",
    "get_book_tail_risk",
    "get_liquidation_days",
    "get_premarket_review",
    "get_sentiment_computed",
    "get_options_surface",
    "get_sofr_curve",
    "get_treasury_curve",
    "screen_equities",
    "get_market_movers",
    "get_factor_profile",
    "get_topk_drop_plan",
    "get_enhanced_index_tilt",
]

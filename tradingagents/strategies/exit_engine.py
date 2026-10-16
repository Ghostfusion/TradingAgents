"""The exit engine: five mechanisms, one decision, no look-ahead.

An entry identifies an opportunity; the exit decides when the opportunity has
deteriorated, the trade has failed, or the reward no longer justifies the risk.
This module composes the repo's **existing** producers into that single
decision - it re-implements none of them:

  initial / trailing stop   ``size.atr`` (the repo's one ATR convention) and the
                            chandelier rule ``swing.chandelier_exit`` prints
  the exit ladder           ``exits.exit_decision`` (``EXIT_PRECEDENCE``,
                            fail-closed conditions, a price per fired slot)
  the time horizon          ``exits.time_exit`` (``Strategies/entry_exit.md`` §58)
  cost netting              ``exits.net_of_cost``
  relative strength         ``relative_strength.relative_strength_report``
                            ("lagging" is the repo's own word for deteriorating)

What it adds, because nothing in the tree answered these:

* :func:`sma_break_confirmed` - the *confirmed* trend exit (N consecutive closes
  below the N-day MA). A single close below the line is the noisy version.
* :func:`momentum_deterioration` - persistence, not level: the composite below
  its band edge for N consecutive sessions.
* :func:`stall_exit` - the opportunity-cost rule (days held, no progress,
  relative strength deteriorating).
* :func:`evaluate_long_exit` - the point-in-time walk: the stop in force when bar
  ``t`` is tested was computed from bars through ``t-1``, the high-water mark and
  the next stop are updated only *after* ``t`` has been evaluated, and a gap fills
  at the open, never at the stop.
* :data:`EXIT_ACTIONS` / :func:`classify_exit` - the published vocabulary
  (``HOLD`` / ``REDUCE`` / ``EXIT`` / ``RISK_EXIT`` / ``UNAVAILABLE``) so an
  unmeasurable position is never silently read as safe.
* :func:`compare_exit_variants` - the ladder's own A/B (initial stop, +trailing,
  +trend, +momentum/time) over identical entries.

Parameter provenance - measured, not remembered. Read this before changing a
default:

* **2.5 x ATR initial stop.** LeBeau (TradeStationWorld 2005, "Exit Strategies for
  Stocks and Futures"): *"my favorite initial stop is placed 2 or 3 ATRs below my
  entry point"*. Alvarez's 10-year R-multiple study of a 52-week-high breakout
  found the best of every stop type tested was the **2.5 x ATR max-loss evaluated
  at the close** (776 total R, versus 607 for the same stop intraday and a 164
  no-stop baseline).
* **3 x ATR trailing from the highest high since entry.** LeBeau's chandelier:
  *"the stop is set 3 ATRs below the highest high (or highest close) since the
  trade was entered ... the stop moves upward whenever a new high is made"*.
  **Measured caveat**: on Alvarez's medium-term breakout the trailing stop was the
  one stop type that did **not** add value (~200-250 total R, negative at tight
  multiples). That is why it is a switch and why :func:`compare_exit_variants`
  exists: measure it on the names at hand before trusting it.
* **``stop_evaluation='close'``.** Alvarez: end-of-day evaluation beat intraday by
  roughly 30 % on identical stops (776 vs 607 total R at 2.5 x ATR). The intraday
  convention is kept because the brief specifies it - as a choice, not a default.
* **50-day MA.** LeBeau: *"exit using moving averages ... 30 to 50 days works well
  for stocks"*.
* **The momentum threshold is the composite's own band edge** (40.0, the
  ``MOMENTUM_BANDS`` "neutral" floor), never the brief's 35 - which sits *inside*
  that band rather than on its edge. The same rule the screener obeys: a threshold
  is the producer's number.
* **20-session stall, shipped OFF.** Alvarez measured this exact rule (exit a
  momentum name under its entry price after N weeks) on a momentum breakout: CAR
  and maximum drawdown essentially unchanged, win rate and average P/L materially
  lower, trade count higher. It stays available, default-off, until a run measures
  it improving something here.

Fail-closed throughout: an unmeasurable rule is absent from ``conditions`` and
named in ``absent`` - never read as "no exit". ``UNAVAILABLE`` is reserved for a
position whose *protective* layer cannot be measured, because "do not silently
assume the position is safe" is the one thing this engine must never do.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from tradingagents.strategies import exits as _exits

#: The published exit vocabulary. ``UNAVAILABLE`` is a verdict, not an error: it
#: says the protective layer could not be measured, so nothing here claims safety.
EXIT_ACTIONS: tuple[str, ...] = ("HOLD", "REDUCE", "EXIT", "RISK_EXIT", "UNAVAILABLE")

#: The composite's own edge: ``MOMENTUM_BANDS``' "neutral" floor. Below it the
#: score is in the first band that is no longer neutral.
DEFAULT_MOMENTUM_EXIT_THRESHOLD = 40.0

#: The one slot whose action is not a plain ``EXIT``: the repo's ladder puts
#: terminal risk first, and its action is ``RISK_EXIT``.
_ACTION_BY_REASON: dict[str, str] = {"risk_gate": "RISK_EXIT"}

_PRICE_SLOTS = ("stop", "trailing_stop", "target")


@dataclass(frozen=True)
class ExitConfig:
    """The exit ladder's parameters, all of them evidence-backed (see module doc).

    ``stop_evaluation`` is ``"close"`` (the measured-better convention: the stop
    is tested against the bar's close and the fill is the next tradable price) or
    ``"intraday"`` (the stop is tested against the bar's low and fills at the
    stop, or at the open when the bar gapped through it).
    """

    atr_period: int = 14
    initial_atr_multiple: float = 2.5
    trailing_atr_multiple: float = 3.0
    trailing_window: int = 22
    trend_ma_period: int = 50
    trend_confirm_bars: int = 2
    momentum_exit_threshold: float = DEFAULT_MOMENTUM_EXIT_THRESHOLD
    momentum_confirm_bars: int = 3
    max_stalled_bars: int = 20
    max_holding_days: int | None = None
    min_holding_days: int | None = None
    enable_trailing: bool = True
    enable_trend: bool = True
    enable_momentum: bool = True
    enable_stall_exit: bool = False
    stop_evaluation: str = "close"
    reduce_within_atr: float = 1.0
    cost_bps: float = 10.0

    def resolved(self) -> ExitConfig:
        """The config with incoherent fields made safe - visibly, never silently."""
        evaluation = str(self.stop_evaluation).strip().lower()
        return replace(
            self,
            stop_evaluation=evaluation if evaluation in ("close", "intraday") else "close",
            atr_period=max(2, int(self.atr_period)),
            trailing_window=max(1, int(self.trailing_window)),
            trend_ma_period=max(1, int(self.trend_ma_period)),
            trend_confirm_bars=max(1, int(self.trend_confirm_bars)),
            momentum_confirm_bars=max(1, int(self.momentum_confirm_bars)),
            max_stalled_bars=max(1, int(self.max_stalled_bars)),
        )


def _atr_at(
    closes: list[float],
    highs: list[float] | None,
    lows: list[float] | None,
    index: int,
    window: int,
) -> tuple[float | None, str]:
    """The ATR as of the close of bar ``index``, with the basis it came from.

    ``size.atr`` - the same simple mean of true ranges the swing tools print -
    over the series through ``index``. Highs/lows absent falls back to
    ``contract.atr_with_source``'s close-to-close proxy, and the basis travels
    with the number instead of being assumed.
    """
    if index < 1 or index >= len(closes):
        return None, "none"
    if highs is not None and lows is not None and len(highs) == len(closes) == len(lows):
        from tradingagents.strategies.size import atr

        value = atr(
            [float(h) for h in highs[: index + 1]],
            [float(low) for low in lows[: index + 1]],
            [float(c) for c in closes[: index + 1]],
            window=window,
        )
        if value is not None and float(value) > 0:
            return float(value), "h/l"
    from tradingagents.strategies.contract import atr_with_source

    value, source = atr_with_source(
        [float(c) for c in closes[: index + 1]], None, None, window=window
    )
    return (float(value), source) if value and float(value) > 0 else (None, "none")


def _sma_series(values: list[float], period: int) -> list[float | None]:
    """Simple moving averages aligned to ``values``; ``None`` until ``period`` bars.

    The same arithmetic mean ``technical_factors.sma_legs`` prints as
    ``sma_fast``/``sma_slow``. The engine needs the *series* because the
    confirmation rule is about consecutive closes, which no scalar read answers.
    """
    out: list[float | None] = []
    running = 0.0
    for i, value in enumerate(values):
        running += float(value)
        if i >= period:
            running -= float(values[i - period])
        out.append(running / period if i >= period - 1 else None)
    return out


def sma_break_confirmed(closes: list[float], *, period: int = 50, confirm_bars: int = 2) -> dict:
    """The confirmed trend exit: ``confirm_bars`` consecutive closes below the MA.

    The one-close rule exits on every ordinary pullback; the confirmation is what
    LeBeau's "be patient at the beginning of the trade" advice costs. ``break`` is
    ``None`` - never ``False`` - when the history cannot decide it.
    """
    bars = max(1, int(confirm_bars))
    ma_period = max(1, int(period))
    if not closes or len(closes) < ma_period + bars - 1:
        return {
            "break": None,
            "ma": None,
            "below": None,
            "bars_below": None,
            "reason": f"needs {ma_period + bars - 1} closes for MA{ma_period} x{bars}",
        }
    values = [float(c) for c in closes]
    series = _sma_series(values, ma_period)
    below = 0
    for i in range(len(values) - 1, -1, -1):
        ma = series[i]
        if ma is None or values[i] >= ma:
            break
        below += 1
    last_ma = series[-1]
    return {
        "break": bool(below >= bars),
        "ma": None if last_ma is None else round(float(last_ma), 4),
        "below": None if last_ma is None else bool(values[-1] < last_ma),
        "bars_below": below,
        "reason": None,
    }


def momentum_deterioration(
    scores: list[float | None],
    *,
    threshold: float = DEFAULT_MOMENTUM_EXIT_THRESHOLD,
    confirm_bars: int = 3,
) -> dict:
    """Persistence, not level: the composite below ``threshold`` for N sessions.

    A missing score inside the window makes the rule **unmeasurable** (``None``),
    never "no deterioration" - a score nobody measured is not a safe score. The
    threshold defaults to the composite's own band edge.
    """
    bars = max(1, int(confirm_bars))
    if not scores or len(scores) < bars:
        return {
            "deteriorated": None,
            "sessions_below": None,
            "threshold": float(threshold),
            "last": None,
            "reason": f"needs {bars} scored sessions, {len(scores or [])} supplied",
        }
    window = list(scores[-bars:])
    if any(score is None for score in window):
        return {
            "deteriorated": None,
            "sessions_below": None,
            "threshold": float(threshold),
            "last": None,
            "reason": f"a score inside the last {bars} sessions is unmeasured",
        }
    below = sum(1 for score in window if float(score) < float(threshold))
    return {
        "deteriorated": bool(below >= bars),
        "sessions_below": below,
        "threshold": float(threshold),
        "last": float(window[-1]),
        "reason": None,
    }


def stall_exit(
    days_held: int | None,
    *,
    unrealized_return: float | None,
    rs_deteriorating: bool | None,
    max_stalled_bars: int = 20,
    min_progress: float = 0.0,
) -> dict:
    """The opportunity-cost exit: no progress after N sessions with RS deteriorating.

    All three inputs must be measured for the rule to fire *or not fire*: an
    unmeasured relative-strength read yields ``None`` (the rule is absent), not a
    cheerful ``False``. Ships off by default - see the module docstring for the
    measurement that keeps it off.
    """
    horizon = max(1, int(max_stalled_bars))
    if days_held is None or unrealized_return is None or rs_deteriorating is None:
        missing = [
            name
            for name, value in (
                ("days_held", days_held),
                ("unrealized_return", unrealized_return),
                ("rs_deteriorating", rs_deteriorating),
            )
            if value is None
        ]
        return {
            "exit": None,
            "days_held": days_held,
            "max_stalled_bars": horizon,
            "reason": f"unmeasurable: need {', '.join(missing)}",
        }
    stalled = int(days_held) >= horizon
    no_progress = float(unrealized_return) <= float(min_progress)
    fires = bool(stalled and no_progress and rs_deteriorating)
    if fires:
        reason = (
            f"held {int(days_held)}d >= {horizon}d with return "
            f"{float(unrealized_return):+.1%} and RS deteriorating"
        )
    elif not stalled:
        reason = f"held {int(days_held)}d < {horizon}d"
    elif not no_progress:
        reason = f"progress {float(unrealized_return):+.1%} > {float(min_progress):+.1%}"
    else:
        reason = "relative strength not deteriorating"
    return {
        "exit": fires,
        "days_held": int(days_held),
        "max_stalled_bars": horizon,
        "reason": reason,
    }


def initial_stop(
    entry_price: float | None, atr: float | None, *, multiple: float = 2.5
) -> float | None:
    """``entry - k x ATR``: the protective stop that also fixes the position size."""
    if entry_price is None or atr is None or float(entry_price) <= 0 or float(atr) <= 0:
        return None
    return float(entry_price) - float(multiple) * float(atr)


def trailing_stop_level(
    prev_stop: float | None,
    highest_high: float | None,
    atr: float | None,
    *,
    multiple: float = 3.0,
) -> float | None:
    """``max(prev_stop, highest_high - k x ATR)`` - a ratchet, which never moves down.

    The ``max`` is the whole point: a trailing stop that can fall is not a
    trailing stop, it is a re-entry invitation.
    """
    if highest_high is None or atr is None or float(atr) <= 0:
        return None
    candidate = float(highest_high) - float(multiple) * float(atr)
    if prev_stop is None:
        return candidate
    return max(float(prev_stop), candidate)


def classify_exit(
    fired_reason: str | None,
    *,
    deteriorated: bool = False,
    coverage: int = 0,
    protective_measured: bool = True,
) -> str:
    """The published action for a set of evaluated conditions.

    The ladder is ``exits.EXIT_PRECEDENCE``'s: a fired slot is an exit, the
    terminal-risk slot is a ``RISK_EXIT``, a deterioration that has fired no rule
    is a ``REDUCE``, and a position whose protective layer could not be measured
    is ``UNAVAILABLE`` - the one verdict that must never be a reassuring ``HOLD``.
    """
    if not protective_measured or coverage == 0:
        return "UNAVAILABLE"
    if fired_reason:
        return _ACTION_BY_REASON.get(str(fired_reason), "EXIT")
    return "REDUCE" if deteriorated else "HOLD"


def _unavailable(reason: str, **extra) -> dict:
    out = {
        "action": "UNAVAILABLE",
        "reason": reason,
        "exit_index": None,
        "exit_price": None,
        "exit_date": None,
        "execution": None,
        "entry_price": None,
        "entry_idx": None,
        "days_held": None,
        "stop_now": None,
        "initial_stop": None,
        "trailing_stop": None,
        "atr": None,
        "hwm": None,
        "hwm_idx": None,
        "unrealized_return": None,
        "gross_return": None,
        "net_return": None,
        "trend_break": None,
        "momentum_deteriorating": None,
        "conditions": {},
        "coverage": 0,
        "absent": {},
        "triggered": {},
        "basis": "",
    }
    out.update(extra)
    return out


def _either_measured(first: bool | None, second: bool | None) -> bool | None:
    """The thesis-break slot, which two independent mechanisms answer.

    ``True`` if either fired. The slot is *measurable* as soon as either
    sub-rule is: the fail-closed risk here is reading "the thesis holds" when
    nothing was measured, and a measured ``False`` next to an unmeasured peer
    is not that. The unmeasured peer is named in ``absent``, so the weaker
    evidence is visible even though the slot still decides.
    """
    if first is True or second is True:
        return True
    if first is None and second is None:
        return None
    return False


def _low_at(lows: list[float] | None, closes: list[float], t: int) -> float:
    return float(lows[t]) if lows is not None and t < len(lows) else float(closes[t])


def _high_at(highs: list[float] | None, closes: list[float], t: int) -> float:
    return float(highs[t]) if highs is not None and t < len(highs) else float(closes[t])


def _date_at(dates: list | None, t: int) -> str | None:
    return str(dates[t])[:10] if dates and t < len(dates) else None


def _fill(
    t: int,
    reason: str,
    level: float | None,
    closes: list[float],
    opens: list[float] | None,
    n: int,
    cfg: ExitConfig,
) -> dict:
    """The price this bar's exit transacts at, and why that price.

    Never invents a price: with only closes and opens to hand the fill is one of
    them, chosen by the convention in force.
    """
    if reason in _PRICE_SLOTS and level is not None:
        if cfg.stop_evaluation == "intraday":
            bar_open = float(opens[t]) if opens is not None and t < len(opens) else None
            if bar_open is not None and bar_open < float(level):
                return {"price": round(bar_open, 4), "execution": "gapped open"}
            return {"price": round(float(level), 4), "execution": "stop level"}
        if t + 1 < n:
            nxt_open = float(opens[t + 1]) if opens is not None and t + 1 < len(opens) else None
            if nxt_open is not None:
                return {"price": round(nxt_open, 4), "execution": "next open"}
            return {"price": round(closes[t + 1], 4), "execution": "next close"}
        return {"price": round(closes[t], 4), "execution": "last close"}
    if t + 1 < n:
        return {"price": round(closes[t + 1], 4), "execution": "next close"}
    return {"price": round(closes[t], 4), "execution": "last close"}


def _basis(
    entry: float,
    price_basis: str,
    atr_entry: float | None,
    atr_basis: str,
    cfg: ExitConfig,
    stop0: float | None,
) -> str:
    stop_text = f"stop {stop0:.4f}" if stop0 is not None else "stop unmeasured"
    return (
        f"entry {entry:.4f} ({price_basis}); ATR{cfg.atr_period} "
        f"{'n/a' if atr_entry is None else f'{atr_entry:.4f}'} ({atr_basis}); "
        f"initial {cfg.initial_atr_multiple:g}xATR -> {stop_text}; "
        f"trail {cfg.trailing_atr_multiple:g}xATR from the high-water mark (w{cfg.trailing_window}); "
        f"MA{cfg.trend_ma_period} x{cfg.trend_confirm_bars}; "
        f"momentum < {cfg.momentum_exit_threshold:g} x{cfg.momentum_confirm_bars}; "
        f"stall {cfg.max_stalled_bars}d ({'on' if cfg.enable_stall_exit else 'off'}); "
        f"evaluation {cfg.stop_evaluation}; costs {cfg.cost_bps:g}bps"
    )


def evaluate_long_exit(
    closes: list[float],
    *,
    entry_price: float | None = None,
    entry_idx: int | None = None,
    entry_date: str | None = None,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    opens: list[float] | None = None,
    dates: list | None = None,
    config: ExitConfig | None = None,
    momentum_scores: list[float | None] | None = None,
    rs_deteriorating: bool | None = None,
    risk_gate: str | None = None,
    target: float | None = None,
    expected_value: float | None = None,
) -> dict:
    """Walk a long from its entry to the last bar and return the exit decision.

    Point-in-time, in the two places that matter:

    * the stop tested on bar ``t`` was computed from bars through ``t-1`` - the
      ATR, the high-water mark and the ratchet all use only what was available
      when the bar opened;
    * the high-water mark and the next stop are updated only *after* ``t`` has
      been evaluated.

    ``action`` is the instruction for the position **now**: a rule that fired
    anywhere in the window stays fired until the position is flat, so the walk
    stops at the first firing bar. When nothing fired, ``action`` is ``REDUCE`` if
    a deterioration read is present (an unconfirmed trend break, the composite
    below its edge on the last scored session without the confirmation count, or
    the price within ``reduce_within_atr`` ATRs of the live stop) and ``HOLD``
    otherwise. ``absent`` names every rule that could not be measured, so a thin
    ``coverage`` is visible rather than reassuring.
    """
    cfg = (config or ExitConfig()).resolved()
    closes = [float(c) for c in closes]
    n = len(closes)
    if n < 2:
        return _unavailable("fewer than two bars: no exit can be evaluated")

    if entry_idx is None and entry_date is not None and dates:
        wanted = str(entry_date)[:10]
        for i, value in enumerate(dates):
            if str(value)[:10] == wanted:
                entry_idx = i
                break
    if entry_idx is None:
        return _unavailable("no entry point: pass entry_idx or an entry_date present in dates")
    if not 0 <= int(entry_idx) < n:
        return _unavailable(f"entry_idx {entry_idx} is outside the {n} bars supplied")
    idx = int(entry_idx)

    supplied = entry_price is not None and float(entry_price) > 0
    entry = float(entry_price) if supplied else closes[idx]
    price_basis = "caller entry price" if supplied else "close at the entry bar"

    atr_entry, atr_basis = _atr_at(closes, highs, lows, idx, cfg.atr_period)
    stop0 = initial_stop(entry, atr_entry, multiple=cfg.initial_atr_multiple)
    protective = stop0 is not None
    if not protective:
        return _unavailable(
            "the protective stop could not be measured (no usable ATR at entry)",
            entry_price=round(entry, 4),
            entry_idx=idx,
            absent={"stop_unmeasured": f"no usable ATR{cfg.atr_period} at bar {idx}"},
            basis=_basis(entry, price_basis, atr_entry, atr_basis, cfg, stop0),
        )

    absent: dict[str, str] = {}
    trend_probe = sma_break_confirmed(
        closes[: idx + 1], period=cfg.trend_ma_period, confirm_bars=cfg.trend_confirm_bars
    )
    if cfg.enable_trend and trend_probe["break"] is None:
        absent["trend_unmeasured"] = str(trend_probe["reason"])
    mom_probe = None
    if cfg.enable_momentum:
        mom_probe = momentum_deterioration(
            list(momentum_scores or []),
            threshold=cfg.momentum_exit_threshold,
            confirm_bars=cfg.momentum_confirm_bars,
        )
        if mom_probe["deteriorated"] is None:
            absent["momentum_unmeasured"] = str(mom_probe["reason"])
    if cfg.enable_stall_exit and rs_deteriorating is None:
        absent["rs_unmeasured"] = "relative strength not supplied to the stall rule"

    hwm = entry
    hwm_idx = idx
    prev_stop = stop0
    fired: dict | None = None
    triggered: dict[str, bool] = {}
    state: dict = {}
    last_closed: int | None = None

    for t in range(idx + 1, n):
        # Levels in force when bar t opens: bars through t-1 only.
        atr_prev, _ = _atr_at(closes, highs, lows, t - 1, cfg.atr_period)
        trail_t = None
        if cfg.enable_trailing and atr_prev is not None:
            trail_t = trailing_stop_level(
                prev_stop, hwm, atr_prev, multiple=cfg.trailing_atr_multiple
            )
        live_stop = max([v for v in (stop0, trail_t) if v is not None], default=None)

        trend_t: bool | None = False
        if cfg.enable_trend:
            trend_t = sma_break_confirmed(
                closes[: t + 1], period=cfg.trend_ma_period, confirm_bars=cfg.trend_confirm_bars
            )["break"]
        mom_t: bool | None = False
        if cfg.enable_momentum:
            mom_t = momentum_deterioration(
                list(momentum_scores or [])[: t + 1],
                threshold=cfg.momentum_exit_threshold,
                confirm_bars=cfg.momentum_confirm_bars,
            )["deteriorated"]

        days_held = t - idx
        unrealized = closes[t] / entry - 1.0
        horizon = _exits.time_exit(days_held, cfg.max_holding_days, cfg.min_holding_days)
        time_fired: bool | None = horizon["exit"]
        if cfg.enable_stall_exit:
            stall = stall_exit(
                days_held,
                unrealized_return=unrealized,
                rs_deteriorating=rs_deteriorating,
                max_stalled_bars=cfg.max_stalled_bars,
            )
            if stall["exit"] is True:
                time_fired = True
            elif time_fired is None:
                time_fired = stall["exit"]

        tested = closes[t] if cfg.stop_evaluation == "close" else _low_at(lows, closes, t)
        decision = _exits.exit_decision(
            close=tested,
            stop=stop0,
            trailing_stop=trail_t,
            target=target,
            thesis_break=_either_measured(trend_t, mom_t),
            risk_gate=risk_gate,
            time_exit_fired=time_fired,
            expected_value=expected_value,
        )
        for name, value in decision["conditions"].items():
            if value:
                triggered[name] = True

        state = {
            "conditions": dict(decision["conditions"]),
            "coverage": int(decision["coverage"]),
            "days_held": days_held,
            "unrealized_return": unrealized,
            "trend_break": trend_t,
            "momentum_deteriorating": mom_t,
            "atr": atr_prev,
            "live_stop": live_stop,
            "trailing_stop": trail_t,
        }
        last_closed = t

        if decision["exit"] is True:
            reason = str(decision["reason"])
            level = {"stop": stop0, "trailing_stop": trail_t, "target": target}.get(reason)
            fired = {
                "reason": reason,
                "index": t,
                "date": _date_at(dates, t),
                **_fill(t, reason, level, closes, opens, n, cfg),
            }
            break

        # Only now may bar t inform the next bar's levels.
        hwm_bar = _high_at(highs, closes, t)
        if hwm_bar > hwm:
            hwm = hwm_bar
            hwm_idx = t
        if live_stop is not None:
            prev_stop = live_stop

    if state == {} or last_closed is None:
        return _unavailable("no bar after the entry bar: nothing to evaluate")

    coverage = int(state.get("coverage", 0))
    fired_reason = fired["reason"] if fired else None
    trend_now = state.get("trend_break")
    mom_now = state.get("momentum_deteriorating")
    if fired is None:
        trend_probe = (
            sma_break_confirmed(
                closes[: last_closed + 1],
                period=cfg.trend_ma_period,
                confirm_bars=cfg.trend_confirm_bars,
            )
            if cfg.enable_trend
            else None
        )
        spot = (
            momentum_deterioration(
                list(momentum_scores or [])[: last_closed + 1],
                threshold=cfg.momentum_exit_threshold,
                confirm_bars=1,
            )
            if cfg.enable_momentum
            else None
        )
        trend_deteriorating = bool(
            trend_probe is not None
            and trend_probe["below"] is True
            and trend_probe["break"] is False
        )
        momentum_weakening = bool(
            spot is not None and spot["deteriorated"] is True and mom_now is not True
        )
        near_stop = False
        live_stop = state.get("live_stop")
        atr_now = state.get("atr")
        if live_stop is not None and atr_now is not None and float(atr_now) > 0:
            near_stop = (
                closes[last_closed] - float(live_stop)
                <= float(cfg.reduce_within_atr) * float(atr_now)
            )
        deteriorated = bool(trend_deteriorating or momentum_weakening or near_stop)
    else:
        deteriorated = False

    action = classify_exit(
        fired_reason, deteriorated=deteriorated, coverage=coverage, protective_measured=protective
    )
    price = fired["price"] if fired else None
    gross = (
        round(float(price) / entry - 1.0, 6)
        if fired is not None and price is not None and entry > 0
        else None
    )
    live_now = state.get("live_stop")
    return {
        "action": action,
        "reason": fired_reason
        or ("deteriorating (unconfirmed)" if deteriorated else "no exit condition fired"),
        "exit_index": fired["index"] if fired else None,
        "exit_price": price,
        "exit_date": fired["date"] if fired else None,
        "execution": fired["execution"] if fired else None,
        "entry_price": round(entry, 4),
        "entry_idx": idx,
        "days_held": state.get("days_held"),
        "stop_now": None if live_now is None else round(float(live_now), 4),
        "initial_stop": round(float(stop0), 4),
        "trailing_stop": (
            None if state.get("trailing_stop") is None else round(state["trailing_stop"], 4)
        ),
        "atr": None if state.get("atr") is None else round(float(state["atr"]), 4),
        "hwm": round(float(hwm), 4),
        "hwm_idx": hwm_idx,
        "unrealized_return": state.get("unrealized_return"),
        "gross_return": gross,
        "net_return": (
            None if gross is None else round(_exits.net_of_cost(gross, cost_bps=cfg.cost_bps), 6)
        ),
        "trend_break": trend_now,
        "momentum_deteriorating": mom_now,
        "conditions": state.get("conditions", {}),
        "coverage": coverage,
        "absent": absent,
        "triggered": triggered,
        "basis": _basis(entry, price_basis, atr_entry, atr_basis, cfg, stop0),
    }


def _peak_gain(
    closes: list[float],
    highs: list[float] | None,
    *,
    start: int | None,
    end: int | None,
    entry: float | None,
) -> float | None:
    """The best gain the trade saw while it was open - the denominator of giveback."""
    if start is None or entry is None or float(entry) <= 0 or not closes:
        return None
    last = len(closes) - 1 if end is None else int(end)
    if highs is not None and len(highs) == len(closes):
        window = highs[int(start) : last + 1]
    else:
        window = closes[int(start) : last + 1]
    if not window:
        return None
    return max(float(v) for v in window) / float(entry) - 1.0


def compare_exit_variants(
    closes: list[float],
    *,
    entry_price: float | None = None,
    entry_idx: int | None = None,
    entry_date: str | None = None,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    opens: list[float] | None = None,
    dates: list | None = None,
    config: ExitConfig | None = None,
    momentum_scores: list[float | None] | None = None,
    rs_deteriorating: bool | None = None,
    risk_gate: str | None = None,
) -> dict:
    """The ladder's own A/B over identical entries: the four variants, one pass each.

    (1) initial ATR stop only; (2) + trailing; (3) + confirmed trend break;
    (4) + momentum deterioration and the stall rule. Each variant's outcome and
    the metrics a stop comparison needs are reported side by side, because the
    honest answer to "does the trailing stop add value here?" is a measurement,
    not a preference. Returns are netted with ``exits.net_of_cost``.
    """
    base = (config or ExitConfig()).resolved()
    variants = (
        (
            "initial_stop_only",
            replace(
                base,
                enable_trailing=False,
                enable_trend=False,
                enable_momentum=False,
                enable_stall_exit=False,
            ),
        ),
        ("plus_trailing", replace(base, enable_trend=False, enable_momentum=False,
                                  enable_stall_exit=False)),
        ("plus_trend", replace(base, enable_momentum=False, enable_stall_exit=False)),
        ("plus_momentum_and_stall", replace(base, enable_stall_exit=True)),
    )
    common = {
        "closes": closes,
        "entry_price": entry_price,
        "entry_idx": entry_idx,
        "entry_date": entry_date,
        "highs": highs,
        "lows": lows,
        "opens": opens,
        "dates": dates,
        "momentum_scores": momentum_scores,
        "rs_deteriorating": rs_deteriorating,
        "risk_gate": risk_gate,
    }
    out: dict[str, dict] = {}
    for name, cfg in variants:
        result = evaluate_long_exit(**common, config=cfg)
        exit_index = result["exit_index"]
        peak = _peak_gain(
            [float(c) for c in closes],
            highs,
            start=result.get("entry_idx"),
            end=exit_index,
            entry=result.get("entry_price"),
        )
        realized = result.get("gross_return")
        surrendered = (
            round(max(0.0, (peak - realized) / peak), 6)
            if peak is not None and peak > 0 and realized is not None
            else None
        )
        out[name] = {
            "action": result["action"],
            "reason": result["reason"],
            "exit_index": exit_index,
            "exit_date": result["exit_date"],
            "exit_price": result["exit_price"],
            "execution": result["execution"],
            "holding_days": (
                None
                if exit_index is None or result.get("entry_idx") is None
                else int(exit_index) - int(result["entry_idx"])
            ),
            "gross_return": realized,
            "net_return": result["net_return"],
            "peak_gain_pct": None if peak is None else round(peak, 6),
            "surrendered_pct": surrendered,
            "triggered": result["triggered"],
            "absent": result["absent"],
            "coverage": result["coverage"],
        }
    return {"variants": out, "order": [name for name, _ in variants]}


__all__ = [
    "DEFAULT_MOMENTUM_EXIT_THRESHOLD",
    "EXIT_ACTIONS",
    "ExitConfig",
    "classify_exit",
    "compare_exit_variants",
    "evaluate_long_exit",
    "initial_stop",
    "momentum_deterioration",
    "sma_break_confirmed",
    "stall_exit",
    "trailing_stop_level",
]

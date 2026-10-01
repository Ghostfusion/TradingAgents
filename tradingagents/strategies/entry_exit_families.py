"""§103's price families: the ENTRY/EXIT members §8-§42 define by construction.

``entry_exit_price`` assembles §100/§101/§102 from the primitives the repo
already had (the ceiling, the target blend, the risk rule, the execution cost,
the exit predicate). §103's recommended object also names a price per
*construction* - the volatility entry, the support entry, the volatility / ATR
/ support / break-even stops, and the volatility / risk-multiple / fair-value
targets. This module computes those, each by the formula its own section states,
from inputs a run already holds: the close series, the tranche plan's entry and
stop, and config. It never re-derives what ``entry_exit_price`` already owns.

The contract is the one the rest of the §103 path keeps: **every member is a
price this run measured, or ``None`` with a reason.** Nothing defaults to the
spot price, no 0-100 score is turned into a price, and a family whose inputs are
absent says so instead of guessing. A basis that is a proxy (an ATR off closes
rather than highs/lows, a support off closes rather than the run's lows) travels
with the number - the rule ``contract.atr_with_source`` already applies.

Three members are deliberately **not** produced here:

* ``momentum_entry_price`` / ``momentum_target`` - the repo emits 0-100
  momentum scores and has no calibrated score -> price map. That is the owner's
  Phase-2 decision, and the same reason ``entry_ceiling`` excludes momentum
  from its ceiling sources.
* ``fair_value_price`` / ``fair_value_target`` - a fair value needs statement
  data, which the pre-graph card does not fetch. A caller that HAS one passes
  ``fair_value`` and both members fill; otherwise they are absent with a reason.
* ``event_exit`` - needs the forward calendar, which the card is built without.

Pure and deterministic: no I/O, no LLM, no vendor calls. Advisory throughout.
"""

from __future__ import annotations

import contextlib
import math

from tradingagents.strategies.contract import atr_with_source
from tradingagents.strategies.entry_ceiling import usable_price_level
from tradingagents.strategies.exits import stop_to_breakeven

#: §103's ENTRY members, verbatim and in the spec's order.
ENTRY_MEMBERS = (
    "signal_price",
    "fair_value_price",
    "valuation_entry_price",
    "technical_entry_price",
    "momentum_entry_price",
    "volatility_entry_price",
    "support_entry_price",
    "expected_return_entry_price",
    "risk_adjusted_entry_price",
    "liquidity_adjusted_entry_price",
    "execution_price",
    "max_entry_price",
    "final_entry_price",
)

#: §103's EXIT members, verbatim and in the spec's order.
EXIT_MEMBERS = (
    "stop_loss_price",
    "volatility_stop",
    "ATR_stop",
    "support_stop",
    "trailing_stop",
    "break_even_stop",
    "fair_value_target",
    "technical_target",
    "momentum_target",
    "volatility_target",
    "risk_reward_target",
    "time_exit",
    "event_exit",
    "thesis_break_exit",
    "expected_value_exit",
    "final_exit_price",
)

#: §9's volatility-entry multiple and horizon, in days.
VOL_ENTRY_K = 1.0
VOL_ENTRY_HORIZON_DAYS = 1
#: §10's execution buffer epsilon, as a fraction of the support level.
SUPPORT_BUFFER_PCT = 0.002
#: §34's volatility-stop and §40's volatility-target multiples.
VOL_STOP_K = 2.0
VOL_TARGET_K = 2.0
#: §35's ATR offset below support (so the stop does not sit ON the level).
SUPPORT_STOP_ATR_MULT = 1.0
#: §42's conservative haircut on a fair-value target.
FAIR_VALUE_HAIRCUT = 0.10
#: The support and volatility lookbacks, in bars.
SUPPORT_WINDOW = 20
SIGMA_WINDOW = 20

_MOMENTUM_REASON = (
    "no calibrated 0-100 momentum-score -> price map exists (owner Phase-2 "
    "decision; the same reason entry_ceiling excludes momentum)"
)
_FAIR_VALUE_REASON = (
    "needs a per-share fair value from statement data, which the pre-graph card "
    "does not fetch"
)
_EVENT_REASON = "needs the forward calendar, which the card is built without"


def _member(value, status: str, reason: str) -> dict:
    return {"value": value, "status": status, "reason": reason}


def _absent(reason: str) -> dict:
    return _member(None, "NO_SOURCE", reason)


def _price_str(value) -> str:
    """A price inside a reason string: 2dp, which is how a reader compares levels."""
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)


def _refuse_wrong_side(record: dict, base, required: str, side: str) -> dict:
    """Refuse a level that is not on the side of the entry it must be on.

    ``required`` is ``"ge"`` (the level must be at or above ``base``) or ``"le"``.
    A price on the wrong side is not a usable level, and printing it as one would
    mislead: FNF 2026-09-30 closed AT its 20-bar low, so ``support*(1+eps)`` came
    out above the reference price and "support - ATR" above the entry it was
    supposed to protect. The member becomes an absent-with-reason instead - never
    a silently inverted number.
    """
    if record.get("value") is None or base is None:
        return record
    value = record["value"]
    ok = value >= base if required == "ge" else value <= base
    if ok:
        return record
    return _absent(
        f"{record.get('reason')} - refused: {_price_str(value)} is not {side} "
        f"the entry {_price_str(base)}"
    )


def member(value, reason: str) -> dict:
    """One §103 member: the measured price, or ``None`` with the reason it is absent.

    Used for the price members AND for the four members that are *conditions*
    rather than prices (``time_exit`` / ``thesis_break_exit`` /
    ``expected_value_exit`` / ``event_exit``): an unevaluated condition is
    ``None`` - absent, never ``False`` - so a time exit nobody could measure is
    not read as "no time exit" (the rule ``exits.exit_decision`` keeps).
    """
    return _member(value, "OK" if value is not None else "NO_SOURCE", reason)


def daily_sigma(closes, window: int = SIGMA_WINDOW) -> float | None:
    """§9's ``sigma_daily``: the sample stdev of the log returns over ``window``.

    ``None`` when fewer than three closes are held: a volatility read off two
    points is not a measurement, and returning ``0.0`` would read as "no
    volatility" - the NA-as-zero class the no-fabrication contract forbids.
    """
    vals = [float(c) for c in (closes or []) if c is not None]
    if len(vals) < 3:
        return None
    rets = [
        math.log(vals[i] / vals[i - 1])
        for i in range(1, len(vals))
        if vals[i - 1] > 0.0 and vals[i] > 0.0
    ]
    if len(rets) < 2:
        return None
    sample = rets[-window:]
    mean = sum(sample) / len(sample)
    var = sum((r - mean) ** 2 for r in sample) / (len(sample) - 1)
    sd = math.sqrt(var)
    return sd if math.isfinite(sd) and sd > 0.0 else None


def support_level(closes, lows=None, window: int = SUPPORT_WINDOW) -> tuple[float | None, str]:
    """The nearest support level, and the basis it came from.

    ``lows`` when the caller holds the run's own lows (a true swing low), else
    the closes as a documented **proxy**: a close-to-close low overstates the
    swing low, so the basis travels with the number rather than being assumed.
    """
    held = [float(v) for v in (lows or []) if v is not None]
    if len(held) >= max(2, window):
        return min(held[-window:]), "lows"
    falls = [float(c) for c in (closes or []) if c is not None]
    if len(falls) >= max(2, window):
        return min(falls[-window:]), "close-proxy"
    return None, "none"


def atr_read(closes, high=None, low=None) -> tuple[float | None, str]:
    """The ATR this module prices its stops from, with its basis."""
    if not closes:
        return None, "none"
    value, source = atr_with_source([float(c) for c in closes], high, low)
    return (value if value and value > 0.0 else None), source


def section_103_members(
    *,
    closes=None,
    high=None,
    low=None,
    price=None,
    valuation_price=None,
    technical_price=None,
    expected_return_price=None,
    fair_value=None,
    entry=None,
    stop=None,
    trailing_stop=None,
    technical_target=None,
    rr_multiple=None,
    config=None,
) -> dict:
    """The §103 members this module produces, as ``{"entry": …, "exit": …}``.

    The caller merges these with the members its own primitives already produce
    (the ceiling, the §100 final, the execution price, the exit conditions), so
    one object carries every name §103 lists. ``entry`` is the reference entry
    the stops and targets are measured from (the tranche's weighted entry when a
    plan exists, else the last close).
    """
    cfg = config or {}
    ref = usable_price_level(price)
    if ref is None and closes:
        ref = usable_price_level(closes[-1])
    base = usable_price_level(entry) or ref
    atr_v, atr_source = atr_read(closes, high, low)
    sigma = daily_sigma(closes)
    support, support_source = support_level(closes, low)

    entry_members: dict[str, dict] = {}

    entry_members["signal_price"] = (
        _member(ref, "OK", "the run's reference price (last close)")
        if ref is not None
        else _absent("no reference price was measured")
    )

    fv = usable_price_level(fair_value)
    entry_members["fair_value_price"] = (
        _member(fv, "OK", "caller-supplied per-share fair value")
        if fv is not None
        else _absent(_FAIR_VALUE_REASON)
    )

    for name, value, label in (
        ("valuation_entry_price", valuation_price, "valuation anchor"),
        ("technical_entry_price", technical_price, "technical anchor"),
    ):
        level = usable_price_level(value)
        entry_members[name] = (
            _member(level, "OK", f"{label} from the §100 anchor sources")
            if level is not None
            else _absent(f"no {label} was measured for this run")
        )

    entry_members["momentum_entry_price"] = _absent(_MOMENTUM_REASON)

    if ref is not None and sigma is not None:
        move = VOL_ENTRY_K * ref * sigma * math.sqrt(VOL_ENTRY_HORIZON_DAYS)
        entry_members["volatility_entry_price"] = _member(
            ref - move,
            "OK",
            f"§9: ref - {VOL_ENTRY_K}*ref*sigma*sqrt({VOL_ENTRY_HORIZON_DAYS}); "
            f"sigma {sigma:.4%} daily ({len(closes or [])} closes)",
        )
    else:
        entry_members["volatility_entry_price"] = _absent(
            "needs a reference price and a daily sigma over >= 3 closes"
        )

    if support is not None:
        entry_members["support_entry_price"] = _member(
            support * (1.0 + SUPPORT_BUFFER_PCT),
            "OK",
            f"§10: support {_price_str(support)} x (1 + {SUPPORT_BUFFER_PCT}); basis {support_source}",
        )
    else:
        entry_members["support_entry_price"] = _absent(
            f"no support level was measurable (basis {support_source})"
        )

    exp_ret = usable_price_level(expected_return_price)
    entry_members["expected_return_entry_price"] = (
        _member(
            exp_ret,
            "OK",
            "§27/§41: the entry at which the expected return still pays",
        )
        if exp_ret is not None
        else _absent("no expected-return level was measured for this run")
    )

    exit_members: dict[str, dict] = {}

    if base is not None and sigma is not None:
        exit_members["volatility_stop"] = _member(
            base - VOL_STOP_K * sigma * base,
            "OK",
            f"§34: entry - {VOL_STOP_K}*sigma*entry; sigma {sigma:.4%} daily",
        )
    else:
        exit_members["volatility_stop"] = _absent(
            "needs a measured entry and a daily sigma over >= 3 closes"
        )

    atr_mult = float(cfg.get("atr_mult", 2.0))
    if base is not None and atr_v is not None:
        exit_members["ATR_stop"] = _member(
            base - atr_mult * atr_v,
            "OK",
            f"§32: entry - {atr_mult}*ATR; ATR {atr_v:.4f} ({atr_source})",
        )
    else:
        exit_members["ATR_stop"] = _absent(
            f"needs a measured entry and an ATR (basis {atr_source})"
        )

    if support is not None and atr_v is not None:
        exit_members["support_stop"] = _member(
            support - SUPPORT_STOP_ATR_MULT * atr_v,
            "OK",
            f"§35: support {_price_str(support)} - {SUPPORT_STOP_ATR_MULT}*ATR; "
            f"ATR {atr_v:.4f} ({atr_source}); basis {support_source}",
        )
    else:
        exit_members["support_stop"] = _absent(
            f"needs a support level and an ATR (basis {support_source} / {atr_source})"
        )

    cushion = float(cfg.get("breakeven_atr", 1.0))
    if base is not None and atr_v is not None:
        exit_members["break_even_stop"] = _member(
            stop_to_breakeven(base, atr_v, cushion_atr=cushion),
            "OK",
            f"§56: entry + {cushion}*ATR after confirmation; ATR {atr_v:.4f} ({atr_source})",
        )
    else:
        exit_members["break_even_stop"] = _absent(
            f"needs a measured entry and an ATR (basis {atr_source})"
        )

    exit_members["fair_value_target"] = (
        _member(
            fv * (1.0 - FAIR_VALUE_HAIRCUT),
            "OK",
            f"§42: FV x (1 - {FAIR_VALUE_HAIRCUT}); conservative haircut",
        )
        if fv is not None
        else _absent(_FAIR_VALUE_REASON)
    )

    tech_t = usable_price_level(technical_target)
    exit_members["technical_target"] = (
        _member(tech_t, "OK", "the plan's own structure target (T2, else T1)")
        if tech_t is not None
        else _absent("the plan measured no structure target")
    )

    exit_members["momentum_target"] = _absent(_MOMENTUM_REASON)

    trail = usable_price_level(trailing_stop)
    exit_members["trailing_stop"] = (
        _member(trail, "OK", "the plan's own trailing level (EMA20 close-through / chandelier)")
        if trail is not None
        else _absent("the plan measured no trailing level")
    )

    # §103 names an event exit; nothing in the repo produces one at card time -
    # the forward calendar is not an input the pre-graph card holds. Named
    # absent so a reader sees the member was considered, not forgotten.
    exit_members["event_exit"] = _absent(_EVENT_REASON)

    if base is not None and sigma is not None:
        exit_members["volatility_target"] = _member(
            base + VOL_TARGET_K * sigma * base,
            "OK",
            f"§40: entry + {VOL_TARGET_K}*sigma*entry; sigma {sigma:.4%} daily",
        )
    else:
        exit_members["volatility_target"] = _absent(
            "needs a measured entry and a daily sigma over >= 3 closes"
        )

    r_m = cfg.get("min_rr")
    try:
        r_m = float(r_m) if r_m is not None else None
    except (TypeError, ValueError):
        r_m = None
    r_m = r_m if (r_m is not None and math.isfinite(r_m) and r_m > 0.0) else None
    if rr_multiple is not None:
        with contextlib.suppress(TypeError, ValueError):
            r_m = float(rr_multiple)
    stop_px = usable_price_level(stop)
    if base is not None and stop_px is not None and r_m is not None and base > stop_px:
        exit_members["risk_reward_target"] = _member(
            base + r_m * (base - stop_px),
            "OK",
            f"§37: entry + {r_m}*(entry - stop); risk {base - stop_px:.4f}",
        )
    else:
        exit_members["risk_reward_target"] = _absent(
            "needs an entry above a measured stop and a positive reward/risk multiple"
        )

    # A level on the wrong side of the entry is not a level. Every stop must sit
    # below the entry it protects and every target above it; one that does not
    # is refused with the reason rather than printed as usable. The break-even
    # stop is deliberately NOT checked: §56 moves the stop UP once the trade is
    # in profit, so it is above the entry by construction.
    for name in ("volatility_stop", "ATR_stop", "support_stop"):
        exit_members[name] = _refuse_wrong_side(exit_members[name], base, "le", "below")
    for name in ("volatility_target", "risk_reward_target", "technical_target"):
        exit_members[name] = _refuse_wrong_side(exit_members[name], base, "ge", "above")
    # §10's entry sits just ABOVE support, so support must be at or below the
    # reference price for the level to mean anything.
    entry_members["support_entry_price"] = _refuse_wrong_side(
        entry_members["support_entry_price"], ref, "le", "at or below"
    )

    return {"entry": entry_members, "exit": exit_members}


__all__ = [
    "ENTRY_MEMBERS",
    "EXIT_MEMBERS",
    "section_103_members",
    "daily_sigma",
    "support_level",
    "atr_read",
    "member",
]

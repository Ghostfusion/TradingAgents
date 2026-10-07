"""Polymarket prediction-market vendor.

Surfaces live, market-implied probabilities for forward-looking events (Fed
decisions, recession, elections, geopolitics, crypto) to the news analyst, as a
complement to news (what happened) and FRED macro data (where things stand):
what the crowd actually prices to happen next.

Uses Polymarket's public Gamma API (https://gamma-api.polymarket.com) — no key,
no auth. Each market's ``outcomePrices`` are the implied probabilities of its
outcomes (a "Yes" at 0.76 means the market prices a 76% chance).
"""
import json
import logging
import re
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

GAMMA_BASE = "https://gamma-api.polymarket.com"

# Network timeout (seconds), consistent with the other vendors.
REQUEST_TIMEOUT = 30

# Default number of markets to return, ranked by traded volume.
DEFAULT_LIMIT = 6


def _request(path: str, params: dict) -> dict:
    response = requests.get(
        f"{GAMMA_BASE}/{path}", params=params, timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()
    return response.json()


def _parse_json_list(value) -> list:
    """Gamma encodes ``outcomes``/``outcomePrices`` as JSON-string arrays."""
    if isinstance(value, list):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []


def _is_forward_looking(market: dict, now: datetime) -> bool:
    """Keep only open markets that resolve in the future.

    ``closed`` is the reliable resolved flag (``active`` stays True even for
    settled markets), and a past ``endDate`` means the event already resolved —
    either way it is not a forward-looking signal.
    """
    if market.get("closed"):
        return False
    end_date = market.get("endDate")
    if end_date:
        try:
            if datetime.fromisoformat(end_date.replace("Z", "+00:00")) < now:
                return False
        except ValueError:
            pass
    return bool(_parse_json_list(market.get("outcomePrices"))) and bool(
        _parse_json_list(market.get("outcomes"))
    )


_DEADLINE_RE = re.compile(r"\bby\b", re.IGNORECASE)


def _yes_probability(market: dict) -> float | None:
    """The 'Yes' leg's implied probability, or None when unreadable.

    ``outcomes`` and ``outcomePrices`` are parallel JSON arrays; the Yes leg is
    located by NAME rather than assumed at index 0.
    """
    outcomes = _parse_json_list(market.get("outcomes"))
    prices = _parse_json_list(market.get("outcomePrices"))
    if not prices:
        return None
    idx = 0
    for i, name in enumerate(outcomes):
        if str(name).strip().lower() == "yes":
            idx = i
            break
    try:
        return float(prices[idx])
    except (ValueError, IndexError, TypeError):
        return None


def _is_deadline_contract(market: dict) -> bool:
    """A "will X occur BY <date>" contract prices P(by the date), not P(X)."""
    return bool(_DEADLINE_RE.search(str(market.get("question") or "")))


def _implied_median_deadline(
    rungs: list[tuple[str, float]]
) -> tuple[str | None, float | None]:
    """The date at which a cumulative "by DATE" ladder crosses 50%.

    ``rungs`` = ``[(date, P(yes))]`` already sorted by date. The cumulative curve
    is forced non-decreasing first: P(by a later date) cannot sit below P(by an
    earlier one), so a lower later rung is thin-market noise, not a real dip.
    Returns ``(date, cumulative)`` at the first crossing, or ``(None, None)``
    when the ladder never reaches 50%.
    """
    run = 0.0
    for date, prob in rungs:
        run = max(run, prob)
        if run >= 0.5:
            return date, run
    return None, None


def _render_market(unit: dict) -> list[str]:
    """One open market's line; a bare rung is labelled, never shown as the event."""
    market = unit["markets"][0]
    prob = _yes_probability(market)
    if prob is None:
        return []
    question = str(market.get("question") or "").strip()
    volume = market.get("volumeNum") or 0
    end_date = (market.get("endDate") or "")[:10]
    wk = market.get("oneWeekPriceChange")
    wk_str = (
        f", 1-week {wk * 100:+.1f}pp"
        if isinstance(wk, (int, float)) and wk
        else ""
    )
    notes = []
    if _is_deadline_contract(market):
        notes.append(
            f"deadline contract: P(the event occurs BY {end_date}), "
            f"not a point probability of it"
        )
    if unit["n_open"] > 1:
        notes.append(
            f"one of {unit['n_open']} open markets in this event - "
            f"not the event's single probability"
        )
    note_str = f" [{'; '.join(notes)}]" if notes else ""
    return [
        f"- **{question}** — Yes {prob:.0%}{note_str} "
        f"(${volume:,.0f} volume, resolves {end_date}{wk_str})"
    ]


def _render_ladder(unit: dict) -> list[str]:
    """A cumulative "by DATE" ladder: sorted rungs + the implied median deadline."""
    event_title = str(unit["event"].get("title") or "").strip() or "event"
    rungs = sorted(
        (
            (str(m.get("endDate") or "")[:10], _yes_probability(m))
            for m in unit["markets"]
        ),
        key=lambda t: t[0],
    )
    rungs = [r for r in rungs if r[1] is not None]
    if len(rungs) < 2:  # a single readable rung is not a ladder
        return _render_market({**unit, "n_open": 1}) if rungs else []
    median_date, median_prob = _implied_median_deadline(rungs)
    out = [
        f"- **{event_title}** — deadline ladder, {len(rungs)} open rungs "
        f"(each rung prices the event BY its date, so the rungs are cumulative "
        f"rather than mutually exclusive):"
    ]
    run = 0.0
    for date, prob in rungs:
        run = max(run, prob)
        out.append(f"    - by {date}: {prob:.0%} (cumulative {run:.0%})")
    if median_date:
        out.append(
            f"  implied median deadline: {median_date} (cumulative {median_prob:.0%})"
        )
    else:
        out.append("  implied median deadline: none (the ladder never reaches 50%)")
    if any(rungs[i][1] > rungs[i + 1][1] + 1e-9 for i in range(len(rungs) - 1)):
        out.append(
            "  note: a later rung is priced below an earlier one on the raw "
            "quotes (thin market); the cumulative read uses the monotone envelope"
        )
    return out


def get_prediction_markets(topic: str, limit: int | None = None) -> str:
    """Return live prediction-market probabilities for an event topic.

    Args:
        topic: Event keyword(s), e.g. "Fed rate cut", "recession 2026",
            "US election", or a sector/company event.
        limit: Max markets to return (ranked by traded volume); ``None`` uses
            DEFAULT_LIMIT.

    Returns:
        A markdown report of the most-traded open markets matching the topic,
        each with its implied probability, traded volume, resolution date, and
        recent (1-week) move. Markets are grouped by their event: a cumulative
        "will X happen by <date>" ladder is reported as its rungs plus the
        implied median deadline (one rung is never presented as the event's
        probability), and any market is marked as one of its event's open
        markets when the event has several.
    """
    if limit is None:
        limit = DEFAULT_LIMIT

    try:
        data = _request("public-search", {"q": topic, "limit_per_type": 20})
    except requests.RequestException as e:
        logger.warning("Polymarket search failed for %r: %s", topic, e)
        return (
            f"Polymarket data is currently unavailable (network error: {e}). "
            f"Proceed without prediction-market signal for '{topic}'."
        )

    now = datetime.now(timezone.utc)
    # Group by EVENT: the original defect read one rung of a ladder as "the"
    # probability of the topic. Two shapes are distinguished. A DEADLINE LADDER
    # is two or more open markets whose questions all read "by <date>": those
    # rungs are CUMULATIVE, so the event's honest summary is its implied median
    # deadline, not any single rung. Anything else is reported per market,
    # marked as one of the event's open markets when it has several.
    units: list[dict] = []
    for event in data.get("events") or []:
        open_markets = [
            m for m in (event.get("markets") or []) if _is_forward_looking(m, now)
        ]
        if not open_markets:
            continue
        if len(open_markets) >= 2 and all(
            _is_deadline_contract(m) for m in open_markets
        ):
            units.append({
                "kind": "ladder",
                "event": event,
                "markets": open_markets,
                "volume": sum(m.get("volumeNum") or 0 for m in open_markets),
                "n_open": len(open_markets),
            })
        else:
            for m in open_markets:
                units.append({
                    "kind": "market",
                    "event": event,
                    "markets": [m],
                    "volume": m.get("volumeNum") or 0,
                    "n_open": len(open_markets),
                })
    units.sort(key=lambda u: u["volume"], reverse=True)

    header = (
        f'## Polymarket prediction markets: "{topic}"\n'
        f"Live, market-implied probabilities (higher traded volume = deeper, "
        f"more reliable). A probability is the crowd's priced odds of the event, "
        f"not a forecast you should take as certain. A \"by <date>\" ladder is "
        f"cumulative - P(the event by each date) - and is summarised by its "
        f"implied median deadline, not by any single rung.\n\n"
    )

    if not units:
        return header + (
            f"No open prediction markets matched '{topic}'. Polymarket coverage "
            f"is concentrated in macro, political, geopolitical, and crypto "
            f"events; a specific equity may have none."
        )

    lines: list[str] = []
    for unit in units[:limit]:
        lines.extend(
            _render_ladder(unit) if unit["kind"] == "ladder" else _render_market(unit)
        )

    return header + "\n".join(lines) + "\n"

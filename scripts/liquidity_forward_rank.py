#!/usr/bin/env python3
"""X6 - a forward-rank test of the liquidity estimators that already exist.

Card: ``docs/paper_survey_26/implementation_plan_cross_section_and_allocation.md``
section 1, X6. This is a **study**, not a producer: it adds no estimator, no
statistic and no public function to ``tradingagents/``, and nothing in-run may
call it (ground rule 8).

What it asks. The engine already computes ``liquidity_risk.amihud_illiquidity``
and ``liquidity_risk.kyle_lambda`` per name; what it never asks is whether a
per-symbol-month price-impact estimate ranks the **cross-section of subsequent**
returns. This script asks exactly that::

    rank_ic(lambda_month_t, fwd_return_t+1)

with ``signal_analysis.rank_ic`` as the statistic. Both pieces already exist and
each has one producer, so this module computes neither.

The panel. ``--panel`` defaults to the repo's own ``reports/`` tree - one
directory per run, each holding the ``research_decision.json`` the engine wrote -
which is the emitted-decision panel the repo already reads as "the panel". A
``.jsonl`` ledger of the same ``{ticker, effective_date}`` rows is read too. An
empty panel is reported as ``unavailable`` with its reason, never as a zero.

The bars. The two estimators need daily closes **and volumes**; those come from
the engine's own OHLCV chain (``analysis_tools._ohlcv``), the same join
``scripts/alpha_health.py`` uses. A name whose bars cannot be read contributes an
``unavailable`` row, never a substituted one.

The window. Every number names the leg it was computed against. The return leg is
``fwd_return_t+1`` - month-end ``t`` to month-end ``t+1`` - and the estimator
uses month ``t``'s own bars, so the trade-direction input is available at ``t``
(point-in-time). A row whose trade direction cannot be determined (the estimator
returned ``None``: too few usable bars, or a degenerate regression) reads
``unavailable`` - never a substituted value.

Offline: nothing under ``tradingagents/`` imports or calls this module.

Examples::

    py -3.12 scripts/liquidity_forward_rank.py
    py -3.12 scripts/liquidity_forward_rank.py --panel reports --json
    py -3.12 scripts/liquidity_forward_rank.py --panel reports/alpha_ledger.jsonl
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingagents.strategies.liquidity_risk import (  # noqa: E402
    amihud_illiquidity,
    kyle_lambda,
)
from tradingagents.strategies.signal_analysis import rank_ic  # noqa: E402

#: The forward-return leg. ``fwd_return_t+1`` = month-end ``t`` -> month-end
#: ``t+1``; the estimator uses month ``t``'s own bars, so its trade-direction
#: input is available at ``t`` (point-in-time, no look-ahead). The X6
#: failing-first mutation shifts this to the contemporaneous leg (``0``), which
#: is exactly the look-ahead the test guards.
_FORWARD_STEPS = 1

#: ``signal_analysis.rank_ic``'s own floor is 10 observations; a cross-section
#: below it is not a rank IC.
DEFAULT_MIN_NAMES = 10

#: ``liquidity_risk.kyle_lambda``'s minimum usable daily changes, sized for a
#: month of daily bars (~21 rows). Passed through to the estimator; its formula
#: is not touched.
DEFAULT_MIN_OBS = 5

#: The estimator's own window, printed with every table so the number travels
#: with the window it was computed over (ground rule 4).
ESTIMATOR_WINDOW = "month t's own daily bars (amihud_illiquidity / kyle_lambda at t)"

#: The report-panel row the engine writes inside each report tree.
PANEL_ROW_KEY = "research_decision.json"

#: The two estimators the study ranks - both already exist.
ESTIMATORS = ("amihud_illiquidity", "kyle_lambda")


def default_panel_path() -> str:
    """The repo's own reports location - the panel the engine already writes."""
    return str(Path(__file__).resolve().parents[1] / "reports")


def return_leg_name() -> str:
    """The return leg's name, so every record states its own window.

    Reads :data:`_FORWARD_STEPS` at call time: shifting the leg to the
    contemporaneous month renames it too, so a stale label cannot outlive the
    leg it describes.
    """
    if _FORWARD_STEPS == 1:
        return "fwd_return_t+1"
    if _FORWARD_STEPS == 0:
        return "return_t"
    return f"fwd_return_t+{_FORWARD_STEPS}"


def _return_leg_basis() -> str:
    """Plain-language window for the return leg (printed beside its name)."""
    if _FORWARD_STEPS == 1:
        return "month-end t -> month-end t+1"
    if _FORWARD_STEPS == 0:
        return "month-end t-1 -> month-end t"
    return f"month-end t -> month-end t+{_FORWARD_STEPS}"


def _month_key(date) -> str | None:
    """``"YYYY-MM"`` for an ISO date, else ``None`` (a bad date is a gap)."""
    s = str(date or "").strip()
    if len(s) >= 7 and s[:4].isdigit() and s[4] == "-" and s[5:7].isdigit():
        return s[:7]
    return None


def _shift_month(month, steps: int) -> str | None:
    """``month`` moved by ``steps`` calendar months (``None`` on a bad month)."""
    key = _month_key(month)
    if key is None:
        return None
    idx = int(key[:4]) * 12 + (int(key[5:7]) - 1) + int(steps)
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


# ---------------------------------------------------------------------------
# The report panel (what the engine already writes)
# ---------------------------------------------------------------------------


def load_report_panel(path) -> list[dict]:
    """The report panel as ``[{ticker, effective_date}, ...]``.

    ``path`` is either the reports tree root (one directory per run, each
    holding the ``research_decision.json`` the engine writes) or a ``.jsonl``
    ledger of the same rows. A missing or unreadable panel degrades to ``[]`` -
    the caller reports that, never a substituted row.
    """
    p = Path(str(path)).expanduser()
    if p.is_file():
        rows = _rows_from_ledger(p)
    elif p.is_dir():
        rows = _rows_from_trees(p)
    else:
        rows = []
    return _dedupe_rows(rows)


def _rows_from_ledger(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    out: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            doc = json.loads(line)
        except ValueError:
            continue
        if isinstance(doc, dict):
            out.append(doc)
    return out


def _rows_from_trees(root: Path) -> list[dict]:
    try:
        trees = sorted(d for d in root.iterdir() if d.is_dir())
    except OSError:
        return []
    out: list[dict] = []
    for tree in trees:
        f = tree / PANEL_ROW_KEY
        if not f.is_file():
            continue
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(doc, dict):
            out.append(doc)
    return out


def _dedupe_rows(rows) -> list[dict]:
    """``{ticker, effective_date}`` rows, deduped by ``(ticker, date)``."""
    seen: dict[tuple[str, str], dict] = {}
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        ticker = str(r.get("ticker") or "").strip().upper()
        date = str(r.get("effective_date") or "").strip()
        if not ticker or not date:
            continue
        seen[(ticker, date)] = {"ticker": ticker, "effective_date": date}
    return [seen[k] for k in sorted(seen)]


# ---------------------------------------------------------------------------
# The bars (the engine's own OHLCV chain)
# ---------------------------------------------------------------------------


def default_bars_fetcher():
    """The engine's own OHLCV chain - the one producer of daily bars here."""
    from tradingagents.agents.utils.analysis_tools import _ohlcv

    return _ohlcv


def _bars_in_month(bars: dict, month: str) -> tuple[list, list]:
    """``(closes, volumes)`` of the bars dated inside ``month``.

    Bars are aligned on the shortest of the three series (never padded): a
    missing or misaligned volume leg leaves the estimator without a
    trade-direction input, which is an ``unavailable`` row, not a guess.
    """
    if not isinstance(bars, dict):
        return [], []
    dates = list(bars.get("dates") or [])
    closes = list(bars.get("closes") or [])
    volumes = list(bars.get("volumes") or [])
    n = min(len(dates), len(closes), len(volumes))
    out_c: list = []
    out_v: list = []
    for i in range(n):
        if _month_key(dates[i]) == month:
            out_c.append(closes[i])
            out_v.append(volumes[i])
    return out_c, out_v


def _month_end_close(bars: dict, month) -> float | None:
    """The last close dated inside ``month`` (``None`` when there is none)."""
    if not isinstance(bars, dict) or month is None:
        return None
    dates = list(bars.get("dates") or [])
    closes = list(bars.get("closes") or [])
    n = min(len(dates), len(closes))
    last = None
    for i in range(n):
        if _month_key(dates[i]) == month:
            last = closes[i]
    try:
        value = float(last)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) and value > 0 else None


def _observation(bars, month: str, *, min_obs: int) -> dict:
    """One symbol-month: the two estimators at ``t`` and the forward-return leg."""
    closes, volumes = _bars_in_month(bars, month)
    amihud = amihud_illiquidity(closes, volumes)
    kyle = kyle_lambda(closes, volumes, min_obs=int(min_obs))
    leg = return_leg_name()
    start = _shift_month(month, _FORWARD_STEPS - 1)
    end = _shift_month(month, _FORWARD_STEPS)
    c0 = _month_end_close(bars, start)
    c1 = _month_end_close(bars, end)
    fwd = (c1 / c0 - 1.0) if (c0 is not None and c1 is not None) else None
    reasons = []
    if amihud is None:
        reasons.append("amihud_illiquidity: fewer than 2 usable bars in month t")
    if kyle is None:
        reasons.append(
            f"kyle_lambda: trade direction undetermined (< {int(min_obs) + 1} "
            "usable bars, or a degenerate regression)"
        )
    if fwd is None:
        reasons.append(f"{leg}: no month-end close for {start} -> {end}")
    return {
        "month": month,
        "amihud_illiquidity": amihud,
        "kyle_lambda": kyle,
        "forward_return": fwd,
        "status": "ok" if not reasons else "unavailable",
        "reasons": reasons,
    }


# ---------------------------------------------------------------------------
# The numbers-of-record table
# ---------------------------------------------------------------------------


def forward_rank_table(
    panel_rows,
    bars_for,
    *,
    min_obs: int = DEFAULT_MIN_OBS,
    min_names: int = DEFAULT_MIN_NAMES,
    months=None,
) -> dict:
    """One ``rank_ic`` row per symbol-month, over the panel's own cross-sections.

    ``panel_rows`` is the report panel (``[{ticker, effective_date}, ...]``);
    ``bars_for(ticker) -> {dates, closes, volumes}`` supplies the daily bars.
    The table names its own window, and a row that cannot be computed reads
    ``unavailable`` with its reason - never a zero, never a substituted value.
    """
    leg = return_leg_name()
    table_out: dict = {
        "study": "X6 forward-rank test of the existing liquidity estimators",
        "window": {
            "estimator": ESTIMATOR_WINDOW,
            "return": leg,
            "return_basis": _return_leg_basis(),
            "steps": int(_FORWARD_STEPS),
            "months": [],
        },
        "estimators": list(ESTIMATORS),
        "min_names": int(min_names),
        "min_obs": int(min_obs),
        "n_panel_rows": 0,
        "n_symbols": 0,
        "n_months": 0,
        "table": [],
        "observations": [],
        "status": "unavailable",
        "reason": "no panel rows",
    }

    rows = [r for r in (panel_rows or []) if isinstance(r, dict)]
    by_month: dict[str, list[str]] = {}
    for r in rows:
        month = _month_key(r.get("effective_date"))
        ticker = str(r.get("ticker") or "").strip().upper()
        if month is None or not ticker:
            continue
        names = by_month.setdefault(month, [])
        if ticker not in names:
            names.append(ticker)
    if months:
        keep = {str(m) for m in months}
        by_month = {m: names for m, names in by_month.items() if m in keep}

    table_out["n_panel_rows"] = len(rows)
    table_out["n_symbols"] = len({t for names in by_month.values() for t in names})
    table_out["n_months"] = len(by_month)
    if not by_month:
        table_out["reason"] = "the report panel carries no (ticker, effective_date) rows"
        if months:
            table_out["reason"] += f" for months {sorted(str(m) for m in months)}"
        return table_out

    cache: dict[str, dict] = {}

    def _bars(ticker: str) -> dict:
        if ticker not in cache:
            try:
                cache[ticker] = bars_for(ticker) or {}
            except Exception:  # noqa: BLE001 - one name's failure is one gap
                cache[ticker] = {}
        return cache[ticker]

    table_out["window"]["months"] = sorted(by_month)
    observations: list[dict] = []
    for month in sorted(by_month):
        obs = []
        for ticker in sorted(by_month[month]):
            row = _observation(_bars(ticker), month, min_obs=int(min_obs))
            row["ticker"] = ticker
            obs.append(row)
        observations.extend(obs)

        ranked = [o for o in obs if o["status"] == "ok"]
        entry: dict = {
            "month": month,
            "return_leg": leg,
            "n_names": len(obs),
            "n_ranked": len(ranked),
            "n_unavailable": len(obs) - len(ranked),
        }
        any_ok = False
        for name in ESTIMATORS:
            usable = [o for o in ranked if o.get(name) is not None]
            signals = [o[name] for o in usable]
            forwards = [o["forward_return"] for o in usable]
            ic = (
                rank_ic(signals, forwards, min_obs=int(min_names))
                if len(signals) >= int(min_names)
                else None
            )
            entry[f"{name}_rank_ic"] = ic
            any_ok = any_ok or ic is not None
        entry["status"] = "ok" if any_ok else "unavailable"
        if not any_ok:
            entry["reason"] = (
                f"{len(ranked)} rankable symbol-month(s) < min_names={int(min_names)}"
                if len(ranked) < int(min_names)
                else "rank_ic degenerate on this cross-section"
            )
        table_out["table"].append(entry)

    table_out["observations"] = observations
    if any(e["status"] == "ok" for e in table_out["table"]):
        table_out["status"] = "ok"
        table_out["reason"] = ""
    else:
        table_out["reason"] = "no symbol-month cross-section produced a rank_ic"
    return table_out


def render_text(table: dict) -> str:
    """The numbers-of-record table as text (its window first)."""
    w = table.get("window") or {}
    lines = [
        "X6 forward-rank test - liquidity estimators vs subsequent returns",
        "=" * 72,
        f"estimator window : {w.get('estimator')}",
        f"return window    : {w.get('return')}  ({w.get('return_basis')})",
        f"months           : {', '.join(w.get('months') or []) or '(none)'}",
        f"panel rows       : {table.get('n_panel_rows')}  "
        f"symbols: {table.get('n_symbols')}  months: {table.get('n_months')}",
        "",
        f"{'month':<9}{'n':>4}{'ranked':>8}{'amihud_rank_ic':>17}{'kyle_rank_ic':>15}  status",
    ]
    for row in table.get("table") or []:
        a = row.get("amihud_illiquidity_rank_ic")
        k = row.get("kyle_lambda_rank_ic")
        lines.append(
            f"{str(row.get('month')):<9}{row.get('n_names'):>4}{row.get('n_ranked'):>8}"
            f"{(f'{a:+.4f}' if a is not None else 'unavailable'):>17}"
            f"{(f'{k:+.4f}' if k is not None else 'unavailable'):>15}"
            f"  {row.get('status')}"
            + (f" ({row.get('reason')})" if row.get("reason") else "")
        )
    if table.get("status") != "ok":
        lines.append("")
        lines.append(f"unavailable: {table.get('reason')}")
    lines.append("")
    lines.append(
        "Advisory study: a forward-rank read of an estimator that already exists; "
        "never a gate, and nothing in-run calls it."
    )
    return "\n".join(lines)


def main(argv=None) -> int:
    doc = (__doc__ or "").splitlines()
    ap = argparse.ArgumentParser(description=doc[0] if doc else "X6 forward-rank study")
    ap.add_argument(
        "--panel", default=default_panel_path(),
        help="report panel root (reports/) or a .jsonl ledger of {ticker, effective_date}",
    )
    ap.add_argument("--months", nargs="*", default=None, help="month filter (YYYY-MM)")
    ap.add_argument(
        "--min-names", type=int, default=DEFAULT_MIN_NAMES,
        help="cross-section floor for a rank_ic",
    )
    ap.add_argument(
        "--min-obs", type=int, default=DEFAULT_MIN_OBS,
        help="kyle_lambda's minimum usable daily changes",
    )
    ap.add_argument("--json", action="store_true", help="emit the table as JSON")
    args = ap.parse_args(argv)

    panel = load_report_panel(args.panel)
    table = forward_rank_table(
        panel,
        default_bars_fetcher(),
        min_obs=args.min_obs,
        min_names=args.min_names,
        months=args.months,
    )
    table["panel_path"] = str(args.panel)
    if args.json:
        print(json.dumps(table, indent=2, default=str))
    else:
        print(render_text(table))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

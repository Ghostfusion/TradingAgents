#!/usr/bin/env python3
"""PLAN-4 - the evaluation CLI over a cached WP-10 panel.

A **caller, not a second implementation**. It loads the cached panels with
``scripts/score_panel.py::load_panel_series`` and reports every row the
measurement layer already produces by calling
``scripts/score_panel.py::evaluate_panel`` (which in turn runs
``alpha_health.score_evaluation_rows`` and the multiple-testing machinery in
``strategies.evaluate``) and rendering it with
``scripts/score_panel.py::render_text``. No statistic is recomputed here, and no
weight vector is invented: the vectors printed are the engines' own declared
tables beside their measured evidence.

Per factor the report carries the harness rows the WP-10 deliverable names - IC,
rank IC, ICIR, decile spread, monotonicity, turnover and persistence - plus the
OOS split, the multiple-testing checks, the redundancy block, and, via
``evaluate_panel``, the **sector and regime robustness splits** (PLAN-6 / MF-3)
and the **technical category correlation matrix** (TECH-24).

The panel is read-only here: the script fetches nothing, so it makes **zero**
network calls. A date with no cached panel file is simply absent, and the split
axes are supplied as JSON maps (``--sector-map`` / ``--regime-map``); with no
sector map the repo's own static curated constituent map supplies the labels it
can prove, and with no regime map every date is unlabelled and that split is
withheld with its reason rather than guessed (master rule 1: NA != 0).

Examples::

    py -3.12 scripts/score_panel_eval.py \\
        --dates 2026-08-06,2026-08-07,2026-08-10 --symbols-file sp500.txt
    py -3.12 scripts/score_panel_eval.py --dates-file trading_dates.txt --json
    py -3.12 scripts/score_panel_eval.py --dates ... --sector-map sectors.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.score_panel import (  # noqa: E402
    OOS_TRAIN_FRAC,
    SPLIT_MIN_NAMES,
    SPLIT_MIN_PERIODS,
    _read_list,
    default_cache_dir,
    evaluate_panel,
    load_panel_series,
    panel_path,
    read_label_map,
    render_text,
)


def evaluate_cached_panel(cache_dir: str, dates, universe=None, *,
                          sector_of=None, regime_of=None, holding: int = 5,
                          n_buckets: int = 10, train_frac: float = OOS_TRAIN_FRAC,
                          cpcv_splits: int = 5, embargo: int = 0, seed: int = 0,
                          n_boot: int = 500, split_min_names: int = SPLIT_MIN_NAMES,
                          split_min_periods: int = SPLIT_MIN_PERIODS,
                          registry=None) -> dict | None:
    """The cached-panel report, or ``None`` when no date has a panel file.

    The one call site of ``score_panel.evaluate_panel`` for this CLI: it does the
    cache read and hands the panels to the harness unchanged, so the rows this
    script prints are the harness' own (no second statistic).
    """
    panels = load_panel_series(dates, universe, cache_dir=cache_dir)
    if not panels:
        return None
    return evaluate_panel(
        panels, dates=list(dates), registry=registry, holding=holding,
        n_buckets=n_buckets, train_frac=train_frac, cpcv_splits=cpcv_splits,
        embargo=embargo, seed=seed, n_boot=n_boot, sector_of=sector_of,
        regime_of=regime_of, split_min_names=split_min_names,
        split_min_periods=split_min_periods,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dates", default=None, help="comma-separated trading dates")
    parser.add_argument("--dates-file", default=None, help="one date per line")
    parser.add_argument("--symbols", default=None, help="comma-separated filter")
    parser.add_argument("--symbols-file", default=None,
                        help="one symbol per line (a filter over the cached rows)")
    parser.add_argument("--cache-dir", default=None,
                        help="default: the configured data_cache_dir (then "
                             "<cache-dir>/panels/<date>.json)")
    parser.add_argument("--sector-map", default=None,
                        help="JSON {ticker: sector} for the sector split; default: "
                             "the repo's static curated constituent map")
    parser.add_argument("--regime-map", default=None,
                        help="JSON {date: regime} for the regime split; the panel "
                             "carries no market-level regime series")
    parser.add_argument("--holding", type=int, default=5)
    parser.add_argument("--buckets", type=int, default=10)
    parser.add_argument("--train-frac", type=float, default=OOS_TRAIN_FRAC)
    parser.add_argument("--cpcv-splits", type=int, default=5)
    parser.add_argument("--embargo", type=int, default=0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--n-boot", type=int, default=500)
    parser.add_argument("--split-min-names", type=int, default=SPLIT_MIN_NAMES)
    parser.add_argument("--split-min-periods", type=int, default=SPLIT_MIN_PERIODS)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    dates = [d[:10] for d in _read_list(args.dates_file, args.dates)]
    if not dates:
        parser.error("--dates or --dates-file is required")
        return 2
    universe = _read_list(args.symbols_file, args.symbols)
    cache_dir = args.cache_dir or default_cache_dir()
    sector_of = read_label_map(args.sector_map)
    regime_of = read_label_map(args.regime_map)

    report = evaluate_cached_panel(
        cache_dir, dates, universe, sector_of=sector_of, regime_of=regime_of,
        holding=args.holding, n_buckets=args.buckets, train_frac=args.train_frac,
        cpcv_splits=args.cpcv_splits, embargo=args.embargo, seed=args.seed,
        n_boot=args.n_boot, split_min_names=args.split_min_names,
        split_min_periods=args.split_min_periods,
    )
    if report is None:
        print(f"no cached panel for {dates} under "
              f"{panel_path(cache_dir, dates[0])} - build one with "
              "scripts/score_panel.py first")
        return 1
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(render_text(report))
        print("\n(evaluate-only: the cache was read, nothing was fetched)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["evaluate_cached_panel", "main"]

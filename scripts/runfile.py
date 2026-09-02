"""Declarative run YAML front-end + recorder-style experiment ledger.

Qlib pillars 2 + 17 port (``qrun`` init-by-config + mlflow-style recorder):

- ``runfile.py --runfile <yaml>`` expands a declarative runfile 1:1 to the
  existing ``pipeline.py`` CLI args (no new execution path). ``--dry-run``
  prints the expanded argv without running anything.
- The experiment ledger appends one JSONL row per run under
  ``data_cache_dir/experiments/`` (home cache -> gitignored by location):
  ``{run_id, config_hash, params, metrics, status, artifact}`` with raw data
  referenced by path only. ``status`` lifecycle pending/done/failed with
  O_APPEND single-line writes (Windows-safe, no new deps).

Runfile schema (all optional; defaults match ``pipeline.py``):
    universe: {file: path | tickers: [..], top: 5, limit: 0,
               min_mcap: 1e10, price_min: 15, pe_max: 40}
    date: 2026-09-02
    vendor: moomoo | yfinance | eodhd
    analysts: [..]              # subset of pipeline ALL_ANALYSTS
    depth: deep | light
    workers: 3
    movers: {count: 50, direction: losers}
    stages: {fit: {start, end}, valid: {start, end}, test: {start, end}}
    factor_model: {enable: false}
    tools: [..]                 # pass-through, advisory

Usage:
    py -3.12 scripts/runfile.py --runfile runs/nightly.yaml --dry-run
    py -3.12 scripts/runfile.py --runfile runs/nightly.yaml
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import yaml
except ImportError:  # pragma: no cover - env without pyyaml
    yaml = None  # type: ignore[assignment]


_MOVERS_DIRECTIONS = ("gainers", "losers")
_VENDORS = ("default", "moomoo", "yfinance", "eodhd")
_DEPTHS = ("deep", "light")


def _default_ledger_dir() -> str:
    try:
        from tradingagents.dataflows.config import get_config

        return os.path.join(str(get_config().get("data_cache_dir") or "~/.tradingagents/cache"),
                            "experiments")
    except Exception:  # noqa: BLE001
        return os.path.join(os.path.expanduser("~/.tradingagents/cache"), "experiments")


def config_hash(params: dict) -> str:
    """Stable sha1 over a canonicalized param dict (reproducibility key)."""
    blob = json.dumps(params, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]


def load_runfile(path: str) -> dict:
    """Parse a runfile YAML; raises on missing file / bad YAML."""
    if yaml is None:
        raise RuntimeError("pyyaml is required for runfile support (pip install pyyaml)")
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: runfile must be a mapping")
    return data


def runfile_to_argv(runfile: dict) -> list[str]:
    """Expand a runfile dict to an argv list for ``pipeline.main``.

    1:1 to the verified ``pipeline.py`` argparse surface; unknown keys are
    ignored (advisory pass-through). Returns the argv WITHOUT the program
    name (caller prepends as needed).
    """
    argv: list[str] = []
    universe = runfile.get("universe") or {}
    file_v = universe.get("file") if isinstance(universe, dict) else None
    tickers = universe.get("tickers") if isinstance(universe, dict) else None
    if file_v:
        argv += ["-f", str(file_v)]
    elif tickers:
        argv += [str(t) for t in tickers]
    if isinstance(universe, dict) and universe.get("universe"):
        argv += ["-u", str(universe["universe"])]
    if isinstance(universe, dict) and universe.get("top"):
        argv += ["--top", str(universe["top"])]
    if isinstance(universe, dict) and universe.get("limit"):
        argv += ["--limit", str(universe["limit"])]
    if isinstance(universe, dict) and universe.get("min_mcap") is not None:
        argv += ["--min-mcap", str(universe["min_mcap"])]
    if isinstance(universe, dict) and universe.get("price_min") is not None:
        argv += ["--price-min", str(universe["price_min"])]
    if isinstance(universe, dict) and universe.get("pe_max") is not None:
        argv += ["--pe-max", str(universe["pe_max"])]
    if runfile.get("date"):
        argv += ["-d", str(runfile["date"])]
    if runfile.get("vendor") and runfile["vendor"] in _VENDORS:
        argv += ["--vendor", str(runfile["vendor"])]
    if runfile.get("analysts"):
        argv += ["--analysts"] + [str(a) for a in runfile["analysts"]]
    if runfile.get("depth") and runfile["depth"] in _DEPTHS:
        argv += ["--depth", str(runfile["depth"])]
    if runfile.get("workers"):
        argv += ["--workers", str(runfile["workers"])]
    movers = runfile.get("movers") or {}
    if isinstance(movers, dict) and movers.get("count"):
        argv += ["-n", str(movers["count"])]
    if isinstance(movers, dict) and movers.get("direction") in _MOVERS_DIRECTIONS:
        argv += ["--movers-direction", str(movers["direction"])]
    return argv


def _params_from_runfile(runfile: dict) -> dict:
    return {
        "universe": runfile.get("universe"),
        "date": runfile.get("date"),
        "vendor": runfile.get("vendor"),
        "depth": runfile.get("depth"),
        "analysts": runfile.get("analysts"),
        "workers": runfile.get("workers"),
        "stages": runfile.get("stages"),
        "factor_model": runfile.get("factor_model"),
        "tools": runfile.get("tools"),
    }


def ledger_append(row: dict, ledger_dir: str | None = None) -> str | None:
    """Append one experiment row (single-line O_APPEND); returns its path."""
    d = ledger_dir or _default_ledger_dir()
    try:
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, "experiments.jsonl")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        return path
    except OSError:
        return None


def new_run_id() -> str:
    import time

    return f"{date.today().strftime('%Y%m%d')}_{int(time.time())}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runfile", required=True, help="path to the run YAML")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the expanded pipeline argv without running")
    parser.add_argument("--ledger", default=None,
                        help="ledger dir override (default: config data_cache_dir/experiments); 'off' disables")
    parser.add_argument("--run-id", default=None, help="explicit run id (default: timestamp)")
    args = parser.parse_args(argv)

    try:
        runfile = load_runfile(args.runfile)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"[err] runfile: {exc}")
        return 2

    argv = runfile_to_argv(runfile)
    params = _params_from_runfile(runfile)
    run_id = args.run_id or new_run_id()
    c_hash = config_hash(params)

    if args.dry_run:
        print("run_id:", run_id)
        print("config_hash:", c_hash)
        print("argv: " + " ".join(["pipeline.py"] + argv))
        return 0

    if args.ledger != "off":
        ledger_append({
            "run_id": run_id,
            "config_hash": c_hash,
            "params": params,
            "metrics": None,
            "status": "pending",
            "artifact": {"runfile": os.path.abspath(args.runfile)},
        }, args.ledger)

    # In-process expansion: import pipeline's main with the expanded argv.
    try:
        import pipeline as pipeline_mod
    except Exception as exc:  # noqa: BLE001
        print(f"[err] importing pipeline: {exc}")
        return 3

    code = pipeline_mod.main([a if a.startswith("-") else a for a in argv])
    if args.ledger != "off":
        ledger_append({
            "run_id": run_id,
            "config_hash": c_hash,
            "params": params,
            "metrics": {"exit_code": code},
            "status": "done" if code == 0 else "failed",
            "artifact": {"runfile": os.path.abspath(args.runfile)},
        }, args.ledger)
    return code


if __name__ == "__main__":
    raise SystemExit(main())

"""R2/R4 helpers + report script (risk audit summary)."""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def audit_summary(entries: list) -> dict:
    """Summarize risk_audit.jsonl entries: verdict counts + limit hits."""
    counts = {}
    hits = []
    for e in entries:
        verdict = e.get("verdict", "?")
        counts[verdict] = counts.get(verdict, 0) + 1
        for r in e.get("reasons") or []:
            if r not in hits:
                hits.append(r)
    return {"counts": counts, "total": len(entries), "limit_hits": hits}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", default=None, help="path to risk_audit.jsonl")
    args = parser.parse_args(argv)
    path = args.audit
    if path is None:
        try:
            from tradingagents.default_config import DEFAULT_CONFIG as cfg

            base = Path(cfg.get("data_cache_dir", "~/.tradingagents")).expanduser()
            path = str(base / "risk_audit.jsonl")
        except Exception:
            path = str(Path.home() / ".tradingagents" / "risk_audit.jsonl")
    entries = []
    p = Path(path)
    if p.exists():
        for ln in p.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                with contextlib.suppress(Exception):
                    entries.append(json.loads(ln))
    summary = audit_summary(entries)
    print(f"audit: {path}")
    print(f"entries: {summary['total']}")
    for verdict, n in sorted(summary["counts"].items()):
        print(f"  {verdict}: {n}")
    if summary["limit_hits"]:
        print("limit hits:")
        for h in summary["limit_hits"][:10]:
            print(f"  - {h}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

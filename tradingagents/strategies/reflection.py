"""Phase 5 - analyst memory & post-trade reflection.

A small JSON-backed ledger per analyst:

  - record_outcome(analyst, ticker, trade_date, delta_r): debit/credit the
    analyst after realized outcomes (delta_r = realized vs benchmark return).
  - score(analyst): weighted hit-rate with recency decay.
  - reflection_hint(analyst): a short critique line (what to re-check next).
  - recent_tickers(limit): most recent tickers (episodic recall stub).

Wire-up: the memory-log realized-return path already persists per ticker;
this module turns outcomes into analyst-level feedback that is injected into
the analyst prompt under config flag enable_reflection.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

_HALF_LIFE_S = 60 * 60 * 24 * 30.0  # one month


class ReflectionLedger(object):
    """JSON-lines backed analyst performance ledger."""

    def __init__(self, path: "str | None" = None):
        self.path = Path(path) if path else None
        self.entries: list = []
        self.scores: dict = {}
        if self.path and self.path.exists():
            try:
                self.entries = [json.loads(ln) for ln in
                                self.path.read_text(encoding="utf-8").splitlines()
                                if ln.strip()]
            except Exception:
                self.entries = []
        self._recompute_scores()

    def _recompute_scores(self):
        now = time.time()
        self.scores = {}
        for e in self.entries:
            analyst = e.get("analyst") or "?"
            delta = e.get("delta_r", 0.0)
            age = max(0.0, now - e.get("ts", now))
            weight = 0.5 ** (age / _HALF_LIFE_S)
            won, total = self.scores.get(analyst, [0.0, 0.0])
            self.scores[analyst] = [
                won + (weight if delta > 0 else 0.0),
                total + weight,
            ]

    def record_outcome(self, analyst: str, ticker: str, trade_date: str,
                       delta_r: float) -> None:
        entry = {
            "analyst": analyst, "ticker": ticker, "trade_date": trade_date,
            "delta_r": round(float(delta_r), 6), "ts": time.time(),
        }
        self.entries.append(entry)
        if self.path:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
        self._recompute_scores()

    def score(self, analyst: str) -> "float | None":
        won, total = self.scores.get(analyst, [0.0, 0.0])
        return won / total if total > 0 else None

    def hits(self, analyst: str) -> int:
        return sum(1 for e in self.entries
                   if e.get("analyst") == analyst and e.get("delta_r", 0.0) > 0)

    def total(self, analyst: str) -> int:
        return sum(1 for e in self.entries if e.get("analyst") == analyst)

    def reflection_hint(self, analyst: str, baseline: float = 0.5) -> str:
        if self.total(analyst) == 0:
            return "no verified track record yet; stay cautious."
        s = self.score(analyst)
        if s is not None and s >= baseline:
            return "verify winners: was the call thesis repeatable (avoid edge cases)?"
        return ("critique: the strongest prior call failed to realize - "
                "re-check timing and data source before trusting this signal.")

    def recent_tickers(self, limit: int = 10) -> list:
        out: list = []
        for e in reversed(self.entries):
            t = e.get("ticker")
            if t and t not in out:
                out.append(t)
            if len(out) >= limit:
                break
        return out

    def recall(self, ticker: str, limit: int = 5) -> list:
        """Episodic recall: recent tickers sharing the same analyst sessions."""
        return self.recent_tickers(limit=limit)


def build_reflection_context(store: ReflectionLedger, analysts: list) -> str:
    """Prompt fragment summarizing each analyst's score and hint."""
    lines = []
    for a in analysts:
        s = store.score(a)
        score_str = "n/a" if s is None else f"{s:.2f}"
        lines.append(f"- {a}: score={score_str} ({store.hits(a)}/{store.total(a)}), "
                     f"hint: {store.reflection_hint(a)}")
    return "\n".join(lines) if lines else "(no reflection history)"


__all__ = ["ReflectionLedger", "build_reflection_context"]

#!/usr/bin/env python3
"""Conditional action report: check report verdicts against the risk basket
and report which conditions are met by the live market.

Design (user spec):
- **Basket names** (``TRADINGAGENTS_RISK_BASKET_WEIGHTS`` in .env, parsed by
  ``default_config.risk_basket_weights``): take the *newest* report per
  symbol; keep it when the verdict is **Underweight / Sell** (reduce/trim
  action). Check whether the report's stated condition (re-entry level, trim
  zone, stop) is met by the live market.
- **Non-basket names**: take the *newest* report per symbol; keep it when the
  verdict is **Overweight / Buy** (add action). Check whether the entry /
  scale-in condition is met.
- Output: a final action report — per symbol, the condition, the deterministic
  MET / NOT_MET / UNKNOWN verdict, the sub-checks, and the action
  (ADD/BUY, TRIM/REDUCE, or MONITOR).

No-fabrication contract (project rule): every check is computed from live
OHLCV via the vendor chain; a condition the checker cannot resolve renders
UNKNOWN with the reason — never an estimate. The optional ``--llm`` flag
invokes a deep-think judge for UNKNOWN conditions (advisory only; the
deterministic verdict is never downgraded).

Examples:
    py -3.12 scripts/action_report.py
    py -3.12 scripts/action_report.py --json
    py -3.12 scripts/action_report.py --llm            # judge UNKNOWN conditions
    py -3.12 scripts/action_report.py --basket AAPL=0.1,MSFT=0.2
    py -3.12 scripts/action_report.py --reports-dir reports --out-dir action_reports

Exit codes: 0 ok, 2 no reports found.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# Basket
# ---------------------------------------------------------------------------


def load_basket(override: str | None = None) -> dict:
    """Basket weights {SYMBOL: weight} from config ``risk_basket_weights``
    (parsed from TRADINGAGENTS_RISK_BASKET_WEIGHTS) or a ``SYM=W,SYM=W``
    override string."""
    if override:
        out = {}
        for part in override.split(","):
            part = part.strip()
            if not part:
                continue
            k, _, v = part.partition("=")
            out[k.strip().upper()] = float(v.strip())
        return out
    try:
        from tradingagents.default_config import DEFAULT_CONFIG

        return {
            str(k).upper(): float(v)
            for k, v in (DEFAULT_CONFIG.get("risk_basket_weights") or {}).items()
        }
    except Exception:  # noqa: BLE001 - empty basket degrades to no basket
        return {}


# ---------------------------------------------------------------------------
# Report discovery + parsing
# ---------------------------------------------------------------------------

_FOLDER_RE = re.compile(r"^([A-Za-z0-9.\-]+)_(\d{8})_(\d{6})$")


def discover_reports(reports_root: str) -> dict:
    """Newest report folder per symbol (by folder-name timestamp).

    Returns {SYMBOL: Path}. A symbol's folder name is ``<SYM>_YYYYMMDD_HHMMSS``;
    the newest is the one with the largest timestamp string.
    """
    root = Path(reports_root)
    out: dict = {}
    if not root.is_dir():
        return out
    for folder in root.iterdir():
        if not folder.is_dir():
            continue
        m = _FOLDER_RE.match(folder.name)
        if not m:
            continue
        sym = m.group(1).upper()
        stamp = m.group(2) + m.group(3)
        if sym not in out or stamp > out[sym][0]:
            out[sym] = (stamp, folder)
    return {s: p for s, (_, p) in out.items()}


def _folder_date(name: str) -> str:
    m = re.search(r"_(\d{8})_\d{6}$", name)
    if not m:
        return ""
    s = m.group(1)
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}"


def _first_number(text: str) -> float | None:
    m = re.search(r"\d+(?:\.\d+)?", text or "")
    return float(m.group(0)) if m else None


def parse_decision(md: str) -> dict:
    """Extract the decision fields from a 5_portfolio/decision.md."""
    out = {
        "rating": "n/a",
        "position_size": "",
        "exec_summary": "",
        "stop_loss": None,
        "price_target": None,
    }
    try:
        from tradingagents.agents.utils.rating import parse_rating

        out["rating"] = parse_rating(md, default="n/a")
    except Exception:  # noqa: BLE001
        pass

    def field(name: str) -> str:
        m = re.search(rf"^\*\*{re.escape(name)}\*\*[:\s]*(.*)$", md, re.M)
        return m.group(1).strip() if m else ""

    out["position_size"] = field("Position Size")
    out["exec_summary"] = field("Executive Summary")
    out["stop_loss"] = _first_number(field("Stop Loss"))
    out["price_target"] = _first_number(field("Price Target"))
    return out


def classify(symbol: str, rating: str, basket: dict) -> str | None:
    """'basket-underweight' | 'non-basket-overweight' | None.

    Buy == Overweight, Sell == Underweight (user rule). Basket names are kept
    on Underweight/Sell (reduce); non-basket names on Overweight/Buy (add).
    """
    r = (rating or "").lower()
    if symbol in basket:
        return "basket-underweight" if r in ("underweight", "sell") else None
    return "non-basket-overweight" if r in ("overweight", "buy") else None


# ---------------------------------------------------------------------------
# Condition extraction
# ---------------------------------------------------------------------------

_TRIGGER_KEYWORDS = (
    "only on", "only if", "re-enter", "reenter", "re-add", "readd",
    "scale", "trigger", "confirmation", "when", "once", "unless",
    "provided", "add only", "trim", "reduce", "reclaim", "breakout",
    "pullback", "test of", "stabilization", "re-entry", "reentry",
)

# Phrases that introduce the *trigger* clause (the condition for the action).
# Specific phrases are tried first; generic ones (trim/reduce/scale/pullback/
# breakout) only when no specific trigger is found, so a Position Size line's
# action description ("reduce to ~half ... capped by the $156.75 stop") doesn't
# shadow the real re-entry clause.
_TRIGGER_PHRASES_SPECIFIC = (
    "only on", "only if", "re-enter", "reenter", "re-add", "readd",
    "add only", "on confirmation", "trigger", "unless", "provided",
    "reclaim", "test of", "stabilization",
)
_TRIGGER_PHRASES_GENERIC = (
    "trim", "reduce", "scale", "pullback", "breakout",
)


def _trigger_clauses(text: str, phrases: tuple[str, ...]) -> list[str]:
    """Clauses from each trigger phrase to the end of its sentence, deduped
    by overlap (a later phrase inside an already-captured clause is skipped).
    Prohibition clauses ("do not chase ...") and clauses with no condition
    indicators are dropped."""
    clauses: list[str] = []
    ranges: list[tuple[int, int]] = []
    pattern = "|".join(re.escape(p) for p in phrases)
    for m in re.finditer(pattern, text, re.I):
        if any(m.start() < r[1] for r in ranges):
            continue
        # Sentence end = the next period followed by whitespace/end (a decimal
        # point like "$158.10" is followed by a digit or bracket, not a space).
        tail = text[m.start():]
        m_end = re.search(r"\.(?=\s|$)", tail)
        end = m.start() + m_end.start() + 1 if m_end else len(text)
        clause = text[m.start():end].strip()
        if not clause:
            continue
        low = clause.lower()
        if re.search(r"do not|don't|avoid|never", low):
            continue
        if not _looks_like_condition(clause):
            continue
        clauses.append(clause)
        ranges.append((m.start(), end))
    return clauses


def _level_sig(clause: str) -> set:
    """Set of price levels in a clause (ranges as (lo, hi), singles as
    (v, v)), ignoring direction and stop/ATR levels — used to dedup clauses
    that restate the same trigger with different wording."""
    sig = set()
    for lvl in _extract_levels(clause):
        if _is_stop_level(clause, lvl):
            continue
        if lvl["type"] == "range":
            sig.add((round(lvl["lo"], 2), round(lvl["hi"], 2)))
        else:
            v = round(lvl["value"], 2)
            sig.add((v, v))
    return sig


def extract_condition(decision: dict) -> str:
    """The trigger clause(s) for the action, collected from both the Position
    Size line and the Executive Summary (deduped). Specific trigger phrases
    ("only on X", "re-enter at X") are preferred; generic ones (trim/reduce/
    scale) are used only when no specific trigger exists."""
    sources = ((decision.get("position_size") or ""), (decision.get("exec_summary") or ""))
    clauses: list[str] = []
    for src in sources:
        clauses += _trigger_clauses(src, _TRIGGER_PHRASES_SPECIFIC)
    if not clauses:
        for src in sources:
            clauses += _trigger_clauses(src, _TRIGGER_PHRASES_GENERIC)
    # Dedup by the set of price levels (ignoring direction and stop/ATR
    # levels): the Position Size and Executive Summary often restate the same
    # trigger with different wording. Keep the LONGEST clause per level-set
    # (sort by sig size desc, then greedily drop subsets). Clauses with no
    # price levels (pure unmeasurable conditions like "clean PUC decision")
    # are kept too — they are still UNKNOWN conditions worth judging.
    ordered = sorted(clauses, key=lambda c: len(_level_sig(c)), reverse=True)
    kept: list[str] = []
    kept_sigs: list[set] = []
    for c in ordered:
        sig = _level_sig(c)
        if sig:
            if any(sig <= k for k in kept_sigs):
                continue
            kept_sigs.append(sig)
        kept.append(c)
    if not kept:
        return (decision.get("position_size") or "").strip()
    return " ".join(kept)


# ---------------------------------------------------------------------------
# Live OHLCV + indicators
# ---------------------------------------------------------------------------


def fetch_ohlcv(ticker: str, days: int = 320, timeout: float = 30.0) -> dict:
    """Daily OHLCV via the vendor chain; empty on failure (never raises).

    ``timeout`` bounds a single vendor call so a hanging moomoo connection
    degrades to "no data" (UNKNOWN) instead of blocking the whole report.
    """
    try:
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as _FutTimeout
        from datetime import datetime, timedelta

        from tradingagents.dataflows.interface import route_to_vendor

        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        def _fetch():
            return route_to_vendor("get_stock_data", ticker, start, end) or ""

        # shutdown(wait=False): a moomoo worker that ignores the future timeout
        # must not block the report (ThreadPoolExecutor.__exit__ would wait).
        pool = ThreadPoolExecutor(max_workers=1)
        try:
            fut = pool.submit(_fetch)
            try:
                out = fut.result(timeout=timeout)
            except _FutTimeout:
                return {"closes": [], "highs": [], "lows": [], "volumes": []}
        finally:
            pool.shutdown(wait=False)
        closes, opens, highs, lows, volumes = [], [], [], [], []
        for line in out.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.lower().startswith("date,"):
                continue
            parts = line.split(",")
            if len(parts) < 6:
                continue
            try:
                closes.append(float(parts[4]))
                opens.append(float(parts[1]))
                highs.append(float(parts[2]))
                lows.append(float(parts[3]))
                volumes.append(float(parts[5]))
            except ValueError:
                pass
        if closes:
            return {"closes": closes, "highs": highs, "lows": lows, "volumes": volumes}
    except Exception:  # noqa: BLE001 - degrade like the router
        pass
    return {"closes": [], "highs": [], "lows": [], "volumes": []}


def _realtime_price(ticker: str) -> float | None:
    """A real-time/latest price, guarded by source (Alpaca -> yfinance)."""
    try:
        from tradingagents.dataflows.config import get_config

        if get_config().get("enable_alpaca"):
            from tradingagents.dataflows.alpaca import get_intraday as _ai

            snap = _ai([ticker])
            price = (snap or {}).get(ticker, {}).get("price")
            if price:
                return float(price)
    except Exception:  # noqa: BLE001
        pass
    try:
        import yfinance as yf

        from tradingagents.dataflows.symbol_utils import normalize_symbol

        fi = yf.Ticker(normalize_symbol(ticker)).fast_info
        price = fi.get("last_price") if hasattr(fi, "get") else getattr(fi, "last_price", None)
        if price and price > 0:
            return float(price)
    except Exception:  # noqa: BLE001
        pass
    return None


def _sma_last(closes: list, n: int) -> float | None:
    if not closes or len(closes) < n:
        return None
    return sum(closes[-n:]) / n


def _volume_ratio(volumes: list, n: int = 30) -> float | None:
    if not volumes or len(volumes) < n + 1:
        return None
    avg = sum(volumes[-n:]) / n
    if avg <= 0:
        return None
    return volumes[-1] / avg


def _macd_hist_last(closes: list) -> float | None:
    try:
        from tradingagents.strategies.value_dip import _macd_hist

        m = _macd_hist(closes)
        if m is None:
            return None
        _, _, hist = m
        return hist[-1] if hist else None
    except Exception:  # noqa: BLE001
        return None


def _rsi_last(closes: list) -> float | None:
    try:
        from tradingagents.strategies.swing import rsi

        return rsi(closes)
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# Deterministic condition check
# ---------------------------------------------------------------------------

_UNMEASURABLE = (
    "stabilization", "stabilise", "stabilize", "catalyst", "earnings",
    "puc", "fomc", "jackson hole", "vdu trigger", "regulatory", "guidance",
    "print", "tariff", "ceo transition", "fed decision", "fed cut",
    "quarterly report",
)


def _level_direction(text: str, start: int, end: int) -> str:
    before = text[max(0, start - 60):start].lower()
    after = text[end:end + 40].lower()
    if any(w in before for w in (
        "above", "over", "reclaim", "break", "recover", "exceed",
        "back above", "close above", "breakout above", "high-volume breakout above",
    )):
        return "above"
    if any(w in before for w in (
        "below", "under", "beneath", "fall below", "drop below",
        "break down", "close below",
    )):
        return "below"
    if any(w in before for w in (
        "test", "retest", "at", "near", "toward", "towards", "around",
        "into", "pullback", "pull back", "zone",
    )):
        return "test"
    if any(w in after for w in ("test", "support", "resistance", "zone")):
        return "test"
    return "level"


def _extract_levels(text: str) -> list[dict]:
    """Price levels/ranges with direction hints from surrounding words."""
    out = []
    for m in re.finditer(r"\$(\d+(?:\.\d+)?)\s*(?:–|—|-|to)\s*\$?(\d+(?:\.\d+)?)", text):
        lo, hi = float(m.group(1)), float(m.group(2))
        if lo > hi:
            lo, hi = hi, lo
        out.append({"type": "range", "lo": lo, "hi": hi, "start": m.start(), "end": m.end()})
    for m in re.finditer(r"\$(\d+(?:\.\d+)?)", text):
        if any(m.start() >= r["start"] and m.end() <= r["end"] for r in out):
            continue
        out.append({"type": "level", "value": float(m.group(1)), "start": m.start(), "end": m.end()})
    for lvl in out:
        lvl["direction"] = _level_direction(text, lvl["start"], lvl["end"])
    return out


def _check_level(lvl: dict, price: float) -> dict:
    d = lvl["direction"]
    if lvl["type"] == "range":
        lo, hi = lvl["lo"], lvl["hi"]
        if d == "above":
            met = price > hi
            label = f"price above ${hi:.2f} (reclaim ${lo:.2f}-${hi:.2f})"
        elif d == "below":
            met = price < lo
            label = f"price below ${lo:.2f} (zone ${lo:.2f}-${hi:.2f})"
        else:
            met = lo * 0.98 <= price <= hi * 1.02
            label = f"price in ${lo:.2f}-${hi:.2f} zone"
        return {"label": label, "verdict": "MET" if met else "NOT_MET",
                "detail": f"price={price:.2f}"}
    v = lvl["value"]
    if d == "above":
        met = price > v
        label = f"price above ${v:.2f}"
    elif d == "below":
        met = price < v
        label = f"price below ${v:.2f}"
    elif d == "test":
        met = abs(price - v) / v <= 0.02
        label = f"price at/near ${v:.2f}"
    else:
        if abs(price - v) / v <= 0.02:
            return {"label": f"price at/near ${v:.2f}", "verdict": "MET",
                    "detail": f"price={price:.2f}"}
        return {"label": f"level ${v:.2f} (direction unclear)", "verdict": "UNKNOWN",
                "detail": f"price={price:.2f}"}
    return {"label": label, "verdict": "MET" if met else "NOT_MET",
            "detail": f"price={price:.2f}"}


def _check_sma(text: str, price: float, closes: list) -> list[dict]:
    checks = []
    for m in re.finditer(r"(50|100|200)[-\s]*(?:day|sma|dma)", text, re.I):
        n = int(m.group(1))
        sma = _sma_last(closes, n)
        if sma is None:
            checks.append({"label": f"SMA{n}", "verdict": "UNKNOWN",
                           "detail": f"need {n}+ closes"})
            continue
        before = text[max(0, m.start() - 40):m.start()].lower()
        if any(w in before for w in ("reclaim", "above", "back above", "over")):
            met = price > sma
            label = f"price above SMA{n} ({sma:.2f})"
        elif any(w in before for w in ("below", "under", "beneath")):
            met = price < sma
            label = f"price below SMA{n} ({sma:.2f})"
        else:
            met = abs(price - sma) / sma <= 0.02
            label = f"price at/near SMA{n} ({sma:.2f})"
        checks.append({"label": label, "verdict": "MET" if met else "NOT_MET",
                       "detail": f"price={price:.2f} sma{n}={sma:.2f}"})
    return checks


def _check_volume(text: str, volumes: list) -> list[dict]:
    if not re.search(r"volume|rvol|above-average|high-volume", text, re.I):
        return []
    ratio = _volume_ratio(volumes)
    if ratio is None:
        return [{"label": "volume", "verdict": "UNKNOWN",
                 "detail": "insufficient volume history"}]
    m = re.search(r"(\d+(?:\.\d+)?)\s*x", text, re.I)
    thr = float(m.group(1)) if m else 1.3
    met = ratio >= thr
    return [{"label": f"volume ratio >= {thr:.1f}x", "verdict": "MET" if met else "NOT_MET",
             "detail": f"ratio={ratio:.2f}"}]


def _check_macd(text: str, closes: list) -> list[dict]:
    if not re.search(r"macd", text, re.I):
        return []
    hist = _macd_hist_last(closes)
    if hist is None:
        return [{"label": "MACD", "verdict": "UNKNOWN", "detail": "insufficient history"}]
    if re.search(r"negative", text, re.I):
        met = hist < 0
        label = "MACD histogram negative"
    else:
        met = hist > 0
        label = "MACD histogram positive"
    return [{"label": label, "verdict": "MET" if met else "NOT_MET",
             "detail": f"hist={hist:.3f}"}]


def _check_rsi(text: str, closes: list) -> list[dict]:
    if not re.search(r"rsi", text, re.I):
        return []
    r = _rsi_last(closes)
    if r is None:
        return [{"label": "RSI", "verdict": "UNKNOWN", "detail": "insufficient history"}]
    m = re.search(r"rsi\s*([><=~≈]+)\s*(\d+)", text, re.I)
    if m:
        op, thr = m.group(1), float(m.group(2))
        if op in (">", ">="):
            met = r > thr
            label = f"RSI > {thr:.0f}"
        elif op in ("<", "<="):
            met = r < thr
            label = f"RSI < {thr:.0f}"
        else:
            met = r <= thr + 5
            label = f"RSI ~ {thr:.0f} (capitulation zone)"
    else:
        met = r <= 35
        label = "RSI oversold (<= 35)"
    return [{"label": label, "verdict": "MET" if met else "NOT_MET",
             "detail": f"rsi={r:.1f}"}]


def _is_stop_level(text: str, lvl: dict) -> bool:
    """A level preceded or followed by a stop word (stop / hard stop /
    stop-loss) or an ATR reference ("~$13-14 ATR gap risk") is not a trigger
    — reported informationally, never blocking a trigger MET."""
    before = text[max(0, lvl["start"] - 40):lvl["start"]].lower()
    # after-context is short (8 chars) so it only catches "$156.75 stop" and
    # not a "stop" that belongs to a later level ("; hard stop below $143").
    after = text[lvl["end"]:lvl["end"] + 8].lower()
    return any(w in before or w in after for w in ("stop", "stop-loss", "hard stop", "stop loss", "atr"))


def _looks_like_condition(text: str) -> bool:
    """A sentence is a condition to check when it carries a price level, an
    SMA/EMA ref, a volume/MACD/RSI keyword, or an unmeasurable trigger word.
    Context sentences ("keep a core to collect the dividend") are skipped."""
    low = text.lower()
    if re.search(r"\$", text):
        return True
    if re.search(r"(50|100|200)[-\s]*(?:day|sma|dma|ema)", text, re.I):
        return True
    if re.search(r"volume|rvol|macd|rsi", low):
        return True
    return any(w in low for w in _UNMEASURABLE)


def _check_sub_clause(text: str, price: float, closes: list, volumes: list) -> dict:
    """Check one OR sub-clause. Measurable trigger checks are AND'd; stop
    levels are informational (never block a MET); unmeasurable words are
    caveats (never block a MET)."""
    checks: list[dict] = []
    for lvl in _extract_levels(text):
        c = _check_level(lvl, price)
        if _is_stop_level(text, lvl):
            c["label"] = "stop: " + c["label"]
            c["informational"] = True
        checks.append(c)
    checks += _check_sma(text, price, closes)
    checks += _check_volume(text, volumes)
    checks += _check_macd(text, closes)
    checks += _check_rsi(text, closes)
    unmeas = [w for w in _UNMEASURABLE if w in text.lower()]
    if not checks:
        if unmeas:
            checks.append({"label": "unmeasurable", "verdict": "UNKNOWN",
                           "detail": "only unmeasurable: " + ", ".join(unmeas)})
        else:
            checks.append({"label": "no-condition", "verdict": "UNKNOWN",
                           "detail": "no measurable or unmeasurable trigger found"})
    trigger_checks = [c for c in checks if not c.get("informational")]
    if any(c["verdict"] == "NOT_MET" for c in trigger_checks):
        verdict = "NOT_MET"
    elif any(c["verdict"] == "MET" for c in trigger_checks):
        verdict = "MET"
    else:
        verdict = "UNKNOWN"
    return {"verdict": verdict, "checks": checks, "caveats": unmeas}


def check_condition(cond: str, ohlcv: dict) -> dict:
    """Deterministic check of a report's condition clause against live OHLCV.

    Returns {"verdict": MET|NOT_MET|UNKNOWN, "checks": [...], "reasons": [...]}.
    """
    closes = ohlcv.get("closes") or []
    volumes = ohlcv.get("volumes") or []
    if not closes:
        return {"verdict": "UNKNOWN", "checks": [],
                "reasons": ["no price history from the vendor chain"]}
    price = float(closes[-1])
    # Split into sentences first (each sentence is a trigger group), skip
    # "do not / avoid" instructions, then split each sentence on the OR
    # separator. `;` / `—` stay inside a sub-clause so sentence fragments
    # ("0% — no new position; trim ...") don't become empty UNKNOWN checks.
    sub_results = []
    for sent in re.split(r"(?<=[.!?])\s+", cond):
        sent = sent.strip()
        if not sent:
            continue
        if re.match(r"^(do not|don't|avoid|never)\b", sent, re.I):
            continue
        if not _looks_like_condition(sent):
            continue
        for sc in re.split(r"\s+or\s+", sent):
            sc = sc.strip()
            if sc:
                sub_results.append(_check_sub_clause(sc, price, closes, volumes))
    if not sub_results:
        sub_results = [_check_sub_clause(cond, price, closes, volumes)]
    checks = [c for s in sub_results for c in s["checks"]]
    caveats = sorted({c for s in sub_results for c in s["caveats"]})
    if any(s["verdict"] == "MET" for s in sub_results):
        verdict = "MET"
    elif any(s["verdict"] == "UNKNOWN" for s in sub_results):
        verdict = "UNKNOWN"
    else:
        verdict = "NOT_MET"
    reasons = []
    if caveats:
        reasons.append("unverifiable qualifiers: " + ", ".join(caveats))
    if verdict == "UNKNOWN" and not any(c["verdict"] == "UNKNOWN" for c in checks):
        reasons.append("no measurable condition found in the text")
    return {"verdict": verdict, "checks": checks, "reasons": reasons}


# ---------------------------------------------------------------------------
# Optional LLM judge
# ---------------------------------------------------------------------------


def _snapshot(ohlcv: dict) -> str:
    """Number-only market snapshot for the LLM judge (never prose)."""
    closes = ohlcv.get("closes") or []
    lines = []
    if closes:
        lines.append(f"- price: {closes[-1]:.2f}")
        for n in (50, 200):
            sma = _sma_last(closes, n)
            if sma is not None:
                lines.append(f"- sma{n}: {sma:.2f}")
    ratio = _volume_ratio(ohlcv.get("volumes") or [])
    if ratio is not None:
        lines.append(f"- volume_ratio_30d: {ratio:.2f}")
    r = _rsi_last(closes)
    if r is not None:
        lines.append(f"- rsi14: {r:.1f}")
    h = _macd_hist_last(closes)
    if h is not None:
        lines.append(f"- macd_hist: {h:.3f}")
    return "\n".join(lines) or "- no market data"


def llm_judge(condition: str, ohlcv: dict) -> str:
    """Optional LLM judge for UNKNOWN conditions; a message on any failure."""
    try:
        from tradingagents.agents.overrides.action_condition_judge import (
            create_action_condition_judge,
        )
        from tradingagents.default_config import DEFAULT_CONFIG
        from tradingagents.llm_clients.factory import create_llm_client

        client = create_llm_client(
            provider=DEFAULT_CONFIG["llm_provider"],
            model=DEFAULT_CONFIG["deep_think_llm"],
            base_url=DEFAULT_CONFIG.get("backend_url"),
        )
        judge = create_action_condition_judge(client.get_llm())
        return judge(condition, _snapshot(ohlcv))
    except Exception as exc:  # noqa: BLE001 - advisory only
        return f"judge unavailable: {exc}"


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _action(kind: str, verdict: str) -> str:
    if verdict == "MET":
        return "TRIM/REDUCE" if kind == "basket-underweight" else "ADD/BUY"
    if verdict == "UNKNOWN":
        return "MONITOR (unverified)"
    return "MONITOR"


def build_report(rows: list[dict], basket: dict, reports_root: str, as_of: str) -> str:
    """Render the final action report markdown."""
    lines = [
        f"# Conditional Action Report — {as_of}",
        "",
        f"Basket: {len(basket)} names (weights from TRADINGAGENTS_RISK_BASKET_WEIGHTS)",
        f"Reports scanned: `{reports_root}`",
        "",
    ]
    met = [r for r in rows if r["verdict"] == "MET"]
    lines.append(
        f"**Summary**: {len(rows)} flagged reports; "
        f"{len(met)} conditions MET (action), "
        f"{sum(1 for r in rows if r['verdict'] == 'UNKNOWN')} UNKNOWN (unverified), "
        f"{sum(1 for r in rows if r['verdict'] == 'NOT_MET')} NOT_MET (monitor)."
    )
    lines.append("")

    for kind, title in (
        ("basket-underweight", "Basket names — Underweight/Sell (reduce/trim)"),
        ("non-basket-overweight", "Non-basket names — Overweight/Buy (add)"),
    ):
        group = [r for r in rows if r["kind"] == kind]
        if not group:
            continue
        lines += [f"## {title}", ""]
        lines += [
            "| Symbol | Weight | Report date | Rating | Verdict | Action |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for r in group:
            w = f"{r['weight']:.2%}" if r.get("weight") is not None else "—"
            lines.append(
                f"| {r['symbol']} | {w} | {r['date']} | {r['rating']} | "
                f"{r['verdict']} | {_action(r['kind'], r['verdict'])} |"
            )
        lines.append("")
        for r in group:
            lines += [
                f"### {r['symbol']} ({r['date']}, {r['rating']})",
                "",
                f"- Report: `{r['report']}`",
                f"- Condition: {r['condition']}",
            ]
            if r.get("stop_loss") is not None:
                lines.append(f"- Stop loss: {r['stop_loss']}")
            if r.get("price_target") is not None:
                lines.append(f"- Price target: {r['price_target']}")
            lines.append(f"- Verdict: **{r['verdict']}** -> {_action(r['kind'], r['verdict'])}")
            for c in r["checks"]:
                lines.append(f"  - {c['label']}: {c['verdict']} ({c['detail']})")
            if r.get("judge"):
                lines.append(f"  - LLM judge: {r['judge']}")
            lines.append("")
    return "\n".join(lines)


def save_report(markdown: str, out_dir: str) -> Path:
    """Write the report to <out_dir>/<timestamp>.md, keeping only the newest."""
    from datetime import datetime as _dt

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    stamp = _dt.now().strftime("%Y%m%d_%H%M%S")
    file = out_path / (stamp + ".md")
    file.write_text(markdown + "\n", encoding="utf-8")
    try:
        for p in out_path.glob("*.md"):
            if p.is_file() and p.resolve() != file.resolve():
                p.unlink()
    except OSError:
        pass
    return file


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    # The report may carry non-ASCII characters (en/em dashes, ≈, and the
    # report text itself). Force UTF-8 output so a cp1252 console or a
    # subprocess that decodes as UTF-8 never crashes on print().
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--basket", default=None,
        help="override basket as SYM=W,SYM=W (default: config risk_basket_weights)",
    )
    parser.add_argument("--reports-dir", default="reports", help="report root (default: reports/)")
    parser.add_argument("--date", default=None, help="as-of date YYYY-MM-DD (default: today)")
    parser.add_argument(
        "--llm", action="store_true",
        help="invoke the LLM judge for UNKNOWN conditions (advisory)",
    )
    parser.add_argument(
        "--llm-max", type=int, default=5,
        help="max LLM judge calls per run (default 5; 0 = unlimited)",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--dry-run", action="store_true", help="print only, write nothing")
    parser.add_argument("--out-dir", default="action_reports", help="folder for the saved report")
    args = parser.parse_args(argv)

    from datetime import date as _date

    from tradingagents.dataflows.utils import resolve_output_path

    # Anchor relative inputs/outputs to the TradingAgents repo root so the web
    # app (launched from TradingNew or trading_web) never reads/writes the CWD.
    reports_dir = resolve_output_path(args.reports_dir)
    out_dir = resolve_output_path(args.out_dir)

    as_of = args.date or _date.today().isoformat()
    basket = load_basket(args.basket)
    reports = discover_reports(reports_dir)
    if not reports:
        print(f"no report folders found under {reports_dir}", file=sys.stderr)
        return 2

    rows = []
    judge_calls = 0
    for sym in sorted(reports):
        folder = reports[sym]
        decision_md = folder / "5_portfolio" / "decision.md"
        if not decision_md.is_file():
            continue
        try:
            md = decision_md.read_text(encoding="utf-8")
        except OSError:
            continue
        decision = parse_decision(md)
        kind = classify(sym, decision["rating"], basket)
        if not kind:
            continue
        ohlcv = fetch_ohlcv(sym)
        cond = extract_condition(decision)
        result = check_condition(cond, ohlcv)
        judge = None
        if args.llm and result["verdict"] == "UNKNOWN":
            if args.llm_max == 0 or judge_calls < args.llm_max:
                judge = llm_judge(cond, ohlcv)
                judge_calls += 1
            else:
                judge = f"skipped (--llm-max {args.llm_max} reached)"
        row = {
            "symbol": sym,
            "kind": kind,
            "weight": basket.get(sym),
            "report": folder.name,
            "date": _folder_date(folder.name),
            "rating": decision["rating"],
            "condition": cond,
            "verdict": result["verdict"],
            "checks": result["checks"],
            "reasons": result["reasons"],
            "judge": judge,
            "stop_loss": decision["stop_loss"],
            "price_target": decision["price_target"],
        }
        # Vibe-Trading persistent-invalidation: when the report's stop-loss
        # clause is NOT_MET (live price breached), record an auto
        # invalidation in the ledger so the next review sees why this thesis
        # was retired (advisory; never gates).
        if result["verdict"] == "NOT_MET" and decision["stop_loss"] is not None:
            try:
                from tradingagents.strategies.invalidation_ledger import append

                append(
                    sym,
                    [f"price_stop_loss: breach below {decision['stop_loss']:g}"],
                    date=_folder_date(folder.name),
                    note=f"action_report NOT_MET on {folder.name}",
                    source="action_report",
                )
                row["invalidation_recorded"] = True
            except Exception:  # noqa: BLE001 - advisory, never blocks
                pass
        rows.append(row)

    if args.json:
        print(json.dumps(rows, indent=2, default=str))
        return 0

    markdown = build_report(rows, basket, reports_dir, as_of)
    print(markdown)
    if not args.dry_run:
        saved = save_report(markdown, str(out_dir))
        print(f"[action_report] saved to {saved}")
    # Close the moomoo context while the process is healthy (see value_screener
    # main()): the SDK's receive thread keeps the process alive after main()
    # returns, and closing at interpreter exit can block.
    try:
        from tradingagents.dataflows.moomoo import close_context

        close_context()
    except Exception:  # noqa: BLE001 - closing is best-effort
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

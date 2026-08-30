"""G2 calibration wiring: _calibrated_p + ledger stamping in the graph.

Verifies decision_hardening_spec G2 end-to-end: a stamped
calibration_ledger.jsonl makes _calibrated_p(decision) return a real calibrated
probability (not the old unconditional None), and calibration is a no-op when
disabled or when no ledger exists.
"""

import json

import pytest

from tradingagents.graph.trading_graph import TradingAgentsGraph

pytestmark = pytest.mark.timeout(120)


class _Mem:
    def __init__(self):
        self._pending = []

    def get_pending_entries(self):
        return self._pending


def _graph(tmp_path, enable=True):
    from tradingagents.default_config import DEFAULT_CONFIG

    cfg = DEFAULT_CONFIG.copy()
    cfg["enable_calibration"] = enable
    cfg["data_cache_dir"] = str(tmp_path)
    g = TradingAgentsGraph(config=cfg)
    g.memory_log = _Mem()
    return g


def _write_ledger(tmp_path, rows):
    f = tmp_path / "calibration_ledger.jsonl"
    f.parent.mkdir(parents=True, exist_ok=True)
    for r in rows:
        with open(f, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(r) + "\n")


def test_calibrated_p_returns_calibrated_conf_when_ledger_exists(tmp_path):
    # same bucket, 4 won / 1 lost -> win_rate 0.8; declared 0.65 -> 0.8 (trust-heavy)
    _write_ledger(
        tmp_path,
        [{"confidence": 0.65, "won": True}] * 4 + [{"confidence": 0.65, "won": False}],
    )
    g = _graph(tmp_path, enable=True)
    p = g._calibrated_p("Here is the decision\n**Confidence**: 0.65\nStop loss: ...")
    assert p is not None
    assert p > 0.65  # calibrated above declared (positive track record)


def test_calibrated_p_no_ledger_returns_none(tmp_path):
    g = _graph(tmp_path, enable=True)
    assert g._calibrated_p("**Confidence**: 0.65") is None


def test_calibrated_p_disabled_returns_none(tmp_path):
    _write_ledger(tmp_path, [{"confidence": 0.65, "won": True}])
    g = _graph(tmp_path, enable=False)
    assert g._calibrated_p("**Confidence**: 0.65") is None


def test_calibrated_p_no_confidence_in_decision_returns_none(tmp_path):
    _write_ledger(tmp_path, [{"confidence": 0.65, "won": True}])
    g = _graph(tmp_path, enable=True)
    assert g._calibrated_p("No confidence line here") is None


def test_maybe_record_calibration_writes_ledger(tmp_path):

    g = _graph(tmp_path, enable=True)
    g.memory_log._pending = [
        {"ticker": "NVDA", "date": "2026-08-01", "decision": "**Confidence**: 0.70\nBuy"}
    ]
    g._maybe_record_calibration("NVDA", "2026-08-01", alpha=0.05)
    f = tmp_path / "calibration_ledger.jsonl"
    assert f.exists()
    rows = [json.loads(ln) for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert rows and rows[0]["confidence"] == 0.70 and rows[0]["won"] is True

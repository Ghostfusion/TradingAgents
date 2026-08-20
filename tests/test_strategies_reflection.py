"""Phase 5 unit tests: reflection ledger (offline, tmp JSON)."""

from tradingagents.strategies.reflection import (
    ReflectionLedger,
    build_reflection_context,
)


def test_ledger_scores_offline(tmp_path):
    store = ReflectionLedger(path=str(tmp_path / "ledger.jsonl"))
    assert store.score("fundamentals") is None
    store.record_outcome("fundamentals", "AAPL", "2026-01-02", 0.03)
    store.record_outcome("fundamentals", "MSFT", "2026-01-03", -0.01)
    assert store.total("fundamentals") == 2
    assert store.hits("fundamentals") == 1
    assert 0.0 < store.score("fundamentals") < 1.0


def test_ledger_persists_to_disk(tmp_path):
    path = tmp_path / "ledger.jsonl"
    store = ReflectionLedger(path=str(path))
    store.record_outcome("news", "TSLA", "2026-01-04", 0.02)
    reloaded = ReflectionLedger(path=str(path))
    assert reloaded.total("news") == 1


def test_reflection_hint_states():
    store = ReflectionLedger()
    assert "cautious" in store.reflection_hint("fundamentals")
    store.record_outcome("fundamentals", "A", "2026-01-01", 0.01)
    store.record_outcome("fundamentals", "B", "2026-01-02", -0.01)
    assert "repeatable" in store.reflection_hint("fundamentals")
    store.record_outcome("fundamentals", "C", "2026-01-03", -0.05)
    assert "critique" in store.reflection_hint("fundamentals")


def test_build_context_renders():
    store = ReflectionLedger()
    store.record_outcome("technical", "NVDA", "2026-01-01", 0.01)
    ctx = build_reflection_context(store, ["technical", "fundamentals"])
    assert "technical" in ctx and "fundamentals" in ctx


def test_recent_tickers_dedupes():
    store = ReflectionLedger()
    store.record_outcome("a", "AAPL", "2026-01-01", 0.0)
    store.record_outcome("b", "AAPL", "2026-01-02", 0.01)
    assert store.recent_tickers() == ["AAPL"]

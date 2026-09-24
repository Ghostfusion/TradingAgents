"""H7: the refusal ledger, the five tiers, and the save-to-miss discipline.

``prediction_ledger`` records decisions the engine TAKEN; this records the
candidates its gates REFUSED. The tiers are 2607.02830's; the ratio is reported
with its event count and never as a constant; and the tie-break is the paper's -
**missed beats saved**.
"""

from __future__ import annotations

from tradingagents.strategies.knife_guard import knife_factor
from tradingagents.strategies.market_tradability import (
    limit_gate,
    suspended,
    volume_gate,
)
from tradingagents.strategies.news_relevance import admit_article
from tradingagents.strategies.refusal_ledger import (
    TIER_FLAT,
    TIER_MISSED_MOON,
    TIER_SAVED_EARLY_DEATH,
    TIER_SAVED_WINDOWED,
    TIER_UNCLASSIFIABLE,
    classify_refusal,
    log_refusal,
    rows,
    save_to_miss_ratio,
    score_all,
)
from tradingagents.strategies.risk_governor import govern
from tradingagents.strategies.value_dip import value_dip_setup


def _row(gate: str = "knife_guard") -> dict:
    return {"symbol": "ACME", "as_of": "2026-01-02", "gate": gate,
            "reason": "test refusal", "snapshot_hash": None}


def _ledger(monkeypatch, tmp_path, *, on: bool):
    """Point the ledger at a temp file and set the gate at the config accessor."""
    path = tmp_path / "refusals.jsonl"
    monkeypatch.setattr(
        "tradingagents.strategies.refusal_ledger._ledger_path",
        lambda results_dir=None: path,
    )
    monkeypatch.setattr(
        "tradingagents.dataflows.config.get_config",
        lambda: {"enable_refusal_ledger": on},
    )
    return path


def _value_dip_refused(*, symbol=None, as_of=None) -> dict:
    """A measured value-dip candidate that its own floors refuse."""
    closes = [100.0 + (i % 5) * 0.3 for i in range(25)]
    highs = [c * 1.01 for c in closes]
    lows = [c * 0.99 for c in closes]
    setup = value_dip_setup(closes, highs, lows, [1e6] * 25,
                            symbol=symbol, as_of=as_of)
    assert setup["candidate"] is False
    return setup


def test_tie_break_missed_beats_saved():
    """A refusal whose forward path BOTH avoided a drawdown and missed a run is a
    miss - the paper's tie-break, missed beats saved. Dropping that branch leaves
    the classifier's saved-first ordering to call such a refusal saved.
    """
    row = _row()
    # 100 -> 80 (the 20% the refusal saved) -> 140 (the 40% run it forwent),
    # inside one 6-bar window.
    both = classify_refusal(row, [100.0, 90.0, 80.0, 95.0, 120.0, 140.0], horizon=6)
    c = both["classification"]
    assert c["saved"] is True and c["missed"] is True
    assert c["tier"] == TIER_MISSED_MOON

    # The contrast, so the tie-break is a real branch rather than a classifier
    # that always answers "miss": a path that only fell and stayed down is a
    # save, and one that dipped and recovered is a windowed save.
    down = classify_refusal(row, [100.0, 92.0, 85.0, 82.0, 80.0, 79.0], horizon=6)
    assert down["classification"]["saved"] is True
    assert down["classification"]["missed"] is False
    assert down["classification"]["tier"] == TIER_SAVED_EARLY_DEATH

    recovered = classify_refusal(row, [100.0, 88.0, 86.0, 95.0, 101.0, 103.0], horizon=6)
    assert recovered["classification"]["tier"] == TIER_SAVED_WINDOWED

    # The ratio is never published without the event count it rests on.
    report = save_to_miss_ratio([both, down, recovered])
    entry = report["gates"]["knife_guard"]
    assert entry["events"] == 3
    assert entry["saves"] == 2 and entry["misses"] == 1
    assert entry["ratio"] == 2.0
    assert report["tie_break"] == "missed beats saved"
    for gate, e in report["gates"].items():
        assert "events" in e, f"gate {gate} published a ratio without its count"
        if e["ratio"] is not None:
            assert e["events"] > 0


def test_gate_off_records_nothing_and_gate_on_records_the_snapshot(monkeypatch, tmp_path):
    """The writer is gated, and it says which it did: with the gate off nothing
    reaches disk and the row reports ``written: False``; with it on the row lands
    and identical inputs hash to one identity.
    """
    _ledger(monkeypatch, tmp_path, on=False)
    row = log_refusal("acme", "2026-01-02", "knife_guard", "block band",
                      snapshot={"K": 3.5})
    assert row["written"] is False
    assert row["symbol"] == "ACME"          # normalised, never fabricated
    assert row["snapshot_hash"]
    assert rows() == []

    _ledger(monkeypatch, tmp_path, on=True)
    row = log_refusal("acme", "2026-01-02", "knife_guard", "block band",
                      snapshot={"K": 3.5})
    assert row["written"] is True
    written = rows()
    assert len(written) == 1
    assert written[0]["gate"] == "knife_guard"
    assert written[0]["snapshot_hash"] == row["snapshot_hash"]

    same = log_refusal("acme", "2026-01-02", "knife_guard", "block band",
                       snapshot={"K": 3.5})
    other = log_refusal("acme", "2026-01-02", "knife_guard", "block band",
                        snapshot={"K": 2.0})
    assert same["snapshot_hash"] == row["snapshot_hash"]
    assert other["snapshot_hash"] != row["snapshot_hash"]


def test_the_engine_refusal_sites_record_behind_the_gate(monkeypatch, tmp_path):
    """Each reachable refusal site appends one row when it refuses and none when
    it passes - and with the gate off every one of those same refusals leaves the
    ledger empty, so the gate is what makes the instrument reachable.
    """
    _ledger(monkeypatch, tmp_path, on=False)
    assert govern(0.9)["verdict"] == "REJECT"
    assert knife_factor(3.5) == (0.0, "block")
    assert suspended(None) is True
    assert limit_gate(0.15, 0.10) == "up"
    assert volume_gate(100, 0.0, 0.2) == 0
    assert admit_article("Download the app now") is False
    _value_dip_refused()
    assert rows() == []

    _ledger(monkeypatch, tmp_path, on=True)
    assert govern(0.9, symbol="ACME", as_of="2026-01-02")["verdict"] == "REJECT"
    assert govern(0.05)["verdict"] == "PASS"           # a pass is not a refusal
    assert knife_factor(3.5, symbol="ACME", as_of="2026-01-02") == (0.0, "block")
    assert knife_factor(1.0)[0] == 1.0                 # normal band: no row
    assert suspended(None, symbol="ACME", as_of="2026-01-02") is True
    assert suspended(100.0) is False                   # a tradable day: no row
    assert limit_gate(0.15, 0.10, symbol="ACME", as_of="2026-01-02") == "up"
    assert limit_gate(0.01, 0.10) is None
    assert volume_gate(100, 0.0, 0.2, symbol="ACME", as_of="2026-01-02") == 0
    assert volume_gate(500, 1000, 0.2) == 200          # capped, not refused: no row
    assert admit_article("Download the app now", symbol="ACME",
                         as_of="2026-01-02") is False
    assert admit_article("Acme beats estimates") is True
    _value_dip_refused(symbol="ACME", as_of="2026-01-02")

    recorded = rows()
    assert [r["gate"] for r in recorded] == [
        "risk_governor",
        "knife_guard",
        "market_tradability",   # suspended
        "market_tradability",   # limit gate
        "market_tradability",   # participation cap
        "news_admission",
        "value_dip",
    ]
    assert all(r["written"] is True for r in recorded)
    assert {r["symbol"] for r in recorded} == {"ACME"}
    assert all(r["snapshot_hash"] for r in recorded)
    assert all(r["reason"] for r in recorded)


def test_missing_paths_are_unclassifiable_never_a_save_or_a_miss():
    """No forward path is ``unclassifiable`` with the reason - not a save, not a
    miss, and never a zero-length "flat"."""
    row = _row()
    for path in (None, [], [100.0], [float("nan")] * 30):
        c = classify_refusal(row, path)["classification"]
        assert c["tier"] == TIER_UNCLASSIFIABLE
        assert c["saved"] is False and c["missed"] is False
        assert c["unavailable"]

    # A gate whose refusals were never sampled has no ratio - not an infinite one.
    report = save_to_miss_ratio([classify_refusal(row, None)])
    entry = report["gates"]["knife_guard"]
    assert entry["events"] == 0
    assert entry["unclassifiable"] == 1
    assert entry["ratio"] is None
    assert entry["unavailable"]


def test_score_all_keys_on_the_row_identity_and_flat_counts_as_an_event(
    monkeypatch, tmp_path
):
    """The sampler joins on the row's own ``(symbol, as_of)``; an unsampled row
    says so instead of inventing a tier, and a quiet path is an event with no
    miss rather than a ratio."""
    _ledger(monkeypatch, tmp_path, on=True)
    log_refusal("acme", "2026-01-02", "value_dip", "value floor missed",
                snapshot={"x": 1})
    log_refusal("beta", "2026-01-03", "value_dip", "value floor missed",
                snapshot={"x": 2})

    scored = score_all({("ACME", "2026-01-02"): [100.0, 100.5, 99.5, 100.2, 100.0]})
    by_symbol = {r["symbol"]: r for r in scored}
    assert by_symbol["ACME"]["classification"]["tier"] == TIER_FLAT
    assert by_symbol["BETA"]["classification"] is None

    entry = save_to_miss_ratio(scored, min_events=5)["gates"]["value_dip"]
    assert entry["events"] == 1 and entry["flat"] == 1
    assert entry["ratio"] is None
    assert entry["underpowered"] is True
    assert entry["min_events"] == 5

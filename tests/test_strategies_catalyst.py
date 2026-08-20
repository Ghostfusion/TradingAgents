"""B1 scheduled-catalyst overlay unit tests (offline, deterministic)."""

import pytest

from tradingagents.strategies.catalyst import (
    apply_catalyst_scale,
    build_catalyst_snapshot,
    calendar_days_between,
    fed_imminence,
    fetch_catalyst_data,
    fold_catalyst_into_overlay,
    implied_move_from_history,
    last_earnings_surprise,
    macro_imminence,
    next_earnings,
    parse_date,
)


def _earnings_rows():
    return [
        {"date": "2026-06-20", "eps_estimate": 1.00, "eps_actual": 1.10},  # beat
        {"date": "2026-08-24", "eps_estimate": 1.05, "eps_actual": None},  # upcoming
    ]


def _move_history():
    return [
        {"period_text": "2026/Q3", "predict_vola_ratio_newest": 4.2},
        {"period_text": "2026/Q2", "predict_vola_ratio_newest": 3.1},
    ]


def _macro_events():
    return [
        {"title": "CPI", "timestamp": "2026-08-18", "star": "HIGH"},
        {"title": "Jobless Claims", "timestamp": "2026-08-20", "star": "MEDIUM"},
    ]


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_parse_date_formats():
    assert parse_date("2026-08-19").strftime("%Y-%m-%d") == "2026-08-19"
    assert parse_date("08/19/2026").strftime("%Y-%m-%d") == "2026-08-19"
    assert parse_date(None) is None
    assert parse_date("garbage") is None


def test_calendar_days_between():
    assert calendar_days_between("2026-08-01", "2026-08-10") == 9
    assert calendar_days_between("2026-08-10", "2026-08-01") == -9
    assert calendar_days_between("bad", "2026-08-10") == -1


def test_last_earnings_surprise_picks_most_recent():
    res = last_earnings_surprise(_earnings_rows())
    assert res is not None
    assert res["side"] == "beat"
    assert res["date"] == "2026-06-20"
    assert res["surprise"] == pytest.approx(0.10)


def test_last_earnings_surprise_handles_missing():
    assert last_earnings_surprise([]) is None
    assert (
        last_earnings_surprise([{"date": "2026-01-01", "eps_estimate": None, "eps_actual": None}])
        is None
    )


def test_next_earnings_forward_window():
    res = next_earnings(_earnings_rows(), "2026-08-10")
    assert res is not None
    assert res["days_until"] == 14
    assert res["date"] == "2026-08-24"


def test_next_earnings_filters_past():
    assert next_earnings(_earnings_rows(), "2026-08-25") is None


def test_implied_move_percent_to_fraction():
    assert implied_move_from_history(_move_history()) == pytest.approx(0.042)
    assert implied_move_from_history([]) is None


def test_macro_imminence_counts_high_only():
    res = macro_imminence(_macro_events(), "2026-08-15", window_days=3)
    # CPI on 08-18 is 3 days out -> in window; claims is MEDIUM -> ignored.
    assert res["count_high"] == 1
    assert res["min_days"] == 3


def test_fed_imminence_nearest_meeting():
    rows = [
        {"meeting_date": "2026-09-15", "target_range": "3.50-3.75%", "probability": 66.9},
        {"meeting_date": "2026-09-15", "target_range": "3.75-4.00%", "probability": 33.1},
        {"meeting_date": "2026-10-27", "target_range": "3.50-3.75%", "probability": 53.6},
    ]
    res = fed_imminence(rows, "2026-09-01", window_days=14)
    assert res["days_until"] == 14
    assert res["modal_prob"] == pytest.approx(66.9)


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------


def _full_data():
    return {
        "earnings_calendar": _earnings_rows(),  # next earnings 08-24 (within 5d default from 08-19)
        "move_history": _move_history(),
        "economic_calendar": _macro_events(),
        "fed_watch": [
            {"meeting_date": "2026-09-15", "target_range": "3.50-3.75%", "probability": 66.9},
        ],
    }


def test_snapshot_earnings_window_scale_down():
    snap = build_catalyst_snapshot(_full_data(), "2026-08-19", {"catalyst_window_days": 5})
    assert snap["verdict"] == "earnings-window"
    assert snap["scale"] < 1.0
    assert any("earnings 2026-08-24" in r for r in snap["reasons"])


def test_snapshot_no_catalyst_neutral():
    snap = build_catalyst_snapshot(
        {"earnings_calendar": [], "move_history": [], "economic_calendar": [], "fed_watch": []},
        "2026-08-19",
        {},
    )
    assert snap["verdict"] == "no-imminent-catalyst"
    assert snap["scale"] == pytest.approx(1.0)
    assert snap["reasons"] == []


def test_snapshot_macro_verdict():
    data = {
        "earnings_calendar": [],
        "move_history": [],
        # CPI on 08-20 is within the 3-day macro window from 08-19
        "economic_calendar": [
            {"title": "CPI", "timestamp": "2026-08-20", "star": "HIGH"},
        ],
        "fed_watch": [],
    }
    snap = build_catalyst_snapshot(
        data, "2026-08-19", {"catalyst_macro_window_days": 3, "catalyst_macro_scale": 0.6}
    )
    assert snap["verdict"] == "macro-catalyst"
    assert snap["scale"] == pytest.approx(0.6)


def test_snapshot_scale_floor_applied():
    data = {
        "earnings_calendar": [{"date": "2026-08-20", "eps_estimate": 1.0, "eps_actual": 0.4}],
        "move_history": [{"predict_vola_ratio_newest": 40.0}],  # giant implied move
        # last earnings is a big miss on 08-20 (past) -> miss_scale applied
        "economic_calendar": [{"title": "CPI", "timestamp": "2026-08-20", "star": "HIGH"}],
        "fed_watch": [{"meeting_date": "2026-08-22", "probability": 60.0}],
    }
    snap = build_catalyst_snapshot(data, "2026-08-19", {"catalyst_scale_floor": 0.3})
    assert snap["scale"] <= 0.6001  # never above the smallest multiplier
    assert snap["scale"] >= 0.3 - 1e-9  # floored
    # a miss inside the earnings window contributes the miss multiplier
    assert "miss" in " ".join(snap["reasons"])


# ---------------------------------------------------------------------------
# Overlay fold + contract scaling
# ---------------------------------------------------------------------------


def test_fold_multiplies_scale_and_stamps():
    overlay = {"regime": "bull", "position_scale": 0.8, "context": "regime=bull"}
    snap = {"verdict": "earnings-window", "scale": 0.5, "reasons": ["earnings in 3d"]}
    out = fold_catalyst_into_overlay(overlay, snap)
    assert out["position_scale"] == pytest.approx(0.4)
    assert out["catalyst"]["verdict"] == "earnings-window"
    assert "catalyst earnings-window" in out["context"]
    # original untouched
    assert overlay["position_scale"] == 0.8


def test_fold_none_noop():
    assert fold_catalyst_into_overlay(None, {"scale": 0.5}) is None
    assert fold_catalyst_into_overlay({"position_scale": 1.0}, None)["position_scale"] == 1.0


def test_apply_catalyst_scale_caps():
    assert apply_catalyst_scale(0.20, {"scale": 0.5}) == pytest.approx(0.10)
    assert apply_catalyst_scale(None, {"scale": 0.5}) is None
    assert apply_catalyst_scale(0.20, None) == 0.20


def test_contract_respects_catalyst_scale():
    from tradingagents.strategies.contract import build_position_contract

    closes = [100.0 + i for i in range(120)]
    base = build_position_contract(cfg={}, closes=closes, calibrated_p=0.6)
    scaled = build_position_contract(cfg={}, closes=closes, calibrated_p=0.6, catalyst_scale=0.5)
    assert base is not None and scaled is not None
    assert scaled.size_pct <= base.size_pct + 1e-9
    assert any("catalyst_scale" in r for r in scaled.reason_parts)
    assert not any("catalyst_scale" in r for r in base.reason_parts)


# ---------------------------------------------------------------------------
# Guarded live fetch
# ---------------------------------------------------------------------------


def test_fetch_catalyst_data_unavailable_returns_dict_with_backdrop(monkeypatch):
    def _boom(*args, **kwargs):
        raise RuntimeError("OpenD down")

    monkeypatch.setattr("tradingagents.dataflows.moomoo._ensure_ctx", _boom)
    monkeypatch.setattr("tradingagents.dataflows.moomoo._moomoo_code", lambda s: "US.AAPL")
    # Patch the OpenD-independent backdrop so the test stays hermetic.
    monkeypatch.setattr(
        "tradingagents.dataflows.massive.fetch_macro_backdrop",
        lambda *a, **k: {"scale": 0.7, "verdict": "macro-backdrop", "reasons": [],
                         "curve_inverted": True, "breakeven": 2.1},
    )
    data = fetch_catalyst_data("AAPL", "2026-08-19")
    # OpenD being down must NOT nullify the whole catalyst now.
    assert data is not None
    assert data["earnings_calendar"] == []
    assert data["macro_backdrop"]["verdict"] == "macro-backdrop"


def test_fetch_catalyst_data_patches_backdrop(monkeypatch):
    """The backdrop fetch is called so macro/fed stay decoupled from OpenD."""
    called = {}

    def _fake_backdrop(trade_date):
        called["td"] = trade_date
        return {"scale": 1.0, "verdict": "no-macro-stress", "reasons": [],
                "curve_inverted": False, "breakeven": 2.2}

    monkeypatch.setattr(
        "tradingagents.dataflows.massive.fetch_macro_backdrop", _fake_backdrop
    )
    monkeypatch.setattr("tradingagents.dataflows.moomoo._moomoo_code", lambda s: "US.AAPL")
    # Make the whole moomoo block raise to isolate the backdrop path.
    def _boom(*a, **k):
        raise RuntimeError("OpenD down")
    monkeypatch.setattr("tradingagents.dataflows.moomoo._ensure_ctx", _boom)
    data = fetch_catalyst_data("AAPL", "2026-08-19")
    assert called.get("td") == "2026-08-19"
    assert data["macro_backdrop"]["verdict"] == "no-macro-stress"

def test_snapshot_applies_macro_backdrop_when_no_event_calendar():
    """A stressed Massive backdrop de-risks when the moomoo event calendar
    is empty (i.e. OpenD down / no forward events)."""
    data = {
        "earnings_calendar": [],
        "move_history": [],
        "economic_calendar": [],  # no HIGH macro events from moomoo
        "fed_watch": [],
        "macro_backdrop": {
            "scale": 0.7, "verdict": "macro-backdrop",
            "reasons": ["yield curve inverted (10y<2y) -> x0.70"],
            "curve_inverted": True, "breakeven": 2.1,
        },
    }
    snap = build_catalyst_snapshot(data, "2026-08-18", {})
    assert snap["verdict"] == "macro-backdrop"
    assert snap["scale"] == 0.7
    assert any("inverted" in r for r in snap["reasons"])


def test_snapshot_skips_backdrop_when_event_calendar_present():
    """A live moomoo event calendar wins over the backdrop (no double-count)."""
    data = {
        "earnings_calendar": [],
        "move_history": [],
        "economic_calendar": [
            {"title": "CPI", "timestamp": "2026-08-19", "star": "HIGH"},
        ],
        "fed_watch": [],
        "macro_backdrop": {
            "scale": 0.7, "verdict": "macro-backdrop",
            "reasons": ["yield curve inverted (10y<2y) -> x0.70"],
            "curve_inverted": True, "breakeven": 2.1,
        },
    }
    snap = build_catalyst_snapshot(data, "2026-08-18", {})
    # 0.6 macro_scale applied (event present); backdrop must not double-apply.
    assert snap["scale"] == 0.6
    assert snap["verdict"] == "macro-catalyst"


def test_fetch_catalyst_data_unpacks_live_shape(monkeypatch):
    class FakeCtx:
        def get_earnings_calendar(self, **kwargs):
            from pandas import DataFrame

            # Real moomoo rows, returned only for the chunk containing the date
            # (the fetch chunks the window into 7-day calls).
            begin, end = kwargs["begin_date"], kwargs["end_date"]
            if not (begin <= "2026-08-24" <= end):
                return 0, DataFrame()
            return 0, DataFrame(
                {
                    "security": ["US.AAPL", "US.OTHER"],
                    "earnings_date": ["2026-08-24", "2026-08-25"],
                    "eps_predict": [1.0, 1.1],
                    "eps_actual": ["N/A", "N/A"],
                }
            )

        def get_financials_earnings_price_history(self, code):
            from pandas import DataFrame

            return 0, DataFrame({"predict_vola_ratio_newest": [3.9]})

        def get_economic_calendar(self, **kwargs):
            from pandas import DataFrame

            # SDK returns (ret, df, next_page, has_more)
            return 0, DataFrame({"title": ["CPI"], "timestamp": ["2026-08-20"], "star": ["HIGH"]}), None, False

        def get_fed_watch_target_rate(self):
            from pandas import DataFrame

            return 0, DataFrame({"meeting_date": ["2026-09-15"], "probability": [66.9]})

    monkeypatch.setattr("tradingagents.dataflows.moomoo._ensure_ctx", lambda: FakeCtx())
    monkeypatch.setattr("tradingagents.dataflows.moomoo._moomoo_code", lambda s: "US.AAPL")
    monkeypatch.setattr(
        "tradingagents.dataflows.massive.fetch_macro_backdrop",
        lambda *a, **k: {"scale": 1.0, "verdict": "no-macro-stress",
                         "reasons": [], "curve_inverted": False, "breakeven": 2.2},
    )
    data = fetch_catalyst_data("AAPL", "2026-08-19")
    assert data is not None
    # security filter keeps only AAPL rows; moomoo fields normalized
    assert len(data["earnings_calendar"]) == 1
    row = data["earnings_calendar"][0]
    assert row["date"] == "2026-08-24"
    assert row["eps_estimate"] == 1.0
    assert row["eps_actual"] is None  # "N/A" actual converted
    assert data["move_history"] and data["move_history"][0]["predict_vola_ratio_newest"] == 3.9


# ---------------------------------------------------------------------------
# Graph wiring (enable_events gate)
# ---------------------------------------------------------------------------


def test_graph_overlay_wiring_enable_events(monkeypatch):
    """_apply_strategy_overlays runs the catalyst fold when enable_events is on."""
    import tradingagents.graph.trading_graph as tg
    from tradingagents.strategies import catalyst as cat_mod

    graph = object.__new__(tg.TradingAgentsGraph)
    graph.config = {
        "enable_strategy_overlays": True,
        "enable_events": True,
        "enable_orderflow": False,
        "enable_position_contract": False,
        "enable_risk_governor": False,
        "enable_computed_context": False,
        "target_vol": 0.15,
    }
    closes = [100.0 + 0.2 * i for i in range(300)]
    monkeypatch.setattr(graph, "_try_fetch_closes", lambda *a, **k: closes)

    snapshot = {"verdict": "earnings-window", "scale": 0.5, "reasons": ["earnings in 3d"]}
    monkeypatch.setattr(cat_mod, "fetch_catalyst_data", lambda *a, **k: {"ok": True})
    monkeypatch.setattr(cat_mod, "build_catalyst_snapshot", lambda *a, **k: snapshot)
    monkeypatch.setattr(
        cat_mod,
        "fold_catalyst_into_overlay",
        lambda overlay, snap: {
            **overlay,
            "catalyst": snap,
            "position_scale": 0.5,
            "context": "catalyst",
        },
    )

    state = {"trade_date": "2026-08-19", "final_trade_decision": "Hold"}
    out = graph._apply_strategy_overlays(state, "AAPL")
    assert out["strategy_overlays"]["catalyst"]["verdict"] == "earnings-window"
    assert out["strategy_overlays"]["position_scale"] == 0.5


def test_graph_overlay_wiring_events_disabled(monkeypatch):
    """enable_events off -> no catalyst key in the overlay."""
    import tradingagents.graph.trading_graph as tg
    from tradingagents.strategies import catalyst as cat_mod

    graph = object.__new__(tg.TradingAgentsGraph)
    graph.config = {
        "enable_strategy_overlays": True,
        "enable_events": False,
        "enable_orderflow": False,
        "enable_position_contract": False,
        "enable_risk_governor": False,
        "enable_computed_context": False,
        "target_vol": 0.15,
    }
    monkeypatch.setattr(graph, "_try_fetch_closes", lambda *a, **k: [100.0 + i for i in range(300)])
    monkeypatch.setattr(
        cat_mod,
        "fetch_catalyst_data",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not fetch")),
    )
    out = graph._apply_strategy_overlays({"trade_date": "2026-08-19"}, "AAPL")
    assert "catalyst" not in (out.get("strategy_overlays") or {})


def test_snapshot_hard_block_off_by_default():
    snap = build_catalyst_snapshot(
        _full_data(), "2026-08-19", {"catalyst_window_days": 5}
    )
    assert snap["hard_block"] is None
    assert snap["verdict"] != "earnings-hard-block"


def test_snapshot_hard_block_when_within_window():
    snap = build_catalyst_snapshot(
        _full_data(),  # next earnings 08-24 -> 5 days out
        "2026-08-19",
        {"catalyst_window_days": 5, "catalyst_hard_block_days": 7},
    )
    assert snap["hard_block"] is not None
    assert snap["hard_block"]["days_until"] == 5
    assert snap["hard_block"]["window_days"] == 7
    assert snap["verdict"] == "earnings-hard-block"
    assert snap["scale"] < 1.0  # de-risk still applies alongside the veto
    assert any("hard-block" in r for r in snap["reasons"])


def test_snapshot_hard_block_no_earnings():
    snap = build_catalyst_snapshot(
        {"earnings_calendar": [], "move_history": [], "economic_calendar": [], "fed_watch": []},
        "2026-08-19",
        {"catalyst_hard_block_days": 7},
    )
    assert snap["hard_block"] is None
    assert snap["verdict"] == "no-imminent-catalyst"


def test_snapshot_hard_block_outside_window_no_veto():
    snap = build_catalyst_snapshot(
        _full_data(),  # earnings 08-24, 5 days out
        "2026-08-19",
        {"catalyst_window_days": 5, "catalyst_hard_block_days": 3},  # block < distance
    )
    assert snap["hard_block"] is None
    assert snap["verdict"] == "earnings-window"  # still de-risked, not vetoed


def test_graph_overlay_wiring_hard_block_rejects(monkeypatch):
    """A catalyst hard block must force a REJECT risk gate even when the
    size limits would pass."""
    import tradingagents.graph.trading_graph as tg
    from tradingagents.strategies import catalyst as cat_mod

    graph = object.__new__(tg.TradingAgentsGraph)
    graph.config = {
        "enable_strategy_overlays": True,
        "enable_events": True,
        "enable_orderflow": False,
        "enable_position_contract": False,
        "enable_risk_governor": True,
        "enable_computed_context": False,
        "risk_audit_enabled": False,
        "data_cache_dir": "~/.tradingagents",
        "target_vol": 0.15,
    }
    closes = [100.0 + 0.2 * i for i in range(300)]
    monkeypatch.setattr(graph, "_try_fetch_closes", lambda *a, **k: closes)

    snapshot = {
        "verdict": "earnings-hard-block",
        "scale": 0.4,
        "reasons": ["earnings hard block"],
        "hard_block": {"days_until": 3, "window_days": 7, "earnings_date": "2026-08-24"},
    }
    monkeypatch.setattr(cat_mod, "fetch_catalyst_data", lambda *a, **k: {"ok": True})
    monkeypatch.setattr(cat_mod, "build_catalyst_snapshot", lambda *a, **k: snapshot)
    monkeypatch.setattr(
        cat_mod,
        "fold_catalyst_into_overlay",
        lambda overlay, snap: {**overlay, "catalyst": snap, "position_scale": 0.4},
    )

    state = {"trade_date": "2026-08-19", "final_trade_decision": "Buy"}
    out = graph._apply_strategy_overlays(state, "AAPL")
    assert out["risk_gate"]["verdict"] == "REJECT"
    assert out["risk_halt"] is True
    assert any("hard block" in r for r in out["risk_gate"]["reasons"])


def test_graph_overlay_wiring_no_hard_block_passes(monkeypatch):
    """Without a hard block, a small size inside the limits stays PASS."""
    import tradingagents.graph.trading_graph as tg
    from tradingagents.strategies import catalyst as cat_mod

    graph = object.__new__(tg.TradingAgentsGraph)
    graph.config = {
        "enable_strategy_overlays": True,
        "enable_events": True,
        "enable_orderflow": False,
        "enable_position_contract": True,
        "enable_risk_governor": True,
        "enable_computed_context": False,
        "risk_audit_enabled": False,
        "target_vol": 0.15,
    }
    closes = [100.0 + 0.2 * i for i in range(300)]
    monkeypatch.setattr(graph, "_try_fetch_closes", lambda *a, **k: closes)

    snapshot = {"verdict": "no-imminent-catalyst", "scale": 1.0, "hard_block": None}
    monkeypatch.setattr(cat_mod, "fetch_catalyst_data", lambda *a, **k: {"ok": True})
    monkeypatch.setattr(cat_mod, "build_catalyst_snapshot", lambda *a, **k: snapshot)
    from tradingagents.strategies import catalyst as cat_mod2

    monkeypatch.setattr(
        cat_mod2,
        "fold_catalyst_into_overlay",
        lambda overlay, snap: {**overlay, "catalyst": snap, "position_scale": 1.0},
    )

    state = {"trade_date": "2026-08-19", "final_trade_decision": "Hold"}
    out = tg.TradingAgentsGraph._apply_strategy_overlays(graph, state, "AAPL")
    assert out["risk_gate"]["verdict"] in ("PASS", "WARN")

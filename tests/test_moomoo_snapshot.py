"""P0/P1 of `docs/design_moomoo_unused_api_surface.md`, offline.

The two readers behind `enable_moomoo_snapshot`:
`tradingagents/dataflows/moomoo.py::get_kl_quota_moomoo` (the K-line quota
pre-flight) and `::get_market_snapshot_moomoo` / `::_batched_snapshot` (the
batched market snapshot).

Offline: the SDK context and `_sdk_call` are mocked, so nothing touches OpenD.
"""

from __future__ import annotations

from unittest import mock

import pandas as pd
import pytest

from tradingagents.dataflows import moomoo


def _frame(codes):
    """A frame shaped like the SDK's `get_market_snapshot` result."""
    return pd.DataFrame(
        {
            "code": list(codes),
            "name": [f"{c} Inc" for c in codes],
            "last_price": [100.0 + i for i in range(len(codes))],
            "pe_ttm_ratio": [20.0] * len(codes),
            "total_market_val": [1.0e11] * len(codes),
        }
    )


def _patch(fn):
    """Run `_sdk_call` inline, so the test exercises our logic, not the SDK."""
    return mock.patch.object(moomoo, "_sdk_call", side_effect=lambda f, *a, **k: f(*a, **k))


@pytest.fixture
def gate_on():
    """`enable_moomoo_snapshot` on for one test, restored afterwards."""
    from tradingagents.dataflows.config import set_config
    from tradingagents.default_config import DEFAULT_CONFIG

    cfg = dict(DEFAULT_CONFIG)
    cfg["enable_moomoo_snapshot"] = True
    set_config(cfg)
    try:
        yield
    finally:
        set_config(dict(DEFAULT_CONFIG))


# --- the offender resolver ---------------------------------------------------


@pytest.mark.unit
def test_offender_resolver_handles_both_measured_message_shapes():
    """Both live refusals name a bare ticker while the caller holds US.TICKER."""
    batch = ["US.AAPL", "US.SQ", "US.SSLZY"]
    assert moomoo._snapshot_offender("Unknown stock. SQ", batch) == "US.SQ"
    assert (
        moomoo._snapshot_offender("US OTC market quote is not available for SSLZY.", batch)
        == "US.SSLZY"
    )


@pytest.mark.unit
def test_offender_resolver_returns_none_when_no_symbol_is_named():
    """A failure that names no symbol must not be blamed on an arbitrary one."""
    assert moomoo._snapshot_offender("some transport failure", ["US.AAPL"]) is None
    assert moomoo._snapshot_offender("Unknown stock. ZZZZZ", ["US.AAPL"]) is None


# --- the bisect --------------------------------------------------------------


@pytest.mark.unit
def test_a_bad_symbol_is_dropped_by_name_and_the_rest_still_return(gate_on):
    """The endpoint is all-or-nothing, so the bisect must save the good rows."""
    ctx = mock.Mock()
    ctx.get_market_snapshot.side_effect = [
        (-1, "Unknown stock. SQ"),
        (0, _frame(["US.AAPL", "US.MSFT"])),
    ]
    with mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx), _patch(None):
        res = moomoo._batched_snapshot(["US.AAPL", "US.SQ", "US.MSFT"])

    assert res["requested"] == 3
    assert res["returned"] == 2
    assert res["dropped"] == ["US.SQ"]
    assert res["failed"] == []
    assert {r["code"] for r in res["rows"]} == {"US.AAPL", "US.MSFT"}


@pytest.mark.unit
def test_several_bad_symbols_are_each_named_and_the_batch_terminates(gate_on):
    """Every refused symbol is recorded, and the retry loop cannot spin."""
    ctx = mock.Mock()
    ctx.get_market_snapshot.side_effect = [
        (-1, "Unknown stock. SQ"),
        (-1, "US OTC market quote is not available for SSLZY."),
        (-1, "Unknown stock. ZZZZZ"),
        (0, _frame(["US.AAPL"])),
    ]
    with mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx), _patch(None):
        res = moomoo._batched_snapshot(["US.AAPL", "US.SQ", "US.SSLZY", "US.ZZZZZ"])

    assert res["dropped"] == ["US.SQ", "US.SSLZY", "US.ZZZZZ"]
    assert res["returned"] == 1
    assert res["failed"] == []


@pytest.mark.unit
def test_a_chunk_of_only_bad_symbols_terminates_without_fabricating_rows(gate_on):
    """The bound that stops the retry loop: an all-bad chunk ends empty."""
    ctx = mock.Mock()
    ctx.get_market_snapshot.side_effect = lambda codes: (
        (-1, f"Unknown stock. {str(codes[0]).rsplit('.', 1)[-1]}")
    )
    with mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx), _patch(None):
        res = moomoo._batched_snapshot(["US.AAA", "US.BBB"], chunk=2)

    assert res["rows"] == []
    assert res["returned"] == 0
    assert sorted(res["dropped"]) == ["US.AAA", "US.BBB"]


@pytest.mark.unit
def test_a_failure_naming_no_symbol_is_recorded_never_silently_empty(gate_on):
    """An unattributable failure must surface as a reason, not as zero rows."""
    ctx = mock.Mock()
    ctx.get_market_snapshot.return_value = (-1, "connection reset")
    with mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx), _patch(None):
        res = moomoo._batched_snapshot(["US.AAPL", "US.MSFT"])

    assert res["returned"] == 0
    assert res["dropped"] == []
    assert res["failed"] and res["failed"][0]["reason"] == "connection reset"
    assert res["reason"] == "connection reset"


@pytest.mark.unit
def test_duplicate_symbols_are_requested_once(gate_on):
    """A duplicated name must not inflate the requested/returned counts."""
    ctx = mock.Mock()
    ctx.get_market_snapshot.return_value = (0, _frame(["US.AAPL"]))
    with mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx), _patch(None):
        res = moomoo._batched_snapshot(["US.AAPL", "US.AAPL", "US.AAPL"])

    assert res["requested"] == 1
    assert res["returned"] == 1


# --- the rendered surface ----------------------------------------------------


@pytest.mark.unit
def test_the_render_names_every_dropped_symbol_and_the_coverage(monkeypatch, gate_on):
    """Coverage travels with the number: the loss is printed, never implied."""
    monkeypatch.setattr(moomoo, "_batched_snapshot", lambda codes: {
        "rows": _frame(["US.AAPL"]).to_dict("records"),
        "requested": 3,
        "returned": 1,
        "dropped": ["US.SQ", "US.ZZZZZ"],
        "failed": [],
        "reason": None,
    })
    out = moomoo.get_market_snapshot_moomoo(["AAPL", "SQ", "ZZZZZ"], as_text=True)

    assert "requested 3, returned 1" in out
    assert "US.SQ" in out and "US.ZZZZZ" in out
    # it says the read is a live snapshot, not a dated close
    assert "not a dated close" in out
    assert "| US.AAPL |" in out


@pytest.mark.unit
def test_an_absent_cell_renders_na_never_a_zero():
    """An ETF has no equity valuation block; `n/a` is not `0.00`."""
    assert moomoo._fmt_snapshot_cell("pe_ttm_ratio", None) == "n/a"
    assert moomoo._fmt_snapshot_cell("pe_ttm_ratio", float("nan")) == "n/a"
    assert moomoo._fmt_snapshot_cell("pe_ttm_ratio", 20.0) == "20.00"
    assert moomoo._fmt_snapshot_cell("total_market_val", 4.9055e12) == "4,905.5B"


# --- the quota reader --------------------------------------------------------


@pytest.mark.unit
def test_quota_remaining_is_none_not_zero_when_unreadable():
    """`None` means unreadable; `0` means exhausted. Collapsing them refuses runs."""
    ctx = mock.Mock()
    ctx.get_history_kl_quota.side_effect = RuntimeError("OpenD down")
    with mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx), _patch(None):
        assert moomoo.kl_quota_remaining_moomoo() is None

    ctx = mock.Mock()
    ctx.get_history_kl_quota.return_value = (-1, "no permission")
    with mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx), _patch(None):
        assert moomoo.kl_quota_remaining_moomoo() is None


@pytest.mark.unit
def test_quota_remaining_reads_the_second_element(gate_on):
    ctx = mock.Mock()
    ctx.get_history_kl_quota.return_value = (0, (26, 74, []))
    with mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx), _patch(None):
        assert moomoo.kl_quota_remaining_moomoo() == 74


@pytest.mark.unit
def test_the_quota_render_states_used_of_total_and_remaining(gate_on):
    ctx = mock.Mock()
    ctx.get_history_kl_quota.return_value = (
        0,
        (26, 74, [{"code": "US.MSFT", "name": "Microsoft", "request_time": "2026-09-18"}]),
    )
    with mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx), _patch(None):
        out = moomoo.get_kl_quota_moomoo()

    assert "Used 26 of 100" in out
    assert "74 remaining" in out
    assert "US.MSFT" in out


# --- the gate ----------------------------------------------------------------


@pytest.mark.unit
def test_gate_off_reads_nothing_at_all(monkeypatch):
    """Gate off => no context is constructed and no SDK call is made."""
    monkeypatch.setattr(moomoo, "_ensure_ctx", lambda: pytest.fail("gate off must not open a context"))

    assert "disabled" in moomoo.get_market_snapshot_moomoo(["AAPL"], as_text=True)
    assert moomoo.get_market_snapshot_moomoo(["AAPL"])["disabled"]
    assert "disabled" in moomoo.get_kl_quota_moomoo()
    assert moomoo.kl_quota_remaining_moomoo() is None


@pytest.mark.unit
def test_gate_on_opens_the_context(monkeypatch, gate_on):
    """The complement: with the gate on the reader actually reads."""
    ctx = mock.Mock()
    ctx.get_history_kl_quota.return_value = (0, (1, 99, []))
    monkeypatch.setattr(moomoo, "_ensure_ctx", lambda: ctx)
    monkeypatch.setattr(moomoo, "_sdk_call", lambda f, *a, **k: f(*a, **k))
    assert moomoo.kl_quota_remaining_moomoo() == 99


@pytest.mark.unit
def test_the_structured_and_text_forms_are_one_read_not_two(gate_on):
    """A second public function would be a second producer for the same read."""
    monkeypatch_res = {
        "rows": _frame(["US.AAPL"]).to_dict("records"),
        "requested": 1,
        "returned": 1,
        "dropped": [],
        "failed": [],
        "reason": None,
    }
    with mock.patch.object(moomoo, "_batched_snapshot", return_value=monkeypatch_res):
        structured = moomoo.get_market_snapshot_moomoo(["AAPL"])
        text = moomoo.get_market_snapshot_moomoo(["AAPL"], as_text=True)

    assert structured["rows"] == monkeypatch_res["rows"]
    assert "| US.AAPL |" in text
    # the renderer is driven by the structured result, not a second call
    assert moomoo._render_market_snapshot(structured) == text


@pytest.mark.unit
def test_the_gate_off_structured_form_is_empty_not_a_silent_zero():
    """`disabled` is named; the empty rows must not read as `measured zero`."""
    res = moomoo.get_market_snapshot_moomoo(["AAPL"])
    assert res["disabled"] and res["rows"] == []
    assert res["requested"] == 0

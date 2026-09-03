"""Hermetic tests for the moomoo value-dip screener (Stock Screening V2).

All OpenQuoteContext / SDK plumbing is mocked; nothing touches OpenD or the
network. The factor-id -> enum-name label map is built from the installed SDK
enums, which import without any RPC.
"""
import inspect
from unittest import mock

import pytest

from tradingagents.dataflows import moomoo


def _sdk_item(*fields):
    """Build a get_stock_screen result row from (factor_id, value_type, value)."""
    res = []
    for fid, vt, val in fields:
        res.append(
            {
                "type": "x",
                "value_type": vt,
                "property": {"name": fid},
                "sval": val if vt == 1 else None,
                "ival": val if vt == 2 else None,
                "aval": val if vt == 3 else None,
                "dval": val if vt == 4 else None,
            }
        )
    return {"stock_id": 1, "results": res}


def _patched_ctx(item_or_items):
    """ctx with get_stock_screen returning one page containing the item(s)."""
    ctx = mock.MagicMock()
    if isinstance(item_or_items, list):
        ctx.get_stock_screen.return_value = (0, (True, len(item_or_items), item_or_items))
    else:
        ctx.get_stock_screen.return_value = (0, (True, 1, [item_or_items]))
    return ctx


@pytest.mark.unit
def test_screen_rows_mapped_and_symbols_stripped():
    item = _sdk_item(
        (1101, 1, "US.EIX"), (1102, 1, "Edison International"),
        (2201, 4, 56.38), (2303, 4, 5.82), (2209, 4, -0.309),
        (3102, 4, -0.235), (4110, 4, 0.28765), (52, 4, 31.624),
    )
    ctx = _patched_ctx(item)
    with (
        mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx),
        mock.patch.object(moomoo, "_sdk_call", side_effect=lambda fn, *a, **k: fn(*a, **k)),
    ):
        rows = moomoo.screen_value_dip_moomoo()
    assert len(rows) == 1
    r = rows[0]
    assert r["symbol"] == "EIX"                       # US. prefix stripped
    assert r["name"] == "Edison International"
    assert r["price"] == pytest.approx(56.38)
    assert r["pe_ttm"] == pytest.approx(5.82)
    assert r["price_to_52w_high"] == pytest.approx(-0.309)
    assert r["change_pct_5d"] == pytest.approx(-0.235)
    assert r["roe"] == pytest.approx(0.28765)
    assert r["rsi"] == pytest.approx(31.624)


@pytest.mark.unit
def test_screen_paginates_until_last_page():
    a = _sdk_item((1101, 1, "US.EIX"), (2201, 4, 56.38))
    b = _sdk_item((1101, 1, "US.PCG"), (2201, 4, 13.33))
    ctx = mock.MagicMock()
    ctx.get_stock_screen.side_effect = [
        (0, (False, 2, [a])),
        (0, (True, 2, [b])),
    ]
    with (
        mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx),
        mock.patch.object(moomoo, "_sdk_call", side_effect=lambda fn, *a, **k: fn(*a, **k)),
    ):
        rows = moomoo.screen_value_dip_moomoo(max_pages=6)
    assert [r["symbol"] for r in rows] == ["EIX", "PCG"]
    assert ctx.get_stock_screen.call_count == 2


@pytest.mark.unit
def test_screen_skips_row_without_code():
    item = _sdk_item((1102, 1, "No Code"), (2201, 4, 12.0))
    ctx = _patched_ctx(item)
    with (
        mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx),
        mock.patch.object(moomoo, "_sdk_call", side_effect=lambda fn, *a, **k: fn(*a, **k)),
    ):
        rows = moomoo.screen_value_dip_moomoo()
    assert rows == []


@pytest.mark.unit
def test_ival_factor_maps_to_int():
    item = _sdk_item((1101, 1, "US.PCG"), (3102, 2, -5))
    ctx = _patched_ctx(item)
    with (
        mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx),
        mock.patch.object(moomoo, "_sdk_call", side_effect=lambda fn, *a, **k: fn(*a, **k)),
    ):
        rows = moomoo.screen_value_dip_moomoo()
    assert rows[0]["change_pct_5d"] == -5


@pytest.mark.unit
def test_unknown_market_raises():
    with (
        mock.patch.object(moomoo, "_ensure_ctx", return_value=mock.MagicMock()),
        pytest.raises(moomoo.MoomooNotConfiguredError),
    ):
        moomoo.screen_value_dip_moomoo(market="XX")


@pytest.mark.unit
def test_default_params_match_value_dip_recipe():
    sig = inspect.signature(moomoo.screen_value_dip_moomoo)
    assert sig.parameters["pe_max"].default == 30.0
    assert sig.parameters["market_cap_min"].default == 1_000_000_000.0
    assert sig.parameters["roe_min"].default == 0.12
    assert sig.parameters["chg5d_max"].default == -0.05
    assert sig.parameters["rsi_max"].default == 35.0
    assert sig.parameters["market"].default == "US"
    assert sig.parameters["price_min"].default == 5.0
    assert sig.parameters["pb_min"].default is None
    assert sig.parameters["pb_max"].default is None
    assert sig.parameters["dip_days"].default == 5


@pytest.mark.unit
def test_builder_uses_dip_days_and_pb_bounds():
    """price/PB bounds and the dip window must reach the request builder."""
    req = mock.MagicMock()
    ctx = mock.MagicMock()
    ctx.get_stock_screen.return_value = (0, (True, 0, []))
    with (
        mock.patch("moomoo.StockScreenRequest", return_value=req),
        mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx),
        mock.patch.object(moomoo, "_sdk_call", side_effect=lambda fn, *a, **k: fn(*a, **k)),
    ):
        moomoo.screen_value_dip_moomoo(
            dip_days=20, price_min=5.0, pb_min=0.5, pb_max=3.0,
        )
    # The fn imports enums locally; assert via the kwargs we can observe.
    def _kw(name):
        for c in req.add_simple_property.call_args_list:
            if str(c.kwargs.get("name")) == str(name):
                return c.kwargs
        return None
    from moomoo.quote.stock_screen_const import CumulativeProperty, SimpleProperty
    price_kw = _kw(SimpleProperty.PRICE)
    assert price_kw and price_kw.get("lower") == 5.0
    pb_kw = _kw(SimpleProperty.PB)
    assert pb_kw and pb_kw.get("lower") == 0.5 and pb_kw.get("upper") == 3.0
    cum_kw = None
    for c in req.add_cumulative_property.call_args_list:
        if str(c.kwargs.get("name")) == str(CumulativeProperty.PRICE_CHANGE_PCT):
            cum_kw = c.kwargs
    assert cum_kw and cum_kw.get("days") == 20

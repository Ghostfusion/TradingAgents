"""Tests for the FINRA market-analyst additions (order-flow spec items 1-2).

Covers the Reg SHO daily short-sale-volume aggregation + staleness gate and
the ATS weekly off-exchange-flow aggregation, both via a monkeypatched
``_get`` (no network). The tools' router/exports are covered by the wiring gate.
"""

import datetime

import pytest

import tradingagents.dataflows.finra as finra

pytestmark = pytest.mark.timeout(90)

# ---------------------------------------------------------------------------
# Reg SHO daily short-sale volume
# ---------------------------------------------------------------------------


def _ssv_row(day, short, total, exempt=0, facility="NCTRF", mkt="B"):
    return {
        "tradeReportDate": day,
        "shortParQuantity": short,
        "shortExemptParQuantity": exempt,
        "totalParQuantity": total,
        "reportingFacilityCode": facility,
        "marketCode": mkt,
    }


def _stub_today(iso):
    """Stub datetime module for finra so 'today' is fixed (no recursion)."""
    import types

    class _D:
        @classmethod
        def today(cls):
            return datetime.date.fromisoformat(iso)

        @staticmethod
        def fromisoformat(s):
            return datetime.date.fromisoformat(s)

    return types.SimpleNamespace(date=_D)


def test_short_sale_volume_aggregates_across_facilities(monkeypatch):
    rows = [
        _ssv_row("2026-01-06", 1_000_000, 2_000_000),
        _ssv_row("2026-01-06", 600_000, 1_000_000, facility="XATS"),  # same day, 2nd facility
        _ssv_row("2026-01-05", 400_000, 1_000_000),
    ]
    monkeypatch.setattr(finra, "_get", lambda *a, **k: rows)
    monkeypatch.setattr(finra, "datetime", _stub_today("2026-01-08"))
    out = finra.get_short_sale_volume("AAPL", days=2)
    assert "2026-01-06: short 1,600,000 / total 3,000,000" in out
    assert "53.3% short" in out  # 1.6M/3.0M
    # newest served date within staleness -> no stale banner
    assert "NOTE:" not in out


def test_short_sale_volume_staleness_banner(monkeypatch):
    monkeypatch.setattr(finra, "_get",
                        lambda *a, **k: [_ssv_row("2026-01-06", 100, 200)])
    monkeypatch.setattr(finra, "datetime", _stub_today("2026-09-01"))
    out = finra.get_short_sale_volume("AAPL", days=1)
    assert "NOTE:" in out and "not a live feed" in out


def test_short_sale_volume_degrades(monkeypatch):
    monkeypatch.setattr(finra, "_get", lambda *a, **k: (_ for _ in ()).throw(ConnectionError("down")))
    out = finra.get_short_sale_volume("AAPL")
    assert "unavailable" in out
    assert finra.get_short_sale_volume("") == "short-sale volume unavailable: no ticker"


# ---------------------------------------------------------------------------
# ATS weekly off-exchange flow
# ---------------------------------------------------------------------------


def _ats_row(week, shares, trades, notional):
    return {
        "issueSymbolIdentifier": "MSFT",
        "weekStartDate": week,
        "totalWeeklyShareQuantity": shares,
        "totalWeeklyTradeCount": trades,
        "totalNotionalSum": notional,
        "marketParticipantName": "UBSA UBS ATS",
    }


def test_dark_pool_flow_aggregates_per_week(monkeypatch):
    rows = [_ats_row("2023-11-06", 5_000_000, 1_000, 150_000_000.0),
            _ats_row("2023-10-30", 3_000_000, 600, 90_000_000.0),
            _ats_row("2023-11-06", 2_000_000, 400, 60_000_000.0)]  # same week, 2nd ATS
    monkeypatch.setattr(finra, "_get", lambda *a, **k: rows)
    out = finra.get_dark_pool_flow("MSFT", weeks=2)
    assert "week 2023-11-06: 7,000,000 shares / 1,400 trades" in out
    assert "$210,000,000 notional" in out
    # stale (weekly tier frozen) -> banner
    assert "NOTE:" in out and "no live free per-ticker dark-pool source" in out


def test_dark_pool_flow_filters_other_issues(monkeypatch):
    rows = [_ats_row("2023-11-06", 5_000_000, 1_000, 150_000_000.0),
            dict(_ats_row("2023-11-06", 9_000_000, 900, 1.0), issueSymbolIdentifier="AAPL")]
    monkeypatch.setattr(finra, "_get", lambda *a, **k: rows)
    out = finra.get_dark_pool_flow("MSFT", weeks=1)
    assert "5,000,000 shares" in out and "9,000,000" not in out  # only the MSFT row


def test_dark_pool_flow_degrades(monkeypatch):
    monkeypatch.setattr(finra, "_get", lambda *a, **k: (_ for _ in ()).throw(TimeoutError("t")))
    out = finra.get_dark_pool_flow("MSFT")
    assert "unavailable" in out
    assert finra.get_dark_pool_flow("") == "dark-pool flow unavailable: no ticker"

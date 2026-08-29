"""Phase-2 tests: fixed-risk sizing (risk_sizing) + pre-trade checks (risk_checks)."""

import pytest

from tradingagents.strategies import risk_checks, risk_sizing as rs
from tradingagents.strategies.value_dip import tranche_plan, tranche_risk_read

pytestmark = pytest.mark.timeout(180)


# ---------------------------------------------------------------------------
# risk_sizing
# ---------------------------------------------------------------------------


def test_risk_points():
    assert rs.risk_points(100, 95) == 5.0
    assert rs.risk_points(95, 100) == 5.0
    assert rs.risk_points(100, 100) == 0.0
    assert rs.risk_points(None, 95) == 0.0


def test_riskable_money():
    assert rs.riskable_money(100000, 0.015, 0.0) == pytest.approx(1500.0)
    # Commission reduces the usable budget.
    assert rs.riskable_money(100000, 0.015, 0.001) == pytest.approx(1500.0 / 1.001)
    assert rs.riskable_money(0, 0.01, 0.0) == 0.0
    assert rs.riskable_money(100000, 1.5, 0.0) == 0.0  # risk_frac > 1


def test_risk_money():
    # risk budget 1500 / risk distance 5 -> 300 units.
    assert rs.risk_money(100, 95, 100000, 0.015) == 300.0
    assert rs.risk_money(100, 95, 100000, 0.015, commission_rate=0.0) == 300.0
    # Degenerate stop (no risk distance) -> 0, never a fabricated size.
    assert rs.risk_money(100, 100, 100000, 0.015) == 0.0
    # Hard limit binds.
    assert rs.risk_money(100, 95, 100000, 0.015, hard_limit=100) == 100.0
    # Exchange rate scales down.
    assert rs.risk_money(100, 95, 100000, 0.015, exchange_rate=2.0) == 150.0


def test_risk_quantity_splits_transches():
    total = rs.risk_quantity(100, 95, 100000, 0.015, units=3)
    assert total == pytest.approx(300.0)
    per = 300.0 / 3
    # Batching rounds each tranche down.
    batched = rs.risk_quantity(100, 95, 100000, 0.015, units=3, unit_batch_size=20)
    assert batched == pytest.approx(3 * (per // 20) * 20)


def test_tranche_plan_commission_aware():
    # Commission reduces size (crossing an integer allocation boundary).
    p0 = tranche_plan(100, 2.0, risk_pct=0.03, account=100000)
    pc = tranche_plan(100, 2.0, risk_pct=0.03, account=100000, commission_rate=0.10)
    assert pc["valid"]
    assert pc["total_shares"] < p0["total_shares"]
    assert pc["capital_at_risk_pct"] <= 0.03 * 1.01


def test_tranche_risk_read_still_valid_and_unchanged_semantics():
    import math

    closes = [100.0 + 3.0 * math.sin(i / 5) for i in range(60)]
    r = tranche_risk_read(closes)
    assert r["valid"]
    assert r["capital_at_risk_pct"] is not None
    assert "peak_deployed_pct" in r
    assert "peak_ok" in r


# ---------------------------------------------------------------------------
# risk_checks
# ---------------------------------------------------------------------------


def test_pre_trade_check_notional_cap():
    assert risk_checks.pre_trade_check("AAPL", 1000.0, {}, max_notional=5000.0) is True
    # Single order over the cap -> denied.
    assert risk_checks.pre_trade_check("AAPL", 6000.0, {}, max_notional=5000.0) is False
    # Cumulative cap: existing 4000 + new 2000 exceeds 5000.
    assert risk_checks.pre_trade_check("AAPL", 2000.0, {"AAPL": 4000.0}, max_notional=5000.0) is False
    # Negative/None notional -> denied.
    assert risk_checks.pre_trade_check("AAPL", -1.0, {}, max_notional=5000.0) is False


def test_pre_trade_check_does_not_mutate_book():
    book = {"AAPL": 1000.0}
    risk_checks.pre_trade_check("AAPL", 2000.0, book, max_notional=5000.0)
    assert book == {"AAPL": 1000.0}  # denied/approved never commits here


def test_rate_limiter_rolling_window():
    lim = risk_checks.RateLimiter(max_count=3, window_secs=10.0)
    assert [lim.allow(t) for t in (0, 1, 2)] == [True, True, True]
    assert lim.allow(3) is False  # 4th within window
    assert lim.count == 3
    assert lim.allow(15) is True  # first expired (0 < 15-10)


def test_pre_trade_check_respects_limiter():
    lim = risk_checks.RateLimiter(max_count=1, window_secs=5.0)
    assert risk_checks.pre_trade_check("AAPL", 10.0, {}, max_notional=100.0, limiter=lim, now=0.0) is True
    assert risk_checks.pre_trade_check("AAPL", 10.0, {}, max_notional=100.0, limiter=lim, now=1.0) is False


def test_notional():
    assert risk_checks.notional(100.0, 10) == 1000.0
    assert risk_checks.notional(None, 10) == 0.0

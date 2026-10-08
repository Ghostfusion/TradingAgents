"""The Form 4 insider vendor: the optional ``edgar`` extra, and what its absence,
an empty window, and a real filing each produce.

Offline: ``sec_edgar._edgar_module`` is replaced by a fake, so no EDGAR request is
made and this suite passes with the optional ``edgartools`` extra absent - which
is the state a bare ``pip install tradingagents`` is in.

The four tests defend what a plausible bug would break: a missing extra degrading
as a *reason* rather than an exception, the window being asserted rather than
assumed, a derived value being nulled when a leg is missing (rather than read as
zero), and the render collapsing to the per-insider net that is the only thing
the prose adds over a table of trades.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest

from tradingagents.dataflows import sec_edgar
from tradingagents.dataflows.errors import NoMarketDataError

pytestmark = pytest.mark.timeout(600)


class _Summary:
    def __init__(self, name: str, position: str, plan: bool | None) -> None:
        self.insider_name = name
        self.position = position
        self.has_10b5_1_plan = plan


class _Form4:
    def __init__(
        self, summary: _Summary, trades: pd.DataFrame, issuer_cik: int = 320193
    ) -> None:
        self._summary = summary
        self.market_trades = trades
        # EDGAR pads the CIK to ten chars on the filing and leaves it bare on the
        # company, so the fake pads too - the comparison must be on the integer.
        self.issuer = SimpleNamespace(cik=str(issuer_cik).zfill(10))

    def get_ownership_summary(self) -> _Summary:
        return self._summary


class _Filing:
    def __init__(self, form4: _Form4, filed: date) -> None:
        self._form4 = form4
        self.filing_date = filed

    def obj(self) -> _Form4:
        return self._form4


class _Company:
    def __init__(self, ticker: str, filings: list, calls: list) -> None:
        self.ticker = ticker
        self.cik = 320193  # Apple's, the queried issuer in every test below
        self._filings = filings
        self._calls = calls

    def get_filings(self, **kwargs) -> list:
        self._calls.append((self.ticker, kwargs))
        return self._filings


def _fake_edgar(filings: list, calls: list, identity: list | None = None):
    """A stand-in for the ``edgar`` module: the three names the vendor touches."""
    return SimpleNamespace(
        Company=lambda ticker: _Company(ticker, filings, calls),
        set_identity=(
            lambda value: identity.append(value) if identity is not None else None
        ),
    )


def _trade(day: date, code: str, shares, price, remaining, kind: str) -> dict:
    return {
        "Date": day,
        "Code": code,
        "Shares": shares,
        "Price": price,
        "Remaining": remaining,
        "AcquiredDisposed": "A" if code == "P" else "D",
        "DirectIndirect": "D",
        "TransactionType": kind,
    }


@pytest.fixture()
def _clean_state(monkeypatch):
    """The two module-level memos, so one test cannot leak into the next."""
    monkeypatch.setattr(sec_edgar, "_EDGAR_IDENTITY_SET", False)
    monkeypatch.setattr(sec_edgar, "_EDGAR_IMPORT_ERROR", None)


def test_the_absent_extra_is_a_reason_not_a_crash(monkeypatch, _clean_state):
    """A bare install has no ``edgar``: the vendor must name the install, not raise."""
    monkeypatch.setattr(sec_edgar, "_EDGAR_IMPORT_ERROR", "No module named 'edgar'")
    monkeypatch.setattr(sec_edgar, "_edgar_module", lambda: None)

    with pytest.raises(NoMarketDataError) as exc:
        sec_edgar.get_insider_transactions_sec_edgar("AAPL")

    assert "edgartools extra is not installed" in exc.value.detail
    assert 'tradingagents[edgar]' in exc.value.detail


def test_the_window_is_passed_to_edgar_and_rows_are_newest_first(monkeypatch, _clean_state):
    """The window must reach EDGAR (a silently-ignored filter is a wrong read),
    the identity must be set once, and the rows must come back newest first."""
    calls: list = []
    identity: list = []
    trades = pd.DataFrame([
        _trade(date(2026, 9, 1), "P", 100, 10.0, 200, "Purchase"),
        _trade(date(2026, 10, 1), "S", 50, None, 150, "Sale"),
    ])
    filing = _Filing(_Form4(_Summary("Jane Doe", "Director", True), trades), date(2026, 10, 3))
    monkeypatch.setattr(
        sec_edgar, "_edgar_module", lambda: _fake_edgar([filing], calls, identity)
    )

    rows = sec_edgar._insider_rows("aapl", "2026-01-01", "2026-12-31")

    assert calls == [("AAPL", {"form": 4, "date": ("2026-01-01", "2026-12-31")})]
    assert identity == [sec_edgar._IDENTITY]
    assert [r["date"] for r in rows] == ["2026-10-01", "2026-09-01"]
    # A missing price is unknown, not free: the derived value is null, never 0.
    assert rows[0]["value"] is None
    assert rows[1]["value"] == 1000.0
    assert rows[1]["plan_10b5_1"] is True
    assert rows[1]["position"] == "Director"


def test_an_empty_window_raises_no_data_naming_the_window(monkeypatch, _clean_state):
    """No Form 4 in the window is no-data with the window in the reason, so the
    router can advance the chain instead of returning an empty table."""
    calls: list = []
    monkeypatch.setattr(sec_edgar, "_edgar_module", lambda: _fake_edgar([], calls))

    with pytest.raises(NoMarketDataError) as exc:
        sec_edgar._insider_rows("AAPL", "2026-01-01", "2026-12-31")

    assert "no open-market Form 4" in exc.value.detail
    assert "2026-01-01" in exc.value.detail and "2026-12-31" in exc.value.detail


def test_the_render_gives_the_per_insider_open_market_net(monkeypatch, _clean_state):
    """The net is the one number the prose adds over the table, and it must count
    open-market only - a P and an S by one insider net to their difference."""
    calls: list = []
    trades = pd.DataFrame([
        _trade(date(2026, 9, 1), "P", 100, 10.0, 200, "Purchase"),
        _trade(date(2026, 9, 2), "S", 40, 20.0, 160, "Sale"),
    ])
    filing = _Filing(_Form4(_Summary("Jane Doe", "Director", True), trades), date(2026, 9, 3))
    monkeypatch.setattr(sec_edgar, "_edgar_module", lambda: _fake_edgar([filing], calls))

    out = sec_edgar.get_insider_transactions_sec_edgar("AAPL", days=30)

    assert "net +60 shares" in out
    assert "bought 100 for $1,000" in out
    assert "sold 40 for $800" in out
    # The flag is the FILING's, so both trades in it carry it: 2, not 1.
    assert "Rule 10b5-1: 2 transaction(s)" in out
    # The subset must be stated, so "no buys" is never read as "no Form 4".
    assert "OPEN-MARKET" in out


def test_a_reporting_owners_filing_is_not_attributed_to_the_queried_issuer(
    monkeypatch, _clean_state
):
    """A CIK's Form 4 feed also carries the filings that CIK made AS A REPORTING
    OWNER of another company's stock. Verified live 2026-10-08: XOM's trailing-365d
    feed held 42 Form 4s, one of them ProPetro Holding Corp.'s. A row must follow
    the filing's OWN issuer, never the query - a foreign trade in this name is a
    fabricated decision, not a missing one."""
    calls: list = []
    ours = pd.DataFrame([_trade(date(2026, 9, 1), "P", 100, 10.0, 200, "Purchase")])
    theirs = pd.DataFrame([_trade(date(2026, 9, 2), "P", 4_000, 60.0, 0, "Purchase")])
    filings = [
        _Filing(
            _Form4(_Summary("Jane Doe", "Director", True), ours), date(2026, 9, 3)
        ),
        _Filing(
            _Form4(_Summary("Other Person", "10% Owner", None), theirs, issuer_cik=1680247),
            date(2026, 9, 4),
        ),
    ]
    monkeypatch.setattr(sec_edgar, "_edgar_module", lambda: _fake_edgar(filings, calls))

    rows = sec_edgar._insider_rows("AAPL", "2026-01-01", "2026-12-31")

    assert [r["insider"] for r in rows] == ["Jane Doe"]
    assert all(r["shares"] != 4_000 for r in rows)


def test_a_filing_whose_issuer_cannot_be_read_is_dropped_not_guessed(
    monkeypatch, _clean_state
):
    """Fail closed at the boundary: an issuer we cannot read is not this issuer's,
    so the row is dropped (a smaller count) rather than attributed (a wrong one)."""
    calls: list = []
    trades = pd.DataFrame([_trade(date(2026, 9, 1), "P", 100, 10.0, 200, "Purchase")])
    unreadable = _Form4(_Summary("Jane Doe", "Director", True), trades)
    unreadable.issuer = None
    monkeypatch.setattr(
        sec_edgar,
        "_edgar_module",
        lambda: _fake_edgar([_Filing(unreadable, date(2026, 9, 3))], calls),
    )

    with pytest.raises(NoMarketDataError) as exc:
        sec_edgar._insider_rows("AAPL", "2026-01-01", "2026-12-31")

    assert "no open-market Form 4" in exc.value.detail

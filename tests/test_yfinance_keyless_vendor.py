"""Keyless yfinance vendor functions: earnings calendar, ownership, analyst ratings.

These wire yfinance's keyless ``Ticker`` surface as registered fallbacks for
the earnings_calendar / analyst_ratings / institution_data categories, so a
run never depends on a moomoo gateway or a paid key for those signals. Hermetic:
mock ``yf.Ticker`` and its DataFrame methods, never hit the network.
"""

import unittest
from unittest import mock

import pandas as pd
import pytest

from tradingagents.dataflows import y_finance

pytestmark = pytest.mark.timeout(180)


def _earnings_df():
    idx = pd.to_datetime(["2026-08-06", "2026-05-07", "2026-02-05"])
    return pd.DataFrame(
        {
            "EPS Estimate": [10.0, 9.5, 9.0],
            "Reported EPS": [10.5, 9.2, 8.8],
            "Surprise(%)": [5.0, -3.1, -2.2],
        },
        index=idx,
    )


def _inst_df():
    return pd.DataFrame(
        {
            "Holder": ["Vanguard Group", "BlackRock Inc"],
            "Shares": [1000000, 900000],
            "Date Reported": ["2025-12-31", "2025-12-31"],
            "% Out": [5.1, 4.6],
        }
    )


def _major_df():
    return pd.DataFrame({0: ["% of Shares Held by All Insiders", "Value"], 1: ["0.51%", "42.00%"]})


def _recs_df():
    return pd.DataFrame({"strongBuy": [5], "buy": [12], "hold": [3], "underperform": [0], "sell": [1]})


def _targets_df():
    return pd.DataFrame(
        {"current": [180.0], "low": [150.0], "high": [200.0], "mean": [178.0], "median": [179.0]}
    )


class _Ticker:
    def get_earnings_dates(self, limit=8):
        return _earnings_df()

    @property
    def institutional_holders(self):
        return _inst_df()

    @property
    def major_holders(self):
        return _major_df()

    @property
    def recommendations_summary(self):
        return _recs_df()

    @property
    def analyst_price_targets(self):
        return _targets_df()


class KeylessYFinanceTests(unittest.TestCase):
    @mock.patch.object(y_finance, "require_symbol", side_effect=lambda s: s)
    @mock.patch.object(y_finance, "yf")
    def test_earnings_calendar_returns_rows(self, mock_yf, _):
        mock_yf.Ticker.return_value = _Ticker()
        out = y_finance.get_earnings_calendar_yfinance("AAPL")
        self.assertIn("Earnings calendar for AAPL", out)
        self.assertIn("estimate=10.00", out)
        self.assertIn("reported=10.50", out)
        self.assertIn("surprise_pct=5.00", out)

    @mock.patch.object(y_finance, "require_symbol", side_effect=lambda s: s)
    @mock.patch.object(y_finance, "yf")
    def test_institution_holdings_returns_rows(self, mock_yf, _):
        mock_yf.Ticker.return_value = _Ticker()
        out = y_finance.get_institution_holdings_yfinance("AAPL")
        self.assertIn("Ownership for AAPL", out)
        self.assertIn("Vanguard Group", out)
        self.assertIn("pct_out=5.10%", out)

    @mock.patch.object(y_finance, "require_symbol", side_effect=lambda s: s)
    @mock.patch.object(y_finance, "yf")
    def test_analyst_ratings_returns_recs_and_targets(self, mock_yf, _):
        mock_yf.Ticker.return_value = _Ticker()
        out = y_finance.get_analyst_ratings_yfinance("AAPL")
        self.assertIn("Analyst ratings for AAPL", out)
        self.assertIn("buy: 12", out)
        self.assertIn("mean: 178.00", out)


class TestFundamentalsFormattingGuards(unittest.TestCase):
    """Regression (MSFT 2026-09-08): dividend yield 0.73 rendered as 73.00%
    (percent-scaled input) and D/E 29.118 vs the true 0.13 (units artifact).
    The formatter must re-normalize a >25% yield and never emit an
    implausible D/E."""

    @mock.patch.object(y_finance, "require_symbol", side_effect=lambda s: s)
    @mock.patch.object(y_finance, "yf")
    def test_dividend_yield_percent_scaled_is_normalized(self, mock_yf, _):
        info = {"longName": "TestCorp", "dividendYield": 0.73}
        mock_yf.Ticker.return_value = _Ticker()
        mock_yf.Ticker.return_value.info = info
        out = y_finance.get_fundamentals("TST")
        self.assertIn("Dividend Yield: 0.73%", out)
        self.assertNotIn("73.00%", out)

    @mock.patch.object(y_finance, "require_symbol", side_effect=lambda s: s)
    @mock.patch.object(y_finance, "yf")
    def test_debt_to_equity_implausible_is_flagged(self, mock_yf, _):
        info = {"longName": "TestCorp", "debtToEquity": 29.118, "dividendYield": 0.0073}
        mock_yf.Ticker.return_value = _Ticker()
        mock_yf.Ticker.return_value.info = info
        out = y_finance.get_fundamentals("TST")
        self.assertIn("Debt to Equity: n/a (implausible vendor value > 10)", out)
        self.assertIn("Dividend Yield: 0.73%", out)

    @mock.patch.object(y_finance, "require_symbol", side_effect=lambda s: s)
    @mock.patch.object(y_finance, "yf")
    def test_dividend_yield_is_cross_checked_against_the_payment_record(self, mock_yf, _):
        """QQQI 2026-09-13: info.dividendYield 0.09 renders as 9.00% while the
        SAME vendor's monthly record pays ~0.65/share (14.3% at 54.56). The
        leaf must carry both figures, so a report cannot quote the bad field
        as the fund's distribution rate."""
        info = {
            "longName": "NEOS NASDAQ-100(R) High Income ETF",
            "dividendYield": 0.09,
            "regularMarketPrice": 54.56,
        }
        tr = _Ticker()
        tr.info = info
        now = pd.Timestamp.now(tz="America/New_York")
        tr.dividends = pd.Series([0.6518] * 12, index=pd.date_range(end=now, periods=12, freq="30D"))
        mock_yf.Ticker.return_value = tr
        out = y_finance.get_fundamentals("QQQI")
        self.assertIn("Dividend Yield: 9.00%", out)
        self.assertIn("contradicts the same vendor's trailing-12m dividend record", out)
        self.assertIn("14.34% at 54.56", out)

    @mock.patch.object(y_finance, "require_symbol", side_effect=lambda s: s)
    @mock.patch.object(y_finance, "yf")
    def test_dividend_yield_note_silent_when_the_record_agrees(self, mock_yf, _):
        info = {
            "longName": "TestCorp",
            "dividendYield": 0.02,
            "regularMarketPrice": 100.0,
        }
        tr = _Ticker()
        tr.info = info
        now = pd.Timestamp.now(tz="America/New_York")
        tr.dividends = pd.Series([0.50] * 4, index=pd.date_range(end=now, periods=4, freq="91D"))
        mock_yf.Ticker.return_value = tr
        out = y_finance.get_fundamentals("TST")
        self.assertIn("Dividend Yield: 2.00%", out)
        self.assertNotIn("NOTE:", out)

    @mock.patch.object(y_finance, "require_symbol", side_effect=lambda s: s)
    @mock.patch.object(y_finance, "yf")
    def test_dividend_yield_note_absent_without_a_payment_record(self, mock_yf, _):
        # No dividend history and no live price -> nothing to cross-check.
        info = {"longName": "TestCorp", "dividendYield": 0.0073}
        mock_yf.Ticker.return_value = _Ticker()
        mock_yf.Ticker.return_value.info = info
        out = y_finance.get_fundamentals("TST")
        self.assertIn("Dividend Yield: 0.73%", out)
        self.assertNotIn("NOTE:", out)


_NVDA_QUARTERLY_BALANCE_CSV = (
    # Verbatim rows from the 2026-09-12 NVDA run's yfinance quarterly balance
    # sheet: a net-cash company reported with a positive vendor "Net Debt".
    ",2026-07-31,2026-04-30,2026-01-31,2025-10-31,2025-07-31\n"
    "Net Debt,10923000000.0,,,,\n"
    "Total Debt,38351000000.0,12348000000.0,11040000000.0,10481000000.0,10598000000.0\n"
    "Cash Cash Equivalents And Short Term Investments,62469000000.0,80572000000.0,"
    "62556000000.0,60608000000.0,53991000000.0\n"
)


_MSFT_QUARTERLY_BALANCE_CSV = (
    # Verbatim 2026-06-30 column of the yfinance payload the 2026-09-16 MSFT run
    # delivered: the vendor "Net Debt" row reconciles against financial debt
    # EXCLUDING capital-lease obligations less cash and equivalents
    # (31,067 + 9,227 - 20,935 = 19,359), so the old note's "is net-CASH ...
    # do not quote it" was a false vendor-error claim, and the report repeated
    # it as "the vendor 'Net Debt' row is mis-signed".
    ",2026-06-30,2026-03-31\n"
    "Net Debt,19359000000.0,8157000000.0\n"
    "Total Debt,56826000000.0,56965000000.0\n"
    "Cash Cash Equivalents And Short Term Investments,76651000000.0,78228000000.0\n"
    "Cash And Cash Equivalents,20935000000.0,32105000000.0\n"
    "Long Term Debt And Capital Lease Obligation,47599000000.0,48126000000.0\n"
    "Current Debt And Capital Lease Obligation,9227000000.0,8839000000.0\n"
    "Long Term Debt,31067000000.0,31423000000.0\n"
    "Current Debt,9227000000.0,8839000000.0\n"
)


class TestNetDebtSignNote(unittest.TestCase):
    """D7 (NVDA 2026-09-12) + MSFT 2026-09-16.

    The note disclosed a BASIS question as a vendor error: it fired whenever
    cash + ST investments exceeded total debt and told the model the vendor row
    "is net-CASH ... do not quote it". Both payloads below reconcile under a
    narrower, entirely standard basis (cash and equivalents only, and/or
    financial debt excluding lease obligations), so the note must now name the
    basis and the widest-basis figure instead of asserting what the vendor
    meant."""

    def test_msft_row_is_disclosed_as_a_basis_not_an_error(self):
        note = y_finance._net_debt_note(_MSFT_QUARTERLY_BALANCE_CSV, "MSFT")
        self.assertIn("19,359,000,000.00", note)
        # The basis that reproduces the row is named, with its arithmetic.
        self.assertIn("excluding capital-lease obligations", note)
        self.assertIn("19,359,000,000.00", note)
        # ...and the widest basis is stated with its own direction.
        self.assertIn("NET CASH", note)
        self.assertIn("76,651,000,000.00", note)
        self.assertIn("56,826,000,000.00", note)
        self.assertIn("19,825,000,000.00", note)
        # The instructions that made the report write "mis-signed" are gone,
        # and the note now says the opposite in as many words.
        self.assertIn("do not call the vendor row a sign error", note)
        self.assertNotIn("mis-signed", note)
        self.assertNotIn("Treat this company as NET CASH", note)
        self.assertNotIn("do not quote", note)

    def test_nvda_row_without_the_component_rows_is_neutral_not_an_accusation(self):
        # This fixture carries only the three rows the old check read, so the
        # basis that would explain the row is not available here: the note must
        # say so and still not claim the vendor is wrong.
        note = y_finance._net_debt_note(_NVDA_QUARTERLY_BALANCE_CSV, "NVDA")
        self.assertIn("10,923,000,000.00", note)
        self.assertIn("cannot be reproduced", note)
        self.assertIn("NET CASH", note)
        self.assertIn("24,118,000,000.00", note)  # 62,469 - 38,351
        self.assertNotIn("Treat this company as NET CASH", note)

    def test_silent_when_the_company_is_genuinely_net_debt(self):
        payload = (
            ",2026-07-31,2026-04-30\n"
            "Net Debt,3000000000.0,\n"
            "Total Debt,8000000000.0,7000000000.0\n"
            "Cash Cash Equivalents And Short Term Investments,5000000000.0,4000000000.0\n"
        )
        self.assertEqual(y_finance._net_debt_note(payload, "TST"), "")

    def test_silent_when_the_widest_basis_agrees_the_sign(self):
        # AMZN 2026-09-14 shape: the row does not reproduce from the carried
        # rows (its basis excludes operating-lease liabilities) but the widest
        # basis agrees the company is in net debt - a note would only teach the
        # model to distrust a row whose sign is right.
        payload = (
            ",2026-06-30\n"
            "Net Debt,17258000000.0\n"
            "Total Debt,209888000000.0\n"
            "Cash Cash Equivalents And Short Term Investments,143089000000.0\n"
            "Cash And Cash Equivalents,101816000000.0\n"
        )
        self.assertEqual(y_finance._net_debt_note(payload, "AMZN"), "")

    def test_silent_when_any_row_is_absent(self):
        rows = _MSFT_QUARTERLY_BALANCE_CSV.splitlines()
        for dropped in (
            "Net Debt",
            "Total Debt",
            "Cash Cash Equivalents And Short Term Investments",
        ):
            with self.subTest(dropped=dropped):
                kept = [ln for ln in rows if not ln.startswith(f"{dropped},")]
                self.assertEqual(y_finance._net_debt_note("\n".join(kept) + "\n", "MSFT"), "")

    def test_exact_labels_keep_the_lease_rows_apart(self):
        """Substring matching cannot separate `Long Term Debt` from `Long Term
        Debt And Capital Lease Obligation` - and the wider row is listed FIRST,
        so a fragment reader adds 16.5bn of leases to the narrow leg and then
        fails to reproduce a row that is exactly reproducible."""
        rows = y_finance._row_values(_MSFT_QUARTERLY_BALANCE_CSV)
        self.assertEqual(rows["long term debt"], 31_067_000_000.0)
        self.assertEqual(
            rows["long term debt and capital lease obligation"], 47_599_000_000.0
        )

    def test_note_survives_the_payload_get_balance_sheet_returns(self):
        """Delivery-path regression: the note must be IN the string the analyst
        receives, not merely computable from it."""
        frame = pd.DataFrame(
            {
                pd.Timestamp("2026-07-31"): [10923000000.0, 38351000000.0, 62469000000.0],
                pd.Timestamp("2026-04-30"): [None, 12348000000.0, 80572000000.0],
                pd.Timestamp("2026-01-31"): [None, 11040000000.0, 62556000000.0],
            },
            index=[
                "Net Debt",
                "Total Debt",
                "Cash Cash Equivalents And Short Term Investments",
            ],
        )

        class _BalanceSheetTicker:
            @property
            def quarterly_balance_sheet(self):
                return frame

        with (
            mock.patch.object(y_finance, "require_symbol", side_effect=lambda s: s),
            mock.patch.object(y_finance, "yf") as mock_yf,
        ):
            mock_yf.Ticker.return_value = _BalanceSheetTicker()
            out = y_finance.get_balance_sheet("NVDA", "quarterly", "2026-09-12")

        self.assertIn("Net Debt,10923000000.0", out)
        self.assertIn("NET CASH", out)
        self.assertIn("62,469,000,000.00", out)
        self.assertIn("cannot be reproduced", out)
        self.assertNotIn("do not quote the vendor Net Debt row", out)


if __name__ == "__main__":
    unittest.main()


class TestEarningsCountdown(unittest.TestCase):
    """The calendar must carry the countdown a report quotes.

    NVDA 2026-09-12 news.md called the next print "83 days away" - the gap from
    the PRIOR print; from the analysis date the count was 66 and no tool printed
    83, so the model computed it and got the base wrong.
    """

    @mock.patch.object(y_finance, "require_symbol", side_effect=lambda s: s)
    @mock.patch.object(y_finance, "yf")
    def test_counts_down_from_curr_date(self, mock_yf, _):
        mock_yf.Ticker.return_value = _Ticker()
        out = y_finance.get_earnings_calendar_yfinance("AAPL", "2026-05-01")
        assert "(in 97d)" in out  # 2026-05-01 -> 2026-08-06
        assert "(in 6d)" in out   # 2026-05-01 -> 2026-05-07
        assert out.count("(in ") == 2  # the 2026-02-05 print is history

    @mock.patch.object(y_finance, "require_symbol", side_effect=lambda s: s)
    @mock.patch.object(y_finance, "yf")
    def test_without_curr_date_there_is_no_countdown(self, mock_yf, _):
        mock_yf.Ticker.return_value = _Ticker()
        out = y_finance.get_earnings_calendar_yfinance("AAPL")
        assert "(in " not in out

    @mock.patch.object(y_finance, "require_symbol", side_effect=lambda s: s)
    @mock.patch.object(y_finance, "yf")
    def test_labels_the_vendor_surprise_basis(self, mock_yf, _):
        """The printed percent need not reconcile with the 2dp EPS pair beside
        it (NVDA 2026-08-26: 6.16% printed vs 6.22% from the pair); the header
        says why so a reader does not take the gap for a slip."""
        mock_yf.Ticker.return_value = _Ticker()
        out = y_finance.get_earnings_calendar_yfinance("AAPL")
        assert "surprise_pct is the vendor's own figure" in out
        assert "unrounded EPS" in out

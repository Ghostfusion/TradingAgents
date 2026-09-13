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


_NVDA_QUARTERLY_BALANCE_CSV = (
    # Verbatim rows from the 2026-09-12 NVDA run's yfinance quarterly balance
    # sheet: a net-cash company reported with a positive vendor "Net Debt".
    ",2026-07-31,2026-04-30,2026-01-31,2025-10-31,2025-07-31\n"
    "Net Debt,10923000000.0,,,,\n"
    "Total Debt,38351000000.0,12348000000.0,11040000000.0,10481000000.0,10598000000.0\n"
    "Cash Cash Equivalents And Short Term Investments,62469000000.0,80572000000.0,"
    "62556000000.0,60608000000.0,53991000000.0\n"
)


class TestNetDebtSignNote(unittest.TestCase):
    """D7 (NVDA 2026-09-12): the delivered balance-sheet payload carried the
    vendor's own ``Net Debt`` row (10,923,000,000) even though that payload's
    cash + ST investments (62,469,000,000) exceed total debt (38,351,000,000).
    The correction note existed for exactly this case and had no test."""

    def test_fires_on_the_real_nvda_quarterly_payload(self):
        note = y_finance._net_debt_note(_NVDA_QUARTERLY_BALANCE_CSV, "NVDA")
        self.assertIn("NET CASH", note)
        self.assertIn("10,923,000,000.00", note)
        self.assertIn("62,469,000,000.00", note)
        self.assertIn("38,351,000,000.00", note)
        self.assertIn("do not quote the vendor Net Debt row", note)

    def test_silent_when_the_company_is_genuinely_net_debt(self):
        payload = (
            ",2026-07-31,2026-04-30\n"
            "Net Debt,3000000000.0,\n"
            "Total Debt,8000000000.0,7000000000.0\n"
            "Cash Cash Equivalents And Short Term Investments,5000000000.0,4000000000.0\n"
        )
        self.assertEqual(y_finance._net_debt_note(payload, "TST"), "")

    def test_silent_when_any_row_is_absent(self):
        rows = _NVDA_QUARTERLY_BALANCE_CSV.splitlines()
        for dropped in (
            "Net Debt",
            "Total Debt",
            "Cash Cash Equivalents And Short Term Investments",
        ):
            with self.subTest(dropped=dropped):
                kept = [ln for ln in rows if not ln.startswith(f"{dropped},")]
                self.assertEqual(y_finance._net_debt_note("\n".join(kept) + "\n", "NVDA"), "")

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
        self.assertTrue(
            out.rstrip().endswith(
                "do not quote the vendor Net Debt row as a positive debt position."
            ),
            out[-400:],
        )


if __name__ == "__main__":
    unittest.main()

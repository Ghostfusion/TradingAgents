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


if __name__ == "__main__":
    unittest.main()

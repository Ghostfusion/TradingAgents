"""A-series enrichment tests: institutional ownership, earnings surprises, expected move."""

import unittest
from unittest import mock

import pandas as pd

from tradingagents.dataflows import moomoo
from tradingagents.dataflows.errors import NoMarketDataError
from tradingagents.dataflows.moomoo import (
    get_earnings_surprise_history_moomoo,
    get_expected_move_moomoo,
    get_institution_holdings_moomoo,
)

RET_OK = 0


class InstitutionHoldingsTests(unittest.TestCase):
    def test_formats_holder_pct_change(self):
        df = pd.DataFrame(
            {
                "period_text": ["2026/Q2", "2026/Q1"],
                "institution_quantity": [5646, 5465],
                "holder_quantity": [3.7e9, 3.8e9],
                "holder_pct": [78.4, 79.6],
                "holder_pct_change": [-1.2, -0.1],
            }
        )
        ctx = mock.Mock()
        ctx.get_shareholders_institutional.return_value = (RET_OK, df)
        with (
            mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx),
            mock.patch.object(moomoo, "_moomoo_code", return_value="US.AVGO"),
        ):
            out = get_institution_holdings_moomoo("AVGO")
        self.assertIn("78.4%", out)
        self.assertIn("-1.2pp", out)
        self.assertIn("3.70B", out)

    def test_empty_raises_no_data(self):
        ctx = mock.Mock()
        ctx.get_shareholders_institutional.return_value = (RET_OK, pd.DataFrame())
        with (
            mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx),
            mock.patch.object(moomoo, "_moomoo_code", return_value="US.AVGO"),
            self.assertRaises(NoMarketDataError),
        ):
            get_institution_holdings_moomoo("AVGO")


class EarningsSurpriseHistoryTests(unittest.TestCase):
    def _hist(self):
        return pd.DataFrame(
            {
                "period_text": ["2026/Q3", "2026/Q2"],
                "pub_trading_day_str": ["2026-09-02", "2026-06-03"],
                "predict_vola_ratio_newest": [9.4, 8.7],
                "option_iv_crush": [None, 6.5],
                "close_price": [362.48, 153.79],
                "last_close_price": [362.48, 175.9],  # upcoming has same (nan guard)
            }
        )

    def test_surprise_table_and_nan_guard(self):
        ctx = mock.Mock()
        ctx.get_financials_earnings_price_history.return_value = (RET_OK, self._hist())
        # targeted calendar windows return AVGO rows with eps actual/predict
        ctx.get_earnings_calendar.side_effect = lambda **kw: (
            RET_OK,
            pd.DataFrame(
                {
                    "security": ["US.AVGO"],
                    "earnings_date": [kw["begin_date"]],
                    "eps_predict": [1.7188],
                    "eps_actual": [1.91],
                    "revenue_predict": [None],
                    "revenue_actual": [None],
                    "ebit_predict": [None],
                    "ebit_actual": [None],
                }
            ),
        )
        with (
            mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx),
            mock.patch.object(moomoo, "_moomoo_code", return_value="US.AVGO"),
        ):
            out = get_earnings_surprise_history_moomoo("AVGO", "2026-08-19")
        self.assertIn("Earnings Surprise History", out)
        # upcoming print must NOT show a nan day move
        self.assertNotIn("nan%", out)
        self.assertIn("9.4%", out)

    def test_no_history_raises(self):
        ctx = mock.Mock()
        ctx.get_financials_earnings_price_history.return_value = (RET_OK, pd.DataFrame())
        with (
            mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx),
            mock.patch.object(moomoo, "_moomoo_code", return_value="US.AVGO"),
            self.assertRaises(NoMarketDataError),
        ):
            get_earnings_surprise_history_moomoo("AVGO", "2026-08-19")


class ExpectedMoveTests(unittest.TestCase):
    def test_current_period_implied_move(self):
        hist = pd.DataFrame(
            {
                "period_text": ["2026/Q3", "2026/Q2"],
                "is_current": [True, False],
                "predict_vola_ratio_newest": [9.4, 8.7],
            }
        )
        kdf = pd.DataFrame({"time_key": ["2026-08-18"], "close": [362.48]})
        ctx = mock.Mock()
        ctx.get_financials_earnings_price_history.return_value = (RET_OK, hist)
        ctx.request_history_kline.return_value = (RET_OK, kdf, None)
        with (
            mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx),
            mock.patch.object(moomoo, "_moomoo_code", return_value="US.AVGO"),
        ):
            out = get_expected_move_moomoo("AVGO", "2026-08-19")
        self.assertIn("9.4%", out)
        self.assertIn("band", out.lower())

    def test_no_move_raises(self):
        ctx = mock.Mock()
        ctx.get_financials_earnings_price_history.return_value = (RET_OK, pd.DataFrame())
        with (
            mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx),
            mock.patch.object(moomoo, "_moomoo_code", return_value="US.AVGO"),
            self.assertRaises(NoMarketDataError),
        ):
            get_expected_move_moomoo("AVGO", "2026-08-19")


if __name__ == "__main__":
    unittest.main()

"""Moomoo vendor: ticker mapping, error taxonomy, and routing fallback.

These tests are offline — they mock the moomoo SDK (or simulate an
unreachable OpenD) and never touch a real gateway, so they run in CI and on
machines without OpenD installed.
"""

import unittest
from datetime import datetime
from unittest import mock

import pandas as pd

import tradingagents.dataflows.config as config_module
from tradingagents.dataflows import interface, moomoo
from tradingagents.dataflows.config import set_config
from tradingagents.dataflows.errors import (
    NoMarketDataError,
    VendorNotConfiguredError,
    VendorRateLimitError,
)
from tradingagents.dataflows.moomoo import (
    MoomooNotConfiguredError,
    _moomoo_code,
)

RET_OK = 0


def _reset():
    config_module.reset_config()
    # Force autostart off: the developer's .env may enable it, and tests must
    # not attempt to launch/find OpenD on this machine.
    set_config({"moomoo_autostart": False})
    # Drop any real (thread-local) OpenQuoteContext a previous test may have
    # created — with OpenD running locally, an earlier test could otherwise
    # cache a live context and make "unreachable" tests return it instead of
    # raising.
    moomoo._close_ctx()
    # Reset the module-level autostart / probe-cache flags so each test starts clean.
    moomoo._autostart_attempted = False
    moomoo._last_probe_fail = 0.0


# ---------------------------------------------------------------------------
# Ticker mapping
# ---------------------------------------------------------------------------


class MoomooCodeTests(unittest.TestCase):
    def test_us_bare_ticker(self):
        self.assertEqual(_moomoo_code("AAPL"), "US.AAPL")
        self.assertEqual(_moomoo_code("tsla"), "US.TSLA")

    def test_hk_padded(self):
        self.assertEqual(_moomoo_code("0700.HK"), "HK.00700")
        self.assertEqual(_moomoo_code("09988.HK"), "HK.09988")

    def test_jp(self):
        self.assertEqual(_moomoo_code("7203.T"), "JP.7203")

    def test_a_share(self):
        self.assertEqual(_moomoo_code("600519.SS"), "SH.600519")
        self.assertEqual(_moomoo_code("000001.SZ"), "SZ.000001")

    def test_au_ca_sg_my(self):
        self.assertEqual(_moomoo_code("BHP.AX"), "AU.BHP")
        self.assertEqual(_moomoo_code("RY.TO"), "CA.RY")
        self.assertEqual(_moomoo_code("D05.SI"), "SG.D05")
        self.assertEqual(_moomoo_code("1155.KL"), "MY.1155")

    def test_crypto(self):
        self.assertEqual(_moomoo_code("BTC-USD"), "CC.BTCUSD")
        self.assertEqual(_moomoo_code("BTCUSDT"), "CC.BTCUSD")
        self.assertEqual(_moomoo_code("ETH-USD"), "CC.ETHUSD")

    def test_us_preferred_hybrid_form(self):
        # Yahoo ``TICKER-P<LETTER>`` preferreds map to moomoo ``US.<T>.PR<LETTER>``
        # (confirmed live on the gateway).
        self.assertEqual(_moomoo_code("GS-PD"), "US.GS.PRD")
        self.assertEqual(_moomoo_code("BAC-PL"), "US.BAC.PRL")
        self.assertEqual(_moomoo_code("T-PC"), "US.T.PRC")
        self.assertEqual(_moomoo_code("WFC-PL"), "US.WFC.PRL")
        self.assertEqual(_moomoo_code("JPM-PM"), "US.JPM.PRM")
        self.assertEqual(_moomoo_code("MS-PK"), "US.MS.PRK")
        self.assertEqual(_moomoo_code("MS-PF"), "US.MS.PRF")
        self.assertEqual(_moomoo_code("WFC-PZ"), "US.WFC.PRZ")
        self.assertEqual(_moomoo_code("KEY-PJ"), "US.KEY.PRJ")
        self.assertEqual(_moomoo_code("C-PK"), "US.C.PRK")

    def test_us_common_share_class_uses_dotted_line(self):
        # BRK-B / BF-B are COMMON share classes, not preferreds: moomoo codes
        # them as a dotted line (US.<T>.<LETTER>), never a phantom preferred.
        self.assertEqual(_moomoo_code("BRK-B"), "US.BRK.B")
        self.assertEqual(_moomoo_code("BRK-A"), "US.BRK.A")
        self.assertEqual(_moomoo_code("BF-B"), "US.BF.B")
        self.assertEqual(_moomoo_code("BRK.B"), "US.BRK.B")

    def test_unsupported_market_raises(self):
        # LSE / India are not covered by moomoo → typed NoMarketDataError
        with self.assertRaises(NoMarketDataError):
            _moomoo_code("AZN.L")
        with self.assertRaises(NoMarketDataError):
            _moomoo_code("RELIANCE.NS")
        with self.assertRaises(NoMarketDataError):
            _moomoo_code("^GSPC")


# ---------------------------------------------------------------------------
# OpenD down → fallback (no autostart by default)
# ---------------------------------------------------------------------------


class MoomooUnreachableTests(unittest.TestCase):
    def setUp(self):
        _reset()

    @mock.patch.object(moomoo, "_probe_or_use_cache", return_value=False)
    def test_no_opend_raises_not_configured(self, _probe):
        with self.assertRaises(MoomooNotConfiguredError):
            moomoo._ensure_ctx()
        # MoomooNotConfiguredError must be treated as VendorNotConfiguredError
        self.assertTrue(issubclass(MoomooNotConfiguredError, VendorNotConfiguredError))

    def test_autostart_enabled_but_no_exe(self):
        # autostart on but no executable / account → still falls back clearly
        set_config({"moomoo_autostart": True, "moomoo_account": "100000"})
        with (
            mock.patch.object(moomoo, "_probe_or_use_cache", return_value=False),
            mock.patch.object(moomoo, "_find_opend_executable", return_value=None),
            self.assertRaises(MoomooNotConfiguredError),
        ):
            moomoo._ensure_ctx()

    def test_ticker_mapping_rejects_unsupported_before_sdk(self):
        # A symbol moomoo can't serve raises before any SDK interaction.
        with (
            mock.patch.object(moomoo, "_ensure_ctx") as ensure,
            self.assertRaises(NoMarketDataError),
        ):
            moomoo.get_stock_data_moomoo("AZN.L", "a", "b")
        ensure.assert_not_called()


# ---------------------------------------------------------------------------
# Routing: moomoo falls back to the next vendor when it errors
# ---------------------------------------------------------------------------


class MoomooRoutingTests(unittest.TestCase):
    def setUp(self):
        _reset()

    def test_moomoo_errors_fall_back_to_yfinance(self):
        # Moomoo raises NoMarketDataError → router continues to yfinance
        def _no_data(*a, **k):
            raise MoomooNotConfiguredError("OpenD not reachable")

        set_config({"data_vendors": {"core_stock_apis": "moomoo,yfinance"}})
        with mock.patch.dict(
            interface.VENDOR_METHODS,
            {"get_stock_data": {"moomoo": _no_data, "yfinance": lambda *a, **k: "YF_DATA"}},
            clear=False,
        ):
            out = interface.route_to_vendor("get_stock_data", "AAPL", "a", "b")
        self.assertEqual(out, "YF_DATA")

    def test_moomoo_alone_and_failing_raises(self):
        # Only moomoo configured + it fails → core category propagates the error
        def _no_data(*a, **k):
            raise MoomooNotConfiguredError("OpenD not reachable")

        set_config({"data_vendors": {"core_stock_apis": "moomoo"}})
        with (
            mock.patch.dict(
                interface.VENDOR_METHODS,
                {"get_stock_data": {"moomoo": _no_data}},
                clear=False,
            ),
            self.assertRaises(MoomooNotConfiguredError),
        ):
            interface.route_to_vendor("get_stock_data", "AAPL", "a", "b")

    def test_successful_moomoo_serves_the_call(self):
        def _moomoo_ok(*a, **k):
            return "MOOMOO_DATA"

        set_config({"data_vendors": {"core_stock_apis": "moomoo"}})
        with mock.patch.dict(
            interface.VENDOR_METHODS,
            {"get_stock_data": {"moomoo": _moomoo_ok}},
            clear=False,
        ):
            out = interface.route_to_vendor("get_stock_data", "AAPL", "a", "b")
        self.assertEqual(out, "MOOMOO_DATA")


# ---------------------------------------------------------------------------
# SDK return handling (mocked context, offline)
# ---------------------------------------------------------------------------


class MoomooSdkHandlingTests(unittest.TestCase):
    def setUp(self):
        _reset()

    def test_stock_data_formats_csv(self):
        df = pd.DataFrame(
            {
                "time_key": ["2025-01-02", "2025-01-03"],
                "open": [100.0, 102.0],
                "high": [101.0, 103.0],
                "low": [99.0, 101.0],
                "close": [101.5, 102.5],
                "volume": [1000, 2000],
            }
        )
        ctx = mock.Mock()
        ctx.request_history_kline.return_value = (RET_OK, df, None)
        with (
            mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx),
            mock.patch.object(moomoo, "_moomoo_code", return_value="US.AAPL"),
        ):
            out = moomoo.get_stock_data_moomoo("AAPL", "2025-01-01", "2025-01-10")
        self.assertIn("# Total records: 2", out)
        self.assertIn("Close", out)
        self.assertIn("101.5", out)

    def test_empty_kline_raises_no_data(self):
        ctx = mock.Mock()
        ctx.request_history_kline.return_value = (RET_OK, pd.DataFrame(), None)
        with (
            mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx),
            mock.patch.object(moomoo, "_moomoo_code", return_value="US.AAPL"),
            self.assertRaises(NoMarketDataError),
        ):
            moomoo.get_stock_data_moomoo("AAPL", "2025-01-01", "2025-01-10")

    def test_ret_error_permission_raises_no_data(self):
        ctx = mock.Mock()
        ctx.request_history_kline.return_value = (-1, "no permission for quote", None)
        with (
            mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx),
            mock.patch.object(moomoo, "_moomoo_code", return_value="US.AAPL"),
            self.assertRaises(NoMarketDataError),
        ):
            moomoo.get_stock_data_moomoo("AAPL", "2025-01-01", "2025-01-10")

    def test_ret_error_login_raises_not_configured(self):
        ctx = mock.Mock()
        ctx.request_history_kline.return_value = (-1, "please login first", None)
        with (
            mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx),
            mock.patch.object(moomoo, "_moomoo_code", return_value="US.AAPL"),
            self.assertRaises(MoomooNotConfiguredError),
        ):
            moomoo.get_stock_data_moomoo("AAPL", "2025-01-01", "2025-01-10")

    def test_short_interest_unpacks_two_dfs(self):
        ctx = mock.Mock()
        hk = pd.DataFrame({"timestamp_str": ["2025-01-03"], "days_to_cover": [2.5]})
        ctx.get_short_interest.return_value = (RET_OK, pd.DataFrame(), hk)
        with (
            mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx),
            mock.patch.object(moomoo, "_moomoo_code", return_value="HK.00700"),
        ):
            out = moomoo.get_short_interest_moomoo("0700.HK")
        self.assertIn("Short Interest", out)
        self.assertIn("Days to Cover", out)

    def test_earnings_calendar_unpacks_two_tuples(self):
        ctx = mock.Mock()
        df = pd.DataFrame({"code": ["00700"], "date": ["2025-04-20"], "eps_estimate": [12.3]})
        ctx.get_earnings_calendar.return_value = (RET_OK, df)
        with (
            mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx),
            mock.patch.object(moomoo, "_moomoo_code", return_value="HK.00700"),
        ):
            out = moomoo.get_earnings_calendar_moomoo("0700.HK", "2025-05-20", 30)
        self.assertIn("Earnings Calendar", out)

    def test_prediction_markets_walks_category_to_contracts(self):
        """Event contracts: category → series → event → contract → snapshot."""
        cats = pd.DataFrame(
            {
                "category": ["ECAT.FED"],
                "category_name": ["Interest Rate"],
                "tags": ["fed,rate"],
            }
        )
        series = pd.DataFrame({"series_code": ["ES.FED-2026"]})
        events = pd.DataFrame({"event_code": ["EC.FED-2026-MAR.EVENT"]})
        contracts = pd.DataFrame(
            {
                "contract_code": ["EC.FED-2026-MAR.CUT", "EC.FED-2026-MAR.HOLD"],
            }
        )
        snap = pd.DataFrame(
            {
                "code": ["EC.FED-2026-MAR.CUT", "EC.FED-2026-MAR.HOLD", "EC.RESOLVED"],
                "name": ["Fed cuts in March", "Fed holds in March", "Old event"],
                "price": [0.76, 0.24, 1.0],  # resolved contract (1.0) must be filtered
                "cumulative_volume": [1_200_000, 900_000, 5],
            }
        )
        ctx = mock.Mock()
        ctx.get_event_contract_category.return_value = (RET_OK, cats)
        ctx.get_event_contract_series_list.return_value = (RET_OK, series)
        ctx.get_event_contract_event_list.return_value = (RET_OK, events)
        ctx.get_event_contract.return_value = (RET_OK, {"contract_list": contracts}, None)
        ctx.get_event_contract_snapshot.return_value = (RET_OK, snap)
        with mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx):
            out = moomoo.get_prediction_markets_moomoo("fed rate cut", limit=5)
        self.assertIn("Fed cuts in March", out)
        self.assertIn("76%", out)
        self.assertNotIn("Old event", out)  # resolved (price=1.0) excluded
        ctx.get_event_contract_snapshot.assert_called_once_with(
            ["EC.FED-2026-MAR.CUT", "EC.FED-2026-MAR.HOLD"]
        )

    def test_prediction_markets_empty_contracts_raises_no_data(self):
        ctx = mock.Mock()
        ctx.get_event_contract_category.return_value = (
            RET_OK,
            pd.DataFrame(
                {
                    "category": ["ECAT.X"],
                    "category_name": ["Economy"],
                    "tags": ["gdp"],
                }
            ),
        )
        ctx.get_event_contract_series_list.return_value = (RET_OK, pd.DataFrame())
        with (
            mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx),
            self.assertRaises(NoMarketDataError),
        ):
            moomoo.get_prediction_markets_moomoo("economy")

    def test_prediction_markets_permission_error_falls_back(self):
        # Region-gated (event contracts need a moomoo SG/MY account): the SDK
        # returns a permission error → typed NoMarketDataError → router falls
        # back to Polymarket.
        ctx = mock.Mock()
        ctx.get_event_contract_category.return_value = (-1, "no permission for event contract")
        with (
            mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx),
            self.assertRaises(NoMarketDataError),
        ):
            moomoo.get_prediction_markets_moomoo("fed")

    # -- Tier 1/2 enrichment tools ----------------------------------------

    def test_capital_flow_formats_tables(self):
        flow = pd.DataFrame(
            {
                "capital_flow_item_time": ["2026-08-10 00:00:00"],
                "in_flow": [-1e8],
                "super_in_flow": [2e7],
                "big_in_flow": [-3e7],
                "mid_in_flow": [-4e7],
                "sml_in_flow": [-5e7],
                "main_in_flow": [-6e7],
            }
        )
        dist = pd.DataFrame(
            {
                "capital_in_super": [1e7],
                "capital_out_super": [2e7],
                "capital_in_big": [1e7],
                "capital_out_big": [2e7],
                "capital_in_mid": [1e7],
                "capital_out_mid": [2e7],
                "capital_in_small": [1e7],
                "capital_out_small": [2e7],
            }
        )
        ctx = mock.Mock()
        ctx.get_capital_flow.return_value = (RET_OK, flow)
        ctx.get_capital_distribution.return_value = (RET_OK, dist)
        with (
            mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx),
            mock.patch.object(moomoo, "_moomoo_code", return_value="US.AAPL"),
        ):
            out = moomoo.get_capital_flow_moomoo("AAPL")
        self.assertIn("Capital Flow", out)
        self.assertIn("institutional distribution", out)

    def test_economic_calendar_unpacks_four_tuples(self):
        df = pd.DataFrame(
            {
                "title": ["CPI"],
                "timestamp": [1768608000.0],
                "country": ["US"],
                "star": ["HIGH"],
                "previous": ["3.0"],
                "consensus": ["2.9"],
                "actual": [""],
            }
        )
        ctx = mock.Mock()
        ctx.get_economic_calendar.return_value = (RET_OK, df, None, False)
        with mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx):
            out = moomoo.get_economic_calendar_moomoo("2026-01-16", 14)
        self.assertIn("Economic Calendar", out)
        self.assertIn("CPI", out)

    def test_fed_watch_formats_probabilities(self):
        df = pd.DataFrame(
            {
                "meeting_date": ["2026-09-15"],
                "target_range": ["3.50-3.75%"],
                "probability": [66.9],
            }
        )
        ctx = mock.Mock()
        ctx.get_fed_watch_target_rate.return_value = (RET_OK, df)
        with mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx):
            out = moomoo.get_fed_watch_moomoo()
        self.assertIn("66.9%", out)

    def test_market_breadth_formats_heatmap_and_distribution(self):
        hm = pd.DataFrame(
            {
                "plate_name": ["Semiconductors"],
                "change_rate": [1.5],
                "rise_count": [12],
                "fall_count": [4],
                "leader_stock": ["US.NVDA"],
            }
        )
        rf = {
            "plate": "US.USAALL",
            "range_list": [
                {
                    "type": "NEGATIVE_INFINITY",
                    "left_border": 0,
                    "right_border": -3,
                    "stock_count": 10,
                },
            ],
        }
        ctx = mock.Mock()
        ctx.get_heat_map_data.return_value = (RET_OK, hm)
        ctx.get_rise_fall_distribution.return_value = (RET_OK, rf)
        with mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx):
            out = moomoo.get_market_breadth_moomoo()
        self.assertIn("Semiconductors", out)
        self.assertIn("Rise/fall distribution", out)

    def test_revenue_breakdown_formats_segments(self):
        data = {
            "period": "2026/Q3",
            "currency_code": "USD",
            "breakdown_list": [
                {
                    "type": "BUSINESS",
                    "item_list": [
                        {"name": "iPhone", "main_oper_income": 5.4e10, "ratio": 49.5},
                    ],
                }
            ],
        }
        ctx = mock.Mock()
        ctx.get_financials_revenue_breakdown.return_value = (RET_OK, data)
        with (
            mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx),
            mock.patch.object(moomoo, "_moomoo_code", return_value="US.AAPL"),
        ):
            out = moomoo.get_revenue_breakdown_moomoo("AAPL")
        self.assertIn("iPhone", out)
        self.assertIn("$54.00B", out)  # 5.4e10 / 1e9 = 54.00B

    def test_corporate_actions_formats_dividends(self):
        div = {"dividend_list": [{"statement": "Cash Dividend: 0.27 USD", "ex_date": "08/10/2026"}]}
        ctx = mock.Mock()
        ctx.get_corporate_actions_dividends.return_value = (RET_OK, div)
        ctx.get_corporate_actions_stock_splits.return_value = (RET_OK, {"split_list": []})
        with (
            mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx),
            mock.patch.object(moomoo, "_moomoo_code", return_value="US.AAPL"),
        ):
            out = moomoo.get_corporate_actions_moomoo("AAPL")
        self.assertIn("0.27 USD", out)

    def test_earnings_catalyst_formats_history(self):
        df = pd.DataFrame(
            {
                "period_text": ["2026/Q3"],
                "pub_trading_day_str": ["2026-07-30"],
                "predict_vola_ratio_newest": [3.9],
                "option_iv_crush": [3.9],
                "close_price": [308.64],
                "last_close_price": [333.14],
            }
        )
        ctx = mock.Mock()
        ctx.get_financials_earnings_price_history.return_value = (RET_OK, df)
        with (
            mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx),
            mock.patch.object(moomoo, "_moomoo_code", return_value="US.AAPL"),
        ):
            out = moomoo.get_earnings_catalyst_moomoo("AAPL")
        self.assertIn("IV crush", out)
        self.assertIn("-7.4%", out)  # (308.64/333.14 - 1) = -7.36%

    def test_capital_flow_embeds_flow_signal(self):
        """L2: deterministic flow summary appended to the tool output."""
        flow = pd.DataFrame({"capital_flow_item_time": ["2026-08-10"],
                             "in_flow": [-1e8], "super_in_flow": [1e7]})
        dist = pd.DataFrame({
            "capital_in_super": [1.2e6], "capital_out_super": [1.1e7],
            "capital_in_big": [2.3e7], "capital_out_big": [3.6e7],
            "capital_in_mid": [4.0e7], "capital_out_mid": [5.7e7],
            "capital_in_small": [7.2e7], "capital_out_small": [1.1e8],
        })
        ctx = mock.Mock()
        ctx.get_capital_flow.return_value = (RET_OK, flow)
        ctx.get_capital_distribution.return_value = (RET_OK, dist)
        with (
            mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx),
            mock.patch.object(moomoo, "_moomoo_code", return_value="US.UNH"),
        ):
            out = moomoo.get_capital_flow_moomoo("UNH", "2026-08-17")
        self.assertIn("**Flow Signal**", out)
        self.assertIn("FLOW_WARNING", out)

    def test_trading_days_between_parses_list(self):
        ctx = mock.Mock()
        ctx.request_trading_days.return_value = (
            RET_OK,
            [
                {"time": "2026-08-10", "trade_date_type": "WHOLE"},
                {"time": "2026-08-11", "trade_date_type": "WHOLE"},
            ],
        )
        with (
            mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx),
            mock.patch.object(moomoo, "_moomoo_code", return_value="US.AAPL"),
        ):
            days = moomoo.get_trading_days_between("AAPL", "2026-08-10", "2026-08-20")
        self.assertEqual(days, ["2026-08-10", "2026-08-11"])

    def test_trading_days_unreachable_raises_not_configured(self):
        with (
            mock.patch.object(moomoo, "_probe_or_use_cache", return_value=False),
            self.assertRaises(MoomooNotConfiguredError),
        ):
            moomoo.get_trading_days_between("AAPL", "2026-08-10", "2026-08-20")

    def test_tier_tools_are_optional_categories(self):
        """All new enrichment categories must degrade to a sentinel, not abort."""
        for method in (
            "get_capital_flow",
            "get_smart_money",
            "get_fed_watch",
            "get_market_breadth",
            "get_revenue_breakdown",
            "get_corporate_actions",
            "get_earnings_catalyst",
        ):
            cat = interface.get_category_for_method(method)
            self.assertIn(cat, interface.OPTIONAL_CATEGORIES, f"{method} -> {cat}")


class MoomooReturnsEndTests(unittest.TestCase):
    """Tier 3: exact trading-day end-date resolution with graceful fallback."""

    def setUp(self):
        _reset()

    def _make_graph(self):
        import tradingagents.graph.trading_graph as tg

        obj = object.__new__(tg.TradingAgentsGraph)
        obj.config = config_module.get_config()
        return obj

    def test_uses_trading_day_calendar_when_reachable(self):
        obj = self._make_graph()
        days = [
            "2026-08-10",
            "2026-08-11",
            "2026-08-12",
            "2026-08-13",
            "2026-08-14",
            "2026-08-17",
            "2026-08-18",
            "2026-08-19",
        ]
        with mock.patch.object(moomoo, "get_trading_days_between", return_value=days):
            end = obj._resolve_returns_end("AAPL", "2026-08-10", 5)
        # days[holding_days + 1] = days[6] = 08-18 → +1 day = 08-19
        self.assertEqual(end.strftime("%Y-%m-%d"), "2026-08-19")

    def test_falls_back_to_calendar_heuristic(self):
        obj = self._make_graph()
        with mock.patch.object(
            moomoo, "get_trading_days_between", side_effect=MoomooNotConfiguredError("down")
        ):
            end = obj._resolve_returns_end("AAPL", "2026-08-10", 5)
        self.assertEqual(end.strftime("%Y-%m-%d"), "2026-08-22")  # 5 + 7 calendar days


class MoomooQualityFixTests(unittest.TestCase):
    """Review-fix regressions: warmup trim, IV scale, CSV order, date anchor."""

    def setUp(self):
        _reset()

    def _klines(self, n_days=300):
        dates = pd.date_range("2025-01-01", periods=n_days, freq="B")
        return pd.DataFrame(
            {
                "time_key": dates.strftime("%Y-%m-%d"),
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 1000.0,
            }
        )

    def test_indicator_warmup_trimmed(self):
        """Only the last look_back_days are reported (no stockstats seeds)."""
        ctx = mock.Mock()
        ctx.request_history_kline.return_value = (RET_OK, self._klines(300), None)
        with (
            mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx),
            mock.patch.object(moomoo, "_moomoo_code", return_value="US.AAPL"),
        ):
            out = moomoo.get_indicators_moomoo("AAPL", "rsi", "2025-05-01", 30)
        lines = [ln for ln in out.splitlines() if ln[:10].startswith("2025-")]
        self.assertGreaterEqual(len(lines), 1)
        # The report window must start at/near cutoff, not at the warmup start.
        self.assertNotIn("2025-01-", "\n".join(lines))
        # A longer warmup window was requested (max(2*lookback+100, 300)).
        args = ctx.request_history_kline.call_args[1]
        start = datetime.strptime(args["start"], "%Y-%m-%d")
        end = datetime.strptime(args["end"], "%Y-%m-%d")
        self.assertGreaterEqual((end - start).days, 300)

    def test_options_iv_normalized_from_percent(self):
        """IV in percent (31.9) must render as 31.9%, not 3190%."""
        import pandas as pd

        calls = pd.DataFrame(
            {"strike": [100], "implied_vol": [31.9], "open_interest": [100], "volume": [10]}
        )
        puts = pd.DataFrame(
            {"strike": [100], "implied_vol": [33.0], "open_interest": [200], "volume": [20]}
        )
        exp = pd.DataFrame({"time": ["2026-08-20"]})
        ctx = mock.Mock()
        ctx.get_option_expiration_date.return_value = (RET_OK, exp)
        ctx.get_option_chain.return_value = (
            RET_OK,
            pd.concat([calls.assign(option_type="CALL"), puts.assign(option_type="PUT")]),
            None,
        )
        with (
            mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx),
            mock.patch.object(moomoo, "_moomoo_code", return_value="US.AAPL"),
        ):
            out = moomoo.get_options_chain_moomoo("AAPL", "2026-08-16")
        self.assertIn("31.9%", out)
        self.assertIn("33.0%", out)

    def test_capital_flow_anchored_by_date(self):
        ctx = mock.Mock()
        flow = pd.DataFrame(
            {
                "capital_flow_item_time": ["2026-07-01 00:00:00"],
                "in_flow": [1e6],
                "super_in_flow": [1],
                "big_in_flow": [1],
                "mid_in_flow": [1],
                "sml_in_flow": [1],
                "main_in_flow": [1],
            }
        )
        dist = pd.DataFrame(
            {
                "capital_in_super": [1],
                "capital_out_super": [1],
                "capital_in_big": [1],
                "capital_out_big": [1],
                "capital_in_mid": [1],
                "capital_out_mid": [1],
                "capital_in_small": [1],
                "capital_out_small": [1],
            }
        )
        ctx.get_capital_flow.return_value = (RET_OK, flow)
        ctx.get_capital_distribution.return_value = (RET_OK, dist)
        with (
            mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx),
            mock.patch.object(moomoo, "_moomoo_code", return_value="US.AAPL"),
        ):
            moomoo.get_capital_flow_moomoo("AAPL", "2026-08-16")
        kwargs = ctx.get_capital_flow.call_args[1]
        self.assertIn("start", kwargs)
        self.assertEqual(kwargs["end"], "2026-08-16")

    def test_stock_data_csv_ordered_columns(self):
        """CSV columns are emitted in a fixed order (Date, Open, High, ...)."""
        df = pd.DataFrame(
            {
                "time_key": ["2025-01-02"],
                "open": [100.0],
                "high": [101.0],
                "low": [99.0],
                "close": [100.5],
                "volume": [1000],
            }
        )
        ctx = mock.Mock()
        ctx.request_history_kline.return_value = (RET_OK, df, None)
        with (
            mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx),
            mock.patch.object(moomoo, "_moomoo_code", return_value="US.AAPL"),
        ):
            out = moomoo.get_stock_data_moomoo("AAPL", "2025-01-01", "2025-01-10")
        header = [ln for ln in out.splitlines() if ln.startswith("Date,")]
        self.assertEqual(header, ["Date,Open,High,Low,Close,Volume"])




class MoomooTopMoversTests(unittest.TestCase):
    """Top-movers rank: symbol conversion, field mapping, error taxonomy."""

    def setUp(self):
        _reset()

    def _rank_df(self, securities):
        import pandas as pd

        return pd.DataFrame(
            {
                "security": securities,
                "name": ["Apple Inc.", "Tencent"],
                "cur_price": [210.5, 780.0],
                "change_ratio": [-4.21, -1.75],
                "change_amount": [-9.3, -1.4],
                "turnover": [1.1e7, 2.2e8],
                "volume": [5.0e7, 2.0e7],
                "pe_ttm": [28.1, 24.5],
                "amplitude": [0.031, 0.028],
                "market_cap": [3.2e12, 5.5e11],
                "volume_ratio": [1.1, 0.9],
            }
        )

    def test_top_movers_unpacks_rank_and_strips_prefix(self):
        ctx = mock.Mock()
        ctx.get_top_movers_rank.return_value = (RET_OK, (42, self._rank_df(["US.AAPL", "US.MSFT"])))
        with mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx):
            rows = moomoo.get_top_movers_moomoo(sort_dir="losers", count=2)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["symbol"], "AAPL")
        self.assertEqual(rows[0]["name"], "Apple Inc.")
        self.assertAlmostEqual(rows[0]["change_ratio"], -0.0421)
        self.assertAlmostEqual(rows[0]["pe_ttm"], 28.1)
        self.assertAlmostEqual(rows[0]["market_cap"], 3.2e12)

    def test_top_movers_hk_converts_to_yahoo_style(self):
        self.assertEqual(moomoo._yahoo_style_symbol("HK.00700"), "00700.HK")
        self.assertEqual(moomoo._yahoo_style_symbol("US.AAPL"), "AAPL")

    def test_top_movers_gainers_dir_passes_descending(self):
        ctx = mock.Mock()
        ctx.get_top_movers_rank.return_value = (RET_OK, (0, self._rank_df(["US.AAPL", "US.MSFT"])))
        with mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx):
            moomoo.get_top_movers_moomoo(sort_dir="gainers", count=1)
        kwargs = ctx.get_top_movers_rank.call_args[1]
        self.assertIn("sort_dir", kwargs)

    def test_top_movers_permission_error_raises_no_data(self):
        ctx = mock.Mock()
        ctx.get_top_movers_rank.return_value = (-1, "no permission for ranking")
        with (
            mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx),
            self.assertRaises(NoMarketDataError),
        ):
            moomoo.get_top_movers_moomoo(count=1)

    def test_hot_movers_merges_and_dedupes(self):
        """get_hot_movers_moomoo: gainers+losers, deduped, hottest first."""
        ctx = mock.Mock()
        gainer_df = self._rank_df(["US.AAPL", "US.AAPL"]).head(1)
        los_df = self._rank_df(["US.MSFT", "US.MSFT"])
        # reuse the same df so rows are valid; loser df has 2 rows
        ctx.get_top_movers_rank.side_effect = [
            (RET_OK, (1, gainer_df)),
            (RET_OK, (1, los_df)),
        ]
        with mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx):
            hot = moomoo.get_hot_movers_moomoo(count=5, market="US")
        symbols = [r["symbol"] for r in hot]
        self.assertIn("AAPL", symbols)   # gainer side
        self.assertIn("MSFT", symbols)   # loser side
        self.assertEqual(len(symbols), len(set(symbols)))  # deduped
        self.assertEqual(ctx.get_top_movers_rank.call_count, 2)  # both directions

    def test_top_movers_login_error_raises_not_configured(self):
        ctx = mock.Mock()
        ctx.get_top_movers_rank.return_value = (-1, "please login first")
        with (
            mock.patch.object(moomoo, "_ensure_ctx", return_value=ctx),
            self.assertRaises(MoomooNotConfiguredError),
        ):
            moomoo.get_top_movers_moomoo(count=1)


class MoomooSdkCallTimeoutTests(unittest.TestCase):
    """The per-call wall-clock timeout wrapper (_sdk_call)."""

    def test_fast_callable_returns_result(self):
        out = moomoo._sdk_call(lambda: (0, "ok"), timeout=2.0)
        self.assertEqual(out, (0, "ok"))

    def test_slow_callable_raises_rate_limit_after_timeout(self):
        import time

        def slow():
            time.sleep(10)
            return (0, "late")

        t0 = time.time()
        with self.assertRaises(VendorRateLimitError):
            moomoo._sdk_call(slow, timeout=0.3)
        self.assertLess(time.time() - t0, 5.0)  # returned well before the call finished

    def test_exception_in_callable_propagates(self):
        def boom():
            raise ValueError("boom")

        with self.assertRaises(ValueError):
            moomoo._sdk_call(boom, timeout=2.0)

    def test_timeout_from_config(self):
        import time

        set_config({"moomoo_call_timeout": 0.2})
        t0 = time.time()
        with self.assertRaises(VendorRateLimitError):
            moomoo._sdk_call(lambda: time.sleep(10))
        self.assertLess(time.time() - t0, 5.0)

    def test_timeout_closes_context(self):
        import time

        with (
            mock.patch.object(moomoo, "_close_ctx") as close_mock,
            self.assertRaises(VendorRateLimitError),
        ):
            moomoo._sdk_call(lambda: time.sleep(10), timeout=0.2)
        close_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()

"""Regression tests for the audit-phase yfinance/stockstats indicator guard.

The yfinance indicator adapter used to swallow every failure: the bulk path
printed to stdout and fell through to the per-date helper, which printed and
returned "" — so a broken computation (bad indicator name, stockstats error,
upstream data problem) was returned as a normal success string of blank
"date: " rows. The router caches any non-sentinel string for its TTL, so the
analyst then read the blanks as data.

Fixed contract: a failed computation raises ``NoMarketDataError`` (logged, never
printed) so the router degrades it through the typed no-data / sentinel channel
and a good computation renders exactly the rows it did before.

(The companion guardrail change — severity >= HIGH caps the rating — is covered
by ``tests/test_decision_guardrail.py::TestRiskCap``.)
"""

from unittest import mock

import pytest

import tradingagents.dataflows.config as config_module
import tradingagents.dataflows.y_finance as y_finance
from tradingagents.dataflows import interface
from tradingagents.dataflows.config import set_config
from tradingagents.dataflows.stockstats_utils import StockstatsUtils
from tradingagents.dataflows.symbol_utils import NoMarketDataError

pytestmark = pytest.mark.timeout(30)

# One good bulk result, shaped exactly like ``_get_stock_stats_bulk`` returns.
GOOD_BULK = {"2026-06-11": "55.5", "2026-06-10": "54.25"}


@pytest.mark.unit
class TestIndicatorDegradation:
    def test_good_computation_renders_the_same_rows(self):
        with mock.patch.object(y_finance, "_get_stock_stats_bulk", return_value=GOOD_BULK):
            out = y_finance.get_stock_stats_indicators_window("AAPL", "rsi", "2026-06-11", 1)

        assert out.startswith("## rsi values from 2026-06-10 to 2026-06-11:\n\n")
        assert "2026-06-11: 55.5\n" in out
        assert "2026-06-10: 54.25\n" in out
        # The trailing per-indicator description is preserved verbatim.
        assert out.rstrip().endswith("always cross-check with trend analysis.")

    def test_bulk_failure_raises_typed_error_not_a_blank_report(self, capsys):
        def _boom(*args, **kwargs):
            raise RuntimeError("stockstats exploded")

        with (
            mock.patch.object(y_finance, "_get_stock_stats_bulk", _boom),
            mock.patch.object(StockstatsUtils, "get_stock_stats", _boom),
            pytest.raises(NoMarketDataError),
        ):
            y_finance.get_stock_stats_indicators_window("AAPL", "rsi", "2026-06-11", 2)

        assert capsys.readouterr().out == ""  # logged, never printed to stdout

    def test_per_date_helper_failure_is_typed(self):
        with (
            mock.patch.object(
                StockstatsUtils, "get_stock_stats", side_effect=RuntimeError("no rows")
            ),
            pytest.raises(NoMarketDataError) as ctx,
        ):
            y_finance.get_stockstats_indicator("AAPL", "rsi", "2026-06-11")
        assert "rsi" in str(ctx.value)

    def test_per_date_helper_success_unchanged(self):
        with mock.patch.object(StockstatsUtils, "get_stock_stats", return_value=42.5):
            assert y_finance.get_stockstats_indicator("AAPL", "rsi", "2026-06-11") == "42.5"

    def test_unsupported_indicator_is_typed_no_data(self):
        with pytest.raises(NoMarketDataError):
            y_finance.get_stock_stats_indicators_window("AAPL", "made_up", "2026-06-11", 1)


@pytest.mark.unit
class TestIndicatorRouting:
    def setup_method(self):
        config_module.reset_config()

    def teardown_method(self):
        config_module.reset_config()

    def test_broken_indicator_degrades_to_sentinel(self):
        set_config({"data_vendors": {"technical_indicators": "yfinance"}})

        def _broken(symbol, indicator, curr_date, look_back_days):
            raise NoMarketDataError(
                symbol, detail=f"stockstats indicator {indicator!r} computation failed"
            )

        with mock.patch.dict(
            interface.VENDOR_METHODS,
            {"get_indicators": {"yfinance": _broken}},
            clear=False,
        ):
            out = interface.route_to_vendor("get_indicators", "AAPL", "rsi", "2026-06-11", 5)

        # A sentinel, never a served success string (which the cache would keep).
        assert out.startswith("NO_DATA_AVAILABLE")
        assert "computation failed" in out

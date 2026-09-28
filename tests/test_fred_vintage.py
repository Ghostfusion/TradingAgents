"""FRED vintage pinning: a historical request must not serve today's revision.

``observation_start``/``observation_end`` bound the *observation* date, not the
data vintage: without ``realtime_start``/``realtime_end`` FRED serves every row
as revised *today*, so a 2020 backtest sees numbers nobody had in 2020. These
tests monkeypatch ``_request`` and assert on the outgoing params, so they are
deterministic and never touch the network.
"""

from datetime import date, timedelta

import pytest

from tradingagents.dataflows import fred

pytestmark = pytest.mark.timeout(600)

# The Nov-2019 CPI print as it stood in the 2020-01-01 vintage (today's revised
# row is 257.879) -- a vintage pin must return this number, not the revision.
_META = {
    "seriess": [
        {
            "title": "Consumer Price Index",
            "units_short": "Index 1982-1984=100",
            "frequency": "Monthly",
        }
    ]
}
_OBS = {"observations": [{"date": "2019-11-01", "value": "257.936"}]}


def _capture(monkeypatch, *, meta=None, obs=None):
    """Replace ``_request`` and return a dict of {path: params} capture."""
    captured = {}
    meta = _META if meta is None else meta
    obs = _OBS if obs is None else obs

    def _impl(path, params):
        captured[path] = dict(params)
        if path == "series":
            return meta
        if path == "series/observations":
            return obs
        raise AssertionError(f"unexpected FRED path: {path}")

    monkeypatch.setattr(fred, "_request", _impl)
    return captured


def _today() -> str:
    return date.today().strftime("%Y-%m-%d")


@pytest.mark.unit
class TestVintageParamsTests:
    def test_past_asof_pins_both_realtime_bounds_to_it(self):
        params = fred._vintage_params("2020-01-01")
        # FRED convention: realtime_start == realtime_end == as-of selects the
        # vintage as it stood that day (observed live on CPIAUCSL/DGS10/T10Y2Y).
        assert params == {"realtime_start": "2020-01-01", "realtime_end": "2020-01-01"}

    def test_yesterday_is_pinned(self):
        yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        assert fred._vintage_params(yesterday)["realtime_start"] == yesterday

    def test_today_is_unpinned(self):
        # A live run must stay byte-identical: today's vintage *is* the request.
        assert fred._vintage_params(_today()) == {}

    def test_future_asof_is_unpinned(self):
        assert fred._vintage_params("2999-12-31") == {}

    def test_malformed_asof_is_unpinned(self):
        assert fred._vintage_params("not-a-date") == {}
        assert fred._vintage_params("") == {}


@pytest.mark.unit
class TestVintageRequestTests:
    def test_series_values_pins_vintage_for_a_past_asof(self, monkeypatch):
        captured = _capture(monkeypatch)
        rows = fred.get_series_values("cpi", "2020-01-01")
        assert rows == [("2019-11-01", 257.936)]
        params = captured["series/observations"]
        assert params["realtime_start"] == "2020-01-01"
        assert params["realtime_end"] == "2020-01-01"

    def test_macro_value_pins_vintage_for_a_past_asof(self, monkeypatch):
        captured = _capture(monkeypatch)
        assert fred.get_macro_value("cpi", "2020-01-01") == 257.936
        params = captured["series/observations"]
        assert params["realtime_start"] == "2020-01-01"
        assert params["realtime_end"] == "2020-01-01"

    def test_today_asof_leaves_both_accessors_unpinned(self, monkeypatch):
        today = _today()
        captured = _capture(monkeypatch)
        fred.get_series_values("cpi", today)
        fred.get_macro_value("cpi", today)
        params = captured["series/observations"]
        assert "realtime_start" not in params
        assert "realtime_end" not in params
        assert params["observation_end"] == today

    def test_future_asof_leaves_the_request_unpinned(self, monkeypatch):
        captured = _capture(monkeypatch)
        fred.get_series_values("cpi", "2999-12-31")
        params = captured["series/observations"]
        assert "realtime_start" not in params
        assert "realtime_end" not in params

    def test_vintage_never_exceeds_observation_end(self, monkeypatch):
        # The pin must equal the as-of date (not a second request / a wider
        # vintage range that would reintroduce the revision leak).
        captured = _capture(monkeypatch)
        fred.get_series_values("CPIAUCSL", "2020-01-01")
        params = captured["series/observations"]
        assert params["realtime_end"] == params["observation_end"]

    def test_metadata_request_is_not_vintage_pinned(self, monkeypatch):
        # Only the observations endpoint carries as-of semantics; the series
        # metadata call is left alone, and the pin is confined to one place.
        captured = _capture(monkeypatch)
        fred.get_macro_value("cpi", "2020-01-01")
        assert "realtime_start" not in captured["series"]
        assert "realtime_end" not in captured["series"]
        assert captured["series/observations"]["realtime_start"] == "2020-01-01"


@pytest.mark.unit
class TestAliasAndWindowTests:
    def test_alias_and_lookback_window_survive_the_pin(self, monkeypatch):
        captured = _capture(monkeypatch)
        fred.get_series_values("unemployment", "2025-01-31", 90)
        params = captured["series/observations"]
        assert params["series_id"] == "UNRATE"
        assert params["observation_end"] == "2025-01-31"
        assert params["observation_start"] == "2024-11-02"
        assert params["realtime_start"] == "2025-01-31"

    def test_no_lookback_means_no_observation_start(self, monkeypatch):
        captured = _capture(monkeypatch)
        fred.get_series_values("10y_treasury", "2025-01-31")
        params = captured["series/observations"]
        assert params["series_id"] == "DGS10"
        assert "observation_start" not in params
        assert params["realtime_end"] == "2025-01-31"

    def test_macro_report_pins_vintage_and_keeps_the_window(self, monkeypatch):
        captured = _capture(monkeypatch)
        out = fred.get_macro_data("cpi", "2025-01-31", 90)
        params = captured["series/observations"]
        assert params["observation_start"] == "2024-11-02"
        assert params["observation_end"] == "2025-01-31"
        assert params["realtime_start"] == "2025-01-31"
        assert "257.936" in out

    def test_macro_report_today_stays_unpinned(self, monkeypatch):
        captured = _capture(monkeypatch)
        fred.get_macro_data("cpi", _today(), 90)
        params = captured["series/observations"]
        assert "realtime_start" not in params
        assert "realtime_end" not in params
